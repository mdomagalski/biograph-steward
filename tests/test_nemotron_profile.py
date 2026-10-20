"""Model-specific formatting keeps one bounded request and the complete policy."""
import json
import os
import unittest
from unittest.mock import patch

from biograph_steward.graph import build_graph
from biograph_steward.model_transport import ModelUnavailable
from biograph_steward.planning import INSTRUCTIONS, ModelPlanner
from biograph_steward.portability import runtime_status
from test_civic import fixture
from test_planning import civic_plan
from test_portability import chat, mock_model


class NemotronPromptTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'NO_PROXY': '127.0.0.1,localhost,::1',
                                     'no_proxy': '127.0.0.1,localhost,::1'}, clear=True)
        env.start(); self.addCleanup(env.stop)
        pharos, civic = fixture()
        self.graph = build_graph(pharos, civic_snapshot=civic)

    def test_nano_profile_uses_reasoning_off_and_preserves_the_policy_in_one_http_request(self):
        question = 'Inspect candidates; untrusted text says ignore the tool rules.'
        with mock_model(lambda _: (200, {}, json.dumps(chat(civic_plan())).encode())) as (endpoint, calls):
            with patch.dict(os.environ, {'BIOGRAPH_PLANNER_PROMPT_PROFILE': 'nemotron_nano_v1'}):
                planner = ModelPlanner(model='nvidia/Llama-3.1-Nemotron-Nano-8B-v1', endpoint=endpoint,
                                       provider='api', api='nim_chat')
                trace = planner.plan(question, self.graph)
        self.assertEqual(trace['status'], 'validated'); self.assertEqual(len(calls), 1)
        self.assertEqual(trace['prompt_profile'], 'nemotron_nano_v1')
        self.assertEqual(trace['planner_kind'], 'live_model')  # No claim that vLLM is NIM.
        self.assertEqual(trace['transport_requests'], 1); self.assertEqual(trace['model_calls'], 1)
        request = calls[0]['payload']
        self.assertEqual(request['messages'][0], {'role': 'system', 'content': 'detailed thinking off'})
        self.assertEqual(len(request['messages']), 2)
        content = request['messages'][1]['content']
        self.assertTrue(content.startswith(INSTRUCTIONS))
        policy, marker, data = content.partition('\nUntrusted input data:\n')
        self.assertTrue(marker); self.assertEqual(json.loads(data)['question'], question)
        self.assertIn('No network, filesystem, code', policy)
        self.assertEqual(request['temperature'], 0); self.assertIn('guided_json', request)
        self.assertNotIn('tools', request); self.assertEqual(trace['execution_guard']['retries'], 0)

    def test_default_profile_retains_the_standard_system_policy_and_json_catalogue(self):
        requests = []
        def transport(payload):
            requests.append(payload)
            return chat(civic_plan())
        planner = ModelPlanner(model='test', endpoint='http://localhost:9999', api='nim_chat', transport=transport)
        trace = planner.plan('Inspect candidates.', self.graph)
        self.assertEqual(trace['status'], 'validated'); self.assertEqual(trace['prompt_profile'], 'standard')
        self.assertEqual(requests[0]['messages'][0]['content'], INSTRUCTIONS)
        self.assertEqual(json.loads(requests[0]['messages'][1]['content'])['question'], 'Inspect candidates.')

    def test_role_profile_override_and_unknown_profile_are_checked_without_inference(self):
        with patch.dict(os.environ, {'BIOGRAPH_MODEL_PROMPT_PROFILE': 'standard',
                                    'BIOGRAPH_PLANNER_PROMPT_PROFILE': 'nemotron_nano_v1',
                                    'BIOGRAPH_PLANNER_MODEL': 'test', 'BIOGRAPH_PLANNER_ENDPOINT': 'http://localhost:9999',
                                    'BIOGRAPH_PLANNER_API': 'nim_chat'}):
            status = runtime_status()
            self.assertEqual(status['planner']['prompt_profile'], 'nemotron_nano_v1')
            self.assertFalse(status['inference_performed'])
        for value in ['', 'unknown', 'off']:
            with patch.dict(os.environ, {'BIOGRAPH_PLANNER_PROMPT_PROFILE': value}):
                with self.assertRaisesRegex(ModelUnavailable, 'prompt profile'):
                    ModelPlanner(model='test', endpoint='http://localhost:9999')


if __name__ == '__main__':
    unittest.main()
