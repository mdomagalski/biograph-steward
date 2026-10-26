"""Invented assay fixtures only: this test never opens experimental outcomes."""
from __future__ import annotations

import io
from itertools import product
import unittest

from biograph_steward import lambourne_outcomes as assay


P1, P2, P3, P4 = "P00001", "P00002", "P00003", "P00004"


def fixtures(*, result="Positive", score="1", c3="True", clw="True",
             a=P1, b=P2, ad="1", db="2", category="Zhang_et_al"):
    panel = assay.PANEL_HEADER + b"\n" + "\t".join(
        (a, b, ad, db, category, category, result, "True", "True")).encode() + b"\n"
    raw = assay.RAW_HEADER + b"\n" + "\t".join((db, ad, category, score, c3, clw)).encode() + b"\n"
    identity = [{"source_row": 2, "uniprot_a": a, "uniprot_b": b,
                 "ad_orf_id": ad, "db_orf_id": db, "source_dataset_column_5": category,
                 "source_dataset_column_6": category,
                 "in_biorxiv_version": "True", "in_published_version": "True"}]
    crosswalk = f"uniprot_ac\torf_id\n{P1}\t1\n{P2}\t2\n{P3}\t3\n{P4}\t4\n".encode()
    return panel, raw, identity, crosswalk


def one(**kwargs):
    result = assay.adapt_outcomes(*fixtures(**kwargs))
    return result, result["rows"][0]


class AuthorStatusTests(unittest.TestCase):
    def test_confirmed_positive_and_negative_use_different_confirmation(self):
        self.assertEqual(assay.author_status("1", True, False), ("Positive", True, True))
        self.assertEqual(assay.author_status("0", None, True), ("Negative", True, False))

    def test_failure_precedence_is_author_order(self):
        for c3, clw in product((True, False, None), repeat=2):
            self.assertEqual(assay.author_status("AA", c3, clw), ("Autoactivator", False, None))
            self.assertEqual(assay.author_status("NA", c3, clw), ("Test failed", False, None))
        self.assertEqual(assay.author_status("1", False, True), ("Failed sequence confirmation", False, True))
        self.assertEqual(assay.author_status("0", None, False), ("Failed sequence confirmation", False, False))

    def test_nullable_confirmation_retains_author_label(self):
        self.assertEqual(assay.author_status("1", None, True), ("Positive", None, True))
        self.assertEqual(assay.author_status("0", None, None), ("Negative", None, False))

    def test_negative_with_any_nonmissing_3at_is_author_inconsistency(self):
        for c3, clw in product((True, False), (True, False, None)):
            with self.subTest(c3=c3, clw=clw), self.assertRaisesRegex(ValueError, "Author inconsistency"):
                assay.author_status("0", c3, clw)

    def test_unknown_values_never_become_boolean_by_truthiness(self):
        for score in ("2", "positive", "0.0", "-1"):
            with self.subTest(score=score), self.assertRaises(ValueError):
                assay.author_status(score, True, True)
        for confirmation in ("True", "False", 1, 0, [], {}):
            with self.subTest(confirmation=confirmation), self.assertRaises(ValueError):
                assay.author_status("1", confirmation, True)


