"""Invented reading fixtures exercise software guards, not biological accuracy."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from scripts import diagnose_verifier as shared
from scripts import probe_verifier_prompt as probe


def response(text):
    return {'model': shared.MODEL, 'usage': {'prompt_tokens': 20, 'completion_tokens': 3},
            'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': text}}]}


class PromptProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet = self.root / 'packet'
        probe.prepare(self.packet)
        self.manifest, self.cases, self.protocol, self.requests = probe.load_packet(self.packet)
        self.references = shared.read(self.packet / 'references.json')

    def run_injected(self, name, *, failure=None):
        destination = self.root / name
        by_request = {digest(r['payload']): case for r, case in zip(self.requests, self.cases)}
        references = {r['id']: r['expected'] for r in self.references}
        calls = []
        original_read = shared.read

        def guarded_read(path):
            if Path(path) == self.packet / 'references.json':
                execution = original_read(destination / 'execution.json')
                self.assertEqual(execution['status'], 'predictions_closed')
                self.assertEqual(execution['executed_requests'], len(calls))
            return original_read(path)

        def transport(request):
            case = by_request[digest(request)]
            calls.append(case['id'])
            self.assertEqual(original_read(destination / 'execution.json')['status'], 'predictions_open')
            self.assertEqual(original_read(destination / 'requests.json'), self.requests)
            self.assertNotIn('guided_choice', request)
            self.assertNotIn('guided_json', request)
            self.assertNotIn('response_format', request)
            self.assertNotIn('expected', json.dumps(request))
            if case['kind'] == 'wire':
                if failure == 'copy' and case['id'] == 'wire-copy':
                    return response('red')
                if failure == 'reasoning' and case['id'] == 'wire-echo':
                    return response('<think>PRIVATE_REASONING_SENTINEL</think>CHECK_7319')
                return response(self.protocol['wire_targets'][case['id']])
            self.assertIsNone(failure, 'A failed wire gate made a classification call')
            return response(references[case['id']])

        with patch.object(shared, 'read', side_effect=guarded_read):
            with patch.object(shared, 'request_once', side_effect=AssertionError('No live model in tests')):
                with redirect_stdout(io.StringIO()):
                    summary = probe.run(self.packet, destination, transport=transport)
        return destination, summary, calls

    def test_wire_failure_stops_after_two_and_reasoning_is_never_recovered(self):
        for failure in ('copy', 'reasoning'):
            with self.subTest(failure=failure):
                destination, summary, calls = self.run_injected(failure, failure=failure)
                self.assertEqual(calls, ['wire-echo', 'wire-copy'])
                self.assertFalse(summary['wire_pass'])
                self.assertFalse(summary['classification_executed'])
                self.assertEqual(summary['requests'], 2)
                self.assertEqual(summary['policies']['current']['cases'], 0)
                self.assertEqual(summary['policies']['neutral']['cases'], 0)
                rows = shared.read(destination / 'traces.json')
                self.assertNotIn('PRIVATE_REASONING_SENTINEL', json.dumps(rows))
                if failure == 'reasoning':
                    self.assertIsNone(rows[0]['final_text'])
                    self.assertTrue(rows[0]['reasoning_wrapper_or_field'])
                    self.assertEqual(rows[0]['status'], 'invalid_output')
                self.assertEqual(probe.verify(self.packet, destination)['packet_sha256'], self.manifest['packet_sha256'])

    def test_eight_frozen_requests_score_policies_separately_and_replay(self):
        destination, summary, calls = self.run_injected('success')
        self.assertEqual(calls, [c['id'] for c in self.cases])
        self.assertEqual(summary['requests'], 8)
        self.assertTrue(summary['wire_pass'])
        for policy in ('current', 'neutral'):
            self.assertEqual(summary['policies'][policy]['cases'], 3)
            self.assertEqual(summary['policies'][policy]['valid'], 3)
            self.assertEqual(summary['policies'][policy]['reference_matches'], 3)
        self.assertIsNone(summary['scientific_accuracy'])
        self.assertEqual(summary['independent_human_labels'], 0)
        for index in range(2, 8, 2):
            left, right = self.requests[index]['payload'], self.requests[index + 1]['payload']
            self.assertEqual({k: v for k, v in left.items() if k != 'messages'},
                             {k: v for k, v in right.items() if k != 'messages'})
            self.assertEqual(left['messages'][0], right['messages'][0])
            left_data = json.loads(left['messages'][1]['content'].split('\nUntrusted input data:\n')[1])
            right_data = json.loads(right['messages'][1]['content'].split('\nUntrusted input data:\n')[1])
            self.assertEqual(left_data, right_data)
            self.assertEqual(left_data['source'], [{'index': 0, 'text': probe.SOURCE}])
        execution = shared.read(destination / 'execution.json')
        self.assertEqual(execution['graph_mutations'], 0)
        self.assertEqual(execution['planned_requests'], 8)
        self.assertEqual(execution['executed_requests'], 8)
        probe.verify(self.packet, destination)

    def test_frozen_inputs_implementation_and_result_replay_reject_tampering(self):
        destination, _, _ = self.run_injected('result')
        summary_path = destination / 'summary.json'
        summary = shared.read(summary_path)
        summary['policies']['current']['reference_matches'] = 0
        write_json(summary_path, summary)
        receipt = shared.read(destination / 'receipt.json')
        receipt['files']['summary.json'] = shared.sha(summary_path)
        receipt['result_sha256'] = digest({k: v for k, v in receipt.items() if k != 'result_sha256'})
        write_json(destination / 'receipt.json', receipt)
        with self.assertRaisesRegex(ValueError, 'summary replay changed'):
            probe.verify(self.packet, destination)

        inputs_path = self.packet / 'inputs.json'
        original_inputs = inputs_path.read_bytes()
        inputs_path.write_bytes(original_inputs + b'\n')
        with self.assertRaisesRegex(ValueError, 'packet bytes changed'):
            probe.load_packet(self.packet)
        inputs_path.write_bytes(original_inputs)
        protocol = shared.read(self.packet / 'protocol.json')
        protocol['shared_code_sha256'] = '0' * 64
        write_json(self.packet / 'protocol.json', protocol)
        manifest = shared.read(self.packet / 'packet.json')
        manifest['files']['protocol.json'] = shared.sha(self.packet / 'protocol.json')
        manifest['packet_sha256'] = digest({k: v for k, v in manifest.items() if k != 'packet_sha256'})
        write_json(self.packet / 'packet.json', manifest)
        with self.assertRaisesRegex(ValueError, 'implementation changed'):
            probe.load_packet(self.packet)


if __name__ == '__main__':
    unittest.main()
