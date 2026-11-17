"""Invented integration cases, not real scientific assertions or references."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.evidence_overlap import (
    _pmids, _qualified_identities, analyze_overlap, publish_overlap, verify_overlap,
)
from biograph_steward.assay_attachment import attach_assay
from biograph_steward.client import digest
from biograph_steward.graph import save_run
from test_assay_attachment import cohort_snapshot, make_publication


def ref(database, accession, qualifier="MI:0356"):
    return {"database": {"name": database}, "id": accession, "qualifier": {"mi_id": qualifier}}


def fixture():
    products = ["UniProtKB:P04637", "UniProtKB:P00533"]
    snapshot = {"content_sha256": "a" * 64, "scope": {"kind": "protein_cohort", "resolutions": [
        {"requested_uniprot": p[10:], "returned_uniprot": p[10:], "status": "resolved"} for p in products]},
        "retrieval": {"context": {"targets": [
            {"uniprot": p[10:], "family": "ppis", "status": "complete", "available": 1,
             "retrieved": 1, "retained": 1, "excluded_by_scope": 0, "issues": []} for p in products]}}}
    obs = {"id": "observation:1", "products": products, "study": "pubmed:12345", "source_kind": "intact_mitab27",
        "graph_edge_id": "assay:1", "evaluable": True, "assay_status": "curated_positive", "assay": "invented method",
        "source_fields": {"evidence_ids": {"values": [ref("intact", "EBI-100"), ref("imex", "IM-100-1")]}}}
    baseline = {"id": "baseline:1", "subject": products[0], "object": products[1],
        "record_kind": "protein_interaction", "predicate": "biograph:has_interaction_annotation", "symmetric": True,
        "qualifiers": {}, "publications": [], "evidence_sources": ["STRINGDB", "Reactome"], "source_record_count": 2}
    assay = {"id": "assay:1", "subject": products[0], "object": products[1], "record_kind": "assay_observation",
        "predicate": "biograph:has_assay_observation_with", "symmetric": False,
        "qualifiers": {"observation_id": obs["id"]}, "publications": ["pubmed:12345", "imex:IM-100"]}
    graph = {"snapshot_sha256": snapshot["content_sha256"], "edges": [baseline, assay], "assay_observations": [obs]}
    attachment = {"summary": {"source_observations": 1, "selected_observations": 1}}
    return snapshot, graph, attachment


def xml_material(*, ambiguous=False, global_experiment="EBI-200", local_id=9):
    row = {"format": "biograph-steward.intact-xml-evidence.v1", "record_kind": "evidence",
        "evidence": {"identifiers": [ref("intact", "EBI-100"), ref("wwpdb", "1abc")],
            "experiments": [{"xml_id": local_id, "source_locator": {"line": 10, "column": 2},
                             "xrefs": [ref("intact", global_experiment), ref("imex", "IM-100", "MI:0662")]}]}}
    raw = (json.dumps(row) + "\n").encode()
    return {"provenance/invented_reader.jsonl": raw * (2 if ambiguous else 1)}


class OverlapSemanticsTests(unittest.TestCase):
    def test_pair_is_represented_but_experiment_lineage_is_unknown(self):
        snapshot, graph, attachment = fixture()
        before = deepcopy((snapshot, graph, attachment))
        value = analyze_overlap(snapshot, graph, attachment, xml_material())
        row = value["records"][0]
        self.assertTrue(row["exact_pair_match"])
        self.assertFalse(row["same_local_qualified_claim_edge_ids"])
        self.assertIsNone(row["baseline_record_identity_overlap"])
        self.assertIsNone(row["baseline_experiment_identity_overlap"])
        self.assertEqual(row["experiment_lineage"], "unresolved")
        self.assertIn("assay_method", row["additional_context_fields_available"])
        self.assertEqual(value["summary"]["verified_independent_evidence"], 0)
        self.assertEqual((snapshot, graph, attachment), before)

    def test_pmid_is_not_an_imex_registration_or_discovery_reference(self):
        self.assertEqual(_pmids(["pubmed:12345", "PMID:12345", "imex:IM-100", "12345", "pubmed:0"]), ["PMID:12345"])
        snapshot, graph, attachment = fixture()
        graph["edges"][0]["publications"] = ["PMID:12345"]
        row = analyze_overlap(snapshot, graph, attachment, {})["records"][0]
        self.assertEqual(row["shared_supporting_pmids"], ["PMID:12345"])
        self.assertEqual(row["experiment_lineage"], "unresolved")

    def test_no_match_requires_both_exact_identifiers_and_complete_ppi_counts(self):
        snapshot, graph, attachment = fixture()
        graph["edges"] = graph["edges"][1:]
        self.assertEqual(analyze_overlap(snapshot, graph, attachment, {})["records"][0]["pair_representation"],
                         "not_represented_in_complete_bounded_baseline")
        for change in ("truncated", "wrong_count", "identity_mismatch", "missing_endpoint"):
            source = deepcopy(snapshot)
            if change == "truncated": source["retrieval"]["context"]["targets"][0]["status"] = "capped"
            if change == "wrong_count": source["retrieval"]["context"]["targets"][0]["available"] = 2
            if change == "identity_mismatch": source["scope"]["resolutions"][0]["status"] = "identity_mismatch"
            if change == "missing_endpoint": source["retrieval"]["context"]["targets"].pop()
            with self.subTest(change=change):
                self.assertEqual(analyze_overlap(source, graph, attachment, {})["records"][0]["pair_representation"],
                                 "unknown_incomplete_or_unresolved")

    def test_negative_or_excluded_observations_are_retained_without_pruning(self):
        snapshot, graph, attachment = fixture()
        graph["assay_observations"][0].update(evaluable=False, assay_status="test_failed", graph_edge_id=None)
        result = analyze_overlap(snapshot, graph, attachment, {})
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["summary"]["excluded_observations_retained"], 1)
        self.assertTrue(result["records"][0]["exact_pair_match"])
        self.assertEqual(result["summary"]["automatic_pruning"], 0)

    def test_structural_aliases_do_not_become_experiment_or_record_identity(self):
        refs = [ref("intact", "EBI-100"), ref("wwpdb", "1abc"), ref("emdb", "EMD-1"), ref("intact", "EBI-999", "MI:0361")]
        self.assertEqual(_qualified_identities(refs, record_only=True), ["intact:EBI-100"])
        snapshot, graph, attachment = fixture()
        row = analyze_overlap(snapshot, graph, attachment, xml_material())["records"][0]["added_source"]
        self.assertEqual(row["external_identity_aliases"], ["wwpdb:1abc"])
        self.assertEqual(row["experiment_ids"], ["intact:EBI-200"])
        self.assertNotIn("imex:IM-100", row["experiment_ids"])

    def test_shared_curated_record_or_experiment_stays_a_separate_flag(self):
        snapshot, graph, attachment = fixture()
        second = deepcopy(graph["assay_observations"][0]); second["id"] = "observation:2"; second["graph_edge_id"] = None
        graph["assay_observations"].append(second)
        result = analyze_overlap(snapshot, graph, attachment, xml_material())
        self.assertEqual(len(result["records"][0]["shared_added_record_identities"]), 1)
        self.assertEqual(len(result["records"][0]["shared_added_experiments"]), 1)
        self.assertEqual(len(result["records"][0]["shared_added_publications"]), 1)
        self.assertIsNone(result["records"][0]["independent_evidence_count"])
        self.assertEqual(result["summary"]["automatic_merges"], 0)

    def test_doi_publication_context_is_available_without_inventing_a_pmid(self):
        snapshot, graph, attachment = fixture()
        graph["assay_observations"][0]["study"] = "doi:10.1234/invented"
        row = analyze_overlap(snapshot, graph, attachment, {})["records"][0]
        self.assertFalse(row["added_source"]["pmids"])
        self.assertTrue(row["added_source"]["context_availability"]["publication"])
        self.assertEqual(row["added_source"]["publication_identifiers"], ["doi:10.1234/invented"])

    def test_ambiguous_xml_record_join_does_not_choose_first_experiment(self):
        row = analyze_overlap(*fixture(), xml_material(ambiguous=True))["records"][0]["added_source"]
        self.assertEqual(row["xml_join_status"], "ambiguous_captured_record_join")
        self.assertFalse(row["experiment_ids"])

    def test_imex_primary_in_xml_xrefs_is_an_evidence_alias(self):
        snapshot, graph, attachment = fixture()
        graph["assay_observations"][0]["source_fields"]["evidence_ids"]["values"] = [ref("imex", "IM-100-1")]
        material = xml_material(); row = json.loads(next(iter(material.values())))
        row["evidence"]["xrefs"] = [ref("imex", "IM-100-1", "MI:0662")]
        material[next(iter(material))] = (json.dumps(row) + "\n").encode()
        result = analyze_overlap(snapshot, graph, attachment, material)["records"][0]["added_source"]
        self.assertEqual(result["xml_join_status"], "one_captured_evidence_record")
        self.assertIn("imex:IM-100-1", result["record_identity_aliases"])

    def test_reused_xml_id_requires_exact_source_locator_and_artifact(self):
        snapshot, graph, attachment = fixture()
        first = graph["assay_observations"][0]
        second = deepcopy(first); second["id"] = "observation:2"; second["graph_edge_id"] = None
        second["source_fields"]["evidence_ids"]["values"] = [ref("intact", "EBI-101")]
        graph["assay_observations"].append(second)
        rows = [json.loads(next(iter(xml_material().values()))) for _ in range(2)]
        rows[0]["evidence"]["experiments"][0]["xrefs"] = []
        rows[1]["evidence"]["identifiers"] = [ref("intact", "EBI-101")]
        rows[1]["evidence"]["experiments"][0]["xrefs"] = []
        rows[1]["evidence"]["experiments"][0]["source_locator"]["line"] = 50
        material = {"provenance/invented_reader.jsonl": b"".join((json.dumps(r) + "\n").encode() for r in rows)}
        result = analyze_overlap(snapshot, graph, attachment, material)["records"][0]
        self.assertFalse(result["shared_added_experiments"])

    def test_isoform_not_silently_matched_to_canonical_pair(self):
        snapshot, graph, attachment = fixture()
        graph["assay_observations"][0]["products"][0] += "-2"
        row = analyze_overlap(snapshot, graph, attachment, {})["records"][0]
        self.assertFalse(row["exact_pair_match"])
        self.assertEqual(row["pair_representation"], "unknown_incomplete_or_unresolved")


class OverlapPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        save_run(cohort_snapshot(), self.root / "source")
        make_publication(self.root / "publication")
        attach_assay(self.root / "source", self.root / "publication", self.root / "attached")

    def test_saved_run_roundtrip_source_bytes_and_ledger_preservation(self):
        source = self.root / "attached"
        before = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob("*") if p.is_file()}
        result = publish_overlap(source, self.root / "report")
        self.assertEqual(verify_overlap(self.root / "report"), result)
        self.assertEqual(len(result["records"]), 4)
        self.assertEqual(result["summary"]["excluded_observations_retained"], 1)
        self.assertEqual(before, {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob("*") if p.is_file()})
        self.assertTrue((self.root / "report/mappings.sssom.tsv").read_text().startswith("# curie_map:"))

    def test_resealed_wrong_classification_does_not_reproduce(self):
        folder = self.root / "report"; publish_overlap(self.root / "attached", folder)
        path = folder / "report.json"; value = json.loads(path.read_text())
        value["records"][0]["experiment_lineage"] = "independent"
        value.pop("content_sha256"); value["content_sha256"] = digest(value)
        path.write_text(json.dumps(value, indent=2) + "\n")
        from biograph_steward.file_utils import sha
        manifest_path = folder / "manifest.json"; manifest = json.loads(manifest_path.read_text())
        manifest["files"]["report.json"] = sha(path); manifest.pop("content_sha256"); manifest["content_sha256"] = digest(manifest)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        with self.assertRaisesRegex(ValueError, "do not reproduce"):
            verify_overlap(folder)

    def test_source_tamper_and_symlink_are_rejected(self):
        folder = self.root / "report"; publish_overlap(self.root / "attached", folder)
        (self.root / "attached/graph.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "workspace changed"):
            verify_overlap(folder)
        (self.root / "alias").symlink_to(self.root / "source", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            publish_overlap(self.root / "alias", self.root / "other")


if __name__ == "__main__":
    unittest.main()
