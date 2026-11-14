"""Transport the locked strict LocalPlus scorer to standard NK/LK tasks.

This post-PK check reuses the unchanged published scorer, reviewed native
baseline readers and official evaluator. It never changes the PK comparison.
Preparation interprets accession/aspect metadata, never future GO columns.
"""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import shutil
import tarfile
import time

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha, new_output
from tools.cafa_prediction import core, strict_alias_context
from tools.cafa_prediction.run import read, pin, verify_pins
from tools.cafa_baselines.intake import selected_rows, naive_predictions, FREQUENCY
from tools.cafa_baselines.reserved_controls import MEMBERS
from tools.cafa_reference.intake import ACCESSION, need

SETTINGS=('no_knowledge','limited')
ASPECTS=('BPO','MFO','CCO')
FORMAT='biograph-steward.cafa5-nonpk-transport-freeze.v1'


def prepare(strict, strict_sha256, identities, author, author_receipt, output):
    strict,identities,author,author_receipt=map(Path,(strict,identities,author,author_receipt))
    parent=strict_alias_context.load_packet(strict,strict_sha256)
    graph=read(strict/'graph.json.gz');labels=read(strict/'training.json.gz')
    universe={n.removeprefix('UniProtKB:') for n in graph['nodes']}
    targets={};eligibility={};union=set()
    input_pins={'adapter':pin(__file__),'strict_protocol':pin(strict/'protocol.json'),
        'core':pin(core.__file__),'baseline_reader':pin(Path(__file__).parents[1]/'cafa_baselines/intake.py')}
    # Both the single scorer and all native controls are chosen before either
    # new setting's future term column is decoded. PK outcomes have been seen.
    for setting in SETTINGS:
        targets[setting]={}
        for aspect in ASPECTS:
            file=identities/(setting+'_'+aspect+'.txt')
            rows=file.read_text().splitlines()
            need(rows and len(rows)==len(set(rows)) and all(ACCESSION.fullmatch(p) for p in rows),
                 'identity metadata must contain exact unique source accessions only.')
            chosen=sorted(set(rows)&universe);targets[setting][aspect]=chosen;union.update(chosen)
            input_pins[setting+'_'+aspect]=pin(file)
            # Do not infer setting membership ourselves: retain the released
            # assignments and explicitly audit historical seed eligibility.
            eligibility[setting+'_'+aspect]={'targets':len(chosen),
                'targets_with_training_rows_in_aspect':sum(any(a==aspect and t not in {'GO:0008150','GO:0005575','GO:0003674'}
                    for a,t in labels[p]) for p in chosen)}
    core.author_modules(author,author_receipt)
    input_pins['author_receipt']=pin(author_receipt)
    receipt=read(author_receipt)
    for name in receipt['files']:input_pins['author/'+name]=pin(author/name)
    verify_pins(input_pins)
    folder=new_output(output,strict,identities,author_receipt)
    for name in ('graph.json.gz','training.json.gz'):shutil.copyfile(strict/name,folder/name)
    shutil.copyfile(strict/'protocol.json',folder/'strict_source_protocol.json')
    for setting,by in targets.items():
        for aspect,ids in by.items():(folder/(setting+'_'+aspect+'.txt')).write_text('\n'.join(ids)+'\n')
        (folder/(setting+'_targets.txt')).write_text('\n'.join(sorted(set().union(*map(set,by.values()))))+'\n')
    (folder/'targets.txt').write_text('\n'.join(sorted(union))+'\n')
    plan={'format':FORMAT,'created_at':utcnow(),'input_pins':input_pins,
        'source_protocol_content_sha256':parent['content_sha256'],'source_protocol_file_sha256':strict_sha256,
        'nodes':len(graph['nodes']),'edges':len(graph['pairs']),'targets':len(union),
        'counts':{s:{a:len(v) for a,v in by.items()} for s,by in targets.items()},'historical_eligibility':eligibility,
        'methods':['strict_alias_localplus',*MEMBERS,'official_naive'],
        'model':'Unchanged author LocalPlus on the unchanged strict-alias full historical graph and all known_t0 seeds.',
        'choice_timing':'Post-PK choice of already deployed strict LocalPlus; no NK/LK future GO labels read before this separate freeze.',
        'PK_outcomes_previously_seen':True,'new_future_GO_labels_read':{s:False for s in SETTINGS},
        'setting_semantics':'Native CAFA task assignment is per protein/aspect. LK can overlap prior PK proteins in other aspects; not independent-study or wholly unseen-protein replication.',
        'evaluation_policy':{'prop':'fill','norm':'cafa','no_orphans':True,'threshold_step':.001,
            'known_exclusion':None,'endpoint':'All six native setting/aspect outcomes, ordinary/IA micro+macro Fmax and Smin; fixed0.5 points retained.',
            'uncertainty':'If run,2000 paired protein bootstrap draws for BPO in both settings against each fixed control; exact author point-curve agreement required.'},
        'new_score_threshold_model_or_graph_fit':False,'source_graph_modified':False,
        'source_dates':{'network':'STRINGv11 December2018','alias_support':'January2019','training':'UniProt2023_03','ontology':'2023-01-01','future_reference':'UniProt2025_03'},
        'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
    plan['content_sha256']=digest(plan);write_json(folder/'protocol.json',plan);return plan


def load(folder,expected):
    folder=Path(folder);plan=read(folder/'protocol.json')
    need(sha(folder/'protocol.json')==expected and plan.get('format')==FORMAT
         and plan.get('content_sha256')==digest({k:v for k,v in plan.items() if k!='content_sha256'}),'nonPK protocol seal differs.')
    need(plan['methods']==['strict_alias_localplus',*MEMBERS,'official_naive']
         and plan['new_future_GO_labels_read']=={s:False for s in SETTINGS}
         and plan['PK_outcomes_previously_seen'] is True,'nonPK frozen method or exposure boundary differs.')
    verify_pins(plan['input_pins'])
    for name,value in plan['files'].items():need(sha(folder/name)==value,'nonPK frozen source differs: '+name)
    return plan


def predict(frozen, protocol_sha256, author, author_receipt, output):
    import numpy as np
    frozen=Path(frozen);plan=load(frozen,protocol_sha256)
    need(sha(author_receipt)==plan['input_pins']['author_receipt']['sha256'],'published scorer receipt differs.')
    modules=core.author_modules(author,author_receipt)
    graph=read(frozen/'graph.json.gz');index={n.removeprefix('UniProtKB:'):i for i,n in enumerate(graph['nodes'])}
    P=modules['alg_utils'].normalizeGraphEdgeWeights(core.adjacency(graph['nodes'],graph['pairs']));del graph
    targets=(frozen/'targets.txt').read_text().splitlines();ix=np.asarray([index[t] for t in targets],dtype=int)
    terms=defaultdict(list)
    for protein,entries in read(frozen/'training.json.gz').items():
        for aspect,term in entries:terms[aspect,term].append(index[protein])
    folder=new_output(output,frozen);start=time.time();rows=0
    write_json(folder/'execution_started.json',{'created_at':utcnow(),'protocol_sha256':protocol_sha256,'new_future_GO_labels_read':False})
    with gzip.GzipFile(filename=str(folder/'strict_alias_localplus.tsv.gz'),mode='wb',mtime=0) as stream:
        for step,((aspect,term),positive) in enumerate(sorted(terms.items()),1):
            scores,_=core.run_term(modules,P,None,positive,'localplus')
            for protein,value in zip(targets,scores[ix]):
                if value>0:stream.write((protein+'\t'+term+'\t'+format(float(value),'.17g')+'\n').encode());rows+=1
            if step%2000==0:print(json.dumps({'terms':step,'total':len(terms),'seconds':time.time()-start}),flush=True)
    load(frozen,protocol_sha256)
    result={'format':FORMAT+'.predictions','created_at':utcnow(),'protocol_sha256':protocol_sha256,
        'protocol_content_sha256':plan['content_sha256'],'target_count':len(targets),'heads':len(terms),'rows':rows,
        'new_future_GO_labels_read':False,'PK_outcomes_previously_seen':True,'model_or_graph_fit':False,
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in folder.iterdir() if p.is_file()}}
    result['content_sha256']=digest(result);write_json(folder/'predictions.json',result);return result


