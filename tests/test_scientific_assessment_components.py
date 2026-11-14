"""Invented aggregate outcomes test scope/privacy, not biological performance."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward import scientific_assessment as module
from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from test_scientific_assessment import fixtures,sealed


def function_source():
    rows=[];denominators=[]
    for frame,count in [('primary',27),('reserved',13)]:
        methods=sorted(module.FUNCTION_METHODS[frame])
        if frame=='primary':methods.remove('fastsinksourceplus');methods.insert(0,'fastsinksourceplus')
        for setting in ('partial','partial_publishedaftert0'):
            for ns in ('biological_process','molecular_function','cellular_component'):
                denominators.append({'frame':frame,'setting':setting,'namespace':ns,'eligible_proteins':3,
                    'IA_eligible_proteins':2,'author_recognized_target_IDs':3,'post_known_TOI_reference_pairs':5})
                rows += [{'frame':frame,'setting':setting,'namespace':ns,'method':method,'status':'pending',
                          'eligible_proteins':3,'IA_eligible_proteins':2} for method in methods]
    row=rows[0];row.update(status='scored',source='/Users/invented/curve.tsv',native_curve_rows=2,
        **{k:.1 for k in ('micro_Fmax','micro_Fmax_tau','IA_micro_Fmax','IA_micro_Fmax_tau','macro_Fmax',
            'macro_Fmax_tau','IA_macro_Fmax','IA_macro_Fmax_tau','unweighted_Smin_tau','IA_weighted_Smin_tau',
            'prediction_coverage_at_micro_Fmax')},unweighted_Smin=3.,IA_weighted_Smin=2.,
        fixed_0_5={'threshold':.5,'namespace':row['namespace'],'status':'author omits thresholds with zero prediction coverage',
                  'PPV':None,'recall':None,'F1':None})
    return sealed({'format':'biograph-steward.cafa5-scientific-aggregate-projection.v1','created_at':'invented-date',
        'status':'snapshot with pending secondary outcomes','scientific_task':'temporal annotation recovery',
        'scope':{'whole_graph_biological_truth_or_clinical_utility_claimed':False,'no_raw_reference_or_prediction_rows_included':True},
        'roles':{'original_primary':{'candidate':'fastsinksourceplus','frame':'primary','metric':'micro_Fmax','conclusion':'Negative original primary retained.'},
                 'deployed_source_profile':'strict_alias_localplus'},'expected_outcome_slots':240,
        'status_counts':dict(Counter(r['status'] for r in rows)),'rows':rows,'denominators':denominators,
        'paired_comparisons':[],'uncertainty_reports':[],'runtime':{'numpy':'1.26.4'},'evaluation_contract':{'fixed_operating_point':.5},
        'reference':{'license':'CC-BY-4.0'},'caveats':['Same-study protein transfer; not independent study replication.'],
        'lineage':{},'source_pins':{'/Users/invented/receipt.json':'a'*64},
        'native_aggregate_source_files_sha256':{'/Users/invented/curve.tsv':'b'*64},
        'all_outcomes_including_negatives_and_unsupported_retained':True,
        'new_model_threshold_or_target_selection_from_this_projection':False})


def biored_sources():
    metrics={'cases':2,'exact_correct':1,'exact_accuracy':.5,'coverage':.5,'unresolved':1,'native_None_cases':1,
        'confusion':{'Association -> Association':1,'None -> Unresolved':1},
        'exact_positive_relation':{'tp':1,'fp':0,'fn':0,'precision':1.,'recall':1.,'f1':1.},
        'entity_pair':{'tp':1,'fp':0,'fn':0,'precision':1.,'recall':1.,'f1':1.}}
    fixed=['always_None','typed_co_mention','specialist_native','specialist_type_guard']
    all_arms=fixed+['flat_context_LLM','source_audit_agent'];comparison={
        'accuracy_delta_95pct_paired_bootstrap':[-.1,.1],'exact_relation_F1_delta_95pct_paired_bootstrap':[-.1,.1]}
    primary={'format':module.BIORED_FORMATS['primary'],'created_at':'invented-date','test_cases':2,'test_publications':2,
        'gold_label_counts':{'Association':1,'None':1},'metrics':{a:deepcopy(metrics) for a in all_arms},
        'per_entity_type_metrics':{'Invented--GeneOrGeneProduct':{a:deepcopy(metrics) for a in all_arms}},
        'prediction_freeze_content_sha256':'c'*64,'agent_default_adoption_criterion_passed':False,'live_graph_changed':False,
        'agent_paired_comparisons':{a:deepcopy(comparison) for a in ['specialist_native','specialist_type_guard','flat_context_LLM']},
        'execution_costs':{'source_audit_agent':{'model_calls':2,'tool_reads':3}},'limitations':['Training membership unestablished.']}
    gene={'format':module.BIORED_FORMATS['gene'],'created_at':'invented-date','cases':2,'publications':1,
        'native_gold_label_counts':{'Association':1,'None':1},'metrics':{a:deepcopy(metrics) for a in fixed},
        'per_entity_type_metrics':{'Invented--GeneOrGeneProduct':{a:deepcopy(metrics) for a in fixed}},
        'primary_prediction_freeze_content_sha256':'c'*64,'source_graph_changes':0,'training_performed':False}
    levels=('pair','pair+novelty','relation','relation+novelty','relation+direction','all')
    artifact={'format':module.BIORED_FORMATS['artifact'],'created_at':'invented-date','source_graph_changes':0,
        'additional_LLM_requests':0,'primary_prediction_freeze_content_sha256':'c'*64,
        'checkpoint_training_membership_independently_audited':False,'native_candidate_rows':3,'native_candidate_publications':2,
        'released_corpus_abstracts':3,'author_metric_reference_agreement':{k:{'precision':.5,'recall':.5,'f1':.5} for k in levels},
        'paper_reported_10_seed_mean_F1':{k:.6 for k in levels},'single_checkpoint_minus_paper_mean_F1':{k:-.1 for k in levels},
        'interpretation':'Artifact diagnostic only, not training independence.'}
    return {k:sealed(v) for k,v in [('primary',primary),('gene',gene),('artifact',artifact)]}


class SeparateComponentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.base,self.base_pins=fixtures(self.root/'base')

    def function(self,value=None,name='function'):
        path=self.root/(name+'_source.json');write_json(path,sealed(value or function_source()))
        out=self.root/(name+'.json');module.prepare_function_recovery_aggregate(path,out,expected_report_pin=sha(path));return out

    def biored(self,values=None,name='biored'):
        values=values or biored_sources();paths={}
        for role,value in values.items():
            paths[role]=self.root/(name+'_'+role+'.json');write_json(paths[role],sealed(value))
        out=self.root/(name+'.json');module.prepare_biored_aggregate(paths,out,expected_report_pins={k:sha(p) for k,p in paths.items()});return out

    def test_v4_keeps_complete_slots_unknowns_and_separate_scope_with_no_operator_paths(self):
        function=self.function();bio=self.biored();out=self.root/'publication'
        module.publish(self.base,out,expected_source_pins=self.base_pins,function_recovery_report=function,
            expected_function_recovery_pin=sha(function),biored_report=bio,expected_biored_pin=sha(bio))
        manifest,summary,files=module.load_publication(out)
        self.assertEqual(manifest['format'],module.FORMAT_V4);self.assertEqual(len(summary['function_recovery']['rows']),240)
        self.assertEqual(summary['function_recovery']['status_counts'],{'scored':1,'pending':239})
        self.assertEqual(summary['default_view']['original'],10)
        self.assertEqual(summary['agent_reference_agreement']['primary']['test_cases'],2)
        self.assertIn('99-target',summary['scope']);self.assertNotEqual(summary['scope'],summary['workspace_scope'])
        self.assertIsNone(summary['function_recovery']['rows'][0]['fixed_0_5']['F1'])
        self.assertNotIn('/Users/',b''.join(files.values()).decode())
        html=files['report.html'].decode();self.assertIn('separate tasks and source scopes',html)
        self.assertIn('Legacy 99-target workspace',html);self.assertNotIn('<h1>Scientific assessment</h1><p class=scope>Whole-graph',html.split('Legacy 99-target')[0])
        self.assertEqual(module.list_publications(self.root)['assessments'][0]['id'],'publication')

    def test_function_cannot_drop_negative_arms_change_denominators_or_fill_pending_with_zero(self):
        for mutate in (lambda v:v['rows'].pop(),lambda v:v['rows'].__setitem__(1,deepcopy(v['rows'][0])),
                lambda v:v['rows'][0].update(eligible_proteins=2),lambda v:v['rows'][1].update(micro_Fmax=0),
                lambda v:v['scope'].update(whole_graph_biological_truth_or_clinical_utility_claimed=True),
                lambda v:[r.update(method='renamed_failure') for r in v['rows'] if r['method']=='localplus'],
                lambda v:v['rows'][1].update(IA_macro_Fmax=0)):
            value=function_source();mutate(value)
            with self.subTest(value=value['rows'][:2]),self.assertRaises(ValueError):self.function(value)

    def test_raw_cases_and_wrong_source_FILE_pins_fail_before_publication(self):
        value=function_source();value['roles']['case_id']='invented-private-case'
        with self.assertRaises(ValueError):self.function(value)
        source=self.root/'source.json';write_json(source,function_source())
        with self.assertRaises(ValueError):module.prepare_function_recovery_aggregate(source,self.root/'no.json',expected_report_pin='0'*64)
        self.assertFalse((self.root/'no.json').exists())

    def test_biored_preserves_abstentions_all_arms_and_recorded_adoption_rule(self):
        for mutate in (lambda v:v['primary']['metrics'].pop('always_None'),
                lambda v:v['primary']['metrics']['source_audit_agent'].update(exact_accuracy=1.),
                lambda v:v['primary'].update(agent_default_adoption_criterion_passed=True),
                lambda v:v['artifact'].update(checkpoint_training_membership_independently_audited=True)):
            values=biored_sources();mutate(values)
            with self.assertRaises(ValueError):self.biored(values)

    def test_component_tampering_and_private_fields_fail_closed(self):
        function=self.function();value=json.loads(function.read_text());value['results']['rows'][0]['case_id']='private'
        write_json(function,sealed(value))
        with self.assertRaises(ValueError):module.publish(self.base,self.root/'no-publication',expected_source_pins=self.base_pins,
            function_recovery_report=function,expected_function_recovery_pin=sha(function))
        self.assertFalse((self.root/'no-publication').exists())

    def test_native_nonfinite_status_is_retained_without_an_invented_score(self):
        value=function_source();value['rows'][1].update(status='nonfinite_native_curve',
            reason='Native output retained; metrics not finite.')
        value['status_counts']=dict(Counter(r['status'] for r in value['rows']))
        component=self.function(value)
        result=json.loads(component.read_text())['results']
        self.assertEqual(result['status_counts']['nonfinite_native_curve'],1)
        self.assertNotIn('micro_Fmax',result['rows'][1])

    def test_native_coverage_preserves_author_eligibility_ratio_without_weakening_F1(self):
        value=function_source();row=value['rows'][0];row['fixed_0_5'].update(
            status='unchanged author curve at predeclared threshold',PPV=.1,recall=.2,F1=.13,coverage=4/3)
        for d in value['denominators']:d['author_recognized_target_IDs']=4
        component=self.function(value);saved=json.loads(component.read_text())['results']['rows'][0]
        self.assertEqual(saved['fixed_0_5']['coverage'],4/3)
        for field,number in (('coverage',5/3),('F1',1.01)):
            changed=deepcopy(value);changed['rows'][0]['fixed_0_5'][field]=number
            with self.assertRaises(ValueError):self.function(changed,name=field)


if __name__=='__main__':unittest.main()
