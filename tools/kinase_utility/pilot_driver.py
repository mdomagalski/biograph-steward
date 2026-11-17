"""Thin local prepare/seal/score transport; no network, shell or inference.

Root supplies and freezes every input path/hash before real measurement access.
Reference CSV has a hash commitment only and is accepted solely by score().
"""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np
from scipy import sparse
from scipy.io import loadmat, savemat, whosmat

for ancestor in Path(__file__).resolve().parents:
    if (ancestor / "biograph_steward/cohort_mapping.py").is_file():
        if str(ancestor) not in sys.path:
            sys.path.insert(0, str(ancestor))
        break
import pilot_methods as methods
from biograph_steward import cohort_mapping
from biograph_steward.cohort_mapping import load_registry

PROJECT_ROOT = Path(cohort_mapping.__file__).resolve().parent.parent
STATS_DIRECTORY = (Path(__file__).resolve().parent if Path(__file__).resolve().with_name("pilot_stats.py").is_file()
                   else PROJECT_ROOT / "runs/scientific_accuracy_round2_20261112/reference_review")
if str(STATS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(STATS_DIRECTORY))
import pilot_stats as stats

MAT_TO_ARM = {"A_raw_mean": "raw_mean", "A_raw_zscore": "raw_zscore",
    "A_rokai_ks_only_zscore": "rokai_ks_only_zscore", "A_rokai_unpruned_zscore": "rokai_unpruned_zscore",
    "A_rokai_native_zscore": "rokai_native_zscore", "A_rokai_primary_zscore": "rokai_primary_zscore",
    "A_rokai_ne_zscore": "rokai_ne_zscore"}
INPUT_VARS = {"X", "Wkin2site", "Wsite2site", "W_unpruned", "W_native", "W_primary", "W_ne"}
PPI_FILES = {"unpruned": "unpruned_native_weighted_kinase_PPI.tsv",
    "native": "native_top80_native_weighted_kinase_PPI.tsv",
    "primary": "human_experimental_top80_native_weighted_kinase_PPI.tsv",
    "ne": "ne_top80_native_weighted_kinase_PPI.tsv"}
FORMATS = {"freeze": "biograph-steward.pilot-execution-freeze.v1",
    "prepared": "biograph-steward.pilot-prepared.v1", "sealed": "biograph-steward.pilot-predictions-sealed.v1",
    "scored": "biograph-steward.pilot-scored.v1"}


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), "Expected an ordinary input file: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sealed(value):
    value = dict(value)
    value["content_sha256"] = digest(value)
    return value


