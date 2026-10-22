#!/usr/bin/env python3
"""Inspect archived INMC identifiers and schema without deriving outcome labels.

Reuse the existing frozen HGNC/UniProt registry. Assay values are processed only
as an unassociated vocabulary; no per-pair assay outcome is returned or scored.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from biograph_steward.cohort_mapping import load_registry


ARCHIVE_SHA256 = "2200fce435e0705470dda73f1dc870e6b6a7b9bee621c8697099dfd38b49ae62"
PANEL_MEMBER = "PPI-Prediction/Experimental validation/PPI_prediction_validation_result_20210624.xls"
TRAIN_MEMBER = "PPI-Prediction/Interactomes/HuRI.csv"
PANEL_HEADER = b"source\ttarget\tfreq\tscore_assay1\tscore_assay2\tscore_assay3"
GENE_ID = re.compile(r"ENSG[0-9]{11}\Z")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identifier_pairs(raw: bytes, *, panel: bool) -> list[tuple[str, str]]:
    """Read only the first two fields; never decode the panel's outcome fields."""
    lines = raw.splitlines()
    header = PANEL_HEADER if panel else b"source,target"
    if not lines or lines[0] != header:
        raise ValueError("Unexpected source header")
    separator = b"\t" if panel else b","
    pairs = []
    for number, line in enumerate(lines[1:], 2):
        cells = line.split(separator)
        if len(cells) != (6 if panel else 2):
            raise ValueError(f"Unexpected source width at row {number}")
        a, b = (cell.decode("ascii") for cell in cells[:2])
        if not GENE_ID.fullmatch(a) or not GENE_ID.fullmatch(b):
            raise ValueError(f"Unexpected gene identifier at row {number}")
        pairs.append((a, b))
    if not pairs:
        raise ValueError("Empty source")
    return pairs


def schema_vocabulary(raw: bytes) -> dict:
    """Inspect codes without exposing their pairing with source identities."""
    identifier_pairs(raw, panel=True)
    fields = PANEL_HEADER.decode().split("\t")
    values = [set() for _ in fields]
    for line in raw.splitlines()[1:]:
        cells = line.split(b"\t")
        for index in range(2, len(fields)):
            values[index].add(cells[index].decode("utf-8"))
    return {fields[index]: sorted(values[index]) for index in range(2, len(fields))}


def map_identifiers(identifiers: set[str], registry) -> list[dict]:
    """Exact declared Ensembl cross-references; no guessed replacements."""
    index = defaultdict(list)
    for gid, gene in registry.genes.items():
        if gene["status"] == "Approved" and gene["ensembl_gene_id"]:
            index[gene["ensembl_gene_id"]].append(gid)
    mappings = []
    for identifier in sorted(identifiers):
        gids = sorted(index.get(identifier, []))
        products = registry.products(gids[0]) if len(gids) == 1 else []
        usable = [product["uniprot_id"] for product in products
                  if product["status"] == "reviewed_human_hgnc_match"
                  and product["shared_across_genes"] is False]
        mappings.append({
            "ensembl_gene_id": identifier,
            "hgnc_ids": gids,
            "gene_status": "unique" if len(gids) == 1 else "unresolved" if not gids else "ambiguous",
            "protein_candidates": products,
            "unshared_reviewed_products": usable,
            "product_status": "unique" if len(usable) == 1 else "none" if not usable else "multiple",
            "assay_isoform_assignment_established": False,
        })
    return mappings


def audit(archive: Path, registry_path: Path) -> tuple[dict, list[dict]]:
    archive_raw = archive.read_bytes()
    if sha256(archive_raw) != ARCHIVE_SHA256:
        raise ValueError("Archive differs from the checked Zenodo release")
    with zipfile.ZipFile(BytesIO(archive_raw)) as source:
        panel_raw, train_raw = (source.read(member) for member in (PANEL_MEMBER, TRAIN_MEMBER))
    panel = identifier_pairs(panel_raw, panel=True)
    training = identifier_pairs(train_raw, panel=False)
    registry_manifest, registry = load_registry(registry_path)
    entities = {value for pair in panel for value in pair}
    training_entities = {value for pair in training for value in pair}
    panel_pairs = {tuple(sorted(pair)) for pair in panel}
    training_pairs = {tuple(sorted(pair)) for pair in training}
    mappings = map_identifiers(entities, registry)
    by_id = {row["ensembl_gene_id"]: row for row in mappings}
    off_diagonal = {pair for pair in panel_pairs if pair[0] != pair[1]}
    report = {
        "format": "biograph-steward.inmc-input-audit.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "script_sha256": sha256(Path(__file__).read_bytes()),
        "archive_sha256": ARCHIVE_SHA256,
        "source_member_sha256": {PANEL_MEMBER: sha256(panel_raw), TRAIN_MEMBER: sha256(train_raw)},
        "registry_sha256": registry_manifest["registry_sha256"],
        "registry_sources": registry_manifest["sources"],
        "schema": {"actual_format": "tsv_despite_xls_suffix", "vocabularies": schema_vocabulary(panel_raw)},
        "counts": {
            "panel_rows": len(panel),
            "panel_unique_unordered_pairs": len(panel_pairs),
            "panel_duplicate_or_reverse_rows": len(panel) - len(panel_pairs),
            "panel_self_pairs": len(panel_pairs) - len(off_diagonal),
            "panel_off_diagonal_pairs": len(off_diagonal),
            "panel_genes": len(entities),
            "training_rows": len(training),
            "training_unique_unordered_pairs": len(training_pairs),
            "training_genes": len(training_entities),
            "panel_genes_in_training": len(entities & training_entities),
            "panel_pairs_in_training": len(panel_pairs & training_pairs),
            "gene_mapping_status": dict(Counter(row["gene_status"] for row in mappings)),
            "product_mapping_status": dict(Counter(row["product_status"] for row in mappings)),
            "off_diagonal_pairs_both_exact_unique_gene_mapping": sum(
                all(by_id[value]["gene_status"] == "unique" for value in pair) for pair in off_diagonal),
            "off_diagonal_pairs_both_single_unshared_reviewed_product": sum(
                all(by_id[value]["gene_status"] == "unique" and by_id[value]["product_status"] == "unique"
                    for value in pair) for pair in off_diagonal),
        },
        "exposure": {"outcome_codes_processed_for_vocabulary": True,
                     "individual_outcomes_displayed": False, "binary_labels_derived": False,
                     "predictions_generated": False, "final_cohort_selected": False},
        "limitations": ["Gene-level source identifiers do not specify assay isoforms.",
                        "Coverage counts are feasibility diagnostics, not eligibility or performance.",
                        "Assay semantics and Pharos source overlap require separate investigation."],
    }
    return report, mappings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("Output directory already exists")
    report, mappings = audit(args.archive, args.registry)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, data in (("report.json", report), ("identifier_mappings.json", mappings)):
        with (args.output_dir / name).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    print(json.dumps(report["counts"], indent=2))


if __name__ == "__main__":
    main()
