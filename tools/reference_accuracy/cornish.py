"""Published CRC cohort genomic support, separate from expert gold and features.

This study-specific adapter reads the authors' unchanged core ST4 with the
existing openpyxl reader. Calls, cohorts, cell values and prior assistance are
preserved. Missing calls and mismatched source contexts are UNKNOWN; no gene is
declared nonassociated and no protein mechanism or driver tier is invented.
"""
from collections import Counter
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import shutil
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.cohort_mapping import load_registry
from biograph_steward.file_utils import sha, new_output
from biograph_steward.human_gene_relation import gene_relationship
from tools.reference_accuracy.design import need, read_rows, write_jsonl

FORMAT = "biograph-steward.Cornish2024-CRC-cohort-reference.v1"
AXIS = "published_CRC_cohort_genomic_association_support"
DOI, PMID, PMCID = "10.1038/s41586-024-07747-9", "39112709", "PMC11374690"
SHEET = "ST4. 193 SNV drivers annotated"
MEMBER = "41586_2024_7747_MOESM4_ESM.xlsx"
COHORTS = {"PRIMARY_MSS": (27, 28, 29), "PRIMARY_MSI": (30, 31, 32),
           "PRIMARY_POL": (33, 34, 35), "METASTASES_MSS": (36, 37, 38)}
DISEASE = "MONDO:0005008"
SOURCE_NAME = "colorectal adenocarcinoma"
POLICY = {"native_core_table_only": SHEET, "native_driver_rows": 193,
    "source_disease_id": DISEASE, "source_disease_name_literal": SOURCE_NAME,
    "all_original_supporting_records_require_exact_disease_scope": True,
    "exact_approved_HGNC_symbol_only": True, "gene_protein_identity_inferred": False,
    "author_call_is_positive_cohort_context_not_expert_gold": True,
    "qvalue_threshold_or_tier_invented": False, "missing_or_subtype_mismatch_is_UNKNOWN": True,
    "learner_features_or_source_graph_changed": False}
LIMITATIONS = [
    "The reference is an author-reported statistical putative-driver call in a specified CRC cohort, not expert gold or biological truth.",
    "IntOGen 2020 ensemble weights use CGC v92 enrichment; CGC-rescued candidates exist. New specimens do not imply independence from cancer-gene priors.",
    "There are 2,023 specimens from 2,017 participants; six people have primary and metastasis samples. Cohort calls are not independent experiment counts.",
    "Original Pharos rows omit primary-study lineage; independence from every original association is unestablished.",
    "Only 193 core coding-driver calls are assessed; anatomical-location-only, noncoding, SV and cluster-specific extensions are outside this scope.",
    "Native driver tiers are not supplied in ST4; Q values are preserved without inventing Tier 1 or changing author thresholds.",
    "Reviewed current gene-to-protein relationships are not identity, historical identifier attestation, protein-form specificity or causal protein mechanisms.",
    "Missing native calls and source disease-context mismatches are UNKNOWN, never biological negatives.",
    "Positive-only support coverage and its preservation do not establish scientific precision, false-removal rates or prediction benefit.",
    "This reference is reserved from app graph/learner features; its inspected outcomes are not an unseen confirmatory holdout.",
]


