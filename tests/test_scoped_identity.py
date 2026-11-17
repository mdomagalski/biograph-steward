"""Invented records only: source-scoped gene and protein context qualification."""
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import unittest

from biograph_steward.client import digest
from biograph_steward.cohort_mapping import Registry
from tools.kinase_utility.scoped_identity import qualify_scoped_identity


def source(rows, delimiter="\t"):
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode()


def row(**changes):
    return {**dict(native_id="record-A", symbol="ALPHA", hgnc="HGNC:1",
                   ensg="ENSG00000000001", protein="P00001"), **changes}


def registry_fixture(*, alias_collision=False, other_product=False):
    # Reuse the Registry's ordinary tabular contract with invented identities;
    # do not depend on another test module or its import-path configuration.
    genes = [{"hgnc_id": "HGNC:1", "symbol": "ALPHA", "status": "Approved",
              "prev_symbol": "", "alias_symbol": "", "uniprot_ids": "P00001" + ("|P00003" if other_product else ""),
              "entrez_id": "1", "ensembl_gene_id": "ENSG00000000001", "locus_type": "gene with protein product"},
             {"hgnc_id": "HGNC:2", "symbol": "BETA", "status": "Approved",
              "prev_symbol": "", "alias_symbol": "ALPHA" if alias_collision else "", "uniprot_ids": "P00002",
              "entrez_id": "2", "ensembl_gene_id": "ENSG00000000002", "locus_type": "gene with protein product"}]
    proteins = [{"Entry": "P00001", "Gene Names (primary)": "ALPHA", "Gene Names (synonym)": "",
                 "HGNC": "HGNC:1;", "GeneID": "1;", "Organism (ID)": "9606", "Protein names": "INVENTED MAIN PRODUCT"},
                {"Entry": "P00002", "Gene Names (primary)": "BETA", "Gene Names (synonym)": "",
                 "HGNC": "HGNC:2;", "GeneID": "2;", "Organism (ID)": "9606", "Protein names": "INVENTED OTHER PRODUCT"}]
    if other_product:
        proteins.append({**proteins[0], "Entry": "P00003", "Protein names": "INVENTED DISTINCT PRODUCT"})
    registry = Registry(source(genes), source(proteins))
    captured = {p["Entry"]: {**p, "Reviewed": "reviewed", "Sequence": "MSTY"} for p in proteins}
    return registry, captured


def binding(raw, rows, ordinal=1):
    return {"source_id": "invented-source", "source_release": "invented-release-1",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_record_id": rows[ordinal - 1]["native_id"],
            "source_data_record_ordinal": ordinal,
            "canonical_source_row_sha256": digest(rows[ordinal - 1])}


