"""Invented-source tests for durable, non-leaking frozen evaluation execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from biograph_steward.source_agent_jobs import read_source_agent_job
from tools import source_agent_evaluation as runner
from test_source_agent import FakeModel
from test_string_physical_source import NativePhysicalTests


class FrozenRunnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = NativePhysicalTests('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        _, self.source, _, self.graph = self.fixture.workspace()
        self.root = self.fixture.root
        self.pins = {'INVENTED-code.py': 'a' * 64}
        patcher = patch.object(runner, 'code_pins', side_effect=lambda: deepcopy(self.pins))
        patcher.start(); self.addCleanup(patcher.stop)
        self.protocol = self.root / 'protocol.md'; self.protocol.write_text('Invented test protocol.\n')
        constraints = {'view': 'candidates', 'max_results': 8, 'max_paths': 2, 'go_limit': 10}
        self.plan = self.root / 'plan.json'
        write_json(self.plan, {'protocol_file': str(self.protocol), 'protocol_file_sha256': sha(self.protocol),
            'cases': [
                {'case_id': 'S01', 'source_run': 'physical',
                 'question': 'Show candidate native STRING physical associations with UniProtKB:P04637.',
                 'constraints': constraints,
                 'expected': {'behavior': 'execute', 'tool': 'native_physical', 'anchor_id': 'UniProtKB:P04637',
                              'untrusted_evaluator_note': 'DO_NOT_SEND_EXPECTED_MARKER'}},
                {'case_id': 'S08', 'source_run': 'physical',
                 'question': 'Show native physical associations of PROTEIN_NOT_IN_THIS_WORKSPACE.',
                 'constraints': constraints,
                 'expected': {'behavior': 'unresolved_identity_preflight', 'tool': None, 'anchor_id': None}}]})
        self.config = self.root / 'config.json'
        write_json(self.config, {'model': 'INVENTED-model', 'provider': 'nim',
            'endpoint': 'http://127.0.0.1:9/v1/chat/completions', 'api': 'nim_chat',
            'prompt_profile': 'standard', 'max_output_tokens': 1200, 'timeout': 1})
        self.runtime = self.root / 'runtime.json'
        write_json(self.runtime, {'format': 'invented_runtime_attestation', 'model': 'INVENTED-model',
                                  'actual_model_or_service_started': False})

    def prepare(self, **kwargs):
        target = self.root / kwargs.pop('name', 'prepared')
        with patch.object(runner.JSONModelClient, 'generate', side_effect=AssertionError('Preparation must not call a model')):
            bound = runner.prepare(self.plan, self.root, self.config, self.runtime, target,
                                   test_mode=True, **kwargs)
        self.assertEqual(bound['model_calls_during_prepare'], 0)
        for record in bound['cases'].values():
            self.assertEqual(record['controller_policy_sha256'], runner.digest(runner.agent.GUIDANCE))
            self.assertRegex(record['plan_schema_sha256'], r'^[a-f0-9]{64}$')
        return target, sha(target / 'prepared.json')

    def run_fixture(self, prepared, frozen_sha, model=None, name='execution'):
        model = model or FakeModel()
        output = self.root / name
        result = runner.run(prepared, frozen_sha, self.root, output, client_factory=lambda config: model)
        return output, result, model

    def test_complete_sources_parity_shared_jobs_and_no_expected_label_in_model_input(self):
        prepared, seal = self.prepare()
        output, execution, model = self.run_fixture(prepared, seal)
        self.assertEqual(execution['status'], 'completed')
        self.assertEqual(execution['reserved_model_calls'], 3)
        self.assertEqual(execution['requested_output_token_ceiling'], 3600)
        report = runner.report(output, self.root / 'report.json')
        self.assertEqual(report['behavioral_cases_passed'], 2)
        self.assertFalse(report['scientific_accuracy_evaluated'])
        self.assertFalse(report['prediction_gain_evaluated'])
        self.assertEqual(report['learner_input_artifacts'], 0)
        self.assertEqual(report['prediction_input_applicability'],
                         'not_applicable_no_source_compatible_prediction_artifact')
        first, unknown = report['cases']
        self.assertTrue(all(first['deterministic_parity'].values()))
        self.assertTrue(first['source_binding_unchanged'])
        self.assertEqual(first['captured_pharos_only']['status'], 'native_source_contract_unavailable')
        self.assertEqual(unknown['agency']['decision_origin'], 'preflight_guard')
        self.assertFalse(unknown['agency']['model_refusal_credit'])
        self.assertEqual(unknown['reserved_transport_calls'], 0)
        self.assertEqual(len(model.calls), 3)
        for event in (output / 'S01/events').glob('*request_intent.json'):
            prompt = runner.read(event)['request']['prompt']
            self.assertNotIn('DO_NOT_SEND_EXPECTED_MARKER', prompt)
        job = read_source_agent_job(self.root / first['saved_job_id'], self.root)
        self.assertFalse(job['actual_model_run'])
        self.assertEqual(job['result']['trace']['provider_kind'], 'injected_test_model')
        self.assertEqual(job['result']['answer']['coverage']['matching_proteins'], 2)
        self.assertEqual(len(job['result']['inspections']), 1)
        with self.assertRaises(FileExistsError):
            self.run_fixture(prepared, seal, model=model)
        self.assertEqual(len(model.calls), 3)

    def test_invalid_original_model_proposal_is_preserved_in_events_and_shared_failure_job(self):
        prepared, seal = self.prepare()
        def bad(phase, value):
            if phase == 'review_proposals': value['proposals'][0]['decision'] = 'prune'
            return value
        output, execution, _ = self.run_fixture(prepared, seal, model=FakeModel(bad))
        report = runner.report(output, self.root / 'report.json')
        first = report['cases'][0]
        self.assertFalse(first['case_passed']); self.assertEqual(first['status'], 'invalid_proposal')
        self.assertTrue(all(first['deterministic_parity'].values()))
        job = read_source_agent_job(self.root / first['saved_job_id'], self.root)
        self.assertEqual(job['result']['status'], 'invalid_proposal')
        self.assertEqual(job['result']['proposals'], [])
        raw = [runner.read(p) for p in (output / 'S01/events').glob('*model_response.json')]
        review = [event for event in raw if event['phase'] == 'review_proposals']
        self.assertEqual(len(review), 1)
        self.assertEqual(review[0]['model_trace']['output']['proposals'][0]['decision'], 'prune')
        self.assertEqual(execution['reserved_model_calls'], 3)

    def test_changed_source_inventory_stops_before_any_inference(self):
        prepared, seal = self.prepare()
        (self.source / 'unexpected_added_source.txt').write_text('Invented post-freeze file.\n')
        output, execution, model = self.run_fixture(prepared, seal)
        self.assertEqual(model.calls, [])
        self.assertEqual(execution['reserved_model_calls'], 0)
        self.assertEqual(execution['status'], 'stopped')
        summary = runner.read(output / 'S01/case_summary.json')
        self.assertFalse(summary['prepared_source_binding_matched'])
        self.assertFalse(summary['case_passed'])
        self.assertTrue((output / 'S01/case_exception.json').is_file())

    def test_code_and_explicit_learner_input_changes_block_before_model(self):
        learner = self.root / 'learner.tsv'; learner.write_text('INVENTED\t1\n')
        prepared, seal = self.prepare(learner_inputs=['fixed_inputs=' + str(learner)])
        model = FakeModel()
        self.pins['INVENTED-code.py'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'implementation changed'):
            self.run_fixture(prepared, seal, model=model)
        self.pins['INVENTED-code.py'] = 'a' * 64
        learner.write_text('INVENTED\t2\n')
        with self.assertRaisesRegex(ValueError, 'learner-input artifact changed'):
            self.run_fixture(prepared, seal, model=model)
        self.assertEqual(model.calls, [])
        self.assertFalse((self.root / 'execution').exists())

    def test_report_rejects_rewritten_model_event(self):
        prepared, seal = self.prepare()
        output, _, _ = self.run_fixture(prepared, seal)
        event = sorted((output / 'S01/events').glob('*model_response.json'))[0]
        value = runner.read(event); value['invented_tamper'] = True
        event.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'event/result bytes changed'):
            runner.report(output, self.root / 'report.json')
        self.assertFalse((self.root / 'report.json').exists())

    def test_boolean_caps_and_credential_config_are_rejected_without_model(self):
        plan = runner.read(self.plan); plan['cases'][0]['constraints']['max_results'] = True
        self.plan.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'caller caps differ'):
            self.prepare()
        plan['cases'][0]['constraints']['max_results'] = 8
        self.plan.write_text(json.dumps(plan))
        runtime = runner.read(self.runtime); runtime['api_key'] = 'INVENTED-DO-NOT-FREEZE'
        self.runtime.write_text(json.dumps(runtime))
        with self.assertRaisesRegex(ValueError, 'do not freeze credentials'):
            self.prepare()

    def test_fixture_binding_cannot_be_relabelled_as_a_live_run(self):
        prepared, seal = self.prepare()
        with self.assertRaisesRegex(ValueError, 'fixture runs require explicit injection'):
            runner.run(prepared, seal, self.root, self.root / 'execution')


class TotalBudgetTests(unittest.TestCase):
    def test_twenty_fifth_request_is_blocked_before_transport_and_intents_are_durable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            budget = runner.Budget(Path(temp) / 'budget')
            class Model:
                kind = 'injected_test_model'; model = 'INVENTED-model'; max_output_tokens = 1200
                calls = 0
                def generate(self, *args, **kwargs):
                    self.calls += 1
                    return {'model_calls': 1, 'status': 'model_error', 'usage': {'completion_tokens': 0}}
            raw = Model(); client = runner.BudgetClient(raw, budget, 'S01', ['INVENTED-model'], fixture=True)
            for _ in range(24): client.generate('INVENTED', {}, 'INVENTED', audit={'phase': 'test'})
            with self.assertRaisesRegex(ValueError, 'total model budget exhausted'):
                client.generate('INVENTED', {}, 'INVENTED')
            self.assertEqual(raw.calls, 24)
            self.assertEqual(budget.calls * runner.MAX_OUTPUT, 28800)
            self.assertEqual(len(list(budget.folder.glob('*request_intent.json'))), 24)
            self.assertEqual(len(list(budget.folder.glob('*transport_response.json'))), 24)


if __name__ == '__main__':
    unittest.main()
