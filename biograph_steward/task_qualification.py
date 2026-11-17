"""Offline, source-bound task eligibility using the existing Gold handoff.

This fixed profile selects source-reported direct human phosphoregulation.
It does not classify biological truth. Unknown fields remain abstentions;
explicit incompatibility removes only the exact evidence edge in a new view.
The original source packet, graph, review states and other support remain.
"""
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from . import gold_packet, signor_source
from .client import digest, utcnow, write_json
from .file_utils import new_output, sha


FORMAT = "biograph-steward.task-qualification.v1"
PROFILE = "source-reported-direct-human-phosphoregulation.v1"
ACTOR = "BioGraph Steward deterministic task qualification"
ALLOWED_MECHANISMS = frozenset({"phosphorylation", "dephosphorylation", "autophosphorylation"})
# Explicit, recognized SIGNOR mechanisms; every other literal stays unknown.
# The upstream SIGNOR mechanism map distinguishes these from phosphorylation:
# https://indra.readthedocs.io/en/latest/_modules/indra/sources/signor/processor.html
INCOMPATIBLE_MECHANISMS = frozenset({"binding", "transcriptional regulation", "acetylation",
                                     "ubiquitination", "polyubiquitination"})
# A different taxon ID may be a human-containing higher group, not another
# species. Only these already source-reviewed species establish mismatch.
INCOMPATIBLE_EXPERIMENTAL_SPECIES = {
    "10090": "Mus musculus", "9534": "Chlorocebus aethiops",
    "9823": "Sus scrofa", "10116": "Rattus norvegicus"}
TAXON_VOCABULARY_BASIS = {
    "source": "NCBI Taxonomy",
    "captured_display_resource": "biograph_steward/regulatory_context_labels.json",
    "metadata_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=taxonomy&id=9606,10090,9534,9823,10116&retmode=xml",
    "metadata_sha256": "7f71362c5804bca2dfe678d6032b4396854daa9d9f9b6a4298cafaa4307693e7",
    "taxonomy_rank_reference": "https://www.ncbi.nlm.nih.gov/datasets/docs/v2/data-processing/taxonomy-processing/taxonomy/",
    "interpretation": "Finite reviewed nonhuman species vocabulary; broader or unfamiliar taxon IDs remain unknown. "
                      "Taxon labels do not independently authenticate the source experiment."}
LIMITATIONS = [
    "Keep means eligible for this named task, not scientifically true or accepted evidence.",
    "Prune means explicitly incompatible with this task, not a false biological relation.",
    "Abstentions and all records outside this source profile remain retained.",
    "Human participant identifiers do not establish a human experiment; source TAX_ID is checked separately.",
    "The source in-vitro code -1 and unreported experimental organism remain unknown for human applicability.",
    "A different taxon ID can name a group containing humans; only the explicit reviewed nonhuman species establish task incompatibility.",
    "Source-reported directness is not purified-catalysis, physical-binding or canonical-site proof.",
    "This profile does not establish colorectal applicability or independent experimental support.",
    "No independent scientific accuracy or biological improvement is established by source-metadata agreement.",
]


def _need(condition, message):
    if not condition:
        raise ValueError("Task qualification: " + message)


def classify_source_fields(raw):
    """Classify only explicit native literals, with three-way unknown handling.

    This pure rule is not a reader. The packet operation additionally requires
    the unchanged, verified native SIGNOR publication. Missing/unknown DIRECT
    never becomes false; the current official reader still requires t/f in a
    selected Oct2026 record and is not relaxed by this classifier.
    """
    _need(isinstance(raw, Mapping), "native source fields must be an object.")
    values = {key: raw.get(key) for key in ("DIRECT", "MECHANISM", "TAX_ID")}
    _need(all(value is None or isinstance(value, str) for value in values.values()),
          "checked native fields must be literal text or unavailable.")
    incompatible, unknown = [], []
    if values["DIRECT"] == "f":
        incompatible.append("source_explicit_indirect")
    elif values["DIRECT"] != "t":
        unknown.append("source_directness_unknown")
    mechanism = values["MECHANISM"]
    if mechanism in INCOMPATIBLE_MECHANISMS:
        incompatible.append("source_mechanism_outside_phosphoregulation")
    elif mechanism not in ALLOWED_MECHANISMS:
        unknown.append("source_mechanism_unreported" if not mechanism else "source_mechanism_unrecognized")
    organism = values["TAX_ID"]
    if organism in INCOMPATIBLE_EXPERIMENTAL_SPECIES:
        incompatible.append("source_experimental_organism_other_than_human")
    elif organism != "9606":
        unknown.append("human_experiment_not_established")
    decision = "prune" if incompatible else "abstain" if unknown else "keep"
    reasons = incompatible + unknown if incompatible or unknown else ["source_fields_match_named_task"]
    return {"decision": decision, "reason_codes": reasons,
            "incompatibility_reasons": incompatible, "unknown_reasons": unknown,
            "checked_source_fields": values}


