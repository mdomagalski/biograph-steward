"""Run a pinned partition of the same author comparison beside remote predictions.

This stdlib operator driver changes execution location only. It uses the released
exact-scope reference, unchanged evaluator, and isolated GPL runners; one gzip
prediction is expanded into a private temporary directory at a time.
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
from datetime import datetime, timezone


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def verify(pins):
    if not pins:raise ValueError('Nonempty source/reference/runner pins are required.')
    for path,expected in pins.items():
        p=Path(path)
        if not p.is_file() or p.is_symlink() or sha(p)!=expected:
            raise ValueError('Pinned remote input differs: '+str(p))


def run(config,output,methods=None):
    config=Path(config); cfg=json.loads(config.read_text())
    if cfg['format']!='biograph-steward.cafa5-remote-author-jobs.v1':raise ValueError('Unreviewed job format.')
    names=list(cfg['methods']) if methods is None else methods
    if not names or len(names)!=len(set(names)) or not set(names)<=set(cfg['methods']):
        raise ValueError('Execution partition is outside the frozen methods.')
    verify(cfg['input_files_sha256'])
    if not cfg['parent_evaluation_config_sha256'] or not cfg['reference_content_sha256']:
        raise ValueError('The frozen comparison and released reference must be identified.')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ)
    env['PYTHONPATH']=str(Path(cfg['author_source'])/'src')+os.pathsep+cfg['dependency_pythonpath']
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    env['MPLBACKEND']='Agg'
    python=cfg.get('python',sys.executable)
    versions=json.loads(subprocess.check_output([python,'-S','-c',
        'import json,numpy,pandas,platform; print(json.dumps({"numpy":numpy.__version__,"pandas":pandas.__version__,"python":platform.python_version()}))'],env=env,text=True))
    if any(versions.get(k)!=v for k,v in cfg['expected_versions'].items()):
        raise ValueError('Isolated runtime versions differ: '+str(versions))
    started={'created_at':datetime.now(timezone.utc).isoformat(),'config_sha256':sha(config),
        'parent_evaluation_config_sha256':cfg['parent_evaluation_config_sha256'],
        'reference_content_sha256':cfg['reference_content_sha256'],'versions':versions,
        'unchanged_author_evaluator':True,'execution_methods':names,
        'temporary_plaintext_scope':'One sealed prediction in a private temporary directory; removed after each method.'}
    write(out/'execution_started.json',started)
    done=[]
    for setting,reference in cfg['references'].items():
        for name in names:
            source=cfg['methods'][name];verify({source['file']:source['sha256']})
            folder=out/setting/name;folder.mkdir(parents=True,exist_ok=False)
            with tempfile.TemporaryDirectory(prefix='biograph-cafa-',dir=cfg['temporary_directory']) as tmp:
                prediction=Path(tmp)/(name+'.tsv')
                opener=gzip.open if source['file'].endswith('.gz') else open
                with opener(source['file'],'rb') as src,prediction.open('wb') as dst:shutil.copyfileobj(src,dst)
                call={'obo_file':cfg['ontology'],'ia':cfg['ia'],'toi_file':cfg['toi'],
                    'pred_dir':tmp,'gt_file':reference['truth'],'exclude':reference['known'],
                    'prop':'fill','norm':'cafa','th_step':0.001,'no_orphans':True,'n_cpu':cfg['threads']}
                job={'author_call':call,'output_dir':str((folder/'scores').resolve())}
                write(folder/'point_job.json',job)
                with (folder/'point.log').open('w') as log:
                    subprocess.run([python,'-S',cfg['point_runner'],'--job-json',str((folder/'point_job.json').resolve())],
                        env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
                if cfg['contributions']:
                    job.update({'prediction':str(prediction),'exact_point_curves':str((folder/'scores/evaluation_all_exact.tsv').resolve()),
                                'output_dir':str((folder/'contributions').resolve())})
                    write(folder/'contributions_job.json',job)
                    with (folder/'contributions.log').open('w') as log:
                        subprocess.run([python,'-S',cfg['contributions_runner'],'--job-json',str((folder/'contributions_job.json').resolve())],
                            env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
            verify({source['file']:source['sha256']});done.append(setting+'/'+name)
            write(out/'progress.json',{'completed':done,'latest':datetime.now(timezone.utc).isoformat()})
    verify(cfg['input_files_sha256'])
    report={**started,'completed':done,'finished_at':datetime.now(timezone.utc).isoformat(),
        'files':{p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    write(out/'report.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--method',action='append',dest='methods')
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
