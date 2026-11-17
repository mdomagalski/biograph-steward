#!/usr/bin/env python3
"""Retain source-faithful Wiki uncertainty; mark replayed native positives KEEP.

This source-content qualification never prunes from absent native references.
The current-GMT eligibility ablation, original graph and scientific review
states are unchanged. It reuses the complete Gold decision/retention contract.
"""
from collections import Counter
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.wiki_history import load_history_packet, query_history, need

PROFILE = "source-faithful-exact-historical-WikiPathways-native-content.v1"
POSITIVES = {"explicitly_encoded_protein_xref", "compatible_gene_level_xref"}


def decision_rows(graph, history, *, replay=query_history):
    """One source-aware row per original edge; no missing-content negatives."""
    decisions, traces, replayed = [], [], {}
    for edge in graph["edges"]:
        raw = edge.get("evidence_record", {})
        wiki = edge.get("record_kind") == "pathway_membership" and raw.get("type") == "WikiPathways"
        decision = "abstain"
        reason = "outside_historical_WikiPathways_profile; retain without scientific assessment"
        if wiki:
            key = (edge["subject"], raw.get("sourceID"))
            stored = history["connections"].get(key)
            need(stored is not None and edge["id"] in stored["original_edge_ids"]
                 and edge["assertion_id"] in stored["original_assertion_ids"],
                 "original Wiki edge is not bound by the pinned historical packet.")
            status = stored["status"]
            need(status in POSITIVES | {"unresolved"}, "unsupported historical status.")
            if status in POSITIVES:
                if key not in replayed:
                    verified = replay(history, *key)
                    replayed[key] = {"status": verified["status"],
                        "native_model_sha256": verified["model"]["gpml_sha256"],
                        "selected_archive_proof": verified["selected_archive_proof"],
                        "schema_reexecuted_in_consumer": verified["schema_reexecuted_in_consumer"],
                        "assessment_sha256": digest(verified["assessment"])}
                proof = replayed[key]
                need(proof["status"] == status, "native positive did not replay exactly.")
                decision = "keep"
                reason = (PROFILE + "; " + status + "; " + key[1] + "; GPML_SHA256=" + stored["native_model_sha256"]
                          + "; source-content support only; gene/protein form identity and biological truth unadjudicated")
            else:
                reason = (PROFILE + "; historical_native_context_unresolved; preserve original evidence; "
                          "absence of a flat native reference is not a biological negative")
            traces.append({"edge_id": edge["id"], "assertion_id": edge["assertion_id"],
                "subject": edge["subject"], "full_source_id": raw.get("sourceID"),
                "native_local_pathway": edge["object"], "native_pwid": raw.get("pwid"),
                "native_record_sha256": digest(raw), "source_locators": edge.get("record_locators", []),
                "historical_status": status, "historical_connection_sha256": stored["content_sha256"],
                "native_model_sha256": stored.get("native_model_sha256"),
                "native_model_file": stored.get("native_model_file"), "decision": decision,
                "biological_negative_asserted": False})
        decisions.append({"edge_id": edge["id"], "decision": decision, "reason": reason, "confidence": None})
    expected = {eid for row in history["connections"].values() for eid in row["original_edge_ids"]}
    need({r["edge_id"] for r in traces} == expected, "original Wiki scope and history edge coverage differ.")
    need(not any(r["decision"] == "prune" for r in decisions), "source-faithful policy must never prune.")
    return decisions, traces, replayed


