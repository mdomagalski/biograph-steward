"""Bounded cohort construction contracts using invented Pharos responses."""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.__main__ import main
from biograph_steward.client import PharosClient, PharosError, VERSION, digest
from biograph_steward.construction import (construct_snapshot, plan_construction,
                                         publish_construction, run_construction,
                                         verify_construction_run)
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.questions import verify_answer
from test_pharos_inventory import InventoryAPI


def request_fixture(**changes):
    return {"accessions": ["P04637", "P00533"], "focus_uniprot": "P04637",
            "profile": "ppi", "relations": ["interactions"], **changes}


def pointer(value, path):
    for part in path.strip('/').split('/'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def reseal(value):
    value = deepcopy(value)
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    return value


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.api = InventoryAPI()
        self.client = PharosClient(transport=self.api)

    def snapshot(self, **changes):
        return construct_snapshot(self.client, request_fixture(**changes), data_kind='synthetic_demo')

    def test_invalid_request_rejected_before_source_access(self):
        cases = [
            {'accessions': []}, {'accessions': 'P04637'},
            {'accessions': ['P04637', 'P04637']}, {'accessions': ['P04637', None]},
            {'accessions': ['P04637', 'p00533']}, {'accessions': ['P04637', 'not-an-accession']},
            {'accessions': [f'P{i:05d}' for i in range(26)], 'focus_uniprot': 'P00000'},
            {'focus_uniprot': 'P01116'}, {'focus_uniprot': None},
            {'profile': 'unbounded'}, {'profile': []},
            {'relations': ['causes']}, {'relations': ['interactions', 'interactions']},
            {'relations': 'interactions'}, {'endpoint': 'https://other.example/graphql'},
            {'context_limits': {'ppis': 999999}}, {'accessions': ['P04637', True]},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                construct_snapshot(self.client, request_fixture(**changes))
        self.assertEqual(self.api.calls, [])

    def test_plan_is_deterministic_and_does_not_mutate_request(self):
        request = request_fixture()
        original = deepcopy(request)
        self.assertEqual(plan_construction(request), plan_construction(deepcopy(request)))
        self.assertEqual(request, original)
        self.assertEqual(self.api.calls, [])

    def test_ppi_profile_fetches_only_ppi_rows_and_preserves_outside_source_records(self):
        snapshot = self.snapshot()
        self.assertEqual(snapshot['scope']['kind'], 'protein_cohort')
        self.assertIsNone(snapshot['disease'])
        self.assertEqual({t['uniprot'] for t in snapshot['targets']}, {'P04637', 'P00533'})
        calls = [c['query'] for c in self.api.calls]
        self.assertFalse(any('DiseaseTargets' in q or 'associatedDisease' in q for q in calls))
        self.assertFalse(any('Scoped_' in q and 'Scoped_ppis' not in q for q in calls))
        coverage = snapshot['retrieval']['context']
        self.assertEqual(coverage['summary']['ppis']['retrieved'], 2)
        self.assertEqual(coverage['summary']['ppis']['retained'], 1)
        self.assertEqual(coverage['summary']['ppis']['excluded_by_scope'], 1)
        self.assertEqual(coverage['summary']['ppis']['target_statuses'], {'complete': 2})
        target = next(t for t in snapshot['targets'] if t['uniprot'] == 'P04637')
        self.assertEqual([r['target']['uniprot'] for r in target['pharos_context']['ppis']], ['P00533'])
        raw = [row for r in snapshot['requests'] if 'Scoped_ppis' in r['request']['query']
               for v in r['response']['data'].values() for row in v['rows']]
        self.assertEqual({r['target']['uniprot'] for r in raw}, {'P00533', 'P01116'})
        self.assertEqual(snapshot['content_sha256'], digest({k: v for k, v in snapshot.items()
                                                           if k != 'content_sha256'}))

    def test_source_locators_remain_local_after_prior_client_requests(self):
        self.client.execute(VERSION)
        snapshot = self.snapshot()
        for row in snapshot['retrieval']['context']['targets']:
            for page in row['pages']:
                record = snapshot['requests'][page['request_index']]
                self.assertIn('Scoped_' + row['family'], record['request']['query'])
                raw = pointer(record['response'], page['response_pointer'])
                self.assertEqual(len(raw), page['returned'])
                parent = pointer(record['response'], page['response_pointer'].rsplit('/', 1)[0])
                self.assertEqual(parent['uniprot'], row['uniprot'])
        for record in snapshot['requests']:
            self.assertEqual(record['response_sha256'], digest(record['response']))

    def test_exact_resolution_retains_missing_and_mismatched_accessions(self):
        ids = ['P04637', 'P00533', 'P01116', 'P15056']
        snapshot = self.snapshot(accessions=ids)
        rows = snapshot['scope']['resolutions']
        self.assertEqual({r['requested_uniprot']: r['status'] for r in rows},
                         {'P04637': 'resolved', 'P00533': 'resolved',
                          'P01116': 'not_found', 'P15056': 'identity_mismatch'})
        self.assertEqual({t['uniprot'] for t in snapshot['targets']}, {'P04637', 'P00533'})
        for row in rows:
            envelope = snapshot['requests'][row['request_index']]
            self.assertEqual(pointer(envelope['response'], row['response_pointer']), row['returned'])
        self.assertNotIn('P42336', snapshot['retrieval']['context']['scope']['seed_uniprots'])
        self.assertEqual(set(snapshot['retrieval']['context']['scope']['ppi_cohort_uniprots']), set(ids))

    def test_count_inconsistency_is_not_reported_as_complete(self):
        self.api.modify = lambda family, uid, skip, response: (
            {**response, 'rows': response['rows'][:1]} if family == 'ppis' else response)
        snapshot = self.snapshot()
        row = next(r for r in snapshot['retrieval']['context']['targets']
                   if r['family'] == 'ppis' and r['uniprot'] == 'P04637')
        self.assertEqual(row['status'], 'inconsistent')
        self.assertTrue(row['issues'])

    def test_database_version_change_rejects_snapshot(self):
        api = InventoryAPI()
        versions = 0

        def changing(payload):
            nonlocal versions
            result = api(payload)
            if 'DatabaseVersion' in payload['query']:
                versions += 1
                result['data']['dbVersion'] = 'before' if versions == 1 else 'after'
            return result

        with self.assertRaises(PharosError):
            construct_snapshot(PharosClient(transport=changing), request_fixture())

    def test_publication_replays_offline_and_preserves_candidates_and_source_trace(self):
        snapshot = self.snapshot()
        before = deepcopy(snapshot)
        with patch.object(PharosClient, '_http', side_effect=AssertionError('Offline publication used network')):
            result = publish_construction(snapshot, self.root / 'published')
            export_packet(self.root / 'published', self.root / 'packet')
            packet = load_packet(self.root / 'packet')
        self.assertEqual(snapshot, before)
        graph, answer = result['graph'], result['question']
        self.assertFalse(any(n['category'] == 'biolink:Disease' for n in graph['nodes']))
        self.assertFalse(any(a['kind'] in {'disease_association', 'disease_filtered_membership'}
                             for a in graph['assertions']))
        self.assertTrue(graph['assertions'])
        self.assertTrue(all(a['lifecycle_state'] == 'candidate' for a in graph['assertions']))
        self.assertTrue(answer['summary'])
        self.assertTrue(answer['citations'])
        verify_answer(answer)
        for row in graph['context_records']:
            self.assertTrue(row['source_response_locators'])
            for locator in row['source_response_locators']:
                response = snapshot['requests'][locator['request_index']]['response']
                self.assertEqual(pointer(response, locator['response_pointer']), row['record'])
        for sentence in answer['summary']:
            self.assertTrue(sentence['citation_ids'])
        saved = json.loads((self.root / 'published/snapshot.json').read_text())
        self.assertEqual(saved, snapshot)
        self.assertEqual(json.loads((self.root / 'published/question.json').read_text()), answer)
        self.assertTrue((self.root / 'published/answer/report.html').is_file())
        self.assertEqual(packet[1], graph)

    def test_output_is_immutable(self):
        result = run_construction(self.client, request_fixture(), self.root / 'published')
        before = {p.relative_to(self.root / 'published'): p.read_bytes()
                  for p in (self.root / 'published').rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):
            publish_construction(json.loads((self.root / 'published/snapshot.json').read_text()),
                                 self.root / 'published')
        self.assertEqual(before, {p.relative_to(self.root / 'published'): p.read_bytes()
                                 for p in (self.root / 'published').rglob('*') if p.is_file()})
        self.assertTrue(result['graph']['nodes'])

    def test_published_receipt_rejects_changed_source_graph_and_answer(self):
        publish_construction(self.snapshot(), self.root / 'published')
        folder = self.root / 'published'
        receipt = verify_construction_run(folder)
        self.assertIsInstance(receipt, dict)
        for name in ['snapshot.json', 'graph.json', 'question.json', 'construction_receipt.json']:
            path = folder / name
            original = path.read_bytes()
            with self.subTest(name=name):
                path.write_text('{}')
                with self.assertRaises(ValueError):
                    verify_construction_run(folder)
                path.write_bytes(original)
        self.assertEqual(verify_construction_run(folder), receipt)

    def test_missing_focus_preserves_graph_with_explicit_answer_abstention(self):
        snapshot = self.snapshot(accessions=['P04637', 'P00533', 'P01116'],
                                 focus_uniprot='P01116')
        result = publish_construction(snapshot, self.root / 'unresolved')
        self.assertTrue(result['graph']['nodes'])
        self.assertIsNone(result['question'])
        self.assertFalse((self.root / 'unresolved/question.json').exists())
        receipt = verify_construction_run(self.root / 'unresolved')
        self.assertEqual(receipt['answer_status'], 'anchor_unresolved')

    def test_all_unresolved_is_an_explicit_empty_graph_not_a_retrieval_failure(self):
        snapshot = self.snapshot(accessions=['P01116'], focus_uniprot='P01116')
        result = publish_construction(snapshot, self.root / 'unresolved')
        self.assertEqual(result['graph']['nodes'], [])
        self.assertIsNone(result['question'])
        self.assertEqual(verify_construction_run(self.root / 'unresolved')['answer_status'], 'anchor_unresolved')

    def test_changed_runtime_requires_new_publication_and_missing_receipt_is_not_listed(self):
        from biograph_steward.construction import _implementation
        from biograph_steward.workspaces import saved_workspaces
        folder = self.root / 'published'
        publish_construction(self.snapshot(), folder)
        before = _implementation()
        with patch('biograph_steward.construction._implementation', return_value={**before, 'construction': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'implementation changed'):
                verify_construction_run(folder)
        self.assertEqual(len(saved_workspaces(self.root)['runs']), 1)
        (folder / 'construction_receipt.json').unlink()
        self.assertEqual(saved_workspaces(self.root)['runs'], [])
        self.assertEqual(saved_workspaces(self.root)['withheld'], 1)

    def test_bad_retrieval_pointer_cannot_publish_a_trace_without_raw_source(self):
        snapshot = self.snapshot()
        row = next(r for r in snapshot['retrieval']['context']['targets'] if r['pages'])
        row['pages'][0]['request_index'] = len(snapshot['requests']) + 10
        with self.assertRaises(ValueError):
            publish_construction(reseal(snapshot), self.root / 'bad_pointer')

    def test_cli_demo_offline_republication_and_verification_need_no_network(self):
        source, replay = self.root / 'cli_demo', self.root / 'cli_replay'
        with patch.object(PharosClient, '_http', side_effect=AssertionError('Offline CLI used network')), redirect_stdout(StringIO()):
            self.assertEqual(main(['construct', '--demo', '--out', str(source)]), 0)
            self.assertEqual(main(['construction-verify', '--run', str(source)]), 0)
            self.assertEqual(main(['construct', '--snapshot', str(source / 'snapshot.json'),
                                   '--out', str(replay)]), 0)
            self.assertEqual(main(['construction-verify', '--run', str(replay)]), 0)
        self.assertEqual((source / 'snapshot.json').read_bytes(), (replay / 'snapshot.json').read_bytes())
        self.assertEqual(json.loads((source / 'graph.json').read_text()),
                         json.loads((replay / 'graph.json').read_text()))
        self.assertEqual(json.loads((source / 'run_manifest.json').read_text())['data_kind'], 'synthetic_demo')
        before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
        with redirect_stderr(StringIO()):
            self.assertEqual(main(['construct', '--snapshot', str(source / 'snapshot.json'),
                                   '--out', str(source / 'nested_replay')]), 1)
        self.assertEqual(before, {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()})

    def test_cli_cohort_guards_precede_model_and_civic_calls(self):
        source = self.root / 'cli_cohort'
        publish_construction(self.snapshot(), source)
        with (patch('biograph_steward.planning.configured_planner', side_effect=AssertionError('Unexpected model setup')),
              patch('biograph_steward.civic.CivicClient', side_effect=AssertionError('Unexpected CIViC setup')),
              redirect_stderr(StringIO()) as errors):
            self.assertEqual(main(['plan-question', '--run', str(source), '--question', 'Inspect P04637',
                                   '--out', str(self.root / 'model_output')]), 1)
            self.assertEqual(main(['civic', '--run', str(source), '--out', str(self.root / 'civic_output')]), 1)
        self.assertIn('no model was called', errors.getvalue())
        self.assertIn('No CIViC request was made', errors.getvalue())
        self.assertFalse((self.root / 'model_output').exists())
        self.assertFalse((self.root / 'civic_output').exists())

    def test_direct_model_workflow_rejects_cohort_before_configuring_model(self):
        from biograph_steward.portability import BoundedQuestionWorkflow
        source = self.root / 'workflow_cohort'
        publish_construction(self.snapshot(), source)
        with patch('biograph_steward.portability.configured_planner',
                   side_effect=AssertionError('Unexpected model configuration')):
            with self.assertRaisesRegex(ValueError, 'no model was called'):
                BoundedQuestionWorkflow(source)

    def test_cli_requires_live_focus_and_cannot_change_offline_scope(self):
        with patch.object(PharosClient, '_http', side_effect=AssertionError('Invalid CLI used network')), redirect_stderr(StringIO()):
            self.assertEqual(main(['construct', '--accessions', 'P04637', '--out', str(self.root / 'invalid_live')]), 1)
            self.assertEqual(main(['construct', '--demo', '--focus-uniprot', 'P04637',
                                   '--out', str(self.root / 'invalid_demo')]), 1)
        self.assertFalse((self.root / 'invalid_live').exists())
        self.assertFalse((self.root / 'invalid_demo').exists())


if __name__ == '__main__':
    unittest.main()
