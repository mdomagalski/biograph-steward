"""Invented positive-label and phase-boundary fixtures; no real HOU outcomes."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.file_utils import sha
from tools.reference_accuracy import hou as h


def source_maps():
    return {'crosswalk':{'GO:0000001':'a','GO:0000002':'b'},'level1':['a','b'],
        'level2':['c'],'level3':['d'],'level1_to_level2':{'a':'c','b':'c'},
        'level1_to_level3':{'a':'d','b':'d'}}


class PositiveRecoveryTests(unittest.TestCase):
    def test_absent_reference_labels_are_unknown_not_false(self):
        report,_=h.positive_metrics({'p':['a'],'q':['b']},{'p':['a','b'],'q':['b']},['a','b','c'])
        self.assertEqual(report['reference_positive_labels'],2)
        self.assertEqual(report['recovered_reference_positive_labels'],2)
        self.assertEqual(report['extra_predicted_labels_truth_unknown'],1)
        self.assertEqual(report['biological_false_positive_labels_assigned'],0)
        for field in ('precision','F1','MCC','specificity','confidence_interval'):self.assertIsNone(report[field])
        self.assertIsNone(report['per_class']['c']['recall'])

    def test_all_frozen_rows_contribute_and_abstention_stays_explicit(self):
        report,_=h.positive_metrics({'p':['a'],'q':['a','b']},{'p':['a'],'q':None},['a','b'])
        self.assertEqual(report['frozen_protein_rows'],2)
        self.assertEqual(report['reference_positive_labels'],3)
        self.assertEqual(report['micro_positive_reference_recovery'],1/3)
        self.assertEqual(report['macro_per_protein_positive_reference_recovery'],.5)
        self.assertEqual(report['unavailable_source_proteins'],1)
        self.assertEqual(report['available_source_positive_reference_recovery'],1.)
        with self.assertRaisesRegex(ValueError,'complete frozen frame'):
            h.positive_metrics({'p':['a'],'q':['b']},{'p':['a']},['a','b'])

    def test_lossy_main_map_and_guessed_labels_fail(self):
        s=source_maps();q={'qualified_exact_GO_crosswalk':dict(s['crosswalk'])}
        self.assertEqual(h.validate_maps(s,q)[0],s['crosswalk'])
        for bad in ('GO:0016020','GO:0005737','GO:0005634'):
            x=source_maps();x['crosswalk'][bad]='a'
            with self.assertRaisesRegex(ValueError,'lossy generic'):
                h.validate_maps(x,{'qualified_exact_GO_crosswalk':dict(x['crosswalk'])})
        with self.assertRaisesRegex(ValueError,'author-map subset'):
            h.validate_maps(s,{'qualified_exact_GO_crosswalk':{'GO:0000999':'a'}})

    def test_hierarchy_projection_deduplicates_and_preserves_abstention(self):
        self.assertEqual(h.project({'a','b'},source_maps()),{'level1':['a','b'],'level2':['c'],'level3':['d']})
        self.assertEqual(h.project(None,source_maps()),dict.fromkeys(h.LEVELS,None))

    def test_reader_rejects_duplicate_ids_unknown_labels_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'test.csv'
            def write(rows):
                with p.open('w',newline='') as f:
                    w=csv.writer(f);w.writerow(['uniprot_id','ensembl_id','level1','level2','level3','sequence']);w.writerows(rows)
            row=['P00001','ENSG1','a;b','c','d','MSEQUENCE']
            write([row]);r=h.read_test(p,sha(p),source_maps());self.assertEqual(r['UniProtKB:P00001']['level1'],['a','b'])
            write([row,row])
            with self.assertRaisesRegex(ValueError,'duplicate'):h.read_test(p,sha(p),source_maps())
            write([['P00001','ENSG1','not_in_ontology','c','d','MSEQUENCE']])
            with self.assertRaisesRegex(ValueError,'unknown/duplicate'):h.read_test(p,sha(p),source_maps())
            pin=sha(p);p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'byte pin differs'):h.read_test(p,pin,source_maps())

    def test_all_five_arms_and_all_levels_are_retained(self):
        source=source_maps();p='UniProtKB:P00001'
        test={p:{'level1':['a'],'level2':['c'],'level3':['d']},'UniProtKB:P00003':dict.fromkeys(h.LEVELS,['a'])}
        forecasts={arm:{p:h.project({'a'},source),'UniProtKB:P00002':h.project(set(),source)} for arm in h.ARMS}
        r,_=h.assess(test,forecasts,{p,'UniProtKB:P00002'},{p,'UniProtKB:P00002','UniProtKB:P00003'},source)
        self.assertEqual(set(r['metrics']),set(h.ARMS))
        self.assertTrue(all(set(x)==set(h.LEVELS) for x in r['metrics'].values()))
        self.assertEqual(r['matched_primary_test_proteins'],1)
        self.assertEqual(r['unmatched_primary_reference_unknown'],1)
        self.assertEqual(r['all_workspace_protein_coverage_only']['reference_ID_matches'],2)
        self.assertFalse(r['unreported_compartments_used_as_negatives'])


class PhaseBoundaryTests(unittest.TestCase):
    def test_source_metadata_pin_checked_before_reference_access(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);source=p/'metadata.json';source.write_text('{}');old=sha(source);source.write_text('{"changed":true}')
            contract={'format':'biograph-steward.HOU-positive-reference-frozen-contract.v1',
                'status':'frozen_before_cohort_label_join','arms':dict.fromkeys(h.ARMS,''),
                'source_readiness':{'file':str(source),'sha256':old}}
            c=p/'contract.json';c.write_text(json.dumps(contract))
            with patch.object(h,'read_test') as opened:
                with self.assertRaisesRegex(ValueError,'byte pin differs'):h.run(c,sha(c),p/'context',p/'out')
                opened.assert_not_called()

    def test_forecast_seal_precedes_reference_labels(self):
        # Invented source packet with the frozen shape, no real source outcomes.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'input';p.mkdir();ctx=root/'context';ctx.mkdir();out=root/'result'
            def save(name,value):
                f=p/name;f.write_text(json.dumps(value));return {'file':str(f),'sha256':sha(f)}
            uid='UniProtKB:P00001';s=source_maps()
            s['crosswalk']={'GO:'+str(i).zfill(7):'a' for i in range(1,161)}
            q={'qualified_exact_GO_crosswalk':{k:v for i,(k,v) in enumerate(s['crosswalk'].items()) if i<107}}
            graph={'edges':[{'record_kind':'go_annotation','subject':uid,'object':'GO:0000001',
                'aggregator':'Pharos','evidence_record':{'goid':'GO:0000001','type':'C'}}]}
            original=save('original.json',graph);current=save('current.json',graph)
            ontology=save('ontology',{});gaf=save('gaf',{})
            es={'rows':[{'protein_id':uid,'primary_source_eligible':True,'primary_target':True,
                'Pharos_GO_documented_complete':True}], 'input_pins':{'original_graph':original,'current_graph':current,'ontology':ontology,'native_GAF':gaf}}
            s['input_pins']={};ss=save('source.json',s);q['source_crosswalk_sha256']=ss['sha256'];qs=save('qualified.json',q);eps=save('eligibility.json',es)
            ref=save('reference',{});other=save('other',{})
            contract={'format':'biograph-steward.HOU-positive-reference-frozen-contract.v1',
                'status':'frozen_before_cohort_label_join','arms':dict.fromkeys(h.ARMS,''),
                'source_readiness':ss,'qualified_mapping':qs,'source_eligibility':eps,
                'author_test':ref,'author_release_metadata':other,'author_paper':other,'source_notebook':other,
                'cohort':{'matched_released_held_out_test_proteins':1,'full218_reference_coverage_only':1}}
            cs=save('contract.json',contract)
            native={'subject':uid,'go_id':'GO:0000001','aspect':'C','relation_literal':'located_in',
                'negated':False,'evidence_code':'IDA','taxon_ids':['taxon:9606'],
                'gene_product_form_id':uid,'annotation_extension_raw':'','with_from_raw':''}
            def opened(*args):
                seal=json.loads((out/'predictions_before_reference_join.json').read_text())
                self.assertFalse(seal['cohort_reference_labels_joined']);self.assertFalse(seal['metrics_computed'])
                self.assertEqual(set(seal['forecasts']),set(h.ARMS))
                return {uid:{'level1':['a'],'level2':['c'],'level3':['d']}}
            with patch.object(h.m,'mitochondrial_terms',return_value=(set(),set(s['crosswalk']),set(s['crosswalk']),{})),\
                 patch.object(h,'load_go_context',return_value=({'source':{'gaf_sha256':gaf['sha256']},'source_graph_file_sha256':original['sha256']},[native],[])),\
                 patch.object(h,'read_test',side_effect=opened):
                r=h.run(cs['file'],cs['sha256'],ctx,out)
            self.assertEqual(r['matched_primary_test_proteins'],1)
            self.assertTrue((out/'execution_receipt.json').is_file())


if __name__=='__main__':unittest.main()
