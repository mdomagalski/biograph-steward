"""Turn one Pharos disease extract into a provenance-bearing, inspectable graph.

This is structural validation, NOT biological verification. Association source
scores remain unmodified and are never combined into a confidence probability.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import csv
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, urlparse

from .client import digest, utcnow, write_json
from . import __version__

LEVELS = {"Tclin", "Tchem", "Tbio", "Tdark"}
UNIPROT = re.compile(r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?$")


def text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def safe_url(value: Any) -> str | None:
    value = text(value)
    parsed = urlparse(value)
    return value if parsed.scheme in {"https", "http"} and parsed.netloc else None


def protein_id(value: Any, demo: bool = False) -> str | None:
    value = text(value)
    if demo and re.fullmatch(r"DEMO_PROTEIN_[0-9]{3}", value):
        return "demo:protein:" + value
    value = value.removeprefix("UniProtKB:")
    return "UniProtKB:" + value if UNIPROT.fullmatch(value) else None


def disease_id(disease: dict, demo: bool = False) -> tuple[str, bool]:
    raw = text(disease.get("mondoID"))
    if demo:
        return "demo:disease:CRC", False
    match = re.fullmatch(r"(?:MONDO[:_])?([0-9]{7})", raw)
    if match:
        return "MONDO:" + match.group(1), True
    return "pharos.disease:" + quote(text(disease.get("name")), safe=""), False


def pathway_id(pathway: dict, demo: bool = False) -> tuple[str | None, bool]:
    source_id = text(pathway.get("sourceID"))
    kind = text(pathway.get("type"))
    if demo and pathway.get("pwid") is not None:
        return "demo:pathway:" + str(pathway["pwid"]), False
    if "reactome" in kind.casefold() and re.fullmatch(r"R-[A-Z]{3}-[0-9]+(?:\.[0-9]+)?", source_id):
        return "REACT:" + source_id, True
    if pathway.get("pwid") is not None:
        return "pharos.pathway:" + str(pathway["pwid"]), False
    return None, False


def publication_ids(reference: Any) -> list[str]:
    """Only explicit PMID labels or PubMed URLs count; bare numbers are ambiguous."""
    value = text(reference)
    matches = re.findall(r"\bPMID\s*:?\s*(\d+)\b", value, flags=re.I)
    matches += re.findall(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", value, flags=re.I)
    return sorted({"PMID:" + x for x in matches})


def verify_snapshot(snapshot: dict) -> None:
    if snapshot.get("snapshot_format") != "biograph-steward.pharos.v1":
        raise ValueError("Unsupported snapshot format; use a snapshot.json produced by this starter.")
    if snapshot.get("data_kind") not in {"live_pharos", "synthetic_demo"}:
        raise ValueError("Snapshot must explicitly identify live_pharos or synthetic_demo data.")
    expected = snapshot.get("content_sha256")
    body = {k: v for k, v in snapshot.items() if k != "content_sha256"}
    if not expected or expected != digest(body):
        raise ValueError("Snapshot integrity check failed. Do not silently edit raw input; rebuild it.")
    for record in snapshot.get("requests", []):
        if record.get("response_sha256") != digest(record.get("response")):
            raise ValueError("Source response integrity check failed; rebuild from the untouched API cache or endpoint.")
    if not isinstance(snapshot.get("disease"), dict) or not snapshot["disease"].get("name"):
        raise ValueError("Snapshot is missing its selected disease.")
    if not isinstance(snapshot.get("targets"), list):
        raise ValueError("Snapshot is missing its target list.")


def build_graph(snapshot: dict, review_events: list[dict] | None = None) -> dict:
    verify_snapshot(snapshot)
    demo = snapshot["data_kind"] == "synthetic_demo"
    disease = snapshot["disease"]
    did, disease_mapped = disease_id(disease, demo)
    provenance_resource = "SYNTHETIC_DEMO" if demo else "Pharos"
    nodes = {did: {"id": did, "name": disease["name"], "category": "biolink:Disease",
                   "identifier_mapped": disease_mapped, "source_identifier": disease.get("mondoID"),
                   "url": None if demo else "https://pharos.nih.gov/diseases/" + quote(disease["name"], safe=""),
                   "tdl": None, "sym": None, "data_kind": snapshot["data_kind"]}}
    edges: dict[str, dict] = {}
    quarantine: list[dict] = []
    target_rows: dict[str, dict] = {}
    duplicate_rows = 0
    seen_rows: set[str] = set()

    def add_edge(subject: str, predicate: str, obj: str, record: dict, locator: str,
                 reasons: list[str], kind: str, source: Any, reference: Any = None, **attributes):
        identity = {"subject": subject, "predicate": predicate, "object": obj,
                    "record": record, "kind": kind}
        if "qualifiers" in attributes:
            identity["qualifiers"] = attributes["qualifiers"]
        eid = "edge:" + digest(identity)[:20]
        if eid in edges:
            edges[eid]["record_locators"].append(locator)
            edges[eid]["duplicate_count"] += 1
            return eid
        edges[eid] = {
            "id": eid, "subject": subject, "predicate": predicate, "object": obj,
            "status": "needs_review" if reasons else "passed_structural_checks",
            "review_reasons": sorted(set(reasons)), "record_kind": kind,
            "aggregator": provenance_resource, "primary_source_raw": source,
            "reference_raw": reference, "publications": publication_ids(reference),
            "evidence_raw": record.get("evidence"),
            "source_scores_raw": {key: record.get(key) for key in
                                  ["score", "conf", "zscore", "log2foldchange", "pvalue"]},
            "evidence_record": record, "record_locators": [locator], "duplicate_count": 0,
            "snapshot_sha256": snapshot["content_sha256"], "data_kind": snapshot["data_kind"],
            "biologically_validated": False,
            "qualifiers": {"disease": obj if kind in {"disease_association", "disease_filtered_membership"} else None},
        }
        edges[eid].update(attributes)
        return eid

    for i, row in enumerate(snapshot["targets"]):
        pointer = f"snapshot.json#/targets/{i}"
        if not isinstance(row, dict):
            quarantine.append({"reason": "malformed_target_record", "locator": pointer, "record": row})
            continue
        fingerprint = digest(row)
        if fingerprint in seen_rows:
            duplicate_rows += 1
            quarantine.append({"reason": "duplicate_target_record", "locator": pointer, "record": row})
            continue
        seen_rows.add(fingerprint)
        pid = protein_id(row.get("uniprot"), demo)
        if not pid or not text(row.get("name")):
            quarantine.append({"reason": "invalid_or_missing_protein_identifier_or_name",
                               "locator": pointer, "record": row})
            continue
        tdl = text(row.get("tdl")) or "Unknown"
        pnode = {"id": pid, "name": row["name"], "sym": row.get("sym"), "tdl": tdl,
                 "category": "biolink:Protein", "family": row.get("fam"),
                 "identifier_mapped": not demo, "data_kind": snapshot["data_kind"],
                 "url": None if demo else "https://pharos.nih.gov/targets/" + quote(text(row["uniprot"]), safe="")}
        if pid not in nodes:
            nodes[pid] = pnode
        elif nodes[pid].get("tdl") != tdl:
            quarantine.append({"reason": "conflicting_target_metadata", "locator": pointer, "record": row})
        reasons = []
        if not disease_mapped and not demo:
            reasons.append("unresolved_disease_ontology_id")
        if tdl not in LEVELS:
            reasons.append("unrecognized_target_development_level")
        records = row.get("diseaseAssociationDetails")
        if records is None:
            records = []
        if not isinstance(records, list):
            quarantine.append({"reason": "malformed_association_details", "locator": pointer, "record": row})
            records = []
        if not records:
            membership = {"evidence": None, "source": None, "reference": None,
                          "note": "Returned in a disease-filtered target list; detailed association evidence absent."}
            add_edge(pid, "biolink:associated_with", did, membership, pointer,
                     reasons + ["association_evidence_details_missing"], "disease_filtered_membership", None)
        for j, record in enumerate(records):
            locator = pointer + f"/diseaseAssociationDetails/{j}"
            if not isinstance(record, dict):
                quarantine.append({"reason": "malformed_association_record", "locator": locator, "record": record})
                continue
            edge_reasons = reasons.copy()
            if not text(record.get("source")):
                edge_reasons.append("primary_source_missing")
            if not text(record.get("reference")) and not text(record.get("evidence")):
                edge_reasons.append("reference_and_evidence_missing")
            record_name = text(record.get("name"))
            if not record_name:
                quarantine.append({"reason": "explicit_disease_context_missing", "locator": locator,
                                   "subject": pid, "record": record})
                continue
            record_did = did
            if record_name.casefold() != disease["name"].strip().casefold():
                edge_reasons.append("evidence_disease_name_differs_from_selected_term")
                edge_reasons.append("unresolved_disease_ontology_id")
                record_did = ("demo:disease:source:" if demo else "pharos.disease:") + quote(record_name, safe="")
                nodes.setdefault(record_did, {"id": record_did, "name": record_name,
                    "category": "biolink:Disease", "identifier_mapped": False,
                    "source_identifier": None, "url": None, "tdl": None, "sym": None,
                    "data_kind": snapshot["data_kind"]})
            add_edge(pid, "biolink:associated_with", record_did, record, locator, edge_reasons,
                     "disease_association", record.get("source"), record.get("reference"))
        pathways = row.get("pathways") or []
        if not isinstance(pathways, list):
            quarantine.append({"reason": "malformed_pathway_list", "locator": pointer, "record": pathways})
            pathways = []
        for j, pathway in enumerate(pathways):
            locator = pointer + f"/pathways/{j}"
            if not isinstance(pathway, dict):
                quarantine.append({"reason": "malformed_pathway_record", "locator": locator, "record": pathway})
                continue
            wid, pathway_mapped = pathway_id(pathway, demo)
            if not wid or not text(pathway.get("name")):
                quarantine.append({"reason": "pathway_identifier_or_name_missing", "locator": locator, "record": pathway})
                continue
            nodes.setdefault(wid, {"id": wid, "name": pathway["name"], "category": "biolink:Pathway",
                                   "identifier_mapped": pathway_mapped, "source_identifier": pathway.get("sourceID"),
                                   "url": safe_url(pathway.get("url")), "tdl": None, "sym": None,
                                   "data_kind": snapshot["data_kind"]})
            edge_reasons = []
            if not text(pathway.get("type")):
                edge_reasons.append("primary_source_missing")
            if not pathway_mapped and not demo:
                edge_reasons.append("local_pathway_identifier_needs_mapping")
            add_edge(pid, "biolink:participates_in", wid, pathway, locator, edge_reasons,
                     "pathway_membership", pathway.get("type"))
        target_rows[pid] = {"id": pid, "symbol": row.get("sym"), "name": row["name"],
                            "tdl": nodes[pid]["tdl"], "family": row.get("fam")}

    from .context import context_records, attach_response_provenance
    from .normalization import normalize_context
    context = context_records(snapshot, quarantine)
    attach_response_provenance(context, snapshot)
    normalization = normalize_context(context, nodes, quarantine, add_edge, snapshot)

    for pid, row in target_rows.items():
        associated = [e for e in edges.values() if e["subject"] == pid and e["object"] == did]
        row["association_record_count"] = len(associated)
        row["other_disease_record_count"] = sum(e["subject"] == pid and e["predicate"] == "biolink:associated_with"
                                                and e["object"] != did for e in edges.values())
        row["reported_sources"] = sorted({text(e["primary_source_raw"]) for e in associated if text(e["primary_source_raw"])})
        row["review_record_count"] = sum(e["status"] == "needs_review" for e in associated)
        row["pathway_count"] = len({e["object"] for e in edges.values() if e["subject"] == pid and e["predicate"] == "biolink:participates_in"})

    status_counts = Counter(e["status"] for e in edges.values())
    summary = {
        "target_rows_received": len(snapshot["targets"]), "proteins": len(target_rows),
        "pathways": sum(n["category"] == "biolink:Pathway" for n in nodes.values()),
        "nodes": len(nodes), "evidence_edges": len(edges),
        "unique_association_pairs": len({(e["subject"], e["object"]) for e in edges.values()
                                         if e["predicate"] == "biolink:associated_with"}),
        "passed_structural_checks": status_counts["passed_structural_checks"],
        "needs_review": status_counts["needs_review"], "quarantined_records": len(quarantine),
        "duplicate_target_records": duplicate_rows,
        "tdl_counts": dict(sorted(Counter(r["tdl"] for r in target_rows.values()).items())),
    }
    graph = {"graph_format": "biograph-steward.evidence-graph.v3", "data_kind": snapshot["data_kind"],
            "disease": disease, "disease_node_id": did, "summary": summary,
            "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
            "edges": sorted(edges.values(), key=lambda e: e["id"]),
            "targets": sorted(target_rows.values(), key=lambda r: (text(r["symbol"]), r["id"])),
            "quarantine": quarantine, "retrieval": snapshot["retrieval"],
            "warnings": snapshot.get("warnings", []), "db_version": snapshot.get("db_version"),
            "snapshot_sha256": snapshot["content_sha256"], "snapshot_created_at": snapshot["created_at"],
            "interpretation": "Known database associations and annotations, not predictions or validated targets. "
                              "Passed structural checks does not mean scientifically verified. "
                              "Pathway membership is not disease-specific evidence."}
    graph["question_scope"] = {
        "template": "pharos_disease_inspection.v1",
        "question": f"Which proteins does Pharos associate with {disease['name']}, and which pathways annotate them?",
        "disease": {"id": did, "name": disease["name"]},
        "relation_families": ["disease_association", "pathway_membership"],
        "limits": deepcopy(snapshot["query_settings"]),
        "pathways_are_disease_specific": False,
        "unsupported_requirements": ["variant-specific response", "therapy resistance", "causal conclusions"],
    }
    graph["context_records"] = context
    graph["normalization"] = normalization
    graph["context_metadata"] = [{"uniprot": t.get("uniprot"), "symbol": t.get("sym"),
                                  **t["pharos_context"].get("metadata", {})}
                                 for t in snapshot["targets"] if isinstance(t, dict) and isinstance(t.get("pharos_context"), dict)]
    if snapshot.get("retrieval", {}).get("context"):
        graph["question_scope"]["question"] = (f"Which proteins does Pharos associate with {disease['name']}, "
            "and what pathway, functional, interaction, drug, tissue and literature context is available for this cohort?")
        graph["question_scope"]["context_families"] = list(snapshot["retrieval"]["context"]["summary"])
    from .assertions import build_assertions, assertion_summary
    graph["review_events"] = deepcopy(review_events) if review_events is not None else []
    graph["assertions"] = build_assertions(graph, graph["review_events"])
    graph["assertion_summary"] = assertion_summary(graph["assertions"])
    edge_lookup = {e["id"]: e for e in graph["edges"]}
    for record in context:
        record["assertion_ids"] = sorted({edge_lookup[eid]["assertion_id"] for eid in record["normalized_evidence_edge_ids"]})
    for family, counts in normalization["families"].items():
        counts["assertions"] = len({aid for r in context if r["family"] == family for aid in r["assertion_ids"]})
    graph["question_scope"]["relation_families"] = sorted({a["kind"] for a in graph["assertions"]})
    graph["summary"]["assertions_by_kind"] = dict(sorted(Counter(a["kind"] for a in graph["assertions"]).items()))
    from .benchmark import audit_graph
    graph['benchmark_readiness'] = audit_graph(graph)
    from .questions import graph_basis
    graph['question_basis_sha256'] = graph_basis(graph)
    return graph


def _write_tsv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            flat = {key: json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list))
                    else "" if value is None else value for key, value in row.items()}
            # Prevent formula interpretation when a table is opened in a spreadsheet.
            for key, value in flat.items():
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                    flat[key] = "'" + value
            writer.writerow(flat)


def save_run(snapshot: dict, directory: Path, *, run_mode: str = "build", review_events: list[dict] | None = None) -> dict:
    graph = build_graph(snapshot, review_events)
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Output directory is not empty. Choose a new directory to preserve previous runs.")
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "snapshot.json", snapshot)
    write_json(directory / "graph.json", graph)
    write_json(directory / "assertions.json", graph["assertions"])
    write_json(directory / "context_records.json", graph["context_records"])
    write_json(directory / "context_metadata.json", graph["context_metadata"])
    write_json(directory / "normalization_report.json", graph["normalization"])
    _write_tsv(directory / "context_records.tsv", graph["context_records"],
               ["id", "subject", "symbol", "family", "label", "source", "record", "record_locators",
                "snapshot_sha256", "review_status", "interpretation", "normalization_status", "normalized_evidence_edge_ids", "assertion_ids"])
    coverage = snapshot.get("retrieval", {}).get("context")
    if coverage is not None:
        write_json(directory / "retrieval_coverage.json", coverage)
        _write_tsv(directory / "retrieval_coverage.tsv", coverage["targets"],
                   ["uniprot", "symbol", "family", "available", "available_before_scope", "retrieved", "retained",
                    "excluded_by_scope", "limit", "status", "issues", "pages"])
    write_json(directory / "review_events.json", graph["review_events"])
    write_json(directory / "question_scope.json", graph["question_scope"])
    _write_tsv(directory / "assertions.tsv", graph["assertions"],
               ["id", "subject", "predicate", "object", "kind", "qualifiers", "lifecycle_state",
                "validation_status", "evidence_edge_ids", "source_record_count", "publications", "normalization_notes", "revision", "snapshot_sha256"])
    from .benchmark import write_audit
    write_audit(graph['benchmark_readiness'], directory)
    write_json(directory / "source_licenses.json", snapshot.get("source_licenses", []))
    for i, record in enumerate(snapshot.get("requests", [])):
        write_json(directory / "raw_responses" / f"{i:03d}.json", record)
    _write_tsv(directory / "nodes.tsv", graph["nodes"],
               ["id", "name", "category", "sym", "tdl", "identifier_mapped", "url", "data_kind"])
    _write_tsv(directory / "edges.tsv", graph["edges"],
               ["id", "assertion_id", "subject", "predicate", "object", "qualifiers", "status", "review_reasons", "aggregator",
                "primary_source_raw", "reference_raw", "publications", "source_scores_raw",
                "record_locators", "source_record_count", "normalization_notes", "observation", "annotation_context", "context_record_ids", "retrieval_provenance", "snapshot_sha256", "data_kind"])
    _write_tsv(directory / "targets.tsv", graph["targets"],
               ["id", "symbol", "name", "tdl", "family", "association_record_count",
                "reported_sources", "review_record_count", "pathway_count"])
    with (directory / "quarantine.jsonl").open("w", encoding="utf-8") as handle:
        for row in graph["quarantine"]:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    trace = [
        {"step": "select_disease", "result": snapshot["disease"]["name"]},
        {"step": "retrieve", "result": snapshot["retrieval"], "data_kind": snapshot["data_kind"]},
        {"step": "normalize_and_check", "result": graph["summary"]},
        {"step": "normalize_source_context", "result": graph["normalization"]},
        {"step": "publish_inspection_graph", "result": "No predictive model or LLM was run."},
    ]
    write_json(directory / "pipeline_trace.json", trace)
    manifest = {"starter_version": __version__, "graph_format": graph['graph_format'],
                "assertion_summary": graph['assertion_summary'], "normalization_policy": graph["normalization"]["policy"], "review_event_count": len(graph['review_events']),
                "created_at": utcnow(), "run_mode": run_mode,
                "data_kind": snapshot["data_kind"], "endpoint": snapshot.get("endpoint"),
                "database_version": snapshot.get("db_version"), "schema_check": snapshot.get("schema_check"),
                "snapshot_sha256": snapshot["content_sha256"], "query_settings": snapshot["query_settings"],
                "retrieval": snapshot["retrieval"], "summary": graph["summary"],
                "network_cache_hits": sum(r.get("loaded_from_cache", False) for r in snapshot.get("requests", [])),
                "upstream_retrieval_times": sorted({r["retrieved_at"] for r in snapshot.get("requests", [])}),
                "biological_validation_performed": False, "link_prediction_performed": False,
                "llm_used": False, "warnings": snapshot.get("warnings", []),
                "license_note": "Software and retrieved data have separate terms. Review source_licenses.json and upstream licenses before redistributing."}
    write_json(directory / "run_manifest.json", manifest)
    from .webapp import report_html
    (directory / "report.html").write_text(report_html(graph), encoding="utf-8")
    return graph
