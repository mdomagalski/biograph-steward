"""Byte-verified cache controls on invented published data, not biology labels."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet, qualified_workspace as module
from biograph_steward.client import digest, write_json
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import save_run


def clear_cache():
    with module._CACHE_LOCK:
        module._CACHE_KEY = None
        module._cached_full_load.cache_clear()


class QualifiedWorkspaceCacheTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        save_run(demo_snapshot(), self.root / 'run')
        gold_packet.export_packet(self.root / 'run', self.root / 'packet')
        gold_packet.save_decisions(self.root / 'packet', self.root / 'packet/decisions.template.json', self.root / 'retained')
        self.workspace = self.root / 'published'
        module.publish_workspace(self.root / 'retained', self.workspace)
        clear_cache()
        self.addCleanup(clear_cache)

    def test_same_bytes_reuse_full_replay_but_recheck_complete_fingerprint_twice(self):
        replay = module._load_workspace_uncached
        fingerprint = module._workspace_fingerprint
        with patch.object(module, '_load_workspace_uncached', wraps=replay) as calls, \
                patch.object(module, '_workspace_fingerprint', wraps=fingerprint) as checks:
            first = module.load_workspace(self.workspace)
            second = module.load_workspace(self.workspace)
        self.assertEqual(calls.call_count, 1)
        self.assertEqual(checks.call_count, 4)
        self.assertEqual(first, second)
        self.assertIsNot(first[0], second[0])
        self.assertIsNot(first[2], second[2])
        self.assertEqual(module._cached_full_load.cache_info().maxsize, 1)

    def test_nested_returned_mutation_cannot_taint_a_subsequent_question_source(self):
        original = module.load_workspace(self.workspace)
        pristine = deepcopy(original)
        original[0]['targets'][0]['name'] = 'caller-mutated source'
        original[1].append({'invented': 'caller event'})
        original[2]['edges'][0]['evidence_record']['invented'] = 'caller mutation'
        self.assertEqual(module.load_workspace(self.workspace), pristine)

    def test_same_length_changed_graph_with_restored_mtime_fails_replay(self):
        module.load_workspace(self.workspace)
        path = self.workspace / 'graph.json'
        old = path.stat()
        raw = path.read_bytes()
        changed = raw.replace(b'synthetic_demo', b'synthetic_demO', 1)
        self.assertNotEqual(raw, changed)
        self.assertEqual(len(raw), len(changed))
        path.write_bytes(changed)
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertEqual(path.stat().st_mtime_ns, old.st_mtime_ns)
        with self.assertRaisesRegex(ValueError, 'does not replay'):
            module.load_workspace(self.workspace)
        self.assertEqual(module._cached_full_load.cache_info().currsize, 0)

    def test_same_length_resealed_marker_with_restored_mtime_cannot_hit_old_cache(self):
        module.load_workspace(self.workspace)
        path = self.workspace / module.MARKER
        old, raw = path.stat(), path.read_bytes()
        value = json.loads(raw)
        value['starter_version'] = 'z' + value['starter_version'][1:]
        value.pop('content_sha256')
        value['content_sha256'] = digest(value)
        write_json(path, value)
        self.assertEqual(len(raw), path.stat().st_size)
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertTrue(gold_packet._sealed(value))
        with self.assertRaisesRegex(ValueError, 'does not replay'):
            module.load_workspace(self.workspace)

    def test_missing_and_added_files_are_not_hidden_by_a_warm_cache(self):
        module.load_workspace(self.workspace)
        path = self.workspace / 'snapshot.json'
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaises((ValueError, OSError)):
            module.load_workspace(self.workspace)
        path.write_bytes(raw)
        module.load_workspace(self.workspace)
        (self.workspace / 'unexpected.txt').write_text('extra source artifact')
        with self.assertRaisesRegex(ValueError, 'file inventory'):
            module.load_workspace(self.workspace)

    def test_symlink_is_rejected_even_if_target_has_identical_bytes(self):
        module.load_workspace(self.workspace)
        path = self.workspace / 'snapshot.json'
        external = self.root / 'same_bytes.json'
        external.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            module.load_workspace(self.workspace)

    def test_cold_change_after_full_replay_fails_and_does_not_cache_result(self):
        replay = module._load_workspace_uncached
        def mutate(folder):
            result = replay(folder)
            (folder / 'added_after_replay.txt').write_text('changed during request')
            return result
        with patch.object(module, '_load_workspace_uncached', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed during the request'):
                module.load_workspace(self.workspace)
        self.assertEqual(module._cached_full_load.cache_info().currsize, 0)

    def test_warm_change_during_fresh_copy_fails_before_returning(self):
        module.load_workspace(self.workspace)
        original = module.deepcopy
        def mutate(value):
            result = original(value)
            (self.workspace / 'added_during_copy.txt').write_text('changed during request')
            return result
        with patch.object(module, 'deepcopy', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed during the request'):
                module.load_workspace(self.workspace)
        self.assertEqual(module._cached_full_load.cache_info().currsize, 0)

    def test_changed_reader_binding_invalidates_otherwise_identical_source(self):
        replay, pins = module._load_workspace_uncached, module._reader_code_pins
        with patch.object(module, '_load_workspace_uncached', wraps=replay) as calls:
            module.load_workspace(self.workspace)
            with patch.object(module, '_reader_code_pins', side_effect=lambda: (*pins(), ('invented_helper', '0' * 64))):
                module.load_workspace(self.workspace)
                module.load_workspace(self.workspace)
            self.assertEqual(calls.call_count, 2)

    def test_concurrent_cold_requests_have_one_replay_and_distinct_results(self):
        replay = module._load_workspace_uncached
        with patch.object(module, '_load_workspace_uncached', wraps=replay) as calls:
            with ThreadPoolExecutor(max_workers=2) as workers:
                results = list(workers.map(module.load_workspace, [self.workspace] * 2))
        self.assertEqual(calls.call_count, 1)
        self.assertEqual(results[0], results[1])
        self.assertIsNot(results[0][2], results[1][2])

    def test_only_one_parsed_workspace_is_retained(self):
        other = self.root / 'second_publication'
        shutil.copytree(self.workspace, other)
        replay = module._load_workspace_uncached
        with patch.object(module, '_load_workspace_uncached', wraps=replay) as calls:
            module.load_workspace(self.workspace)
            module.load_workspace(other)
            module.load_workspace(self.workspace)
        self.assertEqual(calls.call_count, 3)
        self.assertEqual(module._cached_full_load.cache_info().currsize, 1)


if __name__ == '__main__':
    unittest.main()
