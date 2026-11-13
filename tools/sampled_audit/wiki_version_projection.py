#!/usr/bin/env python3
"""Optional source-reported membership projection onto exact version URLs.

The source's WikiPathways URL is used verbatim. No URI identity conversion,
revision collapse, native-content verification or scientific truth is inferred.
This JSONL exchange view is separate from the app and standard-export profile.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha

FORMAT = "biograph-steward.exact-version-wikipathways-projection.v1"
PROFILE = "source-reported-exact-version-WikiPathways-URL.v1"
MANIFEST = "projection_manifest.json"
ROWS = ("nodes", "edges", "edge_mapping", "node_mapping", "assertion_mapping", "resource_mapping")
VERSION = re.compile(r"(WP[1-9][0-9]*)_r([1-9][0-9]*)\Z")
BOUNDARIES = {"source_graph_changed": False, "review_states_changed": False, "duplicate_triples_merged": False,
    "native_version_content_verified": False, "scientific_accuracy_measured": False,
    "standards_validation_executed": False, "full_standard_conformance_claimed": False,
    "new_protein_interactions_inferred": False, "downstream_utility_tested": False,
    "model_calls": 0, "source_fetches": 0}
LIMITS = [
    "Memberships are reported by the preserved source, not independently validated biology.",
    "A version-labelled source URL does not verify retrieval or content of that historical model; public links may redirect to current content.",
    "Different revisions and unversioned identifiers are never collapsed.",
    "Repeated triples keep distinct original evidence IDs and are not independent experiments.",
    "Excluded records remain in the complete preserved source; exclusion is not pruning or a biological negative.",
    "Shared pathway context is not a new protein interaction; downstream utility remains untested.",
    "Membership stays directed protein-to-pathway; A-to-version-from-B is shared context, not a new directed protein-to-protein path.",
    "No KGX validator, Biolink conformance or new identifier identity mapping is claimed.",
]


def need(condition, message):
    if not condition:
        raise ValueError("WikiPathways version projection: " + message)


def version_url(value, full_id):
    """Recognize only the explicit legacy version-URL convention in the source."""
    if not isinstance(value, str) or not isinstance(full_id, str) or not VERSION.fullmatch(full_id):
        return False
    # URL parsers can discard controls or separate params from the path. Match
    # the source literal directly; do not canonicalize it into an eligible ID.
    return any(value == scheme + "://" + host + "/instance/" + full_id
               for scheme in ("http", "https")
               for host in ("www.wikipathways.org", "wikipathways.org"))


def project_graph(graph):
    """Pure projection, with every original evidence and assertion accounted for."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    assertions = {a["id"]: a for a in graph["assertions"]}
    need(len(nodes) == len(graph["nodes"]) and len(assertions) == len(graph["assertions"])
         and len({e["id"] for e in graph["edges"]}) == len(graph["edges"]), "source identities are not unique.")
    groups, local_versions = defaultdict(list), defaultdict(set)
    for edge in graph["edges"]:
        assertion = assertions.get(edge.get("assertion_id"))
        need(assertion is not None and edge["subject"] in nodes and edge["object"] in nodes
             and all(assertion.get(k) == edge.get(k) for k in ("subject", "predicate", "object"))
             and assertion.get("kind") == edge.get("record_kind")
             and edge["id"] in assertion.get("evidence_edge_ids", []), "source assertion/evidence binding differs.")
        raw = edge.get("evidence_record", {})
        if edge.get("record_kind") == "pathway_membership" and raw.get("type") == "WikiPathways":
            full_id = raw.get("sourceID")
            local_versions[edge["object"]].add(digest({"provider": raw["type"], "source_id": full_id}))
            if isinstance(full_id, str) and VERSION.fullmatch(full_id):
                key = (raw["type"], full_id)
                groups[key].append(edge)
    conflicts = {key for key, edges in groups.items()
                 if len({digest({k: v for k, v in e["evidence_record"].items() if k != "pwid"})
                         for e in edges}) != 1}
    projected, ledger, used, resources = [], [], {}, {}
    assertion_edges = defaultdict(list)
    for index, edge in enumerate(graph["edges"]):
        assertion = assertions[edge["assertion_id"]]
        raw, reasons, target = edge.get("evidence_record", {}), [], None
        full_id = raw.get("sourceID")
        key = ((raw.get("type"), full_id)
               if isinstance(full_id, str) and VERSION.fullmatch(full_id) else None)
        if edge.get("record_kind") != "pathway_membership" or raw.get("type") != "WikiPathways":
            reasons.append("outside_exact_version_WikiPathways_profile")
        else:
            full_id, url = raw.get("sourceID"), raw.get("url")
            if not isinstance(full_id, str) or VERSION.fullmatch(full_id) is None:
                reasons.append("unversioned_or_unsupported_source_identifier")
            if not version_url(url, full_id):
                reasons.append("missing_or_unsupported_exact_version_source_URL")
            if key in conflicts:
                reasons.append("conflicting_native_metadata_for_exact_provider_and_full_version")
            if key is not None and len(local_versions[edge["object"]]) != 1:
                reasons.append("local_pathway_identifier_has_conflicting_version_metadata")
            if edge.get("primary_source_raw") != "WikiPathways" or edge.get("predicate") != "biolink:participates_in":
                reasons.append("source_provider_or_predicate_outside_profile")
            if edge.get("symmetric") is True or assertion.get("symmetric") is True:
                reasons.append("symmetric_membership_outside_profile")
            if edge["object"] != "pharos.pathway:" + str(raw.get("pwid")) or nodes[edge["object"]].get("category") != "biolink:Pathway":
                reasons.append("native_local_pathway_binding_differs")
            subject = nodes[edge["subject"]]
            if (subject.get("category") != "biolink:Protein" or subject.get("identifier_mapped") is not True
                    or not re.fullmatch(r"UniProtKB:[A-Z0-9]{6}(?:[A-Z0-9]{4})?(?:-[1-9][0-9]*)?", edge["subject"])):
                reasons.append("subject_identity_outside_profile")
            if any(v is not None for item in (edge, assertion) for v in item.get("qualifiers", {}).values()):
                reasons.append("nonempty_qualification_requires_a_separate_semantic_profile")
            if not isinstance(raw.get("name"), str) or not raw["name"].strip():
                reasons.append("native_pathway_name_unavailable")
            if not reasons:
                target = url
                used[edge["subject"]] = {"id": edge["subject"], "category": [subject["category"]], "name": subject["name"]}
                used[target] = {"id": target, "category": ["biolink:Pathway"], "name": raw["name"]}
                resources[key] = {"id": target, "source_provider": raw["type"], "full_source_id": full_id,
                    "native_metadata_without_local_pwid": {k: deepcopy(v) for k, v in raw.items() if k != "pwid"}}
                projected.append({"id": edge["id"], "subject": edge["subject"], "predicate": edge["predicate"],
                    "object": target, "symmetric": False,
                    "source_assertion_id": assertion["id"], "source_pathway_id": edge["object"],
                    "source_pwid": raw["pwid"], "source_assertion_lifecycle_state": assertion.get("lifecycle_state"),
                    "source_evidence_status": edge.get("status"), "interpretation": "source_reported_membership_not_scientific_validation"})
        entry = {"source_edge_id": edge["id"], "source_assertion_id": assertion["id"],
            "source_subject_id": edge["subject"], "source_pathway_id": edge["object"],
            "source_pwid": raw.get("pwid"), "source_provider": raw.get("type"), "full_source_id": raw.get("sourceID"),
            "status": "represented" if target else "preserved_outside_projection", "reasons": reasons,
            "projection_edge_id": edge["id"] if target else None, "projection_object": target,
            "source_edge_sha256": digest(edge), "source_assertion_sha256": digest(assertion),
            "source_edge_locator": "source_retained_package/retained_graph.json#/edges/" + str(index),
            "source_qualifiers": deepcopy(edge.get("qualifiers", {})),
            "source_assertion_qualifiers": deepcopy(assertion.get("qualifiers", {})),
            "source_evidence_status": edge.get("status"), "source_lifecycle_state": edge.get("lifecycle_state"),
            "source_assertion_lifecycle_state": assertion.get("lifecycle_state"),
            "review_history_preserved_in_source": True}
        ledger.append(entry)
        assertion_edges[assertion["id"]].append(entry)
    by_edge = {entry["source_edge_id"]: entry for entry in ledger}
    resource_ledger = []
    for key, edges in sorted(groups.items(), key=lambda x: repr(x[0])):
        full_id = key[1]
        match = VERSION.fullmatch(full_id) if isinstance(full_id, str) else None
        represented = resources.get(key)
        resource_ledger.append({"source_provider": key[0], "full_source_id": full_id,
            "status": "represented" if represented else "preserved_outside_projection",
            "reasons": sorted({reason for e in edges for reason in by_edge[e["id"]]["reasons"]}),
            "projection_node_id": represented["id"] if represented else None,
            "source_edge_ids": [e["id"] for e in edges], "source_assertion_ids": [e["assertion_id"] for e in edges],
            "source_pathway_ids": [e["object"] for e in edges], "source_pwids": [e["evidence_record"].get("pwid") for e in edges],
            "native_metadata": deepcopy(represented), "native_version_content_verified": False,
            "source_identifier_version_relation": ({"subject": full_id, "predicate": "http://purl.org/dc/terms/isVersionOf",
                "object": match.group(1), "content_equivalence": False, "graph_edge_created": False} if match else None)})
    node_targets = defaultdict(set)
    for edge in projected:
        node_targets[edge["subject"]].add(edge["subject"])
        node_targets[edge["source_pathway_id"]].add(edge["object"])
    node_ledger = [{"source_node_id": n["id"], "source_node_sha256": digest(n),
        "projection_node_ids": sorted(node_targets[n["id"]]),
        "status": "represented" if node_targets[n["id"]] else "preserved_outside_projection"} for n in graph["nodes"]]
    assertion_ledger = []
    for assertion in graph["assertions"]:
        rows = assertion_edges[assertion["id"]]
        count = sum(r["status"] == "represented" for r in rows)
        assertion_ledger.append({"source_assertion_id": assertion["id"], "source_assertion_sha256": digest(assertion),
            "status": "represented" if rows and count == len(rows) else "partially_represented" if count else "preserved_outside_projection",
            "source_edge_ids": list(assertion["evidence_edge_ids"]),
            "projection_edge_ids": [r["projection_edge_id"] for r in rows if r["projection_edge_id"] is not None],
            "source_lifecycle_state": assertion.get("lifecycle_state")})
    return {"profile": PROFILE, "nodes": [used[k] for k in sorted(used)], "edges": projected,
        "edge_mapping": ledger, "node_mapping": node_ledger, "assertion_mapping": assertion_ledger,
        "resource_mapping": resource_ledger,
        "counts": {"source_nodes": len(nodes), "source_edges": len(graph["edges"]), "source_assertions": len(assertions),
            "projected_nodes": len(used), "projected_edges": len(projected), "version_resources": len(resources),
            "projected_subjects": len({e["subject"] for e in projected}),
            "distinct_subject_version_claims": len({(e["subject"], e["object"]) for e in projected}),
            "preserved_outside_projection": len(ledger) - len(projected),
            "exclusions_by_reason": dict(sorted(Counter(r for e in ledger for r in e["reasons"]).items()))}}


