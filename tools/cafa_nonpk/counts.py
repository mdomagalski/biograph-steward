# SPDX-License-Identifier: GPL-3.0-only
"""Isolated native non-exclusion counts for the frozen NK/LK comparison.

The unchanged author compute_confusion_matrix and normalize APIs provide all
scoring. Before resampling, both precommitted micro-F endpoint curves must agree
at every threshold with the full unchanged author evaluation. All numeric
column differences remain a separate diagnostic, including reduction roundoff.
This optional research adapter is not imported by the MIT application.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime,timezone


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def verify(pins):
    if not pins:raise ValueError('Nonempty pinned inputs are required.')
    for path,pin in pins.items():
        p=Path(path)
        if p.is_symlink() or not p.is_file() or sha(p)!=pin:raise ValueError('Pinned input differs: '+str(p))


def compare_curves(derived,point):
    """Exact native row/grid agreement with the existing fixed numeric bound."""
    import numpy as np
    if len(derived)!=len(point) or derived.empty or point.empty:raise ValueError('Native curve row count differs or is empty.')
    if len(set(point['tau']))!=len(point):raise ValueError('Duplicate native threshold.')
    point=point.sort_values('tau').reset_index(drop=True);derived=derived.sort_values('tau').reset_index(drop=True)
    if not np.array_equal(derived['tau'].to_numpy(),point['tau'].to_numpy()):raise ValueError('Native threshold grid differs.')
    columns=set(point)-{'filename','ns'}
    if columns!=set(derived)-{'ns'}:raise ValueError('Native numeric column inventory differs.')
    worst=0.;by={}
    for column in sorted(columns):
        a=derived[column].to_numpy(dtype=np.float64);b=point[column].to_numpy(dtype=np.float64)
        if not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('Nonfinite native curve; do not create an interval.')
        difference=float(np.max(np.abs(a-b)));by[column]=difference;worst=max(worst,difference)
    endpoint=max(by['f_micro'],by['f_micro_w'])
    if endpoint>1e-12:raise ValueError('Declared ordinary/IA micro-F endpoint agreement failed: '+str(endpoint))
    return {'max_absolute_curve_difference':endpoint,'author_curve_rows':len(point),
            'numeric_columns':len(columns),'column_max_absolute_difference':by,
            'complete_raw_numeric_max_absolute_difference':worst,
            'complete_raw_numeric_columns_within_1e_12':worst<=1e-12,
            'raw_weighted_Smin_count_bitwise_identity':all(c in by and by[c]==0. for c in ('fp_w','mi_w','s_w')),
            'endpoint_scope':'Precommitted ordinary and IA-weighted micro-F curves at every native threshold; unchanged1e-12 bound.',
            'raw_column_diagnostic_scope':'All native numeric columns retained separately. NumPy reduction layout can change large weighted raw FP/MI/Smin by final-place roundoff; no point curve or scoring formula is changed.'}


def worker(job_path):
    import numpy as np
    import pandas as pd
    from cafaeval.parser import obo_parser,update_toi,gt_parser,pred_parser
    from cafaeval.evaluation import compute_confusion_matrix,normalize
    if (np.__version__,pd.__version__)!=('1.26.4','2.2.3'):raise ValueError('Use the shared native runtime.')
    job=json.loads(Path(job_path).read_text());verify(job['input_files_sha256']);call=job['author_call']
    if not(call['exclude'] is None and call['prop']=='fill' and call['norm']=='cafa'
           and call['th_step']==.001 and call['no_orphans'] is True):raise ValueError('Non-exclusion policy differs.')
    ns='biological_process';out=Path(job['output_dir']);out.mkdir(parents=True,exist_ok=False)
    ontologies=update_toi(obo_parser(call['obo_file'],('is_a','part_of'),call['ia'],False),call['toi_file'])
    ground=gt_parser(call['gt_file'],ontologies)
    prediction=pred_parser(job['prediction'],ontologies,ground,'fill',None)
    if ns not in ground or ns not in prediction:
        write(out/'agreement.json',{'author_point_agreement_passed':False,'status':'no_native_curve',
            'reason':'Native reference/prediction namespace absent; no counts or zero-valued interval imputed.'})
        return
    ontology=ontologies[ns];g=ground[ns].matrix;pred=prediction[ns].matrix
    ids=[None]*len(ground[ns].ids)
    for protein,index in ground[ns].ids.items():ids[index]=protein
    tau=np.arange(.001,1,.001);ordinary=np.zeros((len(ids),len(tau),6),dtype=np.float64);weighted=np.zeros_like(ordinary)
    eligible=np.zeros(len(ids),dtype=bool);eligible_w=np.zeros_like(eligible)
    for i in range(len(ids)):
        for toi,counts,mask,ic in ((ontology.toi,ordinary,eligible,None),(ontology.toi_ia,weighted,eligible_w,ontology.ia)):
            truth=g[i:i+1,toi]
            n_gt=np.asarray([truth.sum() if ic is None else (truth*ic[toi]).sum()])
            if n_gt[0]<=0:continue
            mask[i]=True
            # This is the native no-exclusion signature, with exactly the
            # native GT/prediction TOI slice. No PK exclusion adapter is used.
            counts[i,:,:]=compute_confusion_matrix(tau,truth,pred[i:i+1,toi],toi,n_gt,ic)
    columns=['n','tp','fp','fn','pr','rc']
    ordinary_curve=normalize(pd.DataFrame(ordinary.sum(0),columns=columns),ns,tau,np.repeat(int(eligible.sum()),len(tau)),'cafa')
    weighted_curve=normalize(pd.DataFrame(weighted.sum(0),columns=columns),ns,tau,np.repeat(int(eligible_w.sum()),len(tau)),'cafa')
    derived=pd.merge(ordinary_curve,weighted_curve,on=['ns','tau'],suffixes=('','_w'))
    derived=derived.loc[derived['cov']>0]
    point=pd.read_csv(job['exact_point_curves'],sep='\t',float_precision='round_trip')
    point=point.loc[point['ns']==ns]
    checks=compare_curves(derived,point)
    expected=json.loads(Path(job['native_outcomes']).read_text())['namespaces'][ns]
    if len(ids)!=expected['author_recognized_target_IDs'] or int(eligible.sum())!=expected['eligible_proteins'] or int(eligible_w.sum())!=expected['IA_eligible_proteins']:
        raise ValueError('Native recognized/eligible denominator differs from point execution.')
    np.savez_compressed(out/'counts.npz',ids=np.asarray(ids),tau=tau,ordinary=ordinary,IA_weighted=weighted,
                        eligible=eligible,eligible_IA_weighted=eligible_w)
    write(out/'agreement.json',{'author_point_agreement_passed':True,'status':'scored_checked_contributions',
        'namespace':ns,'known_exclusion':None,'raw_reference_proteins':len(ids),
        'ordinary_eligible':int(eligible.sum()),'IA_weighted_eligible':int(eligible_w.sum()),
        'checks':{'declared_ordinary_and_IA_micro_F_curves':{k:checks[k] for k in ('max_absolute_curve_difference','author_curve_rows','endpoint_scope')}},
        'complete_native_numeric_diagnostic':checks,'numerical_integration_version':2,
        'original_full_29_column_v1_gate_failure_preserved':True,'implementation_sha256':sha(__file__),
        'source_point_sha256':sha(job['exact_point_curves']),'numpy':np.__version__,'pandas':pd.__version__})
    verify(job['input_files_sha256'])


def run(config,output):
    config=Path(config);cfg=json.loads(config.read_text());verify(cfg['input_files_sha256'])
    if cfg['format']!='biograph-steward.cafa5-nonpk-native-count-jobs.v1' or cfg['known_exclusion'] is not None:
        raise ValueError('Use the frozen native nonPK count policy.')
    out=Path(output);out.mkdir(parents=True,exist_ok=False);done=[]
    env=dict(os.environ);env['PYTHONPATH']=str(Path(cfg['author_source'])/'src')+os.pathsep+cfg['dependency_pythonpath']
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    for setting,references in cfg['references'].items():
        for method,spec in cfg['methods'].items():
            verify({spec['file']:spec['sha256']});folder=out/setting/method;folder.mkdir(parents=True)
            with tempfile.TemporaryDirectory(prefix='biograph-nonpk-count-',dir=cfg['temporary_directory']) as tmp:
                plain=Path(tmp)/(method+'.tsv')
                with gzip.open(spec['file'],'rb') as src,plain.open('wb') as dst:shutil.copyfileobj(src,dst)
                point=Path(cfg['points'][setting][method]);native=point.with_name('native_outcomes.json')
                job={'author_call':{'obo_file':cfg['ontology'],'ia':cfg['ia'],'toi_file':cfg['toi'],
                    'gt_file':references['truth'],'exclude':None,'prop':'fill','norm':'cafa','th_step':.001,'no_orphans':True},
                    'prediction':str(plain),'exact_point_curves':str(point),'native_outcomes':str(native),
                    'input_files_sha256':{str(point):cfg['input_files_sha256'][str(point)],
                        str(native):cfg['input_files_sha256'][str(native)],str(plain):sha(plain)},
                    'output_dir':str(folder/'contributions')}
                write(folder/'job.json',job)
                with (folder/'execution.log').open('w') as log:
                    subprocess.run([cfg['python'],'-S',str(Path(__file__).resolve()),'--worker-job-json',str(folder/'job.json')],
                        env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
            done.append(setting+'/'+method);write(out/'progress.json',{'completed':done,'updated_at':datetime.now(timezone.utc).isoformat()})
    verify(cfg['input_files_sha256'])
    write(out/'report.json',{'format':cfg['format']+'.completed','config_sha256':sha(config),
        'completed':done,'known_exclusion':None,'source_graph_or_predictions_changed':False,
        'files':{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker-job-json');p.add_argument('--config');p.add_argument('--output')
    args=p.parse_args()
    if args.worker_job_json:worker(args.worker_job_json)
    else:
        if not(args.config and args.output):p.error('--config and --output required.')
        run(args.config,args.output)
