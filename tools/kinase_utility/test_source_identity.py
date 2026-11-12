"""Invented source identities only; no real benchmark or activity inference."""
from copy import deepcopy
import csv
from io import StringIO
import unittest

from biograph_steward.cohort_mapping import Registry
from source_identity import resolve_source_protein_context


def encoded(rows):
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode()


def fixture(*, alias_collision=False, other_product=False):
    genes = [{"hgnc_id": "HGNC:1", "symbol": "ALPHA", "status": "Approved",
        "prev_symbol": "", "alias_symbol": "", "uniprot_ids": "P00001" + ("|P00003" if other_product else ""),
        "entrez_id": "1", "ensembl_gene_id": "INVENTED1", "locus_type": "gene with protein product"},
        {"hgnc_id": "HGNC:2", "symbol": "BETA", "status": "Approved",
        "prev_symbol": "", "alias_symbol": "ALPHA" if alias_collision else "", "uniprot_ids": "P00002",
        "entrez_id": "2", "ensembl_gene_id": "INVENTED2", "locus_type": "gene with protein product"}]
    proteins = [{"Entry": "P00001", "Gene Names (primary)": "ALPHA", "Gene Names (synonym)": "",
        "HGNC": "HGNC:1;", "GeneID": "1;", "Organism (ID)": "9606", "Protein names": "INVENTED MAIN PRODUCT"},
        {"Entry": "P00002", "Gene Names (primary)": "BETA", "Gene Names (synonym)": "",
        "HGNC": "HGNC:2;", "GeneID": "2;", "Organism (ID)": "9606", "Protein names": "INVENTED OTHER GENE"}]
    if other_product:
        proteins.append({**proteins[0], "Entry": "P00003", "Protein names": "INVENTED DISTINCT uORF PRODUCT"})
    registry = Registry(encoded(genes), encoded(proteins))
    captured = {p["Entry"]: {"Entry": p["Entry"], "Gene Names (primary)": p["Gene Names (primary)"],
        "HGNC": p["HGNC"], "GeneID": p["GeneID"], "Organism (ID)": "9606", "Reviewed": "reviewed",
        "Sequence": "MSTY", "Sequence version": "1", "Date of last sequence modification": "2020-01-01"}
        for p in proteins}
    return registry, captured


