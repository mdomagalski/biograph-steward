from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.function_context import (FORMAT,QUERY,digest,sha,validate_query,load_publication, get_query,download_path,list_publications,load_display_notes)
from biograph_steward.function_context import MAX_MANIFEST_BYTES,MAX_QUERY_BYTES


def example():
    return {'format':QUERY,'publication_id':'demo','query':{'id':'UniProtKB:P00533'},
        'state':'ranked_hypotheses','uncalibrated_score':True,'knowledge_level':'prediction','curated_acceptance':False,
        'weighted_degree':1.,'candidates':[{'GO_ID':'GO:0000001','aspect':'BPO','score':.8,'known_in_training_snapshot':False,
            'complete_contributions':True,'contributors':[{'protein':'UniProtKB:P04637','raw_STRING_weight':.8,
                'normalized_contribution':.8,'known_t0_term_row':['P04637','GO:0000001','BPO'],
                'native_STRING_pair':['9606.ENSP0001','9606.ENSP0002'],
                'source_pair':{'subject':'UniProtKB:P00533','object':'UniProtKB:P04637','weight':'.8','pair_id':'pharos319ppi:1:2'}}]}]}


class QueryPublicationTests(unittest.TestCase):
    def fixture(self,p,query_bytes=None):
        (p/'queries').mkdir();f=p/'queries/P00533.json';f.write_bytes(query_bytes if query_bytes is not None else json.dumps(example()).encode())
        m={'format':FORMAT,'publication_id':'demo','source_graph_modified':False,'future_reference_labels_included':False,
            'query_files':{'UniProtKB:P00533':'queries/P00533.json'},'files':{'queries/P00533.json':{'sha256':sha(f),'bytes':f.stat().st_size}}}
        m['content_sha256']=digest(m);(p/'publication.json').write_text(json.dumps(m));return f

    def test_exact_contributor_and_source_identity(self):
        self.assertIs(validate_query(q:=example(),'demo'),q)
        for field,value in [('normalized_contribution',.5),('known_t0_term_row',['P04637','GO:0000002','BPO']),('native_STRING_pair',['bad','9606.ENSP0002'])]:
            bad=deepcopy(q);bad['candidates'][0]['contributors'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate_query(bad,'demo')

    def test_isolate_abstention_and_no_acceptance(self):
        q=example();q.update(weighted_degree=0.,state='no_qualified_neighbor_context',candidates=[])
        validate_query(q,'demo');q['curated_acceptance']=True
        with self.assertRaises(ValueError):validate_query(q,'demo')

    def test_saved_file_hash_tampering_rejected_without_optional_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'queries').mkdir();f=p/'queries/P00533.json';f.write_text(json.dumps(example()))
            m={'format':FORMAT,'publication_id':'demo','source_graph_modified':False,'future_reference_labels_included':False,
                'downloads':{'example':'queries/P00533.json'},
                'query_files':{'UniProtKB:P00533':'queries/P00533.json'},'files':{'queries/P00533.json':{'sha256':sha(f),'bytes':f.stat().st_size}}}
            m['content_sha256']=digest(m);(p/'publication.json').write_text(json.dumps(m));manifest,queries=load_publication(p)
            self.assertEqual(get_query(manifest,queries,'P00533')['query']['id'],'UniProtKB:P00533')
            self.assertEqual(download_path(p,'example'),f)
            self.assertEqual(list_publications([{'id':'demo','path':str(p),'sha256':sha(p/'publication.json')}])[0]['query_count'],1)
            with self.assertRaises(ValueError):get_query(manifest,queries,'P01116')
            with self.assertRaises(ValueError):download_path(p,'../queries/P00533.json')
            f.write_text(f.read_text()+' ')
            with self.assertRaises(ValueError):load_publication(p)

    def test_directory_symlink_cannot_escape_even_with_matching_file_hash(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as outside:
            p=Path(tmp);f=self.fixture(p);external=Path(outside)/f.name;external.write_bytes(f.read_bytes());f.unlink();f.parent.rmdir();(p/'queries').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(ValueError):load_publication(p)

    def test_manifest_and_query_sizes_are_bounded_before_json_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'publication.json').write_bytes(b' '*(MAX_MANIFEST_BYTES+1))
            with self.assertRaisesRegex(ValueError,'manifest exceeds'):load_publication(p)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p,b' '*(MAX_QUERY_BYTES+1))
            with self.assertRaisesRegex(ValueError,'query response exceeds'):load_publication(p)

    def test_malformed_nested_shapes_fail_with_controlled_errors(self):
        bad=[[],None]
        for key,value in [('query',[]),('query',{'id':[]}),('candidates',[[]])]:
            q=example();q[key]=value;bad.append(q)
        for field,value in [('GO_ID',[]),('aspect',[]),('contributors',[[]])]:
            q=example();q['candidates'][0][field]=value;bad.append(q)
        for field,value in [('protein',[]),('source_pair',[]),('native_STRING_pair',[[],None])]:
            q=example();q['candidates'][0]['contributors'][0][field]=value;bad.append(q)
        q=example();q['candidates'][0]['contributors'][0]['source_pair']['subject']=[];bad.append(q)
        q=example();q['candidates'][0]['contributors'][0]['source_pair']['weight']=10**400;bad.append(q)
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_query(value,'demo')


