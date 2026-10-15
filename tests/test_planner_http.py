"""Local planner/report transport, using only invented model and source data."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from biograph_steward.graph import save_run
from biograph_steward.webapp import create_server
from biograph_steward.evaluation import freeze_suite,run_evaluation
from biograph_steward.planning import ModelPlanner
from test_civic import fixture
from test_planning import response,civic_plan
from test_evaluation import cases


class PlannerHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        p,c=fixture();save_run(p,self.root/'base');save_run(p,self.root/'enriched',civic_snapshot=c)
        self.server=create_server(0,self.root);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def post(self,path,body):
        with urlopen(Request(self.url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})) as r:return json.loads(r.read())

    def test_unconfigured_model_is_explicit_and_no_case_is_silently_graded(self):
        with patch.dict('os.environ',{},clear=True):
            with urlopen(self.url+'/api/planner') as r:status=json.loads(r.read())
            self.assertFalse(status['configured'])
            with self.assertRaises(HTTPError) as ctx:self.post('/api/plan',{'run_id':'enriched','question':'Question'})
            self.assertEqual(ctx.exception.code,400)

    def test_one_planner_call_exports_trace_and_bound_citations_without_source_changes(self):
        original=(self.root/'enriched'/'snapshot.json').read_bytes()
        model=ModelPlanner(model='test',endpoint='http://localhost:9999',transport=lambda p:response(civic_plan()))
        with patch('biograph_steward.planning.ModelPlanner',return_value=model):
            result=self.post('/api/plan',{'run_id':'enriched','question':'Inspect candidate evidence.'})
        self.assertEqual(result['trace']['model_calls'],1);self.assertEqual(result['tool_calls'],1)
        self.assertTrue(result['answer']['citations'])
        self.assertTrue((self.root/result['plan_id']/'planner_trace.json').exists())
        self.assertEqual((self.root/'enriched'/'snapshot.json').read_bytes(),original)
        for body in [{'run_id':'../outside','question':'q'},{'run_id':'enriched','question':'q','command':'edit'}]:
            with self.assertRaises(HTTPError):self.post('/api/plan',body)

    def test_report_and_reviewer_download_routes_are_bounded(self):
        freeze_suite(self.root/'base',self.root/'enriched',self.root/'suite',cases=cases())
        run_evaluation(self.root/'suite',self.root/'results')
        with urlopen(self.url+'/api/evaluation/results/') as r:
            html=r.read().decode();self.assertIn('scientific improvement has not been established',html)
        with urlopen(self.url+'/api/evaluation/results/evidence_reviews.tsv') as r:
            self.assertIn('attachment',r.headers['Content-Disposition']);self.assertIn('unit_sha256',r.read().decode())
        with self.assertRaises(HTTPError):urlopen(self.url+'/api/evaluation/results/snapshot.json')
        with self.assertRaises(HTTPError):urlopen(self.url+'/api/evaluation/../../etc/passwd')


if __name__=='__main__':unittest.main()
