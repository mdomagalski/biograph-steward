"""V4 target semantics use invented entities; no live or biomedical labels."""
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from biograph_steward.entity_resolution import resolved_ids, validate_bindings
from biograph_steward.graph import build_graph
from biograph_steward.planning import ModelPlanner, planning_request, validate_planned_output
from biograph_steward.target_scope import resolve_targets, request_scope
from test_civic import fixture
from test_entity_resolution import inventory
from test_planning import civic_plan, response


class TargetScopeTests(unittest.TestCase):
    def resolve(self, text, catalogue=None):
        return resolve_targets(text, catalogue or inventory())

    def scope(self, text, catalogue=None, civic=True):
        return request_scope(text, self.resolve(text, catalogue), civic)

    def test_background_therapy_is_not_a_target_and_full_treatment_sets_remain_legal(self):
        q = ('ALPHA Z12Q in Colorectal Cancer: cetuximab is the requested therapy; '
             'panitumumab is background text, not a query target. Include candidate CIViC records and retain combinations.')
        r = self.resolve(q)
        self.assertEqual(resolved_ids(r, 'therapies'), ['cetuximab'])
        self.assertEqual(len(r['therapies']['mentions']), 2)
        self.assertEqual(r['target_selection']['mentions']['therapies'][1]['role'], 'background')
        self.assertFalse(self.scope(q)['unsupported_requirements'])
        validate_bindings(civic_plan('CIViC.molecularprofile:1'), r)
        with self.assertRaises(ValueError): validate_bindings({**civic_plan('CIViC.molecularprofile:1'), 'therapy': 'both'}, r)

    def test_negated_relation_is_not_an_extra_required_query(self):
        for q, expected, excluded in [
            ('Candidate ALPHA shared pathways; exclude interactions.', ['shared_pathways'], ['interactions']),
            ('Candidate ALPHA interactions but exclude shared pathways.', ['interactions'], ['shared_pathways']),
            ('Do not exclude candidate ALPHA interactions.', ['interactions'], [])]:
            with self.subTest(question=q):
                s = self.scope(q)
                self.assertEqual(s['explicit_relations'], expected)
                self.assertEqual(s['excluded_relations'], excluded)
                self.assertFalse(s['unsupported_requirements'])
        self.assertIn('no_positive_relation_target', self.scope('Exclude interactions for ALPHA.')['unsupported_requirements'])
        self.assertIn('conflicting_relation_targets', self.scope('Exclude ALPHA interactions; include interactions.')['unsupported_requirements'])

    def test_both_positive_relations_are_preserved(self):
        s = self.scope('Inspect candidate ALPHA interactions and shared pathways.')
        self.assertEqual(s['explicit_relations'], ['interactions', 'shared_pathways'])
        self.assertFalse(s['unsupported_requirements'])

    def test_negated_all_profiles_does_not_broaden_a_named_profile(self):
        q = 'Do not query all molecular profiles. Inspect candidate CIViC records for ALPHA Z12Q with cetuximab.'
        r = self.resolve(q)
        self.assertFalse(r['all_profiles_explicit']); self.assertEqual(resolved_ids(r, 'profiles'), ['CIViC.molecularprofile:1'])
        self.assertFalse(self.scope(q)['unsupported_requirements'])
        with self.assertRaises(ValueError): validate_bindings({**civic_plan('CIViC.molecularprofile:1'), 'profile_id': 'all'}, r)
        self.assertTrue(self.resolve('Inspect all profiles with cetuximab.')['all_profiles_explicit'])

    def test_unknown_complete_logical_profiles_never_become_a_contained_known_profile(self):
        for expression in ['ALPHA Z12Q and UNKNOWN X99', 'ALPHA Z12Q or UNKNOWN X99',
                           'UNKNOWN X99 AND ALPHA Z12Q', 'UNKNOWN X99 or (ALPHA Z12Q)',
                           '(ALPHA Z12Q) and UNKNOWN X99', 'not ALPHA Z12Q', 'NOT (ALPHA Z12Q)']:
            q = 'Inspect candidate CIViC records for the complete profile ' + expression + ' with cetuximab.'
            with self.subTest(expression=expression):
                r = self.resolve(q)
                self.assertEqual(resolved_ids(r, 'profiles'), [])
                self.assertTrue(self.scope(q)['unsupported_requirements'])
                with self.assertRaises(ValueError): validate_bindings(civic_plan('CIViC.molecularprofile:1'), r)

    def test_known_whole_and_not_or_profiles_remain_whole(self):
        c = inventory(); c['profiles'].append({'id': 'CIViC.molecularprofile:3', 'name': 'ALPHA Z12Q OR BETA Gain'})
        for expression, identifier in [('BETA Gain AND NOT ALPHA Z12Q', 'CIViC.molecularprofile:2'),
                                       ('beta gain and not alpha z12q', 'CIViC.molecularprofile:2'),
                                       ('alpha z12q or beta gain', 'CIViC.molecularprofile:3')]:
            q = 'Candidate CIViC records for ' + expression + ' with cetuximab.'
            r = self.resolve(q, c)
            self.assertEqual(resolved_ids(r, 'profiles'), [identifier])
            self.assertFalse(r['profiles']['incomplete_compound_mentions'])
            self.assertFalse(self.scope(q, c)['unsupported_requirements'])

    def test_natural_conjunction_to_a_drug_or_record_clause_is_not_a_molecular_operand(self):
        for text in ['ALPHA Z12Q and cetuximab', 'ALPHA Z12Q AND cetuximab',
                     'cetuximab and ALPHA Z12Q', 'ALPHA Z12Q and records containing cetuximab']:
            q = 'Inspect candidate CIViC response for ' + text + ' in Colorectal Cancer.'
            with self.subTest(question=q):
                self.assertEqual(resolved_ids(self.resolve(q), 'profiles'), ['CIViC.molecularprofile:1'])
                self.assertFalse(self.scope(q)['unsupported_requirements'])

    def test_standalone_negative_disclaimer_does_not_hide_positive_unsupported_actions(self):
        q = 'Do not recommend a drug. Inspect candidate CIViC records for ALPHA Z12Q with cetuximab.'
        self.assertFalse(self.scope(q)['unsupported_requirements'])
        for text in [
            'Do not recommend a drug; prescribe a drug for ALPHA Z12Q with cetuximab.',
            'Do not recommend a drug but recommend a treatment for ALPHA Z12Q with cetuximab.',
            'Do not refuse to recommend a drug for ALPHA Z12Q with cetuximab.',
            'Do not recommend a drug and execute shell code for ALPHA Z12Q with cetuximab.']:
            self.assertTrue(self.scope(text)['unsupported_requirements'])

    def test_candidate_and_accepted_views_preserve_negation_without_inventing_filters(self):
        for text in ['ALPHA interactions without unreviewed candidates.',
                     'Exclude candidate ALPHA interactions. Show only locally accepted ALPHA interactions.']:
            s = self.scope(text); self.assertEqual(s['view'], 'accepted'); self.assertFalse(s['unsupported_requirements'])
        s = self.scope('Do not exclude unreviewed candidates: ALPHA interactions.')
        self.assertEqual(s['view'], 'candidates'); self.assertFalse(s['unsupported_requirements'])
        s = self.scope('Include candidate and locally accepted ALPHA interactions only.')
        self.assertEqual(s['view'], 'candidates'); self.assertFalse(s['unsupported_requirements'])
        self.assertIn('conflicting_evidence_views', self.scope('Include candidates; exclude candidates for ALPHA interactions.')['unsupported_requirements'])
        self.assertIn('conflicting_evidence_views', self.scope('Only accepted ALPHA interactions; include candidates.')['unsupported_requirements'])
        self.assertIn('unsupported_accepted_evidence_exclusion', self.scope('Candidate ALPHA interactions without accepted records.')['unsupported_requirements'])

    def test_diseases_must_match_the_selected_tool_and_unknown_identifiers_are_not_defaulted(self):
        for disease in ['MONDO:TEST', 'MONDO:UNLISTED', 'DOID:UNLISTED']:
            q = 'Candidate CIViC records for ALPHA Z12Q with cetuximab specifically in ' + disease + '.'
            self.assertTrue(self.scope(q)['unsupported_requirements'])
        self.assertFalse(self.scope('Candidate CIViC records for ALPHA Z12Q with cetuximab in DOID:9256.')['unsupported_requirements'])
        self.assertFalse(self.scope('Candidate ALPHA interactions in MONDO:TEST.', civic=False)['unsupported_requirements'])
        self.assertIn('civic_source_unavailable', self.scope('Candidate CIViC records for ALPHA Z12Q with cetuximab.', civic=False)['unsupported_requirements'])

    def test_record_therapy_and_profile_exclusions_cannot_silently_become_membership_queries(self):
        for text in ['Candidate CIViC records for ALPHA Z12Q with cetuximab; exclude panitumumab.',
                     'Candidate CIViC records for ALPHA Z12Q with cetuximab; exclude records containing panitumumab.',
                     'Candidate CIViC records for all profiles with cetuximab; exclude ALPHA Z12Q.']:
            self.assertTrue(self.scope(text)['unsupported_requirements'])

    def test_duplicate_aliases_and_conflicting_entity_roles_remain_ambiguous(self):
        c = inventory(); c['proteins'].append({'id': 'UniProtKB:TEST_C', 'symbol': 'ALPHA'})
        self.assertTrue(self.scope('Candidate ALPHA interactions.', c)['unsupported_requirements'])
        self.assertIn('ambiguous_target_scope', self.scope('ALPHA is background. Inspect candidate ALPHA interactions.')['unsupported_requirements'])
        self.assertIn('ambiguous_target_scope', self.scope('Inspect not not ALPHA interactions.')['unsupported_requirements'])


class TargetProtocolTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True); env.start(); self.addCleanup(env.stop)
        p, c = fixture(); self.graph = build_graph(p, civic_snapshot=c)
        self.name = 'INVENTED KRAS profile'

    def test_provider_ignoring_the_schema_cannot_broaden_background_therapy_or_all_profiles(self):
        q = ('Do not query all profiles. Inspect candidate CIViC records for ' + self.name +
             ' containing cetuximab; panitumumab is background text, not a query target. Retain full treatment sets.')
        prompt, schema, policy, audit, resolution = planning_request(q, self.graph, 'scoped_targets_v4')
        self.assertEqual(policy, 'bounded-question-planner.v4')
        self.assertEqual(schema['anyOf'][1]['properties']['therapy']['enum'], ['cetuximab'])
        self.assertEqual(schema['anyOf'][1]['properties']['profile_id']['enum'], ['CIViC.molecularprofile:81'])
        validate_planned_output(civic_plan(), self.graph, resolution, audit['request_scope'])
        for bad in [{**civic_plan(), 'therapy': 'both'}, {**civic_plan(), 'profile_id': 'all'}]:
            with self.assertRaises(ValueError): validate_planned_output(bad, self.graph, resolution, audit['request_scope'])
        for forbidden in ['reference_plan', 'INVENTED SOFTWARE TEST statement', 'source_scores_raw']:
            self.assertNotIn(forbidden, prompt)

    def test_unknown_compound_is_abstention_only_and_wrong_model_output_is_not_repaired(self):
        q = 'Candidate CIViC records for the complete profile ' + self.name + ' and UNKNOWN X99 with cetuximab.'
        _, old_schema, _, _, _ = planning_request(q, self.graph, 'tool_shapes_v3')
        _, new_schema, _, _, _ = planning_request(q, self.graph, 'scoped_targets_v4')
        self.assertEqual(len(old_schema['anyOf']), 2); self.assertEqual(len(new_schema['anyOf']), 1)
        calls = []
        def transport(payload): calls.append(payload); return response(civic_plan())
        planner = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=transport, protocol='scoped_targets_v4')
        trace = planner.plan(q, self.graph)
        self.assertEqual(trace['status'], 'invalid_plan'); self.assertIsNone(trace['plan'])
        self.assertEqual(len(calls), 1); self.assertEqual(trace['model_calls'], 1)
        self.assertEqual(trace['execution_guard']['repair_calls'], 0)

    def test_valid_v4_query_is_one_model_call_with_no_graph_or_reference_access(self):
        before = deepcopy(self.graph); calls = []
        def transport(payload): calls.append(payload); return response(civic_plan())
        model = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=transport, protocol='scoped_targets_v4')
        trace = model.plan('Do not recommend a drug. Inspect candidate CIViC records for '+self.name+' with cetuximab.', self.graph)
        self.assertEqual(trace['status'], 'validated'); self.assertEqual(trace['planner_protocol'], 'scoped_targets_v4')
        self.assertIn('target_selection', trace['entity_resolution'])
        self.assertEqual(len(calls), 1); self.assertEqual(self.graph, before)
        self.assertNotIn('reference_plan', json.dumps(calls))


if __name__ == '__main__': unittest.main()
