#!/usr/bin/env python3
"""Verify frozen sample/reviews and summarize AI-assisted audit outcomes.

The existing Gold loaders verify the source and optional disposition packages.
This adapter replays sample selection/dossiers and exact review bindings. It
does not retrieve evidence, assign biological labels or generate a truth score.
"""
from collections import Counter
from copy import deepcopy
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet, go_ontology_qualification as go
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.inspection import inspect_selection
from tools.sampled_audit.prepare import CRITERIA, FORMAT, METHOD, draw_sample, write_jsonl
from tools.sampled_audit.audit_statistics import AXES, STATUSES, summarize

SCORE_FORMAT = "biograph-steward.sampled-evidence-audit-score.v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def need(condition, message):
    if not condition:
        raise ValueError("Sampled audit scoring: " + message)


def text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def rows(path):
    need(Path(path).is_file() and not Path(path).is_symlink(), "row input must be an ordinary file.")
    values = [gold_packet._decode(line) for line in Path(path).read_bytes().splitlines()]
    need(all(isinstance(row, dict) for row in values), "JSONL rows must be objects.")
    return values


def verify_tree(folder, pins, report_name):
    folder = Path(folder)
    need(folder.is_dir() and not folder.is_symlink(), "input directory must be ordinary.")
    paths = list(folder.rglob("*"))
    need(not any(p.is_symlink() for p in paths) and all(p.is_file() or p.is_dir() for p in paths),
         "input paths must be ordinary files/directories without symlinks.")
    need(isinstance(pins, dict) and all(gold_packet._safe_relative(name)
         and isinstance(pin, str) and SHA256.fullmatch(pin) for name, pin in pins.items()),
         "file inventory/pins are invalid.")
    need({p.relative_to(folder).as_posix() for p in paths if p.is_file()} == set(pins) | {report_name},
         "file inventory differs from frozen report.")
    expected_dirs = {parent.as_posix() for name in pins for parent in Path(name).parents
                     if parent.as_posix() != "."}
    need({p.relative_to(folder).as_posix() for p in paths if p.is_dir()} == expected_dirs,
         "directory inventory differs from frozen report.")
    need(all(sha(folder / name) == pin for name, pin in pins.items()), "frozen input bytes changed.")


