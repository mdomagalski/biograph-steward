"""Run existing native CAFA point/count/paired-bootstrap adapters unchanged.

This is an execution-only continuation for the fixed development producer. It
opens no new reference setting, trains/tunes nothing, and changes no live app.
Any partial failure remains in the new output directory with its source pins.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output
from .archive import fingerprints, need, sealed
from .run import FORMAT, read_seal


def evaluation_runtime():
    import numpy, scipy, pandas
    actual = {'python':platform.python_version(),'numpy':numpy.__version__,
        'scipy':scipy.__version__,'pandas':pandas.__version__}
    need(actual == {'python':'3.10.12','numpy':'1.26.4','scipy':'1.13.1','pandas':'2.2.3'},
         'single earlier official-evaluator numeric runtime required.')
    return actual


def run(jobs, jobs_sha256, plan, plan_sha256, output):
    jobs, plan = Path(jobs), Path(plan)
    need(fingerprints(jobs)['sha256'] == jobs_sha256 and fingerprints(plan)['sha256'] == plan_sha256,
         'native job/paired plan FILE differs.')
    config = read_seal(jobs, FORMAT+'.native-jobs')
    policy = read_seal(plan, 'biograph-steward.deepgo-development-paired-plan.v1')
    need(config['evaluation_plan_file_sha256'] == plan_sha256, 'paired plan is not the frozen producer plan.')
    need(policy['draws'] == 2000 and policy['seed'] == 20261113 and policy['new_method'] == 'deepgose'
         and policy['comparison_plan'] == {f:[['deepgose','strict_alias_localplus']] for f in ('primary','reserved')}
         and policy['development_exposed_label_reuse'] is True,
         'unchanged development contrast/uncertainty scope required.')
    need(fingerprints(config['native_driver'])['sha256'] == config['native_driver_sha256'],
         'existing native driver FILE differs.')
    actual_runtime = evaluation_runtime()
    out = new_output(output, jobs, plan)
    status = {'format':FORMAT+'.native-continuation','created_at':utcnow(),
        'jobs_file_sha256':jobs_sha256,'paired_plan_file_sha256':plan_sha256,
        'implementation_file_sha256':fingerprints(__file__)['sha256'],'runtime':actual_runtime,
        'status':'SCORING_UNCHANGED_NATIVE_AUTHOR','live_app_graph_or_review_changes':False,
        'new_reference_release':False,'new_model_calls':0}
    write_json(out/'status.json',status)
    try:
        def execute(item):
            frame, spec = item
            need(fingerprints(spec['config'])['sha256'] == spec['config_sha256'], 'native per-frame job changed.')
            with (out/(frame+'_native.log')).open('wb') as log:
                subprocess.run([sys.executable,'-S',config['native_driver'],'--config',spec['config'],
                    '--output',spec['output']],check=True,stdout=log,stderr=subprocess.STDOUT)
            return frame
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            status['completed_native_frames'] = list(pool.map(execute, config['jobs'].items()))
        status['status'] = 'BOOTSTRAPPING_FIXED_PAIRED_BPO'
        write_json(out/'status.json',status)
        from tools.cafa_reference.paired_bootstrap import run as paired_bootstrap
        reports = {}
        for frame, spec in config['jobs'].items():
            folder = Path(spec['output'])/'partial/deepgose/contributions'
            methods = {key:{k:v for k,v in value.items() if k in ('counts','counts_sha256','agreement','agreement_sha256')}
                for key,value in policy['reused_comparator_counts'][frame].items()}
            methods['deepgose'] = {'counts':str(folder/'counts.npz'),
                'counts_sha256':fingerprints(folder/'counts.npz')['sha256'],
                'agreement':str(folder/'agreement.json'),
                'agreement_sha256':fingerprints(folder/'agreement.json')['sha256']}
            bootstrap_config = {'draws':2000,'seed':20261113,'methods':methods,
                'comparisons':policy['comparison_plan'][frame], 'development_exposed_label_reuse':True,
                'paired_plan_file_sha256':plan_sha256,'native_jobs_file_sha256':jobs_sha256}
            file = out/(frame+'_bootstrap_config.json');write_json(file,bootstrap_config)
            report = paired_bootstrap(file,out/(frame+'_bootstrap'))
            reports[frame] = {'report_file':str(out/(frame+'_bootstrap/report.json')),
                'report_file_sha256':fingerprints(out/(frame+'_bootstrap/report.json'))['sha256'],
                'report_content_sha256':report['content_sha256']}
        need(fingerprints(jobs)['sha256'] == jobs_sha256 and fingerprints(plan)['sha256'] == plan_sha256,
             'native/paired inputs changed during scoring.')
        status.update(status='COMPLETE_POINTS_COUNTS_AND_FIXED_UNCERTAINTY',bootstrap_reports=reports,
            finished_at=utcnow())
    except Exception as error:
        status.update(status='FAILED_PRESERVED',error_type=type(error).__name__,error=str(error),failed_at=utcnow())
        raise
    finally:
        write_json(out/'status.json',sealed({k:v for k,v in status.items() if k != 'content_sha256'}))
    return read_seal(out/'status.json',FORMAT+'.native-continuation')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('jobs','jobs-sha256','plan','plan-sha256','output'):
        parser.add_argument('--'+key,required=True)
    value=run(**vars(parser.parse_args()))
    print(json.dumps({'format':value['format'],'content_sha256':value['content_sha256']}))
