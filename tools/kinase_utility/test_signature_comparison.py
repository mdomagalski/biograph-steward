import math
import unittest

from signature_comparison import (
    adjust_for_host_protein, collapse_site_contrasts, infer_scores,
    log2_contrasts, score_recovery,
)


class SignatureComparisonTests(unittest.TestCase):
    def test_nonpaired_log_contrast_and_observed_zero(self):
        result = log2_contrasts({"a": 2, "b": 8, "c": 4, "d": 16, "e": 2, "f": 8},
            groups={"reference": ["a", "b"], "treatment": ["c", "d"], "equal": ["e", "f"]}, control="reference")
        self.assertEqual(result["contrasts"], {"treatment": 1.0, "equal": 0.0})
        self.assertFalse(result["replicate_pairing_assumed"])

    def test_zero_intensity_is_preserved_but_not_logged(self):
        result = log2_contrasts({"x": 0, "y": 3}, groups={"ctrl": ["x"], "ko": ["y"]}, control="ctrl")
        self.assertIsNone(result["contrasts"]["ko"])
        self.assertEqual(result["input_values"]["x"], 0)
        self.assertEqual(result["groups"]["ctrl"]["nonpositive_samples"], ["x"])

    def test_missing_replicate_does_not_become_a_one_replicate_estimate(self):
        result = log2_contrasts({"a": 1, "b": None, "c": 2}, groups={"ctrl": ["a", "b"], "ko": ["c"]}, control="ctrl")
        self.assertIsNone(result["contrasts"]["ko"])

    def test_undeclared_or_overlapping_samples_fail(self):
        with self.assertRaises(ValueError):
            log2_contrasts({"a": 1}, groups={"ctrl": ["a"], "ko": ["a"]}, control="ctrl")
        with self.assertRaises(ValueError):
            log2_contrasts({"a": "2", "b": 1}, groups={"ctrl": ["a"], "ko": ["b"]}, control="ctrl")
        with self.assertRaises(ValueError):
            log2_contrasts({"a": 1}, groups={"ctrl": None, "ko": ["a"]}, control="ctrl")

    def test_duplicate_conflicts_are_not_averaged_or_treated_as_biology(self):
        rows = [{"record_id": "one", "site_id": "p:S1", "contrasts": {"c": 0}},
                {"record_id": "two", "site_id": "p:S1", "contrasts": {"c": 1}},
                {"record_id": "three", "site_id": "p:S2", "contrasts": {"c": 0}}]
        result = collapse_site_contrasts(rows, conditions=["c"])
        self.assertIsNone(result["site_values"]["c"]["p:S1"])
        self.assertEqual(result["site_values"]["c"]["p:S2"], 0)
        self.assertIn("aggregation_unresolved", result["aggregation"][0]["conditions"]["c"]["status"])

    def test_protein_sensitivity_has_no_unadjusted_fallback(self):
        result = adjust_for_host_protein({"c": {"p:S1": 1, "q:T2": 2}},
            site_hosts={"p:S1": "p", "q:T2": "q"}, protein_values={"c": {"p": .5}})
        self.assertEqual(result["site_values"]["c"]["p:S1"], .5)
        self.assertIsNone(result["site_values"]["c"]["q:T2"])
        self.assertFalse(result["unadjusted_fallback_used"])
        blank = adjust_for_host_protein({"c": {"unknown:S1": 1}},
            site_hosts={"unknown:S1": ""}, protein_values={"c": {"": .5}})
        self.assertIsNone(blank["site_values"]["c"]["unknown:S1"])
        self.assertEqual(blank["adjustment"][0]["unavailable_reason"], "unique_host_unavailable")

    def test_published_uncentered_zscore_and_sample_sd(self):
        # Sample SD of [1,2,3] is1. Signature sum3 /sqrt2, not centeredKSEA.
        result = infer_scores({"c": {"s1": 1, "s2": 2, "s3": 3}}, {"k": ["s1", "s2"]}, min_sites=2)
        self.assertAlmostEqual(result["scores"]["c"]["k"], 3 / math.sqrt(2))
        self.assertEqual(result["backgrounds"]["c"]["sample_sd"], 1)

    def test_minimum_counts_distinct_finite_sites(self):
        result = infer_scores({"c": {"a": -1, "b": 1, "missing": None}},
            {"eligible": ["a", "b", "a"], "small": ["a", "missing"]}, min_sites=2)
        self.assertEqual(result["scores"]["c"]["eligible"], 0)
        self.assertIsNone(result["scores"]["c"]["small"])
        self.assertEqual(result["eligibility"]["c"]["eligible"]["measured_distinct_sites"], 2)

    def test_constant_background_and_nonfinite_are_not_scores(self):
        result = infer_scores({"c": {"a": 1, "b": 1}}, {"k": ["a", "b"]}, min_sites=2)
        self.assertIsNone(result["scores"]["c"]["k"])
        with self.assertRaises(ValueError):
            infer_scores({"c": {"a": float("nan")}}, {"k": ["a"]}, min_sites=1)

    def test_average_tie_rank_missing_denominator_and_single_cell_design(self):
        result = score_recovery({"single": {"A": -2, "B": -2, "C": None}},
            [{"condition": "single", "target": "A", "sign": -1},
             {"condition": "single", "target": "C", "sign": -1}], candidate_ids=["A", "B", "C"])
        self.assertEqual([row["rank"] for row in result["cases"]], [1.5, 3])
        self.assertEqual(result["target_score_coverage"], .5)
        self.assertFalse(result["biological_negatives_assumed"])

    def test_arbitrary_three_condition_design_and_no_duplicate_expectations(self):
        result = score_recovery({name: {"A": -1} for name in ["x", "y", "z"]},
            [{"condition": name, "target": "A", "sign": -1, "cell": name} for name in ["x", "y", "z"]], candidate_ids=["A"])
        self.assertEqual(len(result["cases"]), 3)
        with self.assertRaises(ValueError):
            score_recovery({}, [{"condition": "x", "target": "A", "sign": -1}] * 2, candidate_ids=["A"])

    def test_partial_catalogue_and_outside_predictions_cannot_gain_rank(self):
        with self.assertRaises(ValueError):
            score_recovery({}, [], candidate_ids=["A"], profile_kind="partial_signature_diagnostic")
        with self.assertRaises(ValueError):
            score_recovery({"x": {"B": -1}}, [], candidate_ids=["A"])

    def test_single_scored_candidate_rank_is_explicitly_non_discriminating(self):
        result = score_recovery({"c": {"A": 2, "B": None, "C": None}},
            [{"condition": "c", "target": "A", "sign": -1}], candidate_ids=["A", "B", "C"])
        row = result["cases"][0]
        self.assertEqual(row["rank"], 1)
        self.assertFalse(row["direction_agreement"])
        self.assertEqual(row["finite_candidate_count"], 1)
        self.assertEqual(row["rank_competition"], "single_finite_candidate")
        self.assertFalse(row["more_than_five_finite_candidates"])


if __name__ == "__main__":
    unittest.main()
