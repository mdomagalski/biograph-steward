"""Pre-outcome full-network context ablation using unchanged author predictors."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import json
import multiprocessing
from pathlib import Path
import time

from .core import adjacency, author_modules, graph_frame, need, ontology_terms, run_term, sha, training_annotations
from .run import digest, load_frozen, new_output, pin, read, timestamp, verify_pins, write

ARMS = {
    'global_induced_oldseeds_fss': {'graph':'induced','seeds':'old','method':'fastsinksourceplus'},
    'global_full_oldseeds_fss': {'graph':'full','seeds':'old','method':'fastsinksourceplus'},
    'global_full_allseeds_fss': {'graph':'full','seeds':'all','method':'fastsinksourceplus'},
    'global_full_allseeds_local': {'graph':'full','seeds':'all','method':'localplus'},
}
_STATE = None


def prepare(config_path, output):
    config=read(config_path)
    need(set(config)=={'parent_freeze','parent_protocol_sha256','full_qualification'},'exact scope-extension configuration required.')
    parent=load_frozen(config['parent_freeze'],config['parent_protocol_sha256'])
    q=read(config['full_qualification']); fullbase=Path(config['full_qualification']).parent
    need(q['format']=='biograph-steward.qualified-full-pharos319-string11.v1' and q['future_GO_labels_read'] is False
         and q['content_sha256']==digest({k:v for k,v in q.items() if k!='content_sha256'}),'full historical source qualification differs.')
    pins={'full_qualification':pin(config['full_qualification']),'configuration':pin(config_path),'adapter':pin(__file__)}
    for name,item in q['files'].items():
        need(sha(fullbase/name)==item['sha256'],'full source data changed.')
        pins['full/'+name]=pin(fullbase/name)
    nodes,pairs=graph_frame(fullbase/'network_nodes.tsv',fullbase/'weighted_pairs.tsv')
    need(len(nodes)==q['protein_nodes'] and len(pairs)==q['qualified_weighted_pairs'],'full qualified graph count differs.')
    oldgraph=read(Path(config['parent_freeze'])/'graph.json.gz'); oldnodes=oldgraph['nodes']; oldset=set(oldnodes)
    need(oldset<=set(nodes),'old graph node lost from full source.')
    oldpairs={tuple(sorted((a,b))):w for a,b,w in oldgraph['pairs']}
    induced=[(a,b,w) for a,b,w in pairs if a in oldset and b in oldset]
    # Some global induced pairs were not in the prior source extraction. Keep
    # the control limited to exact originally admitted pairs to isolate mapping.
    induced=[(a,b,w) for a,b,w in induced if tuple(sorted((a,b))) in oldpairs]
    need(len(induced)==q['old_pairs_carried_with_identical_weights'],'globally requalified original control count differs.')
    for a,b,w in induced: need(abs(w-oldpairs[tuple(sorted((a,b)))])<1e-12,'old carried weight changed.')
    known=parent['input_pins']['known_t0']['file']; ontology=parent['input_pins']['ontology']['file']
    labels,frequency,counts=training_annotations(known,nodes,ontology_terms(ontology))
    oldlabels=read(Path(config['parent_freeze'])/'training.json.gz')
    need({p:[list(entry) for entry in sorted(v)] for p,v in labels.items() if 'UniProtKB:'+p in oldset}==oldlabels,'old seed annotations differ in full extraction.')
    targets=(Path(config['parent_freeze'])/'targets.txt').read_text().splitlines()
    folder=new_output(output)
    write(folder/'full_graph.json.gz',{'nodes':nodes,'pairs':pairs})
    write(folder/'induced_graph.json.gz',{'nodes':oldnodes,'pairs':induced})
    write(folder/'all_training.json.gz',{p:sorted(v) for p,v in labels.items()})
    write(folder/'old_training.json.gz',oldlabels)
    (folder/'targets.txt').write_text('\n'.join(targets)+'\n')
    oldterms=sorted({t for entries in oldlabels.values() for _,t in entries})
    (folder/'original_terms.txt').write_text('\n'.join(oldterms)+'\n')
    allterms={t for entries in labels.values() for _,t in entries}
    # Embed the immutable historical authority; remote execution validates this
    # self-contained packet, while local qualification validates source paths.
    write(folder/'parent_protocol.json',parent); write(folder/'full_qualification.json',q)
    sources={'known_t0':pin(known),'ontology':pin(ontology),'core':pin(Path(__file__).with_name('core.py')),'runner':pin(Path(__file__).with_name('run.py'))}
    sources.update(pins); verify_pins(sources)
    receipt={'format':'biograph-steward.cafa5-full-context-freeze.v1','created_at':timestamp(),
        'input_pins':sources,'parent_protocol_file_sha256':config['parent_protocol_sha256'],
        'parent_protocol_content_sha256':parent['content_sha256'],'full_qualification_content_sha256':q['content_sha256'],
        'arms':ARMS,'parameters':parent['methods'],'runtime':parent['runtime'],'author_commit':parent['author_commit'],
        'counts':{**counts,'full_nodes':len(nodes),'full_pairs':len(pairs),'old_nodes':len(oldnodes),'old_global_pairs':len(induced),
            'all_seed_proteins':sum(bool(v) for v in labels.values()),'old_seed_proteins':sum(bool(v) for v in oldlabels.values()),
            'all_seed_terms':len(allterms),'original_seed_terms':len(oldterms),'new_heads':len(allterms-set(oldterms)),'targets':len(targets)},
        'primary_candidate_changed':False,'future_GO_labels_read':False,'automatic_graph_change':False,
        'purpose':'Fixed secondary graph-context/seeds/vocabulary decomposition. Compare full old-seeds vs globally requalified induced control, then full all-seeds vs full old-seeds. Compare full all-seeds FSS vs matched full LocalPlus. New term heads are separated with the predeclared original_terms sensitivity.',
        'head_sensitivity':'Each all-seed arm emits both complete available training vocabulary and separately the exact original9753term subset. Do not select between them after scoring.',
        'inference_scope':'All1294 prior exact target identities, including isolates and globally ambiguous mappings retained as nodes. Missing annotations are not biological negatives. Source assertions are not pruned by this experiment.',
        'interpretation_limits':['Archived canonical accession/locus correspondence, not verified construct/sequence/isoform identity.','Global ambiguity quarantine is eligibility abstention, not evidence that an interaction is biologically false.','This scope extension was fixed before opening CAFA5 future GO terms; it is a secondary intervention, not a retrospective replacement for the primary candidate.'],
        'files':{p.name:sha(p) for p in sorted(folder.iterdir())}}
    receipt['content_sha256']=digest(receipt); write(folder/'protocol.json',receipt); return receipt


def load_packet(folder, expected):
    folder=Path(folder); p=read(folder/'protocol.json')
    need(sha(folder/'protocol.json')==expected and p['content_sha256']==digest({k:v for k,v in p.items() if k!='content_sha256'}),'full packet protocol seal differs.')
    need(p['arms']==ARMS and p['future_GO_labels_read'] is False,'full packet method choices differ.')
    for role,path in [('adapter',Path(__file__)),('core',Path(__file__).with_name('core.py')),('runner',Path(__file__).with_name('run.py'))]:
        need(sha(path)==p['input_pins'][role]['sha256'],'scope execution code differs from frozen preparation: '+role)
    for name,s in p['files'].items(): need(sha(folder/name)==s,'full packet body changed: '+name)
    return p


def _term(task):
    method,aspect,term,positives=task
    modules,P,targets=_STATE
    scores,diagnostic=run_term(modules,P,None,positives,method)
    return aspect,term,scores[targets],diagnostic


def predict(frozen, expected, author_directory, author_receipt, output, workers):
    global _STATE
    import numpy as np
    need(1<=workers<=8,'bounded1..8CPU workers required.')
    frozen=Path(frozen); p=load_packet(frozen,expected)
    modules=author_modules(author_directory,author_receipt)
    targets=(frozen/'targets.txt').read_text().splitlines(); originalterms=set((frozen/'original_terms.txt').read_text().splitlines())
    folder=new_output(output); write(folder/'execution_started.json',{'protocol_file_sha256':expected,'created_at':timestamp(),'workers':workers,'future_GO_labels_read':False})
    all_labels=read(frozen/'all_training.json.gz'); old_labels=read(frozen/'old_training.json.gz')
    reports={}; diagnostics=[]; lastgraph=None
    for name,arm in ARMS.items():
        start=time.time()
        if arm['graph']!=lastgraph:
            graph=read(frozen/(arm['graph']+'_graph.json.gz')); nodes=graph['nodes']; index={n.split(':',1)[1]:i for i,n in enumerate(nodes)}
            P=modules['alg_utils'].normalizeGraphEdgeWeights(adjacency(nodes,graph['pairs'])); lastgraph=arm['graph']
            del graph
        target_index=np.asarray([index[t] for t in targets],dtype=int); _STATE=(modules,P,target_index)
        labels=old_labels if arm['seeds']=='old' else all_labels
        terms=defaultdict(list)
        for protein,entries in labels.items():
            for aspect,term in entries: terms[(aspect,term)].append(index[protein])
        tasks=[(arm['method'],aspect,term,positive) for (aspect,term),positive in sorted(terms.items())]
        rows=0; sensitivity_rows=0
        with gzip.GzipFile(filename=str(folder/(name+'.tsv.gz')),mode='wb',mtime=0) as stream:
            sensitivity=gzip.GzipFile(filename=str(folder/(name+'_originalheads.tsv.gz')),mode='wb',mtime=0) if arm['seeds']=='all' else None
            try:
                with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('fork')) as pool:
                    for step,(aspect,term,scores,diagnostic) in enumerate(pool.map(_term,tasks,chunksize=8),1):
                        for target,value in zip(targets,scores):
                            if value>0:
                                body=(target+'\t'+term+'\t'+format(float(value),'.17g')+'\n').encode(); stream.write(body); rows+=1
                                if sensitivity and term in originalterms: sensitivity.write(body); sensitivity_rows+=1
                        diagnostics.append({'arm':name,'aspect':aspect,'term':term,**diagnostic})
                        if step%1000==0: print(json.dumps({'arm':name,'terms':step,'total':len(tasks),'seconds':time.time()-start}),flush=True)
            finally:
                if sensitivity: sensitivity.close()
        reports[name]={'terms':len(tasks),'emitted_rows':rows,'originalhead_rows':sensitivity_rows,'seconds':time.time()-start}
        print(json.dumps({'completed':name,**reports[name]}),flush=True)
    write(folder/'diagnostics.json.gz',diagnostics); load_packet(frozen,expected)
    result={'format':'biograph-steward.cafa5-full-context-predictions.v1','created_at':timestamp(),'protocol_file_sha256':expected,
        'protocol_content_sha256':p['content_sha256'],'arms':reports,'future_GO_labels_read':False,
        'files':{f.name:{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(folder.iterdir())}}
    result['content_sha256']=digest(result); write(folder/'predictions.json',result); return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare'); a.add_argument('--config',required=True); a.add_argument('--output',required=True)
    a=sub.add_parser('predict'); a.add_argument('--frozen',required=True); a.add_argument('--protocol-sha256',required=True); a.add_argument('--author-directory',required=True); a.add_argument('--author-receipt',required=True); a.add_argument('--output',required=True); a.add_argument('--workers',type=int,default=4)
    args=parser.parse_args(); result=prepare(args.config,args.output) if args.command=='prepare' else predict(args.frozen,args.protocol_sha256,args.author_directory,args.author_receipt,args.output,args.workers)
    print(result['content_sha256'])
