from copy import deepcopy
import unittest

from run_signature_comparison import numeric_values, validate_plan, validate_candidate_roster
from biograph_steward.cohort_mapping import SOURCES
from test_source_identity import fixture as identity_fixture


def fixture():
    paths = ["/invented/protein.xlsx", "/invented/sites.xlsx", "/invented/roster.json",
             "/invented/sequences.tsv", "/invented/membership.jsonl", "/invented/registry/manifest.json",
             *["/invented/registry/" + name for name in SOURCES]]
    pins = {path: "0" * 64 for path in paths}
    def workbook(path, role):
        fields = ({"accession": 0, "source_group_count": 5, "source_unique_peptides": 6} if role == "protein"
                  else {"accession": 0, "peptide": 1, "protein_site": 2, "modification_names": 3, "modification_positions": 4})
        return {"path": path, "contract": {"workbook_sha256": pins[path], "sheet_name": "Declared",
            "headers": ["Accession", "Peptide", "Site", "Mods", "Positions", "Groups", "Unique", "Sample", "Sample"],
            "fields": fields, "accession_syntax": "bare_uniprot", "peptide_syntax": "plain_uppercase",
            "protein_site_syntax": "residue_position", "modification_syntax": "alphabase_separate", "quant_columns": [
            {"sample_id": sample, "index": i + 7, "unit": "source_reported_normalized_TMT_intensity"}
            for i, sample in enumerate(["control", "intervention"])]}}
    return {"files_sha256": pins, "sample_groups": {"reference": ["control"], "new_question": ["intervention"]},
        "control_group": "reference", "minimum_finite_distinct_sites": 5,
        "roster_identity_policy": "source_frozen_gene_product_correspondence.v1",
        "workbooks": {"protein": workbook(paths[0], "protein"), "phosphosite": workbook(paths[1], "phosphosite")},
        "candidate_roster": paths[2], "sequence_reference": paths[3], "registry_directory": "/invented/registry",
        "signature_profiles": {"source": {"path": paths[4], "kind": "complete_candidate_universe"}},
        "expected_cases": [{"condition": "new_question", "target": "INVENTED", "sign": -1}]}


class SignatureRunnerTests(unittest.TestCase):
    def test_profile_has_no_fixed_study_cell_or_sample_names(self):
        validate_plan(fixture())

    def test_unpinned_role_and_partial_only_catalogue_fail_before_access(self):
        plan = fixture(); del plan["files_sha256"][plan["sequence_reference"]]
        with self.assertRaises(ValueError):
            validate_plan(plan)
        plan = fixture(); plan["signature_profiles"]["source"]["kind"] = "partial_signature_diagnostic"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_units_samples_and_reference_population_must_be_declared(self):
        mutations = [
            lambda p: p["workbooks"]["protein"]["contract"]["quant_columns"][0].update(unit=None),
            lambda p: p["workbooks"]["phosphosite"]["contract"]["quant_columns"][1].update(sample_id="unknown"),
            lambda p: p["expected_cases"][0].update(condition="unstated"),
            lambda p: p["sample_groups"].update(reference=None),
            lambda p: p["workbooks"]["phosphosite"]["contract"]["fields"].pop("protein_site"),
        ]
        for mutate in mutations:
            plan = fixture(); mutate(plan)
            with self.assertRaises(ValueError):
                validate_plan(plan)

    def test_native_zero_survives_and_formula_boolean_text_are_not_coerced(self):
        template = {"formula": None, "cell_type": "n", "text": "0", "address": "A2"}
        cells = [
            ("zero", template, "source_literal"),
            ("formula", {**template, "formula": {"text": "1+1"}, "text": "2"}, "source_literal"),
            ("boolean", {**template, "cell_type": "b", "text": "1"}, "source_literal"),
            ("textnumber", {**template, "cell_type": "s", "text": "5"}, "source_literal"),
            ("missing", {**template, "text": None}, "missing_cell"),
        ]
        raw = {"raw_quant_values": [{"sample_id": name, "cell": deepcopy(cell), "source_value_state": state}
                                     for name, cell, state in cells]}
        original = deepcopy(raw)
        values, diagnostics = numeric_values(raw)
        self.assertEqual(values["zero"], 0)
        self.assertTrue(all(values[name] is None for name in ["formula", "boolean", "textnumber", "missing"]))
        self.assertEqual(len(diagnostics), 4)
        self.assertEqual(raw, original)

    def test_audit_warning_does_not_silently_redefine_frozen_catalogue_policy(self):
        registry, sequences = identity_fixture()
        registry.proteins["P00001"]["ncbi_gene_ids"] = ["1", "3"]
        sequences["P00001"]["GeneID"] = "1;3;"
        roster = [{"gene": "ALPHA", "enzyme": "UniProtKB:P00001", "hgnc_id": "HGNC:1"}]
        audit = validate_candidate_roster(roster, registry, sequences,
            policy="source_frozen_gene_product_correspondence.v1")
        self.assertTrue(audit[0]["source_correspondence_qualified"])
        self.assertEqual(audit[0]["separate_identity_audit"]["status"], "source_protein_context_unresolved")
        self.assertFalse(audit[0]["audit_changes_source_admission"])
        with self.assertRaises(ValueError):
            validate_candidate_roster(roster, registry, sequences, policy="silently_changed_policy")


if __name__ == "__main__":
    unittest.main()