def write_json(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def jsonl(path, rows):
    with Path(path).open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def load_sealed(path, expected_format=None):
    value = json.loads(Path(path).read_text())
    need(isinstance(value, dict) and value.get("content_sha256") == digest(
        {k: v for k, v in value.items() if k != "content_sha256"}), "Broken JSON content seal.")
    if expected_format:
        need(value.get("format") == expected_format, "Unexpected receipt format.")
    return value


def code_paths():
    # Directly used project code is mandatory; root may pin further dependencies.
    source = Path(__file__).resolve().parent / "rokai_source_metadata"
    return [Path(__file__).resolve(), Path(methods.__file__).resolve(), Path(stats.__file__).resolve(),
            Path(cohort_mapping.__file__).resolve(),
            PROJECT_ROOT / "biograph_steward/cptac.py", PROJECT_ROOT / "biograph_steward/client.py",
            Path(__file__).resolve().with_name("run_numeric_batch.m"), source / "LICENSE",
            *sorted((source / "src/rokai").glob("*.m"))]


def verify_freeze(path):
    path = Path(path).resolve()
    frozen = load_sealed(path, FORMATS["freeze"])
    pins = frozen.get("files_sha256")
    need(isinstance(pins, dict) and pins, "Freeze must pin explicit input/code files.")
    need(all(Path(p).is_absolute() for p in pins), "Freeze paths must be explicit absolute paths.")
    for p, expected in pins.items():
        need(sha(p) == expected, "Frozen input/code bytes changed: " + p)
    for p in code_paths():
        need(str(p) in pins, "Required driver/helper/dependency code was not frozen: " + str(p))
    for p, expected in frozen.get("sealed_json", {}).items():
        need(p in pins and load_sealed(p)["content_sha256"] == expected,
             "Frozen protocol/source receipt seal differs.")
    need(type(frozen.get("expected_condition_count")) is int and frozen["expected_condition_count"] > 0,
         "Declare the fixed source condition count.")
    cells = frozen.get("expected_cells")
    need(isinstance(cells, list) and len(cells) == len(set(cells)) == 2
         and all(isinstance(c, str) and c for c in cells), "Declare the exact two-cell roster.")
    prefixes = frozen.get("condition_cell_prefixes")
    need(isinstance(prefixes, dict) and set(prefixes) == set(cells)
         and all(isinstance(p, str) and p for p in prefixes.values())
         and len(set(prefixes.values())) == 2, "Freeze the verified source-header cell prefixes explicitly.")
    need(frozen.get("condition_drug_delimiter") == ".", "Freeze the author's literal dot-separated source ID contract.")
    roles = frozen.get("input_roles")
    need(isinstance(roles, dict) and set(roles) == {"measurement_csv", "condition_roster", "registry_directory",
        "sequence_reference", "prior_directory", "ppi_paths"}, "Bind every preparation input role explicitly.")
    need(all(Path(roles[k]).is_absolute() for k in roles if k != "ppi_paths")
         and isinstance(roles["ppi_paths"], dict) and set(roles["ppi_paths"]) == set(PPI_FILES)
         and all(Path(p).is_absolute() for p in roles["ppi_paths"].values()), "Input roles require absolute paths.")
    need(re.fullmatch(r"[0-9a-f]{64}", frozen.get("reference_csv_sha256", "")),
         "Commit the opaque reference byte hash without reading reference rows.")
    return frozen


def pinned(path, frozen):
    path = Path(path).resolve()
    need(str(path) in frozen["files_sha256"] and sha(path) == frozen["files_sha256"][str(path)],
         "Input is absent from the execution freeze or changed: " + str(path))
    return path


def verify_outputs(directory, receipt):
    directory = Path(directory)
    for name, expected in receipt["output_files_sha256"].items():
        need(Path(name).name == name, "Receipt output name is not a local basename.")
        need(sha(directory / name) == expected, "Immutable output changed: " + name)


def ordinary_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _ppi(path, enzymes):
    import csv
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t", strict=True)
        need(reader.fieldnames == ["pair_id", "subject", "object", "weight"], "Unexpected native PPI TSV schema.")
        rows = list(reader)
    seen_ids, by_pair = set(), {}
    for row in rows:
        need(None not in row and all(v is not None for v in row.values()), "Malformed PPI row.")
        a, b = row["subject"], row["object"]
        pair = tuple(sorted((a, b)))
        need(a in enzymes and b in enzymes and a != b and row["pair_id"]
             and row["pair_id"] not in seen_ids and pair not in by_pair, "PPI roster/self/duplicate conflict.")
        weight = Decimal(row["weight"])
        need(weight.is_finite() and 0 <= weight <= 1, "Native PPI weights must be normalized [0,1].")
        seen_ids.add(row["pair_id"])
        by_pair[pair] = (row["pair_id"], weight)
    index = {enzyme: i for i, enzyme in enumerate(enzymes)}
    rr, cc, values = [], [], []
    for (a, b), (_, weight) in sorted(by_pair.items()):
        rr.extend((index[a], index[b])); cc.extend((index[b], index[a])); values.extend((float(weight), float(weight)))
    return sparse.csc_matrix((values, (rr, cc)), shape=(len(enzymes), len(enzymes)), dtype=np.float64), by_pair


def prepare(*, execution_freeze, measurement_csv, condition_roster, registry_directory,
            sequence_reference, prior_directory, ppi_paths, output):
    frozen = verify_freeze(execution_freeze)
    supplied_roles = {"measurement_csv": str(Path(measurement_csv).resolve()),
        "condition_roster": str(Path(condition_roster).resolve()), "registry_directory": str(Path(registry_directory).resolve()),
        "sequence_reference": str(Path(sequence_reference).resolve()), "prior_directory": str(Path(prior_directory).resolve()),
        "ppi_paths": {arm: str(Path(p).resolve()) for arm, p in ppi_paths.items()}}
    need(supplied_roles == frozen["input_roles"], "Preparation input roles differ from the execution freeze.")
    measurement_csv, condition_roster, sequence_reference = [pinned(p, frozen) for p in
        (measurement_csv, condition_roster, sequence_reference)]
    prior_directory, registry_directory = Path(prior_directory).resolve(), Path(registry_directory).resolve()
    prior_receipt_path = pinned(prior_directory / "receipt.json", frozen)
    prior = load_sealed(prior_receipt_path)
    verify_outputs(prior_directory, prior)
    for name in ("links.jsonl", "enzyme_roster.json"):
        pinned(prior_directory / name, frozen)
    for name in ("manifest.json", *cohort_mapping.SOURCES):
        pinned(registry_directory / name, frozen)
    registry_manifest, registry = load_registry(registry_directory)
    need(prior.get("registry_sha256") == registry_manifest["registry_sha256"], "Prior/measurement registry differs.")
    for mapping_name in ("input_files_sha256", "module_files_sha256"):
        for name, expected in prior.get(mapping_name, {}).items():
            path = Path(name) if Path(name).is_absolute() else PROJECT_ROOT / name
            need(sha(path) == expected, "Final prior upstream input/code changed: " + name)
    conditions = json.loads(condition_roster.read_text())
    need(isinstance(conditions, list) and len(conditions) == frozen["expected_condition_count"]
         and len(set(conditions)) == len(conditions) and all(isinstance(c, str) and c for c in conditions),
         "Header-only condition roster differs from the fixed source population.")
    condition_cells, condition_drugs = {}, {}
    for condition in conditions:
        matches = [cell for cell, prefix in frozen["condition_cell_prefixes"].items() if condition.startswith(prefix)]
        need(len(matches) == 1, "Source condition does not have one explicitly frozen cell prefix.")
        parts = condition.split(frozen["condition_drug_delimiter"])
        need(len(parts) == 2 and all(parts) and parts[0] == matches[0], "Source ID does not match the documented cell.drug contract.")
        condition_cells[condition] = matches[0]
        condition_drugs[condition] = parts[1]
    sequence = methods.parse_sequence_reference(sequence_reference.read_bytes())
    links = ordinary_jsonl(prior_directory / "links.jsonl")
    roster = json.loads((prior_directory / "enzyme_roster.json").read_text())
    need(isinstance(roster, list) and roster and all(set(r) == {"enzyme", "gene", "hgnc_id"} for r in roster),
         "Unexpected final source enzyme roster schema.")
    for key in ("enzyme", "gene", "hgnc_id"):
        need(len({r[key] for r in roster}) == len(roster), "Final source enzyme roster is not injective.")
    for row in roster:
        mapped = methods.resolve_gene_protein(row["gene"], registry, sequence)
        need(mapped["status"] == "qualified" and mapped["protein_id"] == row["enzyme"]
             and mapped["hgnc_id"] == row["hgnc_id"] and mapped["approved_symbol"] == row["gene"],
             "Final source enzyme no longer matches the exact helper correspondence.")
    # Only this interface opens measurement rows; no metadata path exists here.
    prepared = methods.prepare_measurements(measurement_csv.read_bytes(), condition_ids=conditions,
        registry=registry, sequence_reference=sequence, qualified_ks_links=links,
        provenance={"execution_freeze_sha256": frozen["content_sha256"], "prior_receipt_sha256": prior["content_sha256"]})
    need([r["enzyme"] for r in roster] == list(prepared.enzyme_ids), "Source and prepared enzyme ordering differ.")
    need(set(ppi_paths) == {"unpruned", "native", "primary", "ne"}, "Declare exactly four PPI paths.")
    matrices, pair_maps = {}, {}
    for arm, path in ppi_paths.items():
        path = pinned(path, frozen)
        need(path.parent == prior_directory and path.name == PPI_FILES[arm]
             and path.name in prior["output_files_sha256"], "PPI arm is not bound to its exact final-prior filename.")
        matrices["W_" + arm], pair_maps[arm] = _ppi(path, prepared.enzyme_ids)
    for arm in ("native", "primary", "ne"):
        need(all(pair in pair_maps["unpruned"] and value == pair_maps["unpruned"][pair]
                 for pair, value in pair_maps[arm].items()), "PPI arm changed source identity or native weights.")
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    numeric = {"X": np.asarray(prepared.X, dtype=np.float64),
        "Wkin2site": prepared.Wkin2site.astype(np.float64).tocsc(),
        "Wsite2site": prepared.Wsite2site.astype(np.float64).tocsc(), **matrices}
    need(set(numeric) == INPUT_VARS, "Unexpected staged numeric variables.")
    savemat(output / "numeric_input.mat", numeric, do_compression=True, format="5", oned_as="column")
    jsonl(output / "measurement_rows.jsonl", prepared.rows)
    jsonl(output / "aggregation.jsonl", prepared.aggregation)
    jsonl(output / "source_links.jsonl", prepared.qualified_ks_links)
    write_json(output / "enzyme_roster.json", roster)
    write_json(output / "site_roster.json", [{"protein_id": p, "site": s} for p, s in prepared.site_ids])
    write_json(output / "condition_roster.json", conditions)
    write_json(output / "condition_cells.json", condition_cells)
    write_json(output / "condition_drugs.json", condition_drugs)
    write_json(output / "provenance.json", prepared.provenance)
    coverage = {"measurement_mapping_states": dict(Counter(r["mapping"]["status"] for r in prepared.rows)),
        "site_count": len(prepared.site_ids), "enzyme_count": len(roster), "condition_count": len(conditions),
        "finite_measurement_values": int(np.isfinite(prepared.X).sum()),
        "missing_measurement_values": int(np.isnan(prepared.X).sum()),
        "finite_values_by_condition": {c: int(np.isfinite(prepared.X[:, i]).sum()) for i, c in enumerate(conditions)},
        "PPI_nonzero_matrix_entries": {arm: int(matrices["W_" + arm].nnz) for arm in ppi_paths},
        "reference_metadata_accessed": False}
    write_json(output / "coverage.json", coverage)
    receipt = sealed({"format": FORMATS["prepared"], "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_freeze_path": str(Path(execution_freeze).resolve()), "execution_freeze_file_sha256": sha(execution_freeze),
        "execution_freeze_content_sha256": frozen["content_sha256"], "expected_cells": frozen["expected_cells"],
        "registry_directory": str(registry_directory),
        "condition_count": len(conditions), "enzyme_count": len(roster), "site_count": len(prepared.site_ids),
        "reference_metadata_accessed": False,
        "output_files_sha256": {p.name: sha(p) for p in sorted(output.iterdir())}})
    write_json(output / "receipt.json", receipt)
    return receipt


def verify_prepared(directory):
    directory = Path(directory).resolve()
    receipt = load_sealed(directory / "receipt.json", FORMATS["prepared"])
    need(sha(receipt["execution_freeze_path"]) == receipt["execution_freeze_file_sha256"], "Execution freeze changed.")
    frozen = verify_freeze(receipt["execution_freeze_path"])
    need(frozen["content_sha256"] == receipt["execution_freeze_content_sha256"], "Execution freeze content changed.")
    verify_outputs(directory, receipt)
    return receipt, frozen


def seal_predictions(*, prepared_directory, output_mat, output):
    prepared_directory = Path(prepared_directory).resolve()
    prep, frozen = verify_prepared(prepared_directory)
    inventory = whosmat(output_mat)
    need({r[0] for r in inventory} == set(MAT_TO_ARM), "Output must contain exactly the seven declared arrays.")
    arrays = loadmat(output_mat)
    shape = (prep["enzyme_count"], prep["condition_count"])
    for name in MAT_TO_ARM:
        array = arrays[name]
        need(array.shape == shape and array.dtype == np.float64 and np.isrealobj(array)
             and not np.isinf(array).any(), "Output shape/type or finite-or-NaN contract failed: " + name)
    roster = json.loads((prepared_directory / "enzyme_roster.json").read_text())
    conditions = json.loads((prepared_directory / "condition_roster.json").read_text())
    predictions = {arm: {condition: {row["gene"]: float(arrays[name][i, j])
        if np.isfinite(arrays[name][i, j]) else None for i, row in enumerate(roster)}
        for j, condition in enumerate(conditions)} for name, arm in MAT_TO_ARM.items()}
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(output_mat, output / "numeric_output.mat")
    write_json(output / "raw_predictions.json", predictions)
    receipt = sealed({"format": FORMATS["sealed"], "created_at": datetime.now(timezone.utc).isoformat(),
        "prepared_directory": str(prepared_directory), "prepared_receipt_file_sha256": sha(prepared_directory / "receipt.json"),
        "prepared_content_sha256": prep["content_sha256"], "execution_freeze_content_sha256": frozen["content_sha256"],
        "candidate_genes": [r["gene"] for r in roster], "condition_ids": conditions,
        "array_shapes": {name: list(arrays[name].shape) for name in MAT_TO_ARM},
        "array_missing_counts": {name: int(np.isnan(arrays[name]).sum()) for name in MAT_TO_ARM},
        "raw_prediction_missing_encoding": "JSON null represents original NaN; raw MAT retained; zero retained; no candidate/condition dropped.",
        "reference_metadata_accessed": False,
        "output_files_sha256": {p.name: sha(p) for p in sorted(output.iterdir())}})
    write_json(output / "receipt.json", receipt)
    return receipt


def score(*, sealed_directory, reference_csv, output):
    sealed_directory = Path(sealed_directory).resolve()
    prediction_receipt = load_sealed(sealed_directory / "receipt.json", FORMATS["sealed"])
    prep_directory = Path(prediction_receipt["prepared_directory"])
    need(sha(prep_directory / "receipt.json") == prediction_receipt["prepared_receipt_file_sha256"], "Prepared receipt changed.")
    prep, frozen = verify_prepared(prep_directory)
    need(prep["content_sha256"] == prediction_receipt["prepared_content_sha256"]
         and frozen["content_sha256"] == prediction_receipt["execution_freeze_content_sha256"], "Prediction input binding differs.")
    verify_outputs(sealed_directory, prediction_receipt)
    predictions = json.loads((sealed_directory / "raw_predictions.json").read_text())
    need(set(predictions) == set(stats.ARMS), "Sealed arm roster differs.")
    # First and only reference body access happens after all prediction bindings.
    need(sha(reference_csv) == frozen["reference_csv_sha256"], "Reference CSV bytes differ from opaque commitment.")
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    write_json(output / "reference_access.json", {"first_parse_started_utc": datetime.now(timezone.utc).isoformat(),
        "reference_csv_sha256": frozen["reference_csv_sha256"],
        "sealed_prediction_receipt_sha256": sha(sealed_directory / "receipt.json")})
    raw = Path(reference_csv).read_bytes()
    (output / "reference.csv").write_bytes(raw)
    typed = methods.parse_reference_csv(raw, condition_column="id", drug_column="drug", cell_column="cell_line",
        targets_column="target", sign_column="sign", provenance={"reference_csv_sha256": frozen["reference_csv_sha256"]})
    allowed = set(prediction_receipt["condition_ids"])
    condition_cells = json.loads((prep_directory / "condition_cells.json").read_text())
    condition_drugs = json.loads((prep_directory / "condition_drugs.json").read_text())
    eligible, scope_exclusions = [], []
    for row in typed:
        reason = ("reference_id_outside_fixed_source_condition_roster" if row["condition"] not in allowed else
                  "reference_cell_does_not_match_source_condition" if row["cell"] != condition_cells[row["condition"]] else
                  "reference_drug_does_not_match_source_condition" if row["drug"] != condition_drugs[row["condition"]] else None)
        if reason:
            scope_exclusions.append({"reason": reason, "row": row})
        else:
            eligible.append(row)
    _, registry = load_registry(prep["registry_directory"])
    references = methods.qualify_expected_targets(eligible, registry)
    results = {arm: methods.score_predictions(values, references,
        candidate_genes=prediction_receipt["candidate_genes"], expected_cells=frozen["expected_cells"])
        for arm, values in predictions.items()}
    assessment = stats.assess_pilot(results)
    qualified_by_condition = {r["condition"]: r for r in references.cases}
    condition_ledger = []
    for condition in prediction_receipt["condition_ids"]:
        originals = [r for r in typed if r["condition"] == condition]
        in_scope = [r for r in eligible if r["condition"] == condition]
        case = qualified_by_condition.get(condition)
        condition_ledger.append({"condition": condition, "source_cell": condition_cells[condition],
            "source_drug": condition_drugs[condition],
            "original_reference_data_row_ordinals": [r["reference_data_row_ordinal"] for r in originals],
            "scope_eligible_reference_data_row_ordinals": [r["reference_data_row_ordinal"] for r in in_scope],
            "qualified_atomic_targets": len(case["targets"]) if case else 0,
            "status": "qualified_reference_condition" if case else
                      "metadata_present_no_qualified_atomic_targets" if in_scope else
                      "metadata_present_outside_source_context" if originals else "no_reference_metadata"})
    original_drug_ledger = []
    for drug in sorted({r["drug"] for r in typed}):
        originals = [r for r in typed if r["drug"] == drug]
        in_scope = [r for r in eligible if r["drug"] == drug]
        cases = [r for r in references.cases if r["drug"] == drug]
        original_drug_ledger.append({"reported_drug": drug,
            "original_reference_data_row_ordinals": [r["reference_data_row_ordinal"] for r in originals],
            "original_condition_ids": sorted({r["condition"] for r in originals}),
            "scope_eligible_reference_data_row_ordinals": [r["reference_data_row_ordinal"] for r in in_scope],
            "qualified_condition_ids": sorted(r["condition"] for r in cases),
            "qualified_atomic_targets": sum(len(r["targets"]) for r in cases),
            "complete_primary_drug": drug in assessment["primary_population"]["drug_ids"]})
    jsonl(output / "reference_rows.jsonl", typed)
    jsonl(output / "reference_scope_exclusions.jsonl", scope_exclusions)
    jsonl(output / "native_condition_ledger.jsonl", condition_ledger)
    write_json(output / "reference_qualification.json", asdict(references))
    write_json(output / "arm_scores.json", results)
    write_json(output / "assessment.json", assessment)
    write_json(output / "drug_ledger.json", {"complete_primary_drugs": assessment["primary_population"]["drug_ids"],
        "incomplete_reference_drugs": assessment["incomplete_reference_drug_groups"],
        "all_original_metadata_drugs": original_drug_ledger,
        "all_arm_drug_summaries": {arm: result["per_drug"] for arm, result in results.items()}})
    receipt = sealed({"format": FORMATS["scored"], "created_at": datetime.now(timezone.utc).isoformat(),
        "sealed_prediction_directory": str(sealed_directory),
        "sealed_prediction_receipt_file_sha256": sha(sealed_directory / "receipt.json"),
        "sealed_prediction_content_sha256": prediction_receipt["content_sha256"],
        "execution_freeze_content_sha256": frozen["content_sha256"],
        "reference_csv_sha256": frozen["reference_csv_sha256"], "reference_rows": len(typed),
        "reference_scope_exclusions": len(scope_exclusions),
        "output_files_sha256": {p.name: sha(p) for p in sorted(output.iterdir())}})
    write_json(output / "receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    for key in ("execution-freeze", "measurement-csv", "condition-roster", "registry-directory",
                "sequence-reference", "prior-directory", "output"):
        p.add_argument("--" + key, required=True)
    for arm in ("unpruned", "native", "primary", "ne"):
        p.add_argument("--ppi-" + arm, required=True)
    p = sub.add_parser("seal")
    for key in ("prepared-directory", "output-mat", "output"):
        p.add_argument("--" + key, required=True)
    p = sub.add_parser("score")
    for key in ("sealed-directory", "reference-csv", "output"):
        p.add_argument("--" + key, required=True)
    args = vars(parser.parse_args(argv)); command = args.pop("command")
    if command == "prepare":
        args["ppi_paths"] = {arm: args.pop("ppi_" + arm) for arm in ("unpruned", "native", "primary", "ne")}
        result = prepare(**args)
    elif command == "seal":
        result = seal_predictions(**args)
    else:
        result = score(**args)
    print(json.dumps({"format": result["format"], "content_sha256": result["content_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
