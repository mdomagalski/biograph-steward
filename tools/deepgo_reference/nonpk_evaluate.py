"""Native no-exclusion continuation for a sealed DeepGO NK/LK extension.

Reuses existing CAFA point/count/paired-bootstrap adapters. No predictor, GPU,
reference release, label parser, metric formula or application consumer is added.
"""
import argparse
from datetime import datetime
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .archive import need, sealed
from .collect import saved_point
from .evaluate import evaluation_runtime
from tools.cafa_combined.collect import native_rows

FORMAT = 'biograph-steward.deepgo-nonpk-evaluation.v1'
SETTINGS = ('no_knowledge','limited')
ASPECTS = ('biological_process','molecular_function','cellular_component')
METHODS = ('deepgose','strict_alias_localplus','official_nonexperimental')
HEADS = {'mf':6851,'cc':2829,'bp':21356}
PRODUCER = '694908cd8c0ca66279c6a470ed7a0dc651520fb530e1e075878b4c41eb399738'


def read_sealed(path, expected=None):
    p=Path(path);need(p.is_file() and not p.is_symlink(),'ordinary sealed file required.')
    if expected is not None:need(sha(p)==expected,'sealed FILE pin differs: '+p.name)
    value=json.loads(p.read_text())
    need(value.get('content_sha256')==digest({k:v for k,v in value.items() if k!='content_sha256'}),'content seal differs: '+p.name)
    return value


def verify(pins):
    need(pins,'nonempty source pins required.')
    for p,h in pins.items():
        need(Path(p).is_file() and not Path(p).is_symlink() and sha(p)==h,'ordinary source pin differs: '+p)


def admit_forecasts(cfg, manifest_expected, lifecycle_expected):
    protocol=read_sealed(cfg['producer_protocol'],PRODUCER)
    need(protocol['format']=='biograph-steward.deepgo-nonpk-development.v1.freeze'
         and protocol['target_count']==547 and protocol['population_counts']=={'no_knowledge':133,'limited':414}
         and protocol['adoption_from_this_development_extension'] is False,'producer population/scope differs.')
    folder=Path(cfg['predictions']);manifest=read_sealed(folder/'predictions.json',manifest_expected)
    need(manifest['format']=='biograph-steward.deepgo-nonpk-development.v1.predictions'
         and manifest['protocol_file_sha256']==PRODUCER
         and manifest['protocol_content_sha256']==protocol['content_sha256']
         and manifest['parent_protocol_sha256']==protocol['inputs']['parent_protocol_sha256']
         and manifest['parent_predictions_sha256']==protocol['inputs']['parent_predictions']['sha256']
         and manifest['runtime']==protocol['parent_runtime']
         and manifest['target_count']==547 and manifest['new_native_inference_targets']==337
         and manifest['literal_cached_forecast_targets']==210
         and manifest['all_three_new_CLI_presentations_exact'] is True
         and manifest['all_reference_denominators_retained'] is True
         and manifest['reference_annotation_rows_read'] is manifest['model_or_threshold_fit'] is False
         and manifest['references_previously_exposed'] is True,'complete source-bound547 forecasts required.')
    expected={f'nonpk_deepgose_{a}.tsv.gz'for a in ('mf','cc','bp')}
    parent_manifest=read_sealed(protocol['inputs']['parent_predictions']['file'],
                                protocol['inputs']['parent_predictions']['sha256'])
    need(set(manifest['files'])==expected and manifest['heads']==parent_manifest['heads']
         and set(manifest['heads'])==set(HEADS),'all three exact parent ordered head sets required.')
    namespaces={'mf':'molecular_function','cc':'cellular_component','bp':'biological_process'}
    for a in ('mf','cc','bp'):
        name=f'nonpk_deepgose_{a}.tsv.gz';spec=manifest['files'][name];p=folder/name
        need(manifest['heads'][a]['count']==HEADS[a]
             and manifest['heads'][a]['native_namespace']==namespaces[a], 'native ordered head metadata differs.')
        need(set(spec)=={'sha256','bytes','md5'} or set(spec)=={'sha256','bytes'},'unrecognized file pin fields.')
        need(p.is_file() and not p.is_symlink() and p.stat().st_size==spec['bytes'] and sha(p)==spec['sha256']
             and manifest['raw_rows'][name]==547*HEADS[a]
             and manifest['native_CLI_checks'][a]['all_337_new_protein_presentations_exact'] is True,
             'complete native aspect forecast differs.')
    done=read_sealed(cfg['lifecycle_done'],lifecycle_expected)
    need(done['kind']=='restoration_complete' and done['outcome']=='forecasts_complete' and done['errors']==[]
         and done['original_exact_restore_verified'] is done['original_healthy_8000'] is True
         and done['owned_process_groups_confirmed_empty'] is True,'successful exact service restoration required before points.')
    need(datetime.fromisoformat(done['created_at'])>=datetime.fromisoformat(manifest['created_at']),
         'lifecycle completion predates these forecasts.')
    return protocol,manifest,done


