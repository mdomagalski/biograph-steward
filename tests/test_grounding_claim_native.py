"""Invented source/grounder fixtures test binding, not biological accuracy."""
from copy import deepcopy
from hashlib import sha256
from importlib.util import find_spec
from types import SimpleNamespace
import unittest

from tools.grounding_claims.native import check_grounding, project_evidence


def evidence(texts=None, refs=None):
    return {"source_api": "invented", "pmid": "123", "text": "Invented A activates B.",
            "annotations": {"agents": {
                "raw_text": ["A", "B"] if texts is None else texts,
                "raw_grounding": [{"HGNC": "1"}, {"HGNC": "2"}] if refs is None else refs}},
            "epistemics": {"hypothesis": True}, "context": {"invented": "context"}}


STATEMENT = {"type": "Activation", "subj": {"name": "NOT_THE_SOURCE_MENTION", "db_refs": {"TEXT": "wrong"}},
             "obj_activity": "activity", "belief": 0.8}


def fake_agent(*, name, db_refs):
    # One supplied field per invented agent; actual preference is delegated
    # to INDRA in the optional native test below, not duplicated here.
    grounding = next(((key, val) for key, val in db_refs.items() if key != "TEXT"), (None, None))
    return SimpleNamespace(get_grounding=lambda: grounding)


class Match:
    def __init__(self, groundings, *, disambiguation=None):
        self.groundings = set(groundings)
        self.disambiguation = disambiguation

    def get_groundings(self):
        return self.groundings

    def to_json(self):
        result = {"term": {"db": sorted(self.groundings)[0][0], "id": sorted(self.groundings)[0][1]},
                  "score": 0.7}
        if self.disambiguation is not None:
            result["disambiguation"] = self.disambiguation
        return result


class Grounder:
    def __init__(self, matches, *, models=None):
        self.matches, self.calls = matches, []
        self.gilda_disambiguators = {} if models is None else models
        self.adeft_disambiguators = {}

    def ground(self, text, *, context=None):
        self.calls.append((text, context))
        result = self.matches[text]
        if isinstance(result, Exception):
            raise result
        return result


def projection(source=None):
    return project_evidence(STATEMENT, source or evidence(), agent_factory=fake_agent)


