"""Synthetic source rows and dispositions only; no biological outcome access."""
from copy import deepcopy
import hashlib
import unittest

from biograph_steward.client import digest
from source_eligibility import apply_reviewed_source_dispositions, canonical_source_row_digest


SOURCE = b"invented source release bytes\n"
SOURCE_SHA = hashlib.sha256(SOURCE).hexdigest()


def record(sid, ordinal, *, target="T1", alias="SAME_ALIAS"):
    return {"source_record_id": sid, "source_data_record_ordinal": ordinal,
            "source_row": {"RECORD": sid, "ALIAS": alias, "CITATION": "invented", "TEXT": "α unchanged"},
            "enzyme": "E1", "site_host": target, "residue": "S", "position": "1"}


def review(row, disposition="exclude"):
    return {"source_release": "invented-v1", "source_sha256": SOURCE_SHA,
            "source_record_id": row["source_record_id"],
            "source_data_record_ordinal": row["source_data_record_ordinal"],
            "canonical_source_row_sha256": digest(row["source_row"]),
            "disposition": disposition, "reason": "Explicit invented review",
            "method": "synthetic source inspection", "actor": "test reviewer"}


def apply(rows, decisions, **kwargs):
    return apply_reviewed_source_dispositions(rows, decisions, source_release="invented-v1",
        source_bytes=SOURCE, source_sha256=SOURCE_SHA, raw_record_id_field="RECORD", **kwargs)


class SourceEligibilityTests(unittest.TestCase):
    def test_exact_record_exclusion_does_not_match_an_alias_globally(self):
        rows = [record("A", 1), record("B", 2, target="T2")]
        original = deepcopy(rows)
        result = apply(rows, [review(rows[0])])
        self.assertEqual([r["source_record_id"] for r in result["retained_records"]], ["B"])
        self.assertEqual(result["excluded_records"], [rows[0]])
        self.assertEqual(result["unreviewed_records_retained"], 1)
        self.assertEqual(rows, original)
        self.assertFalse(result["identifiers_remapped"])
        self.assertFalse(result["biological_truth_assessed"])

    def test_another_eligible_support_preserves_the_collapsed_link(self):
        rows = [record("A", 1), record("B", 2)]
        result = apply(rows, [review(rows[0])])
        self.assertEqual(result["removed_link_keys"], [])
        self.assertEqual(len(result["retained_link_support"]), 1)
        self.assertEqual([r["source_record_id"] for r in result["retained_link_support"][0]["source_records"]], ["B"])
        both = apply(rows, [review(r) for r in rows])
        self.assertEqual(both["retained_link_support"], [])
        self.assertEqual(both["removed_link_keys"], [{"enzyme":"E1","site_host":"T1","residue":"S","position":"1"}])

    def test_abstention_and_explicit_retention_preserve_unmodified_records(self):
        rows = [record("A", 1), record("B", 2)]
        result = apply(rows, [review(rows[0], "abstain"), review(rows[1], "retain")])
        self.assertEqual(result["retained_records"], rows)
        self.assertEqual(result["excluded_records"], [])
        result["retained_records"][0]["source_row"]["ALIAS"] = "changed output"
        self.assertEqual(rows[0]["source_row"]["ALIAS"], "SAME_ALIAS")

    def test_changed_full_source_bytes_fail_before_applying_review(self):
        row = record("A", 1)
        with self.assertRaisesRegex(ValueError, "source bytes"):
            apply_reviewed_source_dispositions([row], [review(row)], source_release="invented-v1",
                source_bytes=SOURCE+b"changed", source_sha256=SOURCE_SHA, raw_record_id_field="RECORD")

    def test_stale_release_file_hash_row_hash_and_ordinal_fail(self):
        row = record("A", 1)
        for field, value in (("source_release", "invented-v0"), ("source_sha256", "0"*64),
                             ("canonical_source_row_sha256", "0"*64),
                             ("source_data_record_ordinal", 2), ("source_data_record_ordinal", True)):
            stale = review(row); stale[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                apply([row], [stale])
        changed = deepcopy(row); changed["source_row"]["TEXT"] += " changed"
        with self.assertRaisesRegex(ValueError, "raw-row digest"):
            apply([changed], [review(row)])

    def test_unknown_duplicate_and_native_record_identity_mismatches_fail(self):
        row = record("A", 1)
        unknown = review(row); unknown["source_record_id"] = "B"
        for rows, decisions in (([row], [unknown]), ([row], [review(row), review(row)]),
                                ([row, deepcopy(row)], []), ([row, record("B", 1)], [])):
            with self.subTest(rows=rows, decisions=decisions), self.assertRaises(ValueError):
                apply(rows, decisions)
        wrong = deepcopy(row); wrong["source_row"]["RECORD"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "native source row"):
            apply([wrong], [])

    def test_unreviewed_source_is_not_silently_dropped(self):
        rows = [record("A", 1), record("B", 2)]
        result = apply(rows, [])
        self.assertEqual(result["retained_records"], rows)
        self.assertEqual(result["unreviewed_records_retained"], 2)
        self.assertEqual(result["applied_dispositions"], [])

    def test_no_unsupported_replacement_or_unexplained_disposition(self):
        row = record("A", 1)
        for field, value in (("replacement_accession", "E2"), ("disposition", "auto_correct"),
                             ("disposition", ["exclude"]), ("reason", ""), ("actor", None)):
            changed = review(row); changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                apply([row], [changed])

    def test_canonical_decoded_row_hash_preserves_unicode_and_exact_strings(self):
        row = record("A", 1)
        self.assertEqual(canonical_source_row_digest(row["source_row"]), digest(row["source_row"]))
        altered = dict(row["source_row"], TEXT="a unchanged")
        self.assertNotEqual(canonical_source_row_digest(altered), canonical_source_row_digest(row["source_row"]))
        with self.assertRaises(ValueError):
            canonical_source_row_digest({"TEXT": float("nan")})

    def test_custom_exact_link_fields_do_not_infer_a_biological_mapping(self):
        row = record("A", 1)
        row["opaque_link"] = "provided-link"
        result = apply([row], [], link_fields=("opaque_link",))
        self.assertEqual(result["retained_link_support"][0]["link"], {"opaque_link":"provided-link"})
        with self.assertRaises(ValueError):
            apply([row], [], link_fields=(["opaque_link"],))


if __name__ == "__main__":
    unittest.main()
