"""Admit the fixed paper-reported ProtT5 cosine3 comparator before scoring.

The originally chosen cosine1 control is retained. Known-at-t0-only inspection
showed that98.68% of its rows were already known in partial knowledge, whereas
the CAFA5 paper reports3/5-neighbor settings. This adds the fixed3-neighbor
setting without examining later GO annotations or sweeping neighbor counts.
"""
import argparse
import gzip
import json
from pathlib import Path
import tarfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .intake import selected_rows, need

MEMBER = 'baselines/prott5/prott5_cosine_3.tsv'


def prepare(archive, qualification, targets, diagnostic, output):
    archive, qualification, targets, diagnostic = map(Path, (archive, qualification, targets, diagnostic))
    original = json.loads(qualification.read_text())
    need(original['status'] == 'completed' and original['format'] == 'biograph-steward.official-cafa5-baseline-intake.v1'
         and original['content_sha256'] == digest({k:v for k,v in original.items() if k != 'content_sha256'}),
         'completed sealed original archive qualification is required.')
    need(sha(archive) == original['archive_sha256'] and sha(targets) == original['target_file_sha256'],
         'original verified archive or target frame differs.')
    need(diagnostic.is_file() and not diagnostic.is_symlink(), 'pre-outcome known-only diagnostic required.')
    ids = targets.read_text().splitlines()
    need(ids and ids == sorted(set(ids)), 'target frame differs.')
    folder = new_output(output, archive, qualification, targets, diagnostic)
    started = {'format':'biograph-steward.cafa5-paper-control-intake.v1','created_at':utcnow(),
        'status':'running','archive_sha256':original['archive_sha256'],
        'original_baseline_qualification_content_sha256':original['content_sha256'],
        'original_baseline_qualification_file_sha256':sha(qualification),
        'target_file_sha256':sha(targets),'target_count':len(ids),
        'known_only_diagnostic_file_sha256':sha(diagnostic),'implementation_sha256':sha(__file__),
        'filter_implementation_sha256':sha(Path(__file__).with_name('intake.py')),
        'member':MEMBER,'method':'official_prott5_cosine3','neighbor_count_sweep':False,
        'future_GO_labels_opened':False,'score_rescaling':False,
        'selection_basis':'Fixed minimum of the3/5-neighbor settings reported in the primary CAFA5 paper, after pre-outcome known-label-only low-novelty coverage diagnostic of cosine1. Original cosine1 and its recipes remain retained.'}
    write_json(folder/'started.json',started)
    stats = None
    with tarfile.open(archive,mode='r|gz') as tar:
        for member in tar:
            if member.name != MEMBER: continue
            need(member.isfile() and stats is None,'invalid/duplicate fixed comparator member.')
            with gzip.GzipFile(filename=str(folder/'official_prott5_cosine3.tsv.gz'),mode='wb',mtime=0) as dst:
                stats=selected_rows(tar.extractfile(member),set(ids),dst)
    need(stats is not None,'fixed comparator member is missing.')
    result={**started,'status':'completed','created_at':utcnow(),'statistics':stats,
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in folder.iterdir()}}
    result['content_sha256']=digest(result);write_json(folder/'qualification.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','qualification','targets','diagnostic','output'):p.add_argument('--'+name,required=True)
    r=prepare(**vars(p.parse_args()));print(json.dumps({'content_sha256':r['content_sha256'],'statistics':r['statistics']}))


if __name__=='__main__':main()
