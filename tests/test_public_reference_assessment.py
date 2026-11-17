"""Actual published aggregate replay and unsafe scientific-claim rejection.

These are presentation/integrity checks, not a new biological evaluation.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward import public_reference_assessment as reference
from biograph_steward import scientific_assessment as assessment
from biograph_steward.file_utils import sha
from biograph_steward.webapp import create_server
from test_scientific_assessment import fixtures
from test_scientific_assessment_ui import NODE, JS, HARNESS

REPORT = Path(__file__).resolve().parents[1] / 'docs/evaluations/public_gold_20261115/summary.json'
OPENCELL = REPORT.parents[1] / 'opencell_localization_20261115/summary.json'


class PublicReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.paths, self.pins = fixtures(self.root/'base')
        self.value = json.loads(REPORT.read_bytes())

    def project(self, value=None):
        raw = json.dumps(value if value is not None else self.value).encode()
        return reference.summary(raw, hashlib.sha256(raw).hexdigest())

    def publish(self):
        out = self.root/'publication'
        assessment.publish(self.paths, out, expected_source_pins=self.pins,
            public_reference_report=REPORT, expected_public_reference_pin=sha(REPORT))
        return out

    def test_actual_public_report_preserves_recovery_unknowns_and_all_panels(self):
        s = self.project()
        self.assertEqual(len(s['localization']['rows']), 15)
        self.assertEqual(len(s['ppi']['rows']), 6)
        self.assertIsNone(s['whole_graph_biological_accuracy'])
        self.assertEqual(s['localization']['matched_proteins'], 31)
        self.assertEqual(s['localization']['reference_unknown_proteins'], 68)
        self.assertEqual(s['clinical']['whole_assertion_scientific_labels_unknown'], 41)
        self.assertTrue(any(r['arms']['physical']['AUROC'] is None for r in s['ppi']['rows']))

    def test_recovery_cannot_be_relabelled_precision_or_discard_unknowns(self):
        for mutation in (
            lambda v: v['localization']['metrics']['B_native_location_scope_qualified']['level1'].update(precision=1.),
            lambda v: v['localization'].update(unmatched_primary_reference_unknown=0),
            lambda v: v['localization']['metrics']['B_native_location_scope_qualified']['level1'].update(recovered_reference_positive_labels=52),
            lambda v: v.update(whole_graph_biological_accuracy=.9),
            lambda v: v['clinical'].update(whole_assertion_scientific_labels_unknown=39),
        ):
            changed=deepcopy(self.value); mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.project(changed)

    def test_reference_panels_cannot_be_dropped_or_undefined_auc_filled(self):
        for mutation in (
            lambda v: v['same_release_ppi']['panels'].pop('manual_assay_historical_pruning_3172'),
            lambda v: v['same_release_ppi']['panels']['canonical_current_workspace_218']['paired_both_native_weights']['arms']['physical'].update(AUROC=0),
            lambda v: v['same_release_ppi']['panels']['canonical_current_workspace_218'].update(graph_improvement_established=True),
        ):
            changed=deepcopy(self.value); mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.project(changed)

    def test_public_source_rejects_raw_cases_and_paths(self):
        for key, value in [('case_id','private-case'),('operator','/Users/private/reference.json')]:
            changed=deepcopy(self.value);changed[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):self.project(changed)

    def test_source_pin_mismatch_rejected_before_creating_publication(self):
        with self.assertRaises(ValueError):
            assessment.publish(self.paths,self.root/'rejected',expected_source_pins=self.pins,
                public_reference_report=REPORT,expected_public_reference_pin='0'*64)
        self.assertFalse((self.root/'rejected').exists())

    def test_opencell_appendix_keeps_all_profiles_and_source_separation_limits(self):
        raw=OPENCELL.read_bytes();value=json.loads(raw)
        projected=reference.opencell_summary(raw,sha(OPENCELL))
        self.assertEqual(len(projected['profiles']),2)
        self.assertEqual(projected['identity']['reciprocal_accession_and_HGNC_ENSG_matches'],23)
        for mutate in (
            lambda v:v.update(fresh_blind_reference=True),
            lambda v:v['profiles'][0]['arms'].pop('C_native_experimental_scope_qualified'),
            lambda v:v['profiles'][0]['arms']['D_native_without_HPA_or_explicit_OpenCell'].update(precision=1.),
        ):
            changed=deepcopy(value);mutate(changed);altered=json.dumps(changed).encode()
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                reference.opencell_summary(altered,hashlib.sha256(altered).hexdigest())
        out=self.root/'with_opencell'
        assessment.publish(self.paths,out,expected_source_pins=self.pins,
            public_reference_report=REPORT,expected_public_reference_pin=sha(REPORT),
            opencell_report=OPENCELL,expected_opencell_pin=sha(OPENCELL))
        _,s,files=assessment.load_publication(out)
        self.assertEqual(files[reference.OPENCELL_FILE],raw)
        self.assertFalse(s['opencell_localization']['fresh_blind_reference'])
        self.assertIn('31/40',files['report.html'].decode())

    def test_v5_publication_replays_exact_source_and_safe_html(self):
        out=self.publish();m,s,files=assessment.load_publication(out)
        self.assertEqual(m['format'],assessment.FORMAT_V5)
        self.assertEqual(files[reference.FILE],REPORT.read_bytes())
        self.assertIn('41/51',files['report.html'].decode())
        self.assertIn('44/51',files['report.html'].decode())
        self.assertIn('HPA',files['report.html'].decode())
        self.assertIsNone(s['whole_graph_scientific_precision'])
        self.assertEqual(assessment.list_publications(self.root)['assessments'][0]['id'],'publication')
        (out/reference.FILE).write_bytes(b'{}')
        with self.assertRaises(ValueError):assessment.load_publication(out)

    @unittest.skipUnless(Path(NODE).is_file(), 'Node runtime unavailable')
    def test_actual_ui_renderer_displays_denominators_and_literal_text(self):
        out=self.publish();_,s,_=assessment.load_publication(out)
        s['public_reference']['title']='<img src=x onerror=alert(1)>'
        process=subprocess.run([NODE,'-e',HARNESS,str(JS)],input=json.dumps({
            'summary':s,'options':{'publicationId':'publication'}}),text=True,capture_output=True,check=True)
        result=json.loads(process.stdout);self.assertIsNone(result['error'])
        text=' '.join(result['text'])
        for phrase in ['41/51','44/51','68 have no matching','HPA','unassessed','co-complex','Undefined']:
            if phrase=='Undefined':
                self.assertIn('Unavailable',text)
            else:self.assertIn(phrase,text)
        self.assertNotIn('img',result['tags'])
        self.assertIn('<img src=x onerror=alert(1)>',result['text'])
        self.assertTrue(any(x.get('href')=='/api/scientific-assessment/publication/files/sources/public_reference.json'
                            for x in result['links']))

    def test_authenticated_http_report_and_exact_aggregate_download(self):
        out=self.publish();server=create_server(0,self.root,access_token='invented-public-reference-token')
        server.RequestHandlerClass.log_message=lambda *args:None
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            opener=build_opener(ProxyHandler({}));base='http://127.0.0.1:'+str(server.server_port)
            for path,expected in [('report',None),('files/sources/public_reference.json',REPORT.read_bytes())]:
                url=base+'/api/scientific-assessment/publication/'+path
                with self.assertRaises(HTTPError) as caught:opener.open(url)
                self.assertEqual(caught.exception.code,401);caught.exception.close()
                with opener.open(Request(url,headers={'Authorization':'Bearer invented-public-reference-token'})) as response:
                    raw=response.read();self.assertEqual(response.status,200)
                    if expected is not None:self.assertEqual(raw,expected)
                    else:self.assertIn(b'44/51',raw)
            self.assertEqual((out/reference.FILE).read_bytes(),REPORT.read_bytes())
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