def controls(frozen, protocol_sha256, archive, qualification, output):
    frozen,archive,qualification=map(Path,(frozen,archive,qualification));plan=load(frozen,protocol_sha256)
    q=read(qualification)
    need(q.get('content_sha256')==digest({k:v for k,v in q.items() if k!='content_sha256'})
         and q.get('status')=='completed' and sha(archive)==q['archive_sha256'],'official baseline archive qualification differs.')
    ids=set((frozen/'targets.txt').read_text().splitlines());folder=new_output(output,frozen,archive,qualification)
    pins={str(p):sha(p) for p in (archive,qualification,Path(__file__),Path(__file__).parents[1]/'cafa_baselines/intake.py')}
    reverse={v:k for k,v in MEMBERS.items()};stats={};frequency=None
    with tarfile.open(archive,mode='r|gz') as source:
        for member in source:
            if member.name not in {*reverse,FREQUENCY}:continue
            need(member.isfile(),'native baseline member is not ordinary.')
            stream=source.extractfile(member)
            if member.name==FREQUENCY:
                need(frequency is None and member.size<10000000,'native frequency member duplicated or oversized.')
                frequency=stream.read();(folder/'cafa5_naive_frequencies.tsv').write_bytes(frequency)
            else:
                name=reverse[member.name];need(name not in stats,'native baseline member repeated.')
                with gzip.GzipFile(filename=str(folder/(name+'.tsv.gz')),mode='wb',mtime=0) as out:
                    stats[name]=selected_rows(stream,ids,out)
                print(json.dumps({'method':name,**stats[name]}),flush=True)
    need(set(stats)==set(MEMBERS) and frequency is not None,'native baseline inventory incomplete.')
    with gzip.GzipFile(filename=str(folder/'official_naive.tsv.gz'),mode='wb',mtime=0) as out:
        stats['official_naive']=naive_predictions(frequency,ids,out)
    for path,value in pins.items():need(sha(path)==value,'native control input changed.')
    load(frozen,protocol_sha256)
    result={'format':FORMAT+'.controls','created_at':utcnow(),'protocol_sha256':protocol_sha256,
        'target_count':len(ids),'members':stats,'input_sha256':pins,'new_future_GO_labels_read':False,
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in folder.iterdir() if p.is_file()}}
    result['content_sha256']=digest(result);write_json(folder/'qualification.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ('strict','strict-sha256','identities','author','author-receipt','output'):p.add_argument('--'+name,required=True)
    for command in ('predict','controls'):
        p=sub.add_parser(command)
        for name in ('frozen','protocol-sha256','output'):p.add_argument('--'+name,required=True)
        for name in (('author','author-receipt') if command=='predict' else ('archive','qualification')):p.add_argument('--'+name,required=True)
    args=vars(parser.parse_args());command=args.pop('command');print(json.dumps(globals()[command](**args),indent=2))
