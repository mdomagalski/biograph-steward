"""Exact version/resource projection controls, with no biological truth labels."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from biograph_steward.reviews import review_run
from tools.sampled_audit import wiki_version_projection as version
from test_normalization import fixture, resign


def pathway(pwid, source="WP1_r10", name="Invented versioned pathway", url=None):
    return {"pwid": pwid, "name": name, "type": "WikiPathways", "sourceID": source,
            "url": url if url is not None else "http://www.wikipathways.org/instance/" + source}


class WikiVersionProjectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.run, self.packet, self.retained, self.output = [self.root / n for n in ("run", "packet", "retained", "projection")]
        source = fixture()
        for target in source["targets"]:
            target["pathways"] = []
        source["targets"][0]["pathways"] = [pathway(101), pathway(102), pathway(103, "WP1_r11"),
            pathway(104, "WP2"), {"pwid": 105, "name": "Other provider", "type": "Reactome", "sourceID": "R-HSA-1"}]
        source["targets"][1]["pathways"] = [pathway(201)]
        self.snapshot = deepcopy(source)
        graph = save_run(resign(source), self.run)
        assertion_id = next(e["assertion_id"] for e in graph["edges"] if e.get("evidence_record", {}).get("pwid") == 101)
        reviewed = self.root / "reviewed"
        self.graph = review_run(self.run, reviewed, assertion_id, "rejected", "Invented reviewer",
                                "Preserve this review without converting source presence into acceptance")
        self.manifest = gold_packet.export_packet(reviewed, self.packet)
        decisions = self.root / "decisions.json"
        write_json(decisions, {"format": gold_packet.DECISION_FORMAT, "packet_id": self.manifest["packet_id"],
            "method": "invented source-retention fixture", "actor": "Invented evaluator", "decisions": [
                {"edge_id": e["id"], "decision": "abstain", "reason": "Unassessed source evidence", "confidence": None}
                for e in self.graph["edges"]]})
        gold_packet.save_decisions(self.packet, decisions, self.retained)
        self.retained_pin = sha(self.retained / "report.json")
        self.retained_graph = gold_packet.load_decisions(self.retained)[1]

    def export(self):
        return version.export_projection(self.retained, self.output, retained_report_sha256=self.retained_pin)

    def test_exact_resources_share_context_without_merging_versions_or_parallel_evidence(self):
        before = deepcopy(self.retained_graph)
        result = version.project_graph(self.retained_graph)
        self.assertEqual(result["counts"]["projected_edges"], 4)
        self.assertEqual(result["counts"]["version_resources"], 2)
        self.assertEqual(result["counts"]["projected_subjects"], 2)
        self.assertEqual(result["counts"]["distinct_subject_version_claims"], 3)
        first = "http://www.wikipathways.org/instance/WP1_r10"
        second = "http://www.wikipathways.org/instance/WP1_r11"
        self.assertEqual({e["object"] for e in result["edges"]}, {first, second})
        duplicates = [e for e in result["edges"] if e["object"] == first and e["subject"] == "UniProtKB:P04637"]
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(len({e["id"] for e in duplicates}), 2)
        self.assertTrue(all(e["symmetric"] is False for e in result["edges"]))
        self.assertTrue(all(e["subject"].startswith("UniProtKB:") for e in result["edges"]))
        self.assertEqual(self.retained_graph, before)
        self.assertEqual(len(result["edge_mapping"]), len(before["edges"]))
        self.assertEqual(len(result["assertion_mapping"]), len(before["assertions"]))
        reviewed = next(e for e in result["edges"] if e["source_pwid"] == 101)
        self.assertEqual(reviewed["source_assertion_lifecycle_state"], "rejected")

    def test_unversioned_and_other_provider_records_are_preserved_outside_projection(self):
        result = version.project_graph(self.retained_graph)
        row = next(e for e in result["edge_mapping"] if e["source_pwid"] == 104)
        self.assertEqual(row["status"], "preserved_outside_projection")
        self.assertIn("unversioned_or_unsupported_source_identifier", row["reasons"])
        self.assertFalse(any(r["full_source_id"] == "WP2" for r in result["resource_mapping"]))
        self.assertEqual({e["source_edge_id"] for e in result["edge_mapping"]}, {e["id"] for e in self.retained_graph["edges"]})
        self.assertFalse(any(e["predicate"] == "http://purl.org/dc/terms/isVersionOf" for e in result["edges"]))
        self.assertTrue(all(not r["source_identifier_version_relation"]["graph_edge_created"] for r in result["resource_mapping"]))

    def test_conflicting_metadata_holds_the_whole_exact_version_group(self):
        graph = deepcopy(self.retained_graph)
        next(e for e in graph["edges"] if e.get("evidence_record", {}).get("pwid") == 102)["evidence_record"]["name"] = "Conflicting title"
        result = version.project_graph(graph)
        self.assertEqual(result["counts"]["projected_edges"], 1)
        row = next(r for r in result["resource_mapping"] if r["full_source_id"] == "WP1_r10")
        self.assertEqual(row["status"], "preserved_outside_projection")
        self.assertIn("conflicting_native_metadata_for_exact_provider_and_full_version", row["reasons"])
        self.assertEqual(len(row["source_edge_ids"]), 3)

    def test_unsupported_source_id_sharing_a_local_pathway_id_also_holds_its_versioned_row(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["targets"][0]["pathways"][3]["pwid"] = 103
        graph = save_run(resign(snapshot), self.root / "conflicting-local-id")
        result = version.project_graph(graph)
        rows = [r for r in result["edge_mapping"] if r["source_pwid"] == 103]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["status"] == "preserved_outside_projection" for r in rows))
        versioned = next(r for r in rows if r["full_source_id"] == "WP1_r11")
        self.assertIn("local_pathway_identifier_has_conflicting_version_metadata", versioned["reasons"])
        self.assertEqual({r["source_edge_id"] for r in result["edge_mapping"]}, {e["id"] for e in graph["edges"]})

    def test_missing_malformed_or_different_URL_is_never_replaced_by_an_invented_ID(self):
        for value in ("", "http://[", "https://example.invalid/instance/WP1_r11",
                      "http://www.wikipathways.org/instance/WP1_r10", "http://www.wikipathways.org/instance/WP1_r11?latest=1",
                      "http://www.wikipathways.org/instance/WP1_r11;latest", "http://www.wikipathways.org/instance/WP1_r11;"):
            graph = deepcopy(self.retained_graph)
            edge = next(e for e in graph["edges"] if e.get("evidence_record", {}).get("pwid") == 103)
            edge["evidence_record"]["url"] = value
            result = version.project_graph(graph)
            row = next(r for r in result["edge_mapping"] if r["source_edge_id"] == edge["id"])
            with self.subTest(value=value):
                self.assertEqual(row["status"], "preserved_outside_projection")
                self.assertIsNone(row["projection_object"])
        self.assertFalse(version.version_url("http://www.wikipathways.org/instance/WP1_r10", ["WP1_r10"]))

    def test_only_literal_URLs_pass_without_parser_whitespace_control_or_params_normalization(self):
        url = "http://www.wikipathways.org/instance/WP1_r10"
        for scheme in ("http", "https"):
            for host in ("www.wikipathways.org", "wikipathways.org"):
                self.assertTrue(version.version_url(scheme + "://" + host + "/instance/WP1_r10", "WP1_r10"))
        for changed in (url + ";latest", url + ";", " " + url, "\t" + url, "\n" + url,
                        "\x00" + url, url.replace("WP1_r10", "WP1_\nr10"), url + "?", url + "#"):
            with self.subTest(changed=repr(changed)):
                self.assertFalse(version.version_url(changed, "WP1_r10"))

    def test_qualifiers_remain_bound_and_are_not_strengthened_to_a_flat_membership(self):
        graph = deepcopy(self.retained_graph)
        edge = next(e for e in graph["edges"] if e.get("evidence_record", {}).get("pwid") == 103)
        edge["qualifiers"]["tissue"] = "Invented tissue"
        result = version.project_graph(graph)
        row = next(r for r in result["edge_mapping"] if r["source_edge_id"] == edge["id"])
        self.assertEqual(row["source_qualifiers"]["tissue"], "Invented tissue")
        self.assertIn("nonempty_qualification_requires_a_separate_semantic_profile", row["reasons"])
        self.assertEqual(row["status"], "preserved_outside_projection")

    def test_export_replays_every_row_and_preserves_the_full_verified_input(self):
        before = {p.relative_to(self.retained).as_posix(): sha(p) for p in self.retained.rglob("*") if p.is_file()}
        report = self.export()
        self.assertEqual(version.verify_projection(self.output), report)
        copied = self.output / "source_retained_package"
        self.assertEqual(gold_packet.load_decisions(copied)[1], self.retained_graph)
        self.assertEqual({p.relative_to(copied).as_posix(): sha(p) for p in copied.rglob("*") if p.is_file()}, before)
        self.assertEqual({p.relative_to(self.retained).as_posix(): sha(p) for p in self.retained.rglob("*") if p.is_file()}, before)
        for flag in ("source_graph_changed", "review_states_changed", "duplicate_triples_merged", "native_version_content_verified",
                     "scientific_accuracy_measured", "standards_validation_executed", "new_protein_interactions_inferred"):
            self.assertIs(report[flag], False)
        with self.assertRaises(ValueError):
            self.export()

    def test_resealed_missing_parallel_edge_still_fails_source_replay(self):
        self.export()
        file = self.output / "edges.jsonl"
        rows = file.read_text().splitlines()
        file.write_text("\n".join(rows[1:]) + "\n")
        report = json.loads((self.output / version.MANIFEST).read_text())
        report["files"]["edges.jsonl"] = sha(file)
        report.pop("content_sha256")
        report["content_sha256"] = digest(report)
        write_json(self.output / version.MANIFEST, report)
        with self.assertRaisesRegex(ValueError, "does not replay: edges"):
            version.verify_projection(self.output)

    def test_resealed_scientific_or_standards_claim_cannot_change_the_projection_boundary(self):
        self.export()
        report = json.loads((self.output / version.MANIFEST).read_text())
        report["scientific_accuracy_measured"] = True
        report.pop("content_sha256")
        report["content_sha256"] = digest(report)
        write_json(self.output / version.MANIFEST, report)
        with self.assertRaisesRegex(ValueError, "interpretation boundary"):
            version.verify_projection(self.output)

    def test_changed_source_during_export_does_not_leave_a_success_manifest(self):
        write = version.gold_packet._jsonl
        def changed_source(path, values):
            result = write(path, values)
            if Path(path).name == "edges.jsonl":
                report = self.retained / "report.json"
                report.write_bytes(report.read_bytes() + b"\n")
            return result
        with patch.object(version.gold_packet, "_jsonl", side_effect=changed_source):
            with self.assertRaisesRegex(ValueError, "source changed"):
                self.export()
        self.assertFalse((self.output / version.MANIFEST).exists())

    def test_changed_implementation_during_export_does_not_get_a_success_manifest(self):
        file_sha = version.sha
        implementation_reads = []
        def changed_implementation(path):
            if Path(path).resolve() == Path(version.__file__).resolve():
                implementation_reads.append(str(path))
                return ("a" if len(implementation_reads) == 1 else "b") * 64
            return file_sha(path)
        with patch.object(version, "sha", side_effect=changed_implementation):
            with self.assertRaisesRegex(ValueError, "implementation changed"):
                self.export()
        self.assertEqual(len(implementation_reads), 2)
        self.assertFalse((self.output / version.MANIFEST).exists())

    def test_corrupt_copied_source_fails_without_a_completed_projection(self):
        copy = version.shutil.copytree
        def changed_copy(source, target, *args, **kwargs):
            result = copy(source, target, *args, **kwargs)
            file = Path(target) / "retained_graph.json"
            if file.exists():
                file.write_bytes(file.read_bytes() + b"\n")
            return result
        with patch.object(version.shutil, "copytree", side_effect=changed_copy):
            with self.assertRaises(ValueError):
                self.export()
        self.assertFalse((self.output / version.MANIFEST).exists())

    def test_source_assertion_binding_or_pinned_input_cannot_be_substituted(self):
        graph = deepcopy(self.retained_graph)
        graph["edges"][0]["assertion_id"] = "assertion:unknown"
        with self.assertRaisesRegex(ValueError, "binding differs"):
            version.project_graph(graph)
        with self.assertRaisesRegex(ValueError, "explicit pin"):
            version.export_projection(self.retained, self.output, retained_report_sha256="0" * 64)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
