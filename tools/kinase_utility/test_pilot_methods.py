"""Deterministic invented identifiers, sequences, measurements and references."""
from copy import deepcopy
import csv
from io import StringIO
import inspect
import math
import unittest

import numpy as np

from biograph_steward.cohort_mapping import Registry
from pilot_methods import (approved_gene, map_measurement_identifier, parse_numeric_cell,
    parse_reference_csv, parse_sequence_reference, prepare_measurements,
    qualify_expected_targets, resolve_gene_protein, score_predictions)


def encoded(rows, delimiter="\t"):
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def gene(n, symbol, products=None, aliases="", previous="", status="Approved"):
    return {"hgnc_id": f"HGNC:{n}", "symbol": symbol, "status": status,
        "prev_symbol": previous, "alias_symbol": aliases,
        "uniprot_ids": products if products is not None else f"P{n:05d}",
        "entrez_id": str(n), "ensembl_gene_id": f"INVENTED{n}",
        "locus_type": "gene with protein product"}


def protein(n, symbol, gid=None, primary=None, accession=None):
    gid = gid or f"HGNC:{n}"
    return {"Entry": accession or f"P{n:05d}", "Gene Names (primary)": primary or symbol,
        "Gene Names (synonym)": "", "HGNC": gid + ";", "GeneID": str(n) + ";",
        "Organism (ID)": "9606", "Protein names": "INVENTED SOFTWARE FIXTURE"}


def fixture(genes=None, proteins=None):
    symbols = ["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON", "ZETA"]
    genes = genes or [gene(i, symbol) for i, symbol in enumerate(symbols, 1)]
    proteins = proteins or [protein(i, symbol) for i, symbol in enumerate(symbols, 1)]
    registry = Registry(encoded(genes), encoded(proteins))
    captured = {p["Entry"]: {"Entry": p["Entry"], "Gene Names (primary)": p["Gene Names (primary)"],
        "Organism (ID)": "9606", "Reviewed": "reviewed", "HGNC": p["HGNC"],
        "Sequence": "MSTYS", "Sequence version": "1", "capture_id": "INVENTED-CAPTURE"}
        for p in proteins}
    return registry, captured


def ks(enzyme="UniProtKB:P00001", host="UniProtKB:P00002", site="S2", **extra):
    return {"enzyme": enzyme, "site_host": host, "residue": site[0], "position": site[1:],
        "phosphorylation_incidence": 1, "source_record_ids": ["INVENTED-KS"], **extra}


def reference(condition="D1-C1", drug="D1", cell="C1", targets="ALPHA", sign=1):
    return {"condition": condition, "drug": drug, "cell": cell,
            "source_targets": targets, "expected_sign": sign}


