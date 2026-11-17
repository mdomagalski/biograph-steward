"""Deterministic, bounded answers from already verified tissue observations.

This reports saved study/reanalysis fields. It does not retrieve literature,
infer molecular binding, rescore statistics or establish independent accuracy.
"""
from copy import deepcopy
import re

from .client import digest
from .inspection import _external_url
from .questions import graph_basis

FORMAT = "biograph-steward.biological-question.v1"
ANCHOR = "UniProtKB:P00533"
INTERPRETATION = ("Primary-enriched proximity in pooled colorectal tumour and adjacent tissue, "
    "under the recorded assay and reanalysis. This does not establish direct binding, "
    "tumour-specific rewiring or clinical relevance. Source records are not independent experiment counts.")


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _citations(row):
    return [{"label": c.get("label") or c.get("id") or "Primary study", "url": c["url"],
             "role": c.get("role", "publication")}
            for c in row.get("citations", []) if isinstance(c, dict) and _external_url(c.get("url"))]


def answer_biological_question(graph, protein=ANCHOR, *, search="", offset=0, limit=25, source_run=None):
    """Page the recorded EGFR tissue observations without changing their scope."""
    _need(protein == ANCHOR, "This saved-data question supports the exact EGFR accession UniProtKB:P00533.")
    _need(isinstance(search, str) and len(search) <= 200, "Use a search string of at most 200 characters.")
    _need(type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 25,
          "Use a nonnegative offset and a page limit from 1 to 25.")
    _need(source_run is None or isinstance(source_run, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source_run),
          "Invalid saved workspace identifier.")
    _need(graph.get("evidence_extension_sha256") and graph.get("evidence_extension"),
          "This workspace has no verified biological source extension.")
    nodes = {row["id"]: row for row in graph["nodes"]}
    _need(ANCHOR in nodes, "EGFR is outside this saved graph.")
    edges = {row["id"]: row for row in graph["edges"]}
    assertions = {a["id"]: a for a in graph.get("assertions", [])}
    rows, seen = [], set()
    for original in graph.get("extension_observations", []):
        if original.get("source_kind") != "mapit":
            continue
        oid, products = original.get("id"), original.get("products")
        _need(isinstance(oid, str) and oid not in seen and isinstance(products, list)
              and len(products) == 2 and ANCHOR in products and len(set(products)) == 2,
              "Saved tissue observation has an ambiguous identity or participant scope.")
        seen.add(oid)
        partner = next(p for p in products if p != ANCHOR)
        _need(partner in nodes, "Tissue partner is missing its saved protein identity.")
        eid = original.get("graph_edge_id")
        _need(eid in edges and edges[eid].get("extension_source_kind") == "mapit"
              and {edges[eid]["subject"], edges[eid]["object"]} == set(products),
              "Saved tissue observation does not match its qualified evidence edge.")
        assertion = assertions.get(edges[eid].get("assertion_id"))
        node = nodes[partner]
        row = {"observation_id": oid, "partner": partner,
            "partner_label": node.get("sym") or node.get("name") or partner,
            "products": deepcopy(products), "graph_edge_id": eid,
            "assertion_id": assertion.get("id") if assertion else None,
            "local_review_state": assertion.get("lifecycle_state", "not_recorded") if assertion else "not_recorded",
            "assay_status": original.get("assay_status"), "assay": deepcopy(original.get("assay")),
            "tissue_label": deepcopy(original.get("tissue_label")),
            "statistics": deepcopy(original.get("statistics", {})),
            "statistical_family": deepcopy(original.get("statistical_family", {})),
            "sampling": deepcopy(original.get("sampling", {})),
            "archive_lookup": deepcopy(original.get("archive_lookup", {})),
            "source_identity": deepcopy(original.get("source_identity", {})),
            "source_locators": deepcopy(original.get("source_locators", [])),
            "citations": _citations(original), "interpretation": INTERPRETATION}
        rows.append(row)
    _need(rows, "This workspace has no qualified MAP-IT tissue observations for EGFR.")
    rows.sort(key=lambda r: (str(r["partner_label"]).casefold(), r["partner"], r["observation_id"]))
    query = search.strip().casefold()
    matched = [r for r in rows if not query or query in " ".join(str(r[k]) for k in
               ("partner", "partner_label", "assay", "tissue_label", "archive_lookup")).casefold()]
    page = matched[offset:offset + limit]
    result = {"format": FORMAT, "template": "egfr_tissue_evidence.v1", "source_run": source_run,
        "question": "Which EGFR partners have recorded colorectal-tissue proximity evidence, and what supports each?",
        "anchor": ANCHOR, "read_only": True, "model_calls": 0, "source_fetches": 0,
        "graph_basis_sha256": graph_basis(graph), "snapshot_sha256": graph["snapshot_sha256"],
        "evidence_extension_sha256": graph["evidence_extension_sha256"],
        "source_summary": deepcopy(graph["evidence_extension"]),
        "summary": {"source_observations": len(rows), "matching_observations": len(matched),
            "returned": len(page), "offset": offset, "limit": limit,
            "next_offset": offset + limit if offset + limit < len(matched) else None,
            "search": search, "primary_Pharos_target_scope_changed": False},
        "records": page, "interpretation": INTERPRETATION,
        "limitations": ["All listed observations remain derived from the saved study and source-key-corrected reanalysis.",
            "Alphabetical display does not rank biological confidence or combine source scores.",
            "An absent row in this view does not establish absence from Pharos, other tissues or other experiments.",
            "Archived overlap describes the bounded historical lookup, not current Pharos novelty or experimental independence.",
            "This page and its download do not independently validate the same observations used to build the graph."]}
    result["content_sha256"] = digest(result)
    return result
