"""Source-preserving MAP-IT proximity observations from the completed reanalysis.

This adapter reprojects saved author-model output. It does not fit a model,
redefine enrichment, infer binding, or turn consumed observations into a test.
The local observation predicate and ordinary assertion machinery already exist.
"""
from collections import Counter
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

from .client import digest, utcnow, write_json

FORMAT = "biograph-steward.mapit-source-publication.v1"
PROJECTION_FORMAT = "biograph-steward.mapit-proximity-projection.v1"
DOI = "10.1038/s41467-026-79134-z"
BAIT = "UniProtKB:P00533"
ASSAY = "MAP-IT photocatalytic carbene-based proximity labelling"
TISSUE = "pooled colorectal tumour and adjacent non-tumour tissue"
PREDICATE = "biograph:has_assay_observation_with"
PREFIX = "extension_sources/mapit/"
ACCESSION = re.compile(r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[0-9]+)?$")
LIMITATIONS = [
    "Derived source-key-corrected additive-model proximity enrichment, not an author-supplied binary gold standard.",
    "The antibody coefficient is Isotype minus Primary; negative Beta_Ab indicates Primary enrichment.",
    "The model pools tissue contexts; it does not establish tumour-specific rewiring or direct binding.",
    "Seven patients, fourteen tissue blocks and repeated measurements are not independent experiments for each protein pair.",
    "Noncalls, filtered groups and unresolved identities are not negative interaction edges.",
    "Archive match states concern the complete April 2024 ncats_ppi layer and its public profile, not absence from current Pharos.",
    "This consumed study cannot independently validate its own integration or pruning.",
    "Protein names retain source annotations; exact accessions do not establish sequence, isoform or construct equivalence.",
    "Controlled-vocabulary references are local broad semantic mappings, not IMEx curation or full standard conformance.",
]
_TABLES = "ncats_ppi,protein,target,t2tc,dataset,dbinfo,ncats_dataSource,input_version"
_MODEL_FILES = {"author_full_stats.tsv", "author_fit_MArrayLM.rds", "execution.log",
                "author_full_stats.rds", "identity_sidecar.tsv", "effective_CFG.R",
                "sessionInfo.after_model.txt", "author_full_stats.xlsx", "effective_CFG.rds",
                "sample_metadata.tsv"}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json(raw):
    from .assay_attachment import _decode
    return _decode(raw)


def _sealed(value):
    return isinstance(value, dict) and value.get("content_sha256") == digest(
        {k: v for k, v in value.items() if k != "content_sha256"})


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _tsv(raw, required):
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")), delimiter="\t")
    _require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames)
             and set(required) <= set(reader.fieldnames), "MAP-IT source table schema differs.")
    rows = list(reader)
    _require(all(None not in row and None not in row.values() for row in rows),
             "Malformed MAP-IT source row.")
    return rows


def _number(text, field):
    if text in ("NA", "NaN"):
        return None
    try:
        value = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid MAP-IT statistic " + field) from exc
    _require(math.isfinite(value), "Nonfinite MAP-IT statistic.")
    if field in {"P_Ab", "Q_Ab"}:
        _require(0 <= value <= 1, "MAP-IT probability outside [0,1].")
    return value


def archive_queries(partners):
    """Use the existing ncats_ppi schema and the already verified resolver rule."""
    _require(partners and len(partners) == len(set(partners))
             and all(ACCESSION.fullmatch(uid) for uid in partners), "Invalid exact MAP-IT roster.")
    roster = ",".join("'" + uid + "'" for uid in sorted({"P00533", *partners}))
    scope = "WITH scope AS (SELECT * FROM protein WHERE uniprot IN (" + roster + ")) "
    proteins = (scope + "SELECT p.uniprot,p.id AS protein_id,p.sym AS symbol,"
                "count(distinct t.target_id) AS target_count FROM scope p "
                "LEFT JOIN t2tc t ON t.protein_id=p.id GROUP BY p.uniprot,p.id,p.sym "
                "ORDER BY p.uniprot,p.id")
    pairs = (scope + "SELECT a.*,p.uniprot AS subject_uniprot,q.uniprot AS object_uniprot "
             "FROM ncats_ppi a JOIN scope p ON p.id=a.protein_id JOIN scope q ON q.id=a.other_id "
             "WHERE (p.uniprot='P00533' AND q.uniprot<>'P00533') OR "
             "(q.uniprot='P00533' AND p.uniprot<>'P00533') "
             "ORDER BY p.uniprot,q.uniprot,a.id")
    return {"proteins": proteins, "pairs": pairs}


