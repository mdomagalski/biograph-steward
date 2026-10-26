"""Invented source contracts; no experimental labels or predictions."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "audit_inmc_inputs", Path(__file__).resolve().parents[1] / "scripts/audit_inmc_inputs.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
A, B, C = "ENSG00000000001", "ENSG00000000002", "ENSG00000000003"


class SourceContractTests(unittest.TestCase):
    def test_changed_archive_is_rejected_before_registry_or_member_access(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive.zip"
            path.write_bytes(b"not the verified archive")
            with self.assertRaisesRegex(ValueError, "checked Zenodo release"):
                audit.audit(path, Path(directory) / "absent_registry")

    def test_identity_pass_does_not_decode_outcomes(self):
        # Non-UTF8 outcome bytes would fail an accidental whole-row decode.
        raw = audit.PANEL_HEADER + f"\n{A}\t{B}\t".encode() + b"\xff\t\xff\t\xff\t\xff\n"
        self.assertEqual(audit.identifier_pairs(raw, panel=True), [(A, B)])

    def test_no_inferred_symmetry_or_deduplication_in_source_rows(self):
        raw = f"source,target\n{A},{B}\n{B},{A}\n{A},{A}\n".encode()
        self.assertEqual(audit.identifier_pairs(raw, panel=False), [(A, B), (B, A), (A, A)])

    def test_schema_never_contains_a_pair_or_a_label_count(self):
        raw = audit.PANEL_HEADER + f"\n{A}\t{B}\tNULL\tNot tested\tAuto-activator\tNot scored\n".encode()
        self.assertEqual(audit.schema_vocabulary(raw), {
            "freq": ["NULL"], "score_assay1": ["Not tested"],
            "score_assay2": ["Auto-activator"], "score_assay3": ["Not scored"],
        })

    def test_malformed_or_wrong_identifier_input_is_rejected(self):
        for raw in (b"source,target\nTP53,KRAS\n", b"target,source\n", b"source,target\n",
                    f"source,target\n{A},{B},extra\n".encode()):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                audit.identifier_pairs(raw, panel=False)


class MappingTests(unittest.TestCase):
    def test_ambiguous_or_withdrawn_identifiers_are_not_arbitrarily_resolved(self):
        calls = []
        registry = SimpleNamespace(genes={
            "HGNC:1": {"status": "Approved", "ensembl_gene_id": A},
            "HGNC:2": {"status": "Approved", "ensembl_gene_id": A},
            "HGNC:3": {"status": "Entry Withdrawn", "ensembl_gene_id": B},
        }, products=lambda gid: calls.append(gid))
        rows = audit.map_identifiers({A, B, C}, registry)
        self.assertEqual([row["gene_status"] for row in rows], ["ambiguous", "unresolved", "unresolved"])
        self.assertEqual(calls, [])
        self.assertEqual(rows[0]["hgnc_ids"], ["HGNC:1", "HGNC:2"])

    def test_multiple_and_conflicting_products_remain_visible(self):
        products = [
            {"uniprot_id": "UniProtKB:P00001", "status": "reviewed_human_hgnc_match", "shared_across_genes": False},
            {"uniprot_id": "UniProtKB:P00002", "status": "reviewed_human_hgnc_match", "shared_across_genes": False},
            {"uniprot_id": "UniProtKB:P00003", "status": "reviewed_human_hgnc_match", "shared_across_genes": True},
            {"uniprot_id": "UniProtKB:P00004", "status": "registry_conflict", "shared_across_genes": False},
        ]
        registry = SimpleNamespace(genes={"HGNC:1": {"status": "Approved", "ensembl_gene_id": A}}, products=lambda gid: products)
        row, = audit.map_identifiers({A}, registry)
        self.assertEqual(row["product_status"], "multiple")
        self.assertEqual(len(row["protein_candidates"]), 4)
        self.assertEqual(row["unshared_reviewed_products"], ["UniProtKB:P00001", "UniProtKB:P00002"])
        self.assertEqual(row["shared_reviewed_products"], ["UniProtKB:P00003"])
        self.assertNotIn("UniProtKB:P00004", row["confirmed_reviewed_products"])
        self.assertFalse(row["assay_isoform_assignment_established"])

    def test_shared_product_is_not_missing_and_retrieval_does_not_collapse_genes(self):
        shared = {"uniprot_id": "UniProtKB:P00001", "status": "reviewed_human_hgnc_match",
                  "shared_across_genes": True}
        registry = SimpleNamespace(genes={
            "HGNC:1": {"status": "Approved", "ensembl_gene_id": A},
            "HGNC:2": {"status": "Approved", "ensembl_gene_id": B},
        }, products=lambda gid: [shared])
        rows = audit.map_identifiers({A, B, C}, registry)
        self.assertEqual([row["product_status"] for row in rows], ["shared_only", "shared_only", "none"])
        roster = audit.context_targets(rows)
        self.assertEqual(roster["panel_gene_ids"], [A, B, C])
        self.assertEqual(roster["panel_genes_without_confirmed_context"], [C])
        self.assertEqual(len(roster["targets"]), 1)
        target = roster["targets"][0]
        self.assertEqual(target["panel_gene_ids"], [A, B])
        self.assertEqual(target["hgnc_ids"], ["HGNC:1", "HGNC:2"])
        self.assertTrue(target["shared_across_registry_genes"])
        self.assertFalse(roster["evaluation_cohort_selected"])
        self.assertFalse(roster["assay_construct_identity_established"])

    def test_unconfirmed_product_never_enters_retrieval_roster(self):
        registry = SimpleNamespace(genes={"HGNC:1": {"status": "Approved", "ensembl_gene_id": A}},
            products=lambda gid: [{"uniprot_id": "UniProtKB:P00001", "status": "registry_conflict",
                                    "shared_across_genes": False}])
        rows = audit.map_identifiers({A}, registry)
        self.assertEqual(rows[0]["product_status"], "unconfirmed")
        self.assertEqual(audit.context_targets(rows)["targets"], [])
        self.assertEqual(audit.context_targets(rows)["panel_genes_without_confirmed_context"], [A])


if __name__ == "__main__":
    unittest.main()
