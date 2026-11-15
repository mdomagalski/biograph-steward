"""Invented-data gates for the holdout boundary and complete paired comparison."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import assessment as module
from .assessment import (CANDIDATE, REQUIRED_ARMS, bootstrap_contrast, open_seal,
                         positive_interval, seal, validate_source_manifest, validate_source_slices,
                         select_context_arm)
from tools.learned_combination.reference import file_sha256
from tools.learned_combination.runner import NS_ASPECT, write_json


class ClaimTests(unittest.TestCase):
    def test_development_selector_uses_only_finite_scores_and_fixed_tie_preference(self):
        scores = {'context_mlp': .2, 'context_gcn': .2, 'coded_context_gcn': .2}
        self.assertEqual(select_context_arm(scores, 'biological_process'), 'context_mlp')
        scores['context_gcn'] = .3
        self.assertEqual(select_context_arm(scores, 'biological_process'), 'context_gcn')
        scores['coded_context_gcn'] = .4
        self.assertEqual(select_context_arm(scores, 'biological_process'), 'coded_context_gcn')
        with self.assertRaisesRegex(ValueError, 'predeclared contextual'):
            select_context_arm(scores, 'molecular_function')
        with self.assertRaisesRegex(ValueError, 'finite consumed-validation'):
            select_context_arm({'context_mlp': .2, 'context_gcn': float('nan')}, 'biological_process')

    def cell(self, *, point=.2, other=.1, lower=.01, upper=.1):
        return {'status': 'evaluated', 'methods': {
            CANDIDATE: {'native_micro_fmax': point}, 'localplus': {'native_micro_fmax': other}},
            'bootstrap': {'comparisons': [{'candidate': CANDIDATE, 'comparator': 'localplus',
                'paired_95_percentile_interval': [lower, upper]}]}}

    def test_positive_point_and_strictly_positive_interval_are_both_required(self):
        self.assertTrue(positive_interval(self.cell(), 'localplus'))
        self.assertFalse(positive_interval(self.cell(lower=0.), 'localplus'))
        self.assertFalse(positive_interval(self.cell(lower=-.001), 'localplus'))
        self.assertFalse(positive_interval(self.cell(point=.09), 'localplus'))
        self.assertFalse(positive_interval(self.cell(point=None), 'localplus'))
        self.assertFalse(positive_interval(self.cell(), 'missing'))
        self.assertFalse(positive_interval({'status': 'reference_absent'}, 'localplus'))

    def test_candidate_name_adapter_preserves_native_bootstrap_data(self):
        arrays = {'context_gcn': object(), 'context_mlp': object()}
        fake = {'scores': {'learned_mix': {'bootstrap_Fmax': [1, 2]}, 'context_mlp': {}},
                'comparisons': [{'candidate': 'learned_mix', 'comparator': 'context_mlp'}]}
        with patch('tools.learned_combination.ordinary_counts.paired_bootstrap', return_value=fake) as native:
            result = bootstrap_contrast(arrays, 'context_gcn')
        self.assertIs(native.call_args.args[0]['learned_mix'], arrays['context_gcn'])
        self.assertIs(native.call_args.args[0]['context_mlp'], arrays['context_mlp'])
        self.assertEqual(result['scores']['context_gcn']['bootstrap_Fmax'], [1, 2])
        self.assertEqual(result['comparisons'][0]['candidate'], 'context_gcn')


class SealTests(unittest.TestCase):
    def setUp(self):
        try:
            import numpy as np
            self.np = np
        except ImportError:
            self.skipTest('Optional NumPy runtime unavailable')
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.protocol = copy.deepcopy(module.PROTOCOL)
        self.protocol['cohort']['count'] = 2
        self.protocol_patch = patch.object(module, 'PROTOCOL', self.protocol)
        self.protocol_patch.start()

    def tearDown(self):
        if hasattr(self, 'protocol_patch'):
            self.protocol_patch.stop()
            self.temp.cleanup()

    def fixture(self):
        values = self.root / 'values.npy'
        self.np.save(values, self.np.asarray([[.7, .2], [.3, .8]], dtype=self.np.float32), allow_pickle=False)
        targets = self.root / 'targets.txt'; targets.write_text('P00001\nP00002\n')
        model_specs = {}
        for ns, aspect in NS_ASPECT.items():
            model_specs[ns] = {}
            for arm in ('context_mlp', 'context_gcn'):
                file = self.root / ('model_' + arm + '_' + aspect + '.json')
                write_json(file, {'namespace': ns, 'validation_ordinary_micro_fmax': .5,
                                  'n_layers': 0 if arm == 'context_mlp' else 8,
                                  'fresh_final_reference_opened': False})
                model_specs[ns][arm] = {'file': str(file), 'sha256': file_sha256(file)}
        arms = {}
        for arm in REQUIRED_ARMS:
            arms[arm] = {}
            for ns, aspect in NS_ASPECT.items():
                meta = {'namespace': ns, 'proteins': ['P00001', 'P00002'],
                        'terms': ['GO:1000001', 'GO:1000002'],
                        'prediction_file': str(values), 'prediction_sha256': file_sha256(values),
                        'final_reference_labels_read_for_forecasting': False}
                if arm in ('context_mlp', 'context_gcn', CANDIDATE):
                    source_arm = 'context_mlp' if arm == CANDIDATE else arm
                    meta['model_metadata_sha256'] = model_specs[ns][source_arm]['sha256']
                file = self.root / (arm + '_' + aspect + '.json'); write_json(file, meta)
                arms[arm][ns] = {'file': str(file), 'sha256': file_sha256(file)}
        choices = self.root / 'choices.json'
        write_json(choices, {'fresh_final_reference_opened': False,
            'selections': {ns: {'selected_arm': 'context_mlp',
                'validation_scores': {'context_mlp': .5, 'context_gcn': .5},
                'model_metadata': model_specs[ns]} for ns in NS_ASPECT}})
        # These paths deliberately do not exist. Sealing must never open them.
        refs = {v: {role: {'file': str(self.root / ('sealed_' + v + '_' + role)), 'sha256': '0' * 64}
                    for role in ('obo', 'toi', 'PK', 'PK_known', 'NK', 'LK')}
                for v in module.VIEWS}
        return {'format': 'biograph-steward.contextual-assessment.v1', 'protocol': self.protocol,
                'references': refs, 'targets': {'file': str(targets), 'sha256': file_sha256(targets)},
                'choices': {'file': str(choices), 'sha256': file_sha256(choices)},
                'arms': arms, 'source_pins': {}, 'n_cpu': 1}

    def test_complete_seal_and_recheck_never_open_reference_paths(self):
        cfg = self.fixture()
        receipt = seal(cfg, self.root / 'seal')
        self.assertEqual(receipt['target_count'], 2)
        self.assertFalse(receipt['reference_files_opened_by_seal'])
        self.assertFalse(receipt['future_GO_labels_opened'])
        loaded, observed = open_seal(self.root / 'seal')
        self.assertEqual(loaded, cfg)
        self.assertEqual(receipt, observed)

    def test_incomplete_arm_and_reordered_proteins_are_rejected(self):
        cfg = self.fixture(); cfg['arms'].pop('deepgose')
        with self.assertRaisesRegex(ValueError, 'complete predeclared'):
            seal(cfg, self.root / 'bad')
        spec = cfg['arms']['localplus']['molecular_function']
        with self.assertRaisesRegex(ValueError, 'full ordered target'):
            validate_source_manifest(spec, ('P00002', 'P00001'), arm='localplus', namespace='molecular_function')

    def test_new_reference_cannot_enter_source_pin_scan(self):
        cfg = self.fixture()
        spec = cfg['references']['native']['PK']; cfg['source_pins'][spec['file']] = spec['sha256']
        with self.assertRaisesRegex(ValueError, 'reference files must not enter'):
            seal(cfg, self.root / 'bad')

    def test_changed_forecast_fails_before_any_reference_is_opened(self):
        cfg = self.fixture(); seal(cfg, self.root / 'seal')
        (self.root / 'values.npy').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'forecast values changed'):
            open_seal(self.root / 'seal')

    def test_unqualified_probability_and_false_label_free_declaration_fail(self):
        cfg = self.fixture(); spec = cfg['arms']['localplus']['molecular_function']
        file = Path(spec['file']); meta = json.loads(file.read_text())
        meta['final_reference_labels_read_for_forecasting'] = True
        file.write_text(json.dumps(meta)); spec['sha256'] = file_sha256(file)
        with self.assertRaisesRegex(ValueError, 'label-free forecast provenance'):
            validate_source_manifest(spec, ('P00001', 'P00002'), arm='localplus', namespace='molecular_function')
        meta['final_reference_labels_read_for_forecasting'] = False
        values = Path(meta['prediction_file'])
        self.np.save(values, self.np.asarray([[1.01, 0.], [.1, .2]]), allow_pickle=False)
        meta['prediction_sha256'] = file_sha256(values)
        file.write_text(json.dumps(meta)); spec['sha256'] = file_sha256(file)
        with self.assertRaisesRegex(ValueError, 'unqualified forecast probability'):
            validate_source_manifest(spec, ('P00001', 'P00002'), arm='localplus', namespace='molecular_function')

    def test_selected_forecasts_must_equal_the_preselected_architecture(self):
        cfg = self.fixture()
        spec = cfg['arms'][CANDIDATE]['molecular_function']
        file = Path(spec['file']); meta = json.loads(file.read_text()); meta['terms'].reverse()
        file.write_text(json.dumps(meta)); spec['sha256'] = file_sha256(file)
        with self.assertRaisesRegex(ValueError, 'preselected contextual arm'):
            seal(cfg, self.root / 'bad')

    def test_optional_coded_context_is_declared_for_bpo_only(self):
        cfg = self.fixture(); bp = 'biological_process'
        cfg['arms']['coded_context_gcn'] = {bp: cfg['arms']['context_gcn'][bp]}
        file = Path(cfg['choices']['file']); choices = json.loads(file.read_text())
        choices['selections'][bp]['selected_arm'] = 'coded_context_gcn'
        choices['selections'][bp]['validation_scores']['coded_context_gcn'] = .5
        # Use a strict validation improvement, retaining the preselected final
        # score array in this invented fixture.
        model_file = self.root / 'coded_model.json'
        from .training import axis_sha
        channels = ['invented.' + str(i) for i in range(40)]
        write_json(model_file, {'namespace': bp, 'validation_ordinary_micro_fmax': .6,
                               'n_layers': 8, 'in_goa': 40, 'context_channels': channels,
                               'context_channels_sha256': axis_sha(channels),
                               'fresh_final_reference_opened': False})
        choices['selections'][bp]['validation_scores']['coded_context_gcn'] = .6
        choices['selections'][bp]['model_metadata']['coded_context_gcn'] = {
            'file': str(model_file), 'sha256': file_sha256(model_file)}
        source = json.loads(Path(cfg['arms']['coded_context_gcn'][bp]['file']).read_text())
        source['model_metadata_sha256'] = file_sha256(model_file)
        source.update(in_goa=40, context_channels=channels, context_channels_sha256=axis_sha(channels))
        source_file = self.root / 'coded_forecast.json'; write_json(source_file, source)
        cfg['arms']['coded_context_gcn'][bp] = {'file': str(source_file), 'sha256': file_sha256(source_file)}
        cfg['arms'][CANDIDATE][bp] = cfg['arms']['coded_context_gcn'][bp]
        file.write_text(json.dumps(choices)); cfg['choices']['sha256'] = file_sha256(file)
        seal(cfg, self.root / 'good')
        choices['selections']['molecular_function']['selected_arm'] = 'coded_context_gcn'
        file.write_text(json.dumps(choices)); cfg['choices']['sha256'] = file_sha256(file)
        with self.assertRaisesRegex(ValueError, 'explicitly declared for this aspect'):
            seal(cfg, self.root / 'bad')

    def test_roundoff_allowance_is_only_for_literal_localplus(self):
        cfg = self.fixture(); ns = 'molecular_function'; spec = cfg['arms']['localplus'][ns]
        file = Path(spec['file']); meta = json.loads(file.read_text())
        meta['upper_roundoff_tolerance'] = 1e-10
        values = self.root / 'roundoff.npy'
        self.np.save(values, self.np.asarray([[1 + 5e-11, 0.], [.1, .2]]), allow_pickle=False)
        meta['prediction_file'] = str(values); meta['prediction_sha256'] = file_sha256(values)
        file.write_text(json.dumps(meta)); spec['sha256'] = file_sha256(file)
        validate_source_manifest(spec, ('P00001', 'P00002'), arm='localplus', namespace=ns)
        with self.assertRaisesRegex(ValueError, 'only literal LocalPlus'):
            validate_source_manifest(spec, ('P00001', 'P00002'), arm='deepgose', namespace=ns)

    def test_source_partitions_must_be_complete_nonoverlapping_and_preoutcome(self):
        file = self.root / 'slices.json'
        value = {'fresh_final_reference_opened': False, 'slices': {
            'short': {'ids': ['P00001'], 'definition': 'literal source length <=1022'},
            'long': {'ids': ['P00002'], 'definition': 'literal source length >1022'}},
            'partitions': [['short', 'long']]}
        def spec():
            file.write_text(json.dumps(value))
            return {'file': str(file), 'sha256': file_sha256(file)}
        validate_source_slices(spec(), ('P00001', 'P00002'))
        value['slices']['long']['ids'] = ['P00001']
        with self.assertRaisesRegex(ValueError, 'partition overlaps'):
            validate_source_slices(spec(), ('P00001', 'P00002'))
        value['slices']['long']['ids'] = []
        with self.assertRaisesRegex(ValueError, 'complete target union'):
            validate_source_slices(spec(), ('P00001', 'P00002'))
        value['fresh_final_reference_opened'] = True
        with self.assertRaisesRegex(ValueError, 'defined before outcomes'):
            validate_source_slices(spec(), ('P00001', 'P00002'))

    def test_actual_native_dual_view_scoring_retains_empty_cells_and_zero_contrasts(self):
        try:
            source = os.environ.get('BIOGRAPH_CAFA_AUTHOR_SOURCE',
                'runs/accuracy_next_20261113/cafa5_intake/evaluator_author_source/src')
            sys.path.insert(0, source)
            from tools.learned_combination.native_adapter import _native
            _native()
        except (ImportError, FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED') == '1':
                raise
            self.skipTest('Optional pinned native evaluator unavailable: ' + str(error))
        from contextlib import redirect_stdout
        import io
        from tools.learned_combination.test_native_adapter import OBO

        cfg = self.fixture()
        content = {'obo': OBO, 'toi': 'GO:1000001\nGO:1000002\nGO:2000001\nGO:3000001\n',
            'PK': 'EntryID\tterm\taspect\nP00001\tGO:1000001\tF\nP00002\tGO:1000002\tF\n',
            'PK_known': 'EntryID\tterm\taspect\nP00001\tGO:0003674\tF\nP00002\tGO:0003674\tF\n',
            'NK': 'EntryID\tterm\taspect\n', 'LK': 'EntryID\tterm\taspect\n'}
        for specs in cfg['references'].values():
            for role, spec in specs.items():
                file = Path(spec['file']); file.write_text(content[role]); spec['sha256'] = file_sha256(file)
        source_slices = self.root / 'slices.json'
        write_json(source_slices, {'fresh_final_reference_opened': False, 'slices': {
            'only1': {'ids': ['P00001'], 'definition': 'invented source subgroup1'},
            'only2': {'ids': ['P00002'], 'definition': 'invented source subgroup2'}},
            'partitions': [['only1', 'only2']]})
        cfg['source_slices'] = {'file': str(source_slices), 'sha256': file_sha256(source_slices)}
        seal(cfg, self.root / 'seal')
        with redirect_stdout(io.StringIO()):
            result = module.evaluate(self.root / 'seal', self.root / 'result')
        self.assertFalse(result['primary_success_over_literal_LocalPlus_both_views'])
        self.assertFalse(result['automatic_graph_or_app_promotion'])
        for view in module.VIEWS:
            cells = result['views'][view]['cells']
            self.assertEqual(len(cells), 9)
            self.assertEqual(cells['NK/molecular_function']['status'], 'reference_absent')
            self.assertEqual(cells['PK/biological_process']['status'], 'reference_absent')
            cell = cells['PK/molecular_function']
            self.assertEqual(cell['status'], 'evaluated')
            self.assertEqual(cell['source_slice_points']['only1']['raw_native_reference_proteins'], 1)
            self.assertEqual(cell['source_slice_points']['only1']['methods'][CANDIDATE]['derived_micro_fmax'], 1.)
            for arm in REQUIRED_ARMS:
                self.assertEqual(cell['methods'][arm]['native_micro_fmax'], 1.)
                self.assertTrue(cell['methods'][arm]['native_curve_agreement']['author_point_agreement_passed'])
            for contrast in cell['bootstrap']['comparisons']:
                self.assertEqual(contrast['paired_95_percentile_interval'], [0., 0.])


if __name__ == '__main__':
    unittest.main()