class GroundingNativeAdapterTests(unittest.TestCase):
    def test_projection_uses_evidence_mentions_and_preserves_qualifiers_and_none(self):
        source = evidence([None, "source alias"], [None, {"HGNC": "10", "TEXT": "source alias"}])
        original = deepcopy(source)
        case = projection(source)
        self.assertEqual(case["status"], "ready")
        self.assertEqual(case["agents"][0]["status"], "neutral")
        self.assertEqual(case["agents"][1]["mention"], "source alias")
        self.assertEqual(case["agents"][1]["assigned"], {"namespace": "HGNC", "id": "10"})
        self.assertEqual(case["original_qualifiers"]["epistemics"], {"hypothesis": True})
        self.assertNotIn("belief", case["original_qualifiers"]["assembled_statement_attributes_as_supplied"])
        self.assertEqual(source, original)
        self.assertEqual(case["assigned_entity_resolver"], "injected_test_agent_factory")

    def test_numeric_primary_pmid_survives_reader_internal_secondary_identifier(self):
        source = evidence()
        source["pmid"] = "12345"
        source["text_refs"] = {"PMID": "TEXT-reader-internal", "PMCID": "PMC123"}
        original = deepcopy(source)
        case = projection(source)
        self.assertEqual(case["pmid"], "12345")
        self.assertIn("malformed_native_text_refs_PMID", case["warnings"])
        self.assertNotIn("conflicting_native_PMID_fields", case["warnings"])
        self.assertEqual(case["original_qualifiers"]["pmid"], "12345")
        self.assertEqual(case["original_qualifiers"]["text_refs"], original["text_refs"])
        self.assertEqual(source, original)

    def test_conflicting_valid_pmids_are_unresolved_and_original_values_preserved(self):
        source = evidence()
        source["pmid"] = 12345
        source["text_refs"] = {"PMID": "67890"}
        case = projection(source)
        self.assertIsNone(case["pmid"])
        self.assertIn("conflicting_native_PMID_fields", case["warnings"])
        self.assertEqual(case["original_qualifiers"]["pmid"], 12345)
        self.assertEqual(case["original_qualifiers"]["text_refs"]["PMID"], "67890")

    def test_malformed_pmids_are_not_coerced_and_each_field_is_reported(self):
        for direct, secondary in [(True, 123.0), ("PMC123", "TEXT123"),
                                  ("", "0"), (-123, "00123"), ("１２３", " 123 ")]:
            with self.subTest(direct=direct, secondary=secondary):
                source = evidence()
                source["pmid"], source["text_refs"] = direct, {"PMID": secondary}
                original = deepcopy(source)
                case = projection(source)
                self.assertIsNone(case["pmid"])
                self.assertIn("malformed_native_evidence_pmid", case["warnings"])
                self.assertIn("malformed_native_text_refs_PMID", case["warnings"])
                self.assertEqual(source, original)

    def test_valid_secondary_pmid_is_used_only_as_the_unique_numeric_identifier(self):
        source = evidence()
        source.pop("pmid")
        source["text_refs"] = {"PMID": "12345"}
        self.assertEqual(projection(source)["pmid"], "12345")
        source["pmid"] = "TEXT-reader-internal"
        case = projection(source)
        self.assertEqual(case["pmid"], "12345")
        self.assertIn("malformed_native_evidence_pmid", case["warnings"])
        source["pmid"] = 12345
        case = projection(source)
        self.assertEqual(case["pmid"], "12345")
        self.assertNotIn("conflicting_native_PMID_fields", case["warnings"])

    def test_missing_or_misaligned_arrays_never_fall_back_to_statement(self):
        for source in [{"text": "text"}, evidence(["A"], [{"HGNC": "1"}, {"HGNC": "2"}])]:
            case = projection(source)
            self.assertEqual(case["status"], "unresolved")
            g = Grounder({})
            prediction = check_grounding(case, g, use_context=True)
            self.assertEqual(prediction["status"], "unresolved")
            self.assertIsNone(prediction["candidate_conflict"])
            self.assertEqual(g.calls, [])

    def test_context_is_exact_evidence_text_and_source_is_unchanged(self):
        case = projection(); original = deepcopy(case)
        g = Grounder({"A": [Match({("HGNC", "1")})], "B": [Match({("HGNC", "2")})]})
        result = check_grounding(case, g, use_context=True)
        self.assertEqual(result["status"], "no_conflict")
        self.assertFalse(result["candidate_conflict"])
        self.assertEqual(g.calls, [("A", case["text"]), ("B", case["text"])])
        self.assertEqual(case, original)
        self.assertEqual(result["input_sha256"], case["input_sha256"])

    def test_no_context_arm_does_not_receive_citation_or_evidence_text(self):
        g = Grounder({"A": [Match({("HGNC", "1")})], "B": [Match({("HGNC", "2")})]})
        result = check_grounding(projection(), g, use_context=False)
        self.assertEqual(result["status"], "no_conflict")
        self.assertEqual(g.calls, [("A", None), ("B", None)])
        self.assertEqual(result["context_kind"], "none")
        self.assertIsNone(result["context_sha256"])

    def test_explicit_publication_context_is_bound_and_does_not_replace_evidence(self):
        case = projection(); original = deepcopy(case)
        citation = "Invented title.\n\nInvented publication abstract."
        g = Grounder({"A": [Match({("HGNC", "1")})], "B": [Match({("HGNC", "2")})]})
        result = check_grounding(case, g, use_context=True, context_text=citation)
        self.assertEqual(result["context_kind"], "provided_context_text")
        self.assertEqual(result["context_sha256"], sha256(citation.encode("utf-8")).hexdigest())
        self.assertEqual(g.calls, [("A", citation), ("B", citation)])
        self.assertEqual(case, original)
        with self.assertRaisesRegex(ValueError, "no-context"):
            check_grounding(case, g, use_context=False, context_text=citation)
        with self.assertRaises(ValueError):
            check_grounding(case, g, use_context=True, context_text="")

    def test_native_mapped_grounding_prevents_namespace_only_false_conflict(self):
        case = projection(evidence(["A"], [{"UP": "P00001"}]))
        result = check_grounding(case, Grounder({"A": [Match({("HGNC", "1"), ("UP", "P00001")})]}), use_context=False)
        self.assertEqual(result["status"], "no_conflict")

    def test_family_specific_gene_difference_is_unresolved_but_same_namespace_conflict_flags(self):
        case = projection(evidence(["VEGF"], [{"HGNC": "12680"}]))
        family = check_grounding(case, Grounder({"VEGF": [Match({("FPLX", "VEGF")})]}), use_context=False)
        self.assertEqual(family["status"], "unresolved")
        self.assertIsNone(family["candidate_conflict"])
        self.assertEqual(family["agents"][0]["status"], "unresolved_namespace_or_granularity")
        other_gene = check_grounding(case, Grounder({"VEGF": [Match({("HGNC", "999")})]}), use_context=False)
        self.assertEqual(other_gene["status"], "candidate_conflict")
        self.assertTrue(other_gene["candidate_conflict"])

    def test_unresolved_part_does_not_produce_no_conflict_but_known_conflict_survives(self):
        case = projection(evidence(["A", "B"], [{"HGNC": "1"}, {}]))
        self.assertEqual(case["status"], "partial")
        same = check_grounding(case, Grounder({"A": [Match({("HGNC", "1")})]}), use_context=False)
        self.assertEqual(same["status"], "unresolved")
        self.assertIsNone(same["candidate_conflict"])
        different = check_grounding(case, Grounder({"A": [Match({("HGNC", "3")})]}), use_context=False)
        self.assertEqual(different["status"], "candidate_conflict")
        self.assertTrue(different["candidate_conflict"])

    def test_no_match_and_missing_source_text_are_unresolved(self):
        result = check_grounding(projection(evidence(["A"], [{"HGNC": "1"}])), Grounder({"A": []}), use_context=False)
        self.assertEqual(result["status"], "unresolved")
        source = evidence(); source["text"] = ""
        case = projection(source);g = Grounder({})
        self.assertEqual(check_grounding(case, g, use_context=False)["status"], "unresolved")
        self.assertEqual(g.calls, [])

    def test_present_source_text_corroboration_conflict_is_not_silently_repaired(self):
        source = evidence(["A"], [{"TEXT": "different original mention", "HGNC": "1"}])
        case = projection(source)
        result = check_grounding(case, Grounder({}), use_context=False)
        self.assertEqual(result["status"], "unresolved")
        self.assertIn("source_agent_text_and_grounding_annotation_differ", result["agents"][0]["reasons"])
        self.assertIn("no_source_agent_with_assigned_grounding", result["reasons"])

    def test_isoform_mismatch_is_unresolved_and_never_canonicalized(self):
        case = projection(evidence(["A"], [{"UP": "P00001-2"}]))
        result = check_grounding(case, Grounder({"A": [Match({("UP", "P00001"), ("HGNC", "1")})]}), use_context=False)
        self.assertEqual(result["agents"][0]["status"], "unresolved_form")
        self.assertEqual(result["status"], "unresolved")
        exact = check_grounding(case, Grounder({"A": [Match({("UP", "P00001-2")})]}), use_context=False)
        self.assertEqual(exact["status"], "no_conflict")

    def test_model_exception_and_unapplied_available_model_are_technical(self):
        case = projection(evidence(["A"], [{"HGNC": "1"}]))
        failed = check_grounding(case, Grounder({"A": RuntimeError("failure")}), use_context=True)
        self.assertEqual(failed["status"], "model_error")
        self.assertIsNone(failed["candidate_conflict"])
        fallback = check_grounding(case, Grounder({"A": [Match({("HGNC", "1")})]}, models={"A": object()}), use_context=True)
        self.assertEqual(fallback["status"], "model_error")
        applied = check_grounding(case, Grounder({"A": [Match({("HGNC", "1")}, disambiguation={"type": "gilda", "score": 0.5})]}, models={"A": object()}), use_context=True)
        self.assertEqual(applied["status"], "no_conflict")
        self.assertEqual(applied["disambiguation_applied_agents"], 1)

    def test_model_availability_matches_native_outer_whitespace_normalization(self):
        case = projection(evidence([" A "], [{"HGNC": "1"}]))
        grounder = Grounder({" A ": [Match({("HGNC", "1")}, disambiguation={"type": "gilda", "score": 0.5})]}, models={"A": object()})
        result = check_grounding(case, grounder, use_context=True)
        self.assertEqual(result["native_model_available_agents"], 1)
        self.assertEqual(result["agents"][0]["mention"], " A ")
        self.assertEqual(grounder.calls, [(" A ", case["text"])])
        missing = Grounder({" A ": [Match({("HGNC", "1")})]}, models={"A": object()})
        self.assertEqual(check_grounding(case, missing, use_context=True)["status"], "model_error")

    def test_projection_changes_and_nonboolean_arm_fail_closed(self):
        case = projection();case["agents"][0]["assigned"]["id"] = "99"
        with self.assertRaisesRegex(ValueError, "seal"):
            check_grounding(case, Grounder({}), use_context=False)
        with self.assertRaises(ValueError):
            check_grounding(projection(), Grounder({}), use_context="false")

    @unittest.skipUnless(find_spec("indra") is not None, "optional INDRA runtime")
    def test_actual_native_agent_namespace_preference(self):
        source = evidence(["A"], [{"TEXT": "A", "HGNC": "1", "UP": "P00001"}])
        case = project_evidence(STATEMENT, source)
        self.assertEqual(case["agents"][0]["assigned"], {"namespace": "HGNC", "id": "1"})
        self.assertEqual(case["assigned_entity_resolver"], "indra.statements.Agent.get_grounding")


if __name__ == "__main__":
    unittest.main()
