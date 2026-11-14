"""Invented aggregate fixtures only; no source/reference cases or predictions."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from .run import write,read,sha,digest
from .publish import prepare


class PublicationBoundary(unittest.TestCase):
    def fixture(self,root,raw_case=False):
        rows=[]
        for frame in ('primary','reserved'):
            for ns in ('biological_process','molecular_function','cellular_component'):
                rows.append({'frame':frame,'setting':'partial','namespace':ns,'method':'strict_alias_localplus',
                    'status':'scored','eligible_proteins':2,'micro_Fmax':.2,'IA_micro_Fmax':.1,
                    'macro_Fmax':.3,'IA_macro_Fmax':.2,'source':'/home/operator/native.tsv',
                    'fixed_0_5':{'namespace':ns,'threshold':.5,'status':'author omits thresholds with zero prediction coverage',
                                  'PPV':None,'recall':None,'F1':None}})
        prior=deepcopy(rows)+[dict(deepcopy(rows[0]),method='synthetic_control_'+str(i))for i in range(234)]
        old={'rows':prior,'native_aggregate_source_files_sha256':{'/home/operator/native.tsv':'a'*64}}
        old['content_sha256']=digest(old);write(root/'old.json',old)
        new=deepcopy(rows)
        for row in new:
            row.pop('source');row['source_curve_sha256']='b'*64;row['method']='combined_strict_genemaniaplus';row['micro_Fmax']=.25
        original={'new_outcome_rows':new,'earlier_240_outcome_rows':prior,
            'earlier_240_report_file_sha256':sha(root/'old.json'),'earlier_240_report_content_sha256':old['content_sha256'],
            'denominators':[],'paired_comparisons':[],
            'predeclared_development_retention_gate':{'passed':False,'rule':'INVENTED FIXTURE'},
            'scope':'INVENTED AGGREGATE FIXTURE','source':{'nodes':2},'oldGM_reserved':{'status':'unsupported'},
            'caveats':['INVENTED, not scientific measurements.'],
            'input_files_sha256':{'/home/operator/native.tsv':'a'*64},
            'operator_metadata':{'file':'/Users/operator/source.json','sha256':'c'*64}}
        if raw_case:original['case_id']='SHOULD NEVER BE PUBLISHED'
        original['content_sha256']=digest(original);write(root/'source.json',original)
        return new

    def test_paths_removed_numbers_nulls_and_complete_inventory_preserved(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);new=self.fixture(root)
            prepare(root/'source.json',root/'old.json',sha(root/'source.json'),root/'public')
            summary=read(root/'public/summary.json');prior=read(root/'public/prior_240_outcomes.json')
            self.assertEqual(summary['new_outcome_rows'],new)
            self.assertEqual(len(prior['rows']),240)
            self.assertEqual(len(summary['matched_profile_metric_changes']),6)
            self.assertIsNone(summary['new_outcome_rows'][0]['fixed_0_5']['PPV'])
            self.assertEqual(summary['earlier_240_inventory']['file_sha256'],sha(root/'public/prior_240_outcomes.json'))
            text=(root/'public/report.json').read_text()
            self.assertNotIn('/home/',text);self.assertNotIn('/Users/',text)

    def test_raw_case_field_rejected_before_publication(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);self.fixture(root,raw_case=True)
            with self.assertRaises(ValueError):
                prepare(root/'source.json',root/'old.json',sha(root/'source.json'),root/'public')
            self.assertFalse((root/'public').exists())


if __name__=='__main__':unittest.main()
