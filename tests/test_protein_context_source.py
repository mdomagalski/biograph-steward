"""Invented wire responses test capture, not protein biological accuracy."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import PharosClient, PharosError, digest
from biograph_steward.file_utils import sha
from biograph_steward.protein_context_source import (
    INFO_URL, MCP_URL, ENTRY_URL, OFFICIAL_CLIENT_SHA256, capture_context, normalize_sequence,
    parse_match_rpc, register_context)
from biograph_steward._vendor.interpro_mcp import mcp_client
from tests.protein_context_fixtures import match_rows


SEQUENCE = "M" + "A" * 37 + "XU"


def rpc(rows, identity=3):
    return {"jsonrpc": "2.0", "id": identity, "result": {"isError": False,
        "content": [{"type": "text", "text": json.dumps({"results": rows})}]}}


class SourceCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runs = Path(self.temp.name).resolve() / "runs"
        self.runs.mkdir()
        self.output = self.runs / "invented"
        self.calls = []
        self.info = {"api": "0.6.0", "release": "111.0", "release_date": "2026-01-01",
                     "analyses": [{"name": "Pfam", "version": "39.0"}]}
        self.sequence = SEQUENCE
        self.wrong_identity = False
        self.drift = False
        self.tool_failure = False
        self.http_failure = False
        self.bad_coordinate = False
        self.found = True
        self.empty = False
        self.info_calls = 0
        self.entry_response = None

    def client(self):
        def transport(payload):
            accession = payload["variables"]["id"]
            return {"data": {"dbVersion": "INVENTED", "source_licenses": [], "target": {
                "uniprot": "P01112" if self.wrong_identity else accession,
                "seq": self.sequence, "interpro": [], "pfam": [], "prosite": [],
                "smart": [], "panther": [], "sequence_annotations": []}}}
        return PharosClient(cache_dir=None, retries=0, transport=transport)

    def http(self, url, payload):
        self.calls.append((url, deepcopy(payload)))
        if url.startswith("https://www.ebi.ac.uk/interpro/api/entry/interpro/"):
            self.assertIsNone(payload)
            status, value = self.entry_response
            return status, {}, json.dumps(value).encode()
        if url == INFO_URL:
            self.info_calls += 1
            info = deepcopy(self.info)
            if self.drift and self.info_calls == 2:
                info["analyses"][0]["version"] = "CHANGED"
            return 200, {"Set-Cookie": "must-not-persist"}, json.dumps(info).encode()
        self.assertEqual(url, MCP_URL)
        method = payload["method"]
        if method == "initialize":
            result = {"protocolVersion": "2025-03-26", "serverInfo": {"name": "invented", "version": "test"}}
        elif method == "notifications/initialized":
            return 202, {}, b""
        elif method == "tools/list":
            result = {"tools": [{"name": "matchSequences", "description": "Invented",
                "inputSchema": {"type": "object", "properties": {"sequencesOrMd5s": {"type": "string"}},
                    "required": ["sequencesOrMd5s"]}}]}
        else:
            self.assertEqual(method, "tools/call")
            self.assertEqual(payload["params"]["name"], "matchSequences")
            md5s = payload["params"]["arguments"]["sequencesOrMd5s"].splitlines()
            self.assertTrue(all(len(x) == 32 for x in md5s))
            self.assertNotIn(SEQUENCE, json.dumps(payload))
            rows = []
            for md5 in md5s:
                matches = [] if self.empty or not self.found else match_rows()
                if self.bad_coordinate:
                    matches[0]["locations"][0]["end"] = len(SEQUENCE) + 1
                rows.append({"md5": md5.lower(), "found": self.found, "matches": matches})
            answer = rpc(rows, payload["id"])
            if self.tool_failure:
                answer["result"]["isError"] = True
            if self.http_failure:
                return 503, {}, b'{"error":"upstream unavailable"}'
            # Reuse unchanged author SSE parser, keeping the literal wire body.
            return 200, {}, ("event: message\ndata: " + json.dumps(answer) + "\n\n").encode()
        return 200, {}, json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": result}).encode()

    def capture(self, proteins=None, **kwargs):
        return capture_context(proteins or ["P04637"], self.output, runs_dir=self.runs,
                               client=self.client(), http_transport=self.http, **kwargs)

    def test_capture_preserves_wire_source_methods_nulls_fragments_and_sites(self):
        manifest = self.capture(register=True)
        rows = parse_match_rpc(json.loads((self.output / "interpro/matches_000.json").read_text()))
        native = next(iter(rows.values()))
        self.assertEqual(native["matches"], match_rows())
        self.assertEqual(len(native["matches"]), 3)
        self.assertIsNone(native["matches"][1]["signature"]["entry"])
        self.assertTrue((self.output / "interpro/matches_000.raw").read_bytes().startswith(b"event:"))
        self.assertEqual(manifest["content_sha256"], digest({k: v for k, v in manifest.items() if k != "content_sha256"}))
        for name, pin in manifest["files"].items():
            self.assertEqual(pin, {"sha256": sha(self.output / name), "bytes": (self.output / name).stat().st_size})
        self.assertEqual(manifest["source_code"]["official_client_sha256"], OFFICIAL_CLIENT_SHA256)
        self.assertEqual(sha(mcp_client.__file__), OFFICIAL_CLIENT_SHA256)
        self.assertNotIn("must-not-persist", (self.output / "source_requests.json").read_text())
        self.assertFalse(manifest["app_or_graph_changed"])
        self.assertFalse(manifest["scientific_accuracy_assessed"])
        self.assertEqual(json.loads((self.runs / "protein_context_index.json").read_text())["contexts"],
                         [{"id": self.output.name, "manifest_sha256": sha(self.output / "protein_context.json")}])

    def test_source_sequence_normalization_preserves_unusual_letters(self):
        self.assertEqual(normalize_sequence(" ma x\nu "), "MAXU")
        for value in (None, " \n"):
            self.assertIsNone(normalize_sequence(value))
        for value in (123, "MAX*", "AA-AA"):
            with self.assertRaises(ValueError):
                normalize_sequence(value)

    def test_same_sequence_has_one_md5_query_without_collapsing_exact_isoforms(self):
        manifest = self.capture(["P04637", "P04637-2"])
        self.assertEqual([r["protein"] for r in manifest["proteins"]], ["UniProtKB:P04637", "UniProtKB:P04637-2"])
        calls = [p for _, p in self.calls if p and p.get("method") == "tools/call"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]["params"]["arguments"]["sequencesOrMd5s"].splitlines()), 1)

    def test_missing_sequence_does_not_query_matches(self):
        self.sequence = None
        manifest = self.capture()
        row = manifest["proteins"][0]
        self.assertEqual(row["status"], "sequence_unavailable")
        for key in ("query_md5", "sequence_sha256", "sequence_length", "matches_file"):
            self.assertIsNone(row[key])
        self.assertFalse(any(p and p.get("method") == "tools/call" for _, p in self.calls))

    def test_optional_deleted_entry_keeps_native_history_and_http_status_without_remap(self):
        self.entry_response = 410, {"accession": "ipr999999", "source_database": "interpro",
            "deletion_date": "2022-08-25T00:00:00.000Z", "name": "INVENTED",
            "history": {"names": ["INVENTED historical name"]}}
        manifest = self.capture(entries=["IPR999999"])
        relative = manifest["entry_files"]["IPR999999"]
        self.assertEqual(json.loads((self.output / relative).read_text()), self.entry_response[1])
        requests = json.loads((self.output / "source_requests.json").read_text())["requests"]
        entry = next(r for r in requests if r.get("response_file") == relative)
        self.assertEqual(entry["http_status"], 410)
        self.assertEqual(entry["url"], ENTRY_URL.format("IPR999999"))
        self.assertNotIn("replacement", manifest)

    def test_optional_current_entry_preserves_llm_and_review_flags_without_truth_inference(self):
        self.entry_response = 200, {"metadata": {"accession": "IPR999999", "name": {"name": "INVENTED"},
            "is_llm": True, "is_reviewed_llm": False, "is_updated_llm": False, "go_terms": None}}
        manifest = self.capture(entries=["IPR999999"])
        native = json.loads((self.output / manifest["entry_files"]["IPR999999"]).read_text())
        self.assertEqual(native, self.entry_response[1])
        self.assertFalse(native["metadata"]["is_reviewed_llm"])
        self.assertFalse(manifest["scientific_accuracy_assessed"])

    def test_entry_identity_mismatch_and_undocumented_failure_do_not_complete(self):
        for number, response in enumerate(((200, {"metadata": {"accession": "IPR000001"}}),
                                            (404, {"detail": "not found"}))):
            self.output = self.runs / ("entry_failure_" + str(number))
            self.entry_response = response
            with self.assertRaises(ValueError):
                self.capture(entries=["IPR999999"])
            self.assertFalse((self.output / "protein_context.json").exists())

    def test_absent_lookup_and_found_empty_remain_distinct(self):
        self.found = False
        manifest = self.capture()
        row = manifest["proteins"][0]
        absent = parse_match_rpc(json.loads((self.output / row["matches_file"]).read_text()))[row["query_md5"]]
        self.assertIs(absent["found"], False)
        self.output = self.runs / "found_empty"
        self.found, self.empty = True, True
        manifest = self.capture()
        row = manifest["proteins"][0]
        empty = parse_match_rpc(json.loads((self.output / row["matches_file"]).read_text()))[row["query_md5"]]
        self.assertIs(empty["found"], True)
        self.assertEqual(empty["matches"], [])

    def test_changed_release_preserves_failure_not_manifest(self):
        self.drift = True
        with self.assertRaisesRegex(ValueError, "release changed"):
            self.capture()
        self.assertTrue((self.output / "interpro/info_after.json").exists())
        self.assertTrue((self.output / "failure.json").exists())
        self.assertFalse((self.output / "protein_context.json").exists())

    def test_exact_identity_mismatch_fails_closed(self):
        self.wrong_identity = True
        with self.assertRaisesRegex(ValueError, "exact protein identity"):
            self.capture()
        self.assertFalse((self.output / "protein_context.json").exists())

    def test_partial_graphql_response_is_not_replaced_or_accepted(self):
        client = PharosClient(cache_dir=None, retries=0, transport=lambda _: {
            "data": {"target": {"uniprot": "P04637", "seq": SEQUENCE}},
            "errors": [{"message": "Invented partial failure"}]})
        with self.assertRaises(PharosError):
            capture_context(["P04637"], self.output, runs_dir=self.runs,
                            client=client, http_transport=self.http)
        self.assertFalse((self.output / "protein_context.json").exists())
        failure = json.loads((self.output / "failure.json").read_text())
        self.assertFalse(failure["biological_negative_inferred"])
        requests = json.loads((self.output / "source_requests.json").read_text())["requests"]
        self.assertEqual(requests[-1]["request"]["variables"], {"id": "P04637"})
        self.assertEqual(requests[-1]["outcome"], "request_failed")

    def test_transport_failure_retains_attempt_metadata_without_native_result(self):
        def failed(url, payload):
            raise TimeoutError("Invented timeout")
        with self.assertRaises(TimeoutError):
            capture_context(["P04637"], self.output, runs_dir=self.runs,
                            client=self.client(), http_transport=failed)
        requests = json.loads((self.output / "source_requests.json").read_text())["requests"]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["url"], INFO_URL)
        self.assertEqual(requests[0]["outcome"], "transport_failed")
        self.assertIsNone(requests[0]["http_status"])
        self.assertFalse((self.output / "protein_context.json").exists())

    def test_tool_failure_preserves_raw_response(self):
        self.tool_failure = True
        with self.assertRaisesRegex(ValueError, "tool failed"):
            self.capture()
        self.assertTrue((self.output / "interpro/matches_000.raw").exists())
        self.assertFalse((self.output / "protein_context.json").exists())

    def test_http_error_preserves_raw_failure(self):
        self.http_failure = True
        with self.assertRaisesRegex(ValueError, "lookup failed"):
            self.capture()
        self.assertIn(b"upstream unavailable", (self.output / "interpro/matches_000.raw").read_bytes())

    def test_out_of_sequence_coordinates_fail_without_source_repair(self):
        self.bad_coordinate = True
        with self.assertRaisesRegex(ValueError, "beyond the exact source sequence"):
            self.capture()
        saved = json.loads((self.output / "interpro/matches_000.json").read_text())
        self.assertEqual(next(iter(parse_match_rpc(saved).values()))["matches"][0]["locations"][0]["end"], 41)

    def test_bad_requests_rejected_before_network_or_output(self):
        for ids in ([], ["P04637", "UniProtKB:P04637"], ["P04637-0"], ["../../P04637"], ["P04637"] * 101):
            with self.assertRaises(ValueError):
                capture_context(ids, self.output, runs_dir=self.runs, client=self.client(), http_transport=self.http)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.calls, [])

    def test_output_and_registration_do_not_overwrite_or_trust_changed_source(self):
        self.capture()
        with self.assertRaisesRegex(ValueError, "new ordinary"):
            self.capture()
        path = self.output / "interpro/matches_000.raw"
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "changed before registration"):
            register_context(self.output, self.runs)
        self.assertFalse((self.runs / "protein_context_index.json").exists())

    def test_native_result_missing_duplicate_unrequested_and_failed_rpc_rejected(self):
        md5 = hashlib.md5(SEQUENCE.encode()).hexdigest()
        row = {"md5": md5, "found": True, "matches": match_rows()}
        for value, expected in ((rpc([]), [md5]), (rpc([row, row]), [md5]),
                                (rpc([row]), ["0" * 32]), ({"jsonrpc": "2.0", "error": {}}, [md5])):
            with self.assertRaises(ValueError):
                parse_match_rpc(value, expected)
        value = rpc([row])
        value["result"].pop("isError")
        with self.assertRaisesRegex(ValueError, "isError=false"):
            parse_match_rpc(value)


if __name__ == "__main__":
    unittest.main()
