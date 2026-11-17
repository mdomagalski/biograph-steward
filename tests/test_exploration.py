"""Annotation traversal preserves review, qualification and source boundaries."""
from copy import deepcopy
import unittest

from biograph_steward.exploration import explore_paths, resolve_entity


def graph_fixture():
    nodes = [{"id": uid, "name": uid, "sym": uid,
              "category": "biolink:Protein" if uid != "W" else "biolink:Pathway"}
             for uid in ("A", "B", "C", "D", "W")]
    graph = {"graph_format": "test", "snapshot_sha256": "source-digest", "nodes": nodes,
             "assertions": [], "edges": [], "review_events": []}
    return graph


def add(graph, uid, subject, obj, *, symmetric=False, state="candidate", usable=True,
        predicate="test:annotation", qualifiers=None):
    qualifiers = qualifiers or {"assay": "MI:0018", "species": "NCBITaxon:9606"}
    eid = "e:" + uid
    edge = {"id": eid, "subject": subject, "predicate": predicate, "object": obj,
            "status": "passed_structural_checks" if usable else "needs_review",
            "qualifiers": deepcopy(qualifiers), "publications": ["PMID:12345"],
            "record_locators": ["snapshot.json#/targets/0/record/0"],
            "evidence_record": {"construct": "100063977", "outcome": "detected"},
            "retrieval_provenance": {"response_sha256": "untouched-response"}}
    graph["edges"].append(edge)
    graph["assertions"].append({"id": uid, "revision": "revision-" + uid,
        "subject": subject, "predicate": predicate, "object": obj,
        "kind": "assay_observation", "symmetric": symmetric, "lifecycle_state": state,
        "qualifiers": deepcopy(qualifiers), "source_names": ["TEST"],
        "evidence_edge_ids": [eid], "structurally_usable_evidence_ids": [eid] if usable else []})
    return graph


