"""Design-based controls, including exhaustive finite-population enumeration."""
from copy import deepcopy
from itertools import combinations, product
import unittest

from tools.sampled_audit.audit_statistics import _mean_and_variance, summarize


def fixture():
    strata = {"large": {"population_size": 100, "sample_size": 2},
              "small": {"population_size": 10, "sample_size": 2}}
    sample = [{"case_id": f"c{i}", "assertion_id": f"a{i}", "stratum": name}
              for i, name in enumerate(("large", "large", "small", "small"))]
    review = [{"case_id": row["case_id"], "source_relative_support": status,
               "primary_evidence_support": "unresolved", "independent_scientific_correctness": "unreviewed"}
              for row, status in zip(sample, ("supported", "supported", "contradicted", "unresolved"))]
    return strata, sample, review


class StratifiedAuditStatisticsTests(unittest.TestCase):
    def test_unequal_allocation_uses_population_weights_and_keeps_unknown(self):
        report = summarize(*fixture())
        axis = report["axes"]["source_relative_support"]
        self.assertAlmostEqual(axis["statuses"]["supported"]["weighted_fraction"], 100 / 110)
        self.assertAlmostEqual(axis["statuses"]["contradicted"]["weighted_fraction"], 5 / 110)
        self.assertAlmostEqual(axis["statuses"]["unresolved"]["weighted_fraction"], 5 / 110)
        self.assertAlmostEqual(axis["weighted_sample_completion_range"]["upper"], 105 / 110)
        self.assertEqual(axis["sample_counts"], {"supported": 2, "contradicted": 1, "unresolved": 1})
        self.assertFalse(report["scientific_accuracy_measured"])
        self.assertIsNone(report["independent_scientific_correctness"]["accuracy_estimate"])

    def test_exhaustive_stratified_draws_recover_mean_and_variance(self):
        # Enumerate every possible draw from two finite populations. This
        # independently checks both unequal weighting and the FPC formula.
        populations = {"a": (0, 0, 1, 1), "b": (0, 1, 1)}
        strata = {name: {"population_size": len(values), "sample_size": 2}
                  for name, values in populations.items()}
        estimates, estimated_variances = [], []
        for draw_a, draw_b in product(combinations(range(4), 2), combinations(range(3), 2)):
            values = {"a": [populations["a"][i] for i in draw_a],
                      "b": [populations["b"][i] for i in draw_b]}
            result = _mean_and_variance(strata, values)
            estimates.append(result["weighted_fraction"])
            estimated_variances.append(result["estimated_design_variance"])
        true_mean = sum(sum(v) for v in populations.values()) / 7
        self.assertAlmostEqual(sum(estimates) / len(estimates), true_mean)
        exact_design_variance = sum((x - true_mean)**2 for x in estimates) / len(estimates)
        self.assertAlmostEqual(sum(estimated_variances) / len(estimated_variances), exact_design_variance)
        self.assertGreater(exact_design_variance, 0)

    def test_paired_removal_preserves_original_denominator_and_labels(self):
        strata, sample, review = fixture()
        before = deepcopy((strata, sample, review))
        report = summarize(strata, sample, review, retained_assertion_ids={"a1", "a3", "other_original_assertion"})
        paired = report["axes"]["source_relative_support"]["paired_intervention"]
        self.assertEqual(paired["sample_counts_removed"], {"supported": 1, "contradicted": 1, "unresolved": 0})
        self.assertAlmostEqual(paired["population_weighted_removed_status_fractions"]["supported"]["weighted_fraction"], 50 / 110)
        self.assertAlmostEqual(paired["population_weighted_removed_status_fractions"]["contradicted"]["weighted_fraction"], 5 / 110)
        self.assertAlmostEqual(paired["population_weighted_retained_fraction"]["weighted_fraction"], 0.5)
        self.assertFalse(paired["biological_error_removal_or_valid_claim_loss_established"])
        self.assertEqual((strata, sample, review), before)

    def test_census_uncertainty_is_zero_but_non_census_singleton_unavailable(self):
        census = _mean_and_variance({"x": {"population_size": 1, "sample_size": 1}}, {"x": [1]})
        self.assertEqual(census["estimated_design_standard_error"], 0)
        self.assertFalse(census["zero_estimated_variance_is_not_certainty"])
        singleton = _mean_and_variance({"x": {"population_size": 10, "sample_size": 1}}, {"x": [1]})
        self.assertIsNone(singleton["estimated_design_standard_error"])
        self.assertEqual(singleton["variance_unavailable_non_census_singleton_strata"], ["x"])

    def test_all_supported_sample_does_not_produce_certain_accuracy_or_CI(self):
        strata, sample, review = fixture()
        for row in review:
            row["source_relative_support"] = "supported"
        report = summarize(strata, sample, review)
        result = report["axes"]["source_relative_support"]["statuses"]["supported"]
        self.assertEqual(result["estimated_design_standard_error"], 0)
        self.assertTrue(result["zero_estimated_variance_is_not_certainty"])
        self.assertIsNone(result["confidence_interval"])
        self.assertIsNone(report["axes"]["source_relative_support"]["independent_biological_accuracy"])

    def test_all_unknown_is_retained_as_full_mass_without_accuracy(self):
        strata, sample, review = fixture()
        for row in review:
            row["source_relative_support"] = "unresolved"
        result = summarize(strata, sample, review)["axes"]["source_relative_support"]
        self.assertEqual(result["weighted_unresolved_fraction"], 1)
        self.assertEqual(result["weighted_sample_completion_range"]["lower"], 0)
        self.assertEqual(result["weighted_sample_completion_range"]["upper"], 1)

    def test_missing_duplicate_or_foreign_reviews_cannot_change_denominator(self):
        strata, sample, review = fixture()
        for rows in (review[:-1], review + [review[0]], [*review[:-1], {**review[-1], "case_id": "other"}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                summarize(strata, sample, rows)

    def test_coherent_duplicate_assertions_or_wrong_strata_allocation_are_rejected(self):
        strata, sample, review = fixture()
        sample[1]["assertion_id"] = sample[0]["assertion_id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            summarize(strata, sample, review)
        strata, sample, review = fixture()
        sample[1]["stratum"] = "small"
        with self.assertRaisesRegex(ValueError, "allocation"):
            summarize(strata, sample, review)

    def test_invalid_labels_and_independent_truth_injection_fail_closed(self):
        for axis, value in (("source_relative_support", "not_found"),
                            ("primary_evidence_support", None),
                            ("independent_scientific_correctness", "supported")):
            strata, sample, review = fixture()
            review[0][axis] = value
            with self.subTest(axis=axis), self.assertRaises(ValueError):
                summarize(strata, sample, review)
        strata, sample, review = fixture()
        review[0]["assertion_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "identity"):
            summarize(strata, sample, review)

    def test_noninteger_zero_negative_or_impossible_design_is_rejected(self):
        for population, sampled in ((True, 1), (5, False), (0, 0), (5, 0), (-2, 1), (1, 2), (2.5, 1)):
            strata, sample, review = fixture()
            strata["large"] = {"population_size": population, "sample_size": sampled}
            with self.subTest(population=population, sampled=sampled), self.assertRaises(ValueError):
                summarize(strata, sample, review)


if __name__ == "__main__":
    unittest.main()
