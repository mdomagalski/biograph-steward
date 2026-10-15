"""Invented graph fixtures check scope, path acceptance, citations and exports."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.assertions import new_review_event
from biograph_steward.client import PharosClient, digest
from biograph_steward.graph import build_graph, save_run
from biograph_steward.questions import answer_question, graph_basis, save_answer, verify_answer, answer_html, resolve_protein
from biograph_steward.__main__ import main
from test_starter import MockAPI


def fixture():
    s=PharosClient(transport=MockAPI(4)).build_snapshot('Test disease')
    def pathway(i):return {'pwid':i,'name':f'Invented pathway {i}','type':'Reactome','sourceID':f'R-HSA-{i}'}
    for i,t in enumerate(s['targets']):
        t['pathways']=[pathway(1),pathway(2)] if i<3 else []
        t['pharos_context']={'metadata':{},'ppis':[]}
    s['targets'][1]['pharos_context']['ppis']=[{'nid':1,'type':'TEST','props':[{'name':'Score','value':'0.8'}],
                                               'target':{'uniprot':'P04637','sym':'TEST_0'}}]
    s['targets'][3]['pharos_context']['ppis']=[{'nid':1,'type':'TEST','target':{'uniprot':'P04637','sym':'TEST_0'}}]
    s['targets'][2]['diseaseAssociationDetails'][0]['name']='Another disease'
    s.pop('content_sha256');s['content_sha256']=digest(s)
    return s


def review(s, ids, state='accepted'):
    events=[];g=build_graph(s)
    for aid in ids:
        events.append(new_review_event(g,aid,state,'Software test','Invented fixture only'))
        g=build_graph(s,events)
    return g


class QuestionTests(unittest.TestCase):
    def setUp(self):self.s=fixture();self.g=build_graph(self.s)

    def test_default_accepted_view_does_not_promote_candidate_paths(self):
        a=answer_question(self.g,'P04637')
        self.assertFalse(a['results']);self.assertFalse(a['citations']);self.assertFalse(a['summary'])
        self.assertEqual(a['availability']['inspectable_proteins'],2)
        self.assertEqual(a['availability']['accepted_proteins'],0)

    def test_exact_disease_and_no_transitive_disease_inference(self):
        a=answer_question(self.g,'P04637',view='candidates')
        self.assertEqual({r['protein']['id'] for r in a['results']},{'UniProtKB:P00533','UniProtKB:P15056'})
        self.assertNotIn('UniProtKB:P01116',{r['protein']['id'] for r in a['results']})
        self.assertTrue(all(p['review_status']=='candidate_evidence' for r in a['results'] for p in r['paths']))
        self.assertTrue(all(c['review_state']=='candidate' for c in a['citations']))
        for r in a['results']:
            for p in r['paths']:
                disease_a=next(x for x in self.g['assertions'] if x['id']==p['assertion_ids'][0])
                self.assertEqual(disease_a['object'],self.g['disease_node_id'])
                self.assertEqual(disease_a['subject'],r['protein']['id'])

    def test_every_summary_sentence_resolves_to_each_path_assertion_and_raw_evidence(self):
        a=answer_question(self.g,'P04637',view='candidates',max_paths=5)
        refs={c['id']:c for c in a['citations']};paths={p['id']:p for r in a['results'] for p in r['paths']}
        for sentence in a['summary']:
            p=paths[sentence['path_id']]
            self.assertEqual([refs[c]['assertion_id'] for c in sentence['citation_ids']],p['assertion_ids'])
            for cid in sentence['citation_ids']:
                c=refs[cid];self.assertTrue(c['evidence_records'])
                self.assertTrue(all(e['record_locators'] for e in c['evidence_records']))
                self.assertEqual(c['used_evidence_edge_ids'],[e['id'] for e in c['evidence_records']])

    def test_whole_path_must_be_accepted(self):
        paths=answer_question(self.g,'P04637',view='candidates',relations=['interactions'])['results']
        target=next(r for r in paths if r['protein']['id']=='UniProtKB:P00533')['paths'][0]
        g=review(self.s,target['assertion_ids'][:1]);self.assertFalse(answer_question(g,'P04637')['results'])
        g=review(self.s,target['assertion_ids']);a=answer_question(g,'P04637')
        self.assertEqual(a['returned_proteins'],1)
        self.assertTrue(all(c['review_state']=='accepted' for c in a['citations']))
        self.assertEqual(a['results'][0]['paths'][0]['kind'],'interaction')

    def test_focal_disease_association_is_not_required_or_fabricated(self):
        initial=answer_question(self.g,'P04637',view='candidates',relations=['interactions'])
        p=initial['results'][0]['paths'][0];g=review(self.s,p['assertion_ids'])
        focal=[a for a in g['assertions'] if a['subject']=='UniProtKB:P04637' and a['kind']=='disease_association'][0]
        self.assertEqual(focal['lifecycle_state'],'candidate')
        answer=answer_question(g,'P04637')
        self.assertNotIn(focal['id'],{c['assertion_id'] for c in answer['citations']})
        self.assertEqual(answer['returned_proteins'],1)

    def test_shared_path_requires_all_three_assertions(self):
        p=answer_question(self.g,'P04637',view='candidates',relations=['shared_pathways'])['results'][0]['paths'][0]
        self.assertEqual(len(p['assertion_ids']),3)
        g=review(self.s,p['assertion_ids'][:2]);self.assertFalse(answer_question(g,'P04637',relations=['shared_pathways'])['results'])
        g=review(self.s,p['assertion_ids']);self.assertEqual(answer_question(g,'P04637',relations=['shared_pathways'])['returned_proteins'],1)

    def test_rejected_and_obsolete_paths_never_appear_in_candidate_answers(self):
        p=answer_question(self.g,'P04637',view='candidates',relations=['interactions'])['results'][0]['paths'][0]
        g=review(self.s,[p['assertion_ids'][1]],state='rejected')
        self.assertNotIn(p['id'],{p['id'] for r in answer_question(g,'P04637',view='candidates')['results'] for p in r['paths']})
        events=[];g=build_graph(self.s)
        for state in ['accepted','obsolete']:
            events.append(new_review_event(g,p['assertion_ids'][1],state,'Tester','Test'));g=build_graph(self.s,events)
        self.assertNotIn(p['id'],{p['id'] for r in answer_question(g,'P04637',view='candidates')['results'] for p in r['paths']})

    def test_limits_and_order_are_explicit_and_deterministic(self):
        a=answer_question(self.g,'P04637',view='candidates',max_results=1,max_paths=1)
        self.assertEqual(a['matching_proteins'],2);self.assertEqual(a['returned_proteins'],1)
        self.assertEqual(a['omitted_proteins'],1)
        r=a['results'][0];self.assertEqual(r['protein']['sym'],'TEST_1')
        self.assertEqual(r['eligible_path_count'],3);self.assertEqual(r['omitted_paths'],2)
        self.assertEqual(r['paths'][0]['kind'],'interaction')
        self.assertEqual(a,answer_question(self.g,'P04637',view='candidates',max_results=1,max_paths=1))

    def test_one_relationship_question_text_matches_scope(self):
        a=answer_question(self.g,'P04637',relations=['interactions'],view='candidates')
        self.assertNotIn('shared pathway',a['question'])
        self.assertTrue(all(p['kind']=='interaction' for r in a['results'] for p in r['paths']))

    def test_unmapped_or_malformed_disease_evidence_cannot_form_paths(self):
        s=deepcopy(self.s);s['targets'][1]['diseaseAssociationDetails'][0]['name']=None
        s.pop('content_sha256');s['content_sha256']=digest(s)
        a=answer_question(build_graph(s),'P04637',view='candidates')
        self.assertNotIn('UniProtKB:P00533',{r['protein']['id'] for r in a['results']})

    def test_preview_coverage_does_not_claim_complete_search(self):
        a=answer_question(self.g,'P04637',view='candidates')
        self.assertTrue(any('unavailable' in gap for gap in a['limitations']))
        self.assertIsNone(a['plan']['selected_coverage']['pathways'])
        self.assertIsNone(a['plan']['selected_coverage']['ppis'])

    def test_unknown_count_coverage_and_source_time_remain_explicit(self):
        g=deepcopy(self.g);g['retrieval']['context']={'summary':{'pathways':{'target_statuses':{'exhausted':4},'available':None}}}
        a=answer_question(g,'P04637',relations=['shared_pathways'],view='candidates')
        self.assertTrue(any('not count-verified' in gap for gap in a['limitations']))
        self.assertEqual(a['snapshot_created_at'],g['snapshot_created_at'])
        self.assertEqual(a['database_version'],g['db_version'])

    def test_context_qualified_memberships_are_not_generalized(self):
        g=deepcopy(self.g)
        for a in g['assertions']:
            if a['kind']=='pathway_membership' and a['subject']=='UniProtKB:P00533':a['qualifiers']['tissue']='UBERON:test'
        a=answer_question(g,'P04637',view='candidates',relations=['shared_pathways'])
        self.assertFalse(a['results'])

    def test_ambiguous_symbols_and_outside_proteins_require_explicit_choices(self):
        g=deepcopy(self.g);g['targets'][1]['symbol']=g['targets'][0]['symbol']
        with self.assertRaisesRegex(ValueError,'Ambiguous'):resolve_protein(g,'TEST_0')
        self.assertEqual(resolve_protein(g,'P04637'),'UniProtKB:P04637')
        with self.assertRaisesRegex(ValueError,'outside'):answer_question(g,'outside')

    def test_invalid_and_unsupported_scope_is_rejected(self):
        for kwargs in [{'relations':[]},{'relations':['resistance']},{'view':'all'}, {'max_results':True},
                       {'max_results':31},{'max_paths':0},{'template':'clinical_response'}]:
            with self.assertRaises(ValueError):answer_question(self.g,'P04637',**kwargs)

    def test_trace_basis_tracks_reviews_without_changing_snapshot(self):
        a=answer_question(self.g,'P04637',view='candidates')
        g=review(self.s,[a['results'][0]['paths'][0]['assertion_ids'][0]])
        b=answer_question(g,'P04637',view='candidates')
        self.assertEqual(a['snapshot_sha256'],b['snapshot_sha256'])
        self.assertNotEqual(a['graph_basis_sha256'],b['graph_basis_sha256'])
        self.assertNotEqual(a['answer_sha256'],b['answer_sha256'])
        self.assertEqual(self.g['question_basis_sha256'],graph_basis(self.g))

    def test_export_integrity_overwrite_protection_and_html_escaping(self):
        g=deepcopy(self.g);g['disease']['name']='</h1><script>bad</script>'
        # Disease mismatches correctly make the answer empty; the question itself must still be escaped.
        a=answer_question(g,'P04637',view='candidates')
        self.assertNotIn('<script>bad</script>',answer_html(a))
        self.assertIn('&lt;script&gt;',answer_html(a))
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'answer';save_answer(a,out)
            self.assertEqual(json.loads((out/'question.json').read_text()),a)
            for name in ['summary.txt','report.html','paths.tsv']:self.assertTrue((out/name).exists())
            with self.assertRaises(ValueError):save_answer(a,out)
        a['overview']='modified'
        with self.assertRaisesRegex(ValueError,'integrity'):verify_answer(a)

    def test_query_does_not_modify_graph_and_cli_matches(self):
        before=deepcopy(self.g);expected=answer_question(self.g,'P04637',view='candidates',source_run='source')
        self.assertEqual(self.g,before)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);save_run(self.s,root/'source')
            with redirect_stdout(StringIO()):
                self.assertEqual(main(['question','--run',str(root/'source'),'--protein','P04637','--view','candidates','--out',str(root/'q')]),0)
            self.assertEqual(json.loads((root/'q/question.json').read_text()),expected)

if __name__=='__main__':unittest.main()