def merge_aspects(folder, manifest, output):
    """The established merge pattern, without PK-only filename assumptions."""
    folder,output=Path(folder),Path(output)
    with output.open('xb')as dst:
        for a in ('mf','cc','bp'):
            name=f'nonpk_deepgose_{a}.tsv.gz';p=folder/name
            need(sha(p)==manifest['files'][name]['sha256'],'sealed source differs before byte concatenation.')
            with p.open('rb')as src:shutil.copyfileobj(src,dst,8*1024*1024)
            need(sha(p)==manifest['files'][name]['sha256'],'sealed source changed during concatenation.')
    return {'file':str(output),'sha256':sha(output),'bytes':output.stat().st_size}


def count_configuration(cfg, points, joined, out):
    parent=json.loads(Path(cfg['parent_jobs']).read_text())
    methods={'deepgose':{'file':joined['file'],'sha256':joined['sha256']},
             **{m:parent['methods'][m] for m in METHODS[1:]}}
    point_paths={};pins=dict(cfg['input_files_sha256'])
    for setting in SETTINGS:
        point_paths[setting]={}
        for method in METHODS:
            root=points/setting/method/'scores' if method=='deepgose' else Path(cfg['old_points'])/setting/method/'scores'
            curve=root/'evaluation_all_exact.tsv';native=root/'native_outcomes.json'
            for path in (curve,native):pins[str(path)]=sha(path)
            point_paths[setting][method]=str(curve)
    pins[joined['file']]=joined['sha256']
    return {'format':'biograph-steward.cafa5-nonpk-native-count-jobs.v1','known_exclusion':None,
        'namespace':'molecular_function','input_files_sha256':pins,'author_source':parent['author_source'],
        'dependency_pythonpath':parent['dependency_pythonpath'],'references':parent['references'],
        'methods':methods,'points':point_paths,'ontology':parent['ontology'],'ia':parent['ia'],'toi':parent['toi'],
        'temporary_directory':str(out),'python':'/usr/bin/python3'}


