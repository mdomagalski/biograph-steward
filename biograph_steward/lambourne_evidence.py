"""Project an already verified Lambourne assessment into qualified observations.

This local evidence layer is neither an IMEx import nor a MITAB/KGX mapping.
The source adapter's outcomes are preserved, not reclassified. A nondetection
describes this assay and these constructs, not absence of a protein interaction.
"""
from collections import Counter
from copy import deepcopy
import re

from .assertions import assertion_summary, build_assertions
from .client import digest
from .graph import protein_id


FORMAT = "biograph-steward.lambourne-assay-evidence.v1"
DOI = "10.1038/s41467-026-70942-x"
ASSAY = "human Y2H-v1"
PREDICATE = "biograph:has_assay_observation_with"
_SHA = re.compile(r"[0-9a-f]{64}")
_EXCLUDED = {"failed_sequence_confirmation", "ambiguous_sequence_confirmation",
             "autoactivator", "test_failed"}
_STATES = {"present_in_raw_ppi": 1, "no_match_both_endpoints_resolved": 0,
           "no_match_one_endpoint_resolved": None}
LIMITATIONS = [
    "These are study-specific human protein Y2H-v1 observations, not universal physical-binding or disease claims.",
    "Human identifies the assayed protein participants; it does not identify the experimental assay host.",
    "Nondetection is not a negative interaction edge. Failed and ineligible assays remain observations without graph edges.",
    "AD and DB ORF roles are retained without assigning a sorted protein endpoint to a construct; the source crosswalk can be one-to-many.",
    "The original Pharos records are preserved as lookup context and are neither accepted, rejected, pruned nor replaced.",
    "A no-match is bounded by the saved Pharos lookup; neither global novelty nor independent evidence is established.",
    "This panel has been consumed by the completed assessment and cannot independently validate this evidence addition.",
    "Source reconciliation and structural checks do not establish biological truth or independent experiment counts.",
    "This local observation representation does not claim IMEx curation or MITAB, Biolink or KGX conformance.",
]


def _sha(value):
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


def _pair(record):
    products = record.get("products")
    if (not isinstance(products, list) or len(products) != 2
            or any(not isinstance(uid, str) or protein_id(uid) != "UniProtKB:" + uid for uid in products)
            or products != sorted(products) or products[0] == products[1]):
        raise ValueError("Assay products must be two sorted, exact UniProt accessions.")
    return tuple(products)


def _source_row(record):
    value = record.get("source_row")
    if type(value) is not int or value < 1:
        raise ValueError("Each observation requires an exact positive source row.")
    return value


def _bindings(bindings):
    if (not isinstance(bindings, dict)
            or any(not _sha(bindings.get(k)) for k in ("protocol_sha256", "result_sha256"))
            or not isinstance(bindings.get("source_sha256"), dict)
            or any(not _sha(bindings["source_sha256"].get(k)) for k in ("panel", "raw", "orf_map"))):
        raise ValueError("Evidence requires sealed protocol/result and exact panel, raw and ORF-map hashes.")
    artifacts = bindings.get("artifact_sha256", {})
    if not isinstance(artifacts, dict) or any(not _sha(value) for value in artifacts.values()):
        raise ValueError("Artifact byte hashes must be SHA-256 values.")


def _eligible(assay):
    status = assay.get("assay_status")
    expected = ((True, True) if status == "detected" else
                (True, False) if status == "not_detected" else
                (False, None) if status in _EXCLUDED else None)
    if expected is None or any(assay.get(k) is not v for k, v in
                               zip(("evaluable", "detected"), expected)):
        raise ValueError("Assay status, eligibility and detection disagree; do not reclassify source outcomes.")
    if assay.get("construct_match") is not True or assay.get("issues") != []:
        raise ValueError("Only reconciled assay records may be projected.")
    raw_rows = assay.get("raw_source_rows")
    if (not isinstance(raw_rows, list) or not raw_rows
            or any(type(n) is not int or n < 1 for n in raw_rows)
            or len(raw_rows) != len(set(raw_rows))):
        raise ValueError("Assay raw source-row locators are missing or ambiguous.")
    return expected[0]


