"""Offline supplied-question controls; no corpus, model service or source calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from . import prepare, query
from .tools import SourceTools


def token_count(*_):
    return {'status': 'completed', 'within_budget': True, 'tokenizer_model_service_requests': 0}


class FakeClient:
    kind = 'injected_test_model'
    def __init__(self, actions):
        self.actions = iter(actions); self.calls = 0

    def generate(self, prompt, schema, policy, audit):
        self.calls += 1
        data = json.loads(prompt.partition('\nUntrusted input data:\n')[2])
        action = next(self.actions)
        if action == 'FAIL':
            return {'status': 'unavailable', 'private': '/private/NEVER_SHOW', 'credential': 'SECRET_TEST_KEY'}
        return {'status': 'completed', 'output': {**action, 'case_id': data['case_id']},
                'usage': {'prompt_tokens': 20, 'completion_tokens': 5, 'total_tokens': 25,
                          'SECRET_TEST_KEY': 1}}


class OperatorTests(unittest.TestCase):
    def fixture(self, root, *, partial=False):
        binary = root / 'not_executable'; binary.write_bytes(b'SYNTHETIC_ONLY')
        qualification = root / 'qualification.json'
        write_json(qualification, prepare.seal({'format': 'biograph-steward.biomcp-binary-qualification.v1',
            'binary': {'file': str(binary), 'sha256': sha(binary)},
            'private': '/private/NEVER_SHOW', 'credential': 'SECRET_TEST_KEY'}))
        calls = []
        def runner(args, folder):
            calls.append(args)
            native = {'query': 'synthetic', 'results': [
                {'pmid': '101', 'title': '<script>source-title</script>', 'source': 'pubmed',
                 'matched_sources': ['pubmed'], 'is_retracted': True},
                {'pmid': '102', 'title': 'Second source', 'source': 'pubmed', 'matched_sources': ['pubmed']}],
                'complete': not partial, 'source_plan': {'candidate_sources': ['pubmed'], 'enrichment_sources': []}}
            return {'stdout': json.dumps(native).encode(), 'stderr': b'', 'exit_code': 0, 'process_status': 'returned'}
        def fetcher(url):
            calls.append(url)
            return b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>101</PMID><Article>
                <ArticleTitle>Exact source</ArticleTitle><Abstract><AbstractText>BODY_NOT_FOR_HTML</AbstractText></Abstract>
                <PublicationTypeList><PublicationType>Retracted Publication</PublicationType></PublicationTypeList>
                </Article><CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn"/>
                </CommentsCorrectionsList></MedlineCitation></PubmedArticle></PubmedArticleSet>'''
        tools = SourceTools(qualification, sha(qualification), root / 'cache', runner=runner, fetcher=fetcher)
        return qualification, tools, calls

    def execute(self, root, question='Synthetic supplied question', *, mode='native', procedure='base', actions=(), partial=False):
        qualification, tools, calls = self.fixture(root, partial=partial)
        client = FakeClient(actions) if mode == 'agent' else None
        receipt = query.run(question, qualification, sha(qualification), mode, procedure,
                            root / 'cache', root / 'output', source_tools=tools, client=client,
                            token_counter=token_count)
        return receipt, (root / 'output/report.html').read_text(), calls, client

    def test_native_needs_neither_model_nor_reference_parser(self):
        with (tempfile.TemporaryDirectory() as temp,
              patch.object(query, '_client', side_effect=AssertionError('model used')),
              patch.object(prepare, 'projected_questions', side_effect=AssertionError('corpus used')),
              patch.dict(sys.modules, {'ijson': None})):
            receipt, html, calls, _ = self.execute(Path(temp), partial=True, procedure='reviewed')
        self.assertEqual(len(calls), 1)
        self.assertEqual(receipt['selection_state'], 'native_search_results')
        self.assertEqual(receipt['workflow_status'], 'partial')
        self.assertEqual(receipt['cost_observations']['model_generation_calls'], 0)
        self.assertIsNone(receipt['procedure_applied']); self.assertFalse(receipt['uses_reference_corpus'])
        self.assertIn('No language model was called', html); self.assertIn('partial', html)

    def test_failed_agent_keeps_papers_without_fabricating_final_selection(self):
        actions = [{'action': 'search_pubmed', 'query': 'synthetic'}, 'FAIL']
        with tempfile.TemporaryDirectory() as temp:
            receipt, html, calls, client = self.execute(Path(temp), mode='agent', actions=actions)
        self.assertEqual(client.calls, 2); self.assertEqual(len(calls), 1)
        self.assertEqual(receipt['final_model_pmids'], [])
        self.assertEqual(receipt['native_candidate_pmids'], ['101', '102'])
        self.assertEqual(receipt['selection_state'], 'no_valid_final_model_selection')
        self.assertIn('No valid final model selection', html)
        self.assertIn('https://pubmed.ncbi.nlm.nih.gov/101/', html)
        self.assertNotIn('SECRET_TEST_KEY', html); self.assertNotIn('/private/NEVER_SHOW', html)

    def test_valid_final_list_and_actual_abstract_identity_are_separate(self):
        actions = [{'action': 'search_pubmed', 'query': 'synthetic'},
                   {'action': 'get_abstract', 'pmid': '101'},
                   {'action': 'finish', 'ranked_pmids': ['102', '101']}]
        with tempfile.TemporaryDirectory() as temp:
            receipt, html, calls, client = self.execute(Path(temp), mode='agent', procedure='reviewed', actions=actions)
            self.assertEqual(receipt['content_sha256'], digest({k: v for k, v in receipt.items() if k != 'content_sha256'}))
            for name, row in receipt['files'].items():
                self.assertEqual(sha(Path(temp) / 'output' / name), row['sha256'])
        self.assertEqual(receipt['final_model_pmids'], ['102', '101']); self.assertEqual(client.calls, 3)
        self.assertEqual(len(calls), 2); self.assertTrue(receipt['duplicate_search_feedback'])
        self.assertEqual(receipt['budgets']['model_generation_calls'], 4)
        self.assertEqual(receipt['budgets']['output_tokens_per_call'], 1200)
        opened = receipt['abstract_inspections'][0]
        self.assertTrue(opened['identity_resolved']); self.assertTrue(opened['abstract_available'])
        self.assertEqual(opened['publication_types'], ['Retracted Publication'])
        self.assertIn('RetractionIn', opened['correction_types'])
        self.assertIn('Final model selection', html); self.assertIn('RetractionIn', html)
        self.assertIn('Retraction source flag: true', html)
        self.assertIn('Publication types: Retracted Publication; Correction types: RetractionIn', html)
        self.assertIn('not a clean bill of health', html)
        self.assertNotIn('BODY_NOT_FOR_HTML', html)

    def test_source_flags_are_plain_text_with_missing_and_empty_caveats(self):
        rows = [{'pmid': '101', 'title': 'Synthetic', 'record_link': 'workflow/tool_result.json',
                 'native_qualification_observations': [{'is_retracted': False},
                     {'publication_types': ['Journal Article', '<script>type</script>'], 'correction_types': []}]}]
        html = query._paper_list(rows)
        self.assertIn('Retraction source flag: false', html)
        self.assertIn('Publication types: Journal Article, &lt;script&gt;type&lt;/script&gt;', html)
        self.assertIn('Correction types: no values returned', html)
        self.assertIn('not independent clearance', html)
        self.assertIn('missing or empty metadata does not establish a clean status', html)
        self.assertNotIn('<script>', html); self.assertNotIn('is_retracted', html)
        rows[0]['native_qualification_observations'] = [{'publication_types': None, 'correction_types': None}]
        html = query._paper_list(rows)
        self.assertIn('Retraction source flag: not recorded', html)
        self.assertIn('Publication types: not recorded; Correction types: not recorded', html)

    def test_html_escapes_supplied_text_and_source_titles_without_raw_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            _, html, _, _ = self.execute(Path(temp), question='<img src=x onerror="bad">')
        self.assertIn('&lt;img', html); self.assertIn('&lt;script&gt;source-title', html)
        self.assertNotIn('<script>', html); self.assertNotIn('<img', html)
        self.assertNotIn('SECRET_TEST_KEY', html); self.assertNotIn('/private/NEVER_SHOW', html)
        self.assertIn(query.BOUNDARY, html)
        self.assertIn('Publication/retraction metadata not recorded or not checked', html)

    def test_invalid_final_does_not_trigger_native_fallback(self):
        actions = [{'action': 'search_pubmed', 'query': 'synthetic'},
                   {'action': 'finish', 'ranked_pmids': ['999']}]
        with tempfile.TemporaryDirectory() as temp:
            receipt, html, calls, client = self.execute(Path(temp), mode='agent', actions=actions)
        self.assertEqual(receipt['workflow_status'], 'invalid_action')
        self.assertEqual(receipt['final_model_pmids'], []); self.assertEqual(len(calls), 1)
        self.assertEqual(client.calls, 2); self.assertIn('Search candidates already captured', html)

    def test_duplicate_search_feedback_consumes_decision_without_source_retry(self):
        actions = [{'action': 'search_pubmed', 'query': 'synthetic'},
                   {'action': 'search_pubmed', 'query': 'synthetic'},
                   {'action': 'finish', 'ranked_pmids': ['101']}]
        with tempfile.TemporaryDirectory() as temp:
            receipt, _, calls, client = self.execute(Path(temp), mode='agent', actions=actions)
        self.assertEqual(client.calls, 3); self.assertEqual(len(calls), 1)
        self.assertEqual(receipt['final_model_pmids'], ['101'])
        self.assertEqual(receipt['cost_observations']['controller_rejected_action_attempts'], 1)
        self.assertEqual(receipt['cost_observations']['source_tool_invocations'], 1)

    def test_native_over_bound_query_is_explicit_and_not_silently_shortened(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt, html, calls, _ = self.execute(Path(temp), question='x' * 2001)
        self.assertEqual(receipt['workflow_status'], 'unsupported_query'); self.assertEqual(calls, [])
        self.assertEqual(receipt['native_candidate_pmids'], [])
        self.assertIn('Source search: unsupported empty/NUL/over2000character query.', html)

    def test_completed_empty_selection_is_explicit_while_candidates_remain(self):
        actions = [{'action': 'search_pubmed', 'query': 'synthetic'},
                   {'action': 'finish', 'ranked_pmids': []}]
        with tempfile.TemporaryDirectory() as temp:
            receipt, html, _, _ = self.execute(Path(temp), mode='agent', actions=actions)
        self.assertEqual(receipt['selection_state'], 'valid_final_model_selection')
        self.assertEqual(receipt['final_model_pmids'], [])
        self.assertEqual(receipt['native_candidate_pmids'], ['101', '102'])
        self.assertIn('Agent finished without selecting papers', html)
        self.assertIn('does not establish that relevant papers or biological evidence are absent', html)
        self.assertIn('https://pubmed.ncbi.nlm.nih.gov/101/', html)

    def test_only_own_bounded_search_reasons_are_shown(self):
        for reason, allowed in [('native non-JSON/timeout/process failure', True),
                                ('/private/NEVER_SHOW <script>SECRET_TEST_KEY</script>', False)]:
            with self.subTest(reason=reason):
                capture = {'tool': 'search_pubmed', 'status': 'unavailable', 'query': 'synthetic',
                           'reason': reason, 'candidates': [], 'native_error': '/private/NEVER_SHOW'}
                result = {'status': 'unavailable', 'ranked_pmids': []}
                view = query.presentation(result, [(capture, 'workflow/tool_result.json')], 'native')
                html = query.render_html('Synthetic', view, query._costs(result), 'base')
                self.assertEqual(view['searches'][0]['reason'] is not None, allowed)
                self.assertNotIn('/private/NEVER_SHOW', html)
                self.assertNotIn('SECRET_TEST_KEY', html)

    def test_untrusted_selection_shapes_fail_without_unhashable_errors(self):
        capture = {'tool': 'search_pubmed', 'status': 'completed', 'query': 'synthetic',
                   'candidates': [{'pmid': '101', 'title': 'Source'}]}
        for bad in ([{}], [[]], ['101', '101'], ['999']):
            with self.subTest(bad=bad):
                view = query.presentation({'status': 'completed', 'ranked_pmids': bad},
                                          [(capture, 'workflow/tool_result_1.json')], 'agent')
                self.assertEqual(view['selection_state'], 'no_valid_final_model_selection')
                self.assertEqual(view['native_candidate_pmids'], ['101'])

    def test_identity_flag_cannot_hide_a_different_opened_article(self):
        capture = {'tool': 'get_abstract', 'status': 'completed', 'pmid': '101',
                   'identity_resolved': True, 'record': {'pmid': '999', 'abstract': []}}
        with self.assertRaisesRegex(ValueError, 'identity'):
            query.presentation({'status': 'completed', 'ranked_pmids': []},
                               [(capture, 'workflow/tool_result_1.json')], 'agent')

    def test_nonlocal_or_credentialed_model_endpoint_is_rejected_without_client(self):
        with patch.object(query, 'JSONModelClient', side_effect=AssertionError('client constructed')):
            for endpoint in ('https://model.invalid/v1/chat/completions',
                             'http://user:secret@127.0.0.1:8011/v1/chat/completions'):
                with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                    query._client(endpoint)


if __name__ == '__main__':
    unittest.main()