def prepare_decisions(packet, history_directory, output, *, history_content_sha256):
    implementation = {name: sha(ROOT / name) for name in (
        "tools/pathway_history/prepare_decisions.py", "biograph_steward/wiki_history.py",
        "biograph_steward/human_gene_relation.py", "biograph_steward/gold_packet.py",
        "biograph_steward/cohort_mapping.py")}
    packet, history_directory = Path(packet), Path(history_directory)
    manifest, graph = gold_packet.load_packet(packet)
    history = load_history_packet(history_directory, expected_content_sha256=history_content_sha256)
    report = history["report"]
    need(sha(packet / "source/graph.json") == report["source_graph_file_sha256"],
         "Gold packet is not the exact original graph used by historical verification.")
    decisions, traces, replayed = decision_rows(graph, history)
    need(len(traces) == report["counts"]["original_rows"], "original Wiki row denominator differs.")
    folder = new_output(output, packet, history_directory)
    write_json(folder / "decisions.json", {"format": gold_packet.DECISION_FORMAT, "packet_id": manifest["packet_id"],
        "method": PROFILE, "actor": "Deterministic exact native-source qualification", "decisions": decisions})
    # Pinned metadata is deliberately separate from the complete portable
    # history packet. The retained Gold package itself includes its full source.
    metadata = folder / "history_metadata"
    metadata.mkdir()
    for name in ("historical_verification.json", "resource_coverage.jsonl", "claim_assessments.jsonl", "edge_assessments.jsonl"):
        shutil.copyfile(history_directory / name, metadata / name)
    write_json(folder / "source_qualification_traces.json", traces)
    write_json(folder / "native_positive_replays.json", [{
        "subject": subject, "full_source_id": source_id, "status": value["status"],
        "native_model_sha256": value["native_model_sha256"],
        "selected_archive_proof": value["selected_archive_proof"],
        "schema_reexecuted_in_consumer": value["schema_reexecuted_in_consumer"],
        "assessment_sha256": value["assessment_sha256"]}
        for (subject, source_id), value in sorted(replayed.items())])
    counts = Counter(r["decision"] for r in decisions)
    # Release full baseline and native proof structures before Gold's replay.
    del graph, history, replayed
    retained = gold_packet.save_decisions(packet, folder / "decisions.json", folder / "retained")
    need(all(retained["counts"][k] == counts[k] for k in ("keep", "prune", "abstain")), "Gold retention differs.")
    need(gold_packet.load_packet(packet)[0] == manifest, "original packet changed during qualification.")
    # Full byte rebinding, without repeating the source/model queries.
    need(load_history_packet(history_directory, expected_content_sha256=history_content_sha256)["report"] == report,
         "historical packet changed during qualification.")
    for name, pin in implementation.items():
        need(sha(ROOT / name) == pin, "qualification implementation changed while running.")
    result = {"format": "biograph-steward.source-faithful-historical-WikiPathways-decisions.v1",
        "profile": PROFILE, "created_at": utcnow(), "packet_id": manifest["packet_id"],
        "graph_sha256": manifest["graph_sha256"], "source_graph_file_sha256": report["source_graph_file_sha256"],
        "history_packet_path_at_capture": str(history_directory.resolve()),
        "history_content_sha256": history_content_sha256,
        "history_report_file_sha256": sha(metadata / "historical_verification.json"),
        "full_native_history_proof_in_separate_portable_packet": True,
        "counts": {"total_edges": len(decisions), "WikiPathways_rows": len(traces),
            "native_positive_groups_replayed": len({(r["subject"], r["full_source_id"]) for r in traces if r["decision"] == "keep"}),
            **{k: counts[k] for k in ("keep", "prune", "abstain")}},
        "current_GMT_ablation_changed": False, "source_graph_mutated": False,
        "scientific_review_states_promoted": False, "biological_truth_assessed": False,
        "missing_native_content_is_negative": False, "native_rows_merged": False,
        "confidence_estimated": False, "source_fetches": 0, "model_calls": 0,
        "retained_package": "retained", "retained_content_sha256": retained["content_sha256"],
        "implementation_sha256": implementation,
        "files": {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*")
                  if p.is_file() and "retained" not in p.relative_to(folder).parts}}
    result["files"]["retained/report.json"] = sha(folder / "retained/report.json")
    result["content_sha256"] = digest(result)
    write_json(folder / "source_faithful_qualification.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--history-content-sha256", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_decisions(args.packet, args.history, args.out,
        history_content_sha256=args.history_content_sha256), indent=2))


if __name__ == "__main__":
    main()
