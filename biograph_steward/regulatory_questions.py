"""Read-only answers from verified, directed SIGNOR source observations.

The saved source claim, its local review and its publication metadata remain
separate. This module fetches nothing and infers no disease or binding context.
"""
from collections import Counter
from copy import deepcopy
import json
import re

from .assertions import assertion_identity
from .client import digest
from .inspection import _external_url
from .questions import graph_basis
from .regulatory_case_notes import case_notes, context_display, organism_display, display_metadata_basis
from .signor_source import _experimental_organism

FORMAT = "biograph-steward.regulatory-question.v1"
TEMPLATE = "source_regulatory_evidence.v1"
ANCHOR = "UniProtKB:P00533"
KIND = "source_regulatory_observation"
INTERPRETATION = ("Curated, source-reported regulation with its recorded direction, effect, mechanism and context. "
    "This does not establish colorectal-cancer applicability, direct binding or independent biological validation. "
    "Source records and publications are not independent experiment counts.")


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _index(rows, label):
    _need(isinstance(rows, list) and all(isinstance(r, dict) and isinstance(r.get("id"), str)
          and r["id"] for r in rows), "Saved " + label + " identities are missing.")
    result = {row["id"]: row for row in rows}
    _need(len(result) == len(rows), "Saved " + label + " identities repeat.")
    return result


def _saved_pair_context(graph, products):
    """Distinguish graph coverage from already retrieved subthreshold evidence."""
    if products[0] == products[1]:
        return {'scope': 'self_regulation_not_a_nonself_PPI_comparison',
            'original_pharos_records': [], 'saved_string_capture': None,
            'independent_evidence_count': None}
    pair = set(products)
    native = [{'edge_id': e['id'], 'providers': deepcopy(e.get('evidence_sources', [])),
               'source_scores_raw': deepcopy(e.get('source_scores_raw', {}))}
        for e in graph['edges'] if e.get('record_kind') == 'protein_interaction'
        and not e.get('extension_source_kind') and {e['subject'], e['object']} == pair]
    captured = [r for r in graph.get('extension_observations', [])
        if (r.get('source_kind') == 'string'
            or str(r.get('id') or r.get('observation_id', '')).startswith('string-source:'))
        and set(r.get('products', [])) == pair]
    _need(len(captured) <= 1, 'Saved STRING pair coverage is ambiguous.')
    source = graph.get('evidence_extension', {}).get('sources', {}).get('string', {})
    saved = None
    if captured:
        row = captured[0]
        saved = {key: deepcopy(row.get(key)) for key in ('id', 'state', 'functional_score',
            'physical_score', 'mapping_states', 'network_row_numbers', 'source_row')}
        saved.update(id=row.get('id') or row.get('observation_id'), source_release=source.get('source_release'),
            workspace_selection_threshold=source.get('selection_threshold'))
    return {'scope': 'Saved original Pharos profile and whole-cohort STRING capture only',
        'original_pharos_records': native, 'saved_string_capture': saved,
        'independent_evidence_count': None,
        'interpretation': 'A source row below the workspace display cutoff still reports an association. Additional direction, mechanism and context do not establish a novel relationship or independent experiment; primary-study reuse remains unresolved.'}


