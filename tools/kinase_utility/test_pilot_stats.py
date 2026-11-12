"""Invented-only tests of the frozen pilot's pure assessment helper."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "claim_methods"))
from pilot_methods import QualifiedReferences, score_predictions
from pilot_stats import (ARMS, COMPARATORS, PRIMARY, DRAWS, SEED,
                         assess_pilot, bootstrap_paired_rank_differences)

CANDIDATES = tuple("ABCDEF")
CELLS = ("CELL1", "CELL2")


def case(drug, cell, genes, sign=-1):
    return {"condition": drug + ":" + cell, "drug": drug, "cell": cell,
            "targets": [{"gene": g, "hgnc_id": "HGNC:" + str(CANDIDATES.index(g) + 1),
                "sign": sign, "reported_tokens": [g], "gene_correspondence_records": [],
                "input_ordinals": [1]} for g in genes]}


def references(n=5):
    rows = []
    for i in range(n):
        genes = [CANDIDATES[i % 6], CANDIDATES[(i + 1) % 6]]
        rows.extend(case("DRUG" + str(i), cell, genes) for cell in CELLS)
    return QualifiedReferences(rows, [], 0, [])


def predictions(refs, level="good"):
    result = {}
    for row in refs.cases:
        targets = {x["gene"] for x in row["targets"]}
        if level == "good":
            result[row["condition"]] = {g: -10 if g in targets else 0 for g in CANDIDATES}
        else:
            result[row["condition"]] = {g: -1 if g in targets else -2 for g in CANDIDATES}
    return result


def scored(preds, refs, candidates=CANDIDATES):
    return score_predictions(preds, refs, candidate_genes=list(candidates), expected_cells=list(CELLS))


def arms(refs=None):
    refs = refs if refs is not None else references()
    return {arm: scored(predictions(refs, "good" if arm == PRIMARY else "bad"), refs) for arm in ARMS}


class BootstrapTests(unittest.TestCase):
    def test_n0_and_n1_intervals_unavailable(self):
        for values, expected_mean in (({}, None), ({"ONLY": -0.25}, -0.25)):
            result = bootstrap_paired_rank_differences({c: dict(values) for c in COMPARATORS})
            self.assertFalse(result["available"])
            self.assertEqual(result["n_drugs"], len(values))
            for c in COMPARATORS:
                self.assertIsNone(result["comparisons"][c]["percentile95_interval"])
                self.assertEqual(result["comparisons"][c]["mean_primary_minus_comparator"], expected_mean)
                self.assertFalse(result["comparisons"][c]["upper95_bound_below_zero"])

    def test_manual_two_drug_distribution_and_fixed_randomness(self):
        maps = {COMPARATORS[0]: {"B": 0.4, "A": -0.2},
                COMPARATORS[1]: {"A": -0.4, "B": 0.2}}
        result = bootstrap_paired_rank_differences(maps)
        self.assertEqual(result, bootstrap_paired_rank_differences(maps))
        self.assertEqual(result["drug_ids"], ["A", "B"])
        self.assertEqual((result["draws"], result["seed"]), (10000, 20261112))
        # For two draws from two labels, possible means are low, midpoint, high
        # with probabilities1/4,1/2,1/4. The percentile95 endpoints are low/high.
        self.assertAlmostEqual(result["comparisons"][COMPARATORS[0]]["mean_primary_minus_comparator"], 0.1)
        self.assertAlmostEqual(result["comparisons"][COMPARATORS[1]]["mean_primary_minus_comparator"], -0.1)
        np.testing.assert_allclose(result["comparisons"][COMPARATORS[0]]["percentile95_interval"], [-0.2, 0.4])
        np.testing.assert_allclose(result["comparisons"][COMPARATORS[1]]["percentile95_interval"], [-0.4, 0.2])

    def test_constant_differences_and_upper_bound_strictly_below_zero(self):
        maps = {COMPARATORS[0]: {"A": -0.1, "B": -0.1},
                COMPARATORS[1]: {"A": 0, "B": 0}}
        result = bootstrap_paired_rank_differences(maps)
        self.assertTrue(result["comparisons"][COMPARATORS[0]]["upper95_bound_below_zero"])
        self.assertFalse(result["comparisons"][COMPARATORS[1]]["upper95_bound_below_zero"])
        np.testing.assert_allclose(result["comparisons"][COMPARATORS[0]]["percentile95_interval"], [-0.1, -0.1])

    def test_reject_unpaired_labels_missing_comparator_and_nonfinite(self):
        invalid = [{COMPARATORS[0]: {}},
                   {COMPARATORS[0]: {"A": 0}, COMPARATORS[1]: {"B": 0}},
                   {c: {"A": np.nan} for c in COMPARATORS},
                   {c: {"A": True} for c in COMPARATORS}]
        for value in invalid:
            with self.assertRaises(ValueError):
                bootstrap_paired_rank_differences(value)


class AssessmentTests(unittest.TestCase):
    def test_fixed_seven_arms_positive_gates_and_hand_computed_delta(self):
        value = arms()
        result = assess_pilot(value)
        self.assertTrue(result["coverage_floor"]["passed"])
        self.assertEqual(result["primary_population"]["primary_condition_target_cases"], 20)
        self.assertEqual(result["primary_population"]["primary_complete_drugs"], 5)
        self.assertEqual(result["primary_population"]["primary_distinct_resolved_target_genes"], 6)
        self.assertTrue(result["point_estimate_benefit_gate_passed"])
        self.assertTrue(result["stronger_within_benchmark_support_gate_passed"])
        for c in COMPARATORS:
            self.assertAlmostEqual(result["paired_rank_bootstrap"]["comparisons"][c]["mean_primary_minus_comparator"], -4 / 6)
        self.assertEqual(set(result["arm_summaries"]), set(ARMS))

    def test_incomplete_groups_cannot_supply_primary_floor(self):
        rows = [case("COMPLETE", cell, ["A"]) for cell in CELLS]
        rows += [case("PARTIAL" + str(i), CELLS[0], list("ABCDE")) for i in range(4)]
        refs = QualifiedReferences(rows, [], 0, [])
        result = assess_pilot(arms(refs))
        self.assertEqual(result["all_qualified_reference_population"]["condition_target_cases"], 22)
        self.assertEqual(result["all_qualified_reference_population"]["distinct_target_genes"], 5)
        self.assertEqual(result["primary_population"]["primary_condition_target_cases"], 2)
        self.assertEqual(result["primary_population"]["primary_distinct_resolved_target_genes"], 1)
        self.assertEqual(result["primary_population"]["primary_complete_drugs"], 1)
        self.assertEqual(len(result["incomplete_reference_drug_groups"]), 4)
        self.assertFalse(result["coverage_floor"]["passed"])
        self.assertFalse(result["point_estimate_benefit_gate_passed"])

    def test_floor_requires_all_four_counts_including_five_drugs(self):
        rows = [case("D" + str(i), cell, list(CANDIDATES)) for i in range(4) for cell in CELLS]
        result = assess_pilot(arms(QualifiedReferences(rows, [], 0, [])))
        self.assertTrue(result["coverage_floor"]["checks"]["primary_condition_target_cases"])
        self.assertTrue(result["coverage_floor"]["checks"]["primary_distinct_resolved_target_genes"])
        self.assertTrue(result["coverage_floor"]["checks"]["primary_cells"])
        self.assertFalse(result["coverage_floor"]["checks"]["primary_complete_drugs"])
        self.assertFalse(result["point_estimate_benefit_gate_passed"])

    def test_empty_and_one_drug_assessment_has_no_available_ci_or_claim(self):
        for n in (0, 1):
            result = assess_pilot(arms(references(n)))
            self.assertEqual(result["primary_population"]["primary_complete_drugs"], n)
            self.assertFalse(result["paired_rank_bootstrap"]["available"])
            self.assertFalse(result["point_estimate_benefit_gate_passed"])
            self.assertFalse(result["stronger_within_benchmark_support_gate_passed"])
            if n == 0:
                self.assertIsNone(result["arm_summaries"][PRIMARY]["macro"]["normalized_rank"])

    def test_zero_opposite_missing_categories_same_primary_population(self):
        rows = [case("D", cell, list("ABCD"), sign=1) for cell in CELLS]
        rows += [case("PARTIAL", CELLS[0], ["A"], sign=1)]
        refs = QualifiedReferences(rows, [{"reason": "INVENTED_EXCLUSION"}], 2, [])
        pred = {r["condition"]: {"A": 1, "B": 0, "C": -1, "D": None, "E": 0, "F": 0} for r in rows}
        result = assess_pilot({arm: scored(pred, refs) for arm in ARMS})
        self.assertEqual(result["primary_direction_categories"]["counts"],
                         {"agreement": 2, "zero": 2, "opposite": 2, "missing": 2})
        self.assertEqual(result["primary_direction_categories"]["same_population_drug_macro_fractions"],
                         {"agreement": .25, "zero": .25, "opposite": .25, "missing": .25})
        self.assertEqual(result["all_qualified_reference_population"]["reference_exclusion_records"], 1)
        self.assertEqual(result["all_qualified_reference_population"]["duplicate_condition_target_sign_rows_collapsed"], 2)

    def test_ties_and_model_abstention_remain_qualified_reference_cases(self):
        refs = references()
        ties = {r["condition"]: {g: 0 for g in CANDIDATES} for r in refs.cases}
        result = assess_pilot({a: scored(ties, refs) for a in ARMS})
        self.assertAlmostEqual(result["arm_summaries"][PRIMARY]["macro"]["normalized_rank"], 3.5 / 6)
        self.assertEqual(result["primary_direction_categories"]["counts"]["zero"], 20)
        self.assertFalse(result["point_estimate_benefit_gate_passed"])
        missing = {r["condition"]: {} for r in refs.cases}
        result = assess_pilot({a: scored(missing, refs) for a in ARMS})
        self.assertTrue(result["coverage_floor"]["passed"])
        self.assertEqual(result["primary_population"]["primary_condition_target_cases"], 20)
        self.assertEqual(result["primary_direction_categories"]["counts"]["missing"], 20)
        self.assertEqual(result["arm_summaries"][PRIMARY]["macro"]["normalized_rank"], 1)
        self.assertEqual(result["arm_summaries"][PRIMARY]["macro"]["target_score_coverage"], 0)
        self.assertFalse(result["point_estimate_benefit_gate_passed"])

    def test_primary_must_beat_both_comparators(self):
        value = arms()
        value[COMPARATORS[1]] = deepcopy(value[PRIMARY])
        result = assess_pilot(value)
        self.assertTrue(result["primary_comparison_checks"][COMPARATORS[0]]["rank_lower"])
        self.assertFalse(result["primary_comparison_checks"][COMPARATORS[1]]["rank_lower"])
        self.assertFalse(result["point_estimate_benefit_gate_passed"])

    def test_coverage_nonworsening_is_a_distinct_guard(self):
        refs = references()
        value = arms(refs)
        pred = predictions(refs)
        first = refs.cases[0]
        pred[first["condition"]][first["targets"][0]["gene"]] = None
        value[PRIMARY] = scored(pred, refs)
        result = assess_pilot(value)
        for c in COMPARATORS:
            self.assertTrue(result["primary_comparison_checks"][c]["rank_lower"])
            self.assertFalse(result["primary_comparison_checks"][c]["target_score_coverage_not_worse"])
        self.assertFalse(result["point_estimate_benefit_gate_passed"])

    def test_direction_nonworsening_is_a_distinct_guard(self):
        refs = references()
        pred = {r["condition"]: {g: 1 if g in {t["gene"] for t in r["targets"]} else 2
                                for g in CANDIDATES} for r in refs.cases}
        value = arms(refs)
        value[PRIMARY] = scored(pred, refs)
        result = assess_pilot(value)
        for c in COMPARATORS:
            self.assertTrue(result["primary_comparison_checks"][c]["rank_lower"])
            self.assertFalse(result["primary_comparison_checks"][c]["sign_agreement_not_worse"])
        self.assertFalse(result["point_estimate_benefit_gate_passed"])

    def test_top5_nonworsening_is_a_distinct_guard(self):
        refs = references()
        value = arms(refs)
        pred = predictions(refs)
        for row in refs.cases[:2]:
            pred[row["condition"]] = predictions(QualifiedReferences([row], [], 0, []), "bad")[row["condition"]]
        value[PRIMARY] = scored(pred, refs)
        control = predictions(refs)
        for row in refs.cases:
            target = {t["gene"] for t in row["targets"]}
            others = [g for g in CANDIDATES if g not in target]
            control[row["condition"]] = {g: -1 if g in target else -2 if g in others[:3] else 0 for g in CANDIDATES}
        for c in COMPARATORS:
            value[c] = scored(control, refs)
        result = assess_pilot(value)
        self.assertTrue(result["primary_comparison_checks"][COMPARATORS[0]]["rank_lower"])
        self.assertFalse(result["primary_comparison_checks"][COMPARATORS[0]]["signed_top5_recovery_not_worse"])
        self.assertFalse(result["point_estimate_benefit_gate_passed"])

    def test_per_cell_guard_uses_same_complete_drugs_and_detects_harm(self):
        refs = references()
        value = arms(refs)
        primary_pred, native_pred = predictions(refs), predictions(refs)
        for row in refs.cases:
            targets = {t["gene"] for t in row["targets"]}
            others = [g for g in CANDIDATES if g not in targets]
            if row["cell"] == CELLS[0]:
                primary_pred[row["condition"]] = {g: -1 if g in targets else -2 for g in CANDIDATES}
                native_pred[row["condition"]] = {g: -1 if g in targets else -2 if g in others[:2] else 0 for g in CANDIDATES}
            else:
                native_pred[row["condition"]] = {g: -1 if g in targets else -2 for g in CANDIDATES}
        value[PRIMARY], value[COMPARATORS[0]] = scored(primary_pred, refs), scored(native_pred, refs)
        result = assess_pilot(value)
        check = result["primary_comparison_checks"][COMPARATORS[0]]
        self.assertTrue(check["rank_lower"])
        self.assertTrue(check["signed_top5_recovery_not_worse"])
        self.assertFalse(check["per_cell_rank_not_worse"][CELLS[0]])
        self.assertTrue(check["per_cell_rank_not_worse"][CELLS[1]])
        self.assertFalse(result["point_estimate_benefit_gate_passed"])

    def test_stronger_ne_stays_visible_without_primary_promotion(self):
        refs = references()
        value = arms(refs)
        pred = predictions(refs)
        for row in refs.cases:
            targets = {t["gene"] for t in row["targets"]}
            one_other = next(g for g in CANDIDATES if g not in targets)
            pred[row["condition"]][one_other] = -11
        value[PRIMARY] = scored(pred, refs)
        value["rokai_ne_zscore"] = scored(predictions(refs), refs)
        result = assess_pilot(value)
        self.assertTrue(result["NE_mean_rank_lower_than_primary"])
        self.assertEqual(result["preselected_primary"], PRIMARY)
        self.assertTrue(result["point_estimate_benefit_gate_passed"])

    def test_rank_point_gate_and_interval_support_gate_are_distinct(self):
        refs = references()
        value = arms(refs)
        primary_pred = predictions(refs)
        # One drug has target meanrank4.5, four have meanrank1.5, and the
        # controls have meanrank2.5. All targets remain top5 and correct-sign.
        # The point gate passes, but resampling can overrepresent the harmed drug.
        for row in refs.cases[:2]:
            targets = {t["gene"] for t in row["targets"]}
            others = [g for g in CANDIDATES if g not in targets]
            primary_pred[row["condition"]] = {g: -1 if g in targets else -2 if g in others[:3] else 0
                                              for g in CANDIDATES}
        control = predictions(refs)
        for row in refs.cases:
            targets = {t["gene"] for t in row["targets"]}
            other = next(g for g in CANDIDATES if g not in targets)
            control[row["condition"]][other] = -11  # target meanrank2.5
        # A negative paired mean and all no-harm guards are not sufficient for
        # both descriptive percentile intervals to exclude0.
        value[PRIMARY] = scored(primary_pred, refs)
        for c in COMPARATORS:
            value[c] = scored(control, refs)
        result = assess_pilot(value)
        for c in COMPARATORS:
            self.assertTrue(result["primary_comparison_checks"][c]["rank_lower"])
            self.assertGreaterEqual(result["paired_rank_bootstrap"]["comparisons"][c]["percentile95_interval"][1], 0)
        self.assertTrue(result["point_estimate_benefit_gate_passed"])
        self.assertFalse(result["both_rank_intervals_upper95_below_zero"])
        self.assertFalse(result["stronger_within_benchmark_support_gate_passed"])

    def test_fixed_arm_candidate_reference_and_primary_ids_must_match(self):
        for change in ("missing_arm", "candidate_order", "reference_targets", "drug_ids", "macro"):
            value = arms()
            if change == "missing_arm":
                value.pop("raw_mean")
            elif change == "candidate_order":
                refs = references()
                value["raw_mean"] = scored(predictions(refs), refs, tuple(reversed(CANDIDATES)))
            elif change == "reference_targets":
                refs = references()
                refs.cases[0]["targets"][0]["sign"] = 1
                value["raw_mean"] = scored(predictions(refs), refs)
            elif change == "drug_ids":
                value["raw_mean"]["per_drug"] = value["raw_mean"]["per_drug"][:-1]
            else:
                value["raw_mean"]["primary_macro_normalized_rank"] += .1
            with self.assertRaises(ValueError, msg=change):
                assess_pilot(value)

    def test_reject_inconsistent_abstention_and_repeated_reference_target(self):
        value = arms()
        value[PRIMARY]["per_target"][0]["abstained"] = True
        with self.assertRaises(ValueError):
            assess_pilot(value)
        value = arms()
        value[PRIMARY]["per_target"].append(deepcopy(value[PRIMARY]["per_target"][0]))
        with self.assertRaises(ValueError):
            assess_pilot(value)

    def test_input_results_not_mutated_and_output_reproducible(self):
        value = arms()
        before = deepcopy(value)
        self.assertEqual(assess_pilot(value), assess_pilot(value))
        self.assertEqual(value, before)


if __name__ == "__main__":
    unittest.main()
