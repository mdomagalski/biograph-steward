#!/usr/bin/env python3
"""Outcome-blind GOA source/qualification inventory using Biopython's GAF parser.

This stages original annotation records, not prediction features. Projection
matches to Pharos are compatibility groups, never proof of record identity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from biograph_steward.client import digest
from audit_pharos_inventory import verified_header, verified_chunk

BLOCKED_REFERENCE = "PMID:36949045"
EXTENSION_IDENTIFIER = re.compile(r"([A-Za-z][A-Za-z0-9_.-]*):([^(),|\s]+)")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_rows(path):
    """Validate the column boundary; interpretation belongs to Bio.UniProt.GOA."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.startswith("!"):
                continue
            raw = line.rstrip("\r\n")
            if not raw:
                continue
            fields = raw.split("\t")
            if len(fields) != 17:
                raise ValueError(f"GAF row {number} has {len(fields)} fields; expected 17.")
            yield number, raw, fields


def projection_key(accession, go_id, evidence, assigned_by):
    return (accession, go_id, evidence or "", assigned_by or "")


def stage_record(number, raw, fields, parsed, accessions):
    # The first taxon identifies the annotated subject; a second can identify
    # the interacting taxon. Isoform suffixes must not be silently removed.
    if fields[0] != "UniProtKB" or fields[1] not in accessions:
        return None
    if fields[12].split("|")[0] != "taxon:9606":
        return None
    qualifiers = parsed["Qualifier"]
    references = parsed["DB:Reference"]
    with_from_ids = [x for x in re.split(r"[|,]", fields[7]) if x]
    extension_ids = sorted({f"{namespace}:{value}" for namespace, value in
                            EXTENSION_IDENTIFIER.findall(fields[15])})
    extension_inventory = [x for x in extension_ids if x.startswith("UniProtKB:")
                           and x.removeprefix("UniProtKB:") in accessions]
    return {
        "source_line": number, "raw_line": raw, "raw_fields": fields,
        "parsed": parsed,
        "projection_key": list(projection_key(fields[1], fields[4], fields[6], fields[14])),
        "negated": "NOT" in qualifiers,
        "blocked_reference_present": BLOCKED_REFERENCE in references,
        "with_from_inventory_ids": sorted({x for x in with_from_ids
            if x.startswith("UniProtKB:") and x.removeprefix("UniProtKB:") in accessions}),
        "annotation_extension_present": bool(fields[15]),
        "extension_inventory_ids": extension_inventory,
        "extension_unresolved_identifiers": sorted(set(extension_ids) - set(extension_inventory)),
        "extension_identifier_scan_is_semantic_validation": False,
        "product_form_present": bool(fields[16]),
        "record_identity_with_pharos_established": False,
        "feature_use_approved": False,
    }


def load_pair_mask(path, inventory_sha256, accessions, retrieval_receipt):
    """Read only an already audited identity mask and its binding receipt."""
    if retrieval_receipt is None:
        raise ValueError("A pair mask requires the same completed Pharos retrieval for verification.")
    path = Path(path)
    report_path = path.with_name("report.json")
    report = json.loads(report_path.read_text())
    if report.get("format") != "biograph-steward.pharos-inventory-audit.v1":
        raise ValueError("Expected the Pharos inventory audit report beside the mask.")
    if report.get("content_sha256") != digest({k: v for k, v in report.items() if k != "content_sha256"}):
        raise ValueError("Pair-mask report digest mismatch.")
    if report.get("inventory_sha256") != inventory_sha256:
        raise ValueError("Pair mask uses a different accession inventory.")
    for key in ("retrieval_plan_sha256", "retrieval_summary_sha256", "db_version"):
        if report.get(key) != retrieval_receipt[key]:
            raise ValueError(f"Pair mask belongs to a different retrieval: {key}.")
    if (report.get("input_files") != retrieval_receipt["input_files"] or
            report.get("chunk_files") != retrieval_receipt["chunk_files"]):
        raise ValueError("Pair mask refers to different saved retrieval files.")
    value = json.loads(path.read_text())
    if value.get("format") != "biograph-steward.pharos-pair-mask-inventory.v1":
        raise ValueError("Expected the audited pair-mask inventory.")
    if report.get("overlaps_sha256") != digest(value):
        raise ValueError("Pair mask differs from its sealed report.")
    pairs = {}
    for row in value["equivalent_product_pairs"]:
        products = row["products"]
        if len(products) != 2 or any(p not in accessions for p in products):
            raise ValueError("Mask contains a product outside the accession inventory.")
        key = tuple(sorted(products))
        if key in pairs or not row["candidate_ids"]:
            raise ValueError("Mask contains duplicate pairs or missing candidate identifiers.")
        pairs[key] = sorted(set(row["candidate_ids"]))
    return pairs, {"path": str(path), "file_sha256": sha(path),
                   "report_sha256": sha(report_path), "report_content_sha256": report["content_sha256"],
                   "retrieval_plan_sha256": report["retrieval_plan_sha256"],
                   "retrieval_summary_sha256": report["retrieval_summary_sha256"],
                   "db_version": report["db_version"],
                   "unordered_product_pairs": len(pairs)}


