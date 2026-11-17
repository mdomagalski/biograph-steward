"""Frozen sample, exact-review and paired-policy verification controls."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet, go_ontology_qualification as go
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from test_go_ontology_qualification import ontology_fixture
from test_normalization import fixture, resign
from tools.sampled_audit.prepare import prepare, write_jsonl
from tools.sampled_audit import score as scoring


class AuditScoringTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.packet, self.audit, self.review_path, self.output = (self.root / name for name in ("packet", "audit", "reviews.jsonl", "score"))
        source = fixture()
        for target in source["targets"]:
            target["pharos_context"]["go"] = []
        source["targets"][0]["pharos_context"]["go"] = [
            {"goid": f"GO:{i:07d}", "type": "P", "term": "Invented term " + str(i),
             "evidence": "IDA", "goeco": "ECO:0000314", "assigned_by": "INVENTED"}
            for i in (1, 2)]
        self.graph = save_run(resign(source), self.root / "run")
        self.manifest = gold_packet.export_packet(self.root / "run", self.packet)
        allocation = {}
        for a in self.graph["assertions"]:
            allocation[a["kind"]] = allocation.get(a["kind"], 0) + 1
        self.sample_report = prepare(self.packet, allocation, 81, self.audit)
        self.protocol = gold_packet._read(self.audit / "protocol.json")
        self.reviews = scoring.rows(self.audit / "reviews.template.jsonl")
        for row in self.reviews:
            row.update(source_relative_support="supported", primary_evidence_support="unresolved",
                       review_actor="Invented audit actor", source_relative_reason="Invented source-fidelity outcome for software control.",
                       primary_evidence_reason="No primary scientific judgment in this invented control.",
                       evidence_basis=[{"kind": "synthetic_source_dossier", "locator": row["case_id"]}])
        write_jsonl(self.review_path, self.reviews)

    def test_direct_script_directory_does_not_shadow_standard_library_statistics(self):
        repository = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-c",
            "import sys; sys.path.insert(0, " + repr(str(repository)) + "); "
            "import statistics; from biograph_steward import cohort_mapping; "
            "assert statistics.median([1,3,5]) == 3; "
            "assert cohort_mapping.statistics is statistics; print('standard-library statistics preserved')"],
            cwd=repository / "tools/sampled_audit", capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("standard-library statistics preserved", result.stdout)

    def reseal_audit(self):
        report = gold_packet._read(self.audit / "sample_manifest.json")
        report["files"] = {p.relative_to(self.audit).as_posix(): sha(p)
                           for p in self.audit.rglob("*") if p.is_file() and p.name != "sample_manifest.json"}
        report.pop("content_sha256")
        report["content_sha256"] = digest(report)
        write_json(self.audit / "sample_manifest.json", report)

    def test_complete_source_bound_review_scores_without_creating_biological_accuracy(self):
        before = {p: sha(p) for parent in (self.packet, self.audit) for p in parent.rglob("*") if p.is_file()}
        report = scoring.score(self.audit, self.packet, self.review_path, self.output)
        self.assertEqual(report["sampled_assertions"], len(self.graph["assertions"]))
        self.assertTrue(report["sample_selection_and_dossiers_replayed"])
        self.assertTrue(report["complete_review_binding_verified"])
        self.assertFalse(report["scientific_accuracy_measured"])
        self.assertIsNone(report["statistics"]["independent_scientific_correctness"]["accuracy_estimate"])
        self.assertEqual((self.output / "reviews.jsonl").read_bytes(), self.review_path.read_bytes())
        self.assertEqual(report["content_sha256"], digest({k: v for k, v in report.items() if k != "content_sha256"}))
        self.assertEqual({p: sha(p) for p in before}, before)

    def test_explicit_renderer_keeps_complete_frozen_dossier_validation(self):
        called = []
        def reader(graph, selection):
            called.append(selection)
            return scoring.inspect_selection(graph, selection)
        report, _, _, _, sample = scoring.load_frozen(self.audit, self.packet, inspection_reader=reader)
        self.assertEqual(len(called), len(sample))
        self.assertEqual(report['sample_id'], self.sample_report['sample_id'])
        with self.assertRaisesRegex(ValueError, 'full source assertion/evidence'):
            scoring.load_frozen(self.audit, self.packet, inspection_reader=lambda graph, selection: {})
        with self.assertRaisesRegex(ValueError, 'callable'):
            scoring.load_frozen(self.audit, self.packet, inspection_reader='unqualified renderer')

    def test_wrong_case_assertion_sample_dossier_or_actor_fails_before_output(self):
        original = deepcopy(self.reviews)
        for key, value in (("case_id", "absent"), ("assertion_id", "another"), ("stratum", "other"),
                           ("sample_id", "audit:other"), ("dossier_content_sha256", "0" * 64),
                           ("review_actor", ""), ("evidence_basis", []),
                           ("primary_evidence_reason", None), ("independent_scientific_correctness", "supported")):
            reviews = deepcopy(original)
            reviews[0][key] = value
            write_jsonl(self.review_path, reviews)
            with self.subTest(key=key), self.assertRaises(ValueError):
                scoring.score(self.audit, self.packet, self.review_path, self.output)
            self.assertFalse(self.output.exists())

    def test_missing_review_never_becomes_a_smaller_denominator(self):
        write_jsonl(self.review_path, self.reviews[:-1])
        with self.assertRaisesRegex(ValueError, "every frozen case"):
            scoring.score(self.audit, self.packet, self.review_path, self.output)
        self.assertFalse(self.output.exists())

    def test_coherently_resealed_dossier_change_is_rejected_against_original_source(self):
        sample = scoring.rows(self.audit / "sample.jsonl")
        row = sample[0]
        dossier_path = self.audit / row["dossier_path"]
        dossier = gold_packet._read(dossier_path)
        dossier["assertion"]["predicate"] = "invented:changed_claim"
        dossier["assertion_content_sha256"] = digest(dossier["assertion"])
        dossier.pop("content_sha256")
        dossier["content_sha256"] = digest(dossier)
        write_json(dossier_path, dossier)
        row["dossier_content_sha256"] = dossier["content_sha256"]
        write_jsonl(self.audit / "sample.jsonl", sample)
        self.reseal_audit()
        with self.assertRaisesRegex(ValueError, "full source assertion"):
            scoring.load_frozen(self.audit, self.packet)

    def test_coherently_resealed_inclusion_weight_or_seed_cannot_select_a_new_sample(self):
        sample = scoring.rows(self.audit / "sample.jsonl")
        sample[0]["inverse_inclusion_weight"] *= 2
        write_jsonl(self.audit / "sample.jsonl", sample)
        self.reseal_audit()
        with self.assertRaisesRegex(ValueError, "probabilities"):
            scoring.load_frozen(self.audit, self.packet)

    def test_extra_empty_directory_or_symlink_is_not_part_of_frozen_inventory(self):
        extra = self.audit / "empty"
        extra.mkdir()
        with self.assertRaisesRegex(ValueError, "directory inventory"):
            scoring.load_frozen(self.audit, self.packet)
        extra.rmdir()
        linked = self.root / "audit_link"
        linked.symlink_to(self.audit, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "directory must be ordinary"):
            scoring.load_frozen(linked, self.packet)

    def test_source_change_during_export_never_gets_a_completed_report(self):
        original_write = scoring.write_json
        def mutate(path, value):
            result = original_write(path, value)
            if Path(path).name == "statistics.json":
                self.review_path.write_bytes(self.review_path.read_bytes() + b"\n")
            return result
        with patch.object(scoring, "write_json", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "changed during scoring export"):
                scoring.score(self.audit, self.packet, self.review_path, self.output)
        self.assertFalse((self.output / "report.json").exists())

    def make_intervention(self):
        ontology = self.root / "invented_ontology.json.gz"
        ontology.write_bytes(gzip.compress(json.dumps(ontology_fixture()).encode(), mtime=0))
        self.qualification = self.root / "qualification"
        qualified = go.qualify_go_ontology(self.packet, ontology, self.qualification, ontology_sha256=sha(ontology))
        self.qualification_pin = sha(self.qualification / "go_ontology_qualification.json")
        self.binding = self.root / "intervention_binding.json"
        value = {"format": "biograph-steward.sampled-audit-intervention-binding.v1",
            "sample_id": self.sample_report["sample_id"], "sample_manifest_content_sha256": self.sample_report["content_sha256"],
            "sample_protocol_content_sha256": self.protocol["content_sha256"],
            "baseline_packet_id": self.manifest["packet_id"], "baseline_graph_sha256": self.manifest["graph_sha256"],
            "policy": go.PROFILE, "policy_implementation_sha256": qualified["implementation_sha256"],
            "qualification_report_content_sha256": qualified["content_sha256"],
            "qualification_report_file_sha256": self.qualification_pin,
            "ontology_source_sha256": qualified["ontology"]["file_sha256"],
            "retained_report_content_sha256": qualified["retained_report_sha256"],
            "policy_or_threshold_tuned_for_sample": False, "sample_changed": False}
        value["content_sha256"] = digest(value)
        write_json(self.binding, value)

    def test_paired_GO_ontology_and_full_disposition_replay_preserve_claim_semantics(self):
        self.make_intervention()
        report = scoring.score(self.audit, self.packet, self.review_path, self.output,
            go_qualification=self.qualification, go_qualification_report_sha256=self.qualification_pin,
            intervention_binding=self.binding)
        self.assertEqual(report["intervention"]["removed_assertions"], 1)
        self.assertTrue(report["intervention"]["source_ontology_classification_replayed"])
        self.assertTrue(report["intervention"]["complete_Gold_disposition_replayed"])
        self.assertFalse(report["intervention"]["independent_biological_pruning_gain_established"])
        paired = scoring.rows(self.output / "paired_cases.jsonl")
        self.assertEqual(sum(not row["retained"] for row in paired), 1)
        removed = report["statistics"]["axes"]["source_relative_support"]["paired_intervention"]
        self.assertEqual(removed["sample_counts_removed"]["supported"], 1)
        self.assertFalse(removed["biological_error_removal_or_valid_claim_loss_established"])

    def test_intervention_pins_or_another_binding_cannot_be_substituted(self):
        self.make_intervention()
        with self.assertRaisesRegex(ValueError, "report bytes"):
            scoring.score(self.audit, self.packet, self.review_path, self.output,
                go_qualification=self.qualification, go_qualification_report_sha256="0" * 64,
                intervention_binding=self.binding)
        binding = gold_packet._read(self.binding)
        binding["sample_id"] = "audit:other"
        binding.pop("content_sha256")
        binding["content_sha256"] = digest(binding)
        write_json(self.binding, binding)
        with self.assertRaisesRegex(ValueError, "binding differs"):
            scoring.score(self.audit, self.packet, self.review_path, self.output,
                go_qualification=self.qualification, go_qualification_report_sha256=self.qualification_pin,
                intervention_binding=self.binding)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
