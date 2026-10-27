#!/usr/bin/env python3
"""Compare an ordinary workbench answer/export with consumed IntAct development rows.

The independent oracle is the frozen eligibility ledger plus the original raw
rows and official JAMI observations. No importer/answer projection is called to
construct expected values. This is bounded source fidelity, not biological truth.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow  # noqa: E402

FORMAT = "biograph-steward.intact-development-fidelity.v1"
DEVELOPMENT = ("40075158", "40404733", "40071126", "40739265")
PROTOCOL = ROOT / "docs/evaluations/intact_fidelity_20261026_protocol.json"
AMENDMENT = ROOT / "docs/evaluations/intact_fidelity_20261026_semantic_amendment.json"
EXPECTED_PROTOCOL_SHA = "d4948f584b8eed374ddfa49084ee58f1fb352d3d68a6630a202bf25742f8920a"
EXPECTED_AMENDMENT_SHA = "2cd2cb485836228ce71dd9d62201c61dd5de45d18563894ac883f188f245e98c"
EXPECTED_INSPECTION_SHA = "f329ef329ce23eaf3ac403890208fa5526a57124999251e7c746f3da667719c2"
EXPECTED_LEDGER_SHA = "232ad603873331a0f19e3447ec8c430e93dd7b5802367190be8cd956c6a16a2b"
EXPECTED_READER_SHA = {
    "40075158": "e9389e26b9169d46aff2f44d106dcc15d6f19667ce872ef47fe1eb17ff3a1cbb",
    "40404733": "c588b5ebac1791957ee80f9d4f38228980c15cf65e65830c037656a3f740781c",
    "40071126": "a81d210892ea39df01391a632c1c62dab33d2d59d4943d9ddf7b6d8c676f82ae",
    "40739265": "f3481bdbf7d34393aabb2c6be8f6ac10dff4fae3454efbfac9ce632e142e4615",
}
PARSED_GROUPS = {
    "participant_identity": ("primary_ids_a", "primary_ids_b", "alternative_ids_a", "alternative_ids_b",
                             "taxa_a", "taxa_b", "interactor_types_a", "interactor_types_b"),
    "source_and_publication": ("publication_ids", "source_databases", "evidence_ids"),
    "detection_and_type": ("detection_methods", "interaction_types", "identification_methods_a", "identification_methods_b"),
    "roles_and_experimental_context": ("biological_roles_a", "biological_roles_b", "experimental_roles_a",
                                       "experimental_roles_b", "interaction_annotations", "host_taxa"),
    "complex_expansion": ("complex_expansion", "evidence_ids"),
    "negative": (), "features_and_stoichiometry": (), "other_missing_values_and_confidence": (),
}
SIDE_COLUMNS = {1: "A", 2: "B", 3: "A", 4: "B", 5: "A", 6: "B", 10: "A", 11: "B",
                17: "A", 18: "B", 19: "A", 20: "B", 21: "A", 22: "B", 23: "A", 24: "B",
                26: "A", 27: "B", 33: "A", 34: "B", 37: "A", 38: "B", 39: "A", 40: "B", 41: "A", 42: "B"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def key(source):
    return tuple(source.get(name) for name in ("publication_id", "artifact_sha256", "source_line"))


def norm(text):
    return " ".join(str(text).split())


class VisibleGroups(HTMLParser):
    """Collect actual visible observation/group text; hidden JSON earns no credit."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.groups = defaultdict(list)
        self.links = defaultdict(list)
        self.table_rows = defaultdict(list)
        self.current_row = None
        self.current_cell = None
        self.observations = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        previous = self.stack[-1] if self.stack else (None, None, None, False)
        observation = attrs.get("data-observation-id", previous[1])
        group = attrs.get("data-field-group", previous[2])
        hidden = (previous[3] or tag in {"script", "style", "template", "textarea"}
                  or "hidden" in attrs or attrs.get("aria-hidden") == "true"
                  or "hidden" in attrs.get("class", "").split()
                  or bool(re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", attrs.get("style", ""), re.I)))
        if observation and not hidden:
            self.observations.add(observation)
            if tag == "a" and isinstance(attrs.get("href"), str):
                self.links[observation].append(attrs["href"])
            if group and tag == "tr":
                self.current_row = {"key": (observation, group), "cells": []}
            elif group and tag in {"td", "th"} and self.current_row is not None:
                self.current_cell = []
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, observation, group, hidden))

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.current_cell is not None and self.current_row is not None:
            self.current_row["cells"].append(norm("".join(self.current_cell)))
            self.current_cell = None
        if tag == "tr" and self.current_row is not None:
            self.table_rows[self.current_row["key"]].append(self.current_row["cells"])
            self.current_row = None
            self.current_cell = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack:
            _, observation, group, hidden = self.stack[-1]
            if observation and group and not hidden:
                self.groups[(observation, group)].append(data)
                if self.current_cell is not None:
                    self.current_cell.append(data)

    def text(self, observation, group):
        return norm(" ".join(self.groups.get((observation, group), [])))