def exposure_diagnostics(row, pairs):
    """Literal identifier candidates only; preserve logical groups in raw fields."""
    focal = row["raw_fields"][1]
    result = {}
    for label, field in [("with_from", "with_from_inventory_ids"),
                         ("extension", "extension_inventory_ids")]:
        hits = []
        for identifier in row[field]:
            partner = identifier.removeprefix("UniProtKB:")
            pair = tuple(sorted((focal, partner)))
            if pair in pairs:
                hits.append({"referenced_identifier": identifier, "unordered_product_pair": list(pair),
                             "candidate_ids": pairs[pair]})
        result[label] = hits
    return result


def pharos_groups(paths, inventory_sha256, accessions):
    """Use a complete, single retrieval bound to the exact GO audit inventory."""
    groups, targets, receipts = Counter(), set(), {}
    paths = [Path(path).absolute() for path in paths]
    if not paths:
        return groups, targets, receipts, None
    folders = {path.parent for path in paths}
    if len(folders) != 1 or paths[0].parent.name != "chunks":
        raise ValueError("Pharos chunks must belong to one completed retrieval directory.")
    folder = paths[0].parent.parent
    plan, source, summary, _, ids, names = verified_header(folder)
    if plan["inventory_sha256"] != inventory_sha256 or set(ids) != accessions:
        raise ValueError("Pharos retrieval uses a different accession inventory.")
    expected_paths = {folder / name for name in names}
    if len(paths) != len(expected_paths) or set(paths) != expected_paths:
        raise ValueError("Supply exactly the completed retrieval's manifest chunks.")
    if summary.get("db_versions") != [source["db_version"]]:
        raise ValueError("Pharos retrieval summary contains different source versions.")
    for number, name in enumerate(names):
        path = folder / name
        expected_ids = ids[number * plan["chunk_size"]:(number + 1) * plan["chunk_size"]]
        value = verified_chunk(folder, name, plan, source, summary, expected_ids)
        if value.get("format") != "biograph-steward.pharos-inventory-chunk.v1":
            raise ValueError("Expected a completed Pharos inventory chunk.")
        for target in value["targets"]:
            accession = target["uniprot"]
            if accession in targets:
                raise ValueError("Repeated accession across Pharos chunks.")
            targets.add(accession)
            for row in target.get("pharos_context", {}).get("go", []):
                groups[projection_key(accession, row["goid"], row.get("evidence"), row.get("assigned_by"))] += 1
        receipts[str(path)] = sha(path)
    retrieval_receipt = {
        "path": str(folder), "retrieval_plan_sha256": plan["content_sha256"],
        "retrieval_summary_sha256": summary["content_sha256"],
        "inventory_sha256": plan["inventory_sha256"], "db_version": source["db_version"],
        "input_files": {name: sha(folder / name) for name in
                  ("plan.json", "source.json", "summary.json", "context_targets.json", "gene_coverage.json")},
        "chunk_files": summary["files"],
    }
    return groups, targets, receipts, retrieval_receipt


def group_comparison(staged, pharos):
    goa = Counter(tuple(row["projection_key"]) for row in staged)
    counts = Counter()
    for key in goa.keys() | pharos.keys():
        a, b = goa[key], pharos.get(key, 0)
        status = ("goa_only_projection" if not b else "pharos_only_projection" if not a else
                  "one_to_one_projection" if a == b == 1 else "multiple_records_projection")
        counts[status] += 1
    return dict(counts)


