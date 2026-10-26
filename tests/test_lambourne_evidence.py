"""Assay observations must never become unqualified interaction conclusions."""
from copy import deepcopy
import unittest

from biograph_steward.client import digest
from biograph_steward.lambourne_evidence import ASSAY, PREDICATE, build_evidence
from biograph_steward.questions import answer_question


def fixture():
    rows, lookups = [], []
    states = [("detected", "no_match_both_endpoints_resolved", ["P01111", "P01112"]),
              ("not_detected", "present_in_raw_ppi", ["P01112", "P01116"]),
              ("failed_sequence_confirmation", "no_match_both_endpoints_resolved", ["P04626", "P04637"]),
              ("not_detected", "no_match_one_endpoint_resolved", ["P00533", "P01111"])]
    for n, (status, state, pair) in enumerate(states, 2):
        identity = {"source_row": n, "uniprot_a": pair[1], "uniprot_b": pair[0],
                    "ad_orf_id": str(n + 100), "db_orf_id": str(n + 200),
                    "source_dataset_column_5": "Invented", "source_dataset_column_6": "Invented"}
        raw = [{"subject": pair[0], "partner": pair[1], "record": {"type": "STRINGDB"},
                "locator": "chunks/invented.json#/requests/0/response/data/t0/rows/0"}] if state == "present_in_raw_ppi" else []
        lookup = {"source_row": n, "products": pair, "identity": identity,
                  "pharos_status": state, "pharos_matches": {"raw": raw, "retained": []},
                  "resolved_endpoint_count": 1 if state == "no_match_one_endpoint_resolved" else 2}
        comparator = {"source_row": n, "products": pair, "identity": deepcopy(identity),
                      "pharos_status": state, "comparator": None if state == "no_match_one_endpoint_resolved" else int(bool(raw)),
                      "lookup_record_sha256": digest(lookup), "huri_overlap": n == 3}
        eligible = status in {"detected", "not_detected"}
        assay = {"source_row": n, "products": pair, "ad_orf_id": identity["ad_orf_id"],
                 "db_orf_id": identity["db_orf_id"], "assay_status": status, "evaluable": eligible,
                 "detected": status == "detected" if eligible else None, "construct_match": True,
                 "issues": [], "raw_source_rows": [n], "raw_final_score": "4" if status == "detected" else "0",
                 "confirmation_3at": True if status == "detected" else None,
                 "confirmation_lw": status == "not_detected", "published_result": "Original source label"}
        rows.append({"comparator": comparator, "assay": assay,
                     "comparator_evaluable": eligible and comparator["comparator"] is not None})
        lookups.append(lookup)
    bindings = {"protocol_sha256": "a" * 64, "result_sha256": "b" * 64,
                "source_sha256": {"panel": "c" * 64, "raw": "d" * 64, "orf_map": "e" * 64},
                "artifact_sha256": {"rows": "f" * 64, "lookup": "0" * 64}}
    return rows, lookups, bindings


