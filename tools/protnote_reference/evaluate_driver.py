"""Strict raw admission around unchanged native point/count/bootstrap APIs.

No new scoring formula, model fit, future-label feature, or app consumer. Check
the exact private Cartesian inventory before native parsers can turn malformed
or missing raw scores into a seemingly ordinary zero forecast.
"""
import argparse
from datetime import datetime
import gzip
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.deepgo_reference.archive import need, sealed
from tools.deepgo_reference.nonpk_evaluate import read_sealed, verify
from tools.deepgo_reference.evaluate import evaluation_runtime
from tools.deepgo_reference.collect import saved_point
from tools.cafa_combined.collect import native_rows

SETTINGS=('no_knowledge','limited')
ASPECTS=('biological_process','molecular_function','cellular_component')
METHOD='protnote_seed42'
COMPARATORS=('deepgose','strict_alias_localplus','official_nonexperimental')
FORMAT='biograph-steward.protnote-native-evaluation.v1'
PRODUCER='biograph-steward.protnote-development.v1'
ACCESSION=re.compile(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})')
GO=re.compile(r'GO:[0-9]{7}')


def bound(cfg,path,expected=None):
    """A selected path must actually occur in the frozen verified inventory."""
    name=str(path);pin=cfg['input_files_sha256'].get(name)
    need(isinstance(pin,str) and re.fullmatch('[a-f0-9]{64}',pin)
         and (expected is None or pin==expected) and sha(name)==pin,'selected source is unbound or changed')
    return pin


def sealed_bound(cfg,spec):
    need(isinstance(spec,dict) and isinstance(spec.get('file'),str),'sealed source specification missing')
    bound(cfg,spec['file'],spec['sha256'])
    return read_sealed(spec['file'],spec['sha256'])


def checked_ids(ids,count=None):
    need(isinstance(ids,list) and ids and len(ids)==len(set(ids))
         and all(isinstance(p,str) and ACCESSION.fullmatch(p) for p in ids)
         and (count is None or len(ids)==count),'target ID inventory differs')
    return ids