def _archive_status(partners, proteins, raw_pairs):
    roster = {"P00533", *partners}
    counts = Counter(row["uniprot"] for row in proteins)
    _require(set(counts) == roster and all(n == 1 for n in counts.values())
             and all(row["target_count"] == 1 for row in proteins),
             "Archive roster is not uniquely resolved at the source accession level.")
    rows_by_partner = {uid: [] for uid in partners}
    for row in raw_pairs:
        endpoints = {row["subject_uniprot"], row["object_uniprot"]}
        _require(len(endpoints) == 2 and "P00533" in endpoints and endpoints <= roster,
                 "Archive pair query returned an outside or self pair.")
        rows_by_partner[next(iter(endpoints - {"P00533"}))].append(row)
    result = {}
    for uid, raw in rows_by_partner.items():
        nonmock = [r for r in raw if r["ppitypes"] != "mock"]
        public = [r for r in nonmock if r["ppitypes"] != "STRINGDB" or
                  (type(r["score"]) in (int, float) and r["score"] >= 400)]
        # Preserve reciprocal rows as source views, never as independent studies.
        result[uid] = {
            "status": ("present_in_archived_public_PPI_profile" if public else
                       "raw_archived_pair_below_public_profile" if nonmock else
                       "no_nonmock_archived_PPI_pair"),
            "raw_nonmock_views": len(nonmock), "public_profile_views": len(public),
            "record_ids": sorted({r["id"] for r in nonmock}),
            "provider_bundles": sorted({r["ppitypes"] for r in nonmock}),
            "source_views": deepcopy(raw),
            "current_Pharos_absence_established": False,
            "independent_evidence_count": None,
        }
    return result