def load_frozen(audit, packet, *, inspection_reader=None):
    """Replay the complete frozen sample and dossiers against the Gold source."""
    # Dossiers freeze a rendered source guide as well as the assertion. A
    # separately qualified historical renderer can reproduce that guide while
    # every source, sampling and complete-dossier equality check stays active.
    reader = inspect_selection if inspection_reader is None else inspection_reader
    need(callable(reader), "source-inspection reader must be callable.")
    audit, packet = Path(audit).absolute(), Path(packet).absolute()
    manifest, graph = gold_packet.load_packet(packet)
    report_pin = sha(audit / "sample_manifest.json")
    report = gold_packet._read(audit / "sample_manifest.json")
    need(gold_packet._sealed(report) and report.get("format") == FORMAT,
         "sample report format/seal differs.")
    verify_tree(audit, report.get("files"), "sample_manifest.json")
    need(report.get("scientific_accuracy_measured") is False
         and report.get("review_judgments_generated") is False,
         "sample preparation cannot contain scientific judgments.")
    protocol = gold_packet._read(audit / "protocol.json")
    need(gold_packet._sealed(protocol) and protocol.get("format") == FORMAT
         and protocol.get("content_sha256") == report.get("protocol_content_sha256"),
         "protocol format/seal/binding differs.")
    need(protocol.get("method") == METHOD and protocol.get("review_criteria") == CRITERIA,
         "sampling method or review criteria differ from this supported profile.")
    need(protocol.get("population_unit") == "assertion"
         and protocol.get("packet_id") == report.get("packet_id") == manifest["packet_id"]
         and protocol.get("baseline_graph_sha256") == report.get("baseline_graph_sha256") == manifest["graph_sha256"]
         and protocol.get("packet_manifest_file_sha256") == sha(packet / "packet_manifest.json"),
         "sample belongs to a different exact baseline packet.")
    population = dict(sorted(Counter(a["kind"] for a in graph["assertions"]).items()))
    need(protocol.get("population_by_stratum") == population
         and protocol.get("population_size") == report.get("population_size") == len(graph["assertions"])
         and protocol.get("evidence_edge_count") == len(graph["edges"]),
         "population counts differ from the complete frozen source.")
    strata, selected = draw_sample(graph["assertions"], protocol.get("sample_allocation"), protocol.get("seed"))
    expected_sample_id = "audit:" + digest({"protocol": protocol["content_sha256"], "sample": selected})
    need(report.get("strata") == strata and report.get("sample_id") == expected_sample_id,
         "sampling weights or selected sample identity differ.")
    saved = rows(audit / "sample.jsonl")
    need(report.get("sample_size") == len(saved) == len(selected), "sample size differs.")
    assertions = {a["id"]: a for a in graph["assertions"]}
    edges = {e["id"]: e for e in graph["edges"]}
    nodes = {n["id"]: n for n in graph["nodes"]}
    templates, expected_files = [], {"protocol.json", "sample.jsonl", "reviews.template.jsonl"}
    for expected, row in zip(selected, saved):
        name = "cases/" + expected["case_id"] + ".json"
        need(set(row) == set(expected) | {"dossier_path", "dossier_content_sha256"}
             and all(row[key] == value for key, value in expected.items()) and row.get("dossier_path") == name,
             "selected identities, probabilities or case locations do not replay.")
        expected_files.add(name)
        dossier = gold_packet._read(audit / name)
        assertion = assertions[expected["assertion_id"]]
        source_edges = [deepcopy(edges[uid]) for uid in assertion["evidence_edge_ids"]]
        rebuilt = {"format": "biograph-steward.sampled-assertion-dossier.v1",
            "sample_id": expected_sample_id, "protocol_content_sha256": protocol["content_sha256"],
            **expected, "assertion": deepcopy(assertion), "assertion_content_sha256": digest(assertion),
            "source_edges": source_edges,
            "source_edge_content_sha256": {e["id"]: digest(e) for e in source_edges},
            "endpoint_nodes": [deepcopy(nodes[uid]) for uid in sorted({assertion["subject"], assertion["object"]})],
            "source_inspection": reader(graph, assertion["id"]),
            "intervention_disposition_exposed": False, "scientific_judgment": "not assigned by preparation"}
        rebuilt["content_sha256"] = digest(rebuilt)
        need(dossier == rebuilt and row["dossier_content_sha256"] == dossier["content_sha256"],
             "dossier content differs from its full source assertion/evidence.")
        templates.append({"case_id": expected["case_id"], "assertion_id": expected["assertion_id"],
            "stratum": expected["stratum"], "sample_id": expected_sample_id,
            "dossier_content_sha256": dossier["content_sha256"],
            **{axis: None for axis in AXES}, "independent_scientific_correctness": "unreviewed",
            "review_actor": None, "source_relative_reason": None, "primary_evidence_reason": None,
            "evidence_basis": [], "reference_independence": "not established"})
    need(set(report["files"]) == expected_files
         and rows(audit / "reviews.template.jsonl") == templates,
         "frozen sample/template inventory differs.")
    verify_tree(audit, report["files"], "sample_manifest.json")
    need(sha(audit / "sample_manifest.json") == report_pin, "sample report changed during verification.")
    return report, protocol, manifest, graph, saved