def admit_forecast(cfg,protocol,manifest):
    """No reference/TOI labels: only fixed IDs, dated ontology axis and scores."""
    need(manifest['format']==PRODUCER+'.predictions'
         and manifest['protocol_file_sha256']==cfg['protocol']['sha256']
         and manifest['protocol_content_sha256']==protocol['content_sha256']
         and manifest['all547_original_identities_accounted_for'] is True
         and manifest['reference_labels_read'] is False,'forecast producer/scope differs')
    producer_cfg=sealed_bound(cfg,cfg['producer_config'])
    done=sealed_bound(cfg,cfg['producer_done'])
    need(done['format']=='biograph-steward.protnote-labelblind.v1.complete' and done['phase']=='pilot'
         and done['config_file_sha256']==manifest['config_file_sha256']==cfg['producer_config']['sha256']
         and done['prediction_manifest_file_sha256']==cfg['predictions']['sha256']
         and done['prediction_manifest_content_sha256']==manifest['content_sha256']
         and done['reference_labels_read'] is False,'complete source-bound pilot DONE required before admission')
    qspec=protocol['producer_input_qualification']
    need(manifest['input_qualification']==qspec,'pre-forward qualification binding differs')
    qualification=sealed_bound(cfg,qspec)
    need(qualification['format']==PRODUCER+'.input-qualification'
         and qualification['ontology_sha256']==protocol['ontology']['sha256']
         and qualification['reference_labels_read'] is False and qualification['model_forward_executed'] is False
         and qualification['axis_defined_without_benchmark_TOI_or_target_labels'] is True,
         'independent dated input qualification differs')
    target_spec=protocol['target_scope']['frames']['targets.txt']
    bound(cfg,target_spec['file'],target_spec['sha256'])
    ordered=checked_ids(Path(target_spec['file']).read_text().splitlines(),547)
    need(qualification['ordered_target_ids']==ordered
         and qualification['target_ids_sha256']==digest(ordered),'qualified target scope differs')
    axis=qualification['axis_go_ids']
    need(isinstance(axis,list) and axis and axis==sorted(set(axis))
         and all(isinstance(term,str) and GO.fullmatch(term) for term in axis)
         and qualification['go_ids_sha256']==digest(axis)
         and re.fullmatch('[a-f0-9]{64}',qualification['axis_sha256']),
         'qualified canonical GO class axis differs')
    need(datetime.fromisoformat(qualification['created_at'])<=datetime.fromisoformat(protocol['created_at'])
         <=datetime.fromisoformat(manifest['created_at']),'pre-forward qualification/protocol timing differs')
    cache_spec=protocol['producer_label_cache']
    expected_sources={**qualification['source_files_sha256'],cache_spec['file']:cache_spec['sha256']}
    need(manifest['source_files_sha256']==expected_sources and qualification['source_files_sha256'],
         'qualified producer source/cache inventory differs')
    for path,pin in expected_sources.items():bound(cfg,path,pin)
    cache=sealed_bound(cfg,cache_spec)
    need(cache['format']=='biograph-steward.protnote-labelblind.v1.cache'
         and cache['config_file_sha256']==manifest['config_file_sha256']
         and cache['axis_sha256']==qualification['axis_sha256']
         and cache['ontology_file_sha256']==protocol['ontology']['sha256']
         and cache['checkpoint_sha256']==protocol['model']['checkpoint_sha256']
         and cache['shape']==[2*len(axis),1024]
         and cache['reference_labels_read'] is False and cache['benchmark_TOI_used'] is False,
         'pre-target label cache source/axis differs')
    bound(cfg,cache['cache_body']['file'],cache['cache_body']['sha256'])
    need(producer_cfg['format']=='biograph-steward.protnote-labelblind.v1.freeze'
         and producer_cfg['status']=='FROZEN_before_any_target_forecast'
         and producer_cfg['producer_input_qualification']==qspec
         and producer_cfg['expected_target_ids_sha256']==qualification['target_ids_sha256']
         and producer_cfg['expected_go_ids_sha256']==qualification['go_ids_sha256']
         and producer_cfg['ontology']==protocol['ontology'] and producer_cfg['targets']==target_spec
         and producer_cfg['dated_fasta']==protocol['target_scope']['dated_fasta']
         and producer_cfg['official_source_commit']==protocol['model']['source_commit']
         and producer_cfg['checkpoint']['sha256']==protocol['model']['checkpoint_sha256']
         and producer_cfg['seed']==protocol['model']['seed']==42
         and producer_cfg['sequence_batch']==protocol['inference']['sequence_batch']==1
         and producer_cfg['text_batch']==protocol['inference']['text_batch']
         and producer_cfg['label_pair_chunk']==protocol['inference']['label_pair_chunk']
         and producer_cfg['no_future_labels_or_TOI'] is True
         and producer_cfg['all547_denominators_retained'] is True
         and producer_cfg['new_training_or_threshold_search'] is False
         and manifest['runtime']==producer_cfg['runtime']
         and manifest['cached_sequence_embeddings']==producer_cfg['reuse_sequence_embeddings'],
         'frozen inference scope differs from evaluation protocol')
    inventory=sealed_bound(cfg,manifest['private_inventory'])
    need(inventory['format']==PRODUCER+'.private-inventory'
         and inventory['ordered_target_ids']==ordered and inventory['axis_go_ids']==axis
         and inventory['target_ids_sha256']==qualification['target_ids_sha256']
         and inventory['go_ids_sha256']==qualification['go_ids_sha256']
         and inventory['input_qualification_file_sha256']==qspec['sha256']
         and inventory['protocol_file_sha256']==cfg['protocol']['sha256']
         and inventory['reference_labels_read'] is False
         and inventory['ontology_sha256']==qualification['ontology_sha256']
         and inventory['axis_sha256']==qualification['axis_sha256'],
         'forecast ID/class inventory differs from pre-forward qualification')
    scorable=checked_ids(inventory['scorable_ids']) if inventory['scorable_ids'] else []
    unscorable=inventory['unscorable']
    need(isinstance(unscorable,list) and all(isinstance(row,dict)
         and set(row)=={'id','reason'} and isinstance(row['reason'],str) and row['reason'] for row in unscorable),
         'explicit unscorable inventory missing')
    missing=checked_ids([row['id'] for row in unscorable]) if unscorable else []
    need(not(set(scorable)&set(missing)) and set(scorable)|set(missing)==set(ordered)
         and len(scorable)+len(missing)==547,'scorable/unscorable partition differs')
    scorable_set=set(scorable);scorable=[p for p in ordered if p in scorable_set]
    forecast=manifest['forecast'];bound(cfg,forecast['file'],forecast['sha256'])
    need(Path(forecast['file']).stat().st_size==forecast['bytes']
         and forecast['file'].endswith('.gz'),'complete compressed raw forecast differs')
    expected_rows=len(scorable)*len(axis)
    need(inventory['forecast_rows']==expected_rows,'full Cartesian forecast extent differs')
    expected=iter(itertools.product(scorable,axis));seen=0
    with gzip.open(forecast['file'],'rt',encoding='utf-8') as stream:
        for line in stream:
            fields=line.rstrip('\r\n').split()
            need(len(fields)==3,'raw forecast row must have exactly three fields')
            identity=next(expected,None)
            need(identity is not None and tuple(fields[:2])==identity,
                 'raw forecast is incomplete, duplicate, extra or not canonical Cartesian order')
            score=float(fields[2])
            need(math.isfinite(score) and 0<=score<=1,'raw forecast score nonfinite or outside probability bounds')
            seen+=1
    need(next(expected,None) is None and seen==expected_rows,'raw forecast Cartesian rows missing')
    bound(cfg,forecast['file'],forecast['sha256'])
    return forecast,{'all547_original_identities_accounted_for':True,
        'scorable_targets':len(scorable),'explicit_unscorable_targets':len(missing),
        'fixed_ontology_classes':len(axis),'finite_unit_interval_cartesian_rows':seen,
        'pre_forward_input_qualification_sha256':qspec['sha256'],
        'pre_target_label_cache_manifest_sha256':cache_spec['sha256'],
        'private_inventory_sha256':manifest['private_inventory']['sha256'],
        'producer_config_file_sha256':cfg['producer_config']['sha256'],
        'producer_complete_DONE_file_sha256':cfg['producer_done']['sha256'],
        'all_raw_scores_finite_in_unit_interval':True,'exact_full_cartesian_forecast_verified':True,
        'no_reference_or_TOI_values_used_for_admission':True}


