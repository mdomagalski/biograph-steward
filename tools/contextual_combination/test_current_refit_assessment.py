"""Invented-only provenance, strong-control and paired-draw assembly checks."""
import copy
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import json

from . import current_refit_assessment as module


def good_forecast(arm):
    return {'arm':arm,'namespace':module.NS,'plan_sha256':module.PLAN_SHA256,
        'development_after_reference_opening':True,'reference_previously_consumed':True,
        'independent_confirmation':False,'final_reference_labels_read_for_forecasting':False,
        'scientific_metrics_computed':False,'models_fitted':arm==module.REFIT,
        'current_validation_metric_computed':False,'upper_roundoff_tolerance':0.}


class BoundaryTests(unittest.TestCase):
    def test_unauthorized_fresh_claim_rejected_before_file_access(self):
        cfg={'format':'biograph-steward.current-refit-assessment.v1',
            'parent_authorized_consumed_reference_assessment':False,
            'development_followup_on_consumed_reference':True,'independent_confirmation':False}
        with patch.object(module,'pinned_json',side_effect=AssertionError('must not read')) as reader:
            with self.assertRaisesRegex(ValueError,'authorization'):module.prepare_inputs(cfg)
            reader.assert_not_called()
        cfg['parent_authorized_consumed_reference_assessment']=True;cfg['independent_confirmation']=True
        with self.assertRaisesRegex(ValueError,'no independent'):module.authorization(cfg)

    def test_fixed_three_arm_aspect_and_epoch_scope(self):
        plan=json.loads(Path(__file__).with_name('current_refit_protocol.json').read_text())
        module.validate_plan(plan)
        for key,change in [('arms',{a:['molecular_function'] for a in module.NEW_ARMS}),
                           ('independent_confirmation',True)]:
            x=copy.deepcopy(plan);x[key]=change
            with self.assertRaises(ValueError):module.validate_plan(x)
        x=copy.deepcopy(plan);x['model']['frozen_epoch_indices_zero_based_in_native_rank_order']=[17,18,19]
        with self.assertRaisesRegex(ValueError,'checkpoint'):module.validate_plan(x)

    def test_provenance_rejects_metric_and_fit_role_fabrication(self):
        for arm in module.NEW_ARMS:
            meta=good_forecast(arm);module.validate_forecast_provenance(meta,arm)
            for key,value in [('independent_confirmation',True),('scientific_metrics_computed',True),
                              ('current_validation_metric_computed',True),('models_fitted',not meta['models_fitted'])]:
                changed=copy.deepcopy(meta);changed[key]=value
                with self.assertRaisesRegex(ValueError,'truthful'):module.validate_forecast_provenance(changed,arm)

    def test_native_roundoff_allowance_only_unchanged_localplus(self):
        for arm in module.NEW_ARMS:
            meta=good_forecast(arm);meta['upper_roundoff_tolerance']=module.LOCALPLUS_UPPER_ROUNDOFF
            if arm==module.UNION_LP:
                self.assertEqual(module.validate_forecast_provenance(meta,arm),'localplus_T0_curated')
            else:
                with self.assertRaisesRegex(ValueError,'epsilon'):module.validate_forecast_provenance(meta,arm)
        x=good_forecast(module.UNION_LP);x['upper_roundoff_tolerance']=.01
        with self.assertRaises(ValueError):module.validate_forecast_provenance(x,module.UNION_LP)

    def test_all_strong_and_earlier_development_controls_are_mandatory(self):
        names=module.SOURCE_COMPARATORS+module.PREVIOUS_NEW_ARMS+('other_original_control',)
        pairs=module.required_pairs(names)
        self.assertEqual(len(pairs),len(names)+13)
        self.assertIn((module.REFIT,module.UNION_LP),pairs)
        self.assertIn((module.UNION_LP,module.UNION_PRIOR),pairs)
        for name in module.SOURCE_COMPARATORS+module.PREVIOUS_NEW_ARMS:
            with self.assertRaisesRegex(ValueError,'complete earlier'):module.required_pairs(tuple(n for n in names if n!=name))


