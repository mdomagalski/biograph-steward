"""Optional checks against real upstream validators, never a schema stand-in."""
import copy
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tempfile
import unittest

from biograph_steward.standards_validation import PACKAGE_VERSIONS, validate_projection, verify_resources


RESOURCES = Path(__file__).resolve().parents[1] / 'runs/export_standards_resources_20261025'


def optional_environment_available():
    try:
        return (RESOURCES.is_dir()
                and all(version(name) == wanted for name, wanted in PACKAGE_VERSIONS.items()))
    except PackageNotFoundError:
        return False


@unittest.skipUnless(optional_environment_available(), 'Requires pinned optional validator environment and source resources.')
class StandardsValidationTest(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            {'id': 'UniProtKB:P00533', 'name': 'EGFR', 'category': ['biolink:Protein']},
            {'id': 'REACT:R-HSA-177929', 'name': 'Signaling by EGFR', 'category': ['biolink:Pathway']},
        ]
        self.edges = [{'id': 'edge:probe', 'subject': 'UniProtKB:P00533',
                       'predicate': 'biolink:participates_in', 'object': 'REACT:R-HSA-177929',
                       'knowledge_level': 'not_provided', 'agent_type': 'not_provided',
                       'primary_knowledge_source': 'infores:reactome',
                       'aggregator_knowledge_source': ['infores:pharos'], 'publications': []}]

    def test_kgx_pass_does_not_override_schema_and_domain_failures(self):
        original = copy.deepcopy((self.nodes, self.edges))
        report = validate_projection(self.nodes, self.edges, RESOURCES)
        self.assertEqual(report['kgx']['status'], 'passed')
        self.assertEqual(report['kgx_jsonl_roundtrip']['status'], 'passed')
        self.assertEqual(report['published_json_schema']['status'], 'failed')
        self.assertEqual(report['published_json_schema']['error_counts'], {'node:enum': 2})
        self.assertEqual(report['declared_domain_range_and_predicate_audit']['status'], 'review_required')
        self.assertFalse(report['full_conformance'])
        self.assertFalse(report['biological_validation_performed'])
        self.assertEqual((self.nodes, self.edges), original)

    def test_unknown_predicate_is_rejected(self):
        self.edges[0]['predicate'] = 'biograph:has_interaction_annotation'
        report = validate_projection(self.nodes, self.edges, RESOURCES)
        self.assertEqual(report['kgx']['status'], 'failed')
        self.assertIn('INVALID_EDGE_PREDICATE', report['kgx']['messages']['ERROR'])

    def test_empty_projection_is_not_a_validation_success(self):
        report = validate_projection([], [], RESOURCES)
        self.assertEqual(report['status'], 'no_supported_records')
        self.assertEqual(report['kgx']['status'], 'not_evaluated')
        self.assertEqual(report['kgx_jsonl_roundtrip']['status'], 'not_evaluated')
        self.assertFalse(report['full_conformance'])

    def test_nested_evidence_does_not_silently_pass_lossless_roundtrip(self):
        self.edges[0]['original_record'] = {'qualifiers': {'negated': None}, 'source': 'Pharos'}
        report = validate_projection(self.nodes, self.edges, RESOURCES)
        self.assertEqual(report['kgx']['status'], 'passed')
        self.assertEqual(report['kgx_jsonl_roundtrip']['status'], 'not_lossless')
        self.assertEqual(report['kgx_jsonl_roundtrip']['changed_records'], 1)
        self.assertIsNone(self.edges[0]['original_record']['qualifiers']['negated'])


class StandardsResourceTest(unittest.TestCase):
    def test_modified_upstream_schema_is_rejected_before_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'biolink-model.yaml').write_text('version: 4.4.6\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch: biolink-model.yaml'):
                verify_resources(temp)


if __name__ == '__main__':
    unittest.main()
