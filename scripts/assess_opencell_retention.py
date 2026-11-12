#!/usr/bin/env python3
"""Freeze preselected graph views, then score author-native OpenCell retention.

Freeze hashes reference files as opaque bytes. Score explicitly opens the native
call table only after verifying the protocol and every bound input. Neither
stage chooses a ranking, changes a source graph, retrieves data or calls a model.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha

FORMAT = "biograph-steward.opencell-positive-retention.v1"
SOURCE_FORMAT = "biograph-steward.qualified-historical-ranking-input.v1"
ARMS = ("unpruned", "native_top80", "pa_top80", "ne_top80",
        "human_experimental_top80", "mps_top80", "combined_experimental_top80")
PRIMARY = "human_experimental_top80"
CONTROLS = ("native_top80", "pa_top80")
PAIR_COLUMNS = ("pair_id", "subject", "object", "edge_id", "source_bundle", "weight", "pruning_eligible")
NODE_COLUMNS = ("node_id", "resolution_status", "canonical_graph_node_present")
RAW_COLUMNS = ("", "experiment", "target", "prey", "protein_ids", "pvals", "enrichment")
UNIPROT = re.compile(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[0-9]+)?\Z")
MIN_PAIRS = 100
MIN_BAITS = 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def seal(value):
    return {**value, "content_sha256": digest(value)}


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON object key.")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


def sealed(value):
    return (isinstance(value, dict) and value.get("content_sha256") ==
            digest({key: item for key, item in value.items() if key != "content_sha256"}))


def tsv(path, columns):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(reader.fieldnames == list(columns), f"Unexpected columns in {Path(path).name}.")
        result = list(reader)
    require(all(None not in row and all(value is not None for value in row.values()) for row in result),
            "Malformed TSV row.")
    return result


def boolean(value):
    require(value in {"true", "false"}, "Membership and eligibility must be literal true/false.")
    return value == "true"


def protein(value):
    require(isinstance(value, str) and value.startswith("UniProtKB:")
            and UNIPROT.fullmatch(value[10:]), "Expected an exact UniProtKB protein identifier.")
    return value[10:]


def load_source(source_dir):
    folder = Path(source_dir)
    qualification = read_json(folder / "source_qualification.json")
    require(sealed(qualification) and qualification.get("format") == SOURCE_FORMAT,
            "Expected a sealed historical source qualification.")
    require(qualification.get("new_assay_calls_accessed") is False
            and qualification.get("original_graph_modified") is False
            and qualification.get("node_universe_preserved") is True,
            "Source qualification must precede reference access and preserve the source graph.")
    for name in ("graph_pairs.tsv", "network_nodes.tsv", "weighted_pairs.tsv", "source_pair_qualification.jsonl"):
        require(qualification.get("qualified_inputs_sha256", {}).get(name) == sha(folder / name),
                f"Qualified source hash mismatch: {name}.")
    pairs = tsv(folder / "graph_pairs.tsv", PAIR_COLUMNS)
    nodes = tsv(folder / "network_nodes.tsv", NODE_COLUMNS)
    require(nodes and len({row["node_id"] for row in nodes}) == len(nodes), "Duplicate or empty node inventory.")
    inventory_ids = {protein(row["node_id"]) for row in nodes}
    require(len(inventory_ids) == len(nodes), "Duplicate node identity in method inventory.")
    # The method inventory can preserve a requested-but-unresolved isolated ID.
    # It is not a protein record in the original canonical source graph.
    node_ids = {protein(row["node_id"]) for row in nodes if boolean(row["canonical_graph_node_present"])}
    by_id, by_endpoints = {}, {}
    for row in pairs:
        left, right = protein(row["subject"]), protein(row["object"])
        require(left < right and left in node_ids and right in node_ids, "Invalid ordered source endpoints.")
        require(row["pair_id"] == "ppi:" + digest({"subject": row["subject"], "object": row["object"]})[:24],
                "Source pair identifier differs from its exact endpoints.")
        require(row["pair_id"] not in by_id and (left, right) not in by_endpoints, "Duplicate source pair.")
        boolean(row["pruning_eligible"])
        by_id[row["pair_id"]] = row
        by_endpoints[(left, right)] = row
    ledger = {}
    for line in (folder / "source_pair_qualification.jsonl").read_text().splitlines():
        row = json.loads(line)
        require(row["pair_id"] in by_id and row["pair_id"] not in ledger, "Duplicate or unknown source qualification row.")
        pair = by_id[row["pair_id"]]
        require(row.get("subject") == pair["subject"] and row.get("object") == pair["object"]
                and type(row.get("qualified_pruning_eligible")) is bool
                and row["qualified_pruning_eligible"] == boolean(pair["pruning_eligible"])
                and type(row.get("original_source_protected")) is bool
                and isinstance(row.get("qualification_reasons"), list), "Inconsistent source qualification row.")
        require(type(row.get("original_pruning_eligible")) is bool
                and row["original_pruning_eligible"] != row["original_source_protected"]
                and (not row["qualified_pruning_eligible"] or
                     (row["original_pruning_eligible"] and not row["qualification_reasons"]
                      and row.get("ranking_background_present") is True))
                and (not row["qualification_reasons"] or
                     (not row["qualified_pruning_eligible"] and row.get("ranking_background_present") is False)),
                "Qualification eligibility or quarantine semantics differ.")
        ledger[row["pair_id"]] = row
    require(set(ledger) == set(by_id), "Source qualification does not cover every pair.")
    eligible = {uid for uid, row in by_id.items() if boolean(row["pruning_eligible"])}
    require(len(pairs) == qualification["original_source_pairs"]
            and len(eligible) == qualification["qualified_rankable_pairs"]
            and qualification["abstain_retained_pairs"] == len(pairs) - len(eligible)
            and qualification["retained_rankable_budget"] == len(eligible) * 4 // 5,
            "Source qualification population or integer budget differs.")
    weighted = tsv(folder / "weighted_pairs.tsv",
                   ("subject", "object", "weight", "pair_id", "edge_id", "source_bundle", "pruning_eligible"))
    require(len(weighted) == len({row["pair_id"] for row in weighted}) == qualification["qualified_weighted_pairs"],
            "Duplicate or changed qualified weighted population.")
    require({row["pair_id"] for row in weighted} ==
            {uid for uid, row in ledger.items() if row.get("ranking_background_present") is True},
            "Weighted method background differs from source qualification.")
    require(all(row["pair_id"] in by_id and not ledger[row["pair_id"]]["qualification_reasons"] for row in weighted),
            "A quarantined weight remains in the method background.")
    require(all(all(row[name] == by_id[row["pair_id"]][name] for name in
                    ("subject", "object", "edge_id", "source_bundle", "pruning_eligible", "weight"))
                for row in weighted), "Weighted row differs from its immutable source pair.")
    return qualification, by_id, by_endpoints, ledger, node_ids, eligible


def load_membership(path, by_id, eligible, budget):
    rows = tsv(path, ("pair_id", *ARMS))
    require(len(rows) == len(by_id), "Membership must cover every source pair.")
    membership = {}
    for row in rows:
        uid = row["pair_id"]
        require(uid in by_id and uid not in membership, "Duplicate or unknown membership pair.")
        membership[uid] = {arm: boolean(row[arm]) for arm in ARMS}
        require(membership[uid]["unpruned"], "The original source view must retain every pair.")
        if uid not in eligible:
            require(all(membership[uid].values()), "Protected or quarantined pairs must remain retained in every view.")
    for arm in ARMS[1:]:
        require(sum(membership[uid][arm] for uid in eligible) == budget,
                f"The preselected {arm} view violates the exact qualified eligible budget.")
    return membership


def file_binding(path, protocol_dir):
    path = Path(path).resolve()
    require(path.is_file() and not path.is_symlink(), "Input must be an ordinary local file.")
    return {"path": os.path.relpath(path, protocol_dir), "bytes": path.stat().st_size, "sha256": sha(path)}


def freeze(source_dir, membership, native_calls, raw_identities, bait_metadata, policy, output, *, artifacts=None):
    output = Path(output).resolve()
    require(not output.exists(), "Use a new frozen output directory.")
    source_dir = Path(source_dir).resolve()
    qualification, by_id, _, _, nodes, eligible = load_source(source_dir)
    load_membership(membership, by_id, eligible, qualification["retained_rankable_budget"])
    require(sha(policy) == qualification.get("candidate_policy_sha256"), "Candidate policy differs from the source qualification.")
    candidate_policy = read_json(policy)
    require(candidate_policy.get("reference_calls_opened") is False
            and candidate_policy.get("primary_candidate") == "STRING11_organism_native_experimental_channel",
            "Candidate policy must fix the organism-native experimental primary before reference access.")
    files = {name: source_dir / name for name in
             ("source_qualification.json", "graph_pairs.tsv", "network_nodes.tsv", "weighted_pairs.tsv", "source_pair_qualification.jsonl")}
    files.update({"membership": membership, "native_calls": native_calls, "raw_identities": raw_identities,
                  "bait_metadata": bait_metadata, "candidate_policy": policy,
                  "runner": Path(__file__), "client_code": ROOT / "biograph_steward/client.py",
                  "file_utils_code": ROOT / "biograph_steward/file_utils.py"})
    for label, path in (artifacts or {}).items():
        require(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", label) and "artifact_" + label not in files,
                "Artifact labels must be unique simple identifiers.")
        files["artifact_" + label] = path
    # The native calls, raw assay table and bait metadata are hashed only here.
    bindings = {name: file_binding(path, output) for name, path in sorted(files.items())}
    protocol = seal({"format": FORMAT, "status": "frozen", "created_at": utcnow(),
        "reference_calls_opened": False, "reference_statistics_interpreted": False,
        "source_qualification_sha256": qualification["content_sha256"], "input_files": bindings,
        "arms": list(ARMS), "primary_candidate": PRIMARY, "controls": list(CONTROLS),
        "source_pairs": len(by_id), "source_nodes": len(nodes),
        "method_inventory_nodes": len(tsv(source_dir / "network_nodes.tsv", NODE_COLUMNS)),
        "qualified_eligible_pairs": len(eligible),
        "eligible_retention_budget": qualification["retained_rankable_budget"],
        "abstain_retained_pairs": len(by_id) - len(eligible),
        "minimum_eligible_positive_pairs": MIN_PAIRS, "minimum_evaluable_exact_bait_labels": MIN_BAITS,
        "primary_gate": "The fixed primary arm retains strictly more qualified positive pairs than both native and PA, with at least 100 eligible positive pairs and 20 evaluable exact author bait labels.",
        "reference": "Exact frozen October 2021 OpenCell author-native positive call file; no assertion of equality to the final 2022 supplementary table.",
        "mapping": "Exact author bait label to ENSG/UniProt; exact raw target/prey identity with a single accession consistent across all raw attempts. Preserve isoforms, ambiguities and construct metadata; no guesses.",
        "denominator": "Unique unordered strictly mapped author-positive pairs present in the qualified eligible source population, shared across all arms.",
        "per_bait": "Exact author target labels with unique mapped partners. Zero-denominator labels remain in the table but are excluded from macro averages.",
        "selection_performed_by_runner": False, "raw_noncalls_evaluated": False,
        "claim_boundary": "Scoped positive coassociation retention in one HEK293T study; no precision, specificity, direct-binding, clinical or CRC-validity claim."})
    output.mkdir(parents=True)
    write_json(output / "protocol.json", protocol)
    return protocol


def verify_frozen(folder, expected_protocol):
    folder = Path(folder).resolve()
    protocol = read_json(folder / "protocol.json")
    require(sealed(protocol) and protocol.get("format") == FORMAT and protocol.get("status") == "frozen"
            and protocol.get("content_sha256") == expected_protocol
            and protocol.get("reference_calls_opened") is False
            and protocol.get("arms") == list(ARMS) and protocol.get("primary_candidate") == PRIMARY
            and protocol.get("controls") == list(CONTROLS)
            and protocol.get("minimum_eligible_positive_pairs") == MIN_PAIRS
            and protocol.get("minimum_evaluable_exact_bait_labels") == MIN_BAITS,
            "Frozen protocol is changed, unsupported or not the expected commitment.")
    paths = {}
    for role, binding in protocol["input_files"].items():
        path = (folder / binding["path"]).resolve()
        require(path.is_file() and path.stat().st_size == binding["bytes"] and sha(path) == binding["sha256"],
                f"Frozen input changed: {role}.")
        paths[role] = path
    require(paths.get("runner") == Path(__file__).resolve(), "Use the exact frozen runner.")
    return protocol, paths


def load_native_calls(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == ["", "target", "prey"], "Unexpected author-native call schema.")
        rows = []
        for line, row in enumerate(reader, 2):
            require(None not in row and all(value is not None for value in row.values()), "Malformed native call row.")
            rows.append({"source_line": line, "source_index": row[""], "target": row["target"], "prey": row["prey"]})
    return rows


def bait_indexes(metadata):
    require(isinstance(metadata, list), "Expected author cell-line metadata rows.")
    identities, details = defaultdict(set), defaultdict(list)
    incomplete_labels = set()
    for row in metadata:
        source = row.get("metadata") or {}
        uniprot = row.get("uniprot_metadata") or {}
        label, up, ensg = source.get("target_name"), uniprot.get("uniprot_id"), source.get("ensg_id")
        if label:
            details[label].append({"metadata": source, "uniprot_metadata": uniprot})
        if label:
            if (isinstance(up, str) and UNIPROT.fullmatch(up) and isinstance(ensg, str)
                    and re.fullmatch(r"ENSG[0-9]+", ensg)):
                identities[label].add((ensg, up))
            else:
                incomplete_labels.add(label)
    # An incomplete same-label row is conflicting source evidence, rather than
    # permission to resolve the label using only its complete rows.
    for label in incomplete_labels:
        identities[label].clear()
    return identities, details


def raw_identity_index(path, calls):
    requested = {(row["target"], row["prey"]) for row in calls}
    evidence = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        require(next(reader, None) == list(RAW_COLUMNS), "Unexpected raw identity schema.")
        for row in reader:
            require(len(row) == len(RAW_COLUMNS), "Malformed raw identity row.")
            _, experiment, target, prey, protein_ids, *_unused_statistics = row
            key = (target, prey)
            if key in requested:
                state = evidence.setdefault(key, {"raw_rows": 0, "experiments": set(), "protein_groups": set()})
                state["raw_rows"] += 1
                state["experiments"].add(experiment)
                state["protein_groups"].add(tuple(protein_ids.split(";")))
    return evidence


def resolve_call(row, identities, details, raw):
    result = dict(row)
    baits = sorted(identities.get(row["target"], set()))
    evidence = raw.get((row["target"], row["prey"]))
    result.update({"bait_identity_candidates": [list(item) for item in baits],
                   "source_bait_metadata_rows": details.get(row["target"], []),
                   "construct_assignment": "not_inferred_from_gene_level_native_call",
                   "raw_identity_evidence": None if evidence is None else {
                       "raw_rows": evidence["raw_rows"], "experiments": sorted(evidence["experiments"]),
                       "protein_groups": [list(item) for item in sorted(evidence["protein_groups"])]}})
    if len(baits) != 1:
        status = "missing_or_ambiguous_bait_source_identity"
    elif evidence is None:
        status = "no_exact_raw_bait_prey_identity"
    elif not evidence["protein_groups"] or any(len(group) != 1 for group in evidence["protein_groups"]):
        status = "ambiguous_or_empty_prey_protein_group"
    else:
        preys = {group[0] for group in evidence["protein_groups"]}
        if len(preys) != 1 or any(not UNIPROT.fullmatch(value) for value in preys):
            status = "inconsistent_or_invalid_prey_source_accession"
        else:
            bait, prey = baits[0][1], next(iter(preys))
            status = "self_pair" if bait == prey else "exact_source_single_accession_pair"
            if bait != prey:
                result.update({"bait_ensg_id": baits[0][0], "bait_uniprot_id": bait,
                               "prey_uniprot_id": prey, "pair": sorted((bait, prey)),
                               "isoform_accessions_preserved": True})
    result["mapping_status"] = status
    return result


def graph_utility(by_id, membership, nodes, arm):
    degree = Counter()
    retained = 0
    for uid, row in by_id.items():
        if membership[uid][arm]:
            retained += 1
            degree[protein(row["subject"])] += 1
            degree[protein(row["object"])] += 1
    return {"source_pairs_retained": retained, "source_pairs_removed": len(by_id) - retained,
            "node_records_preserved": len(nodes), "isolated_proteins": sum(not degree[node] for node in nodes)}


def summarize_calls(calls, identities, details, raw, by_id, by_endpoints, source_ledger, membership, nodes):
    ledger, primary_pairs = [], set()
    bait_partners = {row["target"]: {} for row in calls}
    for row in calls:
        resolved = resolve_call(row, identities, details, raw)
        category = "mapping_unresolved"
        if "pair" in resolved:
            pair = by_endpoints.get(tuple(resolved["pair"]))
            if pair is None:
                category = "source_absent"
            else:
                uid = pair["pair_id"]
                state = source_ledger[uid]
                resolved.update({"source_pair_id": uid, "source_qualification": state,
                                 "view_retained": membership[uid]})
                if state["original_source_protected"]:
                    category = "source_protected"
                elif state["qualification_reasons"]:
                    category = "source_quarantined"
                elif state["qualified_pruning_eligible"]:
                    category = "qualified_eligible"
                    primary_pairs.add(uid)
                    bait_partners[row["target"]][resolved["prey_uniprot_id"]] = uid
                else:
                    raise ValueError("Unexplained source abstention.")
        resolved["evaluation_category"] = category
        ledger.append(resolved)
    denominator = len(primary_pairs)
    per_bait = []
    for label, partners in sorted(bait_partners.items()):
        pair_ids = set(partners.values())
        count = len(pair_ids)
        item = {"target": label, "eligible_positive_partners": count}
        for arm in ARMS:
            kept = sum(membership[uid][arm] for uid in pair_ids)
            item[arm + "_retained"] = kept
            item[arm + "_retention"] = kept / count if count else None
        for control in CONTROLS:
            item["primary_minus_" + control] = (item[PRIMARY + "_retention"] - item[control + "_retention"]
                                                       if count else None)
        per_bait.append(item)
    evaluated = [row for row in per_bait if row["eligible_positive_partners"]]
    arms = {}
    for arm in ARMS:
        retained = sum(membership[uid][arm] for uid in primary_pairs)
        arms[arm] = {"eligible_positive_pairs": denominator, "positive_pairs_retained": retained,
                     "positive_pairs_lost": denominator - retained,
                     "micro_retention": retained / denominator if denominator else None,
                     "macro_bait_retention": (sum(row[arm + "_retention"] for row in evaluated) / len(evaluated)
                                              if evaluated else None),
                     **graph_utility(by_id, membership, nodes, arm)}
    paired = {}
    for control in CONTROLS:
        deltas = [row["primary_minus_" + control] for row in evaluated]
        paired[control] = {"positive_pair_count_difference": arms[PRIMARY]["positive_pairs_retained"] - arms[control]["positive_pairs_retained"],
                           "micro_retention_difference": (arms[PRIMARY]["micro_retention"] - arms[control]["micro_retention"]
                                                          if denominator else None),
                           "mean_bait_retention_difference": sum(deltas) / len(deltas) if deltas else None,
                           "baits_improved": sum(value > 0 for value in deltas),
                           "baits_tied": sum(value == 0 for value in deltas),
                           "baits_worse": sum(value < 0 for value in deltas),
                           "minimum_bait_difference": min(deltas) if deltas else None,
                           "maximum_bait_difference": max(deltas) if deltas else None}
    sufficient = denominator >= MIN_PAIRS and len(evaluated) >= MIN_BAITS
    advantage = all(arms[PRIMARY]["positive_pairs_retained"] > arms[control]["positive_pairs_retained"] for control in CONTROLS)
    decision = "unscorable_insufficient_coverage" if not sufficient else ("bounded_positive_retention_gain" if advantage else "no_gain_over_both_controls")
    metrics = {"native_call_rows_preserved": len(ledger),
        "mapping_status_counts": dict(sorted(Counter(row["mapping_status"] for row in ledger).items())),
        "evaluation_category_row_counts": dict(sorted(Counter(row["evaluation_category"] for row in ledger).items())),
        "primary_unique_eligible_positive_pairs": denominator,
        "all_exact_author_bait_labels": len(per_bait), "evaluable_exact_author_bait_labels": len(evaluated),
        "zero_denominator_bait_labels": len(per_bait) - len(evaluated),
        "mapped_quarantined_call_rows_including_original_protected": sum(bool(row.get("source_qualification", {}).get("qualification_reasons")) for row in ledger),
        "arms": arms, "paired_primary_vs_control": paired,
        "primary_decision": decision, "coverage_gate_passed": sufficient,
        "primary_utility_gate_passed": sufficient and advantage,
        "raw_noncalls_evaluated": False, "precision_or_scientific_accuracy_established": False,
        "inferential_p_values_or_confidence_intervals": None}
    return ledger, per_bait, metrics


def score(frozen, expected_protocol, output, *, allow_reference_calls=False):
    require(allow_reference_calls, "Scoring requires explicit --allow-reference-calls after the freeze.")
    protocol, paths = verify_frozen(frozen, expected_protocol)
    qualification, by_id, by_endpoints, source_ledger, nodes, eligible = load_source(paths["source_qualification.json"].parent)
    require(qualification["content_sha256"] == protocol["source_qualification_sha256"], "Source qualification differs from freeze.")
    membership = load_membership(paths["membership"], by_id, eligible, protocol["eligible_retention_budget"])
    output = Path(output).resolve()
    require(not output.exists(), "Use a new scoring output directory.")
    output.mkdir(parents=True)
    write_json(output / "outcome_access_receipt.json", {"format": FORMAT + ".outcome-access", "at": utcnow(),
               "protocol_sha256": expected_protocol, "action": "Open frozen author-native calls for the first scoring execution in this output directory."})
    calls = load_native_calls(paths["native_calls"])
    identities, details = bait_indexes(read_json(paths["bait_metadata"]))
    raw = raw_identity_index(paths["raw_identities"], calls)
    ledger, per_bait, metrics = summarize_calls(calls, identities, details, raw, by_id, by_endpoints,
                                               source_ledger, membership, nodes)
    with (output / "call_mapping_ledger.jsonl").open("w", encoding="utf-8") as handle:
        for row in ledger:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    columns = ("target", "eligible_positive_partners", *[value for arm in ARMS for value in (arm + "_retained", arm + "_retention")],
               *["primary_minus_" + control for control in CONTROLS])
    with (output / "per_bait_descriptive.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(per_bait)
    report = seal({"format": FORMAT + ".result", "status": "completed", "created_at": utcnow(),
        "protocol_sha256": expected_protocol, "source_qualification_sha256": qualification["content_sha256"],
        "primary_candidate": PRIMARY, "controls": list(CONTROLS), "metrics": metrics,
        "reference_scope": protocol["reference"], "claim_boundary": protocol["claim_boundary"],
        "source_graph_changed": False, "ranking_or_threshold_selection_performed": False,
        "source_nodes_preserved": len(nodes), "raw_native_call_file_copied": False,
        "audit_ledger_distribution": "Local derived audit contains native source rows; no public redistribution license is assumed.",
        "outputs_sha256": {name: sha(output / name) for name in ("outcome_access_receipt.json", "call_mapping_ledger.jsonl", "per_bait_descriptive.tsv")}})
    write_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    before = commands.add_parser("freeze")
    for name in ("source-dir", "membership", "native-calls", "raw-identities", "bait-metadata", "policy", "output"):
        before.add_argument("--" + name, type=Path, required=True)
    before.add_argument("--artifact", action="append", default=[], metavar="LABEL=PATH")
    after = commands.add_parser("score")
    after.add_argument("--frozen", type=Path, required=True)
    after.add_argument("--expected-protocol", required=True)
    after.add_argument("--output", type=Path, required=True)
    after.add_argument("--allow-reference-calls", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "freeze":
            artifacts = {}
            for value in args.artifact:
                label, separator, path = value.partition("=")
                require(separator and label not in artifacts and path, "Use unique --artifact LABEL=PATH values.")
                artifacts[label] = Path(path)
            result = freeze(args.source_dir, args.membership, args.native_calls, args.raw_identities,
                            args.bait_metadata, args.policy, args.output, artifacts=artifacts)
            print(json.dumps({"status": result["status"], "protocol_sha256": result["content_sha256"],
                              "reference_calls_opened": False, "output": str(args.output)}, indent=2))
        else:
            result = score(args.frozen, args.expected_protocol, args.output, allow_reference_calls=args.allow_reference_calls)
            print(json.dumps({"status": result["status"], "primary_decision": result["metrics"]["primary_decision"],
                              "report_sha256": result["content_sha256"], "output": str(args.output)}, indent=2))
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
