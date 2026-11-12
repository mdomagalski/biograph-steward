"""Private, source-preserving BioPlex HCT116 context on existing Pharos pairs.

The official BioPlexPy reader preserves the native nine-column TSV. This
adapter additionally uses the author's separate bait/prey table and a global
bijective GeneID/literal-accession ledger. It adds observations, never nodes,
edges, direct-binding claims, assay-resolved isoforms or pruning decisions.
Native-table redistribution terms remain unverified; publications are private.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
from html import escape
from io import StringIO
import json
import math
from pathlib import Path
import re

from .assay_attachment import _capture, _decode, _ordinary, _sealed
from .client import digest, utcnow, write_json
from .file_utils import new_output

FORMAT = "biograph-steward.bioplex-source-publication.v1"
PROJECTION_FORMAT = "biograph-steward.bioplex-source-projection.v1"
INTAKE_FORMAT = "biograph-steward.bioplex-source-intake.v1"
POLICY = "HCT116-native-bijective-literal-both-primary-existing-pair-context-only.v1"
RELEASE = "HCT116-1.0-native-filtered"
SOURCE_URL = "https://bioplex.hms.harvard.edu/interactions.php"
COMPANION_URL = "https://bioplex.hms.harvard.edu/data/BioPlex_HCT116_Network_5.5K_Dec_2019.tsv"
DIRECTED_URL = "https://bioplex.hms.harvard.edu/data/BioPlex_3.0_HCT116_DirectedEdges.tsv"
COMPANION_SHA256 = "b37be6de6fe15e948151ab9480cfcb88a6795780cf7a4059b386b07f3c1e760d"
DIRECTED_SHA256 = "1959ac2939668fe1056960e92a76ccead38898e126aa694aa628905d47540d1a"
COMPANION_FILE = "source/HCT116_native_companion.tsv"
DIRECTED_FILE = "source/HCT116_native_directed.tsv"
INTAKE_FILE = "source/intake.json"
PREFIX = "extension_sources/bioplex/"
COMPANION_COLUMNS = ("GeneA", "GeneB", "UniprotA", "UniprotB", "SymbolA", "SymbolB", "pW", "pNI", "pInt")
DIRECTED_COLUMNS = ("Bait GeneID", "Bait Symbol", "Prey GeneID", "Prey Symbol")
ACCESSION = re.compile(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?\Z")
GENE = re.compile(r"[1-9][0-9]*\Z")
SOURCE_LICENSE = {"source": "BioPlex HCT116 native filtered source tables", "license": None,
    "source_terms_url": SOURCE_URL, "native_data_redistribution": "unverified",
    "publication_scope": "local_private_research_only", "public_raw_data_export_authorized": False,
    "note": "Public availability and BioPlexPy's MIT software license do not establish native-table redistribution rights. Do not include this publication or its derived source rows in public repositories or submission archives without separate rights clearance."}
CITATIONS = [
    {"id": "PMID:33961781", "label": "BioPlex 3.0 experimental protocol and inference", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8165030/", "role": "source_study_protocol"},
    {"id": "PMID:8044777", "label": "Parental HCT116 mismatch-repair context", "url": "https://pubmed.ncbi.nlm.nih.gov/8044777/", "role": "historical_cell_model_context", "inspected_scope": "Primary abstract; full text not inspected."},
    {"id": "CVCL_0291", "label": "Cellosaurus HCT116 standard-name metadata", "url": "https://www.cellosaurus.org/CVCL_0291", "role": "project_added_cell_line_name_mapping"},
    {"id": SOURCE_URL, "label": "Author-native BioPlex downloads", "url": SOURCE_URL, "role": "source_downloads"}]
METHOD_CONTEXT = {
    "assay": "Affinity purification–mass spectrometry",
    "reported_study_protocol": "CMV-driven lentiviral expression of human ORFeome/OC ORFs with a C-terminal FLAG-HA tag; puromycin-selected stable ATCC HCT116 cells.",
    "inference_unit": "Entrez GeneID after peptide/protein parsimony; author literal UniProt labels are retained, not assay-resolved isoform identities.",
    "per_row_unknown": "Exact bait clone, allele, full sequence, expression stoichiometry, experimental batch genotype and mismatch-repair activity are not resolved by these native tables.",
    "model_context": "Primary literature documents MLH1-associated mismatch-repair deficiency in parental HCT116. This is historical model context, not an independently verified phenotype of the BioPlex batch.",
    "interpretation": "Tagged-ORF coassociation does not establish endogenous mismatch-repair competence, repair restoration, direct binding or patient colorectal-cancer benefit."}
LIMITATIONS = [
    "These are source-reported, gene-level coassociation calls under tagged-expression cell-model conditions; bait/prey roles are assay roles, not causal direction.",
    "The native companion's pW, pNI and pInt are classifier class scores for an undirected gene pair; they are not calibrated probabilities of biological truth or direction-specific scores.",
    "CompPASS-Plus uses prior-assisted training labels from STRING/GeneMANIA. These calls are not independent gold-standard truth for a Pharos/STRING graph.",
    "A BioPlex provider label in Pharos does not identify the exact study, cell line or source row; exact underlying evidence reuse remains unresolved.",
    "Exact author accession matching does not establish sequence, isoform, construct or gene-family equivalence. No suffix stripping or symbol-based mapping is performed.",
    "Missing selected records do not establish absence of an interaction. Source rows are not independent experiment counts.",
    "The complete source publication and derived row records are private research artifacts; native-table redistribution rights have not been verified."]


def _need(condition, message):
    if not condition:
        raise ValueError("BioPlex source: " + message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _accessions(values):
    _need(isinstance(values, list) and 1 <= len(values) <= 250
          and all(isinstance(v, str) and ACCESSION.fullmatch(v) for v in values)
          and values == sorted(set(values)), "expected unique sorted exact primary-cohort accessions.")
    return values


def _cohort(snapshot):
    _need(_sealed(snapshot) and snapshot.get("data_kind") == "live_pharos", "expected a sealed live Pharos snapshot.")
    rows = snapshot.get("targets")
    _need(isinstance(rows, list) and all(isinstance(r, dict) and isinstance(r.get("uniprot"), str) for r in rows),
          "snapshot primary identities are missing.")
    ids = [r["uniprot"] for r in rows]
    _need(len(ids) == len(set(ids)), "snapshot primary identities repeat.")
    return _accessions(sorted(ids))


def _rows(raw, columns):
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8"), newline=""), delimiter="\t", strict=True)
        _need(reader.fieldnames == list(columns), "native TSV header differs.")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("BioPlex source: invalid UTF-8 or quoted TSV.") from exc
    _need(all(None not in row and all(isinstance(v, str) for v in row.values()) for row in rows),
          "native TSV row width differs.")
    return rows


def parse_release(companion_raw, directed_raw, accessions):
    """Pure native-reader contract; publishing also verifies complete file pins."""
    scope = set(_accessions(accessions))
    companion = _rows(companion_raw, COMPANION_COLUMNS)
    directed = _rows(directed_raw, DIRECTED_COLUMNS)
    labels, genes = defaultdict(set), defaultdict(set)
    invalid_genes, invalid_gene_labels = set(), set()
    companion_pairs = defaultdict(list)
    counts = Counter()
    for ordinal, row in enumerate(companion, 2):
        for name in ("pW", "pNI", "pInt"):
            try:
                value = float(row[name])
            except (ValueError, TypeError) as exc:
                raise ValueError("BioPlex source: invalid native class score.") from exc
            _need(math.isfinite(value) and 0 <= value <= 1, "invalid native class score range.")
        for suffix in ("A", "B"):
            gene, accession = row["Gene" + suffix], row["Uniprot" + suffix]
            if not GENE.fullmatch(gene):
                if ACCESSION.fullmatch(accession):
                    invalid_gene_labels.add(accession)
                counts["invalid_companion_gene_endpoints"] += 1
                continue
            labels[gene].add(accession)
            if ACCESSION.fullmatch(accession):
                genes[accession].add(gene)
            else:
                invalid_genes.add(gene)
        if all(GENE.fullmatch(row[x]) for x in ("GeneA", "GeneB")):
            key = tuple(sorted((row["GeneA"], row["GeneB"])))
            companion_pairs[key].append({"source_row_ordinal": ordinal,
                "decoded_source_row_sha256": digest(row), "raw_source_row": dict(row),
                "source_scores_raw": {k: row[k] for k in ("pW", "pNI", "pInt")}})
    resolved = {}
    for gene, accessions_ in labels.items():
        if gene in invalid_genes or len(accessions_) != 1:
            continue
        accession = next(iter(accessions_))
        if accession in invalid_gene_labels or len(genes[accession]) != 1:
            continue
        resolved[gene] = accession
    directed_pairs = {tuple(sorted((r["Bait GeneID"], r["Prey GeneID"]))) for r in directed
                      if all(GENE.fullmatch(r[k]) for k in ("Bait GeneID", "Prey GeneID"))}
    _need(directed_pairs == set(companion_pairs), "directed and companion native gene-pair inventories differ.")
    observations = []
    for ordinal, row in enumerate(directed, 2):
        bait, prey = row["Bait GeneID"], row["Prey GeneID"]
        if not GENE.fullmatch(bait) or not GENE.fullmatch(prey):
            counts["invalid_directed_gene_rows"] += 1
            continue
        if bait not in resolved or prey not in resolved:
            counts["quarantined_identity_rows"] += 1
            continue
        if bait == prey:
            counts["self_gene_rows"] += 1
            continue
        if not {resolved[bait], resolved[prey]} <= scope:
            counts["outside_primary_cohort_rows"] += 1
            continue
        records = deepcopy(companion_pairs[tuple(sorted((bait, prey)))])
        scores = {digest(r["source_scores_raw"]): r["source_scores_raw"] for r in records}
        identity = {"directed_file_sha256": _sha(directed_raw), "source_row_ordinal": ordinal,
                    "decoded_source_row_sha256": digest(row),
                    "companion_file_sha256": _sha(companion_raw),
                    "companion_rows": [r["decoded_source_row_sha256"] for r in records]}
        oid = "bioplex-context:" + digest(identity)[:24]
        observations.append({"id": oid, "observation_id": oid, "source_kind": "bioplex",
            "record_kind": "cell_line_coassociation_observation", "source_release": RELEASE,
            "products": sorted("UniProtKB:" + resolved[g] for g in (bait, prey)),
            "bait": {"gene_id": bait, "symbol": row["Bait Symbol"], "uniprot": "UniProtKB:" + resolved[bait],
                     "literal_uniprot_accession": resolved[bait]},
            "prey": {"gene_id": prey, "symbol": row["Prey Symbol"], "uniprot": "UniProtKB:" + resolved[prey],
                     "literal_uniprot_accession": resolved[prey]},
            "directed_record": {"source_row_ordinal": ordinal, "decoded_source_row_sha256": digest(row),
                                "raw_source_row": dict(row)},
            "companion_records": records,
            "source_scores_raw": deepcopy(next(iter(scores.values()))) if len(scores) == 1 else {},
            "score_reporting": "unanimous_native_companion_pair_scores" if len(scores) == 1 else "multiple_distinct_native_companion_score_sets_preserved",
            "score_scope": "native_undirected_gene_pair_not_bait_direction_specific",
            "cell_line_literal": "HCT116", "cell_line_id": "CVCL_0291",
            "cell_line_id_basis": "Project exact standard-name mapping to Cellosaurus; not an identifier supplied by the native table or authentication of the experimental stock.",
            "participant_taxon": "NCBITaxon:9606", "assay_host_taxon": "NCBITaxon:9606",
            "method_context": deepcopy(METHOD_CONTEXT),
            "context_qualification": "Study protocol is source-reported; exact row-level clone, allele and experimental-batch repair activity remain unverified.",
            "context_review": {"kind": "agent_assisted_source_and_primary_literature_check", "human_expert_reviewed": False},
            "assay_status": "author_native_filtered_coassociation_call",
            "citations": deepcopy(CITATIONS), "study": "PMID:33961781",
            "source_identity": identity,
            "source_locators": [{"role": "native_bait_prey_row", "locator": DIRECTED_FILE + "#row=" + str(ordinal)}]
                + [{"role": "native_undirected_score_row", "locator": COMPANION_FILE + "#row=" + str(r["source_row_ordinal"])} for r in records],
            "graph_edge_id": None, "biologically_validated": False, "independent_validation": False,
            "independent_evidence_count": None, "exact_study_reuse_resolved": False,
            "limitations": list(LIMITATIONS)})
    summary = {"native_companion_rows": len(companion), "native_directed_rows": len(directed),
        "resolved_gene_ids": len(resolved), "quarantined_gene_ids": len(labels) - len(resolved),
        "selected_source_observations": len(observations),
        "selected_unique_pairs": len({tuple(o["products"]) for o in observations}),
        "excluded_row_counts": dict(sorted(counts.items())), "extension_nodes_added": 0,
        "extension_edges_added": 0, "independent_evidence_count": None,
        "automatic_acceptance_performed": False, "automatic_pruning_performed": False,
        "biological_validation_performed": False, "publication_scope": "local_private_research_only"}
    return {"observations": observations, "summary": summary}


def _projection(material):
    intake = _decode(material[INTAKE_FILE])
    _need(_sealed(intake) and intake.get("format") == INTAKE_FORMAT and intake.get("policy") == POLICY,
          "source intake contract differs.")
    for name, expected in ((COMPANION_FILE, COMPANION_SHA256), (DIRECTED_FILE, DIRECTED_SHA256)):
        _need(_sha(material[name]) == expected and intake.get("source_files_sha256", {}).get(name) == expected,
              "complete pinned native source bytes differ.")
    _need(intake.get("source_license") == SOURCE_LICENSE, "source rights metadata differs.")
    result = parse_release(material[COMPANION_FILE], material[DIRECTED_FILE], intake["accessions"])
    value = {"format": PROJECTION_FORMAT, "policy": POLICY, "source_kind": "bioplex", "source_release": RELEASE,
        "scope": {"accessions": intake["accessions"], "snapshot_sha256": intake["snapshot_sha256"],
                  "kind": "both_exact_primary_existing_pair_context_only"},
        "bindings": {"source_files_sha256": intake["source_files_sha256"],
            "intake_content_sha256": intake["content_sha256"], "snapshot_sha256": intake["snapshot_sha256"]},
        **result, "source_license": deepcopy(SOURCE_LICENSE), "citations": deepcopy(CITATIONS),
        "method_context": deepcopy(METHOD_CONTEXT), "limitations": list(LIMITATIONS)}
    value["content_sha256"] = digest(value)
    return value


def publish_release(source_companion, source_directed, snapshot, output):
    """Capture existing pinned files privately; no retrieval, model or graph edit."""
    material = {COMPANION_FILE: _ordinary(source_companion), DIRECTED_FILE: _ordinary(source_directed)}
    intake = {"format": INTAKE_FORMAT, "policy": POLICY, "accessions": _cohort(snapshot),
        "snapshot_sha256": snapshot["content_sha256"], "source_release": RELEASE,
        "source_urls": {COMPANION_FILE: COMPANION_URL, DIRECTED_FILE: DIRECTED_URL},
        "source_files_sha256": {n: _sha(raw) for n, raw in material.items()},
        "source_license": deepcopy(SOURCE_LICENSE)}
    intake["content_sha256"] = digest(intake)
    material[INTAKE_FILE] = (json.dumps(intake, indent=2) + "\n").encode()
    projection = _projection(material)
    folder = new_output(output, source_companion, source_directed)
    for name, raw in material.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    write_json(folder / "projection.json", projection)
    (folder / "RIGHTS.txt").write_text(SOURCE_LICENSE["note"] + "\nPrivate research publication only.\n")
    (folder / "index.html").write_text("<!doctype html><html lang='en'><meta charset='utf-8'><title>Private BioPlex context</title>"
        "<h1>BioPlex HCT116 source context</h1><p>Private research source capture; native-table redistribution rights are unverified.</p>"
        "<p>Existing pairs gain assay context only: no nodes, edges, independent validation or repair-restoration claim.</p><pre>"
        + escape(json.dumps(projection["summary"], indent=2)) + "</pre><a href='projection.json'>Private source-row projection</a></html>")
    manifest = {"format": FORMAT, "policy": POLICY, "source_kind": "bioplex", "source_release": RELEASE,
        "created_at": utcnow(), "projection_content_sha256": projection["content_sha256"],
        "bindings": deepcopy(projection["bindings"]), "summary": deepcopy(projection["summary"]),
        "source_license": deepcopy(SOURCE_LICENSE), "citations": deepcopy(CITATIONS),
        "files": {p.relative_to(folder).as_posix(): _sha(p.read_bytes()) for p in sorted(folder.rglob("*")) if p.is_file()},
        "baseline_modified": False, "automatic_pruning": False, "independent_validation_performed": False,
        "standard_conformance_claimed": False, "public_raw_data_export_authorized": False, "model_calls": 0}
    manifest["content_sha256"] = digest(manifest)
    write_json(folder / "publication.json", manifest)
    return load_publication(folder)[0]


def load_publication(path):
    manifest, files = _capture(path, "publication.json")
    _need(manifest.get("format") == FORMAT and manifest.get("policy") == POLICY
          and manifest.get("source_kind") == "bioplex" and manifest.get("source_release") == RELEASE
          and manifest.get("model_calls") == 0 and all(manifest.get(k) is False for k in
          ("baseline_modified", "automatic_pruning", "independent_validation_performed", "standard_conformance_claimed", "public_raw_data_export_authorized")),
          "unsupported private publication contract.")
    _need(set(files) == {"publication.json", COMPANION_FILE, DIRECTED_FILE, INTAKE_FILE, "projection.json", "RIGHTS.txt", "index.html"},
          "private source publication inventory differs.")
    projection = _projection(files)
    _need(_decode(files["projection.json"]) == projection
          and manifest.get("projection_content_sha256") == projection["content_sha256"]
          and manifest.get("bindings") == projection["bindings"] and manifest.get("summary") == projection["summary"]
          and manifest.get("source_license") == SOURCE_LICENSE and manifest.get("citations") == CITATIONS,
          "publication does not reproduce from pinned complete native files.")
    return manifest, projection, files


def prepare(snapshot, baseline_graph, manifest, projection):
    """Attach only exact existing-pair context; no added graph assertions."""
    _need(_sealed(manifest) and _sealed(projection) and manifest.get("format") == FORMAT
          and projection.get("format") == PROJECTION_FORMAT and manifest.get("policy") == projection.get("policy") == POLICY
          and manifest.get("projection_content_sha256") == projection["content_sha256"]
          and manifest.get("bindings") == projection.get("bindings") and manifest.get("summary") == projection.get("summary")
          and manifest.get("source_license") == projection.get("source_license") == SOURCE_LICENSE,
          "preparation requires the matching verified private publication.")
    _need(manifest.get("source_kind") == projection.get("source_kind") == "bioplex"
          and manifest.get("source_release") == projection.get("source_release") == RELEASE
          and manifest.get("model_calls") == 0 and all(manifest.get(k) is False for k in
          ("baseline_modified", "automatic_pruning", "independent_validation_performed", "standard_conformance_claimed", "public_raw_data_export_authorized"))
          and projection["bindings"].get("source_files_sha256") == {
              COMPANION_FILE: COMPANION_SHA256, DIRECTED_FILE: DIRECTED_SHA256},
          "unsupported private source preparation contract.")
    _need(projection.get("scope", {}).get("accessions") == _cohort(snapshot)
          and projection["scope"].get("snapshot_sha256") == snapshot["content_sha256"]
          and baseline_graph.get("snapshot_sha256") == snapshot["content_sha256"],
          "publication does not bind exactly this primary snapshot cohort.")
    nodes = {n["id"] for n in baseline_graph["nodes"] if n.get("category") == "biolink:Protein"}
    pairs = defaultdict(list)
    for edge in baseline_graph["edges"]:
        if (edge.get("record_kind") == "protein_interaction" and edge["subject"] != edge["object"]
                and not edge.get("extension_source_kind")):
            pairs[tuple(sorted((edge["subject"], edge["object"])))].append(edge["id"])
    observations = []
    for source in projection["observations"]:
        row = deepcopy(source)
        key = tuple(row["products"])
        _need(set(key) <= nodes and key in pairs, "context endpoints must form an already represented baseline interaction pair.")
        row["baseline_pair_edge_ids"] = sorted(pairs[key])
        row["baseline_pair_pointer_scope"] = "existing_endpoint_annotation_only_not_exact_study_reuse_proof"
        row["graph_edge_id"] = None
        row["source_publication_sha256"] = manifest["content_sha256"]
        row["integration_state"] = "context_only_for_existing_primary_pair"
        for locator in row["source_locators"]:
            locator["locator"] = PREFIX + locator["locator"]
        observations.append(row)
    return {"nodes": [], "edges": [], "observations": observations,
        "summary": {**deepcopy(projection["summary"]), "publication_sha256": manifest["content_sha256"],
            "source_release": RELEASE, "additional_source_records": 0, "new_workspace_pairs": 0,
            "context_only_observations": len(observations), "source_license": deepcopy(SOURCE_LICENSE),
            "limitations": list(LIMITATIONS)}}
