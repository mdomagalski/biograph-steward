"""Invented tissue observations exercise deterministic scope and source guidance."""
from copy import deepcopy
import unittest

from biograph_steward.biological_questions import answer_biological_question, ANCHOR
from biograph_steward.client import digest
from biograph_steward.inspection import inspect_selection, _source_path


def fixture(count=30):
    graph = {"graph_format": "invented-biological-fixture", "snapshot_sha256": "1" * 64,
        "evidence_extension_sha256": "2" * 64, "evidence_extension": {"sources": {"mapit": {"qualified_partner_observations": count}}},
        "nodes": [{"id": ANCHOR, "sym": "EGFR"}], "edges": [], "assertions": [],
        "extension_observations": [], "review_events": []}
    for n in range(count):
        partner = "UniProtKB:P" + str(n).zfill(5)
        oid, eid, aid = "invented-observation:" + str(n), "invented-edge:" + str(n), "invented-assertion:" + str(n)
        graph["nodes"].append({"id": partner, "sym": "Partner " + str(n).zfill(2)})
        o = {"id": oid, "source_kind": "mapit", "products": [ANCHOR, partner], "partner": partner,
            "graph_edge_id": eid, "assay": "Invented proximity-labelled tissue study",
            "assay_status": "primary_enriched_proximity", "tissue_label": "Invented pooled colorectal tissue",
            "statistics": {"Beta_Ab": -1.2, "P_Ab": 0.0001, "Q_Ab": 0.002},
            "statistical_family": {"modeled_groups": 5000, "adjustment": "full-family BH"},
            "sampling": {"patients": 7}, "archive_lookup": {"status": "represented_in_archive"},
            "source_identity": {"source_matrix_row": n + 2, "whole_group": partner},
            "source_locators": [{"locator": "extension_sources/mapit/source/model.tsv#row=" + str(n + 2),
                                 "role": "full_family_model_statistic"}],
            "study": "doi:10.1234/invented", "citations": [{"id": "doi:10.1234/invented",
                "url": "https://doi.org/10.1234/invented", "role": "primary_study"}]}
        graph["extension_observations"].append(o)
        graph["edges"].append({"id": eid, "subject": ANCHOR, "object": partner,
            "record_kind": "tissue_proximity_observation", "predicate": "biograph:has_assay_observation_with",
            "extension_source_kind": "mapit", "assertion_id": aid, "evidence_record": deepcopy(o),
            "primary_source_raw": "Invented source data", "aggregator": "Source preserving projection",
            "status": "passed_structural_checks", "snapshot_sha256": graph["snapshot_sha256"],
            "publications": ["doi:10.1234/invented"], "record_locators": [o["source_locators"][0]["locator"]],
            "qualifiers": {"observation_id": oid, "assay": o["assay"], "tissue_label": o["tissue_label"]}})
        graph["assertions"].append({"id": aid, "subject": ANCHOR, "object": partner,
            "predicate": "biograph:has_assay_observation_with", "kind": "tissue_proximity_observation",
            "revision": "fixture-revision", "lifecycle_state": "accepted" if n == 0 else "candidate",
            "evidence_edge_ids": [eid], "qualifiers": graph["edges"][-1]["qualifiers"]})
    return graph


