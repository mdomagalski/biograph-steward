"""Probability-design controls use invented graphs, not scientific labels."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json
from biograph_steward.demo import demo_snapshot
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from tools.reference_accuracy import design


class ReferenceDesignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.packet, self.out = [self.root / name for name in ("run", "packet", "design")]
        self.graph = save_run(demo_snapshot(), self.run)
        self.manifest = gold_packet.export_packet(self.run, self.packet)
        self.frame, _ = design.frame_for(self.graph)
        self.allocation = {row["stratum"]: 1 for row in self.frame}

    def prepare(self, **kwargs):
        return design.prepare(self.packet, self.allocation, 173, self.out, **kwargs)

    def test_strata_use_assertion_family_and_structural_disposition_not_review_labels(self):
        assertions = [{"id": "a", "kind": "pathway_membership", "evidence_edge_ids": ["e1"]},
                      {"id": "b", "kind": "pathway_membership", "evidence_edge_ids": ["e2"]},
                      {"id": "c", "kind": "go_annotation", "evidence_edge_ids": ["e3"]}]
        graph = {"assertions": assertions}
        original = deepcopy(graph)
        frame, families = design.frame_for(graph, retained_ids={"a", "c"})
        self.assertEqual({row["stratum"] for row in frame},
            {"pathway_membership::retained", "pathway_membership::pruned", "go_annotation::retained"})
        self.assertEqual(graph, original)
        self.assertEqual(families, ["go_annotation", "pathway_membership"])
        self.assertTrue(all(row["assertion_sha256"] == digest(assertions[i]) for i, row in enumerate(frame)))

    def test_draw_is_input_order_invariant_and_keeps_exact_inclusion_probabilities(self):
        allocation = {name: 1 for name in {row["stratum"] for row in self.frame}}
        first = design.selected_rows(self.frame, allocation, 71)
        second = design.selected_rows(list(reversed(self.frame)), allocation, 71)
        self.assertEqual(first, second)
        for row in first[1]:
            stratum = first[0][row["stratum"]]
            self.assertEqual(row["inclusion_probability"], {"numerator": 1, "denominator": stratum["population_size"]})
            self.assertTrue(row["case_id"].startswith("reference_"))

    def test_prepare_replays_complete_source_bound_dossiers_and_does_not_modify_inputs(self):
        before = {p.relative_to(self.packet).as_posix(): sha(p) for p in self.packet.rglob("*") if p.is_file()}
        report = self.prepare()
        replay, protocol, graph, sample = design.load_design(self.out, self.packet)
        self.assertEqual(report, replay)
        self.assertEqual(graph, self.graph)
        self.assertEqual(len(sample), len(self.allocation))
        self.assertFalse(protocol["references_or_labels_read_by_preparation"])
        self.assertIsNone(json.loads((self.out / sample[0]["dossier_path"]).read_text())["independent_scientific_judgment"])
        self.assertEqual(before, {p.relative_to(self.packet).as_posix(): sha(p) for p in self.packet.rglob("*") if p.is_file()})
        with self.assertRaises(ValueError):
            self.prepare()

    def test_assertion_with_surviving_evidence_is_retained_and_pruned_unit_is_not_dropped(self):
        multi = next(a for a in self.graph["assertions"] if len(a["evidence_edge_ids"]) > 1)
        single = next(a for a in self.graph["assertions"] if len(a["evidence_edge_ids"]) == 1)
        removed = {multi["evidence_edge_ids"][0], single["evidence_edge_ids"][0]}
        decisions, retained = self.root / "decisions.json", self.root / "retained"
        write_json(decisions, {"format": gold_packet.DECISION_FORMAT, "packet_id": self.manifest["packet_id"],
            "method": "invented structural intervention", "actor": "invented fixture", "decisions": [
                {"edge_id": e["id"], "decision": "prune" if e["id"] in removed else "abstain",
                 "reason": "invented fixture decision; no biological claim", "confidence": None} for e in self.graph["edges"]]})
        gold_packet.save_decisions(self.packet, decisions, retained)
        _, _, surviving, _, _ = design.source_inputs(self.packet, retained, sha(retained / "report.json"))
        frame, _ = design.frame_for(self.graph, retained_ids=surviving)
        by_id = {row["assertion_id"]: row for row in frame}
        self.assertEqual(by_id[multi["id"]]["disposition"], "retained")
        self.assertEqual(by_id[single["id"]]["disposition"], "pruned")
        self.assertEqual(len(frame), len(self.graph["assertions"]))

    def test_family_scope_is_declared_and_unsupported_or_empty_scope_fails(self):
        kind = self.graph["assertions"][0]["kind"]
        frame, _ = design.frame_for(self.graph, families=[kind])
        allocation = {frame[0]["stratum"]: len(frame)}
        report = design.prepare(self.packet, allocation, 0, self.out, families=[kind])
        _, protocol, _, _ = design.load_design(self.out, self.packet)
        self.assertEqual(report["population_size"], len(frame))
        self.assertEqual(protocol["outside_domain_assertions"], len(self.graph["assertions"]) - len(frame))
        for families in ([], ["invented_unknown_family"], [kind, kind]):
            with self.subTest(families=families), self.assertRaises(ValueError):
                design.frame_for(self.graph, families=families)

    def test_resealed_changed_weights_or_source_case_still_fails_replay(self):
        self.prepare()
        sample = design.read_rows(self.out / "sample.jsonl")
        sample[0]["inclusion_probability"]["numerator"] += 1
        design.write_jsonl(self.out / "sample.jsonl", sample)
        report = json.loads((self.out / design.MANIFEST).read_text())
        report["files"]["sample.jsonl"] = sha(self.out / "sample.jsonl")
        report.pop("content_sha256"); report["content_sha256"] = digest(report)
        write_json(self.out / design.MANIFEST, report)
        with self.assertRaisesRegex(ValueError, "case/dossier"):
            design.load_design(self.out, self.packet)

    def test_preparation_boundary_cannot_be_resealed_into_a_scientific_result(self):
        self.prepare()
        report = json.loads((self.out / design.MANIFEST).read_text())
        report["scientific_accuracy_measured"] = True
        report.pop("content_sha256"); report["content_sha256"] = digest(report)
        write_json(self.out / design.MANIFEST, report)
        with self.assertRaisesRegex(ValueError, "boundary"):
            design.load_design(self.out, self.packet)

    def test_changed_source_during_preparation_has_no_success_manifest(self):
        write = design.write_jsonl
        def changed(path, values):
            result = write(path, values)
            if Path(path).name == "sample.jsonl":
                file = self.packet / "packet_manifest.json"
                file.write_bytes(file.read_bytes() + b"\n")
            return result
        with patch.object(design, "write_jsonl", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "changed during"):
                self.prepare()
        self.assertFalse((self.out / design.MANIFEST).exists())


if __name__ == "__main__":
    unittest.main()
