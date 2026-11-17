"""Saved-data mode gates side effects before any source or model factory."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
from zipfile import ZipFile

from biograph_steward.__main__ import main
from biograph_steward.client import digest
from biograph_steward.evidence_extension import publish_extension
from biograph_steward.graph import save_run
from biograph_steward.questions import answer_question, save_answer
from biograph_steward.runtime import AccessPolicy, SAVED_REVIEW_POSTS
from biograph_steward.webapp import create_server, report_html
from test_physical_ranking_http import snapshot_fixture, collect_fixture_packet
from test_string_physical_source import source_fixture
from biograph_steward import string_physical_source

TOKEN='invented-saved-review-mode-token'


class SavedReviewPolicyTests(unittest.TestCase):
    def test_mode_is_explicit_operator_boolean_and_matches_existing_gateway_saved_routes(self):
        policy=AccessPolicy(saved_data_only=True)
        nginx=Path('deploy/aws/reviewer_gateway/nginx.conf.in').read_text()
        self.assertEqual(SAVED_REVIEW_POSTS, frozenset(re.findall(r'"POST:([^" ]+)" 1;',nginx)))
        self.assertFalse(policy.allows_action('GET','/api/planner'))
        self.assertFalse(policy.allows_action('POST','/api/build',{}))
        self.assertTrue(policy.allows_action('POST','/api/question',{}))
        self.assertTrue(policy.allows_action('POST','/api/question',{'template':'native_string_physical.v1'}))
        for ranking in ('physical',None,False,['physical']):
            self.assertFalse(policy.allows_action('POST','/api/question',{'ranking':ranking}))
        self.assertTrue(AccessPolicy().allows_action('POST','/api/build',{}))
        for value in ('false',1,None):
            with self.assertRaises(ValueError): AccessPolicy(saved_data_only=value)

    def test_CLI_flag_reaches_server_and_default_local_behavior_is_preserved(self):
        with patch.dict(os.environ,{},clear=True), patch('biograph_steward.webapp.serve') as serve:
            self.assertEqual(main(['serve','--saved-data-only','--no-browser']),0)
            self.assertTrue(serve.call_args.kwargs['saved_data_only'])
            self.assertEqual(main(['serve','--no-browser']),0)
            self.assertFalse(serve.call_args.kwargs['saved_data_only'])

    def test_capability_bootstrap_does_not_mutate_or_relabel_saved_graph(self):
        graph={'invented':'source graph bytes'};before=digest(graph)
        html=report_html(graph,saved_data_only=True)
        self.assertIn('const appCapabilities=Object.freeze({"saved_data_only": true',html)
        self.assertIn('"live_physical_ranking": false',html)
        self.assertEqual(digest(graph),before)
        self.assertIn('"saved_data_only": false',report_html(graph))


class SavedReviewHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.run=self.root/'saved';self.snapshot=snapshot_fixture()
        self.graph=save_run(self.snapshot,self.run)
        self.before={p.relative_to(self.run).as_posix():p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        self.server=create_server(0,self.root,access_token=TOKEN,saved_data_only=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port);self.opener=build_opener(ProxyHandler({}))
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def request(self,path,body=None,*,headers=None):
        h={'Authorization':'Bearer '+TOKEN,**(headers or {})}
        if body is not None:h['Content-Type']='application/json'
        return self.opener.open(Request(self.url+path,json.dumps(body).encode() if body is not None else None,h))

    def denied(self,path,body=None,**kwargs):
        with self.assertRaises(HTTPError) as error:self.request(path,body,**kwargs)
        self.assertEqual(error.exception.code,403)
        payload=json.loads(error.exception.read());error.exception.close()
        self.assertEqual(payload['error_code'],'saved_data_only')

    def test_forbidden_actions_and_live_ranking_stop_before_any_factory_or_source_read(self):
        with ExitStack() as stack:
            factories=[stack.enter_context(patch(name,side_effect=AssertionError('Forbidden factory invoked'))) for name in
                ('biograph_steward.webapp.PharosClient','biograph_steward.planning.configured_planner',
                 'biograph_steward.physical_ranking.collect_ranking','biograph_steward.reviews.read_run')]
            for path in ('/api/build','/api/construct','/api/search','/api/plan','/api/civic','/api/review','/api/refresh-compare','/api/submission-export'):
                self.denied(path,{})
            self.denied('/api/planner')
            for extra in ({},{'Host':'localhost','X-BioGraph-Saved-Data-Only':'0','X-Forwarded-Host':'localhost'}):
                self.denied('/api/question',{'run_id':'saved','protein':'P04637','view':'candidates','ranking':'physical'},headers=extra)
            for factory in factories:factory.assert_not_called()

    def test_saved_question_reopen_and_download_still_work_with_source_bytes_unchanged(self):
        body={'run_id':'saved','protein':'P04637','view':'candidates','relations':['interactions']}
        with patch('biograph_steward.physical_ranking.collect_ranking',side_effect=AssertionError('No live ranking')) as collector:
            with self.request('/api/question',body) as r:result=json.loads(r.read())
            self.assertTrue(result['answer']['citations'])
            with self.request('/api/question/'+result['question_id']) as r:self.assertEqual(json.loads(r.read()),result)
            with self.request('/api/download/'+result['question_id']) as r:
                with ZipFile(io.BytesIO(r.read())) as z:self.assertIn('question.json',{Path(n).name for n in z.namelist()})
            collector.assert_not_called()
        self.assertEqual(self.before,{p.relative_to(self.run).as_posix():p.read_bytes() for p in self.run.rglob('*') if p.is_file()})

    def test_previously_saved_physical_packet_replays_without_retrieval(self):
        base=answer_question(self.graph,'P04637',view='candidates',relations=['interactions'],max_results=30)
        from biograph_steward.physical_ranking import collect_ranking
        packet=collect_fixture_packet(self.graph,'UniProtKB:P04637',base['results'],collector=collect_ranking)
        answer=answer_question(self.graph,'P04637',view='candidates',relations=['interactions'],max_results=30,
            ranking='physical',ranking_source=packet,source_run='saved')
        save_answer(answer,self.root/'previous_physical')
        with patch('biograph_steward.physical_ranking.collect_ranking',side_effect=AssertionError('Replay must not fetch')):
            with self.request('/api/question/previous_physical') as r:self.assertEqual(json.loads(r.read())['answer'],answer)

    def test_native_physical_question_remains_offline_and_candidate_states_are_preserved(self):
        sources=source_fixture(self.root/'bulk',self.snapshot);pub=self.root/'publication'
        string_physical_source.publish_sources(self.snapshot,sources,pub)
        publish_extension(self.run,{'string_physical':pub},self.root/'native')
        with patch('biograph_steward.physical_ranking.collect_ranking',side_effect=AssertionError('No live ranking')):
            with self.request('/api/question',{'run_id':'native','protein':'P04637','template':'native_string_physical.v1','view':'candidates'}) as r:
                answer=json.loads(r.read())['answer']
            self.assertTrue(answer['citations']);self.assertTrue(all(c['review_state']=='candidate' for c in answer['citations']))
            with self.request('/api/question',{'run_id':'native','protein':'P04637','template':'native_string_physical.v1','view':'accepted'}) as r:
                accepted=json.loads(r.read())['answer']
            self.assertEqual(accepted['returned_proteins'],0)

    def test_health_reports_operator_mode_and_UI_bootstrap_exposes_no_source_capability(self):
        with self.request('/healthz') as r:self.assertTrue(json.loads(r.read())['saved_data_only'])
        with self.request('/') as r:html=r.read().decode()
        self.assertIn('"saved_data_only": true',html)
        self.assertIn('"model_planning": false',html)


if __name__=='__main__':unittest.main()