class BiologicalQuestionTests(unittest.TestCase):
    def test_pages_are_complete_source_bound_copies_without_mutation(self):
        graph = fixture(); before = deepcopy(graph)
        first = answer_biological_question(graph, source_run="fixture")
        second = answer_biological_question(graph, offset=25, source_run="fixture")
        self.assertEqual(len(first["records"]), 25)
        self.assertEqual(len(second["records"]), 5)
        self.assertEqual(first["summary"]["source_observations"], 30)
        self.assertEqual(first["summary"]["next_offset"], 25)
        self.assertIsNone(second["summary"]["next_offset"])
        self.assertEqual((first["model_calls"], first["source_fetches"]), (0, 0))
        self.assertEqual(first["records"][0]["local_review_state"], "accepted")
        self.assertIn("not establish direct binding", first["interpretation"])
        self.assertEqual(first["content_sha256"], digest({k: v for k, v in first.items() if k != "content_sha256"}))
        first["records"][0]["statistics"]["Q_Ab"] = 1
        self.assertEqual(graph, before)

    def test_search_no_results_and_bounds_are_explicit(self):
        graph = fixture()
        result = answer_biological_question(graph, search="Partner 29")
        self.assertEqual(result["summary"]["matching_observations"], 1)
        self.assertEqual(result["records"][0]["partner_label"], "Partner 29")
        self.assertEqual(answer_biological_question(graph, search="not observed")["records"], [])
        for kw in ({"protein": "KRAS"}, {"offset": -1}, {"limit": 26}, {"limit": True}, {"search": "x" * 201}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                answer_biological_question(graph, **kw)

    def test_qualified_observation_requires_its_exact_source_edge(self):
        graph = fixture(1); graph["edges"][0]["object"] = ANCHOR
        with self.assertRaisesRegex(ValueError, "qualified evidence edge"):
            answer_biological_question(graph)

    def test_inspection_opens_extension_observation_with_statistics_and_doi(self):
        graph = fixture(1)
        result = inspect_selection(graph, "invented-observation:0", run_id="fixture")
        self.assertEqual(result["selection"]["kind"], "observation")
        self.assertIn("MAP-IT tissue proximity", [r["title"] for r in result["sections"]])
        self.assertIn("Archived Pharos context", [r["title"] for r in result["sections"]])
        self.assertTrue(any(l["url"] == "https://doi.org/10.1234/invented" for l in result["links"]))
        self.assertTrue(any(l["url"].startswith('/api/extension-source/fixture/extension_sources/mapit/') for l in result["links"]))
        self.assertFalse(any(g["field"] == "primary_reference" for g in result["missing_context"]))
        self.assertEqual(result["source_records"][0]["reference_status"], "references_supplied")

    def test_extension_locator_cannot_traverse_or_switch_source_type(self):
        valid = _source_path("fixture", "extension_sources/mapit/source/model.tsv#row=7")
        self.assertEqual(valid, "/api/extension-source/fixture/extension_sources/mapit/source/model.tsv#row=7")
        for value in ("extension_sources/mapit/../secret", "extension_sources/mapit//model.tsv",
                      "extension_sources/unknown/model.tsv", "extension_sources/mapit/secret%2fkey"):
            self.assertIsNone(_source_path("fixture", value))

    def test_string_source_coverage_is_not_displayed_as_an_assay(self):
        graph = fixture(1)
        edge = graph['edges'][0]
        edge.update(record_kind='protein_interaction', extension_source_kind='string', publications=[],
            predicate='biograph:has_interaction_annotation', qualifiers={'evidence_type':'STRING12.5functional_association'},
            evidence_record={'source_release':'12.5','source_row':{'functional_experimental_score':0.4}},
            source_scores_raw={'functional_combined_score':0.7,'physical_combined_score':0})
        graph['assertions'][0].update(kind='protein_interaction', predicate=edge['predicate'], qualifiers=edge['qualifiers'])
        graph['extension_observations']=[{'observation_id':'string-source:fixture', 'graph_edge_id':edge['id'],
            'products':[edge['subject'],edge['object']], 'state':'qualifying_functional_association',
            'mapping_states':['resolved','resolved'], 'string_ids':['9606.A','9606.B'], 'network_row_numbers':[2,3]}]
        result=inspect_selection(graph,'string-source:fixture',run_id='fixture')
        self.assertIn('Versioned STRING annotation',[r['title'] for r in result['sections']])
        self.assertIn('STRING source coverage',[r['title'] for r in result['sections']])
        self.assertNotIn('Source outcome',[r['title'] for r in result['sections']])

    def test_unsafe_external_citation_is_omitted_without_inventing_reference(self):
        graph = fixture(1)
        graph["extension_observations"][0]["citations"] = [{"url": "javascript:alert(1)"}]
        answer = answer_biological_question(graph)
        self.assertEqual(answer["records"][0]["citations"], [])


if __name__ == '__main__':
    unittest.main()
