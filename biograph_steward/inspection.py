"""Read-only guidance over already source-bound evidence.

This is a display adapter, not a verifier, agent or new annotation protocol.
It reuses the existing IntAct and CIViC explanation functions; missing source
fields remain missing. Callers must load the graph through ``reviews.read_run``
before exposing it. Nothing here fetches sources or changes review decisions.
"""
from __future__ import annotations

from copy import deepcopy
import re
from urllib.parse import quote, urlsplit

from .assertions import CONTEXT_QUALIFIERS, QUALIFIERS
from .graph import safe_url
from .questions import graph_basis

FORMAT = "biograph-steward.source-inspection.v1"
MI_URL = "https://github.com/HUPO-PSI/psi-mi-CV/blob/master/psi-mi.owl"
REVIEW_NOTE = ("Local acceptance records a human review decision. Structural checks, "
               "source editorial acceptance and local review do not establish biological truth.")
INDEPENDENCE_NOTE = ("Source labels, record aliases, rows and cited publications are not "
                     "independent experiment counts. Missing references do not establish independence.")


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _external_url(value):
    """Reuse the core HTTP(S) gate and also reject credentials and controls."""
    try:
        value = safe_url(value)
    except ValueError:
        return None
    if not value or any(char.isspace() or ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.username is not None or parsed.password is not None or not parsed.hostname:
            return None
        parsed.port
    except ValueError:
        return None
    return value


def _publication(identifier):
    value = _text(identifier)
    match = re.fullmatch(r"(?:PMID|pubmed):([0-9]+)", value, re.I)
    if match:
        return "https://pubmed.ncbi.nlm.nih.gov/" + match[1] + "/"
    match = re.fullmatch(r"doi:(10\.[0-9]{4,9}/\S+)", value, re.I)
    if match:
        return "https://doi.org/" + quote(match[1], safe="/().;:_-")
    return None


def _source_path(run_id, locator):
    """Turn a preserved relative assay locator into this run's source route."""
    if run_id is None or not isinstance(locator, str):
        return None
    path, _, fragment = locator.partition("#")
    if (not path or path.startswith("/") or "\\" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))):
        return None
    if path.startswith("extension_sources/"):
        if not re.fullmatch(r"extension_sources/(?:string|mapit|signor|bioplex)/[A-Za-z0-9_./-]+", path):
            return None
        route = "/api/extension-source/"
    else:
        route = "/api/assay-source/"
    return (route + run_id + "/" + quote(path, safe="/")
            + ("#" + quote(fragment, safe="=/_-") if fragment else ""))


def _selection(graph, selected):
    observations_all = [dict(row, id=row.get("id") or row.get("observation_id")) for collection in
                        ("assay_observations", "extension_observations") for row in graph.get(collection, [])]
    matches = [(kind, row) for kind, collection in (
        ("assertion", graph.get("assertions", [])), ("edge", graph.get("edges", [])),
        ("observation", observations_all)) for row in collection if row.get("id") == selected]
    if len(matches) != 1:
        raise ValueError("Choose one exact assertion, evidence edge or assay observation identifier from this workspace.")
    kind, row = matches[0]
    edge_index = {edge["id"]: edge for edge in graph.get("edges", [])}
    assertion = row if kind == "assertion" else None
    if kind == "assertion":
        if any(eid not in edge_index for eid in row.get("evidence_edge_ids", [])):
            raise ValueError("Selected assertion has missing evidence edges.")
        edges = [edge_index[eid] for eid in row.get("evidence_edge_ids", [])]
    elif kind == "edge":
        edges = [row]
    else:
        eid = row.get("graph_edge_id")
        if eid is not None and eid not in edge_index:
            raise ValueError("Selected observation has a missing evidence edge.")
        edges = [edge_index[eid]] if eid is not None else []
    if assertion is None and edges:
        ids = {edge.get("assertion_id") for edge in edges if edge.get("assertion_id")}
        assertions = [a for a in graph.get("assertions", []) if a["id"] in ids]
        if len(assertions) == 1:
            assertion = assertions[0]
        elif ids:
            raise ValueError("Evidence edge has an unresolved assertion binding.")
    observation_ids = {edge.get("qualifiers", {}).get("observation_id") for edge in edges}
    observations = ([row] if kind == "observation" else
                    [o for o in observations_all if o["id"] in observation_ids
                     or o.get("graph_edge_id") in {edge["id"] for edge in edges}])
    return kind, row, assertion, edges, observations