def _source_decisions(packet, manifest, graph):
    publication_path = packet / "source/extension_sources/signor"
    publication, projection, files = signor_source.load_publication(publication_path)
    _need(projection["bindings"]["snapshot_sha256"] == manifest["snapshot_sha256"],
          "SIGNOR publication belongs to another snapshot.")
    source = graph.get("evidence_extension", {}).get("sources", {}).get("signor")
    _need(isinstance(source, dict) and source.get("publication_sha256") == publication["content_sha256"],
          "graph has no matching verified SIGNOR publication.")
    native = {row["source_record_id"]: row for row in projection["observations"]}
    _need(len(native) == len(projection["observations"]), "native source record IDs repeat.")
    observations = [row for row in graph.get("extension_observations", [])
                    if row.get("source_kind") == "signor"]
    _need(len(observations) == len(native), "graph does not account for every selected native record.")
    edges = {edge["id"]: edge for edge in graph["edges"]}
    seen_records, seen_edges, trace = set(), set(), []
    for observation in observations:
        sid = observation.get("source_record_id")
        _need(sid in native and sid not in seen_records, "source observation ID is unknown or repeated.")
        seen_records.add(sid)
        original = native[sid]
        for field in ("id", "source_record_id", "source_data_record_ordinal", "source_row", "products"):
            _need(observation.get(field) == original[field], "observation differs from its native source record.")
        _need(observation.get("source_publication_sha256") == publication["content_sha256"],
              "observation source publication binding changed.")
        eid = observation.get("graph_edge_id")
        if eid is None:
            _need(observation.get("integration_state") == "endpoint_outside_resolved_cohort",
                  "an integrated source observation has no exact evidence edge.")
        else:
            _need(eid in edges and eid not in seen_edges, "source evidence edge is missing or repeated.")
            seen_edges.add(eid)
            edge = edges[eid]
            _need(edge.get("record_kind") == "source_regulatory_observation"
                  and edge.get("extension_source_kind") == "signor"
                  and edge.get("source_publication_sha256") == publication["content_sha256"]
                  and edge.get("evidence_record") == observation
                  and edge.get("observation") == observation
                  and [edge.get("subject"), edge.get("object")] == original["products"],
                  "source observation does not match its exact evidence edge.")
        result = classify_source_fields(original["source_row"])
        trace.append({"edge_id": eid, "observation_id": original["id"],
            "source_record_id": sid, "source_data_record_ordinal": original["source_data_record_ordinal"],
            "canonical_source_row_sha256": digest(original["source_row"]),
            "source_release": publication["source_release"],
            "source_sha256": projection["bindings"]["source_sha256"],
            "source_publication_sha256": publication["content_sha256"],
            "source_locator": "source/" + signor_source.PREFIX + signor_source.RAW_FILE
                              + "#data-record=" + str(original["source_data_record_ordinal"]),
            "participant_taxon": observation["participant_taxon"],
            "assay_host_taxon": observation["assay_host_taxon"],
            "projected_to_graph": eid is not None, **result})
    _need(seen_edges == {edge["id"] for edge in graph["edges"]
                         if edge.get("extension_source_kind") == "signor"},
          "a SIGNOR evidence edge has no unique native source observation.")
    bindings = {"release": publication["source_release"],
        "source_sha256": projection["bindings"]["source_sha256"],
        "source_bytes": len(files[signor_source.RAW_FILE]),
        "publication_content_sha256": publication["content_sha256"],
        "projection_content_sha256": projection["content_sha256"]}
    return trace, bindings