def _model_rows(files):
    """Preserve the entire modeled family before selecting graph observations."""
    identities = _tsv(files["source/primary/identity_sidecar.tsv"],
                      ("Source.Matrix.Row", "Model.Protein", "Protein.Group", "Genes",
                       "Exact.UniProt", "Identity.Status"))
    stats = _tsv(files["source/primary/author_full_stats.tsv"],
                 ("Protein", "Genes", "Beta_Ab", "P_Ab", "Q_Ab", "ImputeStatus"))
    raw = _tsv(files["source/raw/EGFR_colon_report.pg_matrix.tsv"],
               ("Protein.Group", "Genes"))
    meta = _tsv(files["source/primary/sample_metadata.tsv"], ("Col", "Block", "Tissue", "Ab", "Sample"))
    raw_header = next(csv.reader(StringIO(files["source/raw/EGFR_colon_report.pg_matrix.tsv"].decode("utf-8-sig")), delimiter="\t"))
    stats_header = next(csv.reader(StringIO(files["source/primary/author_full_stats.tsv"].decode("utf-8-sig")), delimiter="\t"))
    _require(len(meta) == 168 and [int(r["Col"]) for r in meta] == list(range(5, 173))
             and len({r["Sample"] for r in meta}) == 168 and len(raw_header) == 172
             and all(r["Sample"] in stats_header for r in meta),
             "Complete MAP-IT sample family is missing or reordered.")
    _require(len(identities) == len(raw) == 6476 and len(stats) == 5378,
             "MAP-IT complete source/model family changed.")
    _require([int(r["Source.Matrix.Row"]) for r in identities] == list(range(2, 6478)),
             "MAP-IT annotation-row lineage differs.")
    mapping = {r["Model.Protein"]: r for r in identities}
    _require(len(mapping) == len(identities), "Repeated MAP-IT model identity.")
    group_counts = Counter(r["Protein.Group"] for r in identities)
    for ident, original in zip(identities, raw):
        _require(ident["Protein.Group"] == original["Protein.Group"]
                 and ident["Genes"] == original["Genes"], "Source annotation lineage differs.")
        valid = bool(ACCESSION.fullmatch(ident["Protein.Group"]))
        exact = valid and group_counts[ident["Protein.Group"]] == 1
        status = ("exact_single_source_accession" if exact else
                  "unresolved_repeated_group" if valid else "unresolved_group_or_accession")
        _require(ident["Identity.Status"] == status and ident["Exact.UniProt"] ==
                 (ident["Protein.Group"] if exact else "NA"), "Whole protein-group identity changed.")
    seen, ledger, selected = set(), [], []
    for physical_row, row in enumerate(stats, 2):
        name = row["Protein"]
        _require(name not in seen and name in mapping, "Missing or repeated model identity.")
        seen.add(name)
        ident = mapping[name]
        _require(row["Genes"] == ident["Genes"] and row["ImputeStatus"] == "not_imputed",
                 "Model annotation or preprocessing differs.")
        beta, p, q = (_number(row[k], k) for k in ("Beta_Ab", "P_Ab", "Q_Ab"))
        _require((p is None) == (q is None) and (p is None or q + 1e-12 >= p),
                 "Full-family P/Q values disagree.")
        estimable = beta is not None and p is not None and q is not None
        positive = estimable and beta < 0 and q < 0.05
        node = ("UniProtKB:" + ident["Exact.UniProt"]
                if ident["Identity.Status"] == "exact_single_source_accession" else None)
        record = {"model_protein": name, "model_table_row": physical_row,
                  "source_matrix_row": int(ident["Source.Matrix.Row"]),
                  "protein_group": ident["Protein.Group"], "source_genes": ident["Genes"],
                  "exact_node_id": node, "identity_status": ident["Identity.Status"],
                  "Beta_Ab": beta, "P_Ab": p, "Q_Ab": q, "estimable": estimable,
                  "primary_enriched": bool(positive),
                  "original_statistics": {k: row[k] for k in ("Beta_Ab", "P_Ab", "Q_Ab")},
                  "state": ("bait_self_observation" if node == BAIT else
                            "enriched_identity_unresolved" if positive and node is None else
                            "primary_enriched_proximity" if positive else
                            "not_called_not_a_negative" if estimable else "unknown_nonestimable")}
        ledger.append(record)
        if positive and node is not None and node != BAIT:
            selected.append(record)
    _require(len(selected) == 120 and len({r["exact_node_id"] for r in selected}) == 120,
             "Completed MAP-IT partner family differs from the fixed reanalysis.")
    return ledger, selected