def imported_source_pins(cfg):
    """Pin actual imported helper modules, not merely neighboring files."""
    import tools.cafa_reference.paired_bootstrap as paired
    functions=(digest,utcnow,write_json,new_output,sha,need,sealed,read_sealed,verify,
               evaluation_runtime,saved_point,native_rows,paired.run,paired.need)
    result={}
    for function in functions:
        path=str(Path(sys.modules[function.__module__].__file__).resolve())
        result[path]=bound(cfg,path)
    return result


def source_contract(cfg,protocol,prior,parent):
    need(protocol['evaluation']['settings']==list(SETTINGS)
         and protocol['evaluation']['all_aspects']==list(ASPECTS)
         and protocol['evaluation']['paired_comparisons']==[[METHOD,m] for m in COMPARATORS]
         and protocol['evaluation']['paired_contrasts']==12
         and protocol['target_scope']['target_count']==547
         and protocol['target_scope']['population_counts']=={'no_knowledge':133,'limited':414}
         and cfg['previous_report']==protocol['previous_evaluation_report'],
         'frozen method, population or comparison inventory differs')
    need(set(parent['references'])==set(SETTINGS)
         and all(row['known'] is None for row in parent['references'].values())
         and parent['nonPK_native_policy']['known_exclusion'] is None,'native None policy required')
    oldpins=prior['input_files_sha256']
    need(oldpins.get(cfg['parent_jobs'])==bound(cfg,cfg['parent_jobs']),
         'selected parent job is not the earlier source-bound job')
    for key in ('ontology','ia','toi'):
        expected=protocol['evaluation']['source_inputs'][key]
        need(parent[key]==expected['file'],'selected scoring ontology/IA/TOI differs')
        bound(cfg,parent[key],expected['sha256'])
        need(parent['input_files_sha256'].get(parent[key])==expected['sha256'],
             'parent selected scoring input pin differs')
    need(protocol['ontology']==protocol['evaluation']['source_inputs']['ontology'],
         'inference and scoring ontology source differs')
    for setting in SETTINGS:
        expected=protocol['evaluation']['source_inputs']['references'][setting]
        selected=parent['references'][setting]['truth']
        need(selected==expected['file'],'selected original reference extent differs')
        bound(cfg,selected,expected['sha256'])
        need(parent['input_files_sha256'].get(selected)==expected['sha256'],
             'parent selected truth source pin differs')
    for path in (cfg['remote_driver'],cfg['counts_runner'],parent['point_runner']):bound(cfg,path)
    for name in ('__init__.py','parser.py','evaluation.py','graph.py','tests.py'):
        path=str(Path(parent['author_source'])/'src/cafaeval'/name)
        need(parent['input_files_sha256'].get(path)==bound(cfg,path),'selected native module source differs')