def read_native_study(archive, expected_sha256):
    """Use the maintained workbook reader, preserving formulas and native cells."""
    archive = Path(archive)
    need(archive.is_file() and not archive.is_symlink() and sha(archive) == expected_sha256,
         "Cornish native archive bytes differ.")
    try:
        import openpyxl
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise ValueError("Cornish native workbook replay requires optional openpyxl==3.1.5.") from exc
    need(openpyxl.__version__ == "3.1.5", "use the inspected openpyxl==3.1.5 reader.")
    with ZipFile(archive) as z:
        members = [info for info in z.infolist() if info.filename == MEMBER]
        need(len(members) == 1 and members[0].file_size <= 25_000_000, "Cornish native workbook member differs.")
        raw = z.read(members[0])
    book = openpyxl.load_workbook(BytesIO(raw), read_only=True, data_only=False)
    try:
        sheet = book[SHEET]
        need(sheet.max_row == 201 and sheet.max_column == 115, "Cornish inspected worksheet dimensions differ.")
        headers = {str(i): list(next(sheet.iter_rows(min_row=i, max_row=i, values_only=True)))
                   for i in (1, 2, 3, 4, 6, 7, 8)}
        need(headers["6"][0] == "Gene" and headers["8"][27:29] == ["Stouffer Q-value", "Stouffer Q-value CGC"],
             "Cornish native column semantics differ.")
        rows = []
        for number, values in enumerate(sheet.iter_rows(min_row=9, max_row=201, values_only=True), 9):
            need(isinstance(values[0], str) and values[0] and isinstance(values[2], str), "Cornish native gene/cohort is missing.")
            cohorts = values[2].split(";")
            need(len(cohorts) == len(set(cohorts)) and set(cohorts) <= set(COHORTS), "Cornish native cohort vocabulary differs.")
            statistics = {cohort: [{"cell": get_column_letter(col) + str(number), "value": values[col - 1]}
                                  for col in COHORTS[cohort]] for cohort in cohorts}
            rows.append({"native_sheet": SHEET, "native_row": number, "gene_cell": "A" + str(number),
                "native_gene_symbol": values[0], "native_cohorts_literal": values[2], "native_cohort_calls": cohorts,
                "native_statistics": statistics, "prior_CRC_driver_any_study_literal": values[3],
                "all_native_row_values": list(values), "native_row_values_sha256": digest(list(values)),
                "native_tier_not_reported_in_table": True, "gene_role_not_extrapolated": True})
        need(len(rows) == len({row["native_gene_symbol"] for row in rows}) == 193, "Cornish native gene rows differ.")
    finally:
        book.close()
    need(sha(archive) == expected_sha256, "Cornish archive changed during native parsing.")
    return rows, {"reader": {"package": "openpyxl", "version": openpyxl.__version__, "data_only": False},
        "archive_member": MEMBER, "workbook_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "header_rows": headers, "native_rows": 193}


def classify(graph, native_rows, registry):
    by_symbol = {row["native_gene_symbol"]: row for row in native_rows}
    need(len(by_symbol) == len(native_rows), "Cornish native gene symbols repeat.")
    edges = {edge["id"]: edge for edge in graph["edges"]}
    labels = []
    for a in sorted(graph["assertions"], key=lambda value: value["id"]):
        bridge = gene_relationship(a["subject"], registry) if a["kind"] == "disease_association" else None
        gene = registry.genes[bridge["hgnc_id"]] if bridge and bridge["qualified"] else None
        exact_symbol = gene and registry.primary[gene["symbol"]] == {bridge["hgnc_id"]}
        record = by_symbol.get(gene["symbol"]) if exact_symbol else None
        source_edges = [edges[e] for e in a["evidence_edge_ids"]]
        scopes = [{"edge_id": e["id"], "name": e.get("evidence_record", {}).get("name"),
                   "subject": e["subject"], "object": e["object"]} for e in source_edges]
        context = (a["kind"] == "disease_association" and a["predicate"] == "biolink:associated_with"
            and a["object"] == DISEASE and a["qualifiers"].get("disease") == DISEASE and bool(source_edges)
            and all(e.get("record_kind") == "disease_association" and e["subject"] == a["subject"]
                    and e["object"] == DISEASE and e.get("evidence_record", {}).get("name") == SOURCE_NAME
                    for e in source_edges))
        eligible = bool(context and record is not None)
        labels.append({"assertion_id": a["id"], "assertion_sha256": digest(a), "family": a["kind"],
            "axis": AXIS, "verdict": "agree" if eligible else "unknown", "evidence_edge_ids": list(a["evidence_edge_ids"]),
            "original_source_disease_scopes": scopes if a["kind"] == "disease_association" else [],
            "exact_original_source_context_eligible": bool(context), "current_gene_product_relation": bridge,
            "native_approved_HGNC_symbol": gene["symbol"] if gene else None,
            "matched_native_row": record if eligible else None,
            "broader_cohort_diagnostic_row": record if record is not None and not context else None,
            "reason": "published_primary_cohort_genomic_association_context" if eligible else
                      "reference_does_not_cover_this_family" if a["kind"] != "disease_association" else
                      "source_disease_scope_not_exact" if not context else "no_exact_native_core_driver_call_or_gene_relation",
            "independent_scientific_correctness": "unreviewed", "native_call_absence_is_negative": False})
    return labels


def inspect_article(path, expected_sha256):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and sha(path) == expected_sha256, "Cornish article pin differs.")
    root = ET.fromstring(path.read_bytes())
    ids = {el.get("pub-id-type"): el.text for el in root.findall(".//article-id")}
    need(ids.get("doi") == DOI and ids.get("pmid") == PMID
         and any("creativecommons.org/licenses/by/4.0" in v for el in root.iter() for v in el.attrib.values())
         and any(el.get("{http://www.w3.org/1999/xlink}href") == MEMBER for el in root.iter("media")),
         "Cornish primary publication identity, license or supplementary member differs.")
    return {"doi": DOI, "PMID": PMID, "PMCID": PMCID, "license": "CC-BY-4.0",
        "article_source_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/" + PMCID + "/fullTextXML",
        "archive_source_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/" + PMCID + "/supplementaryFiles",
        "specimens": 2023, "distinct_participants": 2017, "primary_specimens": 1898,
        "metastasis_specimens": 122, "recurrence_specimens": 3, "paired_primary_and_metastasis_participants": 6,
        "discovery_population": "UK100000Genomes main programme v8 paired tumour/blood WGS; colorectal adenocarcinoma histology",
        "prior_assistance": "IntOGen2020 downloadedFeb2021; CGCv92-weighted seven-method ensemble, CGC-rescued candidates",
        "prior_TCGA_PCAWG_IntOGen_comparisons_are_not_the_new_UK_discovery_samples": True,
        "independence_from_every_original_Pharos_study_established": False}


