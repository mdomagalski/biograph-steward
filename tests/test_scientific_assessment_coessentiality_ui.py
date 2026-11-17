"""Execute the actual v2 renderer on invented complete saved aggregates."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from biograph_steward import scientific_assessment as module
from test_scientific_assessment import fixtures
from test_scientific_assessment_coessentiality import coessentiality_fixtures
from test_scientific_assessment_ui import NODE, JS, HARNESS


@unittest.skipUnless(Path(NODE).is_file(), 'Node runtime unavailable for renderer execution')
class ScientificAssessmentCoessentialityUITests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        paths, pins = fixtures(root / 'base')
        extra, extra_pins = coessentiality_fixtures(root / 'extra', paths, pins)
        self.summary = module.publish(paths, root / 'publication', expected_source_pins=pins,
            coessentiality_reports=extra, expected_coessentiality_pins=extra_pins)['summary']

    def test_actual_renderer_keeps_full_curves_controls_absolute_fractions_and_limits(self):
        self.summary['coessentiality']['limitations'].append('<script>remains literal evidence text</script>')
        result = subprocess.run([NODE, '-e', HARNESS, str(JS)], input=json.dumps({
            'summary': self.summary, 'options': {'publicationId': 'assessment_v2'}}),
            text=True, capture_output=True, check=True)
        value = json.loads(result.stdout)
        self.assertIsNone(value['error'])
        self.assertEqual(value['tags'].count('table'), 10)  # original5 + complete optional5
        self.assertNotIn('script', value['tags'])
        self.assertIn('<script>remains literal evidence text</script>', value['text'])
        combined = ' '.join(value['text'])
        for phrase in ('92 fixed measured-gene queries', '3968 different-chromosome primary pairs',
                       'complete N=1–10', 'Twenty count-matched', 'not confidence intervals',
                       'Absolute shared-context hit fractions', 'All 87 arms and 5 declared scopes',
                       'not a CRC-specific reference', 'now consumed', 'not edge-truth probabilities',
                       'did not show a consistent advantage', '0.250000'):
            self.assertIn(phrase, combined)
        for role in module.COESS_NAMES:
            self.assertTrue(any(link['href'] == '/api/scientific-assessment/assessment_v2/files/sources/coess_'
                                + role + '.json' for link in value['links']))


if __name__ == '__main__':
    unittest.main()