def field_groups():
    if sha(PROTOCOL) != EXPECTED_PROTOCOL_SHA or sha(AMENDMENT) != EXPECTED_AMENDMENT_SHA:
        raise ValueError("The original protocol or mandatory amendment changed.")
    return {group["group"]: group["columns_1based"] for group in read_json(PROTOCOL)["field_contract"]}


def load_reference(inspection):
    """Open only the four previously consumed development sources, never reserved."""
    inspection = Path(inspection).resolve()
    report = read_json(inspection / "report.json")
    if report.get("reserved_final_rows_opened") is not False:
        raise ValueError("Reference inspection must preserve the reserved access boundary.")
    study_pmids = [study["publication_id"].removeprefix("pubmed:") for study in report["studies"]]
    if study_pmids != list(DEVELOPMENT):
        raise ValueError("Use exactly the original four consumed development publications.")
    if sha(inspection / "report.json") != EXPECTED_INSPECTION_SHA or sha(inspection / "row_ledger.jsonl") != EXPECTED_LEDGER_SHA:
        raise ValueError("Original development inspection or eligibility mask changed; do not redefine the denominator.")
    ledger = read_jsonl(inspection / "row_ledger.jsonl")
    ledger_by_key = {key(row): row for row in ledger}
    if len(ledger_by_key) != len(ledger):
        raise ValueError("Reference row locators are not unique.")
    records, source_files = [], {}
    for study in report["studies"]:
        pmid = study["publication_id"].removeprefix("pubmed:")
        # This finite whitelist is checked before any source-body file is opened.
        if pmid not in DEVELOPMENT:
            raise ValueError("Reserved or unapproved reference access is forbidden.")
        raw_path = ROOT / "runs/intact_fidelity_preparation_20261026/opaque_sources" / (pmid + ".txt")
        raw = raw_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != study["source_sha256"]:
            raise ValueError("Consumed development artifact bytes changed.")
        reader_path = inspection / (pmid + "_reader.jsonl")
        if sha(reader_path) != EXPECTED_READER_SHA[pmid]:
            raise ValueError("The original official-reader reference observations changed.")
        rows = read_jsonl(reader_path)
        lines = raw.decode("utf-8").splitlines()
        if len(rows) != len(lines):
            raise ValueError("Original reader does not account for every physical development row.")
        source_files[pmid] = {"raw_path": raw_path, "raw": raw,
                              "reader_path": reader_path, "reader": reader_path.read_bytes()}
        for number, (row, line) in enumerate(zip(rows, lines), 1):
            source = {"publication_id": study["publication_id"], "artifact_sha256": study["source_sha256"], "source_line": number}
            record = ledger_by_key.get(key(source))
            if (record is None or row.get("line_number") != number or row.get("raw_line") != line
                    or row.get("raw_cells") != line.split("\t")
                    or record.get("raw_row_sha256") != hashlib.sha256(line.encode("utf-8")).hexdigest()):
                raise ValueError("Original raw, reader and eligibility locator binding differs.")
            records.append({"ledger": record, "reader_record": row})
    if len(records) != len(ledger) or sum(row["eligible"] for row in ledger) != 4:
        raise ValueError("The frozen four-row eligible denominator changed.")
    if sum(row["kind"] == "evidence" for row in ledger) != 14:
        raise ValueError("The original fourteen-evidence-row accounting changed.")
    return records, ledger, source_files


def _values(reader, name):
    return ((reader.get("source_fields") or {}).get(name) or {}).get("values", [])


def _negative(reader):
    literal = reader["raw_cells"][35]
    return {"literal": literal, "value": literal == "true",
            "origin": "mitab27_default_false" if literal == "-" else "explicit"}


def _qualifications(reader):
    literal = reader["raw_cells"][15]
    return {"negative": _negative(reader),
            "expansion": {"literal": literal, "annotation_origin": "not_supplied" if literal == "-" else "supplied",
                          "methods": _values(reader, "complex_expansion")},
            "binary_origin": "unknown_no_inference", "direct_binding_inferred": False,
            "independent_evidence_count": None}


def _group_semantics(group, reader):
    qualifications = _qualifications(reader)
    return {
        "participant_identity": {"identity_basis": "exact source primary identifiers", "A_B_orientation_preserved": True},
        "source_and_publication": {"independent_evidence_count": None},
        "detection_and_type": {"direct_binding_inferred": False},
        "roles_and_experimental_context": {"host_labels_are_literal": True, "cell_line_identifier_inferred": False},
        "complex_expansion": {**qualifications["expansion"], "binary_origin": "unknown_no_inference"},
        "negative": qualifications["negative"],
        "features_and_stoichiometry": {"sequence_or_construct_identity_inferred": False},
        "other_missing_values_and_confidence": {"confidence_is_calibrated_truth_probability": False},
    }[group]


