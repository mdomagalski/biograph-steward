#!/usr/bin/env python3
"""Retrieve an explicit accession inventory using the existing Pharos adapter.

Stages source records, not learner features. Resumable chunks retain the entire
PPI population and all tissue labels. No experimental outcome file is opened.
The explicit-ID transport is adapted from the archived matched-panel adapter;
its CRC filters, feature policy and cohort selection are deliberately absent.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from biograph_steward.client import (ENDPOINT, LICENSES, VERSION, PharosClient,
                                    PharosError, digest, utcnow, write_json)
from biograph_steward.graph import UNIPROT
from biograph_steward.retrieval import BATCH_SIZE, MAX_LIMITS, retrieve_context

LIMITS = {**MAX_LIMITS, "publications": 0}
PPI_LIMITS = {key: (MAX_LIMITS[key] if key == "ppis" else 0) for key in MAX_LIMITS}
ACCESSION_FORMAT = "biograph-steward.lambourne-ppi-lookup-candidate-inventory.v1"
ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text())


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def accession_inventory(path):
    inventory = read_json(path)
    if inventory.get("format") == ACCESSION_FORMAT:
        ids = inventory.get("published_uniprot_accessions")
        if (not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not UNIPROT.fullmatch(x) for x in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("Inventory must contain unique valid accessions.")
        if (inventory.get("outcome_fields_decoded") is not False or
                not re.fullmatch(r"[a-f0-9]{40}", str(inventory.get("author_commit", ""))) or
                not re.fullmatch(r"[a-f0-9]{64}", str(inventory.get("author_panel_sha256", "")))):
            raise ValueError("Accession inventory lacks reviewed author source bindings.")
        return inventory, sorted(ids)
    if inventory.get("format") != "biograph-steward.inmc-context-targets.v1":
        raise ValueError("Expected the audited context inventory, not an outcome table.")
    genes = inventory["panel_gene_ids"]
    ids = [r["uniprot_id"].removeprefix("UniProtKB:") for r in inventory["targets"]]
    if not ids or len(ids) != len(set(ids)) or any(not UNIPROT.fullmatch(x) for x in ids):
        raise ValueError("Inventory must contain unique valid accessions.")
    if len(genes) != len(set(genes)) or not genes:
        raise ValueError("Inventory must retain distinct original gene identifiers.")
    mapped = {g for r in inventory["targets"] for g in r["panel_gene_ids"]}
    gaps = set(inventory["panel_genes_without_confirmed_context"])
    if mapped & gaps or mapped | gaps != set(genes):
        raise ValueError("Inventory gene coverage is inconsistent.")
    return inventory, sorted(ids)


def identity_query(ids):
    definitions = ", ".join(f"$id{i}: String!" for i in range(len(ids)))
    fields = " ".join(f"t{i}: target(q: {{uniprot: $id{i}}}) {{ uniprot sym name tdl fam }}"
                      for i in range(len(ids)))
    return f"query ExplicitInventoryTargets({definitions}) {{ {fields} }}", {
        f"id{i}": uid for i, uid in enumerate(ids)}


def seal(value):
    return {**value, "content_sha256": digest(value)}


def verify_sealed(value):
    if value.get("content_sha256") != digest({k: v for k, v in value.items() if k != "content_sha256"}):
        raise ValueError("Saved retrieval artifact changed.")
    for record in value.get("requests", []):
        if record.get("response_sha256") != digest(record["response"]):
            raise ValueError("Saved Pharos response changed.")
        PharosClient._validate_response(record["response"])
    return value


def build_chunk(client, ids, all_ids, expected_version, progress=None, *, limits=None, ppi_batch_size=1):
    """Indices in every locator refer to this chunk's request list."""
    start = len(client.records)
    before = client.execute(VERSION, cache=False).get("dbVersion")
    if not before or before != expected_version:
        raise PharosError("Pharos version changed; start a separate retrieval.")
    targets, resolution = [], []
    for offset in range(0, len(ids), BATCH_SIZE):
        batch = ids[offset:offset + BATCH_SIZE]
        index = len(client.records) - start
        data = client.execute(*identity_query(batch))
        for i, uid in enumerate(batch):
            key = f"t{i}"
            row = data.get(key)
            if key not in data or (row is not None and not isinstance(row, dict)):
                raise PharosError("Malformed explicit identity response.")
            status = ("not_found" if row is None else
                      "resolved" if row.get("uniprot") == uid else "identity_mismatch")
            resolution.append({"requested_uniprot": uid, "status": status, "returned": row,
                               "request_index": index, "response_pointer": f"/data/{key}"})
            if status == "resolved":
                targets.append(deepcopy(row))
    limits = LIMITS if limits is None else limits
    coverage = retrieve_context(
        client, targets, limits, row_budget=sum(limits.values()) * len(ids),
        expression_scope="all", ppi_cohort=all_ids,
        batch_sizes={"ppis": ppi_batch_size, "expressions": 1}, progress=progress) if targets else None
    if coverage:
        for row in coverage["targets"]:
            for page in row["pages"]:
                page["request_index"] -= start
    after = client.execute(VERSION, cache=False).get("dbVersion")
    if after != before:
        raise PharosError("Pharos version changed during this chunk; no completed chunk published.")
    return seal({
        "format": "biograph-steward.pharos-inventory-chunk.v1", "created_at": utcnow(),
        "endpoint": client.endpoint, "requested_uniprots": ids,
        "db_version_before": before, "db_version_after": after,
        "target_resolution": resolution, "targets": targets, "retrieval_coverage": coverage,
        "requests": client.records[start:], "disease_filter_used": False,
        "outcome_values_loaded": False, "model_requests": 0,
        "transport_kind": "injected_test" if client.transport else "http",
        "feature_use_approved": False,
    })


