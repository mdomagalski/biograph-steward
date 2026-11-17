"""Freeze/replay assertion-family x disposition SRSWOR evaluation designs.

Sampling reuses the established sampled-audit draw, but this contract never
relabels or pools that earlier audit. No reference outcomes are read here.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import argparse
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.sampled_audit.prepare import draw_sample, write_jsonl

FORMAT = "biograph-steward.reference-agreement-design.v1"
PROTOCOL = "protocol.json"
MANIFEST = "design_manifest.json"
SHA = re.compile(r"[0-9a-f]{64}\Z")


def need(condition, message):
    if not condition:
        raise ValueError("Reference design: " + message)


def read_rows(path):
    need(path.is_file() and not path.is_symlink(), "row files must be ordinary files.")
    values = [gold_packet._decode(line) for line in path.read_bytes().splitlines()]
    need(all(isinstance(row, dict) for row in values), "rows must be objects.")
    return values


def inventory(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and p != folder / MANIFEST}


def frame_for(graph, *, retained_ids=None, families=None):
    """Disposition is structural survival, never a scientific truth label."""
    all_families = {a["kind"] for a in graph["assertions"]}
    need(all(isinstance(k, str) and re.fullmatch(r"[a-z][a-z0-9_]*", k) for k in all_families),
         "unsupported family identifiers.")
    families = sorted(all_families if families is None else families)
    need(families and len(set(families)) == len(families) and set(families) <= all_families,
         "provide a unique, nonempty family subset.")
    ids = [a["id"] for a in graph["assertions"]]
    need(len(set(ids)) == len(ids), "assertion IDs repeat.")
    if retained_ids is not None:
        need(isinstance(retained_ids, (set, frozenset)) and retained_ids <= set(ids),
             "retained assertions are outside the source frame.")
    frame = []
    for a in sorted(graph["assertions"], key=lambda value: value["id"]):
        if a["kind"] not in families:
            continue
        disposition = ("not_intervened" if retained_ids is None else
                       "retained" if a["id"] in retained_ids else "pruned")
        frame.append({"assertion_id": a["id"], "family": a["kind"],
            "disposition": disposition, "stratum": a["kind"] + "::" + disposition,
            "assertion_sha256": digest(a), "evidence_edge_ids": list(a["evidence_edge_ids"])})
    return frame, families


def source_inputs(packet, dispositions=None, disposition_report_sha256=None):
    packet = Path(packet).absolute()
    manifest, graph = gold_packet.load_packet(packet)
    pins = {str(packet / "packet_manifest.json"): sha(packet / "packet_manifest.json"),
            **{str(packet / name): pin for name, pin in manifest["files"].items()}}
    retained_ids, binding = None, None
    if dispositions is None:
        need(disposition_report_sha256 is None, "a disposition pin needs its package.")
    else:
        dispositions = Path(dispositions).absolute()
        need(isinstance(disposition_report_sha256, str) and SHA.fullmatch(disposition_report_sha256)
             and sha(dispositions / "report.json") == disposition_report_sha256,
             "the exact disposition report pin is required.")
        report, retained = gold_packet.load_decisions(dispositions)
        need(report["packet_id"] == manifest["packet_id"] and report["graph_sha256"] == manifest["graph_sha256"],
             "dispositions refer to another original graph.")
        remaining = {e["id"] for e in retained["edges"]}
        retained_ids = {a["id"] for a in graph["assertions"] if any(e in remaining for e in a["evidence_edge_ids"])}
        need(retained_ids == {a["id"] for a in retained["assertions"]},
             "assertion retention differs from surviving original evidence.")
        binding = {"report_file_sha256": disposition_report_sha256,
            "report_content_sha256": report["content_sha256"], "method": report["method"],
            "retained_assertions": len(retained_ids), "pruned_assertions": len(graph["assertions"]) - len(retained_ids)}
        pins.update({str(dispositions / "report.json"): disposition_report_sha256,
                     **{str(dispositions / name): pin for name, pin in report["files"].items()}})
    return manifest, graph, retained_ids, binding, pins


def selected_rows(frame, allocation, seed):
    strata, sample = draw_sample([{"id": row["assertion_id"], "kind": row["stratum"]} for row in frame], allocation, seed)
    lookup = {row["assertion_id"]: row for row in frame}
    for number, row in enumerate(sample, 1):
        row["case_id"] = "reference_%04d" % number
        row.update({key: lookup[row["assertion_id"]][key] for key in ("family", "disposition", "assertion_sha256")})
    return strata, sample


def indices(graph):
    return ({a["id"]: a for a in graph["assertions"]},
            {e["id"]: e for e in graph["edges"]}, {n["id"]: n for n in graph["nodes"]})


def dossier(case, graph, sample_id, protocol_sha, index=None):
    assertions, edges, nodes = index or indices(graph)
    assertion = assertions[case["assertion_id"]]
    value = {"format": "biograph-steward.reference-agreement-case.v1", "sample_id": sample_id,
        "protocol_content_sha256": protocol_sha, **case, "assertion": deepcopy(assertion),
        "source_edges": [deepcopy(edges[e]) for e in assertion["evidence_edge_ids"]],
        "endpoint_nodes": [deepcopy(nodes[key]) for key in sorted({assertion["subject"], assertion["object"]})],
        "reference_labels_read": False, "independent_scientific_judgment": None}
    value["content_sha256"] = digest(value)
    return value


def prepare(packet, allocation, seed, output, *, dispositions=None, disposition_report_sha256=None, families=None):
    manifest, graph, retained_ids, binding, pins = source_inputs(packet, dispositions, disposition_report_sha256)
    frame, families = frame_for(graph, retained_ids=retained_ids, families=families)
    counts = dict(sorted(Counter(row["stratum"] for row in frame).items()))
    need(isinstance(allocation, dict) and set(allocation) == set(counts)
         and all(type(n) is int and 1 <= n <= counts[k] for k, n in allocation.items()),
         "allocation must cover every nonempty family/disposition stratum.")
    need(type(seed) is int and seed >= 0, "seed must be a nonnegative integer.")
    code_pin = sha(__file__)
    folder = new_output(output, packet, *(tuple() if dispositions is None else (dispositions,)))
    protocol = {"format": FORMAT, "created_at": utcnow(), "unit": "qualified_assertion",
        "packet_id": manifest["packet_id"], "graph_sha256": manifest["graph_sha256"],
        "packet_manifest_sha256": sha(Path(packet) / "packet_manifest.json"), "data_kind": manifest["data_kind"],
        "population_frame": "stored assertion IDs, not deduplicated biological facts", "family_scope": families,
        "population_size": len(frame), "outside_domain_assertions": len(graph["assertions"]) - len(frame),
        "population_by_stratum": counts, "allocation": dict(sorted(allocation.items())), "seed": seed,
        "method": "Fixed stratified simple random sampling without replacement; family x structural disposition",
        "disposition_binding": binding, "original_audit_samples_reused_or_pooled": False,
        "references_or_labels_read_by_preparation": False, "source_graph_changed": False}
    protocol["content_sha256"] = digest(protocol)
    write_json(folder / PROTOCOL, protocol)
    # Protocol is persisted before selected IDs are drawn or dossiers inspected.
    strata, selected = selected_rows(frame, allocation, seed)
    sample_id = "reference-audit:" + digest({"protocol": protocol["content_sha256"], "selected": selected})
    (folder / "cases").mkdir()
    sample, index = [], indices(graph)
    for row in selected:
        value = dossier(row, graph, sample_id, protocol["content_sha256"], index)
        name = "cases/" + row["case_id"] + ".json"
        write_json(folder / name, value)
        sample.append({**row, "dossier_path": name, "dossier_content_sha256": value["content_sha256"]})
    write_jsonl(folder / "frame.jsonl", frame)
    write_jsonl(folder / "sample.jsonl", sample)
    need(all(sha(path) == pin for path, pin in pins.items()) and sha(__file__) == code_pin,
         "source inputs or implementation changed during preparation.")
    report = {"format": FORMAT, "protocol_content_sha256": protocol["content_sha256"], "sample_id": sample_id,
        "packet_id": manifest["packet_id"], "graph_sha256": manifest["graph_sha256"], "strata": strata,
        "population_size": len(frame), "sample_size": len(sample), "input_files_sha256": pins,
        "implementation_sha256": code_pin, "draw_implementation_sha256": sha(ROOT / "tools/sampled_audit/prepare.py"),
        "files": inventory(folder), "labels_generated": False, "scientific_accuracy_measured": False}
    report["content_sha256"] = digest(report)
    write_json(folder / MANIFEST, report)
    return report


def load_design(folder, packet, *, dispositions=None, disposition_report_sha256=None):
    folder = Path(folder).absolute()
    need(folder.is_dir() and not folder.is_symlink() and not any(p.is_symlink() for p in folder.rglob("*")),
         "design must use ordinary files/directories.")
    report = gold_packet._read(folder / MANIFEST)
    protocol = gold_packet._read(folder / PROTOCOL)
    need(gold_packet._sealed(report) and gold_packet._sealed(protocol) and report.get("format") == protocol.get("format") == FORMAT,
         "design/protocol identity or content seal differs.")
    need(report.get("labels_generated") is False and report.get("scientific_accuracy_measured") is False
         and protocol.get("references_or_labels_read_by_preparation") is False
         and protocol.get("source_graph_changed") is False
         and protocol.get("original_audit_samples_reused_or_pooled") is False,
         "outcome-free preparation boundary differs.")
    need(report["files"] == inventory(folder), "design inventory or bytes changed.")
    manifest, graph, retained_ids, binding, pins = source_inputs(packet, dispositions, disposition_report_sha256)
    need(protocol["packet_id"] == manifest["packet_id"] and protocol["graph_sha256"] == manifest["graph_sha256"]
         and protocol["packet_manifest_sha256"] == sha(Path(packet) / "packet_manifest.json")
         and protocol["disposition_binding"] == binding, "source/disposition binding differs.")
    frame, _ = frame_for(graph, retained_ids=retained_ids, families=protocol["family_scope"])
    need(read_rows(folder / "frame.jsonl") == frame, "frame does not replay from source.")
    strata, selected = selected_rows(frame, protocol["allocation"], protocol["seed"])
    sample_id = "reference-audit:" + digest({"protocol": protocol["content_sha256"], "selected": selected})
    sample = read_rows(folder / "sample.jsonl")
    need(report["protocol_content_sha256"] == protocol["content_sha256"] and report["sample_id"] == sample_id
         and report["strata"] == strata and len(sample) == len(selected)
         and report["population_size"] == protocol["population_size"] == len(frame)
         and report["sample_size"] == len(sample)
         and protocol["population_by_stratum"] == dict(sorted(Counter(r["stratum"] for r in frame).items()))
         and protocol["outside_domain_assertions"] == len(graph["assertions"]) - len(frame),
         "design draw, counts or weights differ.")
    index = indices(graph)
    for actual, expected in zip(sample, selected):
        value = dossier(expected, graph, sample_id, protocol["content_sha256"], index)
        name = "cases/" + expected["case_id"] + ".json"
        need(actual == {**expected, "dossier_path": name, "dossier_content_sha256": value["content_sha256"]}
             and gold_packet._read(folder / name) == value, "sample case/dossier binding differs.")
    need(all(sha(path) == pin for path, pin in pins.items()), "source changed during replay.")
    return report, protocol, graph, sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--allocation", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--family", action="append")
    parser.add_argument("--dispositions", type=Path)
    parser.add_argument("--disposition-report-sha256")
    args = parser.parse_args()
    result = prepare(args.packet, gold_packet._read(args.allocation), args.seed, args.out,
        dispositions=args.dispositions, disposition_report_sha256=args.disposition_report_sha256, families=args.family)
    print(result["content_sha256"])


if __name__ == "__main__":
    main()
