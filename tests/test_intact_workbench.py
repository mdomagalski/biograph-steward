"""Entirely invented IntAct publications exercise the ordinary workbench path.

Allowed development PMIDs are only filenames required by the bounded importer.
No real publication, reader artifact, source body, model or remote service is read.
"""
from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
from html import unescape
from io import BytesIO, StringIO
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import ZipFile

from biograph_steward.assay_attachment import attach_assay, load_publication, read_assay
from biograph_steward.assay_questions import answer_assay_question
from biograph_steward.client import canonical, digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import export_packet, load_packet, load_decisions, save_decisions
from biograph_steward.graph import save_run
from biograph_steward.intact_evidence import build_evidence
from biograph_steward.intact_publication import DEVELOPMENT, FORMAT, records_from_material
from biograph_steward.questions import answer_question, graph_basis, save_answer, verify_answer
from biograph_steward.reviews import read_run, review_run
from biograph_steward.standard_export import project_graph
from biograph_steward.webapp import create_server
from test_assay_attachment import cohort_snapshot, _inventory, _seal
from test_intact_evidence import fixture, identifier
from test_normalization import resign


def read(path):
    return json.loads(Path(path).read_text())


def jsonl(path, rows):
    Path(path).write_text("".join(canonical(row) + "\n" for row in rows))


