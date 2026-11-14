# SPDX-License-Identifier: GPL-3.0-only
"""Combine the locked strict source profile with published GeneMANIA+.

This is explicitly development reuse of already exposed CAFA outcomes. It adds
one fixed method/source cell without changing previous forecasts, source files,
labels, parameters or official evaluator behavior. Large outputs stay on Brev.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

FORMAT = 'biograph-steward.cafa5-combined-development.v1'
STRICT_SHA = '539abc8840afe90fd67d2dfefe5f22e7dc538978281e483bdcf45221b4ee4502'
GRAPH_SHA = '41547ab466240f05b99e361f3f1b1f16afbbcd0e2c17d8f0c49d8a8668f0de9b'
TRAINING_SHA = 'e699fe01fdb65e3dbcbbb2d977da0f87ec00e3f3d85df7586e2c14617b7d1ad8'
OLD_FORECAST_SHA = 'e870d5bc7a74aec9ad1e901a9409e873110d3caf739cf66c5ce998ddf6897756'
PARAMETERS = {'alpha': 1, 'tol': .00001}


def need(value, message):
    if not value:
        raise ValueError('Combined development: '+message)


def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):
            result.update(block)
    return result.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def read(path):
    path=Path(path)
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as stream:
        return json.load(stream)


def pin(path):
    path=Path(path).resolve()
    need(path.is_file() and not path.is_symlink(),'ordinary pinned source required.')
    return {'file':str(path),'bytes':path.stat().st_size,'sha256':sha(path)}


def target_frames(primary,reserved,old):
    a=Path(primary).read_text().splitlines();b=Path(reserved).read_text().splitlines()
    c=Path(old).read_text().splitlines()
    for rows in (a,b,c):
        need(rows==sorted(set(rows)),'target identities must be sorted and unique.')
        need(all(p and p.isalnum() and len(p) in (6,10) for p in rows),'exact accession identities required.')
    need(len(a)==1294 and len(b)==4806 and len(c)==547 and not(set(a)&set(b)),
         'preserved original/reserve/earlier transport frames differ.')
    common=sorted((set(a)|set(b))&set(c))
    need(len(set(a)&set(c))==26 and len(set(b)&set(c))==184 and len(common)==210,
         'the declared common-target identity audit differs.')
    return {'primary':a,'reserved':b},c,common


def prepare(strict,old_frozen,old_forecasts,author_receipt,output):
    strict,old_frozen,old_forecasts,author_receipt=map(Path,(strict,old_frozen,old_forecasts,author_receipt))
    need(sha(strict/'protocol.json')==STRICT_SHA and sha(strict/'graph.json.gz')==GRAPH_SHA
         and sha(strict/'training.json.gz')==TRAINING_SHA,'locked strict source packet differs.')
    need(sha(old_forecasts/'strict_alias_genemaniaplus.tsv.gz')==OLD_FORECAST_SHA,
         'earlier547-target native GM output differs.')
    frames,old,common=target_frames(strict/'primary_targets.txt',strict/'reserved_targets.txt',old_frozen/'targets.txt')
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False)
    for name in ('graph.json.gz','training.json.gz','primary_targets.txt','reserved_targets.txt'):
        shutil.copyfile(strict/name,folder/name)
    (folder/'old_targets.txt').write_text('\n'.join(old)+'\n')
    (folder/'common_targets.txt').write_text('\n'.join(common)+'\n')
    package=Path(__file__).parents[1]
    code=[Path(__file__),package/'cafa_prediction/core.py',package/'cafa_prediction/run.py',
          package/'cafa_nonpk/gm_supplement.py',package/'cafa_nonpk/run.py']
    inputs={'strict_protocol':pin(strict/'protocol.json'),'author_receipt':pin(author_receipt),
        'old_gm_protocol':pin(old_forecasts/'protocol.json'),
        'old_gm_manifest':pin(old_forecasts/'predictions.json'),
        'old_gm_forecast':pin(old_forecasts/'strict_alias_genemaniaplus.tsv.gz')}
    inputs.update({'code/'+p.relative_to(package).as_posix():pin(p) for p in code})
    need(len(inputs)==10,'source pin role collision.')
    protocol={'format':FORMAT+'.freeze','created_unix':time.time(),
        'scope':'Exposed-label DEVELOPMENT combination, not a fresh independent/prospective benchmark.',
        'method':'strict_alias_genemaniaplus','parameters':PARAMETERS,
        'source':{'nodes':20412,'undirected_weighted_pairs':985863,'historical_features_only':True,
            'graph_sha256':GRAPH_SHA,'training_sha256':TRAINING_SHA},
        'targets':{'primary':1294,'reserved':4806,'union':6100,'prior_output_common':210,
            'prior_common_primary':26,'prior_common_reserved':184},
        'previous_PK_NK_LK_outcomes_exposed':True,'new_labels_opened_or_retrieved':False,
        'feature_annotation_cutoff':'Official known_t0 at the2023 CAFA submission deadline.',
        'choice_reason':'One previously missing cell: fuller strict historical source plus the fixed published GM method.',
        'no_new_hyperparameter_score_threshold_or_fusion_selection':True,
        'output_policy':'Full precision raw positive scores; missing output is arithmetic zero, not negative biology.',
        'numerical_policy':'Unchanged author CG and tested numerical_certificate/author_scores wrapper; no score clipping.',
        'overlap_check':'All raw positive rows for210 common target identities must exactly match the earlier547-target output.',
        'evaluation':{'contract':'Unchanged official CAFA evaluator and existing released PK truth/known masks.',
            'settings':['primary/partial','reserved/partial'],
            'namespaces':['biological_process','molecular_function','cellular_component'],
            'readouts':['micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax','Smin','fixed_0_5'],
            'original_240_slot_results':'Preserved as earlier comparison source; append the six new outcomes separately.',
            'controls':'All previously frozen controls remain reported; no new baseline/recipe selection.',
            'BPO_paired':{'draws':2000,'seed':20261113,'primary':['genemaniaplus','strict_alias_localplus','localplus'],
                'reserved':['strict_alias_localplus','official_prott5_cosine3','official_nonexperimental'],
                'interaction':'Original cohort only: (fullGM-fullLocal)-(oldGM-oldLocal), descriptive.',
                'oldGM_reserved':'Unsupported coverage-only: every reserve ID is outside the old source graph; no superiority interval invented.'}},
        'retention_gate':'Before reading new cell outcomes: retain a practical combination advantage only if ordinary and IA BPO paired95% difference intervals versus matched full strict Local exclude zero above on both existing cohorts; additionally show original versus oldGM and all macro/fixed-cutoff/control trade-offs. This is development selection, never confirmatory evidence.',
        'failure_policy':'Preserve partial outputs/failures, report all outcomes; no parameter sweep or automatic promotion.',
        'GPL_runtime_separate_from_MIT_app':True,'app_graph_or_review_changes':False,
        'input_pins':inputs,'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
    protocol['content_sha256']=digest(protocol);write(folder/'protocol.json',protocol)
    return protocol


def load(frozen,expected):
    frozen=Path(frozen);p=read(frozen/'protocol.json')
    need(sha(frozen/'protocol.json')==expected and p['content_sha256']==digest({k:v for k,v in p.items()if k!='content_sha256'}),
         'development freeze differs.')
    need(p['format']==FORMAT+'.freeze' and p['parameters']==PARAMETERS and p['previous_PK_NK_LK_outcomes_exposed'] is True,
         'fixed method/development exposure contract differs.')
    for name,h in p['files'].items():need(sha(frozen/name)==h,'frozen data changed: '+name)
    return p


def prior_groups(path,all_targets,common,rank):
    """Read each old head once; retained rows remain exact original text."""
    previous=-1;current=None;rows=[];last_protein=None
    with gzip.open(path,'rt',newline='') as stream:
        for line in stream:
            parts=line.rstrip('\n').split('\t')
            need(len(parts)==3 and parts[0] in all_targets and parts[1] in rank,'earlier forecast frame differs.')
            value=float(parts[2]);need(math.isfinite(value) and value>0,'earlier forecast is not raw positive scores.')
            head=rank[parts[1]]
            if head!=current:
                if current is not None:yield current,rows
                need(head>previous,'earlier forecast term order repeats or changes.')
                previous=head;current=head;rows=[];last_protein=None
            need(last_protein is None or parts[0]>last_protein,'earlier term-target pair repeats or changes order.')
            last_protein=parts[0]
            if parts[0] in common:rows.append(line)
        if current is not None:yield current,rows


def predict(frozen,expected,author,author_receipt,old_forecast,output):
    import numpy as np
    from tools.cafa_prediction import core
    from tools.cafa_nonpk.gm_supplement import numerical_certificate,author_scores
    frozen=Path(frozen);p=load(frozen,expected)
    code=p['input_pins']
    for key,path in [('code/cafa_combined/run.py',Path(__file__)),('code/cafa_prediction/core.py',Path(core.__file__)),
        ('code/cafa_nonpk/gm_supplement.py',Path(__file__).parents[1]/'cafa_nonpk/gm_supplement.py')]:
        need(sha(path)==code[key]['sha256'],'pinned producer source differs: '+key)
    need(sha(author_receipt)==code['author_receipt']['sha256'] and sha(old_forecast)==OLD_FORECAST_SHA,
         'pinned author source or old forecast differs.')
    need(core.PARAMETERS['genemaniaplus']==PARAMETERS,'published defaults changed.')
    need(shutil.disk_usage(Path(output).parent).free>=4*1024**3,'Require4GiB free output space; do not delete existing artifacts.')
    modules=core.author_modules(author,author_receipt)
    graph=read(frozen/'graph.json.gz');nodes=graph['nodes'];need(len(nodes)==20412 and len(graph['pairs'])==985863,'strict graph frame differs.')
    index={x.removeprefix('UniProtKB:'):i for i,x in enumerate(nodes)}
    W=core.adjacency(nodes,graph['pairs']);del graph
    L=modules['gm'].setup_laplacian(W);M,certificate=numerical_certificate(W,L)
    terms=defaultdict(list)
    for protein,annotations in read(frozen/'training.json.gz').items():
        for aspect,term in annotations:terms[aspect,term].append(index[protein])
    heads=sorted(terms);need(len(heads)==17670,'historical training-head inventory differs.')
    rank={term:i for i,(aspect,term)in enumerate(heads)};need(len(rank)==len(heads),'GO term namespaces collide.')
    frames,old,common=target_frames(frozen/'primary_targets.txt',frozen/'reserved_targets.txt',frozen/'old_targets.txt')
    targets=sorted(frames['primary']+frames['reserved']);frame_of={t:k for k,v in frames.items()for t in v}
    target_indices=np.asarray([index[t]for t in targets],dtype=int);common=set(common)
    old_groups=iter(prior_groups(old_forecast,set(old),common,rank));previous=next(old_groups,None)
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False)
    write(folder/'execution_started.json',{'protocol_file_sha256':expected,'method':p['method'],
        'previous_evaluation_labels_exposed':True,'new_source_or_labels_retrieved':False,'created_unix':time.time()})
    streams={key:gzip.GzipFile(filename=str(folder/(key+'_strict_alias_genemaniaplus.tsv.gz')),mode='wb',mtime=0)for key in frames}
    counts={key:0 for key in frames};common_rows=0;maximum_residual=0.;maximum_bound=0.;negative_scores=0;minimum_score=0.;maximum_iterations=0
    start=time.time()
    try:
        for step,((aspect,term),positives)in enumerate(sorted(terms.items())):
            scores,diagnostic=author_scores(modules,L,M,certificate,positives)
            maximum_residual=max(maximum_residual,diagnostic['equation_residual_norm'])
            maximum_bound=max(maximum_bound,diagnostic['componentwise_error_bound'])
            maximum_iterations=max(maximum_iterations,diagnostic['iterations'])
            negative_scores+=diagnostic['negative_graph_scores'];minimum_score=min(minimum_score,diagnostic['minimum_graph_score'])
            overlap=[]
            for protein,value in zip(targets,scores[target_indices]):
                if value>0:
                    line=protein+'\t'+term+'\t'+format(float(value),'.17g')+'\n'
                    streams[frame_of[protein]].write(line.encode());counts[frame_of[protein]]+=1
                    if protein in common:overlap.append(line)
            expected_rows=previous[1] if previous is not None and previous[0]==step else []
            need(overlap==expected_rows,'common-target raw positive scores differ at head '+str(step))
            common_rows+=len(overlap)
            if previous is not None and previous[0]==step:previous=next(old_groups,None)
            if (step+1)%2000==0:
                need(shutil.disk_usage(folder).free>=1024**3,'Less than1GiB free; preserve partial forecasts and fail.')
                progress={'heads_completed':step+1,'heads':len(heads),'wall_seconds':time.time()-start,'positive_rows':counts,'common_raw_rows_identical':common_rows}
                write(folder/'progress.json',progress);print(json.dumps(progress),flush=True)
        need(previous is None,'earlier output has unmatched trailing heads.')
    finally:
        for stream in streams.values():stream.close()
    load(frozen,expected);need(sha(old_forecast)==OLD_FORECAST_SHA,'old forecast changed during overlap audit.')
    for key,path in [('code/cafa_combined/run.py',Path(__file__)),('code/cafa_prediction/core.py',Path(core.__file__)),
        ('code/cafa_nonpk/gm_supplement.py',Path(__file__).parents[1]/'cafa_nonpk/gm_supplement.py')]:
        need(sha(path)==code[key]['sha256'],'producer source changed during execution.')
    report={'format':FORMAT+'.predictions','created_unix':time.time(),'protocol_file_sha256':expected,
        'protocol_content_sha256':p['content_sha256'],'target_counts':{k:len(v)for k,v in frames.items()},
        'heads':len(heads),'positive_rows':counts,'wall_seconds':time.time()-start,
        'prior_common_target_identities':210,'prior_common_raw_positive_rows':common_rows,
        'prior_common_raw_positive_rows_exactly_identical':True,'all_heads_passed_unchanged_author_residual_check':True,
        'matrix_certificate':certificate,'maximum_equation_residual_norm':maximum_residual,
        'maximum_componentwise_error_bound':maximum_bound,'negative_graph_score_values':negative_scores,
        'minimum_native_graph_score':minimum_score,'maximum_iterations':maximum_iterations,
        'raw_scores_clipped_or_changed':False,'parameters':PARAMETERS,'development_exposed_label_reuse':True,
        'new_source_or_labels_retrieved':False,'files':{x.name:{'sha256':sha(x),'bytes':x.stat().st_size}for x in folder.glob('*.tsv.gz')}}
    report['content_sha256']=digest(report);write(folder/'predictions.json',report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('prepare')
    for name in ('strict','old-frozen','old-forecasts','author-receipt','output'):a.add_argument('--'+name,required=True)
    a=s.add_parser('predict')
    for name in ('frozen','expected','author','author-receipt','old-forecast','output'):a.add_argument('--'+name,required=True)
    a=vars(p.parse_args());command=a.pop('command');r=globals()[command](**a)
    print(json.dumps({'format':r['format'],'content_sha256':r['content_sha256']}))


if __name__=='__main__':main()
