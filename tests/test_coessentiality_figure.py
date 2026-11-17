"""Aggregate-only figure guards with invented presentation fixtures."""
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from tools.coessentiality_feasibility.figure import load_aggregates


class AggregateFigureTests(unittest.TestCase):
    def reseal(self, path):
        data=json.loads(path.read_text());data.pop('content_sha256',None)
        data['content_sha256']=digest(data);write_json(path,data)
        return data

    def fixture(self, base):
        folders=[base/name for name in ('binary','ra','transfer')]
        for folder in folders:
            folder.mkdir()
        binary,ra,transfer=folders
        points=[{'N':n,'enrichment':0.0 if n==1 else 1.0,'observed_mean_RA_per_slot':0.1} for n in range(1,11)]
        names=['normalized','current','historical']+[f'diagnostic_{i}' for i in range(84)]
        write_json(binary/'curves.json',{a:{'nonsyntenic':points} for a in names})
        write_json(ra/'curves.json',{a:points for a in names})
        bands=[{'N':n,'draws':20,'defined_draws':20,'not_a_confidence_interval':True,
                'minimum':0.0,'median':1.0,'maximum':2.0} for n in range(1,11)]
        write_json(binary/'descriptive_control_envelopes.json',
            {a:{k:{'nonsyntenic':bands} for k in ('count','degree')} for a in ('current','historical')})
        write_json(ra/'control_envelopes.json',
            {a:{k:bands for k in ('count','degree')} for a in ('current','historical')})
        write_json(transfer/'curves.json',{a:{'RA':points,'binary_diagnostic':points}
            for a in ['normalized','historical']+[f'control_{i}' for i in range(40)]})
        write_json(transfer/'control_envelopes.json',
            {m:{k:bands for k in ('count','degree')} for m in ('RA','binary_diagnostic')})
        b={'format':'biograph-steward.coessentiality-functional-concordance.v1','query_genes':92,
           'pair_scope_counts':{'nonsyntenic':3968},'files':{p.name:sha(p) for p in binary.iterdir()}}
        b['content_sha256']=digest(b);write_json(binary/'report.json',b)
        r={'format':'biograph-steward.exploratory-RA-context-result.v1','query_genes':92,'primary_pairs':3968,
           'source_arms':87,'N':list(range(1,11)),'already_consumed_binary_result':b['content_sha256'],
           'reference_status':'consumed_exploratory_extension','calibrated_accuracy_negative_or_prune_labels_created':False,
           'production_graph_changed':False,'files':{p.name:sha(p) for p in ra.iterdir()}}
        r['content_sha256']=digest(r);write_json(ra/'report.json',r)
        t={'format':'biograph-steward.prospective-gene-transfer-result.v1','fixed_queries':128,'primary_pairs':7648,
           'all_unordered_pairs':8128,'source_arms':42,'N':list(range(1,11)),
           'prospective_gene_transfer_within_same_published_reference':True,
           'independent_experimental_confirmation_or_whole_proteome_accuracy':False,
           'new_model_or_production_graph_change':False,'calibrated_negative_truth_or_prune_labels_created':False,
           'source_only_coverage':{},'files':{p.name:sha(p) for p in transfer.iterdir()}}
        t['content_sha256']=digest(t);write_json(transfer/'report.json',t)
        return folders

    def update_inventory(self, folder, name):
        path=folder/'report.json';data=json.loads(path.read_text())
        data['files'][name]=sha(folder/name);write_json(path,data);self.reseal(path)

    def test_both_fixed_cohorts_and_all_N_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folders=self.fixture(Path(tmp));paths,pins,reports,profiles,plotted=load_aggregates(*folders)
            self.assertEqual(len(paths),9)
            self.assertEqual(profiles['exploratory92']['queries'],92)
            self.assertEqual(profiles['prospective128']['queries'],128)
            self.assertEqual(plotted['N'],list(range(1,11)))
            self.assertEqual(plotted['cohorts']['prospective128']['RA_OE']['historical'][0],0.0)

    def test_tampered_transfer_aggregate_is_not_presented(self):
        with tempfile.TemporaryDirectory() as tmp:
            folders=self.fixture(Path(tmp))
            with (folders[2]/'curves.json').open('a') as f:
                f.write(' ')
            with self.assertRaisesRegex(ValueError,'file pin'):
                load_aggregates(*folders)

    def test_resealed_missing_N_is_not_silently_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folders=self.fixture(Path(tmp));p=folders[2]/'curves.json'
            data=json.loads(p.read_text());data['historical']['RA'].pop(4);write_json(p,data)
            self.update_inventory(folders[2],'curves.json')
            with self.assertRaisesRegex(ValueError,'every primary N'):
                load_aggregates(*folders)

    def test_same_reference_cannot_be_relabelled_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            folders=self.fixture(Path(tmp));p=folders[2]/'report.json';data=json.loads(p.read_text())
            data['independent_experimental_confirmation_or_whole_proteome_accuracy']=True
            write_json(p,data);self.reseal(p)
            with self.assertRaisesRegex(ValueError,'scope differs'):
                load_aggregates(*folders)

    def test_control_ranges_cannot_be_relabelled_CIs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folders=self.fixture(Path(tmp));p=folders[2]/'control_envelopes.json'
            data=json.loads(p.read_text());data['RA']['count'][0]['not_a_confidence_interval']=False
            write_json(p,data);self.update_inventory(folders[2],'control_envelopes.json')
            with self.assertRaisesRegex(ValueError,'control range scope'):
                load_aggregates(*folders)


if __name__=='__main__':
    unittest.main()
