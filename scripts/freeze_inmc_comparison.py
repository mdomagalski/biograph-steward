#!/usr/bin/env python3
"""Bind checked graph, runtime and scorer receipts without reading assay outcomes.

Creates a new graph packet. A CPU resource check authorizes only that exact CPU
runtime; a different device requires a new check and a new immutable freeze.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
import run_inmc_comparison as runner

SCORER = ROOT / "biograph_steward/inmc_outcomes.py"
ASSAY = ROOT / "docs/evaluations/inmc_assay_contract_20261022.json"
HIERARCHY_SCRIPT = ROOT / "scripts/smoke_pykeen_hierarchy.py"
PACKAGES = {"pykeen", "torch", "numpy", "scipy", "scikit-learn"}


def _ordinary(path):
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ValueError("Proof inputs must be ordinary files, not symlinks.")
    return path.read_bytes()


def _proof(path, *, sealed):
    raw = _ordinary(path)
    value = runner.strict_json(raw)
    if not isinstance(value, dict) or value.get("status") != "passed":
        raise ValueError("A passed proof report is required.")
    if sealed and value.get("content_sha256") != digest(
            {key: item for key, item in value.items() if key != "content_sha256"}):
        raise ValueError("Resource proof content seal differs.")
    return raw, value


def _members(folder, inventory):
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError("Resource proof lacks its bound file inventory.")
    contents = {}
    for name, expected in inventory.items():
        if not isinstance(name, str) or not isinstance(expected, str) or not runner.HEX.fullmatch(expected):
            raise ValueError("Malformed resource proof file inventory.")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name == "report.json":
            raise ValueError("Unsafe resource proof member path.")
        if any((folder / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
            raise ValueError("Resource proof members cannot traverse symlinks.")
        raw = _ordinary(folder / relative)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Resource proof file fingerprint differs: " + name)
        contents[name] = raw
    if "manifest.json" not in contents:
        raise ValueError("Resource proof must bind its runtime manifest.")
    return contents


def _execution(manifest):
    device = manifest.get("device")
    if device not in {"cpu", "cuda", "cuda:0"}:
        raise ValueError("Resource manifest has an unsupported device.")
    packages = manifest.get("packages")
    if (not isinstance(packages, dict) or set(packages) != PACKAGES or
            any(not isinstance(value, str) or not value for value in packages.values()) or
            not isinstance(manifest.get("python"), str) or not manifest["python"] or
            (manifest.get("cuda_runtime") is not None and not isinstance(manifest["cuda_runtime"], str))):
        raise ValueError("Resource manifest must identify the exact Python and package runtime.")
    return {"device": "cuda:0" if device.startswith("cuda") else "cpu",
            "python": manifest["python"], "packages": packages,
            "cuda_runtime": manifest.get("cuda_runtime")}


def freeze_comparison(graph, hierarchy_smoke, resource_smoke, output_dir):
    graph, hierarchy_smoke, resource_smoke = map(Path, (graph, hierarchy_smoke, resource_smoke))
    packet = runner.validate_packet(graph, resource_smoke=True)
    if packet["protocol"]["fully_frozen"]:
        raise ValueError("Use the original prepared graph, not an already frozen packet.")
    if not SCORER.is_file():
        raise ValueError("The assay scoring implementation must exist before freezing.")
    scorer_sha, assay_sha = sha(SCORER), sha(ASSAY)
    if packet["files"].get("assay_contract.json") != assay_sha:
        raise ValueError("Prepared graph must bind the current prespecified assay contract.")
    hierarchy_raw, hierarchy = _proof(hierarchy_smoke, sealed=False)
    hierarchy_manifest_raw = _ordinary(hierarchy_smoke.with_name("manifest.json"))
    hierarchy_manifest = runner.strict_json(hierarchy_manifest_raw)
    if (hierarchy.get("format") != "biograph-steward.pykeen-hierarchy-smoke.v1" or
            hierarchy.get("purpose") != "engineering_only" or
            hierarchy.get("biomedical_inputs_used") is not False or
            hierarchy.get("biological_quality_measured") is not False or
            hierarchy_manifest.get("input") != "invented constants in this script only" or
            hierarchy_manifest.get("script_sha256") != sha(HIERARCHY_SCRIPT)):
        raise ValueError("Hierarchy proof must bind the current engineering-only synthetic smoke.")
    resource_raw, resource = _proof(resource_smoke, sealed=True)
    resource_members = _members(resource_smoke.parent, resource.get("files"))
    resource_manifest = runner.strict_json(resource_members["manifest.json"])
    runner_sha = sha(Path(runner.__file__))
    expected_inputs = {key: packet["files"][key] for key in runner.REQUIRED if key != "protocol.json"}
    bindings = {"runner_sha256": runner_sha, "graph_input_files": expected_inputs,
                "graph_report_sha256": packet["report_sha256"],
                "protocol_sha256": packet["files"]["protocol.json"]}
    for receipt in (resource, resource_manifest):
        if (receipt.get("resource_smoke") is not True or receipt.get("candidate_outcomes_loaded") is not False or
                any(receipt.get(key) != expected for key, expected in bindings.items())):
            raise ValueError("Resource proof does not bind this runner, graph and outcome-blind execution.")
    if resource.get("candidate_pairs_scored") != 0 or resource_manifest.get("candidate_pairs_scored") is not False:
        raise ValueError("Resource proof must not have scored the reserved candidate panel.")
    execution = _execution(resource_manifest)
    if resource.get("execution") != execution:
        raise ValueError("Resource proof execution differs from its runtime manifest.")
    if (resource_manifest.get("model") != packet["protocol"]["model"] or
            resource_manifest.get("training") != packet["protocol"]["training"]):
        raise ValueError("Resource proof used a different model or training contract.")
    for package in ("pykeen", "torch", "numpy"):
        if hierarchy_manifest.get("packages", {}).get(package, "").split("+")[0] != execution["packages"][package].split("+")[0]:
            raise ValueError("Hierarchy and resource proofs used different core package versions.")

    proofs = {"validation/hierarchy_smoke.json": hierarchy_raw,
              "validation/hierarchy_manifest.json": hierarchy_manifest_raw,
              "validation/resource_smoke.json": resource_raw,
              "validation/resource_runtime.json": resource_members["manifest.json"],
              "validation/parent_graph_report.json": _ordinary(graph / "report.json")}
    if set(proofs) & set(packet["files"]):
        raise ValueError("Prepared graph already contains conflicting validation proof names.")
    copied = {name: _ordinary(graph / name) for name in packet["files"]}
    if any(hashlib.sha256(raw).hexdigest() != packet["files"][name] for name, raw in copied.items()):
        raise ValueError("Prepared graph changed while freezing.")
    protocol = deepcopy(packet["protocol"])
    protocol.update(fully_frozen=True, runner_sha256=runner_sha,
                    scoring_implementation={"path": "biograph_steward/inmc_outcomes.py", "sha256": scorer_sha},
                    assay_contract_sha256=assay_sha, execution=execution,
                    parent_graph_content_sha256=packet["report"]["content_sha256"])
    for name in ("hierarchy_smoke", "resource_smoke"):
        protocol[name] = {"status": "passed", "report_sha256": hashlib.sha256(proofs[f"validation/{name}.json"]).hexdigest()}
    protocol["hierarchy_smoke"].update(manifest_sha256=hashlib.sha256(hierarchy_manifest_raw).hexdigest(),
                                       script_sha256=sha(HIERARCHY_SCRIPT))
    protocol["resource_smoke"]["runtime_manifest_sha256"] = resource["files"]["manifest.json"]
    output = new_output(output_dir, graph, hierarchy_smoke.parent, resource_smoke.parent)
    for name, raw in {**copied, **proofs}.items():
        if name == "protocol.json":
            continue
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    write_json(output / "protocol.json", protocol)
    report = deepcopy(packet["report"])
    report.pop("content_sha256")
    report.update(status="comparison_frozen", fully_frozen=True, frozen_at=utcnow(),
                  parent_graph_report_sha256=packet["report_sha256"],
                  parent_graph_content_sha256=packet["report"]["content_sha256"],
                  freeze_implementation_sha256=sha(Path(__file__)),
                  remaining_before_full_freeze=[],
                  execution=execution,
                  scoring_implementation=protocol["scoring_implementation"],
                  resource_proof_files_verified=resource["files"],
                  resource_proof_artifacts_copied=False,
                  outcome_values_loaded=False, author_positive_pairs_opened=False,
                  scientific_predictions_generated=False, model_requests=0)
    report["files"] = {path.relative_to(output).as_posix(): sha(path) for path in sorted(output.rglob("*")) if path.is_file()}
    report["content_sha256"] = digest(report)
    write_json(output / "report.json", report)
    runner.validate_packet(output)
    if (sha(SCORER) != scorer_sha or sha(ASSAY) != assay_sha or sha(Path(runner.__file__)) != runner_sha or
            sha(graph / "report.json") != packet["report_sha256"]):
        raise ValueError("Implementation or input changed during freeze; do not execute this packet.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--hierarchy-smoke", type=Path, required=True)
    parser.add_argument("--resource-smoke", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = freeze_comparison(args.graph, args.hierarchy_smoke, args.resource_smoke, args.output_dir)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{result['status']}: {args.output_dir.resolve()} ({result['execution']['device']}; outcomes unopened)")
