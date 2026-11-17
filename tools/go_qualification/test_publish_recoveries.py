"""Invented source-adapter boundary; real graph/Gold/disposition replay."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.evidence_extension import publish_extension
from biograph_steward.graph import save_run
from biograph_steward.normalization import GO_CATEGORIES
from biograph_steward.reviews import review_run
from tools.go_qualification import publish_recoveries as producer


class RecoveryPublicationTests(unittest.TestCase):
    def setUp(self):
        from test_assay_attachment import cohort_snapshot
        from test_evidence_extension_export import (make_publication, load_fixture_publication,
                                                    prepare_fixture)
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.snapshot = cohort_snapshot()
        self.make_publication = make_publication
        self.load_fixture = load_fixture_publication
        self.prepare_fixture = prepare_fixture
        self.base = self.root / 'base'
        save_run(self.snapshot, self.base)
        self.old_publications = {k: self.root / ('publication_' + k) for k in ('string', 'mapit')}
        for kind, folder in self.old_publications.items():
            make_publication(folder, kind)
        self.collision = False
        adapter = SimpleNamespace(load_publication=load_fixture_publication,
                                  prepare=self.prepare, __file__=__file__)
        self.adapter = adapter
        registry = patch('biograph_steward.evidence_extension._adapter', return_value=adapter)
        registry.start(); self.addCleanup(registry.stop)
        self.source = self.root / 'original'
        self.graph = publish_extension(self.base, self.old_publications, self.source)
        self.packet = self.root / 'original_packet'
        manifest = gold_packet.export_packet(self.source, self.packet)
        self.decisions = gold_packet._read(self.packet / 'decisions.template.json')
        self.decisions.update(method='invented policy', actor='invented test operator')
        self.decisions['decisions'][0].update(decision='prune', reason='Invented source qualification')
        write_json(self.root / 'old_decisions.json', self.decisions)
        self.retained = self.root / 'original_retained'
        gold_packet.save_decisions(self.packet, self.root / 'old_decisions.json', self.retained)
        self.inputs = [self.root / n for n in ('census', 'qualification', 'context')]
        for folder in self.inputs:
            folder.mkdir()
        self.go_adapter = SimpleNamespace(publish_recoveries=self.publish_go)
        module = patch.dict('sys.modules', {'biograph_steward.goa_source': self.go_adapter})
        module.start(); self.addCleanup(module.stop)
        # from-package imports may otherwise retain a previously loaded module.
        package = patch('biograph_steward.goa_source', self.go_adapter, create=True)
        package.start(); self.addCleanup(package.stop)

    def prepare(self, snapshot, baseline, manifest, projection):
        if projection['kind'] != 'goa':
            return self.prepare_fixture(snapshot, baseline, manifest, projection)
        projection = {**projection, 'object': 'GO:1234567'}
        result = self.prepare_fixture(snapshot, baseline, manifest, projection)
        result['nodes'] = [{'id': 'GO:1234567', 'name': 'Invented native test process',
            'category': GO_CATEGORIES['P'], 'go_aspect': 'P', 'identifier_mapped': True}]
        e = result['edges'][0]
        e.update(record_kind='native_go_annotation', predicate='biograph:has_native_go_annotation',
                 symmetric=False, qualifiers={'go_aspect': 'P', 'go_relation': 'involved_in',
                    'species': 'NCBITaxon:9606', 'observation_id': 'fixture:goa'})
        if self.collision:
            e['id'] = self.graph['edges'][0]['id']
        return result

    def publish_go(self, census, qualification, retained_package, context, output, *, census_sha256):
        self.make_publication(Path(output), 'goa')
        return self.load_fixture(output)[0]

    def build(self, output='prepared'):
        return producer.build_recoveries(self.inputs[0], self.inputs[1], self.retained,
            self.inputs[2], self.root / output, census_sha256='a' * 64)

    def test_preserves_exact_old_payloads_decision_rows_and_source_bytes(self):
        before = producer.inventory(self.retained)
        result = self.build()
        folder = self.root / 'prepared'
        loaded, graph, retained = producer.load_prepared(folder)
        self.assertEqual(loaded, result)
        self.assertEqual(producer.inventory(self.retained), before)
        self.assertEqual(result['preservation']['added_edges'], 1)
        self.assertEqual(result['preservation']['added_nodes'], 1)
        self.assertTrue(result['preservation']['extension_container_binding_changed'])
        current_decisions = gold_packet._read(folder / 'retained/decisions.json')
        self.assertEqual(current_decisions['decisions'][:-1], self.decisions['decisions'])
        self.assertEqual(current_decisions['decisions'][-1]['decision'], 'abstain')
        old = {e['id']: e for e in self.graph['edges']}
        self.assertEqual({e['id']: e for e in graph['edges'] if e['id'] in old}, old)
        self.assertEqual(graph['review_events'], [])
        for kind, pub in self.old_publications.items():
            self.assertEqual(producer.inventory(pub), producer.inventory(folder / 'raw_run/extension_sources' / kind))
        self.assertEqual((folder / 'raw_run/snapshot.json').read_bytes(), (self.source / 'snapshot.json').read_bytes())
        self.assertEqual(len(retained['edges']), len(graph['edges']) - 1)
        self.assertFalse((folder / 'workspace').exists())

    def test_edge_id_collision_fails_without_publishing_or_modifying_old_package(self):
        before = producer.inventory(self.retained)
        self.collision = True
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            self.build()
        self.assertFalse((self.root / 'prepared').exists())
        self.assertEqual(producer.inventory(self.retained), before)

    def test_extension_bound_accepted_review_is_not_dropped_or_rebound(self):
        assertion = next(a for a in self.graph['assertions'] if a.get('extension_source_kind'))
        reviewed = self.root / 'reviewed'
        review_run(self.source, reviewed, assertion['id'], 'accepted', 'Invented reviewer', 'Invented test review')
        packet = self.root / 'reviewed_packet'
        gold_packet.export_packet(reviewed, packet)
        decisions = gold_packet._read(packet / 'decisions.template.json')
        write_json(self.root / 'reviewed_decisions.json', decisions)
        self.retained = self.root / 'reviewed_retained'
        gold_packet.save_decisions(packet, self.root / 'reviewed_decisions.json', self.retained)
        before = producer.inventory(self.retained)
        with self.assertRaisesRegex(ValueError, 'extension-bound review events'):
            self.build()
        self.assertEqual(producer.inventory(self.retained), before)
        self.assertFalse((self.root / 'prepared').exists())

    def test_unrelated_core_review_is_carried_forward_exactly(self):
        assertion = next(a for a in self.graph['assertions'] if not a.get('extension_source_kind')
                         and a['kind'] != 'disease_filtered_membership'
                         and a['structurally_usable_evidence_ids'])
        reviewed = self.root / 'core_reviewed'
        self.graph = review_run(self.source, reviewed, assertion['id'], 'accepted',
                                'Invented reviewer', 'Invented core source review')
        packet = self.root / 'core_reviewed_packet'
        gold_packet.export_packet(reviewed, packet)
        decisions = gold_packet._read(packet / 'decisions.template.json')
        write_json(self.root / 'core_reviewed_decisions.json', decisions)
        self.retained = self.root / 'core_reviewed_retained'
        gold_packet.save_decisions(packet, self.root / 'core_reviewed_decisions.json', self.retained)
        self.build()
        _, graph, _ = producer.load_prepared(self.root / 'prepared')
        self.assertEqual(graph['review_events'], self.graph['review_events'])
        self.assertEqual(next(a for a in graph['assertions'] if a['id'] == assertion['id']),
                         next(a for a in self.graph['assertions'] if a['id'] == assertion['id']))

    def test_prepared_file_tamper_prevents_finalization(self):
        self.build()
        folder = self.root / 'prepared'
        path = folder / 'raw_run/extension_sources/string/source.json'
        path.write_bytes(path.read_bytes() + b' ')
        with patch.object(producer.qualified_workspace, 'publish_workspace') as publish:
            with self.assertRaisesRegex(ValueError, 'inventory or seal'):
                producer.finalize_recoveries(folder, self.inputs[0], 'b' * 64, self.root / 'workspace')
            publish.assert_not_called()

    def test_finalization_requires_new_history_and_delegates_exact_binding(self):
        result = self.build()
        folder = self.root / 'prepared'
        with self.assertRaisesRegex(ValueError, 'history is required'):
            producer.finalize_recoveries(folder, None, None, self.root / 'workspace')
        def fake_workspace(source, output, **kwargs):
            Path(output).mkdir()
            return {'content_sha256': 'c' * 64}
        with patch.object(producer.qualified_workspace, 'publish_workspace',
                          side_effect=fake_workspace) as publish:
            published = producer.finalize_recoveries(folder, self.inputs[0], 'b' * 64, self.root / 'workspace')
        self.assertEqual(publish.call_count, 1)
        self.assertEqual(publish.call_args.args[0], folder / 'retained')
        self.assertEqual(publish.call_args.kwargs,
            {'history': self.inputs[0], 'history_content_sha256': 'b' * 64})
        self.assertTrue((self.root / 'workspace').is_dir())
        self.assertEqual(published['preparation_content_sha256'], result['content_sha256'])
        self.assertFalse(published['independent_biological_accuracy_established'])

    def test_workspace_cannot_be_added_inside_sealed_preparation(self):
        self.build()
        folder = self.root / 'prepared'
        with patch.object(producer.qualified_workspace, 'publish_workspace') as publish:
            with self.assertRaisesRegex(ValueError, 'outside every input'):
                producer.finalize_recoveries(folder, self.inputs[0], 'b' * 64, folder / 'workspace')
            publish.assert_not_called()

    def test_preexisting_source_publication_reuse_binds_exact_inputs(self):
        census, qualification, context = self.inputs
        write_json(census / 'report.json', {'invented_census': True})
        (qualification / 'replacement_proposals.json').write_text('[]\n')
        (qualification / 'ontology.json').write_text('{"invented": true}\n')
        (context / 'context.json').write_text('{"invented_context": true}\n')
        packet, graph = gold_packet.load_packet(self.packet)
        old_report, retained = gold_packet.load_decisions(self.retained)
        qualification_report = {'packet_id': packet['packet_id'], 'graph_sha256': packet['graph_sha256'],
                                'ontology': {'source_file': 'ontology.json'}}
        qualification_report['content_sha256'] = digest(qualification_report)
        write_json(qualification / 'go_ontology_qualification.json', qualification_report)
        intake = {'original_packet_id': packet['packet_id'], 'original_graph_sha256': packet['graph_sha256'],
                  'baseline_go_edges_sha256': digest([]), 'retained_go_edges_sha256': digest([])}
        material = {'intake.json': __import__('json').dumps(intake).encode(),
            'census/report.json': (census / 'report.json').read_bytes(),
            'proposals.json': (qualification / 'replacement_proposals.json').read_bytes(),
            'ontology.json': (qualification / 'ontology.json').read_bytes(),
            'context/context.json': (context / 'context.json').read_bytes(),
            'binding.json': __import__('json').dumps(qualification_report['ontology']).encode()}
        manifest = {'invented_manifest': True}
        adapter = SimpleNamespace(load_publication=lambda p: (manifest,
            {'bindings': {'census_file_sha256': sha(census / 'report.json')}}, material),
            _go_edges=lambda g: [], INTAKE='intake.json', CENSUS='census/', PROPOSALS='proposals.json',
            ONTOLOGY='ontology.json', ONTOLOGY_BINDING='binding.json', CONTEXT='context/', CONTEXT_REPORT='context.json')
        kwargs = (adapter, self.root / 'invented_publication', census, qualification, context,
                  packet, old_report, graph, retained, sha(census / 'report.json'))
        result = producer._reuse_publication(*kwargs, self.root / 'copied_publication')
        self.assertEqual(result, manifest)
        self.assertEqual(producer.inventory(self.root / 'copied_publication'),
                         {name: __import__('hashlib').sha256(raw).hexdigest() for name, raw in material.items()})
        (context / 'context.json').write_text('{"different": true}\n')
        with self.assertRaisesRegex(ValueError, 'source captures differ'):
            producer._reuse_publication(*kwargs, self.root / 'wrong_copy')
        self.assertFalse((self.root / 'wrong_copy').exists())

    def test_existing_assertion_revision_or_decision_change_is_rejected(self):
        self.build()
        folder = self.root / 'prepared'
        _, graph = gold_packet.load_packet(folder / 'packet')
        decisions = gold_packet._read(folder / 'decisions.json')
        for field in ('revision', 'lifecycle_state', 'review_history'):
            changed = deepcopy(graph)
            aid = self.graph['assertions'][0]['id']
            next(a for a in changed['assertions'] if a['id'] == aid)[field] = 'wrong'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'existing assertion'):
                producer.preserved_properties(self.graph, changed, self.decisions, decisions)
        changed = deepcopy(decisions)
        changed['decisions'][0]['decision'] = 'keep'
        with self.assertRaisesRegex(ValueError, 'decision rows'):
            producer.preserved_properties(self.graph, graph, self.decisions, changed)


if __name__ == '__main__':
    unittest.main()
