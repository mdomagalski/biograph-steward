"""CLI replay must not silently drop an attached source publication."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from biograph_steward.__main__ import main
from biograph_steward.graph import save_run
from biograph_steward.reviews import read_run
from test_assay_attachment import cohort_snapshot, make_publication


class AssayCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.publication, self.attached = [self.root / name for name in ('source', 'publication', 'attached')]
        save_run(cohort_snapshot(), self.source)
        make_publication(self.publication)

    def command(self, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([str(arg) for arg in args])
        return code, out.getvalue(), err.getvalue()

    def attach(self):
        code, _, error = self.command('assay-attach', '--run', self.source,
                                     '--publication', self.publication, '--out', self.attached)
        self.assertEqual(code, 0, error)
        return read_run(self.attached)[2]

    def test_explicit_replay_preserves_complete_source_and_graph(self):
        graph = self.attach()
        replay = self.root / 'replay'
        code, _, error = self.command('replay', '--snapshot', self.attached / 'snapshot.json',
                                     '--assay-run', self.attached, '--out', replay)
        self.assertEqual(code, 0, error)
        self.assertEqual(read_run(replay)[2], graph)
        self.assertEqual((replay / 'assay_source/publication.json').read_bytes(),
                         (self.publication / 'publication.json').read_bytes())

    def test_implicit_drop_fails_without_publishing_output(self):
        self.attach()
        replay = self.root / 'replay'
        code, _, error = self.command('replay', '--snapshot', self.attached / 'snapshot.json', '--out', replay)
        self.assertEqual(code, 1)
        self.assertIn('--assay-run', error)
        self.assertFalse(replay.exists())

    def test_replay_requires_an_actual_attachment(self):
        replay = self.root / 'replay'
        code, _, error = self.command('replay', '--snapshot', self.source / 'snapshot.json',
                                     '--assay-run', self.source, '--out', replay)
        self.assertEqual(code, 1)
        self.assertIn('no qualified assay attachment', error)
        self.assertFalse(replay.exists())


if __name__ == '__main__':
    unittest.main()
