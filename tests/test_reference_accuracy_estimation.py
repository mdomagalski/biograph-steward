"""Exhaustive finite-population controls; invented outcomes are not biomedical gold."""
from copy import deepcopy
from fractions import Fraction
import itertools
import math
import unittest

from tools.reference_accuracy.estimation import estimate


def rows(strata, outcomes):
    sample, labels = [], []
    for name, selected in outcomes.items():
        family, disposition = name.split("::")
        for uid, verdict in selected:
            row = {"case_id": uid, "assertion_id": "assertion:" + uid, "stratum": name,
                   "family": family, "disposition": disposition}
            sample.append(row); labels.append({**row, "verdict": verdict})
    return sample, labels


class ReferenceEstimationTests(unittest.TestCase):
    def test_exact_census_unknown_bounds_and_conditional_ratio_keep_full_denominator(self):
        strata = {"go_annotation::retained": {"population_size": 4, "sample_size": 4}}
        sample, labels = rows(strata, {next(iter(strata)): list(zip("abcd", ["agree", "disagree", "unknown", "unknown"]))})
        result = estimate(strata, sample, labels)
        overall = result["overall"]
        self.assertEqual(overall["identification"]["lower"], 0.25)
        self.assertEqual(overall["identification"]["upper"], 0.75)
        self.assertEqual(overall["identification"]["endpoint_status"], "exact_census_reference_identification_bounds")
        self.assertEqual(overall["resolved_only_agreement_ratio"]["value"], 0.5)
        self.assertEqual(overall["unknown_reference_mass"], 0.5)
        self.assertIsNone(result["independent_biological_accuracy_estimate"])
        self.assertFalse(result["unknown_dropped_from_full_frame_denominator"])

    def test_exhaustive_stratified_draws_recover_mean_and_design_variance(self):
        populations = {"go_annotation::retained": list(zip("abc", ["agree", "unknown", "disagree"])),
                       "pathway_membership::pruned": list(zip("defg", ["agree", "agree", "unknown", "disagree"]))}
        strata = {name: {"population_size": len(pop), "sample_size": 2} for name, pop in populations.items()}
        predictions, variances = [], []
        for left, right in itertools.product(*(list(itertools.combinations(pop, 2)) for pop in populations.values())):
            sample, labels = rows(strata, dict(zip(populations, (left, right))))
            result = estimate(strata, sample, labels)["overall"]
            value = result["rates"]["agree"]
            predictions.append(Fraction(str(value["weighted_fraction"])))
            variances.append(value["estimated_design_variance"])
            self.assertEqual(result["population_units"], 7)
            self.assertEqual(result["sampled_units"], 4)
            self.assertEqual(result["identification"]["endpoint_status"], "estimated_reference_identification_bound_endpoints")
        exact_mean = Fraction(3, 7)
        mean = sum(predictions) / len(predictions)
        true_variance = sum((float(x) - float(exact_mean))**2 for x in predictions) / len(predictions)
        self.assertAlmostEqual(float(mean), float(exact_mean), places=14)
        self.assertAlmostEqual(sum(variances) / len(variances), true_variance, places=14)

    def test_family_and_disposition_domains_preserve_their_own_population_weights(self):
        strata = {"go_annotation::retained": {"population_size": 6, "sample_size": 2},
                  "go_annotation::pruned": {"population_size": 2, "sample_size": 2},
                  "pathway_membership::retained": {"population_size": 10, "sample_size": 2}}
        sample, labels = rows(strata, {name: [(name+str(i), verdict) for i, verdict in enumerate(values)] for name, values in {
            "go_annotation::retained": ["agree", "unknown"], "go_annotation::pruned": ["disagree", "unknown"],
            "pathway_membership::retained": ["unknown", "unknown"]}.items()})
        result = estimate(strata, sample, labels)
        self.assertAlmostEqual(result["overall"]["rates"]["agree"]["weighted_fraction"], 3/18)
        self.assertAlmostEqual(result["by_family"]["go_annotation"]["rates"]["agree"]["weighted_fraction"], 3/8)
        self.assertEqual(result["by_disposition"]["pruned"]["population_units"], 2)
        self.assertEqual(result["by_disposition"]["pruned"]["sample_counts"]["disagree"], 1)

    def test_non_census_singleton_does_not_fabricate_standard_error(self):
        strata = {"go_annotation::retained": {"population_size": 9, "sample_size": 1}}
        sample, labels = rows(strata, {next(iter(strata)): [("a", "agree")]})
        value = estimate(strata, sample, labels)["overall"]["rates"]["agree"]
        self.assertIsNone(value["estimated_design_standard_error"])
        self.assertEqual(value["variance_unavailable_non_census_singleton_strata"], list(strata))

    def test_homogeneous_small_sample_zero_variance_is_not_certainty(self):
        strata = {"go_annotation::retained": {"population_size": 100, "sample_size": 2}}
        sample, labels = rows(strata, {next(iter(strata)): [("a", "unknown"), ("b", "unknown")]})
        result = estimate(strata, sample, labels)["overall"]
        self.assertTrue(result["rates"]["unknown"]["zero_estimated_variance_is_not_certainty"])
        self.assertEqual(result["identification"]["lower"], 0)
        self.assertEqual(result["identification"]["upper"], 1)
        self.assertIsNone(result["resolved_only_agreement_ratio"]["value"])

    def test_missing_duplicate_wrong_case_and_uninterpreted_labels_fail_closed(self):
        strata = {"go_annotation::retained": {"population_size": 2, "sample_size": 2}}
        sample, labels = rows(strata, {next(iter(strata)): [("a", "agree"), ("b", "unknown")]})
        variants = [labels[:-1], labels + [labels[0]]]
        wrong = deepcopy(labels); wrong[0]["assertion_id"] = "assertion:other"; variants.append(wrong)
        opaque = deepcopy(labels); opaque[0]["verdict"] = "AI_is_sure"; variants.append(opaque)
        for value in variants:
            with self.subTest(labels=value), self.assertRaises(ValueError):
                estimate(strata, sample, value)


if __name__ == "__main__":
    unittest.main()
