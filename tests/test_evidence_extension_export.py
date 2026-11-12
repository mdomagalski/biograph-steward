"""Invented publications test portable source integrity, not scientific accuracy."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biograph_steward.__main__ import main
from biograph_steward.assay_attachment import _capture, attach_assay
from biograph_steward.client import digest, write_json
from biograph_steward.evidence_extension import publish_extension
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import (MANIFEST_FILE, _input_names_valid, _packet_id,
    export_packet, load_packet, save_decisions, load_decisions)
from biograph_steward.graph import save_run
from biograph_steward.reviews import read_run, review_run
from test_assay_attachment import cohort_snapshot, make_publication as make_assay, _seal


def read(path):
    return json.loads(Path(path).read_text())


def make_publication(folder, kind):
    folder.mkdir()
    write_json(folder / 'source.json', {'kind': kind,
        'subject': 'UniProtKB:P00533',
        'object': 'UniProtKB:P31749' if kind == 'mapit' else 'UniProtKB:P04626',
        'description': 'Invented fixture only; no scientific measurement.'})
    manifest = {'format': 'invented-test-publication.v1',
        'source_license': {'source': 'Invented test data', 'license': 'CC0-1.0'},
        'files': {'source.json': sha(folder / 'source.json')}}
    write_json(folder / 'publication.json', _seal(manifest))


def load_fixture_publication(folder):
    manifest, files = _capture(folder, 'publication.json')
    return manifest, json.loads(files['source.json']), files


def prepare_fixture(snapshot, baseline, manifest, projection):
    kind = projection['kind']
    nodes = []
    if projection['object'] not in {n['id'] for n in baseline['nodes']}:
        nodes = [{'id': projection['object'], 'name': 'Invented additional protein',
                  'category': 'biolink:Protein', 'sym': 'INVENTED',
                  'identifier_mapped': True, 'source_identifier': projection['object'],
                  'url': None, 'tdl': None, 'data_kind': 'invented_tissue_test'}]
    eid = 'edge:' + digest({'publication': manifest['content_sha256'], 'kind': kind})[:20]
    edge = {'id': eid, 'subject': projection['subject'], 'object': projection['object'],
        'predicate': ('biograph:has_assay_observation_with' if kind == 'mapit'
                      else 'biograph:has_interaction_annotation'),
        'record_kind': 'tissue_proximity_observation' if kind == 'mapit' else 'protein_interaction',
        'status': 'passed_structural_checks', 'review_reasons': [],
        'aggregator': 'Invented fixture', 'primary_source_raw': 'Invented fixture',
        'reference_raw': None, 'publications': [], 'evidence_raw': None,
        'source_scores_raw': {}, 'evidence_record': deepcopy(projection),
        'record_locators': ['extension_sources/' + kind + '/source.json'],
        'duplicate_count': 0, 'snapshot_sha256': snapshot['content_sha256'],
        'data_kind': 'invented_tissue_test' if kind == 'mapit' else 'invented_string_test',
        'biologically_validated': False, 'symmetric': True,
        'qualifiers': {'evidence_type': 'invented_' + kind, 'observation_id': 'fixture:' + kind},
        'extension_source_kind': kind, 'extension_publication_sha256': manifest['content_sha256']}
    observation = {'id': 'fixture:' + kind, 'source_kind': kind,
                   'graph_edge_id': eid, 'note': projection['description']}
    return {'nodes': nodes, 'edges': [edge], 'observations': [observation],
            'summary': {'source_kind': kind, 'invented_observations': 1}}


class EvidenceExtensionExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source, self.run, self.packet = [self.root / n for n in ('source', 'extended', 'packet')]
        self.snapshot = cohort_snapshot()
        self.base = save_run(self.snapshot, self.source)
        self.publications = {k: self.root / ('publication_' + k) for k in ('string', 'mapit')}
        for kind, folder in self.publications.items():
            make_publication(folder, kind)
        adapter = SimpleNamespace(load_publication=load_fixture_publication,
                                  prepare=prepare_fixture, __file__=__file__)
        registry = patch('biograph_steward.evidence_extension._adapter', return_value=adapter)
        registry.start(); self.addCleanup(registry.stop)
        self.graph = publish_extension(self.source, self.publications, self.run)

    def command(self, *args):
        out, error = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(error):
            code = main([str(arg) for arg in args])
        return code, out.getvalue(), error.getvalue()

    def test_cli_explicit_replay_preserves_both_complete_sources(self):
        replay = self.root / 'cli_replay'
        code, _, error = self.command('replay', '--snapshot', self.run / 'snapshot.json',
                                      '--extension-run', self.run, '--out', replay)
        self.assertEqual((code, error), (0, ''))
        self.assertEqual(read_run(replay)[2], self.graph)
        before = {p.relative_to(self.run / 'extension_sources').as_posix(): p.read_bytes()
                  for p in (self.run / 'extension_sources').rglob('*') if p.is_file()}
        after = {p.relative_to(replay / 'extension_sources').as_posix(): p.read_bytes()
                 for p in (replay / 'extension_sources').rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual((replay / 'evidence_extension.json').read_bytes(),
                         (self.run / 'evidence_extension.json').read_bytes())

    def test_cli_replay_requires_explicit_extension_preservation(self):
        replay = self.root / 'cli_missing_flag'
        code, _, error = self.command('replay', '--snapshot', self.run / 'snapshot.json',
                                      '--out', replay)
        self.assertEqual(code, 1)
        self.assertIn('--extension-run', error)
        self.assertFalse(replay.exists())

    def rebind_outer(self):
        """Keep outer file hashes consistent to test the inner source contract."""
        manifest = read(self.packet / MANIFEST_FILE)
        manifest['graph_sha256'] = digest(read(self.packet / 'source/graph.json'))
        manifest['input_files'] = {n: sha(self.packet / 'source' / n) for n in manifest['input_files']}
        manifest['packet_id'] = _packet_id(manifest)
        template = read(self.packet / 'decisions.template.json')
        template['packet_id'] = manifest['packet_id']
        write_json(self.packet / 'decisions.template.json', template)
        manifest['files'] = {n: sha(self.packet / n) for n in manifest['files']}
        write_json(self.packet / MANIFEST_FILE, _seal(manifest))

    def test_complete_two_source_export_preserves_original_graph_and_bytes(self):
        before = {p.relative_to(self.run).as_posix(): p.read_bytes()
                  for p in self.run.rglob('*') if p.is_file()}
        manifest = export_packet(self.run, self.packet)
        self.assertEqual(load_packet(self.packet), (manifest, self.graph))
        self.assertEqual(manifest['counts']['extension_observations'], 2)
        self.assertIn('extension_observations.jsonl', manifest['files'])
        self.assertTrue(_input_names_valid(manifest['input_files']))
        for source in ('string', 'mapit'):
            self.assertIn('extension_sources/' + source + '/publication.json', manifest['input_files'])
            self.assertIn(source + '_source_projection', manifest['implementation_sha256'])
        for name in manifest['input_files']:
            self.assertEqual((self.packet / 'source' / name).read_bytes(), before[name])
        self.assertEqual((self.run / 'snapshot.json').read_bytes(), (self.source / 'snapshot.json').read_bytes())
        old = {r['id']: r for r in self.base['edges']}
        current = {r['id']: r for r in self.graph['edges']}
        self.assertTrue(all(current[k] == v for k, v in old.items()))
        self.assertEqual(before, {p.relative_to(self.run).as_posix(): p.read_bytes()
                                 for p in self.run.rglob('*') if p.is_file()})

    def test_portable_packet_does_not_rebuild_source_graph(self):
        export_packet(self.run, self.packet)
        for path in (self.run, self.source, *self.publications.values()):
            shutil.rmtree(path)
        with patch('biograph_steward.graph.build_graph', side_effect=AssertionError('No source graph rebuild')):
            self.assertEqual(load_packet(self.packet)[1], self.graph)

    def test_missing_extension_cannot_silently_drop_new_evidence(self):
        (self.run / 'evidence_extension.json').unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            export_packet(self.run, self.packet)
        self.assertFalse(self.packet.exists())

    def test_partial_source_inventory_is_rejected(self):
        names = {'snapshot.json', 'graph.json', 'run_manifest.json', 'review_events.json',
                 'evidence_extension.json', 'extension_sources/string/publication.json'}
        self.assertFalse(_input_names_valid(names))
        names.add('extension_observations.json')
        self.assertTrue(_input_names_valid(names))
        names.add('extension_sources/../../outside')
        self.assertFalse(_input_names_valid(names))

    def test_raw_source_tamper_fails_after_outer_reseal(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/extension_sources/mapit/source.json'
        path.write_bytes(path.read_bytes() + b'\nTAMPER')
        self.rebind_outer()
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            load_packet(self.packet)

    def test_resealed_extension_cannot_override_raw_publication(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/evidence_extension.json'
        value = read(path)
        value['sources']['mapit']['prepared']['observations'][0]['note'] = 'Invented altered observation'
        write_json(path, _seal(value)); self.rebind_outer()
        with self.assertRaisesRegex(ValueError, 'do not reproduce'):
            load_packet(self.packet)

    def test_resealed_graph_cannot_strengthen_proximity_to_direct_binding(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/graph.json'; graph = read(path)
        next(e for e in graph['edges'] if e.get('extension_source_kind') == 'mapit')['predicate'] = 'biolink:directly_physically_interacts_with'
        write_json(path, graph); self.rebind_outer()
        with self.assertRaisesRegex(ValueError, 'extension edges disagree'):
            load_packet(self.packet)

    def test_resealed_observation_ledger_cannot_omit_a_source(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/extension_observations.json'
        write_json(path, read(path)[:1]); self.rebind_outer()
        with self.assertRaisesRegex(ValueError, 'observation ledger disagrees'):
            load_packet(self.packet)

    def test_extra_marked_edge_is_not_accepted_as_baseline(self):
        export_packet(self.run, self.packet)
        path = self.packet / 'source/graph.json'; graph = read(path)
        extra = deepcopy(next(e for e in graph['edges'] if e.get('extension_source_kind') == 'mapit'))
        extra['id'] = 'edge:invented-duplicate'; graph['edges'].append(extra)
        write_json(path, graph); self.rebind_outer()
        with self.assertRaisesRegex(ValueError, 'extension edges disagree'):
            load_packet(self.packet)

    def test_explicit_prune_preserves_full_baseline_and_observation_trace(self):
        export_packet(self.run, self.packet)
        value = read(self.packet / 'decisions.template.json')
        eid = next(e['id'] for e in self.graph['edges'] if e.get('extension_source_kind') == 'mapit')
        value.update(actor='Invented reviewer', method='Invented explicit test decision')
        next(r for r in value['decisions'] if r['edge_id'] == eid).update(decision='prune',reason='Fixture only')
        decision, output = self.root / 'decisions.json', self.root / 'retained'
        write_json(decision, value); save_decisions(self.packet, decision, output)
        _, retained = load_decisions(output)
        self.assertEqual(retained['nodes'], self.graph['nodes'])
        self.assertNotIn(eid, {r['id'] for r in retained['edges']})
        obs = next(r for r in retained['extension_observations'] if r['source_kind'] == 'mapit')
        self.assertIsNone(obs['graph_edge_id']); self.assertEqual(obs['retention']['decision'], 'prune')
        self.assertEqual(load_packet(output / 'baseline_packet')[1], self.graph)
        self.assertTrue((output / 'retained_extension_observations.jsonl').is_file())

    def test_review_keeps_publication_identity_and_source_bytes(self):
        assertion = next(a for a in self.graph['assertions'] if a.get('extension_source_kind') == 'mapit')
        reviewed = self.root / 'reviewed'
        graph = review_run(self.run, reviewed, assertion['id'], 'provisional', 'Invented reviewer', 'Inspect fixture only')
        self.assertEqual(graph['review_events'][-1]['evidence_extension_sha256'], graph['evidence_extension_sha256'])
        export_packet(reviewed, self.packet)
        self.assertEqual(load_packet(self.packet)[1], graph)

    def test_old_assay_and_new_sources_have_complete_combined_licenses(self):
        old_publication, old_run = self.root / 'assay_pub', self.root / 'assay_run'
        make_assay(old_publication); attach_assay(self.source, old_publication, old_run)
        combined = self.root / 'combined'
        graph = publish_extension(old_run, self.publications, combined)
        manifest = export_packet(combined, self.packet)
        self.assertEqual(load_packet(self.packet), (manifest, graph))
        self.assertIn('assay_source/publication.json', manifest['input_files'])
        self.assertIn('extension_sources/mapit/publication.json', manifest['input_files'])
        self.assertEqual(len(read(self.packet / 'source/source_licenses.json')),
                         len(self.snapshot['source_licenses']) + 3)


if __name__ == '__main__':
    unittest.main()
