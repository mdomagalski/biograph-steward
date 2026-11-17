"""Preserve source-qualified SIGNOR regulation for an exact Pharos cohort.

SIGNOR's Oct2026 stable table has 27 columns and t/f directness. Existing
pypath/INDRA processed readers inspected during source review expect YES and
INDRA's file reader expects a SCORE column absent from this release. This
narrow standard-library reader retains the actual released fields, including
self-regulation and all context literals. Experimental organism is separate
from the exact human-protein cohort: SIGNOR maps animal evidence to human
orthologues. It synthesizes no causal mechanism,
score, clinical claim, or independent experimental support.
"""
from collections import Counter
from copy import deepcopy
import csv
import hashlib
from html import escape
from io import StringIO
import json
from pathlib import Path
import re

from .assay_attachment import _capture, _decode, _ordinary, _sealed
from .client import digest, utcnow, write_json
from .file_utils import new_output

FORMAT = "biograph-steward.signor-source-publication.v2"
PROJECTION_FORMAT = "biograph-steward.signor-source-projection.v2"
INTAKE_FORMAT = "biograph-steward.signor-source-intake.v2"
POLICY = "signor4-oct2026-exact-primary-cohort-all-source-organisms.v2"
RELEASE = "Oct2026"
SOURCE_URL = "https://www.signor.uniroma2.it/releases/Oct2026_release.txt"
RELEASE_SHA256 = "63db6f65e9148e81354f564c3c3cdfc9ee45dc421553bd0926e5fae511ef9d06"
PREDICATE = "biograph:source_reported_causal_relation"
PREFIX = "extension_sources/signor/"
RAW_FILE = "source/Oct2026_release.txt"
INTAKE_FILE = "source/intake.json"
PUBMED_FILE = "source/pubmed.xml"
ACCESSION = re.compile(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?\Z")
COLUMNS = tuple("ENTITYA TYPEA IDA DATABASEA ENTITYB TYPEB IDB DATABASEB EFFECT MECHANISM RESIDUE SEQUENCE TAX_ID CELL_DATA TISSUE_DATA MODULATOR_COMPLEX TARGET_COMPLEX MODIFICATIONA MODASEQ MODIFICATIONB MODBSEQ PMID DIRECT NOTES ANNOTATOR SENTENCE SIGNOR_ID".split())
SOURCE_LICENSE = {"source": "SIGNOR 4.0, Oct2026 stable release", "license": "CC-BY-4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "source_terms_url": "https://signor.uniroma2.it/about/",
    "citation": "Lo Surdo et al. SIGNOR 4.0: the 2025 update with focus on phosphorylation data. Nucleic Acids Research 54:D682–D690 (2026). doi:10.1093/nar/gkaf1237.",
    "note": "Attribute SIGNOR and the Oct2026 release. Source qualification and exact-cohort selection are added by BioGraph Steward."}
CITATIONS = [{"id": "doi:10.1093/nar/gkaf1237", "url": "https://doi.org/10.1093/nar/gkaf1237",
    "role": "resource_publication", "pmid": "41243950"},
    {"id": "https://signor.uniroma2.it/documentation/SIGNOR_curation_manual_July_2021.docx",
     "url": "https://signor.uniroma2.it/documentation/SIGNOR_curation_manual_July_2021.docx",
     "role": "source_field_definitions", "sections": ["About proteins", "Organism, cell lines/tissues"],
     "inspected_sha256": "b30491b1d61cbca8ede75c7b188bd5865c81fbbf793663d4931cd1b7fb3a2e28"}]
PARTICIPANT_TAXON_BASIS = ("Exact membership in the supplied primary Pharos human-protein cohort; "
    "SIGNOR represents animal-model relations on human orthologue proteins. Source TAX_ID is not the participant-taxonomy basis.")
LIMITATIONS = [
    "These are source-reported regulatory relations, not independently validated colorectal-cancer mechanisms or treatment recommendations.",
    "Effect, mechanism, residue, cell and tissue fields retain their source literals; phosphorylation alone does not imply activation.",
    "Source-reported directness does not independently establish physical binding; unknown directness is never converted to false.",
    "Empty experimental context means unreported, not context-independent or colorectal-specific evidence.",
    "Source TAX_ID reports the supporting experimental organism; -1 denotes in-vitro experiments in the source manual. It does not establish participant taxonomy or a verified assay host.",
    "Animal-model source claims may be mapped to human orthologues. Exact human-cohort endpoints do not prove that an effect was demonstrated in humans.",
    "Self-regulatory records are retained separately from nonself protein-pair counts; protein families, complexes and isoforms are not expanded or collapsed.",
    "A missing selected row does not establish that a regulatory relationship is absent.",
    "SIGNOR and Pharos may reuse publications or upstream resources. Source records and source counts are not independent experimental support.",
    "The stable source file contains no SCORE column; no source score or confidence formula is imputed.",
    "Relevant MI2CAST/CausalTAB source fields are preserved; this local projection does not claim full standard conformance.",
    "Publication types and correction notices are source metadata; absence of a Review label does not establish primary experimental evidence or an uncorrected result.",
    "Residue and sequence fields retain source coordinates; exact accession identity does not establish sequence, isoform or construct equivalence.",
]


def _need(condition, message):
    if not condition:
        raise ValueError("SIGNOR source: " + message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _accessions(value):
    _need(isinstance(value, list) and 1 <= len(value) <= 250
          and all(isinstance(uid, str) and ACCESSION.fullmatch(uid) for uid in value)
          and value == sorted(set(value)),
          "expected 1–250 unique sorted exact primary-cohort accessions.")
    return value


def _cohort(snapshot):
    _need(_sealed(snapshot) and snapshot.get("data_kind") == "live_pharos",
          "expected a sealed live Pharos snapshot.")
    rows = snapshot.get("targets")
    _need(isinstance(rows, list) and all(isinstance(row, dict) and isinstance(row.get("uniprot"), str)
          for row in rows), "snapshot primary target identities are missing.")
    identifiers = [row["uniprot"] for row in rows]
    _need(len(identifiers) == len(set(identifiers)), "snapshot primary identities repeat.")
    return _accessions(sorted(identifiers))


def _experimental_organism(raw):
    """Retain the source's organism code without inferring an actual assay host."""
    if raw == "-1":
        state, taxon = "source_reported_in_vitro", None
    elif raw == "":
        state, taxon = "unreported", None
    elif re.fullmatch(r"[1-9][0-9]*", raw):
        state, taxon = "source_reported_taxon", "NCBITaxon:" + raw
    else:
        state, taxon = "raw_unresolved", None
    return {"source_experimental_organism_raw": raw, "source_experimental_taxon": taxon,
        "source_experimental_organism_reporting_state": state}


def parse_release(raw, accessions):
    """Parse the exact stable schema, preserving every selected raw field.

    This pure parser accepts synthetic fixtures. Publishing additionally binds
    the full bytes to RELEASE_SHA256; a self-declared source URL is insufficient.
    Record ordinals count CSV data records, not physical lines or publications.
    """
    accessions = set(_accessions(accessions))
    _need(isinstance(raw, bytes) and len(raw) <= 64 * 1024 * 1024,
          "source must be bounded UTF-8 bytes.")
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8"), newline=""), delimiter="\t", strict=True)
        _need(reader.fieldnames == list(COLUMNS), "expected the exact 27-column Oct2026 source schema.")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("SIGNOR source: invalid UTF-8/TSV source.") from exc
    _need(all(set(row) == set(COLUMNS) and all(isinstance(v, str) for v in row.values()) for row in rows),
          "malformed source record.")
    selected, states, seen = [], Counter(), set()
    for ordinal, row in enumerate(rows, 1):
        if row["TYPEA"] != "protein" or row["TYPEB"] != "protein":
            state = "nonprotein_participant"
        elif row["DATABASEA"] != "UNIPROT" or row["DATABASEB"] != "UNIPROT":
            state = "non_uniprot_namespace"
        elif not all(ACCESSION.fullmatch(row[key]) for key in ("IDA", "IDB")):
            state = "nonexact_accession"
        elif not all(row[key] in accessions for key in ("IDA", "IDB")):
            state = "outside_primary_cohort"
        else:
            state = "selected_primary_cohort_protein_regulation"
            _need(row["DIRECT"] in {"t", "f"}, "unknown directness literal in a selected source record.")
            _need(row["PMID"].isascii() and row["PMID"].isdigit() and int(row["PMID"]) > 0,
                  "selected record requires an exact numeric source PMID.")
            _need(bool(re.fullmatch(r"SIGNOR-[0-9]+", row["SIGNOR_ID"]))
                  and row["SIGNOR_ID"] not in seen, "missing or repeated selected source record identity.")
            seen.add(row["SIGNOR_ID"])
            selected.append({"source_record_id": row["SIGNOR_ID"], "source_data_record_ordinal": ordinal,
                "products": ["UniProtKB:" + row["IDA"], "UniProtKB:" + row["IDB"]],
                "self_regulation": row["IDA"] == row["IDB"],
                "source_reported_direct": row["DIRECT"] == "t", **_experimental_organism(row["TAX_ID"]),
                "source_row": deepcopy(row)})
        states[state] += 1
    return {"source_rows": len(rows), "row_states": dict(sorted(states.items())), "records": selected}


def _projection(files):
    _need({RAW_FILE, INTAKE_FILE} <= set(files), "preserved release and intake are required.")
    intake = _decode(files[INTAKE_FILE])
    raw = files[RAW_FILE]
    _need(_sealed(intake) and intake.get("format") == INTAKE_FORMAT and intake.get("policy") == POLICY
          and intake.get("source_url") == SOURCE_URL and intake.get("source_release") == RELEASE
          and intake.get("source_sha256") == RELEASE_SHA256 == _sha(raw)
          and intake.get("source_bytes") == len(raw)
          and bool(re.fullmatch(r"[0-9a-f]{64}", str(intake.get("snapshot_sha256", "")))),
          "source release bytes, exact cohort intake or interpretation policy changed.")
    accessions = _accessions(intake.get("accessions"))
    parsed = parse_release(raw, accessions)
    publication_metadata = {}
    metadata_sha = intake.get("pubmed_xml_sha256")
    if metadata_sha is not None:
        from .literature import parse_pubmed
        _need(PUBMED_FILE in files and len(files[PUBMED_FILE]) <= 20_000_000
              and metadata_sha == _sha(files[PUBMED_FILE]), "preserved PubMed metadata bytes changed.")
        metadata = parse_pubmed(files[PUBMED_FILE])
        expected = {record["source_row"]["PMID"] for record in parsed["records"]}
        _need(expected <= set(metadata), "optional PubMed metadata must cover every selected source PMID.")
        for pmid in sorted(expected, key=int):
            paper = metadata[pmid]
            publication_metadata[pmid] = {key: deepcopy(paper.get(key)) for key in
                ("pmid", "pmcid", "doi", "title", "publication_types", "correction_types")}
            publication_metadata[pmid].update(metadata_status="available", primary_experimental_evidence="not_assessed",
                source_format="PubMed XML", source_sha256=metadata_sha,
                source_locator=PUBMED_FILE + "#PubmedArticle[PMID=" + pmid + "]",
                interpretation="Publication types and linked publication notices are metadata, not an assay-quality verdict. Comment links are not necessarily corrections; absence of a Review label does not establish primary experimental evidence.")
    else:
        _need(PUBMED_FILE not in files, "PubMed metadata exists without an intake binding.")
    observations = []
    for record in parsed["records"]:
        row = record["source_row"]
        oid = "signor.observation:" + digest({"source_sha256": RELEASE_SHA256,
            "source_record_id": row["SIGNOR_ID"], "data_record_ordinal": record["source_data_record_ordinal"]})[:24]
        observations.append({"id": oid, **deepcopy(record), "source_kind": "signor",
            "source": {"kind": "signor", "release": RELEASE, "url": SOURCE_URL},
            "source_release": RELEASE, "local_review_state": "candidate", "participant_taxon": "NCBITaxon:9606",
            "participant_taxon_basis": PARTICIPANT_TAXON_BASIS,
            "assay_host_taxon": None, "assay_host_taxon_basis": "Not inferred; the source-reported experimental organism remains a separate field.",
            "effect_literal": row["EFFECT"], "mechanism_literal": row["MECHANISM"],
            "direct_literal": row["DIRECT"], "cell_context_raw": row["CELL_DATA"],
            "tissue_context_raw": row["TISSUE_DATA"],
            "cell_context_reporting": "reported" if row["CELL_DATA"] else "unreported",
            "tissue_context_reporting": "reported" if row["TISSUE_DATA"] else "unreported",
            "residue_raw": row["RESIDUE"], "sequence_raw": row["SEQUENCE"],
            "supporting_sentence_raw": row["SENTENCE"], "publications": ["PMID:" + row["PMID"]],
            "publication_metadata": [deepcopy(publication_metadata[row["PMID"]])] if row["PMID"] in publication_metadata else [],
            "primary_experimental_evidence": "not_assessed",
            "citations": [{"id": "PMID:" + row["PMID"],
                "url": "https://pubmed.ncbi.nlm.nih.gov/" + row["PMID"] + "/", "role": "source_reported_support"},
                *deepcopy(CITATIONS)],
            "source_locators": [{"locator": RAW_FILE + "#data-record=" + str(record["source_data_record_ordinal"]),
                "file_sha256": RELEASE_SHA256, "role": "original_source_data_record"}],
            "biologically_validated": False, "independent_evidence_count": None,
            "interpretation": "Source-reported regulation on exact human-cohort proteins with literal effect/mechanism and experimental-organism context; no inferred human/CRC effect or independent validation."})
    pairs = {tuple(sorted(record["products"])) for record in observations if not record["self_regulation"]}
    summary = {"source_kind": "signor", "source_release": RELEASE, "requested_primary_accessions": len(accessions),
        "source_rows": parsed["source_rows"], "source_row_states": parsed["row_states"],
        "qualified_regulatory_observations": len(observations), "distinct_nonself_pairs": len(pairs),
        "self_regulatory_records": sum(r["self_regulation"] for r in observations),
        "self_regulatory_participants": len({r["products"][0] for r in observations if r["self_regulation"]}),
        "cell_context_reported_records": sum(bool(r["cell_context_raw"]) for r in observations),
        "tissue_context_reported_records": sum(bool(r["tissue_context_raw"]) for r in observations),
        "direct_literal_counts": dict(sorted(Counter(r["direct_literal"] for r in observations).items())),
        "source_experimental_organism_raw_counts": dict(sorted(Counter(r["source_experimental_organism_raw"] for r in observations).items())),
        "source_experimental_organism_reporting_state_counts": dict(sorted(Counter(r["source_experimental_organism_reporting_state"] for r in observations).items())),
        "participant_taxon": "NCBITaxon:9606", "participant_taxon_basis": PARTICIPANT_TAXON_BASIS,
        "source_experimental_organisms_used_for_selection": False,
        "assay_host_taxon_inferred": False,
        "selected_publication_pmids": len({r["source_row"]["PMID"] for r in observations}),
        "publication_metadata_available_pmids": len(publication_metadata),
        "publication_metadata_marked_review_pmids": sum("Review" in paper["publication_types"] for paper in publication_metadata.values()),
        "publication_metadata_with_linked_notices_pmids": sum(bool(paper["correction_types"]) for paper in publication_metadata.values()),
        "publication_metadata_with_erratum_in_pmids": sum("ErratumIn" in paper["correction_types"] for paper in publication_metadata.values()),
        "publication_metadata_with_retraction_notice_pmids": sum(bool(set(paper["correction_types"]) & {"RetractionIn", "RetractionOf"}) for paper in publication_metadata.values()),
        "primary_experimental_evidence_assessed": False,
        "independent_evidence_count": None, "automatic_acceptance_performed": False,
        "automatic_pruning_performed": False, "biological_validation_performed": False}
    value = {"format": PROJECTION_FORMAT, "policy": POLICY, "source_kind": "signor", "source_release": RELEASE,
        "scope": {"kind": "exact_primary_snapshot_cohort", "accessions": accessions,
            "snapshot_sha256": intake["snapshot_sha256"], "self_regulation_retained": True,
            "experimental_organisms": "all_source_reported_values_retained_without_selection",
            "family_complex_or_isoform_expansion": False},
        "bindings": {"source_sha256": RELEASE_SHA256, "intake_content_sha256": intake["content_sha256"],
            "snapshot_sha256": intake["snapshot_sha256"], "pubmed_xml_sha256": metadata_sha},
        "publication_metadata": publication_metadata,
        "observations": observations, "summary": summary, "source_license": deepcopy(SOURCE_LICENSE),
        "citations": deepcopy(CITATIONS), "limitations": list(LIMITATIONS)}
    value["content_sha256"] = digest(value)
    return value


def publish_release(source, snapshot, output, *, pubmed_xml=None):
    """Package the already-retrieved official release; no network/model/graph edits."""
    source = Path(source).absolute()
    raw = _ordinary(source)
    _need(_sha(raw) == RELEASE_SHA256, "expected the pinned complete official Oct2026 release bytes.")
    accessions = _cohort(snapshot)
    intake = {"format": INTAKE_FORMAT, "policy": POLICY, "source_release": RELEASE,
        "source_url": SOURCE_URL, "source_sha256": RELEASE_SHA256, "source_bytes": len(raw),
        "accessions": accessions, "snapshot_sha256": snapshot["content_sha256"]}
    material = {RAW_FILE: raw}
    if pubmed_xml is not None:
        material[PUBMED_FILE] = _ordinary(pubmed_xml)
        intake["pubmed_xml_sha256"] = _sha(material[PUBMED_FILE])
    intake["content_sha256"] = digest(intake)
    material[INTAKE_FILE] = (json.dumps(intake, indent=2, ensure_ascii=False) + "\n").encode()
    projection = _projection(material)
    folder = new_output(output, source, *((pubmed_xml,) if pubmed_xml is not None else ()))
    for name, data in material.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_json(folder / "projection.json", projection)
    (folder / "LICENSE.txt").write_text("SIGNOR 4.0 Oct2026 source data: CC BY 4.0.\n"
        + SOURCE_LICENSE["citation"] + "\nhttps://creativecommons.org/licenses/by/4.0/\n"
        "https://signor.uniroma2.it/about/\nBioGraph Steward adds exact-cohort source qualification.\n")
    (folder / "index.html").write_text("<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>SIGNOR source qualification</title><h1>SIGNOR 4.0 regulatory source records</h1>"
        "<p>Directed, source-qualified observations. All effects, mechanisms and experimental contexts are reported source values; no colorectal applicability is inferred.</p>"
        "<pre>" + escape(json.dumps(projection["summary"], indent=2)) + "</pre>"
        "<p>Self-regulatory records are retained. Unreported context is unknown. Source records are candidate evidence, not independent validation.</p>"
        "<a href='projection.json'>Complete raw-field projection and provenance</a></html>")
    files = {p.relative_to(folder).as_posix(): _sha(p.read_bytes()) for p in sorted(folder.rglob("*")) if p.is_file()}
    manifest = {"format": FORMAT, "policy": POLICY, "created_at": utcnow(), "source_kind": "signor",
        "source_release": RELEASE, "bindings": deepcopy(projection["bindings"]),
        "projection_content_sha256": projection["content_sha256"], "summary": deepcopy(projection["summary"]),
        "source_license": deepcopy(SOURCE_LICENSE), "citations": deepcopy(CITATIONS), "files": files,
        "baseline_modified": False, "automatic_pruning": False, "independent_validation_performed": False,
        "standard_conformance_claimed": False, "model_calls": 0}
    manifest["content_sha256"] = digest(manifest)
    write_json(folder / "publication.json", manifest)
    return load_publication(folder)[0]


def load_publication(path):
    """Verify saved bytes and reproject the exact raw release without retrieval."""
    manifest, files = _capture(path, "publication.json")
    _need(manifest.get("format") == FORMAT and manifest.get("policy") == POLICY
          and manifest.get("source_kind") == "signor" and manifest.get("source_release") == RELEASE
          and manifest.get("model_calls") == 0 and all(manifest.get(key) is False for key in
          ("baseline_modified", "automatic_pruning", "independent_validation_performed", "standard_conformance_claimed")),
          "unsupported source publication contract.")
    _need({RAW_FILE, INTAKE_FILE, "projection.json", "LICENSE.txt", "index.html"} <= set(files),
          "publication is incomplete.")
    projection = _projection(files)
    _need(_decode(files["projection.json"]) == projection
          and manifest.get("projection_content_sha256") == projection["content_sha256"]
          and manifest.get("summary") == projection["summary"]
          and manifest.get("bindings") == projection["bindings"]
          and manifest.get("source_license") == SOURCE_LICENSE and manifest.get("citations") == CITATIONS,
          "publication differs from exact raw source parser replay.")
    return manifest, projection, files


def prepare(snapshot, baseline_graph, manifest, projection):
    """Prepare candidate records between exact primary nodes; never mutate inputs."""
    _need(_sealed(manifest) and _sealed(projection) and manifest.get("format") == FORMAT
          and manifest.get("policy") == projection.get("policy") == POLICY
          and projection.get("format") == PROJECTION_FORMAT
          and manifest.get("projection_content_sha256") == projection.get("content_sha256")
          and manifest.get("bindings") == projection.get("bindings")
          and manifest.get("summary") == projection.get("summary")
          and manifest.get("source_license") == projection.get("source_license") == SOURCE_LICENSE,
          "preparation requires a matching verified source publication.")
    _need(manifest.get("source_kind") == projection.get("source_kind") == "signor"
          and manifest.get("source_release") == projection.get("source_release") == RELEASE
          and manifest.get("model_calls") == 0 and all(manifest.get(key) is False for key in
          ("baseline_modified", "automatic_pruning", "independent_validation_performed", "standard_conformance_claimed")),
          "unsupported source preparation contract.")
    accessions = _cohort(snapshot)
    _need(projection.get("scope", {}).get("accessions") == accessions
          and projection["scope"].get("snapshot_sha256") == snapshot["content_sha256"]
          and baseline_graph.get("snapshot_sha256") == snapshot["content_sha256"],
          "publication does not bind exactly this primary snapshot cohort.")
    primary = {"UniProtKB:" + uid for uid in accessions}
    nodes = {node["id"] for node in baseline_graph["nodes"] if node.get("category") == "biolink:Protein"}
    old_pairs = {tuple(sorted((edge["subject"], edge["object"]))) for edge in baseline_graph["edges"]
        if edge.get("record_kind") == "protein_interaction" and edge["subject"] != edge["object"]}
    observations, edges, new_pairs, existing_pairs = [], [], set(), set()
    for original in projection["observations"]:
        row = deepcopy(original)
        a, b = row["products"]
        _need({a, b} <= primary, "source projection contains an endpoint outside the primary cohort.")
        pair = tuple(sorted((a, b)))
        row["baseline_nonself_pair_present"] = pair in old_pairs if a != b else None
        row["graph_edge_id"] = None
        row["source"].update(publication_sha256=manifest["content_sha256"], locator_base=PREFIX,
                             license=deepcopy(SOURCE_LICENSE))
        row["source_publication_sha256"] = manifest["content_sha256"]
        for locator in row["source_locators"]:
            locator["locator"] = PREFIX + locator["locator"]
        for paper in row["publication_metadata"]:
            paper["source_locator"] = PREFIX + paper["source_locator"]
        if not {a, b} <= nodes:
            row["integration_state"] = "endpoint_outside_resolved_cohort"
        else:
            state = ("source_reported_self_regulation" if a == b else
                "additional_causal_source_record_for_existing_pair" if pair in old_pairs else
                "new_nonself_workspace_pair")
            row["integration_state"] = state
            if a != b:
                (existing_pairs if pair in old_pairs else new_pairs).add(pair)
            eid = "edge:" + digest({"publication": manifest["content_sha256"], "observation": row["id"],
                "snapshot": snapshot["content_sha256"]})[:20]
            row["graph_edge_id"] = eid
            # Assertion identity uses the established text/null qualifier contract.
            # Complete raw values and explicit booleans remain in the immutable
            # source observation, bound here by observation_id.
            qualifiers = {"regulatory_effect": row["effect_literal"] or None,
                "regulatory_mechanism": row["mechanism_literal"] or None,
                "source_directness": row["direct_literal"],
                "cell_line": row["cell_context_raw"] or None,
                "tissue": row["tissue_context_raw"] or None,
                "residue": row["residue_raw"] or None, "sequence": row["sequence_raw"] or None,
                "observation_id": row["id"], "species": "NCBITaxon:9606",
                "evidence_type": "SIGNOR4.0source_reported_regulation"}
            edges.append({"id": eid, "subject": a, "predicate": PREDICATE, "object": b,
                "record_kind": "source_regulatory_observation", "symmetric": False,
                "qualifiers": qualifiers, "status": "passed_structural_checks", "review_reasons": [],
                "lifecycle_state": "candidate", "local_review_state": "candidate",
                "aggregator": "SIGNOR", "primary_source_raw": "SIGNOR 4.0", "evidence_sources": ["SIGNOR"],
                "reference_raw": SOURCE_URL, "publications": deepcopy(row["publications"]),
                "evidence_raw": row["supporting_sentence_raw"], "source_scores_raw": {},
                "evidence_record": deepcopy(row), "observation": deepcopy(row),
                "record_locators": [entry["locator"] for entry in row["source_locators"]],
                "source_record_count": 1, "duplicate_count": 0, "source_publication_sha256": manifest["content_sha256"],
                "extension_source_kind": "signor", "extension_publication_sha256": manifest["content_sha256"],
                "snapshot_sha256": snapshot["content_sha256"], "data_kind": "published_database_annotations",
                "biologically_validated": False,
                "retrieval_provenance": {"aggregator": "SIGNOR", "database_version": RELEASE,
                    "source_url": SOURCE_URL, "source_sha256": RELEASE_SHA256,
                    "source_responses": [PREFIX + RAW_FILE] + ([PREFIX + PUBMED_FILE] if row["publication_metadata"] else []),
                    "publication_metadata_sha256": projection["bindings"].get("pubmed_xml_sha256"),
                    "source_data_record_ordinal": row["source_data_record_ordinal"]},
                "normalization_notes": list(LIMITATIONS)})
        observations.append(row)
    summary = {**deepcopy(projection["summary"]), "publication_sha256": manifest["content_sha256"],
        "additional_source_records": len(edges), "new_workspace_pairs": len(new_pairs),
        "new_nonself_workspace_pairs": len(new_pairs),
        "existing_workspace_pairs_with_new_source_record": len(existing_pairs),
        "new_pair_source_records": sum(o["integration_state"] == "new_nonself_workspace_pair" for o in observations),
        "existing_pair_source_records": sum(o["integration_state"] == "additional_causal_source_record_for_existing_pair" for o in observations),
        "integrated_self_regulatory_records": sum(o["integration_state"] == "source_reported_self_regulation" for o in observations),
        "integration_state_counts": dict(sorted(Counter(o["integration_state"] for o in observations).items())),
        "extension_nodes_added": 0, "extension_edges_added": len(edges), "primary_Pharos_targets_added": 0,
        "primary_Pharos_records_modified": 0, "baseline_snapshot_sha256": snapshot["content_sha256"],
        "source_license": deepcopy(SOURCE_LICENSE), "limitations": list(LIMITATIONS)}
    return {"nodes": [], "edges": sorted(edges, key=lambda e: e["id"]),
        "observations": observations, "summary": summary}
