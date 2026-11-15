"""Invented native publications qualify HTTP replay reuse, not biological truth."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import threading
import unittest
from unittest.mock import patch

from biograph_steward import reviews, saved_run_cache as module
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.questions import answer_question
import test_string_physical_source as source_fixture


def clear_cache():
    with module._LOCK:
        module._clear_locked()


class SavedRunCacheTests(unittest.TestCase):
    def setUp(self):
        fixture = source_fixture.NativePhysicalTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.baseline, self.run, _, self.graph = fixture.workspace()
        clear_cache()
        self.addCleanup(clear_cache)

    def test_same_bytes_reuse_one_full_replay_and_fresh_complete_fingerprints(self):
        original = reviews.read_run
        fingerprint = module._fingerprint
        with patch.object(reviews, 'read_run', wraps=original) as reader, \
                patch.object(module, '_fingerprint', wraps=fingerprint) as checks:
            cold = module.read_run(self.run)
            warm = module.read_run(self.run)
        self.assertEqual(cold, original(self.run))
        self.assertEqual(cold, warm)
        self.assertEqual(reader.call_count, 1)
        self.assertEqual(checks.call_count, 4)
        self.assertIsNot(cold[0], warm[0])
        self.assertIsNot(cold[2], warm[2])
        self.assertEqual(module._cached_full_read.cache_info().maxsize, 1)

    def test_nested_returned_mutation_cannot_contaminate_graph_snapshot_reviews_or_question(self):
        cold = module.read_run(self.run)
        pristine = deepcopy(cold)
        expected = answer_question(pristine[2], 'P04637', template='native_string_physical.v1',
                                   relations=['interactions'], view='candidates', source_run=self.run.name)
        cold[0]['targets'][0]['name'] = 'caller mutation'
        cold[1].append({'invented': 'caller review'})
        cold[2]['edges'][0]['evidence_record']['caller_mutation'] = True
        warm = module.read_run(self.run)
        self.assertEqual(warm, pristine)
        self.assertEqual(answer_question(warm[2], 'P04637', template='native_string_physical.v1',
                         relations=['interactions'], view='candidates', source_run=self.run.name), expected)

    def test_same_size_changed_graph_with_restored_mtime_fails_and_evicts(self):
        module.read_run(self.run)
        path = self.run / 'graph.json'
        original = path.read_bytes(); stamp = path.stat()
        changed = original.replace(b'live_pharos', b'live_pharOs', 1)
        self.assertNotEqual(changed, original)
        self.assertEqual(len(changed), len(original))
        path.write_bytes(changed)
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, 'does not replay'):
            module.read_run(self.run)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 0)
        path.write_bytes(original)
        self.assertEqual(module.read_run(self.run)[2], self.graph)

    def test_resealed_source_projection_still_fails_original_semantic_validation(self):
        module.read_run(self.run)
        publication = self.run / 'extension_sources/string_physical'
        path = publication / 'projection.json'
        projection = json.loads(path.read_text())
        projection['pair_ledger'][0]['native_physical_score'] = 999
        projection.pop('content_sha256')
        projection['content_sha256'] = digest(projection)
        write_json(path, projection)
        metadata = publication / 'publication.json'
        manifest = json.loads(metadata.read_text())
        manifest['projection_sha256'] = projection['content_sha256']
        manifest['files']['projection.json'] = sha(path)
        manifest.pop('content_sha256')
        manifest['content_sha256'] = digest(manifest)
        write_json(metadata, manifest)
        with self.assertRaisesRegex(ValueError, 'complete source replay'):
            module.read_run(self.run)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 0)

    def test_added_file_and_empty_directory_invalidate_without_adding_new_source_rules(self):
        original = reviews.read_run
        with patch.object(reviews, 'read_run', wraps=original) as reader:
            module.read_run(self.run)
            extra = self.run / 'operator_note.txt'
            extra.write_text('Invented extra non-source note; ordinary reader permits it.')
            self.assertEqual(module.read_run(self.run), original(self.run))
            extra.unlink()
            directory = self.run / 'empty_non_source_directory'
            directory.mkdir()
            self.assertEqual(module.read_run(self.run), original(self.run))
            self.assertEqual(reader.call_count, 3)
        # Source-kind inventory remains strict under the original reader.
        (self.run / 'extension_sources/unexpected_source').mkdir()
        with self.assertRaisesRegex(ValueError, 'source inventory'):
            module.read_run(self.run)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 0)

    def test_deleted_source_file_and_symlink_directory_never_reuse_a_warm_graph(self):
        module.read_run(self.run)
        path = self.run / 'extension_sources/string_physical/projection.json'
        raw = path.read_bytes(); path.unlink()
        with self.assertRaises((ValueError, OSError)):
            module.read_run(self.run)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 0)
        path.write_bytes(raw)
        module.read_run(self.run)
        (self.run / 'linked_directory').symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            module.read_run(self.run)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 0)

    def test_changed_new_reader_helper_pin_forces_replay_and_all_core_helpers_are_pinned(self):
        names = {row[0] for row in module._reader_code_pins()}
        for name in ('reviews.py', 'saved_run_cache.py', 'goa_locations.py', 'string_physical_source.py', 'string_native.py'):
            self.assertIn(name, names)
        original, file_sha = reviews.read_run, module.sha
        def changed(path):
            return '0' * 64 if Path(path).name == 'goa_locations.py' else file_sha(path)
        with patch.object(reviews, 'read_run', wraps=original) as reader:
            module.read_run(self.run)
            with patch.object(module, 'sha', side_effect=changed):
                module.read_run(self.run)
                module.read_run(self.run)
            self.assertEqual(reader.call_count, 2)

    def test_replaced_underlying_reader_binding_cannot_reuse_the_previous_result(self):
        original = reviews.read_run
        with patch.object(reviews, 'read_run', wraps=original) as first:
            module.read_run(self.run)
            self.assertEqual(first.call_count, 1)
        with patch.object(reviews, 'read_run', wraps=original) as second:
            module.read_run(self.run)
            module.read_run(self.run)
            self.assertEqual(second.call_count, 1)

    def test_concurrent_cold_requests_do_one_semantic_read_and_return_independent_graphs(self):
        original, eligible = reviews.read_run, module._eligible
        in_reader, second_entered, release = threading.Event(), threading.Event(), threading.Event()
        first_ident = []
        def observed_eligibility(folder):
            if first_ident and threading.get_ident() != first_ident[0]:
                second_entered.set()
            return eligible(folder)
        def blocked(folder):
            first_ident.append(threading.get_ident())
            in_reader.set()
            if not release.wait(5):
                raise AssertionError('Test cold replay was not released.')
            return original(folder)
        with patch.object(reviews, 'read_run', side_effect=blocked) as reader, \
                patch.object(module, '_eligible', side_effect=observed_eligibility):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(module.read_run, self.run)
                self.assertTrue(in_reader.wait(5))
                second = pool.submit(module.read_run, self.run)
                try:
                    self.assertTrue(second_entered.wait(5))
                finally:
                    release.set()
                values = [first.result(), second.result()]
        self.assertEqual(reader.call_count, 1)
        self.assertEqual(values[0], values[1])
        self.assertIsNot(values[0][2], values[1][2])

    def test_source_change_during_cold_replay_fails_and_evicts(self):
        original = reviews.read_run
        def mutate(folder):
            result = original(folder)
            (self.run / 'changed_during_read.txt').write_text('Invented mutation.')
            return result
        with patch.object(reviews, 'read_run', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed during the request'):
                module.read_run(self.run)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 0)

    def test_source_change_during_warm_copy_fails_and_evicts(self):
        module.read_run(self.run)
        original = module.deepcopy
        def mutate(value):
            result = original(value)
            (self.run / 'changed_during_copy.txt').write_text('Invented mutation.')
            return result
        with patch.object(module, 'deepcopy', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed during the request'):
                module.read_run(self.run)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 0)

    def test_mode_changes_and_qualified_runs_pass_through_the_original_reader(self):
        original = reviews.read_run
        with patch.object(reviews, 'read_run', wraps=original) as reader, \
                patch.object(module, '_fingerprint', side_effect=AssertionError('Ineligible run must not be fingerprint-cached.')):
            self.assertEqual(module.read_run(self.baseline), original(self.baseline))
            self.assertEqual(module.read_run(self.baseline), original(self.baseline))
            self.assertEqual(reader.call_count, 2)
        (self.run / 'qualified_workspace.json').write_text('{}')
        sentinel = ({'invented': 'qualified loader'}, [], {'invented': 'qualified graph'})
        with patch.object(reviews, 'read_run', return_value=sentinel) as reader, \
                patch.object(module, '_fingerprint', side_effect=AssertionError('Qualified path must pass through.')):
            self.assertIs(module.read_run(self.run), sentinel)
            self.assertEqual(reader.call_count, 1)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 0)

    def test_only_one_ordinary_parsed_workspace_is_retained(self):
        other = self.root / 'second_ordinary'
        shutil.copytree(self.run, other)
        original = reviews.read_run
        with patch.object(reviews, 'read_run', wraps=original) as reader:
            module.read_run(self.run)
            module.read_run(other)
            module.read_run(self.run)
            self.assertEqual(reader.call_count, 3)
        self.assertEqual(module._cached_full_read.cache_info().currsize, 1)


if __name__ == '__main__':
    unittest.main()