def _reference_links(reader, source):
    links = [("source_artifact", source["artifact_sha256"], source["url"])]
    for field in ("publication_ids", "evidence_ids"):
        for item in _values(reader, field):
            database = ((item.get("database") or {}).get("name") or "").lower()
            identifier = item.get("id")
            if database == "pubmed":
                url = "https://pubmed.ncbi.nlm.nih.gov/" + quote(identifier, safe="") + "/"
            elif database in {"intact", "imex"}:
                url = "https://www.ebi.ac.uk/intact/search?query=" + quote(identifier, safe="")
            else:
                continue
            links.append(("publication" if field == "publication_ids" else "evidence", database + ":" + identifier, url))
    return links


def _semantics_readable(group, text, reader):
    text = text.casefold()
    negative = _negative(reader)
    if group == "negative":
        polarity = "negative" if negative["value"] else "positive"
        origin = "default" if negative["origin"] == "mitab27_default_false" else "explicit"
        return polarity in text and origin in text
    if group == "complex_expansion" and reader["raw_cells"][15] == "-":
        return bool(re.search(r"not supplied|not provided|no expansion annotation", text)) and bool(
            re.search(r"unknown|not established|not inferred", text))
    if group == "detection_and_type":
        return "direct binding" in text and bool(re.search(r"\bnot\b|doesn't|cannot", text))
    if group == "other_missing_values_and_confidence" and reader["raw_cells"][14] != "-":
        return "probability" in text and bool(re.search(r"\bnot\b|isn't|cannot", text))
    return bool(norm(text))


