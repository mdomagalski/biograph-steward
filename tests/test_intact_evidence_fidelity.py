"""Mutation checks for the independent evaluator using wholly invented records."""
from copy import deepcopy
from html import escape
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.evaluate_intact_evidence_fidelity import (
    DEVELOPMENT, PARSED_GROUPS, SIDE_COLUMNS, VisibleGroups, evaluate_rows,
    field_groups, load_reference, summarize,
)


def fixture():
    """Hand-authored source oracle and outputs; no importer/answer code is called."""
    columns = field_groups()
    raw = ["-"] * 42
    for column, value in {
        1: "uniprotkb:P12345-2", 2: "uniprotkb:Q12345", 7: 'psi-mi:"MI:0006"(anti bait coimmunoprecipitation)',
        9: "pubmed:99999999", 10: "taxid:9606(human)", 11: "taxid:9606(human)",
        12: 'psi-mi:"MI:0914"(association)', 13: 'psi-mi:"MI:0469"(intact)', 14: "intact:SYNTHETIC",
        15: "synthetic-score:0.5", 17: 'psi-mi:"MI:0499"(unspecified role)', 18: 'psi-mi:"MI:0499"(unspecified role)',
        19: 'psi-mi:"MI:0496"(bait)', 20: 'psi-mi:"MI:0498"(prey)', 21: 'psi-mi:"MI:0326"(protein)',
        22: 'psi-mi:"MI:0326"(protein)', 29: "taxid:4932(synthetic yeast host)", 36: "false", 39: "0", 40: "1",
    }.items():
        raw[column - 1] = value
    term = lambda identifier, label: {"mi_id": identifier, "name": label}
    xref = lambda database, identifier: {"database": {"name": database}, "id": identifier}
    full_values = {name: [] for names in PARSED_GROUPS.values() for name in names}
    full_values.update({"primary_ids_a": [xref("uniprotkb", "P12345-2")], "primary_ids_b": [xref("uniprotkb", "Q12345")],
        "taxa_a": [{"taxid": 9606, "common_name": "human"}], "taxa_b": [{"taxid": 9606, "common_name": "human"}],
        "interactor_types_a": [term("MI:0326", "protein")], "interactor_types_b": [term("MI:0326", "protein")],
        "publication_ids": [xref("pubmed", "99999999")], "source_databases": [term("MI:0469", "intact")],
        "evidence_ids": [xref("intact", "SYNTHETIC")], "detection_methods": [term("MI:0006", "anti bait coimmunoprecipitation")],
        "interaction_types": [term("MI:0914", "association")], "biological_roles_a": [term("MI:0499", "unspecified role")],
        "biological_roles_b": [term("MI:0499", "unspecified role")], "experimental_roles_a": [term("MI:0496", "bait")],
        "experimental_roles_b": [term("MI:0498", "prey")], "host_taxa": [{"taxid": 4932, "common_name": "synthetic yeast host"}]})
    source_fields = {name: {"values": value} for name, value in full_values.items()}
    model_participants = [{"side": "A", "features": [], "stoichiometry": {"min": 0, "max": 0}},
                          {"side": "B", "features": [], "stoichiometry": {"min": 1, "max": 1}}]
    negative = {"literal": "false", "value": False, "origin": "explicit"}
    expansion = {"literal": "-", "annotation_origin": "not_supplied", "methods": []}
    semantics = {
        "participant_identity": {"identity_basis": "exact source primary identifiers", "A_B_orientation_preserved": True},
        "source_and_publication": {"independent_evidence_count": None},
        "detection_and_type": {"direct_binding_inferred": False},
        "roles_and_experimental_context": {"host_labels_are_literal": True, "cell_line_identifier_inferred": False},
        "complex_expansion": {**expansion, "binary_origin": "unknown_no_inference"},
        "negative": negative, "features_and_stoichiometry": {"sequence_or_construct_identity_inferred": False},
        "other_missing_values_and_confidence": {"confidence_is_calibrated_truth_probability": False},
    }
    texts = {group: "Source fields remain explicitly labeled." for group in columns}
    texts.update({"negative": "Explicit false flag describes positive evidence in this experiment.",
        "complex_expansion": "No expansion annotation was supplied; binary origin is unknown.",
        "detection_and_type": "These source methods do not establish direct binding.",
        "other_missing_values_and_confidence": "The source score is not a calibrated truth probability."})
    references, observations, results, edges = [], [], [], []
    for index in range(4):
        publication = "pubmed:" + DEVELOPMENT[index // 2]
        source = {"publication_id": publication, "artifact_sha256": "a" * 64,
                  "release": "2026-10-17", "source_line": index + 2,
                  "raw_row_sha256": hashlib.sha256("\t".join(raw).encode()).hexdigest()}
        reader = {"raw_cells": deepcopy(raw), "raw_line": "\t".join(raw), "source_fields": deepcopy(source_fields),
                  "interaction": {"participants": deepcopy(model_participants)}}
        references.append({"ledger": {**source, "eligible": True, "kind": "evidence"}, "reader_record": deepcopy(reader)})
        source["url"] = "https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psimitab/pmid/2025/" + publication.removeprefix("pubmed:") + ".txt"
        groups = {}
        for group, group_columns in columns.items():
            groups[group] = {"raw_fields": [{"column": column, "value": raw[column - 1],
                "label": "Source field " + str(column) + (" " + SIDE_COLUMNS[column] if column in SIDE_COLUMNS else "")}
                for column in group_columns],
                "parsed_fields": {name: deepcopy(full_values[name]) for name in PARSED_GROUPS[group]},
                "semantics": deepcopy(semantics[group])}
        groups["features_and_stoichiometry"]["reader_fields"] = deepcopy(model_participants)
        participants = []
        for offset, side in enumerate(("a", "b")):
            participants.append({"side": side.upper(), "product_id": "UniProtKB:" + ("P12345-2" if offset == 0 else "Q12345"),
                **{destination: deepcopy(full_values[name + side]) for destination, name in
                   (("primary_ids", "primary_ids_"), ("alternative_ids", "alternative_ids_"), ("taxa", "taxa_"),
                    ("interactor_types", "interactor_types_"), ("biological_roles", "biological_roles_"),
                    ("experimental_roles", "experimental_roles_"), ("identification_methods", "identification_methods_"))},
                "aliases_raw": raw[4 + offset], "features_raw": raw[36 + offset], "stoichiometry_raw": raw[38 + offset],
                "reader_fields": deepcopy(model_participants[offset]), "identity_inferred": False})
        observation = {"id": "synthetic-observation-" + str(index), "source": source,
            "raw_cells": deepcopy(raw), "source_fields": deepcopy(source_fields), "reader_record": reader,
            "participants": participants, "qualified_fields": groups,
            "qualifications": {"negative": deepcopy(negative), "expansion": deepcopy(expansion),
                "binary_origin": "unknown_no_inference", "direct_binding_inferred": False, "independent_evidence_count": None},
            "graph_edge_id": "synthetic-edge-" + str(index), "evaluable": True, "biologically_validated": False,
            "independent_evidence_count": None, "source_kind": "intact_mitab27", "assay_status": "curated_positive",
            "assay_hosts": deepcopy(full_values["host_taxa"]), "products": ["UniProtKB:P12345-2", "UniProtKB:Q12345"]}
        observation["citations"] = [
            {"kind": "source_artifact", "identifier": source["artifact_sha256"], "url": source["url"]},
            {"kind": "publication", "identifier": "pubmed:99999999", "url": "https://pubmed.ncbi.nlm.nih.gov/99999999/"},
            {"kind": "evidence", "identifier": "intact:SYNTHETIC", "url": "https://www.ebi.ac.uk/intact/search?query=SYNTHETIC"},
        ]
        result = {"observation_id": observation["id"], "source_observation": deepcopy(observation),
                  "qualified_fields": deepcopy(groups), "citations": deepcopy(observation["citations"]),
                  "field_groups": [{"group": name, "text": texts[name], "fields": [
                    {"columns": [field["column"]], "label": field["label"], "value": field["value"]}
                    for field in group["raw_fields"]]} for name, group in groups.items()]}
        observations.append(observation); results.append(result)
        edges.append({"id": observation["graph_edge_id"], "record_kind": "assay_observation",
                      "qualifiers": {"observation_id": observation["id"]}, "subject": "UniProtKB:P12345-2",
                      "object": "UniProtKB:Q12345", "predicate": "biograph:has_assay_observation_with"})
    return references, observations, results, edges


def render(results, hidden=False, publication=False):
    return "".join('<section data-observation-id="' + escape(result["observation_id"]) + '">'
        + "".join('<a href="' + escape(link["url"]) + '">Source</a>' for link in result["citations"])
        + ('<a href="source/' + result["source_observation"]["source"]["publication_id"].removeprefix("pubmed:") + '.txt">Local source</a>' if publication else '')
        + "".join('<section data-field-group="' + escape(group["group"]) + '"' + (' hidden' if hidden else '') + '>'
            + escape(group["text"]) + '<table>' + "".join('<tr><th>' + escape(field["label"]) + '</th><td>'
                + escape(field["value"]) + '</td><td>' + ", ".join(map(str, field["columns"])) + '</td></tr>' for field in group["fields"]) + '</table>'
            + '</section>' for group in result["field_groups"]) + '</section>' for result in results)


def evaluate(references, observations, results, edges, html=None):
    return evaluate_rows(references, observations, results, deepcopy(observations), deepcopy(results),
                         render(results) if html is None else html, graph_edges=edges)


class IndependentFidelityTests(unittest.TestCase):
    def test_complete_source_qualified_outputs_pass_all_groups(self):
        references, observations, results, edges = fixture()
        evaluated = evaluate(references, observations, results, edges)
        self.assertTrue(all(row["strict_fidelity"] for row in evaluated["rows"]))
        summary = summarize(evaluated, references)
        self.assertEqual(summary["strict_fidelity"]["numerator"], 4)
        self.assertEqual(summary["strict_fidelity"]["denominator"], 4)
        self.assertEqual(summary["strata"]["negative_literal"]["true"]["status"], "unevaluated_empty_stratum")

    def test_missing_answer_and_merged_source_record_keep_four_row_denominator(self):
        references, observations, results, edges = fixture()
        evaluated = evaluate(references, observations[:-1], results[:-1], edges[:-1])
        metrics = summarize(evaluated, references)
        self.assertEqual(metrics["coverage"]["denominator"], 4)
        self.assertEqual(metrics["coverage"]["numerator"], 3)
        self.assertEqual(metrics["strict_fidelity"]["numerator"], 3)

    def test_consistently_wrong_import_answer_and_export_do_not_define_the_oracle(self):
        references, observations, results, edges = fixture()
        for index, observation in enumerate(observations):
            observation["participants"][0]["experimental_roles"] = [{"mi_id": "MI:0498", "name": "prey"}]
            observation["qualifications"]["binary_origin"] = "true_binary"
            results[index]["source_observation"] = deepcopy(observation)
        evaluated = evaluate(references, observations, results, edges)
        self.assertFalse(any(row["strict_fidelity"] for row in evaluated["rows"]))
        failures = {check["name"] for row in evaluated["rows"] for check in row["checks"] if not check["passed"]}
        self.assertIn("participant_a.experimental_roles", failures)
        self.assertIn("qualification_semantics", failures)

    def test_raw_json_preservation_without_visible_answer_is_not_strict_fidelity(self):
        references, observations, results, edges = fixture()
        evaluated = evaluate(references, observations, results, edges, render(results, hidden=True))
        self.assertFalse(any(row["strict_fidelity"] for row in evaluated["rows"]))
        self.assertEqual(summarize(evaluated, references)["coverage"]["numerator"], 0)
        self.assertTrue(all(row["serialized_records_present"] for row in evaluated["rows"]))
        self.assertTrue(all(row["groups"]["participant_identity"]["raw_preserved"] for row in evaluated["rows"]))
        self.assertFalse(any(row["groups"]["participant_identity"]["readable_covered"] for row in evaluated["rows"]))

    def test_wrong_side_labels_and_lost_host_label_are_detected(self):
        references, observations, results, edges = fixture()
        for result in results:
            group = next(group for group in result["field_groups"] if group["group"] == "roles_and_experimental_context")
            for field in group["fields"]:
                if field["columns"] == [19]: field["label"] = "Experimental role B"
                if field["columns"] == [29]: field["value"] = "taxid:4932"
        evaluated = evaluate(references, observations, results, edges)
        self.assertFalse(any(row["strict_fidelity"] for row in evaluated["rows"]))

    def test_source_database_name_without_the_publication_link_fails(self):
        references, observations, results, edges = fixture()
        for result in results:
            result["citations"] = [link for link in result["citations"] if link["kind"] != "publication"]
        evaluated = evaluate(references, observations, results, edges)
        self.assertFalse(any(row["strict_fidelity"] for row in evaluated["rows"]))
        failures = {check["name"] for row in evaluated["rows"] for check in row["checks"] if not check["passed"]}
        self.assertIn("visible_source_links", failures)

    def test_reserved_inspection_is_rejected_before_any_source_body_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "report.json").write_text(json.dumps({"reserved_final_rows_opened": False,
                "studies": [{"publication_id": "pubmed:39833857"}]}))
            with patch.object(Path, "read_bytes", side_effect=AssertionError("No source body may be opened")):
                with self.assertRaises(ValueError): load_reference(root)

    def test_hidden_script_json_does_not_create_visible_source_groups(self):
        visible = VisibleGroups()
        visible.feed('<section data-observation-id="x"><script><section data-field-group="negative">positive explicit</section></script>'
                     '<section data-field-group="negative" style="display:none">positive explicit</section></section>')
        self.assertEqual(visible.text("x", "negative"), "")

    def test_publication_stage_uses_stored_display_and_viewer_without_app_substitutes(self):
        references, observations, results, edges = fixture()
        displays = [{name: value for name, value in result.items() if name != "source_observation"} for result in results]
        evaluated = evaluate_rows(references, observations, displays, [], [], render(results, publication=True),
                                  graph_edges=edges, assessment_stage="source_publication_fidelity_only")
        self.assertTrue(all(row["strict_fidelity"] for row in evaluated["rows"]))
        check_names = {check["name"] for row in evaluated["rows"] for check in row["checks"]}
        self.assertNotIn("one_packet_observation", check_names)
        self.assertNotIn("one_answer_export_result", check_names)
        self.assertIn("one_stored_display_fragment", check_names)

    def test_publication_html_only_role_swap_is_detected(self):
        references, observations, results, edges = fixture()
        text = render(results, publication=True).replace('<th>Source field 19 A</th>', '<th>Source field 19 B</th>')
        evaluated = evaluate_rows(references, observations, results, [], [], text,
                                  graph_edges=edges, assessment_stage="source_publication_fidelity_only")
        self.assertFalse(any(row["strict_fidelity"] for row in evaluated["rows"]))
        failed = {check["name"] for row in evaluated["rows"] for check in row["checks"] if not check["passed"]}
        self.assertIn("roles_and_experimental_context.visible_column_label_value_binding", failed)

    def test_publication_extra_unqualified_or_duplicate_edge_fails_bijection(self):
        references, observations, results, edges = fixture()
        extra = {"id": "unsupported-extra", "record_kind": "ppi", "subject": "UniProtKB:P12345-2", "object": "UniProtKB:Q12345"}
        evaluated = evaluate_rows(references, observations, results, [], [], render(results, publication=True),
                                  graph_edges=edges + [extra], assessment_stage="source_publication_fidelity_only")
        self.assertFalse(all(check["passed"] for check in evaluated["global_checks"]))
        evaluated = evaluate_rows(references, observations, results, [], [], render(results, publication=True),
                                  graph_edges=edges + [edges[0]], assessment_stage="source_publication_fidelity_only")
        self.assertFalse(all(check["passed"] for check in evaluated["global_checks"]))


if __name__ == "__main__":
    unittest.main()
