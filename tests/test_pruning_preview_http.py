"""Authenticated read-only preview routes use invented, fully bound artifacts."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward.pruning_preview import DOWNLOAD_FILES
from biograph_steward.webapp import create_server, report_html
from test_pruning_preview import make_preview


TOKEN = "invented-pruning-preview-http-token"
PREFIX = "/api/pruning-preview/assessment"


class PruningPreviewHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.preview = make_preview(self.root)
        # A separate workspace is deliberately not an assessment. None of these
        # read-only routes should load or rewrite its graph or review state.
        workspace = self.root / "current_workspace"
        workspace.mkdir()
        (workspace / "graph.json").write_text('{"invented_workspace":"unchanged"}\n')
        (workspace / "review_events.json").write_text("[]\n")
        self.before = self.files()
        self.server = create_server(0, self.root, access_token=TOKEN)
        self.server.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and not path.is_symlink()}

    def request(self, route, *, auth=True, body=None):
        headers = {"Authorization": "Bearer " + TOKEN} if auth else {}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers.update({"Content-Type": "application/json", "Origin": self.url})
        return self.opener.open(Request(self.url + route, data=data, headers=headers), timeout=10)

    def get_json(self, route, **kwargs):
        with self.request(route, **kwargs) as response:
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            return json.loads(response.read())

    def assert_http(self, status, route, **kwargs):
        with self.assertRaises(HTTPError) as raised:
            self.request(route, **kwargs)
        self.assertEqual(raised.exception.code, status)
        raised.exception.close()

    def test_authenticated_saved_assessment_does_not_load_or_mutate_workspace(self):
        with ExitStack() as stack:
            stack.enter_context(patch("biograph_steward.client.PharosClient.execute",
                                      side_effect=AssertionError("No source retrieval")))
            stack.enter_context(patch("biograph_steward.model_transport.JSONModelClient.generate",
                                      side_effect=AssertionError("No model call")))
            stack.enter_context(patch("biograph_steward.neptune.Mirror.inspect",
                                      side_effect=AssertionError("No Neptune call")))
            stack.enter_context(patch("biograph_steward.reviews.read_run",
                                      side_effect=AssertionError("No workspace replay")))
            listing = self.get_json("/api/pruning-previews")
            self.assertEqual([row["id"] for row in listing["previews"]], ["assessment"])
            summary = self.get_json(PREFIX)
            self.assertEqual(summary["default_arm"], "unpruned")
            self.assertEqual(summary["id"], "assessment")
            self.assertEqual(summary["scope"]["kind"], "frozen_retrospective_assessment")
            self.assertFalse(summary["scope"]["current_workspace_applied"])
            self.assertFalse(summary["provenance"]["independent_validation"])
            self.assertFalse(summary["provenance"]["full_source_replay_performed_by_viewer"])
            pairs = self.get_json(PREFIX + "/pairs")
            self.assertEqual(pairs["arm"], "unpruned")
            self.assertEqual(pairs["total"], 9)
            self.assertEqual(pairs["limit"], 25)
            for arm in ("native_top80", "ne_top80", "unpruned"):
                self.get_json(PREFIX + "/pairs?" + urlencode({"arm": arm, "limit": 1}))
        self.assertEqual(self.files(), self.before)

    def test_all_preview_resources_require_authentication(self):
        one = self.get_json(PREFIX + "/pairs")["rows"][0]
        for route in ("/api/pruning-previews", PREFIX, PREFIX + "/pairs",
                      PREFIX + "/pair/" + quote(one["pair_id"], safe=""),
                      PREFIX + "/files/summary.json"):
            with self.subTest(route=route):
                self.assert_http(401, route, auth=False)

    def test_empty_pair_query_bypasses_parser_and_nonempty_queries_stay_strict(self):
        # Strict empty-query behavior differs between supported Python versions.
        with patch("biograph_steward.webapp.parse_qs",
                   side_effect=AssertionError("Empty query must use default filters")) as parser:
            for suffix in ("", "?"):
                with self.subTest(suffix=suffix):
                    pairs = self.get_json(PREFIX + "/pairs" + suffix)
                    self.assertEqual((pairs["arm"], pairs["limit"]), ("unpruned", 25))
            parser.assert_not_called()
        with patch("biograph_steward.webapp.parse_qs", wraps=parse_qs) as parser:
            self.assertEqual(self.get_json(PREFIX + "/pairs?limit=1")["limit"], 1)
            parser.assert_called_once_with("limit=1", keep_blank_values=True,
                                           strict_parsing=True, errors="strict", max_num_fields=5)
            for query in ("search", "&"):
                with self.subTest(query=query):
                    self.assert_http(400, PREFIX + "/pairs?" + query)
            self.assertEqual([call.args[0] for call in parser.call_args_list],
                             ["limit=1", "search", "&"])
            self.assertTrue(all(call.kwargs["strict_parsing"] for call in parser.call_args_list))
        self.assertEqual(self.files(), self.before)

    def test_bounded_pages_exact_details_and_detection_removal_filter(self):
        first = self.get_json(PREFIX + "/pairs?limit=1&offset=0")
        second = self.get_json(PREFIX + "/pairs?limit=1&offset=1")
        self.assertEqual(first["total"], second["total"])
        self.assertEqual(len(first["rows"]), 1)
        self.assertNotEqual(first["rows"][0]["pair_id"], second["rows"][0]["pair_id"])
        removed = self.get_json(PREFIX + "/pairs?arm=native_top80&selection=detections_removed")
        self.assertEqual(removed["total"], 1)
        pair = removed["rows"][0]
        self.assertTrue(pair["assay"]["detected"])
        self.assertFalse(pair["arms"]["native_top80"]["retained"])
        self.assertTrue(pair["arms"]["ne_top80"]["retained"])
        detail = self.get_json(PREFIX + "/pair/" + quote(pair["pair_id"], safe=""))
        self.assertEqual(detail, pair)
        search = self.get_json(PREFIX + "/pairs?" + urlencode({"search": "GENE1"}))
        self.assertGreater(search["total"], 0)
        self.assertEqual(self.get_json(PREFIX + "/pairs?selection=removed")["total"], 0)
        self.assertEqual(self.get_json(PREFIX + "/pairs?arm=ne_top80&selection=detections_removed")["total"], 0)

    def test_excluded_unassessed_and_uncovered_states_are_not_false_or_pruned(self):
        excluded = self.get_json(PREFIX + "/pairs?selection=excluded")
        self.assertEqual(excluded["total"], 2)
        self.assertTrue(all(row["assay"]["detected"] is None
                            and row["assay"]["evaluable"] is False for row in excluded["rows"]))
        uncovered = self.get_json(PREFIX + "/pairs?arm=native_top80&selection=uncovered")
        self.assertEqual(uncovered["total"], 2)
        for row in uncovered["rows"]:
            self.assertFalse(row["graph_present"])
            self.assertEqual(row["edge_ids"], [])
            self.assertTrue(all(arm["retained"] is None and arm["decision"] == "abstain"
                                for arm in row["arms"].values()))
        unassessed = self.get_json(PREFIX + "/pairs?selection=unassessed")
        self.assertEqual(unassessed["total"], 3)
        self.assertTrue(all(row["assay"] is None and row["graph_present"]
                            for row in unassessed["rows"]))

    def test_downloads_are_allowlisted_and_preserve_published_bytes(self):
        summary = self.get_json(PREFIX)
        self.assertEqual(set(summary["downloads"]), set(DOWNLOAD_FILES))
        for name in sorted(DOWNLOAD_FILES):
            with self.subTest(name=name), self.request(summary["downloads"][name]) as response:
                self.assertEqual(response.read(), (self.preview / name).read_bytes())
                self.assertIn('attachment; filename="' + name + '"', response.headers["Content-Disposition"])
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        for name in ("snapshot.json", "pair_groups.json", "../manifest.json", "%2E%2E%2Fmanifest.json"):
            with self.subTest(name=name):
                self.assert_http(404, PREFIX + "/files/" + name)
        self.assertEqual(self.files(), self.before)

    def test_invalid_or_duplicate_queries_and_write_routes_are_rejected(self):
        invalid = ("arm=unknown", "selection=unknown", "write=true", "arm=unpruned&arm=ne_top80",
                   "search=a&search=b", "limit=0", "limit=101", "limit=-1", "limit=true",
                   "offset=-1", "offset=1.5", "offset=false", "offset=12345678901",
                   "search=%00", "search=%0A", "search=%1F", "search=%7F", "search=%FF",
                   "search=" + "x" * 201)
        for query in invalid:
            with self.subTest(query=query):
                self.assert_http(400, PREFIX + "/pairs?" + query)
        for route in ("/api/pruning-previews?limit=1", PREFIX + "?arm=unpruned",
                      PREFIX + "/files/metrics.json?arm=unpruned"):
            self.assert_http(400, route)
        for route in (PREFIX, PREFIX + "/apply", PREFIX + "/prune"):
            self.assert_http(404, route, body={})
        self.assert_http(404, PREFIX + "/pair/ppi%3A" + "0" * 24)
        self.assertEqual(self.files(), self.before)

    def test_changed_bytes_cannot_be_hidden_by_cached_values_or_restored_timestamp(self):
        self.get_json(PREFIX)
        path = self.preview / "summary.json"
        before = path.stat()
        raw = path.read_bytes()
        changed = raw.replace(b"Pharos", b"Xharos", 1)
        self.assertNotEqual(changed, raw)
        self.assertEqual(len(changed), len(raw))
        path.write_bytes(changed)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assert_http(400, PREFIX)
        self.assert_http(400, PREFIX + "/pairs")
        self.assert_http(400, PREFIX + "/files/summary.json")
        self.assertEqual(self.get_json("/api/pruning-previews")["previews"], [])

    def test_run_preparation_and_file_symlinks_are_withheld(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root / "assessment", target_is_directory=True)
        self.assert_http(404, "/api/pruning-preview/alias")
        self.assertEqual([r["id"] for r in self.get_json("/api/pruning-previews")["previews"]], ["assessment"])
        name = "metrics.json"
        original = self.preview / name
        copied = self.root / "copied_metrics.json"
        copied.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(copied)
        self.assert_http(400, PREFIX)
        self.assertEqual(self.get_json("/api/pruning-previews")["previews"], [])
        original.unlink()
        original.write_bytes(copied.read_bytes())
        outside = self.root / "moved_preview"
        self.preview.rename(outside)
        self.preview.symlink_to(outside, target_is_directory=True)
        self.assert_http(404, PREFIX)
        self.assertEqual(self.get_json("/api/pruning-previews")["previews"], [])

    def test_page_includes_preview_once_and_preserves_physical_priority_control(self):
        html = report_html()
        self.assertEqual(html.count('id="pruningPreviewPanel"'), 1)
        self.assertEqual(html.count('id="questionRanking"'), 1)
        self.assertIn("Physical association priority · STRING", html)
        self.assertIn("initializePruningPreview();", html)


if __name__ == "__main__":
    unittest.main()
