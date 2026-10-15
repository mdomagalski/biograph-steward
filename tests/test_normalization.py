"""Scientific meaning, duplication and provenance boundaries for context adapters."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from biograph_steward.assertions import assertion_identity, new_review_event
from biograph_steward.client import digest
from biograph_steward.graph import build_graph, save_run
from biograph_steward.reviews import review_run
from test_retrieval import ContextAPI
from biograph_steward.client import PharosClient


def fixture():
    s = PharosClient(transport=ContextAPI()).build_snapshot('Test disease', profile='scoped', tissue_term='colon rectum')
    # Two views of the same association, plus a repeated identical source row.
    s['targets'][0]['pharos_context']['ppis'] = [
        {'nid':2,'type':'STRINGDB,Reactome','props':[{'name':'Score','value':'0.9'}],
         'target':{'uniprot':'P00533','sym':'TEST_1'}},
        {'nid':2,'type':'STRINGDB,Reactome','props':[{'name':'Score','value':'0.9'}],
         'target':{'uniprot':'P00533','sym':'TEST_1'}}]
    s['targets'][1]['pharos_context']['ppis'] = [
        {'nid':1,'type':'Reactome,STRINGDB','props':[{'name':'Score','value':'0.8'}],
         'target':{'uniprot':'P04637','sym':'TEST_0'}}]
    s['targets'][0]['pharos_context']['expressions'] = [
        {'expid':1,'type':'TEST Protein','tissue':'colon - endothelial cells', 'value':None,'qual':'Not detected',
         'uberon':{'uid':'UBERON:0001155','name':'colon'}},
        {'expid':2,'type':'TEST Protein','tissue':'colon - glandular cells', 'value':None,'qual':'High',
         'uberon':{'uid':'UBERON:0001155','name':'colon'}},
        {'expid':3,'type':'TEST RNA','tissue':'colon', 'value':'0','qual':None,
         'uberon':{'uid':'UBERON:0001155','name':'colon'},'pub':{'pmid':999}}]
    return resign(s)


def resign(s):
    s.pop('content_sha256',None);s['content_sha256']=digest(s);return s


def by_kind(g, kind):
    return [a for a in g['assertions'] if a['kind']==kind]


class NormalizationTests(unittest.TestCase):
    def test_reciprocal_and_exact_duplicates_do_not_inflate_claims(self):
        g=build_graph(fixture());a=by_kind(g,'protein_interaction')[0]
        self.assertEqual(len(by_kind(g,'protein_interaction')),1)
        self.assertLess(a['subject'],a['object'])
        self.assertTrue(a['symmetric'])
        self.assertEqual(a['source_record_count'],3)
        self.assertEqual(len(a['evidence_edge_ids']),1)
        self.assertIsNone(a['independent_evidence_count'])
        e=next(e for e in g['edges'] if e['id'] in a['evidence_edge_ids'])
        self.assertEqual(len(e['record_locators']),3)
        self.assertEqual(e['reciprocal_views_collapsed'],1)
        self.assertEqual(a['source_names'],['Reactome','STRINGDB'])
        scores=e['source_scores_raw']['properties_by_view']
        self.assertEqual({p['properties'][0]['value'] for p in scores},{'0.9','0.8'})
        self.assertNotIn('confidence_probability',e)
        self.assertEqual(g['normalization']['families']['ppis']['exact_duplicate_rows_grouped'],1)

    def test_reordering_or_reversing_views_keeps_claim_identity_and_revision(self):
        s=fixture();g=build_graph(s);s['targets'].reverse()
        for t in s['targets']:
            for values in t['pharos_context'].values():
                if isinstance(values,list):values.reverse()
        other=build_graph(resign(s))
        before=by_kind(g,'protein_interaction')[0];after=by_kind(other,'protein_interaction')[0]
        self.assertEqual(before['id'],after['id'])
        self.assertEqual(before['revision'],after['revision'])

    def test_changed_score_changes_evidence_revision_but_not_claim_identity(self):
        s=fixture();a=by_kind(build_graph(s),'protein_interaction')[0]
        s['targets'][1]['pharos_context']['ppis'][0]['props'][0]['value']='0.2'
        b=by_kind(build_graph(resign(s)),'protein_interaction')[0]
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['revision'],b['revision'])

    def test_go_is_annotation_not_inferred_positive_function_or_disease(self):
        g=build_graph(fixture());a=by_kind(g,'go_annotation')[0]
        self.assertEqual(a['predicate'],'biograph:has_go_annotation')
        self.assertEqual(a['object'],'GO:0000001')
        self.assertEqual(a['qualifiers']['go_aspect'],'P')
        self.assertIsNone(a['qualifiers']['disease'])
        self.assertNotIn('positive',a['qualifiers'].values())
        e=next(e for e in g['edges'] if e['id'] in a['evidence_edge_ids'])
        self.assertEqual(e['evidence_raw'],'IEA')
        self.assertIsNone(e['annotation_context']['relation'])
        self.assertIsNone(e['annotation_context']['negated'])
        self.assertEqual(e['evidence_record']['assigned_by'],'TEST')

    def test_multiple_go_sources_share_annotation_without_independence_claim(self):
        s=fixture();go=s['targets'][0]['pharos_context']['go'][0]
        s['targets'][0]['pharos_context']['go'].extend([deepcopy(go),{**go,'assigned_by':'SECOND','evidence':'IDA'}])
        g=build_graph(resign(s));a=by_kind(g,'go_annotation')[0]
        self.assertEqual(a['source_record_count'],3)
        self.assertEqual(len(a['evidence_edge_ids']),2)
        self.assertIsNone(a['independent_evidence_count'])

    def test_absence_zero_cells_and_assays_are_kept_separate(self):
        g=build_graph(fixture());assertions=by_kind(g,'expression_observation')
        self.assertEqual(len(assertions),3)
        self.assertEqual({a['object'] for a in assertions},{'UBERON:0001155'})
        self.assertEqual(len({a['id'] for a in assertions}),3)
        edges=[e for e in g['edges'] if e['record_kind']=='expression_observation']
        self.assertTrue(any(e['observation']['qualitative_raw']=='Not detected' for e in edges))
        zero=next(e for e in edges if e['observation']['value_raw']=='0')
        self.assertIsNone(zero['observation']['unit'])
        self.assertEqual(zero['publications'],['PMID:999'])
        self.assertTrue(all(e['predicate']!='biolink:expressed_in' for e in edges))
        self.assertTrue(all(a['qualifiers']['disease'] is None for a in assertions))
        self.assertTrue(all(a['qualifiers']['species'] is None for a in assertions))

    def test_drugs_keep_local_ids_without_treatment_or_binding_inference(self):
        g=build_graph(fixture());a=by_kind(g,'drug_listing')[0]
        self.assertTrue(a['object'].startswith('pharos.ligand:'))
        self.assertEqual(a['predicate'],'biograph:has_drug_listing')
        self.assertIsNone(a['qualifiers']['therapy']);self.assertIsNone(a['qualifiers']['response'])
        self.assertNotIn('accepted',a['allowed_transitions'])

    def test_discovery_pmids_are_never_copied_to_go_ppi_drug_or_disease_evidence(self):
        g=build_graph(fixture())
        self.assertTrue(all(not a['publications'] for a in g['assertions'] if a['kind']!='expression_observation'))
        self.assertTrue(all(r['normalization_status']=='discovery_only' and not r['assertion_ids']
                            for r in g['context_records'] if r['family']=='publications'))
        self.assertFalse(any(n['id'].startswith('PMID:') for n in g['nodes']))

    def test_invalid_context_is_quarantined_without_outside_nodes(self):
        s=fixture();c=s['targets'][0]['pharos_context']
        c['go'].extend([None,{'goid':'GO:no','type':'P','term':'invalid'}])
        c['ppis'].append({'type':'STRINGDB','target':{'uniprot':'P01116'}})
        c['drugs'].append({'ligid':'x','name':'not confirmed','isdrug':False})
        c['expressions'].extend([{'expid':4,'tissue':'colon','type':'TEST','value':None,'qual':None},
                                 {'expid':True,'tissue':'colon','type':'TEST','value':'2'}])
        g=build_graph(resign(s))
        reasons={q['reason'] for q in g['quarantine']}
        self.assertTrue({'malformed_context_record','invalid_go_identifier_aspect_or_term',
                         'interaction_partner_outside_selected_cohort','invalid_or_unconfirmed_drug_listing',
                         'expression_measurement_missing','expression_identifier_tissue_or_assay_missing'}<=reasons)
        self.assertNotIn('UniProtKB:P01116',{n['id'] for n in g['nodes']})

    def test_malformed_context_containers_and_null_target_ids_are_accounted_for(self):
        for broken in [None,{'go':None}]:
            s=fixture();s['targets'][0]['pharos_context']=broken
            g=build_graph(resign(s))
            self.assertTrue(any(q['reason'] in {'malformed_pharos_context','malformed_context_list'} for q in g['quarantine']))
        s=fixture();s['targets'][0]['uniprot']=None
        g=build_graph(resign(s))
        self.assertTrue(any(q['reason']=='context_subject_not_a_valid_seed_protein' for q in g['quarantine']))

    def test_blank_expression_value_is_not_a_measurement(self):
        s=fixture();r=s['targets'][0]['pharos_context']['expressions'][2];r['value']='  '
        g=build_graph(resign(s))
        self.assertEqual(len(by_kind(g,'expression_observation')),2)
        self.assertTrue(any(q['reason']=='expression_measurement_missing' for q in g['quarantine']))

    def test_repeated_target_rows_do_not_duplicate_context_ids_or_claims(self):
        s=fixture();before=build_graph(s)
        s['targets'].append(deepcopy(s['targets'][0]))
        after=build_graph(resign(s))
        self.assertEqual(len(after['context_records']),len(before['context_records']))
        self.assertEqual(len({r['id'] for r in after['context_records']}),len(after['context_records']))
        self.assertEqual({a['id'] for a in after['assertions']},{a['id'] for a in before['assertions']})
        self.assertEqual(after['summary']['duplicate_target_records'],1)
        self.assertGreater(after['normalization']['families']['go']['exact_duplicate_rows_grouped'],0)

    def test_conflicting_go_aspects_are_quarantined(self):
        s=fixture();r=s['targets'][0]['pharos_context']['go'][0]
        s['targets'][0]['pharos_context']['go'].append({**r,'type':'C'})
        g=build_graph(resign(s));self.assertFalse(by_kind(g,'go_annotation'))
        self.assertEqual(sum(q['reason']=='conflicting_go_aspects' for q in g['quarantine']),2)

    def test_unmapped_tissue_is_explicit_and_not_autoaccepted(self):
        s=fixture();s['targets'][0]['pharos_context']['expressions'][0]['uberon']=None
        a=next(a for a in by_kind(build_graph(resign(s)),'expression_observation')
               if a['qualifiers']['observation_id']=='pharos.expression:1')
        self.assertTrue(a['object'].startswith('biograph.tissue:'))
        self.assertNotIn('accepted',a['allowed_transitions'])

    def test_source_response_rows_and_original_times_are_resolvable(self):
        s=PharosClient(transport=ContextAPI()).build_snapshot('Test disease',profile='scoped',tissue_term='colon rectum')
        g=build_graph(s)
        for entry in g['context_records']:
            self.assertTrue(entry['source_response_locators'])
            for location in entry['source_response_locators']:
                envelope=s['requests'][location['request_index']]
                raw=envelope['response']
                for part in location['response_pointer'].strip('/').split('/'):
                    raw=raw[int(part)] if isinstance(raw,list) else raw[part]
                self.assertEqual(raw,entry['record'])
                self.assertEqual(location['retrieved_at'],envelope['retrieved_at'])
                self.assertEqual(location['response_sha256'],envelope['response_sha256'])

    def test_legacy_claim_identity_and_reviews_remain_compatible(self):
        from biograph_steward.demo import demo_snapshot
        s=demo_snapshot();g=build_graph(s)
        a=next(a for a in g['assertions'] if a['structurally_usable_evidence_ids'])
        old={'subject':a['subject'],'predicate':a['predicate'],'object':a['object'],'kind':a['kind'],
             'qualifiers':{k:a['qualifiers'][k] for k in ('disease','variant','therapy','species','tissue','cell_line','response')}}
        self.assertEqual(a['id'],'assertion:'+digest(old)[:24])
        event=new_review_event(g,a['id'],'accepted','Tester','Reviewed fixture')
        reviewed=build_graph(s,[event])
        self.assertEqual(reviewed['assertion_summary']['lifecycle_counts']['accepted'],1)

    def test_new_qualifiers_change_identity_and_legacy_nulls_do_not(self):
        base=assertion_identity('p','r','o','k',{})
        self.assertEqual(base,assertion_identity('p','r','o','k',{'assay':None}))
        self.assertNotEqual(base,assertion_identity('p','r','o','k',{'assay':'RNA'}))
        with self.assertRaises(ValueError):assertion_identity('p','r','o','k',{'measurement_value':0})

    def test_source_context_maps_to_edges_and_assertions_with_valid_locators(self):
        s=fixture();before=deepcopy(s);g=build_graph(s)
        self.assertEqual(s,before)
        for entry in g['context_records']:
            for eid in entry['normalized_evidence_edge_ids']:
                e=next(e for e in g['edges'] if e['id']==eid)
                self.assertIn(entry['id'],e['context_record_ids'])
                self.assertIn(e['assertion_id'],entry['assertion_ids'])
                for path in e['record_locators']:
                    value=s
                    for part in path.split('#/')[1].split('/'):
                        value=value[int(part)] if isinstance(value,list) else value[part]
                    self.assertIsNotNone(value)
        self.assertTrue(all(a['lifecycle_state']=='candidate' for a in g['assertions']))

    def test_review_and_replay_preserve_new_assertions_and_exports(self):
        s=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);g=save_run(s,p/'source');a=by_kind(g,'protein_interaction')[0]
            reviewed=review_run(p/'source',p/'reviewed',a['id'],'accepted','Tester','Checked both endpoint views')
            other=save_run(s,p/'replayed',review_events=reviewed['review_events'])
            self.assertEqual(reviewed,other)
            self.assertEqual(json.loads((p/'source/normalization_report.json').read_text()),g['normalization'])
            self.assertEqual(reviewed['benchmark_readiness']['counts']['reviewed_positive_labels'],0)
            self.assertTrue(all(x in (p/'source/edges.tsv').read_text() for x in ['context_record_ids','observation','source_record_count']))

if __name__=='__main__':unittest.main()
