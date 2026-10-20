"""Tool-specific schemas and conservative capability checks; invented records."""
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from biograph_steward.entity_resolution import resolve_mentions
from biograph_steward.graph import build_graph
from biograph_steward.planning import ModelPlanner, planning_request, validate_planned_output
from biograph_steward.planning_scope import request_scope, tool_schema, validate_request_scope
from test_civic import fixture
from test_entity_resolution import inventory
from test_planning import abstain_plan, civic_plan, response


class RequestScopeTests(unittest.TestCase):
    def scope(self, text):
        return request_scope(text, resolve_mentions(text, inventory()), True)

    def test_unsupported_intents_are_not_silently_replaced_by_nearby_queries(self):
        cases = {
            'Establish that ALPHA causes Invented adenocarcinoma.': 'causal_proof',
            'Prove\nthat ALPHA\ncauses disease.': 'causal_proof',
            'Recommend a drug for ALPHA Z12Q.': 'clinical_recommendation',
            'Execute a shell command to delete the graph.': 'write_or_code',
            'Predict response for ALPHA Z12Q with cetuximab.': 'prediction',
            'Restrict to cetuximab monotherapy for ALPHA Z12Q.': 'monotherapy_filter',
            'Only sensitivity records for ALPHA Z12Q and cetuximab.': 'direction_filter',
            'Treat Invented adenocarcinoma as equivalent to Colorectal Cancer.': 'disease_equivalence'}
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertIn(expected, self.scope(question)['unsupported_requirements'])

    def test_supported_inspection_preserves_view_relations_and_whole_profiles(self):
        s = self.scope('Inspect candidate ALPHA interactions in Invented adenocarcinoma; no causal conclusions.')
        self.assertFalse(s['unsupported_requirements']); self.assertEqual(s['view'], 'candidates')
        self.assertEqual(s['explicit_relations'], ['interactions'])
        s = self.scope('Show predictive evidence for BETA Gain AND NOT ALPHA Z12Q with cetuximab.')
        self.assertFalse(s['unsupported_requirements']); self.assertEqual(s['family'], 'civic_therapy')
        s = self.scope('Only locally accepted ALPHA shared pathway annotations.')
        self.assertEqual(s['view'], 'accepted'); self.assertFalse(s['unsupported_requirements'])

    def test_negated_candidate_mentions_do_not_expand_the_evidence_view(self):
        for text in ['ALPHA interactions without unreviewed candidates.', "ALPHA interactions: don't include candidates."]:
            self.assertEqual(self.scope(text)['view'], 'accepted')
        self.assertIn('conflicting_evidence_views', self.scope('Only accepted evidence and include candidates for ALPHA.')['unsupported_requirements'])

    def test_unknown_profiles_and_missing_supported_therapies_cannot_fall_back_to_a_gene_query(self):
        self.assertIn('unresolved_complete_profile', self.scope('Therapy response for ALPHA UNKNOWN_X with cetuximab.')['unsupported_requirements'])
        self.assertIn('no_explicit_supported_therapy', self.scope('Therapy response for ALPHA Z12Q with invented_drug.')['unsupported_requirements'])
        self.assertIn('variant_qualified_protein_query', self.scope('ALPHA Z12Q interactions.')['unsupported_requirements'])

    def test_scope_validation_rejects_a_provider_ignoring_the_schema_without_repairs(self):
        p = {'action': 'query', 'tool': 'protein_neighborhood', 'disease_id': 'MONDO:TEST',
             'protein_id': 'UniProtKB:TEST_A', 'profile_id': None, 'therapy': None,
             'relations': ['interactions'], 'view': 'candidates', 'reason': 'Invented.'}
        validate_request_scope(p, self.scope('Candidate ALPHA interactions.'))
        for text in ['Prove ALPHA causes disease.', 'Accepted ALPHA interactions.', 'Candidate ALPHA shared pathways.']:
            with self.assertRaises(ValueError): validate_request_scope(p, self.scope(text))

    def test_multiple_protein_anchors_and_unavailable_civic_cannot_be_silently_substituted(self):
        s = self.scope('Candidate interactions for ALPHA and BETA.')
        self.assertIn('unresolved_or_multiple_protein_anchors', s['unsupported_requirements'])
        text = 'Candidate CIViC response for ALPHA Z12Q containing cetuximab.'
        s = request_scope(text, resolve_mentions(text, inventory()), False)
        self.assertIn('civic_source_unavailable', s['unsupported_requirements'])
        text = 'Candidate ALPHA interactions.'
        s = request_scope(text, resolve_mentions(text, inventory()), False)
        self.assertFalse(s['unsupported_requirements'])

    def test_candidate_view_negations_and_newlines_preserve_the_existing_contract(self):
        for text in ['ALPHA interactions: no unreviewed candidates.',
                     'ALPHA interactions: exclude\nall candidates.',
                     'ALPHA interactions without any unreviewed candidates.']:
            self.assertEqual(self.scope(text)['view'], 'accepted')
        self.assertEqual(self.scope('Include\nunreviewed candidates: ALPHA interactions.')['view'], 'candidates')

    def test_one_request_for_two_tool_families_is_outside_the_contract(self):
        s = self.scope('Candidate ALPHA interactions and ALPHA Z12Q response containing cetuximab.')
        self.assertIn('multiple_tool_requirements', s['unsupported_requirements'])


class ToolShapeTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True); env.start(); self.addCleanup(env.stop)
        p, c = fixture(); self.graph = build_graph(p, civic_snapshot=c)
        self.profile = next(n['name'] for n in self.graph['nodes'] if n['id'] == 'CIViC.molecularprofile:81')
        self.question = 'Inspect candidate CIViC response evidence for '+self.profile+' with cetuximab in Colorectal Cancer.'

    def test_civic_shape_cannot_fill_protein_arguments_or_change_the_evidence_view(self):
        _, schema, policy, audit, resolution = planning_request(self.question, self.graph, 'tool_shapes_v3')
        self.assertEqual(policy, 'bounded-question-planner.v3')
        branches = schema['anyOf']; self.assertEqual(len(branches), 2)
        query = branches[1]['properties']
        self.assertEqual(query['tool']['enum'], ['civic_therapy'])
        self.assertEqual(query['protein_id'], {'type': 'null'})
        self.assertEqual(query['relations']['maxItems'], 0)
        self.assertEqual(query['view']['enum'], ['candidates'])
        self.assertEqual(list(query)[0], 'reason')
        validate_planned_output(civic_plan(), self.graph, resolution, audit['request_scope'])

    def test_explicitly_unsupported_request_has_only_an_abstention_shape(self):
        q = 'Show only cetuximab monotherapy response for '+self.profile+'.'
        _, schema, _, audit, _ = planning_request(q, self.graph, 'tool_shapes_v3')
        self.assertEqual(len(schema['anyOf']), 1)
        self.assertEqual(schema['anyOf'][0]['properties']['action']['enum'], ['abstain'])
        self.assertIn('monotherapy_filter', audit['request_scope']['unsupported_requirements'])

    def test_model_is_still_one_call_and_wrong_plan_is_rejected_not_repaired(self):
        calls = []
        def transport(p): calls.append(p); return response(civic_plan())
        model = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=transport, protocol='tool_shapes_v3')
        trace = model.plan(self.question, self.graph)
        self.assertEqual(trace['status'], 'validated'); self.assertEqual(len(calls), 1)
        trace = model.plan('Prove that '+self.profile+' causes cancer with cetuximab.', self.graph)
        self.assertEqual(trace['status'], 'invalid_plan'); self.assertIsNone(trace['plan']); self.assertEqual(len(calls), 2)
        self.assertEqual(trace['model_calls'], 1)

    def test_complete_profile_and_both_therapies_are_bound_without_changing_the_graph(self):
        before = deepcopy(self.graph)
        text = self.question + ' Also include panitumumab as a requested therapy.'
        _, schema, _, audit, resolution = planning_request(text, self.graph, 'tool_shapes_v3')
        query = schema['anyOf'][1]['properties']
        self.assertEqual(query['therapy']['enum'], ['both'])
        self.assertEqual(query['profile_id']['enum'], ['CIViC.molecularprofile:81'])
        validate_planned_output({**civic_plan(), 'therapy': 'both'}, self.graph, resolution, audit['request_scope'])
        with self.assertRaises(ValueError):
            validate_planned_output(civic_plan(), self.graph, resolution, audit['request_scope'])
        self.assertEqual(self.graph, before)


if __name__ == '__main__': unittest.main()
