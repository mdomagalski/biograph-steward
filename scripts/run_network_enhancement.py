#!/usr/bin/env python3
"""Run the pinned GPL author Network Enhancement implementation externally.

This MIT adapter contains no implementation of the denoising algorithm. Obtain
the unchanged author files in an ignored run directory with ``fetch-author``;
``prepare`` validates source-only TSV inputs, and ``run`` invokes GNU Octave.
Only scores for the original weighted edges leave the Octave process. No assay
outcomes, graph decisions, thresholds or model training are used here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.request import urlopen


AUTHOR_REVISION = "8662284871274b805ed82f725af54ab76dc79e53"
AUTHOR_BASE = (
    "https://raw.githubusercontent.com/wangboyunze/Network_Enhancement/"
    + AUTHOR_REVISION + "/"
)
AUTHOR_HASHES = {
    "LICENSE": "87946a54ba55e1b6a76c47ea26a3ea625882979fe5c9b3482af71823a602ba4b",
    "core/Network_Enhancement.m": "39f1b627efaef5daf5192566fa7f8e26d1bf062c5b2f3429419b2977e97cb54b",
    "core/NE_dn.m": "9a8b54da2eb9c467855495d6bbedd36a56c012d9faf5619848c02ac5598c0ecd",
    "core/TransitionFields.m": "1800d145dce0177f5e94132fc54b42d8494c5ae0870cea1d0471e922d4857221",
    "core/dominateset.m": "ccf6a448dcff913772c9293c62da2fc93241357ff52f7d988ea51082182f9c08",
}
OCTAVE_IMAGE = (
    "docker.io/gnuoctave/octave:11.3.0@sha256:"
    "185db7993e000d4f3f6e7bbbf7fb3f999f52e799ea52231ad8a15353381e0dcb"
)
FORMAT = "biograph-steward.network-enhancement.v1"
FORBIDDEN_COLUMNS = {"label", "labels", "outcome", "outcomes", "detected", "assay_score"}
PAIR_COLUMNS = {"subject", "object", "weight", "pair_id", "edge_id", "source_bundle", "pruning_eligible"}
NODE_COLUMNS = {"node_id", "resolution_status", "canonical_graph_node_present"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ordinary(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected an ordinary file: {path}")
    return path.read_bytes()


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def seal(value: dict) -> dict:
    payload = {key: item for key, item in value.items() if key != "content_sha256"}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return {**payload, "content_sha256": sha(canonical.encode("utf-8"))}


def read_tsv(raw: bytes, required: set[str], allowed: set[str]) -> list[dict]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), delimiter="\t")
    fields = reader.fieldnames
    if (not fields or len(set(fields)) != len(fields) or not required.issubset(fields)
            or FORBIDDEN_COLUMNS.intersection(fields) or not set(fields).issubset(allowed)):
        raise ValueError("TSV columns are duplicated, lack required fields or contain outcomes.")
    rows = list(reader)
    if not rows or any(None in row or None in row.values() for row in rows):
        raise ValueError("TSV must contain complete, nonempty rows.")
    return rows


def load_inputs(nodes_raw: bytes, pairs_raw: bytes) -> tuple[list[str], list[dict]]:
    nodes = [row["node_id"] for row in read_tsv(nodes_raw, {"node_id"}, NODE_COLUMNS)]
    if any(not node or node != node.strip() for node in nodes) or len(nodes) != len(set(nodes)):
        raise ValueError("Node identifiers must be nonempty, unique and trimmed.")
    node_set, seen_pairs, seen_ids, pairs = set(nodes), set(), set(), []
    for row in read_tsv(pairs_raw, {"subject", "object", "weight", "pair_id"}, PAIR_COLUMNS):
        subject, obj, identifier = row["subject"], row["object"], row["pair_id"]
        pair = tuple(sorted((subject, obj)))
        if (subject not in node_set or obj not in node_set or subject == obj
                or pair in seen_pairs or not identifier or identifier != identifier.strip()
                or identifier in seen_ids):
            raise ValueError("Weighted edges must have declared distinct endpoints and unique pairs/IDs.")
        weight = float(row["weight"])
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("Original weighted edges require finite positive weights.")
        pairs.append({"subject": subject, "object": obj, "pair_id": identifier, "weight": weight})
        seen_pairs.add(pair)
        seen_ids.add(identifier)
    return nodes, pairs


def verify_author(folder: Path) -> dict[str, str]:
    actual = {name: sha(ordinary(folder / name)) for name in AUTHOR_HASHES}
    if actual != AUTHOR_HASHES:
        raise ValueError("Author source/license differ from the pinned unchanged implementation.")
    if {p.name for p in (folder / "core").iterdir()} != {Path(name).name for name in AUTHOR_HASHES if name.startswith("core/")}:
        raise ValueError("Author core directory contains unexpected files that could shadow functions.")
    return actual


def fetch_author(output: Path) -> dict:
    # Deliberately separate from execution: the predictor itself runs offline.
    if output.exists():
        raise ValueError("Author destination must not already exist.")
    payloads = {}
    for name, expected in AUTHOR_HASHES.items():
        with urlopen(AUTHOR_BASE + name, timeout=60) as response:
            raw = response.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024 or sha(raw) != expected:
            raise ValueError("Author download does not match pinned bytes: " + name)
        payloads[name] = raw
    output.mkdir(parents=True)
    for name, raw in payloads.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    receipt = {"repository": "https://github.com/wangboyunze/Network_Enhancement",
               "revision": AUTHOR_REVISION, "license": "GPL-3.0", "files": verify_author(output)}
    write_json(output / "source_receipt.json", receipt)
    return receipt


def octave_script(node_count: int) -> str:
    # Matrix construction and original-edge projection only. The external author
    # function supplies every denoising operation without modification.
    return f"""addpath('/author/core');
