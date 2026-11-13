"""The actual assessment DOM renderer displays only invented aggregates."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from biograph_steward import scientific_assessment as module
from biograph_steward.file_utils import sha
from test_scientific_assessment import fixtures
from test_scientific_assessment_grounding import grounding_fixture
from test_scientific_assessment_ui import NODE, JS, HARNESS


@unittest.skipUnless(Path(NODE).is_file(), 'Node runtime unavailable for renderer execution')
class ScientificAssessmentGroundingUITests(unittest.TestCase):
    def test_v3_dom_keeps_component_denominators_scope_safe_text_and_receipt_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            paths, pins = fixtures(root / 'base')
            _, aggregate, _ = grounding_fixture(root / 'component')
            manifest = module.publish(paths, root / 'assessment', expected_source_pins=pins,
                grounding_report=aggregate, expected_grounding_pin=sha(aggregate))
            summary = manifest['summary']
            summary['grounding']['interpretation'] = '<script>literal test text</script>'
            completed = subprocess.run([NODE, '-e', HARNESS, str(JS)], input=json.dumps({
                'summary': summary, 'options': {'publicationId': 'assessment'}}),
                text=True, capture_output=True, check=True)
            result = json.loads(completed.stdout)
            self.assertIsNone(result['error'])
            self.assertNotIn('script', result['tags'])
            self.assertIn('<script>literal test text</script>', result['text'])
            self.assertIn('0.500000 (1/2)', result['text'])
            self.assertTrue(any('outside-endpoint cases are not negatives' in x for x in result['text']))
            self.assertTrue(any('common-resolved intersection contains 2 cases' in x for x in result['text']))
            self.assertTrue(any('Not whole-Pharos precision' in x for x in result['text']))
            self.assertTrue(any(x['href'] == '/api/scientific-assessment/assessment/files/sources/grounding.json'
                                for x in result['links']))
            self.assertNotIn('PRIVATE-', '\n'.join(result['text']))


if __name__ == '__main__':
    unittest.main()