def _record(original, graph, nodes, edges, assertions, primary, protein, publication):
    oid, products = original["id"], original["products"]
    _need(set(products) <= primary and all(p in nodes and nodes[p].get("category") == "biolink:Protein"
          for p in products), "Saved regulatory participants must be exact primary graph proteins.")
    raw = original.get("source_row")
    _need(isinstance(raw, dict) and products == ["UniProtKB:" + str(raw.get(k, "")) for k in ("IDA", "IDB")]
          and original.get("source_record_id") == raw.get("SIGNOR_ID"),
          "Saved regulatory participants or record identity differ from the source row.")
    fields = {"effect_literal": "EFFECT", "mechanism_literal": "MECHANISM", "direct_literal": "DIRECT",
              "cell_context_raw": "CELL_DATA", "tissue_context_raw": "TISSUE_DATA",
              "residue_raw": "RESIDUE", "sequence_raw": "SEQUENCE", "supporting_sentence_raw": "SENTENCE"}
    _need(all(isinstance(raw.get(source), str) and original.get(field) == raw[source]
              for field, source in fields.items()), "Saved regulatory fields differ from their literal source row.")
    _need(isinstance(raw.get('TAX_ID'), str)
          and all(original.get(key) == value for key, value in _experimental_organism(raw['TAX_ID']).items())
          and original.get('participant_taxon') == 'NCBITaxon:9606'
          and original.get('assay_host_taxon') is None,
          "Saved experimental-organism fields must remain separate from the primary human protein identities.")
    _need(raw["DIRECT"] in {"t", "f"} and type(original.get("source_reported_direct")) is bool
          and original["source_reported_direct"] == (raw["DIRECT"] == "t")
          and type(original.get("self_regulation")) is bool
          and original["self_regulation"] == (products[0] == products[1]),
          "Saved regulatory directness or self-regulation differs from the source.")
    for name in ("cell", "tissue"):
        _need(original.get(name + "_context_reporting") ==
              ("reported" if original[name + "_context_raw"] else "unreported"),
              "Saved regulatory context reporting differs from the source.")
    eid = original.get("graph_edge_id")
    _need(isinstance(eid, str) and eid, "Saved regulatory observation is missing its evidence edge identity.")
    edge = edges.get(eid)
    _need(edge is not None and edge.get("record_kind") == KIND and edge.get("extension_source_kind") == "signor"
          and edge.get("symmetric") is False and [edge.get("subject"), edge.get("object")] == products
          and isinstance(edge.get("predicate"), str) and edge["predicate"].strip()
          and isinstance(edge.get("qualifiers"), dict) and edge["qualifiers"].get("observation_id") == oid
          and isinstance(edge.get("assertion_id"), str)
          and edge.get("snapshot_sha256") == graph["snapshot_sha256"]
          and edge.get("extension_publication_sha256") == publication
          and edge.get("source_publication_sha256") == publication
          and original.get("source_publication_sha256") == publication
          and isinstance(original.get("source"), dict) and original["source"].get("publication_sha256") == publication
          and edge.get("evidence_record") == original and edge.get("observation") == original,
          "Saved regulatory observation does not match its ordered, source-bound evidence edge.")
    assertion = assertions.get(edge.get("assertion_id"))
    identity = assertion_identity(edge["subject"], edge["predicate"], edge["object"], KIND, edge["qualifiers"])
    aid = "assertion:" + digest(identity)[:24]
    _need(assertion is not None and assertion.get("id") == aid
          and all(assertion.get(k) == value for k, value in identity.items())
          and assertion.get("extension_source_kind") == "signor"
          and assertion.get("evidence_extension_sha256") == graph["evidence_extension_sha256"]
          and isinstance(assertion.get("evidence_edge_ids"), list) and eid in assertion["evidence_edge_ids"]
          and assertion.get("revision") == digest({"identity": aid, "evidence": assertion["evidence_edge_ids"]})
          and isinstance(assertion.get("lifecycle_state"), str)
          and assertion["lifecycle_state"] in {"candidate", "provisional", "accepted", "quarantined", "rejected", "obsolete"},
          "Saved regulatory assertion identity, source binding or local review state is incomplete.")
    citations = original.get("citations")
    _need(isinstance(citations, list) and all(isinstance(c, dict) and _external_url(c.get("url"))
          for c in citations), "Saved regulatory source citations require safe HTTP(S) links.")
    pmid = raw.get("PMID")
    _need(isinstance(pmid, str) and pmid.isascii() and pmid.isdigit() and int(pmid) > 0
          and original.get("publications") == ["PMID:" + pmid]
          and any(c.get("id") == "PMID:" + pmid and
                  c["url"] == "https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/" for c in citations),
          "Saved regulatory record must preserve its source-reported PMID citation.")
    subject, obj = products
    labels = {p: nodes[p].get("sym") or nodes[p].get("name") or p for p in products}
    partner = obj if subject == protein else subject
    result = deepcopy(original)
    result.update(observation_id=oid, subject=subject, subject_label=labels[subject], object=obj,
        object_label=labels[obj], partner=partner, partner_label=labels[partner],
        relative_direction="self" if subject == obj else "outgoing" if subject == protein else "incoming",
        assertion_id=assertion["id"], assertion_revision=assertion["revision"],
        local_review_state=assertion["lifecycle_state"], source_observation=deepcopy(original),
        citations=deepcopy(citations), interpretation=INTERPRETATION)
    result['project_literature_check'] = case_notes(original)
    result['cell_context_display'] = context_display(original['cell_context_raw'])
    result['tissue_context_display'] = context_display(original['tissue_context_raw'])
    result['source_experimental_organism_display'] = organism_display(original)
    result['saved_pair_context'] = _saved_pair_context(graph, products)
    return result


