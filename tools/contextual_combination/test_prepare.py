"""Synthetic identity, prior-scope and full-repertoire preparation checks."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

from .prepare import (_check_path, exclude_reserved, sequence_hashes_from_fasta,
                      priors_from_full_fit, full_targets, projected_heads,
                      write_feature_memmap, final_features, _save_matrices)


def record(full, prefix=None):
    return {'sequence_sha256':hashlib.sha256(full.encode()).hexdigest(),
            'native_first1022_sha256':hashlib.sha256((prefix or full).encode()).hexdigest()}


class BoundaryTests(unittest.TestCase):
    def test_all_reserved_epochs_literal_full_and_effective_input_duplicates(self):
        candidates=('P1','P2','P3','P4','P5')
        old={'P1':record('literal-old'),'P2':record('samefull'),
             'P3':record('differenttail','sameprefix'),'P4':record('safe'),
             'P5':record('new_epoch_same')}
        reserved={'validation_all':{'P1':record('literal-new'),'V2':record('samefull'),
                                    'V3':record('longother','sameprefix')},
                  'new_reference_all':{'N1':record('new_epoch_same')}}
        kept,audit=exclude_reserved(candidates,old,reserved)
        self.assertEqual(kept,('P4',))
        self.assertEqual(audit['literal_accession_excluded'],1)
        self.assertEqual(audit['additional_full_sequence_excluded'],2)
        self.assertEqual(audit['additional_native_first1022_excluded'],1)
        self.assertFalse(audit['homology_disjointness_established'])

    def test_partial_hashes_cannot_establish_separation(self):
        with self.assertRaisesRegex(ValueError,'cover every'):
            exclude_reserved(['P1','P2'],{'P1':record('A')},{'test':{'N':record('N')}})
        with self.assertRaises((KeyError,ValueError)):
            exclude_reserved(['P1'],{'P1':{'sequence_sha256':'a'*64}}, {'test':{'N':record('N')}})

    def test_new_heldout_term_sources_are_not_preparation_inputs(self):
        for path in ('/data/reference_apr_nov_2026_v1/native_reference_v1/sealed_reference/groundtruth_PK.tsv',
                     '/data/reference_apr_nov_2026_v1/native_reference_v1/t1/train_terms.tsv',
                     '/data/reference_apr_nov_2026_v1/fixed_t0_sensitivity_v1/groundtruth_PK.tsv'):
            with self.assertRaisesRegex(ValueError,'held-out'):_check_path(path)
        _check_path('/data/reference_apr_nov_2026_v1/combined_reference_metadata_v1/union_target_sequence_records.json')


class NumericPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import pandas as pd
            cls.np,cls.pd=np,pd
        except ImportError as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest(str(error))

    def test_priors_use_full_universe_before_aspect_root_filter(self):
        np=self.np
        graph=SimpleNamespace(idxs=3,terms_list=[{'id':'GO:0003674','adj':[],'children':[1]},
            {'id':'GO:1000001','adj':[0],'children':[2]},
            {'id':'GO:1000002','adj':[1],'children':[]}])
        target=np.array([[1,1,1],[1,1,0],[1,0,0],[0,0,0]],dtype=np.float32)
        raw,conditional,nulls=priors_from_full_fit(target,graph)
        np.testing.assert_allclose(raw,[.75,.5,.25],rtol=1e-7)
        np.testing.assert_allclose(conditional,[.75,2/3,.5],rtol=1e-7)
        np.testing.assert_array_equal(nulls,[0,.25,.5])
        smaller=priors_from_full_fit(target[:3],graph)[0]
        self.assertNotEqual(float(raw[2]),float(smaller[2]))
        np.testing.assert_array_equal(target,[[1,1,1],[1,1,0],[1,0,0],[0,0,0]])
        with self.assertRaisesRegex(ValueError,'upward closed'):
            priors_from_full_fit(np.array([[0,0,1]],dtype=np.float32),graph)
        set_graph=SimpleNamespace(idxs=graph.idxs,terms_list=[
            dict(node,adj=set(node['adj']),children=set(node['children'])) for node in graph.terms_list])
        for actual,expected in zip(priors_from_full_fit(target,set_graph),(raw,conditional,nulls)):
            np.testing.assert_array_equal(actual,expected)

    def test_native_feature_cache_keeps_row_order_and_refuses_overwrite(self):
        np=self.np
        class FakeTensor:
            def __init__(self,value):self.value=value
            def numpy(self):return self.value
        class FakeDataset:
            nout=2
            def __len__(self):return 3
            def __getitem__(self,index):
                value=np.zeros((9,2),dtype=np.float32);value[1]=index/4
                return {'x':FakeTensor(value)}
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'features.npy'
            write_feature_memmap(FakeDataset(),path)
            observed=np.load(path,allow_pickle=False)
            self.assertEqual(observed.shape,(3,9,2))
            np.testing.assert_array_equal(observed[:,1,0],[0,.25,.5])
            with self.assertRaisesRegex(ValueError,'already exists'):
                write_feature_memmap(FakeDataset(),path)

    def test_sequence_identity_checks_actual_truncated_model_input(self):
        try:
            import Bio  # noqa:F401
        except ImportError as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            self.skipTest(str(error))
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'source.fasta'
            path.write_text('>sp|P00001|INVENTED OX=9606\n'+'A'*1100+'\n>sp|P00002|INVENTED OX=10090\n'+'A'*1022+'B'*78+'\n')
            rows=sequence_hashes_from_fasta(path,{'P00001','P00002'})
            self.assertNotEqual(rows['P00001']['sequence_sha256'],rows['P00002']['sequence_sha256'])
            self.assertEqual(rows['P00001']['native_first1022_sha256'],rows['P00002']['native_first1022_sha256'])


class NativeLabelAndHeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=Path(os.environ.get('BIOGRAPH_CAFA_AUTHOR_SOURCE',str(Path(__file__).resolve().parents[2]/'runs/accuracy_next_20261113/cafa5_intake/evaluator_author_source/src')))
        sys.path.insert(0,str(source))
        try:
            import numpy as np
            import pandas as pd
            from tools.learned_combination.native_adapter import _native
            cls.np,cls.pd,cls.native=np,pd,_native()
        except ImportError as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest(str(error))

    def ontology(self,folder):
        from tools.learned_combination.test_native_adapter import OBO
        path=folder/'ontology.obo';path.write_text(OBO)
        return self.native['parser'].obo_parser(str(path),('is_a','part_of'),None,False)

    def test_full_targets_keep_known_positives_and_do_not_read_outside_ID_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);ont=self.ontology(folder)
            additions=folder/'allowed_consumed.tsv'
            additions.write_text('EntryID\tterm\taspect\nP00001\tGO:1000002\tF\nP00002\tGO:3000001\tC\n')
            targets,known,receipt=full_targets(['P00001'],ont,
                {'P00001':[['MFO','GO:1000001']]},[additions],folder)
            ns='molecular_function'
            self.assertTrue(known[ns][0,ont[ns].terms_dict['GO:1000001']['index']])
            self.assertTrue((targets[ns][known[ns]]==1).all())
            self.assertTrue(targets[ns][0,ont[ns].terms_dict['GO:1000002']['index']])
            self.assertEqual(int(targets['cellular_component'].sum()),0)
            self.assertTrue(receipt['full']['sha256'])

    def test_head_availability_comes_from_producer_vocabulary_not_scores(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);ont=self.ontology(folder)
            files={}
            for aspect,head in (('mf','GO:1000001'),('bp','GO:2000001'),('cc','GO:3000001')):
                path=folder/(aspect+'.pkl');self.pd.DataFrame({'gos':[head]}).to_pickle(path);files[aspect]=str(path)
            training={'outside_query_protein':[['MFO','GO:1000002'],['BPO','GO:2000001'],['CCO','GO:3000001']]}
            heads,audit=projected_heads({'deepgo_heads':files},ont,training)
            mf='molecular_function'
            self.assertEqual(heads['localplus'][mf],[ont[mf].terms_dict['GO:1000002']['index']])
            self.assertEqual(heads['deepgose'][mf],[ont[mf].terms_dict['GO:1000001']['index']])
            self.assertEqual(audit['localplus/'+mf]['available_canonical_heads'],1)

    def test_final_features_reuse_frozen_priors_and_retain_label_free_rows(self):
        from tools.learned_combination.core import ScoreMatrix
        from tools.learned_combination.reference import file_sha256
        source=Path(os.environ.get('BIOGRAPH_STACKER_AUTHOR_SOURCE',
            str(Path(__file__).resolve().parents[2]/'runs/contextual_gain_20261115/operator/combination_methods_v1/author')))
        if not source.is_dir():
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':
                self.fail('source-pinned stacker source is required for native preparation tests')
            self.skipTest('source-pinned stacker source unavailable')
        np=self.np
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);ont=self.ontology(folder);ids=('P00001','P00002')
            target_file=folder/'identities.txt';target_file.write_text('\n'.join(ids)+'\n')
            training=folder/'training.json.gz'
            with gzip.open(training,'wt') as f:json.dump({'known_training':[
                ['MFO','GO:1000001'],['BPO','GO:2000001'],['CCO','GO:3000001']]},f)
            heads={}
            for aspect,term in (('mf','GO:1000001'),('bp','GO:2000001'),('cc','GO:3000001')):
                path=folder/(aspect+'.pkl');self.pd.DataFrame({'gos':[term]}).to_pickle(path);heads[aspect]=str(path)
            fit=folder/'fit';fit.mkdir();(fit/'prepared.json').write_text(json.dumps({'source_input_pins':{}}))
            prior_files={}
            for ns,graph in ont.items():
                p=fit/'priors'/ns;p.mkdir(parents=True)
                for name,value in (('raw',.2),('conditional',.4),('nulls',.5)):
                    q=p/(name+'.npy');np.save(q,np.full(graph.idxs,value),allow_pickle=False);prior_files[str(q)]=file_sha256(q)
                (p/'receipt.json').write_text(json.dumps({'files':{Path(q).name:pin for q,pin in prior_files.items() if Path(q).parent==p}}))
            raw=folder/'raw';raw.mkdir()
            matrices={ns:ScoreMatrix(ids,tuple(n['id'] for n in graph.terms_list),
                np.zeros((len(ids),graph.idxs)),0.) for ns,graph in ont.items()}
            for method in ('localplus','deepgose','goa_final'):_save_matrices(raw/method,matrices)
            (raw/'intake.json').write_text(json.dumps({'source_input_pins':{},'final_input_pins':{}}))
            cfg={'input_pins':{},'final_input_pins':{},'all_new_reference_targets':str(target_file),
                 'ontology':str(folder/'ontology.obo'),'strict_training':str(training),
                 'deepgo_heads':heads,'author_root':str(source),'workers':1}
            result=final_features(cfg,fit,raw,folder/'final')
            for ns,row in result['final'].items():
                m=json.loads(Path(row['manifest']).read_text());self.assertEqual(m['proteins'],list(ids))
                self.assertNotIn('targets_file',m);self.assertNotIn('known_positive_mask_file',m)
                self.assertFalse(m['new_heldout_GO_columns_read'])
                x=np.load(m['feature_file'],allow_pickle=False)
                self.assertEqual(x.shape,(2,9,ont[ns].idxs));np.testing.assert_array_equal(x[0],x[1])
                np.testing.assert_array_equal(x[:,8,:],0.)
            for q,pin in prior_files.items():self.assertEqual(file_sha256(q),pin)


if __name__=='__main__':unittest.main()
