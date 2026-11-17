"""Invented-data control precision, identity and consumed-only selection gates."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from .controls import export_controls, fit_alpha_controls, load_parents, soft_control
from .training import PARAMETERS, sha, write_json
from tools.learned_combination.core import ALPHA_GRID


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            from .test_postprocessing import PostprocessTests
            PostprocessTests.setUpClass()
            cls.np, cls.author = np, PostprocessTests.root
        except (ImportError, FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED') == '1':
                raise
            raise unittest.SkipTest('Optional native source/runtime unavailable: ' + str(error))

    def fixture(self, root):
        terms = ['GO:1000000', 'GO:1000001']
        proteins = ['invented1', 'invented2']
        graph = SimpleNamespace(idxs=2, order=[1, 0], terms_list=[
            {'id': terms[0], 'adj': set(), 'children': {1}},
            {'id': terms[1], 'adj': {0}, 'children': set()}])
        parents, pins = {}, {}
        for name, values in (('localplus', [[1 + 5e-11, .9], [.8, .3]]),
                             ('deepgose', [[.2, .8], [.5, .4]])):
            array = root / (name + '.npy')
            self.np.save(array, self.np.asarray(values, dtype=self.np.float64), allow_pickle=False)
            meta = root / (name + '.json')
            write_json(meta, {'namespace': 'molecular_function', 'proteins': proteins, 'terms': terms,
                             'prediction_file': str(array), 'prediction_sha256': sha(array),
                             'final_reference_labels_read_for_forecasting': False})
            parents[name] = {'file': str(meta), 'sha256': sha(meta)}
            pins.update({str(array): sha(array), str(meta): sha(meta)})
        cfg = {'format': 'biograph-steward.contextual-controls.v1', 'namespace': 'molecular_function',
               'author_root': str(self.author), 'parents': parents, 'input_file_pins': pins}
        return cfg, graph

    def selection(self, root, alpha=.6):
        path = root / 'frozen_selection.json'
        write_json(path, {'format': 'biograph-steward.contextual-alpha-selection.v1',
            'namespace': 'molecular_function', 'fresh_final_reference_opened': False,
            'postprocessing': PARAMETERS['postprocessing'], 'alpha': alpha,
            'alpha_grid': list(ALPHA_GRID), 'tie_rule': 'smallest alpha on the fixed grid'})
        return {'file': str(path), 'sha256': sha(path)}

    def test_literal_parent_precision_and_qualified_roundoff_are_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg, graph = self.fixture(Path(temp))
            parents, metadata = load_parents(cfg)
            self.assertEqual(parents['localplus'].values.dtype, self.np.float64)
            self.assertGreater(parents['localplus'].values.max(), 1.)
            self.assertEqual(parents['localplus'].terms, parents['deepgose'].terms)

    def test_changed_artifact_or_axis_does_not_silently_align(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg, graph = self.fixture(Path(temp))
            meta_file = Path(cfg['parents']['deepgose']['file'])
            meta = json.loads(meta_file.read_text()); meta['proteins'].reverse()
            meta_file.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, 'input pin'):
                load_parents(cfg)
            cfg['parents']['deepgose']['sha256'] = sha(meta_file)
            cfg['input_file_pins'][str(meta_file)] = sha(meta_file)
            with self.assertRaisesRegex(ValueError, 'identity axes differ'):
                load_parents(cfg)

    def test_soft_control_cast_is_explicit_and_mixing_precedes_closure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cfg, graph = self.fixture(root)
            parents, _ = load_parents(cfg)
            raw = parents['localplus'].values.copy()
            bundle = soft_control(cfg, graph, parents, .5, root / 'soft')
            self.assertEqual(self.np.load(bundle['prediction_file']).dtype, self.np.float32)
            self.assertGreater(bundle['float32_cast_max_abs'], 0.)
            self.assertFalse(bundle['probability_clipping'])
            self.assertEqual(bundle['localplus_weight'], .5)
            self.np.testing.assert_array_equal(parents['localplus'].values, raw)

    def test_final_controls_accept_no_evaluation_configuration_before_any_read(self):
        with patch('tools.contextual_combination.controls.sha') as reader:
            for key in ('evaluation', 'references', 'validation_manifest'):
                with self.assertRaisesRegex(ValueError, 'cannot receive'):
                    export_controls({key: {}}, {'file': '/invented', 'sha256': 'x'}, '/unused')
            reader.assert_not_called()

    def test_final_export_keeps_two_raw_and_four_matched_soft_arms(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cfg, graph = self.fixture(root)
            frozen = self.selection(root)
            with patch('tools.contextual_combination.controls.model_graph', return_value=graph):
                result = export_controls(cfg, frozen, root / 'export')
            self.assertEqual(set(result['arms']), {'localplus_model_axis_raw', 'deepgose_model_axis_raw', 'localplus_soft',
                'deepgose_soft', 'equal_mix', 'development_alpha_mix'})
            original = json.loads(Path(cfg['parents']['localplus']['file']).read_text())
            literal = json.loads(Path(result['arms']['localplus_model_axis_raw']['file']).read_text())
            self.assertEqual(literal['prediction_sha256'], original['prediction_sha256'])
            self.assertIn('not complete original source heads', literal['source_scope'])
            self.assertFalse(result['reference_files_read_for_forecasting'])

    def test_consumed_alpha_selection_uses_all_eleven_identical_deployed_arms_and_tie_rule(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cfg, graph = self.fixture(root)
            val = root / 'val.json'; write_json(val, {'invented': True})
            cfg['validation_manifest'] = str(val)
            cfg['evaluation'] = {'references': {'truth': {'file': '/invented-truth'},
                'known': {'file': '/invented-known'}}}
            meta = json.loads(Path(cfg['parents']['localplus']['file']).read_text())
            seen = []
            def score(cfg, frame, bundle, output):
                seen.append(bundle['localplus_weight'])
                return .9 if bundle['localplus_weight'] in (.6, .7) else .2
            def subset(files, proteins, output):
                Path(output).write_text('invented-frame-only\n')
            with patch('tools.contextual_combination.controls.validate_validation_sources'), \
                 patch('tools.contextual_combination.controls.read_feature_manifest', return_value=(meta, None, None)), \
                 patch('tools.contextual_combination.controls.model_graph', return_value=graph), \
                 patch('tools.learned_combination.runner.subset_reference', side_effect=subset), \
                 patch('tools.contextual_combination.controls.score_saved_consumed_forecast', side_effect=score):
                result = fit_alpha_controls(cfg, root / 'fit')
            self.assertEqual(seen, list(ALPHA_GRID))
            self.assertEqual(result['alpha'], .6)
            self.assertFalse(result['fresh_final_reference_opened'])


if __name__ == '__main__':
    unittest.main()
