"""Synthetic archive checks for answer-only support filtering and native export."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from biograph_steward.client import digest
from biograph_steward.questions import answer_question, graph_basis, save_answer, verify_answer, verify_pathway_files
from biograph_steward.wiki_history import inspect_model, assess_subject
import test_qualified_workspace as source_fixture
from test_cohort_mapping import gene, protein, registry
from test_pathway_history_models import model_xml


class NativePathwayQuestionTests(unittest.TestCase):
    def setUp(self):
        source_fixture.QualifiedWorkspaceTests.setUp(self)
        self.native = self.root/'native'
        (self.native/'models').mkdir(parents=True)
        (self.native/'archives').mkdir()
        products = [t['id'].split(':', 1)[1] for t in self.graph['targets']]
        self.reg = registry([gene('HGNC:1', 'ONE', products=products[0]), gene('HGNC:2', 'TWO', products=products[1])],
            [protein(products[0], 'HGNC:1', 'ONE'), protein(products[1], 'HGNC:2', 'TWO')])
        self.packet = {'directory': self.native, 'report': {'content_sha256': 'a'*64, 'files': {}},
            'registry': self.reg, 'resources': {}, 'connections': {}}
        archive = self.native/'archives/invented.zip'
        models = {}
        with zipfile.ZipFile(archive, 'w') as zipped:
            for full_id, second in [('WP1_r10', True), ('WP1_r11', False), ('WP2_r20', False)]:
                extra = ('<DataNode GraphId="two" Type="GeneProduct"><Xref Database="Entrez Gene" ID="2"/></DataNode>'
                    if second else '')
                raw = model_xml(extras=extra)
                wpid, revision = full_id.split('_r')
                member = 'Hs_Invented_'+wpid+'_'+revision+'.gpml'
                zipped.writestr(member, raw)
                path = 'models/'+full_id+'.gpml'
                (self.native/path).write_bytes(raw)
                schema = {'executed': True, 'passed': True, 'synthetic_software_fixture': True}
                model = inspect_model(raw, full_source_id=full_id, archive_member=member,
                    validate=lambda raw: deepcopy(schema))
                models[full_id] = (model, path, member, schema)
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.packet['report']['files']['archives/invented.zip'] = archive_sha
        for full_id, (model, path, member, schema) in models.items():
            self.packet['report']['files'][path] = model['gpml_sha256']
            resource = {'status': 'exact_publisher_revision_content_available', 'native_model_file': path,
                'gpml_sha256': model['gpml_sha256'], 'official_schema_validation': schema,
                'candidates': [{'portable_archive_file': 'archives/invented.zip', 'archive_sha256': archive_sha,
                    'archive_member': member, 'source_url': 'https://example.org/invented.zip'}]}
            self.packet['resources'][full_id] = resource
            for target in self.graph['targets']:
                uid = target['id']
                edges = [e for e in self.graph['edges'] if e['subject'] == uid
                    and e.get('evidence_record', {}).get('sourceID') == full_id]
                if edges:
                    self.packet['connections'][(uid, full_id)] = {**assess_subject(uid, model, self.reg),
                        'original_edge_ids': [e['id'] for e in edges], 'native_model_sha256': model['gpml_sha256']}
        self.graph['qualified_view']['pathway_history'] = {'content_sha256': 'a'*64}
        self.graph['qualified_view']['source_support_default'] = 'native_supported'
        self.graph['question_basis_sha256'] = graph_basis(self.graph)

    def question(self, **kwargs):
        return answer_question(self.graph, self.protein, template='qualified_pathway_source_context.v1',
            view='candidates', source_run='qualified', pathway_history_source=self.packet, **kwargs)

    def test_native_support_filters_the_answer_and_preserves_unknown_graph_edges(self):
        before = deepcopy(self.graph)
        answer = self.question()
        self.assertEqual(answer['results'][0]['eligible_path_count'], 1)
        self.assertEqual({c['source_model_id'] for c in answer['citations']}, {'WP1_r10'})
        self.assertTrue(all(c['historical_contents_verified_in_this_answer'] for c in answer['citations']))
        self.assertEqual(self.graph, before)
        all_source = self.question(source_support='all_source_annotations')
        self.assertEqual(all_source['results'][0]['eligible_path_count'], 2)
        self.assertTrue(any(c['historical_source']['status'] == 'unresolved' for c in all_source['citations']))

    def test_native_source_packet_is_required_and_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, 'exact archived pathway proof'):
            answer_question(self.graph, self.protein, template='qualified_pathway_source_context.v1')

    def test_saved_native_bytes_and_fields_are_replayable(self):
        answer = self.question()
        verify_answer(answer)
        save_answer(answer, self.root/'native_answer')
        path = self.root/'native_answer/historical_models/WP1_r10.gpml'
        self.assertEqual(path.read_bytes(), (self.native/'models/WP1_r10.gpml').read_bytes())
        self.assertTrue((path.parent/'provenance.json').is_file())
        altered = deepcopy(answer)
        altered['citations'][0]['historical_source']['model']['native_organism'] = 'Invented other species'
        altered['answer_sha256'] = digest({k: v for k, v in altered.items() if k != 'answer_sha256'})
        with self.assertRaisesRegex(ValueError, 'do not replay'):
            verify_answer(altered)

    def test_wrong_archive_member_bytes_stop_source_answer(self):
        archive = self.native/'archives/invented.zip'
        archive.write_bytes(b'not the pinned archive')
        with self.assertRaisesRegex(ValueError, 'archive changed'):
            self.question()

    def test_saved_exports_verify_without_scratch_and_still_reject_tampering(self):
        answer = self.question()
        original_answer = deepcopy(answer)
        directory = self.root/'read_only_answer'
        save_answer(answer, directory)
        files_before = {p.relative_to(directory): p.read_bytes()
                        for p in directory.rglob('*') if p.is_file()}
        ordinary_open = Path.open

        def read_only_open(path, mode='r', *args, **kwargs):
            if any(flag in mode for flag in 'wax+'):
                raise AssertionError('Saved-question verification must not write files')
            return ordinary_open(path, mode, *args, **kwargs)

        def verify_read_only():
            with patch('tempfile.TemporaryDirectory', side_effect=AssertionError('No scratch directory')), \
                    patch('tempfile.mkdtemp', side_effect=AssertionError('No scratch directory')), \
                    patch.object(Path, 'open', new=read_only_open):
                verify_pathway_files(answer, directory)

        verify_read_only()
        self.assertEqual(answer, original_answer)
        self.assertEqual({p.relative_to(directory): p.read_bytes()
                          for p in directory.rglob('*') if p.is_file()}, files_before)
        target = directory/'paths.tsv'
        original_paths = target.read_bytes()
        target.write_bytes(original_paths + b'INVENTED ALTERED EXPORT\n')
        with self.assertRaisesRegex(ValueError, 'paths.tsv'):
            verify_read_only()
        target.write_bytes(original_paths)
        verify_read_only()


if __name__ == '__main__':
    unittest.main()
