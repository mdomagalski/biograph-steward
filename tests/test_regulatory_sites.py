"""Source-reported site displays, with invented records and real source checks."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from biograph_steward.assertions import build_assertions
from biograph_steward.client import digest
from biograph_steward.regulatory_questions import answer_regulatory_question
from biograph_steward.regulatory_sites import answer_regulatory_sites
from biograph_steward.signor_source import _experimental_organism
from test_regulatory_questions import (
    ANCHOR, BRAF, fixture, observation, edge_for, assertion_for)


def source_change(graph, record="SIGNOR-1", **changes):
    """Rebind every copy of invented source fields; never touch real sources."""
    row = observation(graph, record)
    row["source_row"].update(changes)
    fields = {"RESIDUE": "residue_raw", "SEQUENCE": "sequence_raw",
        "EFFECT": "effect_literal", "MECHANISM": "mechanism_literal",
        "CELL_DATA": "cell_context_raw", "TISSUE_DATA": "tissue_context_raw",
        "SENTENCE": "supporting_sentence_raw", "DIRECT": "direct_literal"}
    for raw, wrapper in fields.items():
        if raw in changes:
            row[wrapper] = changes[raw]
    row["source_reported_direct"] = row["direct_literal"] == "t"
    row.update(_experimental_organism(row["source_row"]["TAX_ID"]))
    for kind in ("cell", "tissue"):
        row[kind + "_context_reporting"] = "reported" if row[kind + "_context_raw"] else "unreported"
    edge = edge_for(graph, record)
    for key, wrapper in {"regulatory_effect": "effect_literal", "regulatory_mechanism": "mechanism_literal",
                         "cell_line": "cell_context_raw", "tissue": "tissue_context_raw",
                         "residue": "residue_raw", "sequence": "sequence_raw"}.items():
        edge["qualifiers"][key] = row[wrapper] or None
    edge["qualifiers"]["source_directness"] = row["direct_literal"]
    edge["evidence_record"] = deepcopy(row)
    edge["observation"] = deepcopy(row)
    graph["assertions"] = build_assertions(graph)


def record(answer, identity="SIGNOR-1"):
    return next(r for r in answer["records"] if r["source_record_id"] == identity)


class RegulatorySiteTests(unittest.TestCase):
    def setUp(self):
        self.graph = fixture()

    def test_phosphate_change_and_net_protein_effect_remain_distinct(self):
        inhibitory = record(answer_regulatory_sites(self.graph), "SIGNOR-2")["site_view"]
        self.assertEqual(inhibitory["modification_action"], "phosphate_addition")
        self.assertEqual(inhibitory["phosphate_change_sign"], 1)
        self.assertEqual(inhibitory["source_protein_effect_literal"], "down-regulates activity")
        self.assertFalse(inhibitory["source_reported_direct"])
        self.assertFalse(inhibitory["purified_catalysis_verified"])
        self.assertEqual(inhibitory["site_effect_on_protein"]["status"], "not_inferred")
        self.assertIsNone(inhibitory["site_effect_on_protein"]["sign"])
        edges = inhibitory["projection_edges"]
        self.assertEqual([e["kind"] for e in edges],
                         ["source_reported_phosphate_change", "source_net_protein_effect"])
        self.assertEqual(edges[1]["subject"], BRAF)  # Not an invented site→protein causal effect.
        self.assertEqual(edges[1]["object"], ANCHOR)
        source_change(self.graph, MECHANISM="dephosphorylation", EFFECT="up-regulates activity")
        removal = record(answer_regulatory_sites(self.graph))["site_view"]
        self.assertEqual((removal["modification_action"], removal["phosphate_change_sign"]),
                         ("phosphate_removal", -1))
        self.assertEqual(removal["source_protein_effect_literal"], "up-regulates activity")
        self.assertIsNone(removal["site_effect_on_protein"]["sign"])

    def test_reported_site_does_not_establish_canonical_or_assayed_proteoform(self):
        source_change(self.graph, RESIDUE="His19", SEQUENCE="unverified source sequence", TAX_ID="-1")
        row = record(answer_regulatory_sites(self.graph, site="H19"))
        view = row["site_view"]
        self.assertEqual(view["status"], "split_source_view")
        self.assertEqual(view["reported_site"]["label"], "H19")
        self.assertEqual(view["reported_site"]["residue_raw"], "His19")
        self.assertFalse(view["reported_site"]["canonical_coordinate_verified"])
        self.assertFalse(view["reported_site"]["experimental_proteoform_verified"])
        self.assertEqual(row["source_experimental_organism_raw"], "-1")
        self.assertEqual(row["sequence_raw"], "unverified source sequence")
        self.assertFalse(view["purified_catalysis_verified"])
        self.assertEqual(answer_regulatory_sites(self.graph, site="His19")["records"],
                         answer_regulatory_sites(self.graph, site=" H19 ")["records"])

    def test_multisite_unlocalized_and_other_mechanisms_are_not_guessed(self):
        for residue in ("", "Ser15;Ser20", "Ser15/20", "Ser?", "Ser0", " Ser15", "site 15"):
            graph = deepcopy(self.graph); source_change(graph, RESIDUE=residue)
            row = record(answer_regulatory_sites(graph))
            self.assertEqual(row["residue_raw"], residue)
            self.assertEqual(row["site_view"]["status"], "unresolved")
            self.assertIsNone(row["site_view"]["reported_site"])
            self.assertEqual(row["site_view"]["projection_edges"], [])
            self.assertFalse(answer_regulatory_sites(graph, site="S15")["records"])
        source_change(self.graph, RESIDUE="Lys382", MECHANISM="acetylation")
        other = record(answer_regulatory_sites(self.graph, site="K382"))["site_view"]
        self.assertEqual(other["reported_site"]["label"], "K382")
        self.assertEqual(other["status"], "unresolved")
        self.assertEqual(other["projection_edges"], [])
        self.assertIsNone(other["phosphate_change_sign"])

    def test_exact_context_filters_and_friendly_choices_do_not_infer_context(self):
        source_change(self.graph, "SIGNOR-2", TISSUE_DATA="BTO:0000149;BTO:0000671")
        result = answer_regulatory_sites(self.graph, cell_context="BTO:0000007", tissue_context="BTO:0000671")
        self.assertEqual([r["source_record_id"] for r in result["records"]], ["SIGNOR-2"])
        source = answer_regulatory_question(self.graph, direction="both")
        expected = record(source, "SIGNOR-2")["cell_context_display"][0]
        choices = result["summary"]["available_filters"]
        choice = next(c for c in choices["cell_contexts"] if c["value"] == "BTO:0000007")
        self.assertEqual((choice["label"], choice["mapping"]), (expected["label"], expected["mapping"]))
        for value in ("BTO:000000", "colorectal", expected["label"]):
            self.assertEqual(answer_regulatory_sites(self.graph, cell_context=value)["records"], [])
        self.assertEqual(answer_regulatory_sites(self.graph, tissue_context="BTO:0000149")["summary"]["matching_observations"], 1)
        self.assertEqual(result["summary"]["direction_observations"], 4)
        self.assertEqual(len(choices["sites"]), 4)  # Choices precede filters/page selection.

    def test_context_availability_is_reported_either_and_unreported_both_blank(self):
        reported = answer_regulatory_sites(self.graph, context_reporting="reported")
        missing = answer_regulatory_sites(self.graph, context_reporting="unreported")
        self.assertEqual({r["source_record_id"] for r in reported["records"]}, {"SIGNOR-2", "SIGNOR-3"})
        self.assertEqual({r["source_record_id"] for r in missing["records"]}, {"SIGNOR-1", "SIGNOR-5"})
        self.assertEqual(reported["summary"]["context_reported_observations"], 2)
        self.assertEqual(reported["summary"]["context_unreported_observations"], 2)
        self.assertEqual(answer_regulatory_sites(self.graph, context_reporting="unreported", cell_context="BTO:0000007")["records"], [])

    def test_pages_cover_complete_verified_scope_without_changing_choices_or_self_counts(self):
        # Exercise multiple upstream pages through the real verified answer,
        # simulating a stricter upstream page cap without a second parser.
        def small_page(*args, **kwargs):
            kwargs["limit"] = 1
            return answer_regulatory_question(*args, **kwargs)
        with patch("biograph_steward.regulatory_sites.answer_regulatory_question", side_effect=small_page):
            first = answer_regulatory_sites(self.graph, limit=2)
            second = answer_regulatory_sites(self.graph, limit=2, offset=2)
        self.assertEqual(len(first["source_answer_page_seals"]), 4)
        self.assertEqual(first["summary"]["next_offset"], 2)
        self.assertIsNone(second["summary"]["next_offset"])
        self.assertEqual(first["summary"]["available_filters"], second["summary"]["available_filters"])
        rows = first["records"] + second["records"]
        self.assertEqual(len({r["observation_id"] for r in rows}), 4)
        self.assertEqual(sum(r["self_regulation"] for r in rows), 1)
        self.assertEqual(record({"records": rows}, "SIGNOR-3")["site_view"]["modification_action"], "phosphate_addition")

    def test_source_review_citations_seals_and_no_mutation_or_fetch(self):
        assertion_for(self.graph)["lifecycle_state"] = "rejected"
        before = deepcopy(self.graph)
        with patch("urllib.request.urlopen", side_effect=AssertionError("No retrieval allowed")):
            answer = answer_regulatory_sites(self.graph, source_run="invented_run")
        row = record(answer)
        self.assertEqual(row["local_review_state"], "rejected")
        self.assertEqual(row["source_observation"], observation(self.graph))
        self.assertTrue(row["citations"])
        self.assertEqual(answer["content_sha256"], digest({k: v for k, v in answer.items() if k != "content_sha256"}))
        self.assertEqual((answer["read_only"], answer["model_calls"], answer["source_fetches"], answer["graph_mutated"]),
                         (True, 0, 0, False))
        row["source_observation"]["source_row"]["RESIDUE"] = "changed"
        row["site_view"]["reported_site"]["label"] = "changed"
        self.assertEqual(self.graph, before)

    def test_filters_and_pagination_cannot_hide_source_tampering(self):
        edge_for(self.graph)["object"] = ANCHOR
        with self.assertRaises(ValueError):
            answer_regulatory_sites(self.graph, site="S9999", cell_context="missing", offset=99)

    def test_invalid_inputs_and_empty_valid_scope(self):
        for kw in ({"site": None}, {"site": "S0"}, {"site": "S15;S20"}, {"site": "s15"},
                   {"cell_context": None}, {"cell_context": "a;b"}, {"tissue_context": "x" * 201},
                   {"context_reporting": True}, {"context_reporting": "unknown"},
                   {"protein": "EGFR"}, {"direction": "sideways"}, {"offset": True},
                   {"offset": -1}, {"limit": 26}, {"limit": True}, {"source_run": "../other"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                answer_regulatory_sites(self.graph, **kw)
        self.graph["extension_observations"] = []
        answer = answer_regulatory_sites(self.graph)
        self.assertEqual(answer["records"], [])
        self.assertEqual(answer["summary"]["available_filters"], {"sites": [], "cell_contexts": [], "tissue_contexts": []})


if __name__ == "__main__":
    unittest.main()
