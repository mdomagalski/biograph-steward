"""Explicit choices guard invented model responses; no model or source network."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import PharosClient, digest
from biograph_steward.assay_attachment import attach_assay
from biograph_steward.construction import run_planned_construction, verify_construction_run
from biograph_steward.construction_planning import (
    POLICY as MODEL_POLICY, save_construction_plan, verify_construction_plan_trace,
)
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.graph import save_run
from biograph_steward.guided_construction import (
    POLICY, guard_construction_trace, validate_guided_selection,
    verify_guided_construction_trace,
)
from biograph_steward.reviews import preserve_construction_plan, read_run, review_run
from test_construction_planning import abstention, planner, proposal, reseal, scope
from test_pharos_inventory import InventoryAPI
from test_assay_attachment import make_publication


def selected(**changes):
    return {"accessions": ["P04637", "P00533", "P01116"],
            "focus_uniprot": "P04637", "profile": "ppi",
            "relations": ["interactions"], **changes}


class GuidedConstructionTests(unittest.TestCase):
    def test_v3_trace_and_attribution_remain_unchanged(self):
        original = planner(proposal()).plan(scope())
        before = deepcopy(original)
        selection = selected()
        guarded = guard_construction_trace(original, selection)
        self.assertEqual(original, before)
        self.assertEqual(guarded["model_trace"], before)
        self.assertEqual(guarded["model_trace_sha256"], digest(before))
        from biograph_steward.file_utils import sha
        from biograph_steward import guided_construction
        self.assertEqual(guarded["selection_guard_implementation_sha256"],
                         sha(Path(guided_construction.__file__)))
        self.assertEqual(original["format"], MODEL_POLICY)
        self.assertEqual(guarded["format"], POLICY)
        self.assertEqual(verify_construction_plan_trace(before), selected())
        self.assertEqual(verify_construction_plan_trace(guarded), selected())
        for key in ("planner_kind", "provider_requested", "model_requested", "model_returned",
                    "usage", "latency_ms", "model_calls", "transport_requests"):
            self.assertEqual(guarded[key], original[key])
        self.assertIs(guarded["explicit_selection_agreement"], True)
        self.assertEqual(guarded["source_calls"], 0)
        self.assertFalse(guarded["scientific_accuracy_evaluated"])
        self.assertIn("arbitrary natural-language", guarded["semantic_intent_validation"])
        self.assertEqual(selection, selected())

    def test_complete_selection_uses_existing_bounds_and_canonical_order(self):
        request = selected(profile="context", relations=["interactions", "shared_pathways"])
        trace = planner(proposal(**request)).plan(scope())
        selection = {**request, "accessions": list(reversed(request["accessions"])),
                     "relations": list(reversed(request["relations"]))}
        guarded = guard_construction_trace(trace, selection)
        self.assertEqual(guarded["exact_selection"], request)
        self.assertEqual(guarded["supplied_selection"], selection)
        self.assertEqual(verify_guided_construction_trace(guarded), request)
        invalid = [None, {}, {**selected(), "assay": "Y2H"},
                   selected(accessions=["TP53"]), selected(accessions=["P04637", "P04637"]),
                   selected(accessions=["P04637", "P15056"]), selected(focus_uniprot="P15056"),
                   selected(profile="ppi", relations=["shared_pathways"])]
        for selection in invalid:
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                validate_guided_selection(scope(), selection)

    def test_matching_subset_and_selected_focus_remain_permitted(self):
        request = selected(accessions=["P04637", "P00533"], focus_uniprot="P00533")
        trace = planner(proposal(**request)).plan(scope())
        self.assertEqual(verify_guided_construction_trace(
            guard_construction_trace(trace, request)), request)

    def test_every_choice_mismatch_is_rejected_without_repair_or_retrieval(self):
        cases = [
            (proposal(), selected(accessions=["P04637", "P00533"])),
            (proposal(), selected(focus_uniprot="P00533")),
            (proposal(), selected(profile="context")),
            (proposal(profile="context", relations=["interactions", "shared_pathways"]),
             selected(profile="context", relations=["shared_pathways"])),
        ]
        for output, selection in cases:
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as temporary:
                original = planner(output).plan(scope())
                guarded = guard_construction_trace(original, selection)
                self.assertEqual(guarded["status"], "invalid_plan")
                self.assertIs(guarded["explicit_selection_agreement"], False)
                self.assertEqual(guarded["model_construction_request"], original["construction_request"])
                self.assertIsNone(guarded["validated_plan"])
                self.assertIsNone(guarded["construction_request"])
                self.assertIsNone(verify_construction_plan_trace(guarded))
                api = InventoryAPI()
                with self.assertRaises(ValueError):
                    run_planned_construction(PharosClient(transport=api), guarded,
                                             Path(temporary) / "blocked")
                self.assertEqual(api.calls, [])
                self.assertFalse((Path(temporary) / "blocked").exists())

    def test_abstention_invalid_plan_and_planner_error_remain_nonexecutable(self):
        traces = [planner(abstention()).plan(scope()),
                  planner(proposal(profile="unavailable")).plan(scope())]
        failed = deepcopy(traces[-1])
        failed.update(status="planner_error", proposed_plan=None)
        traces.append(reseal(failed))
        for original in traces:
            with self.subTest(status=original["status"]):
                guarded = guard_construction_trace(original, selected())
                self.assertEqual(guarded["status"], original["status"])
                self.assertIsNone(guarded["explicit_selection_agreement"])
                self.assertIsNone(verify_guided_construction_trace(guarded))

    def test_outer_and_inner_integrity_are_independently_rechecked(self):
        guarded = guard_construction_trace(planner(proposal()).plan(scope()), selected())
        cases = []
        for field, value in [("status", "abstained"), ("construction_request", None),
                             ("explicit_selection_agreement", False), ("source_calls", 1),
                             ("planner_kind", "live_model"), ("usage", {}),
                             ("scope", scope(question="Different question")),
                             ("exact_selection", selected(profile="context")),
                             ("selection_guard_implementation_sha256", "0" * 64),
                             ("model_trace_sha256", "0" * 64)]:
            changed = deepcopy(guarded)
            changed[field] = value
            cases.append(reseal(changed))
        changed = deepcopy(guarded)
        changed["model_trace"]["construction_request"]["profile"] = "context"
        cases.append(reseal(changed))
        changed = deepcopy(guarded)
        changed["unverified_extra"] = True
        cases.append(reseal(changed))
        for changed in cases:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                verify_guided_construction_trace(changed)
        unchanged = deepcopy(guarded)
        unchanged["content_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_guided_construction_trace(unchanged)

    def test_wrapper_cannot_nest_or_promote_experimental_trace(self):
        guarded = guard_construction_trace(planner(proposal()).plan(scope()), selected())
        with self.assertRaises(ValueError):
            guard_construction_trace(guarded, selected())
        for format in ("biograph-steward.nemotron-construction-tool.v2", "unknown"):
            trace = deepcopy(guarded["model_trace"])
            trace["format"] = format
            with self.assertRaises(ValueError):
                guard_construction_trace(reseal(trace), selected())


class GuidedPublicationTests(unittest.TestCase):
    def test_guard_survives_plan_save_publication_packet_review_and_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            request = selected(accessions=["P04637", "P00533"])
            trace = planner(proposal(**request)).plan(scope(accessions=request["accessions"]))
            guarded = guard_construction_trace(trace, request)
            saved = root / "plan/construction_planner_trace.json"
            save_construction_plan(guarded, saved)
            raw = saved.read_bytes()
            built = root / "published"
            result = run_planned_construction(PharosClient(transport=InventoryAPI()), guarded, built)
            self.assertEqual(verify_construction_run(built)["request"], request)
            self.assertEqual((built / "construction_planner_trace.json").read_bytes(), raw)
            packet = built / "gold_packet"
            load_packet(packet)
            self.assertEqual((packet / "source/construction_planner_trace.json").read_bytes(), raw)
            assertion = result["graph"]["assertions"][0]
            reviewed = root / "reviewed"
            review_run(built, reviewed, assertion["id"], "provisional", "Fixture reviewer", "Inspect source")
            replay = root / "replayed"
            snapshot, events, _ = read_run(reviewed)
            save_run(snapshot, replay, review_events=events)
            preserve_construction_plan(reviewed, replay)
            for index, folder in enumerate((reviewed, replay)):
                self.assertEqual((folder / "construction_planner_trace.json").read_bytes(), raw)
                self.assertEqual(read_run(folder)[2]["construction"]["request"], request)
                exported = root / ("export_" + str(index))
                export_packet(folder, exported)
                load_packet(exported)
                self.assertEqual((exported / "source/construction_planner_trace.json").read_bytes(), raw)

    def test_assay_attachment_also_preserves_guard_in_source_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            request = selected(accessions=["P04637", "P00533"])
            trace = planner(proposal(**request)).plan(scope(accessions=request["accessions"]))
            guarded = guard_construction_trace(trace, request)
            built, publication, attached = [root / name for name in ("built", "assay", "attached")]
            run_planned_construction(PharosClient(transport=InventoryAPI()), guarded, built)
            raw = (built / "construction_planner_trace.json").read_bytes()
            make_publication(publication)
            attach_assay(built, publication, attached)
            self.assertEqual((attached / "construction_planner_trace.json").read_bytes(), raw)
            read_run(attached)
            exported = root / "export"
            export_packet(attached, exported)
            load_packet(exported)
            self.assertEqual((exported / "source/construction_planner_trace.json").read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