def _provenance(assay, index, lookup_index, bindings, row, lookup):
    hashes = bindings["source_sha256"]
    artifacts = bindings.get("artifact_sha256", {})
    return [
        {"locator": "source/freeze/source/panel.tsv#row=" + str(assay["source_row"]),
         "file_sha256": hashes["panel"], "role": "published_assay_record"},
        *[{"locator": "source/freeze/source/raw_human.tsv#row=" + str(n),
           "file_sha256": hashes["raw"], "role": "raw_assay_record"} for n in assay["raw_source_rows"]],
        {"locator": "source/freeze/source/orf_map.tsv", "file_sha256": hashes["orf_map"],
         "role": "construct_crosswalk", "row_resolved": False},
        {"locator": "source/results/rows.json#/" + str(index),
         "file_sha256": artifacts.get("rows"), "record_sha256": digest(row),
         "result_sha256": bindings["result_sha256"], "role": "assessed_observation"},
        {"locator": "source/freeze/lookup/pair_lookup.json#/" + str(lookup_index),
         "file_sha256": artifacts.get("lookup"), "record_sha256": digest(lookup),
         "protocol_sha256": bindings["protocol_sha256"], "role": "frozen_pharos_lookup"},
    ]


def build_evidence(rows, lookup_rows, bindings):
    """Build a deterministic local observation layer from verified assessment data.

    ``rows`` and ``lookup_rows`` must be the complete respective saved arrays.
    ``bindings`` requires protocol_sha256, result_sha256 and source_sha256 with
    panel/raw/orf_map keys. Optional artifact_sha256 rows/lookup keys bind their
    JSON file bytes. This function checks joins and semantics, but the caller
    must first verify the sealed assessment and the hashes of its input files.
    No input is mutated; runtime ordering affects locators, never observation IDs.
    """
    _bindings(bindings)
    if (not isinstance(rows, list) or not isinstance(lookup_rows, list)
            or any(not isinstance(row, dict) for row in rows + lookup_rows)
            or len(rows) != len(lookup_rows)):
        raise ValueError("Assessment and lookup must be complete arrays of equal size.")
    lookup_by_key, lookup_pairs, lookup_source_rows = {}, set(), set()
    for index, lookup in enumerate(lookup_rows):
        pair, source_row = _pair(lookup), _source_row(lookup)
        if pair in lookup_pairs or source_row in lookup_source_rows:
            raise ValueError("Lookup pair/source-row bijection is not unique.")
        lookup_pairs.add(pair)
        lookup_source_rows.add(source_row)
        lookup_by_key[(pair, source_row)] = (index, lookup)
    observations, nodes, edges, seen = [], {}, [], set()
    for index, row in enumerate(rows):
        comparator, assay = row.get("comparator"), row.get("assay")
        if not isinstance(comparator, dict) or not isinstance(assay, dict):
            raise ValueError("Each assessed row requires its comparator and assay record.")
        pair, source_row = _pair(assay), _source_row(assay)
        key = (pair, source_row)
        if key in seen or key not in lookup_by_key:
            raise ValueError("Assessment and lookup pair/source-row bijection differs.")
        seen.add(key)
        lookup_index, lookup = lookup_by_key[key]
        if (_pair(comparator) != pair or _source_row(comparator) != source_row
                or comparator.get("lookup_record_sha256") != digest(lookup)
                or comparator.get("identity") != lookup.get("identity")
                or comparator.get("pharos_status") != lookup.get("pharos_status")):
            raise ValueError("Assessment comparator does not match its exact frozen lookup record.")
        identity = comparator.get("identity")
        if (not isinstance(identity, dict) or identity.get("source_row") != source_row
                or any(not isinstance(identity.get(k), str) for k in ("uniprot_a", "uniprot_b"))
                or sorted([identity["uniprot_a"], identity["uniprot_b"]]) != list(pair)
                or any(not isinstance(assay.get(role), str) or not assay[role]
                       or assay[role] != identity.get(role) for role in ("ad_orf_id", "db_orf_id"))):
            raise ValueError("Source protein and AD/DB construct identities disagree.")
        eligible = _eligible(assay)
        state = comparator["pharos_status"]
        if (state not in _STATES or comparator.get("comparator") != _STATES[state]
                or type(comparator.get("comparator")) is bool
                or row.get("comparator_evaluable") is not (eligible and _STATES[state] is not None)):
            raise ValueError("Comparator state or eligibility contradicts the saved assay.")
        observation_id = "lambourne.observation:" + digest({"doi": DOI, "products": list(pair),
            "ad_orf_id": assay["ad_orf_id"], "db_orf_id": assay["db_orf_id"]})[:24]
        provenance = _provenance(assay, index, lookup_index, bindings, row, lookup)
        observation = {"id": observation_id, "study": "doi:" + DOI, "assay": ASSAY,
            "detection_method": {"id": "MI:0018", "label": "two hybrid"},
            "participant_taxon": "NCBITaxon:9606", "assay_host_taxon": None,
            "products": ["UniProtKB:" + uid for uid in pair],
            "constructs": {"ad_orf_id": assay["ad_orf_id"], "db_orf_id": assay["db_orf_id"],
                           "ad_experimental_role": {"id": "MI:0498", "label": "prey"},
                           "db_experimental_role": {"id": "MI:0496", "label": "bait"},
                           "protein_to_construct_orientation_inferred": False},
            "assay_status": assay["assay_status"], "evaluable": eligible,
            "graph_edge_id": None, "local_review_state": "candidate",
            "biologically_validated": False, "independent_evidence_count": None,
            "source_row": source_row, "source_locators": provenance,
            "original": deepcopy(row), "lookup": deepcopy(lookup)}
        for uid in observation["products"]:
            nodes.setdefault(uid, {"id": uid, "name": uid, "category": "biolink:Protein",
                "identifier_mapped": True, "data_kind": "published_assay_observations",
                "identity_note": "Source participant accession; no current accession or construct mapping is inferred."})
        if eligible:
            edge_id = "edge:" + digest({"observation_id": observation_id, "assay": assay})[:20]
            observation["graph_edge_id"] = edge_id
            edges.append({"id": edge_id, "subject": observation["products"][0],
                "predicate": PREDICATE, "object": observation["products"][1],
                "record_kind": "assay_observation", "symmetric": False,
                "qualifiers": {"assay": ASSAY, "observation_id": observation_id,
                    "measurement_qualifier": assay["assay_status"], "species": "NCBITaxon:9606"},
                "status": "passed_structural_checks", "review_reasons": [],
                "publications": ["doi:" + DOI], "primary_source_raw": "Lambourne et al.",
                "aggregator": "BioGraph Steward source-preserving projection",
                "evidence_record": deepcopy(assay), "source_record_count": len(assay["raw_source_rows"]),
                "record_locators": [entry["locator"] for entry in provenance],
                "retrieval_provenance": deepcopy(provenance),
                "observation": {key: deepcopy(observation[key]) for key in
                    ("id", "study", "assay", "detection_method", "participant_taxon", "assay_host_taxon", "constructs", "assay_status")},
                "normalization_notes": ["The local predicate records an assay observation between the listed participants; it does not assert an unqualified interaction.",
                    "Subject/object sorting does not assign AD/DB orientation or biological direction.",
                    "Species qualification describes the protein participants, not the experimental host."],
                "snapshot_sha256": bindings["result_sha256"],
                "data_kind": "published_assay_observations", "biologically_validated": False})
        observations.append(observation)
    if seen != set(lookup_by_key):
        raise ValueError("Assessment and lookup inventories are not a complete bijection.")
    graph = {"graph_format": "biograph-steward.assay-observation-graph.v1",
        "data_kind": "published_assay_observations", "snapshot_sha256": bindings["result_sha256"],
        "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
        "edges": sorted(edges, key=lambda row: row["id"]), "review_events": [],
        "interpretation": "Study-qualified assay observations. No Pharos source edge is modified or accepted.",
        "independent_evidence_count": None, "biologically_validated": False}
    graph["assertions"] = build_assertions(graph)
    graph["assertion_summary"] = assertion_summary(graph["assertions"])
    counts = Counter(observation["assay_status"] for observation in observations)
    summary = {"observations": len(observations), "assay_status_counts": dict(sorted(counts.items())),
        "assay_evaluable": sum(observation["evaluable"] for observation in observations),
        "assay_excluded": sum(not observation["evaluable"] for observation in observations),
        "comparator_evaluable": sum(row["comparator_evaluable"] for row in rows),
        "graph_nodes": len(graph["nodes"]), "graph_edges": len(graph["edges"]),
        "graph_assertions": len(graph["assertions"]),
        "detected_without_bounded_pharos_match": sum(observation["assay_status"] == "detected"
            and observation["original"]["comparator"]["pharos_status"] == "no_match_both_endpoints_resolved"
            for observation in observations),
        "pharos_records_modified": 0, "automatically_accepted_assertions": 0,
        "independently_validated_new_interactions": None}
    graph["summary"] = deepcopy(summary)
    return {"format": FORMAT, "bindings": deepcopy(bindings),
        "observations": sorted(observations, key=lambda row: row["id"]),
        "graph": graph, "summary": summary, "limitations": list(LIMITATIONS)}