def make_publication(folder, *, excluded=False):
    """Publish four invented eligible records, optionally one excluded record."""
    folder = Path(folder)
    (folder / "source").mkdir(parents=True)
    (folder / "reader").mkdir()
    records, ledger, catalog, studies = [], [], [], []
    source_hashes, reader_hashes = {}, {}
    for index, pmid in enumerate(sorted(DEVELOPMENT)):
        row = deepcopy(fixture()[0][0]["reader_record"])
        row["line_number"] = 1
        publications = row["source_fields"]["publication_ids"]
        publications["values"] = [identifier("pubmed", pmid), identifier("imex", "IM-SYNTHETIC-" + str(index))]
        publications["raw"] = "pubmed:" + pmid + "|imex:IM-SYNTHETIC-" + str(index)
        row["raw_cells"][8] = publications["raw"]
        evidence = row["source_fields"]["evidence_ids"]
        evidence["values"] = [identifier("intact", "EBI-SYNTHETIC-" + str(index)), identifier("imex", "IM-SYNTHETIC-" + str(index) + "-1")]
        evidence["raw"] = "intact:EBI-SYNTHETIC-" + str(index) + "|imex:IM-SYNTHETIC-" + str(index) + "-1"
        row["raw_cells"][13] = evidence["raw"]
        row["raw_cells"][35] = ["false", "true", "-", "false"][index]
        row["interaction"]["negative"] = row["raw_cells"][35] == "true"
        row["raw_line"] = "\t".join(row["raw_cells"])
        rows = [row]
        if excluded and index == 0:
            extra = deepcopy(row)
            extra["line_number"] = 2
            for name in ("taxa_a", "taxa_b"):
                field = extra["source_fields"][name]
                field.update(raw="taxid:10090(synthetic mouse)", values=[{"taxid": 10090, "common_name": "synthetic mouse"}])
                extra["raw_cells"][field["column"] - 1] = field["raw"]
            extra["raw_line"] = "\t".join(extra["raw_cells"])
            rows.append(extra)
        source_path, reader_path = folder / "source" / (pmid + ".txt"), folder / "reader" / (pmid + ".jsonl")
        source_path.write_text("".join(r["raw_line"] + "\n" for r in rows))
        jsonl(reader_path, rows)
        source_hashes[pmid], reader_hashes[pmid] = sha(source_path), sha(reader_path)
        catalog.append({"publication_id": "pubmed:" + pmid, "artifact_sha256": source_hashes[pmid],
                        "reader_sha256": reader_hashes[pmid], "source_file": "source/" + pmid + ".txt",
                        "reader_file": "reader/" + pmid + ".jsonl"})
        for number, record in enumerate(rows, 1):
            records.append({**{k: catalog[-1][k] for k in ("publication_id", "artifact_sha256", "source_file", "reader_file")},
                            "reader_record": record})
            ledger.append({"publication_id": "pubmed:" + pmid, "artifact_sha256": source_hashes[pmid],
                           "release": "2026-10-17", "source_line": number,
                           "raw_row_sha256": hashlib.sha256(record["raw_line"].encode()).hexdigest(),
                           "kind": "evidence", "eligible": number == 1,
                           "exclusion_reasons": [] if number == 1 else ["participant_taxonomy_not_only_explicit_human_a", "participant_taxonomy_not_only_explicit_human_b"]})
        studies.append({"publication_id": "pubmed:" + pmid, "source_sha256": source_hashes[pmid],
                        "physical_rows": len(rows), "counts": {"evidence": len(rows), "eligible": 1, "excluded_evidence": len(rows) - 1}})
    runtime = {"synthetic_fixture": "Invented runtime binding; Java was not executed."}
    controls = _seal({"format": "biograph-steward.intact-reader-controls-result.v1",
                      "status": "passed", "all_checks_passed": True, "synthetic_only": True,
                      "reference_rows_accessed": False, "runtime_bindings": runtime,
                      "note": "Invented transport fixture; not a real controls result."})
    write_json(folder / "controls_report.json", controls)
    write_json(folder / "inspection_report.json", {
        "status": "development_inspected_not_fidelity_scored", "synthetic_fixture": True,
        "bindings": {"controls_report_sha256": sha(folder / "controls_report.json"), "runtime_bindings": runtime},
        "studies": studies, "totals": {"physical_rows": len(records), "evidence": len(records), "eligible": 4,
                                        "excluded_evidence": len(records) - 4}})
    write_json(folder / "protocol.json", {"synthetic_fixture": "Invented protocol input."})
    write_json(folder / "semantic_amendment.json", {"synthetic_fixture": "Invented semantic amendment input."})
    jsonl(folder / "row_ledger.jsonl", ledger)
    bindings = {"protocol_sha256": sha(folder / "protocol.json"), "amendment_sha256": sha(folder / "semantic_amendment.json"),
                "result_sha256": sha(folder / "inspection_report.json"), "ledger_sha256": sha(folder / "row_ledger.jsonl"),
                "source_sha256": source_hashes, "reader_sha256": reader_hashes,
                "controls_report_sha256": sha(folder / "controls_report.json"), "reader_runtime": runtime}
    evidence = build_evidence(records, ledger, bindings)
    write_json(folder / "evidence.json", evidence)
    write_json(folder / "graph.json", evidence["graph"])
    (folder / "LICENSE.md").write_text("Invented test records only; no real publication data copied.\n")
    (folder / "index.html").write_text("<!doctype html><p>Invented test publication.</p>")
    manifest = _seal({"format": FORMAT, "created_at": "2026-10-26T00:00:00+00:00", "synthetic_fixture": True,
                      "source_catalog": catalog, "bindings": bindings, "summary": evidence["summary"],
                      "implementation_sha256": {"invented_fixture": "a" * 64}, "baseline_modified": False,
                      "automatic_pruning": False, "independent_validation_performed": False,
                      "standard_conformance_claimed": False, "files": _inventory(folder, "publication.json")})
    write_json(folder / "publication.json", manifest)
    return manifest


class IntactWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.publication, self.run = (self.root / name for name in ("cohort", "publication", "attached"))
        self.snapshot = cohort_snapshot()
        self.base = save_run(self.snapshot, self.source)
        self.manifest = make_publication(self.publication, excluded=True)

    def attach(self):
        return attach_assay(self.source, self.publication, self.run)

    def reseal_publication(self):
        manifest = read(self.publication / "publication.json")
        manifest["files"] = _inventory(self.publication, "publication.json")
        write_json(self.publication / "publication.json", _seal(manifest))

    def test_loader_attach_replay_preserve_sources_and_qualified_outcomes(self):
        manifest, evidence, files = load_publication(self.publication)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(len(evidence["row_ledger"]), 5)
        self.assertEqual(evidence["summary"]["excluded_evidence"], 1)
        graph = self.attach()
        self.assertEqual(read_run(self.run)[2], graph)
        self.assertEqual(graph["nodes"], self.base["nodes"])
        self.assertEqual([e for e in graph["edges"] if e["record_kind"] != "assay_observation"], self.base["edges"])
        self.assertEqual(len(graph["assay_observations"]), 4)
        self.assertEqual(Counter(r["assay_status"] for r in graph["assay_observations"]), {"curated_positive": 3, "curated_negative": 1})
        self.assertEqual(len({r["id"] for r in graph["assay_observations"]}), 4)
        self.assertEqual(len({tuple(r["products"]) for r in graph["assay_observations"]}), 1)
        for name, raw in files.items():
            self.assertEqual((self.run / "assay_source" / name).read_bytes(), raw)
        self.assertEqual(read_assay(self.run)["source_license"]["license_file"], "assay_source/LICENSE.md")
        self.assertIn("No Pharos match", graph["assay_evidence"]["lookup_note"])

    def test_dedicated_answer_save_dispatch_keeps_visible_context_and_full_export(self):
        graph = self.attach()
        answer = answer_assay_question(graph, "P04637", source_run=self.run.name)
        out = self.root / "answer"
        save_answer(answer, out)
        self.assertEqual(read(out / "question.json"), answer)
        verify_answer(answer)
        exported = [json.loads(line) for line in (out / "assay_evidence.jsonl").read_text().splitlines()]
        self.assertEqual(len(exported), 4)
        self.assertEqual([r["source_observation"] for r in exported], graph["assay_observations"])
        html, text = (out / "report.html").read_text(), (out / "summary.txt").read_text()
        self.assertEqual(html.count("data-field-group="), 32)
        for token in ("MINT", "Synthetic host 1", "Synthetic host 2", "MI:0006", "MI:0915", "prey", "bait",
                      "source-qualified negative", "MITAB27 '-' default", "binary experimental origin is unknown"):
            self.assertIn(token, unescape(html))
            self.assertIn(token, text)
        self.assertFalse((out / "paths.tsv").exists())
        generic = answer_question(graph, "P04637", view="candidates")
        self.assertFalse(any(c["kind"] == "assay_observation" for c in generic["citations"]))

    def test_review_changes_local_state_without_rewriting_source_and_invalidates_basis(self):
        graph = self.attach()
        before = answer_assay_question(graph)
        assertion = next(a for a in graph["assertions"] if a["kind"] == "assay_observation")
        reviewed = review_run(self.run, self.root / "reviewed", assertion["id"], "provisional", "Synthetic reviewer", "Fixture inspection only")
        self.assertEqual(reviewed["assay_observations"], graph["assay_observations"])
        after = answer_assay_question(reviewed)
        changed = next(r for r in after["results"] if r["assertion_id"] == assertion["id"])
        self.assertEqual(changed["local_review_state"], "provisional")
        self.assertEqual(changed["source_observation"]["local_review_state"], "candidate")
        self.assertNotEqual(before["graph_basis_sha256"], after["graph_basis_sha256"])
        self.assertEqual(after["graph_basis_sha256"], graph_basis(reviewed))
        self.assertEqual(read_run(self.run)[2], graph)

    def test_packet_is_complete_offline_and_pins_intact_projection(self):
        from biograph_steward import intact_evidence, intact_publication
        graph = self.attach()
        packet = self.root / "packet"
        manifest = export_packet(self.run, packet)
        self.assertEqual(manifest["implementation_sha256"]["assay_observation_projection"], sha(intact_evidence.__file__))
        self.assertEqual(manifest["implementation_sha256"]["intact_publication"], sha(intact_publication.__file__))
        self.assertEqual(load_packet(packet)[1], graph)
        for item in self.manifest["files"]:
            self.assertEqual((packet / "source/assay_source" / item).read_bytes(), (self.publication / item).read_bytes())
        self.assertTrue(all(d["decision"] == "abstain" for d in read(packet / "decisions.template.json")["decisions"]))
        for folder in (self.source, self.publication, self.run):
            shutil.rmtree(folder)
        with patch("biograph_steward.client.PharosClient.execute", side_effect=AssertionError("No network")):
            self.assertEqual(load_packet(packet)[1], graph)
        with self.assertRaisesRegex(ValueError, "outside this KGX profile"):
            project_graph(graph)

    def test_changed_source_is_rejected_even_when_publication_inventory_is_resealed(self):
        source = self.publication / self.manifest["source_catalog"][0]["source_file"]
        source.write_bytes(source.read_bytes() + b"INVENTED CHANGED ROW\n")
        self.reseal_publication()
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            load_publication(self.publication)

    def test_controls_integrity_status_and_runtime_binding_fail_closed(self):
        original = (self.publication / "controls_report.json").read_bytes()
        for field, value, reseal in [("status", "failed", True), ("runtime_bindings", {"other": "runtime"}, True),
                                    ("synthetic_only", False, True), ("reference_rows_accessed", True, True),
                                    ("all_checks_passed", False, False)]:
            controls = json.loads(original)
            controls[field] = value
            write_json(self.publication / "controls_report.json", _seal(controls) if reseal else controls)
            controls_sha = sha(self.publication / "controls_report.json")
            inspection = read(self.publication / "inspection_report.json")
            inspection["bindings"]["controls_report_sha256"] = controls_sha
            write_json(self.publication / "inspection_report.json", inspection)
            manifest = read(self.publication / "publication.json")
            manifest["bindings"]["controls_report_sha256"] = controls_sha
            manifest["bindings"]["result_sha256"] = sha(self.publication / "inspection_report.json")
            write_json(self.publication / "publication.json", manifest)
            self.reseal_publication()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "reader controls"):
                with patch("biograph_steward.intact_publication.records_from_material",
                           side_effect=AssertionError("Bad controls must stop before source decoding")):
                    load_publication(self.publication)

    def test_packet_review_keeps_source_records_and_review_bindings(self):
        graph = self.attach()
        assertion = next(a for a in graph["assertions"] if a["kind"] == "assay_observation")
        reviewed = self.root / "reviewed"
        reviewed_graph = review_run(self.run, reviewed, assertion["id"], "provisional",
                                    "Synthetic reviewer", "Source-fidelity inspection only")
        packet, decisions, output = (self.root / name for name in ("packet", "decisions.json", "retained"))
        export_packet(reviewed, packet)
        self.assertEqual(load_packet(packet)[1], reviewed_graph)
        event = reviewed_graph["review_events"][-1]
        self.assertEqual(event["assay_publication_sha256"], graph["assay_publication_sha256"])
        self.assertEqual(event["assay_attachment_sha256"], graph["assay_attachment_sha256"])
        bundle = read(packet / "decisions.template.json")
        bundle.update(actor="Synthetic test reviewer", method="Test exclusion; no biological judgment")
        edge_id = next(e["id"] for e in graph["edges"] if e["record_kind"] == "assay_observation")
        next(d for d in bundle["decisions"] if d["edge_id"] == edge_id).update(
            decision="prune", reason="Synthetic transport test only")
        write_json(decisions, bundle)
        save_decisions(packet, decisions, output)
        report, retained = load_decisions(output)
        self.assertNotIn(edge_id, {e["id"] for e in retained["edges"]})
        self.assertEqual(len(retained["assay_observations"]), 4)
        self.assertEqual(load_packet(output / report["baseline_packet"])[1], reviewed_graph)
        retained_row = next(o for o in retained["assay_observations"]
                            if o["retention"]["baseline_graph_edge_id"] == edge_id)
        original = next(o for o in graph["assay_observations"] if o["graph_edge_id"] == edge_id)
        self.assertEqual(retained_row["reader_record"], original["reader_record"])
        self.assertEqual(retained_row["qualifications"], original["qualifications"])
        self.assertIsNone(retained_row["graph_edge_id"])

    def test_omitted_or_reserved_catalog_fails_before_any_source_decoding(self):
        class MustNotDecode(bytes):
            def decode(self, *args, **kwargs):
                raise AssertionError("Ineligible catalog must be rejected before decoding")
        catalog, bindings = deepcopy(self.manifest["source_catalog"]), deepcopy(self.manifest["bindings"])
        files = {entry["source_file"]: MustNotDecode(b"not decoded") for entry in catalog}
        with self.assertRaisesRegex(ValueError, "all four development"):
            records_from_material(files, catalog[:-1], bindings)
        catalog[0]["publication_id"] = "pubmed:39833857"
        with self.assertRaisesRegex(ValueError, "all four development"):
            records_from_material(files, catalog, bindings)

    def test_resealed_sidecar_or_missing_source_cannot_change_observation_meaning(self):
        self.attach()
        sidecar = self.run / "assay_attachment.json"
        saved = sidecar.read_bytes()
        changed = json.loads(saved)
        changed["observations"][0]["qualifications"]["negative"]["value"] = True
        write_json(sidecar, _seal(changed))
        with self.assertRaises(ValueError):
            read_run(self.run)
        sidecar.write_bytes(saved)
        (self.run / "assay_source/LICENSE.md").unlink()
        with self.assertRaises(ValueError):
            export_packet(self.run, self.root / "invalid_packet")

    def test_empty_cohort_match_retains_publication_and_returns_honest_zero_answer(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["targets"] = [r for r in snapshot["targets"] if r["uniprot"] == "P00533"]
        snapshot["scope"]["requested_uniprot"] = ["P00533"]
        snapshot["scope"]["resolutions"] = [{"requested_uniprot": "P00533", "returned_uniprot": "P00533", "status": "resolved"}]
        save_run(resign(snapshot), self.root / "one_protein")
        graph = attach_assay(self.root / "one_protein", self.publication, self.run)
        answer = answer_assay_question(graph)
        self.assertEqual(answer["results"], [])
        self.assertEqual(graph["assay_evidence"]["outside_cohort_observations"], 4)
        self.assertEqual(graph["assay_evidence"]["source_accounting"]["excluded_evidence"], 1)
        manifest = export_packet(self.run, self.root / "empty_packet")
        self.assertEqual(manifest["counts"]["assay_observations"], 0)

    def test_cli_uses_saved_sources_and_qualified_answer_dispatch(self):
        from biograph_steward.__main__ import main
        self.attach()
        out = self.root / "cli_answer"
        with redirect_stdout(StringIO()), patch("biograph_steward.client.PharosClient.execute", side_effect=AssertionError("No network")):
            result = main(["assay-question", "--run", str(self.run), "--protein", "P04637", "--out", str(out)])
        self.assertEqual(result, 0)
        self.assertEqual(read(out / "question.json")["template"], "qualified_assay_evidence.v1")
        self.assertTrue((out / "assay_evidence.jsonl").is_file())


class IntactWorkbenchHttpTests(unittest.TestCase):
    token = "synthetic-intact-http-test-token"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        save_run(cohort_snapshot(), self.root / "cohort")
        self.manifest = make_publication(self.root / "publication")
        self.server = create_server(0, self.root, access_token=self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, body=None, *, auth=True):
        headers = {"Authorization": "Bearer " + self.token} if auth else {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        return build_opener(ProxyHandler({})).open(Request(self.url + path, headers=headers,
            data=json.dumps(body).encode() if body is not None else None))

    def error(self, code, path, body=None, **kwargs):
        with self.assertRaises(HTTPError) as result:
            with self.request(path, body, **kwargs) as response:
                response.read()
        self.assertEqual(result.exception.code, code)
        result.exception.close()

    def attach(self):
        with self.request("/api/assay-attach", {"run_id": "cohort", "publication_id": "publication"}) as response:
            return json.loads(response.read())["run_id"]

    def test_attach_answer_reopen_download_and_source_links_work(self):
        with self.request("/api/assay-publications") as response:
            self.assertIn("publication", [r["publication_id"] for r in json.loads(response.read())["publications"]])
        run_id = self.attach()
        with self.request("/api/assay-question", {"run_id": run_id}) as response:
            result = json.loads(response.read())
        self.assertEqual(len(result["answer"]["results"]), 4)
        with self.request("/api/question/" + result["question_id"]) as response:
            self.assertEqual(json.loads(response.read())["answer"], result["answer"])
        with self.request("/api/download/" + result["question_id"]) as response:
            with ZipFile(BytesIO(response.read())) as archive:
                prefix = result["question_id"] + "/"
                self.assertIn(prefix + "assay_evidence.jsonl", archive.namelist())
                self.assertEqual(archive.read(prefix + "report.html").count(b"data-field-group="), 32)
        relative = self.manifest["source_catalog"][0]["source_file"]
        with self.request("/api/assay-source/" + run_id + "/" + relative) as response:
            self.assertEqual(response.headers.get_content_type(), "text/plain")
            self.assertEqual(response.read(), (self.root / "publication" / relative).read_bytes())

    def test_auth_invalid_inputs_and_traversal_fail_before_question_creation(self):
        run_id = self.attach()
        valid = {"run_id": run_id}
        self.error(401, "/api/assay-question", valid, auth=False)
        for body in [{}, {"run_id": "../cohort"}, {**valid, "protein": "TP53"}, {**valid, "unexpected": True}]:
            self.error(400, "/api/assay-question", body)
        self.assertFalse(any(p.name.startswith("assay_question_") for p in self.root.iterdir()))
        self.error(400, "/api/assay-source/" + run_id + "/../snapshot.json")

    def test_source_tamper_prevents_answer_and_saved_question_reopening(self):
        run_id = self.attach()
        with self.request("/api/assay-question", {"run_id": run_id}) as response:
            result = json.loads(response.read())
        source = self.root / run_id / "assay_source" / self.manifest["source_catalog"][0]["source_file"]
        source.write_bytes(source.read_bytes() + b"changed")
        self.error(400, "/api/assay-question", {"run_id": run_id})
        self.error(400, "/api/question/" + result["question_id"])
        self.error(400, "/api/download/" + result["question_id"])

    def test_resealed_answer_cannot_change_source_path_or_graph_bindings(self):
        run_id = self.attach()
        with self.request("/api/assay-question", {"run_id": run_id}) as response:
            result = json.loads(response.read())
        (self.root / "source_alias").symlink_to(self.root / run_id, target_is_directory=True)
        answer_path = self.root / result["question_id"] / "question.json"
        for field, value in [("source_run", "../outside"), ("source_run", "missing_run"),
                             ("source_run", "source_alias"), ("graph_basis_sha256", "0" * 64),
                             ("snapshot_sha256", "0" * 64), ("assay_publication_sha256", "0" * 64),
                             ("assay_attachment_sha256", "0" * 64)]:
            answer = deepcopy(result["answer"])
            answer[field] = value
            answer.pop("answer_sha256")
            answer["answer_sha256"] = digest(answer)
            verify_answer(answer)
            write_json(answer_path, answer)
            with self.subTest(field=field, value=value):
                self.error(400, "/api/question/" + result["question_id"])
                self.error(400, "/api/download/" + result["question_id"])


if __name__ == "__main__":
    unittest.main()