def answer_regulatory_question(graph, protein=ANCHOR, *, direction="outgoing", search="", offset=0, limit=25,
                               source_run=None):
    """Page directed saved source claims, retaining every local review state."""
    _need(isinstance(graph, dict) and isinstance(graph.get("graph_format"), str) and graph["graph_format"],
          "Choose a verified saved graph.")
    _need(isinstance(direction, str) and direction in {"outgoing", "incoming", "both"},
          "Choose outgoing, incoming or both directions.")
    _need(isinstance(search, str) and len(search) <= 200, "Use a search string of at most 200 characters.")
    _need(type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 25,
          "Use a nonnegative offset and a page limit from 1 to 25.")
    _need(source_run is None or isinstance(source_run, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source_run),
          "Invalid saved workspace identifier.")
    nodes = _index(graph.get("nodes"), "node")
    targets = _index(graph.get("targets"), "primary target")
    primary = set(targets)
    _need(isinstance(protein, str) and protein.startswith("UniProtKB:") and protein in primary
          and protein in nodes and nodes[protein].get("category") == "biolink:Protein",
          "Choose an exact UniProtKB identifier from the primary graph targets; symbols are not resolved here.")
    extension = graph.get("evidence_extension")
    sources = extension.get("sources") if isinstance(extension, dict) else None
    summary = sources.get("signor") if isinstance(sources, dict) else None
    _need(isinstance(summary, dict) and graph.get("evidence_extension_sha256") and graph.get("snapshot_sha256")
          and isinstance(summary.get("publication_sha256"), str) and summary["publication_sha256"],
          "This workspace has no verified SIGNOR source extension.")
    edges = _index(graph.get("edges"), "edge")
    assertions = _index(graph.get("assertions"), "assertion")
    observations = graph.get("extension_observations")
    _need(isinstance(observations, list) and all(isinstance(r, dict) for r in observations),
          "Saved source observation ledger is missing.")
    source = [r for r in observations if r.get("source_kind") == "signor"]
    seen = set()
    for row in source:
        oid, products = row.get("id"), row.get("products")
        _need(isinstance(oid, str) and oid and oid not in seen and isinstance(products, list)
              and len(products) == 2 and all(isinstance(p, str) and p for p in products),
              "Saved regulatory observation has an ambiguous identity or ordered participant scope.")
        seen.add(oid)
    anchored = [r for r in source if protein in r["products"]]
    selected = [r for r in anchored if direction == "both" or
                r["products"][0 if direction == "outgoing" else 1] == protein]
    records = [_record(r, graph, nodes, edges, assertions, primary, protein, summary["publication_sha256"])
               for r in selected]
    records.sort(key=lambda r: (str(r["partner_label"]).casefold(), r["partner"],
                                r["relative_direction"], r["observation_id"]))
    query = search.strip().casefold()
    # Search source values and participant labels, never the application's
    # generic limitations (which mention CRC even when no source context does).
    matching = [r for r in records if not query or query in json.dumps(
        [*r["source_observation"]["source_row"].values(), *r["products"],
         r["subject_label"], r["object_label"],
         [v['label'] for v in r['cell_context_display'] + r['tissue_context_display']]], ensure_ascii=False).casefold()]
    page = matching[offset:offset + limit]
    counts = Counter(r["local_review_state"] for r in records)
    answer = {"format": FORMAT, "template": TEMPLATE, "source_kind": "signor", "source_run": source_run,
        "question": "What source-reported regulation is recorded " +
            {"outgoing": "from", "incoming": "to", "both": "involving"}[direction] + " " + protein + "?",
        "anchor": protein, "direction": direction, "read_only": True, "model_calls": 0, "source_fetches": 0,
        "graph_basis_sha256": graph_basis(graph), "snapshot_sha256": graph["snapshot_sha256"],
        "evidence_extension_sha256": graph["evidence_extension_sha256"],
        "review_events_sha256": digest(graph.get("review_events", [])),
        "source_publication_sha256": summary["publication_sha256"],
        "source_observations_sha256": digest(source), "source_summary": deepcopy(summary),
        "context_display_basis": display_metadata_basis(),
        "summary": {"source_observations": len(source), "anchored_observations": len(anchored),
            "direction_observations": len(records), "matching_observations": len(matching),
            "returned": len(page), "offset": offset, "limit": limit,
            "next_offset": offset + limit if offset + limit < len(matching) else None,
            "search": search, "direction": direction,
            "counts_scope": "Direction-selected source observations before search and pagination.",
            "cell_context_reported_observations": sum(bool(r["cell_context_raw"]) for r in records),
            "cell_context_unreported_observations": sum(not r["cell_context_raw"] for r in records),
            "tissue_context_reported_observations": sum(bool(r["tissue_context_raw"]) for r in records),
            "tissue_context_unreported_observations": sum(not r["tissue_context_raw"] for r in records),
            "self_regulatory_observations": sum(r["self_regulation"] for r in records),
            "distinct_source_publications": len({p for r in records for p in r['publications']}),
            "source_experimental_organism_counts": dict(sorted(Counter(r['source_experimental_organism_raw'] for r in records).items())),
            "local_review_states": dict(sorted(counts.items())), "primary_Pharos_target_scope_changed": False},
        "records": page, "interpretation": INTERPRETATION,
        "limitations": ["Blank cell and tissue fields remain unreported; no colorectal applicability is inferred.",
            "Human protein identifiers do not establish a human experiment. Source experimental-organism codes and human-orthologue remapping remain separate.",
            "All local review states are shown separately from source curation; local acceptance is not biological validation.",
            "Publication types and linked notices remain saved metadata; no primary-experimental classification is inferred.",
            "An absent record in this bounded workspace does not establish absence of regulation elsewhere.",
            "Alphabetical display and literal search do not rank confidence or infer approximate biological context."]}
    answer["content_sha256"] = digest(answer)
    return answer
