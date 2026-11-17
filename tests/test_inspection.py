"""Invented source fixtures check guidance fidelity; no biological gold labels."""
from copy import deepcopy
import json
import unittest
from urllib.parse import parse_qs, urlsplit

from biograph_steward.assertions import build_assertions
from biograph_steward.graph import build_graph
from biograph_steward.inspection import (
    _civic_context_url, _go_context_url, _reactome_context_url, inspect_selection,
)
from biograph_steward.intact_evidence import build_evidence as intact_evidence
from biograph_steward.lambourne_evidence import build_evidence as assay_evidence
from biograph_steward.questions import graph_basis
from test_civic import CivicAPI, fixture as civic_fixture
from test_cohort_graph import fixture as cohort_fixture
from test_intact_evidence import fixture as intact_fixture
from test_lambourne_evidence import fixture as assay_fixture
from test_normalization import resign


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
    def test_civic_current_profile_preserves_complex_scope_and_original_references(self):
        api = CivicAPI()
        profile = deepcopy(api.rows[0]["molecularProfile"])
        profile.update(isComplex=True, isMultiVariant=True, rawName="#VID81 AND #VID82")
        other = deepcopy(profile["variants"][0])
        other.update(id=82, name="Second invented variant")
        profile["variants"].append(other)
        for row in api.rows:
            row["molecularProfile"] = deepcopy(profile)
        pharos, civic = civic_fixture(api)
        graph = build_graph(pharos, civic_snapshot=civic)
        edge = next(e for e in graph["edges"] if e["record_kind"] == "variant_therapy_response")
        before = deepcopy(graph)
        view = inspect_selection(graph, edge["id"])
        lookup = next(link for link in view["links"] if link["kind"] == "context_lookup")
        self.assertEqual(lookup["url"], "https://civicdb.org/molecular-profiles/81")
        self.assertEqual(lookup["label"], "Current CIViC profile and Assertions")
        context = next(q for q in view["questions"] if q["id"] == "context")
        trace = next(q for q in view["questions"] if q["id"] == "source-trace")
        self.assertIn(lookup["id"], context["link_ids"])
        self.assertNotIn(lookup["id"], trace["link_ids"])
        self.assertNotIn(lookup["id"], view["source_records"][0]["link_ids"])
        for phrase in ("Evidence Items and Assertions", "not restricted to accepted Assertions",
                       "across diseases and therapies", "complex profiles", "editorial status",
                       "whole therapy set", "variant origin", "combination exclusions",
                       "automatically match or refute", "change local review", "independent corroboration"):
            self.assertIn(phrase, context["answer"])
        self.assertEqual(view["source_records"][0]["reference_status"], "references_supplied")
        self.assertEqual(edge["subject"], "CIViC.molecularprofile:81")
        self.assertEqual(edge["evidence_record"]["molecularProfile"]["rawName"], "#VID81 AND #VID82")
        self.assertEqual(view["review"]["state"], "candidate")
        self.assertEqual((view["read_only"], view["source_fetches"], view["model_calls"], view["actions"]),
                         (True, 0, 0, []))
        self.assertEqual(graph, before)

    def test_civic_lookup_requires_native_profile_identity_and_agreeing_optional_link(self):
        edge = {"record_kind": "variant_therapy_response", "primary_source_raw": "CIViC",
                "subject": "CIViC.molecularprofile:81"}
        for profile in ({"id": 81}, {"id": 81, "link": None},
                        {"id": 81, "link": "/molecular-profiles/81"},
                        {"id": 81, "link": "https://civicdb.org/molecular-profiles/81"}):
            with self.subTest(profile=profile):
                self.assertEqual(_civic_context_url(edge, {"molecularProfile": profile}),
                                 "https://civicdb.org/molecular-profiles/81")
        for identifier in (True, False, 0, -1, 81.0, "81", "081", None):
            with self.subTest(identifier=identifier):
                self.assertIsNone(_civic_context_url(edge, {"molecularProfile": {"id": identifier}}))
        for link in ("", "/molecular-profiles/82", "/variants/81", "/molecular-profiles/081",
                     "https://civicdb.org/molecular-profiles/81?status=Accepted",
                     "https://civicdb.org/molecular-profiles/81#assertions",
                     "https://civicdb.org.evil.example/molecular-profiles/81",
                     "http://civicdb.org/molecular-profiles/81", "/molecular-profiles/81/", True):
            with self.subTest(link=link):
                self.assertIsNone(_civic_context_url(edge, {"molecularProfile": {"id": 81, "link": link}}))
        for field, value in (("subject", "CIViC.molecularprofile:82"), ("subject", "CIViC.variant:81"),
                             ("subject", "CIViC.molecularprofile:081"), ("primary_source_raw", "OTHER"),
                             ("record_kind", "protein_interaction")):
            with self.subTest(field=field, value=value):
                self.assertIsNone(_civic_context_url({**edge, field: value}, {"molecularProfile": {"id": 81}}))
        for profile in (None, [], "81"):
            self.assertIsNone(_civic_context_url(edge, {"molecularProfile": profile}))

    def test_civic_parallel_records_share_lookup_without_merging_evidence_or_notes(self):
        api = CivicAPI()
        api.rows = [api.row(100, "RESISTANCE"), api.row(101, "RESISTANCE")]
        pharos, civic = civic_fixture(api)
        graph = build_graph(pharos, civic_snapshot=civic)
        assertion = next(a for a in graph["assertions"] if a["kind"] == "variant_therapy_response")
        self.assertEqual(len(assertion["evidence_edge_ids"]), 2)
        before = deepcopy(graph)
        view = inspect_selection(graph, assertion["id"])
        self.assertEqual(len(view["source_records"]), 2)
        self.assertEqual(sum(link["kind"] == "context_lookup" for link in view["links"]), 1)
        self.assertEqual(sum(row["field"] == "civic_profile_context" for row in view["missing_context"]), 1)
        self.assertEqual(sum(link["kind"] == "source_record" for link in view["links"]), 2)
        self.assertEqual(view["reuse"]["independent_evidence_count"], None)
        self.assertEqual(graph, before)

    def test_civic_mismatched_lookup_is_omitted_without_changing_original_reference_status(self):
        pharos, civic = civic_fixture()
        original = build_graph(pharos, civic_snapshot=civic)
        original_edge = next(e for e in original["edges"] if e["record_kind"] == "variant_therapy_response")
        original_view = inspect_selection(original, original_edge["id"])
        expected_sources = original_view["source_records"]
        expected_links = {link["id"]: (link["kind"], link["url"]) for link in original_view["links"]}
        for field, value in (("subject", "CIViC.molecularprofile:82"),
                             ("profile_id", True), ("profile_id", "81"),
                             ("profile_link", "/molecular-profiles/82"),
                             ("primary_source_raw", "OTHER")):
            with self.subTest(field=field, value=value):
                graph = deepcopy(original)
                edge = next(e for e in graph["edges"] if e["id"] == original_edge["id"])
                if field == "profile_id":
                    edge["evidence_record"]["molecularProfile"]["id"] = value
                elif field == "profile_link":
                    edge["evidence_record"]["molecularProfile"]["link"] = value
                else:
                    edge[field] = value
                before = deepcopy(graph)
                view = inspect_selection(graph, edge["id"])
                self.assertFalse(any(link["kind"] == "context_lookup" for link in view["links"]))
                self.assertEqual([s["reference_status"] for s in view["source_records"]],
                                 [s["reference_status"] for s in expected_sources])
                links = {link["id"]: (link["kind"], link["url"]) for link in view["links"]}
                self.assertEqual([[links[lid] for lid in s["link_ids"]] for s in view["source_records"]],
                                 [[expected_links[lid] for lid in s["link_ids"]] for s in expected_sources])
                self.assertEqual((view["source_fetches"], view["model_calls"]), (0, 0))
                self.assertEqual(graph, before)

    def test_reactome_current_lookup_preserves_old_source_link_and_distinct_context_scope(self):
        snapshot = cohort_fixture()
        record = snapshot["targets"][0]["pathways"][0]
        old_url = "https://idg.reactome.org/PathwayBrowser/#/" + record["sourceID"]
        record = {**record, "url": old_url}
        snapshot["targets"][0]["pathways"][0] = record
        graph = build_graph(resign(snapshot))
        edge = next(e for e in graph["edges"] if e["record_kind"] == "pathway_membership"
                    and e["evidence_record"].get("url") == old_url)
        before = deepcopy(graph)
        view = inspect_selection(graph, edge["id"])
        lookup = next(link for link in view["links"] if link["kind"] == "context_lookup")
        self.assertEqual(lookup["url"], "https://reactome.org/content/detail/" + record["sourceID"])
        self.assertTrue(any(link["url"] == old_url and link["kind"] == "source_reference"
                            for link in view["links"]))
        context = next(q for q in view["questions"] if q["id"] == "context")
        trace = next(q for q in view["questions"] if q["id"] == "source-trace")
        self.assertIn(lookup["id"], context["link_ids"])
        self.assertNotIn(lookup["id"], trace["link_ids"])
        self.assertNotIn(lookup["id"], view["source_records"][0]["link_ids"])
        for phrase in ("reaction and complex roles", "compartment", "inferred from another species",
                       "supporting references", "does not identify a protein's specific role",
                       "do not verify the historical imported release", "independent corroboration"):
            self.assertIn(phrase, context["answer"])
        self.assertEqual((view["read_only"], view["source_fetches"], view["model_calls"], view["actions"]),
                         (True, 0, 0, []))
        self.assertEqual(graph, before)

    def test_reactome_lookup_does_not_fill_missing_references_or_repeat_parallel_notes(self):
        snapshot = cohort_fixture()
        record = snapshot["targets"][0]["pathways"][0]
        snapshot["targets"][0]["pathways"].append({**record, "pwid": 555})
        graph = build_graph(resign(snapshot))
        assertion = next(a for a in graph["assertions"] if a["kind"] == "pathway_membership"
                         and len(a["evidence_edge_ids"]) == 2)
        before = deepcopy(graph)
        view = inspect_selection(graph, assertion["id"])
        self.assertEqual(len(view["source_records"]), 2)
        self.assertEqual(sum(link["kind"] == "context_lookup" for link in view["links"]), 1)
        self.assertEqual(sum(row["field"] == "reactome_pathway_context" for row in view["missing_context"]), 1)
        self.assertTrue(all(row["reference_status"] == "primary_reference_not_supplied"
                            and row["link_ids"] == [] for row in view["source_records"]))
        self.assertFalse(any(link["kind"] == "publication" for link in view["links"]))
        self.assertEqual(sum(row["field"] == "primary_reference" for row in view["missing_context"]), 2)
        self.assertEqual(graph, before)

    def test_reactome_lookup_rejects_alias_versions_nonhuman_and_source_mismatches(self):
        edge = {"record_kind": "pathway_membership", "primary_source_raw": "Reactome",
                "object": "REACT:R-HSA-1"}
        record = {"type": "Reactome", "sourceID": "R-HSA-1"}
        self.assertEqual(_reactome_context_url(edge, record), "https://reactome.org/content/detail/R-HSA-1")
        for identifier in ("R-HSA-0", "R-HSA-01", "R-HSA-1.2", "R-MMU-1", "REACT:1",
                           "R-HSA-1\n", " R-HSA-1", "R-HSA-1?species=9606", 1, None):
            with self.subTest(identifier=identifier):
                self.assertIsNone(_reactome_context_url({**edge, "object": "REACT:" + str(identifier)},
                                                       {**record, "sourceID": identifier}))
        for field, value in (("object", "REACT:R-HSA-2"), ("object", "R-HSA-1"),
                             ("primary_source_raw", "STRINGDB,Reactome"), ("primary_source_raw", "reactome"),
                             ("record_kind", "protein_interaction")):
            with self.subTest(field=field, value=value):
                self.assertIsNone(_reactome_context_url({**edge, field: value}, record))
        self.assertIsNone(_reactome_context_url(edge, {**record, "type": "WikiPathways"}))
        graph = build_graph(cohort_fixture())
        native = next(e for e in graph["edges"] if e["record_kind"] == "pathway_membership")
        native["object"] = "REACT:R-HSA-999"
        before = deepcopy(graph)
        self.assertFalse(any(link["kind"] == "context_lookup"
                             for link in inspect_selection(graph, native["id"])["links"]))
        self.assertEqual(graph, before)

    def test_go_current_lookup_is_exact_and_not_a_historical_primary_reference(self):
        graph = build_graph(cohort_fixture())
        edge = next(e for e in graph["edges"] if e["record_kind"] == "go_annotation")
        before = deepcopy(graph)
        view = inspect_selection(graph, edge["id"])
        lookup = next(link for link in view["links"] if link["kind"] == "context_lookup")
        self.assertEqual(lookup["url"], "https://www.ebi.ac.uk/QuickGO/annotations?geneProductId="
                         + edge["subject"].replace(":", "%3A") + "&goId="
                         + edge["object"].replace(":", "%3A") + "&goUsage=exact")
        self.assertEqual(parse_qs(urlsplit(lookup["url"]).query), {
            "geneProductId": [edge["subject"]], "goId": [edge["object"]], "goUsage": ["exact"]})
        context = next(q for q in view["questions"] if q["id"] == "context")
        trace = next(q for q in view["questions"] if q["id"] == "source-trace")
        self.assertIn(lookup["id"], context["link_ids"])
        self.assertNotIn(lookup["id"], trace["link_ids"])
        self.assertIn("NOT-qualified", context["answer"])
        self.assertIn("does not identify the historical Pharos record", context["answer"])
        self.assertEqual(view["source_records"][0]["reference_status"], "primary_reference_not_supplied")
        self.assertNotIn(lookup["id"], view["source_records"][0]["link_ids"])
        self.assertFalse(any(link["kind"] == "publication" for link in view["links"]))
        self.assertEqual((view["read_only"], view["source_fetches"], view["model_calls"], view["actions"]),
                         (True, 0, 0, []))
        self.assertEqual(graph, before)

    def test_go_lookup_omits_tampered_ids_and_inconsistent_source_term(self):
        base = build_graph(cohort_fixture())
        original = next(e for e in base["edges"] if e["record_kind"] == "go_annotation")
        for field, value in (
            ("subject", "P04637"), ("subject", "UniProtKB:TP53"),
            ("subject", "UniProtKB:P04637&qualifier=NOT"),
            ("subject", " UniProtKB:P04637"), ("subject", "UniProtKB:P04637\n"),
            ("object", "GO:0000001&goUsage=descendants"), ("object", "GO:1"),
            ("record_goid", "GO:0000002"), ("record_goid", "GO:0000001&qualifier=NOT"),
        ):
            with self.subTest(field=field, value=value):
                graph = deepcopy(base)
                edge = next(e for e in graph["edges"] if e["id"] == original["id"])
                if field == "record_goid":
                    edge["evidence_record"]["goid"] = value
                else:
                    edge[field] = value
                before = deepcopy(graph)
                view = inspect_selection(graph, edge["id"])
                self.assertFalse(any(link["kind"] == "context_lookup" for link in view["links"]))
                self.assertEqual(graph, before)

    def test_go_lookup_preserves_full_product_identifier_and_ignores_other_families(self):
        # URL construction preserves an explicit form; it does not identify an
        # isoform as the canonical product or make a scientific mapping claim.
        edge = {"record_kind": "go_annotation", "subject": "UniProtKB:P04637-2", "object": "GO:0000001"}
        url = _go_context_url(edge, {"goid": "GO:0000001"})
        self.assertEqual(parse_qs(urlsplit(url).query)["geneProductId"], ["UniProtKB:P04637-2"])
        self.assertIsNone(_go_context_url({**edge, "record_kind": "protein_interaction"}, {"goid": edge["object"]}))

    def test_go_lookup_does_not_repeat_guidance_or_merge_parallel_source_records(self):
        snapshot = cohort_fixture()
        record = snapshot["targets"][0]["pharos_context"]["go"][0]
        snapshot["targets"][0]["pharos_context"]["go"].append({**record, "assigned_by": "SECOND", "evidence": "IDA"})
        graph = build_graph(resign(snapshot))
        assertion = next(a for a in graph["assertions"] if a["kind"] == "go_annotation"
                         and len(a["evidence_edge_ids"]) == 2)
        before = deepcopy(graph)
        view = inspect_selection(graph, assertion["id"])
        self.assertEqual(len(view["source_records"]), 2)
        self.assertEqual(sum(link["kind"] == "context_lookup" for link in view["links"]), 1)
        self.assertEqual(sum(row["field"] == "go_annotation_context" for row in view["missing_context"]), 1)
        self.assertTrue(all(row["reference_status"] == "primary_reference_not_supplied"
                            for row in view["source_records"]))
        self.assertEqual(graph, before)

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

    def test_civic_first_explanation_preserves_study_type_and_complete_treatment_context(self):
        pharos, civic = civic_fixture()
        graph = build_graph(pharos, civic_snapshot=civic)
        edge = next(e for e in graph["edges"] if e["record_kind"] == "variant_therapy_response"
                    and len(e["evidence_record"]["therapies"]) > 1)
        edge["evidence_record"]["evidenceLevel"] = "C"
        before = deepcopy(graph)
        view = inspect_selection(graph, edge["id"])
        text = next(q["answer"] for q in view["questions"] if q["id"] == "what-shows")
        self.assertIn("C — Case study", text)
        record = edge["evidence_record"]
        for therapy in record["therapies"]:
            self.assertIn(therapy["name"], text)
        for value in (record["molecularProfile"]["name"], record["disease"]["name"], record["evidenceDirection"]):
            self.assertIn(value, text)
        self.assertIn("ingredient filter does not isolate a single-drug effect", text)
        self.assertIn("not a new confidence estimate", text)
        self.assertEqual(view["review"]["state"], "candidate")
        self.assertEqual(graph, before)

    def test_unmapped_civic_level_is_preserved_without_a_clinical_category_guess(self):
        pharos, civic = civic_fixture()
        graph = build_graph(pharos, civic_snapshot=civic)
        edge = next(e for e in graph["edges"] if e["record_kind"] == "variant_therapy_response")
        edge["evidence_record"]["evidenceLevel"] = "SOURCE_FUTURE_LEVEL"
        view = inspect_selection(graph, edge["id"])
        text = next(q["answer"] for q in view["questions"] if q["id"] == "what-shows")
        self.assertIn("SOURCE_FUTURE_LEVEL — Unmapped source level", text)
        self.assertNotIn("— Clinical evidence", text)

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
