#!/usr/bin/env python3
"""Audit staged Pharos coverage and candidate-pair overlap without outcome decoding.

This is a mask inventory, not a feature generator or biological evaluation.
Only the first two identity fields of the pinned experimental table are decoded.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_inmc_inputs import ARCHIVE_SHA256, PANEL_MEMBER, identifier_pairs, sha256
from retrieve_pharos_inventory import accession_inventory, file_sha, read_json, seal, verify_sealed
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output

BLOCKED_PMID = re.compile(r"(?<![0-9])36949045(?![0-9])")
REFERENCE_FIELDS = {"reference", "references", "pub", "publications", "pmid", "pmids"}
POLARITY_FIELDS = {"negated", "negation", "qualifier", "qualifiers", "relation", "extensions"}


def panel_identities(archive):
    raw = Path(archive).read_bytes()
    if sha256(raw) != ARCHIVE_SHA256:
        raise ValueError("Archive differs from the checked Zenodo release")
    with zipfile.ZipFile(BytesIO(raw)) as bundle:
        member = bundle.read(PANEL_MEMBER)
    return identifier_pairs(member, panel=True), sha256(member)


def pair_inventory(pairs, inventory):
    products = {gene: set() for gene in inventory["panel_gene_ids"]}
    for row in inventory["targets"]:
        for gene in row["panel_gene_ids"]:
            products[gene].add(row["uniprot_id"].removeprefix("UniProtKB:"))
    if {gene for pair in pairs for gene in pair} != set(products):
        raise ValueError("Experimental identity population differs from the frozen inventory.")
    originals = defaultdict(list)
    for number, pair in enumerate(pairs, 2):
        originals[tuple(sorted(pair))].append({"source_row": number, "source": pair[0], "target": pair[1]})
    candidates, equivalents = [], defaultdict(set)
    for index, (pair, source_rows) in enumerate(sorted(originals.items())):
        candidate_id = f"candidate:{index:05d}"
        projected = {tuple(sorted((a, b))) for a in products[pair[0]] for b in products[pair[1]]}
        for projected_pair in projected:
            equivalents[projected_pair].add(candidate_id)
        candidates.append({"id": candidate_id, "original_genes": list(pair), "source_rows": source_rows,
                           "products_by_gene": {gene: sorted(products[gene]) for gene in set(pair)},
                           "self_pair": pair[0] == pair[1], "equivalent_product_pairs": [list(p) for p in sorted(projected)],
                           "missing_mapped_context_genes": [gene for gene in sorted(set(pair)) if not products[gene]]})
    return products, candidates, equivalents


def verified_header(folder):
    folder = Path(folder)
    for name in ["plan.json", "source.json", "summary.json", "context_targets.json", "gene_coverage.json"]:
        if (folder / name).is_symlink():
            raise ValueError("Audit inputs must be ordinary saved files, not symlinks.")
    plan, source, summary = [verify_sealed(read_json(folder / name))
                             for name in ["plan.json", "source.json", "summary.json"]]
    inventory, ids = accession_inventory(folder / "context_targets.json")
    if file_sha(folder / "context_targets.json") != plan["inventory_sha256"]:
        raise ValueError("Saved inventory hash differs from the plan.")
    if inventory.get("archive_sha256") != ARCHIVE_SHA256:
        raise ValueError("Inventory does not identify the pinned experimental archive.")
    if (source.get("plan_sha256") != plan["content_sha256"] or
            summary.get("plan_sha256") != plan["content_sha256"] or
            source.get("endpoint") != plan["endpoint"] or plan["ppi_cohort"] != ids):
        raise ValueError("Retrieval artifacts have inconsistent plan or population bindings.")
    size = plan["chunk_size"]
    if type(size) is not int or size < 1 or not summary.get("retrieval_finished"):
        raise ValueError("A completed explicit-accession retrieval is required.")
    names = [f"chunks/{offset:05d}.json" for offset in range(0, len(ids), size)]
    actual = {str(p.relative_to(folder)) for p in (folder / "chunks").glob("*.json")}
    if actual != set(names) or set(summary["files"]) != set(names):
        raise ValueError("Chunk files do not match the completed retrieval manifest.")
    for record in source["requests"]:
        if record["endpoint"] != plan["endpoint"]:
            raise ValueError("Source response endpoint differs from the plan.")
    return plan, source, summary, inventory, ids, names


def verified_chunk(folder, name, plan, source, summary, expected_ids):
    path = Path(folder) / name
    if path.is_symlink() or file_sha(path) != summary["files"][name]:
        raise ValueError("Chunk file hash differs from the completed manifest.")
    chunk = verify_sealed(read_json(path))
    if (chunk.get("plan_sha256") != plan["content_sha256"] or chunk["requested_uniprots"] != expected_ids or
            chunk["endpoint"] != plan["endpoint"] or
            chunk["db_version_before"] != source["db_version"] or chunk["db_version_after"] != source["db_version"]):
        raise ValueError("Chunk identity, version, or plan binding is inconsistent.")
    resolutions = chunk["target_resolution"]
    if ([row["requested_uniprot"] for row in resolutions] != expected_ids or
            any(row["status"] not in {"resolved", "not_found", "identity_mismatch"} for row in resolutions)):
        raise ValueError("Chunk resolution does not account for every requested accession.")
    resolved = [row["requested_uniprot"] for row in resolutions if row["status"] == "resolved"]
    if [row["uniprot"] for row in chunk["targets"]] != resolved:
        raise ValueError("Chunk targets differ from resolved identities.")
    for record in chunk["requests"]:
        if record["endpoint"] != plan["endpoint"]:
            raise ValueError("Chunk response endpoint differs from the plan.")
    return chunk


def source_rows(chunk, name, family):
    for request_index, envelope in enumerate(chunk["requests"]):
        if not re.search(r"\bquery\s+Scoped_" + re.escape(family) + r"\b", envelope["request"]["query"]):
            continue
        for alias, target in envelope["response"]["data"].items():
            if not re.fullmatch(r"t[0-9]+", alias) or not isinstance(target, dict):
                raise ValueError("Malformed scoped response alias.")
            uid = target.get("uniprot")
            if envelope["request"]["variables"].get("id" + alias[1:]) != uid or not isinstance(target.get("rows"), list):
                raise ValueError("Scoped response target differs from its request.")
            for index, row in enumerate(target["rows"]):
                if not isinstance(row, dict):
                    raise ValueError("Malformed scoped annotation row.")
                yield uid, row, f"{name}#/requests/{request_index}/response/data/{alias}/rows/{index}"


def retained_rows(chunk, name, family):
    for index, target in enumerate(chunk["targets"]):
        for row_index, row in enumerate(target.get("pharos_context", {}).get(family, [])):
            yield target["uniprot"], row, f"{name}#/targets/{index}/pharos_context/{family}/{row_index}"


def go_observation():
    return {"rows": 0, "assigned_by": Counter(), "observed_fields": Counter(),
            "rows_with_reference_field": 0, "rows_with_nonempty_reference_field": 0,
            "rows_with_polarity_or_relation_field": 0}


def count_go(summary, row):
    summary["rows"] += 1
    summary["assigned_by"][str(row.get("assigned_by") or "<missing>")] += 1
    summary["observed_fields"].update(row.keys())
    summary["rows_with_reference_field"] += bool(REFERENCE_FIELDS & row.keys())
    summary["rows_with_nonempty_reference_field"] += any(row.get(key) not in (None, "", []) for key in REFERENCE_FIELDS)
    summary["rows_with_polarity_or_relation_field"] += bool(POLARITY_FIELDS & row.keys())


def mention_diagnostics(artifact, name):
    observations = []
    for index, envelope in enumerate(artifact["requests"]):
        count = len(BLOCKED_PMID.findall(json.dumps(envelope["response"], sort_keys=True)))
        if count:
            observations.append({"locator": f"{name}#/requests/{index}/response", "matches": count,
                                 "response_sha256": envelope["response_sha256"]})
    return observations


def audit(folder, archive):
    folder = Path(folder)
    plan, source, saved, inventory, ids, names = verified_header(folder)
    pairs, member_hash = panel_identities(archive)
    products, candidates, equivalents = pair_inventory(pairs, inventory)
    matches = {"raw": [], "retained": []}
    total_ppi = Counter()
    go = {"raw": go_observation(), "retained": go_observation()}
    mentions = mention_diagnostics(source, "source.json")
    statuses, resolved, families = Counter(), set(), {}
    response_count = cached_response_count = 0
    for number, name in enumerate(names):
        chunk = verified_chunk(folder, name, plan, source, saved,
                               ids[number * plan["chunk_size"]:(number + 1) * plan["chunk_size"]])
        statuses.update(row["status"] for row in chunk["target_resolution"])
        resolved.update(row["requested_uniprot"] for row in chunk["target_resolution"] if row["status"] == "resolved")
        response_count += len(chunk["requests"])
        cached_response_count += sum(bool(row.get("loaded_from_cache")) for row in chunk["requests"])
        for family, row in (chunk["retrieval_coverage"] or {}).get("summary", {}).items():
            aggregate = families.setdefault(family, {"retrieved": 0, "retained": 0, "excluded_by_scope": 0,
                                                     "available": 0, "target_statuses": Counter()})
            for key in ["retrieved", "retained", "excluded_by_scope"]:
                aggregate[key] += row[key]
            aggregate["available"] = None if row["available"] is None or aggregate["available"] is None else aggregate["available"] + row["available"]
            aggregate["target_statuses"].update(row["target_statuses"])
        mentions.extend(mention_diagnostics(chunk, name))
        raw_counts = Counter()
        for view, iterator in [("raw", source_rows), ("retained", retained_rows)]:
            for uid, row, locator in iterator(chunk, name, "ppis"):
                partner = row.get("target", {}).get("uniprot")
                if not isinstance(partner, str) or not partner:
                    raise ValueError("PPI source row lacks a partner identity.")
                key = (uid, digest(row))
                if view == "raw":
                    raw_counts[key] += 1
                elif raw_counts[key] < 1:
                    raise ValueError("Retained PPI row has no identical raw response view.")
                else:
                    raw_counts[key] -= 1
                total_ppi[view] += 1
                product_pair = tuple(sorted((uid, partner)))
                if product_pair in equivalents:
                    providers = sorted({p.strip() for p in str(row.get("type") or "").split(",") if p.strip()})
                    matches[view].append({"reported_subject": uid, "reported_partner": partner,
                                          "unordered_product_pair": list(product_pair),
                                          "candidate_ids": sorted(equivalents[product_pair]), "providers": providers,
                                          "source_bundle": row.get("type"), "record_sha256": digest(row), "locator": locator})
            for _, row, _ in iterator(chunk, name, "go"):
                count_go(go[view], row)
    gene_coverage = [{"original_gene_id": gene, "requested_products": sorted(values),
                      "resolved_products": sorted(values & resolved)} for gene, values in sorted(products.items())]
    expected_coverage = read_json(folder / "gene_coverage.json")
    reconciled = bool(resolved) and all(
        family in families and families[family]["target_statuses"] == {"complete": len(resolved)}
        for family, limit in plan["limits"].items() if limit)
    if ([{**row, "requested_products": sorted(row["requested_products"])} for row in expected_coverage] != gene_coverage or
            dict(statuses) != saved["resolution_statuses"] or families != saved["families"] or
            saved["requested_accessions"] != len(ids) or saved["original_gene_count"] != len(products) or
            saved["genes_with_resolved_context"] != sum(bool(row["resolved_products"]) for row in gene_coverage) or
            saved["completed_chunks"] != len(names) or saved["db_versions"] != [source["db_version"]] or
            saved["successful_source_envelopes"] != response_count or saved["cached_source_envelopes"] != cached_response_count or
            saved["all_requested_families_count_reconciled"] != reconciled):
        raise ValueError("Saved coverage summary does not reproduce from its chunks and inventory.")
    for family, observed in [("ppis", total_ppi), ("go", {view: row["rows"] for view, row in go.items()})]:
        expected = families.get(family, {"retrieved": 0, "retained": 0})
        if observed.get("raw", 0) != expected["retrieved"] or observed.get("retained", 0) != expected["retained"]:
            raise ValueError("Annotation rows do not reproduce the saved coverage counts.")
    for candidate in candidates:
        candidate["genes_without_resolved_pharos_context"] = [gene for gene in sorted(set(candidate["original_genes"]))
                                                             if not products[gene] & resolved]
    match_summary = {}
    for view, rows in matches.items():
        match_summary[view] = {"source_views_scanned": total_ppi[view], "matching_source_views": len(rows),
                              "matching_unordered_product_pairs": len({tuple(row["unordered_product_pair"]) for row in rows}),
                              "original_candidate_pairs_matched": len({cid for row in rows for cid in row["candidate_ids"]}),
                              "matching_views_by_provider": dict(Counter(p for row in rows for p in (row["providers"] or ["<missing>"])))}
    overlaps = {"format": "biograph-steward.pharos-pair-mask-inventory.v1", "candidate_pairs": candidates,
                "equivalent_product_pairs": [{"products": list(pair), "candidate_ids": sorted(cids)}
                                             for pair, cids in sorted(equivalents.items())],
                "matches": matches, "blocked_publication_mentions": mentions,
                "policy": "Mask all original candidate pairs and every mapped unordered product equivalent, regardless of assay outcome or context availability. This inventory performs no graph masking."}
    report = {"format": "biograph-steward.pharos-inventory-audit.v1", "created_at": utcnow(),
              "archive_sha256": ARCHIVE_SHA256, "panel_member": PANEL_MEMBER, "panel_member_sha256": member_hash,
              "retrieval_plan_sha256": plan["content_sha256"], "retrieval_summary_sha256": saved["content_sha256"],
              "inventory_sha256": plan["inventory_sha256"], "db_version": source["db_version"],
              "counts": {"original_candidate_rows": len(pairs), "original_unordered_candidate_pairs": len(candidates),
                         "original_self_pairs": sum(row["self_pair"] for row in candidates),
                         "equivalent_unordered_product_pairs": len(equivalents),
                         "self_equivalent_product_pairs": sum(a == b for a, b in equivalents),
                         "original_pairs_without_mapped_context": sum(bool(row["missing_mapped_context_genes"]) for row in candidates),
                         "original_pairs_without_resolved_pharos_context": sum(bool(row["genes_without_resolved_pharos_context"]) for row in candidates),
                         "original_gene_count": len(products), "requested_accessions": len(ids), "resolved_accessions": len(resolved)},
              "coverage": {"resolution_statuses": dict(statuses), "families": families,
                           "all_requested_families_count_reconciled": saved["all_requested_families_count_reconciled"]},
              "ppi_overlap": match_summary, "go_field_observations": go,
              "blocked_publication_diagnostic": {"pattern": BLOCKED_PMID.pattern, "pmid": "36949045",
                                                "matching_response_envelopes": len(mentions), "string_matches": sum(row["matches"] for row in mentions)},
              "exposure": {"only_pair_identity_fields_decoded": True, "outcome_values_decoded": False,
                           "author_positive_pairs_opened": False, "labels_or_features_generated": False,
                           "candidate_pairs_excluded": False, "model_requests": 0},
              "limitations": ["Direct pair matches identify exclusion candidates, not independent source experiments or assay labels.",
                              "Many-to-many products and shared entries preserve identity uncertainty; assayed constructs remain unresolved.",
                              "Provider counts overlap and are not counts of independent supporting studies.",
                              "A missing PMID string does not establish source independence; upstream HuRI/STRING and other derivative lineage still needs review.",
                              "GO field availability describes retrieved API rows only; absent reference/negation fields do not establish absent references or positive annotation polarity.",
                              "Coverage and overlap do not establish scientific accuracy, added value, or permission to train."],
              "input_files": {name: file_sha(folder / name) for name in ["plan.json", "source.json", "summary.json", "context_targets.json", "gene_coverage.json"]},
              "chunk_files": saved["files"], "retrieval_code_sha256": plan["code_sha256"],
              "audit_code_sha256": {str(path.relative_to(ROOT)): file_sha(path) for path in
                                    [Path(__file__), ROOT / "scripts/audit_inmc_inputs.py", ROOT / "scripts/retrieve_pharos_inventory.py"]},
              "overlaps_sha256": digest(overlaps)}
    return seal(report), overlaps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("Choose a new output directory.")
    report, overlaps = audit(args.retrieval_dir, args.archive)
    out = new_output(args.output_dir, args.retrieval_dir, args.archive)
    write_json(out / "report.json", report)
    write_json(out / "overlaps.json", overlaps)
    print(json.dumps({key: report[key] for key in ["counts", "ppi_overlap", "blocked_publication_diagnostic"]}, indent=2))


if __name__ == "__main__":
    main()