class ScopedIdentityTests(unittest.TestCase):
    def qualify(self, rows=None, fields=None, registry=None, captured=None, **changes):
        rows = rows or [row()]
        raw = source(rows)
        if registry is None:
            registry, captured = registry_fixture(alias_collision=True)
        fields = {"HGNC": "hgnc"} if fields is None else fields
        columns = set(fields.values()) | {"symbol"}
        options = dict(binding=binding(raw, rows), delimiter="\t", record_id_field="native_id",
            identifier_fields=fields, symbol_field="symbol", unavailable_values={column: ["", "NA"] for column in columns},
            registry=registry, sequence_reference=captured)
        options.update(changes)
        return qualify_scoped_identity(raw, **options)

    def test_explicit_hgnc_disambiguates_one_record_without_global_symbol_override(self):
        registry, captured = registry_fixture(alias_collision=True)
        before = deepcopy((registry.genes, registry.proteins, registry.relations, captured))
        result = self.qualify(registry=registry, captured=captured)
        self.assertEqual((result["status"], result["hgnc_id"], result["approved_symbol"]),
                         ("qualified_source_gene_context", "HGNC:1", "ALPHA"))
        self.assertEqual(result["symbol_resolution_audit"]["shadowed_relation_candidates"], ["HGNC:2"])
        self.assertFalse(result["global_alias_override"])
        self.assertEqual((registry.genes, registry.proteins, registry.relations, captured), before)
        # The same raw token can refer to another gene only when its explicit
        # stable identifier and that gene's curated alias supply the context.
        other = self.qualify([row(hgnc="HGNC:2")], registry=registry, captured=captured)
        self.assertEqual((other["hgnc_id"], other["approved_symbol"]), ("HGNC:2", "BETA"))

    def test_gene_only_symbol_never_gets_a_stable_identifier_manufactured(self):
        for token in ["ALPHA", "BETA", "UNKNOWN"]:
            result = self.qualify([row(symbol=token)], fields={})
            self.assertEqual(result["status"], "source_identity_unresolved")
            self.assertIsNone(result["hgnc_id"])
            self.assertIn("no_explicit_source_stable_identifier", result["reasons"])

    def test_hgnc_or_ensg_qualification_does_not_choose_even_a_unique_protein(self):
        for fields in [{"HGNC": "hgnc"}, {"ENSEMBL": "ensg"}]:
            result = self.qualify(fields=fields)
            self.assertEqual(result["gene_status"], "qualified")
            self.assertIsNone(result["protein_id"])
            self.assertEqual(result["protein_status"], "not_reported")
            self.assertFalse(result["gene_protein_identity_equivalence"])

    def test_literal_protein_reuses_existing_audit_without_proteoform_or_catalytic_claim(self):
        registry, captured = registry_fixture(alias_collision=True, other_product=True)
        for accession in ["P00001", "UniProtKB:P00003"]:
            result = self.qualify([row(protein=accession)], fields={"UniProtKB": "protein"},
                                  registry=registry, captured=captured)
            self.assertEqual(result["gene_status"], "qualified")
            self.assertEqual(result["protein_id"], accession if accession.startswith("UniProtKB:") else "UniProtKB:" + accession)
            self.assertFalse(result["experimental_proteoform_identity_established"])
            self.assertFalse(result["catalytic_truth_established"])
            self.assertEqual(result["citation_grounding_status"], "not_assessed")

    def test_present_identifier_and_symbol_conflicts_are_exposed_not_ignored(self):
        for item, fields, reason in [
            (row(ensg="ENSG00000000002"), {"HGNC": "hgnc", "ENSEMBL": "ensg"}, "explicit_identifiers_resolve_to_different_genes"),
            (row(protein="P00002"), {"HGNC": "hgnc", "UniProtKB": "protein"}, "explicit_identifiers_resolve_to_different_genes"),
            (row(symbol="BETA"), {"HGNC": "hgnc"}, "reported_symbol_disagrees_with_explicit_stable_gene"),
        ]:
            result = self.qualify([item], fields=fields)
            self.assertEqual(result["status"], "source_identity_conflict")
            self.assertIn(reason, result["conflicts"])
            self.assertIsNone(result["hgnc_id"])
            self.assertIsNone(result["protein_id"])

    def test_unavailable_is_not_conflicting_and_present_unknown_is_not_silently_rescued(self):
        fields = {"HGNC": "hgnc", "ENSEMBL": "ensg"}
        result = self.qualify([row(ensg="NA")], fields=fields)
        self.assertEqual(result["gene_status"], "qualified")
        self.assertEqual(result["identifier_audit"][0]["status"], "unavailable")
        for item in [row(ensg="ENSG00000000099"), row(ensg="ENSG00000000001.2")]:
            result = self.qualify([item], fields=fields)
            self.assertEqual(result["status"], "source_identity_unresolved")
            self.assertIsNone(result["hgnc_id"])
        all_missing = self.qualify([row(hgnc="NA")])
        self.assertIn("no_explicit_source_stable_identifier", all_missing["reasons"])

    def test_nonunique_ensg_and_withdrawn_hgnc_are_not_selected_by_expected_context(self):
        registry, captured = registry_fixture(alias_collision=True)
        registry.genes["HGNC:2"]["ensembl_gene_id"] = "ENSG00000000001"
        result = self.qualify(fields={"HGNC": "hgnc", "ENSEMBL": "ensg"}, registry=registry, captured=captured)
        self.assertEqual(result["status"], "source_identity_unresolved")
        registry.genes["HGNC:1"]["status"] = "Entry Withdrawn"
        self.assertIsNone(self.qualify(registry=registry, captured=captured)["hgnc_id"])

    def test_isoform_secondary_or_absent_protein_is_not_remapped(self):
        for value in ["P00001-2", "Q99999", "HGNC:1"]:
            result = self.qualify([row(protein=value)], fields={"UniProtKB": "protein"})
            self.assertEqual(result["status"], "source_identity_unresolved")
            self.assertIsNone(result["protein_id"])

    def test_present_secondary_protein_conflict_remains_visible_without_qualification(self):
        registry, captured = registry_fixture()
        captured["P00001"]["GeneID"] = "2;"
        result = self.qualify(fields={"UniProtKB": "protein"}, registry=registry, captured=captured)
        self.assertEqual(result["status"], "source_identity_unresolved")
        self.assertIn("conflicting_secondary_GeneID_context", result["protein_audit"]["reasons"])
        self.assertIsNone(result["hgnc_id"])
        self.assertIsNone(result["protein_id"])

    def test_full_file_record_ordinal_and_canonical_raw_row_bindings_are_all_required(self):
        rows = [row(), row(native_id="record-B", symbol="BETA", hgnc="HGNC:2")]
        raw = source(rows); good = binding(raw, rows)
        for key, value in [("source_sha256", "0" * 64), ("source_record_id", "record-B"),
                           ("source_data_record_ordinal", 2), ("source_data_record_ordinal", True),
                           ("canonical_source_row_sha256", digest(rows[1]))]:
            with self.assertRaises(ValueError):
                self.qualify(rows, binding={**good, key: value})
        second = self.qualify(rows, binding=binding(raw, rows, 2))
        self.assertEqual(second["hgnc_id"], "HGNC:2")

    def test_explicit_column_and_missing_marker_contract_and_csv_structure_are_checked(self):
        for changes in [dict(identifier_fields={"NCBIGene": "hgnc"}),
                        dict(identifier_fields={"HGNC": "absent"}, unavailable_values={"symbol": [], "absent": []}),
                        dict(unavailable_values={"hgnc": []}), dict(delimiter=[]), dict(symbol_field="hgnc")]:
            with self.assertRaises(ValueError):
                self.qualify(**changes)
        raw = b"native_id,symbol,hgnc,hgnc\nrecord-A,ALPHA,HGNC:1,HGNC:1\n"
        with self.assertRaises(ValueError):
            qualify_scoped_identity(raw, binding={**binding(raw, [row()]), "source_sha256": hashlib.sha256(raw).hexdigest()},
                delimiter=",", record_id_field="native_id", identifier_fields={"HGNC": "hgnc"}, symbol_field="symbol",
                unavailable_values={"hgnc": [], "symbol": []}, registry=registry_fixture()[0], sequence_reference={})

    def test_source_and_registry_types_are_checked_before_resolution(self):
        for registry, captured in [(({}, registry_fixture()[0]), {}), (registry_fixture()[0], None)]:
            with self.assertRaises(TypeError):
                self.qualify(registry=registry, captured=captured)


if __name__ == "__main__":
    unittest.main()
