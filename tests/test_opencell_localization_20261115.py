import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('opencell_localization',Path(__file__).resolve().parents[1]/'scripts/opencell_localization_20261115.py')
oc=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(oc)


class OpenCellLocalizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_author_map_is_read_without_executing_code(self):
        p=self.root/'author.py';p.write_text("raise RuntimeError('do not execute')\nclass HRC:\n x='coarse'\nclass OC:\n a='membrane'\nclass HPA:\n a='Plasma membrane'\nhigh_res_oc_hpa_labels=[{'consensus':HRC.x,'oc':OC.a,'hpa':HPA.a}]\n")
        maps,classes=oc.author_categories(p)
        self.assertEqual(maps,{'oc':{'membrane':'coarse'},'hpa':{'Plasma membrane':'coarse'}})
        self.assertEqual(classes,['coarse'])

    def test_nonliteral_author_category_rejected(self):
        p=self.root/'author.py';p.write_text("high_res_oc_hpa_labels=fetch_external_labels()\n")
        with self.assertRaises(ValueError):oc.author_categories(p)

    def test_missing_compartments_stay_unknown(self):
        cohort={'UniProtKB:X'};reference={'ENSG00000000001':{'target_name':'example','grades':{'1':[],'2':[],'3':['nucleus']}}}
        identities={'UniProtKB:X':{'ensg_id':'ENSG00000000001','construct_rows':[]}}
        forecasts={a:{'UniProtKB:X':['nucleus','other']} for a in oc.ARMS}
        report,_=oc.score_reference(reference,identities,cohort,forecasts,{'nucleus':'nucleus'},
             {'nucleus':'nucleus','other':'other'},['nucleus','other'],[2,3])
        for metrics in report['metrics'].values():
            self.assertEqual(metrics['recovered_reference_positive_labels'],1)
            self.assertEqual(metrics['extra_predicted_labels_truth_unknown'],1)
            self.assertIsNone(metrics['precision']);self.assertIsNone(metrics['specificity'])

    def test_grade1_and_unmapped_categories_not_promoted(self):
        p=self.root/'ref.csv'
        with p.open('w') as f:
            writer=csv.writer(f);writer.writerow(oc.SCHEMAS['localization']);writer.writerow(['example','ENSG00000000001','nucleus','artifact','membrane'])
        rows=oc.read_reference(p)
        self.assertEqual(rows['ENSG00000000001']['grades']['1'],['membrane'])
        report,_=oc.score_reference(rows,{'UniProtKB:X':{'ensg_id':'ENSG00000000001','construct_rows':[]}},
          {'UniProtKB:X'},{a:{'UniProtKB:X':['membrane']} for a in oc.ARMS},{'nucleus':'nucleus'},
          {'membrane':'membrane'},['nucleus','membrane'],[2,3])
        self.assertEqual(report['unmapped_reference_categories'],{'artifact':1})
        self.assertEqual(report['metrics'][oc.ARMS[0]]['recovered_reference_positive_labels'],0)

    def test_duplicate_reference_ensg_rejected(self):
        p=self.root/'ref.csv'
        with p.open('w') as f:
            writer=csv.writer(f);writer.writerow(oc.SCHEMAS['localization'])
            writer.writerows([['example','ENSG00000000001','nucleus','','']]*2)
        with self.assertRaises(ValueError):oc.read_reference(p)

    def test_ambiguous_library_accession_not_rescued_by_name(self):
        p=self.root/'meta.csv'
        with p.open('w') as f:
            writer=csv.writer(f);writer.writerow(['uniprot_id','ensg_id','enst_id','tagged_terminus','gene_name'])
            writer.writerows([['X','ENSG00000000001','ENST1','C','same'],['X','ENSG00000000002','ENST2','N','same']])
        good,counts=oc.exact_metadata(p)
        self.assertEqual(good,{});self.assertEqual(counts['library_rows'],2)

    def test_provider_and_reference_exclusion_preserves_missing_source(self):
        def row(pid,provider,refs):
            return {'subject':pid,'negated':False,'aspect':'C','relation_literal':'located_in','go_id':'GO:1',
                    'parsed':{'Assigned_By':provider,'DB:Reference':refs}}
        native=[row('UniProtKB:X','HPA',[]),row('UniProtKB:X','Other',['PMID:35271311']),
                row('UniProtKB:Y','Other',['PMID:1'])]
        with patch.object(oc,'exclusion_reasons',return_value=[]):
            labels,report=oc.source_separated_native(native,{'UniProtKB:X','UniProtKB:Y','UniProtKB:Z'},
                                                     {'GO:1':'nucleus'},{'GO:1'})
        self.assertEqual(labels,{'UniProtKB:X':[],'UniProtKB:Y':['nucleus'],'UniProtKB:Z':None})
        self.assertEqual(report['excluded_native_rows'],{'HPA_assigned_rows':1,'explicit_OpenCell_reference_rows':1})
        self.assertFalse(report['hidden_indirect_citation_reuse_excluded'])

    def test_hou_inversion_does_not_create_ambiguous_focal_adhesion_mapping(self):
        author={'hpa':{'Actin filaments':'cytoskeleton','Focal adhesion sites':'membrane','Cytosol':'cytoplasm'}}
        maps,ambiguous,unmapped=oc.source_label_categories(['actin-filaments','cytosol','generic-unknown'],author)
        self.assertEqual(maps,{'actin-filaments':'cytoskeleton','cytosol':'cytoplasm'})
        self.assertEqual(ambiguous,{});self.assertEqual(unmapped,['generic-unknown'])


if __name__=='__main__':unittest.main()