def load_reviews(path, sample, sample_id):
    """Require complete explicit judgments bound to the exact frozen dossiers."""
    reviews = rows(path)
    by_case = {row["case_id"]: row for row in sample}
    seen = set()
    for row in reviews:
        case = row.get("case_id")
        need(text(case) and case in by_case and case not in seen, "review case is unknown or duplicated.")
        seen.add(case)
        target = by_case[case]
        need(all(row.get(key) == target[key] for key in ("assertion_id", "stratum", "dossier_content_sha256"))
             and row.get("sample_id") == sample_id, "review belongs to a different sampled identity or dossier.")
        need(all(type(row.get(axis)) is str and row[axis] in STATUSES for axis in AXES)
             and row.get("independent_scientific_correctness") == "unreviewed",
             "review outcome vocabulary or independent scientific scope differs.")
        need(all(text(row.get(key)) for key in ("review_actor", "source_relative_reason", "primary_evidence_reason"))
             and row["review_actor"].casefold() != "unassigned",
             "every review needs an explicit actor and both evidence reasons.")
        basis = row.get("evidence_basis")
        need(isinstance(basis, list) and bool(basis)
             and all(text(item) or isinstance(item, dict) and bool(item) for item in basis),
             "every review needs a nonempty explicit evidence basis, including missing-evidence cases.")
    need(seen == set(by_case), "reviews must cover every frozen case, including unresolved cases.")
    return reviews


