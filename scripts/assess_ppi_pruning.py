#!/usr/bin/env python3
"""Freeze/materialize one fixed PPI task view, then explicitly score consumed assays.

This is budgeted source-graph pruning, not a biological-falsity classifier.
Freeze does not parse outcome rows. Scoring requires the sealed protocol ID and
an explicit outcome-access flag; neither stage retrieves data or calls a model.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gc
from html import escape
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import _decode, load_packet, load_decisions, save_decisions
from run_network_enhancement import AUTHOR_HASHES, OCTAVE_IMAGE
from prepare_ppi_pruning_graph import native_string_score

FORMAT = "biograph-steward.ppi-pruning-comparison.v1"
SOURCE_FORMAT = "biograph-steward.ppi-pruning-source.v1"
NE_FORMAT = "biograph-steward.network-enhancement.v1"
AUTHOR_REVISION = "8662284871274b805ed82f725af54ab76dc79e53"
ARMS = ("unpruned", "native_top80", "ne_top80")
POLICY = {
    "eligible": "Exact STRINGDB-only unordered pairs with resolved canonical endpoints and explicit native scores.",
    "other_sources": "Mixed, non-STRING and unresolved records abstain and remain in every view.",
    "retention_numerator": 4, "retention_denominator": 5,
    "operating_point": "Retain floor(4*N/5) eligible pairs independently in each scored arm.",
    "budget_population": "Budget applies to the entire eligible source graph, not the measured assay subset; measured retained counts may differ.",
    "tie_break": "Descending unmodified score, then ascending exact pair_id; used only at the operating point.",
    "confidence": None,
    "interpretation": "Task-specific budgeted view; a prune decision does not establish biological falsity.",
    "outcomes": "Previously consumed Lambourne human Y2H-v1 observations; nondetection is assay-conditional.",
    "reference_expected_nominations": 3222, "reference_expected_eligible": 2676,
    "threshold_tuning": False, "hyperparameter_search": False,
}
PAIR_COLUMNS = ("pair_id", "subject", "object", "edge_id", "source_bundle", "weight", "pruning_eligible")
NODE_COLUMNS = ("node_id", "resolution_status", "canonical_graph_node_present")
CODE = ("scripts/assess_ppi_pruning.py", "scripts/score_string_component.py",
        "scripts/prepare_ppi_pruning_graph.py", "scripts/run_network_enhancement.py",
        "scripts/run_string_component.py", "biograph_steward/string_component.py",
        "biograph_steward/gold_packet.py", "biograph_steward/assertions.py",
        "biograph_steward/client.py", "biograph_steward/file_utils.py")


def graph_utility(graph):
    """Undirected connectivity accounting; no biological validity inference."""
    parent = {row["id"]: row["id"] for row in graph["nodes"]}
    size = dict.fromkeys(parent, 1)
    degree = Counter()

    def find(uid):
        while parent[uid] != uid:
            parent[uid] = parent[parent[uid]]
            uid = parent[uid]
        return uid

    for edge in graph["edges"]:
        left, right = edge["subject"], edge["object"]
        require(left in parent and right in parent, "Retained graph contains an unknown endpoint.")
        degree[left] += 1; degree[right] += 1
        a, b = find(left), find(right)
        if a != b:
            if size[a] < size[b]:
                a, b = b, a
            parent[b] = a; size[a] += size[b]
    components = Counter(find(uid) for uid in parent)
    return {"preserved_node_count": len(parent), "isolated_nodes": sum(not degree[uid] for uid in parent),
            "undirected_component_count": len(components),
            "largest_undirected_component_nodes": max(components.values(), default=0),
            "interpretation": "Connectivity of the complete retained node/edge inventory; not biological accuracy."}


def view_proof(folder):
    """Run full existing replay and return compact graph identity/accounting."""
    report, graph = load_decisions(folder)
    return {"report_sha256": sha(Path(folder) / "report.json"), "counts": report["counts"],
            "edge_ids": sorted(edge["id"] for edge in graph["edges"]),
            "retained_edges": len(graph["edges"]), "retained_graph_sha256": digest(graph),
            "node_inventory_sha256": digest(graph["nodes"]), "utility": graph_utility(graph)}


def _isolated_view_proof(folder, *, packet=None, decisions=None):
    # Existing packet replay is deliberately comprehensive and memory-intensive.
    # Separate workers release its parsed snapshots/graphs fully between phases.
    prelude = "import sys,json;sys.path.insert(0,sys.argv[1]);"
    if packet is not None:
        subprocess.run([sys.executable, "-c", prelude +
            "from assess_ppi_pruning import save_decisions;save_decisions(*sys.argv[2:])",
            str(ROOT / "scripts"), str(packet), str(decisions), str(folder)], check=True, cwd=ROOT)
    result = subprocess.run([sys.executable, "-c", prelude +
        "from assess_ppi_pruning import view_proof;print(json.dumps(view_proof(sys.argv[2])))",
        str(ROOT / "scripts"), str(folder)], check=True, cwd=ROOT, capture_output=True, text=True)
    return json.loads(result.stdout)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Use an ordinary input file.")
    return _decode(path.read_bytes())


def sealed(value):
    return (isinstance(value, dict) and value.get("content_sha256")
            == digest({k: v for k, v in value.items() if k != "content_sha256"}))


def seal(value):
    return {**value, "content_sha256": digest(value)}


def inventory(folder):
    folder = Path(folder).resolve()
    result = {}
    for path in sorted(folder.rglob("*")):
        require(not path.is_symlink(), "Input/output inventories must not contain symlinks.")
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = sha(path)
    return result


def tsv(path, columns, *, extra=False):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Use an ordinary TSV input.")
    with path.open(encoding="utf-8", newline="") as stream:
        parser = csv.DictReader(stream, delimiter="\t")
        names = parser.fieldnames
        require(names is not None and len(names) == len(set(names))
                and (set(columns) <= set(names) if extra else tuple(names) == tuple(columns)),
                "TSV columns differ from the declared input contract.")
        rows = list(parser)
    require(all(None not in row and all(v is not None for v in row.values()) for row in rows),
            "TSV row width differs from its header.")
    return rows


def number(value, *, maximum=None):
    require(type(value) in (int, float, str) and value != "", "Explicit numeric score required.")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid numeric score.") from exc
    require(math.isfinite(result) and result >= 0 and (maximum is None or result <= maximum),
            "Scores must be finite, nonnegative and within their declared native range.")
    return result


def pair_id(subject, obj):
    require(isinstance(subject, str) and subject and isinstance(obj, str) and obj and subject < obj,
            "Pairs require ordered distinct exact endpoint identifiers.")
    return "ppi:" + digest({"subject": subject, "object": obj})[:24]


def prepare_groups(graph, pair_rows, node_rows, ne_rows):
    """Validate complete PPI accounting and group every evidence ID per pair."""
    nodes = {row["id"] for row in graph["nodes"]}
    edge_by_id = {row["id"]: row for row in graph["edges"]}
    resolved = {}
    for row in node_rows:
        uid, status, present = (row[k] for k in NODE_COLUMNS)
        require(uid and uid not in resolved and status in {"resolved", "not_found", "identity_mismatch"}
                and present in {"true", "false"}, "Invalid or duplicate network node identity/state.")
        require((present == "true") == (uid in nodes) and (present != "true" or status == "resolved"),
                "Canonical graph presence differs from the node-resolution ledger.")
        resolved[uid] = status == "resolved" and present == "true"
    require(nodes <= set(resolved), "Node-resolution ledger must account for every canonical graph node.")
    groups, seen_edges = {}, set()
    for row in pair_rows:
        uid, left, right, eid = (row[k] for k in ("pair_id", "subject", "object", "edge_id"))
        require(uid == pair_id(left, right), "Pair identifier does not bind its exact canonical endpoints.")
        require(eid in edge_by_id and eid not in seen_edges, "Missing or repeated source evidence edge.")
        edge = edge_by_id[eid]
        require(edge.get("record_kind") == "protein_interaction"
                and edge.get("predicate") == "biograph:has_interaction_annotation"
                and sorted((edge["subject"], edge["object"])) == [left, right],
                "Pair row is not the preserved PPI edge and endpoint identity.")
        bundle = row["source_bundle"]
        require(isinstance(bundle, str) and bundle == edge.get("primary_source_raw"),
                "Source bundle differs from the preserved evidence record.")
        providers = [part.strip() for part in bundle.split(",")]
        require(all(providers) and len(providers) == len(set(providers)), "Invalid source bundle.")
        native = number(row["weight"], maximum=1) if "STRINGDB" in providers else None
        if native is not None:
            require(native == native_string_score(edge),
                    "Native weight must be the unchanged Pharos STRING score, not another field.")
        else:
            require(row["weight"] == "", "Non-STRING rows cannot supply a STRING native score.")
        require(row["pruning_eligible"] in {"true", "false"}, "Eligibility must be an explicit boolean string.")
        eligible_row = set(providers) == {"STRINGDB"} and resolved.get(left, False) and resolved.get(right, False)
        require((row["pruning_eligible"] == "true") == eligible_row,
                "Pruning eligibility differs from the fixed source-only rule.")
        group = groups.setdefault(uid, {"pair_id": uid, "subject": left, "object": right,
            "edge_ids": [], "providers": set(), "native_values": set(), "row_eligibility": []})
        require((group["subject"], group["object"]) == (left, right), "Pair ID collision.")
        group["edge_ids"].append(eid); group["providers"].update(providers)
        group["row_eligibility"].append(eligible_row)
        if native is not None:
            group["native_values"].add(native)
        seen_edges.add(eid)
    ppi_edges = {uid for uid, row in edge_by_id.items() if row.get("record_kind") == "protein_interaction"}
    require(seen_edges == ppi_edges, "Every original PPI evidence edge must be accounted for exactly once.")
    enhanced = {}
    for row in ne_rows:
        require(row["pair_id"] not in enhanced, "Duplicate author-NE score identity.")
        enhanced[row["pair_id"]] = number(row["score"])
    weighted = {uid for uid, g in groups.items() if "STRINGDB" in g["providers"]}
    require(set(enhanced) == weighted, "Author NE scores must cover precisely the original STRING-containing pairs.")
    for uid, group in groups.items():
        require(len(group["native_values"]) <= 1, "A pair has conflicting native scores; no aggregation is invented.")
        group["native_score"] = next(iter(group.pop("native_values")), None)
        group["ne_score"] = enhanced.get(uid)
        group["eligible"] = group["providers"] == {"STRINGDB"} and all(group.pop("row_eligibility"))
        group["providers"] = sorted(group["providers"])
        group["edge_ids"].sort()
    return groups


def select_arms(groups):
    eligible = [uid for uid, group in groups.items() if group["eligible"]]
    require(eligible, "No source-eligible STRINGDB-only pairs are available.")
    keep_count = len(eligible) * 4 // 5
    selections = {"unpruned": set(eligible)}
    diagnostics = {"eligible_pairs": len(eligible), "retained_pairs_per_scored_arm": keep_count}
    for arm, field in (("native_top80", "native_score"), ("ne_top80", "ne_score")):
        order = sorted(eligible, key=lambda uid: (-groups[uid][field], uid))
        selected = set(order[:keep_count]); selections[arm] = selected
        cutoff = groups[order[keep_count - 1]][field] if keep_count else None
        ties = [uid for uid in eligible if groups[uid][field] == cutoff] if cutoff is not None else []
        diagnostics[arm] = {"cutoff_score": cutoff, "cutoff_tied_pairs": len(ties),
            "cutoff_tied_retained": len(selected.intersection(ties)),
            "cutoff_tie_split": bool(set(ties) & selected and set(ties) - selected),
            "ranking_vector_sha256": digest([{ "pair_id": uid, "score": groups[uid][field]} for uid in sorted(eligible)])}
    diagnostics["native_ne_selected_pairs_differ"] = selections["native_top80"] != selections["ne_top80"]
    return selections, diagnostics


def decision_ledger(manifest, graph, groups, selected, arm):
    by_edge = {}
    for uid, group in groups.items():
        decision = ("keep" if uid in selected else "prune") if group["eligible"] else "abstain"
        reason = (f"{arm}: {POLICY['interpretation']} Pair {uid}; "
                  + ("fixed STRINGDB-only retention policy." if group["eligible"] else
                     "outside source eligibility; preserve unassessed evidence."))
        for eid in group["edge_ids"]:
            by_edge[eid] = {"edge_id": eid, "decision": decision, "reason": reason, "confidence": None}
    return {"format": "biograph-steward.edge-decisions.v1", "packet_id": manifest["packet_id"],
        "method": "fixed_ppi_task_view_v1:" + arm, "actor": "BioGraph Steward fixed PPI task-view policy",
        "decisions": [by_edge.get(edge["id"], {"edge_id": edge["id"], "decision": "abstain",
            "reason": "Outside this fixed PPI task view; preserve unassessed source evidence.", "confidence": None})
            for edge in graph["edges"]]}


def implementation():
    return {name: sha(ROOT / name) for name in CODE}


def verify_source(source, ne_output):
    source, ne_output = Path(source).resolve(), Path(ne_output).resolve()
    protocol = read(source / "source_protocol.json")
    require(sealed(protocol) and protocol.get("format") == SOURCE_FORMAT and protocol.get("outcomes_loaded") is False,
            "Source preparation must be complete, sealed and outcome-blind.")
    require(set(protocol.get("files", {})) == {"network_nodes.tsv", "weighted_pairs.tsv", "graph_pairs.tsv"},
            "Source input file contract differs.")
    for name, expected in protocol["files"].items():
        require(sha(source / name) == expected, "Prepared source input changed: " + name)
    manifest, graph = load_packet(source / "gold_packet")
    require(protocol.get("packet_id") == manifest["packet_id"]
            and protocol.get("graph_sha256") == digest(graph)
            and protocol.get("snapshot_sha256") == graph["snapshot_sha256"]
            and protocol.get("packet_manifest_sha256") == sha(source / "gold_packet/packet_manifest.json"),
            "Source graph/packet bindings differ.")
    ne = read(ne_output / "manifest.json")
    require(sealed(ne) and ne.get("format") == NE_FORMAT and ne.get("status") == "completed"
            and ne.get("runtime_execution_verified") is True, "Author NE execution is incomplete or changed.")
    require(ne.get("author", {}).get("revision") == AUTHOR_REVISION
            and ne["author"].get("compatibility_patches") == []
            and ne["author"].get("source_files_sha256") == AUTHOR_HASHES
            and ne.get("adapter_sha256") == sha(ROOT / "scripts/run_network_enhancement.py")
            and ne.get("runtime_image") == OCTAVE_IMAGE
            and ne.get("runtime", {}).get("octave_version") == "11.3.0"
            and ne.get("method", {}).get("output_scope") == "original_input_edges_only"
            and ne["method"].get("order") == 2 and ne["method"].get("alpha") == 0.9
            and ne["method"].get("K") == min(20, math.ceil(ne["node_count"] / 10))
            and ne["method"].get("parameter_selection") == "author_defaults_no_tuning"
            and ne["method"].get("pruning_or_labels_applied") is False,
            "Author code/runtime/output scope differs from the fixed method.")
    require(all(ne.get("inputs_sha256", {}).get(name) == sha(source / name)
                for name in ("network_nodes.tsv", "weighted_pairs.tsv"))
            and ne.get("outputs_sha256", {}).get("scores.tsv") == sha(ne_output / "scores.tsv"),
            "Author NE scores are not bound to these exact source inputs.")
    node_rows = tsv(source / "network_nodes.tsv", NODE_COLUMNS)
    groups = prepare_groups(graph, tsv(source / "graph_pairs.tsv", PAIR_COLUMNS), node_rows,
                            tsv(ne_output / "scores.tsv", ("pair_id", "score")))
    weighted = tsv(source / "weighted_pairs.tsv", ("subject", "object", "weight", "pair_id"), extra=True)
    require(len(weighted) == len({row["pair_id"] for row in weighted})
            and {row["pair_id"] for row in weighted} == {uid for uid, g in groups.items() if g["native_score"] is not None},
            "Weighted author input must represent every original STRING-containing pair once.")
    require(ne.get("node_count") == len(node_rows) and ne.get("original_edge_count") == len(weighted)
            and ne.get("score_count") == len(weighted), "Author execution input/output counts differ from source tables.")
    for row in weighted:
        group = groups[row["pair_id"]]
        require((row["subject"], row["object"]) == (group["subject"], group["object"])
                and number(row["weight"], maximum=1) == group["native_score"], "Weighted author input changed a source score or endpoint.")
    return protocol, manifest, graph, groups


def freeze(source, ne_output, candidates, assessment_rows, predictions, output, *, with_ap=False, decision_policy=None):
    """Materialize all views and freeze every binding before any outcome parse."""
    source, ne_output = Path(source).resolve(), Path(ne_output).resolve()
    references = {name: Path(path).resolve() for name, path in
                  (("candidates", candidates), ("assessment_rows", assessment_rows), ("predictions", predictions))}
    if decision_policy is not None:
        references["decision_policy"] = Path(decision_policy).resolve()
    require(all(p.is_file() and not p.is_symlink() for p in references.values()), "Reference files must already exist.")
    before = {"source": inventory(source), "ne_output": inventory(ne_output)}
    source_protocol, manifest, graph, groups = verify_source(source, ne_output)
    selections, diagnostics = select_arms(groups)
    output = new_output(output, source, ne_output, *references.values())
    if not diagnostics["native_ne_selected_pairs_differ"]:
        write_json(output / "no_op.json", {"status": "no_op_at_fixed_budget", "diagnostics": diagnostics,
            "outcomes_loaded": False, "scoring_permitted": False})
        raise ValueError("Native and NE retain identical pair sets at the fixed budget; no scoring is permitted.")
    graph_sha256 = source_protocol["graph_sha256"]
    node_inventory_sha256 = digest(graph["nodes"])
    # Only edge identities are needed once the source/packet is fully verified.
    graph = {"edges": [{"id": edge["id"]} for edge in graph["edges"]]}
    gc.collect()
    all_edges = {edge["id"] for edge in graph["edges"]}
    protected = all_edges - {eid for group in groups.values() if group["eligible"] for eid in group["edge_ids"]}
    arm_proofs, retained_sets = {}, {}
    for arm in ARMS:
        ledger = decision_ledger(manifest, graph, groups, selections[arm], arm)
        path = output / (arm + ".decisions.json"); write_json(path, ledger)
        proof = _isolated_view_proof(output / arm, packet=source / "gold_packet", decisions=path)
        wanted = {edge["id"] for edge in graph["edges"]} - {row["edge_id"] for row in ledger["decisions"] if row["decision"] == "prune"}
        actual = set(proof.pop("edge_ids"))
        require(actual == wanted and proof["node_inventory_sha256"] == node_inventory_sha256,
                "Materialized graph does not match the exact ledger or preserved node inventory.")
        require(protected <= actual, "A protected mixed/non-STRING/out-of-scope source edge was removed.")
        retained_sets[arm] = wanted
        arm_proofs[arm] = {**proof, "retained_edge_ids_sha256": digest(sorted(wanted)),
            "eligible_pairs_retained": len(selections[arm]),
            "eligible_pairs_removed": diagnostics["eligible_pairs"] - len(selections[arm]),
            "protected_source_edges": len(protected), "all_protected_source_edges_retained": True}
    require(retained_sets["native_top80"] != retained_sets["ne_top80"]
            and all(retained_sets[arm] < retained_sets["unpruned"] for arm in ARMS[1:]),
            "The actual derived edge inventories have no comparison contrast.")
    require(arm_proofs["native_top80"]["eligible_pairs_removed"] == arm_proofs["ne_top80"]["eligible_pairs_removed"]
            == diagnostics["eligible_pairs"] - diagnostics["retained_pairs_per_scored_arm"],
            "Scored arms must use the exact identical eligible-pair removal budget.")
    require(before == {"source": inventory(source), "ne_output": inventory(ne_output)}, "Source inputs changed while materializing views.")
    write_json(output / "pair_groups.json", [groups[uid] for uid in sorted(groups)])
    write_json(output / "selection_diagnostics.json", diagnostics)
    bindings = {name: {"path": str(path), "sha256": sha(path)} for name, path in references.items()}
    protocol = seal({"format": FORMAT, "created_at": utcnow(), "status": "frozen",
        "policy": POLICY, "with_average_precision": bool(with_ap), "python": platform.python_version(),
        "source_path": str(source), "ne_output_path": str(ne_output), "input_inventories": before,
        "source_protocol_sha256": source_protocol["content_sha256"], "packet_id": manifest["packet_id"],
        "graph_sha256": graph_sha256, "reference_files": bindings, "implementation_sha256": implementation(),
        "arms": arm_proofs, "diagnostics": diagnostics,
        "files": {"pair_groups.json": sha(output / "pair_groups.json"),
                  "selection_diagnostics.json": sha(output / "selection_diagnostics.json")},
        "outcomes_loaded": False, "reference_exposure": "consumed_development",
        "study_independence_established": False, "scientific_accuracy_established": False})
    write_json(output / "protocol.json", protocol)
    return protocol


def verify_frozen(folder, expected_protocol):
    folder = Path(folder).resolve(); protocol = read(folder / "protocol.json")
    require(sealed(protocol) and protocol.get("format") == FORMAT and protocol.get("status") == "frozen"
            and protocol["content_sha256"] == expected_protocol and protocol["policy"] == POLICY
            and protocol.get("outcomes_loaded") is False, "Use the exact reviewed frozen protocol ID.")
    require(protocol["implementation_sha256"] == implementation(), "Comparison implementation changed after freeze.")
    require(protocol["input_inventories"] == {"source": inventory(protocol["source_path"]),
            "ne_output": inventory(protocol["ne_output_path"])}, "Source/author-score inputs changed after freeze.")
    for item in protocol["reference_files"].values():
        require(sha(item["path"]) == item["sha256"], "Consumed reference bytes changed after freeze.")
    for name, expected in protocol["files"].items():
        require(sha(folder / name) == expected, "Frozen comparison output changed.")
    groups = {g["pair_id"]: g for g in read(folder / "pair_groups.json")}
    selections, diagnostics = select_arms(groups)
    require(diagnostics == protocol["diagnostics"] and diagnostics["native_ne_selected_pairs_differ"], "Frozen pair selections changed.")
    for arm in ARMS:
        actual = _isolated_view_proof(folder / arm)
        edge_ids = actual.pop("edge_ids")
        proof = protocol["arms"][arm]
        require(all(actual[key] == proof[key] for key in actual)
                and digest(edge_ids) == proof["retained_edge_ids_sha256"],
                "Actual retained view changed after freeze.")
    return protocol, groups, selections


def _fraction(numerator, denominator):
    return numerator / denominator if denominator else None


def retention_metrics(rows, arm):
    eligible = [row for row in rows if row["assay_evaluable"]]
    present = [row for row in eligible if row["graph_present"]]
    retained = [row for row in present if row["arms"][arm]["retained"]]
    removed = [row for row in present if not row["arms"][arm]["retained"]]
    detected = sum(row["detected"] for row in eligible)
    present_detected = sum(row["detected"] for row in present)
    kept_detected = sum(row["detected"] for row in retained)
    removed_nondetected = sum(not row["detected"] for row in removed)
    return {"assay_eligible_pairs": len(eligible), "detected_total": detected,
        "not_detected_total": len(eligible) - detected, "source_present_pairs": len(present),
        "source_absent_pairs": len(eligible) - len(present), "retained_pairs": len(retained),
        "pruned_pairs": len(removed), "retained_detected": kept_detected,
        "pruned_detected": present_detected - kept_detected,
        "retained_not_detected": len(retained) - kept_detected, "pruned_not_detected": removed_nondetected,
        "full_panel_detection_coverage": _fraction(kept_detected, detected),
        "detection_retention_relative_to_unpruned_present": _fraction(kept_detected, present_detected),
        "nondetection_removal_relative_to_unpruned_present": _fraction(removed_nondetected, len(present) - present_detected),
        "full_panel_nondetection_prune_fraction": _fraction(removed_nondetected, len(eligible) - detected),
        "retained_detection_fraction": _fraction(kept_detected, len(retained)),
        "full_panel_retained_pair_coverage": _fraction(len(retained), len(eligible)),
        "retained_fraction_of_source_present_assay_pairs": _fraction(len(retained), len(present))}


def joined_observations(joined, groups, selections):
    """Adapt the existing validated construct/source join without relabeling it."""
    rows = []
    for item in joined:
        candidate, assay = item["candidate"], item["assay"]
        products = candidate["products"]
        uid = pair_id(*sorted("UniProtKB:" + value for value in products))
        group = groups.get(uid)
        arms = {}
        for arm in ARMS:
            decision = ("keep" if uid in selections[arm] else "prune") if group and group["eligible"] else "abstain"
            arms[arm] = {"decision": decision, "retained": None if group is None else decision != "prune"}
        rows.append({"products": list(products), "source_row": candidate["source_row"],
            "pair_id": uid, "constructs": candidate["constructs"], "assay_status": assay["assay_status"],
            "assay_evaluable": assay["evaluable"], "detected": assay["detected"],
            "graph_present": group is not None, "pruning_eligible": bool(group and group["eligible"]),
            "source_providers": group["providers"] if group else [],
            "exposure": candidate["exposure"], "arms": arms,
            "scores": {"native": group["native_score"] if group else None,
                       "ne": group["ne_score"] if group else None}})
    return rows


def metrics_for_rows(rows, *, with_ap=False):
    arms = {arm: retention_metrics(rows, arm) for arm in ARMS}
    main = {key: (None if arms["native_top80"][key] is None or arms["ne_top80"][key] is None else
                  arms["ne_top80"][key] - arms["native_top80"][key])
            for key in ("retained_detected", "pruned_detected", "pruned_not_detected",
                        "detection_retention_relative_to_unpruned_present", "retained_detection_fraction")}
    eligible = [row for row in rows if row["assay_evaluable"]]
    ap = None
    if with_ap:
        import sklearn
        from sklearn.metrics import average_precision_score
        from score_string_component import SKLEARN_VERSION
        require(sklearn.__version__ == SKLEARN_VERSION, "Optional AP requires the existing pinned sklearn runtime.")
        ap = {}
        for name in ("native", "ne"):
            numeric = sum(row["scores"][name] is not None for row in eligible)
            positives = sum(row["detected"] for row in eligible)
            ap[name] = {"numeric_scores": numeric, "missing_tied_below_numeric": len(eligible) - numeric,
                "value": float(average_precision_score([int(row["detected"]) for row in eligible],
                    [row["scores"][name] if row["scores"][name] is not None else -1 for row in eligible]))
                    if numeric and positives else None}
    strata = {}
    for huri in (False, True):
        for inmc in (False, True):
            subset = [row for row in rows if row["exposure"]["huri_overlap"] is huri
                      and row["exposure"]["inmc_overlap"] is inmc]
            strata[f"huri={huri},inmc={inmc}"] = {"all_nominations": len(subset),
                "arms": {arm: retention_metrics(subset, arm) for arm in ARMS}}
    return {"format": FORMAT + ".metrics", "dataset_status": "consumed_development",
        "primary_endpoint": "Recorded human Y2H-v1 detection retention at the fixed source-graph removal budget.",
        "population": {"all_nominations": len(rows), "assay_eligible": len(eligible),
            "assay_excluded": len(rows) - len(eligible),
            "assay_exclusion_states": dict(sorted(Counter(row["assay_status"] for row in rows if not row["assay_evaluable"]).items())),
            "source_presence_states": {"present": sum(row["graph_present"] for row in eligible),
                                       "absent": sum(not row["graph_present"] for row in eligible)},
            "pruning_eligible_reference_pairs": sum(row["pruning_eligible"] for row in eligible)},
        "arms": arms, "ne_minus_native_at_identical_graph_budget": main,
        "budget_population": POLICY["budget_population"],
        "pruning_eligible_measured_subset": {"all_nominations": sum(row["pruning_eligible"] for row in rows),
            "arms": {arm: retention_metrics([row for row in rows if row["pruning_eligible"]], arm) for arm in ARMS}},
        "average_precision": ap, "average_precision_policy": "Secondary raw-score ranking on unpruned inputs across the full measured panel, including protected mixed STRING sources; not AP of the pruned graph. Raw score ties preserved; source-missing rows tie at -1 below explicit nonnegative scores. No operating-point ID tie-break enters AP.",
        "known_exposure_strata": strata, "confidence_intervals_computed": False,
        "scientific_accuracy_established": False, "independent_validation": False,
        "nondetection_means_biological_falsity": False,
        "note": "All assay-eligible pairs remain in the denominator. Absent graph pairs are uncovered, not pruned or false. Unflagged source exposure is not certified independence."}


def score_frozen(folder, expected_protocol, output):
    protocol, groups, selections = verify_frozen(folder, expected_protocol)
    output = new_output(output, folder, protocol["source_path"], protocol["ne_output_path"])
    write_json(output / "outcome_access_receipt.json", {"at": utcnow(), "protocol_sha256": expected_protocol,
        "purpose": "Explicit post-freeze read of the already-consumed reference; not a fresh holdout."})
    from score_string_component import _validate_join
    refs = protocol["reference_files"]
    # This is the first parse of outcomes in this runner, after all freeze/view checks.
    joined = _validate_join(read(refs["candidates"]["path"]), read(refs["assessment_rows"]["path"]),
                            read(refs["predictions"]["path"]))
    rows = joined_observations(joined, groups, selections)
    require(len(rows) == POLICY["reference_expected_nominations"]
            and sum(row["assay_evaluable"] for row in rows) == POLICY["reference_expected_eligible"],
            "The fixed complete Lambourne reference population changed.")
    metrics = metrics_for_rows(rows, with_ap=protocol["with_average_precision"])
    write_json(output / "metrics.json", metrics)
    (output / "pair_accounting.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    table = "".join("<tr>" + "".join("<td>" + escape(str(value)) + "</td>" for value in
        (arm, metrics["arms"][arm]["retained_pairs"], metrics["arms"][arm]["retained_detected"],
         metrics["arms"][arm]["pruned_detected"], metrics["arms"][arm]["pruned_not_detected"],
         metrics["arms"][arm]["retained_detection_fraction"])) + "</tr>" for arm in ARMS)
    (output / "report.html").write_text("<!doctype html><html lang='en'><meta charset='utf-8'><title>Fixed PPI pruning comparison</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:1100px;margin:40px auto;padding:0 20px}table{border-collapse:collapse}td,th{padding:9px;border:1px solid #ccc}</style>"
        "<h1>Fixed PPI task-view pruning</h1><p>Native score and author Network Enhancement retain the same declared number of eligible STRINGDB-only graph pairs. All other source records remain.</p>"
        "<p>Previously consumed human Y2H-v1 outcomes; no independent validation or universal biological-falsity claim.</p>"
        "<table><tr><th>View</th><th>Retained measured pairs</th><th>Retained detections</th><th>Removed detections</th><th>Removed nondetections</th><th>Detection fraction retained</th></tr>"
        + table + "</table><p>Source-absent pairs remain in the full reference denominator. Nondetection is assay-conditional.</p>"
        "<p><a href='metrics.json'>Complete metrics, denominators and exposure strata</a> · <a href='pair_accounting.jsonl'>Every nominated pair</a></p></html>", encoding="utf-8")
    verify_frozen(folder, expected_protocol)
    report = seal({"format": FORMAT + ".result", "status": "completed", "created_at": utcnow(),
        "protocol_sha256": expected_protocol, "model_calls": 0, "new_outcome_source_accesses": 0,
        "original_source_unchanged": True, "actual_retained_graph_contrast_verified": True,
        "scientific_accuracy_established": False, "independent_validation": False,
        "files": {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}})
    write_json(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("freeze", help="Materialize fixed views and freeze all hashes without reading outcomes.")
    p.add_argument("--source", type=Path, required=True); p.add_argument("--ne-output", type=Path, required=True)
    p.add_argument("--candidates", type=Path, required=True); p.add_argument("--assessment-rows", type=Path, required=True)
    p.add_argument("--reference-predictions", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    p.add_argument("--with-ap", action="store_true", help="Declare optional pinned-sklearn full-panel AP before outcome access.")
    p.add_argument("--decision-policy", type=Path, help="Also bind the separately declared interpretation/decision-policy file.")
    p = sub.add_parser("score", help="Explicitly join consumed assay observations after the reviewed freeze.")
    p.add_argument("--freeze", type=Path, required=True); p.add_argument("--protocol-sha256", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--allow-consumed-outcome-access", action="store_true", required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        value = freeze(args.source, args.ne_output, args.candidates, args.assessment_rows,
                       args.reference_predictions, args.out, with_ap=args.with_ap, decision_policy=args.decision_policy)
    else:
        value = score_frozen(args.freeze, args.protocol_sha256, args.out)
    print(json.dumps({key: value[key] for key in ("format", "status", "content_sha256")}, indent=2))


if __name__ == "__main__":
    main()
