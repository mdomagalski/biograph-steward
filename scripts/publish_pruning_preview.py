#!/usr/bin/env python3
"""Publish a bounded read-only view of an already completed pruning assessment.

No retrieval, model call, source-graph replay or new biological evaluation is
performed. Existing fixed selections must reproduce the frozen edge inventories.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from assess_ppi_pruning import select_arms
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output
from biograph_steward.pruning_preview import (FORMAT, ARMS, CAPS, assemble, json_lines, load_preview,
    ordinary, require, sealed, target_labels)
from biograph_steward.gold_packet import _decode


def publish_preview(results, protocol_path, groups_path, output, *, targets=None,
                    source_protocol=None, decision_policy=None):
    results, protocol_path, groups_path = Path(results), Path(protocol_path), Path(groups_path)
    raw = {"protocol.json": ordinary(protocol_path, CAPS["protocol.json"]),
           "pair_groups.json": ordinary(groups_path, CAPS["pair_groups.json"]),
           "result.json": ordinary(results / "report.json", CAPS["result.json"])}
    protocol, result = _decode(raw["protocol.json"]), _decode(raw["result.json"])
    require(sealed(protocol) and sealed(result), "Use sealed completed result/protocol files.")
    require(set(result.get("files", {})) == {"metrics.json", "pair_accounting.jsonl", "report.html", "outcome_access_receipt.json"},
            "Completed result file inventory differs from the supported assessment.")
    for name, expected in result["files"].items():
        data = ordinary(results / name, CAPS.get(name, 500_000))
        require(hashlib.sha256(data).hexdigest() == expected, "Completed result bytes changed: " + name)
        if name in {"metrics.json", "pair_accounting.jsonl"}:
            raw[name] = data
    require(hashlib.sha256(raw["pair_groups.json"]).hexdigest() == protocol.get("files", {}).get("pair_groups.json"),
            "Pair groups differ from the frozen source projection.")
    groups = _decode(raw["pair_groups.json"])
    selections, diagnostics = select_arms({g["pair_id"]: g for g in groups})
    require(diagnostics == protocol.get("diagnostics"), "Existing fixed source selections differ from the frozen protocol.")
    decisions = [{"pair_id": group["pair_id"], "arms": {
        arm: ("keep" if group["pair_id"] in selections[arm] else "prune") if group["eligible"] else "abstain"
        for arm in ARMS}} for group in sorted(groups, key=lambda row: row["pair_id"])]
    raw["dispositions.jsonl"] = "".join(json.dumps(row, sort_keys=True) + "\n" for row in decisions).encode()
    sources = [results, protocol_path, groups_path]
    for path, name in ((targets, "targets.tsv"), (source_protocol, "source_protocol.json"),
                       (decision_policy, "decision_policy.json")):
        if path is not None:
            raw[name] = ordinary(path, CAPS[name]); sources.append(Path(path))
    if targets is not None:
        require(hashlib.sha256(raw["targets.tsv"]).hexdigest()
                == protocol["input_inventories"]["source"]["ordinary_run/targets.tsv"],
                "Protein labels differ from the frozen source target table.")
    source = _decode(raw["source_protocol.json"]) if source_protocol is not None else None
    if source is not None:
        require(sealed(source) and source.get("content_sha256") == protocol["source_protocol_sha256"]
                and source.get("graph_sha256") == protocol["graph_sha256"], "Source metadata binding differs.")
    if decision_policy is not None:
        require(hashlib.sha256(raw["decision_policy.json"]).hexdigest()
                == protocol["reference_files"]["decision_policy"]["sha256"], "Fixed interpretation policy changed.")
    summary, _ = assemble(protocol, result, _decode(raw["metrics.json"]), groups,
        json_lines(raw["pair_accounting.jsonl"], 20_000), decisions,
        target_labels(raw.get("targets.tsv")), source)
    output = new_output(output, *sources)
    for name, data in raw.items():
        (output / name).write_bytes(data)
    write_json(output / "summary.json", summary)
    files = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}
    manifest = {"format": FORMAT, "created_at": utcnow(), "files": files,
        "source_protocol_sha256": protocol["content_sha256"], "source_result_sha256": result["content_sha256"],
        "publication_kind": "read_only_historical_projection", "model_calls": 0,
        "new_source_requests": 0, "workspace_modified": False, "new_scientific_evaluation": False,
        "note": "Published from a completed retrospective assessment. File hashes and frozen edge commitments do not authenticate scientific truth."}
    write_json(output / "manifest.json", {**manifest, "content_sha256": digest(manifest)})
    return load_preview(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True, help="Completed assessment result directory")
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--groups", type=Path, required=True)
    parser.add_argument("--targets", type=Path, help="Optional source target table, hash-bound by the frozen protocol")
    parser.add_argument("--source-protocol", type=Path)
    parser.add_argument("--decision-policy", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = publish_preview(args.results, args.protocol, args.groups, args.output,
        targets=args.targets, source_protocol=args.source_protocol, decision_policy=args.decision_policy)
    print(json.dumps({"status": "published_read_only", "output": str(args.output),
        "source_pairs": summary["scope"]["source_pair_count"], "preview_pairs": summary["scope"]["preview_pair_count"]}))


if __name__ == "__main__":
    main()