def load_intervention(folder, expected_report_sha256, binding_path, sample_report, protocol, manifest, graph):
    """Verify the preexisting GO policy using native ontology and Gold replay."""
    folder, binding_path = Path(folder).absolute(), Path(binding_path).absolute()
    need(folder.is_dir() and not folder.is_symlink(), "GO qualification must be an ordinary directory.")
    need(not any(path.is_symlink() for path in folder.rglob("*")),
         "GO qualification paths must not contain symlinks.")
    need(isinstance(expected_report_sha256, str) and SHA256.fullmatch(expected_report_sha256),
         "an explicit pinned GO qualification report SHA256 is required.")
    top_path = folder / "go_ontology_qualification.json"
    need(top_path.is_file() and not top_path.is_symlink() and sha(top_path) == expected_report_sha256,
         "GO qualification report bytes differ from the pin.")
    qualification = gold_packet._read(top_path)
    need(gold_packet._sealed(qualification) and qualification.get("format") == go.FORMAT
         and qualification.get("profile") == go.PROFILE,
         "the supported GO qualification policy/report is required.")
    need(binding_path.is_file() and not binding_path.is_symlink(), "intervention binding must be ordinary.")
    binding_pin = sha(binding_path)
    binding = gold_packet._read(binding_path)
    need(gold_packet._sealed(binding)
         and binding.get("format") == "biograph-steward.sampled-audit-intervention-binding.v1",
         "intervention binding format/seal differs.")
    for key, expected in {
        "sample_id": sample_report["sample_id"], "sample_manifest_content_sha256": sample_report["content_sha256"],
        "sample_protocol_content_sha256": protocol["content_sha256"], "baseline_packet_id": manifest["packet_id"],
        "baseline_graph_sha256": manifest["graph_sha256"], "policy": go.PROFILE,
        "policy_implementation_sha256": protocol["intervention"]["policy_implementation_sha256"],
        "qualification_report_content_sha256": qualification["content_sha256"],
        "qualification_report_file_sha256": expected_report_sha256,
        "ontology_source_sha256": qualification["ontology"]["file_sha256"],
        "retained_report_content_sha256": qualification["retained_report_sha256"],
        "policy_or_threshold_tuned_for_sample": False, "sample_changed": False,
    }.items():
        need(binding.get(key) == expected, "intervention binding differs: " + key)
    need(qualification.get("packet_id") == manifest["packet_id"]
         and qualification.get("graph_sha256") == manifest["graph_sha256"]
         and qualification.get("implementation_sha256") == binding["policy_implementation_sha256"] == sha(ROOT / "biograph_steward/go_ontology_qualification.py")
         and qualification.get("source_graph_mutated") is False
         and qualification.get("source_review_states_mutated") is False,
         "GO qualification belongs to another baseline/policy or changed its source.")
    pins = qualification.get("files")
    need(isinstance(pins, dict) and all(gold_packet._safe_relative(name)
         and isinstance(pin, str) and SHA256.fullmatch(pin) for name, pin in pins.items()),
         "GO qualification file pins are incomplete.")
    need(all((folder / name).is_file() and not (folder / name).is_symlink()
             and sha(folder / name) == pin for name, pin in pins.items()), "GO qualification source bytes differ.")
    source_name = qualification["ontology"].get("source_file")
    need(source_name in pins and pins[source_name] == qualification["ontology"]["file_sha256"],
         "GO native ontology source binding is missing.")
    nodes, ontology, _ = go.load_ontology(folder / source_name, pins[source_name])
    need(ontology == qualification["ontology"], "GO ontology metadata does not replay.")
    expected_decisions, expected_traces = {}, []
    for edge in graph["edges"]:
        decision = "abstain"
        if edge.get("record_kind") == "go_annotation":
            need(edge.get("predicate") == "biograph:has_go_annotation"
                 and edge.get("evidence_record", {}).get("goid") == edge.get("object"),
                 "original GO source projection is inconsistent.")
            result = go.classify_term(edge["object"], nodes)
            decision = result["decision"]
            expected_traces.append({"edge_id": edge["id"], "subject": edge["subject"],
                "term_id": edge["object"], "source_record_sha256": digest(edge["evidence_record"]),
                "source_locators": edge.get("record_locators", []), **result})
        expected_decisions[edge["id"]] = decision
    need(qualification.get("source_decisions") == expected_traces, "GO lifecycle decisions do not replay.")
    retained_report, retained = gold_packet.load_decisions(folder / "retained")
    need(retained_report["content_sha256"] == qualification["retained_report_sha256"]
         and retained_report.get("packet_id") == manifest["packet_id"]
         and retained_report.get("graph_sha256") == manifest["graph_sha256"]
         and retained_report.get("method") == go.PROFILE,
         "retained graph package differs from the frozen GO policy/baseline.")
    decisions = gold_packet._read(folder / "retained/decisions.json")
    need(gold_packet._read(folder / "decisions.json") == decisions,
         "GO source decisions differ from the materialized disposition package.")
    need({row["edge_id"]: row["decision"] for row in decisions["decisions"]} == expected_decisions,
         "retained ledger differs from the published primary-ID policy.")
    remaining_edges = {edge["id"] for edge in retained["edges"]}
    retained_ids = {a["id"] for a in graph["assertions"] if any(eid in remaining_edges for eid in a["evidence_edge_ids"])}
    need(retained_ids == {a["id"] for a in retained["assertions"]},
         "retained assertion support does not equal surviving baseline evidence.")
    captured_pins = {str(top_path): expected_report_sha256, str(binding_path): binding_pin,
        **{str(folder / name): pin for name, pin in pins.items()},
        str(folder / "retained/report.json"): sha(folder / "retained/report.json"),
        **{str(folder / "retained" / name): pin for name, pin in retained_report["files"].items()}}
    return retained_ids, {"binding_content_sha256": binding["content_sha256"],
        "qualification_report_content_sha256": qualification["content_sha256"],
        "retained_report_content_sha256": retained_report["content_sha256"],
        "policy": go.PROFILE, "ontology": ontology,
        "baseline_assertions": len(graph["assertions"]), "retained_assertions": len(retained_ids),
        "removed_assertions": len(graph["assertions"]) - len(retained_ids),
        "source_ontology_classification_replayed": True, "complete_Gold_disposition_replayed": True,
        "independent_biological_pruning_gain_established": False}, captured_pins


