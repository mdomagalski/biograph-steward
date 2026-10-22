"""Standard-library tests: python -m unittest discover -s tests -v.

The mock transport tests behavior, not the actual Pharos deployment.
"""
from __future__ import annotations
from copy import deepcopy
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from biograph_steward.client import (
    PharosClient, PharosError, digest, write_json, VERSION, REQUIRED_FIELDS, TARGETS,
)
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import (
    build_graph, verify_snapshot, save_run, protein_id, disease_id, pathway_id, publication_ids,
)
from biograph_steward.webapp import create_server, report_html


def resign(snapshot):
    snapshot.pop('content_sha256', None)
    snapshot['content_sha256'] = digest(snapshot)
    return snapshot


class MockAPI:
    """Invented response records for contract tests, NOT real API data."""
    def __init__(self, count=4):
        self.calls = []
        self.count = count
        self.rows = []
        ids = ['P04637', 'P00533', 'P01116', 'P15056', 'P31749', 'P42336']
        for i in range(count):
            self.rows.append({'uniprot': ids[i], 'sym': f'TEST_{i}', 'name': f'Test protein {i}',
                              'tdl': 'Tbio', 'fam': 'TEST', 'diseaseAssociationDetails': [
                                  {'name': 'Test disease', 'source': 'MOCK', 'evidence': 'Mock only',
                                   'reference': 'TEST:1', 'score': 0.0}], 'pathways': []})

    def __call__(self, payload):
        self.calls.append(deepcopy(payload))
        query, var = payload['query'], payload['variables']
        if 'InspectType' in query:
            name = var['name']
            key = 'inputFields' if name == 'IFilter' else 'fields'
            return {'data': {'__type': {'name': name, key: [{'name': x} for x in REQUIRED_FIELDS[name]]}}}
        if 'DatabaseVersion' in query:
            return {'data': {'dbVersion': 'TEST-ONLY'}}
        if 'SearchDiseases' in query:
            return {'data': {'diseases': {'count': 1, 'diseases': [{'name': 'Test disease', 'mondoID': 'MONDO:0000001'}]}}}
        if 'DiseaseInfo' in query:
            return {'data': {'disease': {'name': 'Test disease', 'mondoID': 'MONDO:0000001'}}}
        if 'DiseaseTargets' in query:
            return {'data': {'targets': {'count': self.count,
                                        'targets': self.rows[var['skip']:var['skip']+var['top']]}}}
        if 'SourceLicenses' in query:
            return {'data': {'dataSourceCounts': []}}
        raise AssertionError(query)


