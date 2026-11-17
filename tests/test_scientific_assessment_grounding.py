"""Invented component aggregates exercise delivery; none are biological gold."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward import scientific_assessment as module
from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from tools.grounding_claims.score import compare_methods
from test_scientific_assessment import fixtures, sealed
from test_scientific_assessment_coessentiality import coessentiality_fixtures


def grounding_fixture(root, *, empty=False):
    root.mkdir()
    cases = [] if empty else [{'case_id': 'PRIVATE-CASE-' + str(i), 'pa_hash': str(i), 'source_hash': str(-i)}
                              for i in range(1, 5)]
    labels = {(r['pa_hash'], r['source_hash']): 'grounding_error' if i < 2 else 'correctly_grounded'
              for i, r in enumerate(cases)}
    states = {'lexical': ['candidate_conflict', 'unresolved', 'no_conflict', 'model_error'],
              'sentence': ['candidate_conflict', 'candidate_conflict', 'no_conflict', 'candidate_conflict'],
              'publication': ['no_conflict', 'candidate_conflict', 'candidate_conflict', 'unresolved']}
    comparison = compare_methods(cases, {arm: {r['case_id']: state for r, state in zip(cases, values)}
                                         for arm, values in states.items()}, labels)
    report = sealed({'format': 'biograph-steward.expert-grounding-component-evaluation.v1',
        'reference': {'DOI': '10.15252/msb.202211325', 'Zenodo': 7559353,
            'data_license': 'CC-BY-NC-SA-4.0', 'expert_labels_assigned_by_project_AI': False},
        'split': 'test', 'primary_frame_cases': len(cases) + 2, 'admitted_endpoint_cases': len(cases),
        'outside_endpoint_cases': 2, 'comparison': comparison,
        'selected_native_curation_tag_counts': {'PRIVATE-NATIVE-TAG': 999},
        'input_files_sha256': {'PRIVATE-LOCAL-PATH': '9' * 64},
        'private_source_text': 'PRIVATE-STATEMENT-TEXT',
        'evaluation_freeze_content_sha256': '1' * 64, 'implementation_sha256': '2' * 64,
        'scoring_helper_sha256': '3' * 64,
        'native_grounder_training_paper_independence_established': False,
        'automatic_corrections_or_prunes_performed': False, 'new_gold_labels_created': False,
        'underlying_biological_truth_measured': False, 'whole_graph_accuracy_estimated': False,
        'source_graph_or_original_reference_changed': False})
    source = root / 'private_evaluator.json'
    write_json(source, report)
    output = root / 'aggregate.json'
    receipt = module.prepare_grounding_aggregate(source, output, expected_report_pin=sha(source))
    return source, output, receipt


class ScientificAssessmentGroundingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.paths, self.pins = fixtures(self.root / 'base')
        self.source, self.aggregate, self.receipt = grounding_fixture(self.root / 'component')

    def publish(self, name='publication', **kwargs):
        return module.publish(self.paths, self.root / name, expected_source_pins=self.pins,
            grounding_report=self.aggregate, expected_grounding_pin=sha(self.aggregate), **kwargs)

    def change_aggregate(self, change):
        value = json.loads(self.aggregate.read_text())
        change(value)
        write_json(self.aggregate, sealed(value))

    def test_sanitizer_excludes_case_ids_native_tags_source_text_and_private_paths(self):
        text = self.aggregate.read_text()
        self.assertNotIn('PRIVATE-', text)
        self.assertNotIn('case_ids', self.receipt['common_resolved_secondary'])
        self.assertNotIn('case_ids', self.receipt)
        self.assertEqual(self.receipt['source_report_file_sha256'], sha(self.source))
        self.assertEqual(self.receipt['evaluation_freeze_content_sha256'], '1' * 64)
        self.assertEqual(self.receipt['reference']['data_license'], 'CC-BY-NC-SA-4.0')
        self.assertFalse(self.receipt['raw_reference_rows_or_case_ids_included'])
        self.assertFalse(self.receipt['native_curation_tags_included'])

    def test_v3_roundtrip_preserves_full_denominators_secondary_scope_and_separate_axis(self):
        manifest = self.publish()
        loaded, summary, files = module.load_publication(self.root / 'publication')
        self.assertEqual(loaded, manifest)
        self.assertEqual(manifest['format'], module.FORMAT_V3)
        self.assertNotIn('coessentiality', summary)
        self.assertEqual(set(files), module.PUBLIC_FILES | {module.GROUNDING_FILE, 'publication.json'})
        g = summary['grounding']
        self.assertEqual((g['primary_frame_cases'], g['admitted_endpoint_cases'], g['outside_endpoint_cases']), (6, 4, 2))
        self.assertEqual(g['metrics_by_arm']['lexical']['error_recall'], 0.5)
        self.assertEqual(g['metrics_by_arm']['lexical']['resolved_accuracy'], 1.0)
        self.assertEqual(g['metrics_by_arm']['lexical']['metric_denominators']['resolved_accuracy'], 2)
        self.assertEqual(g['metrics_by_arm']['lexical']['abstention_cases'], 2)
        self.assertEqual(g['common_resolved_secondary']['n_cases'], 2)
        self.assertEqual(len(g['paired_comparisons']), 3)
        self.assertIsNone(summary['whole_graph_scientific_precision'])
        self.assertFalse(summary['prospective_prediction_gain_established'])
        self.assertIn(b'not pooled', files['README.txt'])
        self.assertNotIn(b'PRIVATE-', b''.join(files.values()))
        self.assertEqual(files[module.GROUNDING_FILE], self.aggregate.read_bytes())
        self.assertIn(b'0.500000 (1/2)', files['report.html'])
        self.assertEqual(module.list_publications(self.root)['assessments'][0]['id'], 'publication')

    def test_v3_can_preserve_the_existing_complete_coessentiality_component(self):
        extra, pins = coessentiality_fixtures(self.root / 'coess', self.paths, self.pins)
        self.publish(coessentiality_reports=extra, expected_coessentiality_pins=pins)
        _, summary, files = module.load_publication(self.root / 'publication')
        self.assertEqual(set(files), module.ALL_PUBLIC_FILES | {'publication.json'})
        self.assertIn('coessentiality', summary)
        self.assertIn('grounding', summary)
        self.assertEqual(len(summary['sources']), 13)

    def test_undefined_metrics_remain_none_even_with_no_admitted_endpoint_cases(self):
        _, path, receipt = grounding_fixture(self.root / 'empty', empty=True)
        for arm in module.GROUNDING_ARMS:
            self.assertIsNone(receipt['metrics_by_arm'][arm]['precision'])
        module.publish(self.paths, self.root / 'empty_publication', expected_source_pins=self.pins,
            grounding_report=path, expected_grounding_pin=sha(path))
        self.assertIn('undefined (0/0)', (self.root / 'empty_publication/report.html').read_text())

    def test_operator_pins_and_new_output_are_required_before_writing(self):
        output = self.root / 'bad.json'
        with self.assertRaisesRegex(ValueError, 'operator pin'):
            module.prepare_grounding_aggregate(self.source, output, expected_report_pin='0' * 64)
        self.assertFalse(output.exists())
        with self.assertRaisesRegex(ValueError, 'new JSON'):
            module.prepare_grounding_aggregate(self.source, self.aggregate, expected_report_pin=sha(self.source))
        with self.assertRaisesRegex(ValueError, 'together'):
            module.publish(self.paths, self.root / 'missing_pin', expected_source_pins=self.pins,
                           grounding_report=self.aggregate)

    def test_raw_evaluator_report_cannot_be_passed_as_the_public_aggregate(self):
        with self.assertRaisesRegex(ValueError, 'only aggregates'):
            module.publish(self.paths, self.root / 'raw', expected_source_pins=self.pins,
                grounding_report=self.source, expected_grounding_pin=sha(self.source))
        self.assertFalse((self.root / 'raw').exists())

    def test_extra_private_fields_are_rejected_at_top_level_and_inside_metrics(self):
        original = deepcopy(self.receipt)
        for level in ('top', 'nested'):
            value = deepcopy(original)
            target = value if level == 'top' else value['metrics_by_arm']['lexical']
            target['source_text'] = 'PRIVATE-STATEMENT-TEXT'
            write_json(self.aggregate, sealed(value))
            with self.subTest(level=level), self.assertRaisesRegex(ValueError, 'only aggregates'):
                self.publish(level)

    def test_abstentions_cannot_be_removed_from_error_recall_denominator(self):
        def change(value):
            m = value['metrics_by_arm']['lexical']
            m['error_recall'] = 1.0
            m['metric_denominators']['error_recall'] = 1
        self.change_aggregate(change)
        with self.assertRaisesRegex(ValueError, 'denominators'):
            self.publish()

    def test_count_bool_scope_promotion_and_invalid_secondary_subset_fail(self):
        for i, change in enumerate((
            lambda v: v.update(admitted_endpoint_cases=True),
            lambda v: v.update(whole_graph_accuracy_estimated=True),
            lambda v: v['common_resolved_secondary'].update(n_cases=4),
        )):
            write_json(self.aggregate, self.receipt)
            self.change_aggregate(change)
            with self.subTest(change=i), self.assertRaises(ValueError):
                self.publish('wrong_' + str(i))

    def test_paired_transitions_must_preserve_full_method_marginals(self):
        self.change_aggregate(lambda v: v['paired_comparisons'][0]['status_transitions']['no_conflict'].update(no_conflict=999))
        with self.assertRaisesRegex(ValueError, 'marginal counts'):
            self.publish()

    def test_resealed_summary_tamper_and_added_raw_payload_are_rejected(self):
        self.publish()
        folder = self.root / 'publication'
        manifest = json.loads((folder / 'publication.json').read_text())
        manifest['summary']['grounding']['interpretation'] = 'A whole graph accuracy claim.'
        write_json(folder / 'publication.json', sealed(manifest))
        with self.assertRaisesRegex(ValueError, 'summary or presentation'):
            module.load_publication(folder)
        self.publish('second')
        (self.root / 'second/raw_cases.jsonl').write_text('PRIVATE-CASE')
        with self.assertRaisesRegex(ValueError, 'additional files'):
            module.load_publication(self.root / 'second')


if __name__ == '__main__':
    unittest.main()
