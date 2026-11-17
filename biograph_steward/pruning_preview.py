"""Read-only projection of a completed, frozen PPI pruning assessment.

This viewer checks published bytes and retained-edge commitments. It never
replays large source graphs, changes a workspace, selects a new threshold or
interprets an unobserved pair as biologically false.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from copy import deepcopy
import csv
import hashlib
import io
import math
from pathlib import Path
import re
from threading import RLock

from .client import digest
from .gold_packet import _decode
from .lambourne_evidence import ASSAY, DOI

FORMAT = "biograph-steward.ppi-pruning-preview.v1"
SOURCE_FORMAT = "biograph-steward.ppi-pruning-comparison.v1"
ARMS = ("unpruned", "native_top80", "ne_top80")
LABELS = {"unpruned": "Original graph", "native_top80": "Native score · top 80%",
          "ne_top80": "Network Enhancement · top 80%"}
SELECTIONS = frozenset({"all", "removed", "detections_removed", "protected",
                        "unassessed", "measured", "excluded", "uncovered"})
REQUIRED_FILES = frozenset({"summary.json", "protocol.json", "result.json", "metrics.json",
                            "pair_groups.json", "pair_accounting.jsonl", "dispositions.jsonl"})
OPTIONAL_FILES = frozenset({"targets.tsv", "source_protocol.json", "decision_policy.json"})
DOWNLOAD_FILES = frozenset({"manifest.json", "summary.json", "protocol.json", "result.json",
                            "metrics.json", "pair_accounting.jsonl", "dispositions.jsonl"})
CAPS = {"manifest.json": 100_000, "summary.json": 500_000, "protocol.json": 2_000_000,
        "result.json": 100_000, "metrics.json": 500_000, "pair_groups.json": 80_000_000,
        "pair_accounting.jsonl": 20_000_000, "dispositions.jsonl": 40_000_000,
        "targets.tsv": 2_000_000, "source_protocol.json": 2_000_000,
        "decision_policy.json": 500_000}
LIMITATIONS = [
    "This is a frozen retrospective assessment, separate from the graph currently open in the workspace.",
    "The panel was already consumed in development; source-study reuse is unresolved and independence is not established.",
    "Pruning selects a task-specific view. A removed functional association is not declared biologically false.",
    "No assay observation in this panel means unassessed. Assay nondetection is conditional, not universal noninteraction.",
    "Excluded assays retain their source reason. Source-absent nominees remain uncovered, never pruned.",
    "AD and DB constructs are preserved without assigning their roles to sorted protein endpoints.",
    "Native association confidence is not calibrated for Y2H detection; NE scores are not calibrated probabilities.",
    "The graph-wide retention budget does not imply equal retained counts in the measured subset.",
    "Raw-score AP is a secondary ranking assessment on unpruned inputs, not AP of the pruned graph.",
    "This comparison does not establish superiority over the separate physical-association ranking workflow.",
    "This viewer checks published file integrity and frozen edge commitments; it does not rerun source-graph replay or authenticate scientific truth.",
]
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PAIR = re.compile(r"ppi:[0-9a-f]{24}\Z")
_cache = OrderedDict()
_cache_lock = RLock()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sealed(value):
    return (isinstance(value, dict) and isinstance(value.get("content_sha256"), str)
            and value["content_sha256"] == digest({k: v for k, v in value.items() if k != "content_sha256"}))


def ordinary(path, cap):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= cap,
            "Expected a bounded ordinary pruning-preview file.")
    raw = path.read_bytes()
    require(len(raw) <= cap, "Pruning-preview file exceeds its size limit.")
    return raw


def fingerprint(path, cap):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= cap,
            "Expected a bounded ordinary pruning-preview file.")
    h, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for raw in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(raw)
            require(size <= cap, "Pruning-preview file exceeds its size limit.")
            h.update(raw)
    return h.hexdigest()


def json_lines(raw, maximum):
    lines = raw.splitlines()
    require(len(lines) <= maximum and all(lines), "Invalid pruning-preview row population.")
    rows = [_decode(line) for line in lines]
    require(all(isinstance(row, dict) for row in rows), "Pruning-preview rows must be objects.")
    return rows


def exact_pair(subject, obj):
    require(isinstance(subject, str) and isinstance(obj, str) and subject.startswith("UniProtKB:")
            and obj.startswith("UniProtKB:") and subject < obj,
            "Expected two ordered exact protein identifiers.")
    return "ppi:" + digest({"subject": subject, "object": obj})[:24]


def target_labels(raw):
    if raw is None:
        return {}
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")), delimiter="\t")
    require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames)
            and {"id", "symbol", "name"} <= set(reader.fieldnames), "Unexpected source target table.")
    labels = {}
    for row in reader:
        require(None not in row and all(value is not None for value in row.values())
                and row["id"] not in labels and row["id"].startswith("UniProtKB:"),
                "Duplicate or malformed source target identity.")
        symbol, name = row["symbol"].strip(), row["name"].strip()
        labels[row["id"]] = {"symbol": symbol or None, "name": name or None,
                            "label": " · ".join(v for v in (symbol, name) if v) or row["id"]}
    require(len(labels) <= 100_000, "Source target table exceeds preview scope.")
    return labels


def assemble(protocol, result, metrics, groups, observations, dispositions, labels=None, source=None):
    """Project existing facts and fixed choices, without scoring or choosing cuts."""
    require(sealed(protocol) and protocol.get("format") == SOURCE_FORMAT
            and protocol.get("status") == "frozen" and protocol.get("outcomes_loaded") is False,
            "Expected a sealed frozen pruning protocol.")
    require(sealed(result) and result.get("format") == SOURCE_FORMAT + ".result"
            and result.get("status") == "completed" and result.get("protocol_sha256") == protocol["content_sha256"]
            and result.get("actual_retained_graph_contrast_verified") is True
            and result.get("original_source_unchanged") is True
            and result.get("independent_validation") is False
            and result.get("scientific_accuracy_established") is False,
            "Expected the completed retrospective pruning result.")
    require(metrics.get("format") == SOURCE_FORMAT + ".metrics"
            and metrics.get("dataset_status") == "consumed_development"
            and metrics.get("independent_validation") is False
            and metrics.get("nondetection_means_biological_falsity") is False,
            "Unsupported pruning assessment semantics.")
    require(isinstance(groups, list) and 1 <= len(groups) <= 200_000
            and isinstance(observations, list) and len(observations) <= 20_000,
            "Preview population exceeds the bounded assessment scope.")
    by_pair, edge_ids = {}, set()
    for group in groups:
        require(isinstance(group, dict) and group.get("pair_id") == exact_pair(group.get("subject"), group.get("object"))
                and group["pair_id"] not in by_pair, "Duplicate or changed source pair identity.")
        ids, providers = group.get("edge_ids"), group.get("providers")
        require(isinstance(ids, list) and ids and len(ids) == len(set(ids))
                and all(isinstance(e, str) and e.startswith("edge:") and e not in edge_ids for e in ids),
                "Source edges are missing or repeated across pairs.")
        require(isinstance(providers, list) and providers == sorted(set(providers)) and providers
                and all(isinstance(x, str) and x for x in providers), "Invalid source provider bundle.")
        require(type(group.get("eligible")) is bool and group["eligible"] == (providers == ["STRINGDB"]),
                "Pruning eligibility differs from the exact STRINGDB-only source rule.")
        for key in ("native_score", "ne_score"):
            value = group.get(key)
            require((value is None and "STRINGDB" not in providers) or
                    (type(value) in (int, float) and math.isfinite(value) and value >= 0
                     and (key != "native_score" or value <= 1)), "Unexpected raw source/NE score.")
        by_pair[group["pair_id"]] = group
        edge_ids.update(ids)
    choices, retained = {}, {arm: set() for arm in ARMS}
    for row in dispositions:
        uid, arms = row.get("pair_id"), row.get("arms")
        require(uid in by_pair and uid not in choices and isinstance(arms, dict) and set(arms) == set(ARMS),
                "Incomplete or duplicate published pair decisions.")
        group = by_pair[uid]
        for arm, choice in arms.items():
            require(choice in ({"keep"} if arm == "unpruned" else {"keep", "prune"}) if group["eligible"] else choice == "abstain",
                    "Published decisions violate protected evidence or the original view.")
            if choice != "prune":
                retained[arm].update(group["edge_ids"])
        choices[uid] = arms
    require(set(choices) == set(by_pair), "Every source pair needs exactly one set of frozen decisions.")
    for arm in ARMS:
        proof = protocol["arms"][arm]
        require(digest(sorted(retained[arm])) == proof["retained_edge_ids_sha256"]
                and len(retained[arm]) == proof["retained_edges"]
                and proof.get("all_protected_source_edges_retained") is True,
                "Published choices differ from the actual frozen graph view.")
    measured, source_rows = {}, set()
    for row in observations:
        require(isinstance(row, dict) and isinstance(row.get("products"), list)
                and len(row["products"]) == 2 and row["products"] == sorted(set(row["products"]))
                and all(isinstance(x, str) for x in row["products"]), "Malformed measured pair identity.")
        uid = exact_pair(*( "UniProtKB:" + x for x in row["products"]))
        require(uid == row.get("pair_id") and uid not in measured
                and type(row.get("source_row")) is int and row["source_row"] > 0
                and row["source_row"] not in source_rows, "Duplicate or changed measured source row.")
        evaluable, detected, status = row.get("assay_evaluable"), row.get("detected"), row.get("assay_status")
        require(type(evaluable) is bool and isinstance(status, str) and status
                and (evaluable == (status in {"detected", "not_detected"}))
                and (detected is (status == "detected") if evaluable else detected is None),
                "Assay exclusion/nondetection semantics changed.")
        present = uid in by_pair
        group = by_pair.get(uid)
        require(row.get("graph_present") is present
                and row.get("pruning_eligible") is bool(group and group["eligible"])
                and row.get("source_providers") == (group["providers"] if group else [])
                and row.get("scores") == {"native": group["native_score"] if group else None,
                                          "ne": group["ne_score"] if group else None},
                "Measured observations no longer match their source group.")
        wanted = {arm: {"decision": choices[uid][arm] if present else "abstain",
                        "retained": choices[uid][arm] != "prune" if present else None} for arm in ARMS}
        require(row.get("arms") == wanted and isinstance(row.get("constructs"), dict)
                and row["constructs"].get("protein_to_construct_orientation_inferred") is False
                and all(isinstance(row["constructs"].get(k), str) and row["constructs"][k] for k in ("ad_orf_id", "db_orf_id"))
                and isinstance(row.get("exposure"), dict), "Measured decisions or construct provenance changed.")
        measured[uid] = row; source_rows.add(row["source_row"])
    require(len(observations) == metrics["population"]["all_nominations"]
            and sum(r["assay_evaluable"] for r in observations) == metrics["population"]["assay_eligible"],
            "Published measured population differs from the completed result.")
    for arm in ARMS:
        eligible = [r for r in observations if r["assay_evaluable"]]
        present = [r for r in eligible if r["graph_present"]]
        kept = [r for r in present if r["arms"][arm]["retained"]]
        expected = {"source_present_pairs": len(present), "source_absent_pairs": len(eligible) - len(present),
                    "retained_pairs": len(kept), "pruned_pairs": len(present) - len(kept),
                    "retained_detected": sum(r["detected"] for r in kept),
                    "pruned_detected": sum(r["detected"] for r in present) - sum(r["detected"] for r in kept),
                    "pruned_not_detected": sum(not r["detected"] for r in present if not r["arms"][arm]["retained"])}
        require(all(metrics["arms"][arm].get(k) == v for k, v in expected.items()),
                "Published pair choices disagree with the completed assay counts.")
    labels = labels or {}
    if labels:
        require(len(labels) == protocol["arms"]["unpruned"]["utility"]["preserved_node_count"]
                and all(g[k] in labels for g in groups for k in ("subject", "object")),
                "Source labels differ from the graph's canonical protein inventory.")
    rows = []
    for uid in sorted(set(by_pair) | set(measured)):
        group, obs = by_pair.get(uid), measured.get(uid)
        subject, obj = ((group["subject"], group["object"]) if group else
                        tuple("UniProtKB:" + x for x in obs["products"]))
        arms = {arm: {"decision": choices[uid][arm] if group else "abstain",
                      "retained": choices[uid][arm] != "prune" if group else None} for arm in ARMS}
        assay = None if obs is None else {"source_row": obs["source_row"], "status": obs["assay_status"],
            "evaluable": obs["assay_evaluable"], "detected": obs["detected"],
            "constructs": obs["constructs"], "exposure": obs["exposure"]}
        rows.append({"pair_id": uid, "subject": subject, "object": obj,
            "edge_ids": group["edge_ids"] if group else [], "providers": group["providers"] if group else [],
            "pruning_eligible": bool(group and group["eligible"]), "graph_present": group is not None,
            "native_score": group["native_score"] if group else None,
            "ne_score": group["ne_score"] if group else None, "arms": arms, "assay": assay,
            "assay_state": "unassessed" if obs is None else "excluded" if not obs["assay_evaluable"] else
                "detected" if obs["detected"] else "not_detected",
            "labels": {"subject": labels.get(subject, {}).get("label", subject),
                       "object": labels.get(obj, {}).get("label", obj)}})
    native, ne = metrics["arms"]["native_top80"], metrics["arms"]["ne_top80"]
    advantage = (ne["retained_detected"] > native["retained_detected"] and
                 ne["retained_detected"] * native["retained_pairs"] >= native["retained_detected"] * ne["retained_pairs"])
    source_counts = source.get("counts", {}) if source else {}
    source_version = source.get("source_bindings", {}).get("database_version") if source else None
    summary = {"format": FORMAT, "title": "Fixed Pharos PPI pruning assessment", "default_arm": "unpruned",
        "scope": {"kind": "frozen_retrospective_assessment", "source_database": "Pharos",
            "source_version": source_version, "source_graph_sha256": protocol["graph_sha256"],
            "source_protein_count": protocol["arms"]["unpruned"]["utility"]["preserved_node_count"],
            "requested_protein_count": source_counts.get("requested_accessions"),
            "source_edge_count": len(edge_ids), "source_pair_count": len(groups),
            "preview_pair_count": len(rows), "dataset_status": metrics["dataset_status"],
            "reference": "Lambourne " + ASSAY, "reference_url": "https://doi.org/" + DOI,
            "current_workspace_applied": False,
            "notice": "This frozen assessment is separate from the currently open workspace. Choosing a policy only previews recorded decisions; it does not apply them."},
        "arms": {arm: {"label": LABELS[arm], "retained_edges": protocol["arms"][arm]["retained_edges"],
            "pruned_edges": len(edge_ids) - protocol["arms"][arm]["retained_edges"],
            "protected_source_edges": protocol["arms"][arm]["protected_source_edges"],
            "assay": deepcopy(metrics["arms"][arm]), "utility": deepcopy(protocol["arms"][arm]["utility"])} for arm in ARMS},
        "comparison": {"primary_decision": "bounded_NE_advantage_observed" if advantage else "tradeoff_no_clear_NE_advantage",
            "bounded_NE_advantage": advantage,
            "primary_rule": "More recorded detections retained, with no lower detection fraction among retained measured pairs, at the same whole-graph budget.",
            "average_precision": deepcopy(metrics.get("average_precision")),
            "average_precision_policy": metrics.get("average_precision_policy"),
            "budget_population": metrics.get("budget_population")},
        "provenance": {"protocol_sha256": protocol["content_sha256"], "result_sha256": result["content_sha256"],
            "packet_id": protocol["packet_id"], "source_version": source_version,
            "created_at": result["created_at"], "published_verification": "saved_file_integrity_and_frozen_edge_commitments",
            "full_source_replay_performed_by_viewer": False, "independent_validation": False},
        "limits": {"maximum_page_size": 100, "maximum_search_length": 200},
        "population": deepcopy(metrics["population"]), "limitations": list(LIMITATIONS)}
    return summary, rows


def _load(folder):
    folder = Path(folder).absolute()
    require(folder.is_dir() and not folder.is_symlink(), "Pruning preview is unavailable.")
    raw = ordinary(folder / "manifest.json", CAPS["manifest.json"])
    manifest = _decode(raw)
    require(sealed(manifest) and manifest.get("format") == FORMAT and isinstance(manifest.get("files"), dict),
            "Pruning preview manifest is invalid.")
    names = set(manifest["files"])
    require(REQUIRED_FILES <= names <= REQUIRED_FILES | OPTIONAL_FILES
            and {p.name for p in folder.iterdir()} == names | {"manifest.json"},
            "Pruning preview file inventory changed.")
    actual = {name: fingerprint(folder / name, CAPS[name]) for name in sorted(names)}
    require(actual == manifest["files"], "Pruning preview bytes changed; contents withheld.")
    key = (str(folder.resolve()), hashlib.sha256(raw).hexdigest(), tuple(actual.items()))
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    data = {name: ordinary(folder / name, CAPS[name]) for name in names}
    require({name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()} == actual,
            "Pruning preview changed while loading.")
    protocol, result, metrics = [_decode(data[name]) for name in ("protocol.json", "result.json", "metrics.json")]
    require(manifest.get("publication_kind") == "read_only_historical_projection"
            and manifest.get("workspace_modified") is False
            and manifest.get("new_scientific_evaluation") is False
            and manifest.get("source_protocol_sha256") == protocol.get("content_sha256")
            and manifest.get("source_result_sha256") == result.get("content_sha256"),
            "Pruning-preview publication mode or source identity changed.")
    require(hashlib.sha256(data["pair_groups.json"]).hexdigest() == protocol["files"]["pair_groups.json"]
            and hashlib.sha256(data["pair_accounting.jsonl"]).hexdigest() == result["files"]["pair_accounting.jsonl"]
            and hashlib.sha256(data["metrics.json"]).hexdigest() == result["files"]["metrics.json"],
            "Published projection differs from the frozen source/result commitments.")
    if "targets.tsv" in data:
        require(hashlib.sha256(data["targets.tsv"]).hexdigest() == protocol["input_inventories"]["source"]["ordinary_run/targets.tsv"],
                "Source protein labels do not match the frozen target table.")
    source = _decode(data["source_protocol.json"]) if "source_protocol.json" in data else None
    if source is not None:
        require(sealed(source) and source.get("content_sha256") == protocol["source_protocol_sha256"]
                and source.get("graph_sha256") == protocol["graph_sha256"], "Source metadata binding changed.")
    if "decision_policy.json" in data:
        require(hashlib.sha256(data["decision_policy.json"]).hexdigest() == protocol["reference_files"]["decision_policy"]["sha256"],
                "Interpretation policy differs from the frozen decision rule.")
    summary, rows = assemble(protocol, result, metrics, _decode(data["pair_groups.json"]),
        json_lines(data["pair_accounting.jsonl"], 20_000), json_lines(data["dispositions.jsonl"], 200_000),
        target_labels(data.get("targets.tsv")), source)
    require(_decode(data["summary.json"]) == summary, "Pruning-preview summary disagrees with its source projection.")
    with _cache_lock:
        _cache[key] = (summary, rows)
        while len(_cache) > 1:
            _cache.popitem(last=False)
    return summary, rows


def load_preview(folder):
    """Verify published integrity and return small, mutation-safe metadata."""
    return deepcopy(_load(folder)[0])


def list_previews(root):
    root = Path(root).resolve()
    items = []
    for run in sorted(root.iterdir(), reverse=True):
        if run.is_symlink() or not run.is_dir() or not _SAFE_ID.fullmatch(run.name):
            continue
        folder = run / "pruning_preview"
        if not (folder / "manifest.json").is_file():
            continue
        try:
            summary = load_preview(folder)
            items.append({"id": run.name, "title": summary["title"], "created_at": summary["provenance"]["created_at"],
                          "source_protein_count": summary["scope"]["source_protein_count"],
                          "source_edge_count": summary["scope"]["source_edge_count"],
                          "dataset_status": summary["scope"]["dataset_status"]})
        except (ValueError, TypeError, KeyError, OSError):
            continue
    return {"previews": items[:20]}


def query_pairs(folder, *, arm="unpruned", selection="all", search="", offset=0, limit=25):
    require(arm in ARMS and selection in SELECTIONS and isinstance(search, str) and len(search) <= 200
            and (not search or search.isprintable())
            and type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 100,
            "Invalid pruning-preview query.")
    _, rows = _load(folder)
    terms = search.casefold().split()
    def selected(row):
        assay, choice = row["assay"], row["arms"][arm]
        if selection == "removed" and choice["decision"] != "prune": return False
        if selection == "detections_removed" and not (choice["decision"] == "prune" and row["assay_state"] == "detected"): return False
        if selection == "protected" and not (row["graph_present"] and not row["pruning_eligible"]): return False
        if selection == "unassessed" and row["assay_state"] != "unassessed": return False
        if selection == "measured" and not (assay and assay["evaluable"]): return False
        if selection == "excluded" and row["assay_state"] != "excluded": return False
        if selection == "uncovered" and row["graph_present"]: return False
        if not terms: return True
        haystack = " ".join(str(x) for x in [row["pair_id"], row["subject"], row["object"],
            *row["labels"].values(), *row["providers"], *row["edge_ids"],
            *(assay["constructs"].values() if assay else []), assay["source_row"] if assay else ""]).casefold()
        return all(term in haystack for term in terms)
    matching = [row for row in rows if selected(row)]
    return {"arm": arm, "selection": selection, "search": search, "offset": offset,
            "limit": limit, "total": len(matching), "rows": deepcopy(matching[offset:offset + limit])}


def pair_detail(folder, pair_id):
    require(isinstance(pair_id, str) and _PAIR.fullmatch(pair_id), "Invalid pruning pair identifier.")
    _, rows = _load(folder)
    found = next((row for row in rows if row["pair_id"] == pair_id), None)
    if found is None:
        raise KeyError("Pruning pair not found in this published assessment.")
    return deepcopy(found)


def read_download(folder, name):
    require(name in DOWNLOAD_FILES, "This pruning-preview file is not available for download.")
    _load(folder)
    data = ordinary(Path(folder) / name, CAPS[name])
    manifest = _decode(ordinary(Path(folder) / "manifest.json", CAPS["manifest.json"]))
    require(sealed(manifest) and manifest.get("format") == FORMAT
            and (name == "manifest.json" or hashlib.sha256(data).hexdigest() == manifest["files"].get(name)),
            "Pruning-preview download changed while reading.")
    return data