def summarize(out, plan, inventory, ids):
    statuses, families, resolved, files = Counter(), {}, set(), {}
    responses = cached = chunks = 0
    versions = set()
    for offset in range(0, len(ids), plan["chunk_size"]):
        name = f"chunks/{offset:05d}.json"
        path = out / name
        if not path.exists():
            continue
        chunk = verify_sealed(read_json(path))
        if (chunk["requested_uniprots"] != ids[offset:offset + plan["chunk_size"]]
                or chunk.get("plan_sha256") != plan["content_sha256"]):
            raise ValueError("Saved chunk differs from the frozen retrieval plan.")
        files[name] = file_sha(path)
        chunks += 1
        versions.update([chunk["db_version_before"], chunk["db_version_after"]])
        statuses.update(r["status"] for r in chunk["target_resolution"])
        resolved.update(r["requested_uniprot"] for r in chunk["target_resolution"] if r["status"] == "resolved")
        responses += len(chunk["requests"])
        cached += sum(bool(r.get("loaded_from_cache")) for r in chunk["requests"])
        for family, row in (chunk["retrieval_coverage"] or {}).get("summary", {}).items():
            aggregate = families.setdefault(family, {"retrieved": 0, "retained": 0,
                "excluded_by_scope": 0, "available": 0, "target_statuses": Counter()})
            for key in ["retrieved", "retained", "excluded_by_scope"]:
                aggregate[key] += row[key]
            aggregate["available"] = (None if row["available"] is None or aggregate["available"] is None
                                      else aggregate["available"] + row["available"])
            aggregate["target_statuses"].update(row["target_statuses"])
    accession_only = inventory.get("format") == ACCESSION_FORMAT
    gene_products = {g: [] for g in inventory.get("panel_gene_ids", [])}
    for row in inventory.get("targets", []):
        for gene in row["panel_gene_ids"]:
            gene_products[gene].append(row["uniprot_id"].removeprefix("UniProtKB:"))
    gene_coverage = [{"original_gene_id": g, "requested_products": ps,
                      "resolved_products": sorted(set(ps) & resolved)} for g, ps in sorted(gene_products.items())]
    complete = sum(statuses.values()) == len(ids)
    summary = seal({"format": "biograph-steward.pharos-inventory-summary.v1", "created_at": utcnow(),
        "plan_sha256": plan["content_sha256"], "retrieval_finished": complete,
        "completed_chunks": chunks, "requested_accessions": len(ids), "resolution_statuses": dict(statuses),
        "original_gene_count": None if accession_only else len(gene_products),
        "genes_with_resolved_context": None if accession_only else sum(bool(r["resolved_products"]) for r in gene_coverage),
        "identity_level": "author_protein_accession" if accession_only else "original_gene_with_product_context",
        "db_versions": sorted(versions), "families": families,
        "successful_source_envelopes": responses, "cached_source_envelopes": cached,
        "all_requested_families_count_reconciled": complete and bool(resolved) and all(
            family in families and families[family]["target_statuses"] == {"complete": len(resolved)}
            for family in plan["limits"] if plan["limits"][family]),
        "files": files, "feature_use_approved": False, "outcome_values_loaded": False,
        "model_requests": 0, "scientific_improvement_measured": False,
        "scope_note": "Uniform bounded API profile, not the full Pharos database or a learner-ready graph. Missing context never removes assay candidates."})
    write_json(out / "gene_coverage.json", gene_coverage)
    if accession_only:
        write_json(out / "accession_coverage.json", [
            {"requested_uniprot": uid, "resolved": uid in resolved} for uid in ids])
    write_json(out / "summary.json", summary)
    return summary


