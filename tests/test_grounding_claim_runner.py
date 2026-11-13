"""Invented end-to-end packets exercise wiring, never benchmark outcomes."""
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from tools.grounding_claims import context, evaluate, run
from tools.grounding_claims.native import project_evidence
from tests.test_grounding_claim_native import Match, fake_agent


def seal(path, value):
    value = deepcopy(value)
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    write_json(path, value)
    return value


class InventedGrounder:
    calls = []

    def __init__(self, terms):
        self.adeft_disambiguators = {'PDK1': None}
        self.gilda_disambiguators = None

    def lookup(self, mention):
        return mention in {'PDK1', 'AKT1', 'A', 'B'}

    def ground(self, mention, *, context=None):
        self.calls.append((mention, context))
        engine = ('adeft' if mention == 'PDK1' else
                  'gilda' if mention == 'AKT1' else None)
        metadata = {'type': engine, 'score': .5} if engine and context else None
        return [Match({('HGNC', '2' if mention == 'B' else '1')},
                      disambiguation=metadata)]


class GroundingRunnerTests(unittest.TestCase):
    def packet(self, root):
        frame, contexts = root / 'frame', root / 'context'
        frame.mkdir()
        cases = []
        for index, (mention, pmid) in enumerate((('A', '1'), ('B', '2')), 1):
            source = {'source_api': 'invented', 'pmid': pmid,
                'text': 'Invented source sentence ' + mention + '.',
                'annotations': {'agents': {'raw_text': [mention],
                    'raw_grounding': [{'HGNC': str(index)}]}}}
            projected = project_evidence({'type': 'Invented'}, source,
                                         agent_factory=fake_agent)
            cases.append({'case_id': 'invented:' + str(index),
                'pa_hash': str(9007199254740993 + index),
                'source_hash': str(-9007199254740993 - index),
                'group_id': str(index) * 64, 'split': 'development',
                'pmid': pmid, 'input': projected})
        with gzip.open(frame / 'cases.jsonl.gz', 'wt', encoding='utf-8') as stream:
            for case in cases:
                stream.write(json.dumps(case) + '\n')
        seal(frame / 'report.json', {'format': run.FRAME_FORMAT,
            'label_categories_inspected': False, 'predictions_run': False,
            'primary_cases': 2, 'split_policy': 'Invented distinct groups.',
            'files': {'cases.jsonl.gz': sha(frame / 'cases.jsonl.gz')}})
        xml = (b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID>'
               b'<Article><ArticleTitle>Invented title</ArticleTitle><Abstract>'
               b'<AbstractText>Invented abstract.</AbstractText></Abstract></Article>'
               b'</MedlineCitation></PubmedArticle><PubmedArticle><MedlineCitation>'
               b'<PMID>2</PMID><Article><ArticleTitle>Title only</ArticleTitle>'
               b'</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>')
        context.capture_context(['1', '2'], contexts, transport=lambda _: xml, pace=0)
        terms = root / 'resources/gilda/1.6.1/grounding_terms.tsv.gz'
        terms.parent.mkdir(parents=True)
        terms.write_bytes(b'invented resource bytes, not native terms')
        model = terms.with_name('gilda_models.json.gz')
        model.write_bytes(b'invented model bytes, no native weights')
        adeft_home = root / 'adeft'
        adeft_files = []
        for suffix in ('grounding_dict.json', 'names.json', 'model.gz'):
            file = adeft_home / '0.13.0/models/PDK1' / ('PDK1_' + suffix)
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b'invented Adeft resource, no native weights')
            adeft_files.append(file)
        def resource(file):
            return {'local_file': str(file), 'bytes': file.stat().st_size,
                    'sha256': sha(file)}
        resources = root / 'resources.json'
        write_json(resources, {'resources': [resource(terms), resource(model)],
            'Adeft_models_included': True,
            'adeft': {'version': '0.13.0', 'cache_home': str(adeft_home),
                      'selected_shortforms': ['PDK1'],
                      'files': [resource(p) for p in adeft_files]}})
        curations = root / 'invented-curations.json'
        curations.write_text('[]')
        plan = root / 'plan.json'
        seal(plan, {'format': 'biograph-steward.grounding-claim-evaluation-freeze.v1',
            'curation_categories_or_predictions_inspected_before_freeze': False,
            'arms': list(run.ARMS), 'frame_report_sha256': sha(frame / 'report.json'),
            'contexts_manifest_sha256': sha(contexts / 'manifest.json'),
            'resource_receipt_sha256': sha(resources), 'raw_curations_sha256': sha(curations),
            'implementation_pins': {str(Path(run.__file__).absolute()): sha(run.__file__)}})
        return frame, contexts, resources, plan, curations, cases

    def fake_native(self):
        package = ModuleType('gilda')
        package.__path__ = []
        module = ModuleType('gilda.grounder')
        module.Grounder = InventedGrounder
        module.load_gilda_models = lambda: {'AKT1': object()}
        return {'gilda': package, 'gilda.grounder': module}

    def execute(self, packet, output):
        InventedGrounder.calls = []
        with patch.dict(sys.modules, self.fake_native()), patch.dict(os.environ), \
                patch.object(run.importlib.metadata, 'version',
                             side_effect=lambda key: run.NATIVE_VERSIONS[key]):
            return run.run(*packet[:4], output, split='development')

    def test_fixed_arms_preserve_exact_inputs_and_missing_abstract_abstains(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = self.packet(root)
            report = self.execute(packet, root / 'predictions')
            self.assertEqual(report['cases'], 2)
            self.assertFalse(report['curation_labels_opened'])
            self.assertEqual(report['status_counts']['publication'],
                             {'no_conflict': 1, 'unresolved': 1})
            with gzip.open(root / 'predictions/predictions.jsonl.gz', 'rt') as stream:
                rows = [json.loads(line) for line in stream]
            self.assertEqual(rows[0]['pa_hash'], packet[-1][0]['pa_hash'])
            self.assertEqual(rows[0]['source_hash'], packet[-1][0]['source_hash'])
            for row in rows:
                self.assertEqual(set(row['predictions']), set(run.ARMS))
                self.assertEqual(row['predictions']['lexical']['context_kind'], 'none')
                self.assertEqual(row['predictions']['sentence']['context_kind'], 'evidence_text')
            self.assertEqual(rows[0]['predictions']['publication']['context_kind'],
                             'provided_context_text')
            self.assertEqual(rows[1]['predictions']['publication']['context_kind'],
                             'unavailable_publication_context')
            self.assertEqual([c for c in InventedGrounder.calls if c[0] == 'B'],
                             [('B', None), ('B', 'Invented source sentence B.')])

    def test_pinned_resource_tamper_rejected_before_native_or_label_use(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = self.packet(root)
            receipt = json.loads(packet[2].read_text())
            Path(receipt['resources'][0]['local_file']).write_bytes(b'changed')
            with patch.object(evaluate, 'label_pairs') as labels:
                with self.assertRaisesRegex(ValueError, 'native model resource differs'):
                    self.execute(packet, root / 'predictions')
                labels.assert_not_called()

    def test_evaluation_rejects_source_identity_mismatch_before_reading_tags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = self.packet(root)
            self.execute(packet, root / 'predictions')
            path = root / 'predictions/predictions.jsonl.gz'
            with gzip.open(path, 'rt') as stream:
                rows = [json.loads(line) for line in stream]
            rows[0]['source_hash'] = '0'
            with gzip.open(path, 'wt') as stream:
                for row in rows:
                    stream.write(json.dumps(row) + '\n')
            report_path = root / 'predictions/report.json'
            report = json.loads(report_path.read_text())
            report['files']['predictions.jsonl.gz'] = sha(path)
            seal(report_path, report)
            with patch.object(evaluate, 'label_pairs') as labels:
                with self.assertRaisesRegex(ValueError, 'identity/input differs'):
                    evaluate.evaluate(packet[0], root / 'predictions', packet[4],
                                      packet[3], root / 'evaluation')
                labels.assert_not_called()


if __name__ == '__main__':
    unittest.main()
