"""Invented identities/rows test cohort-support scope, not cancer-driver truth."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json
from biograph_steward.cohort_mapping import SOURCES, collect_registry
from biograph_steward.demo import demo_snapshot
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from tools.reference_accuracy import cornish, design, score
from test_cohort_mapping import gene, protein, registry, tsv


def native_row(symbol="TEST"):
    return {"native_gene_symbol": symbol, "native_sheet": cornish.SHEET, "native_row": 9,
        "gene_cell": "A9", "native_cohort_calls": ["PRIMARY_MSS"], "native_cohorts_literal": "PRIMARY_MSS",
        "native_statistics": {"PRIMARY_MSS": [{"cell": "AB9", "value": 0.01}, {"cell": "AC9", "value": "NA"}]},
        "native_tier_not_reported_in_table": True, "gene_role_not_extrapolated": True}


def graph(name=cornish.SOURCE_NAME):
    return {"assertions": [{"id": "assertion:one", "kind": "disease_association", "subject": "UniProtKB:P00001",
        "predicate": "biolink:associated_with", "object": cornish.DISEASE,
        "qualifiers": {"disease": cornish.DISEASE}, "evidence_edge_ids": ["edge:one"]}],
        "edges": [{"id": "edge:one", "record_kind": "disease_association", "subject": "UniProtKB:P00001",
                   "object": cornish.DISEASE, "evidence_record": {"name": name}}]}


class CornishContextTests(unittest.TestCase):
    def setUp(self):
        self.registry = registry([gene("HGNC:1", "TEST")], [protein("P00001", "HGNC:1", "TEST")])

    def label(self, value=None, rows=None):
        return cornish.classify(value or graph(), [native_row()] if rows is None else rows, self.registry)[0]

    def test_published_gene_context_is_positive_support_without_truth_or_tier_inference(self):
        g = graph(); before = deepcopy(g); row = self.label(g)
        self.assertEqual(row["verdict"], "agree")
        self.assertEqual(row["current_gene_product_relation"]["relation"], "gene_to_protein_relationship_not_identity")
        self.assertEqual(row["matched_native_row"]["native_statistics"]["PRIMARY_MSS"][1]["value"], "NA")
        self.assertEqual(row["independent_scientific_correctness"], "unreviewed")
        self.assertFalse(row["native_call_absence_is_negative"])
        self.assertEqual(g, before)

    def test_narrower_anatomic_source_does_not_match_only_broad_CRC_discovery(self):
        for name in ("colon adenocarcinoma", "rectum adenocarcinoma", "Colorectal Adenocarcinoma", None):
            with self.subTest(name=name):
                row = self.label(graph(name))
                self.assertEqual(row["verdict"], "unknown")
                self.assertFalse(row["exact_original_source_context_eligible"])
                self.assertIsNotNone(row["broader_cohort_diagnostic_row"])

    def test_disease_identifier_qualifier_and_predicate_are_never_silently_changed(self):
        for field, value in (("object", "MONDO:other"), ("predicate", "biolink:causes")):
            g = graph(); g["assertions"][0][field] = value
            self.assertEqual(self.label(g)["verdict"], "unknown")
        g = graph(); g["assertions"][0]["qualifiers"]["disease"] = "MONDO:other"
        self.assertEqual(self.label(g)["verdict"], "unknown")

    def test_exact_approved_symbol_and_current_product_relation_no_aliases_or_isoform_stripping(self):
        for symbol in ("test", "OLD_TEST", "TEST-1"):
            self.assertEqual(self.label(rows=[native_row(symbol)])["verdict"], "unknown")
        g = graph(); g["assertions"][0]["subject"] += "-2"; g["edges"][0]["subject"] += "-2"
        self.assertEqual(self.label(g)["verdict"], "unknown")
        self.registry.primary["TEST"].add("HGNC:2")
        self.assertEqual(self.label()["verdict"], "unknown")

    def test_gene_reference_conflict_and_absence_are_UNKNOWN_not_negative(self):
        self.assertEqual(self.label(rows=[])["verdict"], "unknown")
        self.registry.proteins["P00001"]["ncbi_gene_ids"] = ["999"]
        self.assertEqual(self.label()["verdict"], "unknown")

    def test_conflicting_supporting_source_scope_keeps_whole_assertion_unresolved(self):
        g = graph(); other = deepcopy(g["edges"][0]); other["id"] = "edge:two"
        other["evidence_record"]["name"] = "rectum adenocarcinoma"; g["edges"].append(other)
        g["assertions"][0]["evidence_edge_ids"].append(other["id"])
        self.assertEqual(self.label(g)["verdict"], "unknown")
        with self.assertRaisesRegex(ValueError, "repeat"):
            self.label(rows=[native_row(), native_row()])


class CornishReferencePacketTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.packet = self.root / "packet"; self.out = self.root / "reference"
        self.graph = save_run(demo_snapshot(), self.root / "run")
        gold_packet.export_packet(self.root / "run", self.packet)
        self.archive = self.root / "archive.zip"
        with ZipFile(self.archive, "w") as z:
            z.writestr(cornish.MEMBER, b"INVENTED mocked reader fixture, never a scientific reference")
        self.article = self.root / "article.xml"
        self.article.write_text('<article xmlns:xlink="http://www.w3.org/1999/xlink"><article-id pub-id-type="doi">'
            + cornish.DOI + '</article-id><article-id pub-id-type="pmid">' + cornish.PMID
            + '</article-id><ext-link xlink:href="https://creativecommons.org/licenses/by/4.0/"/>'
            + '<media xlink:href="' + cornish.MEMBER + '"/></article>')
        self.registry = self.root / "registry"
        raw = dict(zip(SOURCES, [tsv([gene("HGNC:1", "TEST")]), tsv([protein("P00001", "HGNC:1", "TEST")])]))
        manifest = collect_registry(self.registry, transport=lambda url: (raw[next(k for k,v in SOURCES.items() if v == url)], {}))
        self.registry_pin = manifest["registry_sha256"]
        self.reader = patch.object(cornish, "read_native_study", return_value=([native_row()], {"reader": "INVENTED test-only fixture"}))
        self.reader.start(); self.addCleanup(self.reader.stop)

    def prepare(self):
        return cornish.prepare(self.packet, self.archive, self.article, self.registry, self.out,
            archive_sha256=sha(self.archive), article_sha256=sha(self.article), registry_sha256=self.registry_pin)

    def test_immutable_source_reference_replays_and_scoring_keeps_distinct_axis(self):
        report = self.prepare()
        replay, labels = cornish.load_reference(self.out, self.packet, report_sha256=sha(self.out / "report.json"))
        self.assertEqual(report, replay); self.assertEqual(len(labels), len(self.graph["assertions"]))
        self.assertFalse(report["reference_labels_added_to_features"])
        result = score.score(self.packet, self.out, self.root / "score", reference_sha256=sha(self.out / "report.json"),
                             reference_kind="crc_genomic_cohort")
        self.assertEqual(result["reference_axis"], cornish.AXIS)
        self.assertTrue(result["positive_only_reference"])
        self.assertFalse(result["resolved_only_agreement_ratio_is_accuracy_evidence"])
        with self.assertRaisesRegex(ValueError, "identity/policy"):
            score.score(self.packet, self.out, self.root / "wrong_axis", reference_sha256=sha(self.out / "report.json"))
        with self.assertRaises(ValueError): self.prepare()

    def test_resealed_fake_label_or_feature_leak_flag_is_rejected(self):
        self.prepare()
        values = design.read_rows(self.out / "reference_labels.jsonl"); values[0]["verdict"] = "disagree"
        design.write_jsonl(self.out / "reference_labels.jsonl", values)
        report = json.loads((self.out / "report.json").read_text()); report["files"] = cornish.inventory(self.out)
        report.pop("content_sha256"); report["content_sha256"] = digest(report); write_json(self.out / "report.json", report)
        with self.assertRaisesRegex(ValueError, "labels do not replay"):
            cornish.load_reference(self.out, self.packet, report_sha256=sha(self.out / "report.json"))
        report["reference_labels_added_to_features"] = True
        report.pop("content_sha256"); report["content_sha256"] = digest(report); write_json(self.out / "report.json", report)
        with self.assertRaisesRegex(ValueError, "reserve scope"):
            cornish.load_reference(self.out, self.packet, report_sha256=sha(self.out / "report.json"))

    def test_changed_copied_article_cannot_receive_success_report(self):
        writer = cornish.write_jsonl
        def changed(path, rows):
            writer(path, rows)
            if Path(path).name == "reference_labels.jsonl":
                p = self.out / "source/article.xml"; p.write_bytes(p.read_bytes() + b"\n")
        with patch.object(cornish, "write_jsonl", side_effect=changed), self.assertRaisesRegex(ValueError, "input/copy"):
            self.prepare()
        self.assertFalse((self.out / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
