"""Source-filtered listings exclude foreign headers without source replay.

All records and sources here are invented; no model or source tool is loaded.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import canonical, digest
from biograph_steward.source_agent_jobs import FORMAT, list_source_agent_jobs


class SourceAgentListingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def record(self, suffix, source):
        folder = self.root / ('source_agent_' + suffix); folder.mkdir()
        raw = b'{"invented_result":true}\n'
        (folder / 'result.json').write_bytes(raw)
        manifest = {'format': FORMAT, 'job_id': folder.name, 'source_run': source,
                    'result_sha256': hashlib.sha256(raw).hexdigest()}
        self.write_manifest(folder, manifest)
        return folder

    def write_manifest(self, folder, manifest):
        manifest = {k: v for k, v in manifest.items() if k != 'content_sha256'}
        manifest['content_sha256'] = digest(manifest)
        (folder / 'manifest.json').write_text(canonical(manifest))

    def verified(self, folder, source):
        return {'job_id': folder.name, 'source_run': source,
                'status': 'completed', 'result': {'invented_fully_verified': True}}

    def test_foreign_source_is_excluded_before_full_verification(self):
        foreign = self.record('foreign', 'companion_workspace')
        selected = self.record('selected', 'current_workspace')
        verified = self.verified(selected, 'current_workspace')
        with patch('biograph_steward.source_agent_jobs.read_source_agent_job', return_value=verified) as reader:
            result = list_source_agent_jobs(self.root, source_run='current_workspace')
        reader.assert_called_once_with(selected, self.root)
        self.assertEqual(result['jobs'], [{k: v for k, v in verified.items() if k != 'result'}])
        self.assertEqual(result['unavailable_jobs'], [])
        self.assertNotIn(foreign.name, [row['job_id'] for row in result['jobs']])

    def test_unfiltered_listing_still_fully_verifies_every_record(self):
        folders = [self.record('one', 'one_workspace'), self.record('two', 'two_workspace')]
        def read(folder, root):
            return self.verified(folder, json.loads((folder / 'manifest.json').read_text())['source_run'])
        with patch('biograph_steward.source_agent_jobs.read_source_agent_job', side_effect=read) as reader:
            result = list_source_agent_jobs(self.root)
        self.assertEqual(reader.call_count, 2)
        self.assertEqual({row['job_id'] for row in result['jobs']}, {f.name for f in folders})

    def test_matching_self_sealed_metadata_never_bypasses_full_source_validation(self):
        folder = self.record('matching', 'current_workspace')
        with patch('biograph_steward.source_agent_jobs.read_source_agent_job', side_effect=ValueError('Source replay failed.')) as reader:
            result = list_source_agent_jobs(self.root, source_run='current_workspace')
        reader.assert_called_once_with(folder, self.root)
        self.assertEqual(result['jobs'], [])
        self.assertEqual(result['unavailable_jobs'], [{'job_id': folder.name, 'reason': 'Source replay failed.'}])

    def test_relabelled_header_cannot_qualify_an_unpinned_result(self):
        folder = self.record('relabelled', 'foreign_workspace')
        metadata = json.loads((folder / 'manifest.json').read_text())
        metadata['source_run'] = 'current_workspace'
        self.write_manifest(folder, metadata)
        (folder / 'result.json').write_text('{"changed_unpinned_result":true}')
        with patch('biograph_steward.source_agent_jobs._source', side_effect=AssertionError('Must reject bytes first.')) as replay:
            result = list_source_agent_jobs(self.root, source_run='current_workspace')
        replay.assert_not_called()
        self.assertEqual(result['jobs'], [])
        self.assertIn('differs from its saved manifest', result['unavailable_jobs'][0]['reason'])

    def test_malformed_headers_remain_unavailable_without_expensive_verification(self):
        folder = self.record('malformed', 'foreign_workspace')
        good = json.loads((folder / 'manifest.json').read_text())
        variants = ['{', '[]', ' ' * 20_001]
        for field, value in [('source_run', '../foreign'), ('source_run', None),
                             ('source_run', True), ('format', 'unknown'), ('job_id', 'source_agent_other')]:
            bad = deepcopy(good); bad[field] = value
            bad['content_sha256'] = digest({k: v for k, v in bad.items() if k != 'content_sha256'})
            variants.append(json.dumps(bad))
        bad = deepcopy(good); bad['content_sha256'] = '0' * 64; variants.append(json.dumps(bad))
        for raw in variants:
            with self.subTest(raw=raw[:80]):
                (folder / 'manifest.json').write_text(raw)
                with patch('biograph_steward.source_agent_jobs.read_source_agent_job') as reader:
                    result = list_source_agent_jobs(self.root, source_run='current_workspace')
                reader.assert_not_called()
                self.assertEqual(result['jobs'], [])
                self.assertEqual([row['job_id'] for row in result['unavailable_jobs']], [folder.name])

    def test_linked_manifest_and_directory_do_not_become_negative_filter_hints(self):
        folder = self.record('linked_manifest', 'foreign_workspace')
        manifest = folder / 'manifest.json'
        original = self.root / 'manifest-copy.json'; manifest.rename(original); manifest.symlink_to(original)
        linked = self.root / 'source_agent_linked_directory'; linked.symlink_to(folder, target_is_directory=True)
        with patch('biograph_steward.source_agent_jobs.read_source_agent_job') as reader:
            result = list_source_agent_jobs(self.root, source_run='current_workspace')
        reader.assert_not_called()
        self.assertEqual(result['jobs'], [])
        self.assertEqual({row['job_id'] for row in result['unavailable_jobs']}, {folder.name, linked.name})

    def test_invalid_requested_source_is_rejected_before_any_reader(self):
        for source in ('../foreign', True, '', 7):
            with self.subTest(source=source), patch('biograph_steward.source_agent_jobs.read_source_agent_job') as reader:
                with self.assertRaises(ValueError):
                    list_source_agent_jobs(self.root, source_run=source)
                reader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
