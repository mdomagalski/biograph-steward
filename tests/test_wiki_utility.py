"""Meaningful control checks for the optional retrospective learner adapter."""
from copy import deepcopy
import unittest

from tools.wiki_utility.prepare import (ARMS, RELATION, validate, degrees, degree_permutation, XS_SEED,
    build_features,replay_features,verify_source_graph_binding)
from tools.wiki_utility.run import schedule, validate_complete_runs, FINGERPRINTS
from biograph_steward.client import digest
from unittest.mock import patch


def fixture():
    genes=["ENSG"+str(i).zfill(11) for i in range(1,5)]
    products=["UniProtKB:P00001","UniProtKB:P00002"]
    versions=["http://www.wikipathways.org/instance/WP1_r10","http://www.wikipathways.org/instance/WP2_r20"]
    supervision=[(genes[0],"interacts",genes[1]),(genes[1],"interacts",genes[0])]
    links=[(genes[0],"reviewed_product_context",products[0]),(genes[2],"reviewed_product_context",products[1])]
    ordinary=[(products[0],RELATION,versions[0]),(products[1],RELATION,versions[1])]
    arms={a:supervision+links+ordinary[:1 if a==ARMS[1] else 2] for a in ARMS}
    return {'entities':genes+products+versions,
            'relations':['interacts','reviewed_product_context','pharos_cc_annotation','go_is_a',RELATION],
            'supervision':supervision,'arms':arms,
            'candidates':[{'id':'candidate:a','original_genes':[genes[0],genes[2]],'self_pair':False}],
            'development':[{'id':'dev:a','original_genes':[genes[1],genes[3]],'self_pair':False}],
            'masked_gene_pairs':[[genes[0],genes[2]],[genes[1],genes[3]]]}


