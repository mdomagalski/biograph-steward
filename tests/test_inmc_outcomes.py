"""Synthetic eligibility, reconciliation and native metric tests; no real inputs."""
from copy import deepcopy
import importlib.util
from itertools import product
import unittest

from biograph_steward.inmc_outcomes import HEADER, materialize, score_comparison


def gene(number):
    return f"ENSG{number:011d}"


def panel(records):
    return HEADER + b"\n" + b"\n".join(
        "\t".join((gene(a), gene(b), freq, *codes)).encode() for a, b, freq, codes in records) + b"\n"


def candidates(records):
    pairs = sorted({tuple(sorted((gene(a), gene(b)))) for a, b, _, _ in records})
    return [{"id": f"candidate:{i:05d}", "original_genes": list(pair), "self_pair": pair[0] == pair[1]}
            for i, pair in enumerate(pairs)]


def materialized():
    records = [(1, 2, "opaque", ("Positive", "Negative", "Negative")),
               (1, 3, "1000000", ("Negative", "Negative", "Negative")),
               (4, 5, "0", ("Positive", "Positive", "Negative")),
               (6, 7, "not-a-number", ("Negative", "Negative", "Negative")),
               (8, 9, "freq", ("Positive", "Not tested", "Negative")),
               (10, 10, "freq", ("Positive", "Negative", "Negative"))]
    return materialize(panel(records), candidates(records),
                       [(gene(a), gene(b)) for a, b in ((1, 2), (4, 5), (8, 9), (10, 10))])


def scores(rows):
    return {arm: {17: {row["id"]: 0.5 if arm == "rgcn_baseline" else
                       0.9 if row["label"] == 1 else 0.1 for row in rows},
                  43: {row["id"]: 0.5 if arm == "rgcn_baseline" else
                       0.9 if row["label"] == 1 else 0.1 for row in rows}}
            for arm in ("rgcn_baseline", "rgcn_enriched")}