class MeasurementMappingTests(unittest.TestCase):
    def test_explicit_missing_and_zero_and_invalid_numbers(self):
        self.assertEqual(parse_numeric_cell("0"), 0.0)
        self.assertEqual(parse_numeric_cell("-0.0"), 0.0)
        for token in ("", "NA", "NaN"):
            self.assertIsNone(parse_numeric_cell(token))
        for token in ("nan", "N/A", "inf", "-inf", "1e999", "NA "):
            with self.assertRaises(ValueError):
                parse_numeric_cell(token)

    def test_exact_three_fields_first_consistency_and_full_site_match(self):
        registry, captured = fixture()
        valid = map_measurement_identifier("ALPHA_S2|ALPHA|S2", registry, captured)
        self.assertEqual((valid["status"], valid["protein_id"], valid["site"]),
                         ("qualified", "UniProtKB:P00001", "S2"))
        for identifier in ("ALPHA_S2|ALPHA", "ALPHA_S2|ALPHA|S2|extra",
            "OTHER_S2|ALPHA|S2", "ALPHA_S02|ALPHA|S02", "ALPHA_S0|ALPHA|S0",
            "ALPHA_S2x|ALPHA|S2x", "ALPHA_s2|ALPHA|s2", "ALPHA_S2|ALPHA|S2\n"):
            self.assertEqual(map_measurement_identifier(identifier, registry, captured)["status"], "quarantined")
        for site in ("T2", "S20"):
            mapped = map_measurement_identifier(f"ALPHA_{site}|ALPHA|{site}", registry, captured)
            self.assertEqual(mapped["reasons"], ["observed_site_does_not_match_captured_sequence"])

    def test_no_namespace_case_or_shadowed_primary_fallback(self):
        registry, captured = fixture([gene(1, "ALPHA", aliases="OLD"), gene(2, "BETA", aliases="ALPHA")],
                                    [protein(1, "ALPHA"), protein(2, "BETA")])
        self.assertEqual(registry.resolve("OLD")["status"], "unique_registry_relation")
        for symbol in ("ALPHA", "alpha", "HGNC:1", "UniProtKB:P00001"):
            self.assertFalse(approved_gene(symbol, registry)["eligible"])
            mapped = map_measurement_identifier(f"{symbol}_S2|{symbol}|S2", registry, captured)
            self.assertEqual(mapped["status"], "protein_context_unresolved")

    def test_unique_hgnc_curated_legacy_uses_current_gene_and_preserves_relation(self):
        registry, captured = fixture([gene(1, "ALPHA", aliases="OLD_ALIAS", previous="OLD_NAME")],
                                    [protein(1, "ALPHA")])
        for token, field in (("OLD_ALIAS", "alias_symbol"), ("OLD_NAME", "prev_symbol")):
            mapped = map_measurement_identifier(f"{token}_S2|{token}|S2", registry, captured)
            self.assertEqual(mapped["status"], "qualified")
            self.assertEqual(mapped["protein_id"], "UniProtKB:P00001")
            self.assertEqual(mapped["reported_gene"], token)
            gene_mapping = mapped["gene_protein_mapping"]
            self.assertEqual(gene_mapping["approved_symbol"], "ALPHA")
            self.assertEqual(gene_mapping["accepted_relation_kind"], "curated_hgnc_legacy")
            self.assertEqual(gene_mapping["curated_hgnc_support"][0]["field"], field)
            self.assertEqual(gene_mapping["curated_hgnc_support"][0]["source_row"], 2)

    def test_uniprot_only_synonym_and_conflicting_hgnc_legacy_are_insufficient(self):
        p = protein(1, "ALPHA")
        p["Gene Names (synonym)"] = "ONLY_UP"
        registry, captured = fixture([gene(1, "ALPHA")], [p])
        self.assertEqual(registry.resolve("ONLY_UP")["status"], "unique_registry_relation")
        self.assertFalse(approved_gene("ONLY_UP", registry)["eligible"])
        registry, captured = fixture([gene(1, "ALPHA", aliases="OLD"), gene(2, "BETA", previous="OLD")],
                                    [protein(1, "ALPHA"), protein(2, "BETA")])
        self.assertEqual(registry.resolve("OLD")["status"], "ambiguous_registry_relation")
        self.assertFalse(approved_gene("OLD", registry)["eligible"])

    def test_total_product_count_rejects_one_confirmed_plus_unconfirmed(self):
        registry, captured = fixture([gene(1, "ALPHA", products="P00001|P00002")], [protein(1, "ALPHA")])
        self.assertEqual(len(registry.products("HGNC:1")), 2)
        mapped = resolve_gene_protein("ALPHA", registry, captured)
        self.assertEqual(mapped["reasons"], ["requires_exactly_one_total_registry_product"])
        self.assertIsNone(mapped["protein_id"])

    def test_shared_unconfirmed_registry_conflict_and_multiple_primary_quarantine(self):
        genes = [gene(1, "ALPHA"), gene(2, "BETA", products="P00001")]
        shared = protein(1, "ALPHA", gid="HGNC:1;HGNC:2", primary="INVENTED_SHARED")
        registry, captured = fixture(genes, [shared])
        self.assertIn("product_shared_or_sharing_unresolved",
                      resolve_gene_protein("ALPHA", registry, captured)["reasons"])
        registry, captured = fixture([gene(1, "ALPHA")], [protein(2, "BETA")])
        unresolved = resolve_gene_protein("ALPHA", registry, captured)
        self.assertIn("product_not_reviewed_human_hgnc_match", unresolved["reasons"])
        registry, captured = fixture([gene(1, "ALPHA")], [protein(1, "BETA", gid="HGNC:2")])
        conflict = resolve_gene_protein("ALPHA", registry, captured)
        self.assertEqual(conflict["protein_candidates"][0]["status"], "registry_conflict")
        self.assertIn("product_not_reviewed_human_hgnc_match", conflict["reasons"])
        registry, captured = fixture([gene(1, "ALPHA")], [protein(1, "ALPHA", primary="ALPHA BETA")])
        self.assertIn("registry_primary_gene_not_exact_single_approved_gene",
                      resolve_gene_protein("ALPHA", registry, captured)["reasons"])

    def test_captured_sequence_reference_requires_same_gene_taxon_and_accession(self):
        registry, captured = fixture()
        for field, value in (("Entry", "P99999"), ("Gene Names (primary)", "BETA"),
                             ("Organism (ID)", "10090"), ("Reviewed", "unreviewed"),
                             ("HGNC", "HGNC:2;"), ("Sequence", "mstys")):
            changed = deepcopy(captured)
            changed["P00001"][field] = value
            self.assertEqual(resolve_gene_protein("ALPHA", registry, changed)["status"],
                             "protein_context_unresolved")
        self.assertEqual(resolve_gene_protein("ALPHA", registry, {})["status"], "protein_context_unresolved")

    def test_captured_hgnc_distinct_set_must_be_exact_resolved_gene(self):
        registry, captured = fixture()
        for literal in ("HGNC:1;HGNC:2;", "HGNC:2;HGNC:1;", "HGNC:2;"):
            changed = deepcopy(captured)
            changed["P00001"]["HGNC"] = literal
            result = resolve_gene_protein("ALPHA", registry, changed)
            self.assertEqual(result["status"], "protein_context_unresolved")
            self.assertIsNone(result["protein_id"])
            self.assertIn("captured_hgnc_conflicts_with_resolved_gene", result["reasons"])
            self.assertEqual(result["sequence_reference"]["HGNC"], literal)
        for literal in ("HGNC:1;", "HGNC:1;HGNC:1;", ""):
            changed = deepcopy(captured)
            changed["P00001"]["HGNC"] = literal
            result = resolve_gene_protein("ALPHA", registry, changed)
            self.assertEqual(result["status"], "qualified")
            self.assertEqual(result["sequence_reference"]["HGNC"], literal)

    def test_sequence_tsv_reuses_strict_table_and_preserves_provenance(self):
        _, captured = fixture()
        raw = encoded(list(captured.values()))
        decoded = parse_sequence_reference(raw)
        self.assertEqual(decoded["P00001"]["capture_id"], "INVENTED-CAPTURE")
        self.assertEqual(decoded["P00001"]["reference_data_row_ordinal"], 1)
        with self.assertRaises(ValueError):
            parse_sequence_reference(encoded([captured["P00001"], captured["P00001"]]))

    def test_duplicate_groups_conflict_unique_finite_and_zero_are_not_averaged(self):
        registry, captured = fixture()
        raw = encoded([
            {"ID": "ALPHA_S2|ALPHA|S2", "C1": "0", "C2": "1", "C3": "NA"},
            {"ID": "ALPHA_S2|ALPHA|S2", "C1": "NaN", "C2": "2", "C3": ""},
            {"ID": "ALPHA_S2|ALPHA|S2", "C1": "0.0", "C2": "1.0", "C3": "NaN"},
            {"ID": "GAMMA_Y4|GAMMA|Y4", "C1": "-1", "C2": "0", "C3": "2"},
            {"ID": "UNKNOWN_S2|UNKNOWN|S2", "C1": "3", "C2": "4", "C3": "5"}], ",")
        links = [ks(), ks(), ks(enzyme="UniProtKB:P00004", site="T3")]
        prepared = prepare_measurements(raw, condition_ids=["C1", "C2", "C3"], registry=registry,
            sequence_reference=captured, qualified_ks_links=links, provenance={"dataset": "INVENTED"})
        self.assertEqual(prepared.enzyme_ids, ("UniProtKB:P00001", "UniProtKB:P00004"))
        self.assertEqual(prepared.Wkin2site.nnz, 2)
        self.assertTrue(np.all(prepared.Wkin2site.data == 1))
        self.assertEqual(prepared.Wsite2site.nnz, 0)
        alpha = prepared.site_ids.index(("UniProtKB:P00001", "S2"))
        self.assertEqual(prepared.X[alpha, 0], 0)
        self.assertTrue(math.isnan(prepared.X[alpha, 1]))
        self.assertTrue(math.isnan(prepared.X[alpha, 2]))
        self.assertIn(("UniProtKB:P00003", "Y4"), prepared.site_ids)  # Observed without KS.
        self.assertIn(("UniProtKB:P00002", "T3"), prepared.site_ids)  # KS without observation.
        group = next(x for x in prepared.aggregation if x["protein_id"] == "UniProtKB:P00001")
        self.assertEqual(group["measurement_data_row_ordinals"], [1, 2, 3])
        self.assertEqual(group["conditions"]["C2"]["unique_finite_values"], [1.0, 2.0])
        self.assertEqual(group["conditions"]["C2"]["status"], "conflicting_finite_values")
        self.assertEqual(prepared.provenance["unresolved_measurement_rows"], 1)
        self.assertFalse(prepared.provenance["metadata_accessed"])
        self.assertFalse(prepared.provenance["duplicate_groups_averaged"])
        self.assertEqual(len(prepared.rows), 5)
        self.assertEqual(prepared.rows[0]["mapping"]["gene_protein_mapping"]["sequence_reference"]["capture_id"],
                         "INVENTED-CAPTURE")

    def test_csv_not_tsv_and_preparation_has_no_metadata_interface(self):
        registry, captured = fixture()
        row = {"ID": "ALPHA_S2|ALPHA|S2", "C1": "0"}
        params = dict(condition_ids=["C1"], registry=registry, sequence_reference=captured, qualified_ks_links=[ks()])
        with self.assertRaises(ValueError):
            prepare_measurements(encoded([row], "\t"), **params)
        with self.assertRaises(ValueError):
            prepare_measurements(encoded([{**row, "expected_target": "ALPHA"}], ","), **params)
        self.assertFalse(any("reference" in key or "metadata" in key
                             for key in inspect.signature(prepare_measurements).parameters
                             if key != "sequence_reference"))
        with self.assertRaises(TypeError):
            prepare_measurements(encoded([row], ","), metadata_file="FORBIDDEN", **params)