class AssayEvidenceTests(unittest.TestCase):
    def test_complete_accounting_and_original_source_preservation(self):
        inputs = fixture()
        original = deepcopy(inputs)
        result = build_evidence(*inputs)
        self.assertEqual(inputs, original)
        self.assertEqual(result["summary"]["observations"], 4)
        self.assertEqual(result["summary"]["assay_evaluable"], 3)
        self.assertEqual(result["summary"]["assay_excluded"], 1)
        self.assertEqual(result["summary"]["comparator_evaluable"], 2)
        self.assertEqual(result["summary"]["detected_without_bounded_pharos_match"], 1)
        by_row = {x["source_row"]: x for x in result["observations"]}
        for row, lookup in zip(inputs[0], inputs[1]):
            observation = by_row[row["assay"]["source_row"]]
            self.assertEqual(observation["original"], row)
            self.assertEqual(observation["lookup"], lookup)
        self.assertEqual(result["summary"]["pharos_records_modified"], 0)

    def test_nondetections_are_qualified_observations_and_failures_have_no_edges(self):
        result = build_evidence(*fixture())
        graph = result["graph"]
        self.assertEqual(len(graph["edges"]), 3)
        self.assertEqual({edge["predicate"] for edge in graph["edges"]}, {PREDICATE})
        self.assertEqual({edge["record_kind"] for edge in graph["edges"]}, {"assay_observation"})
        self.assertFalse(any("negative" in edge for edge in graph["edges"]))
        self.assertEqual(sum(edge["qualifiers"]["measurement_qualifier"] == "not_detected" for edge in graph["edges"]), 2)
        excluded = next(o for o in result["observations"] if not o["evaluable"])
        self.assertIsNone(excluded["graph_edge_id"])
        self.assertTrue(set(excluded["products"]) <= {node["id"] for node in graph["nodes"]})
        self.assertTrue(set(excluded["products"]).isdisjoint({edge[k] for edge in graph["edges"] for k in ("subject", "object")}))

    def test_no_automatic_acceptance_or_independence(self):
        result = build_evidence(*fixture())
        for assertion in result["graph"]["assertions"]:
            self.assertEqual(assertion["lifecycle_state"], "candidate")
            self.assertFalse(assertion["biologically_validated"])
            self.assertIsNone(assertion["independent_evidence_count"])
            self.assertEqual(assertion["review_history"], [])
        self.assertEqual(result["summary"]["automatically_accepted_assertions"], 0)
        self.assertIsNone(result["summary"]["independently_validated_new_interactions"])

    def test_construct_roles_and_species_are_not_inferred_from_sorting(self):
        result = build_evidence(*fixture())
        first = next(o for o in result["observations"] if o["source_row"] == 2)
        self.assertEqual(first["constructs"]["ad_orf_id"], "102")
        self.assertEqual(first["constructs"]["db_orf_id"], "202")
        self.assertFalse(first["constructs"]["protein_to_construct_orientation_inferred"])
        self.assertEqual(first["constructs"]["ad_experimental_role"]["id"], "MI:0498")
        self.assertEqual(first["constructs"]["db_experimental_role"]["id"], "MI:0496")
        self.assertEqual(first["detection_method"]["id"], "MI:0018")
        self.assertEqual(first["participant_taxon"], "NCBITaxon:9606")
        self.assertIsNone(first["assay_host_taxon"])
        self.assertEqual(first["assay"], ASSAY)

    def test_source_locators_bind_correct_array_indices_and_exact_file_hashes(self):
        result = build_evidence(*fixture())
        for observation in result["observations"]:
            by_role = {entry["role"]: entry for entry in observation["source_locators"]}
            self.assertEqual(by_role["published_assay_record"]["file_sha256"], "c" * 64)
            self.assertTrue(by_role["published_assay_record"]["locator"].endswith("#row=" + str(observation["source_row"])))
            self.assertEqual(by_role["raw_assay_record"]["file_sha256"], "d" * 64)
            self.assertEqual(by_role["assessed_observation"]["file_sha256"], "f" * 64)
            self.assertEqual(by_role["frozen_pharos_lookup"]["record_sha256"], digest(observation["lookup"]))
            self.assertFalse(by_role["construct_crosswalk"]["row_resolved"])

    def test_observation_identity_survives_input_reordering_but_preserves_roles(self):
        rows, lookups, bindings = fixture()
        first = build_evidence(rows, lookups, bindings)
        second = build_evidence(list(reversed(rows)), list(reversed(lookups)), bindings)
        self.assertEqual([o["id"] for o in first["observations"]], [o["id"] for o in second["observations"]])
        self.assertEqual([e["id"] for e in first["graph"]["edges"]], [e["id"] for e in second["graph"]["edges"]])
        rows[0]["assay"]["ad_orf_id"] = "202"
        rows[0]["assay"]["db_orf_id"] = "102"
        for identity in (rows[0]["comparator"]["identity"], lookups[0]["identity"]):
            identity.update(ad_orf_id="202", db_orf_id="102")
        rows[0]["comparator"]["lookup_record_sha256"] = digest(lookups[0])
        changed = build_evidence(rows, lookups, bindings)
        ids = lambda value: {o["source_row"]: o["id"] for o in value["observations"]}
        self.assertNotEqual(ids(first)[2], ids(changed)[2])

    def test_ordinary_question_does_not_propagate_assay_observations(self):
        graph = build_evidence(*fixture())["graph"]
        graph["scope"] = {"kind": "protein_cohort", "name": "Invented assay fixtures", "resolutions": []}
        graph["targets"] = [{"id": node["id"], "symbol": node["id"], "name": node["id"]} for node in graph["nodes"]]
        graph["normalization"] = {"policy": "local-observations"}
        graph["retrieval"] = {}
        graph["snapshot_created_at"] = "2026-10-25T00:00:00Z"
        answer = answer_question(graph, "P01111", relations=["interactions"], view="candidates")
        self.assertEqual(answer["results"], [])

    def test_changed_lookup_is_rejected(self):
        rows, lookups, bindings = fixture()
        lookups[1]["pharos_matches"]["raw"][0]["record"]["type"] = "Changed"
        with self.assertRaisesRegex(ValueError, "exact frozen lookup"):
            build_evidence(rows, lookups, bindings)

    def test_missing_extra_or_duplicate_inventory_is_rejected(self):
        for mutation in (lambda rows, lookups: rows.pop(),
                         lambda rows, lookups: rows.__setitem__(1, deepcopy(rows[0])),
                         lambda rows, lookups: lookups.__setitem__(1, deepcopy(lookups[0]))):
            with self.subTest(mutation=mutation):
                rows, lookups, bindings = fixture()
                mutation(rows, lookups)
                with self.assertRaises(ValueError):
                    build_evidence(rows, lookups, bindings)

    def test_inconsistent_status_eligibility_and_constructs_are_rejected(self):
        for field, value in (("detected", False), ("evaluable", False), ("construct_match", False),
                             ("ad_orf_id", "different"), ("issues", ["unresolved"]),
                             ("assay_status", "unexpected_state"), ("raw_source_rows", [])):
            with self.subTest(field=field):
                rows, lookups, bindings = fixture()
                rows[0]["assay"][field] = value
                with self.assertRaises(ValueError):
                    build_evidence(rows, lookups, bindings)

    def test_unresolved_comparator_is_never_zero_or_eligible(self):
        for field, value in (("comparator", 0), ("comparator", False)):
            rows, lookups, bindings = fixture()
            rows[-1]["comparator"][field] = value
            with self.assertRaisesRegex(ValueError, "Comparator state"):
                build_evidence(rows, lookups, bindings)
        rows, lookups, bindings = fixture()
        rows[-1]["comparator_evaluable"] = True
        with self.assertRaisesRegex(ValueError, "Comparator state"):
            build_evidence(rows, lookups, bindings)

    def test_bad_hash_bindings_and_invalid_protein_identity_are_rejected(self):
        rows, lookups, bindings = fixture()
        bindings["source_sha256"]["raw"] = "unknown"
        with self.assertRaises(ValueError):
            build_evidence(rows, lookups, bindings)
        rows, lookups, bindings = fixture()
        rows[0]["assay"]["products"] = ["Invented", "P01112"]
        with self.assertRaises(ValueError):
            build_evidence(rows, lookups, bindings)


if __name__ == "__main__":
    unittest.main()
