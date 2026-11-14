"""Input/source-pin tests need no torch, model, source dataset or reference."""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from .native import pinned, check_author_import_paths


class NativeInputTests(unittest.TestCase):
    def test_changed_or_linked_pinned_inputs_are_not_loaded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invented'; path.write_bytes(b'invented metadata')
            spec = {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(pinned(spec), path)
            link = Path(folder) / 'link'; link.symlink_to(path)
            with self.assertRaises(ValueError): pinned({**spec, 'file': str(link)})
            path.write_bytes(b'changed source')
            with self.assertRaises(ValueError): pinned(spec)

    def test_cached_transitive_author_module_cannot_bypass_source_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'pinned_author'; root.mkdir()
            inside = root / 'base.py'; inside.write_text('# invented')
            outside = Path(folder) / 'other_version.py'; outside.write_text('# invented')
            with patch.dict('sys.modules', {'deepgo._invented_cached': SimpleNamespace(__file__=str(inside))}):
                check_author_import_paths(root)
            with patch.dict('sys.modules', {'deepgo._invented_cached': SimpleNamespace(__file__=str(outside))}):
                with self.assertRaisesRegex(ValueError, 'transitive'):
                    check_author_import_paths(root)


if __name__ == '__main__': unittest.main()