class ReferenceTests(unittest.TestCase):
    def test_explicit_reference_csv_numeric_signs_and_no_label_inference(self):
        raw = encoded([
            {"case": "D1-C1", "drug_name": "D1", "cell_name": "C1", "genes": "ALPHA; BETA", "s": "+1"},
            {"case": "D1-C2", "drug_name": "D1", "cell_name": "C2", "genes": "GAMMA", "s": "-1.0"},
            {"case": "D2-C1", "drug_name": "D2", "cell_name": "C1", "genes": "DELTA", "s": "inhibited"}], ",")
        rows = parse_reference_csv(raw, condition_column="case", drug_column="drug_name", cell_column="cell_name",
            targets_column="genes", sign_column="s", provenance={"fixture": "INVENTED"})
        self.assertEqual([r["expected_sign"] for r in rows], [1, -1, None])
        self.assertEqual(rows[0]["source_targets"], "ALPHA; BETA")
        self.assertEqual(rows[2]["raw_sign"], "inhibited")

    def test_semicolons_only_duplicates_conflicts_invalid_symbols_and_signs(self):
        registry, _ = fixture()
        rows = [reference(targets=" ALPHA ;ALPHA; BETA"), reference(targets="ALPHA"),
            reference(targets="BETA", sign=-1), reference(targets="ALPHA,BETA; UNKNOWN"),
            reference(targets="GAMMA", sign=True)]
        result = qualify_expected_targets(rows, registry)
        self.assertEqual([(t["gene"], t["sign"]) for t in result.cases[0]["targets"]], [("ALPHA", 1)])
        self.assertEqual(result.duplicate_condition_target_sign_rows_collapsed, 2)
        counts = [x["reason"] for x in result.exclusions]
        self.assertIn("conflicting_expected_signs", counts)
        self.assertEqual(counts.count("reference_target_not_qualified_gene_token"), 2)
        self.assertIn("invalid_numeric_expected_sign", counts)

    def test_conflicting_case_context_is_reference_error(self):
        registry, _ = fixture()
        result = qualify_expected_targets([reference(), reference(drug="OTHER")], registry)
        self.assertEqual(result.cases, [])
        self.assertEqual(result.exclusions[0]["reason"], "conflicting_reference_condition_contexts")

    def test_primary_and_curated_legacy_references_collapse_same_atomic_gene(self):
        registry, _ = fixture([gene(1, "ALPHA", previous="OLD")], [protein(1, "ALPHA")])
        result = qualify_expected_targets([reference(targets="OLD; ALPHA")], registry)
        self.assertEqual(len(result.cases[0]["targets"]), 1)
        target = result.cases[0]["targets"][0]
        self.assertEqual((target["gene"], target["hgnc_id"]), ("ALPHA", "HGNC:1"))
        self.assertEqual(target["reported_tokens"], ["ALPHA", "OLD"])
        self.assertEqual(result.duplicate_condition_target_sign_rows_collapsed, 1)