class AdapterTests(unittest.TestCase):
    def test_confirmed_endpoint_and_nondetection_meaning(self):
        report, row = one()
        self.assertTrue(report["scoring_allowed"])
        self.assertTrue(row["evaluable"])
        self.assertIs(row["detected"], True)
        self.assertEqual(row["assay_status"], "detected")
        self.assertIn("not biological falsity", report["endpoint"])
        report, row = one(result="Negative", score="0", c3="NULL")
        self.assertTrue(row["evaluable"])
        self.assertIs(row["detected"], False)
        self.assertEqual(row["required_confirmation"], "lw")
        self.assertEqual(row["assay_status"], "not_detected")

    def test_all_failure_states_stay_excluded_and_retained(self):
        scenarios = [("Test failed", "NA", "NULL", "test_failed"),
                     ("Autoactivator", "AA", "True", "autoactivator"),
                     ("Failed sequence confirmation", "1", "False", "failed_sequence_confirmation")]
        for result, score, c3, status in scenarios:
            with self.subTest(result=result):
                report, row = one(result=result, score=score, c3=c3)
                self.assertTrue(report["scoring_allowed"])
                self.assertEqual(row["assay_status"], status)
                self.assertFalse(row["evaluable"])
                self.assertIsNone(row["detected"])
                self.assertEqual(report["counts"]["published_nominations"], 1)

    def test_null_applicable_confirmation_is_explicit_qualification(self):
        for result, score, clw in (("Positive", "1", "True"), ("Negative", "0", "NULL")):
            with self.subTest(result=result):
                report, row = one(result=result, score=score, c3="NULL", clw=clw)
                self.assertEqual(row["author_result"], result)
                self.assertEqual(row["published_result"], result)
                self.assertEqual(row["assay_status"], "ambiguous_sequence_confirmation")
                self.assertFalse(row["evaluable"])
                self.assertIsNone(row["detected"])
                self.assertTrue(report["scoring_allowed"])

    def test_numeric_boolean_forms_follow_author_csv_conversion(self):
        for token in ("1", "1.0"):
            report, row = one(c3=token)
            self.assertTrue(report["scoring_allowed"])
            self.assertIs(row["confirmation_3at"], True)
        for token in ("0", "0.0"):
            report, row = one(result="Failed sequence confirmation", c3=token)
            self.assertTrue(report["scoring_allowed"])
            self.assertIs(row["confirmation_3at"], False)

    def test_source_status_disagreement_blocks_whole_assessment(self):
        report, row = one(result="Negative")
        self.assertFalse(report["scoring_allowed"])
        self.assertIn("raw_published_status_mismatch", row["issues"])
        self.assertEqual(row["assay_status"], "inconsistent")
        self.assertFalse(row["evaluable"])

    def test_unknown_raw_and_published_states_block(self):
        for kwargs in ({"score": "2"}, {"c3": "yes"}, {"result": "Maybe"}):
            with self.subTest(kwargs=kwargs):
                report, row = one(**kwargs)
                self.assertFalse(report["scoring_allowed"])
                self.assertEqual(row["assay_status"], "unexpected_state")
                self.assertFalse(row["evaluable"])

    def test_author_inconsistency_is_not_silently_overridden_by_supplement(self):
        report, row = one(result="Negative", score="0", c3="False")
        self.assertFalse(report["scoring_allowed"])
        self.assertIn("author_preprocessing_inconsistency", row["issues"])

    def test_unordered_protein_endpoints_do_not_reassign_experimental_orientation(self):
        report, row = one(a=P2, b=P1)
        self.assertTrue(report["scoring_allowed"])
        self.assertEqual(row["products"], [P1, P2])
        self.assertEqual((row["ad_orf_id"], row["db_orf_id"]), ("1", "2"))
        report, row = one(ad="2", db="1")
        self.assertTrue(report["scoring_allowed"])
        self.assertTrue(row["construct_match"])

    def test_opposite_raw_orientation_cannot_substitute_for_tested_construct(self):
        panel, raw, identity, mapping = fixtures()
        raw = raw.replace(b"2\t1\tZhang", b"1\t2\tZhang")
        report = assay.adapt_outcomes(panel, raw, identity, mapping)
        self.assertFalse(report["scoring_allowed"])
        self.assertIn("raw_construct_orientation_mismatch", report["rows"][0]["issues"])

    def test_missing_or_inconsistent_mapping_blocks_even_with_published_positive(self):
        for mapping in (f"uniprot_ac\torf_id\n{P1}\t1\n{P3}\t3\n".encode(),
                        f"uniprot_ac\torf_id\n{P1}\t3\n{P2}\t2\n".encode()):
            panel, raw, identity, _ = fixtures()
            report = assay.adapt_outcomes(panel, raw, identity, mapping)
            self.assertFalse(report["scoring_allowed"])
            self.assertIn("orf_crosswalk_mismatch", report["rows"][0]["issues"])

    def test_raw_missing_construct_stays_visible(self):
        panel, raw, identity, mapping = fixtures()
        raw = raw.replace(b"2\t1\tZhang", b"4\t3\tZhang")
        report = assay.adapt_outcomes(panel, raw, identity, mapping)
        self.assertFalse(report["scoring_allowed"])
        self.assertEqual(report["rows"][0]["raw_source_rows"], [])
        self.assertIn("raw_construct_missing", report["rows"][0]["issues"])

    def test_identical_raw_duplicates_preserve_provenance_and_conflicting_rows_block(self):
        panel, raw, identity, mapping = fixtures()
        duplicate = raw + raw.splitlines()[1] + b"\n"
        report = assay.adapt_outcomes(panel, duplicate, identity, mapping)
        self.assertTrue(report["scoring_allowed"])
        self.assertEqual(report["rows"][0]["raw_source_rows"], [2, 3])
        conflict = raw + raw.splitlines()[1].replace(b"\t1\tTrue", b"\t1\tFalse") + b"\n"
        report = assay.adapt_outcomes(panel, conflict, identity, mapping)
        self.assertFalse(report["scoring_allowed"])
        self.assertIn("conflicting_raw_construct_rows", report["rows"][0]["issues"])

    def test_duplicate_published_pair_and_construct_block_without_cherry_picking(self):
        panel, raw, identity, mapping = fixtures()
        panel += panel.splitlines()[1] + b"\n"
        identity.append(dict(identity[0], source_row=3))
        report = assay.adapt_outcomes(panel, raw, identity, mapping)
        self.assertFalse(report["scoring_allowed"])
        self.assertEqual(len(report["rows"]), 2)
        self.assertIn("duplicate_nominated_pair", report["rows"][1]["issues"])
        self.assertIn("duplicate_nominated_construct", report["rows"][1]["issues"])

    def test_controls_are_never_decoded_or_scored(self):
        panel, raw, identity, mapping = fixtures()
        panel += f"{P3}\t{P4}\t3\t4\thsPRS-v2\thsPRS-v2\t".encode() + b"\xff\tNULL\tNULL\n"
        identity.append(dict(source_row=3, uniprot_a=P3, uniprot_b=P4, ad_orf_id="3", db_orf_id="4",
                             source_dataset_column_5="hsPRS-v2", source_dataset_column_6="hsPRS-v2",
                             in_biorxiv_version="NULL", in_published_version="NULL"))
        raw += b"4\t3\thsPRS-v2\t\xff\t\xff\t\xff\n"
        report = assay.adapt_outcomes(panel, raw, identity, mapping)
        self.assertTrue(report["scoring_allowed"])
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["counts"]["excluded_nonnomination_rows"], 1)

    def test_identity_change_or_outcome_selected_subset_rejected_before_scoring(self):
        panel, raw, identity, mapping = fixtures()
        for changed in ([], [dict(identity[0], ad_orf_id="99")], [dict(identity[0], result="Positive")]):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "frozen complete audit"):
                assay.adapt_outcomes(panel, raw, changed, mapping)

    def test_duplicate_header_position_and_width_are_required(self):
        panel, raw, identity, mapping = fixtures()
        malformed = [panel.replace(b"source_dataset\tsource_dataset", b"source_dataset\tsource_dataset.1"),
                     panel.replace(b"\tPositive\t", b"\tPositive\textra\t")]
        for data in malformed:
            with self.subTest(data=data), self.assertRaises(ValueError):
                assay.adapt_outcomes(data, raw, identity, mapping)
        changed = panel.replace(b"Zhang_et_al\tZhang_et_al", b"Zhang_et_al\thsPRS-v2")
        identity[0]["source_dataset_column_6"] = "hsPRS-v2"
        with self.assertRaisesRegex(ValueError, "columns disagree"):
            assay.adapt_outcomes(changed, raw, identity, mapping)