class SourceIdentityTests(unittest.TestCase):
    def test_known_protein_disambiguates_shadowed_current_symbol_without_alias_lookup(self):
        registry, captured = fixture(alias_collision=True)
        self.assertEqual(registry.resolve("ALPHA")["shadowed_relation_candidates"], ["HGNC:2"])
        original = deepcopy((registry.proteins, registry.genes, captured))
        mapped = resolve_source_protein_context("UniProtKB:P00001", registry, captured)
        self.assertEqual((mapped["status"], mapped["protein_id"], mapped["hgnc_id"], mapped["approved_symbol"]),
            ("qualified_source_protein_context", "UniProtKB:P00001", "HGNC:1", "ALPHA"))
        self.assertEqual((registry.proteins, registry.genes, captured), original)
        self.assertFalse(mapped["gene_protein_identity_equivalence"])
        self.assertFalse(mapped["experimental_proteoform_identity_established"])
        self.assertFalse(mapped["catalytic_role_verified"])
        self.assertEqual(mapped["citation_grounding_status"], "not_assessed")

    def test_additional_gene_product_does_not_change_literal_product_identity(self):
        registry, captured = fixture(other_product=True)
        self.assertEqual(len(registry.products("HGNC:1")), 2)
        for accession in ("P00001", "P00003"):
            mapped = resolve_source_protein_context("UniProtKB:" + accession, registry, captured)
            self.assertEqual(mapped["status"], "qualified_source_protein_context")
            self.assertEqual(mapped["protein_id"], "UniProtKB:" + accession)
            self.assertEqual(len(mapped["all_declared_or_linked_gene_products"]), 2)
            self.assertFalse(mapped["source_accession_remapped"])
            self.assertEqual(mapped["citation_grounding_status"], "not_assessed")

    def test_gene_only_secondary_unknown_and_isoform_inputs_are_not_rescued(self):
        registry, captured = fixture()
        for identifier in ("ALPHA", "P00001", "HGNC:1", "UniProtKB:P00001-2", "UniProtKB:Q99999"):
            mapped = resolve_source_protein_context(identifier, registry, captured)
            self.assertNotEqual(mapped["status"], "qualified_source_protein_context")
            self.assertIsNone(mapped["protein_id"])
            self.assertFalse(mapped["source_accession_remapped"])

    def test_conflicting_or_missing_gene_cross_references_are_unresolved(self):
        for field, value in (("HGNC", "HGNC:2;"), ("HGNC", "HGNC:1;HGNC:2;"), ("HGNC", ""),
                             ("GeneID", "2;"), ("GeneID", "1;2;")):
            registry, captured = fixture(); captured["P00001"][field] = value
            self.assertNotEqual(resolve_source_protein_context("UniProtKB:P00001", registry, captured)["status"],
                                "qualified_source_protein_context")
        registry, captured = fixture(); registry.proteins["P00001"]["hgnc_ids"] = ["HGNC:1", "HGNC:2"]
        self.assertIn("exact_single_reciprocal_HGNC_context_required",
            resolve_source_protein_context("UniProtKB:P00001", registry, captured)["reasons"])

    def test_reciprocal_product_and_nonconflicting_GeneID_context_required(self):
        registry, captured = fixture(); registry.genes["HGNC:1"]["uniprot_ids"] = "P00003"
        self.assertIn("HGNC_does_not_reciprocally_declare_literal_protein",
            resolve_source_protein_context("UniProtKB:P00001", registry, captured)["reasons"])
        registry, captured = fixture(); registry.proteins["P00001"]["ncbi_gene_ids"] = ["2"]
        self.assertIn("conflicting_secondary_GeneID_context",
            resolve_source_protein_context("UniProtKB:P00001", registry, captured)["reasons"])

    def test_missing_secondary_cross_reference_is_unavailable_not_conflicting(self):
        registry, captured = fixture()
        registry.proteins["P00001"]["ncbi_gene_ids"] = []
        captured["P00001"]["GeneID"] = ""
        mapped = resolve_source_protein_context("UniProtKB:P00001", registry, captured)
        self.assertEqual(mapped["status"], "qualified_source_protein_context")
        self.assertEqual(mapped["secondary_GeneID_corroboration"]["status"], "unavailable")
        self.assertEqual(mapped["secondary_GeneID_corroboration"]["missing_sources"],
            ["registry_UniProt", "sequence_reference_UniProt"])
        # Present nonunique IDs remain unresolved even if one equals HGNC's ID.
        registry, captured = fixture()
        registry.proteins["P00001"]["ncbi_gene_ids"] = ["1", "2"]
        captured["P00001"]["GeneID"] = "1;2;"
        mapped = resolve_source_protein_context("UniProtKB:P00001", registry, captured)
        self.assertEqual(mapped["secondary_GeneID_corroboration"]["status"], "ambiguous")
        self.assertIn("non_unique_secondary_GeneID_context", mapped["reasons"])
        self.assertIsNone(mapped["protein_id"])

    def test_reference_sequence_entry_review_taxon_and_gene_conflicts_rejected(self):
        for field, value in (("Sequence", ""), ("Sequence", "MS*T"), ("Sequence", None),
            ("Entry", "P00002"), ("Reviewed", "unreviewed"), ("Organism (ID)", "10090"),
            ("Gene Names (primary)", "BETA")):
            registry, captured = fixture(); captured["P00001"][field] = value
            result = resolve_source_protein_context("UniProtKB:P00001", registry, captured)
            self.assertNotEqual(result["status"], "qualified_source_protein_context")
            self.assertTrue(result["reasons"])
        registry, captured = fixture(); del captured["P00001"]
        self.assertIn("literal_primary_accession_absent_from_sequence_reference",
            resolve_source_protein_context("UniProtKB:P00001", registry, captured)["reasons"])

    def test_withdrawn_or_duplicate_approved_context_is_not_qualified(self):
        registry, captured = fixture(); registry.genes["HGNC:1"]["status"] = "Entry Withdrawn"
        self.assertIn("captured_HGNC_gene_not_approved",
            resolve_source_protein_context("UniProtKB:P00001", registry, captured)["reasons"])
        registry, captured = fixture(); registry.primary["ALPHA"].add("HGNC:2")
        self.assertIn("approved_symbol_not_unique_in_HGNC_registry",
            resolve_source_protein_context("UniProtKB:P00001", registry, captured)["reasons"])


if __name__ == "__main__":
    unittest.main()
