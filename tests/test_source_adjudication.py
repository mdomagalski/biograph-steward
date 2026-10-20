"""Invented source-context overlays; never human or scientific gold judgments."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.crc_pilot import (prepare_pilot, retrieve_pilot_literature, run_pilot,
                                      verify_pilot_result)
from biograph_steward.graph import save_run
from biograph_steward.literature import load_literature
from biograph_steward.source_adjudication import (adjudicate_source, paper_passages,
                                                validate_decision, verify_adjudication)
from test_civic import fixture
from test_crc_pilot import FakeVerifier, jats_xml, pubmed_xml
from test_evaluation import cases


def decision(item, passages):
    return {'format': 'biograph-steward.ai-context-decision.v1', 'author_kind': 'ai_assistant',
            'method': 'INVENTED software test, not source adjudication.', 'item_id': item['item_id'],
            'record_sha256': item['record_sha256'], 'pmid': item['pmid'], 'decision': 'unresolved_context',
            'summary': 'INVENTED <script>source-context</script> decision.',
            'proposed_scoped_summary': 'INVENTED proposed wording.',
            'findings': [{'id': 'test', 'status': 'not_established', 'explanation': 'INVENTED source gap.',
                          'sources': [{'locator': passages[0]['locator'], 'text_sha256': digest(passages[0]['text'])}]}],
            'reviewed_source_locators': [passages[0]['locator']],
            'limitations': ['INVENTED test only; not a scientific judgment.']}


class AdjudicationTests(unittest.TestCase):
    def test_decision_requires_ai_provenance_exact_record_and_source_bindings(self):
        record = {'id': 1, 'description': 'INVENTED'}
        item = {'item_id': 1, 'record_sha256': digest(record), 'source_record': record, 'pmid': '123'}
        passages = [{'locator': 'body1', 'text': 'INVENTED passage.'}]
        original = decision(item, passages)
        validate_decision(original, item, passages)
        for key, value in [('author_kind', 'human_expert'), ('record_sha256', 'wrong'), ('pmid', '456')]:
            changed = deepcopy(original); changed[key] = value
            with self.assertRaises(ValueError): validate_decision(changed, item, passages)
        changed = deepcopy(original); changed['scientific_gold_label'] = 'SUPPORT'
        with self.assertRaises(ValueError): validate_decision(changed, item, passages)
        changed = deepcopy(original); changed['findings'][0]['sources'][0]['text_sha256'] = 'wrong'
        with self.assertRaises(ValueError): validate_decision(changed, item, passages)
        changed = deepcopy(original); changed['reviewed_source_locators'] = ['invented locator']
        with self.assertRaises(ValueError): validate_decision(changed, item, passages)

    def test_caption_provenance_is_distinct_from_figure_image_review(self):
        paper = {'pmid': '123', 'abstract': [], 'full_text': [{'locator': '/article/body/p[1]', 'text': 'INVENTED'}]}
        raw = jats_xml('123').replace(b'</article>', b'<floats-group><fig id="F1"><caption><p>INVENTED caption.</p></caption></fig></floats-group></article>')
        passages = paper_passages(paper, raw)
        self.assertEqual(passages[-1]['locator'], '/article//fig[@id="F1"]/caption')
        self.assertEqual(passages[-1]['text'], 'INVENTED caption.')
        with self.assertRaises(ValueError): paper_passages(paper, jats_xml('456'))

    def test_overlay_retains_original_verdicts_traces_and_empty_human_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p, c = fixture()
            save_run(p, root / 'base'); save_run(p, root / 'enriched', civic_snapshot=c)
            prepare_pilot(root / 'base', root / 'enriched', root / 'packet', size=4, cases=cases())
            def transport(url):
                return pubmed_xml(url.split('id=')[-1].split(',')) if 'db=pubmed' in url else jats_xml(url.split('id=')[-1])
            retrieve_pilot_literature(root / 'packet', root / 'literature', transport=transport)
            run_pilot(root / 'packet', root / 'literature', root / 'pilot', mode='configured', verifier=FakeVerifier())
            original_files = {str(p.relative_to(root / 'pilot')): p.read_bytes() for p in (root / 'pilot').rglob('*') if p.is_file()}
            _, papers = load_literature(root / 'literature')
            item = json.loads((root / 'pilot/panel.json').read_text())[0]; paper = papers[item['pmid']]
            passages = paper_passages(paper, (root / 'literature' / (paper['pmcid'] + '.xml')).read_bytes())
            write_json(root / 'decision.json', decision(item, passages))
            result = adjudicate_source(root / 'pilot', root / 'literature', root / 'decision.json', root / 'overlay')
            self.assertEqual(result['human_scientific_labels'], 0)
            self.assertIsNone(result['scientific_accuracy'])
            self.assertEqual(result['original_verdicts_changed'], 0)
            self.assertFalse(result['source_scope']['figure_images_reviewed'])
            self.assertEqual(result['new_verifier_model_requests'], 0)
            self.assertEqual(json.loads((root / 'overlay/source_provenance.json').read_text())['license'], ['INVENTED TEST LICENSE'])
            verify_adjudication(root / 'overlay'); verify_pilot_result(root / 'pilot')
            for name, raw in original_files.items():
                self.assertEqual((root / 'pilot' / name).read_bytes(), raw)
            self.assertIn('&lt;script&gt;', (root / 'overlay/report.html').read_text())
            self.assertNotIn('<script>', (root / 'overlay/report.html').read_text())
            for trace in (root / 'overlay/traces').glob('*.json'):
                self.assertEqual(trace.read_bytes(), (root / 'pilot/traces' / trace.name).read_bytes())
            changed = json.loads((root / 'overlay/decision.json').read_text()); changed['author_kind'] = 'human_expert'
            write_json(root / 'overlay/decision.json', changed)
            with self.assertRaises(ValueError): verify_adjudication(root / 'overlay')


if __name__ == '__main__':
    unittest.main()
