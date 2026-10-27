"""Source-qualified IntAct answers using the existing guided-answer envelope.

This view reports preserved evidence records, including their local review
states. It neither traverses PPI paths nor turns curator records into independent
experiments or biological validation.
"""
from collections import Counter
from copy import deepcopy
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from .client import canonical, digest


TEMPLATE = "qualified_assay_evidence.v1"
SOURCE_KIND = "intact_mitab27"
FIELD_GROUPS = (
    "participant_identity", "source_and_publication", "detection_and_type",
    "roles_and_experimental_context", "complex_expansion", "negative",
    "features_and_stoichiometry", "other_missing_values_and_confidence",
)
GROUP_LABELS = {
    "participant_identity": "Participants and source identities",
    "source_and_publication": "Source records and publication",
    "detection_and_type": "Detection methods and interaction type",
    "roles_and_experimental_context": "Roles and experimental context",
    "complex_expansion": "Complex-expansion annotation",
    "negative": "Reported outcome and negative-evidence flag",
    "features_and_stoichiometry": "Features, constructs and stoichiometry",
    "other_missing_values_and_confidence": "Source confidence and cross-references",
}
LIMITATIONS = [
    "These are source-qualified evidence records within the selected exact protein cohort, not general protein-interaction paths or disease-mechanism claims.",
    "Local candidate, accepted and other review states are shown separately from source curation and experimental outcomes. Local acceptance is not biological validation.",
    "A physical association or co-immunoprecipitation record does not establish direct binding. A missing expansion annotation leaves binary experimental origin unknown.",
    "Negative evidence is conditional on its recorded context. An absent record, excluded row or missing annotation does not establish absence of an interaction.",
    "Source A/B order and bait/prey roles remain separate. Host labels describe the source's experimental context; participant taxonomy does not substitute for the host.",
    "Evidence identifiers can be aliases for one record. Multiple records, reciprocal roles and publications are not independent biological confirmations.",
    "Source fidelity, scientific accuracy, novelty and improvement over Pharos are separate questions; this answer alone measures none of them.",
]


def _answer_observation(row):
    from .intact_evidence import answer_observation
    return answer_observation(row)


def _source_link(link):
    if not isinstance(link, dict) or not isinstance(link.get("label"), str):
        raise ValueError("Assay citations require a source label and URL.")
    url = link.get("url")
    if not isinstance(url, str):
        raise ValueError("Assay citations require a source URL.")
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Assay source links must use ordinary HTTP(S) URLs.")
    return link


def _fragments(row):
    value = deepcopy(_answer_observation(row))
    groups = value.get("field_groups")
    if (value.get("observation_id") != row["id"] or not isinstance(value.get("text"), str)
            or not isinstance(groups, list)
            or [group.get("group") for group in groups] != list(FIELD_GROUPS)):
        raise ValueError("IntAct answer must preserve the observation and eight frozen field groups.")
    columns = set()
    for group in groups:
        if not isinstance(group.get("text"), str) or not isinstance(group.get("fields"), list):
            raise ValueError("IntAct answer groups require readable text and source fields.")
        for field in group["fields"]:
            if (not isinstance(field, dict) or not isinstance(field.get("label"), str)
                    or not isinstance(field.get("value"), str)
                    or not isinstance(field.get("columns"), list)
                    or any(type(c) is not int or not 1 <= c <= 42 for c in field["columns"])):
                raise ValueError("IntAct answer fields require readable values and MITAB27 column locators.")
            columns.update(field["columns"])
    if columns != set(range(1, 43)):
        raise ValueError("IntAct answer does not expose all 42 source columns.")
    if not isinstance(value.get("citations"), list):
        raise ValueError("IntAct answer source citations are missing.")
    for citation in value["citations"]:
        _source_link(citation)
    if not isinstance(value.get("qualified_fields"), dict):
        raise ValueError("IntAct answer is missing its source qualifications.")
    return value


