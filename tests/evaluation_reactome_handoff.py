"""Invented fixtures only: real-denominator guards are never relaxed in production.

Source-loader and tiny schedule seams below are confined to unittest patches.
The real native fit, preparation, file authentication, freeze and scoring run.
"""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import freeze_reactome_context as freeze
import prepare_reactome_context_graphs as projection
import run_reactome_context as runner
import score_reactome_context as score
from biograph_steward.client import digest
from biograph_steward.file_utils import sha


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def reseal(value):
    value.pop("content_sha256", None)
    value["content_sha256"] = digest(value)
    return value


def reseal_predictions(folder, report):
    report["files"] = {p.name: sha(p) for p in folder.iterdir() if p.is_file() and p.name != "report.json"}
    write(folder / "report.json", reseal(report))


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name).resolve()
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.graph = cls.base / "prepared"
        fixture = runner.synthetic_fixture()
        genes = fixture["entities"][:7]
        extra = [(genes[0], genes[3]), (genes[0], genes[4]), (genes[6], genes[6])]
        fixture["candidates"] += [{"id": f"invented_extra_{i}", "original_genes": [a, b], "self_pair": a == b}
                                  for i, (a, b) in enumerate(extra)]
        fixture["masked_gene_pairs"] += [list(p) for p in extra]
        inventory = {"panel_gene_ids": genes, "panel_genes_without_confirmed_context": [g for g in genes if g not in (genes[0], genes[2])],
                     "targets": [{"uniprot_id": "UniProtKB:INVENTED1", "panel_gene_ids": [genes[0]]},
                                 {"uniprot_id": "UniProtKB:INVENTED2", "panel_gene_ids": [genes[2]]}]}
        entities = [{"id": name, "type": "original_gene" if name.startswith("ENSG") else
                     "reviewed_product_context" if name.startswith("UniProtKB:") else "go_term"}
                    for name in fixture["entities"] if not name.startswith("REACT:")]
        baseline = fixture["arms"][runner.ARMS[0]]
        original = cls.base / "original"
        original.mkdir()
        (original / "arms").mkdir()
        projection.table(original / "arms/baseline.tsv", baseline)
        projection.table(original / "supervision.tsv", fixture["supervision"])
        split = {"masked_gene_pairs": fixture["masked_gene_pairs"],
                 "training_degree": {g: 2 if g != genes[6] else 0 for g in genes}}
        cls.archive, cls.workbook = cls.base / "invented.zip", cls.base / "invented.xlsx"
        codes = [("Positive", "Negative", "Negative"), ("Negative",) * 3, ("Negative",) * 3,
                 ("Positive", "Not tested", "Negative"), ("Negative",) * 3]
        cls.panel = score.inmc_outcomes.HEADER + b"\n" + b"".join(
            ("\t".join([*row["original_genes"], "opaque", *code]) + "\n").encode()
            for row, code in zip(fixture["candidates"], codes))
        with zipfile.ZipFile(cls.archive, "w") as source:
            source.writestr(score.original.PANEL_MEMBER, cls.panel)
            source.writestr("never_read_synthetic.txt", "Unrelated member")
        from openpyxl import Workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Fig.6"
        sheet.append(["source", "target"])
        sheet.append(fixture["candidates"][0]["original_genes"])
        sheet.append(fixture["candidates"][3]["original_genes"])
        workbook.save(cls.workbook)
        contract = {"source_archive_sha256": sha(cls.archive), "author_positive_workbook_sha256": sha(cls.workbook),
                    "source_member_sha256": {score.original.PANEL_MEMBER: hashlib.sha256(cls.panel).hexdigest()},
                    "population": {"candidate_pairs": 5, "self_pairs_separate": 1, "off_diagonal_nominations": 4,
                                   "original_gene_ids": len({g for row in fixture["candidates"] for g in row["original_genes"]})}, "limitations": ["INVENTED FIXTURE ONLY"]}
        for name, value in (("candidates.json", fixture["candidates"]), ("split.json", split),
                            ("development_pairs.json", fixture["development"]), ("source_inventory.json", inventory),
                            ("assay_contract.json", contract), ("report.json", {"invented": True})):
            write(original / name, value)
        frozen = {"entities": entities, "relations": [{"id": r} for r in fixture["relations"][:-1]],
                  "inventory": inventory, "candidates": fixture["candidates"], "split": split,
                  "baseline": baseline, "supervision": fixture["supervision"],
                  "report": {"files": {name: sha(original / name) for name in projection.COPY_FILES}, "chunk_files": {}}}
        frozen["report"]["files"]["arms/baseline.tsv"] = sha(original / "arms/baseline.tsv")
        records = [(f"INVENTED{i}", {"pwid": 9000001, "name": "Invented pathway", "type": "Reactome",
                    "sourceID": "R-HSA-9000001", "url": "https://reactome.org/content/detail/R-HSA-9000001"},
                    {"retained": f"invented/{i}", "raw_response": f"invented/raw/{i}"}) for i in (1, 2)]
        selected = {"learner": {**runner.MODEL, "loss": "SoftplusLoss", "version": "1.11.1", "torch_version": "2.6.0"},
                    "training": runner.TRAINING, "evaluation": {}, "coverage_only_diagnostic": {}, "population": {},
                    "predictor_exclusions": [], "source_independence_limit": "INVENTED", "stopping": "one fixture run",
                    "source_inventory": {"available_reactome_counts": {"source_rows": 2, "products": 2, "pathway_stable_ids": 1,
                        "distinct_product_pathway_memberships": 2, "stable_id_label_conflicts": 0,
                        "pharos_pathway_id_to_multiple_stable_id_conflicts": 0, "invalid_human_stable_ids": 0}}}
        for obj, name, value in ((projection, "ROOT", cls.base), (projection, "ORIGINAL", "original"),
                                 (projection, "SNAPSHOT", "snapshot"), (projection, "CODE_FILES", set())):
            cls.stack.enter_context(patch.object(obj, name, value))
        cls.stack.enter_context(patch.object(projection, "selection_bindings", return_value=(selected, {})))
        cls.stack.enter_context(patch.object(projection, "frozen_baseline", return_value=frozen))
        cls.stack.enter_context(patch.object(projection, "snapshot_records", return_value=(records, {"files": {}, "families": {"pathways": {"retained": 2}}})))
        projection.prepare(cls.graph)
        def packet(path):
            result = projection.validate_prepared_packet(path)
            result["entities"] = [r["id"] for r in result["entities"]]
            result["relations"] = [r["id"] for r in result["relations"]]
            result["development"] = json.loads((Path(path) / "development_pairs.json").read_text())
            result["masked_gene_pairs"] = result["split"]["masked_gene_pairs"]
            runner.validate_inputs(result)
            result["graph_bindings"] = runner.graph_bindings(path, result)
            return result
        cls.stack.enter_context(patch.object(runner, "validate_packet", side_effect=packet))
        original_schedule = runner.schedule
        def tiny_schedule(n, *, mode):
            if mode == "synthetic_check":
                return original_schedule(n, mode=mode)
            epochs, batch, seeds = (1, 12, [17]) if mode == "resource_check" else (2, 8, [17, 43, 101])
            updates = epochs * runner.math.ceil(n / batch)
            return {"epochs": epochs, "batch_size": batch, "seeds": seeds, "updates_per_arm_seed": updates,
                    "runs": 2 * len(seeds), "total_updates": 2 * len(seeds) * updates}
        cls.stack.enter_context(patch.object(runner, "schedule", side_effect=tiny_schedule))
        original_contract = freeze.reporting_contract()
        original_contract.update(population="invented_unittest_fixture_only", primary_eligible_pairs=3,
                                 primary_detected_pairs=1, primary_nondetected_pairs=2)
        cls.stack.enter_context(patch.object(freeze, "reporting_contract", return_value=original_contract))
        cls.stack.enter_context(patch.object(score.original, "AUTHOR_ROWS", 2))
        cls.synthetic, cls.resource, cls.frozen, cls.predictions = [cls.base / s for s in ("synthetic", "resource", "freeze", "predictions")]
        runner.run_synthetic(cls.synthetic)
        runner.run(cls.graph, cls.resource, device="cpu", resource_check=True)
        freeze.freeze_comparison(cls.graph, cls.synthetic / "report.json", cls.resource / "report.json", cls.frozen, device="cpu")
        runner.run(cls.graph, cls.predictions, device="cpu", execution_packet=cls.frozen)

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(dir=self.base))
        self.addCleanup(shutil.rmtree, self.case)
        self.pred = self.case / "predictions"
        shutil.copytree(self.predictions, self.pred)
        self.report = json.loads((self.pred / "report.json").read_text())
        self.out = self.case / "scored"

    def invoke(self, **changes):
        args = dict(graph=self.graph, execution_packet=self.frozen, predictions=self.pred, archive=self.archive,
                    workbook=self.workbook, output=self.out, device="cpu")
        args.update(changes)
        return score.run(**args)

    def test_full_native_prepare_freeze_prediction_score_wiring(self):
        result = self.invoke()
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["independent_validation"])
        metrics = json.loads((self.out / "metrics.json").read_text())
        self.assertEqual(metrics["coverage"]["primary_scored_pairs_per_arm_seed"], 3)
        self.assertEqual(set(metrics["paired_comparison"]["deltas_by_seed"]), {"17", "43", "101"})
        self.assertEqual(metrics["reactome_endpoint_coverage_strata"]["1"]["status"], "insufficient_class_support")
        self.assertFalse(metrics["statistical_significance_claimed"])
        self.assertTrue((self.out / "exposure_started.json").is_file())

    def test_missing_and_nonfinite_or_labelled_prediction_rows_block_before_source(self):
        for change in (lambda rows: rows.pop(), lambda rows: rows[0].update(score=True),
                       lambda rows: rows[0].update(author_positive=True), lambda rows: rows[0].update(score=123.0),
                       lambda rows: rows.reverse()):
            with self.subTest(change=change):
                name = "rgcn_baseline_17_scores.json"
                rows = json.loads((self.predictions / name).read_text())
                change(rows)
                write(self.pred / name, rows)
                reseal_predictions(self.pred, self.report)
                with self.assertRaises(ValueError):
                    self.invoke(archive=self.case / "absent", workbook=self.case / "absent")
                self.assertFalse(self.out.exists())

    def test_missing_prediction_and_checkpoint_artifacts_block(self):
        for name in ("rgcn_baseline_17_scores.json", "rgcn_reactome_101_state.pt"):
            target = self.pred / name
            saved = target.read_bytes()
            target.unlink()
            with self.assertRaises((ValueError, OSError)):
                self.invoke(archive=self.case / "absent")
            self.assertFalse(self.out.exists())
            target.write_bytes(saved)

    def test_incomplete_runs_bad_query_adjacency_budget_and_fingerprints_block(self):
        for mutate in (lambda r: r["arms"].pop(), lambda r: r["arms"][0].update(query_sha256="a" * 64),
                       lambda r: r["arms"][0].update(adjacency_sha256="b" * 64),
                       lambda r: r["arms"][0].update(optimizer_steps=1),
                       lambda r: r["arms"][0].update(negative_proposal_sha256="c" * 64)):
            report = deepcopy(self.report)
            mutate(report)
            for row in report["arms"]:
                write(self.pred / f'{row["arm"]}_{row["seed"]}_receipt.json', row)
            reseal_predictions(self.pred, report)
            with self.assertRaises(ValueError):
                self.invoke(archive=self.case / "absent")
            self.assertFalse(self.out.exists())

    def test_runtime_code_graph_execution_drift_blocks_before_sources(self):
        for key, change in (("execution", {}), ("implementation_sha256", {}), ("graph_bindings", {}),
                            ("execution_packet_sha256", "a" * 64), ("candidate_outcomes_loaded", True)):
            report = deepcopy(self.report)
            report[key] = change
            reseal_predictions(self.pred, report)
            with self.assertRaises(ValueError):
                self.invoke(archive=self.case / "absent")
        actual = runner.runtime_binding("cpu")
        actual["machine"] = "invented_changed_machine"
        with patch.object(runner, "runtime_binding", return_value=actual), self.assertRaisesRegex(ValueError, "runtime"):
            self.invoke(archive=self.case / "absent")

    def test_changed_candidate_and_mask_bytes_fail_prepared_validator(self):
        for name in ("candidates.json", "split.json"):
            graph = self.case / name.replace(".", "_")
            shutil.copytree(self.graph, graph)
            (graph / name).write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "member changed"):
                self.invoke(graph=graph, archive=self.case / "absent")

    def test_freeze_missing_synthetic_only_corrupt_and_stale_resource_proofs_never_freeze(self):
        cases = [self.case / "missing/report.json", self.synthetic / "report.json"]
        bad = self.case / "bad_resource"
        shutil.copytree(self.resource, bad)
        resource = json.loads((bad / "report.json").read_text())
        resource["execution"]["machine"] = "changed_machine"
        write(bad / "report.json", reseal(resource))
        cases.append(bad / "report.json")
        for i, path in enumerate(cases):
            out = self.case / f"no_freeze_{i}"
            with self.assertRaises((ValueError, OSError)):
                freeze.freeze_comparison(self.graph, self.synthetic / "report.json", path, out, device="cpu")
            self.assertFalse(out.exists())
        (bad / "report.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "seal"):
            freeze.freeze_comparison(self.graph, self.synthetic / "report.json", bad / "report.json", self.case / "corrupt", device="cpu")

    def test_sealed_proof_with_changed_underlying_artifact_is_rejected(self):
        bad = self.case / "bad_synthetic"
        shutil.copytree(self.synthetic, bad)
        (bad / "rgcn_baseline_17_scores.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            freeze.freeze_comparison(self.graph, bad / "report.json", self.resource / "report.json", self.case / "no_freeze", device="cpu")

    def test_frozen_handoff_code_or_proof_corruption_blocks_scoring(self):
        for change in (lambda f: f.update(handoff_implementation_sha256={}), lambda f: f.update(fully_frozen=False),
                       lambda f: f["proofs"]["resource_check"].update(sha256="a" * 64)):
            frozen = self.case / f"changed_freeze_{len(list(self.case.iterdir()))}"
            shutil.copytree(self.frozen, frozen)
            envelope = json.loads((frozen / "execution.json").read_text())
            change(envelope)
            write(frozen / "execution.json", reseal(envelope))
            with self.assertRaises(ValueError):
                self.invoke(execution_packet=frozen, archive=self.case / "absent")

    def test_stale_handoff_and_contract_block_before_any_full_fit(self):
        for key in ("handoff_implementation_sha256", "reporting_contract"):
            frozen = self.case / ("stale_" + key)
            shutil.copytree(self.frozen, frozen)
            envelope = json.loads((frozen / "execution.json").read_text())
            envelope[key] = {}
            write(frozen / "execution.json", reseal(envelope))
            with patch.object(runner, "_fit") as fit:
                with self.assertRaisesRegex(ValueError, "handoff"):
                    runner.run(self.graph, self.case / ("blocked_" + key), device="cpu", execution_packet=frozen)
                fit.assert_not_called()

    def test_source_drift_stops_before_access_receipt_and_parser(self):
        bad = self.case / "changed.xlsx"
        bad.write_bytes(b"changed")
        with patch.object(score.original, "_author_pairs") as parser:
            with self.assertRaisesRegex(ValueError, "source fingerprints"):
                self.invoke(workbook=bad)
            parser.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_row_semantics_failure_retains_failure_and_outcome_access_receipt(self):
        with patch.object(score.inmc_outcomes, "materialize", side_effect=ValueError("contradictory assay rows")):
            with self.assertRaisesRegex(ValueError, "contradictory"):
                self.invoke()
        self.assertTrue((self.out / "exposure_started.json").exists())
        failure = json.loads((self.out / "failure.json").read_text())
        self.assertFalse(failure["performance_reporting_allowed"])
        self.assertFalse((self.out / "metrics.json").exists())

    def test_positive_negative_mixed_deltas_ties_zero_coverage_and_empty_strata(self):
        packet, _, _ = score.validate_predictions(self.graph, self.frozen, self.pred, device="cpu")
        materialized = score.inmc_outcomes.materialize(self.panel, packet["candidates"],
                [packet["candidates"][0]["original_genes"], packet["candidates"][3]["original_genes"]])
        coverage = deepcopy(packet["coverage"])
        for row in coverage["rows"]:
            row["covered_endpoint_count"] = row["coverage_only_score"] = 0
        def arm_scores(positive_high):
            return {row["id"]: (1.0 if (i == 0) == positive_high else 0.0) for i, row in enumerate(packet["candidates"])}
        for expected in ("positive", "negative", "mixed"):
            scores = {runner.ARMS[0]: {}, runner.ARMS[1]: {}}
            for seed in runner.TRAINING["seeds"]:
                baseline_high = expected == "negative" or (expected == "mixed" and seed == 43)
                scores[runner.ARMS[0]][seed] = arm_scores(baseline_high)
                scores[runner.ARMS[1]][seed] = arm_scores(not baseline_high)
            result = score.score_fixed(materialized, scores, coverage)
            deltas = [v["average_precision"] for v in result["paired_comparison"]["deltas_by_seed"].values()]
            self.assertTrue(all(d > 0 for d in deltas) if expected == "positive" else
                            all(d < 0 for d in deltas) if expected == "negative" else min(deltas) < 0 < max(deltas))
            self.assertAlmostEqual(result["paired_comparison"]["mean_deltas"]["average_precision"], sum(deltas) / 3)
            self.assertAlmostEqual(result["coverage_only_diagnostic"]["metrics"]["average_precision"], 1 / 3)
            self.assertEqual(result["coverage_only_diagnostic"]["metrics"]["roc_auc"], .5)
            self.assertEqual(result["reactome_endpoint_coverage_strata"]["1"]["status"], "empty")
            self.assertIsNone(result["reactome_endpoint_coverage_strata"]["2"]["metrics_by_arm_seed"])
        with patch.object(freeze, "reporting_contract", return_value={**freeze.reporting_contract(), "primary_eligible_pairs": 1751}):
            with self.assertRaisesRegex(ValueError, "denominator"):
                score.score_fixed(materialized, scores, coverage)


if __name__ == "__main__":
    unittest.main()
