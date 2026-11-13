"""Invented source/resource packets; no biological labels, models or network."""
from io import BytesIO
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from tools.grounding_claims import context, reproduce as subject, run


class Response(BytesIO):
    status = 200
    url = 'https://example.org/invented'


def seal(path, value):
    value = dict(value)
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    write_json(path, value)
    return value


class ReproductionTests(unittest.TestCase):
    def test_signed_identity_preserves_large_integer_and_rejects_normalization(self):
        self.assertEqual(subject.exact_id(-9007199254740993), '-9007199254740993')
        for bad in [True, False, 1.0, '01', '-0', '+1', ' 1', '1 ', None]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                subject.exact_id(bad)

    def test_exact_capture_and_overwrite_refusal(self):
        raw = b'invented source bytes'
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'source'
            with patch.object(subject, 'urlopen', return_value=Response(raw)):
                receipt = subject.download('https://example.org/invented', path,
                    expected_bytes=len(raw), md5=hashlib.md5(raw).hexdigest(),
                    sha256=hashlib.sha256(raw).hexdigest())
            self.assertTrue(receipt['success'])
            self.assertEqual(path.read_bytes(), raw)
            with patch.object(subject, 'urlopen') as network, self.assertRaises(ValueError):
                subject.download('https://example.org/invented', path, cap=100)
            network.assert_not_called()
            self.assertEqual(path.read_bytes(), raw)

    def test_wrong_publisher_checksum_or_size_preserves_failed_capture(self):
        raw = b'invented reference bytes'
        variants = [{'expected_bytes': len(raw), 'md5': '0' * 32},
                    {'expected_bytes': len(raw), 'sha256': '0' * 64},
                    {'expected_bytes': len(raw) + 1}, {'cap': 3}]
        for arguments in variants:
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as td:
                path = Path(td) / 'source'
                with patch.object(subject, 'urlopen', return_value=Response(raw)), self.assertRaises(ValueError):
                    subject.download('https://example.org/invented', path, **arguments)
                self.assertFalse(path.exists())
                self.assertTrue(path.with_name('source.part').exists())
                receipt = json.loads(path.with_name('source.receipt.json').read_text())
                self.assertFalse(receipt['success'])
                self.assertTrue(receipt['partial_file_preserved'])

    def packet(self, root):
        # Not JSON: successful freeze proves reference values are never decoded.
        curations = root / 'invented-reference'
        curations.write_bytes(b'invented opaque reference bytes, never decode as labels')
        reference_hash = sha(curations)
        join = root / 'join_report.json'
        seal(join, {'source_compressed_SHA256': subject.CORPUS_SHA,
            'curations_SHA256': reference_hash, 'all_original_pair_IDs_joined': True,
            'curation_tag_comment_or_correctness_fields_used': False,
            'grounder_or_model_predictions_run': False})
        frame = root / 'frame'
        frame.mkdir()
        cases = [{'case_id': 'invented:' + str(i), 'group_id': str(i) * 64,
                  'split': split, 'pmid': str(i)}
                 for i, split in [(1, 'development'), (2, 'test')]]
        with gzip.open(frame / 'cases.jsonl.gz', 'wt') as stream:
            for row in cases:
                stream.write(json.dumps(row) + '\n')
        here = Path(subject.__file__).parent
        seal(frame / 'report.json', {'format': run.FRAME_FORMAT,
            'label_categories_inspected': False, 'predictions_run': False,
            'primary_cases': 2, 'split_seed': 'invented', 'split_policy': 'invented disjoint components',
            'implementation_sha256': sha(here / 'prepare.py'),
            'native_adapter_sha256': sha(here / 'native.py'),
            'input_files_sha256': {str(join): sha(join)},
            'files': {'cases.jsonl.gz': sha(frame / 'cases.jsonl.gz')}})
        contexts = root / 'contexts'
        xml = b'<PubmedArticleSet>' + b''.join(
            b'<PubmedArticle><MedlineCitation><PMID>' + str(i).encode() + b'</PMID>'
            b'<Article><ArticleTitle>Invented title</ArticleTitle><Abstract>'
            b'<AbstractText>Invented source context.</AbstractText></Abstract>'
            b'</Article></MedlineCitation></PubmedArticle>' for i in (1, 2)) + b'</PubmedArticleSet>'
        context.capture_context(['1', '2'], contexts, transport=lambda _: xml, pace=0)
        gilda = root / 'gilda/1.6.1'
        gilda.mkdir(parents=True)
        native_rows, native_hashes = [], {}
        for name in subject.GILDA_RESOURCE_HASHES:
            path = gilda / name
            path.write_bytes(b'invented resource bytes for ' + name.encode())
            native_rows.append({'local_file': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)})
            native_hashes[name] = sha(path)
        home = root / 'adeft'
        asset = home / '0.13.0/models/TEST/TEST_model.gz'
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b'invented Adeft asset; never load as a model')
        receipt = root / 'resources.json'
        write_json(receipt, {'grounding_predictions_run': False, 'Adeft_models_included': True,
            'resources': native_rows, 'adeft': {'version': '0.13.0', 'cache_home': str(home),
            'selected_shortforms': ['TEST'], 'files': [
                {'local_file': str(asset), 'bytes': asset.stat().st_size, 'sha256': sha(asset)}]}})
        return {'frame': frame, 'contexts': contexts, 'resource_receipt': receipt,
            'curations': curations, 'output': root / 'local-freeze.json'}, reference_hash, native_hashes

    def invoke(self, arguments, reference_hash, native_hashes, **extra):
        with patch.object(subject, 'CURATIONS_SHA', reference_hash), \
                patch.object(subject, 'GILDA_RESOURCE_HASHES', native_hashes), \
                patch.object(subject.importlib.metadata, 'version', side_effect=lambda name: run.NATIVE_VERSIONS[name]):
            return subject.freeze(**arguments, acknowledge_source_only=True, **extra)

    def test_freeze_requires_explicit_declaration_before_opening_paths(self):
        with self.assertRaisesRegex(ValueError, 'acknowledge-source-only'):
            subject.freeze('missing', 'missing', 'missing', 'missing', 'missing')

    def test_local_freeze_contract_and_parent_do_not_require_old_absolute_paths(self):
        with tempfile.TemporaryDirectory() as td:
            arguments, reference_hash, native_hashes = self.packet(Path(td))
            first = self.invoke(arguments, reference_hash, native_hashes)
            self.assertFalse(first['curation_categories_or_predictions_inspected_before_freeze'])
            self.assertFalse(first['source_only_acknowledgement']['independently_verified_blinding'])
            self.assertEqual(first['arms'], list(run.ARMS))
            self.assertEqual(first['split']['development_cases'], 1)
            self.assertEqual(first['split']['reserved_test_cases'], 1)
            self.assertEqual(run.sealed(arguments['output']), first)
            parent = Path(td) / 'published-parent.json'
            first['implementation_pins'] = {'/nonexistent/old-checkout/' + Path(p).name: h
                for p, h in first['implementation_pins'].items()}
            seal(parent, first)
            arguments['output'] = Path(td) / 'relocated-freeze.json'
            second = self.invoke(arguments, reference_hash, native_hashes, parent_freeze=parent)
            self.assertTrue(second['parent_freeze_reference']['implementation_content_hashes_match'])
            self.assertTrue(second['parent_freeze_reference']['reproduction_is_not_new_independent_validation'])

    def test_freeze_rejects_reference_frame_context_resource_and_producer_tampering(self):
        for kind in ('reference', 'frame', 'context', 'resource', 'producer', 'join_source'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                arguments, reference_hash, native_hashes = self.packet(Path(td))
                if kind == 'reference':
                    arguments['curations'].write_bytes(b'changed opaque reference')
                elif kind == 'frame':
                    with (arguments['frame'] / 'cases.jsonl.gz').open('ab') as stream:
                        stream.write(b'changed compressed source')
                elif kind == 'context':
                    (arguments['contexts'] / 'pubmed_batch_0001.xml').write_bytes(b'changed source XML')
                elif kind == 'resource':
                    receipt = json.loads(arguments['resource_receipt'].read_text())
                    Path(receipt['resources'][0]['local_file']).write_bytes(b'changed model bytes')
                elif kind == 'producer':
                    report = json.loads((arguments['frame'] / 'report.json').read_text())
                    report['implementation_sha256'] = '0' * 64
                    seal(arguments['frame'] / 'report.json', report)
                else:
                    join = Path(td) / 'join_report.json'
                    report = json.loads(join.read_text())
                    report['source_compressed_SHA256'] = '0' * 64
                    seal(join, report)
                    report = json.loads((arguments['frame'] / 'report.json').read_text())
                    report['input_files_sha256'][str(join)] = sha(join)
                    seal(arguments['frame'] / 'report.json', report)
                with self.assertRaises(ValueError):
                    self.invoke(arguments, reference_hash, native_hashes)
                self.assertFalse(arguments['output'].exists())

    def test_freeze_refuses_to_overwrite_prior_contract(self):
        with tempfile.TemporaryDirectory() as td:
            arguments, reference_hash, native_hashes = self.packet(Path(td))
            self.invoke(arguments, reference_hash, native_hashes)
            before = arguments['output'].read_bytes()
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                self.invoke(arguments, reference_hash, native_hashes)
            self.assertEqual(arguments['output'].read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
