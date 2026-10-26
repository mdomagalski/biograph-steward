"""Prediction-runner boundaries; all fixtures are invented and contain no assays."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from biograph_steward.client import digest
from biograph_steward.file_utils import sha

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_inmc_comparison.py"
SPEC = importlib.util.spec_from_file_location("inmc_prediction_runner", MODULE_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def table(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("subject\tpredicate\tobject\n" + "".join("\t".join(row) + "\n" for row in rows))


def seal(folder):
    report = {"format": "synthetic-packet", "data_kind": "synthetic_demo",
              "files": {str(path.relative_to(folder)): sha(path) for path in sorted(folder.rglob("*"))
                        if path.is_file() and path.name != "report.json"}}
    report["content_sha256"] = digest(report)
    write(folder / "report.json", report)
    return report


def frozen_fields(folder, execution):
    root = MODULE_PATH.parents[1]
    (folder / "assay_contract.json").write_bytes((root / runner.ASSAY_CONTRACT).read_bytes())
    return {"fully_frozen": True, "runner_sha256": sha(MODULE_PATH), "execution": execution,
            "scoring_implementation": {"path": runner.SCORER, "sha256": sha(root / runner.SCORER)},
            "assay_contract_sha256": sha(root / runner.ASSAY_CONTRACT)}


def invented_execution():
    return {"device": "cpu", "python": "synthetic", "packages": {name: "synthetic" for name in runner.PACKAGES},
            "cuda_runtime": None}


def fixture(folder):
    """Six genes on an invented ring; one reserved pair, one development pair."""
    genes = [f"ENSG{i:011d}" for i in range(1, 7)]
    proteins = ["UniProtKB:TEST1", "UniProtKB:TEST2"]
    terms = ["GO:9000001", "GO:9000002"]
    entities = [{"id": value, "type": kind} for kind, values in
                (("gene", genes), ("protein", proteins), ("go_term", terms)) for value in values]
    write(folder / "entities.json", entities)
    write(folder / "relations.json", [{"id": name} for name in sorted(runner.RELATIONS)])
    supervision = [(genes[i], "interacts", genes[(i + 1) % 6]) for i in range(6)]
    supervision += [(b, r, a) for a, r, b in supervision]
    baseline = supervision + [(genes[0], "reviewed_product_context", proteins[0]),
                              (genes[2], "reviewed_product_context", proteins[1]),
                              (proteins[0], "pharos_cc_annotation", terms[0]),
                              (proteins[1], "pharos_cc_annotation", terms[0])]
    for name, triples in (("supervision.tsv", supervision), ("arms/scaffold.tsv", supervision),
                          ("arms/baseline.tsv", baseline),
                          ("arms/enriched.tsv", baseline + [(terms[0], "go_is_a", terms[1])])):
        table(folder / name, triples)
    write(folder / "candidates.json", [{"id": "invented_reserved", "original_genes": [genes[0], genes[2]],
                                       "self_pair": False}])
    write(folder / "development_pairs.json", [[genes[1], genes[3]]])
    write(folder / "split.json", {"masked_gene_pairs": [[genes[0], genes[2]], [genes[1], genes[3]]]})
    write(folder / "protocol.json", {"fully_frozen": False, "model": runner.MODEL, "training": runner.TRAINING})
    seal(folder)
    return genes


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "graph"
        self.genes = fixture(self.folder)

    def change(self, name, function, *, reseal=True):
        path = self.folder / name
        value = json.loads(path.read_text())
        function(value)
        write(path, value)
        if reseal:
            seal(self.folder)

    def test_resource_validation_preserves_vocabulary_and_candidates(self):
        before = sha(self.folder / "report.json")
        packet = runner.validate_packet(self.folder, resource_smoke=True)
        self.assertEqual(len(packet["entities"]), 10)
        self.assertEqual(len(packet["supervision"]), 12)
        self.assertEqual(packet["candidates"][0]["id"], "invented_reserved")
        self.assertEqual(before, sha(self.folder / "report.json"))

    def test_full_execution_requires_freeze_and_receipts(self):
        with self.assertRaisesRegex(ValueError, "frozen protocol"):
            runner.validate_packet(self.folder)
        self.change("protocol.json", lambda p: p.update(frozen_fields(self.folder, invented_execution())))
        with self.assertRaisesRegex(ValueError, "hierarchy_smoke"):
            runner.validate_packet(self.folder)

    def test_full_validates_bound_smoke_content_and_actual_graph(self):
        files = json.loads((self.folder / "report.json").read_text())["files"]
        hierarchy = {"status": "passed", "synthetic_only": True}
        execution = invented_execution()
        resource = {"status": "passed", "resource_smoke": True, "runner_sha256": sha(MODULE_PATH),
                    "execution": execution,
                    "graph_input_files": {key: files[key] for key in runner.REQUIRED if key != "protocol.json"}}
        write(self.folder / "validation/hierarchy_smoke.json", hierarchy)
        write(self.folder / "validation/resource_smoke.json", resource)
        def update(p):
            p.update(frozen_fields(self.folder, execution))
            for name in ("hierarchy_smoke", "resource_smoke"):
                p[name] = {"status": "passed", "report_sha256": sha(self.folder / f"validation/{name}.json")}
        self.change("protocol.json", update)
        runner.validate_packet(self.folder)
        resource["graph_input_files"]["candidates.json"] = "a" * 64
        write(self.folder / "validation/resource_smoke.json", resource)
        self.change("protocol.json", update)
        with self.assertRaisesRegex(ValueError, "different graph inputs"):
            runner.validate_packet(self.folder)

    def test_hash_drift_detected_before_runtime(self):
        self.change("candidates.json", lambda rows: rows[0].update(id="changed"), reseal=False)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_seal_drift_detected(self):
        path = self.folder / "report.json"
        report = json.loads(path.read_text())
        report["status"] = "tampered"
        write(path, report)
        with self.assertRaisesRegex(ValueError, "seal"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_budget_mutation_and_nonboolean_freeze_rejected(self):
        self.change("protocol.json", lambda p: p["training"].update(num_epochs=1))
        with self.assertRaisesRegex(ValueError, "budget"):
            runner.validate_packet(self.folder, resource_smoke=True)
        self.change("protocol.json", lambda p: p.update(training=copy.deepcopy(runner.TRAINING), fully_frozen=1))
        with self.assertRaisesRegex(ValueError, "boolean"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_reserved_reverse_in_any_arm_is_rejected(self):
        a, b = self.genes[2], self.genes[0]
        for name in ("supervision.tsv", "arms/scaffold.tsv", "arms/baseline.tsv", "arms/enriched.tsv"):
            with (self.folder / name).open("a") as handle:
                handle.write(f"{a}\tinteracts\t{b}\n")
        seal(self.folder)
        with self.assertRaisesRegex(ValueError, "Held-out"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_development_overlap_and_duplicate_pair_rejected(self):
        self.change("development_pairs.json", lambda rows: rows.__setitem__(0, [self.genes[2], self.genes[0]]))
        with self.assertRaisesRegex(ValueError, "overlaps"):
            runner.validate_packet(self.folder, resource_smoke=True)
        self.change("candidates.json", lambda rows: rows.append({"id": "reverse", "original_genes": [self.genes[2], self.genes[0]]}))
        with self.assertRaisesRegex(ValueError, "Duplicate pair"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_equivalence_masks_cover_literals_and_are_enforced(self):
        self.change("split.json", lambda p: p["masked_gene_pairs"].pop())
        with self.assertRaisesRegex(ValueError, "omits literal"):
            runner.validate_packet(self.folder, resource_smoke=True)
        self.change("split.json", lambda p: p.update(masked_gene_pairs=[
            [self.genes[0], self.genes[2]], [self.genes[1], self.genes[3]], [self.genes[0], self.genes[1]]]))
        with self.assertRaisesRegex(ValueError, "Held-out"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_outcome_fields_and_incorrect_self_flag_rejected(self):
        self.change("candidates.json", lambda rows: rows[0].update(score_assay1="INVENTED"))
        with self.assertRaisesRegex(ValueError, "Outcome"):
            runner.validate_packet(self.folder, resource_smoke=True)
        self.change("candidates.json", lambda rows: (rows[0].pop("score_assay1"), rows[0].update(self_pair=True)))
        with self.assertRaisesRegex(ValueError, "self-pair"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_nonhierarchy_enrichment_and_duplicate_rows_rejected(self):
        path = self.folder / "arms/enriched.tsv"
        with path.open("a") as handle:
            handle.write(f"{self.genes[1]}\treviewed_product_context\tUniProtKB:TEST1\n")
        seal(self.folder)
        with self.assertRaisesRegex(ValueError, "additive"):
            runner.validate_packet(self.folder, resource_smoke=True)
        with path.open("a") as handle:
            handle.write(f"{self.genes[1]}\treviewed_product_context\tUniProtKB:TEST1\n")
        seal(self.folder)
        with self.assertRaisesRegex(ValueError, "duplicate triples"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_symlink_inventory_escape_rejected(self):
        path = self.folder / "candidates.json"
        outside = Path(self.temp.name) / "outside.json"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            runner.validate_packet(self.folder, resource_smoke=True)

    def test_cli_has_no_outcome_or_budget_override_option(self):
        result = subprocess.run([sys.executable, str(MODULE_PATH), "--help"], capture_output=True, text=True, check=True)
        self.assertIn("--resource-smoke", result.stdout)
        self.assertNotIn("--outcomes", result.stdout)
        self.assertNotIn("--epochs", result.stdout)

    def test_runtime_device_drift_rejected(self):
        execution = invented_execution()
        runner.check_execution({"execution": execution}, execution)
        changed = copy.deepcopy(execution)
        changed["device"] = "cuda:0"
        with self.assertRaisesRegex(ValueError, "runtime/device differs"):
            runner.check_execution({"execution": execution}, changed)
        changed = copy.deepcopy(execution)
        changed["packages"]["torch"] = "different"
        with self.assertRaisesRegex(ValueError, "runtime/device differs"):
            runner.check_execution({"execution": execution}, changed)

    def test_stale_scorer_or_assay_contract_blocks_full_execution(self):
        self.change("protocol.json", lambda p: p.update(frozen_fields(self.folder, invented_execution())))
        self.change("protocol.json", lambda p: p["scoring_implementation"].update(sha256="a" * 64))
        with self.assertRaisesRegex(ValueError, "scoring implementation"):
            runner.validate_packet(self.folder)
        self.change("protocol.json", lambda p: p.update(frozen_fields(self.folder, invented_execution())))
        self.change("protocol.json", lambda p: p.update(assay_contract_sha256="a" * 64))
        with self.assertRaisesRegex(ValueError, "assay contract"):
            runner.validate_packet(self.folder)


@unittest.skipUnless(os.environ.get("BIOGRAPH_TEST_GRAPH_ML") == "1", "Optional pinned PyKEEN synthetic runtime")
class RuntimeTests(unittest.TestCase):
    def test_resource_smoke_scores_development_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root / "graph")
            # An isolated gene inside the mapped index range must remain present;
            # native graph-based sampling fails this case in PyKEEN 1.11.1.
            entities_path = root / "graph/entities.json"
            entities = json.loads(entities_path.read_text())
            entities.append({"id": "ENSG00000000000", "type": "gene"})
            write(entities_path, entities)
            seal(root / "graph")
            report = runner.run(root / "graph", root / "result", device="cpu", resource_smoke=True)
            self.assertEqual(report["status"], "passed")
            self.assertFalse(report["candidate_outcomes_loaded"])
            self.assertEqual(report["candidate_pairs_scored"], 0)
            self.assertEqual(len(report["arms"]), 2)
            for arm in report["arms"]:
                rows = json.loads((root / "result" / arm["scores_file"]).read_text())
                self.assertEqual({row["partition"] for row in rows}, {"development"})
                self.assertEqual(arm["optimizer_steps"], 1)
                self.assertEqual(arm["score_rows"], 1)
            self.assertEqual(report["arms"][0]["initial_parameters_sha256"],
                             report["arms"][1]["initial_parameters_sha256"])
            self.assertEqual(report["arms"][0]["positive_batch_sha256"], report["arms"][1]["positive_batch_sha256"])

    def test_full_fixed_budget_on_invented_graph(self):
        import platform
        from importlib.metadata import version
        import torch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root / "graph")
            # This synthetic contract fixture exercises guards and all four model
            # paths. Its invented receipts do not certify a biological graph.
            graph_files = json.loads((root / "graph/report.json").read_text())["files"]
            execution = {"device": "cpu", "python": platform.python_version(),
                         "packages": {name: version(name) for name in runner.PACKAGES}, "cuda_runtime": torch.version.cuda}
            write(root / "graph/validation/hierarchy_smoke.json", {"status": "passed", "synthetic_test_fixture": True})
            write(root / "graph/validation/resource_smoke.json", {
                "status": "passed", "resource_smoke": True, "runner_sha256": sha(MODULE_PATH),
                "execution": execution,
                "graph_input_files": {key: graph_files[key] for key in runner.REQUIRED if key != "protocol.json"},
                "synthetic_test_fixture": True})
            protocol_path = root / "graph/protocol.json"
            protocol = json.loads(protocol_path.read_text())
            protocol.update(frozen_fields(root / "graph", execution))
            for name in ("hierarchy_smoke", "resource_smoke"):
                protocol[name] = {"status": "passed", "report_sha256": sha(root / f"graph/validation/{name}.json")}
            write(protocol_path, protocol)
            seal(root / "graph")
            report = runner.run(root / "graph", root / "result", device="cpu")
            self.assertEqual(len(report["arms"]), 12)
            self.assertEqual({arm["arm"] for arm in report["arms"]}, {
                "rgcn_scaffold", "rgcn_baseline", "rgcn_enriched", "complex_scaffold"})
            self.assertEqual({arm["optimizer_steps"] for arm in report["arms"]}, {20})
            self.assertEqual(report["candidate_pairs_scored"], 1)
            self.assertFalse(report["biological_accuracy_measured"])
            for arm in report["arms"]:
                rows = json.loads((root / "result" / arm["scores_file"]).read_text())
                self.assertEqual({row["partition"] for row in rows}, {"candidate", "development"})
                self.assertEqual(arm["score_rows"], 2)


if __name__ == "__main__":
    unittest.main()
