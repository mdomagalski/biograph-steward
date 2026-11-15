"""Invented pairing/provenance tests for consumed-reference development only."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import annotation_prior_assessment as module
from .annotation_prior_assessment import (CANDIDATE, MATCHED_PRIOR, ORIGINAL_PRIOR,
    check_authorization, combined_bootstrap, load_original_counts, prior_equivalence,
    validate_plan)
from tools.learned_combination.reference import file_sha256


class BoundaryTests(unittest.TestCase):
    def test_unapproved_or_false_freshness_execution_fails_before_file_access(self):
        cfg = {'format': 'biograph-steward.annotation-prior-assessment.v1',
               'parent_authorized_consumed_reference_assessment': False,
               'development_followup_on_consumed_reference': True,
               'independent_confirmation': False}
        with patch.object(module, 'pinned_json', side_effect=AssertionError('must not read')) as reader:
            with self.assertRaisesRegex(ValueError, 'parent must authorize'):
                module.prepare_inputs(cfg)
            reader.assert_not_called()
        cfg['parent_authorized_consumed_reference_assessment'] = True
        cfg['independent_confirmation'] = True
        with self.assertRaisesRegex(ValueError, 'consumed-reference status'):
            check_authorization(cfg)

    def test_fixed_plan_rejects_new_variant_or_confidence_value(self):
        path = Path(__file__).with_name('annotation_prior_protocol.json')
        plan = json.loads(path.read_text());validate_plan(plan)
        changed = copy.deepcopy(plan);changed['real_variants']['count'] = 2
        with self.assertRaisesRegex(ValueError, 'one fixed'):
            validate_plan(changed)
        changed = copy.deepcopy(plan)
        changed['published_operator']['annotation_score_as_float64'] = .99
        with self.assertRaisesRegex(ValueError, 'Float32 annotation score'):
            validate_plan(changed)


class NumericTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            cls.np = np
        except ImportError:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED') == '1':raise
            raise unittest.SkipTest('Optional NumPy runtime unavailable')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root = Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def frame(self):
        np = self.np
        return {'ids': np.asarray(['P1','P2','P3']), 'tau': np.asarray([.001,.5,.999]),
                'ordinary': np.asarray([[[1,1,0,0,1,1]]*3,
                    [[1,0,1,1,0,0]]*3, [[0,0,0,1,0,0]]*3], dtype=np.float64)}

    def test_saved_original_counts_require_literal_order_grid_and_pin(self):
        np = self.np;row = self.frame();folder = self.root/'native/PK';folder.mkdir(parents=True)
        path = folder/'bp_control_counts.npz'
        np.savez_compressed(path, **row, eligible=np.ones(3,dtype=bool))
        rel = 'native/PK/bp_control_counts.npz';report = {'files': {rel:file_sha256(path)}}
        actual = load_original_counts(self.root,report,'native','PK','bp','control',row['ids'],row['tau'])
        np.testing.assert_array_equal(actual['ordinary'],row['ordinary'])
        with self.assertRaisesRegex(ValueError, 'pairing frame'):
            load_original_counts(self.root,report,'native','PK','bp','control',row['ids'][::-1],row['tau'])
        with self.assertRaisesRegex(ValueError, 'pairing frame'):
            load_original_counts(self.root,report,'native','PK','bp','control',row['ids'],np.asarray([.001,.6,.999]))
        report['files'][rel] = '0'*64
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            load_original_counts(self.root,report,'native','PK','bp','control',row['ids'],row['tau'])

    def test_actual_invented_producer_delivery_is_accepted_without_contract_reinvention(self):
        from . import annotation_prior as producer
        from .test_annotation_prior import SourceAdmissionTests
        from tools.learned_combination.runner import write_json
        fixture=SourceAdmissionTests(methodName='runTest');fixture.setUp()
        folder=self.root/'invented_original';folder.mkdir()
        producer_cfg=fixture.fixture(folder)
        with patch.object(producer,'ORIGINAL_SEAL_SHA256',producer_cfg['original_seal_sha256']), \
             patch.object(producer,'TARGET_COUNT',len(fixture.proteins)), \
             patch.object(producer,'AUTHOR_SCRIPT_SHA256',producer_cfg['author_script']['sha256']):
            producer.run(producer_cfg,self.root/'actual_producer_outputs')
        original_cfg=json.loads((folder/'configuration.json').read_text())
        original={'forecast_seal_sha256':producer_cfg['original_seal_sha256']}
        report=self.root/'invented_original_report.json';write_json(report,original)
        plan=json.loads(Path(__file__).with_name('annotation_prior_protocol.json').read_text())
        plan['original_forecast_seal_sha256']=producer_cfg['original_seal_sha256']
        plan['original_raw_report_sha256']=file_sha256(report)
        plan['published_operator']['source_sha256']=producer_cfg['author_script']['sha256']
        plan_file=self.root/'invented_plan.json';write_json(plan_file,plan)
        review_file=self.root/'invented_independent_review.json'
        write_json(review_file,{'qualified':True,'plan_sha256':file_sha256(plan_file),
            'development_followup_on_consumed_reference':True})
        delivery=self.root/'actual_producer_outputs/delivery.json'
        cfg={'format':'biograph-steward.annotation-prior-assessment.v1',
            'parent_authorized_consumed_reference_assessment':True,
            'development_followup_on_consumed_reference':True,'independent_confirmation':False,
            'plan':{'file':str(plan_file),'sha256':file_sha256(plan_file)},
            'independent_plan_review':{'file':str(review_file),'sha256':file_sha256(review_file)},
            'original_seal_directory':str(folder),
            'original_report':{'file':str(report),'sha256':file_sha256(report)},
            'qualified_producer_source':{'file':producer.__file__,'sha256':file_sha256(producer.__file__)},
            'merge_delivery':{'file':str(delivery),'sha256':file_sha256(delivery)}}
        with patch.object(module,'open_seal',return_value=(original_cfg,{})):
            _,_,_,_,arms,targets=module.prepare_inputs(cfg)
        self.assertEqual(targets,fixture.proteins)
        self.assertEqual(set(arms),set(module.NEW_ARMS))
        self.assertEqual(set(arms[CANDIDATE]),set(module.NS_ASPECT))
        # Actual producer schema passes; each contradictory field is rejected
        # in both the delivery envelope and a per-namespace forecast manifest.
        for per_forecast in (False,True):
            original_delivery=json.loads(delivery.read_text())
            spec=original_delivery['forecasts']['biological_process']
            manifest=Path(spec['file'])
            clean_metadata=manifest.read_text()
            for field,bad in (('scientific_metrics_computed',True),
                              ('forecast_scores_transformed',False),
                              ('models_fitted',True),('fresh_final_reference_claimed',True)):
                content=json.loads(clean_metadata) if per_forecast else copy.deepcopy(original_delivery)
                content[field]=bad
                if per_forecast:
                    manifest.write_text(json.dumps(content))
                    changed=copy.deepcopy(original_delivery)
                    changed['forecasts']['biological_process']['sha256']=file_sha256(manifest)
                else:changed=content
                delivery.write_text(json.dumps(changed))
                cfg['merge_delivery']['sha256']=file_sha256(delivery)
                with patch.object(module,'open_seal',return_value=(original_cfg,{})):
                    with self.assertRaisesRegex(ValueError,'transformed scores from scientific metrics'):
                        module.prepare_inputs(cfg)
                manifest.write_text(clean_metadata)
            delivery.write_text(json.dumps(original_delivery))
        clean_delivery=json.loads(delivery.read_text())
        for field,bad in (('original_forecast_seal_sha256','0'*64),('source_code_sha256','0'*64)):
            changed=copy.deepcopy(clean_delivery);changed[field]=bad
            delivery.write_text(json.dumps(changed));cfg['merge_delivery']['sha256']=file_sha256(delivery)
            with patch.object(module,'open_seal',return_value=(original_cfg,{})):
                with self.assertRaisesRegex(ValueError,'bound to'):
                    module.prepare_inputs(cfg)
        delivery.write_text(json.dumps(clean_delivery));cfg['merge_delivery']['sha256']=file_sha256(delivery)
        spec=clean_delivery['matched_prior_forecasts']['biological_process']
        meta_path=Path(spec['file']);meta=json.loads(meta_path.read_text())
        meta['matched_prior_only']=False;meta_path.write_text(json.dumps(meta))
        changed=copy.deepcopy(clean_delivery)
        changed['matched_prior_forecasts']['biological_process']['sha256']=file_sha256(meta_path)
        delivery.write_text(json.dumps(changed));cfg['merge_delivery']['sha256']=file_sha256(delivery)
        with patch.object(module,'open_seal',return_value=(original_cfg,{})):
            with self.assertRaisesRegex(ValueError,'exactly zero model'):
                module.prepare_inputs(cfg)

    def test_reused_draws_and_losses_equal_one_joint_existing_bootstrap(self):
        np=self.np
        from .assessment import bootstrap_contrast
        first=self.frame();worse=copy.deepcopy(first);worse['ordinary'][:,:,1]=0
        worse['ordinary'][:,:,2]=1;worse['ordinary'][:,:,3]=1
        old=bootstrap_contrast({'old_selected':first,'strong_control':first,ORIGINAL_PRIOR:first},'old_selected')
        new=bootstrap_contrast({CANDIDATE:worse,MATCHED_PRIOR:first},CANDIDATE)
        before=copy.deepcopy(old);joined=combined_bootstrap(old,new)
        self.assertEqual(old,before)
        all_at_once=bootstrap_contrast({'old_selected':first,'strong_control':first,
            ORIGINAL_PRIOR:first,CANDIDATE:worse,MATCHED_PRIOR:first},CANDIDATE)
        self.assertEqual(joined['scores'],all_at_once['scores'])
        self.assertEqual(len(joined['comparisons']),4)
        actual={row['comparator']:row for row in joined['comparisons']}
        for row in all_at_once['comparisons']:
            expected=actual[row['comparator']]
            for key in ('difference_draws','difference_mean','paired_95_percentile_interval','fraction_draws_above_zero'):
                self.assertEqual(expected[key],row[key])
        self.assertLess(actual['strong_control']['difference_mean'],0.)
        self.assertFalse(joined['independent_confirmation'])
        self.assertTrue(joined['original_native_gated_draws_reused_without_recomputation'])

    def test_wrong_seed_or_missing_arm_cannot_join_old_and_new_draws(self):
        from .assessment import bootstrap_contrast
        row=self.frame()
        old=bootstrap_contrast({'old_selected':row,ORIGINAL_PRIOR:row},'old_selected')
        new=bootstrap_contrast({CANDIDATE:row,MATCHED_PRIOR:row},CANDIDATE)
        new['seed']=99
        with self.assertRaisesRegex(ValueError,'fixed protein design'):combined_bootstrap(old,new)
        new['seed']=20261113;new['scores']['old_selected']=new['scores'][CANDIDATE]
        with self.assertRaisesRegex(ValueError,'distinct'):combined_bootstrap(old,new)

    def test_prior_point_and_every_single_draw_must_equal_exactly(self):
        values=[.5]*2000
        old={'scores':{ORIGINAL_PRIOR:{'bootstrap_Fmax':values}}}
        new={'scores':{MATCHED_PRIOR:{'bootstrap_Fmax':values.copy()}}}
        self.assertEqual(prior_equivalence(.5,.5,old,new)['status'],'passed')
        with self.assertRaisesRegex(ValueError,'point differs'):prior_equivalence(.5,.50000000001,old,new)
        new['scores'][MATCHED_PRIOR]['bootstrap_Fmax'][143]=self.np.nextafter(.5,1.)
        with self.assertRaisesRegex(ValueError,'paired Fmax peaks differ'):prior_equivalence(.5,.5,old,new)
        with self.assertRaisesRegex(ValueError,'requires all paired'):prior_equivalence(.5,.5,None,None)

    def test_unscorable_cells_remain_explicitly_unverified(self):
        result=prior_equivalence(None,None,None,None)
        self.assertFalse(result['equivalence_claimed'])
        self.assertIn('unavailable',result['status'])


class NativeHeightControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            from tools.learned_combination.native_adapter import _native
            cls.np=np;cls.native=_native()
        except (ImportError,ModuleNotFoundError) as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest('Optional pinned native evaluator unavailable: '+str(error))

    def test_actual_native_curves_differ_but_prior_peaks_and_draws_remain_identical(self):
        np=self.np
        from tools.learned_combination.native_adapter import evaluate_native
        from tools.learned_combination.ordinary_counts import contributions,verify_curve
        from .assessment import bootstrap_contrast
        namespace='molecular_function';native=self.native['graph']
        terms={}
        for i in range(4):
            term='GO:100000'+str(i)
            terms[term]={'name':term,'namespace':namespace,'def':'','alt_id':[],
                         'rel':[] if i==0 else ['GO:1000000']}
        ontology=native.Graph(namespace,terms);ontology.toi=np.asarray([1,2,3],dtype=int)
        ids={'P1':0,'P2':1,'P3':2};truth=np.zeros((3,4),dtype=bool)
        truth[0,1]=truth[1,2]=truth[2,3]=True
        support=np.asarray([[0,1,0,0],[0,1,1,0],[0,0,1,0]],dtype=bool)
        gt=native.GroundTruth(dict(ids),truth,namespace);tau=np.arange(.001,1,.001)
        rows={};points={};curves={}
        for arm,height in ((ORIGINAL_PRIOR,1.),(MATCHED_PRIOR,float(np.float32(.99)))):
            pred=native.Prediction(dict(ids),support.astype(np.float64)*height,namespace)
            pred._learned_combination_terms=tuple(terms)
            with redirect_stdout(io.StringIO()):
                curve,point=evaluate_native({namespace:pred},{namespace:gt},{namespace:ontology},tau=tau,n_cpu=1)
            counts,_=contributions(pred,gt,ontology,tau)
            self.assertTrue(verify_curve(counts,curve,namespace=namespace)['author_point_agreement_passed'])
            rows[arm]={'ids':np.asarray(list(ids)),'tau':tau,'ordinary':counts}
            points[arm]=point[namespace];curves[arm]=curve
        # Above .99 the matched arm is intentionally empty; full curve identity
        # would be an incorrect gate for this source-qualified height control.
        self.assertFalse(np.array_equal(rows[ORIGINAL_PRIOR]['ordinary'],rows[MATCHED_PRIOR]['ordinary']))
        old=bootstrap_contrast({'old_selected':rows[ORIGINAL_PRIOR],ORIGINAL_PRIOR:rows[ORIGINAL_PRIOR]},'old_selected')
        new=bootstrap_contrast({CANDIDATE:rows[MATCHED_PRIOR],MATCHED_PRIOR:rows[MATCHED_PRIOR]},CANDIDATE)
        self.assertEqual(prior_equivalence(points[ORIGINAL_PRIOR],points[MATCHED_PRIOR],old,new)['status'],'passed')


if __name__=='__main__':unittest.main()