def run(config, expected, manifest_expected, lifecycle_expected, output):
    need(all(os.environ.get(k)=='1'for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')),'one-thread numeric environment required.')
    cfg=read_sealed(config,expected)
    need(cfg['format']==FORMAT+'.freeze' and cfg['producer_protocol_file_sha256']==PRODUCER
         and cfg['focus_namespace']=='molecular_function' and cfg['known_exclusion'] is None
         and cfg['previous_reference_outcomes_exposed'] is True,'fixed native nonPK evaluation scope required.')
    need(manifest_expected==cfg['forecast_manifest_file_sha256']
         and lifecycle_expected==cfg['lifecycle_done_file_sha256'],'completed forecast/lifecycle admission differs.')
    runtime=evaluation_runtime();verify(cfg['input_files_sha256'])
    need(cfg['implementation_file']==str(Path(__file__).resolve()) and cfg['input_files_sha256'][cfg['implementation_file']]==sha(__file__),
         'executed evaluator differs from freeze.')
    parent=json.loads(Path(cfg['parent_jobs']).read_text())
    need(parent['references'].keys()==dict.fromkeys(SETTINGS).keys()
         and all(r['known']is None for r in parent['references'].values())
         and parent['nonPK_native_policy']['known_exclusion']is None,'do not use PK known-mask semantics.')
    protocol,manifest,done=admit_forecasts(cfg,manifest_expected,lifecycle_expected)
    previous=read_sealed(cfg['previous_aggregate'])
    need(previous['format']=='biograph-steward.cafa5-native-NK-LK-transport-aggregate.v1'
         and len(previous['rows'])==36,'all prior36 native outcomes required.')
    out=new_output(output,config);tmp=out/'temporary';tmp.mkdir()
    write_json(out/'STARTED.json',sealed({'created_at':utcnow(),'freeze_file_sha256':expected,
        'producer_protocol_file_sha256':PRODUCER,'forecast_manifest_file_sha256':manifest_expected,
        'lifecycle_done_file_sha256':lifecycle_expected,'runtime':runtime,'known_exclusion':None,
        'no_new_reference_release':True,'app_or_PK_sources_changed':False}))
    try:
        joined=merge_aspects(cfg['predictions'],manifest,out/'nonpk_deepgose.tsv.gz')
        point_cfg=dict(parent);point_cfg['input_files_sha256']={**parent['input_files_sha256'],**cfg['input_files_sha256'],
            joined['file']:joined['sha256'],str(Path(cfg['predictions'])/'predictions.json'):manifest_expected}
        point_cfg.update(methods={'deepgose':{'file':joined['file'],'sha256':joined['sha256']}},
            contributions=False,threads=1,temporary_directory=str(tmp))
        jobs=out/'point_jobs.json';write_json(jobs,point_cfg);points=out/'points'
        env=dict(os.environ)
        with (out/'points.log').open('xb')as log:
            subprocess.run([sys.executable,'-S',cfg['remote_driver'],'--config',str(jobs),'--output',str(points)],
                env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        counts_cfg=count_configuration(cfg,points,joined,tmp);file=out/'counts_jobs.json';write_json(file,counts_cfg)
        with (out/'counts.log').open('xb')as log:
            subprocess.run([sys.executable,'-S',cfg['counts_runner'],'--config',str(file),'--output',str(out/'counts')],
                env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        from tools.cafa_reference.paired_bootstrap import run as bootstrap
        reports={};agreements={};pins={str(Path(cfg['predictions'])/'predictions.json'):manifest_expected,
            cfg['lifecycle_done']:lifecycle_expected,str(jobs):sha(jobs),str(file):sha(file)}
        for setting in SETTINGS:
            methods={}
            for method in METHODS:
                c=out/'counts'/setting/method/'contributions';a=json.loads((c/'agreement.json').read_text())
                need(a['author_point_agreement_passed']is True and a['known_exclusion']is None
                     and a['namespace']=='molecular_function','native no-exclusion MFO count gate required.')
                agreements[setting+'/'+method]=a
                methods[method]={'counts':str(c/'counts.npz'),'counts_sha256':sha(c/'counts.npz'),
                    'agreement':str(c/'agreement.json'),'agreement_sha256':sha(c/'agreement.json')}
            bcfg={'draws':2000,'seed':20261113,'methods':methods,
                'comparisons':[['deepgose','strict_alias_localplus'],['deepgose','official_nonexperimental']],
                'namespace':'molecular_function','known_exclusion':None,'development_exposed_reference':True}
            bfile=out/(setting+'_bootstrap_config.json');write_json(bfile,bcfg)
            reports[setting]=bootstrap(bfile,out/(setting+'_bootstrap'))
            pins[str(out/(setting+'_bootstrap/report.json'))]=sha(out/(setting+'_bootstrap/report.json'))
        denoms={(d['setting'],d['namespace']):d for d in previous['denominators']};rows=[]
        for setting in SETTINGS:
            folder=points/setting/'deepgose/scores';curve=folder/'evaluation_all_exact.tsv';fixed=folder/'fixed_threshold_0_5.json';native=folder/'native_outcomes.json'
            statuses=json.loads(native.read_text())['namespaces'];values=native_rows(curve) if curve.exists()else[]
            fixed_rows=json.loads(fixed.read_text())['rows']
            for p in (fixed,native):pins[str(p)]=sha(p)
            if curve.exists():pins[str(curve)]=sha(curve)
            for namespace in ASPECTS:
                d=denoms[setting,namespace];status=statuses[namespace]
                need(all(status[k]==d[k]for k in ('author_recognized_target_IDs','eligible_proteins','IA_eligible_proteins')),
                     'native denominator differs from earlier setting/aspect.')
                rows.append({'analysis_scope':'DeepGO_NK_LK_development_extension','setting':setting,
                    'namespace':namespace,'method':'deepgose','known_exclusion':None,
                    **{k:d[k]for k in ('author_recognized_target_IDs','eligible_proteins','IA_eligible_proteins',
                        'TOI_reference_pairs','raw_released_target_IDs','raw_released_annotation_rows')},
                    'source_curve_sha256':sha(curve) if curve.exists()else None,
                    'native_curve_rows':status.get('native_curve_rows',0),
                    **saved_point([r for r in values if r['ns']==namespace],fixed_rows,namespace)})
        paired=[{'setting':setting,'namespace':'molecular_function',**c}for setting,b in reports.items()for c in b['comparisons']]
        need(len(rows)==6 and len(paired)==8,'all six new point outcomes and eight MFO contrasts required.')
        verify(cfg['input_files_sha256'])
        result=sealed({'format':FORMAT+'.results','created_at':utcnow(),'evaluation_freeze_file_sha256':expected,
            'producer_protocol_file_sha256':PRODUCER,'forecast_manifest_file_sha256':manifest_expected,
            'lifecycle_done_file_sha256':lifecycle_expected,'runtime':runtime,'known_exclusion':None,
            'focus_namespace':'molecular_function','expected_outcome_slots':42,'new_outcome_rows':rows,
            'earlier_36_outcome_rows':previous['rows'],'previous_aggregate_file_sha256':sha(cfg['previous_aggregate']),
            'denominators':previous['denominators'],'paired_comparisons':paired,'uncertainty_reports':reports,
            'native_MFO_point_count_agreements':agreements,'input_files_sha256':{**cfg['input_files_sha256'],**pins},
            'all_existing_controls_negatives_and_missing_retained':True,'app_default_or_consumer_changed':False,
            'original_PK_protocol_or_results_changed':False,'new_reference_release':False,
            'raw_reference_or_forecast_rows_included':False,'limitations':cfg['limitations']})
        write_json(out/'report.json',result);write_json(out/'DONE.json',sealed({'status':'complete',
            'report_file_sha256':sha(out/'report.json'),'report_content_sha256':result['content_sha256']}))
        return result
    except BaseException as e:
        write_json(out/'FAILURE.json',sealed({'status':'failed_preserved','error_type':type(e).__name__,
            'old_predictions_results_or_live_app_changed':False}));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','expected','manifest-expected','lifecycle-expected','output'):p.add_argument('--'+key,required=True)
    r=run(**vars(p.parse_args()));print(json.dumps({'status':'complete','content_sha256':r['content_sha256']}))
