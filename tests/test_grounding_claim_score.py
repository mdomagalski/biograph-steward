"""Invented logic fixtures, not biological gold or an evaluation result."""

from copy import deepcopy
import unittest

from tools.grounding_claims.score import (
    OUTSIDE_ENDPOINT, compare_methods, label_pairs, metrics,
)


class TagGuard(dict):
    """A reserved row raises if any caller attempts to inspect its tag."""

    def get(self, key, default=None):
        if key == "tag":
            raise AssertionError("Reserved tag was inspected")
        return super().get(key, default)

    def __getitem__(self, key):
        if key == "tag":
            raise AssertionError("Reserved tag was inspected")
        return super().__getitem__(key)


def case(case_id, pa_hash, source_hash):
    return {"case_id": case_id, "pa_hash": pa_hash, "source_hash": source_hash}


class NativeLabelTests(unittest.TestCase):
    def test_only_unanimous_native_endpoint_tags_are_admitted(self):
        rows = [
            {"pa_hash": -1, "source_hash": 10, "tag": "correct"},
            {"pa_hash": "-1", "source_hash": "10", "tag": "correct"},
            {"pa_hash": 2, "source_hash": -20, "tag": "grounding"},
            {"pa_hash": 3, "source_hash": 30, "tag": "hypothesis"},
            {"pa_hash": 4, "source_hash": 40, "tag": "act_vs_amt"},
        ]
        before = deepcopy(rows)
        result = label_pairs(rows, [(str(i), str(j)) for i, j in [(-1, 10), (2, -20), (3, 30), (4, 40)]])
        self.assertEqual(result[("-1", "10")]["label"], "correctly_grounded")
        self.assertEqual(result[("2", "-20")]["label"], "grounding_error")
        self.assertEqual(result[("-1", "10")]["curation_row_count"], 2)
        self.assertEqual(result[("-1", "10")]["native_tag_counts"], [{"tag": "correct", "count": 2}])
        self.assertEqual(result[("3", "30")]["label"], OUTSIDE_ENDPOINT)
        self.assertEqual(result[("4", "40")]["label"], OUTSIDE_ENDPOINT)
        self.assertEqual(rows, before)

    def test_duplicates_do_not_outvote_a_conflict(self):
        rows = [{"pa_hash": 1, "source_hash": 2, "tag": tag}
                for tag in ["correct", "correct", "grounding"]]
        result = label_pairs(rows, [("1", "2")])[("1", "2")]
        self.assertEqual(result["label"], OUTSIDE_ENDPOINT)
        self.assertEqual(result["curation_row_count"], 3)
        self.assertEqual(result["native_tag_counts"], [
            {"tag": "correct", "count": 2}, {"tag": "grounding", "count": 1},
        ])

    def test_missing_null_and_absent_pairs_remain_outside(self):
        rows = [
            {"pa_hash": 1, "source_hash": 2, "tag": "correct"},
            {"pa_hash": 1, "source_hash": 2},
            {"pa_hash": 3, "source_hash": 4, "tag": None},
        ]
        result = label_pairs(rows, [("1", "2"), ("3", "4"), ("5", "6")])
        self.assertTrue(all(row["label"] == OUTSIDE_ENDPOINT for row in result.values()))
        self.assertEqual(result[("1", "2")]["missing_tag_row_count"], 1)
        self.assertEqual(result[("3", "4")]["native_tag_counts"], [{"tag": None, "count": 1}])
        self.assertEqual(result[("5", "6")]["curation_row_count"], 0)

    def test_filter_precedes_reserved_tag_access_or_type_validation(self):
        reserved = TagGuard(pa_hash="9", source_hash="8", tag=object())
        result = label_pairs([reserved, {"pa_hash": 1, "source_hash": 2, "tag": "grounding"}], [("1", "2")])
        self.assertEqual(result[("1", "2")]["label"], "grounding_error")
        self.assertEqual(label_pairs([reserved], []), {})

    def test_noncanonical_ids_are_not_coerced(self):
        for bad in [True, False, 1.0, None, "1.0", "1e3", " 1", "1 ", "+1", "01", "-0", "١"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                label_pairs([], [(bad, "2")])
        with self.assertRaises(ValueError):
            label_pairs([{"pa_hash": True, "source_hash": 2, "tag": "correct"}], [("1", "2")])

    def test_selected_pair_alias_duplicates_and_bad_tag_type_fail(self):
        with self.assertRaises(ValueError):
            label_pairs([], [(1, -2), ("1", "-2")])
        with self.assertRaises(ValueError):
            label_pairs([{"pa_hash": 1, "source_hash": 2, "tag": ["correct"]}], [("1", "2")])
        self.assertEqual(label_pairs([{"pa_hash": 1, "source_hash": 2, "tag": "Correct"}], [("1", "2")])[("1", "2")]["label"], OUTSIDE_ENDPOINT)

    def test_toy_row_and_pair_totals_are_preserved(self):
        # These artificial sizes exercise row accounting; no real tags are read.
        pairs = [(str(i), str(-i)) for i in range(1, 5710)]
        rows = [{"pa_hash": p, "source_hash": s, "tag": "correct"} for p, s in pairs]
        rows += [dict(row) for row in rows[:313]]
        result = label_pairs(rows, pairs)
        self.assertEqual(len(result), 5709)
        self.assertEqual(sum(row["curation_row_count"] for row in result.values()), 6022)


class MetricTests(unittest.TestCase):
    def test_abstentions_stay_in_gold_denominators_not_confusion(self):
        rows = [
            {"gold": "grounding_error", "status": "candidate_conflict"},
            {"gold": "grounding_error", "status": "no_conflict"},
            {"gold": "grounding_error", "status": "unresolved"},
            {"gold": "grounding_error", "status": "model_error"},
            {"gold": "correctly_grounded", "status": "candidate_conflict"},
            {"gold": "correctly_grounded", "status": "no_conflict"},
            {"gold": "correctly_grounded", "status": "unresolved"},
            {"gold": "correctly_grounded", "status": "model_error"},
        ]
        result = metrics(rows)
        self.assertEqual(result["confusion_resolved"], {"TP": 1, "FP": 1, "FN": 1, "TN": 1})
        self.assertEqual(result["precision"], .5)
        self.assertEqual(result["error_recall"], .25)
        self.assertEqual(result["false_conflict_rate"], .25)
        self.assertEqual(result["coverage"], .5)
        self.assertEqual(result["resolved_accuracy"], .5)
        self.assertEqual(result["metric_denominators"]["resolved_accuracy"], 4)
        self.assertEqual(result["abstentions_by_gold"]["grounding_error"], {"unresolved": 1, "model_error": 1})

    def test_undefined_ratios_remain_none(self):
        empty = metrics([])
        for key in ["precision", "error_recall", "false_conflict_rate", "coverage", "resolved_accuracy"]:
            self.assertIsNone(empty[key])
        abstained = metrics([{"gold": "grounding_error", "status": "unresolved"}])
        self.assertIsNone(abstained["precision"])
        self.assertIsNone(abstained["false_conflict_rate"])
        self.assertIsNone(abstained["resolved_accuracy"])
        self.assertEqual(abstained["error_recall"], 0)
        self.assertEqual(abstained["coverage"], 0)

    def test_statuses_and_boolean_flags_are_strict(self):
        good = {"gold": "grounding_error", "status": "model_error", "resolved": False,
                "model_error": True, "candidate_conflict": None, "no_conflict": False,
                "input": {"resolved": "unknown", "score": .99}}
        self.assertEqual(metrics([good])["abstention_cases"], 1)
        for update in [{"status": True}, {"status": "correct"}, {"gold": "grounding"},
                       {"resolved": 0}, {"resolved": True}, {"model_error": False},
                       {"candidate_conflict": True}, {"candidate_conflict": False},
                       {"no_conflict": True}]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                metrics([{**good, **update}])

    def test_native_conflict_flag_is_ternary_without_integer_coercion(self):
        expected = {"candidate_conflict": True, "no_conflict": False,
                    "unresolved": None, "model_error": None}
        for status, flag in expected.items():
            valid = {"gold": "grounding_error", "status": status,
                     "candidate_conflict": flag}
            self.assertEqual(metrics([valid])["status_counts"][status], 1)
            for bad in [True, False, None, 0, 1, "true", "false", []]:
                if bad is flag:
                    continue
                with self.subTest(status=status, bad=bad), self.assertRaises(ValueError):
                    metrics([{**valid, "candidate_conflict": bad}])

    def test_optional_case_ids_cannot_duplicate_or_be_partly_missing(self):
        row = {"gold": "correctly_grounded", "status": "no_conflict", "case_id": "a"}
        with self.assertRaises(ValueError):
            metrics([row, dict(row)])
        with self.assertRaises(ValueError):
            metrics([row, {"gold": "grounding_error", "status": "model_error"}])


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.cases = [case("a", "-1", "10"), case("b", "2", "-20"),
                      case("c", "3", "30"), case("d", "4", "40")]
        self.labels = {("-1", "10"): "grounding_error", ("2", "-20"): "correctly_grounded",
                       ("3", "30"): "grounding_error", ("4", "40"): "correctly_grounded"}
        self.predictions = {
            "baseline": {"a": "no_conflict", "b": "candidate_conflict", "c": "unresolved", "d": "no_conflict"},
            "context": {"a": "candidate_conflict", "b": "no_conflict", "c": "model_error", "d": "unresolved"},
        }

    def test_full_population_and_explicit_common_secondary_are_separate(self):
        result = compare_methods(self.cases, self.predictions, self.labels)
        self.assertEqual(result["all_selected_case_count"], 4)
        self.assertTrue(all(m["n_cases"] == 4 for m in result["metrics_by_arm"].values()))
        common = result["common_resolved_secondary"]
        self.assertFalse(common["primary"])
        self.assertEqual(common["case_ids"], ["a", "b"])
        self.assertTrue(all(m["n_cases"] == 2 for m in common["metrics_by_arm"].values()))
        self.assertEqual(result["metrics_by_arm"]["context"]["coverage"], .5)
        self.assertEqual(result["metrics_by_arm"]["context"]["error_recall"], .5)
        pair = result["paired_comparisons"][0]
        self.assertEqual(sum(sum(row.values()) for row in pair["status_transitions"].values()), 4)
        self.assertEqual(pair["correctness_transitions"]["error"]["correct"], 2)
        self.assertEqual(pair["correctness_transitions"]["correct"]["abstention"], 1)
        self.assertEqual(pair["correctness_transitions"]["abstention"]["abstention"], 1)
        self.assertEqual(pair["resolved_case_change"], -1)
        self.assertEqual(pair["confusion_count_changes"], {"TP": 1, "FP": -1, "FN": -1, "TN": 0})

    def test_unanimous_label_records_flow_through_without_mutation(self):
        raw = [{"pa_hash": -1, "source_hash": 10, "tag": "grounding"},
               {"pa_hash": 2, "source_hash": -20, "tag": "correct"}]
        labels = label_pairs(raw, [("-1", "10"), ("2", "-20")])
        cases = self.cases[:2]
        predictions = {"one": {"a": {"case_id": "a", "status": "candidate_conflict",
                                      "resolved": True, "candidate_conflict": True,
                                      "input": {"score": .01, "gold": "not used"}},
                               "b": "no_conflict"}}
        before = deepcopy((cases, predictions, labels))
        result = compare_methods(cases, predictions, labels)
        self.assertEqual(result["metrics_by_arm"]["one"]["resolved_accuracy"], 1)
        self.assertEqual((cases, predictions, labels), before)
        self.assertEqual(result["paired_comparisons"], [])

    def test_native_prediction_shape_preserves_abstentions_in_comparison(self):
        native = {
            "a": {"format": "native-fixture", "status": "candidate_conflict",
                  "candidate_conflict": True, "agents": [], "use_context": True},
            "b": {"format": "native-fixture", "status": "no_conflict",
                  "candidate_conflict": False, "agents": [], "use_context": True},
            "c": {"format": "native-fixture", "status": "unresolved",
                  "candidate_conflict": None, "agents": [], "use_context": True},
            "d": {"format": "native-fixture", "status": "model_error",
                  "candidate_conflict": None, "agents": [], "use_context": True},
        }
        plain = {case_id: row["status"] for case_id, row in native.items()}
        result = compare_methods(self.cases, {"native": native, "plain": plain}, self.labels)
        outcome = result["metrics_by_arm"]["native"]
        self.assertEqual(outcome["confusion_resolved"], {"TP": 1, "FP": 0, "FN": 0, "TN": 1})
        self.assertEqual(outcome["coverage"], .5)
        self.assertEqual(outcome["error_recall"], .5)
        self.assertEqual(outcome["abstentions_by_gold"], {
            "grounding_error": {"unresolved": 1, "model_error": 0},
            "correctly_grounded": {"unresolved": 0, "model_error": 1},
        })
        self.assertEqual(outcome, result["metrics_by_arm"]["plain"])
        self.assertEqual(result["common_resolved_secondary"]["case_ids"], ["a", "b"])
        transitions = result["paired_comparisons"][0]["status_transitions"]
        for status in ["candidate_conflict", "no_conflict", "unresolved", "model_error"]:
            self.assertEqual(transitions[status][status], 1)

    def test_missing_extra_or_unknown_predictions_fail_not_become_negatives(self):
        variants = [
            {"a": "no_conflict", "b": "no_conflict", "c": "unresolved"},
            {**self.predictions["baseline"], "extra": "no_conflict"},
            {**self.predictions["baseline"], "a": "unknown"},
            {**self.predictions["baseline"], "a": {"status": "no_conflict", "case_id": "wrong"}},
            {**self.predictions["baseline"], "a": {"status": "no_conflict", "pa_hash": "9", "source_hash": "10"}},
        ]
        for predictions in variants:
            with self.subTest(predictions=predictions), self.assertRaises(ValueError):
                compare_methods(self.cases, {"bad": predictions}, self.labels)

    def test_duplicate_cases_and_invalid_ids_fail(self):
        for cases in [self.cases + [dict(self.cases[0])],
                      self.cases + [case("different", -1, 10)],
                      [{**self.cases[0], "case_id": True}],
                      [{**self.cases[0], "pa_hash": -1.0}]]:
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                compare_methods(cases, self.predictions, self.labels)

    def test_missing_outside_or_disagreeing_gold_fails(self):
        for labels in [{k: v for k, v in self.labels.items() if k != ("-1", "10")},
                       {**self.labels, ("-1", "10"): OUTSIDE_ENDPOINT},
                       {**self.labels, ("-1", "10"): {"label": OUTSIDE_ENDPOINT}}]:
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                compare_methods(self.cases, self.predictions, labels)
        with self.assertRaises(ValueError):
            compare_methods([{**self.cases[0], "gold": "correctly_grounded"}],
                            {"one": {"a": "candidate_conflict"}}, self.labels)

    def test_nonselected_label_values_are_not_accessed(self):
        reserved = ("99", "100")

        class LabelGuard(dict):
            def __getitem__(self, key):
                if key == reserved:
                    raise AssertionError("Unselected label value was inspected")
                return super().__getitem__(key)

        labels = LabelGuard(self.labels)
        labels[reserved] = object()
        result = compare_methods(self.cases, self.predictions, labels)
        self.assertEqual(result["all_selected_case_count"], 4)

    def test_canonical_label_alias_collision_fails(self):
        labels = {**self.labels, (-1, 10): "correctly_grounded"}
        with self.assertRaises(ValueError):
            compare_methods(self.cases, self.predictions, labels)

    def test_common_resolved_is_intersection_of_every_arm(self):
        predictions = {**self.predictions, "third": {"a": "unresolved", "b": "no_conflict",
                                                     "c": "unresolved", "d": "no_conflict"}}
        result = compare_methods(self.cases, predictions, self.labels)
        self.assertEqual(result["common_resolved_secondary"]["case_ids"], ["b"])
        self.assertEqual(len(result["paired_comparisons"]), 3)

    def test_no_common_resolution_and_empty_cases_do_not_report_accuracy(self):
        result = compare_methods([self.cases[0]],
                                 {"left": {"a": "unresolved"}, "right": {"a": "model_error"}},
                                 self.labels)
        self.assertEqual(result["common_resolved_secondary"]["n_cases"], 0)
        self.assertTrue(all(m["resolved_accuracy"] is None
                            for m in result["common_resolved_secondary"]["metrics_by_arm"].values()))
        self.assertIsNone(result["paired_comparisons"][0]["metric_changes"]["precision"])
        empty = compare_methods([], {"empty": {}}, {})
        self.assertIsNone(empty["metrics_by_arm"]["empty"]["coverage"])


if __name__ == "__main__":
    unittest.main()
