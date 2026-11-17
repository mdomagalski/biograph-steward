"""Invented-source boundary and I/O fixtures; native runtime parity is separate.

The dense score spy below tests masking and alias-merge order, not the author's
LocalPlus implementation. The real native kernel/StackDataset must pass their
pinned-runtime admission on Brev before any real feature preparation or fit.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from . import crossfit_prepare as module


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def invented_graph():
    nodes = [
        {'id': 'GO:0008150', 'adj': set(), 'children': {1, 2}},
        {'id': 'GO:2000001', 'adj': {0}, 'children': set()},
        {'id': 'GO:2000002', 'adj': {0}, 'children': set()}]
    return SimpleNamespace(idxs=3, terms_list=nodes,
        terms_dict={n['id']: {'index': i} for i, n in enumerate(nodes)},
        terms_dict_alt={'GO:2999999': ['GO:2000001', 'GO:2000002']})


class SourceSchemaTests(unittest.TestCase):
    def config(self):
        source = {'file': '/invented/source.json', 'sha256': 'a' * 64}
        cfg = {key: dict(source) for key in module.DIRECT_SPECS}
        cfg.update(format=module.FORMAT, parent_authorized_source_preparation=True,
            parent_axis=list(module.PARENTS), contexts={r: dict(source) for r in ('fit', 'validation', 'final')},
            raw_localplus={r: dict(source) for r in ('validation', 'final')},
            original_full_priors={r: dict(source) for r in ('raw', 'conditional', 'nulls')},
            localplus_author_root='/invented/localplus', stack_author_root='/invented/stacker',
            splitter_runtime={'sklearn_version': 'actual-version-before-generation', 'source': dict(source)},
            input_file_pins={source['file']: source['sha256']}, workers=2, **module.FLAGS)
        return cfg

    def test_schema_does_not_open_sources_and_requires_explicit_authorization(self):
        cfg = self.config()
        with patch.object(module, 'file_sha256', side_effect=AssertionError('no source access')) as reader:
            module.validate_schema(cfg)
            cfg['parent_authorized_source_preparation'] = False
            with self.assertRaisesRegex(ValueError, 'explicit source-only authorization'):
                module.verify_config(cfg)
            reader.assert_not_called()

    def test_parent_swap_extra_label_role_DeepGO_and_worker_overrun_rejected(self):
        cases = []
        cfg = self.config(); cfg['parent_axis'].reverse(); cases.append(cfg)
        cfg = self.config(); cfg['raw_localplus']['fit'] = cfg['plan']; cases.append(cfg)
        cfg = self.config(); cfg['validation_truth'] = cfg['plan']; cases.append(cfg)
        cfg = self.config(); cfg['input_file_pins']['/invented/deepgose/terms.pkl'] = 'a' * 64; cases.append(cfg)
        cfg = self.config(); cfg['input_file_pins']['/invented/groundtruth.tsv'] = 'a' * 64; cases.append(cfg)
        cfg = self.config(); cfg['workers'] = 5; cases.append(cfg)
        for cfg in cases:
            with self.subTest(cfg=cfg), self.assertRaises(ValueError): module.validate_schema(cfg)

    def test_only_exact_declared_sklearn_source_is_allowed_in_existing_runtime(self):
        cfg = self.config()
        splitter = '/data/deepgo/runtime/site-packages/sklearn/model_selection/_split.py'
        cfg['splitter_runtime']['source'] = {'file': splitter, 'sha256': 'b' * 64}
        cfg['input_file_pins'][splitter] = 'b' * 64
        module.validate_schema(cfg)
        for other in ('/data/deepgo/other/_split.py', '/data/deepgo/runtime/model.py',
                      '/data/deepgo/runtime/terms.pkl', '/data/deepgo/runtime/scores.npy'):
            changed = json.loads(json.dumps(cfg)); changed['input_file_pins'][other] = 'c' * 64
            with self.subTest(path=other), self.assertRaisesRegex(ValueError, 'DeepGO'):
                module.validate_schema(changed)
        # Even declaring a differently named file cannot bypass the policy.
        cfg['splitter_runtime']['source'] = {'file': '/data/deepgo/runtime/model.py', 'sha256': 'c' * 64}
        cfg['input_file_pins']['/data/deepgo/runtime/model.py'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'DeepGO'): module.validate_schema(cfg)

    def test_failed_stage_preserves_configuration_and_failure_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'attempt'; cfg = self.config()
            with patch.object(module, 'verify_config'), patch.object(module, 'inputs', side_effect=ValueError('invented source gate')):
                with self.assertRaisesRegex(ValueError, 'invented source gate'): module.prepare(cfg, output, stage='parents')
                self.assertTrue((output / 'configuration.json').exists())
                failure = json.loads((output / 'parents_failure.json').read_text())
                self.assertEqual(failure['status'], 'failed')
                with self.assertRaises(FileExistsError): module.prepare(cfg, output, stage='parents')
            self.assertEqual(json.loads((output / 'parents_failure.json').read_text()), failure)


class FoldAuditTests(unittest.TestCase):
    def fixture(self):
        proteins = ['P%d' % i for i in range(6)]
        groups = [sha_text(x) for x in ('same', 'same', 'b', 'c', 'd', 'e')]
        folds = []
        for number, right in enumerate(([0, 1], [2], [3], [4], [5])):
            folds.append({'fold_index': number, 'heldout_rows': list(right),
                          'complement_rows': [i for i in range(6) if i not in right]})
        return proteins, groups, folds

    def test_exact_sequence_grouped_complete_fold_partitions(self):
        p, g, folds = self.fixture(); result, assignment = module.validate_folds(p, g, folds)
        self.assertEqual(assignment, [0, 0, 1, 2, 3, 4])
        self.assertEqual(result[0]['heldout_proteins'], ['P0', 'P1'])
        self.assertTrue(all(f['group_overlap'] == 0 for f in result))

    def test_alias_accessions_same_full_sequence_cannot_cross_fold(self):
        p, g, folds = self.fixture()
        folds[0] = {'fold_index': 0, 'heldout_rows': [0], 'complement_rows': [1, 2, 3, 4, 5]}
        with self.assertRaisesRegex(ValueError, 'identical full sequences'): module.validate_folds(p, g, folds)

    def test_duplicate_heldout_fold_does_not_silently_overwrite_global_rows(self):
        p, g, folds = self.fixture(); folds[-1] = dict(folds[-2], fold_index=4)
        with self.assertRaisesRegex(ValueError, 'exactly once'): module.validate_folds(p, g, folds)


class NumpyFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import pandas  # Real native-prior helper reduction dependency.
            cls.np = np
        except ImportError as error: raise unittest.SkipTest(str(error))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.graph = invented_graph(); self.terms = [n['id'] for n in self.graph.terms_list]

    def tearDown(self): self.temp.cleanup()

    def test_native_alias_mapping_keeps_literal_heads_before_MAX(self):
        projection, heads = module.localplus_projection({module.NS: self.graph},
            {('BPO', 'GO:2000001'): {0}, ('BPO', 'GO:2999999'): {1}, ('MFO', 'GO:2000002'): {2}})
        self.assertEqual(heads, [1, 2])
        self.assertEqual(projection[('BPO', 'GO:2999999')], (1, 2))
        self.assertEqual(len(projection), 2)

    def test_score_aliases_separately_not_union_and_keep_empty_head_observed(self):
        np = self.np; calls = []; weights = np.asarray([[0, .3, .5], [0, 0, 0], [0, 0, 0]])
        def score_spy(P, positives):
            calls.append(positives.copy()); seed = np.zeros(3); seed[positives] = 1
            return weights @ seed, 0., 0.
        heads = {('BPO', 'GO:2000001'): {1}, ('BPO', 'GO:2999999'): {2}, ('BPO', 'GO:2000002'): {0}}
        projection = {('BPO', 'GO:2000001'): (1,), ('BPO', 'GO:2999999'): (1,), ('BPO', 'GO:2000002'): (2,)}
        path = self.root / 'literal.npy'
        receipt = module.score_literal_heads({'fss': SimpleNamespace(runLocal=score_spy)},
            SimpleNamespace(shape=(3, 3)), heads, projection, [1, 2], [0, None], {0}, path)
        values = np.load(path)
        self.assertEqual(values[0, 0], .5); self.assertNotEqual(values[0, 0], .8)
        np.testing.assert_array_equal(values[:, 1], 0.)
        np.testing.assert_array_equal(values[1], 0.)
        self.assertEqual(receipt['empty_complement_literal_heads'], 1)
        self.assertFalse(receipt['empty_fold_head_means_missing'])
        self.assertEqual(calls[-1].dtype, np.int64); self.assertEqual(len(calls[-1]), 0)

    def test_native_complement_priors_include_root_negative_rows_before_filter(self):
        np = self.np
        targets = np.asarray([[1, 1, 0], [1, 0, 1], [0, 0, 0], [1, 0, 0]], dtype=np.float32)
        proteins = ['P0', 'P1', 'P2', 'P3']
        fold = {'fold_index': 0, 'complement_rows': [1, 2, 3], 'heldout_rows': [0]}
        source = {'file': 'original_targets.npy', 'sha256': 'b' * 64}
        fold_spec = {'file': 'folds.json', 'sha256': 'c' * 64}
        p = module.prior_receipt(targets, self.graph, proteins, fold, source, fold_spec, self.root / 'priors')
        receipt = module.pinned(p); raw = module.load_array(receipt['files']['raw'])
        self.assertEqual(receipt['complement_proteins'], ['P1', 'P2', 'P3'])
        self.assertTrue(receipt['computed_before_root_positive_filter'])
        self.assertAlmostEqual(raw[0], 2 / 3, places=6)
        self.assertEqual(raw[1], 0); self.assertAlmostEqual(raw[2], 1 / 3, places=6)
        self.assertEqual(receipt['target_source'], source)
        # A mistakenly root-filtered denominator would yield root 1, child .5.
        self.assertNotEqual(raw[0], 1.); self.assertNotEqual(raw[2], .5)

    def test_original_raw_parent_reindex_and_tamper_guard(self):
        np = self.np; p = self.root / 'localplus.npy'
        np.save(p, np.arange(9, dtype=np.float64).reshape(3, 3) / 10)
        mp = self.root / 'localplus.json'
        mp.write_text(json.dumps({module.NS: {'proteins': ['P0', 'P1', 'P2'], 'terms': self.terms, **module.spec(p)}}))
        source = module.spec(mp); pins = {str(p): module.file_sha256(p), str(mp): module.file_sha256(mp)}
        values, rows = module.read_raw_localplus(source, ['P2', 'P0'], self.terms, pins)
        np.testing.assert_array_equal(rows, [2, 0]); self.assertEqual(values[rows[0], 0], .6)
        with self.assertRaisesRegex(ValueError, 'identity axes differ'):
            module.read_raw_localplus(source, ['P0'], self.terms[::-1], pins)
        np.save(p, np.zeros((3, 3), dtype=np.float64))
        with self.assertRaisesRegex(ValueError, 'cache changed'): module.read_raw_localplus(source, ['P0'], self.terms, pins)

    def test_two_parent_wiring_rebuilds_role_frequency_and_keeps_zero_LP_head(self):
        np = self.np; captured = []
        context = np.zeros((3, 40, 3), dtype=bool); context[2, 1, 0] = True
        local = np.zeros((2, 1), dtype=np.float64)
        def dataset_spy(author, **kwargs): captured.append(kwargs); return kwargs
        def writer_spy(dataset, path, *, workers):
            n = len(dataset['proteins']); raw = dataset['prior_raw']; heads = dataset['predictions'][0][1]
            result = np.zeros((n, 9, 3), dtype=np.float32); result[:, 0] = 1; result[:, 0, heads] = 0
            result[:, 5:8] = raw[None, None, :]
            for i, columns in enumerate(dataset['goa_indices']): result[i, 8, columns] = 1
            np.save(path, result)
        with patch.object(module, 'make_dataset', side_effect=dataset_spy), patch.object(module.prep, 'write_feature_memmap', side_effect=writer_spy):
            for name, raw in [('fold', np.asarray([.5, 0., .25])), ('allfit', np.asarray([.75, .25, .25]))]:
                module.write_role_features(None, self.graph, ['P2', 'P0'], self.terms, local, [1],
                    (raw, np.ones(3)), context, [2, 0], self.root / (name + '.npy'), workers=1)
        a, b = captured
        self.assertEqual(len(a['predictions']), 2)
        np.testing.assert_array_equal(a['predictions'][0][1], [1])
        np.testing.assert_array_equal(a['predictions'][1][1], [0, 1, 2])
        self.assertFalse(a['predictions'][1][0].flags.writeable)  # Bounded broadcast, no full N×GO copy.
        self.assertFalse(np.array_equal(a['predictions'][1][0], b['predictions'][1][0]))
        self.assertFalse(a['predictions'][0][0].any())  # Available observed-zero LP head retained.

    def feature_stage_fixture(self):
        """Synthetic source receipts; kernel and native dataset admission remain separate."""
        np = self.np; output = self.root / 'prepared'; output.mkdir()
        source_dir = self.root / 'sources'; source_dir.mkdir()
        def save_json(name, value):
            path = source_dir / name; path.write_text(json.dumps(value)); return module.spec(path)
        def save_array(name, value):
            path = source_dir / name; np.save(path, value); return module.spec(path)
        proteins = ['P%d' % i for i in range(10)]
        groups = [sha_text('group%d' % (i // 2)) for i in range(10)]
        folds = [{'fold_index': k, 'heldout_rows': [2*k, 2*k+1],
                  'complement_rows': [i for i in range(10) if i // 2 != k]} for k in range(5)]
        folds, assignment = module.validate_folds(proteins, groups, folds)
        targets = np.zeros((10, 3), dtype=np.float32); targets[:8, 0] = 1
        targets[:4, 1] = 1; targets[4:8, 2] = 1
        y = save_array('targets.npy', targets); known = save_array('known.npy', targets > 0)
        original = {'proteins': proteins, 'terms': self.terms, 'targets_file': y['file'],
            'known_positive_mask_file': known['file'], 'file_pins': {y['file']: y['sha256'], known['file']: known['sha256']},
            'target_semantics': 'known_T0_union_allowed_development_additions_upward_closed'}
        original_spec = save_json('original.json', original)
        full_prior = module.prep.priors_from_full_fit(targets, self.graph)
        old_priors = {n: save_array(n+'.npy', a) for n, a in zip(('raw', 'conditional', 'nulls'), full_prior)}
        plan = save_json('plan.json', {'invented_fixture': True})
        sequence = save_json('sequence.json', {p: {'sequence_sha256': g} for p, g in zip(proteins, groups)})
        roles = {'fit': proteins, 'validation': ['V0', 'V1'], 'final': ['F0', 'F1']}
        contexts = {r: np.zeros((len(ids), 40, 3), dtype=bool) for r, ids in roles.items()}
        contexts['fit'][::2, 1, 0] = True
        context_specs = {r: save_json(r+'_context.json', {'invented_fixture': True}) for r in roles}
        raws = {}; pins = {}
        for role in ('validation', 'final'):
            raw = np.zeros((2, 3), dtype=np.float64); raw[:, 1] = [.125, .25]
            array = save_array(role+'_raw.npy', raw); pins[array['file']] = array['sha256']
            raws[role] = save_json(role+'_raw.json', {module.NS: {'proteins': roles[role], 'terms': self.terms, **array}})
        cfg = {'plan': plan, 'original_fit_manifest': original_spec, 'sequence_records': sequence,
            'original_full_priors': old_priors, 'contexts': context_specs, 'raw_localplus': raws,
            'model_obo': plan, 'channel_contract': plan, 'stack_author_root': '/invented/author', 'workers': 1,
            'input_file_pins': pins, **module.FLAGS}
        for s in [plan, sequence, original_spec, y, known, *old_priors.values(), *context_specs.values(), *raws.values()]:
            pins[s['file']] = s['sha256']
        module.prep.write_json(output / 'configuration.json', cfg)
        fold_meta = {'plan_sha256': plan['sha256'], 'folds': folds, 'fold_index_by_row': assignment}
        module.prep.write_json(output / 'fold_manifest.json', fold_meta)
        parents = {}
        for fold in folds:
            folder = output / ('fold_%d' % fold['fold_index']); folder.mkdir()
            path = folder / 'localplus.npy'; np.save(path, np.full((2, 1), fold['fold_index'] / 10., dtype=np.float64))
            parents[str(fold['fold_index'])] = module.spec(path)
        ready = {'status': 'complete', 'parent_axis': module.PARENTS, 'configuration': module.spec(output / 'configuration.json'),
            'producer_source': module.spec(module.__file__), 'fold_manifest': module.spec(output / 'fold_manifest.json'),
            'fold_parents': parents, 'localplus_head_indices': [1], 'original_full_source_replay': {'invented_fixture': True},
            'stage_runtime': {'invented_fixture': True}}
        module.prep.write_json(output / 'parents_ready.json', ready)
        counts = {'fit_universe': 10, 'full_positive_cells': 16, 'root_positive_rows': 8,
            'validation_proteins': 2, 'final_proteins': 2, 'model_terms': 3}
        opened = ({module.NS: self.graph}, original, targets, contexts, roles, counts)
        return cfg, output, opened

    def feature_writer_spy(self, dataset, path, *, workers):
        """Raw-channel plumbing spy, explicitly not native propagation parity."""
        np = self.np; result = np.zeros((len(dataset['proteins']), 9, 3), dtype=np.float32)
        for i in range(len(result)):
            for number, (values, heads) in enumerate(dataset['predictions']):
                base = 4 * number; result[i, base] = 1; result[i, base, heads] = 0
                result[i, base+1] = dataset['prior_raw']; result[i, base+2:base+4] = dataset['prior_cond']
                result[i, base+1:base+4, heads] = values[i, :, None]
            result[i, 8, dataset['goa_indices'][i]] = 1
        np.save(path, result)

    def test_full_feature_stage_keeps_global_order_complement_priors_and_all_pins(self):
        np = self.np; cfg, output, opened = self.feature_stage_fixture()
        author = SimpleNamespace(source_receipt={'invented_dataset_spy': True})
        with patch.object(module, 'verify_config'), patch.object(module, 'inputs', return_value=opened), \
             patch.object(module, 'load_author', return_value=author), \
             patch.object(module, 'make_dataset', side_effect=lambda author, **kw: kw), \
             patch.object(module.prep, 'write_feature_memmap', side_effect=self.feature_writer_spy):
            ready = module.prepare_features(cfg, output)
        self.assertEqual(ready['status'], 'complete'); self.assertEqual(ready['parent_axis'], module.PARENTS)
        fit = module.pinned(ready['manifests']['fit']); features = np.load(fit['feature_file'])
        np.testing.assert_array_equal(features[:, 1, 1], np.repeat(np.arange(5, dtype=np.float32) / 10, 2))
        for fold in range(5):
            receipt = module.pinned(ready['prior_receipts']['folds'][fold]); raw = module.load_array(receipt['files']['raw'])
            np.testing.assert_array_equal(features[2*fold:2*fold+2, 5], np.broadcast_to(raw.astype(np.float32), (2, 3)))
        full = module.pinned(ready['prior_receipts']['all_fit']); full_raw = module.load_array(full['files']['raw'])
        for role in ('validation', 'final'):
            meta = module.pinned(ready['manifests'][role]); values = np.load(meta['feature_file'])
            np.testing.assert_array_equal(values[:, 5], np.broadcast_to(full_raw.astype(np.float32), (2, 3)))
            self.assertEqual(meta['feature_prior_receipts'], [ready['prior_receipts']['all_fit']])
        self.assertEqual(fit['targets_file'], opened[1]['targets_file'])
        for path, digest in ready['input_file_pins'].items(): self.assertEqual(module.file_sha256(path), digest)
        self.assertIn(ready['source_admission']['file'], ready['input_file_pins'])
        self.assertIn(fit['feature_file'], ready['input_file_pins'])
        with patch.object(module, 'verify_config'):
            with self.assertRaisesRegex(ValueError, 'preserve existing/failed'): module.prepare_features(cfg, output)
        self.assertFalse((output / 'features_failure.json').exists())

    def test_full_prior_drift_aborts_before_any_feature_cache(self):
        np = self.np; cfg, output, opened = self.feature_stage_fixture()
        path = Path(cfg['original_full_priors']['raw']['file']); np.save(path, np.zeros(3))
        # Admit its changed pin deliberately: the numerical original-vector
        # comparison is an additional guard beyond ordinary hash admission.
        cfg['original_full_priors']['raw']['sha256'] = module.file_sha256(path)
        cfg['input_file_pins'][str(path)] = module.file_sha256(path)
        (output / 'configuration.json').write_text(json.dumps(cfg))
        prior_ready = json.loads((output / 'parents_ready.json').read_text())
        prior_ready['configuration'] = module.spec(output / 'configuration.json')
        (output / 'parents_ready.json').write_text(json.dumps(prior_ready))
        with patch.object(module, 'verify_config'), patch.object(module, 'inputs', return_value=opened), \
             patch.object(module, 'load_author', return_value=SimpleNamespace()):
            with self.assertRaisesRegex(ValueError, 'native full-fit prior differs'): module.prepare_features(cfg, output)
        self.assertTrue((output / 'features_failure.json').exists()); self.assertFalse((output / 'features').exists())


if __name__ == '__main__': unittest.main()
