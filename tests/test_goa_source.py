"""Invented source packets test replay, full-frame binding and native semantics."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import goa_source as goa, go_qualification as go
from biograph_steward import gold_packet, go_ontology_qualification as ontology
from biograph_steward.assertions import build_assertions
from biograph_steward.client import canonical, digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from tools.go_qualification.audit_replacements import audit
from test_normalization import fixture, resign


def parsed_record(fields, number, pin):
    parsed = dict(zip(go.GAF_FIELDS, fields))
    for key in ("Qualifier", "DB:Reference", "With", "Synonym", "Taxon_ID"):
        parsed[key] = parsed[key].split("|") if parsed[key] else []
    return go.native_record(number, "\t".join(fields), fields, parsed, pin)


class GoaSourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.run, self.packet, self.qualification, self.context, self.census, self.publication = (
            self.root / n for n in ("run", "packet", "qualification", "context", "census", "publication"))
        snapshot = fixture()
        for target in snapshot["targets"]:
            target["pharos_context"]["go"] = []
        snapshot["targets"][0]["pharos_context"]["go"] = [
            {"goid": "GO:0000002", "term": "Invented obsolete", "type": "P", "evidence": "IDA", "assigned_by": "INVENTED"},
            {"goid": "GO:0000004", "term": "Invented retained", "type": "P", "evidence": "IDA", "assigned_by": "INVENTED"}]
        self.snapshot = resign(snapshot)
        self.graph = save_run(self.snapshot, self.run)
        gold_packet.export_packet(self.run, self.packet)
        self.old_subject = next(e["subject"] for e in self.graph["edges"] if e.get("record_kind") == "go_annotation")
        def node(term, **meta):
            return {"id": ontology.GO_IRI + term[3:], "type": "CLASS", "lbl": "Invented " + term, "meta": meta}
        active_meta = {"basicPropertyValues": [{"pred": "http://www.geneontology.org/formats/oboInOwl#hasOBONamespace", "val": "biological_process"}]}
        value = {"graphs": [{"id": "http://purl.obolibrary.org/obo/go.owl", "meta": {
            "version": "http://purl.obolibrary.org/obo/go/releases/2026-01-01/go.owl",
            "basicPropertyValues": [{"pred": ontology.LICENSE, "val": "TEST FIXTURE ONLY"}]},
            "nodes": [node("GO:0000001", **active_meta), node("GO:0000004", **active_meta),
                node("GO:0000002", deprecated=True, basicPropertyValues=[{
                    "pred": ontology.REPLACED_BY, "val": ontology.GO_IRI + "0000001"}]),
                *[node(t) for t in ("GO:0003674", "GO:0005575", "GO:0008150")]], "edges": []}]}
        self.ontology_file = self.root / "ontology.json.gz"
        self.ontology_file.write_bytes(gzip.compress(json.dumps(value).encode(), mtime=0))
        ontology.qualify_go_ontology(self.packet, self.ontology_file, self.qualification,
                                    ontology_sha256=sha(self.ontology_file))
        self.headers = ["!gaf-version: 2.2", "!generated-by: INVENTED", "!date-generated: 2026-01-01"]
        base = ["UniProtKB", self.old_subject.split(":", 1)[1], "INVENTED", "involved_in",
                "GO:0000001", "PMID:12345|OTHER:alias", "IDA", "", "P", "Invented protein",
                "", "protein", "taxon:9606", "20260101", "INVENTED", "", ""]
        second = list(base)
        second[5] = "PMID:12346"
        unrelated = list(base)
        unrelated[4] = "GO:0000004"
        self.fields = [base, second, unrelated]
        self.gaf = self.root / "annotations.gaf.gz"
        self.gaf.write_bytes(gzip.compress(("\n".join(self.headers + ["\t".join(f) for f in self.fields]) + "\n").encode(), mtime=0))
        self.gaf_pin = sha(self.gaf)
        self.native = [parsed_record(f, i, self.gaf_pin) for i, f in enumerate(self.fields, len(self.headers) + 1)]
        source = {"headers": self.headers, "total_source_rows": len(self.fields), "gaf_sha256": self.gaf_pin,
            "parser": {"package": "biopython", "version": "1.88", "function": "Bio.UniProt.GOA.gafiterator"}}
        with patch.object(go, "read_native_gaf", return_value=(self.native, source)):
            go.qualify_go_context(self.packet, self.gaf, self.context, expected_gaf_sha256=self.gaf_pin,
                                  source_url="https://example.invalid/invented.gaf.gz")
        audit(self.qualification, self.qualification / "retained", self.context, self.census,
              qualification_sha256=sha(self.qualification / "go_ontology_qualification.json"),
              retained_sha256=sha(self.qualification / "retained/report.json"),
              context_sha256=sha(self.context / "go_context_qualification.json"))

    def publish(self):
        goa.publish_recoveries(self.census, self.qualification, self.qualification / "retained",
                              self.context, self.publication, census_sha256=sha(self.census / "report.json"))
        return goa.load_publication(self.publication)

    def reseal_outer(self):
        manifest = json.loads((self.publication / "publication.json").read_text())
        manifest["files"] = {p.relative_to(self.publication).as_posix(): sha(p)
            for p in self.publication.rglob("*") if p.is_file() and p.name != "publication.json"}
        manifest.pop("content_sha256")
        manifest["content_sha256"] = digest(manifest)
        write_json(self.publication / "publication.json", manifest)

    def test_complete_source_replay_preserves_every_native_field_and_new_source_identity(self):
        manifest, projection, material = self.publish()
        self.assertEqual(len(projection["baseline_go_edges"]), 2)
        self.assertEqual(projection["summary"]["qualified_native_records"], 2)
        self.assertEqual(projection["summary"]["distinct_subject_term_concepts"], 1)
        self.assertEqual({r["native_record"]["id"]: r["native_record"] for r in projection["observations"]},
                         {r["id"]: r for r in self.native[:2]})
        self.assertEqual(material[goa.CONTEXT + "source/annotations.gaf.gz"], self.gaf.read_bytes())
        before = deepcopy((self.snapshot, self.graph, manifest, projection))
        added = goa.prepare(self.snapshot, self.graph, manifest, projection)
        self.assertEqual(before, (self.snapshot, self.graph, manifest, projection))
        self.assertEqual(len(added["nodes"]), 1)
        self.assertEqual(len(added["edges"]), 2)
        for e in added["edges"]:
            native = e["observation"]["native_record"]
            self.assertEqual(e["evidence_record"], e["observation"])
            self.assertEqual(native["raw_fields"], native["raw_line"].split("\t"))
            self.assertEqual(e["record_kind"], "native_go_annotation")
            self.assertEqual(e["qualifiers"], {"go_aspect": "P", "species": "NCBITaxon:9606", "go_relation": "involved_in"})
            self.assertNotIn("observation_id", e["qualifiers"])
            self.assertNotIn("disease", e["qualifiers"])
            self.assertEqual(e["local_review_state"], "candidate")
            self.assertFalse(e["biologically_validated"])
            self.assertEqual(e["observation"]["graph_edge_id"], e["id"])
            self.assertEqual(native["source_gaf_sha256"], self.gaf_pin)
        group_graph = {"edges": deepcopy(added["edges"]), "data_kind": "live_pharos", "snapshot_sha256": self.snapshot["content_sha256"],
                       "evidence_extension_sha256": "invented"}
        self.assertEqual(len(build_assertions(group_graph)), 1)
        self.assertEqual(manifest["source_license"]["license"], "CC-BY-4.0")

    def test_complete_foreign_or_partial_GO_frame_rejected_even_for_unchanged_candidate(self):
        manifest, projection, _ = self.publish()
        for change in ("drop_retained", "assigner", "extra_GO"):
            graph = deepcopy(self.graph)
            if change == "drop_retained":
                graph["edges"] = [e for e in graph["edges"] if e["object"] != "GO:0000004"]
            elif change == "assigner":
                next(e for e in graph["edges"] if e["object"] == "GO:0000004")["evidence_record"]["assigned_by"] = "OTHER"
            else:
                e = deepcopy(next(e for e in graph["edges"] if e.get("record_kind") == "go_annotation"))
                e["id"] += "extra"
                graph["edges"].append(e)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "complete baseline GO frame"):
                goa.prepare(self.snapshot, graph, manifest, projection)

    def test_new_snapshot_cannot_reuse_publication(self):
        manifest, projection, _ = self.publish()
        changed = deepcopy(self.snapshot)
        changed["created_at"] = "2026-02-01T00:00:00Z"
        changed = resign(changed)
        with self.assertRaisesRegex(ValueError, "different exact snapshot"):
            goa.prepare(changed, self.graph, manifest, projection)

    def test_existing_node_name_and_attributes_are_never_modified(self):
        manifest, projection, _ = self.publish()
        graph = deepcopy(self.graph)
        graph["nodes"].append({"id": "GO:0000001", "name": "Historical distinct label",
                               "category": "biolink:BiologicalProcess", "historical": True})
        before = deepcopy(graph)
        result = goa.prepare(self.snapshot, graph, manifest, projection)
        self.assertEqual(result["nodes"], [])
        self.assertEqual(graph, before)
        self.assertEqual(result["observations"][0]["go_label"], "Invented GO:0000001")

    def test_resealed_derived_native_field_cannot_disagree_with_raw_GAF(self):
        self.publish()
        path = self.publication / goa.CONTEXT / "native_records.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines()]
        rows[0]["negated"] = True
        path.write_text("".join(canonical(r) + "\n" for r in rows))
        context = self.publication / goa.CONTEXT / "go_context_qualification.json"
        report = json.loads(context.read_text())
        report["files"]["native_records.jsonl"] = sha(path)
        report.pop("content_sha256")
        report["content_sha256"] = digest(report)
        write_json(context, report)
        self.reseal_outer()
        with self.assertRaises(ValueError):
            goa.load_publication(self.publication)

    def test_duplicate_native_proof_is_rejected(self):
        self.publish()
        path = self.publication / goa.CONTEXT / "native_records.jsonl"
        path.write_bytes(path.read_bytes() + path.read_bytes().splitlines()[0] + b"\n")
        self.reseal_outer()
        with self.assertRaises(ValueError):
            goa.load_publication(self.publication)

    def test_missing_candidate_is_rejected_after_census_and_intake_are_resealed(self):
        self.publish()
        name = "qualified_nonduplicate_native_records.jsonl"
        path = self.publication / goa.CENSUS / name
        path.write_bytes(path.read_bytes().splitlines()[0] + b"\n")
        census_path = self.publication / goa.CENSUS / "report.json"
        report = json.loads(census_path.read_text())
        report["files"][name] = sha(path)
        report.pop("content_sha256")
        report["content_sha256"] = digest(report)
        write_json(census_path, report)
        intake_path = self.publication / goa.INTAKE
        intake = json.loads(intake_path.read_text())
        intake["census_file_sha256"] = sha(census_path)
        intake.pop("content_sha256")
        intake["content_sha256"] = digest(intake)
        write_json(intake_path, intake)
        self.reseal_outer()
        with self.assertRaisesRegex(ValueError, "do not replay"):
            goa.load_publication(self.publication)

    def test_retained_frame_cannot_omit_current_annotation_with_resealed_hashes(self):
        self.publish()
        path = self.publication / goa.RETAINED_GO
        path.write_text("[]\n")
        intake_path = self.publication / goa.INTAKE
        intake = json.loads(intake_path.read_text())
        intake["retained_go_edges_sha256"] = digest([])
        intake.pop("content_sha256")
        intake["content_sha256"] = digest(intake)
        write_json(intake_path, intake)
        self.reseal_outer()
        with self.assertRaisesRegex(ValueError, "complete original active"):
            goa.load_publication(self.publication)

    def test_resealed_projection_changes_are_not_accepted_as_source_facts(self):
        self.publish()
        path = self.publication / "projection.json"
        value = json.loads(path.read_text())
        value["observations"][0]["go_label"] = "Invented false label"
        value.pop("content_sha256")
        value["content_sha256"] = digest(value)
        write_json(path, value)
        self.reseal_outer()
        with self.assertRaisesRegex(ValueError, "projection does not reproduce"):
            goa.load_publication(self.publication)

    def test_native_context_and_polarity_gate_is_reused(self):
        for column, replacement in ((3, "NOT|involved_in"), (6, "TAS"), (7, "UniProtKB:P12345"),
                                    (12, "taxon:10090"), (15, "occurs_in(CL:0000001)"),
                                    (16, self.old_subject + "-2")):
            fields = list(self.fields[0])
            fields[column] = replacement
            row = parsed_record(fields, 4, self.gaf_pin)
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, "outside the unopposed"):
                goa.validate_native_record(row)

    def test_wrong_explicit_census_pin_fails_before_output(self):
        with self.assertRaisesRegex(ValueError, "explicit census file pin"):
            goa.publish_recoveries(self.census, self.qualification, self.qualification / "retained",
                                  self.context, self.publication, census_sha256="0" * 64)
        self.assertFalse(self.publication.exists())


if __name__ == "__main__":
    unittest.main()
