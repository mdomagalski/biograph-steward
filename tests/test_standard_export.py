"""Invented-source projection/integrity checks, not standards or biological scores.

Artifact tests replace the optional validator/resource loader with explicitly
synthetic reports. The separate pinned-tool integration audit tests the actual
upstream algorithms; a mocked success is never evidence of their conformance.
"""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.graph import build_graph, save_run
from biograph_steward.standard_export import (PROFILE, RECEIPT, export_standard,
                                               project_graph, verify_standard)
from test_normalization import fixture


def read(path):
    return json.loads(Path(path).read_text())


def seal(value):
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    return value


def bytes_in(folder):
    return {path.relative_to(folder).as_posix(): path.read_bytes()
            for path in folder.rglob('*') if path.is_file()}


class StandardProjectionTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph(fixture())

    def pathway(self, graph=None):
        graph = self.graph if graph is None else graph
        edge = next(row for row in graph['edges'] if row['record_kind'] == 'pathway_membership')
        assertion = next(row for row in graph['assertions'] if row['id'] == edge['assertion_id'])
        return edge, assertion

    def mapping(self, graph, edge):
        return next(row for row in project_graph(graph)['edge_mapping']
                    if row['source_edge_id'] == edge['id'])

    def test_complete_partition_preserves_source_and_known_annotation_limits(self):
        original = deepcopy(self.graph)
        result = project_graph(self.graph)
        self.assertEqual(self.graph, original)
        self.assertEqual(result['profile'], PROFILE)
        self.assertEqual(result['counts']['projected_edges'], 5)
        self.assertEqual(result['counts']['source_edges'],
                         result['counts']['projected_edges'] + result['counts']['excluded_edges'])
        self.assertEqual({row['source_edge_id'] for row in result['edge_mapping']},
                         {row['id'] for row in self.graph['edges']})
        self.assertEqual(len(result['edge_mapping']), len(self.graph['edges']))
        self.assertEqual({row['source_assertion_id'] for row in result['assertion_mapping']},
                         {row['id'] for row in self.graph['assertions']})
        self.assertEqual({row['source_node_id'] for row in result['node_mapping']},
                         {row['id'] for row in self.graph['nodes']})
        expected = {
            'go_annotation': 'go_relation_polarity_and_extensions_unavailable',
            'protein_interaction': 'annotation_bundle_not_mapped_to_a_concrete_standard_interaction_predicate',
            'drug_listing': 'listing_does_not_assert_a_standard_drug_target_relation',
            'expression_observation': 'qualified_expression_observation_outside_this_profile',
        }
        for kind, reason in expected.items():
            rows = [row for row in result['edge_mapping'] if row['source_kind'] == kind]
            self.assertTrue(rows, kind)
            self.assertTrue(all(row['status'] == 'excluded' and reason in row['reasons'] for row in rows))
        originals = {row['id']: row for row in self.graph['edges']}
        for row in result['edge_mapping']:
            self.assertEqual(row['source_edge_sha256'], digest(originals[row['source_edge_id']]))

    def test_core_exchange_rows_do_not_smuggle_nested_extensions_or_review_truth(self):
        result = project_graph(self.graph)
        endpoints = {value for edge in result['edges'] for value in (edge['subject'], edge['object'])}
        self.assertEqual({node['id'] for node in result['nodes']}, endpoints)
        for node in result['nodes']:
            self.assertEqual(set(node), {'id', 'name', 'category'})
            self.assertIsInstance(node['category'], list)
        for edge in result['edges']:
            self.assertNotIn('original_record', edge)
            self.assertNotIn('original_assertion', edge)
            self.assertNotIn('confidence', edge)
            self.assertNotIn('biologically_validated', edge)
            self.assertEqual(edge['predicate'], 'biolink:participates_in')
            self.assertEqual(edge['primary_knowledge_source'], 'infores:reactome')
            self.assertEqual(edge['aggregator_knowledge_source'], ['infores:pharos'])
            self.assertEqual(edge['knowledge_level'], 'not_provided')
        omitted = [row for row in result['node_mapping'] if row['source_node_id'] not in endpoints]
        self.assertTrue(omitted)
        self.assertTrue(all(row['status'] == 'preserved_in_source_packet' for row in omitted))

    def test_nonempty_edge_or_assertion_qualification_cannot_be_dropped(self):
        for side in ('edge', 'assertion'):
            for qualifier in ('disease', 'species', 'negated', 'custom_context'):
                with self.subTest(side=side, qualifier=qualifier):
                    graph = deepcopy(self.graph)
                    edge, assertion = self.pathway(graph)
                    (edge if side == 'edge' else assertion)['qualifiers'][qualifier] = False if qualifier == 'negated' else 'TEST:1'
                    row = self.mapping(graph, edge)
                    self.assertEqual(row['status'], 'excluded')
                    self.assertIn('nonempty_qualification_requires_a_separate_mapping_contract', row['reasons'])

    def test_noninspectable_lifecycle_is_preserved_but_not_projected(self):
        for state in ('candidate', 'provisional', 'accepted', 'rejected', 'quarantined', 'obsolete'):
            with self.subTest(state=state):
                graph = deepcopy(self.graph)
                edge, assertion = self.pathway(graph)
                assertion['lifecycle_state'] = state
                row = self.mapping(graph, edge)
                self.assertEqual(row['status'], 'represented' if state in {'candidate', 'provisional', 'accepted'} else 'excluded')
                self.assertEqual(assertion['lifecycle_state'], state)

    def test_unmapped_identity_or_nonreactome_source_is_not_guessed(self):
        for role in ('subject', 'object'):
            with self.subTest(role=role):
                graph = deepcopy(self.graph)
                edge, _ = self.pathway(graph)
                node = next(row for row in graph['nodes'] if row['id'] == edge[role])
                node['identifier_mapped'] = False
                self.assertEqual(self.mapping(graph, edge)['status'], 'excluded')
        for source in ('KEGG', 'Reactome,STRINGDB', 'reactome', None):
            with self.subTest(source=source):
                graph = deepcopy(self.graph)
                edge, _ = self.pathway(graph)
                edge['primary_source_raw'] = source
                self.assertIn('pathway_requires_exact_mapped_reactome_identity_and_source',
                              self.mapping(graph, edge)['reasons'])

    def test_unexpected_predicate_is_not_rewritten_to_membership(self):
        edge, assertion = self.pathway()
        edge['predicate'] = assertion['predicate'] = 'biolink:related_to'
        row = self.mapping(self.graph, edge)
        self.assertEqual(row['status'], 'excluded')
        self.assertIn('unexpected_source_predicate', row['reasons'])

    def test_evidence_assertion_identity_conflict_is_an_error(self):
        edge, assertion = self.pathway()
        assertion['object'] = 'REACT:R-HSA-999'
        with self.assertRaisesRegex(ValueError, 'identity disagree'):
            project_graph(self.graph)

    def test_one_excluded_evidence_record_does_not_hide_partial_assertion_coverage(self):
        edge, assertion = self.pathway()
        extra = deepcopy(edge)
        extra['id'] = 'edge:synthetic-second-view'
        extra['qualifiers']['species'] = 'NCBITaxon:9606'
        self.graph['edges'].append(extra)
        assertion['evidence_edge_ids'].append(extra['id'])
        result = project_graph(self.graph)
        row = next(row for row in result['assertion_mapping'] if row['source_assertion_id'] == assertion['id'])
        self.assertEqual(row['status'], 'partially_represented')
        self.assertEqual((row['represented_edges'], row['source_edges']), (1, 2))


class StandardExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.packet, self.output = (self.root / name for name in ('run', 'packet', 'export'))
        self.resources = self.root / 'resources'
        self.resources.mkdir()
        (self.resources / 'SYNTHETIC_TEST_RESOURCE.txt').write_text('Invented resource stub; no actual standard validation.')
        self.resource_report = {'fixture': 'synthetic_test_only',
                                'files': {'SYNTHETIC_TEST_RESOURCE.txt': sha(self.resources / 'SYNTHETIC_TEST_RESOURCE.txt')}}
        self.graph = save_run(fixture(), self.run)
        self.packet_manifest = export_packet(self.run, self.packet)
        resource_patch = patch('biograph_steward.standard_export.verify_resources',
                               return_value=deepcopy(self.resource_report))
        resource_patch.start()
        self.addCleanup(resource_patch.stop)

    def validation(self, nodes, edges, resources):
        return seal({'format': 'biograph-steward.standards-validation.v1',
                     'fixture': 'synthetic_test_only; upstream validators were not run',
                     'packages': {}, 'resources': deepcopy(self.resource_report),
                     'input_sha256': digest({'nodes': nodes, 'edges': edges}),
                     'counts': {'nodes': len(nodes), 'edges': len(edges)},
                     'kgx': {'status': 'not_run_synthetic_test'},
                     'published_json_schema': {'status': 'not_run_synthetic_test'},
                     'kgx_jsonl_roundtrip': {'status': 'not_run_synthetic_test'},
                     'declared_domain_range_and_predicate_audit': {'status': 'not_run_synthetic_test'},
                     'full_conformance': False, 'biological_validation_performed': False})

    def export(self):
        with patch('biograph_steward.standards_validation.validate_projection', side_effect=self.validation):
            return export_standard(self.packet, self.output, self.resources)

    def reseal_files(self):
        receipt = read(self.output / RECEIPT)
        receipt['files'] = {path.relative_to(self.output).as_posix(): sha(path)
                            for path in self.output.rglob('*') if path.is_file() and path.name != RECEIPT}
        write_json(self.output / RECEIPT, seal(receipt))

    def test_export_preserves_every_source_byte_and_offline_verify_never_revalidates(self):
        before = bytes_in(self.packet)
        run_before = bytes_in(self.run)
        report = self.export()
        self.assertEqual(bytes_in(self.packet), before)
        self.assertEqual(bytes_in(self.output / 'source_packet'), before)
        self.assertEqual(bytes_in(self.run), run_before)
        self.assertEqual(load_packet(self.output / 'source_packet'), (self.packet_manifest, self.graph))
        self.assertFalse(report['biological_validation_performed'])
        self.assertFalse(report['full_standard_conformance_claimed'])
        self.assertIn('synthetic_test_only', report['validation']['fixture'])
        with patch('biograph_steward.standards_validation.validate_projection', side_effect=AssertionError('No validator on load')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('No network on load')):
            self.assertEqual(verify_standard(self.output), report)

    def test_existing_or_nested_output_is_rejected_without_changing_source(self):
        self.export()
        before = bytes_in(self.packet)
        for destination in (self.output, self.packet / 'new-export', self.resources / 'new-export'):
            with self.subTest(destination=destination):
                with patch('biograph_steward.standards_validation.validate_projection', side_effect=AssertionError('Validate after destination check')):
                    with self.assertRaisesRegex(ValueError, 'new output'):
                        export_standard(self.packet, destination, self.resources)
        self.assertEqual(before, bytes_in(self.packet))

    def test_validator_error_does_not_publish_a_partial_export(self):
        with patch('biograph_steward.standards_validation.validate_projection', side_effect=ValueError('Synthetic missing dependency')):
            with self.assertRaisesRegex(ValueError, 'missing dependency'):
                export_standard(self.packet, self.output, self.resources)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.standard-projection-*')), [])

    def test_changed_bytes_added_files_and_symlinks_are_rejected(self):
        self.export()
        path = self.output / 'projection_edges.jsonl'
        original = path.read_bytes()
        path.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'receipt or files'):
            verify_standard(self.output)
        path.write_bytes(original)
        extra = self.output / 'unexpected.txt'
        extra.write_text('extra')
        with self.assertRaisesRegex(ValueError, 'receipt or files'):
            verify_standard(self.output)
        extra.unlink()
        extra.symlink_to(self.resources / 'SYNTHETIC_TEST_RESOURCE.txt')
        with self.assertRaisesRegex(ValueError, 'without symlinks'):
            verify_standard(self.output)

    def test_resealed_projection_or_ledger_still_must_match_preserved_source(self):
        self.export()
        for name in ('projection_edges.jsonl', 'edge_mapping.jsonl', 'node_mapping.jsonl', 'assertion_mapping.jsonl'):
            with self.subTest(name=name):
                path = self.output / name
                original = path.read_bytes()
                rows = [json.loads(line) for line in original.splitlines()]
                self.assertTrue(rows)
                path.write_text('\n'.join(json.dumps(row) for row in rows[1:]) + '\n')
                self.reseal_files()
                with self.assertRaisesRegex(ValueError, 'rows do not reproduce'):
                    verify_standard(self.output)
                path.write_bytes(original)
                self.reseal_files()

    def test_resealed_report_cannot_change_scope_identity_or_claim_conformance(self):
        self.export()
        path = self.output / 'report.json'
        original = read(path)
        for field, value in (('profile', 'invented-profile'), ('source_packet_id', 'invented-packet'),
                             ('source_graph_sha256', '0' * 64), ('data_kind', 'invented-kind'),
                             ('full_standard_conformance_claimed', True), ('biological_validation_performed', True)):
            with self.subTest(field=field):
                report = deepcopy(original)
                report[field] = value
                write_json(path, report)
                self.reseal_files()
                with self.assertRaises(ValueError):
                    verify_standard(self.output)
        write_json(path, original)
        self.reseal_files()
        verify_standard(self.output)

    def test_resealed_duplicate_json_keys_are_rejected_before_mapping_replay(self):
        self.export()
        path = self.output / 'projection_edges.jsonl'
        rows = path.read_text().splitlines()
        rows[0] = '{"predicate":"biolink:related_to",' + rows[0][1:]
        path.write_text('\n'.join(rows) + '\n')
        self.reseal_files()
        with self.assertRaisesRegex(ValueError, 'Invalid strict JSON input'):
            verify_standard(self.output)

    def test_resealed_validation_must_remain_bound_to_projection_and_resources(self):
        self.export()
        validation_path, report_path, receipt_path = (self.output / name for name in ('validation.json', 'report.json', RECEIPT))
        original_validation, original_report = read(validation_path), read(report_path)
        for field, value in (('input_sha256', '0' * 64), ('counts', {'nodes': 0, 'edges': 0}),
                             ('resources', {'fixture': 'other'}), ('full_conformance', True),
                             ('biological_validation_performed', True)):
            with self.subTest(field=field):
                validation = deepcopy(original_validation)
                validation[field] = value
                seal(validation)
                report = deepcopy(original_report)
                report['validation'] = validation
                write_json(validation_path, validation)
                write_json(report_path, report)
                receipt = read(receipt_path)
                receipt['validation_sha256'] = digest(validation)
                write_json(receipt_path, seal(receipt))
                self.reseal_files()
                with self.assertRaises(ValueError):
                    verify_standard(self.output)

    def test_resealed_outer_receipt_does_not_hide_corrupted_source_packet(self):
        self.export()
        path = self.output / 'source_packet/edges.jsonl'
        path.write_text('')
        self.reseal_files()
        with self.assertRaisesRegex(ValueError, 'Packet file inventory'):
            verify_standard(self.output)

    def test_cli_export_and_offline_verify_report_recorded_audit_statuses(self):
        from biograph_steward.__main__ import main
        output = StringIO()
        with patch('biograph_steward.standards_validation.validate_projection', side_effect=self.validation), redirect_stdout(output):
            self.assertEqual(main(['standards-export', '--packet', str(self.packet),
                                   '--resources', str(self.resources), '--out', str(self.output)]), 0)
        first = json.loads(output.getvalue())
        output = StringIO()
        with patch('biograph_steward.standards_validation.validate_projection', side_effect=AssertionError('Offline CLI must not rerun validators')), redirect_stdout(output):
            self.assertEqual(main(['standards-verify', '--run', str(self.output)]), 0)
        reopened = json.loads(output.getvalue())
        self.assertEqual(reopened['counts'], first['counts'])
        self.assertEqual(set(reopened['recorded_validation_status'].values()), {'not_run_synthetic_test'})
        self.assertFalse(reopened['full_standard_conformance_claimed'])
        self.assertFalse(reopened['biological_validation_performed'])

    def test_cli_optional_dependency_failure_is_visible_and_publishes_nothing(self):
        from biograph_steward.__main__ import main
        errors = StringIO()
        with patch('biograph_steward.standards_validation.validate_projection', side_effect=ValueError('Synthetic missing optional validator')), redirect_stderr(errors):
            self.assertEqual(main(['standards-export', '--packet', str(self.packet),
                                   '--resources', str(self.resources), '--out', str(self.output)]), 1)
        self.assertIn('missing optional validator', errors.getvalue())
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
