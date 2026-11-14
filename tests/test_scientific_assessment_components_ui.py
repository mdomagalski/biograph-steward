"""Render verified invented task capsules without pooling source scopes."""
from collections import Counter
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from biograph_steward import scientific_assessment as module
from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from test_scientific_assessment import fixtures, sealed
from test_scientific_assessment_components import function_source, biored_sources
from test_scientific_assessment_ui import NODE, JS, HARNESS

HARNESS = HARNESS.replace('const nodes=[];', '''
function expand(n){
 if(n.tag==='details' && (input.expand||[]).includes(n.children[0]?.textContent)){
   n.open=true;n.ontoggle?.();n.ontoggle?.();
 }
 for(const c of n.children)expand(c);
}
expand(container);
const nodes=[];
''')


@unittest.skipUnless(Path(NODE).is_file(), 'Node runtime unavailable')
class ScientificTaskUITests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve(); paths, pins = fixtures(root/'base')
        function = function_source()
        for method, score in [('localplus', .1), ('strict_alias_localplus', .2)]:
            row = next(r for r in function['rows'] if r['frame']=='primary'
                and r['setting']=='partial' and r['namespace']=='biological_process' and r['method']==method)
            row.update({k:v for k,v in function['rows'][0].items()
                if k not in {'frame','setting','namespace','method'}})
            row.update(micro_Fmax=score, IA_micro_Fmax=score, macro_Fmax=.04,
                fixed_0_5={'threshold':.5,'namespace':row['namespace'],
                    'status':'unchanged author curve at predeclared threshold','PPV':.3,'recall':.02,'F1':.0375,'coverage':.2})
        function['status_counts'] = dict(Counter(r['status'] for r in function['rows']))
        function['paired_comparisons'] = [{'frame':'primary','setting':'partial','namespace':'biological_process',
            'candidate':'strict_alias_localplus','comparator':'localplus','readout':'ordinary',
            'difference_mean':.9,'source_report_sha256':'d'*64,'paired_95_percentile_interval':[.01,.2]}]
        source=root/'function_source.json'; write_json(source,sealed(function)); function_path=root/'function.json'
        module.prepare_function_recovery_aggregate(source,function_path,expected_report_pin=sha(source))
        bio_paths={}
        for role,value in biored_sources().items():
            bio_paths[role]=root/(role+'.json');write_json(bio_paths[role],value)
        bio=root/'biored.json';module.prepare_biored_aggregate(bio_paths,bio,
            expected_report_pins={k:sha(v) for k,v in bio_paths.items()})
        out=root/'publication';module.publish(paths,out,expected_source_pins=pins,
            function_recovery_report=function_path,expected_function_recovery_pin=sha(function_path),
            biored_report=bio,expected_biored_pin=sha(bio))
        _,self.summary,_=module.load_publication(out)

    def render(self, *expand):
        completed=subprocess.run([NODE,'-e',HARNESS,str(JS)],input=json.dumps({
            'summary':self.summary,'options':{'publicationId':'invented_tasks'},'expand':expand}),
            text=True,capture_output=True,check=True)
        return json.loads(completed.stdout)

    def test_tasks_display_all_arms_and_negative_adoption_without_pooling_legacy_graph(self):
        result=self.render();self.assertIsNone(result['error'])
        text=' '.join(result['text'])
        self.assertIn('0.100000 → 0.200000',text)
        self.assertIn('Negative original primary retained.',text)
        self.assertIn('not a calibrated confidence',text)
        self.assertIn('IA macro',text);self.assertIn('Fixed 0.5 F1',text)
        self.assertIn('kept out of the default decision path',text)
        self.assertIn('Nano · flat context',text);self.assertIn('Nano · bounded tool agent',text)
        self.assertIn('Always no reported relation',text)
        self.assertNotIn('Native Wiki history',text)  # older workspace is separately collapsed
        self.assertTrue(any(x.get('href')=='/api/scientific-assessment/invented_tasks/files/sources/function_recovery.json'
                            for x in result['links']))

    def test_uncertainty_uses_native_observed_difference_and_retains_all_pending_slots(self):
        result=self.render('All paired uncertainty comparisons',
            'Every declared outcome · 240 cohort/setting/method/aspect slots')
        self.assertIsNone(result['error']);text=' '.join(result['text'])
        self.assertIn('0.100000',text);self.assertNotIn('0.900000',text)
        self.assertIn('0.010000 to 0.200000',text)
        self.assertIn('pending',text);self.assertIn('Unavailable',text)
        # A repeated toggle must not append the entire outcome table twice.
        self.assertEqual(result['text'].count('Every declared outcome · 240 cohort/setting/method/aspect slots'),1)

    def test_fixed_operating_points_preserve_missingness_and_native_denominator_caveat(self):
        result=self.render('Fixed 0.5 operating-point trade-offs',
            'Additional-cohort transfer and exact reference denominators')
        self.assertIsNone(result['error']);text=' '.join(result['text'])
        self.assertIn('0.300000',text);self.assertIn('0.020000',text)
        self.assertIn('Unavailable',text);self.assertIn('Author-recognized IDs',text)
        self.assertIn('ratio above one is preserved',text)

    def test_unreported_costs_stay_unknown_and_reference_scopes_remain_separate(self):
        result=self.render('Agent contrasts, tool use and model costs',
            'Complete gene-involving specialist assessment · separate denominator',
            'Released artifact consistency · all native task rows')
        self.assertIsNone(result['error']);text=' '.join(result['text'])
        self.assertIn('Unreported',text);self.assertIn('one request',text)
        self.assertIn('candidate pairs from 1 publications',text)
        self.assertIn('single released checkpoint',text)
        self.assertNotIn('NaN',text)

    def test_literal_text_and_explicit_legacy_expansion_preserve_scope(self):
        self.summary['function_recovery']['title']='<img src=x onerror=alert(1)>'
        result=self.render('99-target source workspace and earlier component assessments')
        self.assertIsNone(result['error']);self.assertNotIn('img',result['tags'])
        self.assertIn('<img src=x onerror=alert(1)>',result['text'])
        self.assertIn('Native Wiki history',result['text'])


if __name__=='__main__':unittest.main()