def evaluate_rows(references, observations, results, exported_observations, answer_export, html_text,
                  graph_edges=None, columns=None, answer_bindings=None, assessment_stage="full_workbench"):
    """Evaluate values using original reader records, never the adapter implementation."""
    if assessment_stage not in {"full_workbench", "source_publication_fidelity_only"}:
        raise ValueError("Unknown source-fidelity assessment boundary.")
    publication_only = assessment_stage == "source_publication_fidelity_only"
    columns = columns or field_groups()
    visible = VisibleGroups(); visible.feed(html_text)
    imported = defaultdict(list)
    for observation in observations:
        imported[key(observation.get("source") or {})].append(observation)
    exported = defaultdict(list)
    for observation in exported_observations:
        exported[key(observation.get("source") or {})].append(observation)
    answers = defaultdict(list)
    for result in results:
        answers[result.get("observation_id")].append(result)
    answer_exports = defaultdict(list)
    for result in answer_export:
        answer_exports[result.get("observation_id")].append(result)
    edges = {edge.get("id"): edge for edge in graph_edges or []}
    rows = []
    expected_keys = {key(ref["ledger"]) for ref in references if ref["ledger"]["eligible"]}
    for ref in references:
        ledger, reader = ref["ledger"], ref["reader_record"]
        if not ledger["eligible"]:
            continue
        checks = []
        def check(name, actual, expected, category):
            checks.append({"name": name, "passed": actual == expected, "category": category,
                           "expected": deepcopy(expected), "observed": deepcopy(actual)})
        candidates = imported.get(key(ledger), [])
        check("one_imported_observation", len(candidates), 1, "row_accounting")
        observation = candidates[0] if len(candidates) == 1 else {}
        identifier = observation.get("id")
        answered = answers.get(identifier, []) if identifier else []
        packet_rows = exported.get(key(ledger), [])
        exported_answer = answer_exports.get(identifier, []) if identifier else []
        check("one_stored_display_fragment" if publication_only else "one_answer_result", len(answered), 1, "row_accounting")
        if not publication_only:
            check("one_packet_observation", len(packet_rows), 1, "row_accounting")
            check("one_answer_export_result", len(exported_answer), 1, "row_accounting")
        result = answered[0] if len(answered) == 1 else {}
        if not publication_only:
            check("packet_retains_complete_observation", packet_rows[0] if len(packet_rows) == 1 else None,
                  observation if observation else None, "serialized_preservation")
            exported_result = {name: value for name, value in exported_answer[0].items() if name != "answer_bindings"} if len(exported_answer) == 1 else None
            check("answer_export_retains_complete_result", exported_result,
                  result if result else None, "serialized_preservation")
            if answer_bindings is not None:
                check("answer_export_bindings", exported_answer[0].get("answer_bindings") if len(exported_answer) == 1 else None,
                      answer_bindings, "source_and_publication")
            check("answer_source_observation", result.get("source_observation"), observation or None, "serialized_preservation")
        expected_source = {name: ledger[name] for name in
                           ("publication_id", "artifact_sha256", "release", "source_line", "raw_row_sha256")}
        expected_source["url"] = ("https://ftp.ebi.ac.uk/pub/databases/intact/" + ledger["release"]
                                  + "/psimitab/pmid/2025/" + ledger["publication_id"].removeprefix("pubmed:") + ".txt")
        check("source_locator", observation.get("source"), expected_source, "source_and_publication")
        expected_links = _reference_links(reader, expected_source)
        for name, link_rows in (("imported_citations", observation.get("citations") or []),
                                ("answer_citations", result.get("citations") or [])):
            check(name, [(link.get("kind"), link.get("identifier"), link.get("url")) for link in link_rows],
                  expected_links, "source_and_publication")
        expected_visible_links = {link[2] for link in expected_links}
        if publication_only:
            expected_visible_links.add("source/" + ledger["publication_id"].removeprefix("pubmed:") + ".txt")
        check("visible_source_links", sorted(set(visible.links.get(identifier, []))),
              sorted(expected_visible_links), "source_and_publication")
        check("all_raw_cells", observation.get("raw_cells"), reader["raw_cells"], "serialized_preservation")
        check("full_official_source_fields", observation.get("source_fields"), reader.get("source_fields"), "serialized_preservation")
        check("original_reader_record", observation.get("reader_record"), reader, "serialized_preservation")
        check("qualification_semantics", observation.get("qualifications"), _qualifications(reader), "critical_qualification")
        for name, expected in (("evaluable", True), ("biologically_validated", False),
                               ("independent_evidence_count", None), ("source_kind", "intact_mitab27")):
            check("source_claim." + name, observation.get(name), expected, "critical_qualification")
        check("qualified_outcome", observation.get("assay_status"),
              "curated_negative" if _negative(reader)["value"] else "curated_positive", "negative")
        check("full_assay_host_values", observation.get("assay_hosts"), _values(reader, "host_taxa"),
              "roles_and_experimental_context")
        source_participants = {part.get("side"): part for part in (observation.get("participants") or [])}
        original_participants = {part.get("side"): part for part in (reader.get("interaction") or {}).get("participants") or []}
        for index, side in enumerate(("a", "b")):
            participant = source_participants.get(side.upper(), {})
            primary = _values(reader, "primary_ids_" + side)
            uniprot = [item["id"] for item in primary if ((item.get("database") or {}).get("name") or "").lower() == "uniprotkb"]
            check("participant_" + side + ".product", participant.get("product_id"),
                  "UniProtKB:" + uniprot[0] if len(set(uniprot)) == 1 else None, "participant_identity")
            for destination, source in (("primary_ids", "primary_ids_"), ("alternative_ids", "alternative_ids_"),
                                        ("taxa", "taxa_"), ("interactor_types", "interactor_types_"),
                                        ("biological_roles", "biological_roles_"), ("experimental_roles", "experimental_roles_"),
                                        ("identification_methods", "identification_methods_")):
                check("participant_" + side + "." + destination, participant.get(destination),
                      _values(reader, source + side), "participant_identity" if destination in
                      {"primary_ids", "alternative_ids", "taxa", "interactor_types"} else "roles_and_experimental_context")
            for destination, column in (("aliases_raw", 5 + index), ("features_raw", 37 + index), ("stoichiometry_raw", 39 + index)):
                check("participant_" + side + "." + destination, participant.get(destination), reader["raw_cells"][column - 1],
                      "features_and_stoichiometry" if destination != "aliases_raw" else "participant_identity")
            check("participant_" + side + ".reader_fields", participant.get("reader_fields"),
                  original_participants.get(side.upper()), "features_and_stoichiometry")
            check("participant_" + side + ".identity_not_inferred", participant.get("identity_inferred"), False,
                  "participant_identity")
        group_results = {}
        displayed = {group.get("group"): group for group in result.get("field_groups") or []}
        imported_groups = observation.get("qualified_fields") or {}
        check("answer_qualified_fields", result.get("qualified_fields"), imported_groups if observation else None,
              "serialized_preservation")
        for group, expected_columns in columns.items():
            projected = imported_groups.get(group) or {}
            raw_fields = projected.get("raw_fields") or []
            values_by_column = {item.get("column"): item.get("value") for item in raw_fields}
            raw_ok = (len(raw_fields) == len(expected_columns) and values_by_column ==
                      {column: reader["raw_cells"][column - 1] for column in expected_columns})
            check(group + ".raw_column_values", raw_ok, True, group)
            expected_parsed = {name: _values(reader, name) for name in PARSED_GROUPS[group]}
            parsed_ok = projected.get("parsed_fields") == expected_parsed and projected.get("semantics") == _group_semantics(group, reader)
            check(group + ".full_parsed_values", projected.get("parsed_fields"), expected_parsed, group)
            check(group + ".qualified_semantics", projected.get("semantics"), _group_semantics(group, reader), group)
            if group == "features_and_stoichiometry":
                expected_features = [{"side": side, "features": (original_participants.get(side) or {}).get("features"),
                                      "stoichiometry": (original_participants.get(side) or {}).get("stoichiometry")}
                                     for side in ("A", "B")]
                feature_ok = projected.get("reader_fields") == expected_features
                parsed_ok = parsed_ok and feature_ok
                check(group + ".official_features_and_stoichiometry", projected.get("reader_fields"), expected_features, group)
            displayed_group = displayed.get(group) or {}
            display_fields = displayed_group.get("fields") or []
            display_by_column = {column: field.get("value") for field in display_fields for column in field.get("columns") or []}
            display_values_ok = display_by_column == {column: reader["raw_cells"][column - 1] for column in expected_columns}
            check(group + ".readable_labeled_values", display_values_ok, True, group)
            labels_ok = bool(display_fields) and all(
                isinstance(field.get("label"), str) and bool(field["label"].strip())
                and all(column not in SIDE_COLUMNS or bool(re.search(r"\b" + SIDE_COLUMNS[column] + r"\b", field["label"]))
                        for column in field.get("columns") or []) for field in display_fields)
            check(group + ".source_side_labels", labels_ok, True, group)
            actual_text = visible.text(identifier, group) if identifier else ""
            text_values_ok = bool(actual_text) and all(
                norm(reader["raw_cells"][column - 1]) in actual_text for column in expected_columns
                if reader["raw_cells"][column - 1] != "-")
            actual_table_rows = visible.table_rows.get((identifier, group), [])
            table_fields_ok = bool(display_fields) and all(
                [norm(field["label"]), norm(field["value"]), norm(", ".join(map(str, field["columns"])))] in actual_table_rows
                or [norm(", ".join(map(str, field["columns"]))), norm(field["label"]), norm(field["value"])] in actual_table_rows
                for field in display_fields)
            semantic_text_ok = _semantics_readable(group, actual_text, reader)
            check(group + ".visible_source_values", text_values_ok, True, group)
            check(group + ".visible_column_label_value_binding", table_fields_ok, True, group)
            check(group + ".visible_semantic_qualification", semantic_text_ok, True, group)
            group_results[group] = {"raw_preserved": raw_ok, "structured_preserved": parsed_ok,
                                    "readable_covered": display_values_ok and labels_ok and text_values_ok and table_fields_ok and semantic_text_ok}
        if graph_edges is not None:
            edge = edges.get(observation.get("graph_edge_id")) or {}
            check("qualified_graph_edge_observation", (edge.get("qualifiers") or {}).get("observation_id"), identifier,
                  "independent_row_identity")
            check("graph_edge_remains_assay_observation", edge.get("record_kind"), "assay_observation", "independent_row_identity")
            expected_products = [source_participants.get(side, {}).get("product_id") for side in ("A", "B")]
            check("observation_preserves_participant_products", observation.get("products"), expected_products, "participant_identity")
            check("graph_edge_source_endpoints", [edge.get("subject"), edge.get("object")], expected_products, "participant_identity")
            check("graph_edge_qualified_predicate", edge.get("predicate"), "biograph:has_assay_observation_with",
                  "critical_qualification")
        serialized_complete = all(len(items) == 1 for items in
                                  ((candidates, answered) if publication_only else (candidates, answered, packet_rows, exported_answer)))
        complete = (serialized_complete and set(imported_groups) == set(columns) and set(displayed) == set(columns)
                    and all(visible.text(identifier, group) for group in columns))
        rows.append({"source": expected_source, "observation_id": identifier, "completed": complete,
                     "serialized_records_present": serialized_complete,
                     "strict_fidelity": bool(checks) and all(item["passed"] for item in checks),
                     "groups": group_results, "checks": checks,
                     "negative_literal": reader["raw_cells"][35],
                     "expansion_stratum": "not_supplied" if reader["raw_cells"][15] == "-" else "supplied"})
    extra = [list(locator) for locator in imported if locator not in expected_keys]
    duplicate_ids = [identifier for identifier, count in Counter(item.get("id") for item in observations).items() if count > 1]
    checked_edges = graph_edges or []
    if not publication_only:
        checked_edges = [edge for edge in checked_edges if edge.get("record_kind") == "assay_observation"]
    expected_edge_ids = sorted(observation.get("graph_edge_id") for observation in observations if observation.get("graph_edge_id"))
    actual_edge_ids = [edge.get("id") for edge in checked_edges]
    global_checks = []
    if graph_edges is not None:
        global_checks = [{"name": "source_observation_graph_edge_bijection", "passed":
                          sorted(actual_edge_ids, key=str) == expected_edge_ids,
                          "expected": expected_edge_ids, "observed": sorted(actual_edge_ids, key=str)},
                         {"name": "graph_edge_ids_unique", "passed": len(actual_edge_ids) == len(set(actual_edge_ids))}]
    return {"rows": rows, "unexpected_observation_locators": extra, "duplicate_observation_ids": duplicate_ids,
            "global_checks": global_checks}


