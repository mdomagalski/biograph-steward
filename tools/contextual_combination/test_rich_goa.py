"""Invented-only source, alias, metadata-preservation and branch-count checks."""
import gzip
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

from .rich_goa import (CHANNELS,NS,load_author,native_groups,native_term_map,
                       normalize,build_context,read_t0_gaf)

OBO='''format-version: 1.2

[Term]
id: GO:0008150
name: invented root
namespace: biological_process

[Term]
id: GO:2000001
name: invented left
namespace: biological_process
alt_id: GO:9000001
alt_id: GO:2000002
is_a: GO:0008150 ! root

[Term]
id: GO:2000002
name: invented right
namespace: biological_process
alt_id: GO:9000001
is_a: GO:0008150 ! root

[Term]
id: GO:2000003
name: invented diamond leaf
namespace: biological_process
is_a: GO:2000001 ! left
is_a: GO:2000002 ! right
'''


class RichGOASourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import pandas as pd
            cls.np,cls.pd=np,pd
            source=os.environ.get('BIOGRAPH_CAFA_AUTHOR_SOURCE')
            if source:sys.path.insert(0,source)
            from tools.learned_combination.native_adapter import _native
            cls.native=_native()
        except (ImportError,FileNotFoundError) as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest(str(error))
        cls.author=Path(os.environ.get('BIOGRAPH_CAFA6_AUTHOR_SOURCE',
            str(Path(__file__).resolve().parents[2]/'runs/contextual_gain_20261115/operator/cafa6_goa38_qualification_v1/author')))
        if not cls.author.is_dir():
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise RuntimeError('CAFA6 source required')
            raise unittest.SkipTest('CAFA6 source unavailable')
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.groups,counter,cls.receipt=load_author(cls.author,cls.root/'kernel')
        cls.counter=staticmethod(counter)
        path=cls.root/'ontology.obo';path.write_text(OBO)
        cls.ont=cls.native['parser'].obo_parser(str(path),('is_a','part_of'),None,False)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def frame(self,rows):
        return self.pd.DataFrame(rows,columns=['EntryID','type','term','source','date'])

    def test_alias_priority_expansion_matches_existing_native_intake(self):
        from tools.learned_combination.native_adapter import load_native_scores
        mapping=native_term_map(self.ont)
        self.assertEqual(mapping['GO:2000002'],(NS,('GO:2000001',)))
        self.assertEqual(set(mapping['GO:9000001'][1]),{'GO:2000001','GO:2000002'})
        for term in ('GO:2000001','GO:2000002','GO:9000001'):
            path=self.root/(term.replace(':','_')+'.tsv');path.write_text('P1 '+term+' 1\n')
            matrices,_=load_native_scores([path],('P1',),self.ont)
            actual={matrices[NS].terms[i] for i in self.np.flatnonzero(matrices[NS].values[0])}
            self.assertEqual(actual,set(mapping[term][1]))

    def test_codes_relations_survive_alias_dedup_and_do_not_inflate_support(self):
        rows=[('P1','involved_in','GO:2000001','IEA','20230101'),
              ('P1','acts_upstream_of_or_within','GO:9000001','IBA','20230101'),
              ('P1','acts_upstream_of_or_within','GO:9000001','IBA','20230101'),
              ('P1','involved_in','GO:2000002','IEA','20230101'),
              ('P1','NOT|involved_in','GO:2000003','IEA','20230101'),
              ('P1','involved_in','GO:2000003','TAS','20230101')]
        frame,audit=normalize(self.frame(rows),self.ont)
        self.assertEqual(audit['exact_normalized_duplicate_rows_collapsed'],3)
        groups,admission=native_groups(self.groups,frame,['P1'],[n['id'] for n in self.ont[NS].terms_list])
        self.assertEqual(admission['NOT_rows_excluded'],1)
        self.assertEqual(admission['experimental_group_rows_excluded'],1)
        self.assertEqual(set(groups['evidence.IEA'].term),{'GO:2000001'})
        self.assertEqual(set(groups['evidence.IBA'].term),{'GO:2000001','GO:2000002'})
        self.assertEqual(set(groups['relation.involved_in'].term),{'GO:2000001'})
        self.assertEqual(set(groups['relation.acts_upstream_of_or_within'].term),{'GO:2000001','GO:2000002'})
        path=self.root/'alias_context.npy';terms=build_context(['P1'],self.ont[NS],groups,self.counter,path)
        x=self.np.load(path);root=terms.index('GO:0008150');a=terms.index('GO:2000001');b=terms.index('GO:2000002')
        self.assertEqual(x.dtype,self.np.bool_);self.assertEqual(x.shape,(1,40,len(terms)))
        self.assertFalse(x[0,CHANNELS.index('global.raw'),root]);self.assertTrue(x[0,CHANNELS.index('global.propagated'),root])
        self.assertTrue(x[0,CHANNELS.index('evidence.IEA.raw'),a]);self.assertFalse(x[0,CHANNELS.index('evidence.IEA.raw'),b])
        self.assertTrue(x[0,CHANNELS.index('support.branches.ge2'),root]);self.assertFalse(x[0,CHANNELS.index('support.branches.ge3'),root])
        self.assertTrue(x[0,CHANNELS.index('support.code_branches.ge3'),root]);self.assertFalse(x[0,CHANNELS.index('support.code_branches.ge4'),root])
        self.assertFalse(x[0,CHANNELS.index('evidence.other.raw')].any())
        self.assertEqual(len(CHANNELS),len(set(CHANNELS)))

    def test_native_diamond_one_seed_counts_two_branches(self):
        from .native_stacker import sequence_edge_graph
        graph=self.ont[NS];values=self.np.zeros((1,graph.idxs),dtype=self.np.float32)
        values[0,graph.terms_dict['GO:2000003']['index']]=1
        self.counter(values,sequence_edge_graph(graph))
        self.assertEqual(values[0,graph.terms_dict['GO:0008150']['index']],2)

    def test_all_threshold_boundaries_and_absent_channels_have_fixed_order(self):
        np=self.np
        terms=['GO:0008150']+['GO:'+str(2100000+i) for i in range(1,6)]
        graph=SimpleNamespace(idxs=6,terms_list=[{'id':terms[0],'adj':[],'children':[1,2,3,4,5]}]
            +[{'id':t,'adj':[0],'children':[]} for t in terms[1:]],order=[1,2,3,4,5,0])
        for n in range(1,6):
            frame=self.frame([('P1','involved_in',term,'IEA','20230101') for term in terms[1:n+1]])
            groups,_=native_groups(self.groups,frame,['P1'],terms)
            path=self.root/('boundary'+str(n)+'.npy');built=build_context(['P1'],graph,groups,self.counter,path)
            self.assertEqual(tuple(built),tuple(terms));x=np.load(path)
            for cutoff in range(2,6):
                self.assertEqual(bool(x[0,CHANNELS.index('support.branches.ge'+str(cutoff)),0]),n>=cutoff)
                self.assertEqual(bool(x[0,CHANNELS.index('support.code_branches.ge'+str(cutoff)),0]),n>=cutoff)
            self.assertFalse(x[0,CHANNELS.index('evidence.IBA.raw')].any())
            self.assertEqual(x.shape,(1,len(CHANNELS),len(terms)))

    def test_gaf_epoch_and_required_field_guards(self):
        def write(name,date,annotation):
            fields=['UniProtKB','P1','invented','NOT|involved_in','GO:2000003','PMID:1','IEA','','P','','','protein','taxon:9606',annotation,'invented','','']
            path=self.root/name
            with gzip.open(path,'wt') as f:f.write('!gaf-version: 2.2\n!date-generated: '+date+' 00:00\n'+'\t'.join(fields)+'\n')
            return path
        good=write('good.gaf.gz','2023-05-18','20230101')
        frame,_=read_t0_gaf(good,['P1'],expected_date='2023-05-18')
        self.assertEqual(frame.type.tolist(),['NOT|involved_in'])
        with self.assertRaisesRegex(ValueError,'header changed'):read_t0_gaf(good,['P1'],expected_date='2023-05-19')
        bad=write('future.gaf.gz','2023-05-18','20230519')
        with self.assertRaisesRegex(ValueError,'assigned after'):read_t0_gaf(bad,['P1'],expected_date='2023-05-18')


if __name__=='__main__':unittest.main()
