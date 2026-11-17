"""Publish a separate native location source through the existing GOA workflow.

This fixed profile is broader than obsolete-term recovery: every eligible
positive active CC located_in row is preserved, including nonexperimental
codes. It does not use a localization benchmark or infer missing negatives.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path

from . import goa_source as goa, go_ontology_qualification as ontology, go_qualification
from .assay_attachment import _ordinary, _sealed
from .client import canonical, digest, utcnow, write_json
from .file_utils import new_output, sha
from .go_context_inspection import load_go_context, FILES, REPORT
from .graph import build_graph

PROFILE = {"policy": goa.LOCATION_POLICY, "aspect": "C", "relation_literal": "located_in",
    "positive_only": True, "active_terms_only": True, "single_human_taxon_only": True,
    "canonical_form_or_empty": True, "annotation_extension_empty": True,
    "with_from_empty": True, "evidence_codes": "all_supplied_codes",
    "ND_and_CC_root_excluded_as_noninformative": True,
    "evidence_code_semantics": "https://geneontology.org/docs/guide-go-evidence-codes/",
    "ND_rule": "https://geneontology.org/GO_REF/0000015.html",
    "with_from_note": "A conservative source profile, not a claim that other valid GAF contexts are erroneous."}
LIMITATIONS = [*goa.LIMITATIONS,
    "This all-code location profile preserves TAS, NAS and other supplied evidence codes; annotations are not all experimental.",
    "ND and the cellular-component root provide no specific supported location and are excluded, not treated as negative biology. IEA, if present, is electronic and not manually reviewed.",
    "The separate Pharos plus native-location workspace is not the retained/enriched default or a fully corrected replacement graph.",
    "No HOU or other benchmark labels, mappings or compartment predictions enter this source publication."]


def complete_scope(snapshot):
    """Require documented complete GO retrieval for every exact primary target."""
    accessions = goa._cohort(snapshot)
    rows = [r for r in snapshot.get("retrieval", {}).get("context", {}).get("targets", [])
            if r.get("family") == "go"]
    goa._need(len(rows) == len(accessions) and {r.get("uniprot") for r in rows} == set(accessions)
        and all(r.get("status") == "complete" and not r.get("issues")
                and type(r.get("retrieved")) is int and r["retrieved"] == r.get("available")
                and r.get("retained") == r["retrieved"] and r.get("excluded_by_scope", 0) == 0 for r in rows),
        "location publication requires complete original-cohort GO retrieval.")
    return accessions


def selected_records(native, nodes):
    """Keep original records; never map labels or fill an absent annotation."""
    selected = []
    for row in native:
        try:
            goa.validate_native_record(row, policy=goa.LOCATION_POLICY)
        except ValueError:
            continue
        if ontology.classify_term(row["go_id"], nodes)["state"] == "active":
            selected.append(row)
    return selected


def projection(folder, files):
    intake = goa._json(files, goa.INTAKE)
    goa._need(_sealed(intake) and intake.get("format") == goa.INTAKE_FORMAT
        and intake.get("policy") == goa.LOCATION_POLICY and intake.get("profile") == PROFILE,
        "location intake seal/profile differs.")
    expected = {goa.INTAKE, goa.BASE_GO, goa.ONTOLOGY, goa.ONTOLOGY_BINDING,
                *(goa.CONTEXT + n for n in (*FILES, REPORT))}
    goa._need(set(files) == expected, "location source inventory differs.")
    base = goa._json(files, goa.BASE_GO)
    goa._need(isinstance(base, list) and base and all(e.get("record_kind") == "go_annotation" for e in base)
        and len({e["id"] for e in base}) == len(base)
        and digest(base) == intake.get("baseline_go_edges_sha256"), "complete location GO frame differs.")
    context, native, links = load_go_context(Path(folder) / goa.CONTEXT)
    goa._need(context["snapshot_sha256"] == intake.get("snapshot_sha256")
        and context["source"] == intake.get("native_source")
        and context["graph_sha256"] == intake.get("native_context_original_graph_sha256")
        and sorted({e["subject"].removeprefix("UniProtKB:") for e in base}) == intake.get("accessions")
        and go_qualification.project_compatibilities({"edges": base}, native) == links,
        "native location context and complete primary GO scope differ.")
    nodes, binding, _ = ontology.load_ontology(Path(folder) / goa.ONTOLOGY,
        goa._json(files, goa.ONTOLOGY_BINDING)["file_sha256"])
    goa._need(binding == goa._json(files, goa.ONTOLOGY_BINDING), "location ontology binding differs.")
    selected = selected_records(native, nodes)
    goa._need(selected, "no native locations qualify for this fixed source profile.")
    observations = []
    for row in selected:
        observation = goa._observation(row, nodes[row["go_id"]], [], context["source"], policy=goa.LOCATION_POLICY)
        observation["interpretation"] = "Native GO annotation with its literal evidence code; separate source, not necessarily manually reviewed, a historical Pharos repair or a disease-specific conclusion."
        observation["source_locators"][1] = {"locator": goa.CONTEXT + "native_records.jsonl#id=" + row["id"],
            "role": "complete_cohort_native_record"}
        observations.append(observation)
    old_concepts = {(e["subject"], e["object"]) for e in base}
    concepts = {(r["subject"], r["go_id"]) for r in selected}
    summary = {"source_kind": "goa", "policy": goa.LOCATION_POLICY, "profile": deepcopy(PROFILE),
        "qualified_native_records": len(selected), "distinct_subject_term_concepts": len(concepts),
        "distinct_subjects": len({r["subject"] for r in selected}),
        "complete_primary_targets": len(intake["accessions"]),
        "primary_targets_without_qualified_location": len(set(intake["accessions"]) -
            {r["subject"].removeprefix("UniProtKB:") for r in selected}),
        "concepts_also_present_in_historical_Pharos": len(concepts & old_concepts),
        "concepts_absent_from_historical_Pharos": len(concepts - old_concepts),
        "supplied_reference_identifiers": len({ref for r in selected for ref in r["reference_identifiers"]}),
        "evidence_code_counts": dict(sorted(Counter(r["evidence_code"] for r in selected).items())),
        "native_CC_located_in_ND_or_root_rows_excluded": sum(r["aspect"] == "C"
            and r["relation_literal"] == "located_in" and (r["evidence_code"] == "ND"
            or r["go_id"] == "GO:0005575") for r in native),
        "assigning_database_counts": dict(sorted(Counter(r["assigned_by"] for r in selected).items())),
        "relation_counts": {"located_in": len(selected)}, "complete_baseline_GO_edges": len(base),
        "automatic_acceptance_performed": False, "historical_records_rewritten": False,
        "biological_validation_performed": False, "independent_evidence_count": None,
        "benchmark_inputs_used": False,
        "counts_scope": "Native rows, protein-term concepts and supplied reference identifiers; none are independent study counts."}
    value = {"format": goa.PROJECTION_FORMAT, "policy": goa.LOCATION_POLICY, "source_kind": "goa",
        "scope": {"snapshot_sha256": intake["snapshot_sha256"], "accessions": intake["accessions"]},
        "bindings": {"native_gaf_sha256": context["source"]["gaf_sha256"], "ontology": binding,
            "recoveries_sha256": digest(selected), "context_report_file_sha256": goa._sha(files[goa.CONTEXT + REPORT])},
        "baseline_go_edges": base, "observations": observations, "summary": summary,
        "source_license": deepcopy(goa.SOURCE_LICENSE), "limitations": list(LIMITATIONS)}
    value["content_sha256"] = digest(value)
    return value


def publish_locations(snapshot_file, context, ontology_file, output, *, snapshot_sha256,
                      context_sha256, ontology_sha256):
    """Publish only the source proof required by the existing GOA attachment."""
    inputs = tuple(map(lambda p: Path(p).absolute(), (snapshot_file, context, ontology_file)))
    snapshot_file, context, ontology_file = inputs
    implementation = {**goa._implementation(), str(Path(__file__).absolute()): sha(__file__)}
    goa._need(sha(snapshot_file) == snapshot_sha256 and sha(context / REPORT) == context_sha256,
              "explicit source snapshot/context pins differ.")
    snapshot = goa._decode(_ordinary(snapshot_file))
    accessions = complete_scope(snapshot)
    context_report, _, _ = load_go_context(context)
    goa._need(context_report["snapshot_sha256"] == snapshot["content_sha256"], "native context belongs to another snapshot.")
    base = goa._go_edges(build_graph(snapshot))
    _, binding, _ = ontology.load_ontology(ontology_file, ontology_sha256)
    intake = {"format": goa.INTAKE_FORMAT, "policy": goa.LOCATION_POLICY, "profile": deepcopy(PROFILE),
        "snapshot_sha256": snapshot["content_sha256"], "snapshot_file_sha256": snapshot_sha256,
        "accessions": accessions, "native_source": context_report["source"],
        "native_context_original_graph_sha256": context_report["graph_sha256"],
        "baseline_go_edges_sha256": digest(base)}
    intake["content_sha256"] = digest(intake)
    material = {goa.INTAKE: (canonical(intake) + "\n").encode(),
        goa.BASE_GO: (canonical(base) + "\n").encode(), goa.ONTOLOGY: _ordinary(ontology_file),
        goa.ONTOLOGY_BINDING: (canonical(binding) + "\n").encode(),
        **{goa.CONTEXT + n: _ordinary(context / n) for n in (*FILES, REPORT)}}
    folder = new_output(output, *inputs)
    for name, raw in material.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    projected = projection(folder, material)
    write_json(folder / "projection.json", projected)
    (folder / "LICENSE.txt").write_text("Native Gene Ontology / UniProt GOA data: CC BY 4.0.\n"
        "https://creativecommons.org/licenses/by/4.0/\nhttps://geneontology.org/docs/go-citation-policy/\n"
        "Preserve assigning databases, references, release and unchanged native annotation bodies.\n")
    manifest = {"format": goa.FORMAT, "kind": "goa", "policy": goa.LOCATION_POLICY, "created_at": utcnow(),
        "snapshot_sha256": snapshot["content_sha256"], "projection_content_sha256": projected["content_sha256"],
        "summary": projected["summary"], "source_license": deepcopy(goa.SOURCE_LICENSE),
        "baseline_modified": False, "automatic_pruning": False, "independent_validation_performed": False,
        "standard_conformance_claimed": False, "model_calls": 0, "implementation_sha256": implementation,
        "files": {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*")) if p.is_file()}}
    goa._need(all(sha(p) == pin for p, pin in implementation.items()), "publication implementation changed.")
    manifest["content_sha256"] = digest(manifest)
    write_json(folder / "publication.json", manifest)
    goa.load_publication(folder)
    return manifest
