"""Separate portable attachment on the existing invented native/QC frame."""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from biograph_steward import go_context_export as export
from biograph_steward.client import digest


class NativeGoContextExportTests(unittest.TestCase):
    def setUp(self):
        from test_go_context_inspection import NativeContextInspectionTests
        from test_go_context_qc import make_qc
        self.fixture = NativeContextInspectionTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root, self.graph, self.context = self.fixture.root, self.fixture.graph, self.fixture.context
        self.selected = next(row for row in self.graph['edges'] if row['record_kind'] == 'go_annotation')
        self.report = json.loads((self.context/'go_context_qualification.json').read_text())
        self.qc = self.root/'quality'
        make_qc(self.qc, self.report, self.fixture.native,
                unsatisfiable={self.fixture.native[1]['id']})

    def build(self, **changes):
        args = {'context': self.context, 'qc': self.qc, 'graph': self.graph,
                'selection_id': self.selected['assertion_id'], 'source_run': 'run'}
        args.update(changes)
        return export.build_go_context_archive(**args)

    def inventory(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_exact_twelve_source_files_and_two_guides_are_byte_identical_and_bound(self):
        before, graph = self.inventory(), deepcopy(self.graph)
        result = self.build()
        with ZipFile(BytesIO(result['content'])) as archive:
            names = {name.removeprefix(export.ROOT+'/') for name in archive.namelist()}
            self.assertEqual(names, export.SOURCE_FILES | {'manifest.json', 'README.txt'})
            self.assertEqual(len(archive.namelist()), 14)
            manifest = json.loads(archive.read(export.ROOT+'/manifest.json'))
            self.assertEqual(manifest, result['manifest'])
            self.assertEqual(manifest['format'], export.FORMAT)
            for name in export.SOURCE_FILES:
                label, relative = name.split('/', 1)
                source = (self.context if label == 'context' else self.qc)/relative
                copied = archive.read(export.ROOT+'/'+name)
                self.assertEqual(copied, source.read_bytes())
                self.assertEqual(manifest['source_files'][name],
                    {'bytes': len(copied), 'sha256': hashlib.sha256(copied).hexdigest()})
            self.assertEqual(manifest['source_bytes'], sum(row['bytes'] for row in manifest['source_files'].values()))
            self.assertEqual(manifest['source_file_count'], 12)
            self.assertEqual(manifest['content_sha256'], digest({k:v for k,v in manifest.items() if k != 'content_sha256'}))
            self.assertEqual(manifest['current_graph_sha256'], digest(self.graph))
            self.assertEqual(manifest['original_graph_sha256'], self.report['graph_sha256'])
            self.assertEqual(manifest['original_graph_file_sha256'], self.report['source_graph_file_sha256'])
            self.assertEqual(manifest['context_report_content_sha256'], self.report['content_sha256'])
            self.assertEqual(manifest['selection_id'], self.selected['assertion_id'])
            self.assertFalse(manifest['ordinary_workspace_export_changed'])
            self.assertFalse(manifest['independent_biological_accuracy_established'])
            self.assertFalse(manifest['public_redistribution_rights_asserted'])
            self.assertFalse(manifest['parser_rules_or_reasoner_reexecuted'])
            guide = archive.read(export.ROOT+'/README.txt').decode()
            for wording in ['OUTSIDE the strict saved workspace', 'BIOGRAPH_GO_CONTEXT_DIR=',
                            'BIOGRAPH_GO_QC_DIR=', 'does not\nrelicense source content',
                            'not a complete backup', 'does not establish historical source']:
                self.assertIn(wording, guide)
        self.assertEqual(hashlib.sha256(result['content']).hexdigest(), result['sha256'])
        self.assertEqual(len(result['content']), result['bytes'])
        self.assertEqual(before, self.inventory())
        self.assertEqual(graph, self.graph)

    def test_qualified_graph_and_original_baseline_bindings_remain_distinct(self):
        qualified = deepcopy(self.graph)
        qualified['qualified_view'] = {'packet_id': self.report['packet_id']}
        workspace = self.root/'qualified_workspace'
        baseline = workspace/'source_retained_package/baseline_packet/source/graph.json'
        baseline.parent.mkdir(parents=True)
        baseline.write_bytes((self.fixture.packet/'source/graph.json').read_bytes())
        manifest = self.build(graph=qualified, source_folder=workspace)['manifest']
        self.assertNotEqual(manifest['current_graph_sha256'], manifest['original_graph_sha256'])
        self.assertEqual(manifest['current_graph_sha256'], digest(qualified))
        baseline.write_bytes(baseline.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError, 'baseline source bytes'):
            self.build(graph=qualified, source_folder=workspace)

    def test_same_source_and_selection_produce_same_archive_without_optional_runtime(self):
        with patch('biograph_steward.go_qualification.read_native_gaf', side_effect=AssertionError('No optional parser')):
            first, second = self.build(), self.build()
        self.assertEqual(first['content'], second['content'])
        self.assertTrue(first['filename'].endswith('.zip'))

    def test_no_scratch_or_source_writes_are_needed(self):
        original_open = Path.open
        def read_only(path, mode='r', *args, **kwargs):
            self.assertFalse(any(letter in mode for letter in 'wax+'), 'Unexpected write: '+str(path))
            return original_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', read_only), patch.object(Path, 'mkdir', side_effect=AssertionError('No scratch')):
            self.assertEqual(self.build()['manifest']['source_file_count'], 12)

    def test_missing_configuration_is_unavailable_before_any_source_read(self):
        for absent in ('context', 'qc'):
            with self.subTest(absent=absent), patch.object(export.go_context_inspection, 'inspect_go_selection') as inspect:
                with self.assertRaisesRegex(ValueError, 'both native context and saved QC'):
                    self.build(**{absent: None})
                inspect.assert_not_called()

    def test_wrong_graph_or_non_go_selection_cannot_export_unrelated_sources(self):
        wrong = deepcopy(self.graph); wrong['snapshot_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'source snapshot'):
            self.build(graph=wrong)
        nong = next(row for row in self.graph['assertions'] if row['kind'] != 'go_annotation')
        with self.assertRaisesRegex(ValueError, 'GO annotation claim'):
            self.build(selection_id=nong['id'])

    def test_extra_files_symlinks_and_tampered_source_fail_closed(self):
        extra = self.context/'not_part_of_packet'; extra.write_text('not exportable')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.build()
        extra.unlink()
        raw = self.context/'native_records.jsonl'; content = raw.read_bytes(); raw.unlink()
        outside = self.root/'outside.jsonl'; outside.write_bytes(content); raw.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.build()
        raw.unlink(); raw.write_bytes(content+b' ')
        with self.assertRaisesRegex(ValueError, 'source bytes'):
            self.build()

    def test_post_validation_changed_bytes_or_extra_path_cannot_escape_pack_checks(self):
        inspect = export.go_context_inspection.inspect_go_selection
        for new_path in (False, True):
            with self.subTest(extra_path=new_path):
                file = self.qc/('unbound' if new_path else 'official_report.json')
                original = file.read_bytes() if file.exists() else None
                def changed(*args, **kwargs):
                    result = inspect(*args, **kwargs)
                    file.write_bytes((original or b'')+b' ')
                    return result
                with patch.object(export.go_context_inspection, 'inspect_go_selection', side_effect=changed):
                    with self.assertRaisesRegex(ValueError, 'inventory|bytes changed while packing'):
                        self.build()
                if original is None:
                    file.unlink()
                else:
                    file.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
