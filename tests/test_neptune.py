"""Synthetic Neptune protocol/parity tests; no cloud or scientific scoring."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.neptune import (MANIFEST, Mirror, export_projection,
                                      _NODES, _EDGES, _NODE, _INCIDENT, _ASSERTIONS)


def fixture():
    graph = {"graph_format": "synthetic-test", "snapshot_sha256": "synthetic-source",
        "db_version": {"version": "synthetic", "unknown_null": None},
        "nodes": [{"id": uid, "name": 'Name, "quoted"\n' + uid,
                   "category": "biolink:Protein"} for uid in ("P:A", "P:B", "P:C")],
        "edges": [], "assertions": [], "review_events": [{"sequence": 1,
            "reason": "A review is preserved, not scored", "reviewer": "SYNTHETIC"}],
        "context_records": [{"id": "context:1", "raw": {"list": [1, None, False]}}],
        "quarantine": [{"reason": "Original source not normalized", "raw": ["x", 2]}],
        "assay_observations": [{"id": "assay:1", "outcome": "not_detected", "graph_edge_id": None}],
        "unknown_inventory": [1, None, True, ["nested", {"a": "β"}], {"unknown": "\x00"}],
        "empty_inventory": [], "metadata": ["A source array may itself be named metadata"]}
    for number, species in enumerate(("NCBITaxon:9606", "NCBITaxon:10090"), 1):
        aid, eid = "assertion:" + str(number), "edge:" + str(number)
        qualifiers = {"assay": "MI:0018", "species": species, "tissue": None}
        graph["edges"].append({"id": eid, "subject": "P:A", "predicate": "biolink:related_to",
            "object": "P:B", "assertion_id": aid, "record_kind": "assay_observation",
            "status": "passed_structural_checks", "qualifiers": qualifiers,
            "evidence_record": {"source_id": "record," + str(number), "outcome": "detected"},
            "record_locators": ["snapshot.json#/targets/0/records/" + str(number)],
            "publications": ["PMID:123"], "source_scores_raw": {"conf": 0.9}})
        graph["assertions"].append({"id": aid, "subject": "P:A", "predicate": "biolink:related_to",
            "object": "P:B", "kind": "assay_observation", "qualifiers": qualifiers,
            "symmetric": False, "lifecycle_state": "candidate" if number == 1 else "provisional",
            "evidence_edge_ids": [eid], "structurally_usable_evidence_ids": [eid],
            "review_history": [], "independent_evidence_count": None})
    return graph


def load_csv(folder, filename):
    result = {}
    with (Path(folder) / filename).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            props = {}
            for column, value in row.items():
                if column.startswith(":") or value == "":
                    continue
                name, kind = column.rsplit(":", 1)
                props[name] = int(value) if kind == "Long" else value
            record = {"db_id": row[":ID"], "props": props}
            if filename == "nodes.csv":
                record["labels"] = row[":LABEL"].split(";")
            else:
                record.update(from_id=row[":START_ID"], to_id=row[":END_ID"], edge_type=row[":TYPE"])
            if record["db_id"] in result:
                raise AssertionError("Duplicate CSV ID")
            result[record["db_id"]] = record
    return result


class FakeNeptune:
    def __init__(self, folder):
        self.nodes = load_csv(folder, "nodes.csv")
        self.edges = load_csv(folder, "relationships.csv")
        self.queries, self.loads, self.statuses = [], [], []

    def execute_open_cypher_query(self, *, openCypherQuery, parameters):
        args = json.loads(parameters)
        self.queries.append((openCypherQuery, args))
        if openCypherQuery in (_NODES, _EDGES):
            source = self.nodes if openCypherQuery == _NODES else self.edges
            rows = [row for uid, row in sorted(source.items()) if uid > args["after"] and
                    (uid.startswith(args["prefix"]) or row["props"].get("dataset_id") == args["dataset_id"]
                     or (openCypherQuery == _EDGES and any(row[key].startswith(args["prefix"])
                         for key in ("from_id", "to_id"))))][:500]
        elif openCypherQuery == _NODE:
            rows = [self.nodes[args["node_id"]]] if args["node_id"] in self.nodes else []
        elif openCypherQuery == _INCIDENT:
            rows = [row for _, row in sorted(self.edges.items()) if args["node_id"] in
                    (row["from_id"], row["to_id"])][:1001]
        elif openCypherQuery == _ASSERTIONS:
            rows = [row for uid, row in sorted(self.nodes.items()) if uid in args["ids"]]
        else:
            raise AssertionError("Unexpected query")
        return {"results": deepcopy(rows)}

    def start_loader_job(self, **kwargs):
        self.loads.append(kwargs)
        return {"status": "200 OK", "payload": {"loadId": "job-123"}}

    def get_loader_job_status(self, **kwargs):
        self.statuses.append(kwargs)
        return {"payload": {"overallStatus": {"status": "LOAD_COMPLETED"}}}


class NeptuneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "projection"
        self.graph = fixture()
        self.manifest = export_projection(self.graph, self.folder)
        self.fake = FakeNeptune(self.folder)
        self.mirror = Mirror("https://synthetic.cluster.neptune.amazonaws.com:8182", "us-east-1", self.fake)

    def test_official_csv_and_all_inventories_round_trip_without_source_changes(self):
        original = fixture()
        self.assertEqual(self.graph, original)
        with (self.folder / "relationships.csv").open(newline="") as handle:
            header = next(csv.reader(handle))
        self.assertEqual(header[:4], [":ID", ":START_ID", ":END_ID", ":TYPE"])
        metadata = next(json.loads(row["props"]["record_json"]) for row in self.fake.nodes.values()
                        if row["labels"] == ["Metadata"])
        restored = metadata["metadata"]
        for inventory, length in metadata["inventories"].items():
            source = self.fake.edges if inventory == "edges" else self.fake.nodes
            records = [row for row in source.values() if row["props"]["inventory"] == inventory
                       and row["props"]["record_role"] == "inventory"]
            self.assertEqual(len(records), length)
            restored[inventory] = [json.loads(row["props"]["record_json"])
                                   for row in sorted(records, key=lambda row: row["props"]["ordinal"])]
        self.assertEqual(restored, original)
        self.assertEqual(digest(restored), self.manifest["graph_sha256"])
        self.assertFalse(self.manifest["queryable"])
        self.assertEqual({row["props"]["q_species"] for row in self.fake.edges.values()},
                         {"NCBITaxon:9606", "NCBITaxon:10090"})
        self.assertEqual(len(self.fake.edges), 2)  # Parallel evidence was not pair-collapsed.
        self.assertTrue((self.folder / MANIFEST).is_file())

    def test_full_parity_and_cached_read_preserve_source_ids_direction_and_review(self):
        receipt = self.mirror.verify(self.graph)
        self.assertTrue(receipt["complete_record_parity"])
        audit_queries = len(self.fake.queries)
        result = self.mirror.inspect(self.graph, "P:B", limit=1)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["edge_ids"]), 1)
        self.assertEqual(result["edges"][0]["subject"], "P:A")
        self.assertEqual(result["edges"][0]["object"], "P:B")
        self.assertIn(result["assertions"][0]["lifecycle_state"], {"candidate", "provisional"})
        self.assertFalse(result["assertions"][0]["symmetric"])
        self.assertEqual(result["full_parity_verified_at"], receipt["verified_at"])
        self.assertEqual(len(self.fake.queries) - audit_queries, 3)
        self.assertEqual(self.mirror.inspect(self.graph, "P:C")["edge_ids"], [])

    def test_incomplete_extra_changed_record_and_wrong_endpoint_fail_full_verification(self):
        uid = next(iter(self.fake.edges))
        for mutate in (lambda f: f.edges.pop(uid),
                       lambda f: f.edges[uid]["props"].update(record_sha256="0" * 64),
                       lambda f: f.edges[uid]["props"].update(q_species="NCBITaxon:999"),
                       lambda f: f.edges[uid].update(to_id=f.edges[uid]["from_id"]),
                       lambda f: f.edges.update({uid + "extra": {**deepcopy(f.edges[uid]), "db_id": uid + "extra"}})):
            with self.subTest(mutation=mutate):
                fake = FakeNeptune(self.folder)
                mutate(fake)
                mirror = Mirror(self.mirror.endpoint, "us-east-1", fake)
                with self.assertRaises(ValueError):
                    mirror.verify(self.graph)
                self.assertFalse(mirror._verified)

    def test_selected_records_are_freshly_checked_after_cached_verification(self):
        self.mirror.verify(self.graph)
        uid = next(iter(self.fake.edges))
        self.fake.edges[uid]["props"]["record_json"] = "{}"
        with self.assertRaises(ValueError):
            self.mirror.inspect(self.graph, "P:A")

    def test_rogue_cross_dataset_relationship_cannot_escape_full_namespace_audit(self):
        self.assertIn("id(s) STARTS WITH $prefix", _EDGES)
        self.assertIn("id(o) STARTS WITH $prefix", _EDGES)
        original = next(iter(self.fake.edges.values()))
        self.fake.edges["foreign:edge"] = {"db_id": "foreign:edge", "from_id": original["from_id"],
            "to_id": "foreign:node", "edge_type": "UNEXPECTED", "props": {"note": "No dataset marker"}}
        with self.assertRaises(ValueError):
            self.mirror.verify(self.graph)
        self.assertFalse(self.mirror._verified)

    def test_optional_sdk_failures_become_bounded_value_errors_without_sensitive_messages(self):
        exceptions = ModuleType("botocore.exceptions")
        class BotoCoreError(Exception):
            pass
        class ClientError(Exception):
            def __init__(self, code):
                super().__init__("sensitive SDK error message and credentials")
                self.response = {"Error": {"Code": code, "Message": "private source text"}}
        exceptions.BotoCoreError, exceptions.ClientError = BotoCoreError, ClientError
        errors = [ClientError("AccessDeniedException"), BotoCoreError("sensitive endpoint and credentials"),
                  ClientError("Invalid code containing sensitive source text")]
        with patch.dict(sys.modules, {"botocore.exceptions": exceptions}):
            for error in errors:
                with self.subTest(error=type(error).__name__):
                    for method in ("query", "load", "status"):
                        if method == "query":
                            target, call = "execute_open_cypher_query", lambda: self.mirror.verify(self.graph)
                        elif method == "load":
                            target, call = "start_loader_job", lambda: self.mirror.load("s3://test-bucket/csv/", "arn:aws:iam::123456789012:role/Loader")
                        else:
                            target, call = "get_loader_job_status", lambda: self.mirror.loader_status("job-123")
                        with patch.object(self.fake, target, side_effect=error), self.assertRaises(ValueError) as caught:
                            call()
                        self.assertLess(len(str(caught.exception)), 200)
                        self.assertNotIn("sensitive", str(caught.exception))
                        self.assertNotIn("private", str(caught.exception))
                        if isinstance(error, ClientError) and error.response["Error"]["Code"] == "AccessDeniedException":
                            self.assertIn("AccessDeniedException", str(caught.exception))

    def test_new_graph_digest_cannot_reuse_a_previous_receipt(self):
        self.mirror.verify(self.graph)
        changed = deepcopy(self.graph)
        changed["review_events"].append({"sequence": 2, "reason": "New review"})
        with self.assertRaises(ValueError):
            self.mirror.inspect(changed, "P:A")

    def test_actual_database_export_reconstructs_all_arrays_parallel_evidence_and_nested_json(self):
        output = Path(self.temp.name) / "database-export"
        receipt = self.mirror.export_graph(self.graph, output)
        restored = json.loads((output / "graph.json").read_text())
        self.assertEqual(restored, self.graph)
        self.assertEqual(digest(restored), receipt["graph_sha256"])
        self.assertTrue(receipt["reconstructed_from_database"])
        self.assertTrue(receipt["complete_graph_parity"])
        self.assertEqual(restored["unknown_inventory"], self.graph["unknown_inventory"])
        self.assertEqual(restored["metadata"], self.graph["metadata"])
        self.assertEqual(len(restored["edges"]), 2)
        self.assertEqual(restored["edges"][0]["subject"], restored["edges"][1]["subject"])
        self.assertNotEqual(restored["edges"][0]["qualifiers"], restored["edges"][1]["qualifiers"])
        # Exactly one shared verification sweep, not audit followed by reread.
        self.assertEqual([query for query, _ in self.fake.queries], [_NODES, _EDGES])
        self.assertEqual(json.loads((output / "export_receipt.json").read_text()), receipt)
        with self.assertRaises(ValueError):
            self.mirror.export_graph(self.graph, output)

    def test_database_export_reads_fresh_and_rejects_changed_records_without_partial_output(self):
        self.mirror.verify(self.graph)
        uid = next(iter(self.fake.edges))
        self.fake.edges[uid]["props"]["record_json"] = "{}"
        output = Path(self.temp.name) / "rejected-export"
        with self.assertRaises(ValueError):
            self.mirror.export_graph(self.graph, output)
        self.assertFalse(output.exists())
        self.assertEqual([query for query, _ in self.fake.queries], [_NODES, _EDGES, _NODES, _EDGES])
        self.assertFalse(self.mirror._verified)

    def test_paging_checks_complete_ids_beyond_first_page(self):
        graph = {"nodes": [{"id": "N:" + str(n)} for n in range(510)], "edges": [], "assertions": []}
        folder = Path(self.temp.name) / "large"
        export_projection(graph, folder)
        fake = FakeNeptune(folder)
        mirror = Mirror(self.mirror.endpoint, "us-east-1", fake)
        self.assertEqual(mirror.verify(graph)["counts"]["vertices"], 511)
        node_queries = [args for query, args in fake.queries if query == _NODES]
        self.assertEqual(len(node_queries), 2)
        self.assertTrue(node_queries[1]["after"])

    def test_export_rejects_duplicate_ids_invalid_json_support_and_existing_output(self):
        for change in (lambda g: g["nodes"].append(deepcopy(g["nodes"][0])),
                       lambda g: g["edges"][0].update(object="missing"),
                       lambda g: g["assertions"][0].update(evidence_edge_ids=[]),
                       lambda g: g.update(invalid={"not_json": float("nan")}),
                       lambda g: g.update(invalid={"set": {1, 2}})):
            graph = fixture()
            change(graph)
            with self.assertRaises(ValueError):
                export_projection(graph, Path(self.temp.name) / "invalid")
        with self.assertRaises(ValueError):
            export_projection(self.graph, self.folder)

    def test_loader_uses_bulk_api_not_mutation_queries_and_clears_cache(self):
        self.mirror.verify(self.graph)
        response = self.mirror.load("s3://synthetic-bucket/mirror/csv/", "arn:aws:iam::123456789012:role/Loader")
        self.assertEqual(response["payload"]["loadId"], "job-123")
        self.assertFalse(self.mirror._verified)
        request = self.fake.loads[0]
        self.assertEqual(request["format"], "opencypher")
        self.assertTrue(request["failOnError"])
        self.assertFalse(request["updateSingleCardinalityProperties"])
        self.assertEqual(request["mode"], "NEW")
        self.assertTrue(request["userProvidedEdgeIds"])
        self.mirror.loader_status("job-123")
        self.assertEqual(self.fake.statuses, [{"loadId": "job-123", "details": True, "errors": True}])

    def test_endpoint_and_read_options_are_bounded(self):
        for endpoint in ("http://example.com:8182", "https://user:secret@example.com", "https://example.com/openCypher", "https://example.com/?token=secret"):
            with self.assertRaises(ValueError):
                Mirror(endpoint, "us-east-1", self.fake)
        for node_id, limit in (("outside", 10), ("P:A", 0), ("P:A", 1001), ("P:A", True)):
            with self.assertRaises(ValueError):
                self.mirror.inspect(self.graph, node_id, limit)
        self.assertEqual(self.fake.queries, [])


if __name__ == "__main__":
    unittest.main()