class WikiUtilityControls(unittest.TestCase):
    def test_lists_from_json_become_native_unique_tuples(self):
        p=fixture();p['supervision']=[list(t) for t in p['supervision']]
        p['arms']={a:[list(t) for t in rows] for a,rows in p['arms'].items()}
        self.assertIsInstance(validate(p)['arms'][ARMS[0]][0],tuple)

    def test_query_labels_masks_and_duplicates_fail_before_training(self):
        mutations=[lambda p:p['candidates'][0].update(label=1),
                   lambda p:p['masked_gene_pairs'].pop(0),
                   lambda p:p['candidates'].append(deepcopy(p['candidates'][0]))]
        for mutate in mutations:
            p=fixture();mutate(p)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):validate(p)

    def test_both_query_orientations_are_excluded_from_supervision(self):
        for reverse in [False,True]:
            p=fixture();a,b=p['candidates'][0]['original_genes']
            t=(b,'interacts',a) if reverse else (a,'interacts',b)
            p['supervision'].append(t)
            for rows in p['arms'].values():rows.append(t)
            with self.assertRaisesRegex(ValueError,'held-out'):validate(p)

    def test_nonwiki_difference_or_unknown_vocabulary_fails(self):
        for triple in [('ENSG00000000001','go_is_a','ENSG00000000002'),
                       ('unknown',RELATION,'http://www.wikipathways.org/instance/WP1_r10')]:
            p=fixture();p['arms'][ARMS[1]].append(triple)
            with self.assertRaises(ValueError):validate(p)

    def test_degree_control_reuses_backend_with_disjoint_bipartite_indices(self):
        rows=[('UniProtKB:A',RELATION,'WP1_r1'),('UniProtKB:B',RELATION,'WP2_r2')]
        def native(edges,**kwargs):
            self.assertEqual(edges,[(0,2),(1,3)])
            self.assertEqual(kwargs['seed'],XS_SEED)
            self.assertFalse(kwargs['allow_self_loops']);self.assertTrue(kwargs['allow_antiparallel'])
            return [(0,3),(1,2)],{'swap_attempts':20}
        result,stats=degree_permutation(rows,native)
        self.assertEqual(degrees(result),degrees(rows));self.assertEqual(stats['swap_attempts'],20)

    def test_degree_control_malformed_or_noop_native_result_fails(self):
        rows=[('UniProtKB:A',RELATION,'WP1_r1'),('UniProtKB:B',RELATION,'WP2_r2')]
        for result in [[(0,2),(1,3)],[(0,3),(0,2)],[(0,1),(1,3)],[(0,3),(0,3)]]:
            with self.subTest(result=result),self.assertRaises(ValueError):
                degree_permutation(rows,lambda *args,**kw:(result,{}))

    def test_actual_fixed_budget_is_equal_for_all_twelve_runs(self):
        selected=schedule(99394,mode='full')
        self.assertEqual((selected['runs'],selected['updates_per_arm_seed'],selected['total_updates']),
                         (12,500,6000))
        with self.assertRaises(ValueError):schedule(99393,mode='full')
        receipts=[{'arm':a,'seed':s,'parameter_count':100,'optimizer_steps':500,
                   'optimizer_state_steps':[500],'epochs_completed':20,
                   **{f:'same_'+str(s) for f in FINGERPRINTS}}
                  for s in selected['seeds'] for a in ARMS]
        validate_complete_runs(receipts,selected)
        for field,bad in [('initial_parameters_sha256','different'),('negative_filter_mask_sha256','different'),
                          ('optimizer_steps',499),('epochs_completed',19)]:
            altered=deepcopy(receipts);altered[0][field]=bad
            with self.subTest(field=field),self.assertRaises(ValueError):validate_complete_runs(altered,selected)
        with self.assertRaises(ValueError):validate_complete_runs(receipts+[receipts[0]],selected)

    def test_source_lineage_uses_native_canonical_hash_not_serialization_hash(self):
        graph={'nodes':[],'edges':[]}
        verify_source_graph_binding(graph,{'graph_sha256':digest(graph)})
        with self.assertRaisesRegex(ValueError,'different original'):
            verify_source_graph_binding({'nodes':[1],'edges':[]},{'graph_sha256':digest(graph)})

    def test_source_replay_rejects_resealed_feature_or_shared_mask_mutation(self):
        p=fixture();base={'entities':p['entities'],'relations':[r for r in p['relations'] if r!=RELATION],
            'supervision':p['supervision'],'arms':{'baseline':[t for t in p['arms'][ARMS[0]] if t[1]!=RELATION]},
            'candidates':p['candidates'],'development':p['development'],
            'masked_gene_pairs':p['masked_gene_pairs']+[['ENSG00000000003','ENSG00000000004']]}
        a,b='UniProtKB:P00001','UniProtKB:P00002'
        x,y='http://www.wikipathways.org/instance/WP1_r10','http://www.wikipathways.org/instance/WP2_r20'
        ordinary=[(a,RELATION,x),(a,RELATION,y),(b,RELATION,y)]
        qualified=[(a,RELATION,x),(b,RELATION,y)]
        links=[t for t in base['arms']['baseline'] if t[1]=='reviewed_product_context']
        def swapped(*args,**kwargs):
            return [(0,3),(1,2)],{'swap_attempts':20,'same_edge':0,'self_loop':0,'duplicate':0,'undir_duplicate':0,'excluded':0}
        with patch('tools.wiki_utility.prepare.registry_links',return_value=(links,[])):
            packet,coverage=build_features(base,ordinary,qualified,None,swapped,ordinary_counts={},qualified_counts={})
            replay_features(base,ordinary,qualified,None,packet,coverage,ordinary_counts={},qualified_counts={})
            for mutation in ['qualified','mask','shared']:
                altered=deepcopy(packet)
                if mutation=='qualified':
                    rows=altered['arms'][ARMS[1]]
                    rows.remove((a,RELATION,x));rows.append((a,RELATION,y))
                elif mutation=='mask':altered['masked_gene_pairs'].pop()
                else:
                    for rows in altered['arms'].values():rows.append(('ENSG00000000001','reviewed_product_context',b))
                validate(altered)  # Old shape-only validation would accept these.
                with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'source-derived'):
                    replay_features(base,ordinary,qualified,None,altered,coverage,ordinary_counts={},qualified_counts={})


if __name__=='__main__':unittest.main()
