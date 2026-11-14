"""Invented aggregate-only42outcome non-exclusion publication checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile,unittest
from biograph_steward.client import digest,write_json
from biograph_steward.file_utils import sha
from .nonpk_publish import prepare,SETTINGS,ASPECTS,CONTROLS


def write(path,v):write_json(path,{**v,'content_sha256':digest(v)})


class NativePublication(unittest.TestCase):
    def fixture(self,root):
        runtime={'python':'3.10.12','numpy':'1.26.4','scipy':'1.13.1','pandas':'2.2.3'}
        den=[{'setting':s,'namespace':a,'author_recognized_target_IDs':2,'eligible_proteins':2,'IA_eligible_proteins':2}for s in SETTINGS for a in ASPECTS]
        def point(s,a,m):return{'setting':s,'namespace':a,'method':m,'known_exclusion':None,'eligible_proteins':2,'IA_eligible_proteins':2,
            'status':'scored','micro_Fmax':.2,'IA_micro_Fmax':.1,'macro_Fmax':.3,'IA_macro_Fmax':.2,
            'unweighted_Smin':3.,'IA_weighted_Smin':2.,'source_curve_sha256':'a'*64,
            'fixed_0_5':{'status':'no_native_coverage','PPV':None,'recall':None,'F1':None}}
        oldrows=[point(s,a,m)for s in SETTINGS for a in ASPECTS for m in (*CONTROLS,'official_blast','official_naive','official_prott5_cosine3','GM')]
        old={'rows':oldrows,'denominators':den};write(root/'old.json',old)
        policy={'format':'biograph-steward.deepgo-nonpk-evaluation.v1.freeze','known_exclusion':None,'focus_namespace':'molecular_function',
            'previous_reference_outcomes_exposed':True,'producer_protocol_file_sha256':'b'*64,
            'forecast_manifest_file_sha256':'c'*64,'lifecycle_done_file_sha256':'d'*64}
        write(root/'freeze.json',policy)
        pairs=[];reports={}
        for s in SETTINGS:
            cs=[{'candidate':'deepgose','comparator':c,'readout':k,'difference_mean':.1 if c==CONTROLS[0]else-.1,
                 'paired_95_percentile_interval':[.01,.2]if c==CONTROLS[0]else[-.2,-.01]}for c in CONTROLS for k in ('ordinary','IA_weighted')]
            b={'draws':2000,'seed':20261113,'numpy':'1.26.4','shared_protein_samples_across_all_arms':True,
               'raw_proteins':2,'scores':{m:{}for m in ('deepgose',*CONTROLS)},'comparisons':cs};b['content_sha256']=digest(b);reports[s]=b
            pairs.extend({'setting':s,'namespace':'molecular_function',**c}for c in cs)
        agreements={s+'/'+m:{'author_point_agreement_passed':True,'known_exclusion':None,'namespace':'molecular_function',
            'raw_reference_proteins':2,'ordinary_eligible':2,'IA_weighted_eligible':2,
            'checks':{'native_micro':{'max_absolute_curve_difference':0.}}}for s in SETTINGS for m in ('deepgose',*CONTROLS)}
        result={'format':'biograph-steward.deepgo-nonpk-evaluation.v1.results','evaluation_freeze_file_sha256':sha(root/'freeze.json'),
            'previous_aggregate_file_sha256':sha(root/'old.json'),'runtime':runtime,**{k:policy[k]for k in ('known_exclusion','focus_namespace','producer_protocol_file_sha256','forecast_manifest_file_sha256','lifecycle_done_file_sha256')},
            'earlier_36_outcome_rows':oldrows,'new_outcome_rows':[point(s,a,'deepgose')for s in SETTINGS for a in ASPECTS],
            'denominators':den,'expected_outcome_slots':42,'paired_comparisons':pairs,'native_MFO_point_count_agreements':agreements,
            'uncertainty_reports':reports,'all_existing_controls_negatives_and_missing_retained':True,'app_default_or_consumer_changed':False,
            'original_PK_protocol_or_results_changed':False,'new_reference_release':False,'raw_reference_or_forecast_rows_included':False,
            'input_files_sha256':{'/data/private/operator.json':'e'*64},'limitations':['INVENTED fixture, not scientific results.']}
        write(root/'source.json',result);return result

    def publish(self,r):return prepare(r/'source.json',sha(r/'source.json'),r/'freeze.json',sha(r/'freeze.json'),r/'old.json',sha(r/'old.json'),r/'public')

    def test_all42points_eight_mixed_intervals_missing_endpoints_and_privacy(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);source=self.fixture(root);r=self.publish(root)
            self.assertEqual(r['results']['earlier_36_outcome_rows'],source['earlier_36_outcome_rows'])
            self.assertEqual(r['results']['paired_comparisons'],source['paired_comparisons'])
            self.assertEqual(r['outcome_slots'],42);self.assertEqual(r['MFO_paired_intervals'],8)
            self.assertIsNone(r['results']['new_outcome_rows'][0]['fixed_0_5']['PPV'])
            self.assertNotIn('/data/',(root/'public/report.json').read_text())
            self.assertIn('exclude=None',(root/'public/report.html').read_text())
            self.assertFalse(r['automatic_adoption'])

    def test_dropped_old_or_negative_outcomes_wrong_mask_runtime_and_rawcase_fail(self):
        for mutation in ('old','negative','mask','runtime','case'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory()as t:
                root=Path(t);d=self.fixture(root);d.pop('content_sha256',None)
                if mutation=='old':d['earlier_36_outcome_rows'].pop()
                elif mutation=='negative':d['paired_comparisons'].pop()
                elif mutation=='mask':d['known_exclusion']='known.tsv'
                elif mutation=='runtime':d['runtime']['numpy']='2.5.4'
                else:d['case_id']='must-not-publish'
                write(root/'source.json',d)
                with self.assertRaises(ValueError):self.publish(root)
                self.assertFalse((root/'public').exists())

if __name__=='__main__':unittest.main()