class OutcomeMaterializationTests(unittest.TestCase):
    def test_all_known_code_combinations_follow_complete_scored_rule(self):
        patterns = list(product(("Positive", "Negative", "Auto-activator", "Not tested", "Not scored"), repeat=3))
        records = [(2 * i + 1, 2 * i + 2, str(i), pattern) for i, pattern in enumerate(patterns)]
        author = [(gene(a), gene(b)) for a, b, _, codes in records if "Positive" in codes]
        result = materialize(panel(records), candidates(records), author)
        self.assertEqual(result["coverage"]["nominated_pairs"], 125)
        self.assertEqual(result["coverage"]["primary_eligible_pairs"], 8)
        self.assertEqual(result["reference_reconciliation"]["eligible_positive_pairs"], 7)
        self.assertEqual(result["reference_reconciliation"]["eligible_negative_pairs"], 1)
        for row in result["rows"]:
            expected = all(v in {"Positive", "Negative"} for v in row["assay_codes"])
            self.assertEqual(row["eligible_primary_off_diagonal"], expected)
            self.assertEqual(row["label"], int("Positive" in row["assay_codes"]) if expected else None)
        self.assertGreater(result["reference_reconciliation"]["author_positives_outside_eligible_subset"], 0)

    def test_identity_population_is_checked_before_outcome_decoding(self):
        records = [(1, 2, "", ("Negative", "Negative", "Negative"))]
        raw = panel(records).replace(b"Negative", b"\xff", 1)
        expected = candidates([(3, 4, "", ("Negative",) * 3)])
        with self.assertRaisesRegex(ValueError, "population mismatch"):
            materialize(raw, expected, [])
        with self.assertRaisesRegex(ValueError, "encoding"):
            materialize(raw, candidates(records), [])

    def test_unknown_and_empty_codes_stop_including_otherwise_positive_rows(self):
        for code in ("", "positive", " Positive", "Unknown", "NA"):
            records = [(1, 2, "opaque", ("Positive", code, "Negative"))]
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, "Unexpected or empty assay code"):
                materialize(panel(records), candidates(records), [(gene(1), gene(2))])

    def test_duplicates_preserve_orientation_and_opaque_freq_without_weighting(self):
        records = [(1, 2, "1000", ("Positive", "Negative", "Negative")),
                   (2, 1, "opaque changed freq", ("Positive", "Negative", "Negative"))]
        result = materialize(panel(records), candidates(records), [(gene(2), gene(1))])
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["coverage"]["duplicate_source_rows"], 1)
        source_rows = result["rows"][0]["source_rows"]
        self.assertEqual([r["source"] for r in source_rows], [gene(1), gene(2)])
        self.assertEqual([r["freq_raw"] for r in source_rows], ["1000", "opaque changed freq"])
        conflicting = [records[0], (2, 1, "1000", ("Negative", "Positive", "Negative"))]
        with self.assertRaisesRegex(ValueError, "contradictory assay codes"):
            materialize(panel(conflicting), candidates(conflicting), [(gene(1), gene(2))])

    def test_author_reference_required_and_checked_against_both_classes(self):
        for codes, author in [(("Positive", "Negative", "Negative"), []),
                              (("Negative",) * 3, [(gene(1), gene(2))])]:
            records = [(1, 2, "0", codes)]
            with self.subTest(codes=codes), self.assertRaisesRegex(ValueError, "disagrees"):
                materialize(panel(records), candidates(records), author)
        records = [(1, 2, "0", ("Positive", "Not tested", "Negative"))]
        with self.assertRaisesRegex(ValueError, "reference is required"):
            materialize(panel(records), candidates(records), None)
        result = materialize(panel(records), candidates(records), [])
        self.assertIsNone(result["rows"][0]["label"])
        self.assertFalse(result["reference_reconciliation"]["author_complement_used_for_negatives"])

    def test_self_pairs_separate_and_unmapped_identifiers_are_preserved(self):
        result = materialized()
        self.assertEqual(result["coverage"]["self_pairs"], 1)
        self.assertEqual(result["coverage"]["primary_eligible_pairs"], 4)
        self_row = next(r for r in result["rows"] if r["self_pair"])
        self.assertEqual(self_row["original_genes"], [gene(10), gene(10)])
        self.assertEqual(self_row["label"], 1)
        self.assertFalse(self_row["eligible_primary_off_diagonal"])

    def test_no_identifier_guessing_or_source_shape_repair(self):
        records = [(1, 2, "0", ("Negative",) * 3)]
        raw = panel(records)
        for altered in (raw.replace(gene(1).encode(), (gene(1) + ".1").encode()),
                        raw.replace(b"source\ttarget", b"target\tsource"),
                        raw + b"\n", raw.replace(b"\t0\t", b"\t0\textra\t")):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                materialize(altered, candidates(records), [])


class OutcomeScoringBoundaryTests(unittest.TestCase):
    def test_missing_nonfinite_unknown_or_different_score_populations_stop_before_metrics(self):
        rows = materialized()["rows"]
        first = rows[0]["id"]
        for value in (None, float("nan"), float("inf"), "0.1", True):
            data = scores(rows)
            if value is None:
                del data["rgcn_enriched"][17][first]
            else:
                data["rgcn_enriched"][17][first] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "score"):
                score_comparison(rows, data)
        data = scores(rows); data["rgcn_enriched"][17]["unknown"] = 0.2
        with self.assertRaisesRegex(ValueError, "score"):
            score_comparison(rows, data)
        data = scores(rows); del data["rgcn_enriched"][17][rows[-1]["id"]]
        with self.assertRaisesRegex(ValueError, "population differs"):
            score_comparison(rows, data)

    def test_seed_changes_and_tampered_eligibility_fail(self):
        rows = materialized()["rows"]
        data = scores(rows); del data["rgcn_enriched"][43]
        with self.assertRaisesRegex(ValueError, "seed sets differ"):
            score_comparison(rows, data)
        altered = deepcopy(rows); altered[-1]["eligible_primary_off_diagonal"] = True
        with self.assertRaisesRegex(ValueError, "violates eligibility"):
            score_comparison(altered, scores(rows))
        altered = deepcopy(rows); altered[0]["author_reference_reconciled"] = False
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            score_comparison(altered, scores(rows))

    def test_one_class_or_no_eligible_rows_cannot_report_primary_metrics(self):
        for codes in (("Negative",) * 3, ("Positive", "Not scored", "Negative")):
            records = [(1, 2, "1", codes)]
            result = materialize(panel(records), candidates(records), [])
            with self.subTest(codes=codes), self.assertRaisesRegex(ValueError, "both observed assay classes"):
                score_comparison(result["rows"], scores(result["rows"]))


