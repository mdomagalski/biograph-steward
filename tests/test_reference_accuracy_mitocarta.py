"""Invented examples only; no author or project outcomes are opened by tests."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.file_utils import sha
from tools.reference_accuracy import mitocarta as m


def native(**updates):
    row = {'subject': 'UniProtKB:P00001', 'go_id': 'GO:0000001', 'aspect': 'C',
        'relation_literal': 'located_in', 'negated': False, 'evidence_code': 'IDA',
        'taxon_ids': ['taxon:9606'], 'gene_product_form_id': 'UniProtKB:P00001',
        'annotation_extension_raw': '', 'with_from_raw': ''}
    row.update(updates); return row


def graph(subject='UniProtKB:P00001', term='GO:0000001'):
    return {'edges': [{'subject': subject, 'object': term, 'record_kind': 'go_annotation',
        'aggregator': 'Pharos', 'evidence_record': {'goid': term, 'type': 'C'}}]}


class InventoryTests(unittest.TestCase):
    def test_unlisted_and_old_negative_training_flags_stay_unknown(self):
        rows = [{'HumanGeneID': 1., 'MitoCarta3.0_List': 'MitoCarta3.0'},
                {'HumanGeneID': 2., 'MitoCarta3.0_List': 'mito-interacting'},
                {'HumanGeneID': 3., 'MitoCarta3.0_List': 0., 'TrainingDataset': 'Tnon_mito'},
                {'HumanGeneID': 'ENSG0001', 'MitoCarta3.0_List': 'MitoCarta3.0'}]
        labels = m.author_labels(rows)
        self.assertEqual({k:v['label'] for k,v in labels.items()}, {'1':1, '2':0, '3':None})
        self.assertNotIn('ENSG0001', labels)

    def test_duplicate_gene_requires_adjudication(self):
        with self.assertRaisesRegex(ValueError, 'duplicate author GeneID'):
            m.author_labels([{'HumanGeneID': 1., 'MitoCarta3.0_List': x} for x in ['MitoCarta3.0', 0.]])

    def test_canonical_form_allowed_distinct_forms_and_context_excluded(self):
        subjects = {'UniProtKB:P00001'}; closure={'GO:0000001'}
        for form in (None, '', 'UniProtKB:P00001'):
            rows, _ = m.native_predictions([native(gene_product_form_id=form)], subjects, closure, closure, experimental=True)
            self.assertEqual(rows['UniProtKB:P00001']['prediction'], 1)
        for changes in ({'gene_product_form_id':'UniProtKB:P00001-2'}, {'annotation_extension_raw':'part_of(CL:0001)'},
                        {'with_from_raw':'GO_REF:001'}, {'negated':True}, {'relation_literal':'colocalizes_with'},
                        {'relation_literal':'is_active_in'}, {'taxon_ids':['taxon:9606','taxon:10090']}):
            rows, _ = m.native_predictions([native(**changes)], subjects, closure, closure, experimental=True)
            self.assertEqual(rows['UniProtKB:P00001']['prediction'], 0, changes)

    def test_all_evidence_vs_experimental_and_missing_source(self):
        subjects = {'UniProtKB:P00001','UniProtKB:P00002'}; closure={'GO:0000001'}
        all_, _ = m.native_predictions([native(evidence_code='IEA')], subjects, closure, closure, experimental=False)
        exp, _ = m.native_predictions([native(evidence_code='IEA')], subjects, closure, closure, experimental=True)
        self.assertEqual(all_['UniProtKB:P00001']['prediction'], 1)
        self.assertEqual(exp['UniProtKB:P00001']['prediction'], 0)
        self.assertIsNone(all_['UniProtKB:P00002']['prediction'])

    def test_partial_source_and_unknown_terms_are_not_biological_negatives(self):
        p='UniProtKB:P00001'
        pred=m.graph_predictions(graph(term='GO:9999999'), {p}, {p:False}, {'GO:0000001'}, {'GO:0000001'})
        self.assertIsNone(pred[p]['prediction']); self.assertEqual(pred[p]['unrecognized_CC_term_rows'],1)
        self.assertEqual(m.gene_or([0,None]),None)
        self.assertEqual(m.gene_or([1,None]),1)
        self.assertEqual(m.gene_or([0,0]),0)

    def test_closure_uses_only_declared_is_a_and_part_of(self):
        root='GO:0005739'
        ids=[root,'GO:0000001','GO:0000002','GO:0000003','GO:0003674','GO:0005575','GO:0008150']
        iri=lambda s:m.GO_IRI+s[3:]
        content={'graphs':[{'id':'http://purl.obolibrary.org/obo/go.owl',
            'meta':{'version':'http://purl.obolibrary.org/obo/go/releases/2026-07-26/go.owl'},
            'nodes':[{'id':iri(s),'type':'CLASS'} for s in ids],
            'edges':[{'sub':iri('GO:0000001'),'obj':iri(root),'pred':'is_a'},
                     {'sub':iri('GO:0000002'),'obj':iri('GO:0000001'),'pred':m.PART_OF},
                     {'sub':iri('GO:0000003'),'obj':iri(root),'pred':'http://purl.obolibrary.org/obo/RO_0002211'}]}]}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'go.json.gz';p.write_bytes(gzip.compress(json.dumps(content).encode()))
            closure,*_=m.mitochondrial_terms(p,sha(p),root)
        self.assertEqual(closure,{root,'GO:0000001','GO:0000002'})

    def test_metrics_keep_abstention_and_single_class_undefined(self):
        r=m.binary_metrics([(1,1),(1,0),(0,1),(0,0),(1,None)])
        self.assertEqual([r[x] for x in ['TP','FN','FP','TN','abstain']],[1,1,1,1,1])
        self.assertEqual(r['precision'],.5);self.assertEqual(r['balanced_accuracy'],.5);self.assertEqual(r['MCC'],0.)
        one=m.binary_metrics([(1,1)])
        self.assertIsNone(one['balanced_accuracy']);self.assertIsNone(one['MCC'])
        empty=m.binary_metrics([]);self.assertIsNone(empty['precision']);self.assertIsNone(empty['accuracy'])

    def test_gene_unit_or_and_coverage_extension_not_scored(self):
        pids=['UniProtKB:P00001','UniProtKB:P00002','UniProtKB:P00003']
        es={'rows':[{'protein_id':p,'gene_id':str(i//2+1),'primary_source_eligible':i<2,
            'primary_target':i<2,'reviewed_canonical_identity_eligible':True} for i,p in enumerate(pids)]}
        preds={a:{p:{'prediction':i%2} for i,p in enumerate(pids[:2])} for a in m.ARMS}
        report,cases=m.assess(es,preds,{'1':{'label':1,'author_category':'MitoCarta3.0'},'2':{'label':0,'author_category':'mito-interacting'}})
        self.assertEqual(len(cases),1);self.assertEqual(cases[0]['predictions']['A_raw_Pharos'],1)
        self.assertEqual(report['coverage']['all_workspace_protein_nodes_coverage_only']['protein_nodes'],3)
        self.assertEqual(report['metrics']['A_raw_Pharos']['gold_known'],1)

    def test_exact_paired_test_requires_two_classes_and_information(self):
        rows=[{'gold':i%2,'predictions':{'a':1-i%2,'b':i%2}} for i in range(6)]
        self.assertEqual(m.paired_correctness(rows,'a','b')['exact_McNemar_two_sided_p'],.03125)
        self.assertIsNone(m.paired_correctness(rows[:5],'a','b')['exact_McNemar_two_sided_p'])
        self.assertIsNone(m.paired_correctness([{'gold':1,'predictions':{'a':0,'b':1}}]*6,'a','b')['exact_McNemar_two_sided_p'])

    def test_pin_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'a';p.write_text('data');q=Path(folder)/'b';q.symlink_to(p)
            with self.assertRaises(ValueError):m.pinned(q,sha(p))


class RunBoundaryTests(unittest.TestCase):
    def fixture(self, root):
        source=root/'source';source.mkdir();context=root/'context';context.mkdir()
        original=source/'original.json';original.write_text(json.dumps(graph()))
        retained=source/'current.json';retained.write_bytes(original.read_bytes())
        ontology=source/'ontology';ontology.write_text('invented ontology')
        gaf=source/'gaf';gaf.write_text('invented GAF')
        workbook=source/'author.xls';workbook.write_text('invented workbook')
        (context/'go_context_qualification.json').write_text('invented context')
        p='UniProtKB:P00001'
        es={'primary_unique_gene_units':1,'primary_source_eligible':1,
            'rows':[{'protein_id':p,'gene_id':'1','primary_source_eligible':True,'primary_target':True,
                     'reviewed_canonical_identity_eligible':True,'Pharos_GO_documented_complete':True}],
            'input_pins':{k:{'file':str(v),'sha256':sha(v)} for k,v in
                          [('original_graph',original),('current_graph',retained),('ontology',ontology),('native_GAF',gaf)]}}
        ep=source/'eligible.json';ep.write_text(json.dumps(es))
        contract={'format':'biograph-steward.mitocarta-bounded-reference-frozen-contract.v1',
            'status':'frozen_before_cohort_label_join','arms':dict.fromkeys(m.ARMS,''),
            'source_eligibility':{'file':ep.name,'sha256':sha(ep),'eligible_primary_gene_units':1,'eligible_primary_proteins':1},
            'ontology':{'file':str(ontology),'sha256':sha(ontology),'root':'GO:0005739'},
            'author_reference':{'file':workbook.name,'sha256':sha(workbook)}}
        cp=source/'contract.json';cp.write_text(json.dumps(contract))
        report={'source':{'gaf_sha256':sha(gaf)},'source_graph_file_sha256':sha(original)}
        return cp,context,original,report

    def test_seal_precedes_first_outcome_read_and_source_change_rejects_success(self):
        for mutate in (False,True):
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);cp,ctx,original,nr=self.fixture(root);output=root/'result'
                def labels(*_):
                    seal=json.loads((output/'predictions_before_reference_join.json').read_text())
                    self.assertFalse(seal['cohort_reference_labels_opened']);self.assertFalse(seal['metrics_computed'])
                    if mutate:original.write_text('changed')
                    return {'1':{'label':1,'author_category':'MitoCarta3.0'}}
                with patch.object(m,'mitochondrial_terms',return_value=({'GO:0000001'},{'GO:0000001'},{'GO:0000001'},{})),\
                     patch.object(m,'load_go_context',return_value=(nr,[native()],[])),\
                     patch.object(m,'read_author_workbook',side_effect=labels):
                    if mutate:
                        with self.assertRaisesRegex(ValueError,'byte pin differs'):m.run(cp,sha(cp),ctx,output)
                        self.assertFalse((output/'report.json').exists())
                    else:
                        result=m.run(cp,sha(cp),ctx,output);self.assertEqual(result['primary_gene_gold_positive'],1)
                        self.assertTrue((output/'execution_receipt.json').is_file())


if __name__=='__main__':unittest.main()
