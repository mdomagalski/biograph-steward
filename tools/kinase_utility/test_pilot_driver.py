"""Invented-only integration of local transport, sealing and scoring boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import loadmat, savemat, whosmat

from biograph_steward.cohort_mapping import SOURCES, collect_registry
import pilot_driver as driver
from test_pilot_methods import encoded, fixture, ks


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def setup(root):
    root = Path(root).resolve()
    registry, captured = fixture()
    # Regenerate the fake registry bytes from its original invented records.
    hgnc = encoded([{k: v for k, v in row.items() if k != "source_row"} for row in registry.genes.values()])
    columns = ["Entry", "Gene Names (primary)", "Gene Names (synonym)", "HGNC", "GeneID", "Organism (ID)", "Protein names"]
    uniprot = encoded([{k: row[k] for k in columns} for row in registry.proteins.values()])
    reg = root / "registry"
    collect_registry(reg, transport=lambda url: (hgnc if "googleapis" in url else uniprot, {"fixture": "INVENTED"}))
    sequence = root / "sequence.tsv"; sequence.write_bytes(encoded(list(captured.values())))
    conditions = [f"{cell}.D{n}" for n in (1, 2, 3) for cell in ("C1", "C2")]
    roster = root / "conditions.json"; dump(roster, conditions)
    matrix = root / "measurements.csv"
    matrix.write_bytes(encoded([{"ID": "ALPHA_S2|ALPHA|S2", **dict(zip(conditions, ["0", "2", "3", "NA", "-1", "1"]))},
        {"ID": "BETA_T3|BETA|T3", **dict(zip(conditions, ["-1", "NA", "0", "1", "2", "NaN"]))}], ","))
    prior = root / "prior"; prior.mkdir()
    enzymes = [{"enzyme": "UniProtKB:P00001", "gene": "ALPHA", "hgnc_id": "HGNC:1"},
               {"enzyme": "UniProtKB:P00002", "gene": "BETA", "hgnc_id": "HGNC:2"}]
    dump(prior / "enzyme_roster.json", enzymes)
    links = [ks(host="UniProtKB:P00001"), ks(enzyme="UniProtKB:P00002", host="UniProtKB:P00002", site="T3")]
    (prior / "links.jsonl").write_text("".join(json.dumps(row) + "\n" for row in links))
    pp = {}
    for arm, filename in driver.PPI_FILES.items():
        p = prior / filename
        header = "pair_id\tsubject\tobject\tweight\n"
        p.write_text(header + ("INVENTED-PAIR\tUniProtKB:P00001\tUniProtKB:P00002\t0.4\n" if arm in {"unpruned", "primary"} else ""))
        pp[arm] = p
    reg_manifest = json.loads((reg / "manifest.json").read_text())
    prior_receipt = driver.sealed({"registry_sha256": reg_manifest["registry_sha256"],
        "output_files_sha256": {p.name: driver.sha(p) for p in prior.iterdir()},
        "input_files_sha256": {}, "module_files_sha256": {}})
    dump(prior / "receipt.json", prior_receipt)
    reference = root / "references.csv"
    reference.write_bytes(encoded([
        {"id": "C1.D1", "cell_line": "C1", "drug": "D1", "sign": "1", "target": "ALPHA"},
        {"id": "C2.D1", "cell_line": "C2", "drug": "D1", "sign": "1", "target": "ALPHA"},
        {"id": "C1.D2", "cell_line": "C1", "drug": "D2", "sign": "1", "target": "UNKNOWN"},
        {"id": "C1.D3", "cell_line": "C2", "drug": "D3", "sign": "1", "target": "ALPHA"},
        {"id": "C2.D3", "cell_line": "C2", "drug": "SWAPPED", "sign": "1", "target": "ALPHA"},
        {"id": "C1.OUTSIDE", "cell_line": "C1", "drug": "OUTSIDE", "sign": "1", "target": "ALPHA"}], ","))
    roles = {"measurement_csv": str(matrix), "condition_roster": str(roster), "registry_directory": str(reg),
        "sequence_reference": str(sequence), "prior_directory": str(prior),
        "ppi_paths": {arm: str(p) for arm, p in pp.items()}}
    paths = [matrix, roster, sequence, *reg.iterdir(), *prior.iterdir(), *driver.code_paths()]
    freeze = driver.sealed({"format": driver.FORMATS["freeze"],
        "files_sha256": {str(p.resolve()): driver.sha(p) for p in paths},
        "sealed_json": {str(prior / "receipt.json"): prior_receipt["content_sha256"],
                        str(reg / "manifest.json"): reg_manifest["registry_sha256"]},
        "expected_condition_count": 6, "expected_cells": ["C1", "C2"],
        "condition_cell_prefixes": {"C1": "C1.", "C2": "C2."}, "condition_drug_delimiter": ".",
        "reference_csv_sha256": driver.sha(reference), "input_roles": roles})
    # Registry manifest has its pre-existing registry_sha256 contract rather than
    # content_sha256, so it is raw-byte pinned and checked by load_registry().
    freeze["sealed_json"].pop(str(reg / "manifest.json"))
    freeze = driver.sealed({k: v for k, v in freeze.items() if k != "content_sha256"})
    freeze_path = root / "freeze.json"; dump(freeze_path, freeze)
    return {"execution_freeze": freeze_path, "measurement_csv": matrix, "condition_roster": roster,
        "registry_directory": reg, "sequence_reference": sequence, "prior_directory": prior,
        "ppi_paths": pp, "output": root / "prepared"}, reference


def fake_output(root, **overrides):
    array = np.array([[0, 1, 2, np.nan, -1, 3], [1, 0, -1, 2, 0, np.nan]], dtype=np.float64)
    values = {name: array.copy() for name in driver.MAT_TO_ARM}
    values.update(overrides)
    path = Path(root) / "model_output.mat"; savemat(path, values, format="5")
    return path


class DriverTests(unittest.TestCase):
    def test_complete_invented_flow_keeps_all_conditions_and_never_reads_reference_before_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, reference = setup(tmp)
            original = Path.read_bytes
            def guarded(path):
                if path.resolve() == reference.resolve():
                    raise AssertionError("Reference body accessed before prediction seal.")
                return original(path)
            with patch.object(Path, "read_bytes", guarded):
                prepared = driver.prepare(**args)
                output = fake_output(tmp)
                prediction = driver.seal_predictions(prepared_directory=args["output"], output_mat=output,
                    output=Path(tmp) / "predictions")
            self.assertFalse(prepared["reference_metadata_accessed"])
            self.assertFalse(prediction["reference_metadata_accessed"])
            numeric = loadmat(args["output"] / "numeric_input.mat")
            self.assertEqual({k for k in numeric if not k.startswith("__")}, driver.INPUT_VARS)
            self.assertEqual(numeric["X"].shape, (2, 6))
            self.assertEqual(numeric["X"][0, 0], 0)
            self.assertEqual(numeric["W_primary"].toarray()[0, 1], .4)  # No extra1e-3 scaling.
            self.assertEqual(numeric["W_native"].nnz, 0)
            raw_predictions = json.loads((Path(tmp) / "predictions/raw_predictions.json").read_text())
            self.assertEqual(len(raw_predictions), 7)
            self.assertTrue(all(len(arm) == 6 for arm in raw_predictions.values()))
            self.assertEqual(raw_predictions["raw_mean"]["C1.D1"]["ALPHA"], 0)
            self.assertIsNone(raw_predictions["raw_mean"]["C2.D2"]["ALPHA"])
            result = driver.score(sealed_directory=Path(tmp) / "predictions", reference_csv=reference,
                                  output=Path(tmp) / "scored")
            self.assertEqual(result["reference_scope_exclusions"], 3)
            exclusions = driver.ordinary_jsonl(Path(tmp) / "scored/reference_scope_exclusions.jsonl")
            self.assertEqual({r["reason"] for r in exclusions}, {
                "reference_id_outside_fixed_source_condition_roster", "reference_cell_does_not_match_source_condition",
                "reference_drug_does_not_match_source_condition"})
            conditions = driver.ordinary_jsonl(Path(tmp) / "scored/native_condition_ledger.jsonl")
            self.assertEqual(len(conditions), 6)
            by_condition = {r["condition"]: r for r in conditions}
            self.assertEqual(by_condition["C2.D2"]["status"], "no_reference_metadata")
            self.assertEqual(by_condition["C1.D2"]["status"], "metadata_present_no_qualified_atomic_targets")
            self.assertEqual(by_condition["C1.D3"]["status"], "metadata_present_outside_source_context")
            drugs = json.loads((Path(tmp) / "scored/drug_ledger.json").read_text())
            all_drugs = {r["reported_drug"]: r for r in drugs["all_original_metadata_drugs"]}
            self.assertEqual(all_drugs["D2"]["qualified_condition_ids"], [])
            self.assertEqual(all_drugs["SWAPPED"]["qualified_atomic_targets"], 0)
            self.assertEqual(drugs["complete_primary_drugs"], ["D1"])
            assessment = json.loads((Path(tmp) / "scored/assessment.json").read_text())
            self.assertEqual(assessment["primary_population"]["primary_condition_target_cases"], 2)
            self.assertFalse(assessment["coverage_floor"]["passed"])
            driver.verify_outputs(Path(tmp) / "scored", result)
            with self.assertRaises(FileExistsError):
                driver.prepare(**args)

    def test_score_requires_sealed_predictions_before_reference_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, reference = setup(tmp); driver.prepare(**args)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("Unexpected body read")):
                with self.assertRaises(ValueError):
                    driver.score(sealed_directory=args["output"], reference_csv=reference, output=Path(tmp) / "scored")

    def test_swapped_ppi_roles_rejected_even_if_hash_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, _ = setup(tmp)
            args["ppi_paths"]["native"], args["ppi_paths"]["primary"] = args["ppi_paths"]["primary"], args["ppi_paths"]["native"]
            with self.assertRaisesRegex(ValueError, "input roles"):
                driver.prepare(**args)
            # Even re-freezing the bad role labels cannot evade the source file contract.
            frozen = json.loads(args["execution_freeze"].read_text())
            frozen["input_roles"]["ppi_paths"] = {k: str(v) for k, v in args["ppi_paths"].items()}
            dump(args["execution_freeze"], driver.sealed({k: v for k, v in frozen.items() if k != "content_sha256"}))
            with self.assertRaisesRegex(ValueError, "exact final-prior filename"):
                driver.prepare(**args)

    def test_changed_source_or_code_pin_stops_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, _ = setup(tmp)
            args["sequence_reference"].write_text("changed")
            with patch.object(driver.methods, "prepare_measurements", side_effect=AssertionError("Must stop before preparation")):
                with self.assertRaisesRegex(ValueError, "Frozen input/code bytes changed"):
                    driver.prepare(**args)

    def test_seal_rejects_inf_wrong_shapes_and_unexpected_arrays_without_dropping(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, _ = setup(tmp); driver.prepare(**args)
            for i, changes in enumerate(({"A_raw_mean": np.full((2, 6), np.inf)},
                                         {"A_raw_mean": np.zeros((1, 6))},
                                         {"unexpected": np.zeros((2, 6))})):
                output = fake_output(tmp, **changes)
                with self.assertRaises(ValueError):
                    driver.seal_predictions(prepared_directory=args["output"], output_mat=output,
                                            output=Path(tmp) / f"predictions_{i}")
                self.assertFalse((Path(tmp) / f"predictions_{i}").exists())

    def test_tampered_prediction_cannot_trigger_reference_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, reference = setup(tmp); driver.prepare(**args)
            driver.seal_predictions(prepared_directory=args["output"], output_mat=fake_output(tmp),
                                    output=Path(tmp) / "predictions")
            (Path(tmp) / "predictions/raw_predictions.json").write_text("{}")
            original = Path.read_bytes
            def guard(path):
                if path.resolve() == reference.resolve():
                    raise AssertionError("Must verify sealed predictions first.")
                return original(path)
            with patch.object(Path, "read_bytes", guard):
                with self.assertRaisesRegex(ValueError, "Immutable output changed"):
                    driver.score(sealed_directory=Path(tmp) / "predictions", reference_csv=reference,
                                 output=Path(tmp) / "scored")


if __name__ == "__main__":
    unittest.main()