class GraphTests(unittest.TestCase):
    def test_demo_is_explicit(self):
        g = build_graph(demo_snapshot())
        self.assertEqual(g['data_kind'], 'synthetic_demo')
        self.assertTrue(all(n['id'].startswith('demo:') for n in g['nodes']))
        self.assertTrue(all(not e['biologically_validated'] for e in g['edges']))

    def test_demo_counts(self):
        g = build_graph(demo_snapshot())
        self.assertEqual(g['summary']['proteins'], 6)
        self.assertEqual(g['summary']['evidence_edges'], 18)
        self.assertEqual(g['summary']['needs_review'], 3)
        self.assertEqual(g['summary']['quarantined_records'], 2)

    def test_uniprot_not_gene_symbol(self):
        self.assertEqual(protein_id('P04637'), 'UniProtKB:P04637')
        self.assertEqual(protein_id('A0A024RBG1'), 'UniProtKB:A0A024RBG1')
        self.assertEqual(protein_id('P04637-2'), 'UniProtKB:P04637-2')
        self.assertIsNone(protein_id('TP53'))
        self.assertIsNone(protein_id('DEMO_PROTEIN_001'))

    def test_disease_mapping_does_not_guess(self):
        self.assertEqual(disease_id({'name':'x','mondoID':'MONDO_0005575'}), ('MONDO:0005575', True))
        identifier, mapped = disease_id({'name':'unknown cancer','mondoID':None})
        self.assertFalse(mapped)
        self.assertTrue(identifier.startswith('pharos.disease:'))

    def test_pathway_mapping(self):
        self.assertEqual(pathway_id({'type':'Reactome','sourceID':'R-HSA-1234','pwid':5}), ('REACT:R-HSA-1234', True))
        self.assertEqual(pathway_id({'type':'other','sourceID':'something','pwid':5}), ('pharos.pathway:5', False))
        self.assertEqual(pathway_id({'type':'other'}), (None, False))

    def test_no_invented_pmids(self):
        self.assertEqual(publication_ids('1234'), [])
        self.assertEqual(publication_ids('PMID:1234; https://pubmed.ncbi.nlm.nih.gov/1234/'), ['PMID:1234'])

    def test_hash_detects_snapshot_edit(self):
        s=demo_snapshot(); s['targets'][0]['tdl']='changed'
        with self.assertRaisesRegex(ValueError,'integrity'): verify_snapshot(s)

    def test_missing_evidence_is_review_not_proof(self):
        g=build_graph(demo_snapshot())
        edge=next(e for e in g['edges'] if e['record_kind']=='disease_filtered_membership')
        self.assertEqual(edge['status'],'needs_review')
        self.assertIsNone(edge['primary_source_raw'])

    def test_other_disease_flagged_not_silently_merged(self):
        g=build_graph(demo_snapshot())
        e=next(e for e in g['edges'] if e['evidence_record'].get('name')=='Demo rectal cancer')
        self.assertIn('evidence_disease_name_differs_from_selected_term',e['review_reasons'])
        self.assertNotEqual(e['object'], g['disease_node_id'])

    def test_source_scores_are_not_confidence(self):
        g=build_graph(demo_snapshot())
        e=next(e for e in g['edges'] if e['primary_source_raw']=='SYNTHETIC_SOURCE_B')
        self.assertEqual(e['source_scores_raw']['score'],0.0)
        self.assertNotIn('model_score',e)
        self.assertIsNone(e['source_scores_raw']['conf'])

    def test_graph_deterministic_for_same_snapshot(self):
        s=demo_snapshot()
        self.assertEqual(build_graph(s),build_graph(s))

    def test_source_evidence_kept_separately(self):
        g=build_graph(demo_snapshot())
        a=[e for e in g['edges'] if e['subject']=='demo:protein:DEMO_PROTEIN_001' and e['predicate']=='biolink:associated_with']
        self.assertEqual(len(a),2)

    def test_no_bad_ids_in_published_graph(self):
        g=build_graph(demo_snapshot())
        ids={n['id'] for n in g['nodes']}
        self.assertTrue(all(e['subject'] in ids and e['object'] in ids for e in g['edges']))

    def test_non_demo_rejects_synthetic_ids(self):
        s=demo_snapshot(); s['data_kind']='live_pharos'; resign(s)
        g=build_graph(s)
        self.assertEqual(g['summary']['proteins'],0)

    def test_export_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); g=save_run(demo_snapshot(),root/'one')
            saved=json.loads((root/'one/snapshot.json').read_text())
            g2=save_run(saved,root/'two',run_mode='replay')
            self.assertEqual(g,g2)
            for f in ['graph.json','nodes.tsv','edges.tsv','targets.tsv','quarantine.jsonl','report.html','run_manifest.json','pipeline_trace.json']:
                self.assertTrue((root/'one'/f).exists())
            manifest=json.loads((root/'two/run_manifest.json').read_text())
            self.assertFalse(manifest['link_prediction_performed'])
            self.assertFalse(manifest['llm_used'])

    def test_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run'; save_run(demo_snapshot(),p)
            with self.assertRaisesRegex(ValueError,'not empty'): save_run(demo_snapshot(),p)

    def test_html_embedded_json_is_escaped(self):
        s=demo_snapshot(); s['disease']['name']='</script><script>alert(1)</script>'; resign(s)
        html=report_html(build_graph(s))
        self.assertNotIn('</script><script>alert(1)</script>',html)
        self.assertIn('\\u003c/script\\u003e',html)


