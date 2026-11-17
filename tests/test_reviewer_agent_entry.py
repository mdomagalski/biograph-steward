"""Entry-registration contracts on invented sources; verified jobs are mocked.

The positive mocked header checks registration wiring, not live inference. The
independent source-agent HTTP tests qualify the real saved-result verifier.
"""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from biograph_steward.questions import answer_question, graph_basis, save_answer
from biograph_steward.workspaces import registered_source_agent_entry
import test_string_physical_source as source_fixture


class ReviewerAgentEntryTests(unittest.TestCase):
    def setUp(self):
        source = source_fixture.NativePhysicalTests()
        source.setUp(); self.addCleanup(source.doCleanups)
        self.root = source.root
        _, self.folder, _, self.graph = source.workspace()
        self.question = 'native_manual_question'
        answer = answer_question(self.graph, 'P04637', template='native_string_physical.v1',
            relations=['interactions'], view='candidates', source_run=self.folder.name)
        save_answer(answer, self.root / self.question)
        self.job_id = 'source_agent_mocked_contract'
        job = self.root / self.job_id; job.mkdir()
        raw = b'{"invented":"registration contract only; not an actual model receipt"}\n'
        (job / 'manifest.json').write_bytes(raw)
        self.registration = {'format': 'biograph-steward.source-agent-reviewer-entry.v1',
            'source_run': self.folder.name, 'question_id': self.question, 'job_id': self.job_id,
            'job_manifest_sha256': hashlib.sha256(raw).hexdigest()}
        self.index = self.root / 'reviewer_agent_entry.json'
        self.index.write_text(json.dumps(self.registration))
        url = '/?run=' + self.folder.name + '&question=' + self.question
        self.entry = {'example_url': url, 'data_kind': 'live_pharos', 'snapshot_sha256': self.graph['snapshot_sha256'],
                      'guided_examples': [{'url': '/?run=retained', 'label': 'Applied qualification'}]}
        self.runs = [{'run_id': self.folder.name, 'data_kind': 'live_pharos',
            'snapshot_sha256': self.graph['snapshot_sha256'], 'questions': [{'question_id': self.question,
                'url': url, 'view': 'candidates', 'template': 'native_string_physical.v1'}]}]
        self.verified = {'actual_model_run': True, 'status': 'completed', 'source_run': self.folder.name,
            'result': {'data_kind': 'live_pharos', 'plan': {'tool': 'native_physical',
                'arguments': {'protein_id': 'UniProtKB:P04637', 'view': 'candidates'}},
                'source_bindings': {'graph_basis_sha256': graph_basis(self.graph)}}}

    def load(self, verified=None):
        with patch('biograph_steward.source_agent_jobs.read_source_agent_job',
                   return_value=verified if verified is not None else self.verified) as reader:
            result = registered_source_agent_entry(self.root, self.runs, self.entry)
        return result, reader

    def test_exact_operator_registration_features_record_and_keeps_manual_question(self):
        result, reader = self.load()
        self.assertEqual(result['example_url'], self.entry['example_url'] + '&agent_job=' + self.job_id + '&view=data')
        self.assertEqual(result['guided_examples'], self.entry['guided_examples'])
        self.assertEqual(result['agent_job_id'], self.job_id)
        reader.assert_called_once_with(self.root / self.job_id, self.root)

    def test_missing_registration_preserves_existing_entry_without_reading_a_job(self):
        self.index.unlink()
        result, reader = self.load()
        self.assertEqual(result, self.entry); reader.assert_not_called()

    def test_injected_failed_foreign_source_and_different_anchor_cannot_be_featured(self):
        bad = []
        for key, value in [('actual_model_run', False), ('status', 'invalid_proposal'), ('source_run', 'foreign')]:
            item = deepcopy(self.verified); item[key] = value; bad.append(item)
        item = deepcopy(self.verified); item['result']['plan']['arguments']['protein_id'] = 'UniProtKB:P00533'; bad.append(item)
        item = deepcopy(self.verified); item['result']['plan']['arguments']['view'] = 'accepted'; bad.append(item)
        item = deepcopy(self.verified); item['result']['source_bindings']['graph_basis_sha256'] = '0' * 64; bad.append(item)
        for verified in bad:
            with self.subTest(verified=verified):
                result, _ = self.load(verified)
                self.assertTrue(result['agent_entry_unavailable'])
                self.assertEqual(result['example_url'], self.entry['example_url'])

    def test_changed_manifest_and_unavailable_source_fail_back_without_selecting_another_job(self):
        (self.root / self.job_id / 'manifest.json').write_text('{}')
        result, reader = self.load()
        reader.assert_not_called(); self.assertTrue(result['agent_entry_unavailable'])
        self.assertNotIn('agent_job_id', result)
        self.runs.clear()
        result, reader = self.load()
        reader.assert_not_called(); self.assertEqual(result['example_url'], self.entry['example_url'])

    def test_linked_oversized_malformed_and_unknown_registration_fields_fail_closed(self):
        cases = ['{', json.dumps({**self.registration, 'apply': True}), ' ' * 10_001,
                 json.dumps({**self.registration, 'job_id': '../outside'}),
                 json.dumps({**self.registration, 'source_run': 'other_cohort'})]
        for raw in cases:
            self.index.write_text(raw)
            result, reader = self.load()
            reader.assert_not_called(); self.assertTrue(result['agent_entry_unavailable'])
        self.index.unlink(); self.index.symlink_to(self.root / self.job_id / 'manifest.json')
        result, reader = self.load()
        reader.assert_not_called(); self.assertTrue(result['agent_entry_unavailable'])

    def test_a_verifier_failure_does_not_promote_a_different_or_latest_record(self):
        with patch('biograph_steward.source_agent_jobs.read_source_agent_job', side_effect=ValueError('Source changed')):
            result = registered_source_agent_entry(self.root, self.runs, self.entry)
        self.assertEqual(result['example_url'], self.entry['example_url'])
        self.assertTrue(result['agent_entry_unavailable'])


if __name__ == '__main__':
    unittest.main()