try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = np = None


@unittest.skipUnless(pd is not None and pd.__version__ == "1.4.3", "Optional author pandas 1.4.3 runtime")
class PinnedAuthorExpressionTests(unittest.TestCase):
    def test_all_invented_score_confirmation_combinations_match_author_expressions(self):
        # These expressions are copied from the preserved historical function;
        # its private database, author files and controls are never accessed.
        for score, c3, clw in product(("0", "1", "AA", "NA"), (True, False, None), (True, False, None)):
            if score == "0" and c3 is not None:
                with self.assertRaises(ValueError):
                    assay.author_status(score, c3, clw)
                continue
            df = pd.DataFrame({"final_score": [score], "seq_confirmation_final_3at": [c3],
                               "seq_confirmation_final_lw": [clw]})
            df["final_score"] = df["final_score"].fillna("NA")
            df["seq_confirmation_final_3at"] = df["seq_confirmation_final_3at"].astype(pd.BooleanDtype())
            df["seq_confirmation_final_lw"] = df["seq_confirmation_final_lw"].astype(pd.BooleanDtype())
            df["result"] = df["final_score"].map({"0": False, "1": True, "AA": np.nan, "NA": np.nan})
            df["seq_confirmation_combined"] = (
                ((df["result"] == True) & (df["seq_confirmation_final_3at"] == True)) |
                ((df["result"] == False) & (df["seq_confirmation_final_lw"] == True)))
            df.loc[df["seq_confirmation_combined"] == False, "result"] = np.nan
            df["result"] = df["result"].map({True: "Positive", False: "Negative", np.nan: "Test failed"})
            df.loc[df["final_score"] == "AA", "result"] = "Autoactivator"
            df.loc[(df["seq_confirmation_combined"] == False) & (df["result"] == "Test failed"), "result"] = "Failed sequence confirmation"
            df.loc[df["final_score"] == "NA", "result"] = "Test failed"
            expected_combined = df.iloc[0]["seq_confirmation_combined"]
            expected_combined = None if pd.isna(expected_combined) else bool(expected_combined)
            actual = assay.author_status(score, c3, clw)
            with self.subTest(score=score, c3=c3, clw=clw):
                self.assertEqual(actual[:2], (df.iloc[0]["result"], expected_combined))

    def test_pinned_default_missing_tokens_are_not_guessed(self):
        from pandas._libs.parsers import STR_NA_VALUES
        self.assertEqual(assay.MISSING, STR_NA_VALUES)

    def test_explicit_boolean_tokens_match_author_csv_and_boolean_conversion(self):
        for token in ("True", "False", "1", "0", "1.0", "0.0", "NULL"):
            data = pd.read_csv(io.StringIO(f"id\tconfirmation\n1\t{token}\n2\tNULL\n"), sep="\t")
            actual = data["confirmation"].astype(pd.BooleanDtype()).iloc[0]
            expected = None if pd.isna(actual) else bool(actual)
            self.assertEqual(assay._confirmation(token), expected)


if __name__ == "__main__":
    unittest.main()
