"""Separate fixed paper-reported K=3 control; original K=1 arms stay intact."""
import argparse
import gzip
import json
from pathlib import Path
import sqlite3
import tempfile

from biograph_steward.client import digest as native_digest
from .core import need, sha
from .fusion import load_scores, verify_baselines
from .run import digest, load_frozen, new_output, pin, read, timestamp, verify_pins, write


def combine(config_path, output):
    config=read(config_path)
    need(set(config)=={'original_fusion_config','cosine3','cosine3_qualification'}, 'exact K3 extension configuration required.')
    original=read(config['original_fusion_config']); verify_baselines(original)
    parent=read(original['prediction_manifest']); base=Path(original['prediction_manifest']).parent
    need(parent['content_sha256']==digest({k:v for k,v in parent.items() if k!='content_sha256'}), 'parent prediction seal differs.')
    protocol=load_frozen(original['prediction_freeze'],parent['protocol_file_sha256'])
    targets=Path(original['targets']).read_text().splitlines()
    need(sha(original['targets'])==protocol['files']['targets.txt'], 'target frame differs.')
    q=read(config['cosine3_qualification'])
    need(q['format']=='biograph-steward.cafa5-paper-control-intake.v1' and q['status']=='completed'
         and q['future_GO_labels_opened'] is False and q['score_rescaling'] is False and q['neighbor_count_sweep'] is False
         and q['content_sha256']==native_digest({k:v for k,v in q.items() if k!='content_sha256'})
         and q['files']['official_prott5_cosine3.tsv.gz']['sha256']==sha(config['cosine3'])
         and q['target_file_sha256']==sha(original['targets'])
         and q['original_baseline_qualification_file_sha256']==sha(original['baseline_qualification']), 'K3 source qualification differs.')
    sources={'prott5_cosine1':Path(config['cosine3']), 'fastsinksourceplus':base/'fastsinksourceplus.tsv.gz','localplus':base/'localplus.tsv.gz'}
    for method in ('fastsinksourceplus','localplus'):
        need(sha(sources[method])==parent['files'][method+'.tsv.gz']['sha256'],'parent scores changed.')
    mapping=read(original['canonical_alias_map']); canonical={**mapping['primary'],**mapping['alternative']}
    pins={key:pin(value) for key,value in sources.items()}
    pins.update({key:pin(original[key]) for key in ('prediction_manifest','targets','baseline_qualification','canonical_alias_map')})
    pins.update({key:pin(config[key]) for key in ('original_fusion_config','cosine3_qualification')})
    pins['adapter']=pin(__file__); pins['shared_fusion_adapter']=pin(Path(__file__).with_name('fusion.py')); pins['configuration']=pin(config_path)
    folder=new_output(output)
    recipe={'format':'biograph-steward.cafa5-fixed-cosine3-fusion.v1','created_at':timestamp(),'input_pins':pins,
        'arms':{'prott5_cosine3_fss_half':{'components':['official_prott5_cosine3','fastsinksourceplus'],'weights':[.5,.5]},'prott5_cosine3_local_half':{'components':['official_prott5_cosine3','localplus'],'weights':[.5,.5]}},
        'reason':q['selection_basis'],'future_GO_labels_read':False,'primary_candidate_changed':False,
        'missing_component':'zero numerical prediction score; no biological-negative assertion',
        'score_processing':'Explicit frozen GO aliases/maxduplicates; unchanged source scores; no rescaling/clipping/threshold fitting.',
        'implementation_note':'Reuse the previously validated bounded SQLite component loader. Its internal prott5_cosine1 slot holds exactly the separately qualified K3 file in this separate invocation; output names and pins identify K3 explicitly.'}
    recipe['content_sha256']=digest(recipe); write(folder/'fusion_protocol.json',recipe)
    diagnostics={}; emitted={}
    with tempfile.TemporaryDirectory(prefix='biograph-cafa-k3-') as temporary:
        db=sqlite3.connect(str(Path(temporary)/'scores.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF'); db.execute('PRAGMA cache_size=-131072')
            db.execute('CREATE TABLE scores(protein TEXT,term TEXT,prott5_cosine1 REAL DEFAULT 0,fastsinksourceplus REAL DEFAULT 0,localplus REAL DEFAULT 0,PRIMARY KEY(protein,term)) WITHOUT ROWID')
            for role,path in sources.items():
                diagnostics[role]=load_scores(db,path,set(targets),role,canonical); print(role,flush=True)
            for name,method in [('prott5_cosine3_fss_half','fastsinksourceplus'),('prott5_cosine3_local_half','localplus')]:
                n=0
                with gzip.GzipFile(filename=str(folder/(name+'.tsv.gz')),mode='wb',mtime=0) as stream:
                    for p,t,v in db.execute('SELECT protein,term,.5*prott5_cosine1+.5*'+method+' FROM scores WHERE prott5_cosine1>0 OR '+method+'>0 ORDER BY protein,term'):
                        stream.write((p+'\t'+t+'\t'+format(v,'.17g')+'\n').encode()); n+=1
                emitted[name]=n
        finally: db.close()
    verify_pins(pins)
    result={'format':recipe['format']+'.results','created_at':timestamp(),'protocol_file_sha256':sha(folder/'fusion_protocol.json'),'protocol_content_sha256':recipe['content_sha256'],
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(folder.iterdir())},'emitted_rows':emitted,'diagnostics':diagnostics,'future_GO_labels_read':False}
    result['content_sha256']=digest(result); write(folder/'fusion_predictions.json',result); return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--config',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); result=combine(args.config,args.output); print(result['content_sha256'])
