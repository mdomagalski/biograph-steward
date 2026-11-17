"""Source-bound adapters around published INDRA and Gilda APIs.

This module proposes grounding conflicts for review. It does not implement a
grounder, use curation labels, correct source identities or judge biological
truth. Optional native dependencies are imported only when needed.
"""
from copy import deepcopy
from hashlib import sha256

from biograph_steward.client import digest


PROJECTION_FORMAT = "biograph-steward.native-grounding-input.v1"
PREDICTION_FORMAT = "biograph-steward.native-grounding-check.v1"


def _native_agent_factory(name, db_refs):
    from indra.statements import Agent
    return Agent(name, db_refs=db_refs)


def _identifier(value):
    if isinstance(value, str) and value:
        return value
    if type(value) is int:
        return str(value)
    return None


def _pmid(evidence, warnings):
    # INDRA readers can retain an internal document identifier in text_refs
    # after set_statements_pmid supplies the actual citation in Evidence.pmid.
    # Validate the two native fields independently; malformed metadata is not a
    # second PMID and must not veto an otherwise unambiguous numeric citation.
    def valid(value, field):
        if value is None:
            return None
        if type(value) is int and value > 0:
            return str(value)
        if (isinstance(value, str) and value.isascii() and value.isdecimal()
                and value[0] != "0"):
            return value
        warnings.append("malformed_native_" + field)
        return None

    direct = valid(evidence.get("pmid"), "evidence_pmid")
    refs = evidence.get("text_refs")
    referenced = valid(refs.get("PMID"), "text_refs_PMID") if isinstance(refs, dict) else None
    if direct and referenced and direct != referenced:
        warnings.append("conflicting_native_PMID_fields")
        return None
    return direct or referenced


def project_evidence(statement_json, evidence_json, *, agent_factory=None):
    """Project one source evidence, never a representative statement mention.

    INDRA's preassembler stores ``raw_text`` and ``raw_grounding`` arrays in
    each Evidence's annotations, using ``agent_list(deep_sorted=True)``. These
    arrays remain paired here. Missing arrays are not reconstructed from the
    representative Statement's agents, standardized names or other evidence.

    ``agent_factory`` is test injection only. The production default uses
    INDRA Agent.get_grounding; its use is identified in the returned projection.
    Input JSON and None positions are preserved. The projection carries its
    own seal; callers should wrap it with case IDs rather than modify it.
    """
    if not isinstance(statement_json, dict) or not isinstance(evidence_json, dict):
        raise ValueError("Supply native Statement and Evidence JSON objects.")
    original = digest({"statement": statement_json, "evidence": evidence_json})
    factory = agent_factory or _native_agent_factory
    warnings, reasons, agents = [], [], []
    text = evidence_json.get("text")
    if not isinstance(text, str) or not text.strip():
        text = None
        reasons.append("source_evidence_text_unavailable")
    annotations = evidence_json.get("annotations")
    supplied = annotations.get("agents") if isinstance(annotations, dict) else None
    raw_text = supplied.get("raw_text") if isinstance(supplied, dict) else None
    raw_grounding = supplied.get("raw_grounding") if isinstance(supplied, dict) else None
    arrays = isinstance(raw_text, list) and isinstance(raw_grounding, list)
    if not arrays:
        reasons.append("evidence_specific_agent_arrays_unavailable")
    elif len(raw_text) != len(raw_grounding):
        reasons.append("evidence_specific_agent_array_lengths_differ")
    else:
        for index, (mention, refs) in enumerate(zip(raw_text, raw_grounding)):
            row = {"index": index, "mention": deepcopy(mention),
                   "raw_grounding": deepcopy(refs), "assigned": None,
                   "status": "unresolved_input", "reasons": []}
            if mention is None and refs is None:
                row["status"] = "neutral"
            elif not isinstance(mention, str) or not mention.strip():
                row["reasons"].append("source_agent_mention_unavailable")
            elif not isinstance(refs, dict):
                row["reasons"].append("source_agent_grounding_unavailable")
            elif refs.get("TEXT") is not None and refs["TEXT"] != mention:
                row["reasons"].append("source_agent_text_and_grounding_annotation_differ")
            else:
                try:
                    namespace, identifier = factory(
                        name=mention, db_refs=deepcopy(refs)).get_grounding()
                    identifier = _identifier(identifier)
                    if not isinstance(namespace, str) or not namespace or identifier is None:
                        row["reasons"].append("native_assigned_grounding_unavailable")
                    else:
                        row["assigned"] = {"namespace": namespace, "id": identifier}
                        row["status"] = "ready"
                except ImportError:
                    raise
                except Exception as exc:
                    row["reasons"].append("native_assigned_grounding_error")
                    row["error_type"] = type(exc).__name__
            agents.append(row)
    actual = [a for a in agents if a["status"] != "neutral"]
    if not actual:
        reasons.append("no_source_agent_mentions")
    ready = sum(a["status"] == "ready" for a in actual)
    if actual and not ready:
        reasons.append("no_source_agent_with_assigned_grounding")
    status = ("unresolved" if reasons or not ready else
              "ready" if ready == len(actual) else "partial")
    source_api = evidence_json.get("source_api")
    if not isinstance(source_api, str) or not source_api:
        source_api = None
        warnings.append("source_api_unavailable")
    excluded = {"evidence", "belief", "id", "matches_hash", "supports", "supported_by"}
    result = {"format": PROJECTION_FORMAT, "status": status,
              "reasons": reasons, "warnings": warnings, "text": text,
              "source_api": source_api, "pmid": _pmid(evidence_json, warnings),
              "agents": agents,
              "raw_agent_arrays": {"raw_text": deepcopy(raw_text),
                                   "raw_grounding": deepcopy(raw_grounding)},
              "original_qualifiers": {
                  "assembled_statement_attributes_as_supplied": {
                      key: deepcopy(value) for key, value in statement_json.items()
                      if key not in excluded},
                  "epistemics": deepcopy(evidence_json.get("epistemics")),
                  "context": deepcopy(evidence_json.get("context")),
                  "pmid": deepcopy(evidence_json.get("pmid")),
                  "text_refs": deepcopy(evidence_json.get("text_refs"))},
              "assigned_entity_resolver": ("indra.statements.Agent.get_grounding"
                                           if agent_factory is None else
                                           "injected_test_agent_factory"),
              "source_input_sha256": original}
    result["input_sha256"] = digest(result)
    if original != digest({"statement": statement_json, "evidence": evidence_json}):
        raise ValueError("Native input JSON changed during projection.")
    return result


