"""Invented context records test exact matching, not cancer-response truth."""
from copy import deepcopy
import unittest

from biograph_steward.client import digest
from tools.reference_accuracy.civic_assertions import context_key, native_response_rows


def record():
    return {"id": 1, "status": "ACCEPTED", "flagged": False, "openRevisionCount": 0,
        "assertionType": "PREDICTIVE", "variantOrigin": "SOMATIC", "therapyInteractionType": None,
        "molecularProfile": {"id": 7, "isComplex": False, "isMultiVariant": False,
            "deprecated": False, "flagged": False, "variants": [{"id": 8, "deprecated": False,
                "flagged": False, "feature": {"id": 9, "deprecated": False,
                    "featureInstance": {"__typename": "Gene", "entrezId": 42}}}]},
        "disease": {"id": 10, "doid": "99", "deprecated": False},
        "therapies": [{"id": 11, "ncitId": "C123", "deprecated": False}]}


class CivicExactContextTests(unittest.TestCase):
    def test_native_evidence_and_assertion_type_fields_share_only_exact_context(self):
        a = record(); e = deepcopy(a)
        e["evidenceType"] = e.pop("assertionType")
        self.assertEqual(context_key(a), context_key(e))
        self.assertNotIn("assertionDirection", a)

    def test_full_variant_profile_therapy_set_and_disease_are_not_widened(self):
        original = record(); key = context_key(original)
        changes = []
        r = deepcopy(original); r["therapies"].append({"id": 12, "ncitId": "C456", "deprecated": False}); r["therapyInteractionType"] = "COMBINATION"; changes.append(r)
        r = deepcopy(original); r["therapyInteractionType"] = "SUBSTITUTES"; changes.append(r)
        r = deepcopy(original); r["molecularProfile"]["id"] = 999; changes.append(r)
        r = deepcopy(original); r["molecularProfile"]["variants"][0]["id"] = 999; changes.append(r)
        r = deepcopy(original); r["disease"]["id"] = 999; changes.append(r)
        r = deepcopy(original); r["disease"]["doid"] = "parent"; changes.append(r)
        r = deepcopy(original); r["variantOrigin"] = "GERMLINE"; changes.append(r)
        for changed in changes:
            with self.subTest(changed=changed):
                self.assertNotEqual(context_key(changed), key)

    def test_flagged_revised_missing_and_deprecated_records_are_unknown(self):
        for field, value in (("flagged", True), ("status", "SUBMITTED"), ("openRevisionCount", 1)):
            r = record(); r[field] = value
            self.assertIsNone(context_key(r))
        r = record(); r["molecularProfile"]["variants"][0]["deprecated"] = True
        self.assertIsNone(context_key(r))
        r = record(); r.pop("variantOrigin")
        self.assertIsNone(context_key(r))
        r = record(); r["molecularProfile"]["id"] = True
        self.assertIsNone(context_key(r))
        r = record(); r["therapies"] *= 2
        self.assertIsNone(context_key(r))

    def test_native_response_digest_and_complete_pagination_are_required(self):
        rows = [record()]
        response = {"data": {"assertions": {"nodes": rows, "totalCount": 1, "pageInfo": {"hasNextPage": False}}}}
        capture = {"assertions": rows, "request_records": [{"endpoint": "https://civicdb.org/api/graphql",
            "response": response, "response_sha256": digest(response)}]}
        self.assertEqual(native_response_rows(capture), rows)
        response["data"]["assertions"]["pageInfo"]["hasNextPage"] = True
        with self.assertRaisesRegex(ValueError, "source/seal"):
            native_response_rows(capture)
        capture["request_records"][0]["response_sha256"] = digest(response)
        with self.assertRaisesRegex(ValueError, "pagination"):
            native_response_rows(capture)


if __name__ == "__main__":
    unittest.main()