def _fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None,
            "status": "evaluated" if denominator else "unevaluated_empty_stratum"}


def summarize(evaluation, references):
    rows = evaluation["rows"]
    denominator = sum(ref["ledger"]["eligible"] for ref in references)
    per_study = []
    for pmid in DEVELOPMENT:
        selected = [row for row in rows if row["source"]["publication_id"] == "pubmed:" + pmid]
        per_study.append({"publication_id": "pubmed:" + pmid,
                          "strict_fidelity": _fraction(sum(row["strict_fidelity"] for row in selected), len(selected))})
    evaluated_studies = [row["strict_fidelity"]["value"] for row in per_study if row["strict_fidelity"]["value"] is not None]
    completed = sum(row["completed"] for row in rows)
    strict = sum(row["strict_fidelity"] for row in rows)
    errors = Counter(check["category"] for row in rows for check in row["checks"] if not check["passed"])
    groups = {group: {metric: _fraction(sum(row["groups"][group][metric] for row in rows), denominator)
                       for metric in ("raw_preserved", "structured_preserved", "readable_covered")}
              for group in PARSED_GROUPS}
    strata = {}
    for key_name, values in (("negative_literal", ("true", "false", "-")), ("expansion_stratum", ("supplied", "not_supplied"))):
        strata[key_name] = {value: _fraction(sum(row["strict_fidelity"] for row in rows if row[key_name] == value),
                                           sum(row[key_name] == value for row in rows)) for value in values}
    return {"coverage": _fraction(completed, denominator), "strict_fidelity": _fraction(strict, denominator),
            "conditional_fidelity": _fraction(strict, completed), "per_field_group": groups,
            "per_publication": per_study,
            "macro_strict_fidelity": sum(evaluated_studies) / len(evaluated_studies) if evaluated_studies else None,
            "eligible_publications_in_macro": len(evaluated_studies), "field_error_counts": dict(errors), "strata": strata}