def retrieve_inventory(inventory_path, output, *, chunk_size=25, resume=False,
                       stop_after_chunks=None, client_factory=None, progress=print, profile="context"):
    inventory_path, out = Path(inventory_path), Path(output)
    inventory, ids = accession_inventory(inventory_path)
    if profile not in {"context", "ppi"}:
        raise ValueError("Use the context or ppi retrieval profile.")
    if inventory.get("format") == ACCESSION_FORMAT and profile != "ppi":
        raise ValueError("The reviewed external accession inventory is approved for the ppi profile only.")
    limits = LIMITS if profile == "context" else PPI_LIMITS
    ppi_batch_size = 1 if profile == "context" else BATCH_SIZE
    if type(chunk_size) is not int or not 1 <= chunk_size <= 100:
        raise ValueError("Use a chunk size from 1 to 100.")
    if stop_after_chunks is not None and (type(stop_after_chunks) is not int or stop_after_chunks < 1):
        raise ValueError("Stop-after-chunks must be positive.")
    bindings = {"format": "biograph-steward.pharos-inventory-plan.v1",
        "inventory_sha256": file_sha(inventory_path), "endpoint": ENDPOINT,
        "chunk_size": chunk_size, "limits": limits, "expression_scope": "all",
        "profile": profile, "ppi_batch_size": ppi_batch_size,
        "ppi_cohort": ids, "ppi_confidence": 400,
        "code_sha256": {str(p.relative_to(ROOT)): file_sha(p) for p in
                        [Path(__file__), ROOT / "biograph_steward/client.py", ROOT / "biograph_steward/retrieval.py"]},
        "not_requested": ["disease associations", "separate GTEx endpoint", "non-drug ligand activities",
                          "GWAS", "LINCS", "full text and publication discovery", "external affiliate datasets"]
                         + (["GO annotation rows", "pathway rows", "drug rows", "expression rows"] if profile == "ppi" else []),
        "use": "Source staging only; all features need source/pair exclusions before any learning."}
    if out.exists():
        if not resume:
            raise ValueError("Output exists; use --resume with the identical inventory and code.")
        plan = verify_sealed(read_json(out / "plan.json"))
        if {k: plan[k] for k in bindings} != bindings:
            raise ValueError("Retrieval plan, inventory, or implementation changed; use a new output.")
    else:
        if resume:
            raise ValueError("Cannot resume a missing output directory.")
        out.mkdir(parents=True)
        plan = seal({**bindings, "created_at": utcnow()})
        write_json(out / "plan.json", plan)
        (out / "context_targets.json").write_bytes(inventory_path.read_bytes())
    def new_client():
        return (client_factory() if client_factory else
                PharosClient(cache_dir=out / "responses", timeout=60, retries=2, ttl_hours=168))
    source_path = out / "source.json"
    if not source_path.exists():
        if any((out / "chunks").glob("*.json")):
            raise ValueError("Completed chunks lack their source metadata; no network requests made.")
        client = new_client()
        version = client.execute(VERSION, cache=False).get("dbVersion")
        catalog = client.execute(LICENSES).get("dataSourceCounts")
        if not isinstance(version, str) or not version or not isinstance(catalog, list):
            raise PharosError("Source version/catalog metadata unavailable.")
        write_json(source_path, seal({"db_version": version, "source_catalog": catalog,
                                     "plan_sha256": plan["content_sha256"], "endpoint": client.endpoint,
                                     "requests": client.records, "created_at": utcnow()}))
    source = verify_sealed(read_json(source_path))
    if source.get("plan_sha256") != plan["content_sha256"] or source.get("endpoint") != plan["endpoint"]:
        raise ValueError("Source metadata does not belong to this plan/endpoint.")
    if file_sha(out / "context_targets.json") != plan["inventory_sha256"]:
        raise ValueError("Saved inventory changed.")
    completed_now = 0
    # Validate every existing chunk before making any further requests.
    summary = summarize(out, plan, inventory, ids)
    if summary["db_versions"] and summary["db_versions"] != [source["db_version"]]:
        raise ValueError("Saved chunks contain different Pharos versions.")
    processed = sum(summary["resolution_statuses"].values())
    retrieved = sum(x["retrieved"] for x in summary["families"].values())
    for offset in range(0, len(ids), chunk_size):
        path = out / "chunks" / f"{offset:05d}.json"
        if path.exists():
            continue
        if stop_after_chunks is not None and completed_now >= stop_after_chunks:
            break
        if progress:
            progress(f"Retrieving accessions {offset + 1}–{min(offset + chunk_size, len(ids))}/{len(ids)}", flush=True)
        client = new_client()
        try:
            chunk = build_chunk(client, ids[offset:offset + chunk_size], ids, source["db_version"],
                                limits=limits, ppi_batch_size=ppi_batch_size)
            chunk.pop("content_sha256")
            chunk["plan_sha256"] = plan["content_sha256"]
            write_json(path, seal(chunk))
        except Exception as exc:
            # Successful envelopes are still preserved by the existing cache.
            write_json(out / "attempts" / (utcnow().replace(":", "-") + ".json"),
                       {"offset": offset, "error_type": type(exc).__name__, "error": str(exc),
                        "successful_requests": len(client.records), "created_at": utcnow()})
            summarize(out, plan, inventory, ids)
            raise
        completed_now += 1
        processed += len(chunk["requested_uniprots"])
        retrieved += (chunk["retrieval_coverage"] or {}).get("rows_retrieved", 0)
        write_json(out / "progress.json", {"created_at": utcnow(), "completed_accessions": processed,
                                          "requested_accessions": len(ids), "retrieved_rows": retrieved})
        if progress:
            progress(f"Saved {processed}/{len(ids)} accessions; {retrieved:,} source rows", flush=True)
    return summarize(out, plan, inventory, ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-chunks", type=int)
    parser.add_argument("--profile", choices=["context", "ppi"], default="context")
    args = parser.parse_args()
    result = retrieve_inventory(args.inventory, args.output_dir, chunk_size=args.chunk_size,
                                resume=args.resume, stop_after_chunks=args.stop_after_chunks, profile=args.profile)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
