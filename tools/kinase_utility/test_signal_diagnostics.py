from copy import deepcopy
import unittest

from signal_diagnostics import describe_signal_background


class SignalDiagnosticsTests(unittest.TestCase):
    def test_uniform_sign_is_visible_without_claiming_its_cause_or_changing_values(self):
        sites, scores = {"contrast": {"a": 1, "b": 2, "missing": None}}, {"contrast": {"x": .5, "y": 1}}
        original = deepcopy((sites, scores))
        result = describe_signal_background(sites, scores)
        self.assertTrue(result["conditions"]["contrast"]["source_scores"]["all_finite_values_positive"])
        self.assertFalse(result["technical_or_biological_cause_established"])
        self.assertFalse(result["normalization_recommended_automatically"])
        self.assertEqual((sites, scores), original)

    def test_mixed_sign_zero_and_empty_panels_remain_distinct(self):
        result = describe_signal_background({"one": {"a": -1, "b": 0, "c": 2}, "empty": {"a": None}},
                                            {"one": {"x": -2, "y": 1}, "empty": {"x": None}})
        self.assertEqual(result["conditions"]["one"]["site_background"]["zero"], 1)
        self.assertFalse(result["conditions"]["one"]["source_scores"]["all_finite_values_negative"])
        self.assertIsNone(result["conditions"]["empty"]["site_background"]["mean"])

    def test_condition_mismatch_and_unresolved_nonfinite_values_fail(self):
        with self.assertRaises(ValueError):
            describe_signal_background({"a": {"s": 1}}, {"b": {"k": 1}})
        with self.assertRaises(ValueError):
            describe_signal_background({"a": {"s": float("inf")}}, {"a": {"k": 1}})


if __name__ == "__main__":
    unittest.main()