def qualify_task(packet, output, *, actor=ACTOR):
    """Write a new task-qualified Gold package; never modify the source packet.

    Verification is supplied by the existing Gold and native publication APIs.
    Their source-byte/parser replay and the exact record-to-edge join subsume
    the optional reviewed-source helper; no optional tools dependency is needed.
    """
    _need(isinstance(actor, str) and bool(actor.strip()) and actor.strip().casefold() != "unassigned",
          "an explicit software actor is required.")
    packet = Path(packet).absolute()
    manifest, graph = gold_packet.load_packet(packet)
    trace, bindings = _source_decisions(packet, manifest, graph)
    by_edge = {row["edge_id"]: row for row in trace if row["edge_id"] is not None}
    decisions = []
    for edge in graph["edges"]:
        result = by_edge.get(edge["id"])
        if result is None:
            decision, reason = "abstain", "outside_source_profile; not assessed by " + PROFILE
        else:
            decision = result["decision"]
            reason = (PROFILE + "; " + result["source_record_id"] + "; "
                      + ", ".join(result["reason_codes"]) + "; task eligibility only, not biological truth")
        decisions.append({"edge_id": edge["id"], "decision": decision,
                          "reason": reason, "confidence": None})
    value = {"format": gold_packet.DECISION_FORMAT, "packet_id": manifest["packet_id"],
             "method": PROFILE, "actor": actor, "decisions": decisions}
    counts = Counter(row["decision"] for row in decisions)
    source_counts = Counter(row["decision"] for row in trace if row["projected_to_graph"])
    by_id = {row["edge_id"]: row["decision"] for row in decisions}
    family_counts = {}
    for edge in graph["edges"]:
        family = family_counts.setdefault(edge["record_kind"],
                                           {"total": 0, "keep": 0, "prune": 0, "abstain": 0})
        family["total"] += 1
        family[by_id[edge["id"]]] += 1
    report = {"format": FORMAT, "profile": PROFILE, "created_at": utcnow(),
        "description": "Source-reported direct phosphorylation/dephosphorylation with human experimental-organism metadata.",
        "actor": actor, "packet_id": manifest["packet_id"],
        "graph_sha256": manifest["graph_sha256"], "snapshot_sha256": manifest["snapshot_sha256"],
        "source_bindings": bindings,
        "profile_fields": {"DIRECT": "t", "MECHANISM": sorted(ALLOWED_MECHANISMS), "TAX_ID": "9606",
                           "explicit_incompatible_mechanisms": sorted(INCOMPATIBLE_MECHANISMS),
                           "explicit_incompatible_experimental_species": deepcopy(INCOMPATIBLE_EXPERIMENTAL_SPECIES),
                           "experimental_taxon_vocabulary_basis": deepcopy(TAXON_VOCABULARY_BASIS)},
        "counts": {"total_edges": len(decisions), **{k: counts[k] for k in ("keep", "prune", "abstain")},
            "profile_edges": len(by_edge), "outside_profile_abstain": len(decisions) - len(by_edge),
            "unknown_profile_abstain": source_counts["abstain"],
            "unprojected_source_records": sum(not row["projected_to_graph"] for row in trace),
            "source_profile": {k: source_counts[k] for k in ("keep", "prune", "abstain")}},
        "edge_family_counts": family_counts,
        "source_decisions": trace, "limitations": deepcopy(LIMITATIONS),
        "source_graph_mutated": False, "source_review_states_mutated": False,
        "biological_truth_assessed": False, "independent_validation_performed": False,
        "independent_biological_accuracy": False,
        "model_calls": 0, "source_fetches": 0, "retained_package": "retained",
        "retained_graph_scope": "New Gold retained projection, not a replacement ordinary saved run. "
            "Original lifecycle and review states remain in baseline_packet; changed evidence support "
            "uses the existing Gold assertion revision policy.",
        "implementation_sha256": sha(Path(__file__))}
    # All qualification and provenance checks precede creating the new output.
    folder = new_output(output, packet)
    write_json(folder / "decisions.json", value)
    # Existing Gold API rebuilds surviving assertions and preserves the baseline.
    retained = gold_packet.save_decisions(packet, folder / "decisions.json", folder / "retained")
    _need(retained["counts"]["keep"] == counts["keep"]
          and retained["counts"]["prune"] == counts["prune"]
          and retained["counts"]["abstain"] == counts["abstain"],
          "retained package decision counts disagree.")
    report["retained_report_sha256"] = retained["content_sha256"]
    report["files"] = {"decisions.json": sha(folder / "decisions.json"),
                       "retained/report.json": sha(folder / "retained/report.json")}
    report["content_sha256"] = digest(report)
    write_json(folder / "task_qualification.json", report)
    return report
