"""Execution metadata for unchanged native evaluation of the sealed new cell.

No metric/scoring formula or reference parser is implemented here. Existing
released references and the unchanged author point/count/bootstrap runners are
reused beside the remote predictions. All new-cell outcomes are development.
"""
import argparse
import json
from pathlib import Path

from .run import read,write,sha,digest,need
from .run_v2 import load,FORMAT


def prepare(base,combined,frozen,expected,predictions,output):
    base,combined,frozen,predictions,output=map(Path,(base,combined,frozen,predictions,output))
    p=load(frozen,expected);m=read(predictions/'predictions.json')
    need(m['format']==FORMAT+'.predictions' and m['content_sha256']==digest({k:v for k,v in m.items()if k!='content_sha256'})
         and m['protocol_file_sha256']==expected and m['prior_common_raw_positive_rows_exactly_identical'] is True,
         'new cell must be sealed and pass the matched-host210 gate before scoring.')
    output.mkdir(parents=True,exist_ok=False);jobs={}
    for frame,oldname in (('primary','primary_BPO_point_jobs_v2.json'),('reserved','reserved_BPO_point_jobs_v1.json')):
        original=base/oldname;cfg=read(original)
        need(cfg['format']=='biograph-steward.cafa5-remote-author-jobs.v1','unchanged native execution contract required.')
        release=base/(frame+'-reference-v1');truth=release/'partial.tsv';known=release/'known_t0_frame.tsv'
        forecast=predictions/(frame+'_strict_alias_genemaniaplus.tsv.gz');entry=m['files'][forecast.name]
        need(sha(forecast)==entry['sha256'],'new forecast source differs.')
        pins=dict(cfg['input_files_sha256'])
        pins.update({str(path):sha(path)for path in (original,truth,known,release/'report.json',
            frozen/'protocol.json',predictions/'predictions.json',Path(__file__).resolve())})
        cfg.update(parent_evaluation_config_sha256=expected,references={'partial':{'truth':str(truth),'known':str(known)}},
            methods={'combined_strict_genemaniaplus':{'file':str(forecast),'sha256':entry['sha256']}},
            threads=2,contributions=True,temporary_directory='/dev/shm',input_files_sha256=pins,
            additional_scope={'development_exposed_labels':True,'new_reference_release':False,
                'old240_results_modified':False,'oldGM_reserved':'unsupported; not an invented zero-score scientific comparator'})
        config=output/(frame+'_native_jobs.json');write(config,cfg)
        jobs[frame]={'config':str(config),'config_sha256':sha(config),'output':str(combined/(frame+'_native_v1'))}
    r={'format':'biograph-steward.combined-development-native-jobs.v1','producer_protocol_sha256':expected,
       'prediction_manifest_sha256':sha(predictions/'predictions.json'),'jobs':jobs,
       'native_driver':str(base/'remote_author.py'),'new_scoring_formula':False,
       'previous_released_truth_reused':True,'all_six_cohort_aspect_outcomes_required':True}
    r['content_sha256']=digest(r);write(output/'jobs.json',r);return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('base','combined','frozen','expected','predictions','output'):p.add_argument('--'+k,required=True)
    print(json.dumps(prepare(**vars(p.parse_args())),indent=2))