class ScoringTests(unittest.TestCase):
    def test_average_ties_signed_ranking_missing_worst_and_zero(self):
        registry, _ = fixture()
        references = qualify_expected_targets([
            reference(targets="ALPHA; GAMMA; ZETA"),
            reference(condition="D1-C2", cell="C2", targets="BETA;DELTA", sign=-1)], registry)
        result = score_predictions({"D1-C1": {"ALPHA": 2, "BETA": 2, "GAMMA": 0, "DELTA": np.nan},
            "D1-C2": {"ALPHA": 1, "BETA": -3, "GAMMA": -3, "DELTA": None}}, references,
            candidate_genes=["ALPHA", "BETA", "GAMMA", "DELTA"], expected_cells=["C1", "C2"])
        targets = {(r["condition"], r["gene"]): r for r in result["per_target"]}
        self.assertEqual(targets["D1-C1", "ALPHA"]["rank"], 1.5)
        self.assertEqual(targets["D1-C2", "BETA"]["rank"], 1.5)
        self.assertEqual(targets["D1-C1", "GAMMA"]["activity"], 0)
        self.assertFalse(targets["D1-C1", "GAMMA"]["sign_agreement"])
        for key in (("D1-C1", "ZETA"), ("D1-C2", "DELTA")):
            self.assertEqual(targets[key]["rank"], 4)
            self.assertEqual(targets[key]["normalized_rank"], 1)
            self.assertTrue(targets[key]["abstained"])
            self.assertFalse(targets[key]["signed_top5_recovery"])  # M<5 does not turn abstention into a hit.
        self.assertEqual(result["coverage"]["scored_atomic_targets"], 3)
        self.assertEqual(result["coverage"]["abstained_atomic_targets"], 2)

    def test_hierarchy_condition_then_two_cells_then_drugs_not_atomic_weighting(self):
        registry, _ = fixture()
        references = qualify_expected_targets([
            reference("D1-C1", "D1", "C1", "ALPHA;BETA"),
            reference("D1-C2", "D1", "C2", "GAMMA"),
            reference("D2-C1", "D2", "C1", "ALPHA"),
            reference("D2-C2", "D2", "C2", "ALPHA")], registry)
        predictions = {c: {"ALPHA": 3, "BETA": 2, "GAMMA": 1} for c in ("D1-C1", "D1-C2", "D2-C1", "D2-C2")}
        result = score_predictions(predictions, references, candidate_genes=["ALPHA", "BETA", "GAMMA"], expected_cells=["C1", "C2"])
        # D1: mean( mean(1/3,2/3), 1 ) = .75; D2: 1/3; drug macro = 13/24.
        self.assertAlmostEqual(result["primary_macro_normalized_rank"], 13 / 24)
        self.assertNotAlmostEqual(result["primary_macro_normalized_rank"], (1+2+3+1+1) / 15)

    def test_valid_hgnc_outside_universe_abstains_invalid_reference_excluded(self):
        registry, _ = fixture()
        references = qualify_expected_targets([reference(targets="ZETA;UNKNOWN"),
            reference("D1-C2", "D1", "C2", "ZETA")], registry)
        result = score_predictions({}, references, candidate_genes=["ALPHA", "BETA"], expected_cells=["C1", "C2"])
        self.assertEqual(result["primary_macro_normalized_rank"], 1)
        self.assertEqual(result["coverage"]["qualified_atomic_reference_targets"], 2)
        self.assertEqual(result["coverage"]["abstained_atomic_targets"], 2)
        self.assertEqual(result["macro_sign_agreement"], 0)
        self.assertEqual(result["macro_signed_top5_recovery"], 0)
        self.assertEqual(result["per_target"][0]["abstention_reason"], "valid_target_outside_fixed_prediction_universe")

    def test_missing_condition_and_conflicting_reference_are_separate(self):
        registry, _ = fixture()
        references = qualify_expected_targets([reference(), reference("D1-C2", "D1", "C2", "ALPHA"),
            reference("D2-C1", "D2", "C1", "BETA"), reference("D2-C1", "D2", "C1", "BETA", -1)], registry)
        result = score_predictions({"D1-C1": {"ALPHA": 2}}, references,
            candidate_genes=["ALPHA", "BETA"], expected_cells=["C1", "C2"])
        self.assertEqual(result["coverage"]["qualified_atomic_reference_targets"], 2)
        self.assertEqual(result["coverage"]["abstained_atomic_targets"], 1)
        self.assertEqual(result["per_target"][1]["abstention_reason"], "condition_predictions_missing")
        self.assertIn("conflicting_expected_signs", [r["reason"] for r in result["reference_exclusions"]])

    def test_incomplete_cell_reference_group_not_model_error_or_one_cell_macro(self):
        registry, _ = fixture()
        references = qualify_expected_targets([reference()], registry)
        result = score_predictions({"D1-C1": {"ALPHA": 1}}, references,
            candidate_genes=["ALPHA"], expected_cells=["C1", "C2"])
        self.assertIsNone(result["primary_macro_normalized_rank"])
        self.assertEqual(result["coverage"]["abstained_atomic_targets"], 0)
        self.assertEqual(len(result["unscorable_reference_drug_groups"]), 1)

    def test_top5_average_tie_boundary_and_sign_agreement_are_distinct(self):
        registry, _ = fixture()
        references = qualify_expected_targets([reference(targets="EPSILON;ZETA"),
            reference("D1-C2", "D1", "C2", "EPSILON;ZETA")], registry)
        values = dict(zip(["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON", "ZETA"], [4, 3, 2, 1, -1, -1]))
        result = score_predictions({"D1-C1": values, "D1-C2": values}, references,
            candidate_genes=list(values), expected_cells=["C1", "C2"])
        self.assertTrue(all(r["rank"] == 5.5 for r in result["per_target"]))
        self.assertEqual(result["macro_signed_top5_recovery"], 0)
        self.assertEqual(result["macro_sign_agreement"], 0)
        self.assertEqual(result["coverage"]["atomic_target_score_coverage"], 1)

    def test_fixed_roster_rejects_extra_genes_duplicate_roster_and_string_scores(self):
        registry, _ = fixture()
        references = qualify_expected_targets([reference()], registry)
        for predictions, candidates in (({"D1-C1": {"BETA": 1}}, ["ALPHA"]),
            ({}, ["ALPHA", "ALPHA"]), ({"D1-C1": {"ALPHA": "1"}}, ["ALPHA"]),
            ({"D1-C1": {"ALPHA": True}}, ["ALPHA"])):
            with self.assertRaises(ValueError):
                score_predictions(predictions, references, candidate_genes=candidates, expected_cells=["C1", "C2"])


if __name__ == "__main__":
    unittest.main()
