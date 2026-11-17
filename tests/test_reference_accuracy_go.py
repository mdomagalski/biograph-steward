"""Invented native records exercise eligibility, never furnish scientific gold."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from biograph_steward import go_qualification as native
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from tools.reference_accuracy import go_reference as ref, design, score
import test_go_context_inspection as fixtures
from test_go_native_qualification import record, edge


def positive(**changes):
    values = {"3": "enables", "6": "IDA", "7": "", "12": "taxon:9606", "15": "", "16": ""}
    values.update(changes)
    return record(**values)


def graph_for(rows):
    e = edge(evidence_record={"goid": "GO:0000001", "evidence": "IDA", "assigned_by": "UniProt", "type": "F"})
    return {"edges": [e], "assertions": [{"id": "assertion:test", "kind": "go_annotation",
        "evidence_edge_ids": [e["id"]]}, {"id": "assertion:outside", "kind": "disease_association", "evidence_edge_ids": []}]}


class GoReferenceEligibilityTests(unittest.TestCase):
    def classify(self, rows):
        graph = graph_for(rows)
        return ref.classify(graph, rows, native.project_compatibilities(graph, rows))

    def test_exact_experimental_reference_covers_only_declared_annotation_scope(self):
        rows = [positive()]
        original = deepcopy(rows)
        labels = self.classify(rows)
        self.assertEqual(labels[1]["verdict"], "agree")
        self.assertEqual(labels[0]["verdict"], "unknown")
        self.assertEqual(rows, original)
        self.assertTrue(all(x["independent_scientific_correctness"] == "unreviewed" for x in labels))

    def test_canonical_column17_literal_is_allowed_but_isoforms_and_other_products_are_not(self):
        self.assertEqual(self.classify([positive(**{"16": "UniProtKB:P00001"})])[1]["verdict"], "agree")
        for value in ("UniProtKB:P00001-1", "UniProtKB:P00001-2", "PR:000000001", "uniprotkb:P00001"):
            with self.subTest(value=value):
                label = self.classify([positive(**{"16": value})])[1]
                self.assertEqual(label["verdict"], "unknown")
                self.assertIn("distinct_product_form_not_collapsed", label["edge_assessments"][0]["candidate_eligibility"][0]["excluded_because"])

    def test_not_is_not_false_biology_and_strict_opposing_rows_leave_unknown(self):
        negative = positive(**{"3": "NOT|enables"})
        for rows in ([negative], [positive(), {**negative, "id": "another-native-row"}]):
            self.assertEqual(self.classify(rows)[1]["verdict"], "unknown")
        self.assertTrue(self.classify([negative])[1]["edge_assessments"][0]["eligible_NOT_record_ids"])

    def test_extensions_withfrom_and_taxon_contexts_are_not_silently_dropped(self):
        for changes in ({"15": "occurs_in(CL:0000001)"}, {"7": "UniProtKB:P00002"},
                        {"12": "taxon:9606|taxon:10090"}, {"12": "taxon:10090"}, {"6": "IEA"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.classify([positive(**changes)])[1]["verdict"], "unknown")

    def test_projection_aliases_or_ancestor_terms_are_not_accepted(self):
        for changes in ({"14": "UniProtKB"}, {"4": "GO:0000002"}, {"1": "P00002"}, {"8": "P"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.classify([positive(**changes)])[1]["verdict"], "unknown")

    def test_missing_and_duplicate_native_rows_and_changed_compatibility_fail_closed(self):
        self.assertEqual(self.classify([])[1]["verdict"], "unknown")
        with self.assertRaisesRegex(ValueError, "duplicate|repeat"):
            self.classify([positive(), positive()])
        rows = [positive()]; graph = graph_for(rows)
        links = native.project_compatibilities(graph, rows); links[0]["native_record_ids"] = []
        with self.assertRaisesRegex(ValueError, "actual original graph"):
            ref.classify(graph, rows, links)


class GoReferencePacketTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NativeContextInspectionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.out, self.plan = f.root / "reference", f.root / "plan.json"
        source = json.loads((f.context / "go_context_qualification.json").read_text())
        self.context_pin = sha(f.context / "go_context_qualification.json")
        plan = {"qualifier_policy": ref.POLICY, "context_report_sha256": self.context_pin,
            "context_report_content_sha256": source["content_sha256"], "native_GAF_sha256": f.pin,
            "source_url": source["source"]["provided_source_url"]}
        plan["content_sha256"] = digest(plan); write_json(self.plan, plan)

    def prepare(self):
        f = self.fixture
        with patch.object(native, "read_native_gaf", side_effect=f.producer):
            return ref.prepare(f.packet, f.context, self.plan, self.out,
                context_sha256=self.context_pin, plan_sha256=sha(self.plan))

    def test_complete_reference_replays_native_proof_and_preserves_all_unknowns(self):
        report = self.prepare()
        reread, labels = ref.load_reference(self.out, self.fixture.packet, report_sha256=sha(self.out / "report.json"))
        self.assertEqual(reread, report)
        self.assertEqual(len(labels), len(self.fixture.graph["assertions"]))
        self.assertTrue(all(r["verdict"] in {"agree", "unknown"} for r in labels))
        self.assertFalse(report["scientific_truth_accuracy_measured"])

    def test_resealed_label_fabrication_fails_full_native_replay(self):
        self.prepare()
        labels = design.read_rows(self.out / "reference_labels.jsonl")
        labels[0]["verdict"] = "disagree"
        design.write_jsonl(self.out / "reference_labels.jsonl", labels)
        report = json.loads((self.out / "report.json").read_text())
        report["files"] = ref.inventory(self.out)
        report.pop("content_sha256"); report["content_sha256"] = digest(report)
        write_json(self.out / "report.json", report)
        with self.assertRaisesRegex(ValueError, "labels do not replay"):
            ref.load_reference(self.out, self.fixture.packet, report_sha256=sha(self.out / "report.json"))

    def test_census_and_fixed_design_score_only_proof_bound_labels(self):
        self.prepare(); f = self.fixture
        before = {str(p): sha(p) for p in f.packet.rglob("*") if p.is_file()}
        result = score.score(f.packet, self.out, f.root / "score", reference_sha256=sha(self.out / "report.json"))
        self.assertEqual(result["population_assertions"], len(f.graph["assertions"]))
        self.assertTrue(result["all_independent_scientific_correctness_unreviewed"])
        stats = json.loads((f.root / "score/statistics.json").read_text())
        self.assertTrue(stats["overall"]["census"])
        frame, _ = design.frame_for(f.graph)
        allocation = {r["stratum"]: 1 for r in frame}
        design.prepare(f.packet, allocation, 18, f.root / "sample")
        sampled = score.score(f.packet, self.out, f.root / "sampled_score", reference_sha256=sha(self.out / "report.json"),
                               design_directory=f.root / "sample")
        self.assertEqual(sampled["sampled_assertions"], len(allocation))
        self.assertEqual(before, {str(p): sha(p) for p in f.packet.rglob("*") if p.is_file()})

    def test_input_mutation_during_scoring_leaves_no_success_report(self):
        self.prepare(); f = self.fixture
        write = score.write_json
        def changed(path, value):
            write(path, value)
            if Path(path).name == "statistics.json":
                proof = self.out / "source_plan.json"
                proof.write_bytes(proof.read_bytes() + b"\n")
        with patch.object(score, "write_json", side_effect=changed), self.assertRaisesRegex(ValueError, "changed during scoring"):
            score.score(f.packet, self.out, f.root / "changed_score", reference_sha256=sha(self.out / "report.json"))
        self.assertFalse((f.root / "changed_score/report.json").exists())


if __name__ == "__main__":
    unittest.main()
