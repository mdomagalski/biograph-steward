"""Invented source fixtures exercise attachment, source integrity and review."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from biograph_steward.assay_attachment import (attach_assay, load_publication, prepare_attachment,
                                             read_assay, PUBLICATION_FORMAT)
from biograph_steward.assertions import new_review_event
from biograph_steward.client import digest, write_json
from biograph_steward.graph import build_graph, save_run
from biograph_steward.gold_packet import export_packet
from biograph_steward.lambourne_evidence import build_evidence
from biograph_steward.questions import answer_question, graph_basis
from biograph_steward.reviews import read_run, review_run
from test_cohort_graph import fixture as base_cohort
from test_lambourne_evidence import fixture as observation_fixture
from test_normalization import resign


def cohort_snapshot():
    snapshot = base_cohort()
    ids = ["P04637", "P00533", "P01111", "P01112", "P01116", "P04626"]
    originals = {row["uniprot"]: row for row in snapshot["targets"]}
    snapshot["targets"] = [deepcopy(originals.get(uid, {
        "uniprot": uid, "sym": "INVENTED_" + uid, "name": "Invented test protein " + uid,
        "tdl": "Tbio", "fam": "TEST", "pathways": []})) for uid in ids]
    snapshot["scope"]["requested_uniprot"] = ids
    snapshot["scope"]["resolutions"] = [{"requested_uniprot": uid, "returned_uniprot": uid,
                                           "status": "resolved"} for uid in ids]
    return resign(snapshot)


def _seal(value):
    value["content_sha256"] = digest({k: v for k, v in value.items() if k != "content_sha256"})
    return value


def _inventory(folder, receipt):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and p.relative_to(folder).as_posix() != receipt}


def make_publication(folder):
    """Make an entirely invented source bundle; never claims scientific replay."""
    folder = Path(folder)
    freeze, results = folder / "source/freeze", folder / "source/results"
    (freeze / "source").mkdir(parents=True)
    results.mkdir(parents=True)
    rows, lookups, _ = observation_fixture()
    write_json(freeze / "lookup/pair_lookup.json", lookups)
    hashes = {}
    for key, name in (("panel", "panel.tsv"), ("raw", "raw_human.tsv"), ("orf_map", "orf_map.tsv")):
        path = freeze / "source" / name
        path.write_text("INVENTED TEST DATA " + key + "\n")
        hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    (freeze / "source/LICENSE").write_text("Invented test licensing material.\n")
    protocol = _seal({"format": "biograph-steward.lambourne-corroboration-freeze.v1",
                      "files": _inventory(freeze, "protocol.json")})
    write_json(freeze / "protocol.json", protocol)
    write_json(results / "rows.json", rows)
    write_json(results / "assay_audit.json", {"source_sha256": hashes})
    report = _seal({"format": "biograph-steward.lambourne-corroboration-result.v1",
                    "protocol_sha256": protocol["content_sha256"],
                    "files": _inventory(results, "report.json")})
    write_json(results / "report.json", report)
    bindings = {"protocol_sha256": protocol["content_sha256"], "result_sha256": report["content_sha256"],
                "source_sha256": hashes, "artifact_sha256": {"rows": report["files"]["rows.json"],
                    "lookup": protocol["files"]["lookup/pair_lookup.json"]}}
    evidence = build_evidence(rows, lookups, bindings)
    write_json(folder / "evidence.json", evidence)
    write_json(folder / "graph.json", evidence["graph"])
    (folder / "index.html").write_text("<!doctype html><p>Invented assay publication</p>")
    manifest = _seal({"format": PUBLICATION_FORMAT, "created_at": "2026-10-26T00:00:00+00:00",
        "bindings": bindings, "summary": evidence["summary"],
        "implementation_sha256": {"invented_fixture": "a" * 64},
        "baseline_modified": False, "automatic_pruning": False,
        "independent_validation_performed": False, "standard_conformance_claimed": False,
        "files": _inventory(folder, "publication.json")})
    write_json(folder / "publication.json", manifest)
    return manifest


class AssayAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.publication, self.output = [self.root / n for n in ("cohort", "publication", "attached")]
        self.snapshot = cohort_snapshot()
        self.base = save_run(self.snapshot, self.source)
        self.manifest = make_publication(self.publication)

    def attach(self):
        return attach_assay(self.source, self.publication, self.output)

    def test_preserves_source_graph_and_complete_selected_observations(self):
        graph = self.attach()
        self.assertEqual(graph["assay_evidence"]["selected_observations"], 4)
        self.assertEqual(graph["assay_evidence"]["eligible_observations"], 3)
        self.assertEqual(graph["assay_evidence"]["excluded_observations"], 1)
        self.assertEqual(graph["nodes"], self.base["nodes"])
        self.assertEqual([e for e in graph["edges"] if e["record_kind"] != "assay_observation"], self.base["edges"])
        self.assertEqual([a for a in graph["assertions"] if a["kind"] != "assay_observation"], self.base["assertions"])
        self.assertEqual(read_run(self.source)[2], self.base)
        for assertion in graph["assertions"]:
            if assertion["kind"] == "assay_observation":
                self.assertEqual(assertion["data_kind"], "published_assay_observations")
                self.assertEqual(assertion["lifecycle_state"], "candidate")
                self.assertFalse(assertion["biologically_validated"])
        excluded = next(o for o in graph["assay_observations"] if not o["evaluable"])
        self.assertIsNone(excluded["graph_edge_id"])
        self.assertEqual(read_run(self.output)[2], graph)

    def test_both_endpoints_must_resolve_inside_declared_cohort(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["targets"] = [r for r in snapshot["targets"] if r["uniprot"] != "P00533"]
        for row in snapshot["scope"]["resolutions"]:
            if row["requested_uniprot"] == "P00533":
                row.update(status="not_found", returned_uniprot=None)
        source = self.root / "unresolved"
        base = save_run(resign(snapshot), source)
        graph = attach_assay(source, self.publication, self.output)
        self.assertEqual(graph["assay_evidence"]["selected_observations"], 3)
        self.assertEqual(graph["assay_evidence"]["outside_cohort_observations"], 1)
        self.assertEqual(graph["nodes"], base["nodes"])
        self.assertFalse(any("UniProtKB:P00533" in o["products"] for o in graph["assay_observations"]))

    def test_full_source_publication_is_portable_and_byte_identical(self):
        originals = {p.relative_to(self.publication).as_posix(): p.read_bytes()
                     for p in self.publication.rglob("*") if p.is_file()}
        graph = self.attach()
        for name, raw in originals.items():
            self.assertEqual((self.output / "assay_source" / name).read_bytes(), raw)
        shutil.rmtree(self.source)
        shutil.rmtree(self.publication)
        self.assertEqual(read_run(self.output)[2], graph)

    def test_assay_review_preserves_sources_and_binds_publication_and_selection(self):
        graph = self.attach()
        assertion = next(a for a in graph["assertions"] if a["kind"] == "assay_observation")
        reviewed_dir = self.root / "reviewed"
        reviewed = review_run(self.output, reviewed_dir, assertion["id"], "provisional", "Test reviewer", "Check exact assay context")
        event = reviewed["review_events"][-1]
        self.assertEqual(event["assay_publication_sha256"], graph["assay_publication_sha256"])
        self.assertEqual(event["assay_attachment_sha256"], graph["assay_attachment_sha256"])
        self.assertEqual(read_run(reviewed_dir)[2], reviewed)
        sidecar = read_assay(self.output)
        changed = deepcopy(event)
        changed["assay_attachment_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "different assay"):
            build_graph(self.snapshot, [changed], assay_attachment=sidecar)

    def test_existing_pharos_review_survives_attachment(self):
        assertion = self.base["assertions"][0]
        reviewed_dir = self.root / "baseline_review"
        reviewed = review_run(self.source, reviewed_dir, assertion["id"], "provisional", "Test", "Source inspection")
        graph = attach_assay(reviewed_dir, self.publication, self.output)
        actual = next(a for a in graph["assertions"] if a["id"] == assertion["id"])
        expected = next(a for a in reviewed["assertions"] if a["id"] == assertion["id"])
        self.assertEqual(actual, expected)

    def test_neighborhood_does_not_convert_observations_into_interaction_paths(self):
        graph = self.attach()
        before = answer_question(self.base, "P04637", view="candidates")
        after = answer_question(graph, "P04637", view="candidates")
        self.assertEqual(before["results"], after["results"])
        self.assertNotEqual(graph_basis(self.base), graph_basis(graph))
        self.assertFalse(any(a["kind"] == "assay_observation" for a in after.get("assertions", [])))

    def test_tampered_original_source_blocks_intake(self):
        with (self.publication / "source/freeze/source/panel.tsv").open("a") as handle:
            handle.write("tampered\n")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            self.attach()
        self.assertFalse(self.output.exists())

    def test_tampered_sidecar_blocks_reopen(self):
        self.attach()
        sidecar = read_assay(self.output)
        sidecar["observations"][0]["assay_status"] = "not_detected"
        write_json(self.output / "assay_attachment.json", _seal(sidecar))
        with self.assertRaisesRegex(ValueError, "differs"):
            read_run(self.output)

    def test_observation_ledger_tampering_cannot_enter_run_export(self):
        self.attach()
        write_json(self.output / 'assay_observations.json', [])
        with self.assertRaisesRegex(ValueError, 'observation ledger'):
            read_run(self.output)

    def test_source_license_tampering_cannot_enter_run_export(self):
        self.attach()
        write_json(self.output / 'source_licenses.json', [])
        with self.assertRaisesRegex(ValueError, 'source licenses'):
            read_run(self.output)

    def test_graph_assay_marker_prevents_missing_manifest_source_bypass(self):
        self.attach()
        (self.output / 'assay_attachment.json').unlink()
        shutil.rmtree(self.output / 'assay_source')
        write_json(self.output / 'run_manifest.json', {'run_mode': 'replay'})
        with self.assertRaisesRegex(ValueError, 'missing its recorded assay'):
            read_run(self.output)

    def test_missing_sidecar_never_silently_drops_attachment(self):
        self.attach()
        (self.output / "assay_attachment.json").unlink()
        shutil.rmtree(self.output / "assay_source")
        with self.assertRaisesRegex(ValueError, "missing its recorded assay"):
            read_run(self.output)

    def test_source_symlink_rejected(self):
        path = self.publication / "index.html"
        path.unlink()
        path.symlink_to(self.publication / "graph.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.attach()

    def test_rejects_disease_and_synthetic_cohorts(self):
        from biograph_steward.demo import demo_snapshot
        from test_normalization import fixture
        for index, snapshot in enumerate((fixture(), resign({**self.snapshot, "data_kind": "synthetic_demo"}))):
            source = self.root / ("unsupported" + str(index))
            save_run(snapshot, source)
            with self.assertRaisesRegex(ValueError, "explicit live Pharos cohort"):
                attach_assay(source, self.publication, self.output)

    def test_refresh_and_gold_export_explicitly_reject_assay_run(self):
        from biograph_steward.refresh import compare_runs
        self.attach()
        with self.assertRaisesRegex(ValueError, "Assay"):
            export_packet(self.output, self.root / "packet")
        with self.assertRaisesRegex(ValueError, "Assay"):
            compare_runs(self.source, self.output)
        self.assertFalse((self.root / "packet").exists())

    def test_existing_output_and_reattachment_rejected(self):
        self.attach()
        with self.assertRaisesRegex(ValueError, "new immutable"):
            self.attach()
        with self.assertRaisesRegex(ValueError, "already has"):
            attach_assay(self.output, self.publication, self.root / "twice")


if __name__ == "__main__":
    unittest.main()