def _reuse(graph, edges, observations, reuse, run_id, add_link):
    result = {"status": "unresolved", "independent_evidence_count": None,
              "note": INDEPENDENCE_NOTE, "records": []}
    if reuse is not None:
        if not isinstance(reuse, dict) or reuse.get("status") not in {"available", "unavailable", "unverifiable"}:
            raise ValueError("Unsupported source-reuse view.")
        if run_id is not None and reuse.get("source_run") != run_id:
            raise ValueError("Source-reuse view belongs to another workspace.")
        if reuse.get("status") == "unverifiable":
            result["status"] = "unverifiable_saved_annotation"
            result["note"] = ("The saved source-reuse annotation could not be verified against the current "
                              "implementation. Its classifications are not displayed; reuse remains unresolved. "
                              + INDEPENDENCE_NOTE)
        if reuse.get("status") == "available":
            for key, expected in (("graph_basis_sha256", graph_basis(graph)),
                                  *((key, graph.get(key)) for key in
                                    ("snapshot_sha256", "assay_attachment_sha256", "assay_publication_sha256"))):
                if not expected or reuse.get(key) != expected:
                    raise ValueError("Source-reuse view belongs to a different source or review basis.")
            selected = {o["id"]: o for o in observations}
            rows = [r for r in reuse.get("observations", []) if r.get("observation_id") in selected]
            if len({r["observation_id"] for r in rows}) != len(rows):
                raise ValueError("Source-reuse observation is ambiguous.")
            for record in rows:
                source = selected[record["observation_id"]]
                if (record.get("products") != source.get("products") or record.get("study") != source.get("study")
                        or record.get("current_string_status") not in {"confirmed_user_assisted", "unknown_not_observed"}
                        or record.get("historical_pharos_reuse") is not None):
                    raise ValueError("Source-reuse view differs from the selected observation.")
                result["records"].append(deepcopy(record))
                for link in record.get("evidence_links", []):
                    add_link(link.get("label"), link.get("url"), "source_record")
            if rows:
                result["status"] = "saved_source_reuse_annotation"
                if run_id:
                    add_link("Saved source-reuse audit", "/api/assay-source-reuse/" + run_id + "/report.html", "local_reuse", local=True)
    civic_rows = graph.get("civic", {}).get("overlap", {}).get("rows", [])
    edge_ids = {edge["id"] for edge in edges}
    selected_civic = [deepcopy(r) for r in civic_rows if r.get("edge_id") in edge_ids]
    if selected_civic:
        result["civic_overlap"] = selected_civic
        if result["status"] == "unresolved":
            result["status"] = "saved_scope_overlap_annotation"
    return result


