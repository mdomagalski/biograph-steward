"""Invented sources test task selection and immutable Gold support, not biology."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet, signor_source as signor
from biograph_steward import task_qualification as qualification
from biograph_steward.evidence_extension import publish_extension
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from biograph_steward.reviews import review_run
from test_assay_attachment import cohort_snapshot
from test_signor_source import source_bytes, source_row


def inventory(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in folder.rglob("*") if p.is_file()}


class SourceFieldQualificationTests(unittest.TestCase):
    def test_explicit_compatible_fields_and_phosphate_removal_are_task_eligible(self):
        for mechanism in qualification.ALLOWED_MECHANISMS:
            value = qualification.classify_source_fields(source_row(1, MECHANISM=mechanism))
            self.assertEqual(value["decision"], "keep")
            self.assertEqual(value["reason_codes"], ["source_fields_match_named_task"])

    def test_unknowns_are_not_an_implicit_complement_of_the_allowed_vocabulary(self):
        changes = [{"DIRECT": ""}, {"DIRECT": "unknown"}, {"MECHANISM": ""},
                   {"MECHANISM": "unrecognized process"}, {"MECHANISM": "Phosphorylation"},
                   {"TAX_ID": "-1"}, {"TAX_ID": ""}, {"TAX_ID": "human"}]
        for change in changes:
            with self.subTest(change=change):
                result = qualification.classify_source_fields(source_row(1, **change))
                self.assertEqual(result["decision"], "abstain")
                self.assertFalse(result["incompatibility_reasons"])
        missing = source_row(1)
        del missing["DIRECT"]
        self.assertEqual(qualification.classify_source_fields(missing)["decision"], "abstain")
        # Do not relax the actual native-release reader to admit an invalid release.
        with self.assertRaisesRegex(ValueError, "unknown directness"):
            signor.parse_release(source_bytes([source_row(1, DIRECT="")]), ["P00533", "P01116"])

    def test_known_incompatibility_has_exact_reasons_and_does_not_disappear_with_unknowns(self):
        for mechanism in qualification.INCOMPATIBLE_MECHANISMS:
            result = qualification.classify_source_fields(source_row(1, MECHANISM=mechanism))
            self.assertEqual(result["decision"], "prune")
            self.assertEqual(result["incompatibility_reasons"], ["source_mechanism_outside_phosphoregulation"])
        result = qualification.classify_source_fields(source_row(1, DIRECT="f", TAX_ID="10090", MECHANISM=""))
        self.assertEqual(result["decision"], "prune")
        self.assertEqual(result["incompatibility_reasons"],
                         ["source_explicit_indirect", "source_experimental_organism_other_than_human"])
        self.assertEqual(result["unknown_reasons"], ["source_mechanism_unreported"])
        for raw in (None, [], {"DIRECT": False}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                qualification.classify_source_fields(raw)

    def test_broad_and_unqualified_taxa_are_not_assumed_to_exclude_humans(self):
        for taxon in ("1", "9605", "40674", "9989", "99999999"):
            with self.subTest(taxon=taxon):
                result = qualification.classify_source_fields(source_row(1, TAX_ID=taxon))
                self.assertEqual(result["decision"], "abstain")
                self.assertEqual(result["unknown_reasons"], ["human_experiment_not_established"])
                self.assertFalse(result["incompatibility_reasons"])
        for taxon in qualification.INCOMPATIBLE_EXPERIMENTAL_SPECIES:
            with self.subTest(nonhuman_species=taxon):
                result = qualification.classify_source_fields(source_row(1, TAX_ID=taxon))
                self.assertEqual(result["decision"], "prune")
                self.assertEqual(result["incompatibility_reasons"],
                                 ["source_experimental_organism_other_than_human"])


class TaskQualificationPacketTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.snapshot = cohort_snapshot()
        self.source = self.root / "source_run"
        self.publication = self.root / "publication"
        self.run = self.root / "extended"
        self.packet = self.root / "packet"
        self.output = self.root / "qualified"
        rows = [source_row(1), source_row(2, DIRECT="f", SENTENCE='Invented\nmultiline "source"'),
                source_row(3, TAX_ID="-1"), source_row(4, TAX_ID="10090"),
                source_row(5, MECHANISM="unrecognized process"), source_row(6, MECHANISM="binding"),
                source_row(7, MECHANISM="dephosphorylation"), source_row(8, TAX_ID=""),
                source_row(9, MECHANISM="")]
        self.raw = source_bytes(rows)
        self.raw_path = self.root / "invented.tsv"
        self.raw_path.write_bytes(self.raw)
        pin = patch.object(signor, "RELEASE_SHA256", signor._sha(self.raw))
        pin.start(); self.addCleanup(pin.stop)
        save_run(self.snapshot, self.source)
        signor.publish_release(self.raw_path, self.snapshot, self.publication)
        graph = publish_extension(self.source, {"signor": self.publication}, self.run)
        eligible = next(e for e in graph["edges"] if e.get("observation", {}).get("source_record_id") == "SIGNOR-1")
        reviewed = self.root / "reviewed"
        self.graph = review_run(self.run, reviewed, eligible["assertion_id"], "rejected",
                                "Invented reviewer", "Fixture-only review state, not task eligibility")
        self.run = reviewed
        self.manifest = gold_packet.export_packet(self.run, self.packet)
        self.before = inventory(self.packet)

    def qualify(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("No source retrieval")):
            return qualification.qualify_task(self.packet, self.output)

    def test_complete_mixed_ledger_preserves_source_reviews_other_support_and_unknowns(self):
        report = self.qualify()
        dispositions, retained = gold_packet.load_decisions(self.output / "retained")
        source = {r["source_record_id"]: r for r in report["source_decisions"]}
        self.assertEqual(report["counts"]["source_profile"], {"keep": 2, "prune": 3, "abstain": 4})
        total = len(self.graph["edges"])
        self.assertEqual(report["counts"]["total_edges"], total)
        self.assertEqual(report["counts"]["outside_profile_abstain"], total - 9)
        self.assertEqual(report["counts"]["unknown_profile_abstain"], 4)
        self.assertEqual(sum(c["total"] for c in report["edge_family_counts"].values()), total)
        for kind, counts in report["edge_family_counts"].items():
            self.assertEqual(counts["total"], sum(counts[k] for k in ("keep", "prune", "abstain")))
            if kind != "source_regulatory_observation":
                self.assertEqual(counts["abstain"], counts["total"])
        self.assertEqual(dispositions["counts"], {"keep": 2, "prune": 3, "abstain": total - 5})
        ledger = json.loads((self.output / "decisions.json").read_text())["decisions"]
        self.assertEqual({r["edge_id"] for r in ledger}, {e["id"] for e in self.graph["edges"]})
        self.assertTrue(all(r["confidence"] is None for r in ledger))
        retained_ids = {e["id"] for e in retained["edges"]}
        self.assertNotIn(source["SIGNOR-2"]["edge_id"], retained_ids)
        self.assertIn(source["SIGNOR-1"]["edge_id"], retained_ids)  # Same protein pair, other support.
        self.assertIn(source["SIGNOR-3"]["edge_id"], retained_ids)  # In-vitro uncertainty is retained.
        self.assertIn(source["SIGNOR-5"]["edge_id"], retained_ids)  # Unknown mechanism is retained.
        self.assertEqual(retained["nodes"], self.graph["nodes"])
        eligible = next(e for e in retained["edges"] if e["id"] == source["SIGNOR-1"]["edge_id"])
        self.assertEqual(next(a for a in retained["assertions"] if a["id"] == eligible["assertion_id"])["lifecycle_state"], "rejected")
        self.assertEqual(gold_packet.load_packet(self.output / "retained/baseline_packet")[1], self.graph)
        self.assertEqual(inventory(self.packet), self.before)
        self.assertEqual(report["source_bindings"]["source_sha256"], signor._sha(self.raw))
        self.assertFalse(report["biological_truth_assessed"])
        self.assertFalse(report["independent_validation_performed"])

    def test_trace_binds_native_multiline_record_fields_and_separate_experimental_organism(self):
        report = self.qualify()
        trace = {r["source_record_id"]: r for r in report["source_decisions"]}
        self.assertEqual(trace["SIGNOR-2"]["source_data_record_ordinal"], 2)
        self.assertTrue(trace["SIGNOR-2"]["source_locator"].endswith("#data-record=2"))
        self.assertEqual(trace["SIGNOR-4"]["participant_taxon"], "NCBITaxon:9606")
        self.assertIsNone(trace["SIGNOR-4"]["assay_host_taxon"])
        self.assertEqual(trace["SIGNOR-4"]["checked_source_fields"]["TAX_ID"], "10090")
        self.assertEqual(trace["SIGNOR-4"]["decision"], "prune")
        self.assertEqual(trace["SIGNOR-3"]["decision"], "abstain")
        self.assertEqual(trace["SIGNOR-8"]["decision"], "abstain")
        self.assertEqual(report["source_bindings"]["release"], signor.RELEASE)
        self.assertEqual(report["profile_fields"]["explicit_incompatible_experimental_species"],
                         qualification.INCOMPATIBLE_EXPERIMENTAL_SPECIES)
        self.assertEqual(report["profile_fields"]["experimental_taxon_vocabulary_basis"],
                         qualification.TAXON_VOCABULARY_BASIS)
        self.assertEqual(report["content_sha256"], qualification.digest({k: v for k, v in report.items() if k != "content_sha256"}))
        self.assertEqual(report["files"]["decisions.json"], sha(self.output / "decisions.json"))

    def test_native_source_tampering_is_rejected_before_output(self):
        path = self.packet / "source/extension_sources/signor" / signor.RAW_FILE
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaises(ValueError):
            self.qualify()
        self.assertFalse(self.output.exists())

    def test_record_ordinal_raw_and_exact_edge_join_fail_closed_before_output(self):
        for field, value in (("source_data_record_ordinal", 999),
                             ("source_publication_sha256", "0" * 64),
                             ("graph_edge_id", self.graph["edges"][0]["id"])):
            graph = deepcopy(self.graph)
            obs = next(r for r in graph["extension_observations"] if r.get("source_kind") == "signor")
            if field == "graph_edge_id" and value == obs["graph_edge_id"]:
                value = "edge:missing"
            obs[field] = value
            with self.subTest(field=field), patch.object(qualification.gold_packet, "load_packet", return_value=(self.manifest, graph)):
                with self.assertRaises(ValueError): self.qualify()
            self.assertFalse(self.output.exists())
        graph = deepcopy(self.graph)
        next(r for r in graph["extension_observations"] if r.get("source_kind") == "signor")["source_row"]["DIRECT"] = "f"
        with patch.object(qualification.gold_packet, "load_packet", return_value=(self.manifest, graph)):
            with self.assertRaises(ValueError): self.qualify()
        self.assertFalse(self.output.exists())

    def test_duplicate_or_unaccounted_source_edges_are_not_silently_ignored(self):
        for variant in ("duplicate", "orphan"):
            graph = deepcopy(self.graph)
            if variant == "duplicate":
                graph["extension_observations"].append(deepcopy(graph["extension_observations"][0]))
            else:
                edge = deepcopy(next(e for e in graph["edges"] if e.get("extension_source_kind") == "signor"))
                edge["id"] = "edge:orphan"
                graph["edges"].append(edge)
            with self.subTest(variant=variant), patch.object(qualification.gold_packet, "load_packet", return_value=(self.manifest, graph)):
                with self.assertRaises(ValueError): self.qualify()
            self.assertFalse(self.output.exists())

    def test_output_must_be_new_and_outside_the_source_packet(self):
        for output in (self.packet, self.packet / "derived", self.packet.parent):
            with self.subTest(output=output), self.assertRaises(ValueError):
                qualification.qualify_task(self.packet, output)
        self.assertEqual(inventory(self.packet), self.before)

    def test_unassigned_actor_is_rejected_before_loading_or_creating_output(self):
        for actor in (None, "", " ", "Unassigned"):
            with self.subTest(actor=actor), patch.object(qualification.gold_packet, "load_packet") as loader:
                with self.assertRaises(ValueError):
                    qualification.qualify_task(self.packet, self.output, actor=actor)
                loader.assert_not_called()
            self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