class DisplayNotesTests(unittest.TestCase):
    def fixture(self):
        pin={'bytes':1,'sha256':'a'*64}
        self.manifest={'content_sha256':'c'*64,'source_versions':{'t0_date':'2023-08-14'},
            'input_source_pins':{'ontology':pin}}
        self.queries={'UniProtKB:P00533':example()}
        self.report={'format':'biograph-steward.historical-display-annotation-overlap.v1',
            'publication_manifest_sha256':'b'*64,'publication_content_sha256':'c'*64,
            'scientific_accuracy_claimed':False,'forecast_modified':False,'future_reference_labels_read':False,
            'original_report':{'sha256':'d'*64,'content_sha256':'e'*64},'author_parser':{'future_labels_read':False},
            'inputs':{name:dict(pin) for name in ('baseline_archive','historical_ontology','known_t0','current_gaf','current_ontology')},
            'native_gaf':{'gaf_sha256':'a'*64,'headers':['!gaf-version: 2.2','!date-generated: 2026-07-28 19:42',
                '!go-version: http://purl.obolibrary.org/obo/go/releases/2026-07-26/extensions/go-plus.ofn']},
            'matching_current_ontology':{'file_sha256':'a'*64,'ontology_version':'http://purl.obolibrary.org/obo/go/releases/2026-07-26/go.owl'},
            'current_hierarchy':{'library':'networkx','admitted_predicates':['http://purl.obolibrary.org/obo/BFO_0000050','is_a']},
            'counts':{'candidates':1,'queries':1,'known_t0_literal':0,'known_t0_author_closure':0,
                'all_evidence_status':{'literal_released_row':1},'july2026_positive_literal':0,
                'july2026_positive_ancestor_only':1,'july2026_no_positive_match':0,'july2026_exact_NOT_present':0},
            'rows':[{'query':'UniProtKB:P00533','GO_ID':'GO:0000001','aspect':'BPO','label':None,'published_score':.8,
                'known_t0_literal':False,'known_t0_author_closure':False,
                'pre_t0_all_evidence':{'status':'literal_released_row','literal_source_row':True,'author_admitted':True,'released_target_rows':2},
                'july2026_goa':{'term_in_matching_ontology':True,'term_deprecated':False,'absence_is_biological_negative':False,
                    'exact_NOT_record_ids':[],'positive_matches':[{'native_record_id':'goa.native:'+'f'*24,'source_line':4,
                        'source_term':'GO:0000002','membership':'admitted_ancestor','source_relation':'involved_in','evidence':'IDA',
                        'references':['PMID:1'],'with_from':[],'taxa':['taxon:9606'],'product_form':'UniProtKB:P00533-1',
                        'extension':'','product_form_equals_query_identifier':False,'context_or_form_specific':True,
                        'ontology_path':['GO:0000002','GO:0000001'],'path_predicates':['is_a']}]}}]}

    def read(self,report=None,manifest_sha='b'*64):
        value=deepcopy(self.report if report is None else report);value['content_sha256']=digest(value)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'notes.json';path.write_text(json.dumps(value))
            return load_display_notes(path,sha(path),self.manifest,self.queries,manifest_file_sha256=manifest_sha)

    def setUp(self):self.fixture()

    def test_later_ancestor_and_form_context_survive_without_upgrading_forecast(self):
        notes=self.read();row=notes['queries']['UniProtKB:P00533'][0]
        self.assertEqual(row['july2026_goa']['positive_matches'][0]['product_form'],'UniProtKB:P00533-1')
        self.assertEqual(row['july2026_goa']['positive_matches'][0]['membership'],'admitted_ancestor')
        self.assertEqual(row['pre_t0_all_evidence']['status'],'literal_released_row')
        self.assertFalse(notes['scientific_accuracy_claimed']);self.assertFalse(notes['forecast_modified'])
        self.assertEqual(notes['source_dates']['matching_native_ontology'],'2026-07-26')

    def test_different_or_incomplete_forecasts_and_forged_counts_are_rejected(self):
        with self.assertRaises(ValueError):self.read(manifest_sha='f'*64)
        for mutate in (lambda r:r['rows'].clear(),lambda r:r['rows'].append(deepcopy(r['rows'][0])),
                lambda r:r['rows'][0].update(published_score=.81),lambda r:r['counts'].update(july2026_positive_literal=1)):
            report=deepcopy(self.report);mutate(report)
            with self.subTest(report=report),self.assertRaises(ValueError):self.read(report)

    def test_source_context_polarity_and_release_cannot_be_silently_changed(self):
        for field,value in [('source_relation','NOT'),('context_or_form_specific',False),('path_predicates',['regulates'])]:
            report=deepcopy(self.report);report['rows'][0]['july2026_goa']['positive_matches'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.read(report)
        report=deepcopy(self.report);report['matching_current_ontology']['ontology_version']='http://purl.obolibrary.org/obo/go/releases/2026-01-01/go.owl'
        with self.assertRaises(ValueError):self.read(report)

    def test_sanitized_sources_and_scientific_flags_are_enforced(self):
        report=deepcopy(self.report);report['inputs']['current_gaf']['path']='/private/operator/file'
        with self.assertRaises(ValueError):self.read(report)
        report=deepcopy(self.report);report['scientific_accuracy_claimed']=True
        with self.assertRaises(ValueError):self.read(report)

    def test_populated_canonical_form_is_not_mistaken_for_a_distinct_form_restriction(self):
        for form,extension,same,restricted in [('UniProtKB:P00533','',True,False),
                ('UniProtKB:P00533-1','',False,True),('PR:000012345','',False,True),
                (None,'',None,False),('UniProtKB:P00533','occurs_in(CL:0000000)',True,True)]:
            report=deepcopy(self.report);match=report['rows'][0]['july2026_goa']['positive_matches'][0]
            match.update(product_form=form,extension=extension,product_form_equals_query_identifier=same,
                         context_or_form_specific=restricted)
            with self.subTest(form=form,extension=extension):self.read(report)


if __name__=='__main__':unittest.main()