def evaluate(inspection, run, answer, packet, out):
    out = Path(out).absolute()
    if out.exists() or out.is_symlink():
        raise ValueError("Choose a new evaluation directory; previous results must remain unchanged.")
    inspection, run, answer, packet = map(lambda path: Path(path).resolve(), (inspection, run, answer, packet))
    columns = field_groups()
    references, ledger, sources = load_reference(inspection)
    inputs = [PROTOCOL, AMENDMENT, inspection / "report.json", inspection / "row_ledger.jsonl",
              run / "graph.json", run / "assay_observations.json", answer / "question.json", answer / "report.html",
              answer / "assay_evidence.jsonl", packet / "assay_observations.jsonl"]
    for pmid, source in sources.items():
        inputs.extend([source["raw_path"], source["reader_path"]])
        for prefix in (run / "assay_source", packet / "source/assay_source"):
            inputs.extend([prefix / "source" / (pmid + ".txt"), prefix / "reader" / (pmid + ".jsonl")])
    inputs.extend([run / "assay_source/row_ledger.jsonl", packet / "source/assay_source/row_ledger.jsonl"])
    bindings = {str(path): sha(path) for path in inputs}
    out.mkdir(parents=True, exist_ok=False)
    commitment = {"format": FORMAT + ".commitment", "created_at": utcnow(), "input_sha256": bindings,
                  "evaluator_sha256": sha(__file__), "protocol_sha256": EXPECTED_PROTOCOL_SHA,
                  "amendment_sha256": EXPECTED_AMENDMENT_SHA, "split": "consumed_development_only",
                  "eligible_denominator": 4, "evidence_row_denominator": 14, "physical_rows": 18,
                  "reserved_final_rows_opened": False}
    (out / "commitment.json").write_text(json.dumps(commitment, indent=2) + "\n")
    graph = read_json(run / "graph.json")
    observations = read_json(run / "assay_observations.json")
    answered = read_json(answer / "question.json")
    evaluated = evaluate_rows(references, observations, answered.get("results") or [],
                              read_jsonl(packet / "assay_observations.jsonl"), read_jsonl(answer / "assay_evidence.jsonl"),
                              (answer / "report.html").read_text(), graph_edges=graph.get("edges") or [], columns=columns,
                              answer_bindings={name: answered[name] for name in
                                  ("answer_sha256", "graph_basis_sha256", "snapshot_sha256", "assay_publication_sha256",
                                   "assay_attachment_sha256", "source_run")})
    preservation = []
    for prefix in (run / "assay_source", packet / "source/assay_source"):
        preservation.append({"name": str(prefix / "row_ledger.jsonl"),
                             "passed": (prefix / "row_ledger.jsonl").read_bytes() == (inspection / "row_ledger.jsonl").read_bytes()})
        for pmid, source in sources.items():
            for kind, filename, expected in (("source", pmid + ".txt", source["raw"]),
                                              ("reader", pmid + ".jsonl", source["reader"])):
                path = prefix / kind / filename
                preservation.append({"name": str(path), "passed": path.read_bytes() == expected})
    preservation.append({"name": "graph_observation_ledger", "passed": graph.get("assay_observations") == observations})
    preservation.append({"name": "answer_content_seal", "passed": answered.get("answer_sha256") == digest(
        {name: value for name, value in answered.items() if name != "answer_sha256"})})
    for name in ("snapshot_sha256", "assay_publication_sha256", "assay_attachment_sha256"):
        preservation.append({"name": "answer_graph_binding." + name, "passed": answered.get(name) == graph.get(name)})
    preservation.append({"name": "input_hashes_unchanged", "passed": all(sha(path) == value for path, value in bindings.items())})
    metrics = summarize(evaluated, references)
    passed = (metrics["strict_fidelity"]["numerator"] == metrics["strict_fidelity"]["denominator"]
              and all(item["passed"] for item in preservation) and not evaluated["unexpected_observation_locators"]
              and not evaluated["duplicate_observation_ids"] and all(item["passed"] for item in evaluated["global_checks"]))
    result = {"format": FORMAT, "created_at": utcnow(), "status": "passed" if passed else "failed",
              "commitment": commitment, "reference_accounting": {"physical_rows": len(ledger),
                  "evidence_rows": sum(row["kind"] == "evidence" for row in ledger),
                  "eligible_rows": sum(row["eligible"] for row in ledger),
                  "excluded_evidence_rows": sum(row["kind"] == "evidence" and not row["eligible"] for row in ledger)},
              "metrics": metrics, "row_evaluation": evaluated, "source_preservation_checks": preservation,
              "model_calls": 0, "gpu_runs": 0, "reserved_final_rows_opened": False,
              "interpretation": "Development-only source fidelity and bounded readable coverage. Visible-value checks and deterministic qualification checks do not establish unrestricted semantic or biological accuracy.",
              "limitations": ["Four eligible rows from two studies and two protein pairs; all four original studies remain accounted for.",
                  "Eligible real negative/default-polarity and expanded strata are empty and remain unevaluated.",
                  "No independent biological accuracy, direct-binding inference, graph-prediction improvement or organizer score is measured."]}
    result["content_sha256"] = digest(result)
    (out / "report.json").write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return result