def _check_projection(case):
    if not isinstance(case, dict) or case.get("format") != PROJECTION_FORMAT:
        raise ValueError("Use a source-bound native grounding projection.")
    value = {key: item for key, item in case.items() if key != "input_sha256"}
    if case.get("input_sha256") != digest(value):
        raise ValueError("Grounding input projection seal differs.")


def _available_model(grounder, mention):
    """Inspect already available native metadata without loading resources."""
    lookup = mention.strip()  # Native Grounder.ground strips before model lookup.
    gilda = getattr(grounder, "gilda_disambiguators", None)
    adeft = getattr(grounder, "adeft_disambiguators", None)
    if isinstance(gilda, dict) and lookup in gilda:
        return True
    if isinstance(adeft, dict) and lookup in adeft:
        return True
    return False if isinstance(gilda, dict) and isinstance(adeft, dict) else None


def _groundings(match):
    result = set()
    for value in match.get_groundings():
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("Native match grounding is malformed.")
        namespace, identifier = value
        identifier = _identifier(identifier)
        if not isinstance(namespace, str) or not namespace or identifier is None:
            raise ValueError("Native match grounding is incomplete.")
        result.add((namespace, identifier))
    if not result:
        raise ValueError("Native match has no grounding.")
    return result


def _agent_result(agent):
    return {"index": agent["index"], "mention": deepcopy(agent["mention"]),
           "assigned": deepcopy(agent["assigned"]), "status": "unresolved",
           "candidate_conflict": None, "reasons": list(agent["reasons"]),
           "ranked_matches": [], "top_native_groundings": [],
           "native_model_available": None, "disambiguation_applied": False}