class ClientTests(unittest.TestCase):
    def test_schema_check(self):
        api=MockAPI(); c=PharosClient(transport=api)
        self.assertEqual(c.check_schema()['status'],'required_fields_present')

    def test_schema_mismatch_fails(self):
        c=PharosClient(transport=lambda p:{'data':{'__type':None}})
        with self.assertRaisesRegex(PharosError,'schema differs'):c.check_schema()

    def test_paginated_build(self):
        api=MockAPI(4);c=PharosClient(transport=api)
        s=c.build_snapshot('Test disease',max_targets=4,page_size=2)
        self.assertEqual(len(s['targets']),4)
        self.assertFalse(s['retrieval']['truncated'])
        calls=[p for p in api.calls if 'DiseaseTargets' in p['query']]
        self.assertEqual([p['variables']['skip'] for p in calls],[0,2])
        verify_snapshot(s)

    def test_bounded_run_says_truncated(self):
        s=PharosClient(transport=MockAPI(5)).build_snapshot('Test disease',max_targets=3,page_size=2)
        self.assertTrue(s['retrieval']['truncated'])
        self.assertEqual(len(s['targets']),3)

    def test_zero_targets_is_successful_empty_extract(self):
        s=PharosClient(transport=MockAPI(0)).build_snapshot('Test disease')
        self.assertFalse(s['retrieval']['truncated'])
        self.assertEqual(build_graph(s)['summary']['proteins'],0)

    def test_no_silent_disease_reassignment(self):
        with self.assertRaisesRegex(PharosError,'Confirm that exact term'):
            PharosClient(transport=MockAPI()).build_snapshot('different input')

    def test_partial_graphql_errors_rejected(self):
        c=PharosClient(transport=lambda p:{'data':{'dbVersion':'x'},'errors':[{'message':'partial failure'}]})
        with self.assertRaisesRegex(PharosError,'partial data rejected'):c.execute(VERSION)

    def test_null_data_rejected(self):
        c=PharosClient(transport=lambda p:{'data':None})
        with self.assertRaises(PharosError):c.execute(VERSION)

    def test_search_uses_variables(self):
        api=MockAPI(); c=PharosClient(transport=api)
        term='\" } arbitrary { mutation'
        c.search(term)
        self.assertEqual(api.calls[-1]['variables']['term'],term)
        self.assertNotIn(term,api.calls[-1]['query'])

    def test_no_pathways_uses_graphql_directive(self):
        api=MockAPI(); PharosClient(transport=api).build_snapshot('Test disease',pathway_top=0)
        req=next(p for p in api.calls if 'DiseaseTargets' in p['query'])
        self.assertFalse(req['variables']['includePathways'])
        self.assertIn('@include',TARGETS)

    def test_cache_is_reused_with_original_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            api=MockAPI(); c=PharosClient(transport=api,cache_dir=Path(tmp))
            c.execute(VERSION); stamp=c.records[0]['retrieved_at']; c.execute(VERSION)
            self.assertEqual(len(api.calls),1)
            self.assertTrue(c.records[-1]['loaded_from_cache'])
            self.assertEqual(c.records[-1]['retrieved_at'],stamp)

    def test_corrupt_cache_is_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            api=MockAPI(); c=PharosClient(transport=api,cache_dir=Path(tmp))
            c.execute(VERSION);p=next(Path(tmp).glob('*.json')); x=json.loads(p.read_text());x['response']['data']['dbVersion']='tampered';p.write_text(json.dumps(x))
            c.execute(VERSION);self.assertEqual(len(api.calls),2)

    def test_refresh_bypasses_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            api=MockAPI(); c=PharosClient(transport=api,cache_dir=Path(tmp),refresh=True)
            c.execute(VERSION);c.execute(VERSION);self.assertEqual(len(api.calls),2)

    def test_bad_limits(self):
        c=PharosClient(transport=MockAPI())
        with self.assertRaises(ValueError):c.build_snapshot('Test disease',max_targets=0)
        with self.assertRaises(ValueError):c.search('')
        with self.assertRaises(ValueError):PharosClient('http://example.com/graphql')

    def test_license_failure_does_not_fake_license(self):
        api=MockAPI()
        def transport(p):
            if 'SourceLicenses' in p['query']:raise PharosError('metadata unavailable')
            return api(p)
        s=PharosClient(transport=transport).build_snapshot('Test disease')
        self.assertEqual(s['source_licenses'],[])
        self.assertTrue(any('redistribution' in w for w in s['warnings']))

    def test_repeated_page_is_error(self):
        api=MockAPI(4)
        def transport(p):
            if 'DiseaseTargets' in p['query']:
                return {'data':{'targets':{'count':4,'targets':api.rows[:2]}}}
            return api(p)
        with self.assertRaisesRegex(PharosError,'repeated'):
            PharosClient(transport=transport).build_snapshot('Test disease',max_targets=4,page_size=2)

    def test_http_errors_not_demo(self):
        c=PharosClient(retries=0)
        with patch('biograph_steward.client.urlopen',side_effect=URLError('network unavailable')):
            with self.assertRaisesRegex(PharosError,'Cannot reach Pharos'):c.execute(VERSION)
        self.assertEqual(c.records,[])

    def test_http_400_not_retried(self):
        error=HTTPError('https://example.com',400,'bad',{},BytesIO(b'bad request'))
        with patch('biograph_steward.client.urlopen',side_effect=error) as mock:
            with self.assertRaisesRegex(PharosError,'HTTP 400'):PharosClient(retries=2).execute(VERSION)
            self.assertEqual(mock.call_count,1)


