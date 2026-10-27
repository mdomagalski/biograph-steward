"""Invented records test answer scope, source citations and visible exports."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import assay_questions as questions
from biograph_steward.questions import verify_answer


def fixture():
    proteins = ["UniProtKB:P12345", "UniProtKB:Q12345", "UniProtKB:O12345"]
    graph = {"graph_format": "invented-test-graph", "data_kind": "synthetic_demo",
             "snapshot_sha256": "1" * 64, "snapshot_created_at": "2026-10-26T00:00:00+00:00",
             "scope": {"kind": "protein_cohort", "name": "Invented proteins"},
             "targets": [{"id": uid} for uid in proteins],
             "nodes": [{"id": uid} for uid in proteins], "edges": [], "assertions": [],
             "assay_publication_sha256": "2" * 64, "assay_attachment_sha256": "3" * 64,
             "assay_evidence": {"source_kind": questions.SOURCE_KIND}, "assay_observations": [],
             "review_events": []}
    for index, state in enumerate(["candidate", "accepted", "rejected"]):
        oid, eid, aid = (prefix + str(index) for prefix in ["observation:", "edge:", "assertion:"])
        products = proteins[:2] if index < 2 else proteins[1:]
        graph["assay_observations"].append({
            "id": oid, "source_kind": questions.SOURCE_KIND, "products": products,
            "evaluable": True, "graph_edge_id": eid, "negative": index == 1,
            "raw_cells": ["synthetic-column-" + str(n) for n in range(1, 43)],
            "source": {"publication_id": "pubmed:99999999", "source_line": index + 2},
            "source_locators": [{"locator": "source/99999999.txt:" + str(index + 2)}]})
        graph["edges"].append({"id": eid, "assertion_id": aid, "record_kind": "assay_observation",
                               "subject": products[0], "object": products[1],
                               "qualifiers": {"observation_id": oid}, "publications": ["pubmed:99999999"]})
        graph["assertions"].append({"id": aid, "revision": "revision:" + str(index),
                                   "kind": "assay_observation", "evidence_edge_ids": [eid],
                                   "lifecycle_state": state, "source_names": ["MINT"],
                                   "assay_publication_sha256": graph["assay_publication_sha256"],
                                   "assay_attachment_sha256": graph["assay_attachment_sha256"]})
    return graph


def fragments(row):
    """An invented adapter output isolates this wrapper from biological parsing."""
    columns = [[1, 2, 3, 4, 5, 6, 10, 11, 21, 22, 33, 34], [8, 9, 13, 14, 25, 31, 32, 35],
               [7, 12, 41, 42], [17, 18, 19, 20, 26, 27, 28, 29, 30], [14, 16], [36],
               [37, 38, 39, 40], [15, 23, 24]]
    return {"observation_id": row["id"],
            "text": "Invented context-qualified " + ("negative" if row["negative"] else "positive") + " record.",
            "field_groups": [{"group": group, "text": "Synthetic source context " + group,
                              "fields": [{"label": "Column " + str(column), "value": row["raw_cells"][column - 1],
                                          "columns": [column]} for column in group_columns]}
                             for group, group_columns in zip(questions.FIELD_GROUPS, columns)],
            "qualified_fields": {"negative": row["negative"], "host": "Synthetic host"},
            "citations": [{"label": "Synthetic PubMed reference", "url": "https://pubmed.ncbi.nlm.nih.gov/99999999/",
                           "kind": "publication", "identifier": "pubmed:99999999"}]}


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.observations, self.groups, self.links, self.text, self.scripts = [], [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-observation-id" in attrs:
            self.observations.append(attrs["data-observation-id"])
        if "data-field-group" in attrs:
            self.groups.append(attrs["data-field-group"])
        if tag == "a":
            self.links.append(attrs["href"])
        if tag in {"script", "details"}:
            self.scripts.append(tag)

    def handle_data(self, value):
        self.text.append(value)


class AssayQuestionTests(unittest.TestCase):
    def setUp(self):
        self.graph = fixture()
        self.patch = patch.object(questions, "_answer_observation", side_effect=fragments)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_all_source_rows_keep_negative_and_local_review_states_without_collapsing_pairs(self):
        original = deepcopy(self.graph)
        answer = questions.answer_assay_question(self.graph, source_run="synthetic-run")
        verify_answer(answer)
        self.assertEqual(self.graph, original)
        self.assertEqual(len(answer["results"]), 3)
        self.assertEqual([r["local_review_state"] for r in answer["results"]], ["candidate", "accepted", "rejected"])
        self.assertEqual([r["qualified_fields"]["negative"] for r in answer["results"]], [False, True, False])
        self.assertTrue(all(r["source_observation"] == o for r, o in zip(answer["results"], self.graph["assay_observations"])))
        self.assertFalse(answer["llm_used"])
        self.assertEqual(answer["plan"]["relations"], [])

    def test_exact_cohort_filter_and_no_symbol_resolution(self):
        answer = questions.answer_assay_question(self.graph, "P12345")
        self.assertEqual(len(answer["results"]), 2)
        self.assertEqual(answer["availability"]["outside_protein_filter"], 1)
        for selector in ["TP53", "P99999", "", [], 5]:
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                questions.answer_assay_question(self.graph, selector)

    def test_references_trace_each_result_to_its_own_assertion_and_source(self):
        answer = questions.answer_assay_question(self.graph)
        for result, citation in zip(answer["results"], answer["citations"]):
            self.assertEqual(result["citation_id"], citation["id"])
            self.assertEqual(result["observation_id"], citation["observation_id"])
            self.assertEqual(result["assertion_id"], citation["assertion_id"])
            self.assertEqual(result["graph_edge_id"], citation["evidence_records"][0]["id"])
            self.assertEqual(citation["source_links"], result["citations"])
            self.assertEqual(citation["source_locators"], result["source_observation"]["source_locators"])

    def test_source_binding_or_evidence_identity_mismatch_fails_closed(self):
        for mutate in [lambda g: g["edges"][0]["qualifiers"].update(observation_id="other"),
                       lambda g: g["assertions"][0].update(assay_attachment_sha256="other"),
                       lambda g: g["assertions"][0].update(evidence_edge_ids=[]),
                       lambda g: g["assay_observations"][0].update(evaluable="true"),
                       lambda g: g["edges"].pop(0),
                       lambda g: g["assay_observations"].append(deepcopy(g["assay_observations"][0]))]:
            graph = deepcopy(self.graph)
            mutate(graph)
            with self.assertRaises(ValueError):
                questions.answer_assay_question(graph)

    def test_lambourne_and_unmarked_empty_attachments_are_not_reinterpreted(self):
        self.graph["assay_observations"][0]["source_kind"] = "lambourne"
        with self.assertRaisesRegex(ValueError, "IntAct"):
            questions.answer_assay_question(self.graph)
        self.graph["assay_observations"] = []
        answer = questions.answer_assay_question(self.graph)
        self.assertEqual(answer["results"], [])
        self.graph["assay_evidence"] = {}
        with self.assertRaisesRegex(ValueError, "IntAct"):
            questions.answer_assay_question(self.graph)

    def test_exclusions_are_counted_and_exported_without_becoming_negative_evidence(self):
        excluded = deepcopy(self.graph["assay_observations"][0])
        excluded.update(id="excluded:1", evaluable=False, graph_edge_id=None)
        self.graph["assay_observations"].append(excluded)
        answer = questions.answer_assay_question(self.graph)
        self.assertEqual(len(answer["results"]), 3)
        self.assertEqual(answer["excluded_observations"], [excluded])
        self.assertEqual(answer["availability"]["excluded_selected_observations"], 1)

    def test_all_field_groups_are_visible_and_source_text_is_escaped(self):
        self.graph["assay_observations"][0]["raw_cells"][0] = '<script>alert("source")</script>'
        answer = questions.answer_assay_question(self.graph)
        html = questions.answer_html(answer)
        parsed = Markup()
        parsed.feed(html)
        self.assertEqual(parsed.observations, [r["observation_id"] for r in answer["results"]])
        self.assertEqual(parsed.groups, list(questions.FIELD_GROUPS) * 3)
        self.assertEqual(parsed.scripts, [])
        visible = " ".join(parsed.text)
        self.assertIn('<script>alert("source")</script>', visible)
        for result in answer["results"]:
            for group in result["field_groups"]:
                self.assertIn(group["text"], visible)
                for field in group["fields"]:
                    self.assertIn(field["value"], visible)
        self.assertEqual(len(parsed.links), 3)

    def test_missing_field_group_or_unsafe_citation_fails_before_answer_creation(self):
        for mutate in [lambda f: f["field_groups"].pop(),
                       lambda f: f["citations"][0].update(url="javascript:alert(1)"),
                       lambda f: f["field_groups"][0]["fields"].pop(0)]:
            def damaged(row):
                value = fragments(row)
                mutate(value)
                return value
            with patch.object(questions, "_answer_observation", side_effect=damaged), self.assertRaises(ValueError):
                questions.answer_assay_question(self.graph)

    def test_text_and_jsonl_preserve_full_records_and_reject_changed_answer(self):
        answer = questions.answer_assay_question(self.graph, source_run="synthetic-run")
        text = questions.answer_text(answer)
        self.assertIn("Local review: candidate", text)
        self.assertIn("Reported outcome and negative-evidence flag", text)
        with tempfile.TemporaryDirectory() as folder:
            questions.save_extra_files(answer, folder)
            saved = [json.loads(line) for line in (Path(folder) / "assay_evidence.jsonl").read_text().splitlines()]
            self.assertEqual(saved[0]["source_observation"], self.graph["assay_observations"][0])
            self.assertEqual(saved[0]["answer_bindings"]["answer_sha256"], answer["answer_sha256"])
            self.assertEqual((Path(folder) / "assay_excluded_observations.jsonl").read_text(), "")
        answer["results"][0]["local_review_state"] = "accepted"
        with self.assertRaisesRegex(ValueError, "integrity"):
            questions.answer_html(answer)


if __name__ == "__main__":
    unittest.main()
