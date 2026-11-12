"""Qualified assertions and explicit human review, separate from source records.

This is a project-local contract, not full Biolink/LinkML validation. Review
acceptance is a recorded human decision, never an automatically inferred label.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime

from .client import digest, utcnow

QUALIFIERS = ("disease", "variant", "therapy", "species", "tissue", "cell_line", "response")
# Nullable core slots retain their v2 identity representation. New slots only
# enter identity when supplied, so old claim IDs and human decisions survive.
CONTEXT_QUALIFIERS = ("go_aspect", "tissue_label", "assay", "observation_id",
                      "measurement_value", "measurement_qualifier", "measurement_unit",
                      "evidence_direction", "variant_origin", "therapy_interaction", "evidence_type",
                      "regulatory_effect", "regulatory_mechanism", "source_directness", "residue", "sequence")
TRANSITIONS = {
    "candidate": {"accepted", "provisional", "quarantined", "rejected"},
    "provisional": {"accepted", "quarantined", "rejected", "obsolete"},
    "accepted": {"provisional", "quarantined", "rejected", "obsolete"},
    "quarantined": {"candidate", "rejected"},
    "rejected": {"candidate"},
    "obsolete": {"candidate"},
}


def assertion_identity(subject: str, predicate: str, obj: str,
                       kind: str, qualifiers: dict) -> dict:
    if not all(isinstance(v, str) and v.strip() for v in (subject, predicate, obj, kind)):
        raise ValueError("Assertions require subject, predicate, object and kind.")
    if set(qualifiers) - set(QUALIFIERS + CONTEXT_QUALIFIERS):
        raise ValueError("Unsupported assertion qualifier.")
    if any(v is not None and (not isinstance(v, str) or not v.strip()) for v in qualifiers.values()):
        raise ValueError("Qualifier values must be nonempty identifiers/text or null.")
    return {"subject": subject, "predicate": predicate, "object": obj,
            "kind": kind, "qualifiers": {**{k: qualifiers.get(k) for k in QUALIFIERS},
                **{k: qualifiers[k] for k in CONTEXT_QUALIFIERS if qualifiers.get(k) is not None}}}


def build_assertions(graph: dict, events: list[dict] | None = None) -> list[dict]:
    groups = {}
    for edge in graph["edges"]:
        identity = assertion_identity(edge["subject"], edge["predicate"], edge["object"],
                                      edge["record_kind"], edge.get("qualifiers", {}))
        aid = "assertion:" + digest(identity)[:24]
        edge["assertion_id"] = aid
        group = groups.setdefault(aid, {"id": aid, **identity, "evidence_edge_ids": [],
            "structurally_usable_evidence_ids": [], "review_reasons": [],
            "publications": [], "source_names": [], "lifecycle_state": "candidate",
            "review_history": [], "data_kind": graph["data_kind"],
            "normalization_notes": [], "source_record_count": 0,
            "symmetric": edge.get("symmetric", False),
            "snapshot_sha256": graph["snapshot_sha256"], "biologically_validated": False})
        group["evidence_edge_ids"].append(edge["id"])
        if edge["status"] == "passed_structural_checks":
            group["structurally_usable_evidence_ids"].append(edge["id"])
        group["review_reasons"].extend(edge["review_reasons"])
        group["publications"].extend(edge["publications"])
        group["normalization_notes"].extend(edge.get("normalization_notes", []))
        group["source_record_count"] += edge.get("source_record_count", len(edge["record_locators"]))
        if edge.get("evidence_sources"):
            group["source_names"].extend(edge["evidence_sources"])
        elif edge.get("primary_source_raw"):
            group["source_names"].append(str(edge["primary_source_raw"]))
        if edge.get("extension_source_kind"):
            group["data_kind"] = edge["data_kind"]
            group["extension_source_kind"] = edge["extension_source_kind"]
            group["evidence_extension_sha256"] = graph["evidence_extension_sha256"]
    for group in groups.values():
        if group["kind"] == "assay_observation" and graph.get("assay_publication_sha256"):
            group["data_kind"] = "published_assay_observations"
            group["assay_publication_sha256"] = graph["assay_publication_sha256"]
            group["assay_attachment_sha256"] = graph["assay_attachment_sha256"]
        for field in ("evidence_edge_ids", "structurally_usable_evidence_ids", "review_reasons",
                      "publications", "source_names", "normalization_notes"):
            group[field] = sorted(set(group[field]))
        group["revision"] = digest({"identity": group["id"], "evidence": group["evidence_edge_ids"]})
        group["validation_status"] = ("has_structurally_usable_evidence"
            if group["structurally_usable_evidence_ids"] else "needs_review")
        group["independent_evidence_count"] = None
        group["origin_note"] = "Source records and publications are not independent experiment counts."
    if events is not None and not isinstance(events, list):
        raise ValueError("Review events must be a list.")
    for sequence, event in enumerate(events or [], 1):
        if not isinstance(event, dict) or event.get("sequence") != sequence:
            raise ValueError("Review history sequence is invalid.")
        group = groups.get(event.get("assertion_id"))
        if group is None:
            raise ValueError("Review refers to an unknown assertion.")
        if event.get("snapshot_sha256") != graph["snapshot_sha256"] or event.get("revision") != group["revision"]:
            raise ValueError("Review belongs to another snapshot or assertion revision; review the new evidence.")
        if group["kind"] == "variant_therapy_response" and event.get("civic_snapshot_sha256") != graph.get("civic_snapshot_sha256"):
            raise ValueError("Review belongs to a different CIViC source snapshot; review the new evidence.")
        if group["kind"] == "assay_observation" and any(
                event.get(key) != graph.get(key) for key in ("assay_publication_sha256", "assay_attachment_sha256")):
            raise ValueError("Review belongs to a different assay publication or cohort selection; review the new evidence.")
        if group.get("extension_source_kind") and event.get("evidence_extension_sha256") != graph.get("evidence_extension_sha256"):
            raise ValueError("Review belongs to a different biological source extension.")
        if event.get("from_state") != group["lifecycle_state"]:
            raise ValueError("Review history has a stale lifecycle state.")
        validate_decision(group, event.get("to_state"), event.get("reviewer"), event.get("reason"))
        try:
            timestamp = datetime.fromisoformat(event["created_at"])
            if timestamp.utcoffset() is None:
                raise ValueError("Timezone is required.")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Review timestamp must include a timezone.") from exc
        group["lifecycle_state"] = event["to_state"]
        group["review_history"].append(deepcopy(event))
    for group in groups.values():
        group["allowed_transitions"] = sorted(state for state in TRANSITIONS[group["lifecycle_state"]]
            if state != "accepted" or (group["structurally_usable_evidence_ids"]
                                        and group["kind"] != "disease_filtered_membership"))
    return sorted(groups.values(), key=lambda a: a["id"])


def validate_decision(assertion: dict, state: str, reviewer: str, reason: str) -> None:
    if not isinstance(state, str) or state not in TRANSITIONS.get(assertion["lifecycle_state"], set()):
        raise ValueError("Invalid lifecycle transition.")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 200:
        raise ValueError("A reviewer name of 1–200 characters is required.")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ValueError("A review reason of 1–4000 characters is required.")
    if state == "accepted" and (not assertion["structurally_usable_evidence_ids"]
                                or assertion["kind"] == "disease_filtered_membership"):
        raise ValueError("Acceptance requires structurally usable evidence; membership alone is insufficient.")


def new_review_event(graph: dict, assertion_id: str, state: str,
                     reviewer: str, reason: str) -> dict:
    assertion = next((a for a in graph["assertions"] if a["id"] == assertion_id), None)
    if assertion is None:
        raise ValueError("Unknown assertion.")
    validate_decision(assertion, state, reviewer, reason)
    event = {"sequence": len(graph.get("review_events", [])) + 1,
            "assertion_id": assertion_id, "revision": assertion["revision"],
            "snapshot_sha256": graph["snapshot_sha256"],
            "from_state": assertion["lifecycle_state"], "to_state": state,
            "reviewer": reviewer.strip(), "reason": reason.strip(), "created_at": utcnow()}
    if assertion["kind"] == "variant_therapy_response":
        event["civic_snapshot_sha256"] = graph["civic_snapshot_sha256"]
    if assertion["kind"] == "assay_observation" and graph.get("assay_publication_sha256"):
        for key in ("assay_publication_sha256", "assay_attachment_sha256"):
            event[key] = graph[key]
    if assertion.get("extension_source_kind"):
        event["evidence_extension_sha256"] = graph["evidence_extension_sha256"]
    return event


def assertion_summary(assertions: list[dict]) -> dict:
    counts = Counter(a["lifecycle_state"] for a in assertions)
    return {"assertions": len(assertions),
            "lifecycle_counts": {state: counts[state] for state in TRANSITIONS},
            "acceptance_note": "Acceptance records human review; it is not an experimental label or automatic biological validation."}
