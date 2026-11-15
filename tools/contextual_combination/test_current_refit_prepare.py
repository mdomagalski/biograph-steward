"""Invented source-union, retention, context and changed-prior cache checks."""
import gzip,json,os
from pathlib import Path
from types import SimpleNamespace
import tempfile,unittest
from unittest.mock import patch

from . import current_refit_prepare as module
from tools.learned_combination.reference import file_sha256


class AuthorizationTests(unittest.TestCase):
    def test_no_source_access_before_explicit_source_only_authorization(self):
        with patch.object(module,'pinned',side_effect=AssertionError('must not read')) as reader:
            with self.assertRaisesRegex(ValueError,'explicit authorization'):
                module.verify_config({'format':'biograph-steward.current-refit-preparation.v1'})
            reader.assert_not_called()


class NativePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            from tools.learned_combination.native_adapter import _native
            cls.np=np;cls.native=_native()
        except ImportError as error:
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise
            raise unittest.SkipTest(str(error))
        cls.stacker=Path(os.environ.get('BIOGRAPH_STACKER_AUTHOR_SOURCE','/source-not-available'))
        cls.rich=Path(os.environ.get('BIOGRAPH_CAFA6_AUTHOR_SOURCE','/source-not-available'))
        if not cls.stacker.is_dir() or not cls.rich.is_dir():
            if os.environ.get('BIOGRAPH_NATIVE_TESTS_REQUIRED')=='1':raise RuntimeError('pinned source roots required')
            raise unittest.SkipTest('pinned native producer source roots unavailable')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        obo=self.root/'invented.obo';obo.write_text('''format-version: 1.2

[Term]
id: GO:0008150
name: invented root
namespace: biological_process

[Term]
id: GO:2000001
name: invented left
namespace: biological_process
is_a: GO:0008150 ! root

[Term]
id: GO:2000002
name: invented right
namespace: biological_process
is_a: GO:0008150 ! root
''')
        self.ont=self.native['parser'].obo_parser(str(obo),('is_a','part_of'),None,False)
        self.graph=self.ont[module.NS];self.terms=[n['id'] for n in self.graph.terms_list]
        self.ids=['P1','P2','P3']

    def tearDown(self):self.temp.cleanup()

    def targets_fixture(self):
        np=self.np
        strict={'P1':[['BPO','GO:2000001']]}
        source=self.root/'old_allowed.tsv';source.write_text('EntryID\tterm\taspect\nP2\tGO:2000001\tP\n')
        original_dir=self.root/'original';original_dir.mkdir()
        arrays,masks,_=module.prep.full_targets(self.ids,self.ont,strict,[source],original_dir)
        old=arrays[module.NS];old_mask=masks[module.NS]
        np.save(self.root/'old.npy',old);np.save(self.root/'old_known.npy',old_mask)
        original_meta={'proteins':self.ids,'terms':self.terms,'targets_file':str(self.root/'old.npy'),
            'known_positive_mask_file':str(self.root/'old_known.npy'),'file_pins':{
                str(self.root/'old.npy'):file_sha256(self.root/'old.npy'),
                str(self.root/'old_known.npy'):file_sha256(self.root/'old_known.npy')}}
        mp=self.root/'original_manifest.json';mp.write_text(json.dumps(original_meta))
        training=self.root/'strict.json.gz'
        with gzip.open(training,'wt') as f:json.dump(strict,f)
        direct=self.root/'direct.tsv';direct.write_text('EntryID\tterm\taspect\nP1\tGO:2000002\tP\nP3\tGO:2000002\tP\nOUTSIDE\tGO:2000002\tP\n')
        cfg={'original_fit_manifest':{'file':str(mp),'sha256':file_sha256(mp)},
            'direct_terms':{'file':str(direct),'sha256':file_sha256(direct)},'model_obo':{'file':'invented','sha256':'invented'},
            'plan':{'file':'invented','sha256':module.PLAN_SHA},'input_file_pins':original_meta['file_pins']}
        (self.root/'configuration.json').write_text(json.dumps(cfg))
        original={'strict_training':str(training),'allowed_development_annotations':[str(source)]}
        plan={'source_adaptation':{'expected_original_full_BP_positive_cells':4,'expected_augmented_BP_positive_cells':7,
            'expected_added_BP_positive_cells':3,'expected_fitting_proteins_with_additions':2,
            'expected_original_root_positive_rows':2,'expected_augmented_root_positive_rows':3}}
        return cfg,original,plan,old,old_mask

    def test_actual_native_union_retains_FULL_not_only_older_known_mask(self):
        np=self.np;cfg,original,plan,old,old_known=self.targets_fixture()
        with patch.object(module,'FIT_COUNT',3):
            meta,new,admission=module.prepare_targets(cfg,self.ont,original,self.root/'targets',plan)
        saved=np.load(meta['known_positive_mask_file'])
        np.testing.assert_array_equal(saved,old>0)
        self.assertGreater(int(saved.sum()),int(old_known.sum()))
        self.assertEqual(int(new.sum()),7)
        self.assertTrue(meta['original_full_positive_retention']);self.assertFalse(meta['fresh_final_reference_claimed'])
        self.assertNotIn('fresh_final_reference_opened',meta)
        a=json.loads(Path(admission['file']).read_text())
        self.assertEqual(a['status'],'passed');self.assertEqual(a['plan_sha256'],module.PLAN_SHA)
        self.assertEqual(a['target_manifest_sha256'],file_sha256(self.root/'targets/manifest.json'))
        self.assertEqual(a['counts']['augmented_root_positive_rows'],3)
        self.assertTrue(a['source_preparation_code']['sha256'])

    def test_replacement_or_original_known_only_mask_cannot_pass_full_retention(self):
        np=self.np;_,_,_,old,known=self.targets_fixture()
        with self.assertRaisesRegex(ValueError,'complete original full'):
            module.retained_union_counts(old,old.copy(),known,self.graph)
        changed=old.copy();changed[old>0]=0
        with self.assertRaisesRegex(ValueError,'full positive was lost'):
            module.retained_union_counts(old,changed,old>0,self.graph)

    def test_parent_cache_rows_are_reindexed_explicitly_and_head_axis_is_literal(self):
        np=self.np;p=self.root/'raw.npy';np.save(p,np.arange(9,dtype=np.float64).reshape(3,3)/10)
        meta={module.NS:{'file':str(p),'sha256':file_sha256(p),'proteins':self.ids,'terms':self.terms}}
        mp=self.root/'raw.json';mp.write_text(json.dumps(meta));spec={'file':str(mp),'sha256':file_sha256(mp)}
        values,rows=module.read_parent(spec,['P3','P1'],self.terms,{str(p):file_sha256(p)})
        np.testing.assert_array_equal(rows,[2,0]);np.testing.assert_array_equal(values[rows,0],[.6,0.])
        with self.assertRaisesRegex(ValueError,'axes differ'):
            module.read_parent(spec,['P1'],self.terms[::-1],{str(p):file_sha256(p)})

    def test_new_priors_change_parent_features_and_same_priors_match_both_roles(self):
        np=self.np;author=module.load_author(self.stacker,jit_backend='none')
        values=np.zeros((3,3),dtype=np.float64);parents={m:(values,np.arange(3)) for m in ('localplus','deepgose')}
        heads={'localplus':[0],'deepgose':[]};context=np.zeros((3,40,3),dtype=bool);context[:,1,0]=True
        old_y=np.asarray([[1,1,0],[1,1,0],[0,0,0]],dtype=np.float32)
        new_y=np.asarray([[1,1,1],[1,1,0],[1,0,1]],dtype=np.float32)
        old_prior=module.prep.priors_from_full_fit(old_y,self.graph)[:2]
        new_prior=module.prep.priors_from_full_fit(new_y,self.graph)[:2]
        paths={name:self.root/(name+'.npy') for name in ('old','fit','final')}
        for role,prior in (('old',old_prior),('fit',new_prior),('final',new_prior)):
            module.write_role_features(author,self.graph,self.ids,self.terms,parents,heads,prior,context,paths[role],workers=1)
        a,b,c=(np.load(paths[n]) for n in ('old','fit','final'))
        self.assertFalse(np.array_equal(a[:,:8],b[:,:8]));np.testing.assert_array_equal(b,c)
        np.testing.assert_array_equal(b[:,8],context[:,1]);self.assertFalse(values.any())

    def test_context_uses_native_NOT_and_experimental_exclusion_with_truthful_metadata(self):
        import gzip
        np=self.np;gaf=self.root/'current.gaf.gz'
        rows=[]
        for qualifier,code,term in [('involved_in','IEA','GO:2000001'),
             ('NOT|involved_in','IEA','GO:2000002'),('involved_in','TAS','GO:2000002')]:
            rows.append(['UniProtKB','P1','invented',qualifier,term,'PMID:invented',code,'','P','invented','','protein','taxon:9606','20260401','invented','',''])
        with gzip.open(gaf,'wt') as f:
            f.write('!gaf-version: 2.2\n!date-generated: 2026-04-10 00:00\n')
            for row in rows:f.write('\t'.join(row)+'\n')
        target_meta={'proteins':self.ids,'terms':self.terms};targets=np.ones((3,3),dtype=np.float32)
        meta=module.fit_context({'rich_author_root':str(self.rich),'gaf':{'file':str(gaf),'sha256':file_sha256(gaf)}},
            self.ont,target_meta,targets,self.root/'context')
        self.assertNotIn('fresh_final_reference_opened',meta)
        self.assertTrue(meta['reference_previously_consumed']);self.assertFalse(meta['independent_confirmation'])
        self.assertEqual(meta['admission_audit']['NOT_rows_excluded'],1)
        self.assertEqual(meta['admission_audit']['experimental_group_rows_excluded'],1)
        self.assertEqual(meta['exact_canonical_NOT_overlap']['accepted_positive_pairs_also_explicit_NOT'],1)
        x=np.load(meta['context_file']);self.assertFalse(x[0,0,self.terms.index('GO:2000002')])
        self.assertEqual(meta['exact_canonical_NOT_overlap']['labels_removed_or_flipped'],0)


if __name__=='__main__':unittest.main()