def group_details(staged, pharos, pair_mask_evaluated=False):
    """Qualification counts by compatible projection, not historical identity."""
    goa = Counter(tuple(row["projection_key"]) for row in staged)
    details, status_by_key = {}, {}
    for key in goa.keys() | pharos.keys():
        a, b = goa[key], pharos.get(key, 0)
        status = ("goa_only_projection" if not b else "pharos_only_projection" if not a else
                  "one_to_one_projection" if a == b == 1 else "multiple_records_projection")
        status_by_key[key] = status
        group = details.setdefault(status, {"groups": 0, "goa_rows": 0, "pharos_rows": 0,
            "negated_goa_rows": 0, "extension_goa_rows": 0, "blocked_reference_goa_rows": 0,
            "with_from_reserved_pair_goa_rows": 0 if pair_mask_evaluated else None,
            "extension_reserved_pair_goa_rows": 0 if pair_mask_evaluated else None})
        group["groups"] += 1
        group["goa_rows"] += a
        group["pharos_rows"] += b
    for row in staged:
        group = details[status_by_key[tuple(row["projection_key"])]]
        group["negated_goa_rows"] += row["negated"]
        group["extension_goa_rows"] += row["annotation_extension_present"]
        group["blocked_reference_goa_rows"] += row["blocked_reference_present"]
        if pair_mask_evaluated:
            for label in ("with_from", "extension"):
                group[label + "_reserved_pair_goa_rows"] += bool(row["reserved_pair_exposure"][label])
    return details