def _verify_material(files):
    protocol = _json(files["source/protocol.json"])
    freeze = _json(files["source/final_freeze_receipt.json"])
    result = _json(files["source/assessment_report.json"])
    execution = _json(files["source/execution_receipt.json"])
    archive = _json(files["archive/archive_receipt.json"])
    extraction = _json(files["archive/extraction_receipt.json"])
    query = _json(files["archive/query_receipt.json"])
    _require(_sealed(protocol) and _sealed(result) and _sealed(extraction),
             "MAP-IT frozen protocol, result or archive extraction seal differs.")
    _require(_sha(files["source/protocol.json"]) == freeze["protocol_file_sha256"]
             == execution["protocol_file_sha256"], "MAP-IT author execution protocol binding differs.")
    _require(execution["complete"] is True and len(execution["variants"]) == 2,
             "Both predeclared author-model variants must be completed.")
    _require({v["name"] for v in execution["variants"]} == {"source_key_corrected", "released_metadata"},
             "Both distinct predeclared metadata variants are required.")
    for variant in execution["variants"]:
        name = variant["name"]
        _require(name in {"source_key_corrected", "released_metadata"} and variant["returncode"] == 0
                 and set(variant["files"]) == _MODEL_FILES,
                 "Incomplete or replacement author-model variant.")
        folder = "primary" if name == "source_key_corrected" else "released"
        for filename, expected in variant["files"].items():
            _require(_sha(files["source/" + folder + "/" + filename]) == expected,
                     "Author-model output binding differs.")
    source_map = {
        "EGFR_colon_report.pg_matrix.tsv": "source/raw/EGFR_colon_report.pg_matrix.tsv",
        "EGFR_colon_report.pr_matrix.tsv": "source/raw/EGFR_colon_report.pr_matrix.tsv",
        "pg_annotation_only.tsv": "source/pg_annotation_only.tsv",
        "identity_sidecar.R": "source/identity_sidecar.R",
        "run_author_variant.R": "source/run_author_variant.R",
        "EGFR_Aggregated_model.released.R": "source/EGFR_Aggregated_model.released.R",
        "EGFR_Aggregated_model.source_key_corrected.R": "source/EGFR_Aggregated_model.source_key_corrected.R",
    }
    for name, location in source_map.items():
        _require(_sha(files[location]) == protocol["run_bundle_files"][name],
                 "MAP-IT author/raw source changed.")
    _require(b"expected_q <- p.adjust(fit$p.value" in files["source/run_author_variant.R"],
             "Original full-family Q fidelity guard is absent.")
    for source_name, location in {
        **{"reference_runtime/" + n: "runtime/" + n for n in
           ("linux-64.mirror.sha256.explicit.txt", "linux-64.package-manifest.json",
            "runtime_acceptance.json", "runtime_probe.container.txt")},
        **{"reference_rules/author_runtime/" + n: "source/" + n for n in
           ("sample_metadata_audit.json", "patient7_metadata_only.patch")},
    }.items():
        _require(_sha(files[location]) == protocol["evidence_bindings"][source_name],
                 "MAP-IT frozen metadata or runtime binding differs.")
    _require(archive["sha256"] == extraction["historical_archive_sha256"]
             == query["archive_sha256"] and archive["gzip_full_crc_and_eof_verified"] is True,
             "Archive query and complete verified source do not agree.")
    _require(query["schema"] == "ncats_ppi exact accession lookup; nonmock raw and resolver profile"
             and query["public_profile"] == "exclude mock; exclude exact STRINGDB score<400",
             "Archive source semantics differ.")
    for name in ("proteins", "pairs"):
        _require(_sha(files["archive/" + name + ".json"]) == query["outputs_sha256"][name]
                 and _sha(files["archive/" + name + ".sql"]) == query["queries_sha256"][name],
                 "Archive query result or exact query differs.")
    license_contract = _json(files["source/licensing_contract.json"])
    _require(_sealed(license_contract) and license_contract["study_doi"] == DOI
             and license_contract["figshare"]["id"] == 31820131
             and license_contract["figshare"]["license"]["name"] == "CC BY 4.0"
             and license_contract["author_code"]["license"] == "cc-by-4.0",
             "Preserve the verified source-specific data license.")
    return protocol, result, archive


