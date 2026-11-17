"""Invented-only frozen checkpoint scheduling; no biological fitting or labels."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import current_refit as module
from .current_refit import (FrozenCheckpointCallback, frozen_priorities,
                            native_epoch_ranking, fit_native_frozen_schedule)
from .training import sha


def fixture(folder):
    scores = [i / 100 for i in range(20)]
    scores[10], scores[12], scores[11] = .93, .92, .91
    path = folder/'invented_original_model.json'
    path.write_text(json.dumps({'namespace':'biological_process','n_layers':8,'in_goa':40,
        'fresh_final_reference_opened':False,'epoch_scores':scores,
        'selected_swa_sources':{'checkpoint0_0.93.pth':'a'*64,
                                'checkpoint1_0.92.pth':'b'*64,
                                'checkpoint2_0.91.pth':'c'*64}}))
    return {'file':str(path),'sha256':sha(path)}


class FrozenPriorityTests(unittest.TestCase):
    def test_validation_config_or_changed_parameters_are_rejected_before_file_access(self):
        from .training_context import CONTEXT_PARAMETERS
        cfg = {'format': 'biograph-steward.current-T0-BP-development-refit.v1',
               'namespace': 'biological_process', 'seed': 20261115, 'params': CONTEXT_PARAMETERS,
               'plan': {}, 'source_readiness': {}, 'author_root': '/not/read',
               'original_model_metadata': {}, 'original_fit_manifest': {},
               'original_final_feature_manifest': {}, 'channel_contract': {},
               'validation_manifest': '/must/not/read'}
        with patch.object(module, 'pinned', side_effect=AssertionError('must not read')) as reader:
            with self.assertRaisesRegex(ValueError, 'only the one frozen'):module.prepare_inputs(cfg)
            reader.assert_not_called()

    def test_original_source_hash_is_checked_before_metadata_is_read(self):
        with patch.object(Path,'read_text',side_effect=AssertionError('must not decode')) as read:
            with self.assertRaisesRegex(ValueError,'only the original'):
                frozen_priorities({'file':'/invented/not-read','sha256':'0'*64})
            read.assert_not_called()

    def test_original_rank_order_is_preserved_and_not_presented_as_current_metric(self):
        with tempfile.TemporaryDirectory() as temp:
            spec=fixture(Path(temp))
            with patch.object(module,'ORIGINAL_MODEL_SHA256',spec['sha256']):
                priorities,meta=frozen_priorities(spec)
            self.assertEqual(tuple(i for i,_ in native_epoch_ranking(priorities)[:3]),(10,12,11))
            self.assertEqual(meta['frozen_checkpoint_priorities'],list(priorities))
            self.assertEqual(meta['frozen_epoch_numbers_one_based'],[11,13,12])
            self.assertFalse(meta['current_validation_metric_computed'])
            self.assertIn('not current validation scores',meta['priority_semantics'])
            self.assertNotIn('epoch_scores',meta)

    def test_score_ties_follow_the_unchanged_native_latest_epoch_rule(self):
        self.assertEqual(native_epoch_ranking([1.,2.,2.,.5])[:3],[(2,2.),(1,2.),(0,1.)])

    def test_callback_rejects_real_loader_and_enforces_exactly_twenty_calls(self):
        p=[float(i) for i in range(20)];p[10],p[12],p[11]=22.,21.,20.
        callback=FrozenCheckpointCallback(p)
        with self.assertRaisesRegex(ValueError,'no validation loader'):callback(None,[])
        with self.assertRaises(AssertionError):iter(callback.placeholder)
        with self.assertRaises(AssertionError):len(callback.placeholder)
        with self.assertRaises(AssertionError):callback.placeholder[0]
        with self.assertRaisesRegex(ValueError,'exactly twenty'):callback.complete()
        actual=[callback(None,callback.placeholder) for _ in range(20)]
        callback.complete();self.assertEqual(actual,p)
        with self.assertRaisesRegex(ValueError,'more than twenty'):callback(None,callback.placeholder)

    def test_changed_epoch_schedule_and_original_swa_score_keys_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            spec=fixture(Path(temp));path=Path(spec['file']);m=json.loads(path.read_text())
            m['selected_swa_sources']['checkpoint0_0.93.pth']='changed-hash'
            # The actual model source digest, not trust in individual fields,
            # guards against edited original metadata.
            path.write_text(json.dumps(m))
            with patch.object(module,'ORIGINAL_MODEL_SHA256',spec['sha256']):
                with self.assertRaisesRegex(ValueError,'only the original'):frozen_priorities(spec)
        p=list(range(20))
        with self.assertRaisesRegex(ValueError,'schedule changed'):FrozenCheckpointCallback(p)


class PositiveUnionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            cls.np = np
        except ImportError:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED') == '1':raise
            raise unittest.SkipTest('Optional NumPy runtime unavailable')

    def test_every_original_full_positive_is_retained_not_only_old_known_subset(self):
        np = self.np
        old = np.asarray([[1, 0, 1], [1, 1, 0]], dtype=np.float32)
        new = np.asarray([[1, 1, 1], [1, 1, 0]], dtype=np.float32)
        expected = {'original_full_positive_cells':4, 'augmented_positive_cells':5,
                    'added_positive_cells':1, 'fitting_proteins_with_additions':1}
        self.assertEqual(module.validate_positive_union(old,new,old>0,expected),expected)
        partial = old > 0; partial[0,2] = False
        with self.assertRaisesRegex(ValueError,'ORIGINAL FULL'):
            module.validate_positive_union(old,new,partial,expected)
        dropped = new.copy(); dropped[0,2] = 0
        with self.assertRaisesRegex(ValueError,'ORIGINAL FULL'):
            module.validate_positive_union(old,dropped,old>0,expected)
        with self.assertRaisesRegex(ValueError,'source-only counts'):
            module.validate_positive_union(old,new,old>0,{**expected,'added_positive_cells':2})

    def test_new_context_records_consumed_state_and_exact_array_axes(self):
        np=self.np
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);array=root/'context.npy';np.save(array,np.zeros((2,40,3),dtype=bool))
            base={'proteins':['invented1','invented2'],'terms':['GO:1000001','GO:1000002','GO:1000003']}
            meta={**base,'format':'biograph-steward.contextual-boolean-features.v1',
                'channels':['invented.'+str(i) for i in range(40)],'context_file':str(array),
                'context_sha256':sha(array),'development_after_reference_opening':True,
                'reference_previously_consumed':True,'independent_confirmation':False,
                'final_reference_labels_read_for_feature_construction':False}
            path=root/'context.json';path.write_text(json.dumps(meta))
            spec={'file':str(path),'sha256':sha(path)};pins={str(path):sha(path),str(array):sha(array)}
            _,values=module.read_development_context(spec,pins,base,fitting=True)
            self.assertEqual(values.shape,(2,40,3))
            meta['fresh_final_reference_opened']=False;path.write_text(json.dumps(meta))
            spec['sha256']=pins[str(path)]=sha(path)
            with self.assertRaisesRegex(ValueError,'truthfully record'):
                module.read_development_context(spec,pins,base,fitting=True)


class NativeCallbackAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import torch
            root=Path(os.environ.get('BIOGRAPH_PROTBOOST_AUTHOR_ROOT',
                'runs/contextual_gain_20261115/operator/combination_methods_v1/author'))
            if not (root/'protnn/train.py').is_file():raise FileNotFoundError(str(root))
            cls.torch=torch;cls.author=SimpleNamespace(root=root)
        except (ImportError,FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_CONTEXT_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest('Optional pinned native CPU runtime unavailable: '+str(error))

    def test_unchanged_native_loop_never_reads_placeholder_and_averages_exact_fixed_epochs(self):
        torch=self.torch
        original=module.FrozenCheckpointCallback
        class StampedInventedCallback(original):
            def __call__(self,model,loader):
                # No training samples/optimizer steps. Stamp a known epoch in
                # the invented scalar state to expose actual SWA selection.
                with torch.no_grad():model.weight.fill_(self.calls)
                return super().__call__(model,loader)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);spec=fixture(root);log=io.StringIO()
            model=torch.nn.Linear(1,1,bias=False)
            with patch.object(module,'ORIGINAL_MODEL_SHA256',spec['sha256']), \
                 patch.object(module,'FrozenCheckpointCallback',StampedInventedCallback),redirect_stdout(log):
                result,receipt=fit_native_frozen_schedule(self.author,model,[],spec,root/'output')
            self.assertEqual(receipt['native_callback_calls'],20)
            self.assertEqual(receipt['frozen_epoch_indices_zero_based'],[10,12,11])
            self.assertEqual(float(result.weight),11.)
            self.assertEqual(receipt['uniform_three_parameter_state_average_max_abs'],0.)
            self.assertFalse(receipt['current_validation_predictions_or_metrics_computed'])
            self.assertFalse(receipt['best_on_refreshed_data_selection_claimed'])
            self.assertFalse(receipt['independent_confirmation'])
            self.assertTrue(receipt['reference_previously_consumed'])
            self.assertTrue(log.getvalue().startswith('REFIT PROVENANCE:'))
            self.assertEqual(log.getvalue().count('Epoch '),20)
            self.assertNotIn('validation_ordinary_micro_fmax',json.dumps(receipt))

    def test_forecast_wrapper_preserves_postprocessing_audit_and_truthful_completion_metadata(self):
        import numpy as np
        from .native_stacker import make_model
        from .test_native_stacker import NativeStackerTests
        from .training import axis_sha, PARAMETERS
        NativeStackerTests.setUpClass();owner=NativeStackerTests()
        args=owner.fixture();torch=self.torch
        names=['invented.'+str(i) for i in range(40)]
        final={'proteins':['invented_final1','invented_final2'],'terms':list(args['terms'])}
        context={**final,'channels':names}
        features=np.full((2,9,5),.3,dtype=np.float32);features[:,[0,4,8]]=0
        data={'final':final,'xx':features,'graph':args['graph'],'cx':context,
              'bx':np.zeros((2,40,5),dtype=bool),'contract':{'channels':names},
              'ready':{'input_file_pins':{}}}
        with tempfile.TemporaryDirectory() as temp, owner.native_cpu_placement():
            root=Path(temp);cfg={'author_root':str(owner.root),'seed':20261115,
                'source_readiness':{'file':'/invented/ready.json','sha256':'a'*64}}
            (root/'configuration.json').write_text(json.dumps(cfg))
            model=make_model(owner.author,n_terms=5,terms=args['terms'],context_channels=names,seed=20261115)
            checkpoint=root/'model.pth';torch.save(model.state_dict(),checkpoint)
            meta={'format':'biograph-steward.current-T0-BP-development-model.v1',
                'plan_sha256':module.PLAN_SHA256,'source_readiness':cfg['source_readiness'],
                'producer_code_sha256':sha(module.__file__),'model_terms_sha256':axis_sha(final['terms']),
                'context_channels':names,'n_layers':8,'in_goa':40,'postprocessing':PARAMETERS['postprocessing'],
                'current_validation_metric_computed':False,'development_after_reference_opening':True,
                'reference_previously_consumed':True,'independent_confirmation':False,
                'checkpoint_file':str(checkpoint),'checkpoint_sha256':sha(checkpoint),
                'configuration_sha256':sha(root/'configuration.json')}
            path=root/'model.json';path.write_text(json.dumps(meta));spec={'file':str(path),'sha256':sha(path)}
            audit={'source_sha256':{'invented-official-source':'b'*64},'full_precision':True}
            def saved(_root,_graph,proteins,terms,values,output):
                prediction=Path(output)/'predictions.npy';np.save(prediction,values)
                return {'proteins':list(proteins),'terms':list(terms),'prediction_file':str(prediction),
                        'prediction_sha256':sha(prediction),'postprocessing':audit}
            with patch.object(module,'prepare_inputs',return_value=data), \
                 patch('tools.contextual_combination.training.save_soft_forecast',side_effect=saved):
                result=module.forecast_prepared(cfg,spec,root/'forecast')
            self.assertEqual(result['postprocessing'],audit)
            self.assertEqual(result['status'],'complete')
            self.assertEqual(result['arm'],module.ARM)
            self.assertTrue(result['models_fitted'])
            self.assertFalse(result['scientific_metrics_computed'])
            self.assertFalse(result['current_validation_metric_computed'])
            self.assertFalse(result['final_reference_labels_read_for_forecasting'])
            self.assertNotIn('fresh_final_reference_opened',result)
            self.assertEqual(result['source_configuration']['sha256'],meta['configuration_sha256'])


if __name__=='__main__':unittest.main()
