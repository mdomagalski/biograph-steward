"""Invented, source-pinned content notes; no biological reference labels."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest as source_digest
from biograph_steward.function_context import (CONTENT_NOTES, FORMAT, digest, sha,
    load_content_notes, load_publication)
from biograph_steward.go_content_currency import FORMAT as INDEX_FORMAT, literal_flags, project_terms
from tools.go_content_currency.project import prepare
from test_function_context import example


def notes_fixture(manifest, queries, publication_sha):
    old={'present':True,'state':'active','name':'Historical <img src=x>',
         'definition':'Recorded binding definition','namespace':'biological_process',
         'synonyms':[],'parents':[{'predicate':'is_a','object':'GO:0008150'}]}
    new={**deepcopy(old),'name':'Changed comparison label','definition':'Changed definition',
         'parents':[]}
    ids=sorted({c['GO_ID'] for q in queries.values() for c in q['candidates']})
    terms=[{'term_id':uid,'scopes':['invented_source'],'graph_labels':['Unknown vintage'],
            'historical':deepcopy(old),'comparison':deepcopy(new),'flags':literal_flags(old,new),
            'semantic_equivalence_inferred':False,'biological_falsehood_inferred':False,
            'automatic_action':'none'} for uid in ids]
    return {'format':CONTENT_NOTES,'publication_manifest_sha256':publication_sha,
        'publication_content_sha256':manifest['content_sha256'],
        'source_currency_index':{'manifest_file_sha256':'b'*64,'manifest_content_sha256':'c'*64,
            'term_frame_sha256':'d'*64,'term_count':100,'index_file_sha256':'e'*64,
            'historical_ontology_file_sha256':manifest['input_source_pins']['ontology']['sha256'],
            'comparison_ontology_file_sha256':'f'*64},
        'source_versions':{'historical_predictor':'2023-01-01','comparison_snapshot':'2026-07-26',
            'graph_Pharos_GO_vintage':'UNKNOWN','latest_release_claimed':False},
        'queries':{p:[{'GO_ID':c['GO_ID'],'aspect':c['aspect'],'published_score':c['score'],
                      'label':c.get('label')} for c in q['candidates']] for p,q in queries.items()},
        'terms':terms,'scientific_accuracy_claimed':False,'forecast_modified':False,
        'semantic_equivalence_claimed':False,'automatic_mapping_or_pruning':False,'graph_modified':False,
        'limitations':['Literal source qualification; no biological verdict.']}


class ContentNotesTests(unittest.TestCase):
    def setUp(self):
        self.manifest={'content_sha256':'a'*64,'input_source_pins':{'ontology':{'sha256':'1'*64}}}
        self.queries={'UniProtKB:P00533':example()}
        self.report=notes_fixture(self.manifest,self.queries,'2'*64)

    def read(self, report=None):
        value=deepcopy(self.report if report is None else report);value['content_sha256']=digest(value)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'notes.json';path.write_text(json.dumps(value))
            return load_content_notes(path,sha(path),self.manifest,self.queries,manifest_file_sha256='2'*64)

    def test_saved_scope_and_literal_differences_do_not_change_forecasts(self):
        before=deepcopy(self.queries);result=self.read()
        self.assertTrue(result['terms']['GO:0000001']['flags']['definition_text_changed'])
        self.assertEqual(result['terms']['GO:0000001']['historical']['name'],'Historical <img src=x>')
        self.assertEqual(result['source_versions']['comparison_snapshot'],'2026-07-26')
        self.assertFalse(result['forecast_modified']);self.assertEqual(self.queries,before)

    def test_candidate_source_scope_flags_and_raw_body_injection_fail_closed(self):
        mutations=(lambda r:r.update(publication_manifest_sha256='3'*64),
            lambda r:r['queries']['UniProtKB:P00533'][0].update(published_score=.81),
            lambda r:r['source_currency_index'].update(historical_ontology_file_sha256='4'*64),
            lambda r:r['terms'].clear(),lambda r:r['terms'].append(deepcopy(r['terms'][0])),
            lambda r:r['terms'][0]['flags'].update(definition_text_changed=False),
            lambda r:r['terms'][0]['historical'].update(raw_stanza='raw body'),
            lambda r:r['source_versions'].update(latest_release_claimed=True),
            lambda r:r.update(automatic_mapping_or_pruning=True))
        for mutate in mutations:
            report=deepcopy(self.report);mutate(report)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.read(report)

    def test_generic_projection_strips_full_bodies_and_offline_writer_crossbinds_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pub=root/'saved';(pub/'queries').mkdir(parents=True)
            query=pub/'queries/a.json';query.write_text(json.dumps(example()))
            manifest={'format':FORMAT,'publication_id':'demo','source_graph_modified':False,
                'future_reference_labels_included':False,'query_files':{'UniProtKB:P00533':'queries/a.json'},
                'files':{'queries/a.json':{'bytes':query.stat().st_size,'sha256':sha(query)}},
                'input_source_pins':self.manifest['input_source_pins']}
            manifest['content_sha256']=digest(manifest);(pub/'publication.json').write_text(json.dumps(manifest))
            source=root/'index';source.mkdir();term=deepcopy(self.report['terms'][0])
            term['historical']['raw_stanza']='preserved only offline'
            term['comparison']['native_node']={'preserved':'only offline'}
            raw=(json.dumps(term)+'\n').encode();(source/'terms.jsonl.gz').write_bytes(gzip.compress(raw))
            index={'format':INDEX_FORMAT,'source_versions':self.report['source_versions'],
                'term_count':1,'term_frame_sha256':source_digest(['GO:0000001']),
                'semantic_equivalence_claimed':False,'biological_accuracy_measured':False,
                'automatic_graph_or_prediction_changes':False,
                'source_inputs':{'historical':{'file_sha256':'1'*64},'comparison':{'file_sha256':'f'*64}},
                'files':{'terms.jsonl.gz':{'bytes':(source/'terms.jsonl.gz').stat().st_size,'sha256':sha(source/'terms.jsonl.gz')}}}
            index['content_sha256']=source_digest(index);(source/'publication.json').write_text(json.dumps(index))
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result=prepare(source,sha(source/'publication.json'),pub,sha(pub/'publication.json'),root/'notes')
            self.assertNotIn('raw_stanza',result['terms'][0]['historical'])
            self.assertNotIn('native_node',result['terms'][0]['comparison'])
            self.assertEqual(before,{p:p.read_bytes() for p in before})
            with self.assertRaises(ValueError):project_terms(index,{'GO:0000001':term},['GO:9999999'])
            with self.assertRaises(ValueError):project_terms(index,{'GO:0000001':term},['GO:0000001']*2)


if __name__=='__main__':unittest.main()