def check_paired_masks(methods,expected):
    import numpy as np
    first=None
    for source in methods.values():
        agreement=json.loads(Path(source['agreement']).read_text())
        need(agreement['known_exclusion'] is None and agreement['namespace']=='molecular_function'
             and agreement['ordinary_eligible']==expected['eligible_proteins']
             and agreement['IA_weighted_eligible']==expected['IA_eligible_proteins']
             and agreement['raw_reference_proteins']==expected['author_recognized_target_IDs'],
             'paired original denominator differs')
        with np.load(source['counts'],allow_pickle=False) as arrays:
            current={key:arrays[key] for key in ('ids','tau','eligible','eligible_IA_weighted')}
        if first is None:first=current
        else:need(all(np.array_equal(current[key],first[key]) for key in first),
                  'paired original ID, threshold or eligible masks differ')


def run(config,expected,output):
    need(all(os.environ.get(key)=='1' for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')),
         'one thread required')
    cfg=read_sealed(config,expected)
    need(cfg['format']==FORMAT+'.freeze','fixed profile required')
    verify(cfg['input_files_sha256']);runtime=evaluation_runtime()
    need(cfg['implementation_file']==str(Path(__file__).resolve()),'executed wrapper path differs')
    bound(cfg,cfg['implementation_file']);actual_sources=imported_source_pins(cfg)
    protocol=sealed_bound(cfg,cfg['protocol'])
    need(protocol['status']=='FROZEN_before_any_target_forecast' and protocol['development_only'] is True
         and protocol['previous_reference_and_metric_exposure'] is True,'development protocol differs')
    manifest=sealed_bound(cfg,cfg['predictions']);prior=sealed_bound(cfg,cfg['previous_report'])
    need(prior['format']=='biograph-steward.deepgo-nonpk-evaluation.v1.results'
         and len(prior['earlier_36_outcome_rows'])==36 and len(prior['new_outcome_rows'])==6,
         'all earlier42 points required')
    bound(cfg,cfg['parent_jobs']);parent=json.loads(Path(cfg['parent_jobs']).read_text())
    source_contract(cfg,protocol,prior,parent);forecast,admission=admit_forecast(cfg,protocol,manifest)
    out=new_output(output,config);tmp=out/'temporary';tmp.mkdir()
    write_json(out/'STARTED.json',sealed({'created_at':utcnow(),'source_freeze_sha256':expected,
        'protocol_sha256':cfg['protocol']['sha256'],'runtime':runtime,'new_model_calls':0,
        'raw_forecast_admission':admission,'actual_imported_helper_sources':actual_sources}))
    pins=dict(cfg['input_files_sha256']);rows=[]
    try:
        jobs=dict(parent);jobs.update(methods={METHOD:forecast},contributions=False,threads=1,
            temporary_directory=str(tmp),input_files_sha256=dict(pins),
            parent_evaluation_config_sha256=cfg['protocol']['sha256'])
        jf=out/'point_jobs.json';write_json(jf,jobs);pins[str(jf)]=sha(jf)
        with (out/'points.log').open('xb') as log:
            subprocess.run([sys.executable,'-S',cfg['remote_driver'],'--config',str(jf),
                '--output',str(out/'points')],check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        points={};den={(row['setting'],row['namespace']):row for row in prior['denominators']}
        need(len(den)==6,'all original denominator strata required')
        for setting in SETTINGS:
            folder=out/'points'/setting/METHOD/'scores'
            curve=folder/'evaluation_all_exact.tsv';native=folder/'native_outcomes.json';fixed=folder/'fixed_threshold_0_5.json'
            statuses=json.loads(native.read_text())['namespaces'];values=native_rows(curve) if curve.exists() else []
            fixed_rows=json.loads(fixed.read_text())['rows']
            for path in (curve,native,fixed):
                if path.exists():pins[str(path)]=sha(path)
            points[setting]={METHOD:str(curve)}
            for ns in ASPECTS:
                d=den[setting,ns];status=statuses[ns]
                need(all(status[key]==d[key] for key in ('author_recognized_target_IDs','eligible_proteins',
                    'IA_eligible_proteins','TOI_reference_pairs')),'original denominator/reference extent changed')
                need(d['eligible_proteins']==protocol['evaluation']['eligible_N'][setting][ns],
                     'protocol original denominator differs')
                rows.append({'analysis_scope':'ProtNote_retrospective_development','setting':setting,
                    'namespace':ns,'method':METHOD,'known_exclusion':None,**d,
                    'source_curve_sha256':sha(curve) if curve.exists() else None,
                    'native_curve_rows':status.get('native_curve_rows',0),
                    **saved_point([value for value in values if value['ns']==ns],fixed_rows,ns)})
        write_json(out/'saved_point_statuses.json',sealed({'format':FORMAT+'.point-statuses',
            'evaluation_freeze_sha256':expected,'rows':rows,'all_six_original_denominators_retained':True}))
        cjobs={'format':'biograph-steward.cafa5-nonpk-native-count-jobs.v1','known_exclusion':None,
            'namespace':'molecular_function','input_files_sha256':dict(pins),
            'author_source':parent['author_source'],'dependency_pythonpath':parent['dependency_pythonpath'],
            'references':parent['references'],'methods':{METHOD:forecast},'points':points,
            'ontology':parent['ontology'],'ia':parent['ia'],'toi':parent['toi'],
            'temporary_directory':str(tmp),'python':'/usr/bin/python3'}
        cf=out/'count_jobs.json';write_json(cf,cjobs);pins[str(cf)]=sha(cf)
        with (out/'counts.log').open('xb') as log:
            subprocess.run([sys.executable,'-S',cfg['counts_runner'],'--config',str(cf),
                '--output',str(out/'counts')],check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        from tools.cafa_reference.paired_bootstrap import run as bootstrap
        reports={};agreements={}
        for setting in SETTINGS:
            folder=out/'counts'/setting/METHOD/'contributions';a=json.loads((folder/'agreement.json').read_text())
            need(a['author_point_agreement_passed'] is True and a['known_exclusion'] is None
                 and a['namespace']=='molecular_function','native curve/count agreement required')
            methods={METHOD:{'counts':str(folder/'counts.npz'),'counts_sha256':sha(folder/'counts.npz'),
                'agreement':str(folder/'agreement.json'),'agreement_sha256':sha(folder/'agreement.json')}}
            agreements[setting+'/'+METHOD]=a
            for method in COMPARATORS:
                paths=prior['uncertainty_reports'][setting]['source_files_sha256']
                old=Path(cfg['previous_report']['file']).parent/'counts'/setting/method/'contributions'
                for path in (old/'counts.npz',old/'agreement.json'):
                    need(pins.get(str(path))==paths[str(path)]==sha(path),'earlier comparator count source differs')
                methods[method]={'counts':str(old/'counts.npz'),'counts_sha256':paths[str(old/'counts.npz')],
                    'agreement':str(old/'agreement.json'),'agreement_sha256':paths[str(old/'agreement.json')]}
            check_paired_masks(methods,den[setting,'molecular_function'])
            for source in methods.values():
                pins[source['counts']]=source['counts_sha256'];pins[source['agreement']]=source['agreement_sha256']
            bcfg={'draws':2000,'seed':20261113,'methods':methods,
                'comparisons':[[METHOD,method] for method in COMPARATORS],
                'namespace':'molecular_function','known_exclusion':None,'development_exposed_reference':True}
            bf=out/(setting+'_bootstrap_config.json');write_json(bf,bcfg);pins[str(bf)]=sha(bf)
            reports[setting]=bootstrap(bf,out/(setting+'_bootstrap'))
            pins[str(out/(setting+'_bootstrap/report.json'))]=sha(out/(setting+'_bootstrap/report.json'))
        paired=[{'setting':setting,'namespace':'molecular_function',**value}
            for setting,report in reports.items() for value in report['comparisons']]
        required={(setting,METHOD,method,readout) for setting in SETTINGS for method in COMPARATORS
            for readout in ('ordinary','IA_weighted')}
        need(len(rows)==6 and len(paired)==12 and {(row['setting'],row['candidate'],row['comparator'],row['readout'])
             for row in paired}==required,'complete six cells and exact12 contrasts required')
        verify(cfg['input_files_sha256'])
        result=sealed({'format':FORMAT+'.results','created_at':utcnow(),'evaluation_freeze_sha256':expected,
            'protocol_sha256':cfg['protocol']['sha256'],'prediction_manifest_sha256':cfg['predictions']['sha256'],
            'previous_report_sha256':cfg['previous_report']['sha256'],'runtime':runtime,
            'raw_forecast_admission':admission,'actual_imported_helper_sources':actual_sources,
            'new_outcome_rows':rows,'earlier42_outcome_rows':prior['earlier_36_outcome_rows']+prior['new_outcome_rows'],
            'paired_comparisons':paired,'uncertainty_reports':reports,
            'native_MFO_point_count_agreements':agreements,'source_files_sha256':pins,
            'all_original_populations_and_reference_masks_retained':True,'development_only':True,
            'new_reference_release':False,'app_default_or_graph_changed':False,'automatic_adoption':False,
            'limitations':protocol['limitations']})
        write_json(out/'report.json',result)
        write_json(out/'DONE.json',sealed({'status':'complete','report_file_sha256':sha(out/'report.json'),
            'report_content_sha256':result['content_sha256']}))
        return result
    except BaseException as error:
        write_json(out/'FAILURE.json',sealed({'status':'failed_preserved','error_type':type(error).__name__,
            'saved_six_cell_point_statuses_preserved':len(rows)==6,'declared_comparison_cells':12,
            'no_invalid_or_missing_curve_interval_imputed':True,'old_results_app_or_graph_changed':False}))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('config','expected','output'):parser.add_argument('--'+key,required=True)
    result=run(**vars(parser.parse_args()))
    print(json.dumps({'status':'complete','content_sha256':result['content_sha256']}))
