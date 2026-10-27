"""Guard the frozen panel's eligibility without opening reference bodies."""
from copy import deepcopy
import unittest

from scripts.inspect_intact_development import assess, source_lines, DEVELOPMENT, RESERVED


def xref(db, accession):
    return {"database": {"name": db}, "id": accession}


def row():
    fields = {key: {"status": "parsed", "values": value} for key, value in {
        "primary_ids_a": [xref("uniprotkb", "P12345-2")],
        "primary_ids_b": [xref("uniprotkb", "Q12345")],
        "taxa_a": [{"taxid": 9606}], "taxa_b": [{"taxid": 9606}],
        "interactor_types_a": [{"mi_id": "MI:0326"}],
        "interactor_types_b": [{"mi_id": "MI:0326"}],
        "publication_ids": [xref("pubmed", "99999999")],
        "source_databases": [{"mi_id": "MI:0469", "name": "intact"}],
        "evidence_ids": [xref("intact", "EBI-SYNTHETIC")],
        "host_taxa": [{"taxid": -1}],
    }.items()}
    return {"row_status": "parsed", "raw_cells": ["-"] * 42,
            "source_fields": fields, "parsed_count": 1, "diagnostics": [],
            "interaction": {"participants": [{"side": "A"}, {"side": "B"}]}}


class IntactDevelopmentGuards(unittest.TestCase):
    def test_human_participants_are_separate_from_in_vitro_host(self):
        result = assess(row(), "99999999")
        self.assertTrue(result["eligible"])
        self.assertEqual(result["source_hosts"], [{"taxid": -1}])
        self.assertEqual(result["source_participants"][0]["uniprot_accessions"], ["P12345-2"])
        self.assertEqual(result["negative_origin"], "mitab27_default_false")
        self.assertEqual(result["binary_origin"], "unknown_no_inference")

    def test_inferred_model_type_does_not_replace_missing_source_type(self):
        source = row()
        source["source_fields"]["interactor_types_a"] = {"status": "missing", "values": []}
        source["interaction"]["participants"][0]["interactor_type"] = {"mi_id": "MI:0326"}
        self.assertFalse(assess(source, "99999999")["eligible"])

    def test_multivalue_method_loss_remains_in_eligible_denominator(self):
        source = row()
        source["diagnostics"] = [{"callback": "onSeveralCvTermsFound", "phase": "row_model"}]
        result = assess(source, "99999999")
        self.assertTrue(result["eligible"])
        self.assertEqual(result["object_projection_limitations"], [{"callback": "onSeveralCvTermsFound", "count": 1}])

    def test_invalid_negative_does_not_become_positive_evidence(self):
        source = row()
        source["raw_cells"][35] = "maybe"
        source["interaction"]["negative"] = False
        result = assess(source, "99999999")
        self.assertFalse(result["eligible"])
        self.assertIsNone(result["negative_value"])
        self.assertIn("negative_literal_invalid", result["exclusion_reasons"])

    def test_negative_expanded_and_optional_missing_remain_eligible(self):
        source = row()
        source["raw_cells"][35] = "true"
        source["raw_cells"][15] = 'psi-mi:"MI:1060"(spoke expansion)'
        result = assess(source, "99999999")
        self.assertTrue(result["eligible"])
        self.assertTrue(result["negative_value"])
        self.assertEqual(result["expansion_origin"], "supplied")

    def test_conflicting_identity_and_taxon_not_resolved_by_first_model_value(self):
        source = row()
        source["source_fields"]["taxa_a"]["values"].append({"taxid": 10090})
        source["source_fields"]["primary_ids_b"]["values"].append(xref("uniprotkb", "Q12346"))
        self.assertFalse(assess(source, "99999999")["eligible"])

    def test_missing_selected_pmid_and_field_error_are_explicit_exclusions(self):
        source = row()
        source["source_fields"]["publication_ids"]["values"] = [xref("pubmed", "99999998")]
        source["source_fields"]["detection_methods"] = {"status": "invalid", "values": []}
        reasons = assess(source, "99999999")["exclusion_reasons"]
        self.assertIn("publication_missing_selected_pmid", reasons)
        self.assertIn("source_field_invalid", reasons)

    def test_extra_explicit_provenance_is_preserved_without_posthoc_narrowing(self):
        source = row()
        source["source_fields"]["publication_ids"]["values"].append(xref("pubmed", "99999998"))
        source["source_fields"]["primary_ids_a"]["values"].append(xref("refseq", "NP_SYNTHETIC"))
        source["source_fields"]["evidence_ids"]["values"] = [xref("imex", "IM-SYNTHETIC-1")]
        result = assess(source, "99999999")
        self.assertTrue(result["eligible"])
        self.assertEqual(len(result["publication_ids"]), 2)
        self.assertEqual(len(result["source_participants"][0]["primary_ids"]), 2)

    def test_multi_source_provenance_is_not_silently_narrowed_to_intact(self):
        source = row()
        source["source_fields"]["source_databases"]["values"].append({"mi_id": None, "name": "irefindex"})
        result = assess(source, "99999999")
        self.assertTrue(result["eligible"])
        self.assertTrue(result["provenance_multiplicity_requires_grouping_audit"])

    def test_invalid_accession_and_recovered_stoichiometry_are_ineligible(self):
        source = row()
        source["source_fields"]["primary_ids_a"]["values"][0]["id"] = "not_an_accession"
        self.assertFalse(assess(source, "99999999")["eligible"])
        source = row()
        source["diagnostics"] = [{"callback": "onInvalidStoichiometry"}]
        source["raw_cells"][38] = "not_an_integer"
        result = assess(source, "99999999")
        self.assertFalse(result["eligible"])
        self.assertIn("reader_invalid_stoichiometry", result["exclusion_reasons"])

    def test_physical_line_framing_and_disjoint_allowlist(self):
        self.assertEqual(source_lines(b"# header\r\na\tb\r\n\r\n"), ["# header", "a\tb", ""])
        with self.assertRaises(ValueError):
            source_lines(b"a\rb\n")
        self.assertFalse(set(DEVELOPMENT) & RESERVED)


if __name__ == "__main__":
    unittest.main()
