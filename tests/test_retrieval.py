"""Invented Pharos responses exercise scope, count, pagination and provenance contracts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from biograph_steward.client import PharosClient, PharosError, digest
from biograph_steward.retrieval import DEFAULT_LIMITS, retrieve_context, reported_count, settings
from biograph_steward.graph import save_run
from test_starter import MockAPI


class ContextAPI(MockAPI):
    def __init__(self):
        super().__init__(2)
        self.context = {t['uniprot']: {family: [] for family in DEFAULT_LIMITS} for t in self.rows}
        self.context['P04637'].update({
            'pathways': [{'pwid': i, 'name': f'Path {i}', 'type': 'Reactome', 'sourceID': f'R-HSA-{i}'} for i in range(1, 6)],
            'go': [{'goid': 'GO:0000001', 'type': 'P', 'term': 'invented annotation', 'evidence': 'IEA', 'assigned_by': 'TEST'}],
            'ppis': [{'nid': 1, 'type': 'STRINGDB', 'props': [{'name':'score','value':'0.9'}], 'target': {'uniprot': 'P00533', 'sym': 'TEST_1'}},
                     {'nid': 2, 'type': 'STRINGDB', 'target': {'uniprot': 'P01116', 'sym': 'OUTSIDE'}}],
            'drugs': [{'ligid':'TEST', 'name':'invented drug', 'isdrug': True}],
            'expressions': [{'expid':1,'tissue':'colon - epithelial cells','qual':'Not detected','type':'TEST'},
                            {'expid':2,'tissue':'heart','value':'0.1','type':'TEST'},
                            {'expid':3,'tissue':'rectum','value':None,'type':'TEST'}],
            'publications': [{'pmid':i,'title':'Invented unrelated paper','date':'2000-01-01'} for i in range(1,4)]})
        self.modify = lambda family, uid, skip, response: response

    def count_for(self, family, uid):
        n = len(self.context[uid][family])
        if family == 'publications': return n
        if family == 'ppis': return [{'name':'STRINGDB','value':n},{'name':'Total','value':n}]
        return [{'name':'drug' if family == 'drugs' else 'TEST','value':n}]

    def __call__(self, payload):
        query, v = payload['query'], payload['variables']
        if 'Scoped' not in query: return super().__call__(payload)
        self.calls.append(deepcopy(payload))
        result = {}
        for i in range(len([k for k in v if k.startswith('id')])):
            uid = v[f'id{i}']
            if 'ScopedMetadata' in query:
                record = {'uniprot':uid,'dataSources':['TEST'],'affiliate_links':[],
                    'pathwayCounts':self.count_for('pathways',uid), 'goCounts':self.count_for('go',uid),
                    'ppiCounts':self.count_for('ppis',uid),'ligandCounts':self.count_for('drugs',uid),
                    'expressionCounts':self.count_for('expressions',uid),'publicationCount':self.count_for('publications',uid)}
            else:
                family = query.split('Scoped_')[1].split('(')[0]
                skip, top = v[f'skip{i}'], v[f'top{i}']
                record = self.modify(family, uid, skip, {'uniprot':uid, 'reported':self.count_for(family,uid),
                    'rows':deepcopy(self.context[uid][family][skip:skip+top])})
            result[f't{i}'] = record
        return {'data':result}


class RetrievalTests(unittest.TestCase):
    def build(self, api=None, **kw):
        client = PharosClient(transport=api or ContextAPI())
        return client.build_snapshot('Test disease', profile='scoped', tissue_term='colon rectum', **kw)

    def test_full_pagination_scope_and_no_citation_leakage(self):
        with patch('biograph_steward.retrieval.CONTEXT_PAGE_SIZE',2):
            s = self.build()
        for request in s['requests']:
            self.assertEqual(request['response_sha256'],digest(request['response']))
        c = s['retrieval']['context']
        self.assertEqual(c['summary']['pathways']['retrieved'],5)
        self.assertEqual(c['summary']['ppis']['available'],2)  # Total, not sum of overlapping sources
        self.assertEqual(c['summary']['ppis']['retained'],1)
        self.assertEqual(c['summary']['expressions']['retained'],2)
        self.assertEqual(s['targets'][0]['pharos_context']['expressions'][0]['qual'],'Not detected')
        self.assertEqual(c['summary']['publications']['target_statuses'],{'complete':2})
        with tempfile.TemporaryDirectory() as tmp:
            g = save_run(s,Path(tmp)/'run')
            self.assertTrue(g['context_records'])
            self.assertTrue(all(not a['publications'] for a in g['assertions']))
            self.assertEqual(len(g['targets']),2)
            self.assertNotIn('UniProtKB:P01116',{n['id'] for n in g['nodes']})
            self.assertTrue((Path(tmp)/'run/retrieval_coverage.tsv').is_file())
            self.assertEqual(json.loads((Path(tmp)/'run/context_records.json').read_text()),g['context_records'])

    def test_request_locators_are_local_to_snapshot(self):
        c=PharosClient(transport=ContextAPI());c.search('test')
        s=c.build_snapshot('Test disease',profile='scoped')
        for row in s['retrieval']['context']['targets']:
            for page in row['pages']:
                record=s['requests'][page['request_index']]
                self.assertIn('Scoped_'+row['family'],record['request']['query'])
                alias=page['response_pointer'].split('/')[2]
                self.assertEqual(record['response']['data'][alias]['uniprot'],row['uniprot'])

    def test_caps_are_explicit_and_expression_needs_scope(self):
        c=PharosClient(transport=ContextAPI())
        s=c.build_snapshot('Test disease',profile='scoped',context_limits={'pathways':3,'publications':1})
        coverage=s['retrieval']['context']
        self.assertEqual(coverage['summary']['pathways']['target_statuses'],{'capped':1,'complete':1})
        self.assertEqual(coverage['summary']['expressions']['target_statuses'],{'not_requested':2})
        self.assertEqual(coverage['summary']['expressions']['retrieved'],0)

    def test_zero_limit_never_sends_top_zero(self):
        api=ContextAPI();self.build(api,context_limits={k:0 for k in DEFAULT_LIMITS})
        self.assertFalse(any('Scoped_' in c['query'] for c in api.calls))

    def test_early_short_page_is_inconsistent_not_complete(self):
        api=ContextAPI()
        api.modify=lambda family,uid,skip,r:{**r,'rows':r['rows'][:1]} if family=='pathways' else r
        s=self.build(api)
        self.assertEqual(s['retrieval']['context']['targets'][0]['status'],'inconsistent')

    def test_changed_count_is_inconsistent(self):
        api=ContextAPI()
        api.modify=lambda family,uid,skip,r:{**r,'reported':[{'name':'TEST','value':99}]} if family=='pathways' else r
        self.assertEqual(self.build(api)['retrieval']['context']['targets'][0]['status'],'inconsistent')

    def test_null_family_rejected_not_empty_success(self):
        api=ContextAPI()
        api.modify=lambda family,uid,skip,r:{**r,'rows':None} if family=='go' else r
        with self.assertRaisesRegex(PharosError,'Malformed go'):self.build(api)

    def test_repeated_page_rejected(self):
        api=ContextAPI()
        api.modify=lambda family,uid,skip,r:{**r,'rows':deepcopy(api.context[uid][family][:2])} if family=='pathways' else r
        with patch('biograph_steward.retrieval.CONTEXT_PAGE_SIZE',2),self.assertRaisesRegex(PharosError,'Repeated'):
            self.build(api)

    def test_partial_page_overlap_cannot_claim_complete(self):
        api=ContextAPI()
        def overlap(family,uid,skip,r):
            if family=='pathways' and skip==2:
                r['rows'][0]=deepcopy(api.context[uid][family][1])
            return r
        api.modify=overlap
        with patch('biograph_steward.retrieval.CONTEXT_PAGE_SIZE',2):
            s=self.build(api)
        row=s['retrieval']['context']['targets'][0]
        self.assertEqual(row['status'],'inconsistent')
        self.assertTrue(any('overlapped' in issue for issue in row['issues']))

    def test_source_envelope_corruption_cannot_be_replayed(self):
        from biograph_steward.graph import verify_snapshot
        s=self.build()
        s['requests'][0]['response']['data']['corrupted']=True
        s.pop('content_sha256');s['content_sha256']=digest(s)
        with self.assertRaisesRegex(ValueError,'Source response integrity'):
            verify_snapshot(s)

    def test_wrong_target_rejected(self):
        api=ContextAPI();api.modify=lambda family,uid,skip,r:{**r,'uniprot':'P01116'}
        with self.assertRaisesRegex(PharosError,'requested target'):self.build(api)

    def test_global_budget_is_enforced_and_recorded(self):
        api=ContextAPI();client=PharosClient(transport=api)
        c=retrieve_context(client,deepcopy(api.rows),DEFAULT_LIMITS,'colon',row_budget=3)
        self.assertEqual(c['rows_retrieved'],3)
        self.assertIn('budget_limited',{r['status'] for r in c['targets']})
        self.assertTrue(all(v>0 for c in api.calls for k,v in c['variables'].items() if k.startswith('top')))

    def test_short_pages_release_reserved_budget_for_later_targets(self):
        api=ContextAPI();api.count_for=lambda family,uid:None
        for uid in api.context:
            api.context[uid]['go']=[{'goid':'GO:0000001','type':'P','term':'Test'}]
        limits={k:0 for k in DEFAULT_LIMITS};limits['go']=3
        c=retrieve_context(PharosClient(transport=api),deepcopy(api.rows),limits,row_budget=3)
        rows=[r for r in c['targets'] if r['family']=='go']
        self.assertEqual([r['retrieved'] for r in rows],[1,1])
        self.assertEqual([r['status'] for r in rows],['exhausted','exhausted'])

    def test_unknown_counts_are_not_reported_as_zero(self):
        self.assertIsNone(reported_count(None,'pathways'))
        self.assertIsNone(reported_count([{'name':'STRINGDB','value':2}],'ppis'))
        self.assertIsNone(reported_count(True,'publications'))
        api=ContextAPI();api.count_for=lambda family,uid:None
        s=self.build(api)
        self.assertEqual(s['retrieval']['context']['summary']['pathways']['target_statuses'],{'exhausted':2})
        self.assertIsNone(s['retrieval']['context']['summary']['pathways']['available'])

    def test_bad_limits_and_tissue_inputs_fail_before_requests(self):
        for limits in [{'ppis':-1},{'publications':201},{'go':True},{'unknown':1}]:
            with self.assertRaises(ValueError):settings(limits)
        with self.assertRaises(ValueError):settings(tissue_term='colon +rectum')

    def test_preview_does_not_fetch_new_families(self):
        api=ContextAPI();s=PharosClient(transport=api).build_snapshot('Test disease')
        self.assertNotIn('context',s['retrieval'])
        self.assertFalse(any('Scoped' in c['query'] for c in api.calls))

if __name__ == '__main__':unittest.main()