def evaluate_publication(inspection, publication, out):
    """Assess the real reusable publication stage without inventing app artifacts."""
    out = Path(out).absolute()
    if out.exists() or out.is_symlink():
        raise ValueError("Choose a new evaluation directory; previous results must remain unchanged.")
    inspection, publication = Path(inspection).resolve(), Path(publication).resolve()
    columns = field_groups()
    references, ledger, sources = load_reference(inspection)
    manifest = read_json(publication / "publication.json")
    evidence = read_json(publication / "evidence.json")
    graph = read_json(publication / "graph.json")
    if (manifest.get("format") != "biograph-steward.intact-evidence-publication.v1"
            or evidence.get("format") != "biograph-steward.intact-qualified-evidence.v1"):
        raise ValueError("Use an actual IntAct source-evidence publication.")
    files = {str(path.relative_to(publication)): sha(path) for path in sorted(publication.rglob("*"))
             if path.is_file() and path != publication / "publication.json"}
    inputs = [PROTOCOL, AMENDMENT, inspection / "report.json", inspection / "row_ledger.jsonl",
              publication / "publication.json", *(publication / name for name in files)]
    for source in sources.values():
        inputs.extend([source["raw_path"], source["reader_path"]])
    bindings = {str(path): sha(path) for path in inputs}
    commitment = {"format": FORMAT + ".commitment", "created_at": utcnow(),
                  "assessment_stage": "source_publication_fidelity_only", "input_sha256": bindings,
                  "evaluator_sha256": sha(__file__), "protocol_sha256": EXPECTED_PROTOCOL_SHA,
                  "amendment_sha256": EXPECTED_AMENDMENT_SHA, "split": "consumed_development_only",
                  "eligible_denominator": 4, "evidence_row_denominator": 14, "physical_rows": 18,
                  "reserved_final_rows_opened": False,
                  "full_comparison_status": "not_run"}
    out.mkdir(parents=True, exist_ok=False)
    (out / "commitment.json").write_text(json.dumps(commitment, indent=2) + "\n")
    observations = evidence.get("observations") or []
    # These are the actual fragments stored by the publisher and its actual
    # HTML viewer. No question, Pharos run, answer ZIP or gold packet is made.
    displays = [observation["display"] for observation in observations if isinstance(observation.get("display"), dict)]
    evaluated = evaluate_rows(references, observations, displays, [], [],
                              (publication / "index.html").read_text(encoding="utf-8"),
                              graph_edges=graph.get("edges") or [], columns=columns,
                              assessment_stage="source_publication_fidelity_only")
    preservation = [
        {"name": "publication_content_seal", "passed": manifest.get("content_sha256") == digest(
            {name: value for name, value in manifest.items() if name != "content_sha256"})},
        {"name": "publication_file_inventory", "passed": manifest.get("files") == files},
        {"name": "evidence_content_seal", "passed": evidence.get("content_sha256") == digest(
            {name: value for name, value in evidence.items() if name != "content_sha256"})},
        {"name": "standalone_graph_export", "passed": graph == evidence.get("graph")},
        {"name": "complete_original_row_ledger", "passed":
            (publication / "row_ledger.jsonl").read_bytes() == (inspection / "row_ledger.jsonl").read_bytes()},
    ]
    projected_ledger = evidence.get("row_ledger") or []
    by_locator = {key(row): row for row in projected_ledger}
    preservation.append({"name": "projected_physical_row_accounting", "passed":
                         len(projected_ledger) == len(references) == len(by_locator)})
    for ref in references:
        original = ref["ledger"]
        projected = by_locator.get(key(original), {})
        expected = {**original, "reader_record": ref["reader_record"],
                    "source_file": "source/" + original["publication_id"].removeprefix("pubmed:") + ".txt",
                    "reader_file": "reader/" + original["publication_id"].removeprefix("pubmed:") + ".jsonl"}
        preservation.append({"name": "projected_source_row." + original["publication_id"] + "." + str(original["source_line"]),
                             "passed": projected == expected})
    for pmid, source in sources.items():
        for kind, filename, expected in (("source", pmid + ".txt", source["raw"]),
                                          ("reader", pmid + ".jsonl", source["reader"])):
            path = publication / kind / filename
            preservation.append({"name": str(path), "passed": path.read_bytes() == expected})
    preservation.append({"name": "input_hashes_unchanged", "passed": all(sha(path) == value for path, value in bindings.items())})
    expected_node_ids = {"UniProtKB:" + item["id"] for reference in references if reference["ledger"]["eligible"]
                         for side in ("a", "b") for item in _values(reference["reader_record"], "primary_ids_" + side)
                         if ((item.get("database") or {}).get("name") or "").lower() == "uniprotkb"}
    actual_node_ids = [node.get("id") for node in graph.get("nodes") or []]
    preservation.append({"name": "standalone_graph_exact_source_participants", "passed":
                         len(actual_node_ids) == len(set(actual_node_ids)) and set(actual_node_ids) == expected_node_ids})
    metrics = summarize(evaluated, references)
    passed = (metrics["strict_fidelity"]["numerator"] == metrics["strict_fidelity"]["denominator"]
              and all(check["passed"] for check in preservation)
              and not evaluated["unexpected_observation_locators"] and not evaluated["duplicate_observation_ids"]
              and all(item["passed"] for item in evaluated["global_checks"]))
    result = {"format": FORMAT, "created_at": utcnow(), "status": "passed" if passed else "failed",
              "assessment_stage": "source_publication_fidelity_only", "commitment": commitment,
              "reference_accounting": {"physical_rows": len(ledger),
                  "evidence_rows": sum(row["kind"] == "evidence" for row in ledger),
                  "eligible_rows": sum(row["eligible"] for row in ledger),
                  "excluded_evidence_rows": sum(row["kind"] == "evidence" and not row["eligible"] for row in ledger)},
              "metrics": metrics, "row_evaluation": evaluated, "source_preservation_checks": preservation,
              "evaluated_outputs": ["Saved source-qualified evidence JSON", "Standalone qualified-observation graph JSON",
                                    "Stored eight-group display fragments", "Actual visible publication HTML",
                                    "Complete original raw, official-reader and eligibility ledgers"],
              "not_run": ["Pharos-attached workbench import", "Guided app question/answer",
                          "Answer ZIP/JSONL handoff", "Gold packet comparison", "Biological accuracy or prediction gain"],
              "full_comparison_status": "not_run", "model_calls": 0, "gpu_runs": 0,
              "reserved_final_rows_opened": False,
              "interpretation": "Bounded development source-publication fidelity only. These results cover the reusable publication and its visible source viewer; they do not establish the prepared Pharos-attached app/answer/export comparison.",
              "limitations": ["The original four-row eligible denominator and fourteen-evidence-row accounting are unchanged.",
                  "Only two development studies contain eligible rows; four original studies remain accounted for.",
                  "Real negative/default-polarity and expanded strata are empty and remain unevaluated.",
                  "Visible-value checks and deterministic qualification checks do not establish unrestricted semantic or biological accuracy.",
                  "The publication JSON is one genuine saved handoff; it is not an independent second export or a fabricated workbench result."]}
    result["content_sha256"] = digest(result)
    (out / "report.json").write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    (out / "assessment_boundary.md").write_text(
        "# Source-publication assessment boundary\n\n"
        "This result evaluates the actual IntAct evidence publication: its saved evidence and graph JSON, "
        "stored display fragments, visible HTML viewer and preserved source records. The independent reference "
        "remains the original consumed development raw files, official-reader outputs and frozen eligibility ledger.\n\n"
        "The denominator remains four eligible source rows; all fourteen evidence rows and eighteen physical rows "
        "remain accounted for. Missing output counts as a miss. Empty real negative/default and expansion strata "
        "are unevaluated. Four reserved publications remain unopened.\n\n"
        "The Pharos-attached workbench, guided app answer, answer ZIP/JSONL and gold packet comparison have not run. "
        "The original full comparison contract remains prepared. No Pharos data, question, packet or model result "
        "was fabricated to stand in for that work. These measurements are source fidelity rather than scientific "
        "accuracy, independent biological validation or graph-prediction improvement.\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspection", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publication", type=Path)
    mode.add_argument("--run", type=Path)
    parser.add_argument("--answer", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.publication and (args.answer or args.packet):
        parser.error("Source-publication mode cannot accept substitute app answer or packet inputs.")
    if args.run and (not args.answer or not args.packet):
        parser.error("Full workbench mode requires both --answer and --packet.")
    try:
        result = (evaluate_publication(args.inspection, args.publication, args.out) if args.publication else
                  evaluate(args.inspection, args.run, args.answer, args.packet, args.out))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps({"status": result["status"], "strict_fidelity": result["metrics"]["strict_fidelity"],
                      "coverage": result["metrics"]["coverage"], "report": str(args.out / "report.json")}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
