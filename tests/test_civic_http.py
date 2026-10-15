"""Local HTTP integration, with invented read-only upstream responses."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from biograph_steward.civic import CivicClient
from biograph_steward.graph import save_run
from biograph_steward.webapp import create_server
from test_civic import fixture, CivicAPI


class CivicHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.snapshot,self.civic=fixture();save_run(self.snapshot,self.root/'source')
        self.server=create_server(0,self.root);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def post(self,path,body):
        with urlopen(Request(self.url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})) as r:return json.loads(r.read())

    def enrich(self):
        with patch('biograph_steward.civic.CivicClient',return_value=CivicClient(transport=CivicAPI())):
            return self.post('/api/civic',{'run_id':'source'})

    def test_retrieve_question_citation_download_reopen_and_review(self):
        before=(self.root/'source'/'snapshot.json').read_bytes();result=self.enrich();rid=result['run_id']
        self.assertEqual(result['graph']['civic']['normalized_items'],4)
        self.assertEqual((self.root/rid/'snapshot.json').read_bytes(),before)
        empty=self.post('/api/therapy-question',{'run_id':rid});self.assertFalse(empty['answer']['results'])
        answer=self.post('/api/therapy-question',{'run_id':rid,'view':'candidates'})
        self.assertTrue(answer['answer']['citations'])
        with urlopen(self.url+'/api/question/'+answer['question_id']) as r:self.assertEqual(json.loads(r.read()),answer)
        with urlopen(self.url+'/api/download/'+answer['question_id']) as r:
            names={Path(n).name for n in ZipFile(BytesIO(r.read())).namelist()}
        self.assertTrue({'question.json','summary.txt','paths.tsv','report.html'}<=names)
        citation=answer['answer']['citations'][0]
        review=self.post('/api/review',{'run_id':rid,'assertion_id':citation['assertion_id'],'state':'accepted',
                                       'reviewer':'Software test','reason':'Invented test fixture only'})
        new=self.post('/api/therapy-question',{'run_id':review['run_id']})
        self.assertEqual(new['answer']['availability']['accepted_assertions'],1)
        self.assertNotEqual(new['answer']['graph_basis_sha256'],answer['answer']['graph_basis_sha256'])
        self.assertTrue((self.root/review['run_id']/'civic_snapshot.json').exists())

    def test_unsupported_scopes_and_repeat_enrichment_are_rejected(self):
        for body in [{'run_id':'../outside'},{'run_id':'source','gene':'NRAS'},{'run_id':'source','max_items':False}]:
            with self.assertRaises(HTTPError) as ctx:self.post('/api/civic',body)
            self.assertEqual(ctx.exception.code,400)
        result=self.enrich();rid=result['run_id']
        for path,body in [('/api/civic',{'run_id':rid}),('/api/therapy-question',{'run_id':rid,'question':'treat patient'}),
                          ('/api/therapy-question',{'run_id':rid,'profile':'G13D'}),('/api/therapy-question',{'run_id':'source'})]:
            with self.assertRaises(HTTPError) as ctx:self.post(path,body)
            self.assertEqual(ctx.exception.code,400)

    def test_source_graph_response_contains_both_provenance_hashes_and_ui(self):
        result=self.enrich()
        with urlopen(self.url+'/api/run/'+result['run_id']) as r:g=json.loads(r.read())['graph']
        self.assertEqual(g['snapshot_sha256'],self.snapshot['content_sha256']);self.assertTrue(g['civic_snapshot_sha256'])
        with urlopen(self.url+'/') as r:html=r.read().decode()
        self.assertIn('id="civicQuestion"',html);self.assertIn('function bindCivicAnswer',html)
        self.assertNotIn('__GUIDED_SCRIPT__',html)


if __name__=='__main__':unittest.main()
