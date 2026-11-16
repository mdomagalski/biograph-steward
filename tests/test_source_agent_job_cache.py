"""Native positive-verification reuse on invented, fully replayable sources."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from biograph_steward import reviews, saved_run_cache, source_agent
from biograph_steward import source_agent_jobs as module
from biograph_steward.client import canonical, digest
from biograph_steward.webapp import verify_saved_refresh
from test_source_agent_http import InjectedClient
import test_string_physical_source as source_fixture


def clear():
    with module._VERIFICATION_LOCK:
        module._VERIFIED_SOURCES.clear()
    with saved_run_cache._LOCK:
        saved_run_cache._clear_locked()


class SourceAgentJobCacheTests(unittest.TestCase):
    def setUp(self):
        fixture = source_fixture.NativePhysicalTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        _, self.source, _, self.graph = fixture.workspace()
        self.result = source_agent.run_source_agent(
            'Inspect candidate native physical partners for UniProtKB:P04637.', self.graph,
            source_run=self.source.name, source_folder=self.source, client=InjectedClient())
        self.assertEqual(self.result['status'], 'completed')
        self.job_id = 'source_agent_positive_cache_fixture'
        module.save_source_agent_job(self.result, self.root, job_id=self.job_id)
        self.folder = self.root / self.job_id
        clear(); self.addCleanup(clear)

    def read(self):
        return module.read_source_agent_job(self.folder, self.root)

    def reseal(self, result):
        result['content_sha256'] = digest({k: v for k, v in result.items() if k != 'content_sha256'})
        raw = (canonical(result) + '\n').encode()
        (self.folder / 'result.json').write_bytes(raw)
        path = self.folder / 'manifest.json'; manifest = json.loads(path.read_text())
        manifest['result_sha256'] = hashlib.sha256(raw).hexdigest()
        manifest['content_sha256'] = digest({k: v for k, v in manifest.items() if k != 'content_sha256'})
        path.write_text(canonical(manifest) + '\n')

    def test_repeated_read_reuses_only_positive_verification_and_hashes_both_boundaries(self):
        reader, verifier, fingerprint = saved_run_cache.read_run, source_agent.verify_source_agent_result, saved_run_cache._fingerprint
        with patch.object(saved_run_cache, 'read_run', wraps=reader) as reads, \
                patch.object(source_agent, 'verify_source_agent_result', wraps=verifier) as verifies, \
                patch.object(saved_run_cache, '_fingerprint', wraps=fingerprint) as checks:
            cold = self.read(); warm = self.read()
        self.assertEqual(cold, warm)
        self.assertEqual(reads.call_count, 1); self.assertEqual(verifies.call_count, 1)
        self.assertEqual(checks.call_count, 6, 'Four agent boundary checks plus the cold graph reader boundaries.')
        self.assertEqual(list(module._VERIFIED_SOURCES.values()), [True])
        cold['result']['answer']['overview'] = 'Caller mutation'
        self.assertNotEqual(cold['result'], self.read()['result'])
        self.assertFalse(warm['actual_model_run'], 'An injected fixture never becomes actual-model evidence.')

    def test_changed_graph_bytes_with_original_size_and_mtime_fail_and_clear(self):
        self.read()
        path = self.source / 'graph.json'; original = path.read_bytes(); stamp = path.stat()
        changed = original.replace(b'live_pharos', b'live_pharOs', 1)
        self.assertNotEqual(original, changed); self.assertEqual(len(original), len(changed))
        path.write_bytes(changed); os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with self.assertRaises(ValueError): self.read()
        self.assertEqual(len(module._VERIFIED_SOURCES), 0)
        path.write_bytes(original)
        self.assertEqual(self.read()['result'], self.result)

    def test_added_deleted_files_and_directories_require_fresh_validation(self):
        verifier = source_agent.verify_source_agent_result
        with patch.object(source_agent, 'verify_source_agent_result', wraps=verifier) as verifies:
            self.read()
            extra = self.source / 'ordinary-extra.txt'; extra.write_text('New inventory member')
            self.read(); extra.unlink(); self.read()
            folder = self.source / 'empty-extra'; folder.mkdir()
            self.read(); folder.rmdir(); self.read()
        self.assertEqual(verifies.call_count, 5)

    def test_a_linked_source_member_is_not_a_warm_hit(self):
        self.read()
        link = self.source / 'linked-extra'; link.symlink_to(self.source / 'snapshot.json')
        with self.assertRaises(ValueError): self.read()
        self.assertEqual(len(module._VERIFIED_SOURCES), 0)

    def test_resealed_changed_result_requires_real_verification_and_cannot_poison_reuse(self):
        self.read(); changed = deepcopy(self.result)
        changed['answer']['overview'] = 'Unsupported replacement answer'
        self.reseal(changed)
        with self.assertRaisesRegex(ValueError, 'saved query, cited answer or focused graph'):
            self.read()
        self.assertEqual(len(module._VERIFIED_SOURCES), 0)
        self.reseal(deepcopy(self.result)); self.assertEqual(self.read()['result'], self.result)

    def test_warm_source_marker_never_bypasses_job_bytes_manifest_seal_or_header(self):
        self.read()
        path = self.folder / 'manifest.json'; original = path.read_bytes()
        manifest = json.loads(original); manifest['status'] = 'completed_empty'
        manifest['content_sha256'] = digest({k: v for k, v in manifest.items() if k != 'content_sha256'})
        path.write_text(canonical(manifest) + '\n')
        with self.assertRaisesRegex(ValueError, 'metadata differs'): self.read()
        path.write_bytes(original)
        manifest = json.loads(original); manifest['content_sha256'] = '0' * 64
        path.write_text(canonical(manifest))
        with self.assertRaisesRegex(ValueError, 'manifest seal'): self.read()
        path.write_bytes(original)
        result = self.folder / 'result.json'; raw = result.read_bytes()
        result.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'result differs'): self.read()
        result.write_bytes(raw)
        self.assertEqual(self.read()['result'], self.result)

    def test_reader_verifier_refresh_and_transitive_builder_bindings_invalidate(self):
        self.read()
        for target, name in ((saved_run_cache, 'read_run'), (source_agent, 'verify_source_agent_result')):
            original = getattr(target, name)
            with self.subTest(binding=name), patch.object(target, name, wraps=original) as replaced:
                self.read(); self.assertEqual(replaced.call_count, 1)
        with patch('biograph_steward.webapp.verify_saved_refresh', wraps=verify_saved_refresh) as refresh:
            self.read(); self.assertEqual(refresh.call_count, 1)
        verifier = source_agent.verify_source_agent_result
        with patch.object(source_agent, 'verify_source_agent_result', wraps=verifier) as verifies:
            self.read()
            with patch.object(reviews, 'build_graph', wraps=reviews.build_graph):
                self.read()
            self.assertEqual(verifies.call_count, 2)

    def test_refresh_construction_assay_qualified_and_reference_markers_never_reuse(self):
        # Even a biological_extension manifest is insufficient when another
        # workflow marker could entail dependencies beyond this source folder.
        self.read()
        for name in module._UNCACHED_SOURCE_MARKERS:
            marker = self.source / name
            with self.subTest(marker=name):
                marker.symlink_to(self.root / 'missing-marker-target')
                with patch('biograph_steward.webapp.verify_saved_refresh', side_effect=ValueError('Authoritative guard executed.')) as refresh:
                    with self.assertRaisesRegex(ValueError, 'Authoritative guard executed'): self.read()
                    with self.assertRaisesRegex(ValueError, 'Authoritative guard executed'): self.read()
                self.assertEqual(refresh.call_count, 2)
                self.assertEqual(len(module._VERIFIED_SOURCES), 0)
                marker.unlink()

    def test_real_qualified_marker_fails_closed_in_the_original_reader(self):
        self.read(); (self.source / 'qualified_workspace.json').write_text('{}')
        for _ in range(2):
            with self.assertRaises((ValueError, KeyError)): self.read()
            self.assertEqual(len(module._VERIFIED_SOURCES), 0)

    def test_mutation_during_verification_never_publishes_a_positive_marker(self):
        original = source_agent.verify_source_agent_result
        def mutate(result, **kwargs):
            original(result, **kwargs)
            result['answer']['overview'] = 'Changed during verification'
        with patch.object(source_agent, 'verify_source_agent_result', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'result changed during verification'): self.read()
        self.assertEqual(len(module._VERIFIED_SOURCES), 0)

    def test_concurrent_cold_reads_run_one_semantic_verification(self):
        barrier = threading.Barrier(6); original = source_agent.verify_source_agent_result
        def verify(*args, **kwargs):
            time.sleep(.04)
            return original(*args, **kwargs)
        def read():
            barrier.wait(timeout=5)
            return self.read()
        with patch.object(source_agent, 'verify_source_agent_result', side_effect=verify) as verifies:
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(lambda _: read(), range(6)))
        self.assertEqual(verifies.call_count, 1)
        self.assertTrue(all(r == results[0] for r in results))

    def test_cache_is_bounded_to_eight_boolean_markers(self):
        verifier = source_agent.verify_source_agent_result
        with patch.object(source_agent, 'verify_source_agent_result', wraps=verifier) as verifies:
            for index in range(10):
                result = deepcopy(self.result)
                # A nonsemantic audit field has its own full-result key, and
                # the unchanged verifier still validates each complete result.
                result['cache_test_audit'] = index
                self.reseal(result); self.read()
        self.assertEqual(verifies.call_count, 10)
        self.assertEqual(len(module._VERIFIED_SOURCES), 8)
        self.assertTrue(all(value is True for value in module._VERIFIED_SOURCES.values()))


if __name__ == '__main__':
    unittest.main()
