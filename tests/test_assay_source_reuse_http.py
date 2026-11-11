"""Authenticated, source-bound publication of supplemental evidence reuse."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import ZipFile

from biograph_steward.webapp import create_server
from test_assay_source_reuse import inventory, make_intact_workspace, make_trace


class AssaySourceReuseHttpTests(unittest.TestCase):
    def setUp(self):
        from biograph_steward.assay_source_reuse import publish_reuse_workspace
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source, self.graph = make_intact_workspace(self.root)
        self.source_before = inventory(self.source)
        self.trace = make_trace(self.root, self.source, self.graph)
        self.annotated = self.root / "annotated"
        self.report = publish_reuse_workspace(self.source, self.trace, self.annotated)
        self.server = create_server(0, self.root, access_token="synthetic-source-reuse-http-token")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, *, auth=True):
        headers = {"Authorization": "Bearer synthetic-source-reuse-http-token"} if auth else {}
        return build_opener(ProxyHandler({})).open(Request(self.url + path, headers=headers))

    def assert_http_error(self, statuses, path, *, auth=True):
        if isinstance(statuses, int):
            statuses = (statuses,)
        with self.assertRaises(HTTPError) as error:
            self.request(path, auth=auth)
        self.assertIn(error.exception.code, statuses)
        error.exception.close()

    def routes(self):
        root = "/api/assay-source-reuse/annotated"
        return [root, *(root + "/" + name for name in
                       ("report.html", "report.json", "records.jsonl")),
                "/api/download/annotated"]

    def test_supplement_metadata_and_artifacts_require_workspace_authentication(self):
        for route in self.routes():
            with self.subTest(route=route):
                self.assert_http_error(401, route, auth=False)
        self.assertEqual(inventory(self.source), self.source_before)

    def test_metadata_preserves_source_binding_and_keeps_historical_reuse_unknown(self):
        with self.request("/api/assay-source-reuse/annotated") as response:
            view = json.loads(response.read())
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(view["status"], "available")
        self.assertEqual(view["source_run"], "annotated")
        for key in ("snapshot_sha256", "assay_attachment_sha256", "assay_publication_sha256"):
            self.assertEqual(view[key], self.graph[key])
        rows = {row["observation_id"]: row for row in view["observations"]}
        expected = self.graph["assay_observations"]
        self.assertEqual(set(rows), {row["id"] for row in expected})
        self.assertEqual(rows[expected[0]["id"]]["current_string_status"], "confirmed_user_assisted")
        self.assertEqual(rows[expected[0]["id"]]["observation_provenance"], "user_assisted_source_link")
        self.assertTrue(all(row["historical_pharos_reuse"] is None for row in rows.values()))
        for observation in expected[1:]:
            self.assertEqual(rows[observation["id"]]["current_string_status"], "unknown_not_observed")
        with self.request("/api/run/annotated") as response:
            self.assertEqual(json.loads(response.read())["graph"], self.graph)
        self.assertEqual(inventory(self.source), self.source_before)

    def test_unannotated_workspace_has_no_inferred_flags_or_report_files(self):
        root = "/api/assay-source-reuse/" + self.source.name
        with self.request(root) as response:
            view = json.loads(response.read())
        self.assertEqual(view["status"], "unavailable")
        self.assertEqual(view["source_run"], self.source.name)
        self.assertFalse(view["observations"])
        for name in ("report.html", "report.json", "records.jsonl"):
            with self.subTest(name=name):
                self.assert_http_error((400, 404), root + "/" + name)
        self.assertEqual(inventory(self.source), self.source_before)

    def test_report_routes_serve_only_the_verified_corresponding_artifacts(self):
        for relative, filename in (("report.html", "source_reuse.html"),
                                   ("report.json", "source_reuse.json"),
                                   ("records.jsonl", "source_reuse_records.jsonl")):
            with self.subTest(relative=relative):
                with self.request("/api/assay-source-reuse/annotated/" + relative) as response:
                    self.assertEqual(response.read(), (self.annotated / filename).read_bytes())
                    self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        for relative in ("snapshot.json", "source_reuse_manifest.json", "../snapshot.json",
                         "%2e%2e/snapshot.json", "source_reuse_source/user_intact_record_link.json"):
            with self.subTest(relative=relative):
                self.assert_http_error((400, 404), "/api/assay-source-reuse/annotated/" + relative)

    def test_download_keeps_original_graph_and_all_supplement_provenance_bytes(self):
        annotated_before = inventory(self.annotated)
        with self.request("/api/download/annotated") as response:
            self.assertEqual(response.headers.get_content_type(), "application/zip")
            with ZipFile(BytesIO(response.read())) as archive:
                self.assertEqual(set(archive.namelist()), {"annotated/" + name for name in annotated_before})
                for name, raw in annotated_before.items():
                    self.assertEqual(archive.read("annotated/" + name), raw, name)
                self.assertEqual(json.loads(archive.read("annotated/graph.json")), self.graph)
                for name in ("source_reuse.json", "source_reuse_records.jsonl", "source_reuse.html",
                             "source_reuse_manifest.json", "source_reuse_source/trace_report.json",
                             "source_reuse_source/user_intact_record_link.json"):
                    self.assertIn("annotated/" + name, archive.namelist())
        self.assertEqual(inventory(self.annotated), annotated_before)
        self.assertEqual(inventory(self.source), self.source_before)

    def test_tampered_and_partial_supplements_block_every_route_and_download(self):
        for filename in ("source_reuse_records.jsonl", "source_reuse.json"):
            target = self.annotated / filename
            original = target.read_bytes()
            for mutation in ("tamper", "remove"):
                with self.subTest(filename=filename, mutation=mutation):
                    if mutation == "tamper":
                        target.write_bytes(original + b" ")
                    else:
                        target.unlink()
                    try:
                        for route in self.routes():
                            with self.subTest(route=route):
                                self.assert_http_error((400, 404), route)
                    finally:
                        target.write_bytes(original)

    def test_symlinked_runs_and_supplement_files_are_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.annotated, target_is_directory=True)
        for route in self.routes():
            with self.subTest(route=route):
                self.assert_http_error((400, 404), route.replace("annotated", "alias"))
        target = self.annotated / "source_reuse.json"
        original = target.read_bytes()
        elsewhere = self.root / "elsewhere.json"
        elsewhere.write_bytes(original)
        target.unlink()
        target.symlink_to(elsewhere)
        try:
            for route in self.routes():
                with self.subTest(route=route):
                    self.assert_http_error((400, 404), route)
        finally:
            target.unlink()
            target.write_bytes(original)

    def test_invalid_and_missing_run_ids_do_not_expose_any_supplement(self):
        for identifier in ("missing", "..", "%2e%2e", "x" * 81, "annotated/extra"):
            for suffix in ("", "/report.json"):
                with self.subTest(identifier=identifier, suffix=suffix):
                    self.assert_http_error((400, 404), "/api/assay-source-reuse/" + identifier + suffix)


if __name__ == "__main__":
    unittest.main()