def score(audit, packet, reviews, output, *, go_qualification=None,
          go_qualification_report_sha256=None, intervention_binding=None):
    """Verify inputs, then write a source-bound AI-assisted audit summary."""
    audit, packet, reviews = Path(audit).absolute(), Path(packet).absolute(), Path(reviews).absolute()
    review_pin = sha(reviews)
    frozen_report_pin = sha(audit / "sample_manifest.json")
    sample_report, protocol, manifest, graph, sample = load_frozen(audit, packet)
    reviewed = load_reviews(reviews, sample, sample_report["sample_id"])
    retained_ids, intervention, extra_pins = None, None, {}
    if go_qualification is not None:
        need(intervention_binding is not None, "the fixed intervention binding is required.")
        retained_ids, intervention, extra_pins = load_intervention(go_qualification,
            go_qualification_report_sha256, intervention_binding, sample_report, protocol, manifest, graph)
    else:
        need(go_qualification_report_sha256 is None and intervention_binding is None,
             "intervention provenance was supplied without a GO qualification.")
    statistics = summarize(sample_report["strata"], sample, reviewed, retained_assertion_ids=retained_ids)
    baseline_pins = {str(packet / "packet_manifest.json"): protocol["packet_manifest_file_sha256"],
                     **{str(packet / name): pin for name, pin in manifest["files"].items()}}
    sample_pins = {str(audit / "sample_manifest.json"): frozen_report_pin,
                   **{str(audit / name): pin for name, pin in sample_report["files"].items()}}
    all_pins = {**baseline_pins, **sample_pins, **extra_pins, str(reviews): review_pin}
    need(all(Path(name).is_file() and not Path(name).is_symlink() and sha(Path(name)) == pin
             for name, pin in all_pins.items()), "an input changed while checking source/review bindings.")
    protected = [audit, packet, reviews]
    if go_qualification is not None:
        protected.extend((go_qualification, intervention_binding))
    folder = new_output(output, *protected)
    write_json(folder / "statistics.json", statistics)
    (folder / "reviews.jsonl").write_bytes(reviews.read_bytes())
    if retained_ids is not None:
        write_jsonl(folder / "paired_cases.jsonl", [{"case_id": row["case_id"],
            "assertion_id": row["assertion_id"], "retained": row["assertion_id"] in retained_ids,
            "evidence_support_rule": "retained if at least one original evidence edge survives"} for row in sample])
    need(sha(folder / "reviews.jsonl") == review_pin and all(sha(Path(name)) == pin for name, pin in all_pins.items()),
         "an input changed during scoring export; output is incomplete.")
    report = {"format": SCORE_FORMAT, "created_at": utcnow(), "status": "executed_ai_assisted_audit",
        "sample_id": sample_report["sample_id"], "sample_report_content_sha256": sample_report["content_sha256"],
        "protocol_content_sha256": protocol["content_sha256"], "packet_id": manifest["packet_id"],
        "baseline_graph_sha256": manifest["graph_sha256"], "review_file_sha256": review_pin,
        "sample_selection_and_dossiers_replayed": True, "complete_review_binding_verified": True,
        "intervention": intervention, "population_assertions": len(graph["assertions"]),
        "sampled_assertions": len(sample), "statistics": statistics,
        "source_graph_changed": False, "review_states_changed": False, "scientific_accuracy_measured": False,
        "model_inference_calls": 0, "source_fetches": 0,
        "implementation_sha256": {"score": sha(__file__),
                                  "statistics": sha(Path(__file__).with_name("audit_statistics.py"))},
        "input_files_sha256": all_pins,
        "files": {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*") if p.is_file()},
        "limits": ["Seals/hashes bind local bytes, not reviewer expertise or source authenticity.",
            "The judgments are AI-assisted source/evidence support; independent scientific correctness is unreviewed.",
            "Source-relative support can establish historical listing/annotation existence without biological truth or current ontology compatibility.",
            "Paired removal of an audit-supported assertion is not automatically loss of scientifically valid biology.",
            "No calibrated biological accuracy/confidence interval or automatic scientific-error pruning benefit is established."]}
    report["content_sha256"] = digest(report)
    write_json(folder / "report.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit", required=True, type=Path)
    p.add_argument("--packet", required=True, type=Path)
    p.add_argument("--reviews", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--go-qualification", type=Path)
    p.add_argument("--go-qualification-report-sha256")
    p.add_argument("--intervention-binding", type=Path)
    args = p.parse_args()
    report = score(args.audit, args.packet, args.reviews, args.out,
        go_qualification=args.go_qualification,
        go_qualification_report_sha256=args.go_qualification_report_sha256,
        intervention_binding=args.intervention_binding)
    print(json.dumps({key: report[key] for key in ("sample_id", "sampled_assertions", "scientific_accuracy_measured", "content_sha256")}, indent=2))


if __name__ == "__main__":
    main()
