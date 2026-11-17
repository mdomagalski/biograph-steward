"""Bind author matrix order to native DepMap Entrez headers without outcomes.

The author load_screens.py strips text after the first space from gene_effect.csv
column labels. This gate requires the entire stripped order to match genes.txt,
then uses the original parenthesized Entrez IDs. No aliases are guessed and no
essentiality observations, matrix values or significance labels are opened.
"""
from collections import Counter, defaultdict
import argparse
import csv
from io import StringIO
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.cohort_mapping import load_registry
from biograph_steward.file_utils import sha, new_output
from biograph_steward.human_gene_relation import gene_relationship
from tools.reference_accuracy.design import need, write_jsonl

FORMAT = "biograph-steward.coessentiality-identifier-gate.v1"


def native_order(genes_text, csv_header):
    names = genes_text.splitlines()
    need(names and all(names) and len(set(names)) == len(names), "matrix gene order is empty or repeated.")
    records = list(csv.reader(StringIO(csv_header)))
    need(len(records) == 1 and records[0][0] == "Broad_ID", "supply only the native DepMap CSV header, no assay rows.")
    parsed = []
    for field in records[0][1:]:
        match = re.fullmatch(r"([^ ]+) \(([1-9][0-9]*)\)", field)
        need(match is not None, "native gene header lacks an exact symbol and Entrez identifier.")
        parsed.append(match.groups())
    need(names == [symbol for symbol, gene in parsed], "author matrix order differs from the complete native header order.")
    return [{"matrix_index": i, "native_symbol": symbol, "native_ncbi_gene_id": gene,
             "native_header_field": records[0][i + 1]} for i, (symbol, gene) in enumerate(parsed)]


def map_targets(targets, registry, order):
    native = defaultdict(list)
    for row in order:
        native[row["native_ncbi_gene_id"]].append(row)
    need(len({row["uniprot"] for row in targets}) == len(targets), "primary protein targets repeat.")
    rows = []
    for target in targets:
        subject = "UniProtKB:" + target["uniprot"]
        bridge = gene_relationship(subject, registry)
        candidates = native.get(bridge["ncbi_gene_id"], []) if bridge["qualified"] else []
        eligible = bridge["qualified"] and len(candidates) == 1
        rows.append({"subject": subject, "source_target_symbol": target.get("sym"), "gene_product_relation": bridge,
            "native_matrix_gene": candidates[0] if eligible else None,
            "matrix_eligibility": "exact_native_Entrez_ID" if eligible else "UNKNOWN_missing_or_ambiguous_native_ID",
            "current_HGNC_symbol": registry.genes[bridge["hgnc_id"]]["symbol"] if bridge["qualified"] else None,
            "native_symbol_alias_matching_performed": False, "gene_protein_identity_claimed": False})
    return rows


def inspect(packet, registry, genes, header, output, *, registry_sha256, genes_sha256, header_sha256):
    packet, registry, genes, header = map(lambda p: Path(p).absolute(), (packet, registry, genes, header))
    need(all(p.is_file() and not p.is_symlink() for p in (genes, header))
         and sha(genes) == genes_sha256 and sha(header) == header_sha256, "identifier/header source pins differ.")
    manifest, graph = gold_packet.load_packet(packet)
    registry_manifest, mapping = load_registry(registry)
    need(registry_manifest["registry_sha256"] == registry_sha256, "official human registry content pin differs.")
    snapshot = gold_packet._read(packet / "source/snapshot.json")
    order = native_order(genes.read_text(), header.read_text())
    rows = map_targets(snapshot["targets"], mapping, order)
    genes_all = {row["gene_product_relation"]["ncbi_gene_id"] for row in rows if row["gene_product_relation"]["qualified"]}
    genes_eligible = {row["gene_product_relation"]["ncbi_gene_id"] for row in rows if row["native_matrix_gene"] is not None}
    pins = {str(genes): genes_sha256, str(header): header_sha256,
        str(packet / "packet_manifest.json"): sha(packet / "packet_manifest.json"),
        **{str(packet / name): pin for name, pin in manifest["files"].items()},
        str(registry / "manifest.json"): sha(registry / "manifest.json"),
        **{str(registry / name): pin for name, pin in registry_manifest["files"].items()}}
    code = sha(__file__)
    out = new_output(output, packet, registry, genes, header)
    write_jsonl(out / "native_matrix_order.jsonl", order)
    write_jsonl(out / "primary_target_mapping.jsonl", rows)
    need(all(sha(path) == pin for path, pin in pins.items()) and sha(__file__) == code,
         "source or implementation changed during outcome-free mapping.")
    report = {"format": FORMAT, "created_at": utcnow(), "packet_id": manifest["packet_id"],
        "graph_sha256": manifest["graph_sha256"], "registry_sha256": registry_sha256,
        "matrix_gene_count": len(order), "primary_proteins": len(rows), "primary_unique_genes": len(genes_all),
        "native_eligible_unique_genes": len(genes_eligible), "missing_or_ambiguous_gene_ids": sorted(genes_all - genes_eligible),
        "eligible_unique_nonself_gene_pairs": len(genes_eligible) * (len(genes_eligible) - 1) // 2,
        "all_author_names_match_native_header_order": True, "native_historical_geneID_bridge_not_symbol_guess": True,
        "matrix_values_opened": False, "essentiality_observation_rows_opened": False,
        "scientific_truth_or_prediction_benefit_assessed": False, "source_graph_changed": False,
        "input_files_sha256": pins, "implementation_sha256": code,
        "limitations": ["Eligibility is experimental-platform coverage, not a biological truth label.",
            "Missing genes remain unknown; gene-to-protein links are relationships, not identity.",
            "Only the CSV header was captured; its full 175MB file checksum has not been independently verified.",
            "No numerical coessentiality values are read here; source/control/task contracts must precede that step."],
        "files": {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    report["content_sha256"] = digest(report); write_json(out / "report.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("packet", "registry", "genes", "header", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    for key in ("registry-sha256", "genes-sha256", "header-sha256"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    print(inspect(a.packet, a.registry, a.genes, a.header, a.out, registry_sha256=a.registry_sha256,
        genes_sha256=a.genes_sha256, header_sha256=a.header_sha256)["content_sha256"])


if __name__ == "__main__":
    main()
