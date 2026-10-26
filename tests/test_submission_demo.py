"""Portable submission demonstration uses invented assay records, not evaluation labels."""
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_submission_demo as demo
from biograph_steward.assay_attachment import attach_assay
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import save_run
from test_assay_attachment import cohort_snapshot, make_publication


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs)['href'])


class SubmissionDemoTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source, self.publication, self.run, self.out = [self.root / name for name in
            ('source', 'publication', 'run', 'output')]
        save_run(cohort_snapshot(), self.source)
        make_publication(self.publication)
        attach_assay(self.source, self.publication, self.run)

    def test_complete_download_reopens_and_report_links_are_local_and_present(self):
        before = demo.files(self.run)
        result = demo.verify(self.run, self.out)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(all(result['checks'].values()))
        self.assertEqual(result['summary']['decisions']['prune'], 0)
        self.assertEqual(result['summary']['decisions']['keep'], 0)
        self.assertEqual(result['summary']['decisions']['abstain'], result['summary']['baseline_edges'])
        self.assertGreater(result['summary']['non_evaluable_assay_observations'], 0)
        self.assertEqual(demo.files(self.run), before)
        self.assertFalse(result['scientific_accuracy_measured'])
        self.assertFalse(result['independent_biological_improvement_demonstrated'])
        self.assertEqual(json.loads((self.out / 'verification.json').read_text()), result)
        page = (self.out / 'index.html').read_text()
        parser = Links(); parser.feed(page)
        self.assertTrue(parser.links)
        for link in parser.links:
            self.assertTrue((self.out / link).is_file(), link)
        self.assertIn('All decisions are abstentions', page)
        with self.assertRaisesRegex(ValueError, 'immutable'):
            demo.verify(self.run, self.out)

    def test_non_assay_and_source_mutation_fail_without_pass_receipt(self):
        ordinary = self.root / 'ordinary'
        save_run(demo_snapshot(), ordinary)
        with self.assertRaisesRegex(ValueError, 'real Pharos cohort'):
            demo.verify(ordinary, self.out)
        self.assertFalse(self.out.exists())
        original = demo.files
        calls = 0

        def source_changed(folder):
            nonlocal calls
            result = original(folder)
            if Path(folder) == self.run:
                calls += 1
                if calls > 1:
                    result['snapshot.json'] = 'changed-during-export'
            return result

        with patch.object(demo, 'files', side_effect=source_changed):
            with self.assertRaisesRegex(ValueError, 'original_run_file_inventory'):
                demo.verify(self.run, self.out)
        self.assertFalse((self.out / 'verification.json').exists())


if __name__ == '__main__':
    unittest.main()