def inventory(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and p != folder / "report.json"}


def prepare(packet, archive, article, registry_directory, output, *, archive_sha256, article_sha256, registry_sha256):
    packet, archive, article, registry_directory = map(lambda p: Path(p).absolute(), (packet, archive, article, registry_directory))
    manifest, graph = gold_packet.load_packet(packet)
    study = inspect_article(article, article_sha256)
    registry_manifest, registry = load_registry(registry_directory)
    need(registry_manifest["registry_sha256"] == registry_sha256, "Cornish registry content pin differs.")
    native, reader = read_native_study(archive, archive_sha256)
    labels = classify(graph, native, registry)
    pins = {str(archive): archive_sha256, str(article): article_sha256,
        str(registry_directory / "manifest.json"): sha(registry_directory / "manifest.json"),
        **{str(registry_directory / name): value for name, value in registry_manifest["files"].items()},
        str(packet / "packet_manifest.json"): sha(packet / "packet_manifest.json"),
        **{str(packet / name): value for name, value in manifest["files"].items()}}
    code = sha(__file__)
    out = new_output(output, packet, archive, article, registry_directory)
    (out / "source").mkdir()
    shutil.copyfile(archive, out / "source/supplementary.zip")
    shutil.copyfile(article, out / "source/article.xml")
    shutil.copytree(registry_directory, out / "registry")
    write_jsonl(out / "native_rows.jsonl", native)
    write_jsonl(out / "reference_labels.jsonl", labels)
    need(sha(out / "source/supplementary.zip") == archive_sha256 and sha(out / "source/article.xml") == article_sha256
         and load_registry(out / "registry")[0] == registry_manifest and all(sha(path) == pin for path, pin in pins.items())
         and sha(__file__) == code, "Cornish input/copy or implementation changed during build.")
    report = {"format": FORMAT, "created_at": utcnow(), "packet_id": manifest["packet_id"], "graph_sha256": manifest["graph_sha256"],
        "axis": AXIS, "policy": POLICY, "publication": study, "native_reader": reader,
        "registry_sha256": registry_sha256, "archive_sha256": archive_sha256, "article_sha256": article_sha256,
        "counts": dict(Counter(row["verdict"] for row in labels)),
        "label_producer": "Author-reported putative coding driver in the new UK cohort; not expert gold or project AI.",
        "source_graph_changed": False, "old_audits_changed": False, "reference_labels_added_to_features": False,
        "independent_experimental_replication": False, "scientific_truth_accuracy_measured": False,
        "implementation_sha256": code, "input_files_sha256": pins, "limitations": LIMITATIONS, "files": inventory(out)}
    report["content_sha256"] = digest(report); write_json(out / "report.json", report)
    return report


def load_reference(folder, packet, *, report_sha256):
    folder = Path(folder).absolute()
    need(not any(p.is_symlink() for p in [folder, *folder.rglob("*")]) and sha(folder / "report.json") == report_sha256,
         "Cornish reference directory or explicit report pin differs.")
    report = gold_packet._read(folder / "report.json")
    need(gold_packet._sealed(report) and report.get("format") == FORMAT and report.get("axis") == AXIS
         and report.get("policy") == POLICY and report["files"] == inventory(folder), "Cornish reference seal/policy/inventory differs.")
    need(all(report.get(k) is False for k in ("source_graph_changed", "old_audits_changed", "reference_labels_added_to_features",
         "independent_experimental_replication", "scientific_truth_accuracy_measured")), "Cornish validation reserve scope differs.")
    manifest, graph = gold_packet.load_packet(packet)
    registry_manifest, registry = load_registry(folder / "registry")
    need(report["packet_id"] == manifest["packet_id"] and report["graph_sha256"] == manifest["graph_sha256"]
         and report["registry_sha256"] == registry_manifest["registry_sha256"], "Cornish reference belongs to another graph/registry.")
    study = inspect_article(folder / "source/article.xml", report["article_sha256"])
    rows, reader = read_native_study(folder / "source/supplementary.zip", report["archive_sha256"])
    labels = classify(graph, rows, registry)
    need(read_rows(folder / "native_rows.jsonl") == rows and read_rows(folder / "reference_labels.jsonl") == labels
         and report["publication"] == study and report["native_reader"] == reader
         and report["counts"] == dict(Counter(row["verdict"] for row in labels)), "Cornish native rows/labels do not replay.")
    need(report["files"] == inventory(folder) and sha(folder / "report.json") == report_sha256,
         "Cornish reference changed during replay.")
    return report, labels


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("packet", "archive", "article", "registry", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    for key in ("archive-sha256", "article-sha256", "registry-sha256"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    print(prepare(a.packet, a.archive, a.article, a.registry, a.out, archive_sha256=a.archive_sha256,
        article_sha256=a.article_sha256, registry_sha256=a.registry_sha256)["content_sha256"])


if __name__ == "__main__":
    main()
