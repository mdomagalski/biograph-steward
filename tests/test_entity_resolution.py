"""Entity binding and tool contracts use only invented catalogues and questions."""
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from biograph_steward.entity_resolution import resolve_mentions, resolved_ids, validate_bindings
from biograph_steward.graph import build_graph
from biograph_steward.planning import (ModelPlanner, PlannerUnavailable, catalogue, planning_request,
                                      tool_contracts, validate_planned_output)
from test_civic import fixture
from test_planning import civic_plan, response


def inventory():
    return {'pharos_disease': {'id': 'MONDO:TEST', 'name': 'Invented adenocarcinoma'},
            'civic_disease': {'id': 'DOID:9256', 'name': 'Colorectal Cancer'},
            'proteins': [{'id': 'UniProtKB:TEST_A', 'symbol': 'ALPHA'}, {'id': 'UniProtKB:TEST_B', 'symbol': 'BETA'}],
            'profiles': [{'id': 'CIViC.molecularprofile:1', 'name': 'ALPHA Z12Q'},
                         {'id': 'CIViC.molecularprofile:2', 'name': 'BETA Gain AND NOT ALPHA Z12Q'}]}


class EntityResolutionTests(unittest.TestCase):
    def test_exact_symbol_ids_case_and_whitespace_bind_without_fuzzy_aliases(self):
        c = inventory()
        for question in ['Neighbors of alpha in Invented adenocarcinoma.', 'Neighbors of UniProtKB:TEST_A.']:
            r = resolve_mentions(question, c)
            self.assertEqual(resolved_ids(r, 'proteins'), ['UniProtKB:TEST_A'])
        r = resolve_mentions('Candidate ALPHA   Z12Q with CETUXIMAB in Colorectal Cancer.', c)
        self.assertEqual(resolved_ids(r, 'profiles'), ['CIViC.molecularprofile:1'])
        self.assertEqual(resolved_ids(r, 'therapies'), ['cetuximab'])
        self.assertEqual(resolved_ids(r, 'diseases'), ['DOID:9256'])
        for text in ['ALPHAX', 'ALPHA_extra', 'UniProtKB:TEST_A2', 'ALPH', 'aⅼpha']:
            self.assertEqual(resolved_ids(resolve_mentions(text, c), 'proteins'), [])

    def test_complete_longest_profile_preserves_negation_and_never_splits_an_unknown_compound(self):
        c = inventory()
        r = resolve_mentions('BETA Gain AND NOT ALPHA Z12Q with cetuximab.', c)
        self.assertEqual(resolved_ids(r, 'profiles'), ['CIViC.molecularprofile:2'])
        self.assertFalse(r['profiles']['incomplete_compound_mentions'])
        for text in ['ALPHA Z12Q AND UNKNOWN X99', 'NOT ALPHA Z12Q', 'UNKNOWN X99 OR ALPHA Z12Q']:
            r = resolve_mentions(text, c)
            self.assertEqual(resolved_ids(r, 'profiles'), [])
            self.assertTrue(r['profiles']['incomplete_compound_mentions'])
        self.assertEqual(resolved_ids(resolve_mentions('ALPHA alone.', c), 'profiles'), [])

    def test_duplicate_labels_remain_ambiguous_and_diseases_are_not_merged(self):
        c = inventory(); c['proteins'].append({'id': 'UniProtKB:TEST_C', 'symbol': 'ALPHA'})
        r = resolve_mentions('ALPHA in Invented adenocarcinoma and Colorectal Cancer.', c)
        self.assertEqual(resolved_ids(r, 'proteins'), [])
        self.assertEqual(len(r['proteins']['ambiguous_mentions']), 1)
        self.assertEqual(resolved_ids(r, 'diseases'), ['DOID:9256', 'MONDO:TEST'])
        self.assertEqual(resolved_ids(resolve_mentions('UniProtKB:TEST_C', c), 'proteins'), ['UniProtKB:TEST_C'])

    def test_all_profiles_and_therapy_scope_cannot_be_silently_broadened(self):
        c = inventory()
        r = resolve_mentions('All records for ALPHA Z12Q containing cetuximab.', c)
        self.assertFalse(r['all_profiles_explicit'])
        p = civic_plan('CIViC.molecularprofile:1')
        validate_bindings(p, r)
        for field, value in [('profile_id', 'all'), ('profile_id', 'CIViC.molecularprofile:2'), ('therapy', 'both')]:
            bad = {**p, field: value}
            with self.assertRaises(ValueError): validate_bindings(bad, r)
        r = resolve_mentions('All molecular profiles in Colorectal Cancer with cetuximab and panitumumab.', c)
        validate_bindings({**p, 'profile_id': 'all', 'therapy': 'both'}, r)
        with self.assertRaises(ValueError): validate_bindings(p, r)

    def test_binding_does_not_allow_unmentioned_known_entities_or_disease_equivalence(self):
        c = inventory()
        p = {'action': 'query', 'tool': 'protein_neighborhood', 'disease_id': 'MONDO:TEST',
             'protein_id': 'UniProtKB:TEST_A', 'profile_id': None, 'therapy': None,
             'relations': ['interactions'], 'view': 'candidates', 'reason': 'Invented.'}
        validate_bindings(p, resolve_mentions('ALPHA interactions in Invented adenocarcinoma.', c))
        for question in ['BETA interactions.', 'UNKNOWN interactions.', 'ALPHA in Colorectal Cancer.']:
            with self.assertRaises(ValueError): validate_bindings(p, resolve_mentions(question, c))


class ToolContractTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True); env.start(); self.addCleanup(env.stop)
        p, c = fixture(); self.graph = build_graph(p, civic_snapshot=c)
        self.profile = next(n['name'] for n in self.graph['nodes'] if n['id'] == 'CIViC.molecularprofile:81')
        self.question = 'Inspect candidate records for '+self.profile+' containing cetuximab in Colorectal Cancer.'

    def test_per_tool_requirements_and_both_evidence_views_are_explicit(self):
        contracts = tool_contracts(self.graph)['tools']
        proteins, civic = contracts
        self.assertNotIn('profile_id', proteins['requires']); self.assertFalse(proteins['civic_required'])
        self.assertNotIn('protein_id', civic['requires'])
        for tool in contracts: self.assertEqual(set(tool['views']), {'accepted', 'candidates'})
        graph = deepcopy(self.graph); graph.pop('civic')
        self.assertEqual([t['name'] for t in tool_contracts(graph)['tools']], ['protein_neighborhood'])

    def test_v2_prompt_contains_only_source_id_matches_and_contracts_not_reference_plans_or_statements(self):
        prompt, schema, policy, audit, resolution = planning_request(self.question, self.graph, 'entity_tools_v2')
        self.assertEqual(policy, 'bounded-question-planner.v2')
        data = json.loads(prompt.partition('\nUntrusted input data:\n')[2])
        self.assertEqual(resolved_ids(resolution, 'profiles'), ['CIViC.molecularprofile:81'])
        self.assertEqual(schema['properties']['profile_id']['enum'], ['CIViC.molecularprofile:81', None])
        self.assertEqual(schema['properties']['therapy']['enum'], ['cetuximab', None])
        self.assertEqual(data['catalogue']['profiles'][0]['id'], 'CIViC.molecularprofile:81')
        self.assertIn('tool_contracts_sha256', audit); self.assertIn('entity_resolution_sha256', audit)
        for forbidden in ['reference_plan', 'INVENTED SOFTWARE TEST statement', 'source_scores_raw']:
            self.assertNotIn(forbidden, prompt)

    def test_v2_uses_one_model_request_and_rejects_wrong_known_bindings_without_repair(self):
        calls = []
        def transport(payload): calls.append(payload); return response(civic_plan())
        model = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=transport, protocol='entity_tools_v2')
        trace = model.plan(self.question, self.graph)
        self.assertEqual(trace['status'], 'validated'); self.assertEqual(len(calls), 1)
        self.assertEqual(trace['planner_protocol'], 'entity_tools_v2')
        changed = self.question.replace(self.profile, 'UNKNOWN_X')
        trace = model.plan(changed, self.graph)
        self.assertEqual(trace['status'], 'invalid_plan'); self.assertIsNone(trace['plan'])
        self.assertEqual(len(calls), 2); self.assertEqual(trace['model_calls'], 1)

    def test_v1_is_still_selectable_and_invalid_protocol_fails_before_any_call(self):
        _, schema, policy, audit, resolution = planning_request(self.question, self.graph)
        self.assertEqual(policy, 'bounded-question-planner.v1'); self.assertIsNone(resolution)
        self.assertNotIn('enum', schema['properties']['profile_id'])
        self.assertEqual(audit['planner_protocol'], 'catalogue_v1')
        with self.assertRaises(PlannerUnavailable):
            ModelPlanner(model='test', endpoint='http://localhost:9999', protocol='auto')


if __name__ == '__main__': unittest.main()
