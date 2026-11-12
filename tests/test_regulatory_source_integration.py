"""Native STRING coverage and directed source answers retain distinct scopes.

The fixture's invented ledger uses the existing STRING adapter contract:
``observation_id`` and no ``id`` or ``source_kind``. It is not a source dataset
or evidence for the biological validity of any pair.
"""
from copy import deepcopy
import unittest
from unittest.mock import patch

from biograph_steward.inspection import inspect_selection
from biograph_steward.regulatory_case_notes import context_display, organism_display
from biograph_steward.regulatory_questions import _saved_pair_context, answer_regulatory_question
from test_regulatory_questions import ANCHOR, BRAF, KRAS, fixture


STRING_OBSERVATION = "string-source:" + "a" * 24


def graph_with_native_string_coverage():
    graph = fixture()
    graph["evidence_extension"]["sources"]["string"] = {
        "source_release": "12.5", "selection_threshold": 0.4,
        "publication_sha256": "b" * 64,
    }
    # Match the native adapter's field names. This intentionally has neither
    # source_kind nor id, which previously made every saved lookup miss.
    graph["extension_observations"].append({
        "observation_id": STRING_OBSERVATION,
        "products": [ANCHOR, KRAS], "state": "functional_score_below400",
        "mapping_states": ["resolved", "resolved"],
        "string_ids": ["9606.ENSP00000000001", "9606.ENSP00000000002"],
        "functional_score": 0.292, "physical_score": None,
        "network_row_numbers": [1728, 2770],
        "source_row": {"functional_combined_score": 0.292,
            "functional_experimental_score": 0.28,
            "functional_coexpression_score": 0.058,
            "physical_combined_score": None},
        "baseline_pair_present": False, "graph_edge_id": None,
        "integration_state": "functional_score_below400",
    })
    return graph


class RegulatorySourceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.graph = graph_with_native_string_coverage()

    def test_native_ledger_without_source_kind_is_visible_with_subthreshold_score(self):
        before = deepcopy(self.graph)
        with patch("urllib.request.urlopen", side_effect=AssertionError("Saved data only")):
            answer = answer_regulatory_question(self.graph, source_run="saved")
        row = next(r for r in answer["records"] if r["source_record_id"] == "SIGNOR-1")
        context = row["saved_pair_context"]
        saved = context["saved_string_capture"]
        self.assertIsNotNone(saved)
        self.assertEqual(saved["id"], STRING_OBSERVATION)
        self.assertEqual(saved["state"], "functional_score_below400")
        self.assertEqual(saved["source_release"], "12.5")
        self.assertEqual(saved["workspace_selection_threshold"], 0.4)
        self.assertEqual(saved["functional_score"], 0.292)
        self.assertIsNone(saved["physical_score"])
        self.assertEqual(saved["source_row"]["functional_experimental_score"], 0.28)
        self.assertEqual(saved["network_row_numbers"], [1728, 2770])
        self.assertEqual(saved["mapping_states"], ["resolved", "resolved"])
        self.assertIsNone(context["independent_evidence_count"])
        self.assertIn("still reports an association", context["interpretation"])
        self.assertIn("reuse remains unresolved", context["interpretation"])
        self.assertNotIn("truth_label", context)
        self.assertNotIn("biological_negative", context)
        self.assertEqual(self.graph, before)
        self.assertNotIn("id", self.graph["extension_observations"][-1])
        self.assertNotIn("source_kind", self.graph["extension_observations"][-1])

    def test_source_inspection_opens_exact_saved_response_rows_without_an_edge(self):
        before = deepcopy(self.graph)
        result = inspect_selection(self.graph, STRING_OBSERVATION, run_id="saved")
        self.assertIsNone(result["assertion"])
        self.assertEqual(result["review"]["state"], "not_applicable")
        section = next(s for s in result["sections"] if s["title"] == "STRING source coverage")
        self.assertEqual(section["fields"]["state"], "functional_score_below400")
        self.assertIn("not assay outcomes", section["text"])
        self.assertEqual({link["url"] for link in result["links"]}, {
            "/api/extension-source/saved/extension_sources/string/capture/network.tsv#row=1728",
            "/api/extension-source/saved/extension_sources/string/capture/network.tsv#row=2770",
        })
        self.assertEqual(result["actions"], [])
        self.assertEqual((result["model_calls"], result["source_fetches"]), (0, 0))
        self.assertEqual(self.graph, before)

    def test_pair_matching_ignores_order_and_other_sources_or_partial_overlap(self):
        original = _saved_pair_context(self.graph, [ANCHOR, KRAS])
        self.assertEqual(_saved_pair_context(self.graph, [KRAS, ANCHOR]), original)
        self.graph["extension_observations"].extend([
            {"id": "mapit.observation:invented", "source_kind": "mapit", "products": [ANCHOR, KRAS]},
            {"observation_id": "string-source:" + "c" * 24,
             "products": [ANCHOR, BRAF], "state": "no_returned_functional_row"},
        ])
        self.assertEqual(_saved_pair_context(self.graph, [ANCHOR, KRAS]), original)
        self.assertIsNone(_saved_pair_context(self.graph, [KRAS, BRAF])["saved_string_capture"])

    def test_self_regulation_never_inherits_a_nonself_ppi_context(self):
        context = _saved_pair_context(self.graph, [ANCHOR, ANCHOR])
        self.assertEqual(context["scope"], "self_regulation_not_a_nonself_PPI_comparison")
        self.assertIsNone(context["saved_string_capture"])
        self.assertEqual(context["original_pharos_records"], [])
        self.assertIsNone(context["independent_evidence_count"])

    def test_original_pair_coverage_and_added_sources_are_not_conflated(self):
        self.graph["edges"].extend([
            {"id": "invented-native-pair", "subject": ANCHOR, "object": KRAS,
             "record_kind": "protein_interaction", "evidence_sources": ["STRINGDB"],
             "source_scores_raw": {"reported_score": 0.2}},
            {"id": "invented-added-pair", "subject": ANCHOR, "object": KRAS,
             "record_kind": "protein_interaction", "extension_source_kind": "string",
             "source_scores_raw": {"functional_combined_score": 0.9}},
        ])
        context = _saved_pair_context(self.graph, [ANCHOR, KRAS])
        self.assertEqual([x["edge_id"] for x in context["original_pharos_records"]], ["invented-native-pair"])
        self.assertEqual(context["saved_string_capture"]["functional_score"], 0.292)
        context["saved_string_capture"]["source_row"]["functional_experimental_score"] = 99
        self.assertEqual(_saved_pair_context(self.graph, [ANCHOR, KRAS])["saved_string_capture"]["source_row"]["functional_experimental_score"], 0.28)

    def test_duplicate_saved_pair_coverage_is_ambiguous(self):
        second = deepcopy(self.graph["extension_observations"][-1])
        second["observation_id"] = "string-source:" + "d" * 24
        self.graph["extension_observations"].append(second)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            _saved_pair_context(self.graph, [ANCHOR, KRAS])

    def test_missing_capture_stays_unknown_and_does_not_become_negative(self):
        self.graph["extension_observations"].pop()
        context = _saved_pair_context(self.graph, [ANCHOR, KRAS])
        self.assertIsNone(context["saved_string_capture"])
        self.assertIsNone(context["independent_evidence_count"])
        self.assertIn("reuse remains unresolved", context["interpretation"])
        self.assertNotIn("absent", context)

    def test_display_labels_preserve_unknown_identifiers_and_organism_reporting(self):
        values = context_display("BTO:0001109;BTO:9999999;literal context")
        self.assertEqual(values[0]["label"], "HCT-116 cell")
        self.assertEqual(values[0]["mapping"], "exact_ontology_identifier_display")
        for row in values[1:]:
            self.assertEqual(row["label"], row["id"])
            self.assertEqual(row["mapping"], "unresolved_literal")
            self.assertIsNone(row["url"])
        self.assertEqual(context_display(""), [])
        self.assertIn("Mus musculus", organism_display({"source_experimental_organism_raw": "10090"})["label"])
        self.assertIn("In vitro", organism_display({"source_experimental_organism_raw": "-1"})["label"])
        self.assertEqual(organism_display({"source_experimental_organism_raw": ""})["label"], "Unreported")
        unresolved = organism_display({"source_experimental_organism_raw": "not-a-taxon"})
        self.assertEqual(unresolved["label"], "not-a-taxon")
        self.assertIsNone(unresolved["url"])


if __name__ == "__main__":
    unittest.main()