def project_material(files):
    """Reproduce the observation ledger and source lookup from preserved bytes."""
    protocol, result, archive = _verify_material(files)
    ledger, selected = _model_rows(files)
    partners = sorted(r["exact_node_id"].split(":", 1)[1] for r in selected)
    queries = archive_queries(partners)
    for name, sql in queries.items():
        _require(files["archive/" + name + ".sql"].decode() == sql,
                 "Archive query is not the complete exact partner lookup.")
    statuses = _archive_status(partners, _json(files["archive/proteins.json"]),
                               _json(files["archive/pairs.json"]))
    bindings = {"protocol_file_sha256": _sha(files["source/protocol.json"]),
                "assessment_content_sha256": result["content_sha256"],
                "stats_sha256": _sha(files["source/primary/author_full_stats.tsv"]),
                "identity_sha256": _sha(files["source/primary/identity_sidecar.tsv"]),
                "archive_sha256": archive["sha256"],
                "query_receipt_sha256": _sha(files["archive/query_receipt.json"])}
    observations = []
    for row in selected:
        partner = row["exact_node_id"]
        oid = "mapit.observation:" + digest({"study": DOI, "variant": "source_key_corrected",
            "partner": partner, "model_row": row["model_table_row"], "bindings": bindings})[:24]
        locators = [
            {"locator": "source/primary/author_full_stats.tsv#row=" + str(row["model_table_row"]),
             "file_sha256": bindings["stats_sha256"], "role": "full_family_model_statistic"},
            {"locator": "source/primary/identity_sidecar.tsv#row=" + str(row["source_matrix_row"]),
             "file_sha256": bindings["identity_sha256"], "role": "exact_whole_group_lineage"},
            {"locator": "source/raw/EGFR_colon_report.pg_matrix.tsv#row=" + str(row["source_matrix_row"]),
             "file_sha256": protocol["run_bundle_files"]["EGFR_colon_report.pg_matrix.tsv"],
             "role": "original_protein_group"},
            {"locator": "archive/pairs.json", "file_sha256": _sha(files["archive/pairs.json"]),
             "role": "bounded_archived_PPI_context"},
        ]
        observations.append({"id": oid, "source_kind": "mapit", "source": {"kind": "mapit"},
            "study": "doi:" + DOI, "products": [BAIT, partner], "anchor": BAIT,
            "partner": partner, "assay": ASSAY, "tissue_label": TISSUE,
            "assay_status": "primary_enriched_proximity", "local_review_state": "candidate",
            "participant_taxon": "NCBITaxon:9606", "evaluable": True,
            "detection_method": {"id": "MI:1313", "label": "proximity labelling technology",
                                 "mapping_origin": "local broad semantic reference"},
            "interaction_type": {"id": "MI:2364", "label": "proximity",
                                 "mapping_origin": "local semantic reference; no binding inference"},
            "statistics": {k: row[k] for k in ("Beta_Ab", "P_Ab", "Q_Ab")},
            "statistical_family": {"modeled_groups": len(ledger), "adjustment": "author full-family BH",
                "contrast": "Isotype minus Primary", "criterion": "finite Beta_Ab<0 and Q_Ab<0.05",
                "model": "additive Tissue+Ab with duplicateCorrelation tissue block"},
            "sampling": {"patients": 7, "tissue_blocks": 14, "measurements": 168},
            "source_identity": deepcopy(row), "source_locators": locators,
            "citations": [{"id": "doi:" + DOI, "url": "https://doi.org/" + DOI,
                           "role": "primary_study"}],
            "archive_lookup": deepcopy(statuses[partner.split(":", 1)[1]]),
            "interpretation": "Primary-enriched pooled colorectal-tissue proximity under the recorded assay and model; not direct binding or tumour-specific rewiring.",
            "biologically_validated": False, "independent_evidence_count": None})
    summary = {"source_kind": "mapit", "full_modeled_groups": len(ledger),
        "full_family_enriched_groups": sum(r["primary_enriched"] for r in ledger),
        "enriched_unresolved_identity_groups": sum(r["primary_enriched"] and r["exact_node_id"] is None for r in ledger),
        "qualified_partner_observations": len(observations), "bait_self_observations_excluded": 1,
        "archive_pair_statuses": dict(sorted(Counter(r["status"] for r in statuses.values()).items())),
        "full_archive_protein_resolution": len(partners), "current_Pharos_novelty_established": False,
        "independent_validation_performed": False, "automatic_acceptance_performed": False,
        "automatic_pruning_performed": False, "limitations": list(LIMITATIONS)}
    value = {"format": PROJECTION_FORMAT, "bindings": bindings, "observations": observations,
             "full_model_ledger": ledger, "summary": summary, "limitations": list(LIMITATIONS)}
    value["content_sha256"] = digest(value)
    return value


def load_publication(path):
    from .assay_attachment import _capture
    manifest, files = _capture(path, "publication.json")
    _require(manifest.get("format") == FORMAT and manifest.get("source_kind") == "mapit"
             and manifest.get("baseline_modified") is False
             and manifest.get("independent_validation_performed") is False,
             "Unsupported MAP-IT source publication.")
    projection = project_material(files)
    _require(projection == _json(files["projection.json"])
             and projection["summary"] == manifest["summary"]
             and projection["content_sha256"] == manifest["projection_content_sha256"],
             "MAP-IT projection does not reproduce.")
    return manifest, projection, files


