"""Invented inputs test adapter boundaries; they are not biological labels."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward import support_comparator as module


class SupportComparatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        files = {
            "cli/commands/evals/paperqa.py": (
                "raise RuntimeError('Never execute this third-party file')\n"
                "NODE_TYPE_MAP: dict = {'GEN': 'gene or protein'}\n"
                "PROMPT_TEMPLATE = 'Association between {seed_type} {seed_name} and {target_type} {target_name}?'\n"),
            "cli/commands/evals/sample_edges.py": "# Invented source artifact\n",
            "conf/base/evals.yml": "seed: 42\n", "LICENSE": "Invented license fixture\n"}
        for name, raw in files.items():
            p = self.upstream / name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(raw)
        patcher = patch.object(module, "UPSTREAM_FILES", {name: sha(self.upstream / name) for name in files})
        patcher.start(); self.addCleanup(patcher.stop)
        self.run = self.root / "run"; self.run.mkdir()
        self.graph = {"graph_format": "invented.v1", "snapshot_sha256": "invented-source-sha",
                      "nodes": [{"id": "UniProtKB:A", "name": "Invented protein A", "category": "biolink:Protein"},
                                {"id": "UniProtKB:B", "name": "Invented protein B", "category": "biolink:Protein"}],
                      "edges": [], "assertions": []}
        for number, assay in enumerate(("invented two hybrid", "invented microscopy")):
            aid, eid, oid = "assertion:" + str(number), "edge:" + str(number), "observation:" + str(number)
            self.graph["edges"].append({"id": eid, "subject": "UniProtKB:A", "object": "UniProtKB:B",
                "predicate": "biograph:has_assay_observation_with", "record_locators": ["invented.tsv#row=2"],
                "observation": {"id": oid, "assay": assay}})
            self.graph["assertions"].append({"id": aid, "subject": "UniProtKB:A", "object": "UniProtKB:B",
                "predicate": "biograph:has_assay_observation_with", "revision": "revision" + str(number),
                "lifecycle_state": "candidate", "symmetric": False, "evidence_edge_ids": [eid],
                "qualifiers": {"species": "NCBITaxon:9606", "assay": assay, "observation_id": oid},
                "publications": ["pubmed:1"]})
        (self.run / "graph.json").write_text(json.dumps(self.graph))
        patcher = patch.object(module, "read_run", return_value=({}, [], self.graph))
        patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch("biograph_steward.assay_source_reuse.read_reuse", return_value={"observations": [
            {"observation_id": "observation:0", "current_string_status": "confirmed_user_assisted",
             "historical_pharos_reuse": None}]})
        patcher.start(); self.addCleanup(patcher.stop)
        self.selections = [{"run": str(self.run), "assertion_id": "assertion:" + str(number),
                            "consumed_development_reason": "Invented consumed software fixture"}
                           for number in (0, 1)]

    def prepare(self):
        output = self.root / "prepared"
        module.prepare_comparator(self.selections, output, self.upstream)
        return output

    def imported(self, preparation, rows):
        source = self.root / "results.csv"
        fields = list(rows[0])
        handle = io.StringIO(newline="")
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        source.write_text(handle.getvalue())
        return module.inspect_results(preparation, source, self.root / "inspected")

    def result_rows(self, preparation):
        rows = list(csv.DictReader(io.StringIO((preparation / "sampled_edges_development.csv").read_text())))
        for index, row in enumerate(rows):
            row.update(task_id="invented-task-" + str(index), status="success", answer=
                       "<response><reasoning>Invented response only.</reasoning><rating>1</rating></response>")
        return rows

    def test_author_literals_are_read_without_execution_and_all_hashes_checked(self):
        template, types = module.load_upstream(self.upstream)
        self.assertIn("{seed_name}", template)
        self.assertEqual(types["GEN"], "gene or protein")
        (self.upstream / "conf/base/evals.yml").write_text("seed: 43\n")
        with self.assertRaisesRegex(ValueError, "Pinned OptimusKG source changed"):
            module.load_upstream(self.upstream)

    def test_distinct_assay_assertions_produce_same_upstream_query_but_keep_context(self):
        before = deepcopy(self.graph)
        prep = self.prepare()
        report, cases = module.load_preparation(prep)
        self.assertEqual(report["case_count"], 2)
        self.assertEqual(report["unique_query_count"], 1)
        self.assertEqual(len(report["identical_queries_for_different_assertions"]), 1)
        self.assertEqual(cases[0]["upstream_query"], cases[1]["upstream_query"])
        self.assertNotEqual(cases[0]["assertion"]["qualifiers"], cases[1]["assertion"]["qualifiers"])
        self.assertEqual(cases[0]["reuse"][0]["current_string_status"], "confirmed_user_assisted")
        self.assertEqual(cases[1]["reuse"], [])
        self.assertEqual(cases[0]["evidence"][0]["record_locators"], ["invented.tsv#row=2"])
        self.assertIsNone(cases[0]["scientific_truth_label"])
        self.assertNotIn("is_true_edge", (prep / "sampled_edges_development.csv").read_text())
        self.assertEqual(self.graph, before)

    def test_no_overwrite_duplicate_case_or_unknown_mapping(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "immutable output"):
            module.prepare_comparator(self.selections, self.root / "prepared", self.upstream)
        with self.assertRaisesRegex(ValueError, "more than once"):
            module.prepare_comparator([self.selections[0]] * 2, self.root / "other", self.upstream)
        self.graph["nodes"][0]["category"] = "biograph:MolecularProfile"
        with self.assertRaisesRegex(ValueError, "outside this explicit upstream mapping"):
            module.prepare_comparator(self.selections, self.root / "other", self.upstream)

    def test_changed_prepared_bytes_are_rejected(self):
        prep = self.prepare()
        (prep / "cases.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            module.load_preparation(prep)

    def test_not_found_is_unverified_and_failure_is_not_a_negative(self):
        prep = self.prepare()
        rows = self.result_rows(prep)
        rows[1]["status"] = "failed"; rows[1]["answer"] = ""
        report = self.imported(prep, rows)
        self.assertEqual(report["status_counts"], {"no_support_reported": 1, "service_failure_unresolved": 1})
        for row in report["results"]:
            self.assertIsNone(row["scientific_truth_label"])
            self.assertFalse(row["qualified_assertion_verified"])
        self.assertFalse(report["scientific_accuracy_measured"])

    def test_partial_pending_results_remain_resumable_without_inventing_missing_answers(self):
        prep = self.prepare()
        rows = self.result_rows(prep)[:1]
        rows[0]["status"] = "pending"; rows[0]["answer"] = ""
        report = self.imported(prep, rows)
        self.assertEqual(len(report["missing_case_ids"]), 1)
        self.assertEqual(report["results"][0]["search_status"], "pending_or_unknown_unresolved")
        self.assertEqual(report["hosted_calls_made_by_import"], 0)

    def test_changed_request_or_reused_remote_task_cannot_be_joined(self):
        prep = self.prepare()
        rows = self.result_rows(prep)
        rows[0]["request_sha256"] = digest("other request")
        with self.assertRaisesRegex(ValueError, "different request"):
            self.imported(prep, rows)
        rows = self.result_rows(prep)
        rows[1]["task_id"] = rows[0]["task_id"]
        with self.assertRaisesRegex(ValueError, "missing or reused"):
            self.imported(prep, rows)

    def test_ambiguous_or_absent_rating_does_not_become_support(self):
        prep = self.prepare()
        rows = self.result_rows(prep)
        rows[0]["answer"] += "<rating>5</rating>"
        rows[1]["answer"] = "I cannot access the source."
        report = self.imported(prep, rows)
        self.assertEqual(report["status_counts"], {"invalid_response_unresolved": 2})

    def test_service_no_successful_answer_flag_is_unresolved_despite_a_rating(self):
        prep = self.prepare()
        rows = self.result_rows(prep)
        for row in rows:
            row["has_successful_answer"] = "False"
        report = self.imported(prep, rows)
        self.assertEqual(report["status_counts"], {"no_successful_answer_unresolved": 2})

    def test_historical_reuse_is_not_mislabeled_as_current_replay_and_corruption_still_fails(self):
        from biograph_steward.assay_source_reuse import FORMAT as reuse_format
        report = {"format": reuse_format, "observations": [{"observation_id": "observation:0"}]}
        report["content_sha256"] = digest(report)
        (self.run / "source_reuse.json").write_text(json.dumps(report))
        manifest = {"format": reuse_format, "implementation_sha256": {"old_reader.py": "old-sha"},
                    "workspace_files": {"graph.json": sha(self.run / "graph.json")},
                    "supplement_files": {"source_reuse.json": sha(self.run / "source_reuse.json")}}
        manifest["content_sha256"] = digest(manifest)
        (self.run / "source_reuse_manifest.json").write_text(json.dumps(manifest))
        with patch("biograph_steward.assay_source_reuse.read_reuse", side_effect=ValueError(
                "Source-reuse audit: manifest or implementation changed.")):
            context = module._reuse_context(self.run)
            self.assertEqual(context["verification"], "unchanged_historical_supplement_not_replayed")
            (self.run / "source_reuse.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "integrity failed"):
                module._reuse_context(self.run)


if __name__ == "__main__":
    unittest.main()
