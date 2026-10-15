"""Invented source records test the CIViC adapter; no clinical gold labels."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.assertions import new_review_event
from biograph_steward.client import PharosClient, digest
from biograph_steward.civic import CivicClient, CivicError, RESOLVE, verify_civic, overlap_report
from biograph_steward.civic_questions import answer_civic_question
from biograph_steward.graph import build_graph, save_run
from biograph_steward.questions import graph_basis, save_answer, verify_answer
from biograph_steward.reviews import read_run, review_run
from biograph_steward.__main__ import main
from test_starter import MockAPI


def resign(s):
    s.pop('content_sha256',None);s['content_sha256']=digest(s);return s


class CivicAPI:
    def __init__(self):
        self.calls=[]
        self.gene={'id':30,'name':'KRAS','entrezId':3845,'deprecated':False,
                   'myGeneInfoDetails':json.dumps({'_id':'3845','taxid':9606,'uniprot':{'Swiss-Prot':'P01116'}})}
        self.disease={'id':11,'name':'INVENTED Colorectal Cancer','doid':'9256','deprecated':False,'link':'/diseases/11'}
        self.cet={'id':16,'name':'Cetuximab','ncitId':'C1723','deprecated':False,'link':'/therapies/16'}
        self.pan={'id':28,'name':'Panitumumab','ncitId':'C1857','deprecated':False,'link':'/therapies/28'}
        self.rows=[self.row(100,'RESISTANCE'),self.row(101,'SENSITIVITYRESPONSE'),
                   self.row(102,'SENSITIVITYRESPONSE',direction='DOES_NOT_SUPPORT'),
                   self.row(103,'RESISTANCE',combo=True)]

    def row(self,eid,significance,direction='SUPPORTS',combo=False):
        profile={'id':81,'name':'INVENTED KRAS profile','rawName':'#VID81','isComplex':False,'isMultiVariant':False,
                 'deprecated':False,'flagged':False,'link':'/molecular-profiles/81',
                 'variants':[{'id':81,'name':'INVENTED variant','deprecated':False,'flagged':False,'link':'/variants/81',
                              'feature':{'id':30,'name':'KRAS','deprecated':False,'featureInstance':{'__typename':'Gene','entrezId':3845}}}]}
        return {'id':eid,'description':'INVENTED SOFTWARE TEST statement, not biomedical evidence.',
                'evidenceType':'PREDICTIVE','evidenceDirection':direction,'significance':significance,'evidenceLevel':'D',
                'evidenceRating':3,'status':'ACCEPTED','flagged':False,'openRevisionCount':0,'variantOrigin':'SOMATIC',
                'therapyInteractionType':'COMBINATION' if combo else None,'link':'/evidence/'+str(eid),
                'molecularProfile':profile,'disease':deepcopy(self.disease),
                'therapies':[deepcopy(self.cet),deepcopy(self.pan)] if combo else [deepcopy(self.cet)],
                'source':{'id':700+eid,'name':'Test citation','sourceType':'PUBMED','citationId':str(90000000+eid),
                          'citation':'INVENTED citation','title':'INVENTED software fixture','sourceUrl':None,
                          'publicationYear':2000,'link':'/sources/'+str(700+eid),'deprecated':False,'retracted':False}}

    def __call__(self,payload):
        self.calls.append(deepcopy(payload))
        if payload['query']==RESOLVE:
            connection=lambda x:{'nodes':[deepcopy(x)],'pageInfo':{'hasNextPage':False}}
            return {'data':{'genes':connection(self.gene),'diseases':connection(self.disease),
                            'cetuximab':connection(self.cet),'panitumumab':connection(self.pan)}}
        v=payload['variables'];rows=[r for r in self.rows if v['therapy'] in [t['id'] for t in r['therapies']]]
        start=int(v['after'] or 0);end=start+v['first']
        return {'data':{'evidenceItems':{'totalCount':len(rows),'nodes':deepcopy(rows[start:end]),
                                        'pageInfo':{'hasNextPage':end<len(rows),'endCursor':str(min(end,len(rows)))}}}}


def fixture(api=None):
    p=PharosClient(transport=MockAPI(4)).build_snapshot('Test disease')
    c=CivicClient(transport=api or CivicAPI()).retrieve()
    return p,c


class CivicTests(unittest.TestCase):
    def test_retrieval_deduplicates_complete_items_and_keeps_every_response_locator(self):
        api=CivicAPI();c=CivicClient(transport=api).retrieve()
        self.assertEqual(len(c['items']),4);self.assertEqual(len(c['items'][-1]['provenance']),2)
        self.assertEqual([x['status'] for x in c['coverage']],['complete','complete'])
        self.assertEqual(len(api.calls),3);verify_civic(c)
        self.assertTrue(all('mutation' not in x['query'].lower() for x in api.calls))

    def test_cap_remains_explicit_and_no_unbounded_retrieval(self):
        c=CivicClient(transport=CivicAPI()).retrieve(1)
        self.assertEqual(c['coverage'][0]['status'],'capped')
        self.assertEqual(c['coverage'][0]['reported'],4)
        for cap in [0,201,True,'100']:
            with self.assertRaises(ValueError):CivicClient(transport=CivicAPI()).retrieve(cap)

    def test_partial_graphql_response_is_rejected(self):
        with self.assertRaisesRegex(CivicError,'partial data'):
            CivicClient(transport=lambda p:{'data':{},'errors':[{'message':'test'}]}).retrieve()

    def test_ambiguous_identifier_resolution_is_rejected(self):
        api=CivicAPI()
        def transport(p):
            r=api(p)
            if p['query']==RESOLVE:r['data']['diseases']['nodes']*=2
            return r
        with self.assertRaisesRegex(CivicError,'ambiguous'):CivicClient(transport=transport).retrieve()

    def test_pagination_does_not_silently_accept_stalled_or_conflicting_versions(self):
        api=CivicAPI();api.rows=[api.row(i,'RESISTANCE') for i in range(1,55)]
        def stalled(p):
            r=api(p)
            if p['query']!=RESOLVE:r['data']['evidenceItems']['pageInfo']={'hasNextPage':True,'endCursor':None}
            return r
        with self.assertRaisesRegex(CivicError,'did not advance'):CivicClient(transport=stalled).retrieve()
        api=CivicAPI()
        def changed(p):
            r=api(p)
            if p['query']!=RESOLVE and p['variables']['therapy']==28:
                r['data']['evidenceItems']['nodes'][0]['description']='Changed during pull'
            return r
        with self.assertRaisesRegex(CivicError,'different versions'):CivicClient(transport=changed).retrieve()

    def test_snapshot_and_raw_source_integrity_are_checked(self):
        _,c=fixture();c['items'][0]['record']['description']='changed'
        with self.assertRaisesRegex(ValueError,'integrity'):verify_civic(c)
        resign(c)
        with self.assertRaisesRegex(ValueError,'differs'):verify_civic(c)

    def test_imported_sidecar_cannot_silently_change_scope_or_use_negative_locators(self):
        _,c=fixture();c['scope']['therapies'][0]['ncitId']='OTHER';resign(c)
        with self.assertRaisesRegex(ValueError,'fixed retrieval scope'):verify_civic(c)
        _,c=fixture();c['items'][0]['provenance'][0]['request_index']=-1;resign(c)
        with self.assertRaisesRegex(ValueError,'locator'):verify_civic(c)

    def test_qualified_identity_preserves_negated_evidence_and_combination_conditions(self):
        p,c=fixture();g=build_graph(p,civic_snapshot=c)
        claims=[a for a in g['assertions'] if a['kind']=='variant_therapy_response']
        self.assertEqual(len(claims),4);self.assertEqual({a['lifecycle_state'] for a in claims},{'candidate'})
        self.assertEqual({a['qualifiers']['evidence_direction'] for a in claims},{'SUPPORTS','DOES_NOT_SUPPORT'})
        combo=next(a for a in claims if a['qualifiers']['therapy_interaction'])
        node=next(n for n in g['nodes'] if n['id']==combo['object']);self.assertEqual(len(node['members']),2)
        self.assertEqual(g['civic']['mapping']['protein_ids'],['UniProtKB:P01116'])
        self.assertNotEqual(combo['qualifiers']['disease'],g['disease_node_id'])

    def test_complex_profile_is_not_split_into_single_variants(self):
        api=CivicAPI();row=api.rows[0];row['molecularProfile']['isComplex']=True
        row['molecularProfile']['rawName']='#VID81 AND #VID82'
        other=deepcopy(row['molecularProfile']['variants'][0]);other['id']=82;other['name']='Second invented variant'
        row['molecularProfile']['variants'].append(other)
        for r in api.rows:r['molecularProfile']=deepcopy(row['molecularProfile'])
        p,c=fixture(api);g=build_graph(p,civic_snapshot=c)
        # The source profile ID and logical expression stay whole.
        a=next(e for e in g['edges'] if e['record_kind']=='variant_therapy_response' and e['evidence_record']['id']==100)
        self.assertEqual(a['subject'],'CIViC.molecularprofile:81');self.assertEqual(len(a['evidence_record']['molecularProfile']['variants']),2)

    def test_inconsistent_profile_definitions_are_not_silently_overwritten(self):
        api=CivicAPI();api.rows[0]['molecularProfile']['rawName']='#VID81 OR #VID99';p,c=fixture(api)
        with self.assertRaisesRegex(ValueError,'Inconsistent CIViC profile'):build_graph(p,civic_snapshot=c)

    def test_no_symbol_fallback_for_gene_protein_mapping(self):
        api=CivicAPI();api.gene['myGeneInfoDetails']=json.dumps({'_id':'3845','uniprot':{'Swiss-Prot':'P99999'}})
        p,c=fixture(api);g=build_graph(p,civic_snapshot=c)
        self.assertEqual(g['civic']['normalized_items'],0)
        self.assertEqual(g['civic']['mapping']['status'],'unresolved')

    def test_missing_taxid_uses_only_fixed_supported_gene_and_cross_reference(self):
        api=CivicAPI();d=json.loads(api.gene['myGeneInfoDetails']);d.pop('taxid');api.gene['myGeneInfoDetails']=json.dumps(d)
        p,c=fixture(api);self.assertEqual(build_graph(p,civic_snapshot=c)['civic']['normalized_items'],4)

    def test_source_status_pending_flags_retraction_scope_and_semantics_exclusions(self):
        changes=[lambda r:r.update(status='SUBMITTED'),lambda r:r.update(openRevisionCount=1),lambda r:r.update(flagged=True),
                 lambda r:r['source'].update(retracted=True),lambda r:r['disease'].update(doid='other'),
                 lambda r:r.update(evidenceDirection='NA'),lambda r:r['molecularProfile'].update(deprecated=True),
                 lambda r:r['molecularProfile']['variants'][0]['feature']['featureInstance'].update(entrezId=999)]
        for change in changes:
            api=CivicAPI();api.rows=[api.rows[0]];change(api.rows[0]);p,c=fixture(api);g=build_graph(p,civic_snapshot=c)
            self.assertEqual(g['civic']['normalized_items'],0);self.assertTrue(g['civic']['excluded_items'])

    def test_overlap_distinguishes_discovery_reference_from_claim_support(self):
        p,c=fixture();pmid=int(c['items'][0]['record']['source']['citationId'])
        p['targets'][0]['pharos_context']={'publications':[{'pmid':pmid,'title':'Invented discovery'}]};resign(p)
        g=build_graph(p,civic_snapshot=c);r=g['civic']['overlap']
        self.assertEqual(r['publication_counts']['shared_discovery_publication'],1)
        self.assertEqual(r['verified_independent_evidence'],0)
        self.assertTrue(all(x['independence']=='unresolved' for x in r['rows']))
        edge=next(e for e in g['edges'] if e['record_kind']=='variant_therapy_response')
        report=overlap_report([edge],[edge],p)
        self.assertEqual(report['rows'][0]['representation'],'duplicate_qualified_assertion')

    def test_accepted_view_requires_local_review_not_civic_editorial_status(self):
        p,c=fixture();g=build_graph(p,civic_snapshot=c)
        a=answer_civic_question(g);self.assertFalse(a['results']);self.assertEqual(a['availability']['inspectable_assertions'],4)
        claim=next(a for a in g['assertions'] if a['kind']=='variant_therapy_response')
        event=new_review_event(g,claim['id'],'accepted','Software test','Invented fixture only')
        accepted=build_graph(p,[event],c);answer=answer_civic_question(accepted)
        self.assertEqual(len(answer['summary']),1);self.assertEqual(answer['citations'][0]['review_state'],'accepted')
        event2=new_review_event(accepted,claim['id'],'provisional','Software test','Invented fixture only')
        self.assertFalse(answer_civic_question(build_graph(p,[event,event2],c))['results'])
        c['created_at']='2026-01-01T00:00:00+00:00';resign(c)
        with self.assertRaisesRegex(ValueError,'different CIViC'):build_graph(p,[event],c)

    def test_cited_summary_preserves_direction_and_reports_discordance(self):
        p,c=fixture();g=build_graph(p,civic_snapshot=c);a=answer_civic_question(g,view='candidates',max_paths=10)
        self.assertTrue(any('does not support sensitivity/response' in s['text'] for s in a['summary']))
        self.assertEqual(len(a['discordant_annotations']),1)
        self.assertEqual(len(a['citations']),4);self.assertEqual(len(a['results'][0]['paths']),4)
        for item in a['summary']:
            self.assertTrue(item['citation_ids']);self.assertIn('DOID:9256',item['text'])
        self.assertTrue(all(c['evidence_records'][0]['retrieval_provenance'] for c in a['citations']))
        self.assertEqual(a,answer_civic_question(g,view='candidates',max_paths=10))

    def test_result_caps_do_not_hide_full_match_or_discordance_counts(self):
        p,c=fixture();a=answer_civic_question(build_graph(p,civic_snapshot=c),view='candidates',max_paths=1)
        self.assertEqual(a['results'][0]['omitted_paths'],3);self.assertEqual(a['availability']['inspectable_assertions'],4)
        self.assertEqual(len(a['discordant_annotations']),1)
        for kw in [{'profile':'G13D'},{'max_results':True},{'max_paths':11},{'therapy':'drug'},{'view':'all'}]:
            with self.assertRaises(ValueError):answer_civic_question(build_graph(p,civic_snapshot=c),**kw)

    def test_substitute_and_sequential_labels_do_not_imply_combination_or_order(self):
        for interaction,expected in [('SUBSTITUTES',' or '),('SEQUENTIAL','order not specified')]:
            api=CivicAPI();api.rows=[api.rows[-1]];api.rows[0]['therapyInteractionType']=interaction
            p,c=fixture(api);a=answer_civic_question(build_graph(p,civic_snapshot=c),view='candidates')
            self.assertIn(expected,a['summary'][0]['text'])

    def test_original_assertion_ids_revisions_and_review_history_survive_enrichment(self):
        p,c=fixture();base=build_graph(p);claim=next(a for a in base['assertions'] if a['structurally_usable_evidence_ids'])
        event=new_review_event(base,claim['id'],'accepted','Software test','Invented fixture')
        base=build_graph(p,[event]);enriched=build_graph(p,[event],c)
        index={a['id']:a for a in enriched['assertions']}
        for a in base['assertions']:
            self.assertEqual(a,index[a['id']])
        self.assertNotEqual(graph_basis(base),graph_basis(enriched))
        self.assertEqual(base['snapshot_sha256'],enriched['snapshot_sha256'])

    def test_saved_sidecar_review_exports_and_cli_replay(self):
        p,c=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';save_run(p,source)
            path=root/'civic.json';path.write_text(json.dumps(c))
            output=root/'enriched'
            with redirect_stdout(StringIO()):
                self.assertEqual(main(['civic','--run',str(source),'--snapshot',str(path),'--out',str(output)]),0)
            _,_,g=read_run(output);claim=next(a for a in g['assertions'] if a['kind']=='variant_therapy_response')
            new=root/'reviewed';review_run(output,new,claim['id'],'accepted','Software test','Invented fixture')
            self.assertEqual(read_run(new)[2]['civic_snapshot_sha256'],c['content_sha256'])
            answer=answer_civic_question(read_run(new)[2],view='candidates');save_answer(answer,root/'answer');verify_answer(answer)
            self.assertIn('profile_id',(root/'answer'/'paths.tsv').read_text())
            for name in ['civic_snapshot.json','civic_report.json','civic_overlap.json','source_licenses.json']:
                self.assertTrue((new/name).exists())
            with redirect_stdout(StringIO()):
                self.assertEqual(main(['therapy-question','--run',str(output),'--view','candidates','--out',str(root/'cli_answer')]),0)
            self.assertTrue((root/'cli_answer'/'question.json').exists())
            self.assertEqual(json.loads((source/'snapshot.json').read_text()),p)


if __name__=='__main__':unittest.main()