def prepare(snapshot, baseline_graph, manifest, projection):
    """Prepare bounded candidate observations, without changing primary targets."""
    _require(_sealed(manifest) and manifest.get("format") == FORMAT and _sealed(projection)
             and projection["content_sha256"] == manifest["projection_content_sha256"],
             "MAP-IT preparation requires a verified source publication.")
    _require(snapshot.get("data_kind") == "live_pharos"
             and baseline_graph.get("snapshot_sha256") == snapshot.get("content_sha256"),
             "MAP-IT extension must bind the supplied live Pharos baseline.")
    _require(BAIT in {r["id"] for r in baseline_graph.get("targets", [])},
             "EGFR must already be an explicitly resolved primary Pharos target.")
    existing = {n["id"] for n in baseline_graph["nodes"]}
    nodes, edges, observations = {}, [], []
    for original in projection["observations"]:
        row = deepcopy(original)
        row["source"].update(publication_sha256=manifest["content_sha256"],
                             locator_base=PREFIX, license=deepcopy(manifest["source_license"]))
        row["source_publication_sha256"] = manifest["content_sha256"]
        for entry in row["source_locators"]:
            entry["locator"] = PREFIX + entry["locator"]
        partner = row["partner"]
        if partner not in existing:
            nodes[partner] = {"id": partner, "name": row["source_identity"]["source_genes"] or partner,
                "category": "biolink:Protein", "identifier_mapped": True,
                "sym": row["source_identity"]["source_genes"], "tdl": None,
                "data_kind": "mapit_derived_tissue_evidence", "primary_source_raw": "MAP-IT source data",
                "extension_source_kind": "mapit",
                "extension_publication_sha256": manifest["content_sha256"],
                "source_publication_sha256": manifest["content_sha256"],
                "source_locators": deepcopy(row["source_locators"]),
                "identity_note": "Exact whole source protein-group accession; not a new Pharos primary target or a sequence/construct equivalence claim."}
        eid = "edge:" + digest({"publication": manifest["content_sha256"],
            "observation": row["id"], "baseline_snapshot": snapshot["content_sha256"]})[:20]
        row["graph_edge_id"] = eid
        edges.append({"id": eid, "subject": BAIT, "predicate": PREDICATE, "object": partner,
            "record_kind": "tissue_proximity_observation", "symmetric": False,
            "qualifiers": {"observation_id": row["id"], "assay": ASSAY, "tissue_label": TISSUE,
                "species": "NCBITaxon:9606", "measurement_qualifier": "primary_enriched_proximity",
                "evidence_type": "MAP-IT source-key-corrected reanalysis; publication:" + manifest["content_sha256"]},
            "status": "passed_structural_checks", "review_reasons": [],
            "publications": ["doi:" + DOI], "primary_source_raw": "MAP-IT source data and released author analysis",
            "reference_raw": "https://doi.org/" + DOI,
            "evidence_raw": "Derived source-key-corrected Primary-enriched pooled-tissue proximity; not direct binding.",
            "source_scores_raw": {"Beta_Ab": row["statistics"]["Beta_Ab"],
                                  "Q_Ab": row["statistics"]["Q_Ab"],
                                  "interpretation": "Author-model coefficient and full-family adjusted statistic, not a confidence score."},
            "duplicate_count": 0,
            "aggregator": "BioGraph Steward source-preserving projection", "evidence_sources": ["MAP-IT"],
            "evidence_record": deepcopy(row), "observation": deepcopy(row), "source_record_count": 1,
            "record_locators": [e["locator"] for e in row["source_locators"]],
            "retrieval_provenance": deepcopy(row["source_locators"]),
            "normalization_notes": list(LIMITATIONS),
            "snapshot_sha256": snapshot["content_sha256"], "data_kind": "mapit_derived_tissue_evidence",
            "extension_source_kind": "mapit", "extension_publication_sha256": manifest["content_sha256"],
            "biologically_validated": False})
        observations.append(row)
    summary = {**deepcopy(projection["summary"]), "source_publication_sha256": manifest["content_sha256"],
        "extension_nodes_added": len(nodes), "extension_edges_added": len(edges),
        "primary_Pharos_targets_added": 0, "primary_Pharos_records_modified": 0,
        "baseline_snapshot_sha256": snapshot["content_sha256"]}
    return {"nodes": sorted(nodes.values(), key=lambda n: n["id"]),
            "edges": sorted(edges, key=lambda e: e["id"]), "observations": observations, "summary": summary}


