"""Software-contract fixtures only; no biomedical accuracy reference judgments."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from scripts import diagnose_verifier as diagnostic


def envelope(text='SUPPORT', *, finish='stop', **message):
    return {'model': diagnostic.MODEL,
            'usage': {'prompt_tokens': 20, 'completion_tokens': 3, 'total_tokens': 23},
            'choices': [{'finish_reason': finish,
                         'message': {'role': 'assistant', 'content': text, **message}}]}


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = self.root / 'context'
        self.context.mkdir()
        # The extractor's source-offset contract is intentionally represented by
        # an invented paragraph, rather than depending on an ignored live run.
        start = 'In the wild-type (WT) KRAS stratum, '
        ending = 'P = .072).'
        middle = 'INVENTED SOFTWARE FIXTURE. '
        focused = start + middle + ' ' * (384 - len(start + middle + ending)) + ending
        self.assertEqual(len(focused), 384)
        prime = 'x' * 77 + focused + ' UNUSED INVENTED SUFFIX.'
        inputs = []
        refs = []
        for index, name in enumerate(('krystal-response', 'krystal-regimen',
                                      'prime-os', 'prime-significance')):
            ident = 'fixture-' + str(index)
            inputs.append({'id': ident, 'document_id': 20921465 if name.startswith('prime') else 36546659,
                'claim': 'Invented fixture claim ' + str(index),
                'document': {'sentences': [
                    {'index': 0, 'text': 'INVENTED BACKGROUND.'},
                    {'index': 1, 'text': 'INVENTED METHODS.'},
                    {'index': 2, 'text': prime if name.startswith('prime') else 'INVENTED RESULTS.'},
                    {'index': 3, 'text': 'INVENTED CONCLUSION.'}]}})
            refs.append({'id': ident, 'reference_id': name,
                         'expected': diagnostic.LABELS[index % len(diagnostic.LABELS)],
                         'private_reference_reason': 'REFERENCE_SENTINEL_DO_NOT_SEND'})
        write_json(self.context / 'inputs.json', inputs)
        write_json(self.context / 'references.json', refs)
        original = {'files': {n: diagnostic.sha(self.context / n)
                              for n in ('inputs.json', 'references.json')}}
        original['packet_sha256'] = digest(original)
        write_json(self.context / 'packet.json', original)
        self.packet = self.root / 'packet'
        diagnostic.prepare(self.context, self.packet)
        self.manifest, self.cases, self.protocol = diagnostic.load_packet(self.packet)
        self.references = diagnostic.read(self.packet / 'references.json')

    def run_stage(self, name, stage, *, previous=None, mode='correct'):
        destination = self.root / name
        references = {r['id']: r for r in self.references}
        cases = {digest(c['data']): c for c in self.cases}
        calls = []

        def transport(request):
            self.assertEqual(diagnostic.read(destination / 'execution.json')['status'], 'predictions_open')
            self.assertTrue((destination / 'requests.json').is_file())
            self.assertNotIn('REFERENCE_SENTINEL_DO_NOT_SEND', json.dumps(request))
            data = json.loads(request['messages'][1]['content'].split('\nUntrusted input data:\n')[1])
            case = cases[digest(data)]
            calls.append(deepcopy(request))
            if mode == 'error':
                raise TimeoutError('PRIVATE_TRANSPORT_ERROR_DO_NOT_PERSIST')
            if case['kind'] == 'facts':
                result = envelope('Invented fixture answer; this has not been scientifically reviewed.')
            else:
                label = references[case['id']]['expected']
                if mode == 'constant_support' or (mode == 'guided_wrong' and 'guided_choice' in request):
                    label = 'SUPPORT'
                result = envelope(label)
            if mode == 'model_mismatch':
                result['model'] = 'INVENTED_DIFFERENT_MODEL'
            if mode == 'thinking':
                message = result['choices'][0]['message']
                message['content'] = '<think>PRIVATE_REASONING_SENTINEL</think>\n' + message['content']
            return result

        # The injected transport is the sole permitted inference path in tests.
        with patch.object(diagnostic, 'request_once', side_effect=AssertionError('Unexpected live request')):
            with redirect_stdout(io.StringIO()):
                summary = diagnostic.run(self.packet, destination, stage, previous=previous, transport=transport)
        return destination, summary, calls

    def test_prepare_freezes_windows_and_references_without_overwrite(self):
        self.assertEqual(len(self.cases), 18)
        self.assertEqual(sum(c['kind'] == 'synthetic' for c in self.cases), 6)
        self.assertEqual(sum(c['kind'] == 'context' for c in self.cases), 8)
        self.assertEqual(sum(c['kind'] == 'facts' for c in self.cases), 4)
        ref_by_id = {r['id']: r for r in self.references}
        for case in self.cases:
            self.assertNotIn('expected', case)
            self.assertNotIn('expected_facts', case)
            ref = ref_by_id[case['id']]
            if case['kind'] == 'context' and ref['case'].startswith('prime') and ref['window'] == 'focused':
                row = case['data']['source'][1]
                self.assertEqual((row['parent_start'], row['parent_end']), (77, 461))
                self.assertEqual(len(row['text']), 384)
                self.assertIn('parent_text_sha256', row)
        with self.assertRaises(FileExistsError):
            diagnostic.prepare(self.context, self.packet)
        self.assertEqual(diagnostic.load_packet(self.packet)[0], self.manifest)

    def test_payload_pair_differs_only_by_decoding_and_excludes_reference_metadata(self):
        case = deepcopy(self.cases[0])
        # Extra reference metadata must not be serialized from case siblings.
        case['expected'] = 'REFERENCE_SENTINEL_DO_NOT_SEND'
        ordinary = diagnostic.payload(case, 'ordinary', self.protocol)
        guided = diagnostic.payload(case, 'guided', self.protocol)
        self.assertEqual(guided.pop('guided_choice'), diagnostic.LABELS)
        self.assertEqual(guided.pop('guided_decoding_backend'), 'xgrammar:no-fallback')
        self.assertEqual(ordinary, guided)
        self.assertNotIn('guided_json', ordinary)
        self.assertNotIn('response_format', ordinary)
        self.assertNotIn('REFERENCE_SENTINEL_DO_NOT_SEND', json.dumps(ordinary))
        self.assertEqual(ordinary['messages'][0], {'role': 'system', 'content': 'detailed thinking off'})
        self.assertEqual(ordinary['temperature'], 0)
        self.assertEqual(ordinary['max_tokens'], 128)
        reversed_payload = diagnostic.payload(case, 'reversed', self.protocol)
        reversed_payload.pop('guided_decoding_backend')
        self.assertEqual(reversed_payload.pop('guided_choice'), list(reversed(diagnostic.LABELS)))
        self.assertEqual(reversed_payload, ordinary)
        with self.assertRaises(ValueError):
            diagnostic.payload(case, 'not-an-arm', self.protocol)

    def test_exact_label_parser_rejects_prose_truncation_tools_and_refusals(self):
        case = self.cases[0]
        request = diagnostic.payload(case, 'ordinary', self.protocol)
        row = diagnostic.observe(case, 'ordinary', request, envelope(' \nSUPPORT\t'))
        self.assertEqual(row['status'], 'valid_label')
        self.assertEqual(row['label'], 'SUPPORT')
        invalid = [envelope('The answer is SUPPORT.'), envelope('SUPPORT', finish='length'),
                   envelope('SUPPORT', tool_calls=[{'id': 'invented'}]),
                   envelope('SUPPORT', function_call={'name': 'invented'}),
                   envelope('SUPPORT', refusal='refused'), envelope('SUPPORT', role='user'),
                   envelope(None), {'choices': []}, [], {'choices': None}]
        for raw in invalid:
            with self.subTest(raw=raw):
                result = diagnostic.observe(case, 'ordinary', request, raw)
                self.assertEqual(result['status'], 'invalid_output')
                self.assertNotIn('label', result)
                self.assertIsNone(result['final_text'])

    def test_reasoning_is_not_recovered_or_persisted(self):
        case = self.cases[0]
        request = diagnostic.payload(case, 'ordinary', self.protocol)
        secret = 'PRIVATE_REASONING_SENTINEL'
        for raw in (envelope('<think>' + secret + '</think>SUPPORT'),
                    envelope('SUPPORT', reasoning_content=secret),
                    envelope('SUPPORT', reasoning=secret)):
            with self.subTest(raw=raw):
                row = diagnostic.observe(case, 'ordinary', request, raw)
                self.assertEqual(row['status'], 'invalid_output')
                self.assertIsNone(row['final_text'])
                self.assertTrue(row['reasoning_wrapper_or_field'])
                self.assertNotIn('label', row)
                self.assertNotIn(secret, json.dumps(row))

    def test_native_reasoning_parser_accepts_only_declared_envelope_and_exact_final(self):
        case = self.cases[0]
        request = diagnostic.payload(case, 'ordinary', self.protocol)
        secret = 'PRIVATE_REASONING_SENTINEL'
        contract = 'native-thinking-final.v1'
        accepted = [envelope('<think>' + secret + '</think>\n SUPPORT '),
                    envelope('SUPPORT', reasoning_content=secret),
                    envelope('SUPPORT', reasoning=secret), envelope('<think></think>SUPPORT'),
                    envelope('SUPPORT')]
        for raw in accepted:
            with self.subTest(raw=raw):
                row = diagnostic.observe(case, 'ordinary', request, raw, reasoning_output=contract)
                self.assertEqual(row['status'], 'valid_label')
                self.assertEqual(row['label'], 'SUPPORT')
                self.assertEqual(row['reasoning_output'], contract)
                self.assertNotIn(secret, json.dumps(row))
                if secret in json.dumps(raw):
                    self.assertTrue(row['reasoning_present'])
                    self.assertEqual(row['reasoning_metadata'][0]['characters'], len(secret))
                    self.assertEqual(len(row['reasoning_metadata'][0]['sha256']), 64)
        rejected = [envelope('<think>' + secret), envelope(secret + '</think>SUPPORT'),
                    envelope('Preface<think>' + secret + '</think>SUPPORT'),
                    envelope('<think><think>' + secret + '</think></think>SUPPORT'),
                    envelope('<think>' + secret + '<THINK>nested</THINK></think>SUPPORT'),
                    envelope('<think>' + secret + '</think><think></think>SUPPORT'),
                    envelope('<think>' + secret + '</think><THINK>extra</THINK>SUPPORT'),
                    envelope('<THINK>' + secret + '</THINK>SUPPORT'),
                    envelope('<think>' + secret + '</think>SUPPORT', reasoning_content=secret),
                    envelope('SUPPORT', reasoning=secret, reasoning_content=secret),
                    envelope('SUPPORT', reasoning_content={'private': secret}),
                    envelope('<think>' + secret + '</think>The answer is SUPPORT.'),
                    envelope('<think>' + secret + '</think>SUPPORT', finish='length'),
                    envelope('<think>' + secret + '</think>SUPPORT', tool_calls=[{'id': 'invented'}])]
        for raw in rejected:
            with self.subTest(raw=raw):
                row = diagnostic.observe(case, 'ordinary', request, raw, reasoning_output=contract)
                self.assertEqual(row['status'], 'invalid_output')
                self.assertNotIn('label', row)
                self.assertIsNone(row['final_text'])
                self.assertNotIn(secret, json.dumps(row))
        untagged = diagnostic.observe(case, 'ordinary', request,
            envelope(secret + ' therefore SUPPORT'), reasoning_output=contract)
        self.assertEqual(untagged['status'], 'invalid_output')
        self.assertIsNone(untagged['final_text'])
        self.assertNotIn(secret, json.dumps(untagged))

    def test_reasoning_profile_has_six_ordinary_calls_strict_gate_and_no_guided_context(self):
        self.packet = self.root / 'thinking-packet'
        diagnostic.prepare(self.context, self.packet, profile='reasoning-on')
        self.manifest, self.cases, self.protocol = diagnostic.load_packet(self.packet)
        self.references = diagnostic.read(self.packet / 'references.json')
        self.assertEqual(self.protocol['system'], 'detailed thinking on')
        self.assertEqual(self.protocol['sampling']['temperature'], 0.6)
        self.assertEqual(self.protocol['sampling']['top_p'], 0.95)
        self.assertEqual(self.protocol['sampling']['seed'], 0)
        self.assertEqual(self.protocol['label_tokens'], 2048)
        self.assertEqual(self.protocol['fact_tokens'], 2048)
        self.assertEqual(self.protocol['classification_arms'], ['ordinary'])
        self.assertEqual(self.protocol['reasoning_output'], 'native-thinking-final.v1')
        for arm in ('guided', 'reversed'):
            with self.assertRaisesRegex(ValueError, 'ordinary output'):
                diagnostic.payload(self.cases[0], arm, self.protocol)
        synthetic, summary, calls = self.run_stage('thinking-synthetic', 'synthetic', mode='thinking')
        self.assertEqual(len(calls), 6)
        self.assertTrue(summary['synthetic_pass'])
        self.assertEqual(set(summary['arms']), {'ordinary'})
        self.assertEqual(summary['arms']['ordinary']['reference_matches'], 6)
        self.assertNotIn('PRIVATE_REASONING_SENTINEL', (synthetic / 'traces.json').read_text())
        diagnostic.verify_result(synthetic, packet=self.packet)
        context, compared, context_calls = self.run_stage('thinking-context', 'context', previous=synthetic, mode='thinking')
        self.assertEqual(len(context_calls), 12)
        self.assertTrue(all('guided_choice' not in r and 'guided_json' not in r and 'response_format' not in r
                            and r['max_tokens'] == 2048 for r in calls + context_calls))
        self.assertEqual(compared['arms']['ordinary']['cases'], 8)
        self.assertEqual(len(compared['fact_answers']), 4)
        self.assertIsNone(compared['synthetic_pass'])
        diagnostic.verify_result(context, packet=self.packet)
        with self.assertRaisesRegex(ValueError, 'no guided enum-order'):
            diagnostic.run(self.packet, self.root / 'thinking-order', 'order', previous=synthetic,
                           transport=lambda _: self.fail('Reasoning-on used guided decoding'))
        failed, failed_summary, failed_calls = self.run_stage('thinking-failed', 'synthetic', mode='constant_support')
        self.assertEqual(len(failed_calls), 6)
        self.assertFalse(failed_summary['synthetic_pass'])
        with self.assertRaisesRegex(ValueError, 'stop biological calls'):
            diagnostic.run(self.packet, self.root / 'thinking-blocked', 'context', previous=failed,
                           transport=lambda _: self.fail('Failed ordinary reasoning arm advanced'))

    def test_payload_uses_frozen_instruction_strings(self):
        protocol = deepcopy(self.protocol)
        protocol['classification_instructions'] = 'FROZEN CLASSIFICATION INSTRUCTION'
        protocol['extraction_instructions'] = 'FROZEN EXTRACTION INSTRUCTION'
        classified = diagnostic.payload(self.cases[0], 'ordinary', protocol)
        facts = next(c for c in self.cases if c['kind'] == 'facts')
        extracted = diagnostic.payload(facts, 'ordinary', protocol)
        self.assertTrue(classified['messages'][1]['content'].startswith('FROZEN CLASSIFICATION INSTRUCTION\n'))
        self.assertTrue(extracted['messages'][1]['content'].startswith('FROZEN EXTRACTION INSTRUCTION\n'))

    def test_few_shot_recipe_has_only_unrelated_examples_and_six_then_twelve_ordinary_calls(self):
        for profile in ('reasoning-off', 'reasoning-on'):
            with self.subTest(profile=profile):
                self.packet = self.root / ('few-shot-packet-' + profile)
                diagnostic.prepare(self.context, self.packet, profile=profile, recipe='few-shot')
                self.manifest, self.cases, self.protocol = diagnostic.load_packet(self.packet)
                self.references = diagnostic.read(self.packet / 'references.json')
                self.assertEqual(self.protocol['recipe'], 'few-shot')
                self.assertEqual(self.protocol['classification_arms'], ['ordinary'])
                self.assertEqual(self.protocol['primary_call_ceiling'], 18)
                self.assertEqual(self.protocol['conditional_order_ceiling'], 0)
                instructions = self.protocol['classification_instructions']
                self.assertIn('The crate contains three red balls and no blue balls.', instructions)
                self.assertEqual(instructions.count('Answer: '), 3)
                self.assertNotIn('ORCHID', instructions)
                self.assertNotIn('REFERENCE_SENTINEL_DO_NOT_SEND', instructions)
                for case in self.cases:
                    if case['kind'] != 'facts':
                        self.assertNotIn(case['data']['claim'], instructions)
                    request = diagnostic.payload(case, 'ordinary', self.protocol)
                    data = json.loads(request['messages'][1]['content'].split('\nUntrusted input data:\n')[1])
                    self.assertEqual(data, case['data'])
                    self.assertNotIn('expected', data)
                    self.assertNotIn('expected_facts', data)
                mode = 'thinking' if profile == 'reasoning-on' else 'correct'
                synthetic, summary, calls = self.run_stage('few-shot-synthetic-' + profile, 'synthetic', mode=mode)
                self.assertEqual(len(calls), 6)
                self.assertTrue(summary['synthetic_pass'])
                self.assertEqual(summary['recipe'], 'few-shot')
                context, compared, context_calls = self.run_stage('few-shot-context-' + profile, 'context',
                                                                  previous=synthetic, mode=mode)
                self.assertEqual(len(context_calls), 12)
                self.assertEqual(compared['arms']['ordinary']['reference_matches'], 8)
                self.assertEqual(len(compared['fact_answers']), 4)
                self.assertTrue(all('guided_choice' not in r and 'guided_json' not in r
                                    and 'response_format' not in r for r in calls + context_calls))
                diagnostic.verify_result(context, packet=self.packet)
                failed, failed_summary, failed_calls = self.run_stage('few-shot-failed-' + profile,
                                                                      'synthetic', mode='constant_support')
                self.assertEqual(len(failed_calls), 6)
                self.assertFalse(failed_summary['synthetic_pass'])
                with self.assertRaisesRegex(ValueError, 'stop biological calls'):
                    diagnostic.run(self.packet, self.root / ('few-shot-blocked-' + profile), 'context', previous=failed,
                                   transport=lambda _: self.fail('Failed few-shot gate made another call'))

    def test_native_guidance_constrains_only_final_segment_while_off_remains_label_only(self):
        for recipe in ('baseline', 'few-shot'):
            for profile in ('reasoning-off', 'reasoning-on'):
                with self.subTest(recipe=recipe, profile=profile):
                    packet = self.root / ('format-' + recipe + '-' + profile)
                    diagnostic.prepare(self.context, packet, profile=profile, recipe=recipe)
                    _, cases, protocol = diagnostic.load_packet(packet)
                    request = diagnostic.payload(cases[0], 'ordinary', protocol)
                    instructions = request['messages'][1]['content'].split('\nUntrusted input data:\n')[0]
                    if profile == 'reasoning-on':
                        self.assertIn(diagnostic.NATIVE_FINAL, instructions)
                        self.assertNotIn(diagnostic.FINAL_ONLY, instructions)
                        self.assertNotIn('Do not explain.', instructions)
                        self.assertIn('normal native response format', protocol['extraction_instructions'])
                    else:
                        self.assertIn(diagnostic.FINAL_ONLY, instructions)
                        self.assertNotIn(diagnostic.NATIVE_FINAL, instructions)
                        self.assertEqual(protocol['reasoning_output'], 'reject')

    def test_claim_free_fact_stage_has_four_ordinary_requests_without_a_synthetic_gate(self):
        destination, summary, calls = self.run_stage('facts-without-prior', 'facts')
        self.assertEqual(len(calls), 4)
        self.assertEqual(summary['requests'], 4)
        self.assertIsNone(summary['synthetic_pass'])
        self.assertIsNone(summary['scientific_accuracy'])
        self.assertEqual(summary['independent_human_labels'], 0)
        self.assertEqual(len(summary['fact_answers']), 4)
        self.assertTrue(all(row['complete_and_correctly_associated'] is None
                            for row in summary['fact_answers']))
        for request in calls:
            self.assertNotIn('guided_choice', request)
            self.assertNotIn('guided_json', request)
            self.assertNotIn('response_format', request)
            data = json.loads(request['messages'][1]['content'].split('\nUntrusted input data:\n')[1])
            self.assertEqual(set(data), {'question', 'source'})
            self.assertNotIn('claim', data)
            self.assertNotIn('expected_facts', data)
            self.assertNotIn('expected', data)
        traces = diagnostic.read(destination / 'traces.json')
        self.assertTrue(all(row['kind'] == 'facts' and row['arm'] == 'ordinary'
                            and row['status'] == 'completed_fact_answer'
                            and 'label' not in row and 'verdict' not in row for row in traces))
        execution = diagnostic.read(destination / 'execution.json')
        self.assertEqual(execution['stage'], 'facts')
        self.assertIsNone(execution['previous_result_sha256'])
        self.assertEqual(execution['graph_mutations'], 0)
        self.assertEqual(execution['planned_requests'], 4)
        diagnostic.verify_result(destination, packet=self.packet)

    def test_model_mismatch_cannot_yield_a_label_or_pass_the_synthetic_gate(self):
        case = self.cases[0]
        request = diagnostic.payload(case, 'ordinary', self.protocol)
        response = envelope('SUPPORT')
        response['model'] = 'INVENTED_DIFFERENT_MODEL'
        row = diagnostic.observe(case, 'ordinary', request, response)
        self.assertEqual(row['status'], 'model_mismatch')
        self.assertNotIn('label', row)
        destination, summary, calls = self.run_stage('wrong-model', 'synthetic', mode='model_mismatch')
        self.assertEqual(len(calls), 12)
        self.assertFalse(summary['synthetic_pass'])
        self.assertEqual(summary['arms']['ordinary']['valid'], 0)
        self.assertTrue(all(r['status'] == 'model_mismatch' and 'label' not in r
                            for r in diagnostic.read(destination / 'traces.json')))
        with self.assertRaisesRegex(ValueError, 'stop biological calls'):
            diagnostic.run(self.packet, self.root / 'model-mismatch-context', 'context', previous=destination,
                           transport=lambda _: self.fail('Wrong returned model advanced to context'))

    def test_predictions_close_before_scoring_and_stages_do_not_promote_scientific_labels(self):
        destination = self.root / 'synthetic'
        original_read = diagnostic.read

        def guarded_read(path):
            if Path(path) == self.packet / 'references.json':
                self.assertEqual(original_read(destination / 'execution.json')['status'], 'predictions_closed')
            return original_read(path)

        with patch.object(diagnostic, 'read', side_effect=guarded_read):
            synthetic, summary, calls = self.run_stage('synthetic', 'synthetic')
        self.assertTrue(summary['synthetic_pass'])
        self.assertEqual(summary['requests'], 12)
        self.assertEqual(len(calls), 12)
        traces = diagnostic.read(synthetic / 'traces.json')
        self.assertEqual([r['sequence'] for r in traces], list(range(1, 13)))
        self.assertEqual([r['arm'] for r in traces[:4]], ['ordinary', 'guided', 'guided', 'ordinary'])
        self.assertEqual(diagnostic.verify_result(synthetic)['packet_sha256'], self.manifest['packet_sha256'])
        context, compared, context_calls = self.run_stage('context-results', 'context', previous=synthetic)
        self.assertEqual(len(context_calls), 12)
        self.assertEqual(compared['arms']['guided']['reference_matches'], 8)
        self.assertEqual(len(compared['fact_answers']), 4)
        self.assertTrue(all(r['complete_and_correctly_associated'] is None for r in compared['fact_answers']))
        self.assertIsNone(compared['scientific_accuracy'])
        self.assertEqual(compared['independent_human_labels'], 0)
        execution = diagnostic.read(context / 'execution.json')
        self.assertEqual(execution['graph_mutations'], 0)
        self.assertEqual(execution['previous_result_sha256'], diagnostic.verify_result(synthetic)['result_sha256'])

    def test_failed_synthetic_stage_blocks_context_and_limits_order_probe_to_qualifying_cases(self):
        previous, summary, calls = self.run_stage('failed', 'synthetic', mode='guided_wrong')
        self.assertFalse(summary['synthetic_pass'])
        self.assertEqual(len(calls), 12)
        with self.assertRaisesRegex(ValueError, 'stop biological calls'):
            diagnostic.run(self.packet, self.root / 'forbidden-context', 'context', previous=previous,
                           transport=lambda _: self.fail('Blocked stage called a model'))
        self.assertFalse((self.root / 'forbidden-context').exists())
        order, order_summary, order_calls = self.run_stage('order', 'order', previous=previous)
        self.assertEqual(len(order_calls), 4)
        self.assertTrue(all(r['arm'] == 'reversed' for r in diagnostic.read(order / 'traces.json')))
        self.assertEqual(order_summary['requests'], 4)
        for call in order_calls:
            self.assertEqual(call['guided_choice'], list(reversed(diagnostic.LABELS)))

    def test_transport_errors_remain_in_denominator_without_retries_or_secret_text(self):
        destination, summary, calls = self.run_stage('errors', 'synthetic', mode='error')
        self.assertEqual(len(calls), 12)
        self.assertEqual(summary['requests'], 12)
        self.assertFalse(summary['synthetic_pass'])
        rows = diagnostic.read(destination / 'traces.json')
        self.assertTrue(all(r['status'] == 'transport_error' and r['error_type'] == 'TimeoutError' for r in rows))
        self.assertNotIn('PRIVATE_TRANSPORT_ERROR_DO_NOT_PERSIST', json.dumps(rows))
        self.assertEqual(summary['arms']['ordinary']['valid'], 0)
        self.assertEqual(summary['arms']['guided']['cases'], 6)

    def test_packet_and_closed_result_integrity_are_required_before_later_calls(self):
        previous, _, _ = self.run_stage('closed', 'synthetic')
        with self.assertRaisesRegex(ValueError, 'require the closed synthetic'):
            diagnostic.run(self.packet, self.root / 'missing-prior', 'context', transport=lambda _: self.fail())
        target = previous / 'traces.json'
        target.write_text(target.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'result bytes changed'):
            diagnostic.verify_result(previous)
        with self.assertRaises(ValueError):
            diagnostic.run(self.packet, self.root / 'bad-prior', 'context', previous=previous,
                           transport=lambda _: self.fail('Tampered prior called model'))
        target = self.packet / 'inputs.json'
        target.write_text(target.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'file bytes changed'):
            diagnostic.load_packet(self.packet)

    def test_source_changes_and_implementation_changes_require_a_new_freeze(self):
        target = self.context / 'inputs.json'
        target.write_text(target.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            diagnostic.prepare(self.context, self.root / 'changed-source')
        protocol = diagnostic.read(self.packet / 'protocol.json')
        protocol['code_sha256'] = '0' * 64
        write_json(self.packet / 'protocol.json', protocol)
        manifest = diagnostic.read(self.packet / 'packet.json')
        manifest['files']['protocol.json'] = diagnostic.sha(self.packet / 'protocol.json')
        manifest['packet_sha256'] = digest({k: v for k, v in manifest.items() if k != 'packet_sha256'})
        write_json(self.packet / 'packet.json', manifest)
        with self.assertRaisesRegex(ValueError, 'implementation changed'):
            diagnostic.load_packet(self.packet)

    def test_packet_replay_detects_changes_even_when_result_receipt_is_recomputed(self):
        def reseal_result(path):
            receipt = diagnostic.read(path / 'receipt.json')
            receipt['files'] = {name: diagnostic.sha(path / name) for name in receipt['files']}
            receipt['result_sha256'] = digest({k: v for k, v in receipt.items() if k != 'result_sha256'})
            write_json(path / 'receipt.json', receipt)

        changed_summary, _, _ = self.run_stage('changed-summary', 'synthetic')
        summary = diagnostic.read(changed_summary / 'summary.json')
        summary['synthetic_pass'] = False
        write_json(changed_summary / 'summary.json', summary)
        reseal_result(changed_summary)
        diagnostic.verify_result(changed_summary)
        with self.assertRaisesRegex(ValueError, 'summary replay changed'):
            diagnostic.verify_result(changed_summary, packet=self.packet)

        changed_request, _, _ = self.run_stage('changed-request', 'synthetic')
        requests = diagnostic.read(changed_request / 'requests.json')
        requests[0]['payload']['temperature'] = 0.5
        write_json(changed_request / 'requests.json', requests)
        execution = diagnostic.read(changed_request / 'execution.json')
        execution['request_inventory_sha256'] = digest(requests)
        write_json(changed_request / 'execution.json', execution)
        rows = diagnostic.read(changed_request / 'traces.json')
        rows[0]['request_sha256'] = digest(requests[0]['payload'])
        write_json(changed_request / 'traces.json', rows)
        reseal_result(changed_request)
        diagnostic.verify_result(changed_request)
        with self.assertRaisesRegex(ValueError, 'frozen request changed'):
            diagnostic.verify_result(changed_request, packet=self.packet)


if __name__ == '__main__':
    unittest.main()