def audit(gaf, inventory_path, output, pharos_paths=(), pair_mask_path=None):
    import Bio
    from Bio.UniProt.GOA import gafiterator
    if Bio.__version__ != "1.88":
        raise ValueError("Use the inspected Biopython 1.88 parser in the isolated audit environment.")
    out = Path(output)
    if out.exists():
        raise ValueError("Use a new audit output to preserve earlier receipts.")
    inventory = json.loads(Path(inventory_path).read_text())
    if inventory.get("format") != "biograph-steward.inmc-context-targets.v1":
        raise ValueError("Expected an audited context inventory, not an outcome table.")
    accessions = {r["uniprot_id"].removeprefix("UniProtKB:") for r in inventory["targets"]}
    if len(accessions) != len(inventory["targets"]):
        raise ValueError("Duplicate accessions in inventory.")
    inventory_sha256 = sha(inventory_path)
    groups, compared_targets, pharos_receipts, retrieval_receipt = pharos_groups(
        pharos_paths, inventory_sha256, accessions)
    pairs, mask_receipt = load_pair_mask(pair_mask_path, inventory_sha256, accessions,
        retrieval_receipt) if pair_mask_path else ({}, None)
    with gzip.open(gaf, "rt", encoding="utf-8") as handle:
        headers = []
        for line in handle:
            if not line.startswith("!"):
                break
            headers.append(line.rstrip("\r\n"))
    if not headers or headers[0] != "!gaf-version: 2.2":
        raise ValueError("This audit requires the inspected GAF 2.2 format.")
    staged, total = [], 0
    with gzip.open(gaf, "rt", encoding="utf-8") as handle:
        for (number, raw, fields), parsed in zip(source_rows(gaf), gafiterator(handle), strict=True):
            total += 1
            row = stage_record(number, raw, fields, parsed, accessions)
            if row is not None:
                row["reserved_pair_exposure"] = exposure_diagnostics(row, pairs) if pair_mask_path else None
                staged.append(row)
    counts = Counter(row["parsed"]["Evidence"] for row in staged)
    references = {ref for row in staged for ref in row["parsed"]["DB:Reference"] if ref}
    covered = {row["raw_fields"][1] for row in staged}
    summary = {
        "format": "biograph-steward.go-qualification-source-audit.v1",
        "inputs": {"gaf_sha256": sha(gaf), "inventory_sha256": sha(inventory_path),
                   "script_sha256": sha(__file__), "pharos_chunks": pharos_receipts,
                   "pharos_retrieval": retrieval_receipt,
                   "provenance_validator_sha256": {str(path.relative_to(ROOT)): sha(path) for path in
                       (ROOT / "scripts/audit_pharos_inventory.py", ROOT / "scripts/retrieve_pharos_inventory.py")}},
        "pair_mask": mask_receipt,
        "parser": {"package": "biopython", "version": Bio.__version__, "function": "Bio.UniProt.GOA.gafiterator"},
        "gaf_headers": headers, "source_rows": total, "inventory_accessions": len(accessions),
        "covered_accessions": len(covered), "uncovered_accessions": sorted(accessions - covered),
        "retained_rows": len(staged), "evidence_counts": dict(sorted(counts.items())),
        "rows_with_reference": sum(bool(r["raw_fields"][5]) for r in staged),
        "distinct_reference_identifiers": len(references),
        "distinct_pmid_identifiers": sum(ref.startswith("PMID:") for ref in references),
        "reference_identifiers_are_independent_studies": False,
        "negated_rows": sum(r["negated"] for r in staged),
        "blocked_reference_rows": sum(r["blocked_reference_present"] for r in staged),
        "with_from_inventory_reference_rows": sum(bool(r["with_from_inventory_ids"]) for r in staged),
        "annotation_extension_rows": sum(r["annotation_extension_present"] for r in staged),
        "extension_inventory_reference_rows": sum(bool(r["extension_inventory_ids"]) for r in staged),
        "extension_unresolved_identifier_rows": sum(bool(r["extension_unresolved_identifiers"]) for r in staged),
        "extension_raw_but_no_identifier_detected_rows": sum(r["annotation_extension_present"] and
            not (r["extension_inventory_ids"] or r["extension_unresolved_identifiers"]) for r in staged),
        "product_form_rows": sum(r["product_form_present"] for r in staged),
        "pharos_compared_accessions": len(compared_targets),
        "projection_group_comparison": group_comparison(
            [r for r in staged if r["raw_fields"][1] in compared_targets], groups) if pharos_paths else None,
        "projection_group_details": group_details(
            [r for r in staged if r["raw_fields"][1] in compared_targets], groups,
            bool(pair_mask_path)) if pharos_paths else None,
        "projection_match_is_record_identity": False, "outcome_values_loaded": False,
        "pair_overlap_evaluated": bool(pair_mask_path), "feature_use_approved": False,
        "pair_exposure_counts": ({label + "_rows": sum(bool(r["reserved_pair_exposure"][label]) for r in staged)
                                  for label in ("with_from", "extension")} if pair_mask_path else None),
        "extension_scan_complete_semantic_mask": False,
        "scientific_improvement_measured": False,
        "interpretation": (
            "Source-only records may reflect release or filter changes; uniqueness of a projected tuple does not establish historical record identity. "
            "Generic With/From inventory flags indicate potential context exposure. "
            + ("Reserved-pair diagnostics identify exact literal accession matches to the audited unordered product equivalents of reserved candidate pairs; they do not establish annotation semantics, study independence or a complete leakage mask."
               if pair_mask_path else
               "Reserved-pair overlap was not evaluated; generic flags are not identified reserved-pair matches.")),
    }
    out.mkdir(parents=True)
    with (out / "staged_annotations.jsonl").open("w") as handle:
        for row in staged:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary["staged_annotations_sha256"] = sha(out / "staged_annotations.jsonl")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gaf", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pharos-chunks", type=Path,
                        help="The chunks directory of one completed, inventory-bound retrieval.")
    parser.add_argument("--pair-mask", type=Path,
                        help="Audited overlaps.json and sealed report.json for that same --pharos-chunks retrieval; no outcome file.")
    args = parser.parse_args()
    paths = sorted(args.pharos_chunks.glob("*.json")) if args.pharos_chunks else []
    if args.pharos_chunks and not paths:
        parser.error("The requested Pharos chunk directory contains no JSON chunks.")
    result = audit(args.gaf, args.inventory, args.output, paths, args.pair_mask)
    print(json.dumps({k: result[k] for k in ["retained_rows", "covered_accessions", "negated_rows", "blocked_reference_rows", "pharos_compared_accessions"]}, indent=2))