class ProducerLinkageTests(unittest.TestCase):
    def fixture(self):
        spec=lambda file,sha:{'file':file,'sha256':sha}
        qualified={key:spec(key+'.py',key+'_code') for key in ('fit_data','refit','controls')}
        targets=spec('target.json','target_hash');ready_spec=spec('ready.json','ready_hash')
        model_spec=spec('model.json','model_hash');train_cfg=spec('train_config.json','train_hash')
        admission_spec=spec('admission.json','admission_hash');gate_spec=spec('controls/gate.json','gate_hash')
        forecasts={a:spec(a+'.json',a+'_hash') for a in module.NEW_ARMS}
        cfg={'qualified_source_pins':qualified,'fit_source_admission':admission_spec,'forecasts':forecasts,
            'refit_generation_receipt':forecasts[module.REFIT],
            'control_generation_receipt':spec('controls/delivery.json','delivery_hash')}
        counts={'original_full_positive_cells':208835,'augmented_positive_cells':210776,
            'added_positive_cells':1941,'fit_universe':4040,'augmented_root_positive_rows':3567,
            'fitting_proteins_with_additions':161,'original_root_positive_rows':3557,
            'original_full_positive_cells_lost':0,'retention_mask_equals_original_FULL':True}
        admission={'status':'passed','qualified':True,'plan_sha256':module.PLAN_SHA256,
            'source_preparation_code':qualified['fit_data'],
            'source_preparation_configuration':spec('prepare_config.json','prepare_hash'),
            'counts':counts,'target_manifest_sha256':'target_hash','target_manifest':targets}
        model={'status':'complete','plan_sha256':module.PLAN_SHA256,'producer_code_sha256':'refit_code',
            'namespace':module.NS,'n_layers':8,'in_goa':40,
            'original_model_metadata_sha256':'1839d2d09ad62b4ee6770fb623dc62dbca4b9ad2ab8c7ba91680c62b5acef2dc',
            'frozen_epoch_indices_zero_based':[10,12,11],'native_callback_calls':20,
            'current_validation_metric_computed':False,'current_validation_predictions_or_metrics_computed':False,
            'reference_previously_consumed':True,'independent_confirmation':False,
            'native_train_and_SWA_bodies_changed':False,'uniform_three_parameter_state_average_max_abs':0.,
            'checkpoint_file':'weights.pth','checkpoint_sha256':'weight_hash','source_readiness':ready_spec,
            'configuration_sha256':'train_hash','source_admission':{'source_admission_sha256':'admission_hash'}}
        meta={module.REFIT:{'status':'complete','producer_code_sha256':'refit_code',
            'producer_source':qualified['refit'],'model_metadata':model_spec,'model_metadata_sha256':'model_hash',
            'source_configuration':train_cfg,'source_readiness':ready_spec}}
        for a in (module.UNION_LP,module.UNION_PRIOR):
            meta[a]={'status':'complete','configuration_sha256':'control_hash','generation_receipt':gate_spec}
        docs={'admission.json':admission,'model.json':model,
            'train_config.json':{'plan':{'sha256':module.PLAN_SHA256},'namespace':module.NS,'seed':20261115,'source_readiness':ready_spec},
            'ready.json':{'source_admission':admission_spec,'manifests':{'targets':targets}},
            'controls/delivery.json':{'status':'complete','plan_sha256':module.PLAN_SHA256,
                'source_code_sha256':'controls_code','arms':{a:{module.NS:forecasts[a]} for a in (module.UNION_LP,module.UNION_PRIOR)},
                'configuration_sha256':'control_hash','generation_receipt_sha256':'gate_hash'},
            'controls/configuration.json':{'source_plan':{'sha256':module.PLAN_SHA256},'candidate_fit_manifest':targets},
            'controls/gate.json':{'plan_sha256':module.PLAN_SHA256,'source_code_sha256':'controls_code',
                'configuration_sha256':'control_hash','new_forecast_arrays_generated_at_receipt':False}}
        hashes={'fit_data.py':'fit_data_code','prepare_config.json':'prepare_hash',
                'refit.py':'refit_code','weights.pth':'weight_hash'}
        return cfg,meta,docs,hashes

    def check(self,cfg,meta,docs,hashes):
        with patch.object(module,'pinned_json',side_effect=lambda spec:docs[spec['file']]), \
             patch.object(module,'file_sha256',side_effect=lambda path:hashes[str(path)]):
            return module.validate_producer_bindings(cfg,meta)

    def test_exact_completed_source_model_and_matched_control_chain(self):
        cfg,meta,docs,hashes=self.fixture()
        self.assertTrue(self.check(cfg,meta,docs,hashes)['completed_and_qualified_producer_linkage_verified'])

    def test_unrelated_honest_forecasts_and_stale_target_prior_chain_rejected(self):
        mutations=[lambda c,m,d:d['controls/delivery.json']['arms'][module.UNION_LP][module.NS].update(sha256='unrelated'),
            lambda c,m,d:d['controls/configuration.json']['candidate_fit_manifest'].update(sha256='stale'),
            lambda c,m,d:d['model.json'].update(native_callback_calls=19),
            lambda c,m,d:d['admission.json'].update(qualified=False),
            lambda c,m,d:m[module.REFIT].update(status='partial'),
            lambda c,m,d:d['controls/delivery.json'].update(source_code_sha256='different_code'),
            lambda c,m,d:d['controls/gate.json'].update(new_forecast_arrays_generated_at_receipt=True)]
        for mutation in mutations:
            cfg,meta,docs,hashes=self.fixture()
            # Break intentional fixture object-sharing: real JSON files are independent.
            cfg,meta,docs=copy.deepcopy(cfg),copy.deepcopy(meta),copy.deepcopy(docs)
            mutation(cfg,meta,docs)
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):self.check(cfg,meta,docs,hashes)


class PairedAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import numpy as np
        except ImportError:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest('Optional scientific NumPy runtime unavailable')
        cls.np=np

    def boot(self,scores):
        return {'draws':2000,'seed':20261113,'raw_proteins':17,'ordinary_only':True,
            'shared_protein_samples_across_all_arms':True,
            'scores':{a:{'bootstrap_Fmax':[float(v)]*2000,'bootstrap_mean':v,
                         'bootstrap_95_percentile_interval':[v,v]} for a,v in scores.items()}}

    def test_saved_old_peaks_retained_and_negative_new_contrasts_visible(self):
        old_values={a:.4 for a in module.SOURCE_COMPARATORS+module.PREVIOUS_NEW_ARMS}
        old=self.boot(old_values);before=copy.deepcopy(old)
        new=self.boot({module.REFIT:.5,module.UNION_LP:.6,module.UNION_PRIOR:.45})
        joined=module.joined_bootstrap(old,new)
        self.assertEqual(old,before)
        self.assertEqual(set(joined['scores']),set(old['scores'])|set(new['scores']))
        for name in old['scores']:self.assertEqual(joined['scores'][name],old['scores'][name])
        pairs={(r['candidate'],r['comparator']):r for r in joined['comparisons']}
        self.assertEqual(set(pairs),set(module.required_pairs(tuple(old['scores']))))
        self.assertLess(pairs[module.REFIT,module.UNION_LP]['paired_95_percentile_interval'][1],0)
        self.assertGreater(pairs[module.UNION_LP,module.UNION_PRIOR]['paired_95_percentile_interval'][0],0)
        self.assertFalse(joined['independent_confirmation']);self.assertFalse(joined['new_success_gate_or_model_selection'])

    def test_pair_design_or_peak_corruption_rejected(self):
        old=self.boot({a:.4 for a in module.SOURCE_COMPARATORS+module.PREVIOUS_NEW_ARMS})
        new=self.boot({module.REFIT:.5,module.UNION_LP:.6,module.UNION_PRIOR:.45})
        for key,value in [('seed',1),('raw_proteins',18),('ordinary_only',False)]:
            changed=copy.deepcopy(new);changed[key]=value
            with self.assertRaisesRegex(ValueError,'fixed protein design'):module.joined_bootstrap(old,changed)
        changed=copy.deepcopy(new);changed['scores'][module.REFIT]['bootstrap_Fmax'][3]=float('nan')
        with self.assertRaisesRegex(ValueError,'invalid preserved'):module.joined_bootstrap(old,changed)


if __name__=='__main__':unittest.main()
