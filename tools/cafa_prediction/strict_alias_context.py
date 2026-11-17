"""Final pre-outcome temporal-alias sensitivity; exact same author predictors."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import multiprocessing
from pathlib import Path
import time

from . import full_context
from .core import adjacency, author_modules, need, sha
from .run import digest, new_output, pin, read, timestamp, verify_pins, write

METHODS=('fastsinksourceplus','localplus')


def prepare(parent_folder,parent_sha,reserved_folder,reserved_sha,audit_path,output):
    parent_folder=Path(parent_folder).resolve(); parent=full_context.load_packet(parent_folder,parent_sha)
    reserved_folder=Path(reserved_folder).resolve(); reserved=full_context.load_packet(reserved_folder,reserved_sha)
    need(reserved['derives_from_full_context_content_sha256']==parent['content_sha256'],'reserved source model differs.')
    audit=read(audit_path)
    need(audit['format']=='biograph-steward.full-source-historical-alias-presence-audit.v1'
         and audit['future_GO_labels_read'] is False
         and audit['content_sha256']==digest({k:v for k,v in audit.items() if k!='content_sha256'}),'historical alias audit differs.')
    source_qualification=read(parent_folder/'full_qualification.json')
    need(audit['input_pins']['qualified_weights']['sha256']==source_qualification['files']['weighted_pairs.tsv']['sha256'],'alias audit uses different source graph.')
    absent=set(audit['qualified_endpoint_proteins_without_exact_historical_alias_match'])
    graph=read(parent_folder/'full_graph.json.gz'); pairs=graph['pairs']
    strict=[(a,b,w) for a,b,w in pairs if a.split(':',1)[1] not in absent and b.split(':',1)[1] not in absent]
    removed=len(pairs)-len(strict)
    need(removed==audit['qualified_edges_touching_missing_exact_alias_match'],'temporal alias exclusion count differs.')
    primary=(parent_folder/'targets.txt').read_text().splitlines(); transfer=(reserved_folder/'targets.txt').read_text().splitlines()
    need(not(set(primary)&set(transfer)) and len(primary)==1294 and len(transfer)==4806,'exact disjoint frames differ.')
    folder=new_output(output); write(folder/'graph.json.gz',{'nodes':graph['nodes'],'pairs':strict})
    for name,origin in [('training.json.gz',parent_folder/'all_training.json.gz'),('primary_targets.txt',parent_folder/'targets.txt'),('reserved_targets.txt',reserved_folder/'targets.txt')]:
        import shutil
        shutil.copyfile(origin,folder/name)
    pins={'primary_protocol':pin(parent_folder/'protocol.json'),'reserved_protocol':pin(reserved_folder/'protocol.json'),
        'alias_audit':pin(audit_path),'adapter':pin(__file__),'shared_context_adapter':pin(full_context.__file__),
        'core':pin(Path(__file__).with_name('core.py')),'runner':pin(Path(__file__).with_name('run.py'))}
    p={'format':'biograph-steward.cafa5-temporal-alias-sensitivity-freeze.v1','created_at':timestamp(),'input_pins':pins,
        'parent_full_context_content_sha256':parent['content_sha256'],'methods':{m:parent['parameters'][m] for m in METHODS},
        'targets':{'primary':len(primary),'reserved':len(transfer),'union':len(primary)+len(transfer)},
        'nodes':len(graph['nodes']),'original_full_edges':len(pairs),'strict_alias_edges':len(strict),
        'abstained_edges':removed,'unattested_mapping_nodes_retained_as_isolates':sorted(absent),
        'policy':'Exact native Jan2019 accession-to-archivedENSP alias presence, all literal source provenances includingBLAST retained. Do not infer sequence/isoform equivalence. Unknown mappings abstain from adjacency, not biologicalfalse/prune labels.',
        'computation':'Same full known_t0 seeds, all17670heads, unchanged authorFSS andLocalPlus parameters, compute all6100scores once then split exact disjointidentityframes. No new scorecalibration or termfilter. Original full-context predictions remain preserved.',
        'role':'Fixed source-eligibility sensitivity, not a performance-selected replacement or new primary candidate.',
        'future_GO_labels_read':False,'final_preoutcome_recipe':True,'files':{f.name:sha(f) for f in sorted(folder.iterdir())}}
    p['content_sha256']=digest(p); write(folder/'protocol.json',p); return p


def load_packet(folder,expected):
    folder=Path(folder); p=read(folder/'protocol.json')
    need(sha(folder/'protocol.json')==expected and p['content_sha256']==digest({k:v for k,v in p.items() if k!='content_sha256'}),'strict source packet seal differs.')
    need(list(p['methods'])==sorted(METHODS) and p['future_GO_labels_read'] is False,'strict source methods differ.')
    for role,path in [('adapter',__file__),('shared_context_adapter',full_context.__file__),('core',Path(__file__).with_name('core.py')),('runner',Path(__file__).with_name('run.py'))]:
        need(sha(path)==p['input_pins'][role]['sha256'],'strict source execution code changed: '+role)
    for name,s in p['files'].items(): need(sha(folder/name)==s,'strict source packet body changed.')
    return p


def predict(frozen,expected,author_directory,author_receipt,output,workers):
    import numpy as np
    need(1<=workers<=8,'bounded CPU worker count required.')
    frozen=Path(frozen); p=load_packet(frozen,expected); modules=author_modules(author_directory,author_receipt)
    graph=read(frozen/'graph.json.gz'); index={n.split(':',1)[1]:i for i,n in enumerate(graph['nodes'])}
    P=modules['alg_utils'].normalizeGraphEdgeWeights(adjacency(graph['nodes'],graph['pairs'])); del graph
    frames={name:(frozen/(name+'_targets.txt')).read_text().splitlines() for name in ('primary','reserved')}
    targets=sorted(frames['primary']+frames['reserved']); frame_of={t:name for name,values in frames.items() for t in values}
    full_context._STATE=(modules,P,np.asarray([index[t] for t in targets],dtype=int))
    terms=defaultdict(list)
    for protein,entries in read(frozen/'training.json.gz').items():
        for aspect,term in entries: terms[(aspect,term)].append(index[protein])
    folder=new_output(output); write(folder/'execution_started.json',{'created_at':timestamp(),'protocol_file_sha256':expected,'workers':workers,'future_GO_labels_read':False})
    diagnostics=[]; reports={}
    for method in METHODS:
        start=time.time(); streams={name:gzip.GzipFile(filename=str(folder/(name+'_'+method+'.tsv.gz')),mode='wb',mtime=0) for name in frames}; counts={name:0 for name in frames}
        tasks=[(method,a,t,positive) for (a,t),positive in sorted(terms.items())]
        try:
            with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('fork')) as pool:
                for step,(aspect,term,scores,diagnostic) in enumerate(pool.map(full_context._term,tasks,chunksize=8),1):
                    for target,value in zip(targets,scores):
                        if value>0:
                            frame=frame_of[target]; streams[frame].write((target+'\t'+term+'\t'+format(float(value),'.17g')+'\n').encode()); counts[frame]+=1
                    diagnostics.append({'method':method,'aspect':aspect,'term':term,**diagnostic})
                    if step%1000==0: print({'method':method,'terms':step,'total':len(tasks),'seconds':time.time()-start},flush=True)
        finally:
            for stream in streams.values(): stream.close()
        reports[method]={'terms':len(tasks),'emitted_rows':counts,'seconds':time.time()-start}; print({'completed':method,**reports[method]},flush=True)
    load_packet(frozen,expected); write(folder/'diagnostics.json.gz',diagnostics)
    result={'format':'biograph-steward.cafa5-temporal-alias-sensitivity-predictions.v1','created_at':timestamp(),
        'protocol_file_sha256':expected,'protocol_content_sha256':p['content_sha256'],'methods':reports,
        'future_GO_labels_read':False,'files':{f.name:{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(folder.iterdir())}}
    result['content_sha256']=digest(result);write(folder/'predictions.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--parent',required=True);a.add_argument('--parent-sha256',required=True);a.add_argument('--reserved',required=True);a.add_argument('--reserved-sha256',required=True);a.add_argument('--alias-audit',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('predict');a.add_argument('--frozen',required=True);a.add_argument('--protocol-sha256',required=True);a.add_argument('--author-directory',required=True);a.add_argument('--author-receipt',required=True);a.add_argument('--output',required=True);a.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();r=prepare(args.parent,args.parent_sha256,args.reserved,args.reserved_sha256,args.alias_audit,args.output) if args.command=='prepare' else predict(args.frozen,args.protocol_sha256,args.author_directory,args.author_receipt,args.output,args.workers); print(r['content_sha256'])
