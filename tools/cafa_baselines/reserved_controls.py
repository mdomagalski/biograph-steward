"""Predeclare exact author baseline controls on the unopened new-gene frame.

This reuses the reviewed native row reader and official naive Cartesian product.
There is one paper-reported ProtT5 K=3 control; no neighbor-count selection.
"""
import argparse
import gzip
import json
from pathlib import Path
import tarfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .intake import need, selected_rows, naive_predictions, FREQUENCY

MEMBERS = {
    'official_blast': 'baselines/BLAST/blast_CAFA5.tsv',
    'official_prott5_cosine3': 'baselines/prott5/prott5_cosine_3.tsv',
    'official_nonexperimental': 'baselines/all_evidence.tsv',
}


def run(archive, qualification, frame, targets, primary_targets, output):
    archive, qualification, frame, targets, primary_targets = map(Path, (archive, qualification, frame, targets, primary_targets))
    q=json.loads(qualification.read_text()); f=json.loads(frame.read_text())
    need(q.get('content_sha256')==digest({k:v for k,v in q.items() if k!='content_sha256'})
         and q.get('status')=='completed' and q.get('future_GO_labels_opened') is False,
         'a complete pre-outcome native baseline qualification is required.')
    need(sha(archive)==q['archive_sha256'], 'official archive changed after publisher-MD5 qualification.')
    ids=targets.read_text().splitlines(); primary=primary_targets.read_text().splitlines()
    need(ids and ids==sorted(set(ids)) and not set(ids)&set(primary), 'reserved targets must be exact, sorted and disjoint from primary.')
    need(sha(primary_targets)==q['target_file_sha256'], 'original benchmark identity frame changed.')
    need(f.get('content_sha256')==digest({k:v for k,v in f.items() if k!='content_sha256'}), 'reserved identity frame seal differs.')
    # The complete frame, native baselines and plan are committed before reading
    # any future GO terms. Accession membership is not an outcome label.
    folder=new_output(output,archive,qualification,frame,targets,primary_targets)
    pins={str(p):sha(p) for p in (archive,qualification,frame,targets,primary_targets,Path(__file__),Path(__file__).with_name('intake.py'))}
    plan={'format':'biograph-steward.reserved-cafa5-native-controls.v1','created_at':utcnow(),
          'input_sha256':pins,'reserved_target_count':len(ids),'primary_target_count':len(primary),
          'targets_disjoint':True,'members':MEMBERS,'future_GO_terms_read':False,
          'choice':'Same fixed published controls as the primary task; use the paper-reported cosine K=3 without sweeping K. Raw rows and scores are retained.',
          'methods':[*MEMBERS,'official_naive'],
          'fixed_fusion_if_executed':{'sources':['official_prott5_cosine3','global_full_allseeds_fss_or_local'], 'weights':[0.5,0.5],
            'rule':'Both FSS and Local mixtures must be sealed before reserved future GO labels open; missing model score is zero for arithmetic only. No threshold/alpha fitting.'}}
    plan['content_sha256']=digest(plan);write_json(folder/'protocol.json',plan)
    reverse={v:k for k,v in MEMBERS.items()}; stats={}; frequency=None
    with tarfile.open(archive,mode='r|gz') as source:
        for member in source:
            if member.name not in {*reverse,FREQUENCY}: continue
            need(member.isfile(),'selected member is not an ordinary file.')
            stream=source.extractfile(member)
            if member.name==FREQUENCY:
                need(frequency is None and member.size<10000000,'frequency member duplicated or oversized.')
                frequency=stream.read();(folder/'cafa5_naive_frequencies.tsv').write_bytes(frequency)
            else:
                name=reverse[member.name];need(name not in stats,'baseline member repeats.')
                with gzip.GzipFile(filename=str(folder/(name+'.tsv.gz')),mode='wb',mtime=0) as out:
                    stats[name]=selected_rows(stream,set(ids),out)
                print(json.dumps({'method':name,**stats[name]}),flush=True)
    need(set(stats)==set(MEMBERS) and frequency is not None,'required control member missing.')
    with gzip.GzipFile(filename=str(folder/'official_naive.tsv.gz'),mode='wb',mtime=0) as out:
        stats['official_naive']=naive_predictions(frequency,set(ids),out)
    for p,s in pins.items():need(sha(p)==s,'frozen source/implementation changed during baseline selection.')
    result={'format':plan['format']+'.results','created_at':utcnow(),'protocol_content_sha256':plan['content_sha256'],
        'protocol_sha256':sha(folder/'protocol.json'),'target_file_sha256':sha(targets),'target_count':len(ids),
        'members':stats,'future_GO_terms_read':False,'score_rescaling':False,
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(folder.iterdir())}}
    result['content_sha256']=digest(result);write_json(folder/'qualification.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','qualification','frame','targets','primary-targets','output'):p.add_argument('--'+n,required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
