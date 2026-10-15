"""Invented benchmark records: hidden labels and provenance must remain separate."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('verification_benchmark',Path(__file__).parents[1]/'scripts'/'prepare_verification_benchmark.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)


class VerificationBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir()
        self.documents=[{'doc_id':1,'title':'INVENTED abstract','abstract':['INVENTED first sentence.','INVENTED second sentence.']},
                        {'doc_id':2,'title':'Other INVENTED abstract','abstract':['No INVENTED relevant finding.']}]
        self.claims=[{'id':1,'claim':'INVENTED test claim.','cited_doc_ids':[1,2],
                      'evidence':{'1':[{'label':'SUPPORT','sentences':[0,1]},{'label':'SUPPORT','sentences':[1]}]}}]
        self.write_sources()
    def tearDown(self):self.tmp.cleanup()
    def write_sources(self):
        for name,data in [('corpus.jsonl',self.documents),('claims_dev.jsonl',self.claims)]:
            (self.source/name).write_text(''.join(json.dumps(r)+'\n' for r in data))
        (self.source/'source_manifest.json').write_text(json.dumps({'source':'INVENTED TEST ONLY','files':{
            name:{'sha256':adapter.sha(self.source/name)} for name in ['corpus.jsonl','claims_dev.jsonl']}}))
    def test_gold_is_separate_and_alternative_rationales_are_not_collapsed(self):
        m=adapter.prepare(self.source,self.root/'prepared')
        inputs=adapter.rows(self.root/'prepared'/'inputs.jsonl');gold=adapter.rows(self.root/'prepared'/'gold.jsonl')
        self.assertEqual(m['claim_abstract_pairs'],2);self.assertEqual(gold[0]['rationale_sets'],[[0,1],[1]])
        self.assertEqual(gold[1]['label'],'NOT_ENOUGH_INFORMATION')
        self.assertNotIn('label',json.dumps(inputs));self.assertNotIn('rationale',json.dumps(inputs))
        self.assertEqual(inputs[0]['document']['sentences'][1]['text'],'INVENTED second sentence.')
    def test_unlabeled_test_or_missing_annotations_never_become_negative_labels(self):
        with self.assertRaises(ValueError):adapter.prepare(self.source,self.root/'test','test')
        self.claims[0].pop('evidence');self.write_sources()
        with self.assertRaisesRegex(ValueError,'Missing expert'):adapter.prepare(self.source,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
    def test_bad_source_bytes_indices_or_conflicting_labels_fail_before_output(self):
        (self.source/'corpus.jsonl').write_text('changed')
        with self.assertRaisesRegex(ValueError,'bytes changed'):adapter.prepare(self.source,self.root/'bytes')
        self.claims[0]['evidence']['1'][0]['sentences']=[99];self.write_sources()
        with self.assertRaisesRegex(ValueError,'indices'):adapter.prepare(self.source,self.root/'index')
        self.claims[0]['evidence']['1'][0]['sentences']=[0]
        self.claims[0]['evidence']['1'][1]['label']='CONTRADICT';self.write_sources()
        with self.assertRaisesRegex(ValueError,'conflicting'):adapter.prepare(self.source,self.root/'labels')
    def test_repeated_output_and_gold_only_citation_additions_are_rejected(self):
        adapter.prepare(self.source,self.root/'prepared')
        with self.assertRaisesRegex(ValueError,'empty benchmark'):adapter.prepare(self.source,self.root/'prepared')
        self.claims[0]['cited_doc_ids']=[2];self.write_sources()
        with self.assertRaisesRegex(ValueError,'oracle'):adapter.prepare(self.source,self.root/'leak')
    def test_repeated_citation_is_counted_once_with_a_recorded_normalization(self):
        self.claims[0]['cited_doc_ids']=[1,1,2];self.write_sources()
        m=adapter.prepare(self.source,self.root/'prepared')
        self.assertEqual(m['claim_abstract_pairs'],2)
        self.assertEqual(m['duplicate_citations'],[{'claim_id':1,'duplicates_collapsed':1}])
    def test_download_reads_only_expected_archive_members_without_extracting_paths(self):
        raw=io.BytesIO()
        with tarfile.open(fileobj=raw,mode='w:gz') as archive:
            for name in ['corpus.jsonl','claims_train.jsonl','claims_dev.jsonl','../../outside']:
                data=b'{}\n';member=tarfile.TarInfo('data/'+name);member.size=len(data)
                archive.addfile(member,io.BytesIO(data))
        with patch.object(adapter,'urlopen',side_effect=[io.BytesIO(raw.getvalue()),io.BytesIO(b'INVENTED TEST LICENSE')]):
            m=adapter.download_source(self.root/'downloaded')
        self.assertEqual(set(m['files']),{'corpus.jsonl','claims_train.jsonl','claims_dev.jsonl'})
        self.assertFalse((self.root/'outside').exists())
        self.assertEqual(m['files']['corpus.jsonl']['sha256'],adapter.sha(self.root/'downloaded'/'corpus.jsonl'))
    def test_document_holdout_excludes_whole_claim_not_only_a_shared_document_pair(self):
        self.claims.append({'id':2,'claim':'Other INVENTED claim.','cited_doc_ids':[2],'evidence':{}});self.write_sources()
        train=self.root/'training';train.mkdir();seen=train/'inputs.jsonl'
        seen.write_text(json.dumps({'id':'train-fixture','document_id':1})+'\n')
        m=adapter.prepare(self.source,self.root/'disjoint',exclude_inputs=seen)
        inputs=adapter.rows(self.root/'disjoint'/'inputs.jsonl')
        self.assertEqual(m['claims'],1);self.assertEqual(m['selection']['excluded_claims'],1)
        self.assertEqual({r['claim_id'] for r in inputs},{2})


if __name__=='__main__':unittest.main()