class ExplorationTests(unittest.TestCase):
    def test_direction_is_preserved_and_symmetry_is_explicit(self):
        graph = add(graph_fixture(), "ab", "A", "B")
        self.assertEqual(explore_paths(graph, "B", "A")["paths"], [])
        graph["assertions"][0]["symmetric"] = True
        result = explore_paths(graph, "B", "A")
        step = result["paths"][0]["steps"][0]
        self.assertEqual((step["subject"], step["object"]), ("A", "B"))
        self.assertEqual((step["from_id"], step["to_id"]), ("B", "A"))
        self.assertEqual(step["traversal_direction"], "reverse_symmetric")
        # Truthy text is not a normalization decision.
        graph["assertions"][0]["symmetric"] = "true"
        self.assertEqual(explore_paths(graph, "B", "A")["paths"], [])

    def test_candidate_and_provisional_are_not_silently_accepted(self):
        graph = add(graph_fixture(), "ab", "A", "B", state="accepted")
        add(graph, "bc", "B", "C", state="provisional")
        candidates = explore_paths(graph, "A", "C")
        path = candidates["paths"][0]
        self.assertEqual(path["review_status"], "candidate_evidence")
        self.assertEqual([s["review_state"] for s in path["steps"]], ["accepted", "provisional"])
        accepted = explore_paths(graph, "A", "C", view="accepted")
        self.assertEqual(accepted["paths"], [])
        self.assertEqual(accepted["excluded_assertions"]["assertions_without_recorded_acceptance"], 1)
        graph["assertions"][1]["lifecycle_state"] = "accepted"
        self.assertEqual(explore_paths(graph, "A", "C", view="accepted")["paths"][0]["review_status"], "accepted")

    def test_rejected_quarantined_obsolete_or_structurally_unusable_do_not_traverse(self):
        for state in ("rejected", "quarantined", "obsolete", "unknown"):
            with self.subTest(state=state):
                result = explore_paths(add(graph_fixture(), "ab", "A", "B", state=state), "A", "B")
                self.assertEqual(result["paths"], [])
                self.assertEqual(result["excluded_assertions"]["assertions_outside_inspectable_review_states"], 1)
        result = explore_paths(add(graph_fixture(), "ab", "A", "B", state="accepted", usable=False), "A", "B")
        self.assertEqual(result["paths"], [])
        self.assertEqual(result["excluded_assertions"]["assertions_without_structurally_usable_evidence"], 1)

    def test_parallel_qualified_assertions_stay_separate_and_source_records_are_retained(self):
        graph = add(graph_fixture(), "ab1", "A", "B", qualifiers={"assay": "MI:0018", "species": "NCBITaxon:9606"})
        add(graph, "ab2", "A", "B", qualifiers={"assay": "MI:0006", "species": "NCBITaxon:10090"})
        graph["assay_attachment_sha256"] = "attachment-digest"
        graph["assay_publication_sha256"] = "publication-digest"
        before = deepcopy(graph)
        result = explore_paths(graph, "A", "B")
        self.assertEqual(len(result["paths"]), 2)
        self.assertEqual([p["assertion_ids"] for p in result["paths"]], [["ab1"], ["ab2"]])
        self.assertEqual({p["steps"][0]["qualifiers"]["species"] for p in result["paths"]},
                         {"NCBITaxon:9606", "NCBITaxon:10090"})
        self.assertEqual(result["citations"][0]["evidence_records"][0], graph["edges"][0])
        self.assertEqual(result["assay_attachment_sha256"], "attachment-digest")
        self.assertEqual(result["assay_publication_sha256"], "publication-digest")
        self.assertEqual(graph, before)
        result["citations"][0]["evidence_records"][0]["evidence_record"]["outcome"] = "changed"
        result["assertions"][0]["qualifiers"]["species"] = "changed"
        self.assertEqual(graph, before)

    def test_hop_cutoff_simple_paths_and_shortest_hop_order(self):
        graph = add(graph_fixture(), "ab", "A", "B", symmetric=True)
        add(graph, "bc", "B", "C")
        add(graph, "ac", "A", "C")
        add(graph, "cd", "C", "D")
        one = explore_paths(graph, "A", "D", max_hops=1)
        self.assertEqual(one["paths"], [])
        result = explore_paths(graph, "A", "D", max_hops=3)
        self.assertEqual([p["node_ids"] for p in result["paths"]], [["A", "C", "D"], ["A", "B", "C", "D"]])
        self.assertTrue(all(len(p["node_ids"]) == len(set(p["node_ids"])) for p in result["paths"]))
        self.assertTrue(result["search"]["complete_within_requested_bounds"])
        self.assertEqual(explore_paths(graph, "A", "D", max_hops=3), result)

    def test_open_target_and_typed_relationship_filters(self):
        graph = add(graph_fixture(), "ab", "A", "B", predicate="test:interaction")
        add(graph, "aw", "A", "W", predicate="test:membership")
        result = explore_paths(graph, "A", predicates=["test:interaction"], node_categories=["biolink:Protein"])
        self.assertEqual([p["node_ids"] for p in result["paths"]], [["A", "B"]])
        self.assertEqual(result["query"]["predicates"], ["test:interaction"])
        self.assertEqual(result["excluded_assertions"]["assertions_outside_selected_relationships"], 1)
        with self.assertRaisesRegex(ValueError, "both chosen endpoints"):
            explore_paths(graph, "A", "W", node_categories=["biolink:Protein"])

    def test_result_cap_requires_a_further_matching_path_and_work_cap_is_explicit(self):
        graph = add(graph_fixture(), "ab", "A", "B")
        exact = explore_paths(graph, "A", max_paths=1)
        self.assertFalse(exact["search"]["truncated"])
        add(graph, "ac", "A", "C")
        capped = explore_paths(graph, "A", max_paths=1)
        self.assertEqual(capped["search"]["truncation_reason"], "max_paths")
        self.assertEqual(capped["search"]["paths_returned"], 1)
        self.assertFalse(capped["search"]["complete_within_requested_bounds"])
        limited = explore_paths(graph, "A", max_expansions=1)
        self.assertEqual(limited["search"]["expansions"], 1)
        self.assertEqual(limited["search"]["truncation_reason"], "max_expansions")

    def test_id_resolution_does_not_silently_choose_ambiguous_symbols(self):
        graph = graph_fixture()
        graph["nodes"][0]["sym"] = "DUPLICATE"
        graph["nodes"][1]["sym"] = "duplicate"
        with self.assertRaisesRegex(ValueError, "Ambiguous entity.*A, B"):
            resolve_entity(graph, "Duplicate")
        self.assertEqual(resolve_entity(graph, "A"), "A")
        graph["nodes"][0]["id"] = "UniProtKB:P22674"
        self.assertEqual(resolve_entity(graph, "P22674"), "UniProtKB:P22674")
        with self.assertRaisesRegex(ValueError, "outside this saved workspace"):
            resolve_entity(graph, "NOT_A_SAVED_NODE")

    def test_invalid_parameters_and_broken_source_references_fail_closed(self):
        graph = add(graph_fixture(), "ab", "A", "B")
        for options in ({"max_hops": True}, {"max_hops": 4}, {"max_paths": 51},
                        {"max_expansions": 20_001}, {"view": "all"}, {"predicates": []},
                        {"predicates": ["absent"]}, {"node_categories": "biolink:Protein"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                explore_paths(graph, "A", **options)
        with self.assertRaisesRegex(ValueError, "distinct"):
            explore_paths(graph, "A", "A")
        graph["edges"][0]["object"] = "C"
        with self.assertRaisesRegex(ValueError, "disagree"):
            explore_paths(graph, "A", "B")
        graph["edges"][0]["object"] = "B"
        graph["edges"][0]["qualifiers"]["species"] = "NCBITaxon:10090"
        with self.assertRaisesRegex(ValueError, "qualifiers disagree"):
            explore_paths(graph, "A", "B")
        graph["edges"] = []
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            explore_paths(graph, "A", "B")

    def test_actual_normalized_workspace_reuses_explicit_symmetry_and_qualifiers(self):
        from biograph_steward.graph import build_graph
        from test_normalization import fixture
        graph = build_graph(fixture())
        assertion = next(a for a in graph["assertions"] if a["kind"] == "protein_interaction")
        result = explore_paths(graph, assertion["object"], assertion["subject"], max_hops=1,
                               predicates=[assertion["predicate"]])
        path = next(p for p in result["paths"] if p["assertion_ids"] == [assertion["id"]])
        self.assertEqual(path["steps"][0]["traversal_direction"], "reverse_symmetric")
        self.assertEqual(path["steps"][0]["qualifiers"], assertion["qualifiers"])
        self.assertEqual(result["snapshot_sha256"], graph["snapshot_sha256"])
        self.assertTrue(all(c["evidence_records"] for c in result["citations"]))


if __name__ == "__main__":
    unittest.main()