def _check_agent(agent, case, grounder, use_context, context_text):
    row = _agent_result(agent)
    if agent["status"] == "neutral":
        row["status"] = "neutral"
        return row
    if agent["status"] != "ready":
        return row
    try:
        matches = grounder.ground(
            agent["mention"], context=context_text)
        row["native_model_available"] = _available_model(grounder, agent["mention"])
        if not isinstance(matches, (list, tuple)):
            raise ValueError("Native grounder did not return ranked matches.")
        row["ranked_matches"] = [deepcopy(match.to_json()) for match in matches]
        # Require portable native JSON; nonfinite or unsupported values are
        # technical output errors, never source-support judgments.
        digest(row["ranked_matches"])
        row["disambiguation_applied"] = any(
            bool(match.get("disambiguation")) for match in row["ranked_matches"])
        if not matches:
            row["reasons"].append("native_grounder_no_match")
            return row
        if use_context and row["native_model_available"] is True and not row["disambiguation_applied"]:
            row["status"] = "model_error"
            row["reasons"].append("available_disambiguation_not_applied")
            return row
        top = _groundings(matches[0])
        row["top_native_groundings"] = [list(value) for value in sorted(top)]
        assigned = (agent["assigned"]["namespace"], agent["assigned"]["id"])
        if assigned in top:
            row.update(status="no_conflict", candidate_conflict=False)
        elif (assigned[0] == "UP" and "-" in assigned[1]) or assigned[0] == "UPPRO":
            row["status"] = "unresolved_form"
            row["reasons"].append("assigned_protein_form_not_explicit_in_top_native_match")
        else:
            term = row["ranked_matches"][0].get("term")
            namespace = term.get("db") if isinstance(term, dict) else None
            if not isinstance(namespace, str) or not namespace:
                raise ValueError("Native top match primary namespace is unavailable.")
            if namespace != assigned[0]:
                row["status"] = "unresolved_namespace_or_granularity"
                row["reasons"].append("top_native_namespace_differs_without_explicit_mapping")
            else:
                row.update(status="candidate_conflict", candidate_conflict=True)
        return row
    except Exception as exc:
        row["status"] = "model_error"
        row["candidate_conflict"] = None
        row["reasons"].append("native_grounder_error")
        row["error_type"] = type(exc).__name__
        return row


def check_grounding(case, grounder, *, use_context, context_text=None):
    """Compare assigned identities with native top matches, without mutation.

    Native default organism and namespace policies are used unchanged. Callers
    must prepopulate and pin the native resources before inference. This
    adapter retrieves no publication text and uses no curator labels, custom
    NLP, score threshold or source-ID substitution.

    With context enabled, None uses the pinned Evidence.text. An explicitly
    supplied string permits a separately frozen publication-context arm; it is
    identified by its raw UTF-8 SHA256 and never changes source text/proof.
    An unavailable publication context must be handled by the caller rather
    than passing None and silently presenting sentence context as publication
    context. The no-context arm rejects an explicit context value.
    """
    _check_projection(case)
    if type(use_context) is not bool:
        raise ValueError("Declare the context arm as a boolean.")
    if not use_context and context_text is not None:
        raise ValueError("The no-context arm cannot receive context text.")
    if context_text is not None and (not isinstance(context_text, str) or not context_text.strip()):
        raise ValueError("Explicit context must be nonempty text.")
    actual_context = (case["text"] if context_text is None else context_text) if use_context else None
    context_kind = ("none" if not use_context else
                    "evidence_text" if context_text is None else "provided_context_text")
    before = digest(case)
    if case["status"] == "unresolved":
        agents = [_agent_result(a) for a in case["agents"]]
        for agent, source in zip(agents, case["agents"]):
            if source["status"] == "neutral":
                agent["status"] = "neutral"
            elif source["status"] == "ready":
                agent["reasons"].append("blocked_by_unresolved_source_input")
        status, conflict = "unresolved", None
    else:
        agents = [_check_agent(a, case, grounder, use_context, actual_context) for a in case["agents"]]
        actual = [a for a in agents if a["status"] != "neutral"]
        if any(a["candidate_conflict"] is True for a in actual):
            status, conflict = "candidate_conflict", True
        elif any(a["status"] == "model_error" for a in actual):
            status, conflict = "model_error", None
        elif actual and all(a["status"] == "no_conflict" for a in actual):
            status, conflict = "no_conflict", False
        else:
            status, conflict = "unresolved", None
    result = {"format": PREDICTION_FORMAT, "input_sha256": case["input_sha256"],
              "use_context": use_context, "status": status,
              "context_kind": context_kind,
              "context_sha256": sha256(actual_context.encode("utf-8")).hexdigest() if actual_context is not None else None,
              "context_characters": len(actual_context) if actual_context is not None else 0,
              "candidate_conflict": conflict, "reasons": list(case["reasons"]),
              "agents": agents, "model_error_agents": sum(a["status"] == "model_error" for a in agents),
              "native_model_available_agents": sum(a["native_model_available"] is True for a in agents),
              "native_model_availability_unknown_agents": sum(
                  a["native_model_available"] is None for a in agents if a["status"] != "neutral"),
              "disambiguation_applied_agents": sum(a["disambiguation_applied"] for a in agents),
              "policy": "Native Gilda top match and explicit native mapped/subsumed identities; default organism/namespace policy, no threshold or ID replacement.",
              "interpretation": "Candidate source-grounding conflict for review, not biological falsehood, calibrated truth probability or protein-form validation."}
    if digest(case) != before:
        raise ValueError("Grounding input projection changed during checking.")
    return result