def publish_completed_analysis(run, out):
    """Package completed analysis and exact full-archive lookups, atomically.

    It uses the previously verified sql-splitter cache; no network/model calls,
    no new source interpretation, and no changes to the original run occur.
    """
    from .assay_attachment import _ordinary
    run, out = Path(run).absolute(), Path(out).absolute()
    _require(run.is_dir() and not out.exists() and not out.is_symlink()
             and run.resolve() not in out.resolve().parents and out.resolve() not in run.resolve().parents,
             "Choose a new MAP-IT publication outside its input run.")
    material = {
        "source/protocol.json": run / "final_analysis_protocol.json",
        "source/final_freeze_receipt.json": run / "final_freeze_receipt.json",
        "source/assessment_report.json": run / "assessment_results/report.json",
        "source/execution_receipt.json": run / "author_verified/study_results/execution_receipt.json",
        "source/raw/EGFR_colon_report.pg_matrix.tsv": run / "reference_rules/intake/EGFR_colon_report.pg_matrix.tsv",
        "source/raw/EGFR_colon_report.pr_matrix.tsv": run / "reference_raw/EGFR_colon_report.pr_matrix.tsv",
        "archive/archive_receipt.json": run / "source/archive_receipt.json",
        "archive/extraction_receipt.json": run / "source_research/extraction_receipt.json",
        "source/licensing_contract.json": run.parent / "mapit_reference_qualification_20261111/study_contract/processed_metadata/processed_reference_contract.json",
    }
    for name in ("pg_annotation_only.tsv", "identity_sidecar.R", "run_author_variant.R",
                 "EGFR_Aggregated_model.released.R", "EGFR_Aggregated_model.source_key_corrected.R",
                 "sample_metadata_audit.json", "patient7_metadata_only.patch"):
        material["source/" + name] = run / "reference_rules/author_runtime" / name
    for name in ("linux-64.mirror.sha256.explicit.txt", "linux-64.package-manifest.json",
                 "runtime_acceptance.json", "runtime_probe.container.txt"):
        material["runtime/" + name] = run / "reference_runtime" / name
    for variant, label in (("source_key_corrected", "primary"), ("released_metadata", "released")):
        directory = run / "author_verified/study_results" / variant
        for path in sorted(directory.iterdir()):
            _require(path.is_file(), "Unexpected author-result directory entry.")
            material["source/" + label + "/" + path.name] = path
    files = {name: _ordinary(path) for name, path in material.items()}
    # Model/source validation precedes querying; no assay outcomes are revised.
    ledger, selected = _model_rows(files)
    partners = sorted(r["exact_node_id"].split(":", 1)[1] for r in selected)
    archive = _json(files["archive/archive_receipt.json"])
    dump = run / "source/pharos319.sql.gz"
    _require(dump.stat().st_size == archive["bytes"] and _file_sha(dump) == archive["sha256"],
             "Full archived source bytes differ from the verified receipt.")
    tool = run / "source_research/sql_splitter_v1.21.0/sql-splitter-aarch64-apple-darwin/sql-splitter"
    tool_archive = run / "source_research/sql_splitter_v1.21.0/sql-splitter-aarch64-apple-darwin.tar.xz"
    cache = run / "source_research/derived/cache"
    _require(tool.is_file() and (cache / "877441d7b69009f721f0494c123e5bd5.duckdb").is_file(),
             "Verified sql-splitter tool and imported source cache are required.")
    extraction = _json(files["archive/extraction_receipt.json"])
    _require(_file_sha(tool_archive) == extraction["native_tool_archive_sha256"],
             "Version-pinned sql-splitter archive differs.")
    with tarfile.open(tool_archive) as tar:
        members = [m for m in tar.getmembers() if m.isfile() and Path(m.name).name == "sql-splitter"]
        _require(len(members) == 1 and _sha(tar.extractfile(members[0]).read()) == _file_sha(tool),
                 "Installed query tool differs from the verified upstream release.")
    environment = dict(os.environ)
    environment["SQL_SPLITTER_CACHE_DIR"] = str(cache)
    queries, commands = archive_queries(partners), {}
    for name, sql in queries.items():
        argv = [str(tool), "query", str(dump), sql, "--tables", _TABLES, "--disk", "--cache",
                "--memory-limit", "2GB", "--format", "json"]
        response = subprocess.run(argv, env=environment, text=True, capture_output=True, check=True, timeout=120)
        _require("Using cached database:" in response.stderr, "Archive query did not use the verified imported cache.")
        files["archive/" + name + ".json"] = response.stdout.encode()
        files["archive/" + name + ".sql"] = sql.encode()
        commands[name] = {"argv": argv, "stderr": response.stderr}
    receipt = {"archive_sha256": archive["sha256"], "created_at": utcnow(),
        "schema": "ncats_ppi exact accession lookup; nonmock raw and resolver profile",
        "public_profile": "exclude mock; exclude exact STRINGDB score<400",
        "queries_sha256": {n: _sha(files["archive/" + n + ".sql"]) for n in queries},
        "outputs_sha256": {n: _sha(files["archive/" + n + ".json"]) for n in queries},
        "cache_sha256": _file_sha(cache / "877441d7b69009f721f0494c123e5bd5.duckdb"),
        "tool_sha256": _file_sha(tool), "commands": commands,
        "lookup_is_current_Pharos_novelty_proof": False}
    files["archive/query_receipt.json"] = (json.dumps(receipt, indent=2) + "\n").encode()
    files["LICENSE.md"] = (
        "# Upstream source terms\n\nThe preserved Figshare data and Zenodo author code are recorded as CC BY 4.0 in source/licensing_contract.json. "
        "Attribute Faulkner et al., DOI " + DOI + ", dataset PXD075907 / Figshare31820131 and author code Zenodo23181000. "
        "Derived calls use a documented metadata correction and are not the authors' binary gold standard. "
        "The article's separate license is not assigned to the data, code or this application. "
        "NCATS archive material retains its source terms; this package does not assign it a new license.\n").encode()
    files["implementation/mapit_source.py"] = _ordinary(Path(__file__))
    projection = project_material(files)
    files["projection.json"] = (json.dumps(projection, indent=2) + "\n").encode()
    manifest = {"format": FORMAT, "source_kind": "mapit", "created_at": utcnow(),
        "projection_content_sha256": projection["content_sha256"],
        "summary": projection["summary"], "baseline_modified": False,
        "independent_validation_performed": False, "automatic_acceptance_performed": False,
        "source_license": {"source": "MAP-IT Figshare data and Zenodo author code",
            "license": "CC BY 4.0", "license_file": PREFIX + "LICENSE.md",
            "attribution": "Faulkner et al.; doi:" + DOI + "; PXD075907; Figshare31820131; Zenodo23181000",
            "note": "Dataset/code-specific terms; article and NCATS source terms remain separate."},
        "implementation_sha256": {"mapit_source.py": _file_sha(Path(__file__))},
        "files": {n: _sha(raw) for n, raw in sorted(files.items())}}
    manifest["content_sha256"] = digest(manifest)
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".mapit-publication-", dir=out.parent))
    try:
        for name, raw in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        write_json(stage / "publication.json", manifest)
        loaded, replay, _ = load_publication(stage)
        _require(loaded == manifest and replay == projection, "MAP-IT publication replay differs.")
        _require(not out.exists(), "Publication output appeared during staging.")
        stage.rename(out)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)
