"""Pure source-reported projection onto verbatim WikiPathways revision URLs.

Used by the optional exchange exporter and read-only application queries. No
historical content, biological truth, identity conversion or review promotion
is inferred by this projection.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import re
from .client import digest

VERSION = re.compile(r"(WP[1-9][0-9]*)_r([1-9][0-9]*)\Z")
PROFILE = "source-reported-exact-version-WikiPathways-URL.v1"

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


