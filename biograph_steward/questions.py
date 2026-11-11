"""Deterministic, scoped evidence-path questions over a verified Pharos graph.

A path describes database annotations. Its summary cites every traversed
assertion; it never propagates disease evidence through a context relationship.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from html import escape
import json
import csv
import io
from pathlib import Path

from .client import digest, write_json

TEMPLATE = "disease_protein_neighborhood.v1"
COHORT_TEMPLATE = "cohort_protein_neighborhood.v1"
RELATIONS = ("interactions", "shared_pathways")
INSPECTABLE = {"candidate", "provisional", "accepted"}


def graph_basis(graph):
    basis = {"snapshot": graph["snapshot_sha256"], "graph_format": graph["graph_format"],
                   "normalization": graph.get("normalization", {}).get("policy"),
                   "nodes": graph["nodes"],
                   "assertions": [{k: a.get(k) for k in ("id", "revision", "lifecycle_state", "qualifiers")}
                                  for a in graph.get("assertions", [])],
                   "review_events": graph.get("review_events", [])}
    if graph.get("civic_snapshot_sha256"):
        basis["civic_snapshot"] = graph["civic_snapshot_sha256"]
    if graph.get("assay_attachment_sha256"):
        basis["assay_attachment"] = graph["assay_attachment_sha256"]
        basis["assay_publication"] = graph["assay_publication_sha256"]
    return digest(basis)


def resolve_protein(graph, selector):
    if not isinstance(selector, str) or not selector.strip() or len(selector) > 200:
        raise ValueError("Choose a protein from this saved cohort.")
    value = selector.strip()
    targets = graph["targets"]
    exact = [t for t in targets if t["id"] == value or t["id"] == "UniProtKB:" + value]
    matches = exact or [t for t in targets if (t.get("symbol") or "").casefold() == value.casefold()]
    if len(matches) > 1:
        raise ValueError("Ambiguous protein symbol; choose an exact identifier: " + ", ".join(t["id"] for t in matches))
    if not matches:
        raise ValueError("Protein is outside the selected cohort. Choose a returned protein identifier.")
    return matches[0]["id"]


def answer_question(graph, protein, *, relations=None, view="accepted", max_results=8,
                    max_paths=2, template=None, source_run=None,
                    ranking="alphabetical", ranking_source=None):
    cohort = graph.get("scope", {}).get("kind") == "protein_cohort"
    expected_template = COHORT_TEMPLATE if cohort else TEMPLATE
    template = expected_template if template is None else template
    if template != expected_template:
        raise ValueError("Unsupported question template for this graph scope. Use the matching guided protein-neighborhood question.")
    if view not in {"accepted", "candidates"}:
        raise ValueError("Evidence view must be accepted or candidates.")
    if type(max_results) is not int or not 1 <= max_results <= 30:
        raise ValueError("Use 1-30 result proteins.")
    if type(max_paths) is not int or not 1 <= max_paths <= 5:
        raise ValueError("Use 1-5 paths per result protein.")
    relations = list(RELATIONS) if relations is None else relations
    if not isinstance(relations, (list, tuple)) or not relations or any(r not in RELATIONS for r in relations):
        raise ValueError("Select interactions, shared_pathways, or both.")
    relations = [r for r in RELATIONS if r in relations]
    if ranking not in {"alphabetical", "physical"}:
        raise ValueError("Choose alphabetical order or physical association priority.")
    if ranking == "alphabetical" and ranking_source is not None:
        raise ValueError("A physical ranking source requires the physical priority option.")
    if ranking == "physical" and "interactions" not in relations:
        raise ValueError("Physical association priority requires reported interaction paths; shared pathways alone are not ranked physically.")
    anchor = resolve_protein(graph, protein)
    nodes = {n["id"]: n for n in graph["nodes"]}
    seed_ids = {t["id"] for t in graph["targets"]}
    did, disease = (None, None) if cohort else (graph["disease_node_id"], graph["disease"]["name"])
    edges = {e["id"]: e for e in graph["edges"]}
    usable, disease_links, memberships, interactions = {}, {}, defaultdict(dict), defaultdict(list)
    excluded = Counter()
    for a in graph.get("assertions", []):
        if a["kind"] not in {"disease_association", "pathway_membership", "protein_interaction"}:
            continue
        if a["lifecycle_state"] not in INSPECTABLE:
            excluded["rejected_quarantined_or_obsolete_assertions"] += 1
            continue
        evidence = [edges[eid] for eid in a["structurally_usable_evidence_ids"] if eid in edges
                    and edges[eid]["status"] == "passed_structural_checks"]
        if not evidence:
            excluded["assertions_without_structurally_usable_evidence"] += 1
            continue
        # This template does not generalize context-qualified records into
        # unqualified protein-level claims.
        if any(v is not None for k, v in a["qualifiers"].items() if k != "disease"):
            excluded["context_qualified_assertions_outside_template"] += 1
            continue
        if a["kind"] == "disease_association":
            if cohort:
                excluded["disease_associations_outside_cohort_template"] += 1
                continue
            if (a["subject"] not in seed_ids or a["object"] != did or a["qualifiers"].get("disease") != did):
                excluded["other_disease_associations"] += 1
                continue
            evidence = [e for e in evidence if e["record_kind"] == "disease_association"
                        and str(e["evidence_record"].get("name") or "").strip().casefold() == disease.strip().casefold()]
            if not evidence:
                excluded["association_without_exact_disease_context"] += 1
                continue
            disease_links[a["subject"]] = a
        elif a["kind"] == "pathway_membership":
            if (a["subject"] not in seed_ids or nodes.get(a["object"], {}).get("category") != "biolink:Pathway"
                    or a["qualifiers"].get("disease") is not None):
                continue
            memberships[a["subject"]][a["object"]] = a
        else:
            if (not a.get("symmetric") or a["subject"] not in seed_ids or a["object"] not in seed_ids
                    or a["qualifiers"].get("disease") is not None):
                continue
            if a["subject"] == anchor and a["object"] != anchor:
                interactions[a["object"]].append(a)
            elif a["object"] == anchor and a["subject"] != anchor:
                interactions[a["subject"]].append(a)
        usable[a["id"]] = (a, evidence)

    def label(uid):
        n = nodes[uid]
        return n.get("sym") or n["name"]

    def path(kind, node_ids, assertions):
        ids = [a["id"] for a in assertions]
        return {"id": "path:" + digest({"kind": kind, "nodes": node_ids, "assertions": ids})[:20],
                "kind": kind, "node_ids": node_ids, "assertion_ids": ids,
                "review_status": "accepted" if all(a["lifecycle_state"] == "accepted" for a in assertions) else "candidate_evidence",
                "assertion_states": {a["id"]: a["lifecycle_state"] for a in assertions}}

    matches = []
    accepted_proteins, inspectable_proteins = 0, 0
    total_paths, accepted_paths = 0, 0
    for uid in sorted(seed_ids - {anchor}, key=lambda x: (label(x).casefold(), x)):
        association = disease_links.get(uid)
        if not cohort and not association:
            continue
        chosen, path_count, accepted_count = [], 0, 0
        counts = Counter()

        def consider(kind, node_ids, assertions):
            nonlocal path_count, accepted_count
            accepted = all(a["lifecycle_state"] == "accepted" for a in assertions)
            path_count += 1
            accepted_count += accepted
            if view == "accepted" and not accepted:
                return
            counts[kind] += 1
            if len(chosen) < max_paths:
                chosen.append(path(kind, node_ids, assertions))

        if "interactions" in relations:
            for annotation in sorted(interactions.get(uid, []), key=lambda a: a["id"]):
                if cohort:
                    consider("interaction", [anchor, uid], [annotation])
                else:
                    consider("interaction", [did, uid, anchor], [association, annotation])
        if "shared_pathways" in relations:
            common = memberships.get(anchor, {}).keys() & memberships.get(uid, {}).keys()
            for wid in sorted(common, key=lambda x: (label(x).casefold(), x)):
                if cohort:
                    consider("shared_pathway", [anchor, wid, uid],
                             [memberships[anchor][wid], memberships[uid][wid]])
                else:
                    consider("shared_pathway", [did, uid, wid, anchor],
                             [association, memberships[uid][wid], memberships[anchor][wid]])
        inspectable_proteins += bool(path_count)
        accepted_proteins += bool(accepted_count)
        total_paths += path_count
        accepted_paths += accepted_count
        if not chosen:
            continue
        states = {p["review_status"] for p in chosen}
        matches.append({"protein": deepcopy(nodes[uid]), "paths": chosen,
                        "eligible_path_count": sum(counts.values()), "matched_relations": dict(counts),
                        "omitted_paths": sum(counts.values()) - len(chosen),
                        "review_status": next(iter(states)) if len(states) == 1 else "mixed_review_states"})
    ranking_packet = None
    ranking_info = None
    if ranking == "physical":
        if not any(row['matched_relations'].get('interaction', 0) for row in matches):
            raise ValueError("No eligible interaction paths are available for physical priority in this evidence view. Explore candidate paths or choose alphabetical order.")
        from .physical_ranking import collect_ranking, verify_packet
        ranking_packet = (collect_ranking(graph, anchor, matches) if ranking_source is None else ranking_source)
        verify_packet(ranking_packet, graph=graph, candidates=matches, anchor=anchor)
        by_id = {row['protein']['id']: row for row in matches}
        for uid, row in by_id.items():
            row['physical_priority'] = _physical_priority(ranking_packet, uid)
        matches = [by_id[row['protein_id']] for row in _physical_order(ranking_packet)]
        ranking_info = _physical_summary(ranking_packet)
    total_matches = len(matches)
    matches = matches[:max_results]
    required = list(dict.fromkeys(aid for r in matches for p in r["paths"] for aid in p["assertion_ids"]))
    citations, citation_index = [], {}
    for i, aid in enumerate(required, 1):
        a, evidence = usable[aid]
        cid = f"E{i:03d}"
        citation_index[aid] = cid
        citations.append({"id": cid, "assertion_id": aid, "revision": a["revision"],
                          "subject": a["subject"], "predicate": a["predicate"], "object": a["object"],
                          "kind": a["kind"], "qualifiers": deepcopy(a["qualifiers"]),
                          "review_state": a["lifecycle_state"], "source_names": deepcopy(a["source_names"]),
                          "normalization_notes": deepcopy(a.get("normalization_notes", [])),
                          "used_evidence_edge_ids": [e["id"] for e in evidence],
                          "source_record_count": sum(e.get("source_record_count", len(e["record_locators"])) for e in evidence),
                          "evidence_records": deepcopy(evidence),
                          "publications": sorted({pmid for e in evidence for pmid in e.get("publications", [])})})
    summary = []
    for r in matches:
        uid = r["protein"]["id"]
        for p in r["paths"]:
            p["citation_ids"] = [citation_index[aid] for aid in p["assertion_ids"]]
            prefix = "Accepted path" if p["review_status"] == "accepted" else "Candidate path (requires review)"
            if p["kind"] == "interaction":
                statement = (f"Pharos reports an interaction annotation connecting {label(anchor)} ({anchor}) with {label(uid)} ({uid})."
                             if cohort else f"Pharos reports an exact-term association between {label(uid)} ({uid}) and {disease}, and an interaction annotation connecting {label(uid)} with {label(anchor)}.")
            else:
                wid = p["node_ids"][1 if cohort else 2]
                statement = (f"Pharos annotates {label(anchor)} ({anchor}) and {label(uid)} ({uid}) to the shared pathway {label(wid)} ({wid})."
                             if cohort else f"Pharos reports an exact-term association between {label(uid)} ({uid}) and {disease}; {label(uid)} and {label(anchor)} have annotations for the shared pathway {label(wid)} ({wid}).")
            summary.append({"path_id": p["id"], "protein_id": uid, "review_status": p["review_status"],
                            "text": prefix + ": " + statement, "citation_ids": p["citation_ids"]})
    if not matches:
        overview = ("No fully accepted evidence paths were found in this saved cohort."
                    if view == "accepted" else "No inspectable evidence paths were found within this saved cohort and the selected relationships.")
    else:
        scope_name = graph["scope"]["name"] if cohort else disease + " cohort"
        overview = f"Showing {len(matches)} of {total_matches} matching proteins in the saved {scope_name}, using {'accepted paths only' if view == 'accepted' else 'accepted and candidate paths for inspection'}."
    if ranking_packet is not None:
        overview += " Matching interaction partners are ordered by available STRING 12.5 physical association scores; unranked matches follow."
    coverage = graph.get("retrieval", {}).get("context", {})
    settings = graph.get("question_scope", {}).get("limits", {})
    selected_coverage = {family: deepcopy(coverage.get("summary", {}).get(family))
                         for family in ("ppis", "pathways") if (family == "ppis" and "interactions" in relations)
                         or (family == "pathways" and "shared_pathways" in relations)}
    gaps = ["Results cover the retrieved seed proteins and the exact selected disease term; related disease terms remain separate.",
            "Pathway and interaction annotations provide general context. Paths do not establish disease mechanisms, physical binding or causality.",
            "Variant-specific therapy response and resistance are outside this question template.",
            "Evidence references point to stored database assertions. Source records without explicit supporting references still require citation recovery.",
            "Records failing structural checks, unmapped pathway identities, and rejected, quarantined or obsolete assertions are excluded.",
            "Protein ordering is alphabetical; path order puts interactions before pathways, then sorts pathway labels. It is not a confidence ranking."]
    if ranking_packet is not None:
        gaps[5] = ("Protein order prioritizes native STRING 12.5 physical association scores, with alphabetical ties and unranked matches last. "
                   "Only matches with an eligible Pharos interaction path receive this priority; pathway-only matches remain unranked.")
        gaps += ["STRING physical scores predict proximity or co-complex association, not proof of direct binding, interaction strength, disease relevance or independent experimental confirmation.",
                 "The current STRING ranking supplement is separate from the saved Pharos release and may reuse evidence already aggregated there. Scores do not change graph relationships or local review states.",
                 "Coverage describes only eligible matching interaction partners in this question; a missing score is not evidence of no interaction."]
    if cohort:
        gaps[0] = "Results cover the exactly resolved proteins in the declared cohort; cohort membership does not imply a disease association."
        gaps.append("A missing path is not evidence of no biological relationship. Retrieval limits, unresolved identities and unreviewed evidence remain explicit.")
        unresolved = [row for row in graph["scope"]["resolutions"] if row["status"] != "resolved"]
        if unresolved:
            gaps.append(f"{len(unresolved)} requested protein identifiers were not resolved exactly and could not form evidence paths; consult the cohort resolution records.")
    if graph["retrieval"].get("truncated"):
        gaps.append("The cohort retrieval is capped; records beyond the declared limits were not searched." if cohort else
                    "The disease cohort is capped; proteins outside the extract were not searched.")
    if any(value is None for value in selected_coverage.values()):
        gaps.append("Per-family retrieval coverage is unavailable for some selected relationships. A preview pathway cap is not evidence of complete coverage.")
    for family, c in selected_coverage.items():
        family_label = "Protein interaction" if family == "ppis" else "Pathway"
        if c and "exhausted" in c["target_statuses"]:
            gaps.append(f"{family_label} pages were exhausted without a reported count for some proteins; completeness is not count-verified.")
        if c and any(status not in {"complete", "exhausted"} for status in c["target_statuses"]):
            gaps.append(f"{family_label} retrieval has limits or unresolved coverage statuses; consult the scope report.")
    if graph["data_kind"] == "synthetic_demo":
        gaps.insert(0, "SYNTHETIC SOFTWARE DEMONSTRATION. All results are invented test data, not scientific evidence.")
    used_nodes = ({anchor} if cohort else {did, anchor}) | {n for r in matches for p in r["paths"] for n in p["node_ids"]}
    connection = "reported interaction annotations or shared pathway annotations" if len(relations) == 2 else (
        "reported interaction annotations" if relations[0] == "interactions" else "shared pathway annotations")
    answer = {"question_format": "biograph-steward.guided-question.v1", "template": template,
              "source_run": source_run, "data_kind": graph["data_kind"], "snapshot_sha256": graph["snapshot_sha256"],
              "snapshot_created_at": graph["snapshot_created_at"], "database_version": graph.get("db_version"),
              "graph_basis_sha256": graph_basis(graph), "review_events_sha256": digest(graph.get("review_events", [])),
              "question": f"Which other proteins associated with {disease} have {connection} with {label(anchor)}?",
              "plan": {"disease": {"id": did, "name": disease}, "protein": deepcopy(nodes[anchor]),
                       "relations": relations, "view": view, "max_results": max_results, "max_paths_per_protein": max_paths,
                       "seed_proteins": len(seed_ids), "retrieval": deepcopy(graph["retrieval"]),
                       "retrieval_settings": deepcopy(settings), "selected_coverage": selected_coverage,
                       "filter_policy": "Exact-term protein-disease evidence plus structurally usable context. Every assertion in an accepted path must be accepted.",
                       "unsupported_requirements": ["variant-specific response", "therapy resistance", "causal conclusions"]},
              "availability": {"accepted_proteins": accepted_proteins, "inspectable_proteins": inspectable_proteins,
                               "accepted_paths": accepted_paths, "inspectable_paths": total_paths},
              "overview": overview, "matching_proteins": total_matches, "returned_proteins": len(matches),
              "omitted_proteins": total_matches - len(matches), "excluded_assertions": dict(sorted(excluded.items())),
              "results": matches, "summary": summary, "citations": citations,
              "nodes": [deepcopy(nodes[uid]) for uid in sorted(used_nodes)], "limitations": gaps,
              "interpretation": "Database-reported evidence paths for inspection. Human acceptance records review; it does not establish experimental labels or clinical truth.",
              "engine": "deterministic_graph_query", "llm_used": False}
    if cohort:
        answer["question"] = f"Which other proteins in {graph['scope']['name']} have {connection} with {label(anchor)}?"
        answer["plan"]["disease"] = None
        answer["plan"]["scope"] = deepcopy(graph["scope"])
        answer["plan"]["filter_policy"] = ("Exactly resolved cohort proteins and structurally usable interaction or shared-pathway annotations. "
            "Every assertion in an accepted path must be accepted; no disease association is required or inferred.")
        answer["plan"]["unsupported_requirements"] = ["disease association inference", "physical binding inference", "variant-specific response", "therapy resistance", "causal conclusions"]
    if ranking_packet is not None:
        answer['plan']['ranking'] = 'physical'
        answer['ranking'] = ranking_info
        answer['physical_ranking_source'] = deepcopy(ranking_packet)
    answer["answer_sha256"] = digest(answer)
    return answer


def _physical_priority(packet, uid):
    annotation = packet['annotations'][uid]
    candidate = next(row for row in packet['requested_candidates'] if row['protein_id'] == uid)
    return {'state': annotation['views']['physical']['state'],
            'physical_score': annotation['views']['physical']['native_score'],
            'functional_score': annotation['views']['functional']['native_score'],
            'source_release': packet['source_release'], 'has_interaction': candidate['has_interaction']}


def _physical_order(packet):
    def key(row):
        priority = _physical_priority(packet, row['protein_id'])
        numeric = priority['state'] == 'numeric'
        return (not numeric, -priority['physical_score'] if numeric else 0,
                row['label'].casefold(), row['protein_id'])
    return sorted(packet['requested_candidates'], key=key)


def _physical_summary(packet):
    counts = Counter(row['views']['physical']['state'] for row in packet['annotations'].values())
    total = len(packet['requested_candidates'])
    return {'source_release': packet['source_release'], 'retrieved_at': packet['created_at'],
            'matching_proteins': total, 'numeric_scored': counts['numeric'],
            'unranked_proteins': total - counts['numeric'], 'states': dict(sorted(counts.items())),
            'packet_sha256': packet['content_sha256'],
            'ordering': 'Native physical score descending; alphabetical ties; unranked matches last.'}


def _physical_text(priority):
    if priority['state'] == 'numeric':
        return f"STRING {priority['source_release']} physical association score: {priority['physical_score']:.3f}"
    labels = {'not_interaction_path': 'Pathway-only match; not ranked physically',
              'no_returned_functional_row': 'No STRING row returned under this query profile',
              'physical_not_returned_under_profile': 'Physical score unavailable under this query profile',
              'unmapped': 'Endpoint mapping unavailable', 'ambiguous': 'Endpoint mapping unresolved',
              'collapsed_representative': 'Both endpoints map to one representative'}
    return labels.get(priority['state'], priority['state'])


def _verify_physical_answer(answer):
    from .physical_ranking import verify_packet
    packet = answer.get('physical_ranking_source')
    verify_packet(packet)
    if (answer.get('plan', {}).get('ranking') != 'physical'
            or answer.get('graph_basis_sha256') != packet['graph_basis_sha256']
            or answer.get('snapshot_sha256') != packet['snapshot_sha256']
            or answer['plan']['protein']['id'] != packet['anchor']
            or answer.get('ranking') != _physical_summary(packet)):
        raise ValueError('Physical priority source, scope or coverage differs from the saved answer.')
    ordered = _physical_order(packet)
    limit = answer['plan']['max_results']
    if (type(limit) is not int or not 1 <= limit <= 30
            or [row['protein']['id'] for row in answer['results']] != [row['protein_id'] for row in ordered[:limit]]
            or answer['matching_proteins'] != len(ordered)
            or answer['returned_proteins'] != len(answer['results'])
            or answer['omitted_proteins'] != len(ordered) - len(answer['results'])):
        raise ValueError('Physical priority order or result denominator changed.')
    for row in answer['results']:
        priority = _physical_priority(packet, row['protein']['id'])
        if (row.get('physical_priority') != priority
                or priority['has_interaction'] != bool(row['matched_relations'].get('interaction', 0))):
            raise ValueError('Returned physical priority differs from its captured source.')


def verify_answer(answer):
    if answer.get("question_format") != "biograph-steward.guided-question.v1":
        raise ValueError("Unsupported guided question format.")
    if answer.get("answer_sha256") != digest({k: v for k, v in answer.items() if k != "answer_sha256"}):
        raise ValueError("Question result integrity check failed.")
    if answer.get('plan', {}).get('ranking') == 'physical' or 'physical_ranking_source' in answer:
        _verify_physical_answer(answer)


def answer_text(answer):
    if answer.get('template') == 'qualified_assay_evidence.v1':
        from .assay_questions import answer_text as qualified_text
        return qualified_text(answer)
    lines = [answer['question'], '', answer['overview'], '']
    if answer.get('ranking') is not None:
        info = answer['ranking']
        lines += [f"Physical priority source: STRING {info['source_release']} | retrieved {info['retrieved_at']}",
                  f"Numeric scores for {info['numeric_scored']} of {info['matching_proteins']} matching proteins; {info['unranked_proteins']} remain unranked.",
                  'Result order:', *[f"- {r['protein'].get('sym') or r['protein']['name']} ({r['protein']['id']}): {_physical_text(r['physical_priority'])}" for r in answer['results']], '']
    from .civic_context import display_coverage_text
    coverage = display_coverage_text(answer)
    if coverage: lines += [coverage, '']
    if answer['data_kind'] == 'synthetic_demo':
        lines.insert(0, 'SYNTHETIC DEMONSTRATION — not scientific evidence.\n')
    for item in answer['summary']:
        lines.append(item['text'] + ' ' + ' '.join('[' + cid + ']' for cid in item['citation_ids']))
        if item.get('context_text'):lines.append(item['context_text'])
    from .civic_context import context_text, overview_text
    if answer.get('source_context_overview') is not None:lines += ['',overview_text(answer['source_context_overview'])]
    contexts=[context_text(c) for c in answer['citations'] if c.get('study_context')]
    if contexts:lines += ['', 'Source context by record:', *contexts]
    lines += ['', 'Scope and limitations:', *['- ' + s for s in answer['limitations']], '', 'Evidence references:']
    for c in answer['citations']:
        lines.append(f"[{c['id']}] {c['assertion_id']} | {c['review_state']} | sources: {', '.join(c['source_names']) or 'not supplied'} | evidence: {', '.join(c['used_evidence_edge_ids'])}")
    lines += ['', 'Source snapshot time: ' + answer['snapshot_created_at'],
              'Database version: ' + str(answer.get('database_version') or 'not supplied'),
              'Snapshot: ' + answer['snapshot_sha256'], 'Graph/review basis: ' + answer['graph_basis_sha256']]
    if answer.get('civic_snapshot_sha256'):
        lines += ['CIViC snapshot: ' + answer['civic_snapshot_sha256'], 'CIViC retrieval: ' + answer['civic_created_at'],
                  'Discordant annotations: ' + json.dumps(answer['discordant_annotations'],ensure_ascii=True)]
    return '\n'.join(lines) + '\n'


def answer_html(answer):
    if answer.get('template') == 'qualified_assay_evidence.v1':
        from .assay_questions import answer_html as qualified_html
        return qualified_html(answer)
    esc = lambda value: escape(str(value), quote=True)
    statements = []
    from .civic_context import context_html, overview_html, display_coverage_html
    coverage = display_coverage_html(answer)
    overview=overview_html(answer['source_context_overview']) if answer.get('source_context_overview') is not None else ''
    priority_html = ''
    if answer.get('ranking') is not None:
        info = answer['ranking']
        priority_html = ('<h2>Physical association priority</h2><p>STRING ' + esc(info['source_release'])
            + ' · retrieved ' + esc(info['retrieved_at']) + '. Numeric scores for '
            + esc(info['numeric_scored']) + ' of ' + esc(info['matching_proteins'])
            + ' matching proteins. Predicted proximity/co-complex association; direct binding is not established.</p><ol>'
            + ''.join('<li>' + esc(r['protein'].get('sym') or r['protein']['name']) + ' ('
                      + esc(r['protein']['id']) + '): ' + esc(_physical_text(r['physical_priority'])) + '</li>'
                      for r in answer['results']) + '</ol>')
    by_id={c['id']:c for c in answer['citations']}
    for s in answer['summary']:
        refs = ' '.join(f'<a href="#{esc(cid)}">[{esc(cid)}]</a>' for cid in s['citation_ids'])
        contexts=''.join(context_html(by_id[cid]) for cid in s['citation_ids'])
        statements.append(f'<li>{esc(s["text"])} {refs}{contexts}</li>')
    citations = ''.join(f'<details id="{esc(c["id"])}"><summary>[{esc(c["id"])}] {esc(c["assertion_id"])} — {esc(c["review_state"])}</summary><pre>{esc(json.dumps(c,indent=2))}</pre></details>' for c in answer['citations'])
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>BioGraph Steward — guided evidence result</title><style>body{max-width:1050px;margin:40px auto;padding:20px;font:16px/1.6 system-ui;color:#172b3a}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f7;padding:16px}li,details{margin:14px 0}a{color:#086b85}.display-coverage{background:#fff8e7;border:1px solid #c9a75e;padding:16px;margin:20px 0}</style>'
            '<h1>' + esc(answer['question']) + '</h1><p>' + esc(answer['data_kind']) + '</p><p>' + esc(answer['overview']) + '</p>'+coverage+overview+priority_html+'<ul>' + ''.join(statements) + '</ul><h2>Scope and limitations</h2><ul>'
            + ''.join('<li>'+esc(s)+'</li>' for s in answer['limitations']) + '</ul><h2>Evidence passports</h2>' + citations
            + '<h2>Reproducible question scope</h2><pre>' + esc(json.dumps({k: answer[k] for k in ['plan','snapshot_created_at','database_version','snapshot_sha256','graph_basis_sha256','answer_sha256','civic_snapshot_sha256','civic_created_at','discordant_annotations','overlap_summary'] if k in answer},indent=2)) + '</pre></html>')


def evidence_context_rows(answer):
    """Flatten saved source records with the qualifications needed outside the app.

    This is an export projection, not a new answer or an extraction from prose.
    In particular, source editorial status and local review remain separate,
    and the complete profile and therapy set stay on each source-item row.
    """
    rows = []
    for citation in answer['citations']:
        edges = {e['id']: e for e in citation['evidence_records']}
        for context in citation.get('study_context', {}).get('records', []):
            edge = edges.get(context.get('edge_id'), {})
            record = edge.get('evidence_record', {})
            profile = record.get('molecularProfile') or {}
            disease = record.get('disease') or {}
            source = record.get('source') or {}
            therapies = record.get('therapies', context.get('therapy_members', []))
            rows.append({
                **deepcopy(context),
                'citation_id': citation['id'], 'assertion_id': citation['assertion_id'],
                'assertion_revision': citation.get('revision'),
                'local_review_state': citation['review_state'], 'source_status': record.get('status'),
                'profile_id': citation['subject'], 'profile_name': profile.get('name'),
                'profile_expression': profile.get('rawName'), 'profile_variants': deepcopy(profile.get('variants', [])),
                'disease_id': citation.get('qualifiers', {}).get('disease'), 'disease_name': disease.get('name'),
                'source_disease_id': 'CIViC.disease:' + str(disease['id']) if disease.get('id') is not None else None,
                'therapy_set_id': citation['object'], 'therapy_members': deepcopy(therapies),
                'therapy_ids': ['CIViC.therapy:' + str(t['id']) for t in therapies],
                'evidence_type': record.get('evidenceType'),
                'source_id': 'CIViC.source:' + str(source['id']) if source.get('id') is not None else None,
                'source_type': source.get('sourceType'),
                'retrieval_provenance': deepcopy(edge.get('retrieval_provenance', [])),
                'source_run': answer.get('source_run'), 'answer_sha256': answer['answer_sha256'],
                'graph_basis_sha256': answer['graph_basis_sha256'],
            })
    return rows


def save_answer(answer, directory):
    verify_answer(answer)
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Question output directory is not empty; choose a new directory.")
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory/'question.json', answer)
    (directory/'summary.txt').write_text(answer_text(answer),encoding='utf-8')
    (directory/'report.html').write_text(answer_html(answer),encoding='utf-8')
    if answer.get('physical_ranking_source') is not None:
        write_json(directory/'physical_ranking_source.json', answer['physical_ranking_source'])
        (directory/'physical_priority.tsv').write_text(_physical_tsv(answer['physical_ranking_source']), encoding='utf-8')
    if answer.get('template') == 'qualified_assay_evidence.v1':
        from .assay_questions import save_extra_files
        save_extra_files(answer, directory)
        return
    from .graph import _write_tsv
    if answer['template'] == 'civic_variant_therapy.v1':
        rows=[{"profile_id":r['profile']['id'],"profile_name":r['profile']['name'],**p} for r in answer['results'] for p in r['paths']]
        columns=['profile_id','profile_name','id','kind','review_status','node_ids','assertion_ids','citation_ids']
    else:
        rows = [{"protein_id": r['protein']['id'], "protein_symbol": r['protein'].get('sym'), **p} for r in answer['results'] for p in r['paths']]
        columns=['protein_id','protein_symbol','id','kind','review_status','node_ids','assertion_ids','citation_ids']
    _write_tsv(directory/'paths.tsv',rows,columns)
    if answer.get('source_context_overview') is not None:
        _write_tsv(directory/'evidence_context.tsv',evidence_context_rows(answer),['citation_id','assertion_id','evidence_id','evidence_level',
                   'evidence_level_label','evidence_direction','significance','variant_origin','therapy_label','therapy_interaction',
                   'therapy_scope_note','source_reference','source_title','description','record_locators','snapshot_sha256','paper_check',
                   'assertion_revision','local_review_state','source_status','profile_id','profile_name','profile_expression',
                   'profile_variants','disease_id','disease_name','source_disease_id','therapy_set_id','therapy_ids','therapy_members',
                   'evidence_type','edge_id','evidence_url','source_id','source_type','source_citation','publication_year',
                   'publication_url','retrieval_provenance','source_run','answer_sha256','graph_basis_sha256'])


def _physical_tsv(packet):
    output = io.StringIO(newline='')
    writer = csv.writer(output, delimiter='\t', lineterminator='\n')
    writer.writerow(['protein_id', 'label', 'state', 'physical_score', 'functional_score', 'source_release', 'has_interaction'])
    for row in _physical_order(packet):
        priority = _physical_priority(packet, row['protein_id'])
        writer.writerow([row['protein_id'], row['label'], priority['state'],
                         '' if priority['physical_score'] is None else priority['physical_score'],
                         '' if priority['functional_score'] is None else priority['functional_score'],
                         priority['source_release'], priority['has_interaction']])
    return output.getvalue()


def _physical_paths_bytes(answer):
    """Replay path serialization with the existing spreadsheet-safe writer."""
    from tempfile import TemporaryDirectory
    from .graph import _write_tsv
    rows = [{"protein_id": row['protein']['id'],
             "protein_symbol": row['protein'].get('sym'), **path}
            for row in answer['results'] for path in row['paths']]
    columns = ['protein_id', 'protein_symbol', 'id', 'kind', 'review_status',
               'node_ids', 'assertion_ids', 'citation_ids']
    with TemporaryDirectory(prefix='biograph-question-export-') as folder:
        path = Path(folder) / 'paths.tsv'
        _write_tsv(path, rows, columns)
        return path.read_bytes()


def verify_ranking_files(answer, directory):
    """Replay source and readable exports for the opted-in physical answer."""
    if answer.get('physical_ranking_source') is None:
        return
    from .assay_attachment import _ordinary, _decode
    directory = Path(directory)
    packet = answer['physical_ranking_source']
    if (_decode(_ordinary(directory/'physical_ranking_source.json')) != packet
            or _ordinary(directory/'physical_priority.tsv').decode('utf-8') != _physical_tsv(packet)):
        raise ValueError('Physical ranking export files differ from the saved source packet.')
    expected = {'summary.txt': answer_text(answer).encode('utf-8'),
                'report.html': answer_html(answer).encode('utf-8'),
                'paths.tsv': _physical_paths_bytes(answer)}
    for name, raw in expected.items():
        if _ordinary(directory/name) != raw:
            raise ValueError('Physical ranking readable export differs from the saved answer: ' + name)
