"""Exact source binding and interpretation limits for optional drug context."""
from copy import deepcopy
import unittest

from biograph_steward.client import PharosClient, digest
from tools.sampled_audit import drug_activity_context as context


def fixture():
    edge = {"id": "edge:invented", "subject": "UniProtKB:INVENTED",
        "predicate": "biograph:has_drug_listing", "object": "pharos.ligand:ABCDEFGHIJKL",
        "evidence_record": {"ligid": "ABCDEFGHIJKL", "name": "invented drug", "isdrug": True}}
    assertion = {"id": "assertion:invented", "kind": "drug_listing",
        "subject": edge["subject"], "predicate": edge["predicate"], "object": edge["object"],
        "evidence_edge_ids": [edge["id"]]}
    dossier = {"format": "biograph-steward.sampled-assertion-dossier.v1", "case_id": "case_invented",
        "assertion_id": assertion["id"], "sample_id": "audit:invented", "assertion": assertion,
        "assertion_content_sha256": digest(assertion), "source_edges": [edge],
        "source_edge_content_sha256": {edge["id"]: digest(edge)}}
    dossier["content_sha256"] = digest(dossier)
    rows = [
        {"actid": 1, "type": "IC50", "value": 7.66, "moa": None, "reference": "invented citation",
         "target": {"uniprot": "INVENTED", "name": "invented target"}, "pubs": [{"pmid": "invented"}]},
        {"actid": 2, "type": "Kd", "value": 8.0, "moa": "invented", "reference": None,
         "target": {"uniprot": "OTHER", "name": "invented target"}, "pubs": None},
        {"actid": 3, "type": None, "value": None, "target": {"uniprot": None}, "pubs": None}]
    response = {"data": {"dbVersion": "invented_version", "ligand": {
        "ligid": "ABCDEFGHIJKL", "name": "invented drug", "isdrug": True,
        "actcnt": 3, "activities": rows, "synonyms": [
            {"name": "ChEMBL", "value": "INVENTED_ONE,INVENTED_TWO"}]}}}
    record = {"endpoint": "https://pharos-api.ncats.io/graphql", "request": {
        "query": context.QUERY, "variables": {"id": "LYCHI:ABCDEFGHIJKL"}},
        "response": response, "response_sha256": digest(response)}
    return dossier, record


def resign_record(record):
    record["response_sha256"] = digest(record["response"])


class DrugActivityContextTests(unittest.TestCase):
    def test_exact_accession_not_name_selects_context_without_semantic_backfill(self):
        dossier, record = fixture()
        before = deepcopy((dossier, record))
        result = context.inspect_record(dossier, record)
        self.assertEqual(result["activity_counts"], {
            "returned": 3, "exact_target": 1, "other_target": 1, "unresolved_target": 1})
        self.assertEqual(result["exact_target_activities"][0]["record"],
                         record["response"]["data"]["ligand"]["activities"][0])
        self.assertIn("not supplied", result["unit_or_scale"])
        self.assertIn("not supplied", result["native_assay_context"])
        self.assertEqual(result["source_ligand"]["synonyms"][0]["value"], "INVENTED_ONE,INVENTED_TWO")
        self.assertFalse(result["review_labels_assigned"])
        self.assertFalse(result["assertion_qualifiers_backfilled"])
        self.assertFalse(result["scientific_accuracy_measured"])
        self.assertEqual((dossier, record), before)

    def test_missing_exact_target_is_not_a_negative_biological_verdict(self):
        dossier, record = fixture()
        record["response"]["data"]["ligand"]["activities"][0]["target"]["uniprot"] = "OTHER"
        resign_record(record)
        result = context.inspect_record(dossier, record)
        self.assertEqual(result["activity_counts"]["exact_target"], 0)
        self.assertFalse(result["review_labels_assigned"])
        self.assertTrue(any("not a biological negative" in item for item in result["limits"]))

    def test_changed_query_variable_or_ligand_cannot_substitute_a_name_match(self):
        for mutation in ("query", "variable", "ligand"):
            dossier, record = fixture()
            if mutation == "query":
                record["request"]["query"] = context.QUERY.replace("all:true", "all:false")
            elif mutation == "variable":
                record["request"]["variables"]["id"] = "name:invented drug"
            else:
                record["response"]["data"]["ligand"]["ligid"] = "DIFFERENT123"
                resign_record(record)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                context.inspect_record(dossier, record)

    def test_changed_response_or_original_source_binding_is_rejected(self):
        dossier, record = fixture()
        record["response"]["data"]["ligand"]["activities"][0]["value"] = 100
        with self.assertRaisesRegex(ValueError, "response bytes"):
            context.inspect_record(dossier, record)
        dossier, record = fixture()
        dossier["source_edges"][0]["evidence_record"]["ligid"] = "DIFFERENT123"
        dossier.pop("content_sha256")
        dossier["content_sha256"] = digest(dossier)
        with self.assertRaisesRegex(ValueError, "source edge"):
            context.inspect_record(dossier, record)

    def test_partial_duplicate_and_over_bound_activity_rows_fail_closed(self):
        for mutation in ("partial", "duplicate", "bound"):
            dossier, record = fixture()
            kwargs = {}
            if mutation == "partial":
                record["response"]["data"]["ligand"]["actcnt"] = 4
            elif mutation == "duplicate":
                record["response"]["data"]["ligand"]["activities"][1]["actid"] = 1
            else:
                kwargs["max_activities"] = 2
            resign_record(record)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                context.inspect_record(dossier, record, **kwargs)

    def test_live_capture_size_guard_prevents_the_unpaginated_followup_call(self):
        dossier, _ = fixture()
        calls = []
        def transport(payload):
            calls.append(payload)
            return {"data": {"dbVersion": "invented", "ligand": {
                "ligid": "ABCDEFGHIJKL", "actcnt": 1001}}}
        client = PharosClient(transport=transport)
        with self.assertRaisesRegex(ValueError, "too large"):
            context.capture(dossier, client)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["query"], context.SIZE_QUERY)

    def test_live_capture_uses_existing_client_and_exact_identifier_twice(self):
        dossier, record = fixture()
        calls = []
        def transport(payload):
            calls.append(payload)
            if payload["query"] == context.SIZE_QUERY:
                return {"data": {"dbVersion": "invented", "ligand": {
                    "ligid": "ABCDEFGHIJKL", "actcnt": 3}}}
            return deepcopy(record["response"])
        client = PharosClient(transport=transport)
        result = context.capture(dossier, client)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(p["variables"] == {"id": "LYCHI:ABCDEFGHIJKL"} for p in calls))
        self.assertEqual(result["activity_counts"]["exact_target"], 1)


if __name__ == "__main__":
    unittest.main()