@unittest.skipUnless(importlib.util.find_spec("sklearn"), "Optional scikit-learn metric runtime")
class NativeOutcomeMetricTests(unittest.TestCase):
    def test_ties_and_perfect_ranking_use_native_ap_auc_and_paired_deltas(self):
        rows = materialized()["rows"]
        result = score_comparison(rows, scores(rows))
        for seed in ("17", "43"):
            self.assertEqual(result["metrics_by_arm_seed"]["rgcn_baseline"][seed],
                             {"average_precision": 0.5, "roc_auc": 0.5})
            self.assertEqual(result["metrics_by_arm_seed"]["rgcn_enriched"][seed],
                             {"average_precision": 1.0, "roc_auc": 1.0})
            self.assertEqual(result["paired_comparison"]["deltas_by_seed"][seed],
                             {"average_precision": 0.5, "roc_auc": 0.5})
        self.assertEqual(result["coverage"]["primary_scored_pairs_per_arm_seed"], 4)
        self.assertIsNone(result["formal_confidence_interval"])
        self.assertFalse(result["statistical_significance_claimed"])
        self.assertEqual(result["coverage"]["optional_gene_metadata"]["status"], "not_supplied")

    def test_gene_influence_removes_all_incident_pairs_and_keeps_no_ci_claim(self):
        rows = materialized()["rows"]
        result = score_comparison(rows, scores(rows))
        influence = result["leave_one_original_gene_out"]
        row = next(r for r in influence["records"] if r["omitted_original_gene"] == gene(1))
        self.assertEqual((row["removed_pairs"], row["remaining_pairs"]), (2, 2))
        self.assertEqual(row["status"], "scored")
        self.assertEqual(row["paired_seed_deltas"]["17"]["change_from_full_delta"]["average_precision"], 0.0)
        self.assertFalse(influence["retraining_performed"])
        self.assertNotIn(gene(10), {r["omitted_original_gene"] for r in influence["records"]})

    def test_insufficient_leave_gene_class_support_reported_without_invalid_auc(self):
        records = [(1, 2, "", ("Positive", "Negative", "Negative")),
                   (3, 4, "", ("Negative",) * 3)]
        rows = materialize(panel(records), candidates(records), [(gene(1), gene(2))])["rows"]
        result = score_comparison(rows, scores(rows))
        self.assertTrue(all(r["status"] == "insufficient_class_support" for r in result["leave_one_original_gene_out"]["records"]))
        self.assertIsNone(result["leave_one_original_gene_out"]["delta_ranges_by_seed"]["17"]["roc_auc"])

    def test_optional_coverage_retains_unknown_and_does_not_exclude_pairs(self):
        rows = materialized()["rows"]
        metadata = {gene(1): {"mapping": True, "context": False, "training_degree": 0}}
        result = score_comparison(rows, scores(rows), coverage_by_gene=metadata)
        strata = result["coverage"]["optional_gene_metadata"]["strata"]
        self.assertEqual(strata["off_diagonal_complete"]["mapping_endpoints"], {"present": 2, "unknown": 6})
        self.assertEqual(result["coverage"]["primary_scored_pairs_per_arm_seed"], 4)
        with self.assertRaisesRegex(ValueError, "Training degree"):
            score_comparison(rows, scores(rows), coverage_by_gene={gene(1): {"training_degree": -1}})


if __name__ == "__main__":
    unittest.main()