warning('on', 'Octave:function-name-clash');
edges = dlmread('/input/indexed_pairs.tsv', '\\t');
n = {node_count};
W = sparse([edges(:,1); edges(:,2)], [edges(:,2); edges(:,1)], ...
           [edges(:,3); edges(:,3)], n, n);
started = tic();
W_out = Network_Enhancement(W);
elapsed = toc(started);
assert(isequal(size(W_out), [n, n]));
assert(all(isfinite(W_out(:))) && all(W_out(:) >= 0));
assert(all(diag(W_out) == 0));
isolated = find(sum(W, 2) == 0);
assert(all(all(W_out(isolated, :) == 0)));
assert(norm(W_out - W_out', 'fro') <= 1e-10 * max(1, norm(W_out, 'fro')));
idx = sub2ind([n, n], edges(:,1), edges(:,2));
fid = fopen('/output/indexed_scores.tsv', 'w');
assert(fid >= 0);
fprintf(fid, '%d\\t%d\\t%.17g\\n', [edges(:,1), edges(:,2), W_out(idx)]');
fclose(fid);
fid = fopen('/output/runtime.txt', 'w');
assert(fid >= 0);
fprintf(fid, 'octave_version=%s\\ncomputer=%s\\nalgorithm_seconds=%.17g\\n', ...
        OCTAVE_VERSION, computer(), elapsed);
fclose(fid);
"""


def prepare(nodes_path: Path, pairs_path: Path, author: Path, output: Path) -> dict:
    author_hashes = verify_author(author)
    nodes_raw, pairs_raw = ordinary(nodes_path), ordinary(pairs_path)
    nodes, pairs = load_inputs(nodes_raw, pairs_raw)
    if output.exists():
        raise ValueError("Output destination must not already exist.")
    output.mkdir(parents=True)
    inputs = output / "input"
    inputs.mkdir()
    (inputs / "network_nodes.tsv").write_bytes(nodes_raw)
    (inputs / "weighted_pairs.tsv").write_bytes(pairs_raw)
    positions = {node: index + 1 for index, node in enumerate(nodes)}
    with (inputs / "indexed_pairs.tsv").open("x", encoding="utf-8", newline="") as handle:
        for pair in pairs:
            handle.write(f"{positions[pair['subject']]}\t{positions[pair['object']]}\t{pair['weight']:.17g}\n")
    (inputs / "run_ne.m").write_text(octave_script(len(nodes)), encoding="utf-8")
    manifest = seal({
        "format": FORMAT, "status": "prepared_not_executed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adapter_sha256": sha(Path(__file__).read_bytes()),
        "author": {"revision": AUTHOR_REVISION, "license": "GPL-3.0",
                   "source_files_sha256": author_hashes, "compatibility_patches": [],
                   "known_warning": "NE_dn.m declares function dn; unchanged author bytes retained"},
        "method": {"name": "Network Enhancement", "order": 2, "alpha": 0.9,
                   "K": min(20, math.ceil(len(nodes) / 10)), "parameter_selection": "author_defaults_no_tuning",
                   "output_scope": "original_input_edges_only", "scores_are_probabilities": False,
                   "pruning_or_labels_applied": False},
        "node_count": len(nodes), "original_edge_count": len(pairs),
        "isolated_node_count": len(set(nodes) - {p[k] for p in pairs for k in ("subject", "object")}),
        "inputs_sha256": {path.name: sha(path.read_bytes()) for path in sorted(inputs.iterdir())},
        "runtime_image": OCTAVE_IMAGE,
        "runtime_execution_verified": False,
    })
    write_json(output / "prepared_manifest.json", manifest)
    return manifest


def docker_command(author: Path, output: Path) -> list[str]:
    return ["docker", "run", "--rm", "--pull=never", "--platform=linux/amd64",
            "--network=none", "--memory=3g", "--memory-swap=3g", "--cpus=1",
            "--pids-limit=128", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--user", f"{os.getuid()}:{os.getgid()}",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--env", "HOME=/tmp",
            "--env", "OPENBLAS_NUM_THREADS=1", "--env", "OMP_NUM_THREADS=1",
            "--mount", f"type=bind,src={author},dst=/author,readonly",
            "--mount", f"type=bind,src={output / 'input'},dst=/input,readonly",
            "--mount", f"type=bind,src={output / 'runtime'},dst=/output",
            OCTAVE_IMAGE, "octave-cli", "--no-gui", "--quiet", "--no-init-file",
            "--no-site-file", "/input/run_ne.m"]


def validate_prepared(output: Path, author: Path) -> tuple[dict, list[str], list[dict]]:
    manifest = json.loads(ordinary(output / "prepared_manifest.json"))
    if (manifest.get("format") != FORMAT or manifest.get("status") != "prepared_not_executed"
            or manifest != seal(manifest)
            or manifest.get("adapter_sha256") != sha(Path(__file__).read_bytes())
            or manifest.get("author", {}).get("source_files_sha256") != verify_author(author)):
        raise ValueError("Prepared adapter or pinned author source changed.")
    input_dir = output / "input"
    if {p.name: sha(ordinary(p)) for p in input_dir.iterdir()} != manifest["inputs_sha256"]:
        raise ValueError("Prepared input bytes changed.")
    nodes, pairs = load_inputs(ordinary(input_dir / "network_nodes.tsv"), ordinary(input_dir / "weighted_pairs.tsv"))
    return manifest, nodes, pairs


def project_scores(raw: bytes, nodes: list[str], pairs: list[dict]) -> list[tuple[str, float]]:
    positions = {node: index + 1 for index, node in enumerate(nodes)}
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8")), delimiter="\t"))
    if len(rows) != len(pairs):
        raise ValueError("Runtime scores must preserve every original edge exactly once.")
    result = []
    for row, pair in zip(rows, pairs):
        if len(row) != 3 or [int(row[0]), int(row[1])] != [positions[pair["subject"]], positions[pair["object"]]]:
            raise ValueError("Runtime scores changed original endpoint order or scored nonedges.")
        score = float(row[2])
        if not math.isfinite(score) or score < 0:
            raise ValueError("Runtime produced a nonfinite or negative edge score.")
        result.append((pair["pair_id"], score))
    return result


def run(output: Path, author: Path, timeout: int) -> dict:
    manifest, nodes, pairs = validate_prepared(output, author)
    runtime_dir = output / "runtime"
    runtime_dir.mkdir()
    command = docker_command(author, output)
    write_json(output / "command.json", {"argv": command, "timeout_seconds": timeout})
    inspected = subprocess.run(["docker", "image", "inspect", OCTAVE_IMAGE], check=True,
                               capture_output=True, text=True)
    (output / "docker_image_inspect.json").write_text(inspected.stdout, encoding="utf-8")
    started = time.monotonic()
    with (output / "stdout.log").open("x") as stdout, (output / "stderr.log").open("x") as stderr:
        completed = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=timeout, check=False)
    if completed.returncode:
        raise RuntimeError(f"External author execution failed ({completed.returncode}); inspect stderr.log.")
    projected = project_scores(ordinary(runtime_dir / "indexed_scores.tsv"), nodes, pairs)
    runtime = dict(line.split("=", 1) for line in ordinary(runtime_dir / "runtime.txt").decode().splitlines())
    if runtime.get("octave_version") != "11.3.0":
        raise ValueError("Runtime does not report pinned Octave 11.3.0.")
    with (output / "scores.tsv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["pair_id", "score"])
        writer.writerows((identifier, format(score, ".17g")) for identifier, score in projected)
    # Recheck all original inputs/source after computation before issuing success.
    validate_prepared(output, author)
    report = seal({**manifest, "status": "completed", "runtime_execution_verified": True,
              "runtime": runtime, "wall_seconds": time.monotonic() - started,
              "python": platform.python_version(), "score_count": len(projected),
              "zero_original_edge_scores": sum(score == 0 for _, score in projected),
              "outputs_sha256": {name: sha(ordinary(output / name)) for name in
                  ("scores.tsv", "command.json", "docker_image_inspect.json", "stdout.log", "stderr.log",
                   "runtime/indexed_scores.tsv", "runtime/runtime.txt")}})
    write_json(output / "manifest.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch-author", help="Download only pinned code/license into an external run directory")
    fetch.add_argument("--out", type=Path, required=True)
    prep = commands.add_parser("prepare", help="Validate source-only inputs; no runtime or network calls")
    prep.add_argument("--nodes", type=Path, required=True)
    prep.add_argument("--pairs", type=Path, required=True)
    prep.add_argument("--author-source", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    execute = commands.add_parser("run", help="Run pre-pulled official image offline; no GPU or outcome access")
    execute.add_argument("--author-source", type=Path, required=True)
    execute.add_argument("--out", type=Path, required=True)
    execute.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    if args.command == "fetch-author":
        result = fetch_author(args.out.absolute())
    elif args.command == "prepare":
        result = prepare(args.nodes.absolute(), args.pairs.absolute(), args.author_source.absolute(), args.out.absolute())
    else:
        result = run(args.out.absolute(), args.author_source.absolute(), args.timeout)
    print(json.dumps({key: result[key] for key in ("status", "node_count", "original_edge_count", "score_count")
                      if key in result}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Network Enhancement adapter: {exc}", file=sys.stderr)
        raise SystemExit(1)