def inspect_selection(graph, selection_id, *, run_id=None, source_reuse=None):
    """Explain one existing selection without fetching, scoring or mutating it.

    ``source_reuse`` may be the verified result of ``assay_source_reuse.reuse_view``.
    Its source/review bindings are checked again before displaying an annotation.
    Returned text and raw field values must be rendered with textContent/escaping.
    Link kinds distinguish publications, original records and local source copies.
    """
    if not isinstance(selection_id, str) or not selection_id or len(selection_id) > 300:
        raise ValueError("Select an existing evidence identifier.")
    if run_id is not None and (not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id)):
        raise ValueError("Invalid workspace identifier.")
    kind, selected, assertion, edges, observations = _selection(graph, selection_id)
    links, link_index, omitted_links, sections, missing = [], {}, [], [], []
    civic_findings = []

    def add_link(label, url, link_kind, *, local=False):
        if not url:
            return None
        valid = url if local else _external_url(url)
        if not valid:
            omitted_links.append({"label": _text(label) or "Source link", "reason": "unsafe_or_unsupported_url"})
            return None
        key = (valid, link_kind)
        if key not in link_index:
            identifier = "source-link-" + str(len(links) + 1)
            link_index[key] = identifier
            links.append({"id": identifier, "label": _text(label) or "Source link", "url": valid, "kind": link_kind})
        return link_index[key]

    sources = []
    for edge in edges:
        labels = edge.get("evidence_sources") or [edge.get("primary_source_raw")]
        labels = list(dict.fromkeys(_text(label) for label in labels if _text(label)))
        source = {"edge_id": edge["id"], "aggregator": edge.get("aggregator"),
                  "source_labels": labels, "structural_status": edge.get("status"),
                  "record_locators": deepcopy(edge.get("record_locators", [])),
                  "snapshot_sha256": edge.get("snapshot_sha256"),
                  "retrieval_provenance": deepcopy(edge.get("retrieval_provenance")), "link_ids": []}
        for publication in edge.get("publications", []):
            lid = add_link(publication, _publication(publication), "publication")
            if lid: source["link_ids"].append(lid)
        record = edge.get("evidence_record") or {}
        for label, url in (("Source-supplied record link", record.get("url")),
                           ("Source-supplied reference", edge.get("reference_raw"))):
            if isinstance(url, str) and ":" in url and not _publication(url):
                lid = add_link(label, url, "source_reference")
                if lid: source["link_ids"].append(lid)
        if edge.get("extension_source_kind"):
            for locator in edge.get("record_locators", []):
                if not isinstance(locator, str) or not locator.startswith("extension_sources/"):
                    continue
                url = _source_path(run_id, locator)
                if url:
                    lid = add_link("Preserved source record", url, "local_source", local=True)
                    if lid: source["link_ids"].append(lid)
            if edge.get("extension_source_kind") == "string":
                sections.append({"id": "string-" + edge["id"], "title": "Versioned STRING annotation",
                    "text": ("This separate STRING release supplies native functional and physical-overlay scores. "
                             "A physical score is not proof of direct binding; the Pharos source record and its historical score remain unchanged."),
                    "fields": {"source_release": record.get("source_release"),
                        "native_scores": deepcopy(edge.get("source_scores_raw", {})),
                        "all_source_channels": deepcopy(record.get("source_row", {})),
                        "mapping_proof": deepcopy(record.get("mapping_proof", []))}})
        if edge.get("record_kind") == "variant_therapy_response":
            from .civic_context import CONTEXT_NOTE, LEVELS_URL, record_context
            context = record_context(edge)
            for label, url, lkind in ((context["evidence_id"], context["evidence_url"], "source_record"),
                                     (context["source_reference"], context["publication_url"], "publication"),
                                     ("CIViC evidence-level definitions", LEVELS_URL, "definition")):
                lid = add_link(label, url, lkind)
                if lid: source["link_ids"].append(lid)
            sections.append({"id": "civic-" + edge["id"], "title": "CIViC source context",
                             "text": context["therapy_scope_note"] + " " + CONTEXT_NOTE, "fields": context})
            # Promote the existing source classifications and complete scope.
            # Evidence levels describe study types; they are not our confidence.
            profile = record.get("molecularProfile") or {}
            disease = record.get("disease") or {}
            disease_text = disease.get("name") or "not supplied"
            if disease.get("doid"):
                disease_text += " (DOID:" + str(disease["doid"]) + ")"
            civic_findings.append(
                context["evidence_id"] + ": source evidence level "
                + str(context["evidence_level"] or "not supplied") + " — " + context["evidence_level_label"]
                + ". Reported significance: " + str(context["significance"] or "not supplied")
                + ". Source direction: " + str(context["evidence_direction"] or "not supplied")
                + ". Complete molecular profile: " + str(profile.get("name") or "not supplied")
                + ". Disease: " + disease_text
                + ". Complete therapy list: " + (context["therapy_label"] or "not supplied")
                + ". " + context["therapy_scope_note"])
        primary = [lid for lid in source["link_ids"] if links[int(lid.rsplit("-", 1)[1]) - 1]["kind"] != "local_source"]
        source["reference_status"] = ("references_supplied" if primary else
                                      "preserved_source_only" if source["link_ids"] else "primary_reference_not_supplied")
        if not primary:
            missing.append({"field": "primary_reference", "edge_id": edge["id"],
                "note": (", ".join(labels) + " is a source label. " if labels else "")
                + "This saved edge supplies no resolvable primary record or publication reference; inspect its saved source locators."})
        sources.append(source)

    for observation in observations:
        if (observation["id"].startswith("string-source:")
                or any(e.get("extension_source_kind") == "string"
                       and e["id"] == observation.get("graph_edge_id") for e in edges)):
            sections.append({"id": observation["id"] + ":coverage", "title": "STRING source coverage",
                "text": "These are source-query and mapping states, not assay outcomes or biological negative labels. Reciprocal rows remain views of one source association.",
                "fields": {k: deepcopy(observation.get(k)) for k in ("products", "state", "integration_state",
                    "baseline_pair_present", "functional_score", "physical_score", "mapping_states", "string_ids", "mapping_proof")}})
            for number in observation.get("network_row_numbers", []):
                url = _source_path(run_id, "extension_sources/string/capture/network.tsv#row=" + str(number))
                if url:
                    add_link("Preserved STRING response row", url, "local_source", local=True)
            continue
        if observation.get("source_kind") == "signor":
            from .regulatory_case_notes import case_notes, context_display, organism_display
            from .regulatory_questions import _saved_pair_context
            notes = case_notes(observation)
            sections.append({"id": observation["id"] + ":literature-check", "title": "Project literature check",
                "text": notes["interpretation"], "fields": notes})
            for note in notes["notes"]:
                for source in note.get("sources", []):
                    add_link(source.get("material") or "Inspected primary source", source.get("url"), "literature_check")
            for citation in observation.get("citations", []):
                add_link(citation.get("label") or citation.get("id") or "Source citation",
                         citation.get("url"), "publication")
            for locator in observation.get("source_locators", []):
                url = _source_path(run_id, locator.get("locator"))
                if url:
                    add_link("Preserved regulatory source record", url, "local_source", local=True)
            sections.append({"id": observation["id"] + ":regulation", "title": "Source-reported regulation",
                "text": ("Direction, effect, mechanism and site are separate source claims. Phosphorylation alone does not imply activation. "
                         "Source-reported directness does not independently establish physical binding."),
                "fields": {k: deepcopy(observation.get(k)) for k in ("products", "source_record_id", "source_release",
                    "effect_literal", "mechanism_literal", "source_reported_direct", "direct_literal",
                    "residue_raw", "sequence_raw", "self_regulation")}})
            sections.append({"id": observation["id"] + ":context", "title": "Reported experimental context",
                "text": ("Unreported context is unknown. Membership in this colorectal gene cohort does not make a source experiment colorectal-specific. "
                         "Human protein identifiers and the source experimental organism are separate. Residue coordinates are source values; sequence, isoform and construct equivalence are not inferred."),
                "fields": {**{k: deepcopy(observation.get(k)) for k in ("cell_context_raw", "cell_context_reporting",
                    "tissue_context_raw", "tissue_context_reporting", "participant_taxon", "participant_taxon_basis",
                    "source_experimental_organism_raw", "source_experimental_organism_reporting_state", "assay_host_taxon",
                    "supporting_sentence_raw", "source_row")},
                    "cell_display": context_display(observation.get('cell_context_raw', '')),
                    "tissue_display": context_display(observation.get('tissue_context_raw', '')),
                    "experimental_organism_display": organism_display(observation)}})
            reuse = _saved_pair_context(graph, observation['products'])
            sections.append({"id": observation["id"] + ":pair-coverage", "title": "Existing pair coverage and source reuse",
                "text": reuse.get('interpretation', 'Self-regulation is separate from the nonself PPI profile.'),
                "fields": reuse})
            captured = reuse.get('saved_string_capture')
            if captured:
                for number in captured.get('network_row_numbers', []):
                    url = _source_path(run_id, 'extension_sources/string/capture/network.tsv#row=' + str(number))
                    if url:
                        add_link('Preserved STRING pair record', url, 'saved_pair_context', local=True)
            sections.append({"id": observation["id"] + ":citations", "title": "Citation scope and publication metadata",
                "text": ("A cited publication can be a review or contain evidence under different conditions. Citation presence does not verify every source claim. "
                         "Publication types and linked notices are metadata; a missing Review label does not establish primary experimental evidence."),
                "fields": {"publication_metadata": deepcopy(observation.get("publication_metadata", [])),
                    "primary_experimental_evidence": observation.get("primary_experimental_evidence", "not_assessed"),
                    "baseline_nonself_pair_present": observation.get("baseline_nonself_pair_present"),
                    "independent_evidence_count": None}})
            continue
        if observation.get("source_kind") == "bioplex":
            from .regulatory_questions import _saved_pair_context
            for citation in observation.get("citations", []):
                add_link(citation.get("label") or citation.get("id") or "Source reference",
                         citation.get("url"), "publication" if citation.get("role") in
                         {"source_study_protocol", "historical_cell_model_context"} else "source_reference")
            for locator in observation.get("source_locators", []):
                url = _source_path(run_id, locator.get("locator"))
                if url:
                    add_link("Preserved BioPlex source row", url, "local_source", local=True)
            sections.append({"id": observation["id"] + ":assay-context", "title": "HCT116 assay context",
                "text": ("Bait is the expressed, tagged product selected for purification; prey is reported as co-isolating with it. "
                         "These experimental roles do not establish regulatory direction or direct binding. "
                         "The author interaction inference is at gene level; the exact clone, allele and isoform are not resolved by the native labels."),
                "fields": {key: deepcopy(observation.get(key)) for key in ("products", "bait", "prey", "cell_line_literal",
                    "cell_line_id", "cell_line_id_basis", "method_context", "context_qualification",
                    "context_review", "citations", "baseline_pair_edge_ids", "source_locators")}})
            sections.append({"id": observation["id"] + ":class-score", "title": "Author pair-class scores",
                "text": ("These are the undirected companion pair's CompPASS-Plus class scores, not direction-specific assay confidence. "
                         "They are not calibrated biological truth probabilities and are not combined with STRING scores. "
                         "Every matched companion record is preserved; no first or best score is chosen."),
                "fields": {key: deepcopy(observation.get(key)) for key in ("source_scores_raw", "companion_records")}})
            coverage = _saved_pair_context(graph, observation["products"])
            sections.append({"id": observation["id"] + ":existing-pair", "title": "Existing pair coverage and reuse",
                "text": ("This context record adds no graph edge or assertion. Baseline edge pointers refer to already represented endpoints; "
                         "a BioPlex provider label alone does not identify this exact study, record or cell line. "
                         "The records share one BioPlex study and do not provide separate independent evidence votes or establish one joint complex."),
                "fields": coverage})
            sections.append({"id": observation["id"] + ":limits", "title": "Cell-model limits and source terms",
                "text": ("The reported study protocol and the nominal parental cell-line background are distinct from a verified clone or assay-batch phenotype. "
                         "Coassociation cannot establish endogenous mismatch-repair competence or functional rescue. "
                         "Native-source redistribution rights remain unverified; the complete source packet is private."),
                "fields": {"limitations": deepcopy(observation.get("limitations", [])),
                    "biologically_validated": observation.get("biologically_validated"),
                    "independent_evidence_count": observation.get("independent_evidence_count")}})
            missing.append({"field": "clone_and_assay_batch",
                "note": "The exact selected clone/allele, assay-batch genotype and repair activity are unverified; the study's tagged-expression protocol does not establish endogenous function."})
            continue
        if observation.get("source_kind") == "mapit":
            for citation in observation.get("citations", []):
                add_link(citation.get("label") or citation.get("id") or "Primary study",
                         citation.get("url"), "publication")
            sections.append({"id": observation["id"] + ":tissue", "title": "MAP-IT tissue proximity",
                "text": ("Primary-antibody enrichment in pooled colorectal tumour and adjacent tissue, under the recorded assay and source-key-corrected reanalysis. "
                         "This is not direct binding, tumour-specific rewiring or independent validation. Isotype−Primary gives negative Beta_Ab for enrichment."),
                "fields": {k: deepcopy(observation.get(k)) for k in ("assay", "tissue_label", "detection_method",
                    "interaction_type", "statistics", "statistical_family", "sampling", "source_identity", "source_locators")}})
            sections.append({"id": observation["id"] + ":archive", "title": "Archived Pharos context",
                "text": "This bounded historical lookup distinguishes existing archived associations from new workspace coverage. It does not certify novelty in current Pharos or independence from prior experiments.",
                "fields": deepcopy(observation.get("archive_lookup", {}))})
        elif observation.get("source_kind") == "intact_mitab27":
            from .intact_evidence import answer_observation
            display = answer_observation(observation)
            for citation in display["citations"]:
                add_link(citation["label"], citation["url"],
                         "source_record" if citation["kind"] == "evidence" else citation["kind"])
            sections.extend({"id": observation["id"] + ":" + group["group"],
                "title": group["group"].replace("_", " ").capitalize(),
                "text": group["text"], "fields": deepcopy(group["fields"])} for group in display["field_groups"])
        elif (observation.get("detection_method") or {}).get("id") == "MI:0018":
            sections.append({"id": observation["id"] + ":constructs", "title": "Two-hybrid constructs",
                "text": ("The activation-domain fusion is the prey; the DNA-binding-domain fusion is the bait. "
                         "These are experimental roles, not biological direction. Match each ORF/construct ID in the source crosswalk; "
                         "the displayed protein order does not assign a protein to a construct."),
                "fields": deepcopy(observation.get("constructs", {}))})
            add_link("PSI-MI assay and role definitions", MI_URL, "definition")
            if observation.get("assay_host_taxon") is None:
                missing.append({"field": "assay_host_taxon", "note": "Experimental host is not supplied here; human participant taxonomy does not identify the host."})
        add_link(observation.get("study"), _publication(observation.get("study")), "publication")
        for locator in observation.get("source_locators", []):
            role = locator.get("role") or "saved source record"
            url = _source_path(run_id, locator.get("locator"))
            if url:
                add_link(role.replace("_", " ").capitalize(), url,
                         "construct_crosswalk" if role == "construct_crosswalk" else "local_source", local=True)
        sections.append({"id": observation["id"] + ":outcome", "title": "Source outcome",
            "text": ("Reported outcome: " + str(observation.get("assay_status", "not supplied")) + ". "
                + ("The observation is excluded from graph edges; a failed or excluded assay does not establish absence of an interaction."
                   if observation.get("evaluable") is False else
                   "This is conditional on the recorded assay and participants; nondetection does not establish universal absence or disease relevance.")),
            "fields": {key: deepcopy(observation.get(key)) for key in
                       ("study", "assay", "assay_status", "participant_taxon", "assay_host_taxon", "source_locators")}})

    qualifiers = deepcopy(assertion.get("qualifiers", {}) if assertion else
                          edges[0].get("qualifiers", {}) if edges else {})
    unknown_qualifiers = sorted(set(qualifiers) - set(QUALIFIERS + CONTEXT_QUALIFIERS))
    if unknown_qualifiers:
        missing.append({"field": "qualifier_interpretation", "note": "Uninterpreted qualifier fields are preserved verbatim: " + ", ".join(unknown_qualifiers) + "."})
    context_only = (not edges and len(observations) == 1 and observations[0].get("source_kind") == "bioplex"
                    and observations[0].get("record_kind") == "cell_line_coassociation_observation")
    record_kind = assertion.get("kind") if assertion else (edges[0].get("record_kind") if edges else
        "cell_line_coassociation_observation" if context_only else "excluded_assay_observation")
    scope_notes = {
        "protein_interaction": "This is a source-reported interaction annotation. Functional association, physical association, direct binding and disease mechanism are different claims; this annotation alone does not establish the latter claims.",
        "pathway_membership": "This record annotates pathway membership. Shared membership alone does not establish direct interaction or disease-specific relevance.",
        "disease_filtered_membership": "A target appeared in a disease-filtered list; detailed association evidence is missing. Membership alone is not a qualified disease assertion.",
        "disease_association": "This is a source-reported disease association. It does not establish a causal mechanism, therapeutic effect or clinical recommendation.",
        "go_annotation": "This record preserves an annotation. The retrieved fields do not resolve GO relation, negation and extensions.",
        "expression_observation": "This is a source-reported expression observation on its original scale. Missing units or values are not inferred.",
        "drug_listing": "This is a target-linked drug listing. It supplies no activity, disease indication or treatment-response assertion.",
        "variant_therapy_response": "Read the complete molecular profile, disease, therapy set, evidence direction and variant origin together. A single variant or drug filter does not establish an isolated effect.",
        "assay_observation": "This is a qualified assay observation between the listed participants. Inspect its method, outcome, constructs and source conditions before interpreting it.",
        "tissue_proximity_observation": "This is enriched proximity in the recorded colorectal-tissue assay and reanalysis. It does not establish direct binding, tumour-specific rewiring, clinical relevance or independent validation.",
        "source_regulatory_observation": "This is source-reported regulation with separate effect, mechanism, site and experimental context. It does not establish colorectal applicability or independent biological validation.",
        "cell_line_coassociation_observation": "This is saved HCT116 tagged-AP-MS context for an already represented protein pair. It adds no graph edge, assertion or acceptance decision. Co-isolation does not establish direct binding or endogenous cell function.",
        "excluded_assay_observation": "This source observation has no evidence edge and no assertion to accept. Its exclusion is not a negative biological result.",
    }
    summary = scope_notes.get(record_kind, "This saved relation is shown verbatim. No additional interpretation is defined for its record kind.")
    if record_kind == "protein_interaction":
        missing.append({"field": "assay_context", "note": "Do not infer assay method, direct binding or an original supporting experiment from a provider label or aggregate score."})
    if record_kind == "expression_observation" and not qualifiers.get("measurement_unit"):
        missing.append({"field": "measurement_unit", "note": "Measurement unit is not supplied; values from different source scales are not combined."})
    missing.append({"field": "independent_evidence_count", "note": INDEPENDENCE_NOTE})
    reuse = _reuse(graph, edges, observations, source_reuse, run_id, add_link)
    review_state = assertion.get("lifecycle_state", "not_recorded") if assertion else "not_applicable" if not edges else "not_recorded"
    review_note = ("This source-context record has no assertion to accept or prune. Its agent-assisted source check is not human expert review or biological validation."
                   if context_only else REVIEW_NOTE)
    review_text = "Local review state: " + review_state + ". " + review_note
    reference_links = [link["id"] for link in links if link["kind"] in {"publication", "source_record", "source_reference", "local_source"}]
    reuse_text = (" ".join(row["explanation"] for row in reuse["records"])
                  if reuse["records"] else reuse["note"] if reuse["status"] == "unverifiable_saved_annotation"
                  else "Source reuse remains unresolved for this selection. " + INDEPENDENCE_NOTE)
    questions = [
        {"id": "what-shows", "question": "What does this record show?",
         "answer": (" ".join(civic_findings) + " Evidence levels are the source's study-type categories, "
                    "not a new confidence estimate or local review decision.") if civic_findings else summary,
         "link_ids": []},
        {"id": "review-state", "question": "Has it been accepted or biologically verified?", "answer": review_text, "link_ids": []},
        {"id": "source-trace", "question": "Where can I inspect its original support?", "answer":
            "Open the original record or publication when supplied. Saved source copies and locators show what this workspace actually retrieved; a source label alone is not a reference.", "link_ids": reference_links},
        {"id": "context", "question": "What context is missing or should I check?", "answer": " ".join(row["note"] for row in missing), "link_ids": [link["id"] for link in links if link["kind"] in {"construct_crosswalk", "definition"}]},
        {"id": "reuse", "question": "Is this independent additional evidence?", "answer": reuse_text, "link_ids": [link["id"] for link in links if link["kind"] == "local_reuse"]},
    ]
    return {"format": FORMAT, "read_only": True, "source_run": run_id,
            "graph_basis_sha256": graph_basis(graph), "snapshot_sha256": graph["snapshot_sha256"],
            "selection": {"id": selection_id, "kind": kind, "record_kind": record_kind},
            "assertion": ({key: deepcopy(assertion.get(key)) for key in
                ("id", "subject", "predicate", "object", "kind", "lifecycle_state", "validation_status", "revision")}
                if assertion else None), "qualifiers": qualifiers,
            "review": {"state": review_state, "note": review_note}, "summary": summary,
            "source_records": sources, "observations": [o["id"] for o in observations],
            "sections": sections, "links": links, "omitted_links": omitted_links,
            "missing_context": missing, "reuse": reuse, "questions": questions,
            "actions": [], "model_calls": 0, "source_fetches": 0,
            "limitations": ["Guidance reports saved source facts; it does not audit papers or establish scientific accuracy.",
                            "This workspace is a bounded extract. Missing entities or references do not establish absence elsewhere.",
                            review_note, INDEPENDENCE_NOTE]}
