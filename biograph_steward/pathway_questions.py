"""Exact-revision source-context questions over a verified retained graph.

This common-neighbour query is explicitly about source annotations. It does
not create a protein interaction or promote candidate/review states. Evidence
groups retain every original edge and assertion; repeats do not get more votes.
"""
from collections import Counter, defaultdict
import base64
from copy import deepcopy

from .client import digest
from .questions import INSPECTABLE, graph_basis, resolve_protein
from .wiki_projection import project_graph, PROFILE

TEMPLATE = "qualified_pathway_source_context.v1"
LIMITATIONS = [
    "The graph uses the declared retained decision view. Decision replay verifies implementation, not the scientific correctness of the decisions.",
    "Shared exact-version source annotations describe A → pathway model ← B. They do not create a protein interaction, causal path or disease mechanism.",
    "Original source assertions and review states are preserved. A repeated source row is not independent experimental corroboration.",
    "A version-labelled URL identifies the source-reported model. It may redirect to latest content; this answer alone does not authenticate historical contents.",
    "Current encoded gene membership, when used by a qualification policy, is distinct from historical model content, exact protein forms and biological truth.",
    "Unknown/abstained evidence remains in the retained graph. A missing result is not evidence of biological absence.",
    "Different revisions, unversioned records, conflicting metadata, nonempty qualifiers and unresolved source identities are not merged.",
    "This question compares retrieved primary proteins. It does not infer disease association for a matching protein or claim complete pathway coverage.",
    "Alphabetical order and unique source-model paths are used; source row multiplicity does not rank confidence."
]


