"""Invented-only checks for the optional source-reproduction boundary."""
from contextlib import redirect_stdout
import gzip
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import guard


class RecipeGuardTests(unittest.TestCase):
    def fixture(self, root):
        root = root.resolve()
        inputs = root / 'inputs'; inputs.mkdir()
        author = root / 'author'; author.mkdir()
        helper = author / 'invented.py'; helper.write_text('# invented only\n')
        source = inputs / 'invented.gaf.gz'
        with gzip.open(source, 'wb') as stream:
            stream.write(b'!gaf-version: 2.2\n!date-generated: 2000-01-01\n!generated-by: INVENTED\n'
                         b'invented annotation bytes; never a real reference case\n')
        spec = {'local_name': source.name, 'required_for_reference': True,
                'bytes': source.stat().st_size, 'sha256': guard.sha(source),
                'header_required': ['!gaf-version: 2.2', '!date-generated: 2000-01-01',
                                    '!generated-by: INVENTED']}
        manifest = {'sources': {'gaf_t1': spec}, 'native_helpers': {
            'commit': 'invented', 'files_sha256': {'invented.py': guard.sha(helper)}}}
        return inputs, author, source, manifest

    def test_reference_access_boundary_precedes_any_input_read(self):
        with patch.object(guard, 'member') as read:
            with self.assertRaisesRegex(ValueError, 'verify hashes reference inputs'):
                guard.verify({}, '/invented', '/invented')
            read.assert_not_called()

    def test_pinned_bytes_and_native_header_pass_without_executing_helpers(self):
        with tempfile.TemporaryDirectory() as temp:
            inputs, author, source, manifest = self.fixture(Path(temp))
            result = guard.verify(manifest, inputs, author, acknowledge_reference_access=True)
            self.assertEqual(result['status'], 'pinned_input_bytes_verified_pipeline_not_executed')
            self.assertFalse(result['native_helper_execution'])
            self.assertFalse(result['runtime_verified'])
            self.assertTrue(result['sources']['gaf_t1']['header_checked'])

    def test_changed_source_bytes_and_header_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            inputs, author, source, manifest = self.fixture(Path(temp))
            data = bytearray(source.read_bytes()); data[-1] ^= 1; source.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'SHA256 changed'):
                guard.verify(manifest, inputs, author, acknowledge_reference_access=True)
            manifest['sources']['gaf_t1']['sha256'] = guard.sha(source)
            source.unlink()
            with gzip.open(source, 'wb') as stream:
                stream.write(b'!gaf-version: 2.2\n!date-generated: 2000-01-02\n!generated-by: INVENTED\nrow\n')
            manifest['sources']['gaf_t1'].update(bytes=source.stat().st_size, sha256=guard.sha(source))
            with self.assertRaisesRegex(ValueError, 'header changed'):
                guard.verify(manifest, inputs, author, acknowledge_reference_access=True)

    def test_changed_helper_or_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            inputs, author, source, manifest = self.fixture(Path(temp))
            (author / 'invented.py').write_text('# changed\n')
            with self.assertRaisesRegex(ValueError, 'upstream helper differs'):
                guard.verify(manifest, inputs, author, acknowledge_reference_access=True)
            saved = inputs / 'saved.gz'; source.rename(saved); source.symlink_to(saved)
            with self.assertRaisesRegex(ValueError, 'symlinked'):
                guard.verify(manifest, inputs, author, acknowledge_reference_access=True)

    def test_explicit_directory_alias_keeps_same_pinned_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            inputs, author, source, manifest = self.fixture(root)
            alias = root / 'input-directory-alias'; alias.symlink_to(inputs, target_is_directory=True)
            result = guard.verify(manifest, alias, author, acknowledge_reference_access=True)
            self.assertEqual(result['sources']['gaf_t1']['sha256'], guard.sha(source))

    def test_published_manifest_and_exact_executed_snapshots_are_self_consistent(self):
        manifest, pin = guard.load_manifest()
        self.assertEqual(len(pin), 64)
        self.assertEqual(len(manifest['executed_driver_snapshots']), 3)
        self.assertEqual(manifest['sources']['gaf_t1']['bytes'], 11061135)
        self.assertIn('!date-generated: 2026-11-04 15:05',
                      manifest['sources']['gaf_t1']['header_required'])
        self.assertTrue(manifest['sources']['gaf_t1']['mutable_download_URL'])
        self.assertEqual(manifest['recorded_runtime']['Bio'], '1.85')

    def test_describe_does_not_inspect_reference_inputs(self):
        with patch.object(guard, 'verify', side_effect=AssertionError('no reference access')), \
             redirect_stdout(io.StringIO()):
            result = guard.main(['describe'])
        self.assertFalse(result['reference_inputs_opened'])


if __name__ == '__main__':
    unittest.main()
