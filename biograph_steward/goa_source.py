"""Publish native GOA additions with the complete, replayable GO census frame.

The publication preserves current GAF annotations rather than rewriting old
Pharos claims.  Its compact proof includes every original/retained GO edge,
the complete native GOA sidecar and ontology, and the unchanged census outputs.
Historical implementation pins are metadata; source bytes and current method
replay establish the local integrity/selection contract, not scientific truth.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote

from . import gold_packet, go_ontology_qualification as ontology, go_qualification
from .assay_attachment import _capture, _decode, _ordinary, _sealed
from .client import canonical, digest, utcnow, write_json
from .file_utils import new_output, sha
from .go_context_inspection import load_go_context, REPORT as CONTEXT_REPORT, FILES as CONTEXT_FILES
from .graph import UNIPROT, verify_snapshot
from .normalization import GO_CATEGORIES

FORMAT = "biograph-steward.native-goa-source-publication.v1"
PROJECTION_FORMAT = "biograph-steward.native-goa-source-projection.v1"
INTAKE_FORMAT = "biograph-steward.native-goa-source-intake.v1"
POLICY = "complete-go-frame-explicit-active-replacement-native-annotations.v1"
PREDICATE = "biograph:has_native_go_annotation"
PREFIX = "extension_sources/goa/"
INTAKE = "source/intake.json"
BASE_GO = "source/baseline_go_edges.json"
RETAINED_GO = "source/retained_go_edges.json"
PROPOSALS = "source/replacement_proposals.json"
ONTOLOGY = "source/ontology/source.json.gz"
ONTOLOGY_BINDING = "source/ontology/binding.json"
CENSUS = "source/census/"
CONTEXT = "source/context/"
CENSUS_OUTPUTS = ("proposal_audit.jsonl", "concept_audit.jsonl",
                  "qualified_nonduplicate_native_records.jsonl", "qualified_recoveries.gaf")
SOURCE_LICENSE = {"source": "Gene Ontology / UniProt GOA native annotations",
    "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "source_terms_url": "https://geneontology.org/docs/go-citation-policy/",
    "note": "Attribute Gene Ontology, UniProt GOA and the assigning databases. Native annotation bodies remain unchanged; BioGraph Steward adds cohort/census qualification."}
LIMITATIONS = [
    "These are separately sourced current GOA annotations, not repaired historical Pharos records or new biological discoveries.",
    "Experimental evidence codes describe native curator annotations; they are not this project's independent verification of the cited experiments.",
    "Native source relations, references, product forms and source dates belong to their own records; missing old qualifiers and review states are not inherited.",
    "The source and Pharos can reuse evidence. Reference aliases on one GAF line are not independent studies or corroborating votes.",
    "Exact human-protein cohort membership does not make every GO annotation colorectal-cancer-specific.",
    "Unmatched or excluded-context records remain unknown or outside this conservative scope, not biologically false.",
    "The pinned ontology/GAF release is explicit and is not asserted to be today's latest source.",
    "This source publication does not establish whole-graph biological accuracy, prediction gain, publisher authentication or full GO pipeline conformance.",
]


def _need(condition, message):
    if not condition:
        raise ValueError("Native GOA source: " + message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _implementation():
    from . import go_context_inspection, go_native_support, go_replacement_selection
    modules = (go_context_inspection, go_native_support, go_replacement_selection,
               go_qualification, ontology, gold_packet)
    return {str(Path(p).absolute()): sha(p) for p in
            [__file__, *(module.__file__ for module in modules)]}


def _json(files, name):
    _need(name in files, "missing preserved proof: " + name)
    return _decode(files[name])


def _jsonl(files, name):
    _need(name in files, "missing preserved inventory: " + name)
    return [_decode(line) for line in files[name].splitlines() if line]


def _go_edges(graph):
    return [deepcopy(e) for e in graph["edges"] if e.get("record_kind") == "go_annotation"]


def _cohort(snapshot):
    verify_snapshot(snapshot)
    _need(snapshot.get("data_kind") == "live_pharos", "an exact live Pharos snapshot is required.")
    ids = [row.get("uniprot") for row in snapshot["targets"]]
    _need(ids and all(isinstance(uid, str) and UNIPROT.fullmatch(uid) for uid in ids)
          and len(ids) == len(set(ids)), "primary target identities are missing or duplicated.")
    return sorted(ids)


def validate_native_record(row):
    """Reconstruct the existing full native record and reuse its fixed gate."""
    from .go_native_support import exclusion_reasons
    try:
        rebuilt = go_qualification.native_record(row["source_line"], row["raw_line"],
                    row["raw_fields"], row["parsed"], row["source_gaf_sha256"])
        _need(row == rebuilt, "native record differs from its literal 17-field reconstruction.")
        _need(row["negated"] is False and not exclusion_reasons(row),
              "native record is outside the unopposed experimental/context scope.")
        _need(row["relation_literal"] in {"enables", "contributes_to", "located_in", "part_of",
              "is_active_in", "colocalizes_with", "involved_in", "acts_upstream_of",
              "acts_upstream_of_or_within", "acts_upstream_of_positive_effect",
              "acts_upstream_of_negative_effect", "acts_upstream_of_or_within_positive_effect",
              "acts_upstream_of_or_within_negative_effect"}, "unsupported native GAF relation literal.")
    except (KeyError, TypeError) as exc:
        raise ValueError("Native GOA source: complete native annotation fields are required.") from exc
    return row


def _citation(reference):
    if re.fullmatch(r"PMID:[0-9]+", reference):
        url = "https://pubmed.ncbi.nlm.nih.gov/" + reference[5:] + "/"
    elif reference.lower().startswith("doi:"):
        url = "https://doi.org/" + quote(reference[4:], safe="/:()")
    elif re.fullmatch(r"GO_REF:[0-9]+", reference):
        url = "https://geneontology.org/references/" + reference
    else:
        url = None
    return {"id": reference, "url": url, "role": "native_annotation_reference_identifier",
            "interpretation": "Identifiers on one native GAF row can alias one cited reference."}


def _observation(native, term, origins, source):
    validate_native_record(native)
    _need(isinstance(term.get("lbl"), str) and bool(term["lbl"].strip()),
          "active GO target requires its literal ontology label.")
    return {"id": "goa.observation:" + digest({"native_record_id": native["id"],
                "gaf_sha256": native["source_gaf_sha256"]})[:24],
        "source_kind": "goa", "native_record": deepcopy(native), "subject": native["subject"],
        "go_id": native["go_id"], "go_label": term["lbl"], "go_aspect": native["aspect"],
        "relation_literal": native["relation_literal"], "evidence_code": native["evidence_code"],
        "assigned_by": native["assigned_by"], "graph_edge_id": None,
        "proposal_origin_edge_ids": sorted(origins), "local_review_state": "candidate",
        "publications": deepcopy(native["reference_identifiers"]),
        "citations": [_citation(ref) for ref in native["reference_identifiers"]],
        "source": {"kind": "goa", "url": source.get("provided_source_url"),
                   "gaf_sha256": native["source_gaf_sha256"]},
        "source_locators": [{"locator": CONTEXT + "source/annotations.gaf.gz#line=" + str(native["source_line"]),
             "file_sha256": native["source_gaf_sha256"], "role": "original_full_GAF_record"},
            {"locator": CENSUS + "qualified_nonduplicate_native_records.jsonl#id=" + native["id"],
             "role": "census_selected_native_record"}],
        "biologically_validated": False, "independent_evidence_count": None,
        "historical_qualifiers_recovered": False, "old_review_state_inherited": False,
        "interpretation": "Native curator annotation on the exact source protein; separate source, not a historical Pharos repair or CRC-specific conclusion."}


def _projection(folder, files):
    """Replay source bytes and the complete GO-frame census, never old code pins."""
    from . import go_replacement_selection as census_method
    intake = _json(files, INTAKE)
    _need(_sealed(intake) and intake.get("format") == INTAKE_FORMAT
          and intake.get("policy") == POLICY, "intake seal or policy differs.")
    census = _json(files, CENSUS + "report.json")
    _need(_sealed(census) and census.get("format") == census_method.FORMAT
          and census.get("census_complete") is True
          and census.get("census_is_independent_truth_evaluation") is False
          and all(census.get(k) is False for k in ("source_graph_changed", "retained_graph_changed",
                                                  "proposals_applied", "review_states_inherited"))
          and census.get("method") == census_method.METHOD
          and _sha(files[CENSUS + "report.json"]) == intake.get("census_file_sha256"),
          "original census receipt or scientific scope differs.")
    _need(set(census.get("files", {})) == set(CENSUS_OUTPUTS)
          and all(_sha(files[CENSUS + name]) == pin for name, pin in census["files"].items()),
          "census output inventory or bytes differ.")
    expected_names = {INTAKE, BASE_GO, RETAINED_GO, PROPOSALS, ONTOLOGY, ONTOLOGY_BINDING,
                      CENSUS + "report.json", *(CENSUS + n for n in CENSUS_OUTPUTS),
                      *(CONTEXT + n for n in CONTEXT_FILES), CONTEXT + CONTEXT_REPORT}
    _need(set(files) == expected_names, "compact GO proof inventory differs.")
    for stored, original in intake.get("historical_source_paths", {}).items():
        _need(stored in files and original in census["input_files_sha256"]
              and _sha(files[stored]) == census["input_files_sha256"][original],
              "preserved original source bytes differ from the historical census pin.")
    required_historical = {PROPOSALS, ONTOLOGY, CONTEXT + CONTEXT_REPORT,
                           *(CONTEXT + n for n in CONTEXT_FILES)}
    _need(set(intake.get("historical_source_paths", {})) == required_historical,
          "complete original data-source bindings are required.")
    base, retained = _json(files, BASE_GO), _json(files, RETAINED_GO)
    _need(isinstance(base, list) and base and isinstance(retained, list)
          and all(isinstance(e, dict) and e.get("record_kind") == "go_annotation" for e in [*base, *retained])
          and len({e["id"] for e in base}) == len(base)
          and len({e["id"] for e in retained}) == len(retained), "complete GO edge inventories are malformed.")
    _need(digest(base) == intake.get("baseline_go_edges_sha256")
          and digest(retained) == intake.get("retained_go_edges_sha256"), "GO frame binding changed.")
    context, native, compatibilities = load_go_context(Path(folder) / "source/context")
    _need(context["source"] == census["native_source"]
          and context["packet_id"] == census["packet_id"] == intake.get("original_packet_id")
          and context["graph_sha256"] == census["baseline_graph_sha256"] == intake.get("original_graph_sha256")
          and context["snapshot_sha256"] == intake.get("snapshot_sha256"), "source/census frame identity differs.")
    _need(go_qualification.project_compatibilities({"edges": base}, native) == compatibilities,
          "stored full GO frame does not match the complete native context scope.")
    nodes, binding, _ = ontology.load_ontology(Path(folder) / ONTOLOGY,
                                              _json(files, ONTOLOGY_BINDING)["file_sha256"])
    _need(binding == _json(files, ONTOLOGY_BINDING) == census["ontology"], "native ontology binding differs.")
    filtered = [e for e in base if ontology.classify_term(e["object"], nodes)["decision"] != "prune"]
    _need(retained == filtered, "retained GO frame is not the complete original active/unknown-term subset.")
    proposals = _json(files, PROPOSALS)
    _need(proposals.get("applied") is False and proposals.get("ontology_sha256") == binding["file_sha256"],
          "original replacement proposal policy differs.")
    rows, concepts, additions, counts = census_method.classify(
        {"edges": base}, {"edges": retained}, proposals["proposals"], native, nodes)
    _need(counts == census["counts"]
          and rows == _jsonl(files, CENSUS + "proposal_audit.jsonl")
          and concepts == _jsonl(files, CENSUS + "concept_audit.jsonl")
          and additions == _jsonl(files, CENSUS + "qualified_nonduplicate_native_records.jsonl"),
          "complete GO census or selected recovery rows do not replay.")
    _need(files[CENSUS + "qualified_recoveries.gaf"].decode("utf-8") == census_method.candidate_gaf(
        context["source"]["headers"], additions, context["source"]["gaf_sha256"]),
        "subset GAF is not the exact selected original annotation bodies.")
    _need(additions, "no qualified nonduplicate native GO annotations to publish.")
    origins = {r["id"]: {p["original_edge_id"] for p in rows
               if r["id"] in p["eligible_positive_record_ids"]} for r in additions}
    observations = [_observation(r, nodes[r["go_id"]], origins[r["id"]], context["source"]) for r in additions]
    summary = {"source_kind": "goa", "qualified_native_records": len(additions),
        "distinct_subject_term_concepts": len({(r["subject"], r["go_id"]) for r in additions}),
        "distinct_subjects": len({r["subject"] for r in additions}),
        "relation_counts": dict(sorted(Counter(r["relation_literal"] for r in additions).items())),
        "complete_baseline_GO_edges": len(base), "complete_retained_GO_edges": len(retained),
        "replacement_proposals_audited": counts["proposals"],
        "automatic_acceptance_performed": False, "historical_records_rewritten": False,
        "biological_validation_performed": False, "independent_evidence_count": None}
    value = {"format": PROJECTION_FORMAT, "policy": POLICY, "source_kind": "goa",
        "scope": {"snapshot_sha256": intake["snapshot_sha256"], "accessions": intake["accessions"]},
        "bindings": {"census_file_sha256": intake["census_file_sha256"],
            "census_content_sha256": census["content_sha256"], "native_gaf_sha256": context["source"]["gaf_sha256"],
            "ontology": binding, "recoveries_sha256": digest(additions)},
        "baseline_go_edges": base, "observations": observations, "summary": summary,
        "source_license": deepcopy(SOURCE_LICENSE), "limitations": list(LIMITATIONS)}
    value["content_sha256"] = digest(value)
    return value


def load_publication(path):
    manifest, material = _capture(path, "publication.json")
    _need(manifest.get("format") == FORMAT and manifest.get("kind") == "goa"
          and manifest.get("policy") == POLICY and manifest.get("source_license") == SOURCE_LICENSE
          and all(manifest.get(k) is False for k in ("baseline_modified", "automatic_pruning",
              "independent_validation_performed", "standard_conformance_claimed")),
          "publication format, license or scientific policy differs.")
    _need("projection.json" in material and "LICENSE.txt" in material, "projection or source license is missing.")
    source = {name: raw for name, raw in material.items() if name.startswith("source/")}
    try:
        projection = _projection(path, source)
    except (KeyError, TypeError, UnicodeError) as exc:
        raise ValueError("Native GOA source: compact source proof is missing or malformed.") from exc
    _need(_decode(material["projection.json"]) == projection
          and manifest.get("projection_content_sha256") == projection["content_sha256"]
          and manifest.get("snapshot_sha256") == projection["scope"]["snapshot_sha256"]
          and manifest.get("summary") == projection["summary"], "saved native GOA projection does not reproduce.")
    _need(set(material) == {"publication.json", "projection.json", "LICENSE.txt", *source},
          "unexpected native GOA publication files.")
    return manifest, projection, material


def publish_recoveries(census, qualification, retained_package, context, output, *, census_sha256):
    """Create a compact complete proof from already verified, local sources."""
    implementation = _implementation()
    census, qualification, retained_package, context = map(lambda p: Path(p).absolute(),
                                                          (census, qualification, retained_package, context))
    _need(sha(census / "report.json") == census_sha256, "explicit census file pin differs.")
    old = gold_packet._read(qualification / "go_ontology_qualification.json")
    _need(gold_packet._sealed(old) and all(sha(qualification / n) == pin for n, pin in old["files"].items()),
          "original ontology qualification binding differs.")
    retained_report, retained_graph = gold_packet.load_decisions(retained_package)
    packet = gold_packet._read(retained_package / "baseline_packet/packet_manifest.json")
    baseline = gold_packet._read(retained_package / "baseline_packet/source/graph.json")
    snapshot = gold_packet._read(retained_package / "baseline_packet/source/snapshot.json")
    accessions = _cohort(snapshot)
    for report in (old, retained_report):
        _need(report["packet_id"] == packet["packet_id"] and report["graph_sha256"] == packet["graph_sha256"],
              "source qualifications do not share one original baseline.")
    proof = _decode(_ordinary(census / "report.json"))
    _need(proof.get("packet_id") == packet["packet_id"]
          and proof.get("baseline_graph_sha256") == packet["graph_sha256"]
          and proof.get("retained_graph_sha256") == retained_report["retained_graph_sha256"],
          "census does not bind the supplied original retained graph.")
    material = {CENSUS + "report.json": _ordinary(census / "report.json"),
                BASE_GO: (canonical(_go_edges(baseline)) + "\n").encode(),
                RETAINED_GO: (canonical(_go_edges(retained_graph)) + "\n").encode(),
                PROPOSALS: _ordinary(qualification / "replacement_proposals.json"),
                ONTOLOGY: _ordinary(qualification / old["ontology"]["source_file"]),
                ONTOLOGY_BINDING: (canonical(old["ontology"]) + "\n").encode()}
    origins = {PROPOSALS: str(qualification / "replacement_proposals.json"),
               ONTOLOGY: str(qualification / old["ontology"]["source_file"])}
    for name in CENSUS_OUTPUTS:
        material[CENSUS + name] = _ordinary(census / name)
    for name in (*CONTEXT_FILES, CONTEXT_REPORT):
        material[CONTEXT + name] = _ordinary(context / name)
        origins[CONTEXT + name] = str(context / name)
    intake = {"format": INTAKE_FORMAT, "policy": POLICY, "snapshot_sha256": snapshot["content_sha256"],
        "accessions": accessions, "original_packet_id": packet["packet_id"],
        "original_graph_sha256": packet["graph_sha256"], "census_file_sha256": census_sha256,
        "baseline_go_edges_sha256": digest(_go_edges(baseline)),
        "retained_go_edges_sha256": digest(_go_edges(retained_graph)), "historical_source_paths": origins}
    intake["content_sha256"] = digest(intake)
    material[INTAKE] = (canonical(intake) + "\n").encode()
    folder = new_output(output, census, qualification, retained_package, context)
    for name, raw in material.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    projection = _projection(folder, material)
    write_json(folder / "projection.json", projection)
    (folder / "LICENSE.txt").write_text("Native Gene Ontology / UniProt GOA data: CC BY 4.0.\n"
        "https://creativecommons.org/licenses/by/4.0/\nhttps://geneontology.org/docs/go-citation-policy/\n"
        "Preserve the source assigning databases, references, release and native annotation bodies.\n")
    inventory = {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*")) if p.is_file()}
    manifest = {"format": FORMAT, "kind": "goa", "policy": POLICY, "created_at": utcnow(),
        "snapshot_sha256": snapshot["content_sha256"], "projection_content_sha256": projection["content_sha256"],
        "summary": deepcopy(projection["summary"]), "source_license": deepcopy(SOURCE_LICENSE),
        "baseline_modified": False, "automatic_pruning": False, "independent_validation_performed": False,
        "standard_conformance_claimed": False, "model_calls": 0,
        "implementation_sha256": implementation, "files": inventory}
    _need(all(sha(path) == pin for path, pin in implementation.items()),
          "source replay implementation changed during publication.")
    manifest["content_sha256"] = digest(manifest)
    write_json(folder / "publication.json", manifest)
    load_publication(folder)
    return manifest


def prepare(snapshot, baseline_graph, manifest, projection):
    """Integrate separate native records; never update existing nodes or edges."""
    accessions = _cohort(snapshot)
    _need(_sealed(manifest) and manifest.get("format") == FORMAT and manifest.get("kind") == "goa"
          and _sealed(projection) and projection.get("format") == PROJECTION_FORMAT
          and projection.get("policy") == POLICY
          and manifest.get("projection_content_sha256") == projection["content_sha256"]
          and projection.get("source_license") == manifest.get("source_license") == SOURCE_LICENSE,
          "source publication/projection binding differs.")
    _need(projection["scope"] == {"snapshot_sha256": snapshot["content_sha256"], "accessions": accessions}
          and baseline_graph.get("snapshot_sha256") == snapshot["content_sha256"],
          "publication belongs to a different exact snapshot/cohort.")
    _need(_go_edges(baseline_graph) == projection["baseline_go_edges"],
          "complete baseline GO frame differs; a retained or partial frame is not an intake.")
    primary = {"UniProtKB:" + uid for uid in accessions}
    existing = {n["id"]: n for n in baseline_graph["nodes"]}
    observations, edges, added_nodes = [], [], {}
    natives = [o["native_record"] for o in projection["observations"]]
    _need(digest(natives) == projection["bindings"]["recoveries_sha256"]
          and len({n["id"] for n in natives}) == len(natives), "selected native record inventory differs.")
    for original in projection["observations"]:
        native = validate_native_record(original["native_record"])
        _need(original["subject"] == native["subject"] and original["go_id"] == native["go_id"]
              and original["go_aspect"] == native["aspect"] and original["relation_literal"] == native["relation_literal"]
              and original["publications"] == native["reference_identifiers"], "observation changes native annotation meaning.")
        subject, term = native["subject"], native["go_id"]
        _need(subject in primary and subject in existing and existing[subject].get("category") == "biolink:Protein",
              "native subject is outside the exact resolved primary protein cohort.")
        category = GO_CATEGORIES[native["aspect"]]
        if term not in existing:
            node = {"id": term, "name": original["go_label"], "category": category,
                "identifier_mapped": True, "source_identifier": term, "go_aspect": native["aspect"],
                "sym": None, "tdl": None, "url": "https://amigo.geneontology.org/amigo/term/" + term,
                "data_kind": "published_database_annotations", "source_ontology": deepcopy(projection["bindings"]["ontology"])}
            _need(term not in added_nodes or added_nodes[term] == node, "native target node metadata conflicts.")
            added_nodes[term] = node
        else:
            _need(existing[term].get("category") == category, "existing GO node category conflicts with the native aspect.")
        row = deepcopy(original)
        eid = "edge:" + digest({"publication": manifest["content_sha256"], "observation": row["id"],
                               "snapshot": snapshot["content_sha256"]})[:20]
        row["graph_edge_id"] = eid
        row["source_publication_sha256"] = manifest["content_sha256"]
        row["source"].update(publication_sha256=manifest["content_sha256"], locator_base=PREFIX,
                             license=deepcopy(SOURCE_LICENSE))
        for loc in row["source_locators"]:
            loc["locator"] = PREFIX + loc["locator"]
        qualifiers = {"go_aspect": native["aspect"], "species": "NCBITaxon:9606",
                      "go_relation": native["relation_literal"]}
        edges.append({"id": eid, "subject": subject, "predicate": PREDICATE, "object": term,
            "record_kind": "native_go_annotation", "symmetric": False, "qualifiers": qualifiers,
            "status": "passed_structural_checks", "review_reasons": [],
            "lifecycle_state": "candidate", "local_review_state": "candidate",
            "aggregator": "GOA", "primary_source_raw": native["assigned_by"],
            "evidence_sources": ["Gene Ontology", "UniProt GOA", native["assigned_by"]],
            "reference_raw": "|".join(native["reference_identifiers"]),
            "publications": deepcopy(native["reference_identifiers"]), "evidence_raw": native["evidence_code"],
            "source_scores_raw": {}, "evidence_record": deepcopy(row), "observation": deepcopy(row),
            "annotation_context": {"aspect": native["aspect"], "relation": native["relation_literal"],
                "negated": native["negated"], "extensions": native["annotation_extension_raw"],
                "evidence_code": native["evidence_code"], "gene_product_form_id": native["gene_product_form_id"]},
            "record_locators": [loc["locator"] for loc in row["source_locators"]],
            "source_record_count": 1, "duplicate_count": 0,
            "source_publication_sha256": manifest["content_sha256"], "extension_source_kind": "goa",
            "extension_publication_sha256": manifest["content_sha256"],
            "snapshot_sha256": snapshot["content_sha256"], "data_kind": "published_database_annotations",
            "biologically_validated": False,
            "retrieval_provenance": {"aggregator": "UniProt GOA", "source_url": row["source"].get("url"),
                "source_sha256": native["source_gaf_sha256"], "source_line": native["source_line"],
                "native_record_id": native["id"], "source_responses": [PREFIX + CONTEXT + "source/annotations.gaf.gz"]},
            "normalization_notes": list(LIMITATIONS)})
        observations.append(row)
    summary = {**deepcopy(projection["summary"]), "publication_sha256": manifest["content_sha256"],
        "additional_source_records": len(edges), "extension_edges_added": len(edges),
        "extension_nodes_added": len(added_nodes), "primary_Pharos_targets_added": 0,
        "primary_Pharos_records_modified": 0, "baseline_snapshot_sha256": snapshot["content_sha256"],
        "source_license": deepcopy(SOURCE_LICENSE), "limitations": list(LIMITATIONS)}
    return {"nodes": [added_nodes[k] for k in sorted(added_nodes)],
            "edges": sorted(edges, key=lambda e: e["id"]), "observations": observations, "summary": summary}
