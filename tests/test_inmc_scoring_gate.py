"""Only invented source archives/workbooks/predictions; never production labels."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import score_inmc_comparison as gate
import test_inmc_comparison as fixtures
from biograph_steward.client import digest
from biograph_steward.file_utils import sha

HAS_NATIVE = (importlib.util.find_spec("openpyxl") is not None and
              importlib.util.find_spec("sklearn") is not None)


def write(path, data):
    fixtures.write(path, data)


def reseal_predictions(folder, report):
    report["files"] = {str(p.relative_to(folder)): sha(p) for p in folder.rglob("*")
                       if p.is_file() and p.name != "report.json"}
    report.pop("content_sha256", None)
    report["content_sha256"] = digest(report)
    write(folder / "report.json", report)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.graph, self.predictions = self.base / "graph", self.base / "predictions"
        self.output = self.base / "score"
        self.genes = fixtures.fixture(self.graph)
        g = self.genes
        self.candidates = [{"id": f"candidate_{i}", "original_genes": [a, b], "self_pair": a == b}
                           for i, (a, b) in enumerate(((g[0], g[2]), (g[0], g[3]), (g[2], g[4]), (g[5], g[5])))]
        self.author_pairs = [[g[0], g[2]], [g[2], g[4]]]
        write(self.graph / "candidates.json", self.candidates)
        write(self.graph / "split.json", {"masked_gene_pairs": [r["original_genes"] for r in self.candidates] + [[g[1], g[3]]],
                                          "training_degree": {gene: 2 for gene in g}})
        write(self.graph / "source_inventory.json", {
            "panel_gene_ids": sorted({x for r in self.candidates for x in r["original_genes"]}),
            "panel_genes_without_confirmed_context": [g[3], g[4], g[5]],
            "targets": [{"uniprot_id": "UniProtKB:TEST1", "panel_gene_ids": [g[0]]},
                        {"uniprot_id": "UniProtKB:TEST2", "panel_gene_ids": [g[2]]}]})
        codes = [("Positive", "Negative", "Negative"), ("Negative",) * 3,
                 ("Positive", "Not tested", "Negative"), ("Negative",) * 3]
        self.panel = gate.inmc_outcomes.HEADER + b"\n" + b"".join(
            ("\t".join([*row["original_genes"], "opaque", *code]) + "\n").encode()
            for row, code in zip(self.candidates, codes))
        self.archive, self.workbook = self.base / "source.zip", self.base / "author.xlsx"
        self.workbook.write_bytes(b"SYNTHETIC: native workbook only created by optional tests")
        self.contract_path = self.base / "declared_contract.json"
        self.execution = fixtures.invented_execution()
        self.contract_patch = mock.patch.object(gate.runner, "ASSAY_CONTRACT", str(self.contract_path))
        self.contract_patch.start()
        self.addCleanup(self.contract_patch.stop)
        self.bind_sources()

    def bind_sources(self):
        with zipfile.ZipFile(self.archive, "w") as source:
            source.writestr(gate.PANEL_MEMBER, self.panel)
            source.writestr("do_not_read.txt", "UNRELATED SYNTHETIC MEMBER")
        genes = {g for r in self.candidates for g in r["original_genes"]}
        contract = {"source_archive_sha256": sha(self.archive),
                    "source_member_sha256": {gate.PANEL_MEMBER: hashlib.sha256(self.panel).hexdigest()},
                    "author_positive_workbook_sha256": sha(self.workbook),
                    "population": {"candidate_pairs": 4, "self_pairs_separate": 1,
                                   "off_diagonal_nominations": 3, "original_gene_ids": len(genes)},
                    "limitations": ["Invented unit-test data only."]}
        write(self.contract_path, contract)
        write(self.graph / "assay_contract.json", contract)
        files = fixtures.seal(self.graph)["files"]
        hierarchy = {"status": "passed", "synthetic_only": True}
        resource = {"status": "passed", "resource_smoke": True, "runner_sha256": sha(Path(gate.runner.__file__)),
                    "execution": self.execution,
                    "graph_input_files": {k: files[k] for k in gate.runner.REQUIRED if k != "protocol.json"}}
        write(self.graph / "validation/hierarchy_smoke.json", hierarchy)
        write(self.graph / "validation/resource_smoke.json", resource)
        protocol = {"fully_frozen": True, "model": gate.runner.MODEL, "training": gate.runner.TRAINING,
                    "runner_sha256": sha(Path(gate.runner.__file__)), "execution": self.execution,
                    "scoring_implementation": {"path": gate.runner.SCORER, "sha256": sha(ROOT / gate.runner.SCORER)},
                    "assay_contract_sha256": sha(self.contract_path)}
        for name in ("hierarchy_smoke", "resource_smoke"):
            protocol[name] = {"status": "passed", "report_sha256": sha(self.graph / f"validation/{name}.json")}
        write(self.graph / "protocol.json", protocol)
        fixtures.seal(self.graph)
        self.make_predictions()

    def make_predictions(self):
        packet = gate.runner.validate_packet(self.graph)
        self.predictions.mkdir(exist_ok=True)
        bindings = {"graph_report_sha256": packet["report_sha256"],
                    "graph_input_files": {k: packet["files"][k] for k in gate.runner.REQUIRED if k != "protocol.json"},
                    "protocol_sha256": packet["files"]["protocol.json"], "runner_sha256": packet["protocol"]["runner_sha256"]}
        common = {"format": gate.runner.FORMAT, **bindings, "resource_smoke": False,
                  "execution": self.execution, "candidate_outcomes_loaded": False}
        manifest = {**common, "model": gate.runner.MODEL, "training": gate.runner.TRAINING,
                    "effective_epochs": 20, "effective_batch_size": 12, "seeds": [17, 43, 101],
                    "candidate_pairs_scored": True, "loss": "SoftplusLoss", "sampler": None,
                    "effective_rgcn_edge_dropout": None, "automatic_memory_optimization": False,
                    "score_aggregation": "mean_of_forward_and_reverse"}
        write(self.predictions / "manifest.json", manifest)
        receipts = []
        for arm in gate.ARMS:
            for seed in gate.runner.TRAINING["seeds"]:
                prefix = f"{arm}_{seed}"
                rows = []
                for partition, source in (("development", packet["development"]), ("candidate", packet["candidates"])):
                    for index, row in enumerate(source):
                        value = float(5 - index)
                        rows.append({**row, "partition": partition, "forward": value, "reverse": value, "score": value})
                write(self.predictions / (prefix + "_scores.json"), rows)
                (self.predictions / (prefix + "_state.pt")).write_bytes(b"SYNTHETIC CHECKPOINT: never unpickle")
                receipt = {"arm": arm, "seed": seed, "status": "passed", "optimizer_steps": 20,
                           "initial_parameters_sha256": "a" * 64, "positive_batch_sha256": "b" * 64,
                           "supervision_triples": 12, "losses": [1.0] * 20,
                           "adjacency_triples": len(packet["arms"][arm.split("_", 1)[1]]) if arm.startswith("rgcn_") else None,
                           "scores_file": prefix + "_scores.json", "score_rows": len(rows), "checkpoint": prefix + "_state.pt"}
                receipts.append(receipt)
                write(self.predictions / (prefix + "_receipt.json"), receipt)
        self.report = {**common, "status": "passed", "biological_accuracy_measured": False,
                       "candidate_pairs_scored": 4, "arms": receipts}
        reseal_predictions(self.predictions, self.report)

    def invoke(self):
        return gate.run(self.graph, self.predictions, self.archive, self.workbook, self.output)

    def mutate_score(self, change):
        path = self.predictions / "rgcn_baseline_17_scores.json"
        rows = json.loads(path.read_text())
        change(rows)
        write(path, rows)
        reseal_predictions(self.predictions, self.report)

    def test_complete_unlabelled_gate_and_coverage(self):
        packet, scores, binding = gate.validate_predictions(self.graph, self.predictions)
        self.assertEqual(set(scores), set(gate.ARMS))
        self.assertEqual({len(v) for arm in scores.values() for v in arm.values()}, {4})
        result = gate.coverage(self.graph, packet)["genes"]
        self.assertTrue(result[self.genes[0]]["context"])
        self.assertFalse(result[self.genes[3]]["mapping"])
        self.assertTrue(all(v["pharos_resolved"] is None for v in result.values()))
        self.assertEqual(binding["assay_contract_sha256"], sha(self.contract_path))

    def test_incomplete_run_rejected_before_sources_even_exist(self):
        self.report["arms"].pop()
        reseal_predictions(self.predictions, self.report)
        self.archive.unlink(); self.workbook.unlink()
        with self.assertRaisesRegex(ValueError, "four arms"):
            self.invoke()
        self.assertFalse(self.output.exists())

    def test_resource_smoke_and_prior_exposure_rejected(self):
        for field, value in (("resource_smoke", True), ("candidate_outcomes_loaded", True)):
            with self.subTest(field=field):
                original = self.report[field]
                self.report[field] = value
                reseal_predictions(self.predictions, self.report)
                with self.assertRaisesRegex(ValueError, "bindings or exposure"):
                    gate.validate_predictions(self.graph, self.predictions)
                self.report[field] = original

    def test_input_hash_and_exact_score_identity_rejected(self):
        self.mutate_score(lambda rows: rows[1].update(original_genes=[self.genes[1], self.genes[4]]))
        with self.assertRaisesRegex(ValueError, "identity differs"):
            gate.validate_predictions(self.graph, self.predictions)
        self.make_predictions()
        (self.predictions / "rgcn_scaffold_17_state.pt").write_bytes(b"drift")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            gate.validate_predictions(self.graph, self.predictions)

    def test_missing_duplicate_and_nonmean_scores_rejected(self):
        for change, pattern in ((lambda rows: rows.pop(), "omit"),
                                (lambda rows: rows.__setitem__(2, rows[1]), "Duplicate"),
                                (lambda rows: rows[1].update(score=0.0), "exact mean"),
                                (lambda rows: rows[1].update(score=True), "finite")):
            with self.subTest(pattern=pattern):
                self.make_predictions()
                self.mutate_score(change)
                with self.assertRaisesRegex(ValueError, pattern):
                    gate.validate_predictions(self.graph, self.predictions)

    def test_paired_initialization_and_budget_rejected(self):
        receipt = self.report["arms"][3]
        receipt["initial_parameters_sha256"] = "c" * 64
        write(self.predictions / f'{receipt["arm"]}_{receipt["seed"]}_receipt.json', receipt)
        reseal_predictions(self.predictions, self.report)
        with self.assertRaisesRegex(ValueError, "initialization"):
            gate.validate_predictions(self.graph, self.predictions)
        receipt["optimizer_steps"] = 19
        write(self.predictions / f'{receipt["arm"]}_{receipt["seed"]}_receipt.json', receipt)
        reseal_predictions(self.predictions, self.report)
        with self.assertRaisesRegex(ValueError, "budget"):
            gate.validate_predictions(self.graph, self.predictions)

    def test_source_drift_stops_before_exposure(self):
        self.workbook.write_bytes(b"changed")
        with mock.patch.object(gate, "_runtime", return_value={}), mock.patch.object(gate, "_author_pairs") as reader:
            with self.assertRaisesRegex(ValueError, "source fingerprints"):
                self.invoke()
            reader.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_runtime_drift_stops_before_any_source_read(self):
        self.archive.unlink(); self.workbook.unlink()
        with mock.patch.object(gate, "version", return_value="drift"):
            with self.assertRaisesRegex(ValueError, "runtime packages/Python"):
                self.invoke()
        self.assertFalse(self.output.exists())

    def test_reversed_source_identity_passes_without_decoding_assay_bytes(self):
        lines = self.panel.splitlines()
        cells = lines[1].split(b"\t")
        cells[0], cells[1], cells[3] = cells[1], cells[0], b"\xff"
        lines[1] = b"\t".join(cells)
        self.panel = b"\n".join(lines) + b"\n"
        self.bind_sources()
        with mock.patch.object(gate, "_runtime", return_value={}), \
                mock.patch.object(gate, "_author_pairs", return_value=self.author_pairs) as reader:
            with self.assertRaisesRegex(ValueError, "Invalid text encoding"):
                self.invoke()
            reader.assert_called_once()
        failure = json.loads((self.output / "failure.json").read_text())
        self.assertEqual(failure["phase"], "assay_materialization_and_reference_reconciliation")
        self.assertFalse((self.output / "metrics.json").exists())

    def test_byte_change_between_inventory_and_parse_is_rejected(self):
        original = gate._sealed
        def race(folder):
            result = original(folder)
            path = self.predictions / "manifest.json"
            value = json.loads(path.read_text()); value["unused"] = "changed after hashing"
            write(path, value)
            return result
        with mock.patch.object(gate, "_sealed", side_effect=race):
            with self.assertRaisesRegex(ValueError, "Parsed file fingerprint"):
                gate.validate_predictions(self.graph, self.predictions)

    def test_panel_population_error_stops_before_author_read_and_leaves_receipt(self):
        self.panel = self.panel.replace(self.genes[0].encode(), self.genes[1].encode())
        self.bind_sources()
        with mock.patch.object(gate, "_runtime", return_value={}), mock.patch.object(gate, "_author_pairs") as reader:
            with self.assertRaisesRegex(ValueError, "population differs"):
                self.invoke()
            reader.assert_not_called()
        failure = json.loads((self.output / "failure.json").read_text())
        self.assertEqual(failure["phase"], "panel_identity_check")
        self.assertTrue((self.output / "exposure_started.json").exists())
        self.assertFalse((self.output / "metrics.json").exists())

    def test_reconciliation_failure_preserves_exposure_without_metrics(self):
        with mock.patch.object(gate, "_runtime", return_value={}), mock.patch.object(gate, "_author_pairs", return_value=[]):
            with self.assertRaisesRegex(ValueError, "disagrees"):
                self.invoke()
        failure = json.loads((self.output / "failure.json").read_text())
        self.assertTrue(failure["candidate_outcomes_loaded"])
        self.assertFalse(failure["performance_reporting_allowed"])
        self.assertFalse((self.output / "outcomes.json").exists())
        self.assertFalse((self.output / "metrics.json").exists())
        self.assertEqual(failure["content_sha256"], digest({k: v for k, v in failure.items() if k != "content_sha256"}))

    def test_author_noncandidate_stops_without_metrics(self):
        for pairs in ([[self.genes[0], self.genes[1]]],):
            with self.subTest(pairs=pairs), mock.patch.object(gate, "_runtime", return_value={}), \
                    mock.patch.object(gate, "_author_pairs", return_value=pairs):
                self.output = self.base / f"bad_reference_{len(pairs)}"
                with self.assertRaisesRegex(ValueError, "non-candidate"):
                    self.invoke()
                self.assertFalse((self.output / "metrics.json").exists())

    def test_existing_output_never_reused(self):
        self.output.mkdir()
        with mock.patch.object(gate, "_runtime", return_value={}), mock.patch.object(gate, "_author_pairs") as reader:
            with self.assertRaisesRegex(ValueError, "immutable"):
                self.invoke()
            reader.assert_not_called()

    @unittest.skipUnless(HAS_NATIVE, "Optional native openpyxl/sklearn synthetic fixture")
    def test_native_workbook_and_full_scoring(self):
        from openpyxl import Workbook
        book = Workbook()
        book.active.title = gate.AUTHOR_SHEET
        book.active.append(["source", "target"])
        for pair in self.author_pairs:
            book.active.append(pair)
        # Author-positive set semantics permit a consistent reversed duplicate;
        # retain its source row count rather than treating its complement as negative.
        book.active.append(list(reversed(self.author_pairs[0])))
        book.create_sheet("Unused").append(["not used as a reference"])
        book.save(self.workbook)
        book.close()
        self.bind_sources()
        with mock.patch.object(gate, "AUTHOR_ROWS", 3), mock.patch.object(gate, "_runtime", return_value={"synthetic_native": True}):
            report = self.invoke()
        self.assertEqual(report["status"], "passed")
        outcomes = json.loads((self.output / "outcomes.json").read_text())
        self.assertEqual(len(outcomes["rows"]), 4)
        self.assertTrue(report["candidate_outcomes_loaded"])
        self.assertEqual(report["author_reference_duplicate_or_reverse_rows"], 1)
        self.assertTrue((self.output / "metrics.json").is_file())
        self.assertFalse((self.output / "failure.json").exists())
        self.assertEqual(report["content_sha256"], digest({k: v for k, v in report.items() if k != "content_sha256"}))

    @unittest.skipUnless(HAS_NATIVE, "Optional native openpyxl workbook fixture")
    def test_native_author_formula_header_and_count_fail_closed(self):
        from openpyxl import Workbook
        for header, row, expected in ((["wrong", "target"], self.author_pairs[0], "header"),
                                      (["source", "target"], ["=1+1", self.genes[2]], "formula"),
                                      (["source", "target"], self.author_pairs[0], "row count")):
            with self.subTest(expected=expected):
                book = Workbook(); book.active.title = gate.AUTHOR_SHEET
                book.active.append(header); book.active.append(row)
                memory = io.BytesIO(); book.save(memory); book.close()
                with mock.patch.object(gate, "AUTHOR_ROWS", 2), self.assertRaisesRegex(ValueError, expected):
                    gate._author_pairs(memory.getvalue())


if __name__ == "__main__":
    unittest.main()
