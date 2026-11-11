"""Invented source fixtures check guidance fidelity; no biological gold labels."""
from copy import deepcopy
import json
import unittest

from biograph_steward.assertions import build_assertions
from biograph_steward.graph import build_graph
from biograph_steward.inspection import inspect_selection
from biograph_steward.intact_evidence import build_evidence as intact_evidence
from biograph_steward.lambourne_evidence import build_evidence as assay_evidence
from biograph_steward.questions import graph_basis
from test_civic import fixture as civic_fixture
from test_cohort_graph import fixture as cohort_fixture
from test_intact_evidence import fixture as intact_fixture
from test_lambourne_evidence import fixture as assay_fixture


def lambourne_graph():
    value = assay_evidence(*assay_fixture())
    graph = value["graph"]
    graph["assay_observations"] = value["observations"]
    return graph


def intact_graph():
    value = intact_evidence(*intact_fixture())
    graph = value["graph"]
    graph["assay_observations"] = value["observations"]
    return graph


class InspectionTests(unittest.TestCase):
    def test_provider_label_without_reference_stays_unresolved(self):
        graph = build_graph(cohort_fixture())
        edge = next(e for e in graph["edges"] if e["record_kind"] == "protein_interaction")
        before = deepcopy(graph)
        view = inspect_selection(graph, edge["id"], run_id="test_workspace")
        self.assertEqual(view["review"]["state"], "candidate")
        self.assertEqual(view["source_records"][0]["source_labels"], edge["evidence_sources"])
        self.assertEqual(view["source_records"][0]["reference_status"], "primary_reference_not_supplied")
        self.assertFalse(any(link["kind"] == "publication" for link in view["links"]))
        self.assertIn("is a source label", next(m["note"] for m in view["missing_context"] if m["field"] == "primary_reference"))
        self.assertIn("physical association", view["summary"])
        self.assertEqual(view["reuse"]["status"], "unresolved")
        self.assertIsNone(view["reuse"]["independent_evidence_count"])
        self.assertEqual(graph, before)

    def test_civic_editorial_acceptance_is_not_local_acceptance(self):
        pharos, civic = civic_fixture()
        graph = build_graph(pharos, civic_snapshot=civic)
        edge = next(e for e in graph["edges"] if e["record_kind"] == "variant_therapy_response"
                    and len(e["evidence_record"]["therapies"]) > 1)
        self.assertEqual(edge["evidence_record"]["status"], "ACCEPTED")
        view = inspect_selection(graph, edge["id"])
        self.assertEqual(view["review"]["state"], "candidate")
        self.assertIn("complete molecular profile", view["summary"])
        context = view["sections"][0]
        self.assertIn("complete combination therapy set", context["text"])
        self.assertEqual(context["fields"]["evidence_direction"], edge["evidence_record"]["evidenceDirection"])
        self.assertTrue(any(link["kind"] == "source_record" and link["url"].endswith(str(edge["evidence_record"]["id"])) for link in view["links"]))
        self.assertEqual(view["reuse"]["status"], "saved_scope_overlap_annotation")
        self.assertIn("not establish biological truth", view["review"]["note"])

    def test_lambourne_guide_retains_constructs_without_assigning_protein_roles(self):
        graph = lambourne_graph()
        observation = next(o for o in graph["assay_observations"] if o["assay_status"] == "detected")
        before = deepcopy(graph)
        view = inspect_selection(graph, observation["id"], run_id="development_demo")
        section = next(s for s in view["sections"] if s["title"] == "Two-hybrid constructs")
        self.assertEqual(section["fields"], observation["constructs"])
        self.assertIn("does not assign a protein to a construct", section["text"])
        self.assertIn("not biological direction", section["text"])
        self.assertTrue(any(m["field"] == "assay_host_taxon" for m in view["missing_context"]))
        crosswalk = next(link for link in view["links"] if link["kind"] == "construct_crosswalk")
        self.assertEqual(crosswalk["url"], "/api/assay-source/development_demo/source/freeze/source/orf_map.tsv")
        self.assertTrue(view["read_only"])
        self.assertEqual((view["source_fetches"], view["model_calls"], view["actions"]), (0, 0, []))
        self.assertEqual(graph, before)

    def test_excluded_observation_does_not_gain_assertion_or_acceptance(self):
        graph = lambourne_graph()
        observation = next(o for o in graph["assay_observations"] if not o["evaluable"])
        view = inspect_selection(graph, observation["id"])
        self.assertIsNone(view["assertion"])
        self.assertEqual(view["source_records"], [])
        self.assertEqual(view["review"]["state"], "not_applicable")
        self.assertIn("no evidence edge", view["summary"])
        self.assertFalse(any(link["kind"].startswith("local") for link in view["links"]))

    def test_intact_explanation_reuses_full_source_fields_and_original_database(self):
        graph = intact_graph()
        observation = graph["assay_observations"][0]
        view = inspect_selection(graph, graph["assertions"][0]["id"], run_id="intact_demo")
        source = view["source_records"][0]
        self.assertIn("IntAct/IMEx", source["aggregator"])
        self.assertEqual(source["source_labels"], ["MINT"])
        self.assertIn("binary experimental origin is unknown", next(s["text"] for s in view["sections"] if s["title"] == "Complex expansion"))
        self.assertTrue(any(link["kind"] == "source_record" and "IM-SYNTHETIC-1" in link["url"] for link in view["links"]))
        self.assertEqual(view["observations"], [observation["id"]])

    def test_local_review_comes_from_assertion_not_stale_observation_copy(self):
        graph = lambourne_graph()
        observation = next(o for o in graph["assay_observations"] if o["evaluable"])
        assertion = next(a for a in graph["assertions"] if a["id"] == next(e for e in graph["edges"] if e["id"] == observation["graph_edge_id"])["assertion_id"])
        assertion["lifecycle_state"] = "provisional"
        self.assertEqual(observation["local_review_state"], "candidate")
        view = inspect_selection(graph, observation["id"])
        self.assertEqual(view["review"]["state"], "provisional")
        self.assertEqual(view["graph_basis_sha256"], graph_basis(graph))

    def test_unsafe_source_links_and_path_traversal_are_not_returned(self):
        graph = lambourne_graph()
        observation = next(o for o in graph["assay_observations"] if o["evaluable"])
        edge = next(e for e in graph["edges"] if e["id"] == observation["graph_edge_id"])
        for url in ("javascript:alert(1)", "https://name:secret@example.org/record", "https://[broken", "https://example.org:bad/record", "https://example.org/a\nb"):
            edge["evidence_record"]["url"] = url
            view = inspect_selection(graph, edge["id"])
            self.assertTrue(view["omitted_links"], url)
            self.assertFalse(any(link["url"] == url for link in view["links"]), url)
        observation["source_locators"].append({"role": "invented", "locator": "../secret.txt"})
        view = inspect_selection(graph, observation["id"], run_id="safe")
        self.assertFalse(any(".." in link["url"] for link in view["links"]))
        with self.assertRaisesRegex(ValueError, "Invalid workspace"):
            inspect_selection(graph, observation["id"], run_id="../escape")

    def test_unknown_qualifier_is_shown_verbatim_and_not_interpreted(self):
        graph = build_graph(cohort_fixture())
        assertion = graph["assertions"][0]
        assertion["qualifiers"]["unrecognized_future_context"] = "INVENTED literal"
        view = inspect_selection(graph, assertion["id"])
        self.assertEqual(view["qualifiers"]["unrecognized_future_context"], "INVENTED literal")
        self.assertTrue(any(m["field"] == "qualifier_interpretation" for m in view["missing_context"]))

    def test_reuse_annotation_requires_matching_source_and_review_bindings(self):
        graph = intact_graph()
        graph.update(assay_attachment_sha256="a"*64, assay_publication_sha256="b"*64)
        observation = graph["assay_observations"][0]
        row = {"observation_id": observation["id"], "products": observation["products"], "study": observation["study"],
               "current_string_status": "confirmed_user_assisted", "historical_pharos_reuse": None,
               "explanation": "Invented fixture: same curated record, not independent evidence.", "evidence_links": []}
        reuse = {"status": "available", "source_run": "test", "graph_basis_sha256": graph_basis(graph),
                 **{key: graph[key] for key in ("snapshot_sha256", "assay_attachment_sha256", "assay_publication_sha256")},
                 "observations": [row]}
        before = deepcopy((graph, reuse))
        view = inspect_selection(graph, observation["id"], run_id="test", source_reuse=reuse)
        self.assertEqual(view["reuse"]["status"], "saved_source_reuse_annotation")
        self.assertIsNone(view["reuse"]["independent_evidence_count"])
        self.assertIn("not independent", view["questions"][-1]["answer"])
        self.assertEqual((graph, reuse), before)
        for key in ("source_run", "graph_basis_sha256", "assay_publication_sha256"):
            changed = deepcopy(reuse); changed[key] = "changed"
            with self.assertRaises(ValueError):
                inspect_selection(graph, observation["id"], run_id="test", source_reuse=changed)
        changed = deepcopy(reuse); changed["observations"][0]["products"] = ["UniProtKB:OTHER"]
        with self.assertRaisesRegex(ValueError, "differs"):
            inspect_selection(graph, observation["id"], run_id="test", source_reuse=changed)

    def test_unknown_selection_fails_and_text_is_not_rendered_as_html(self):
        graph = build_graph(cohort_fixture())
        with self.assertRaisesRegex(ValueError, "exact assertion"):
            inspect_selection(graph, "does_not_exist")
        edge = graph["edges"][0]
        edge["primary_source_raw"] = '<script>alert("invented")</script>'
        edge.pop("evidence_sources", None)
        view = inspect_selection(graph, edge["id"])
        self.assertIn('<script>alert("invented")</script>', view["source_records"][0]["source_labels"])
        # It is intentionally JSON/text; rendering this with textContent is the UI contract.
        json.dumps(view)

    def test_unverifiable_optional_audit_never_restores_classification(self):
        graph = intact_graph()
        selected = graph["assertions"][0]["id"]
        view = inspect_selection(graph, selected, run_id="test", source_reuse={
            "status": "unverifiable", "source_run": "test", "observations": [{
                "observation_id": graph["assay_observations"][0]["id"],
                "current_string_status": "confirmed_user_assisted"}]})
        self.assertEqual(view["reuse"]["status"], "unverifiable_saved_annotation")
        self.assertEqual(view["reuse"]["records"], [])
        self.assertIn("could not be verified", view["questions"][-1]["answer"])
        self.assertFalse(any(link["kind"] == "local_reuse" for link in view["links"]))


if __name__ == "__main__":
    unittest.main()
