# SPDX-License-Identifier: GPL-3.0-only
"""V2: unchanged GM cell, with an exact separately executed same-Brev control.

The v1 cross-runtime text-identity failure and original547 output are preserved.
Only the numerical reproducibility reference changes, before new cell scoring.
No prediction method, source, labels, normalization or outcome gate is changed.
"""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import shutil
import time
from .run import read,write,sha,digest,need,pin,target_frames,prior_groups,PARAMETERS

FORMAT='biograph-steward.cafa5-combined-development.v2'


def load(frozen,expected):
    frozen=Path(frozen);p=read(frozen/'protocol.json')
    need(sha(frozen/'protocol.json')==expected and p['content_sha256']==digest({k:v for k,v in p.items()if k!='content_sha256'}),'v2 freeze differs.')
    need(p['format']==FORMAT+'.freeze' and p['parameters']==PARAMETERS and p['previous_PK_NK_LK_outcomes_exposed'] is True,'development/defaults contract differs.')
    for name,h in p['files'].items():need(sha(frozen/name)==h,'frozen historical data changed.')
    return p


def prepare(v1,expected,matched_manifest,output):
    from .run import load as load_v1
    v1=Path(v1);original=load_v1(v1,expected);matched_manifest=Path(matched_manifest);m=read(matched_manifest)
    need(m['format']=='biograph-steward.combined-GM-same-host-replay.v1.predictions'
         and m['content_sha256']==digest({k:v for k,v in m.items()if k!='content_sha256'})
         and m['targets']==547 and m['heads']==17670 and m['original_reference_unchanged'] is True,
         'completed original547 same-host replay receipt is required.')
    replay_protocol_file=matched_manifest.with_name('protocol.json');replay=read(replay_protocol_file)
    need(sha(replay_protocol_file)==m['protocol_file_sha256']
         and replay['content_sha256']==m['protocol_content_sha256']
         and replay['content_sha256']==digest({k:v for k,v in replay.items()if k!='content_sha256'})
         and replay['graph_sha256']==original['source']['graph_sha256']
         and replay['training_sha256']==original['source']['training_sha256']
         and replay['parameters']==PARAMETERS and replay['runtime']==m['runtime']
         and expected in replay['input_files_sha256'].values(),
         'same-host replay is not bound to this exact v1 source/target/default packet.')
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False)
    for name,h in original['files'].items():
        shutil.copyfile(v1/name,folder/name);need(sha(folder/name)==h,'historical source copy differs.')
    p={k:v for k,v in original.items()if k not in ('content_sha256','created_unix','format')}
    p.update(format=FORMAT+'.freeze',created_unix=time.time(),
        original_v1_protocol=pin(v1/'protocol.json'),matched_runtime_replay_manifest=pin(matched_manifest),
        matched_runtime_forecast=m['files']['strict_alias_genemaniaplus.tsv.gz'],
        matched_runtime=m['runtime'],
        numerical_reproducibility_version=2,
        original547_benchmark_replaced=False,
        numerical_repair='Exact210 raw-row identity remains required, now against a separately executed same-Brev547 replay. Original cross-runtime differences and failed v1 remain explicit; no score clipping, tolerance relaxation, model/default/data/label or outcome-policy change.',
        overlap_check='Every positive row on210 common identities must equal the separately executed same-host547 replay, including empty/trailing-head checks.')
    p['input_pins']={**p['input_pins'],'code/cafa_combined/run_v2.py':pin(__file__),
                     'matched_runtime_replay_manifest':pin(matched_manifest),
                     'matched_runtime_replay_protocol':pin(replay_protocol_file)}
    p['content_sha256']=digest(p);write(folder/'protocol.json',p);return p


def predict(frozen,expected,author,author_receipt,old_forecast,output):
    import numpy as np
    import scipy,os,platform
    from tools.cafa_prediction import core
    from tools.cafa_nonpk.gm_supplement import numerical_certificate,author_scores
    frozen=Path(frozen);p=load(frozen,expected)
    runtime={'python':platform.python_version(),'system':platform.system(),'machine':platform.machine(),
        'numpy':np.__version__,'scipy':scipy.__version__,
        'thread_environment':{k:os.environ.get(k)for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}}
    need(runtime==p['matched_runtime'],'actual numerical runtime differs from the matched547 control.')
    code=p['input_pins']
    for key,path in [('code/cafa_combined/run_v2.py',Path(__file__)),('code/cafa_prediction/core.py',Path(core.__file__)),
        ('code/cafa_nonpk/gm_supplement.py',Path(__file__).parents[1]/'cafa_nonpk/gm_supplement.py')]:
        need(sha(path)==code[key]['sha256'],'pinned producer source differs: '+key)
    need(sha(author_receipt)==code['author_receipt']['sha256'] and sha(old_forecast)==p['matched_runtime_forecast']['sha256'],
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
    load(frozen,expected);need(sha(old_forecast)==p['matched_runtime_forecast']['sha256'],'old forecast changed during overlap audit.')
    for key,path in [('code/cafa_combined/run_v2.py',Path(__file__)),('code/cafa_prediction/core.py',Path(core.__file__)),
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
        'raw_scores_clipped_or_changed':False,'parameters':PARAMETERS,'execution_runtime':runtime,'development_exposed_label_reuse':True,
        'new_source_or_labels_retrieved':False,'files':{x.name:{'sha256':sha(x),'bytes':x.stat().st_size}for x in folder.glob('*.tsv.gz')}}
    report['content_sha256']=digest(report);write(folder/'predictions.json',report);return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for key in ('v1','expected','matched-manifest','output'):p.add_argument('--'+key,required=True)
    p=sub.add_parser('predict')
    for key in ('frozen','expected','author','author-receipt','old-forecast','output'):p.add_argument('--'+key,required=True)
    a=vars(parser.parse_args());command=a.pop('command');r=globals()[command](**a)
    print(json.dumps({'format':r['format'],'content_sha256':r['content_sha256']}))