def _inventory(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and p != folder / MANIFEST}


def _verify_rows(folder, replay):
    for name in ROWS:
        actual = [gold_packet._decode(line) for line in (folder / (name + ".jsonl")).read_bytes().splitlines()]
        need(actual == replay[name], "projection does not replay: " + name)


def export_projection(retained, output, *, retained_report_sha256):
    implementation_pin = sha(Path(__file__))
    retained = Path(retained).absolute()
    need(re.fullmatch(r"[0-9a-f]{64}", retained_report_sha256 or "")
         and sha(retained / "report.json") == retained_report_sha256, "retained report differs from the explicit pin.")
    source_report, graph = gold_packet.load_decisions(retained)
    projection = project_graph(graph)
    folder = new_output(output, retained)
    copied = folder / "source_retained_package"
    shutil.copytree(retained, copied)
    copied_report, copied_graph = gold_packet.load_decisions(copied)
    need(copied_report == source_report and copied_graph == graph
         and sha(copied / "report.json") == retained_report_sha256, "preserved retained package differs.")
    for name in ROWS:
        gold_packet._jsonl(folder / (name + ".jsonl"), projection[name])
    need(gold_packet.load_decisions(retained)[0] == source_report
         and sha(retained / "report.json") == retained_report_sha256, "source changed during projection export.")
    need(gold_packet.load_decisions(copied)[0] == source_report, "preserved source changed during export.")
    _verify_rows(folder, projection)
    need(sha(Path(__file__)) == implementation_pin, "implementation changed during projection export.")
    report = {"format": FORMAT, "profile": PROFILE, "created_at": utcnow(),
        "source_retained_report_sha256": retained_report_sha256,
        "source_retained_report_content_sha256": source_report["content_sha256"],
        "source_retained_graph_sha256": source_report["retained_graph_sha256"],
        "source_packet_id": source_report["packet_id"], "counts": projection["counts"],
        **BOUNDARIES, "limits": LIMITS,
        "implementation_sha256": implementation_pin, "files": _inventory(folder)}
    report["content_sha256"] = digest(report)
    write_json(folder / MANIFEST, report)
    try:
        verify_projection(folder)
    except Exception:
        (folder / MANIFEST).unlink(missing_ok=True)
        raise
    return report


