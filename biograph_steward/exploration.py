"""Read-only, bounded annotation paths over a replayed workspace graph.

This is ordinary simple-path traversal, not a biological inference engine. The
core package has no graph-library dependency. NetworkX's ``all_simple_paths``
documents the same no-repeated-node and hop-cutoff semantics, and warns that
enumeration can grow factorially. This small deque wrapper additionally caps
work, carries qualified assertion/source records and uses our existing review
and explicit-symmetry policies. It does not invent an inverse relationship.

References:
https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.simple_paths.all_simple_paths.html
https://docs.python.org/3.10/library/collections.html#collections.deque
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from copy import deepcopy

from .client import digest
from .questions import INSPECTABLE, graph_basis

FORMAT = "biograph-steward.annotation-exploration.v1"
MAX_HOPS = 3
MAX_PATHS = 50
MAX_EXPANSIONS = 20_000


def _index(rows, label):
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"Workspace {label} must be a list of records.")
    result = {}
    for row in rows:
        uid = row.get("id")
        if not isinstance(uid, str) or not uid.strip() or uid in result:
            raise ValueError(f"Workspace {label} need unique nonempty identifiers.")
        result[uid] = row
    return result


def resolve_entity(graph, selector):
    """Resolve saved node IDs, then unambiguous saved names/symbols only."""
    if not isinstance(selector, str) or not selector.strip() or len(selector) > 300:
        raise ValueError("Choose an entity from this saved workspace.")
    nodes = _index(graph.get("nodes"), "nodes")
    value = selector.strip()
    # Bare accessions are already a supported protein selector in questions.py.
    for uid in (value, "UniProtKB:" + value):
        if uid in nodes:
            return uid
    matches = sorted(uid for uid, node in nodes.items() if any(
        isinstance(node.get(key), str) and node[key].casefold() == value.casefold()
        for key in ("sym", "symbol", "name")))
    if len(matches) > 1:
        raise ValueError("Ambiguous entity; choose an exact identifier: " + ", ".join(matches))
    if not matches:
        raise ValueError("Entity is outside this saved workspace; choose a returned identifier.")
    return matches[0]


def _selection(values, available, label):
    if values is None:
        return None
    if (not isinstance(values, (list, tuple)) or not values
            or any(not isinstance(value, str) or value not in available for value in values)):
        raise ValueError(f"Choose {label} present in this saved workspace.")
    return sorted(set(values))


def explore_paths(graph, source, target=None, *, max_hops=2, view="candidates",
                  predicates=None, node_categories=None, max_paths=20,
                  max_expansions=2000):
    """Return shortest-hop-first simple paths and the exact evidence they use.

    ``view='accepted'`` requires every assertion to have recorded acceptance.
    ``view='candidates'`` also includes candidate/provisional assertions but keeps
    those states explicit. Both views require structurally usable source rows.
    Only a stored ``symmetric is True`` flag permits reverse traversal. Node
    categories, if selected, constrain all visited nodes including endpoints.
    A missing path describes this saved scope/filter/cap, not biological absence.
    """
    for value, maximum, label in ((max_hops, MAX_HOPS, "hops"),
                                   (max_paths, MAX_PATHS, "paths"),
                                   (max_expansions, MAX_EXPANSIONS, "expansions")):
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f"Use 1–{maximum} {label}.")
    if view not in {"accepted", "candidates"}:
        raise ValueError("Evidence view must be accepted or candidates.")
    nodes = _index(graph.get("nodes"), "nodes")
    assertions = _index(graph.get("assertions"), "assertions")
    edges = _index(graph.get("edges"), "edges")
    source_id = resolve_entity(graph, source)
    target_id = None if target is None else resolve_entity(graph, target)
    if source_id == target_id:
        raise ValueError("Choose distinct source and target entities, or leave the target open.")
    predicates = _selection(predicates, {a.get("predicate") for a in assertions.values()}, "relationships")
    node_categories = _selection(node_categories, {n.get("category") for n in nodes.values()}, "entity categories")
    if node_categories is not None and any(
            nodes[uid].get("category") not in node_categories
            for uid in (source_id, target_id) if uid is not None):
        raise ValueError("Selected entity categories must include both chosen endpoints.")

    excluded = Counter()
    adjacency = defaultdict(list)
    usable = {}
    for aid, assertion in sorted(assertions.items()):
        subject, obj = assertion.get("subject"), assertion.get("object")
        if subject not in nodes or obj not in nodes:
            raise ValueError("Workspace assertion refers to an unknown node.")
        if not isinstance(assertion.get("predicate"), str) or not assertion["predicate"].strip():
            raise ValueError("Workspace assertion is missing its relationship.")
        state = assertion.get("lifecycle_state")
        if state not in INSPECTABLE:
            excluded["assertions_outside_inspectable_review_states"] += 1
            continue
        if view == "accepted" and state != "accepted":
            excluded["assertions_without_recorded_acceptance"] += 1
            continue
        if predicates is not None and assertion["predicate"] not in predicates:
            excluded["assertions_outside_selected_relationships"] += 1
            continue
        if node_categories is not None and any(
                nodes[uid].get("category") not in node_categories for uid in (subject, obj)):
            excluded["assertions_outside_selected_entity_categories"] += 1
            continue
        evidence_ids = assertion.get("structurally_usable_evidence_ids")
        if not isinstance(evidence_ids, list):
            raise ValueError("Workspace assertion is missing its evidence ledger.")
        if any(eid not in edges for eid in evidence_ids):
            raise ValueError("Workspace assertion refers to an unknown evidence record.")
        evidence = [edges[eid] for eid in sorted(set(evidence_ids))
                    if edges[eid].get("status") == "passed_structural_checks"]
        if not evidence:
            excluded["assertions_without_structurally_usable_evidence"] += 1
            continue
        if any((e.get("subject"), e.get("predicate"), e.get("object")) !=
               (subject, assertion["predicate"], obj) for e in evidence):
            raise ValueError("Workspace evidence endpoints disagree with their assertion.")
        qualifiers = assertion.get("qualifiers", {})
        if not isinstance(qualifiers, dict) or any(not isinstance(e.get("qualifiers", {}), dict) for e in evidence):
            raise ValueError("Workspace assertion and evidence qualifiers must be records.")
        # Assertion identity fills absent core slots with null; this is the only
        # representational difference permitted between an edge and its claim.
        nonnull_qualifiers = {key: value for key, value in qualifiers.items() if value is not None}
        if any({key: value for key, value in e.get("qualifiers", {}).items() if value is not None}
               != nonnull_qualifiers for e in evidence):
            raise ValueError("Workspace evidence qualifiers disagree with their assertion.")
        usable[aid] = (assertion, evidence)
        adjacency[subject].append((obj, aid, "forward"))
        # The normalizer marks Pharos interaction annotations symmetric. Assay
        # bait/prey and other directed records remain one-way; never guess.
        if assertion.get("symmetric") is True and subject != obj:
            adjacency[obj].append((subject, aid, "reverse_symmetric"))
    for row in adjacency.values():
        row.sort()

    query = {"source_id": source_id, "target_id": target_id, "max_hops": max_hops,
             "view": view, "predicates": predicates, "node_categories": node_categories,
             "max_paths": max_paths, "max_expansions": max_expansions}
    basis = graph_basis(graph)
    frontier = deque([([source_id], [])])
    paths = []
    expansions = 0
    truncation = None
    while frontier and truncation is None:
        node_ids, traversals = frontier.popleft()
        for neighbor, aid, direction in adjacency[node_ids[-1]]:
            if expansions >= max_expansions:
                truncation = "max_expansions"
                break
            expansions += 1
            if neighbor in node_ids:
                continue
            new_nodes = node_ids + [neighbor]
            new_traversals = traversals + [(aid, direction)]
            if target_id is None or neighbor == target_id:
                # Probe one further match before calling a result cap truncated.
                # Exactly max_paths total matches is still a complete search.
                if len(paths) >= max_paths:
                    truncation = "max_paths"
                    break
                identity = {"graph_basis_sha256": basis, "node_ids": new_nodes,
                            "traversals": new_traversals}
                paths.append({"id": "exploration-path:" + digest(identity)[:20],
                              "node_ids": new_nodes,
                              "assertion_ids": [a for a, _ in new_traversals],
                              "traversals": new_traversals})
            if len(new_traversals) < max_hops and neighbor != target_id:
                frontier.append((new_nodes, new_traversals))

    used_ids = sorted({aid for p in paths for aid in p["assertion_ids"]})
    citations = []
    for number, aid in enumerate(used_ids, 1):
        assertion, evidence = usable[aid]
        citations.append({"id": f"X{number:03d}", "assertion_id": aid,
            "revision": assertion.get("revision"), "subject": assertion["subject"],
            "predicate": assertion["predicate"], "object": assertion["object"],
            "kind": assertion.get("kind"), "qualifiers": deepcopy(assertion.get("qualifiers", {})),
            "review_state": assertion["lifecycle_state"],
            "source_names": deepcopy(assertion.get("source_names", [])),
            "publications": sorted({p for e in evidence for p in e.get("publications", [])}),
            "used_evidence_edge_ids": [e["id"] for e in evidence],
            "evidence_records": deepcopy(evidence)})
    citation_by_id = {c["assertion_id"]: c["id"] for c in citations}
    for path in paths:
        path["steps"] = []
        for index, (aid, direction) in enumerate(path.pop("traversals")):
            assertion = usable[aid][0]
            path["steps"].append({"assertion_id": aid,
                "from_id": path["node_ids"][index], "to_id": path["node_ids"][index + 1],
                "subject": assertion["subject"], "predicate": assertion["predicate"],
                "object": assertion["object"], "traversal_direction": direction,
                "symmetric": assertion.get("symmetric") is True,
                "qualifiers": deepcopy(assertion.get("qualifiers", {})),
                "review_state": assertion["lifecycle_state"], "citation_id": citation_by_id[aid]})
        path["hop_count"] = len(path["steps"])
        path["review_status"] = ("accepted" if all(s["review_state"] == "accepted" for s in path["steps"])
                                 else "candidate_evidence")
        path["citation_ids"] = [s["citation_id"] for s in path["steps"]]
    result = {"format": FORMAT, "query": query, "snapshot_sha256": graph["snapshot_sha256"],
        "graph_basis_sha256": basis,
        "direction_policy": "Stored subject-to-object direction; reverse traversal only where the saved assertion explicitly marks symmetric=true.",
        "interpretation": "Paths connect saved annotations. They do not establish a biological mechanism, propagate qualifiers, or validate a new endpoint relationship. Missing paths are not evidence of biological absence.",
        "review_note": "Acceptance is a recorded review decision; candidate/provisional assertions remain explicitly unaccepted. Structural checks do not establish scientific accuracy.",
        "search": {"expansions": expansions, "paths_returned": len(paths),
                   "truncated": truncation is not None, "truncation_reason": truncation,
                   "complete_within_requested_bounds": truncation is None},
        "excluded_assertions": dict(sorted(excluded.items())), "paths": paths,
        "nodes": [deepcopy(nodes[uid]) for uid in sorted({uid for p in paths for uid in p["node_ids"]})],
        "assertions": [deepcopy(usable[aid][0]) for aid in used_ids], "citations": citations}
    for key in ("civic_snapshot_sha256", "assay_publication_sha256", "assay_attachment_sha256"):
        if graph.get(key):
            result[key] = graph[key]
    return result
