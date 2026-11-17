import copy
import hashlib
import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from biograph_steward.client import digest
from tools.mechanistic_review.model_review import (aggregate, request_for, infer,
                                                  file_sha, write_json, append_durable)


def fixture():
    statement = {'type': 'Complex', 'members': [
        {'name': 'invented-a', 'db_refs': {'HGNC': '1'}},
        {'name': 'invented-b', 'db_refs': {'HGNC': '2'}},
        {'name': 'invented-c', 'db_refs': {'HGNC': '3'}}],
        'evidence': [{'text': 'Invented source one.', 'source_api': 'fixture'},
                     {'text': 'Invented source two.', 'source_api': 'fixture'}]}
    seal = hashlib.sha256(json.dumps(statement, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()
    return {'statement': statement, 'input_sha256': seal,
            'original_evidence_count': 2, 'all_original_evidence_admitted': True}


class ModelReviewTest(unittest.TestCase):
    def test_complete_native_nary_source_is_preserved(self):
        case = fixture()
        before = copy.deepcopy(case)
        prompt, schema, budget = request_for(case)
        data = json.loads(prompt.split('\nUntrusted input data:\n')[1])
        self.assertEqual(data['native_statement'], case['statement'])
        self.assertEqual(len(data['native_statement']['members']), 3)
        self.assertEqual(schema['required'], ['E01', 'E02'])
        self.assertEqual(budget, 208)
        self.assertEqual(case, before)

    def test_source_omission_or_released_belief_stops_request(self):
        case = fixture()
        case['statement']['evidence'].pop()
        with self.assertRaises(ValueError):
            request_for(case)
        case = fixture()
        case['statement']['belief'] = 0.99
        with self.assertRaises(ValueError):
            request_for(case)

    def test_native_any_support_all_fail_otherwise_abstain_policy(self):
        schema = request_for(fixture())[1]
        support = {'verdict': 'supports', 'reason': 'none'}
        fail = {'verdict': 'fails', 'reason': 'wrong_relation'}
        unknown = {'verdict': 'unclear', 'reason': 'unclear'}
        self.assertEqual(aggregate({'E01': support, 'E02': fail}, schema), 'retain_candidate')
        self.assertEqual(aggregate({'E01': fail, 'E02': fail}, schema), 'prune_candidate')
        self.assertEqual(aggregate({'E01': unknown, 'E02': fail}, schema), 'abstain')

    def test_incomplete_or_contradictory_response_is_not_pruned(self):
        schema = request_for(fixture())[1]
        with self.assertRaises(ValueError):
            aggregate({'E01': {'verdict': 'fails', 'reason': 'wrong_relation'}}, schema)
        with self.assertRaises(ValueError):
            aggregate({'E01': {'verdict': 'supports', 'reason': 'grounding'},
                       'E02': {'verdict': 'fails', 'reason': 'wrong_relation'}}, schema)
        with self.assertRaises(ValueError):
            aggregate({'E01': {'verdict': [], 'reason': 'wrong_relation'},
                       'E02': {'verdict': 'fails', 'reason': 'wrong_relation'}}, schema)

    def test_interrupted_request_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case = {**fixture(), 'case_id': 'invented-only', 'split': 'test'}
            cases = root / 'cases.jsonl'
            cases.write_text(json.dumps(case) + '\n')
            protocol = {'native_baseline': {'source_cases': {'sha256': file_sha(cases)},
                         'reserve_count': 1}, 'model_review': {'code_files': [],
                         'max_output_tokens_total': 1000}}
            proto = root / 'protocol.json'
            write_json(proto, protocol)
            pin = file_sha(proto)
            prompt, schema, budget = request_for(case)
            preflight = {'protocol_sha256': pin, 'rows': [{
                'case_id': case['case_id'], 'prompt_sha256': digest(prompt),
                'schema_sha256': digest(schema), 'fits': True}]}
            preflight['content_sha256'] = digest(preflight)
            pre = root / 'preflight.json'
            write_json(pre, preflight)
            out = root / 'model.json'
            append_durable(out.with_suffix('.request_intents.jsonl'), {
                'case_id': case['case_id'], 'input_sha256': case['input_sha256'],
                'protocol_sha256': pin, 'max_output_tokens': budget})
            with patch('tools.mechanistic_review.model_review.JSONModelClient') as client:
                infer(proto, pin, cases, pre, 'http://127.0.0.1:1', out)
                client.return_value.generate.assert_not_called()
            result = json.loads(out.read_text())['rows'][0]
            self.assertEqual(result['status'], 'model_error')
            self.assertEqual(result['proposal'], 'abstain')
            self.assertTrue(result['trace']['request_may_have_been_sent'])


if __name__ == '__main__':
    unittest.main()