class HttpTransportIntegrationTests(unittest.TestCase):
    def test_full_pipeline_via_real_http_to_a_local_mock(self):
        api = MockAPI(4)
        class GraphQLHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                data = json.dumps(api(payload)).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def log_message(self, *args):
                pass
        backend = ThreadingHTTPServer(('127.0.0.1', 0), GraphQLHandler)
        thread = threading.Thread(target=backend.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f'http://127.0.0.1:{backend.server_port}/graphql'
            c = PharosClient(endpoint, timeout=5, retries=0)
            self.assertEqual(c.search('test')['count'], 1)
            snapshot = c.build_snapshot('Test disease', max_targets=3, page_size=2)
            self.assertEqual(len(snapshot['targets']), 3)
            self.assertTrue(snapshot['retrieval']['truncated'])
            self.assertEqual(build_graph(snapshot)['summary']['proteins'], 3)
            self.assertEqual(snapshot['endpoint'], endpoint)
            # This proves the HTTP plumbing, not connectivity to real Pharos.
            self.assertEqual(snapshot['db_version'], 'TEST-ONLY')
        finally:
            backend.shutdown(); backend.server_close(); thread.join()


class LocalServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.server=create_server(0,Path(cls.tmp.name)/'runs')
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()

    def post(self,path,body,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=Request(self.url+path,data=json.dumps(body).encode(),headers=headers)
        return urlopen(req)

    def test_ui_served(self):
        with urlopen(self.url) as r:
            self.assertIn('<title>BioGraph Steward | Evidence workbench</title>',r.read().decode())

    def test_demo_http_and_zip(self):
        with self.post('/api/build',{'mode':'demo'}) as r:data=json.loads(r.read())
        self.assertEqual(data['graph']['data_kind'],'synthetic_demo')
        with urlopen(self.url+'/api/download/'+data['run_id']) as r:
            self.assertTrue(r.read().startswith(b'PK'))

    def test_review_api_preserves_source_and_rejects_bad_decisions(self):
        with self.post('/api/build', {'mode': 'demo'}) as r: original = json.loads(r.read())
        assertion = next(a for a in original['graph']['assertions'] if a['kind'] == 'disease_association'
                         and 'accepted' in a['allowed_transitions'])
        body = {'run_id': original['run_id'], 'assertion_id': assertion['id'],
                'state': 'accepted', 'reviewer': 'HTTP test reviewer', 'reason': 'Synthetic review test'}
        with self.post('/api/review', body) as r: reviewed = json.loads(r.read())
        self.assertNotEqual(original['run_id'], reviewed['run_id'])
        self.assertEqual(reviewed['graph']['assertion_summary']['lifecycle_counts']['accepted'], 1)
        self.assertEqual(reviewed['graph']['snapshot_sha256'], original['graph']['snapshot_sha256'])
        with urlopen(self.url+'/api/run/'+reviewed['run_id']) as r:
            reopened = json.loads(r.read())
        self.assertEqual(reopened['graph'], reviewed['graph'])
        with urlopen(self.url+'/api/run/'+original['run_id']) as r:
            self.assertEqual(json.loads(r.read())['graph']['assertion_summary']['lifecycle_counts']['accepted'], 0)
        with self.post('/api/review', {**body, 'run_id': reviewed['run_id'], 'state': 'obsolete'}) as r:
            obsolete = json.loads(r.read())
        self.assertEqual(len(obsolete['graph']['review_events']), 2)
        for change in [{'run_id': '../outside'}, {'reviewer': ''}, {'state': 'obsolete'}, {'assertion_id': 'unknown'}]:
            with self.assertRaises(HTTPError) as ctx: self.post('/api/review', {**body, **change})
            self.assertEqual(ctx.exception.code, 400)

    def test_cross_origin_rejected(self):
        with self.assertRaises(HTTPError) as ctx:self.post('/api/build',{'mode':'demo'},'https://example.com')
        self.assertEqual(ctx.exception.code,403)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(HTTPError) as ctx:self.post('/api/build',{'mode':'unknown'})
        self.assertEqual(ctx.exception.code,400)

    def test_path_traversal_rejected(self):
        with self.assertRaises(HTTPError) as ctx:urlopen(self.url+'/api/download/../../etc/passwd')
        self.assertEqual(ctx.exception.code,404)


if __name__=='__main__':unittest.main()