def answer_assay_question(graph, protein=None, *, source_run=None):
    """Answer from every selected eligible IntAct row, without review promotion."""
    from .questions import graph_basis
    rows = graph.get("assay_observations")
    summary = graph.get("assay_evidence")
    if (not isinstance(rows, list) or not isinstance(summary, dict)
            or not graph.get("assay_attachment_sha256") or not graph.get("assay_publication_sha256")):
        raise ValueError("Choose a saved run with an attached IntAct evidence publication.")
    if any(not isinstance(row, dict) or row.get("source_kind") != SOURCE_KIND for row in rows):
        raise ValueError("This qualified-answer template supports IntAct MITAB27 records only.")
    if any(type(row.get("evaluable")) is not bool for row in rows):
        raise ValueError("Every assay observation requires an explicit source-eligibility decision.")
    if not rows and summary.get("source_kind") != SOURCE_KIND:
        raise ValueError("An empty attachment requires an explicit IntAct source-kind marker.")
    identifiers = [row.get("id") for row in rows]
    if any(not isinstance(uid, str) or not uid for uid in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Assay observations require unique source-bound identifiers.")
    cohort = {target["id"] for target in graph["targets"]}
    anchor = None
    if protein is not None:
        if not isinstance(protein, str) or not protein.strip():
            raise ValueError("Choose an exact UniProt identifier from the saved cohort.")
        anchor = protein.strip()
        if not anchor.startswith("UniProtKB:"):
            anchor = "UniProtKB:" + anchor
        if anchor not in cohort:
            raise ValueError("Choose an exact UniProt identifier from the saved cohort; symbols are not resolved here.")
    edges = {edge["id"]: edge for edge in graph["edges"]}
    assertions = {assertion["id"]: assertion for assertion in graph["assertions"]}
    results, citations, statements = [], [], []
    selected = [row for row in rows if anchor is None or anchor in row.get("products", [])]
    eligible = [row for row in selected if row.get("evaluable") is True]
    for row in eligible:
        if (not isinstance(row.get("products"), list) or len(row["products"]) != 2
                or not set(row["products"]) <= cohort):
            raise ValueError("An eligible assay record has missing or outside-cohort participants.")
        edge = edges.get(row.get("graph_edge_id"))
        assertion = assertions.get(edge.get("assertion_id")) if edge else None
        if (not edge or not assertion or edge.get("record_kind") != "assay_observation"
                or assertion.get("kind") != "assay_observation"
                or edge["id"] not in assertion.get("evidence_edge_ids", [])
                or edge.get("qualifiers", {}).get("observation_id") != row["id"]
                or set((edge.get("subject"), edge.get("object"))) != set(row["products"])
                or assertion.get("assay_publication_sha256") != graph["assay_publication_sha256"]
                or assertion.get("assay_attachment_sha256") != graph["assay_attachment_sha256"]):
            raise ValueError("Assay evidence, assertion identity or source binding is incomplete.")
        result = _fragments(row)
        cid = "E" + str(len(results) + 1).zfill(3)
        result.update({"citation_id": cid, "assertion_id": assertion["id"],
                       "assertion_revision": assertion["revision"],
                       "local_review_state": assertion["lifecycle_state"],
                       "graph_edge_id": edge["id"], "source_observation": deepcopy(row)})
        results.append(result)
        citations.append({"id": cid, "observation_id": row["id"],
                          "assertion_id": assertion["id"], "revision": assertion["revision"],
                          "review_state": assertion["lifecycle_state"],
                          "source_names": deepcopy(assertion.get("source_names", [])),
                          "used_evidence_edge_ids": [edge["id"]], "source_record_count": 1,
                          "evidence_records": [deepcopy(edge)],
                          "publications": deepcopy(edge.get("publications", [])),
                          "source_links": deepcopy(result["citations"]),
                          "source_locators": deepcopy(row.get("source_locators", []))})
        statements.append({"observation_id": row["id"], "text": result["text"],
                           "review_status": assertion["lifecycle_state"], "citation_ids": [cid]})
    review_counts = dict(sorted(Counter(row["local_review_state"] for row in results).items()))
    overview = (f"Showing {len(results)} qualified source evidence records"
                + (f" involving {anchor}" if anchor else " within this saved cohort")
                + ". All local review states are retained and labeled; records are not independent experiment counts.")
    answer = {
        "question_format": "biograph-steward.guided-question.v1", "template": TEMPLATE,
        "source_run": source_run, "data_kind": graph["data_kind"], "source_kind": SOURCE_KIND,
        "snapshot_sha256": graph["snapshot_sha256"], "snapshot_created_at": graph["snapshot_created_at"],
        "database_version": graph.get("db_version"), "graph_basis_sha256": graph_basis(graph),
        "review_events_sha256": digest(graph.get("review_events", [])),
        "assay_publication_sha256": graph["assay_publication_sha256"],
        "assay_attachment_sha256": graph["assay_attachment_sha256"],
        "question": "What source-qualified assay evidence is recorded" + (f" for {anchor}?" if anchor else " for this protein cohort?"),
        "plan": {"protein": anchor, "scope": deepcopy(graph.get("scope")),
                 "filter_policy": "Exactly selected, source-eligible IntAct observations; no outcome or local review-state exclusion.",
                 "view": "source_records_all_local_review_states", "relations": [],
                 "unsupported_requirements": ["direct binding inference", "disease mechanism inference", "independent evidence counting"]},
        "overview": overview, "results": results, "summary": statements, "citations": citations,
        "availability": {"attached_observations": len(rows), "selected_observations": len(selected),
                         "eligible_selected_observations": len(eligible), "returned_observations": len(results),
                         "excluded_selected_observations": len(selected) - len(eligible),
                         "outside_protein_filter": len(rows) - len(selected),
                         "local_review_states": review_counts},
        "excluded_observations": [deepcopy(row) for row in selected if row.get("evaluable") is not True],
        "source_attachment_summary": deepcopy(summary),
        "limitations": list(LIMITATIONS),
        "interpretation": "Preserved source evidence with separate local review, not unqualified PPI paths or scientific validation.",
        "engine": "deterministic_qualified_evidence_query", "llm_used": False,
    }
    if graph["data_kind"] == "synthetic_demo":
        answer["limitations"].insert(0, "SYNTHETIC SOFTWARE DEMONSTRATION: invented records, not scientific evidence.")
    answer["answer_sha256"] = digest(answer)
    return answer


def _verify(answer):
    from .questions import verify_answer
    verify_answer(answer)
    if answer.get("template") != TEMPLATE:
        raise ValueError("Unsupported qualified assay answer template.")


def answer_text(answer):
    _verify(answer)
    lines = [answer["question"], "", answer["overview"], ""]
    for row in answer["results"]:
        lines += [f'[{row["citation_id"]}] Source evidence record',
                  "Local review: " + row["local_review_state"] + " (not a source outcome)",
                  "Observation: " + row["observation_id"], "Assertion: " + row["assertion_id"]]
        for group in row["field_groups"]:
            lines += ["", GROUP_LABELS[group["group"]], group["text"]]
            for field in group["fields"]:
                lines.append(field["label"] + ": " + field["value"] + " [source columns " + ", ".join(map(str, field["columns"])) + "]")
        lines += ["", "Source links:"]
        lines.extend(link["label"] + ": " + link["url"] for link in row["citations"])
        lines.append("")
    lines += ["Scope and limitations:", *["- " + value for value in answer["limitations"]],
              "", "Pharos cohort snapshot: " + answer["snapshot_sha256"],
              "Assay publication: " + answer["assay_publication_sha256"],
              "Graph/review basis: " + answer["graph_basis_sha256"],
              "Answer: " + answer["answer_sha256"]]
    return "\n".join(lines) + "\n"


def answer_html(answer):
    _verify(answer)
    esc = lambda value: escape(str(value), quote=True)
    sections = []
    for row in answer["results"]:
        groups = []
        for group in row["field_groups"]:
            fields = "".join("<tr><th>" + esc(field["label"]) + "</th><td>" + esc(field["value"])
                             + "</td><td>" + esc(", ".join(map(str, field["columns"]))) + "</td></tr>"
                             for field in group["fields"])
            groups.append('<section data-field-group="' + esc(group["group"]) + '"><h3>'
                          + esc(GROUP_LABELS[group["group"]]) + "</h3><p>" + esc(group["text"])
                          + "</p><table><thead><tr><th>Source field</th><th>Reported value</th><th>MITAB columns</th></tr></thead><tbody>"
                          + fields + "</tbody></table></section>")
        links = " · ".join('<a href="' + esc(_source_link(link)["url"]) + '">' + esc(link["label"]) + "</a>"
                           for link in row["citations"])
        sections.append('<section class="observation" data-observation-id="' + esc(row["observation_id"])
                        + '" id="' + esc(row["citation_id"]) + '"><h2>[' + esc(row["citation_id"])
                        + "] Source evidence record</h2><p><strong>Local review: " + esc(row["local_review_state"])
                        + "</strong> — separate from source curation and experimental outcome.</p><p>Observation: "
                        + esc(row["observation_id"]) + "<br>Assertion: " + esc(row["assertion_id"])
                        + "</p><p>" + links + "</p>" + "".join(groups) + "</section>")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>BioGraph Steward — qualified assay evidence</title><style>body{max-width:1150px;margin:32px auto;padding:20px;font:16px/1.5 system-ui;color:#172b3a}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #cbd5dc;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}td{white-space:pre-wrap}.observation{border-top:3px solid #26818b;margin:32px 0;padding-top:16px}a{color:#086b85}p{overflow-wrap:anywhere}</style></head><body><h1>'
            + esc(answer["question"]) + "</h1><p>" + esc(answer["overview"]) + "</p>" + "".join(sections)
            + "<h2>Scope and limitations</h2><ul>" + "".join("<li>" + esc(value) + "</li>" for value in answer["limitations"])
            + "</ul><h2>Source bindings</h2><p>Pharos cohort snapshot: " + esc(answer["snapshot_sha256"])
            + "<br>Assay publication: " + esc(answer["assay_publication_sha256"])
            + "<br>Graph/review basis: " + esc(answer["graph_basis_sha256"])
            + "<br>Answer: " + esc(answer["answer_sha256"]) + "</p></body></html>")


def save_extra_files(answer, directory):
    """Write self-contained evidence rows alongside the ordinary answer files."""
    _verify(answer)
    directory = Path(directory)
    bindings = {key: answer[key] for key in ("answer_sha256", "graph_basis_sha256", "snapshot_sha256",
                                             "assay_publication_sha256", "assay_attachment_sha256", "source_run")}
    rows = [{**deepcopy(row), "answer_bindings": deepcopy(bindings)} for row in answer["results"]]
    (directory / "assay_evidence.jsonl").write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    (directory / "assay_excluded_observations.jsonl").write_text(
        "".join(canonical(row) + "\n" for row in answer["excluded_observations"]), encoding="utf-8")