def verify_projection(folder):
    folder = Path(folder)
    need(folder.is_dir() and not folder.is_symlink() and not any(p.is_symlink() for p in folder.rglob("*")),
         "projection must contain ordinary files/directories.")
    report = gold_packet._read(folder / MANIFEST)
    need(gold_packet._sealed(report) and report.get("format") == FORMAT and report.get("profile") == PROFILE,
         "projection identity or seal differs.")
    need(all(type(report.get(k)) is type(v) and report[k] == v for k, v in BOUNDARIES.items())
         and report.get("limits") == LIMITS, "projection interpretation boundary differs.")
    need(report.get("files") == _inventory(folder), "projection file inventory or bytes changed.")
    source_report, graph = gold_packet.load_decisions(folder / "source_retained_package")
    need(sha(folder / "source_retained_package/report.json") == report["source_retained_report_sha256"]
         and source_report["content_sha256"] == report["source_retained_report_content_sha256"]
         and source_report["retained_graph_sha256"] == report["source_retained_graph_sha256"]
         and source_report["packet_id"] == report["source_packet_id"], "preserved source binding differs.")
    replay = project_graph(graph)
    need(replay["counts"] == report["counts"], "projection counts do not replay.")
    _verify_rows(folder, replay)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    build = modes.add_parser("export")
    build.add_argument("--retained", type=Path, required=True)
    build.add_argument("--retained-report-sha256", required=True)
    build.add_argument("--out", type=Path, required=True)
    check = modes.add_parser("verify")
    check.add_argument("--projection", type=Path, required=True)
    args = parser.parse_args()
    report = (export_projection(args.retained, args.out, retained_report_sha256=args.retained_report_sha256)
              if args.mode == "export" else verify_projection(args.projection))
    print(report["content_sha256"])


if __name__ == "__main__":
    main()
