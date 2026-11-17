# SPDX-License-Identifier: GPL-3.0-only
"""Same-Brev numerical replay of the old547-target GM output, not a new arm.

The old reference/output is retained unchanged. Platform-dependent numerical
differences are reported separately; the new6100-target producer must match
this separately executed, pinned same-host replay exactly on common targets.
"""
import argparse
from collections import defaultdict
import gzip
import json
import os
from pathlib import Path
import platform
import time

from .run import load,read,sha,digest,write,need,OLD_FORECAST_SHA


def run(frozen,expected,author,author_receipt,old_forecast,old_manifest,output):
    import numpy as np
    import scipy
    from tools.cafa_prediction import core
    from tools.cafa_nonpk.gm_supplement import numerical_certificate,author_scores
    frozen=Path(frozen);p=load(frozen,expected)
    need(sha(old_forecast)==OLD_FORECAST_SHA,'original547 reference changed.')
    old_meta=read(old_manifest);need(old_meta['files']['strict_alias_genemaniaplus.tsv.gz']['sha256']==OLD_FORECAST_SHA,
                                  'original547 manifest binding differs.')
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False)
    runtime={'python':platform.python_version(),'system':platform.system(),'machine':platform.machine(),
        'numpy':np.__version__,'scipy':scipy.__version__,
        'thread_environment':{k:os.environ.get(k)for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}}
    pins={str(Path(x).resolve()):sha(x)for x in (Path(__file__),Path(core.__file__),
        Path(__file__).parents[1]/'cafa_nonpk/gm_supplement.py',Path(frozen)/'protocol.json',
        Path(author_receipt),Path(old_forecast),Path(old_manifest))}
    commitment={'format':'biograph-steward.combined-GM-same-host-replay.v1.freeze',
        'created_unix':time.time(),'input_files_sha256':pins,'parameters':core.PARAMETERS['genemaniaplus'],
        'graph_sha256':p['source']['graph_sha256'],'training_sha256':p['source']['training_sha256'],
        'runtime':runtime,'targets':'Exact original547 NK/LK identities; reference labels are never read.',
        'role':'Numerical replay control only, not replacement of old547 benchmark or an additional accuracy result.',
        'old_producer_platform':'Not directly recorded by old prediction manifest; /Users source paths indicate provenance, not conclusive execution architecture.',
        'previous_exact_cross_runtime_gate_failure_preserved':True,
        'raw_scores_clipped_or_changed':False,'evaluation_outcomes_read':False}
    commitment['content_sha256']=digest(commitment);write(folder/'protocol.json',commitment)
    modules=core.author_modules(author,author_receipt)
    graph=read(frozen/'graph.json.gz');nodes=graph['nodes'];index={x.removeprefix('UniProtKB:'):i for i,x in enumerate(nodes)}
    W=core.adjacency(nodes,graph['pairs']);del graph
    L=modules['gm'].setup_laplacian(W);M,certificate=numerical_certificate(W,L)
    terms=defaultdict(list)
    for protein,entries in read(frozen/'training.json.gz').items():
        for aspect,term in entries:terms[aspect,term].append(index[protein])
    heads=sorted(terms);rank={term:i for i,(aspect,term)in enumerate(heads)}
    targets=(frozen/'old_targets.txt').read_text().splitlines();indices=np.asarray([index[t]for t in targets],dtype=int)
    from .run import prior_groups
    groups=iter(prior_groups(old_forecast,set(targets),set(targets),rank));previous=next(groups,None)
    maximum_difference=0.;different_values=0;support_mismatches=0;positive_rows=0
    maximum_residual=0.;maximum_bound=0.;minimum_score=0.;negative_scores=0;maximum_iterations=0
    start=time.time()
    with gzip.GzipFile(filename=str(folder/'strict_alias_genemaniaplus.tsv.gz'),mode='wb',mtime=0)as stream:
        for step,((aspect,term),seeds)in enumerate(sorted(terms.items())):
            scores,d=author_scores(modules,L,M,certificate,seeds)
            maximum_residual=max(maximum_residual,d['equation_residual_norm']);maximum_bound=max(maximum_bound,d['componentwise_error_bound'])
            minimum_score=min(minimum_score,d['minimum_graph_score']);negative_scores+=d['negative_graph_scores'];maximum_iterations=max(maximum_iterations,d['iterations'])
            old_rows=previous[1]if previous is not None and previous[0]==step else []
            old={line.split('\t')[0]:float(line.rstrip().split('\t')[2])for line in old_rows}
            observed={}
            for protein,value in zip(targets,scores[indices]):
                if value>0:
                    observed[protein]=float(value);positive_rows+=1
                    stream.write((protein+'\t'+term+'\t'+format(float(value),'.17g')+'\n').encode())
            support_mismatches+=len(old.keys()^observed.keys())
            for protein in old.keys()|observed.keys():
                delta=abs(old.get(protein,0.)-observed.get(protein,0.));maximum_difference=max(maximum_difference,delta)
                different_values+=int(delta!=0)
                need(delta<=old_meta['maximum_componentwise_error_bound']+d['componentwise_error_bound']+1e-12,
                     'cross-runtime score differs beyond the two native certified solution error bounds.')
            if previous is not None and previous[0]==step:previous=next(groups,None)
            if (step+1)%2000==0:
                progress={'heads_completed':step+1,'positive_rows':positive_rows,'seconds':time.time()-start,
                    'original_vs_replay_max_abs_difference':maximum_difference,'support_mismatches':support_mismatches}
                write(folder/'progress.json',progress);print(json.dumps(progress),flush=True)
    need(previous is None,'original forecast has unmatched trailing heads.')
    for path,h in pins.items():need(sha(path)==h,'matched-replay source changed during execution.')
    load(frozen,expected)
    report={'format':'biograph-steward.combined-GM-same-host-replay.v1.predictions','created_unix':time.time(),
        'protocol_file_sha256':sha(folder/'protocol.json'),'protocol_content_sha256':commitment['content_sha256'],
        'runtime':runtime,'targets':len(targets),'heads':len(heads),'positive_rows':positive_rows,'wall_seconds':time.time()-start,
        'original_reference_unchanged':True,'original_vs_replay_different_values':different_values,
        'original_vs_replay_max_abs_difference':maximum_difference,'original_vs_replay_positive_support_mismatches':support_mismatches,
        'maximum_equation_residual_norm':maximum_residual,'maximum_componentwise_error_bound':maximum_bound,
        'minimum_native_graph_score':minimum_score,'negative_graph_score_values':negative_scores,'maximum_iterations':maximum_iterations,
        'matrix_certificate':certificate,'raw_scores_clipped_or_changed':False,'new_accuracy_evaluation':False,
        'files':{x.name:{'bytes':x.stat().st_size,'sha256':sha(x)}for x in folder.glob('*.tsv.gz')}}
    report['content_sha256']=digest(report);write(folder/'predictions.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('frozen','expected','author','author-receipt','old-forecast','old-manifest','output'):p.add_argument('--'+key,required=True)
    result=run(**vars(p.parse_args()));print(json.dumps({'content_sha256':result['content_sha256']}))
