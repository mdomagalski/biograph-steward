"""Invented records verify source-qualified reuse annotations, not biology."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from biograph_steward.assay_attachment import attach_assay
from biograph_steward.client import digest
from biograph_steward.graph import save_run
from biograph_steward.intact_final_publication import publish_material
from test_assay_attachment import cohort_snapshot
from test_intact_final_publication import material
from test_intact_evidence import identifier


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sealed(value):
    return {**value, "content_sha256": digest(value)}


def inventory(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in folder.rglob("*") if p.is_file()}


def make_intact_workspace(root, *, typed_identity=True):
    """Use the real publication/attachment pipeline with entirely invented rows."""
    files, catalog, bindings, inspection, records, ledger = material("development_replay")
    for index, (entry, wrapper, account) in enumerate(zip(catalog, records, ledger)):
        row = wrapper["reader_record"]
        intact_id, imex_id = "EBI-" + str(100 + index), "IM-100-" + str(index + 1)
        evidence = row["source_fields"]["evidence_ids"]
        evidence.update(raw="intact:" + intact_id + "|imex:" + imex_id,
                        values=[identifier("intact", intact_id), identifier("imex", imex_id)])
        row["raw_cells"][13] = evidence["raw"]
        row["raw_line"] = "\t".join(row["raw_cells"])
        source_name, reader_name = entry["source_file"], entry["reader_file"]
        files[source_name] = (row["raw_line"] + "\n").encode()
        files[reader_name] = (json.dumps(row) + "\n").encode()
        pmid = entry["publication_id"].split(":", 1)[1]
        source_sha = sha(files[source_name])
        entry.update(artifact_sha256=source_sha, reader_sha256=sha(files[reader_name]))
        bindings["source_sha256"][pmid] = source_sha
        bindings["reader_sha256"][pmid] = entry["reader_sha256"]
        account.update(artifact_sha256=source_sha, raw_row_sha256=sha(row["raw_line"].encode()))
        wrapper["artifact_sha256"] = source_sha
        xml = {"format": "biograph-steward.intact-xml-evidence.v1", "record_kind": "evidence",
               "source_locator": {"line": 20 + index, "column": 3},
               "evidence": {"source_locator": {"line": 20 + index, "column": 3},
                            "identifiers": [identifier("intact", intact_id)],
                            "xrefs": [{"database": {"name": "imex"}, "id": imex_id,
                                       "qualifier": {"mi_id": "MI:0662"}}],
                            "experiments": [{"xml_id": index + 1,
                                "source_locator": {"line": 10 + index, "column": 3},
                                "xrefs": [identifier("intact", "EBI-" + str(200 + index))],
                                "publication": {"identifiers": [{"database": {"name": "pubmed"},
                                    "id": pmid, "qualifier": {"mi_id": "MI:0358",
                                                               "name": "primary-reference"}}],
                                    "xrefs": [], "pubmed_id": pmid},
                                "detection_method": {"mi_id": "MI:0006",
                                    "name": "anti bait coimmunoprecipitation",
                                    "full_name": "anti bait coimmunoprecipitation"}}]}}
        if not typed_identity:
            for ref in xml["evidence"]["identifiers"] + xml["evidence"]["xrefs"]:
                ref["qualifier"]["mi_id"] = "MI:0361"
        files["provenance/" + pmid + "_reader.jsonl"] = (json.dumps(xml) + "\n").encode()
    files["row_ledger.jsonl"] = b"".join((json.dumps(row) + "\n").encode() for row in ledger)
    bindings["ledger_sha256"] = sha(files["row_ledger.jsonl"])
    publication, cohort, attached = (root / name for name in ("publication", "cohort", "attached"))
    publish_material(files, catalog, bindings, inspection, publication)
    save_run(cohort_snapshot(), cohort)
    graph = attach_assay(cohort, publication, attached)
    return attached, graph


def make_trace(root, source, graph):
    """Minimal invented instance of the existing bounded provider trace format."""
    preparation, trace = root / "preparation", root / "trace"
    preparation.mkdir(); trace.mkdir()
    observations = graph["assay_observations"]
    rows = [{"id": row["id"], "products": row["products"], "study": row["study"],
             "record_ids": ["imex:IM-100-" + str(index + 1), "intact:EBI-" + str(100 + index)],
             "experiment_ids": ["intact:EBI-" + str(200 + index)],
             "current_string_curated_record_reuse": ("confirmed_user_assisted" if index == 0
                                                       else "unknown_not_observed"),
             "original_pharos_import_reuse": None}
            for index, row in enumerate(observations)]
    pmid = observations[0]["study"].split(":", 1)[1]
    reader = source / "assay_source/provenance" / (pmid + "_reader.jsonl")
    user = {"recorded_at": "2026-10-27T12:00:00+00:00",
            "observation_provenance": "Invented user-copied STRING source link for testing.",
            "as_supplied": "ebi.ac.uk/intact/query/IM-100-1",
            "source_namespace": "imex", "source_record_id": "IM-100-1",
            "source_record_curie": "imex:IM-100-1", "pair_display_labels": ["Invented A", "Invented B"],
            "method_label": "anti bait coimmunoprecipitation", "method_mi_id_from_existing_source": "MI:0006",
            "automated_string_api_exposes_this_record_link": False}
    scope = {"format": "biograph-steward.provider-pair-lineage-scope.v1",
             "created_at": "2026-10-27T12:00:00+00:00",
             "pair": [p.split(":", 1)[1] for p in observations[0]["products"]], "taxon": 9606,
             "existing_study": "PMID:" + pmid,
             "input_directories": {"original_workspace": str(source)},
             "input_files_sha256": {"original_workspace": {name: sha(raw)
                                     for name, raw in inventory(source).items()}}}
    (preparation / "scope.json").write_bytes(encode(scope))
    (preparation / "user_intact_record_link.json").write_bytes(encode(user))
    proof = {"status": "confirmed_user_assisted_exact_curated_record",
             "source_record_id": "imex:IM-100-1", "identity_aliases": rows[0]["record_ids"],
             "observation_id": observations[0]["id"], "publication": "PMID:" + pmid,
             "source_experiment_ids": rows[0]["experiment_ids"],
             "source_experiment_identity_exposed_by_string_api": False,
             "string_link_provenance": user,
             "official_source_reader": {"file": str(reader), "sha256": sha(reader.read_bytes()),
                                        "line": 1, "source_xml_locator": {"line": 20, "column": 3}},
             "independent_additional_record_over_current_string": False,
             "historical_pharos_record_inclusion_verified": False}
    report = sealed({"format": "biograph-steward.bounded-provider-pair-lineage.v1",
        "scope": {"pair": scope["pair"], "taxon": 9606, "existing_intact_study": "PMID:" + pmid,
                  "assessment": "Invented consumed development case only"},
        "string": {"source_release": "12.5", "exact_intact_record_reuse_proof": proof,
                   "exact_reactome_record_identity_reuse": None,
                   "api_supporting_record_ids_exposed": False,
                   "actual_consumed_intact_record_reuse": True,
                   "actual_consumed_intact_experiment_reuse": None},
        "original_overlap": {"observations": rows},
        "historical_pharos": {"source_release_label": "pharos319", "provider_import_release": None,
                              "current_provider_records_attested_as_original_inputs": False},
        "verified_independent_evidence_count": None, "original_graph_modified": False,
        "scientific_accuracy_measured": False, "predictive_gain_measured": False,
        "fresh_study_bodies_opened": 0, "model_calls": 0, "gpu_calls": 0,
        "input_directories": {"preparation": str(preparation)},
        "input_files_sha256": {"preparation": {name: sha(raw)
                                                for name, raw in inventory(preparation).items()}},
        "limitations": ["Invented software fixture, no biological inference."]})
    (trace / "report.json").write_bytes(encode(report))
    (trace / "record_reuse.jsonl").write_bytes(b"".join((json.dumps(row) + "\n").encode() for row in rows))
    (trace / "manifest.json").write_bytes(encode(sealed({"format": report["format"],
        "files": {name: sha(raw) for name, raw in inventory(trace).items()}})))
    return trace


def reseal_trace(trace, edit_report=None, edit_scope=None, edit_user=None, edit_rows=None):
    """Make semantically changed, internally hash-consistent adversarial inputs."""
    report = json.loads((trace / "report.json").read_text())
    preparation = Path(report["input_directories"]["preparation"])
    for name, edit in (("scope.json", edit_scope), ("user_intact_record_link.json", edit_user)):
        if edit:
            value = json.loads((preparation / name).read_text()); edit(value)
            (preparation / name).write_bytes(encode(value))
    if edit_rows:
        rows = [json.loads(line) for line in (trace / "record_reuse.jsonl").read_text().splitlines()]
        edit_rows(rows)
        (trace / "record_reuse.jsonl").write_bytes(b"".join((json.dumps(row) + "\n").encode() for row in rows))
        report["original_overlap"]["observations"] = rows
    report["input_files_sha256"]["preparation"] = {name: sha(raw)
                                                    for name, raw in inventory(preparation).items()}
    if edit_report:
        edit_report(report)
    report.pop("content_sha256", None)
    (trace / "report.json").write_bytes(encode(sealed(report)))
    manifest = json.loads((trace / "manifest.json").read_text())
    manifest.pop("content_sha256", None)
    manifest["files"] = {name: sha(raw) for name, raw in inventory(trace).items()
                         if name != "manifest.json"}
    (trace / "manifest.json").write_bytes(encode(sealed(manifest)))


class AssaySourceReuseTests(unittest.TestCase):
    def setUp(self):
        from biograph_steward.assay_source_reuse import publish_reuse_workspace, read_reuse, reuse_view
        self.publish, self.read, self.view = publish_reuse_workspace, read_reuse, reuse_view
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.graph = make_intact_workspace(self.root)
        self.trace = make_trace(self.root, self.source, self.graph)
        self.output = self.root / "annotated"

    def test_unannotated_run_has_no_inferred_reuse_classification(self):
        before = inventory(self.source)
        self.assertIsNone(self.read(self.source))
        view = self.view(self.source, "attached")
        self.assertEqual(view["status"], "unavailable")
        self.assertEqual(view["source_run"], "attached")
        self.assertFalse(view["observations"])
        self.assertEqual(inventory(self.source), before)

    def test_publication_preserves_workspace_and_separates_current_provider_from_history(self):
        before, original_graph = inventory(self.source), deepcopy(self.graph)
        report = self.publish(self.source, self.trace, self.output)
        self.assertEqual(self.read(self.output), report)
        for name, raw in before.items():
            self.assertEqual((self.output / name).read_bytes(), raw, name)
        self.assertEqual(inventory(self.source), before)
        self.assertEqual(self.graph, original_graph)
        for name in ("source_reuse.json", "source_reuse_records.jsonl", "source_reuse.html",
                     "source_reuse_manifest.json", "source_reuse_source/trace_report.json",
                     "source_reuse_source/trace_ledger.jsonl", "source_reuse_source/trace_manifest.json",
                     "source_reuse_source/scope.json",
                     "source_reuse_source/user_intact_record_link.json"):
            self.assertTrue((self.output / name).is_file(), name)
        view = self.view(self.output, "annotated")
        self.assertEqual(view["status"], "available")
        self.assertEqual(view["source_run"], "annotated")
        for key in ("snapshot_sha256", "assay_attachment_sha256", "assay_publication_sha256"):
            self.assertEqual(view[key], self.graph[key])
        rows = {row["observation_id"]: row for row in view["observations"]}
        self.assertEqual(set(rows), {row["id"] for row in self.graph["assay_observations"]})
        first = rows[self.graph["assay_observations"][0]["id"]]
        self.assertEqual(first["current_string_status"], "confirmed_user_assisted")
        self.assertEqual(first["observation_provenance"], "user_assisted_source_link")
        self.assertEqual(first["provider"], "STRING")
        self.assertEqual(first["provider_version"], "12.5")
        self.assertEqual(set(first["record_ids"]), {"imex:IM-100-1", "intact:EBI-100"})
        self.assertTrue(first["evidence_links"])
        for row in list(rows.values())[1:]:
            self.assertEqual(row["current_string_status"], "unknown_not_observed")
            self.assertEqual(row["observation_provenance"], "not_observed")
        self.assertTrue(all(row["historical_pharos_reuse"] is None for row in rows.values()))

    def test_publication_is_portable_and_does_not_depend_on_original_trace_paths(self):
        report = self.publish(self.source, self.trace, self.output)
        shutil.rmtree(self.source)
        shutil.rmtree(self.trace)
        shutil.rmtree(self.root / "preparation")
        moved = self.root / "moved"
        self.output.rename(moved)
        self.assertEqual(self.read(moved), report)
        self.assertEqual(self.view(moved, "moved")["status"], "available")

    def test_existing_output_and_source_output_overlap_are_rejected(self):
        self.output.mkdir()
        (self.output / "keep.txt").write_text("untouched")
        for output in (self.output, self.source, self.source / "nested", self.source.parent):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.publish(self.source, self.trace, output)
        self.assertEqual((self.output / "keep.txt").read_text(), "untouched")

    def test_changed_annotation_and_missing_annotation_file_fail_closed(self):
        self.publish(self.source, self.trace, self.output)
        target = self.output / "source_reuse_records.jsonl"
        original = target.read_bytes()
        target.write_bytes(original + b"{}\n")
        with self.assertRaises(ValueError):
            self.read(self.output)
        target.write_bytes(original)
        (self.output / "source_reuse.json").unlink()
        with self.assertRaises(ValueError):
            self.read(self.output)

    def test_changed_workspace_and_symlinked_inputs_are_rejected(self):
        self.publish(self.source, self.trace, self.output)
        (self.output / "assay_source/evidence.json").write_text("{}")
        with self.assertRaises(ValueError):
            self.read(self.output)
        alias = self.root / "source_alias"
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.publish(alias, self.trace, self.root / "from_alias")
        trace_alias = self.root / "trace_alias"
        trace_alias.symlink_to(self.trace, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.publish(self.source, trace_alias, self.root / "from_trace_alias")

    def test_resealed_wrong_source_binding_is_rejected_before_publication(self):
        for name in ("snapshot.json", "assay_attachment.json", "assay_observations.json"):
            with self.subTest(name=name):
                original = (self.root / "preparation/scope.json").read_bytes()
                reseal_trace(self.trace, edit_scope=lambda scope:
                    scope["input_files_sha256"]["original_workspace"].update({name: "f" * 64}))
                with self.assertRaises(ValueError):
                    self.publish(self.source, self.trace, self.output)
                self.assertFalse(self.output.exists())
                (self.root / "preparation/scope.json").write_bytes(original)
                reseal_trace(self.trace)

    def test_same_pair_does_not_substitute_for_exact_curated_identity(self):
        reseal_trace(self.trace, edit_report=lambda report:
            report["string"]["exact_intact_record_reuse_proof"].update(
                observation_id=self.graph["assay_observations"][1]["id"]))
        with self.assertRaises(ValueError):
            self.publish(self.source, self.trace, self.output)
        self.assertFalse(self.output.exists())

    def test_resealed_unmatched_user_link_is_rejected(self):
        def change_user(user):
            user.update(as_supplied="ebi.ac.uk/intact/query/IM-999-1", source_record_id="IM-999-1",
                        source_record_curie="imex:IM-999-1")
        def change_report(report):
            proof = report["string"]["exact_intact_record_reuse_proof"]
            proof.update(source_record_id="imex:IM-999-1")
            proof["string_link_provenance"].update(as_supplied="ebi.ac.uk/intact/query/IM-999-1",
                source_record_id="IM-999-1", source_record_curie="imex:IM-999-1")
        reseal_trace(self.trace, edit_report=change_report, edit_user=change_user)
        with self.assertRaises(ValueError):
            self.publish(self.source, self.trace, self.output)
        self.assertFalse(self.output.exists())

    def test_resealed_provider_status_cannot_promote_an_unobserved_row(self):
        reseal_trace(self.trace, edit_rows=lambda rows: rows[1].update(
            current_string_curated_record_reuse="confirmed_user_assisted"))
        with self.assertRaises(ValueError):
            self.publish(self.source, self.trace, self.output)
        self.assertFalse(self.output.exists())

    def test_resealed_historical_pharos_claim_cannot_be_inferred_from_current_string(self):
        reseal_trace(self.trace, edit_rows=lambda rows: rows[0].update(original_pharos_import_reuse=True))
        with self.assertRaises(ValueError):
            self.publish(self.source, self.trace, self.output)
        self.assertFalse(self.output.exists())

    def test_generic_cross_reference_is_not_an_identity_qualified_record_alias(self):
        other = self.root / "nonidentity"
        other.mkdir()
        source, graph = make_intact_workspace(other, typed_identity=False)
        trace = make_trace(other, source, graph)
        with self.assertRaises(ValueError):
            self.publish(source, trace, other / "annotated")
        self.assertFalse((other / "annotated").exists())

    def test_resealed_manual_method_must_match_captured_typed_experiment(self):
        reseal_trace(self.trace,
            edit_user=lambda user: user.update(method_mi_id_from_existing_source="MI:0410"),
            edit_report=lambda report: report["string"]["exact_intact_record_reuse_proof"][
                "string_link_provenance"].update(method_mi_id_from_existing_source="MI:0410"))
        with self.assertRaises(ValueError):
            self.publish(self.source, self.trace, self.output)
        self.assertFalse(self.output.exists())

    def test_resealed_publication_claim_must_match_captured_typed_experiment(self):
        reseal_trace(self.trace, edit_report=lambda report:
            report["string"]["exact_intact_record_reuse_proof"].update(publication="PMID:99999999"))
        with self.assertRaises(ValueError):
            self.publish(self.source, self.trace, self.output)
        self.assertFalse(self.output.exists())

    def test_resealed_sidecar_classification_must_still_replay_from_copied_proof(self):
        self.publish(self.source, self.trace, self.output)
        report_path = self.output / "source_reuse.json"
        report = json.loads(report_path.read_text())
        report["observations"][1]["current_string_status"] = "confirmed_user_assisted"
        report.pop("content_sha256")
        report_path.write_bytes(encode(sealed(report)))
        ledger_path = self.output / "source_reuse_records.jsonl"
        ledger_path.write_bytes(b"".join((json.dumps(row) + "\n").encode()
                                         for row in report["observations"]))
        manifest_path = self.output / "source_reuse_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for name in ("source_reuse.json", "source_reuse_records.jsonl"):
            manifest["supplement_files"][name] = sha((self.output / name).read_bytes())
        manifest.pop("content_sha256")
        manifest_path.write_bytes(encode(sealed(manifest)))
        with self.assertRaisesRegex(ValueError, "does not replay"):
            self.read(self.output)


if __name__ == "__main__":
    unittest.main()
