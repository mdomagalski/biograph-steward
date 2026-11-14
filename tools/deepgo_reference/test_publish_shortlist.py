"""Invented aggregate-only fixed-budget publication checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from .publish_shortlist import prepare, FRAMES, ASPECTS, METHODS


def write(path,value):write_json(path,{**value,'content_sha256':digest(value)})


class Publication(unittest.TestCase):
    def fixture(self,root):
        runtime={'python':'3.10.12','numpy':'1.26.4','scipy':'1.13.1','pandas':'2.2.3'}
        den={'eligible_proteins':2,'IA_eligible_proteins':2}
        freeze={'format':'biograph-steward.deepgo-shortlist.v1.freeze','k':3,
            'focus_namespace':'molecular_function','previous_reference_and_metric_exposure':True,
            'no_new_shortlist_endpoint_values_seen':True,'runtime':runtime,
            'input_files_sha256':{'/data/private/forecast.gz':'b'*64},
            'frames':{f:{'denominators':{a:den for a in ASPECTS}}for f in FRAMES}}
        write(root/'freeze.json',freeze)
        rows=[]
        for f in FRAMES:
            for a in ASPECTS:
                for m in METHODS:
                    tp=(2 if m=='deepgose' else 1) if a=='molecular_function' else (1 if m=='deepgose' else 2)
                    normal={'eligible_proteins':2,'TP':tp,'reference_unmatched_predictions':4-tp,
                        'returned_candidates':4,'unused_budget_slots':2,
                        'curator_supported_slots_per_fixed3_budget':tp/6,'PPV_among_returned':tp/4,
                        'micro_recall':tp/4,'filled_slot_fraction':2/3,'prediction_coverage':1.,
                        'shortlists_with_ancestor_related_pair':1,'ancestor_related_pairs':1,
                        'mean_IA_per_returned_term':2.,'curator_supported_IA_per_fixed3_budget':1.,
                        'shortlist_is_ancestor_closed':False}
                    checks={k:{'passed':True,'columns':['n','tp','fp','fn','pr','rc'],
                        'eligible_proteins':2,'relative_tolerance':1e-12,'absolute_tolerance':1e-12,
                        'same_native_function_same_post_known_eligible_frame':True}for k in ('ordinary','IA_weighted')}
                    rows.append({'frame':f,'namespace':a,'method':m,'k':3,'ordinary':normal,
                        'IA_weighted':{'eligible_proteins':2,'PPV_among_returned':.5,'micro_recall':.5},
                        'native_batch_point_agreement':checks,'native_reference_protein_order_sha256':'c'*64})
        pairs=[]
        for f in FRAMES:
            for a in ASPECTS:
                delta=1/6 if a=='molecular_function' else -1/6
                pairs.append({'frame':f,'namespace':a,'candidate':'deepgose','comparator':'strict_alias_localplus',
                    'metric':'curator_supported_slots_per_fixed3_budget','role':'designated_focus'if a=='molecular_function'else'secondary',
                    'eligible_proteins':2,'point_difference':delta,'paired_95_percentile_interval':[delta-.05,delta+.05]})
        result={'format':'biograph-steward.deepgo-shortlist.v1.results','k':3,'freeze_file_sha256':sha(root/'freeze.json'),
            'runtime':runtime,'source_files_sha256':freeze['input_files_sha256'],
            'numeric_artifact_files_sha256':{'/data/private/counts.npz':'d'*64},'rows':rows,'paired_comparisons':pairs,
            'primary_BPO_adoption_rule_changed':False,'app_default_or_consumer_changed':False,
            'raw_reference_or_forecast_rows_included':False,
            'uncertainty':{'implementation':'scipy.stats.bootstrap','version':'1.13.1','paired':True,
                'draws':2000,'seed':20261113,'method':'percentile','confidence_level':.95,'batch':100,'multiplicity_adjusted':False},
            'limitations':['INVENTED; not scientific results.']}
        write(root/'source.json',result);return result

    def publish(self,root):return prepare(root/'source.json',sha(root/'source.json'),root/'freeze.json',sha(root/'freeze.json'),root/'public')

    def test_all_profiles_positive_and_negative_pairs_budget_and_privacy_preserved(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);source=self.fixture(root);result=self.publish(root)
            self.assertEqual(result['results']['rows'],source['rows'])
            self.assertEqual(result['results']['paired_comparisons'],source['paired_comparisons'])
            self.assertEqual(len(result['results']['rows']),12)
            self.assertEqual(len(result['results']['paired_comparisons']),6)
            self.assertNotIn('/data/',(root/'public/report.json').read_text())
            html=(root/'public/report.html').read_text()
            for term in ('DEVELOPMENT','Supported slots','PPV among returned','BPO','MFO','CCO','ancestor'):
                self.assertIn(term,html)
            self.assertFalse(result['app_default_or_consumer_changed'])
            self.assertEqual(len(list((root/'public').iterdir())),3)

    def test_bad_budget_dropped_negative_wrong_paired_point_or_raw_case_fail_closed(self):
        for mutation in ('budget','drop','point','population','row_budget','case'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);d=self.fixture(root);d.pop('content_sha256',None)
                if mutation=='budget':d['rows'][0]['ordinary']['curator_supported_slots_per_fixed3_budget']=.9
                elif mutation=='drop':d['paired_comparisons'].pop()
                elif mutation=='point':d['paired_comparisons'][0]['point_difference']=.8
                elif mutation=='population':d['paired_comparisons'][0]['eligible_proteins']=3
                elif mutation=='row_budget':d['rows'][0]['k']=10
                else:d['case_id']='must-not-publish'
                write(root/'source.json',d)
                with self.assertRaises(ValueError):self.publish(root)
                self.assertFalse((root/'public').exists())


if __name__=='__main__':unittest.main()
