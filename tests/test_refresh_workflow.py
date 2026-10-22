"""Invented persistence controls for portable, ancestry-bound refresh results."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from shutil import copytree, rmtree
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.assertions import new_review_event
from biograph_steward.client import digest, write_json
from biograph_steward.graph import build_graph, save_run
from biograph_steward.refresh_workflow import (RefreshRuntimeMismatch, refresh_artifact_required,
                                              run_refresh, verify_refresh, verify_refresh_files)
from test_refresh import claim, mock_snapshot, source_bytes


class RefreshPersistenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.before, self.after = self.root / 'before', self.root / 'after'
        snapshot = mock_snapshot()
        graph = build_graph(snapshot)
        event = new_review_event(graph, claim(graph)['id'], 'accepted',
                                 'Invented source reviewer', 'Invented source assessment.')
        save_run(snapshot, self.before, review_events=[event])
        save_run(mock_snapshot(), self.after)

    def result(self, name='result', carry=True):
        output = self.root / name
        run_refresh(self.before, self.after, output, carry_reviews=carry)
        return output

    @staticmethod
    def reseal(output, *, update_parent_hashes=False):
        """Remove only the byte-integrity obstacle; semantic replay must still fail."""
        receipt_path = output / 'refresh_receipt.json'
        receipt = json.loads(receipt_path.read_text())
        receipt['files'] = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(output.rglob('*'))
                            if p.is_file() and p != receipt_path}
        if update_parent_hashes:
            for label, files in receipt['inputs'].items():
                for name in files:
                    files[name] = hashlib.sha256((output / 'refresh_inputs' / label / name).read_bytes()).hexdigest()
        receipt.pop('receipt_sha256')
        receipt['receipt_sha256'] = digest(receipt)
        write_json(receipt_path, receipt)

    def test_standalone_result_survives_removing_original_parents_and_relocation(self):
        (self.before / 'unrelated.private').write_text('Invented excluded input; do not copy.')
        output = self.result()
        expected = verify_refresh(output)
        for label in ('before', 'after'):
            copied = output / 'refresh_inputs' / label
            self.assertEqual({p.name for p in copied.iterdir()},
                             {'snapshot.json', 'graph.json', 'run_manifest.json', 'review_events.json'})
        rmtree(self.before)
        rmtree(self.after)
        portable = self.root / 'relocated' / 'renamed-result'
        copytree(output, portable)
        rmtree(output)
        self.assertEqual(verify_refresh(portable), expected)
        self.assertNotIn(str(self.root), (portable / 'refresh_comparison.json').read_text())

    def test_runtime_change_is_distinct_from_changed_saved_bytes(self):
        output = self.result()
        receipt = verify_refresh(output)
        changed = {**receipt['code_hashes'], 'civic_context': '0' * 64}
        original = source_bytes(output)
        with patch('biograph_steward.refresh_workflow._code_hashes', return_value=changed):
            self.assertEqual(verify_refresh_files(output), receipt)
            with self.assertRaises(RefreshRuntimeMismatch) as caught:
                verify_refresh(output)
            self.assertEqual(caught.exception.changed_modules, ['civic_context'])
            self.assertIn('No current replay was performed', str(caught.exception))
            self.assertEqual(source_bytes(output), original)
            (output / 'refresh_report.html').write_text('Altered historical report')
            for checker in (verify_refresh_files, verify_refresh):
                with self.assertRaisesRegex(ValueError, 'saved bytes changed') as error:
                    checker(output)
                self.assertNotIsInstance(error.exception, RefreshRuntimeMismatch)

    def test_overlap_nonempty_and_symlink_output_guards_preserve_both_parents(self):
        expected = source_bytes(self.before), source_bytes(self.after)
        occupied = self.root / 'occupied'
        occupied.mkdir()
        (occupied / 'keep.txt').write_text('Invented file.')
        link = self.root / 'linked-output'
        link.symlink_to(occupied, target_is_directory=True)
        for output in (self.before, self.after, self.before / 'nested', self.after / 'nested', occupied, link):
            with self.subTest(output=output.name), self.assertRaises(ValueError):
                run_refresh(self.before, self.after, output)
        self.assertEqual((source_bytes(self.before), source_bytes(self.after)), expected)
        self.assertEqual((occupied / 'keep.txt').read_text(), 'Invented file.')

    def test_changed_report_is_rejected_before_and_after_receipt_resealing(self):
        output = self.result()
        report = output / 'refresh_report.html'
        report.write_text(report.read_text() + '<!-- Invented alteration. -->')
        with self.assertRaises(ValueError):
            verify_refresh(output)
        self.reseal(output)
        with self.assertRaisesRegex(ValueError, 'report does not replay'):
            verify_refresh(output)

    def test_resealed_derived_graph_and_review_events_do_not_override_replay(self):
        for name in ('graph.json', 'review_events.json'):
            with self.subTest(name=name):
                output = self.result(name=name.replace('.', '-'))
                value = json.loads((output / name).read_text())
                if name == 'graph.json':
                    value['assertions'][0]['biologically_validated'] = True
                else:
                    self.assertEqual(len(value), 1)
                    value[0]['migration']['fresh_human_adjudication'] = True
                write_json(output / name, value)
                self.reseal(output)
                with self.assertRaisesRegex(ValueError, 'graph, source or review inheritance does not replay'):
                    verify_refresh(output)

    def test_resealed_forged_original_review_remains_bound_to_preserved_parent(self):
        output = self.result()
        events = json.loads((output / 'review_events.json').read_text())
        migration = events[0]['migration']
        migration['original_event']['reviewer'] = 'Invented replacement actor'
        migration['original_event_sha256'] = digest(migration['original_event'])
        write_json(output / 'review_events.json', events)
        graph = json.loads((output / 'graph.json').read_text())
        graph['review_events'] = deepcopy(events)
        for assertion in graph['assertions']:
            if assertion['id'] == events[0]['assertion_id']:
                assertion['review_history'] = deepcopy(events)
        write_json(output / 'graph.json', graph)
        self.reseal(output)
        with self.assertRaises(ValueError):
            verify_refresh(output)

    def test_parent_mutation_is_rejected_even_after_parent_and_receipt_hashes_change(self):
        output = self.result()
        parent = output / 'refresh_inputs/before/run_manifest.json'
        manifest = json.loads(parent.read_text())
        manifest['starter_version'] = 'invented-different-transformer'
        write_json(parent, manifest)
        self.reseal(output, update_parent_hashes=True)
        with self.assertRaisesRegex(ValueError, 'comparison does not replay'):
            verify_refresh(output)

    def test_resealed_missing_or_extra_derived_files_fail_expected_inventory(self):
        for change in ('missing', 'extra'):
            with self.subTest(change=change):
                output = self.result(name=change)
                if change == 'missing':
                    (output / 'assertions.tsv').unlink()
                else:
                    (output / 'unrequested.json').write_text('{}')
                self.reseal(output)
                with self.assertRaises(ValueError):
                    verify_refresh(output)

    def test_receipt_policy_identity_cannot_be_changed_by_self_rehashing(self):
        output = self.result()
        path = output / 'refresh_receipt.json'
        receipt = json.loads(path.read_text())
        receipt['review_carryover_actor'] = 'Invented false actor'
        receipt.pop('receipt_sha256')
        receipt['receipt_sha256'] = digest(receipt)
        write_json(path, receipt)
        with self.assertRaisesRegex(ValueError, 'execution policy changed'):
            verify_refresh(output)

    def test_reusing_a_prior_refresh_is_rejected_even_with_a_complete_verified_receipt(self):
        prior = self.result()
        verify_refresh(prior)
        with self.assertRaisesRegex(ValueError, 'chained refresh ancestry is not supported'):
            run_refresh(prior, self.after, self.root / 'verified-prior-reuse')
        (prior / 'refresh_receipt.json').unlink()
        self.assertTrue(refresh_artifact_required(prior))
        blocked = self.root / 'blocked-reuse'
        with self.assertRaisesRegex(ValueError, 'chained refresh ancestry is not supported'):
            run_refresh(prior, self.after, blocked)
        self.assertFalse(blocked.exists())

    def test_manifest_mode_alone_requires_refresh_verification(self):
        manifest_path = self.before / 'run_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['run_mode'] = 'refresh'
        write_json(manifest_path, manifest)
        self.assertTrue(refresh_artifact_required(self.before))
        with self.assertRaisesRegex(ValueError, 'chained refresh ancestry is not supported'):
            run_refresh(self.before, self.after, self.root / 'blocked-manifest-only')

    def test_changing_a_manifest_does_not_hide_inherited_review_events(self):
        prior = self.result()
        graph = json.loads((prior / 'graph.json').read_text())
        ordinary = self.root / 'disguised-prior'
        save_run(json.loads((prior / 'snapshot.json').read_text()), ordinary,
                 review_events=graph['review_events'], run_mode='build')
        self.assertTrue(refresh_artifact_required(ordinary))
        with self.assertRaisesRegex(ValueError, 'chained refresh ancestry is not supported'):
            run_refresh(ordinary, self.after, self.root / 'blocked-disguised-prior')

    def test_malformed_receipt_containers_and_manifest_raise_value_error(self):
        for field in (None, 'files', 'inputs', 'code_hashes', 'parent'):
            with self.subTest(field=field):
                output = self.result(name='malformed-' + str(field))
                path = output / 'refresh_receipt.json'
                receipt = json.loads(path.read_text())
                if field is None:
                    receipt = []
                elif field == 'parent':
                    receipt['inputs']['before'] = []
                else:
                    receipt[field] = []
                write_json(path, receipt)
                with self.assertRaisesRegex(ValueError, 'Malformed refresh receipt metadata'):
                    verify_refresh(output)
        output = self.result(name='malformed-manifest')
        write_json(output / 'run_manifest.json', [])
        self.reseal(output)
        with self.assertRaisesRegex(ValueError, 'manifest disagrees'):
            verify_refresh(output)


if __name__ == '__main__':
    unittest.main()