def answer_pathway_question(graph, protein, *, view="candidates", max_results=8, max_paths=2, source_run=None,
                            source_support=None, history=None):
    if not graph.get("qualified_view", {}).get("decision_replay_verified"):
        raise ValueError("Open a verified retained workspace to query qualified pathway source context.")
    if view not in {"accepted", "candidates"}:
        raise ValueError("Choose accepted or candidate source annotations.")
    if type(max_results) is not int or not 1 <= max_results <= 30 or type(max_paths) is not int or not 1 <= max_paths <= 5:
        raise ValueError("Use 1–30 proteins and 1–5 model paths per protein.")
    anchor = resolve_protein(graph, protein)
    binding = graph['qualified_view'].get('pathway_history')
    if binding is not None and (history is None or history['report']['content_sha256'] != binding['content_sha256']):
        raise ValueError('This source question requires its exact archived pathway proof packet.')
    source_support = (graph['qualified_view'].get('source_support_default', 'all_source_annotations')
        if source_support is None else source_support)
    if not isinstance(source_support, str) or source_support not in {'native_supported', 'all_source_annotations'}:
        raise ValueError('Choose native_supported or all_source_annotations for source context.')
    if source_support == 'native_supported' and history is None:
        raise ValueError('Archived native support is unavailable in this workspace.')
    projection = project_graph(graph)
    nodes = {n["id"]: deepcopy(n) for n in graph["nodes"]}
    for n in projection["nodes"]:
        if n["id"] not in nodes:
            nodes[n["id"]] = {**deepcopy(n), "category": n["category"][0]}
    assertions = {a["id"]: a for a in graph["assertions"]}
    source_edges = {e["id"]: e for e in graph["edges"]}
    seed = {t["id"] for t in graph["targets"]}
    groups = defaultdict(list)
    excluded = defaultdict(set)
    for row in projection["edges"]:
        assertion = assertions[row["source_assertion_id"]]
        if row["subject"] not in seed:
            excluded["outside_primary_protein_scope"].add(assertion['id'])
        elif assertion["lifecycle_state"] not in INSPECTABLE:
            excluded["rejected_quarantined_or_obsolete"].add(assertion['id'])
        else:
            if history is not None:
                full_id = source_edges[row['id']]['evidence_record']['sourceID']
                connection = history['connections'].get((row['subject'], full_id))
                if connection is None or row['id'] not in connection['original_edge_ids']:
                    raise ValueError('Native pathway support scope differs from the original source evidence.')
                if source_support == 'native_supported' and connection['status'] not in {
                        'explicitly_encoded_protein_xref', 'compatible_gene_level_xref'}:
                    excluded['native_support_unresolved_excluded_from_this_answer_not_pruned'].add(assertion['id'])
                    continue
            groups[(row["subject"], row["object"])].append(row)
    memberships = defaultdict(dict)
    grouped = {}
    for (subject, model), rows in groups.items():
        aid = "source-context:" + digest({"subject": subject, "model": model,
            "evidence": sorted(r["id"] for r in rows)})[:24]
        source_ids = sorted({r["source_assertion_id"] for r in rows})
        states = {assertions[x]["lifecycle_state"] for x in source_ids}
        state = next(iter(states)) if len(states) == 1 else "mixed_review_states"
        evidence = [deepcopy(source_edges[r["id"]]) for r in sorted(rows, key=lambda r: r["id"])]
        record = {"assertion_id": source_ids[0], "source_context_group_id": aid,
            "source_assertion_ids": source_ids, "revision": None,
            "subject": subject, "predicate": rows[0]["predicate"], "object": model,
            "kind": "pathway_membership", "qualifiers": {}, "review_state": state,
            "source_review_states": {x: assertions[x]["lifecycle_state"] for x in source_ids},
            "source_names": ["WikiPathways (source reported through Pharos)"],
            "normalization_notes": ["One displayed source-context group joins exact matching native version URLs. "
                "Its original local pathway IDs and assertions remain in the source records below.",
                "This group is not a new accepted assertion or an independent experiment."],
            "used_evidence_edge_ids": [e["id"] for e in evidence],
            "source_record_count": sum(e.get("source_record_count", len(e.get("record_locators", []))) for e in evidence),
            "evidence_records": evidence,
            "publications": sorted({p for e in evidence for p in e.get("publications", [])}),
            "source_model_id": evidence[0]["evidence_record"]["sourceID"],
            "historical_contents_verified_in_this_answer": False}
        grouped[aid] = record
        memberships[subject][model] = aid

    label = lambda uid: nodes[uid].get("sym") or nodes[uid].get("name") or uid
    matches, all_paths, accepted_paths, accepted_proteins = [], 0, 0, 0
    for uid in sorted(seed - {anchor}, key=lambda x: (label(x).casefold(), x)):
        paths = []
        common = memberships[anchor].keys() & memberships[uid].keys()
        accepted_count = 0
        for model in sorted(common, key=lambda x: (label(x).casefold(), x)):
            aids = [memberships[anchor][model], memberships[uid][model]]
            accepted = all(grouped[x]["review_state"] == "accepted" for x in aids)
            accepted_count += accepted
            if view == "accepted" and not accepted:
                continue
            paths.append({"id": "path:" + digest({"nodes": [anchor, model, uid], "groups": aids})[:20],
                "kind": "shared_pathway", "node_ids": [anchor, model, uid], "source_context_group_ids": aids,
                "assertion_ids": sorted({s for x in aids for s in grouped[x]["source_assertion_ids"]}),
                "source_assertion_ids": sorted({s for x in aids for s in grouped[x]["source_assertion_ids"]}),
                "review_status": "accepted" if accepted else "candidate_evidence",
                "assertion_states": {s: assertions[s]['lifecycle_state']
                    for x in aids for s in grouped[x]['source_assertion_ids']}})
        all_paths += len(common)
        accepted_paths += accepted_count
        accepted_proteins += bool(accepted_count)
        if paths:
            shown = paths[:max_paths]
            states = {p["review_status"] for p in shown}
            matches.append({"protein": deepcopy(nodes[uid]), "paths": shown,
                "eligible_path_count": len(paths), "omitted_paths": len(paths) - len(shown),
                "matched_relations": {"shared_pathway": len(paths)},
                "review_status": next(iter(states)) if len(states) == 1 else "mixed_review_states"})
    matching = len(matches)
    inspectable = len({uid for uid in seed - {anchor} if memberships[anchor].keys() & memberships[uid].keys()})
    matches = matches[:max_results]
    aids = list(dict.fromkeys(a for row in matches for p in row["paths"] for a in p["source_context_group_ids"]))
    citations = [{"id": f"E{i:03d}", **deepcopy(grouped[aid])} for i, aid in enumerate(aids, 1)]
    historical_models = {}
    if history is not None:
        from .wiki_history import query_history
        for citation in citations:
            native = query_history(history, citation['subject'], citation['source_model_id'])
            citation['historical_source'] = native
            citation['historical_contents_verified_in_this_answer'] = native.get('model', {}).get('exact_publisher_revision_binding') is True
            if source_support == 'native_supported' and native['status'] not in {
                    'explicitly_encoded_protein_xref', 'compatible_gene_level_xref'}:
                raise ValueError('Selected native-supported source group does not replay from its archived model.')
            if native.get('native_gpml_file'):
                full_id = citation['source_model_id']
                raw = (history['directory']/native['native_gpml_file']).read_bytes()
                historical_models[full_id] = {'gpml_sha256': native['model']['gpml_sha256'],
                    'gpml_base64': base64.b64encode(raw).decode('ascii'),
                    'archive_proof': deepcopy(native['selected_archive_proof']),
                    'complete_native_archive_in_question_zip': False,
                    'complete_native_archive_in_workspace_zip': True}
    refs = {c["source_context_group_id"]: c["id"] for c in citations}
    summary = []
    for row in matches:
        uid = row["protein"]["id"]
        for path in row["paths"]:
            path["citation_ids"] = [refs[x] for x in path["source_context_group_ids"]]
            model = path["node_ids"][1]
            summary.append({"path_id": path["id"], "protein_id": uid, "review_status": path["review_status"],
                "text": f"In this retained source view, {label(anchor)} ({anchor}) and {label(uid)} ({uid}) "
                        f"have source annotations for the same cited WikiPathways model, {label(model)} "
                        f"({grouped[path['source_context_group_ids'][0]]['source_model_id']}). "
                        "This is shared source context; their original review states remain below.",
                "citation_ids": path["citation_ids"]})
    used = {anchor} | {n for row in matches for p in row["paths"] for n in p["node_ids"]}
    answer = {"question_format": "biograph-steward.guided-question.v1", "template": TEMPLATE,
        "source_run": source_run, "data_kind": graph["data_kind"], "snapshot_sha256": graph["snapshot_sha256"],
        "snapshot_created_at": graph["snapshot_created_at"], "database_version": graph.get("db_version"),
        "graph_basis_sha256": graph_basis(graph), "review_events_sha256": digest(graph.get("review_events", [])),
        "question": f"Which retrieved proteins share exact-revision WikiPathways source context with {label(anchor)}?",
        "plan": {"disease": None, "protein": deepcopy(nodes[anchor]), "relations": ["shared_pathways"],
            "view": view, "max_results": max_results, "max_paths_per_protein": max_paths,
            "seed_proteins": len(seed), "selected_coverage": {}, "source_projection_profile": PROFILE,
            "source_support": source_support,
            "filter_policy": "Retained source graph; verbatim exact-version URLs; candidates stay labelled. "
                "Repeated records are grouped for display and do not increase model-path counts."},
        "availability": {"accepted_proteins": accepted_proteins, "inspectable_proteins": inspectable,
            "accepted_paths": accepted_paths, "inspectable_paths": all_paths},
        "overview": f"Showing {len(matches)} of {matching} matching proteins in the qualified retained source view. "
            "Each path represents one exact cited model shared by two retrieved proteins, not a new protein interaction.",
        "matching_proteins": matching, "returned_proteins": len(matches), "omitted_proteins": matching - len(matches),
        "excluded_assertions": {k: len(v) for k, v in sorted(excluded.items())},
        "results": matches, "summary": summary, "citations": citations,
        "nodes": [nodes[x] for x in sorted(used)], "limitations": deepcopy(LIMITATIONS),
        "qualified_view": deepcopy(graph["qualified_view"]), "projection_counts": projection["counts"],
        "interpretation": "Qualified source-annotation context for inspection, not independently validated biological truth.",
        "engine": "deterministic_exact_revision_source_query", "llm_used": False}
    if history is not None:
        answer['historical_models'] = historical_models
        answer['historical_packet_content_sha256'] = history['report']['content_sha256']
        answer['overview'] += (' Archived native support is required; unresolved source annotations stay in the workspace.'
            if source_support == 'native_supported' else ' All retained source annotations are inspectable, including unresolved native support.')
        answer['limitations'][3] = ('Displayed native models are rebound to exact publisher archive members. '
            'The core replays literal XML and identifier matches against a byte-bound producer XSD receipt; it does not reexecute XSD. '
            'Whole-model citations and exact element-attached reference links stay separate; none is asserted to support every member.')
        answer['limitations'].append('A gene-level xref match supports encoded gene context through the pinned registry; it does not establish exact historical protein forms or an independent biological experiment.')
    answer["answer_sha256"] = digest(answer)
    return answer
