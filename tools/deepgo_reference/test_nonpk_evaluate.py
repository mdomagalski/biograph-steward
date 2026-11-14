"""Invented sealed-metadata and exact compressed-member tests; no real cases."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import gzip,json
from pathlib import Path
import tempfile
import unittest
from biograph_steward.client import digest,write_json
from biograph_steward.file_utils import sha
from .nonpk_evaluate import admit_forecasts, merge_aspects, HEADS, PRODUCER


def write(path,d):write_json(path,{**d,'content_sha256':digest(d)})


class NativeTransport(unittest.TestCase):
    def fixture(self,root):
        now=datetime.now(timezone.utc)
        namespaces={'mf':'molecular_function','cc':'cellular_component','bp':'biological_process'}
        heads={a:{'count':n,'ordered_head_sha256':str(i)*64,'native_namespace':namespaces[a]}for i,(a,n)in enumerate(HEADS.items())}
        write(root/'parent_predictions.json',{'heads':heads})
        parent_prediction={'file':str(root/'parent_predictions.json'),'sha256':sha(root/'parent_predictions.json')}
        protocol={'format':'biograph-steward.deepgo-nonpk-development.v1.freeze',
            'target_count':547,'population_counts':{'no_knowledge':133,'limited':414},
            'adoption_from_this_development_extension':False,
            'parent_runtime':{'INVENTED':'metadata'},
            'inputs':{'parent_protocol_sha256':'a'*64,'parent_predictions':parent_prediction}}
        # Gate uses the real constant producer pin; a test substitutes only its
        # file verifier while retaining all source-binding comparisons.
        write(root/'protocol.json',protocol)
        p=json.loads((root/'protocol.json').read_text()); files={}
        for a in ('mf','cc','bp'):
            path=root/f'nonpk_deepgose_{a}.tsv.gz';path.write_bytes(gzip.compress(('INVENTED_'+a+'\n').encode(),mtime=0))
            files[path.name]={'sha256':sha(path),'bytes':path.stat().st_size}
        manifest={'format':'biograph-steward.deepgo-nonpk-development.v1.predictions',
            'created_at':now.isoformat(),'protocol_file_sha256':PRODUCER,'protocol_content_sha256':p['content_sha256'],
            'parent_protocol_sha256':'a'*64,'parent_predictions_sha256':parent_prediction['sha256'],'runtime':{'INVENTED':'metadata'},
            'target_count':547,'new_native_inference_targets':337,'literal_cached_forecast_targets':210,
            'all_three_new_CLI_presentations_exact':True,'all_reference_denominators_retained':True,
            'reference_annotation_rows_read':False,'model_or_threshold_fit':False,'references_previously_exposed':True,
            'heads':heads,'files':files,'raw_rows':{f'nonpk_deepgose_{a}.tsv.gz':547*n for a,n in HEADS.items()},
            'native_CLI_checks':{a:{'all_337_new_protein_presentations_exact':True}for a in HEADS}}
        write(root/'predictions.json',manifest)
        done={'kind':'restoration_complete','created_at':(now+timedelta(seconds=2)).isoformat(),'outcome':'forecasts_complete','errors':[],
            'original_exact_restore_verified':True,'original_healthy_8000':True,'owned_process_groups_confirmed_empty':True}
        write(root/'DONE.json',done)
        cfg={'producer_protocol':str(root/'protocol.json'),'predictions':str(root),'lifecycle_done':str(root/'DONE.json')}
        return cfg,manifest

    def admit(self,root,cfg):
        from unittest.mock import patch
        from . import nonpk_evaluate as module
        real=module.read_sealed
        def reader(path,expected=None):
            return real(path,None if Path(path).name=='protocol.json' else expected)
        with patch.object(module,'read_sealed',side_effect=reader):
            return admit_forecasts(cfg,sha(root/'predictions.json'),sha(root/'DONE.json'))

    def test_complete_bound_forecasts_restore_and_exact_gzip_concatenation(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);cfg,manifest=self.fixture(root);_,m,_=self.admit(root,cfg)
            result=merge_aspects(root,m,root/'joined.tsv.gz')
            self.assertEqual(gzip.decompress((root/'joined.tsv.gz').read_bytes()),b'INVENTED_mf\nINVENTED_cc\nINVENTED_bp\n')
            self.assertEqual(result['sha256'],sha(root/'joined.tsv.gz'))
            with self.assertRaises(FileExistsError):merge_aspects(root,m,root/'joined.tsv.gz')

    def test_wrong_population_failed_restore_old_completion_or_missing_file_fail(self):
        for mutation in ('population','restore','old_completion','missing','fit'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory()as t:
                root=Path(t);cfg,m=self.fixture(root)
                if mutation in ('restore','old_completion'):
                    d=json.loads((root/'DONE.json').read_text());d.pop('content_sha256')
                    if mutation=='restore':d['original_exact_restore_verified']=False
                    else:d['created_at']='2000-01-01T00:00:00+00:00'
                    write(root/'DONE.json',d)
                elif mutation=='missing':(root/'nonpk_deepgose_cc.tsv.gz').unlink()
                else:
                    d=json.loads((root/'predictions.json').read_text());d.pop('content_sha256')
                    if mutation=='population':d['target_count']=546
                    else:d['model_or_threshold_fit']=True
                    write(root/'predictions.json',d)
                with self.assertRaises(ValueError):self.admit(root,cfg)


if __name__=='__main__':unittest.main()
