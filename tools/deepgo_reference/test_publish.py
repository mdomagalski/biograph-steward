"""Invented aggregate-only delivery checks; no models or reference inputs."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from .publish import FORMAT, prepare


def write(path, value):
    write_json(path, {**value, 'content_sha256': digest(value)})


class AggregatePublication(unittest.TestCase):
    def fixture(self, root, *, raw_case=False, hidden_path=False):
        rows = []
        for frame in ('primary', 'reserved'):
            for aspect in ('biological_process', 'molecular_function', 'cellular_component'):
                rows.append({'frame': frame, 'setting': 'partial', 'namespace': aspect,
                    'method': 'strict_alias_localplus', 'status': 'scored', 'eligible_proteins': 2,
                    'micro_Fmax': .2, 'IA_micro_Fmax': .1, 'macro_Fmax': .3, 'IA_macro_Fmax': .2,
                    'unweighted_Smin': 3., 'IA_weighted_Smin': 2.,
                    'source': '/data/operator/native.tsv',
                    'fixed_0_5': {'namespace': aspect, 'status': 'no_native_coverage',
                                  'PPV': None, 'recall': None, 'F1': None}})
        prior = deepcopy(rows) + [dict(deepcopy(rows[0]), method='invented_' + str(i)) for i in range(234)]
        prior[-1]['method'] = 'invented_<script>escape-me</script>'
        old = {'rows': prior, 'native_aggregate_source_files_sha256': {'/data/operator/native.tsv': 'a' * 64}}
        write(root / 'old.json', old)
        combined = deepcopy(rows)
        for row in combined:
            row.pop('source'); row['source_curve_sha256'] = 'b' * 64
            row['method'] = 'combined_strict_genemaniaplus'
        previous = {'format': 'biograph-steward.combined-development-results.v1',
            'new_outcome_rows': combined, 'earlier_240_outcome_rows': prior,
            'earlier_240_report_file_sha256': sha(root / 'old.json'),
            'earlier_240_report_content_sha256': __import__('json').loads((root / 'old.json').read_text())['content_sha256']}
        write(root / 'previous.json', previous)
        new = deepcopy(combined)
        for row in new:
            row['method'] = 'deepgose'; row['micro_Fmax'] = .25; row['source_curve_sha256'] = 'c' * 64
        comparisons = [{'frame': frame, 'readout': readout, 'candidate': 'deepgose',
            'comparator': 'strict_alias_localplus', 'paired_95_percentile_interval': [-.1, .2],
            'difference_mean': .05} for frame in ('primary', 'reserved') for readout in ('ordinary', 'IA_weighted')]
        source = {'format': FORMAT + '.results', 'scope': 'INVENTED, NOT SCIENTIFIC RESULTS',
            'new_outcome_rows': new, 'earlier_240_outcome_rows': prior,
            'earlier_six_combined_GM_outcome_rows': combined,
            'earlier_complete_comparison_file_sha256': sha(root / 'previous.json'),
            'denominators': [], 'paired_comparisons': comparisons,
            'predeclared_development_retention_gate': {'passed': False, 'rule': 'INVENTED FOUR-CI RULE',
                'automatic_product_or_graph_change': False, 'independent_confirmatory_gain_claimed': False},
            'caveats': ['INVENTED <script>escape-me</script>'],
            'input_files_sha256': {'/data/operator/aggregate.json': 'd' * 64}}
        if raw_case: source['case_id'] = 'must-not-publish'
        if hidden_path: source['unexpected'] = '/data/operator/private/file.txt'
        write(root / 'source.json', source)
        return new, comparisons

    def test_complete_inventory_numbers_intervals_nulls_and_escaping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); new, comparisons = self.fixture(root)
            report = prepare(root / 'source.json', root / 'previous.json', root / 'old.json',
                             sha(root / 'source.json'), root / 'public')
            import json
            prior = json.loads((root / 'public/prior_246_outcomes.json').read_text())
            self.assertEqual(len(prior['rows']), 246)
            self.assertEqual(report['all_outcome_slots'], 252)
            self.assertEqual(report['results']['new_outcome_rows'], new)
            self.assertEqual(report['results']['paired_comparisons'], comparisons)
            self.assertIsNone(report['results']['new_outcome_rows'][0]['fixed_0_5']['PPV'])
            self.assertEqual(report['results']['new_outcome_rows'][0]['IA_weighted_Smin'], 2.)
            raw = (root / 'public/report.json').read_text()
            self.assertNotIn('/data/', raw)
            html = (root / 'public/report.html').read_text()
            self.assertNotIn('<script>', html)
            self.assertIn('&lt;script&gt;escape-me&lt;/script&gt;', html)
            self.assertIn('All FOUR', html)
            self.assertIn('Not returned', html)
            self.assertIn('DEVELOPMENT', html)
            self.assertEqual(len(list((root / 'public').iterdir())), 5)

    def test_raw_case_or_unmapped_operator_path_fails_before_output(self):
        for options in ({'raw_case': True}, {'hidden_path': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); self.fixture(root, **options)
                with self.assertRaises(ValueError):
                    prepare(root / 'source.json', root / 'previous.json', root / 'old.json',
                            sha(root / 'source.json'), root / 'public')
                self.assertFalse((root / 'public').exists())

    def test_positive_max_appendix_cannot_flip_primary_and_is_bound_and_private(self):
        import json
        for mutation in (None, 'wrong_primary', 'raw_case'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); new, _ = self.fixture(root)
                source = json.loads((root / 'source.json').read_text()); source.pop('content_sha256')
                source['input_files_sha256']['/data/operator/status.json'] = 'e' * 64
                write(root / 'source.json', source)
                rows = []
                for row in new:
                    for method in ('deepgose_max', 'strict_alias_localplus_max'):
                        rows.append({**deepcopy(row), 'method': method, 'propagation': 'max'})
                pairs = [{'frame': frame, 'readout': kind, 'candidate': 'deepgose_max',
                    'comparator': 'strict_alias_localplus_max', 'paired_95_percentile_interval': [.01, .2],
                    'difference_mean': .1} for frame in ('primary', 'reserved')
                    for kind in ('ordinary', 'IA_weighted')]
                maximum = {'format': 'biograph-steward.deepgo-common-max-sensitivity.results.v1',
                    'actual_propagation': 'max', 'source_freeze_file_sha256': 'f' * 64,
                    'execution_freeze_file_sha256': 'a' * 64, 'rows': rows, 'new_outcome_slots': 12,
                    'paired_comparisons': pairs, 'primary_fill_252_outcomes_overwritten': False,
                    'primary_four_CI_adoption_rule_changed': False, 'automatic_adoption_from_sensitivity': False,
                    'new_source_model_training_or_reference_release': False,
                    'raw_reference_or_forecast_rows_included': False,
                    'input_files_sha256': {'/data/operator/max_curve.tsv': 'b' * 64}}
                execution = {'format': 'biograph-steward.deepgo-common-max-sensitivity.execution.v1',
                    'source_freeze_file_sha256': 'f' * 64, 'execution_freeze_file_sha256': 'a' * 64,
                    'primary_completion_file_sha256': 'e' * 64, 'actual_author_propagation': 'max',
                    'sequential_native_jobs': True, 'parent_fill_primary_and_adoption_rule_unchanged': True,
                    'new_model_calls': 0, 'new_reference_release': False}
                if mutation == 'wrong_primary': execution['primary_completion_file_sha256'] = '0' * 64
                if mutation == 'raw_case': maximum['case_id'] = 'must-not-publish'
                write(root / 'max.json', maximum); write(root / 'max_execution.json', execution)
                args = {'max_source': root / 'max.json', 'max_expected': sha(root / 'max.json'),
                    'max_execution': root / 'max_execution.json',
                    'max_execution_expected': sha(root / 'max_execution.json')}
                def publish():
                    return prepare(root / 'source.json', root / 'previous.json', root / 'old.json',
                                   sha(root / 'source.json'), root / 'public', **args)
                if mutation is not None:
                    with self.assertRaises(ValueError): publish()
                    self.assertFalse((root / 'public').exists()); continue
                report = publish(); appendix = json.loads((root / 'public/max_sensitivity.json').read_text())
                self.assertFalse(report['results']['predeclared_development_retention_gate']['passed'])
                self.assertFalse(appendix['primary_fill_retention_gate_unchanged']['passed'])
                self.assertFalse(appendix['automatic_adoption'])
                self.assertEqual(report['results']['new_outcome_rows'], new)
                self.assertEqual(report['all_outcome_slots'], 252)
                self.assertEqual(appendix['results']['rows'], rows)
                self.assertEqual(appendix['results']['paired_comparisons'], pairs)
                self.assertEqual(len(list((root / 'public').iterdir())), 7)
                self.assertNotIn('/data/', (root / 'public/max_sensitivity.json').read_text())
                self.assertIn('max_sensitivity.html', (root / 'public/report.html').read_text())
                self.assertIn('not a literal reproduction', (root / 'public/max_sensitivity.html').read_text())


if __name__ == '__main__': unittest.main()
