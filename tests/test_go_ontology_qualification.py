"""Synthetic ontology lifecycle tests; no biological truth labels are invented."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet, go_ontology_qualification as qualification
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from biograph_steward.reviews import review_run
from test_normalization import fixture, resign


def ontology_fixture():
    def node(number, **metadata):
        return {"id": qualification.GO_IRI + f"{number:07d}", "type": "CLASS", "meta": metadata}
    def prop(pred, number):
        return {"pred": pred, "val": qualification.GO_IRI + f"{number:07d}"}
    nodes = [node(1), node(2, deprecated=True, basicPropertyValues=[prop(qualification.REPLACED_BY, 1)]),
             node(3, deprecated=True, basicPropertyValues=[prop(qualification.CONSIDER, 1)]),
             node(5, deprecated=True, basicPropertyValues=[prop(qualification.REPLACED_BY, 99)]),
             node(6, deprecated=True, basicPropertyValues=[prop(qualification.REPLACED_BY, 1),
                                                         prop(qualification.REPLACED_BY, 7)]),
             node(7), node(3674), node(5575), node(8150)]
    return {"graphs": [{"id": "http://purl.obolibrary.org/obo/go.owl", "meta": {
        "version": "http://purl.obolibrary.org/obo/go/releases/2026-01-01/go.owl",
        "basicPropertyValues": [{"pred": qualification.LICENSE, "val": "TEST LICENSE ONLY"}]},
        "nodes": nodes, "edges": []}]}


def inventory(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}


class GoOntologyQualificationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.ontology = self.root / "synthetic.json.gz"
        self.ontology_value = ontology_fixture()
        self.write_ontology(self.ontology_value)
        self.snapshot = fixture()
        for target in self.snapshot["targets"]:
            target["pharos_context"]["go"] = []
        self.snapshot["targets"][0]["pharos_context"]["go"] = [
            {"goid": f"GO:{n:07d}", "type": "P", "term": "Invented term " + str(n),
             "evidence": "IDA", "goeco": "ECO:0000314", "assigned_by": "INVENTED"}
            for n in range(1, 7)]
        self.run, self.packet, self.output = [self.root / n for n in ("run", "packet", "output")]
        graph = save_run(resign(self.snapshot), self.run)
        active = next(e for e in graph["edges"] if e.get("object") == "GO:0000001")
        self.reviewed = self.root / "reviewed"
        self.graph = review_run(self.run, self.reviewed, active["assertion_id"], "rejected",
                                "Invented reviewer", "Synthetic review, unrelated to ontology currency")
        self.manifest = gold_packet.export_packet(self.reviewed, self.packet)
        self.before = inventory(self.packet)

    def write_ontology(self, value):
        self.ontology.write_bytes(gzip.compress(json.dumps(value).encode(), mtime=0))
        self.pin = sha(self.ontology)

    def qualify(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("No retrieval")):
            return qualification.qualify_go_ontology(self.packet, self.ontology, self.output,
                                                    ontology_sha256=self.pin)

    def test_complete_ledger_filters_only_obsolete_term_ids_preserves_unknown_and_source(self):
        report = self.qualify()
        dispositions, retained = gold_packet.load_decisions(self.output / "retained")
        self.assertEqual(report["counts"]["go_profile"], {"keep": 1, "prune": 4, "abstain": 1})
        self.assertEqual(report["counts"]["explicit_active_replacement_proposals"], 1)
        self.assertEqual(report["counts"]["obsolete_without_safe_active_replacement"], 3)
        self.assertEqual(len(retained["edges"]), len(self.graph["edges"]) - 4)
        self.assertEqual(retained["nodes"], self.graph["nodes"])
        self.assertEqual(dispositions["counts"]["prune"], 4)
        retained_ids = {e["id"] for e in retained["edges"]}
        for edge in self.graph["edges"]:
            if edge.get("record_kind") != "go_annotation" or edge["object"] in ("GO:0000001", "GO:0000004"):
                self.assertIn(edge["id"], retained_ids)
            else:
                self.assertNotIn(edge["id"], retained_ids)
        eligible = next(e for e in retained["edges"] if e.get("object") == "GO:0000001")
        assertion = next(a for a in retained["assertions"] if a["id"] == eligible["assertion_id"])
        self.assertEqual(assertion["lifecycle_state"], "rejected")
        self.assertIsNone(eligible["annotation_context"]["negated"])
        self.assertEqual(inventory(self.packet), self.before)
        self.assertEqual(gold_packet.load_packet(self.output / "retained/baseline_packet")[1], self.graph)
        self.assertEqual((self.output / report["ontology"]["source_file"]).read_bytes(), self.ontology.read_bytes())
        ledger = json.loads((self.output / "decisions.json").read_text())["decisions"]
        self.assertEqual(len(ledger), len(self.graph["edges"]))
        self.assertEqual({r["edge_id"] for r in ledger}, {e["id"] for e in self.graph["edges"]})
        self.assertTrue(all(r["confidence"] is None for r in ledger))
        self.assertFalse(report["biological_truth_assessed"])
        self.assertFalse(report["independent_biological_accuracy"])
        self.assertFalse(report["existing_method"]["official_ontobio_executed"])
        self.assertFalse(report["functional_relations_or_polarities_recovered"])

    def test_exact_replacements_are_proposals_only_and_consider_is_never_applied(self):
        report = self.qualify()
        trace = {r["term_id"]: r for r in report["source_decisions"]}
        proposal = trace["GO:0000002"]["replacement_proposal"]
        self.assertEqual(proposal["to_id"], "GO:0000001")
        self.assertFalse(proposal["applied"])
        self.assertIsNone(trace["GO:0000003"]["replacement_proposal"])
        self.assertEqual(trace["GO:0000003"]["consider_only"], [qualification.GO_IRI + "0000001"])
        self.assertIsNone(trace["GO:0000005"]["replacement_proposal"])
        self.assertIsNone(trace["GO:0000006"]["replacement_proposal"])
        self.assertFalse(report["replacement_proposals_applied"])
        proposals = json.loads((self.output / "replacement_proposals.json").read_text())
        self.assertEqual(len(proposals["proposals"]), 1)
        self.assertFalse(proposals["applied"])
        for name, expected in report["files"].items():
            self.assertEqual(sha(self.output / name), expected)
        self.assertEqual(report["content_sha256"], digest({k: v for k, v in report.items() if k != "content_sha256"}))

    def test_ontology_hash_tampering_and_invalid_binding_fail_before_output(self):
        for pin in ("", "not-a-pin", "0" * 64):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                qualification.qualify_go_ontology(self.packet, self.ontology, self.output, ontology_sha256=pin)
            self.assertFalse(self.output.exists())
        self.ontology.write_bytes(self.ontology.read_bytes() + b"changed")
        with self.assertRaises(ValueError):
            self.qualify()
        self.assertFalse(self.output.exists())

    def test_malformed_obographs_metadata_and_duplicate_ids_fail_before_output(self):
        variants = []
        for mutate in (lambda x: x["graphs"].append(deepcopy(x["graphs"][0])),
                       lambda x: x["graphs"][0]["meta"].pop("version"),
                       lambda x: x["graphs"][0]["nodes"].append(deepcopy(x["graphs"][0]["nodes"][0])),
                       lambda x: x["graphs"][0]["nodes"][0]["meta"].update(deprecated="false"),
                       lambda x: x["graphs"][0]["nodes"][0]["meta"].update(basicPropertyValues="bad"),
                       lambda x: x["graphs"][0]["nodes"].pop()):
            value = deepcopy(self.ontology_value)
            mutate(value)
            variants.append(value)
        for value in variants:
            with self.subTest(value=value):
                self.write_ontology(value)
                with self.assertRaises(ValueError):
                    self.qualify()
                self.assertFalse(self.output.exists())

    def test_unknown_term_and_deprecated_replacement_target_stay_unresolved(self):
        nodes, _, _ = qualification.load_ontology(self.ontology, self.pin)
        for term in (None, "GO:invalid", "GO:0000004"):
            with self.subTest(term=term):
                result = qualification.classify_term(term, nodes)
                self.assertEqual(result["decision"], "abstain")
                self.assertIsNone(result["replacement_proposal"])
        nodes["GO:0000001"]["meta"]["deprecated"] = True
        result = qualification.classify_term("GO:0000002", nodes)
        self.assertEqual(result["decision"], "prune")
        self.assertIsNone(result["replacement_proposal"])

    def test_graph_primary_term_mismatch_is_rejected_before_output(self):
        changed = deepcopy(self.graph)
        edge = next(e for e in changed["edges"] if e.get("record_kind") == "go_annotation")
        edge["evidence_record"]["goid"] = "GO:0000099"
        with patch.object(qualification.gold_packet, "load_packet", return_value=(self.manifest, changed)):
            with self.assertRaisesRegex(ValueError, "literal primary source term"):
                self.qualify()
        self.assertFalse(self.output.exists())

    def test_output_must_be_new_and_outside_source_material(self):
        for output in (self.packet, self.packet / "derived", self.root, self.ontology.parent):
            with self.subTest(output=output), self.assertRaises(ValueError):
                qualification.qualify_go_ontology(self.packet, self.ontology, output, ontology_sha256=self.pin)
        self.assertEqual(inventory(self.packet), self.before)

    def test_actor_is_required_before_source_loading(self):
        for actor in (None, "", " ", "Unassigned"):
            with self.subTest(actor=actor), patch.object(qualification.gold_packet, "load_packet") as loader:
                with self.assertRaises(ValueError):
                    qualification.qualify_go_ontology(self.packet, self.ontology, self.output,
                                                      ontology_sha256=self.pin, actor=actor)
                loader.assert_not_called()
            self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
