"""Local HTTP contract: immutable question exports and snapshot-bound review state."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from biograph_steward.webapp import create_server


class QuestionHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.server=create_server(0,self.root)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.source=self.post('/api/build',{'mode':'demo'})

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def post(self,path,body):
        with urlopen(Request(self.url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})) as r:
            return json.loads(r.read())

    def query(self,**kw):
        return self.post('/api/question',{'run_id':self.source['run_id'],'protein':'demo:protein:DEMO_PROTEIN_001',**kw})

    def test_saved_answer_reopens_and_downloads_without_mutating_source(self):
        source=self.root/self.source['run_id'];before={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
        result=self.query(view='candidates')
        self.assertTrue(result['answer']['results']);self.assertEqual(result['answer']['data_kind'],'synthetic_demo')
        with urlopen(self.url+'/api/question/'+result['question_id']) as r:self.assertEqual(json.loads(r.read()),result)
        with urlopen(self.url+'/api/download/'+result['question_id']) as r:
            archive=ZipFile(BytesIO(r.read()));names={Path(name).name for name in archive.namelist()}
            self.assertTrue({'question.json','summary.txt','report.html','paths.tsv'}<=names)
        self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir() if p.is_file()})

    def test_accepted_path_after_review_has_a_new_basis_and_old_answer_stays_unchanged(self):
        old=self.query(view='candidates');path=old['answer']['results'][0]['paths'][0]
        empty=self.query();self.assertEqual(empty['answer']['returned_proteins'],0)
        run_id=self.source['run_id']
        for aid in path['assertion_ids']:
            reviewed=self.post('/api/review',{'run_id':run_id,'assertion_id':aid,'state':'accepted',
                                              'reviewer':'Synthetic HTTP QA','reason':'Invented workflow fixture only'})
            run_id=reviewed['run_id']
        new=self.query(run_id=run_id)
        self.assertGreater(new['answer']['returned_proteins'],0)
        self.assertTrue(all(c['review_state']=='accepted' for c in new['answer']['citations']))
        self.assertNotEqual(old['answer']['graph_basis_sha256'],new['answer']['graph_basis_sha256'])
        self.assertEqual(old['answer']['snapshot_sha256'],new['answer']['snapshot_sha256'])
        with urlopen(self.url+'/api/question/'+old['question_id']) as r:self.assertEqual(json.loads(r.read()),old)

    def test_invalid_or_unsupported_scopes_are_rejected(self):
        for changes in [{'run_id':'../outside'},{'protein':'missing'},{'relations':['resistance']},
                        {'view':'all'},{'max_results':False},{'question_text':'Which therapy should I choose?'}]:
            with self.assertRaises(HTTPError) as ctx:self.query(**changes)
            self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError) as ctx:urlopen(self.url+'/api/question/../../etc/passwd')
        self.assertEqual(ctx.exception.code,404)

    def test_tampered_saved_question_is_rejected(self):
        result=self.query(view='candidates');path=self.root/result['question_id']/'question.json'
        answer=json.loads(path.read_text());answer['overview']='tampered';path.write_text(json.dumps(answer))
        with self.assertRaises(HTTPError) as ctx:urlopen(self.url+'/api/question/'+result['question_id'])
        self.assertEqual(ctx.exception.code,400)

if __name__=='__main__':unittest.main()
