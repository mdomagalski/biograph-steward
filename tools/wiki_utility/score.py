#!/usr/bin/env python3
"""Score the fixed complete replay with the existing recorded-assay adapter.

Assay non-detections are conditional recorded outcomes, not claims of universal
noninteraction. Previously excluded/unknown/self rows remain in the complete
row ledger. This tool cannot make a fresh-confirmation or biological-truth claim.
"""
from collections import defaultdict
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.wiki_utility.prepare import verify, need, ARMS, SEEDS
from tools.wiki_utility.run import validate_complete_runs, schedule, MODEL, TRAINING
from biograph_steward import gold_packet, inmc_outcomes
from biograph_steward.client import digest,write_json,utcnow
from biograph_steward.file_utils import sha,new_output


def score(packet_path,predictions,out):
    protocol,packet=verify(packet_path)
    predictions=Path(predictions)
    report=gold_packet._read(predictions/'report.json')
    need(gold_packet._sealed(report) and report.get('format')=='biograph-steward.wiki-utility-native-development-run.v1'
         and report.get('mode')=='full' and report.get('candidate_outcomes_loaded') is False,'full unscored run required')
    need(report['packet_report_sha256']==sha(Path(packet_path)/'report.json') and report['packet_content_sha256']==protocol['content_sha256'],
         'run differs from frozen graph packet')
    need(report.get('schedule')==schedule(len(packet['supervision']),mode='full')
         and report.get('profile')=={'model':MODEL,'training':TRAINING}
         and report.get('implementation_sha256')==protocol['implementation_sha256'],
         'fixed full-run budget, model or implementation differs')
    need(not any(p.is_symlink() for p in [predictions,*predictions.parents,*predictions.rglob('*')]),'symlink in predictions')
    files={p.relative_to(predictions).as_posix():sha(p) for p in predictions.rglob('*') if p.is_file() and p!=predictions/'report.json'}
    need(files==report['files'],'prediction inventory differs')
    validate_complete_runs(report['results'],report['schedule'])
    expected={(partition,r['id']):r for partition in ('development','candidate')
              for r in packet['development' if partition=='development' else 'candidates']}
    by_arm=defaultdict(dict)
    for receipt in report['results']:
        rows=gold_packet._read(predictions/receipt['scores_file'])
        actual={(r['partition'],r['id']):r for r in rows}
        need(len(actual)==len(rows)==len(expected) and set(actual)==set(expected),'score population differs')
        for key,row in actual.items():
            need(row['original_genes']==expected[key]['original_genes'] and row['self_pair']==expected[key]['self_pair'],
                 'score identity differs')
            need(type(row['score']) in (float,int) and abs(row['score']-(row['forward']+row['reverse'])/2)<1e-8,
                 'score aggregation differs')
        by_arm[receipt['arm']][receipt['seed']]={r['id']:r['score'] for r in rows if r['partition']=='candidate'}
    need(set(by_arm)==set(ARMS) and all(set(v)==set(SEEDS) for v in by_arm.values()),'missing fixed arm or seed')
    source=protocol['consumed_outcome_cache'];path=ROOT/source['path']
    need(sha(path)==source['sha256'] and source.get('previously_exposed') is True,'consumed outcome bytes differ')
    materialized=gold_packet._read(path)
    need({r['id'] for r in materialized['rows']}=={r['id'] for r in packet['candidates']},'outcome identities differ')
    metrics=inmc_outcomes.score_comparison(materialized['rows'],by_arm,
        baseline_arm=ARMS[0],enriched_arm=ARMS[1])
    out=new_output(out,packet_path,predictions,path)
    write_json(out/'metrics.json',metrics)
    write_json(out/'all_outcome_rows.json',materialized['rows'])
    result={'format':'biograph-steward.wiki-utility-development-score.v1','created_at':utcnow(),
        'packet_report_sha256':sha(Path(packet_path)/'report.json'),'predictions_report_sha256':sha(predictions/'report.json'),
        'outcomes_sha256':sha(path),'primary_comparison':{'unqualified':ARMS[0],'qualified':ARMS[1]},
        'retrospective_consumed_reference':True,'fresh_independent_confirmation':False,
        'scientific_truth_accuracy_measured':False,'automatic_graph_changes':False,
        'scope':'Fixed recorded-assay recovery sensitivity; sparse direct Wiki coverage, indirect message effects possible.',
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    result['content_sha256']=digest(result);write_json(out/'report.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('packet','predictions','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();print(score(a.packet,a.predictions,a.out)['content_sha256'])
if __name__=='__main__':main()
