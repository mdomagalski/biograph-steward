"""Synthetic boundaries only: these fixtures contain no real held-out terms."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from tools.cafa_nonpk import evaluate as module


def seal(value):
    value.pop('content_sha256', None); value['content_sha256']=digest(value); return value


class NonPKBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def fixture(self):
        data=self.root/'pinned'; data.write_text('historical only')
        methods={n:{'file':str(data),'sha256':sha(data)} for n in
            ('strict_alias_localplus','official_blast','official_prott5_cosine3','official_nonexperimental','official_naive')}
        ids=self.root/'ids.txt';ids.write_text('P04637\n')
        value={'format':module.FORMAT,'policy':deepcopy(module.POLICY),'methods':methods,
            'new_future_GO_labels_read':{s:False for s in module.SETTINGS},'PK_outcomes_previously_seen':True,
            'new_fit_or_threshold_selection':False,'input_files_sha256':{str(data):sha(data),str(ids):sha(ids)},
            'identities':{s:{a:{'file':str(ids),'sha256':sha(ids),'count':1} for a in module.ASPECTS} for s in module.SETTINGS}}
        config=self.root/'config.json';write_json(config,seal(value));return config,value,data

    def test_filter_releases_only_predeclared_protein_aspect_without_rewriting_native_bytes(self):
        # The non-admitted future column deliberately is not decodable ASCII.
        # Reading it would violate the setting/aspect boundary even for the same protein.
        raw=b'EntryID\tterm\taspect\r\nP04637\tGO:0000001\tBPO\r\nP04637\t\xff\tMFO\r\nQ13315\t\xfe\tBPO\r\n'
        out=self.root/'truth.tsv'
        counts=module.filter_truth(io.BytesIO(raw),out,{'BPO':{'P04637'},'MFO':set(),'CCO':set()})
        self.assertEqual(out.read_bytes(),b'EntryID\tterm\taspect\r\nP04637\tGO:0000001\tBPO\r\n')
        self.assertEqual(counts['raw_proteins_by_aspect'],{'BPO':1,'MFO':0,'CCO':0})
        self.assertEqual(counts['raw_rows_by_aspect']['MFO'],0)

    def test_complete_five_arm_freeze_and_non_exclusion_policy_fail_closed(self):
        config,value,data=self.fixture(); self.assertEqual(module.verify(config,sha(config))['policy']['known_exclusion'],None)
        for mutate in (lambda v:v['methods'].pop('official_nonexperimental'),
                       lambda v:v['policy'].update(known_exclusion='known_t0.tsv'),
                       lambda v:v['new_future_GO_labels_read'].update(limited=True),
                       lambda v:v['identities']['limited']['MFO'].update(count=2)):
            changed=deepcopy(value);mutate(changed);write_json(config,seal(changed))
            with self.subTest(changed=changed),self.assertRaises(ValueError): module.verify(config,sha(config))
        write_json(config,seal(value));data.write_text('mutated historical bytes')
        with self.assertRaises(ValueError): module.verify(config,sha(config))

    def test_wrong_explicit_pin_stops_before_future_archive_is_opened(self):
        config,_,_=self.fixture()
        with patch.object(module.tarfile,'open') as archive:
            with self.assertRaises(ValueError):module.release(config,'0'*64,self.root/'unreleased')
            archive.assert_not_called()
        self.assertFalse((self.root/'unreleased').exists())

    def test_point_adapter_rejects_PK_exclusion_before_calling_author_parser(self):
        job=self.root/'job.json';write_json(job,{'author_call':{'exclude':'known.tsv','prop':'fill','norm':'cafa',
            'no_orphans':True,'th_step':.001},'output_dir':str(self.root/'scores')})
        fake_eval=SimpleNamespace(cafa_eval=lambda **_:self.fail('author must not run'),write_results=None)
        fake_parser=SimpleNamespace(obo_parser=lambda *_:self.fail('parser must not run'),update_toi=None,gt_parser=None)
        with patch.dict('sys.modules',{'numpy':SimpleNamespace(__version__='1.26.4'),
                'pandas':SimpleNamespace(__version__='2.2.3'),'cafaeval.evaluation':fake_eval,'cafaeval.parser':fake_parser}):
            with self.assertRaises(ValueError):module.point(job)
        self.assertFalse((self.root/'scores').exists())

    def test_supplement_must_be_complete_and_bound_to_same_preoutcome_target_frame(self):
        folder=self.root/'supplement';folder.mkdir();score=folder/'strict_alias_genemaniaplus.tsv.gz';score.write_bytes(b'invented sealed bytes')
        protocol={'format':'biograph-steward.cafa5-nonpk-gm-supplement.v1','protocol_sha256':'a'*64,
            'method':'strict_alias_genemaniaplus','parameters':{'alpha':1,'tol':1e-5},'new_future_GO_labels_read':False,
            'new_fit_or_threshold_selection':False,'primary_five_arm_protocol_modified':False,'PK_outcomes_previously_seen':True,
            'input_files_sha256':{},'choice_timing':'Invented fixture: selected before any new terms.'}
        write_json(folder/'protocol.json',seal(protocol));psha=sha(folder/'protocol.json')
        prediction={'format':protocol['format']+'.predictions','protocol_file_sha256':psha,
            'protocol_content_sha256':protocol['content_sha256'],'target_count':2,'new_future_GO_labels_read':False,
            'every_head_passed_pinned_author_convergence_check':True,
            'files':{score.name:{'sha256':sha(score),'bytes':score.stat().st_size}}}
        write_json(folder/'predictions.json',seal(prediction));msha=sha(folder/'predictions.json')
        self.assertEqual(module.verify_supplement(folder,psha,msha,'a'*64,2)['method'],'strict_alias_genemaniaplus')
        with self.assertRaises(ValueError):module.verify_supplement(folder,psha,msha,'b'*64,2)
        with self.assertRaises(ValueError):module.verify_supplement(folder,psha,msha,'a'*64,3)
        prediction['every_head_passed_pinned_author_convergence_check']=False;write_json(folder/'predictions.json',seal(prediction))
        with self.assertRaises(ValueError):module.verify_supplement(folder,psha,sha(folder/'predictions.json'),'a'*64,2)

    def test_execution_rebasing_retains_all_settings_arms_and_native_exclude_none(self):
        config,value,data=self.fixture();author=self.root/'author';author.mkdir();code=author/'code.py';code.write_text('synthetic author fixture')
        value.update(inputs={k:str(data) for k in ('ontology','ia','toi')},author_source=str(author),
            author_files_sha256={'code.py':sha(code)})
        value['input_files_sha256'][str(code)]=sha(code);write_json(config,seal(value))
        ref=self.root/'reference';ref.mkdir()
        for setting in module.SETTINGS:(ref/(setting+'.tsv')).write_text('EntryID\tterm\taspect\n')
        write_json(ref/'truth_access_started.json',seal({'synthetic_only':True}))
        report={'format':module.FORMAT+'.released','config_file_sha256':sha(config),'future_GO_columns_decoded':True,
            'known_exclusion':None,'files':{p.name:sha(p) for p in ref.iterdir()}}
        write_json(ref/'report.json',seal(report));runner=str(Path(module.__file__).resolve())
        required={str(data),str(code),runner,*[str(p.resolve()) for p in ref.iterdir() if p.name!='report.json']}
        paths={p:'/remote/author/code.py' if p==str(code) else '/remote/f'+str(i) for i,p in enumerate(sorted(required))}
        out=self.root/'jobs.json'
        jobs=module.execution_jobs(config,sha(config),ref,sha(ref/'report.json'),paths,out,
            author_source='/remote/author',dependency_pythonpath='/remote/deps',python='/usr/bin/python3',temporary_directory='/dev/shm')
        self.assertEqual(set(jobs['methods']),set(value['methods']));self.assertEqual(set(jobs['references']),set(module.SETTINGS))
        self.assertTrue(all(r['known'] is None for r in jobs['references'].values()))
        self.assertFalse(jobs['contributions']);self.assertEqual(jobs['expected_versions'],{'numpy':'1.26.4','pandas':'2.2.3'})
        with self.assertRaises(ValueError):module.execution_jobs(config,sha(config),ref,sha(ref/'report.json'),paths,
            self.root/'no_supplement.json',author_source='/remote/author',dependency_pythonpath='/remote/deps',
            python='/usr/bin/python3',temporary_directory='/dev/shm',supplementary_only=True)


if __name__=='__main__':unittest.main()
