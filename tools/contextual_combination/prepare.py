# SPDX-License-Identifier: GPL-3.0-only
"""Identity-separated caches for the qualified published contextual stacker.

Boundary construction reads identities/sequences only. Score intake reuses the
existing pinned native adapter. Supervised targets and priors read only the
explicitly allowed historical/development sources; new held-out term files are
never accepted by this module. Cached feature arrays retain native StackDataset
float32 channels before its published logit transform.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
import multiprocessing
from pathlib import Path
import re
from datetime import datetime, timezone

from tools.learned_combination.core import ScoreMatrix, need
from tools.learned_combination.reference import file_sha256, read_target_ids

NAMESPACES = ('molecular_function', 'biological_process', 'cellular_component')
NS_ASPECT = {'molecular_function':'mf', 'biological_process':'bp', 'cellular_component':'cc'}
_DATASET = None


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def _check_path(path):
    text = str(path)
    need(not any(x in text for x in ('reference_apr_nov_2026_v1/native_reference_v1/sealed_reference/',
         'reference_apr_nov_2026_v1/fixed_t0_sensitivity_v1/groundtruth',
         'reference_apr_nov_2026_v1/native_reference_v1/t1/',
         'reference_apr_nov_2026_v1/public_sources/goa_human_t1_')),
         'new held-out labels/TOI/T1 annotations cannot enter feature preparation.')


def config(path):
    value = json.loads(Path(path).read_text())
    need(value['format']=='biograph-steward.contextual-preparation.v1', 'explicit preparation format required.')
    for name, pin in {**value['input_pins'],**value.get('feature_code_pins',{}),
                      **value.get('final_input_pins',{})}.items():
        _check_path(name)
        need(file_sha256(name)==pin, 'preparation input differs: '+name)
    return value


def _hash_records(value, wanted=None):
    need(isinstance(value,dict) and value, 'nonempty exact sequence-hash mapping required.')
    result={}
    for accession, record in value.items():
        if wanted is not None and accession not in wanted:
            continue
        need(isinstance(record,dict), 'sequence record must be a mapping.')
        hashes={k:record[k] for k in ('sequence_sha256','native_first1022_sha256')}
        need(all(isinstance(v,str) and re.fullmatch('[a-f0-9]{64}',v) for v in hashes.values()),
             'both full and native first1022 sequence SHA256 required.')
        result[accession]=hashes
    if wanted is not None:
        need(set(result)==set(wanted), 'sequence metadata must cover every declared target.')
    return result


def exclude_reserved(candidates, candidate_hashes, reserved):
    """Literal accession, full-sequence and actual 1022-residue-input separation.

    ``reserved`` maps epoch roles to complete accession/hash mappings. Hashes
    for the same accession may differ between epochs; keep both sets rather
    than overwriting one epoch with the other.
    """
    candidates=tuple(candidates)
    need(candidates and len(candidates)==len(set(candidates)), 'unique nonempty candidate IDs required.')
    source=_hash_records(candidate_hashes,set(candidates))
    need(reserved and all(isinstance(x,str) and x for x in reserved), 'named complete reserved frames required.')
    checked={name:_hash_records(rows) for name,rows in reserved.items()}
    reserved_ids=set().union(*(set(rows) for rows in checked.values()))
    full={r['sequence_sha256'] for rows in checked.values() for r in rows.values()}
    prefix={r['native_first1022_sha256'] for rows in checked.values() for r in rows.values()}
    literal=set(candidates)&reserved_ids
    same_full={p for p in set(candidates)-literal if source[p]['sequence_sha256'] in full}
    same_prefix={p for p in set(candidates)-literal-same_full if source[p]['native_first1022_sha256'] in prefix}
    retained=tuple(sorted(set(candidates)-literal-same_full-same_prefix))
    need(retained, 'no fitting/validation proteins remain after exclusions.')
    return retained, {'candidate_count':len(candidates),'literal_accession_excluded':len(literal),
        'additional_full_sequence_excluded':len(same_full),'additional_native_first1022_excluded':len(same_prefix),
        'retained_count':len(retained),'reserved_counts':{k:len(v) for k,v in checked.items()},
        'excluded_ids':{'literal':sorted(literal),'full_sequence':sorted(same_full),'native_first1022':sorted(same_prefix)},
        'homology_disjointness_established':False,'base_model_training_independence_established':False}


def sequence_hashes_from_fasta(path, wanted):
    """Native Bio.SeqIO parser, exact accession join, global taxa retained."""
    from Bio import SeqIO
    wanted=set(wanted);found={}
    opener=gzip.open if Path(path).suffix=='.gz' else open
    with opener(path,'rt') as stream:
        for record in SeqIO.parse(stream,'fasta'):
            fields=record.id.split('|')
            if len(fields)!=3 or fields[1] not in wanted:
                continue
            accession=fields[1]
            need(fields[0]=='sp' and accession not in found,'canonical unique SwissProt sequence identity required.')
            sequence=str(record.seq)
            need(sequence and re.fullmatch('[A-Z]+',sequence),'sequence is empty/invalid; no normalization permitted.')
            found[accession]={'sequence_sha256':hashlib.sha256(sequence.encode('ascii')).hexdigest(),
                'native_first1022_sha256':hashlib.sha256(sequence[:1022].encode('ascii')).hexdigest()}
    need(set(found)==wanted,'global reserved target list lacks exact dated SwissProt sequences.')
    return found


def boundary(cfg, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    old=json.loads(Path(cfg['old_sequence_records']).read_text())
    all_ids=read_target_ids(cfg['all_old_targets'])
    need(set(old)==set(all_ids),'old sequence/forecast target universes differ.')
    validation_all=read_target_ids(cfg['all_old_validation_targets'])
    validation_hashes=sequence_hashes_from_fasta(cfg['old_validation_fasta'],validation_all)
    new_hashes=json.loads(Path(cfg['new_reference_sequence_records']).read_text())
    new_ids=read_target_ids(cfg['all_new_reference_targets'])
    new_hashes=_hash_records(new_hashes,set(new_ids))
    fit_ids,fit_audit=exclude_reserved(all_ids,old,{'old_validation_all':validation_hashes,'new_reference_all':new_hashes})
    val_candidates=read_target_ids(cfg['old_validation_candidates'])
    val_ids,val_audit=exclude_reserved(val_candidates,old,{'new_reference_all':new_hashes})
    need(not(set(fit_ids)&set(val_ids)),'fit and validation accession sets overlap.')
    for name,ids in (('fit_ids.txt',fit_ids),('validation_ids.txt',val_ids)):
        (output/name).write_text('\n'.join(ids)+'\n')
    write_json(output/'old_validation_global_sequence_hashes.json',validation_hashes)
    result={'format':'biograph-steward.contextual-identity-boundary.v1','created_at':now(),
        'fit':fit_audit,'validation':val_audit,'new_reference_targets':len(new_ids),
        'all_old_validation_targets':len(validation_all),'new_heldout_GO_columns_read':False,
        'fit_val_exact_or_model_input_overlap':False,'source_input_pins':cfg['input_pins'],
        'files':{p.name:file_sha256(p) for p in output.iterdir()}}
    write_json(output/'boundary.json',result)
    return result


def _save_matrices(folder, matrices):
    import numpy as np
    folder.mkdir(parents=True,exist_ok=False);result={}
    for ns,matrix in matrices.items():
        path=folder/(ns+'.npy');np.save(path,matrix.values,allow_pickle=False)
        result[ns]={'file':str(path),'sha256':file_sha256(path),'proteins':list(matrix.proteins),
                    'terms':list(matrix.terms),'upper_roundoff_tolerance':matrix.upper_roundoff_tolerance}
    write_json(folder/'manifest.json',result)


def _load_matrices(folder):
    import numpy as np
    result={}
    for ns,row in json.loads((Path(folder)/'manifest.json').read_text()).items():
        need(file_sha256(row['file'])==row['sha256'],'raw context cache changed.')
        result[ns]=ScoreMatrix(tuple(row['proteins']),tuple(row['terms']),
            np.load(row['file'],mmap_mode='r',allow_pickle=False),row['upper_roundoff_tolerance'])
    return result


def raw_cache(cfg, output):
    """One lossless all6437 intake; true head masks are handled separately."""
    import numpy as np
    from tools.learned_combination.native_adapter import native_ontologies,load_native_scores,_native
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    ids=read_target_ids(cfg['all_old_targets']);ont=native_ontologies(cfg['ontology'])
    pk=set(read_target_ids(cfg['pk_targets']));other=tuple(p for p in ids if p not in pk)
    audits={}
    for method in ('localplus','deepgose'):
        files=cfg['forecast_files'][method]
        matrices,audit=load_native_scores(files['PK'],ids,ont,localplus=method=='localplus')
        remaining,extra=load_native_scores(files['nonPK'],other,ont,localplus=method=='localplus')
        index={p:i for i,p in enumerate(ids)};rows=np.asarray([index[p] for p in other])
        for ns in matrices:
            matrices[ns].values[rows,:]=remaining[ns].values
        _save_matrices(output/method,matrices)
        audits[method]={'PK':audit,'nonPK_only':extra,'PK_precedence':True};del matrices,remaining
    for epoch,source in cfg['nonexperimental_context'].items():
        need(epoch in ('fit','validation'),'only declared fit/validation GOA contexts accepted here.')
        matrices,audit=load_native_scores([source],ids,ont)
        for ns,matrix in matrices.items():
            need(np.isin(matrix.values,[0.,1.]).all(),'native nonexperimental context must be binary score1 membership.')
            if np.any(matrix.values):
                _native()['graph'].propagate(matrix.values,ont[ns],ont[ns].order,mode='max')
        _save_matrices(output/('goa_'+epoch),matrices);audits['goa_'+epoch]=audit;del matrices
    write_json(output/'intake.json',{'created_at':now(),'audits':audits,'heldout_GO_columns_read':False,
        'source_input_pins':cfg['input_pins'],'context_closure':'unchanged native max; binary membership, no score calibration'})


def projected_heads(cfg, ontologies, training):
    """Producer vocabularies, never positive-cell or source-row heuristics."""
    import pandas as pd
    from tools.learned_combination.native_adapter import _native
    terms={ns:tuple(n['id'] for n in ont.terms_list) for ns,ont in ontologies.items()}
    vocab={'localplus':{},'deepgose':{}};audit={}
    native_lookup={}
    for ns,ont in ontologies.items():
        for term in ont.terms_dict:native_lookup[term]=(ns,[ont.terms_dict[term]['index']])
        for term,values in ont.terms_dict_alt.items():native_lookup[term]=(ns,[ont.terms_dict[t]['index'] for t in values])
    local_terms=set()
    for rows in training.values():
        for aspect,term in rows:local_terms.add(term)
    for method in vocab:
        for ns,aspect in NS_ASPECT.items():
            if method=='localplus':
                source=local_terms
            else:
                frame=pd.read_pickle(cfg['deepgo_heads'][aspect])
                need(list(frame.columns)==['gos'],'published DeepGO head pickle schema differs.')
                source=frame.gos.tolist()
                need(len(source)==len(set(source)),'publisher DeepGO heads repeat.')
            indexes=set();unknown=0;other_ns=0
            for term in source:
                if term not in native_lookup:unknown+=1;continue
                actual,where=native_lookup[term]
                if actual!=ns:other_ns+=1;continue
                indexes.update(where)
            vocab[method][ns]=sorted(indexes)
            audit[method+'/'+ns]={'available_canonical_heads':len(indexes),'source_terms':len(source),
                'source_terms_outside_model_ontology':unknown,'source_terms_in_other_aspects':other_ns,
                'head_policy':'actual producer vocabulary projected through unchanged native primary/alternative IDs; MAX duplicate scores'}
    return vocab,audit


def full_targets(ids, ontologies, training, additions, output):
    """Full known repertoire union allowed additions, with untouched max closure."""
    import numpy as np
    from tools.learned_combination.native_adapter import _native
    native=_native();ids=tuple(ids);allowed=set(ids);paths={}
    for role in ('known','full'):
        path=output/(role+'_allowed_labels.tsv');paths[role]=path
        with path.open('x') as stream:
            stream.write('EntryID\tterm\taspect\n')
            for protein,rows in training.items():
                if protein in allowed:
                    for aspect,term in rows:stream.write(protein+'\t'+term+'\t'+aspect+'\n')
            if role=='full':
                for source in additions:
                    _check_path(source)
                    with Path(source).open() as inp:
                        for line in inp:
                            fields=line.rstrip('\r\n').split('\t')
                            if fields[0] in allowed:stream.write(line if line.endswith('\n') else line+'\n')
    parsed={role:native['parser'].gt_parser(str(path),ontologies) for role,path in paths.items()}
    arrays={};known={};index={p:i for i,p in enumerate(ids)}
    for ns,ont in ontologies.items():
        arrays[ns]=np.zeros((len(ids),ont.idxs),dtype=np.float32)
        known[ns]=np.zeros((len(ids),ont.idxs),dtype=bool)
        for role,destination in (('known',known[ns]),('full',arrays[ns])):
            if ns not in parsed[role]:continue
            for p,row in parsed[role][ns].ids.items():destination[index[p],:]=parsed[role][ns].matrix[row,:]
        need(np.all(arrays[ns][known[ns]]==1),'known positive became a supervised negative.')
    return arrays,known,{role:{'file':str(path),'sha256':file_sha256(path)} for role,path in paths.items()}


def priors_from_full_fit(targets, graph):
    """The published create_helpers NaN-parent block and Pandas reductions.

    This deliberately precedes any per-aspect root-positive training filter.
    It is the native benchmark convention, not a negative-biology assertion.
    """
    import numpy as np
    from pandas import DataFrame
    from .native_stacker import sequence_edge_graph
    graph=sequence_edge_graph(graph)
    trg=np.asarray(targets,dtype=np.float32).copy()
    need(trg.ndim==2 and trg.shape[0]>0 and trg.shape[1]==graph.idxs
         and np.isin(trg,[0.,1.]).all(),'full binary fit repertoire required before priors.')
    for k,node in enumerate(graph.terms_list):
        adj=node['adj']
        if len(adj)>0:
            na=np.nonzero(np.nansum(trg[:,adj],axis=1)==0)[0]
            need(np.nansum(trg[na,k])==0,'full training targets are not upward closed.')
            trg[na,k]=np.nan
    frame=DataFrame(trg,columns=[x['id'] for x in graph.terms_list])
    conditional=frame.mean().fillna(0).values
    nulls=frame.isnull().mean().values
    marginal=conditional*(1-nulls)
    need(np.isfinite(marginal).all() and np.isfinite(conditional).all(),'native priors became nonfinite.')
    return marginal,conditional,nulls


def _feature_row(index):
    return _DATASET[int(index)]['x'].numpy()


def write_feature_memmap(dataset, path, *, workers=1):
    import numpy as np
    global _DATASET
    need(type(workers) is int and 1<=workers<=4,'bounded one-to-four CPU workers required.')
    need(not Path(path).exists(),'feature cache already exists; preserve prior outputs.')
    _DATASET=dataset
    first=_feature_row(0)
    need(first.dtype==np.float32 and first.shape==(9,dataset.nout),'native dataset channel shape/dtype differs.')
    need(np.isfinite(first).all() and np.isin(first[[0,4,8]],[0.,1.]).all(),
         'native flags and GOA must be finite binary channels.')
    result=np.lib.format.open_memmap(path,mode='w+',dtype=np.float32,shape=(len(dataset),9,dataset.nout))
    result[0]=first
    if workers==1:
        iterator=map(_feature_row,range(1,len(dataset)))
        for i,value in enumerate(iterator,1):result[i]=value
    else:
        with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('fork')) as pool:
            for i,value in enumerate(pool.map(_feature_row,range(1,len(dataset)),chunksize=4),1):result[i]=value
    result.flush();del result;_DATASET=None


def features(cfg, boundary_dir, raw_dir, output):
    import numpy as np
    from tools.learned_combination.native_adapter import native_ontologies
    from .native_stacker import load_author,make_dataset
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    boundary_dir,raw_dir=Path(boundary_dir),Path(raw_dir)
    split=json.loads((boundary_dir/'boundary.json').read_text())
    need(split['source_input_pins']==cfg['input_pins'],'identity-boundary inputs changed before features.')
    need(json.loads((raw_dir/'intake.json').read_text())['source_input_pins']==cfg['input_pins'],
         'raw-intake inputs changed before features.')
    fit_ids=read_target_ids(boundary_dir/'fit_ids.txt');val_ids=read_target_ids(boundary_dir/'validation_ids.txt')
    with gzip.open(cfg['strict_training'],'rt') as stream:training=json.load(stream)
    ont=native_ontologies(cfg['ontology']);author=load_author(cfg['author_root'],jit_backend='numba')
    heads,head_audit=projected_heads(cfg,ont,training)
    targets,known,target_receipts=full_targets(fit_ids,ont,training,cfg['allowed_development_annotations'],output)
    local=_load_matrices(raw_dir/'localplus');deep=_load_matrices(raw_dir/'deepgose')
    result={'format':'biograph-steward.contextual-prepared-features.v1','created_at':now(),'fit':{},'validation':{},
        'boundary_sha256':file_sha256(boundary_dir/'boundary.json'),'raw_intake_sha256':file_sha256(raw_dir/'intake.json'),
        'heads':head_audit,'target_label_sources':target_receipts,'native_source_receipt':author.source_receipt,
        'fit_universe_before_aspect_filter':len(fit_ids),'new_heldout_GO_columns_read':False,
        'source_input_pins':cfg['input_pins'],'feature_code_pins':cfg.get('feature_code_pins',{})}
    for ns in NAMESPACES:
        prior_dir=output/'priors'/ns;prior_dir.mkdir(parents=True)
        raw,conditional,nulls=priors_from_full_fit(targets[ns],ont[ns])
        for name,array in (('raw',raw),('conditional',conditional),('nulls',nulls)):
            np.save(prior_dir/(name+'.npy'),array,allow_pickle=False)
        prior_receipt={'fit_universe':list(fit_ids),'fit_universe_count':len(fit_ids),
            'computed_before_root_positive_filter':True,'formula':'native create_helpers NaN-parent block; Pandas mean/isnull mean; raw=conditional*(1-null)',
            'files':{p.name:file_sha256(p) for p in prior_dir.iterdir()}}
        write_json(prior_dir/'receipt.json',prior_receipt)
        index={p:i for i,p in enumerate(local[ns].proteins)}
        for role,ids in (('fit',fit_ids),('validation',val_ids)):
            print(now(),'FEATURES',role,ns,len(ids),flush=True)
            folder=output/role/ns;folder.mkdir(parents=True)
            rows=np.asarray([index[p] for p in ids])
            goa=_load_matrices(raw_dir/('goa_'+role))[ns]
            goa_indices=[np.flatnonzero(goa.values[i]) for i in rows]
            left=np.asarray(heads['localplus'][ns],dtype=np.int64);right=np.asarray(heads['deepgose'][ns],dtype=np.int64)
            dataset=make_dataset(author,proteins=ids,terms=local[ns].terms,graph=ont[ns],
                predictions=[(local[ns].values[np.ix_(rows,left)],left),(deep[ns].values[np.ix_(rows,right)],right)],
                prior_raw=raw,prior_cond=conditional,goa_indices=goa_indices,
                targets=targets[ns] if role=='fit' else None)
            feature_path=folder/'features.npy';write_feature_memmap(dataset,feature_path,workers=cfg.get('workers',2))
            manifest={'proteins':list(ids),'terms':list(local[ns].terms),'namespace':ns,
                'feature_file':str(feature_path),'features_shape':[len(ids),9,ont[ns].idxs],
                'features_dtype':'float32','features_semantics':'native StackDataset channels before native logit transform',
                'prior_receipt_file':str(prior_dir/'receipt.json'),'sourcepins':cfg['input_pins'],
                'file_pins':{str(feature_path):file_sha256(feature_path)}}
            if role=='fit':
                target_path=folder/'targets.npy';known_path=folder/'known_positive_mask.npy'
                np.save(target_path,targets[ns],allow_pickle=False);np.save(known_path,known[ns],allow_pickle=False)
                manifest.update(targets_file=str(target_path),known_positive_mask_file=str(known_path),
                    target_semantics='known_T0_union_allowed_development_additions_upward_closed')
                manifest['file_pins'].update({str(target_path):file_sha256(target_path),str(known_path):file_sha256(known_path)})
            write_json(folder/'manifest.json',manifest)
            result[role][ns]={'manifest':str(folder/'manifest.json'),'sha256':file_sha256(folder/'manifest.json')}
            del goa,dataset
    write_json(output/'prepared.json',result)
    return result


def final_raw(cfg, output):
    """Label-free, lossless final parent scores on the fixed model ontology."""
    import numpy as np
    from tools.learned_combination.native_adapter import native_ontologies,load_native_scores,_native
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    ids=read_target_ids(cfg['all_new_reference_targets']);ont=native_ontologies(cfg['ontology'])
    audits={}
    for method in ('localplus','deepgose'):
        matrices,audit=load_native_scores(cfg['final_forecast_files'][method],ids,ont,
                                        localplus=method=='localplus')
        _save_matrices(output/method,matrices);audits[method]=audit;del matrices
    matrices,audit=load_native_scores([cfg['final_nonexperimental_context']],ids,ont)
    for ns,matrix in matrices.items():
        need(np.isin(matrix.values,[0.,1.]).all(),'final context must be binary score1 membership.')
        if np.any(matrix.values):
            _native()['graph'].propagate(matrix.values,ont[ns],ont[ns].order,mode='max')
    _save_matrices(output/'goa_final',matrices);audits['goa_final']=audit
    result={'created_at':now(),'audits':audits,'new_heldout_GO_columns_read':False,
            'source_input_pins':cfg['input_pins'],'final_input_pins':cfg['final_input_pins'],
            'context_closure':'unchanged native max; binary membership, no score calibration'}
    write_json(output/'intake.json',result)
    return result


def final_features(cfg, fit_dir, raw_dir, output):
    """Apply frozen fit priors to all declared final identities, without labels."""
    import numpy as np
    from tools.learned_combination.native_adapter import native_ontologies
    from .native_stacker import load_author,make_dataset
    fit_dir,raw_dir,output=Path(fit_dir),Path(raw_dir),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    fitted=json.loads((fit_dir/'prepared.json').read_text())
    need(fitted['source_input_pins']==cfg['input_pins'],'fit input universe changed before final features.')
    intake=json.loads((raw_dir/'intake.json').read_text())
    need(intake['source_input_pins']==cfg['input_pins']
         and intake['final_input_pins']==cfg['final_input_pins'],'final intake inputs changed.')
    ids=read_target_ids(cfg['all_new_reference_targets']);ont=native_ontologies(cfg['ontology'])
    with gzip.open(cfg['strict_training'],'rt') as stream:training=json.load(stream)
    heads,head_audit=projected_heads(cfg,ont,training)
    author=load_author(cfg['author_root'],jit_backend='numba')
    local=_load_matrices(raw_dir/'localplus');deep=_load_matrices(raw_dir/'deepgose')
    goa=_load_matrices(raw_dir/'goa_final')
    result={'format':'biograph-steward.contextual-final-features.v1','created_at':now(),'final':{},
            'fitted_preparation_sha256':file_sha256(fit_dir/'prepared.json'),
            'raw_intake_sha256':file_sha256(raw_dir/'intake.json'),'heads':head_audit,
            'source_input_pins':cfg['input_pins'],'final_input_pins':cfg['final_input_pins'],
            'feature_code_pins':cfg.get('feature_code_pins',{}),'new_heldout_GO_columns_read':False}
    for ns in NAMESPACES:
        need(local[ns].proteins==deep[ns].proteins==goa[ns].proteins==tuple(ids)
             and local[ns].terms==deep[ns].terms==goa[ns].terms,'final input axes differ.')
        prior_dir=fit_dir/'priors'/ns;prior=json.loads((prior_dir/'receipt.json').read_text())
        for name,pin in prior['files'].items():
            need(file_sha256(prior_dir/name)==pin,'frozen fit prior changed before final features.')
        raw=np.load(prior_dir/'raw.npy',allow_pickle=False)
        conditional=np.load(prior_dir/'conditional.npy',allow_pickle=False)
        left=np.asarray(heads['localplus'][ns],dtype=np.int64)
        right=np.asarray(heads['deepgose'][ns],dtype=np.int64)
        dataset=make_dataset(author,proteins=ids,terms=local[ns].terms,graph=ont[ns],
            predictions=[(local[ns].values[:,left],left),(deep[ns].values[:,right],right)],
            prior_raw=raw,prior_cond=conditional,
            goa_indices=[np.flatnonzero(goa[ns].values[i]) for i in range(len(ids))])
        folder=output/ns;folder.mkdir();path=folder/'features.npy'
        print(now(),'FINAL_FEATURES',ns,len(ids),flush=True)
        write_feature_memmap(dataset,path,workers=cfg.get('workers',2))
        manifest={'proteins':list(ids),'terms':list(local[ns].terms),'namespace':ns,
                  'feature_file':str(path),'features_shape':[len(ids),9,ont[ns].idxs],
                  'features_dtype':'float32','features_semantics':'native StackDataset channels before native logit transform',
                  'prior_receipt_file':str(prior_dir/'receipt.json'),
                  'file_pins':{str(path):file_sha256(path)},'new_heldout_GO_columns_read':False}
        write_json(folder/'manifest.json',manifest)
        result['final'][ns]={'manifest':str(folder/'manifest.json'),'sha256':file_sha256(folder/'manifest.json')}
        del dataset
    write_json(output/'prepared.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('boundary','raw','features','final_raw','final_features'))
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--boundary');p.add_argument('--raw');p.add_argument('--fit')
    a=p.parse_args();cfg=config(a.config)
    if a.phase=='boundary':r=boundary(cfg,a.output)
    elif a.phase=='raw':r=raw_cache(cfg,a.output)
    elif a.phase=='features':r=features(cfg,a.boundary,a.raw,a.output)
    elif a.phase=='final_raw':r=final_raw(cfg,a.output)
    else:r=final_features(cfg,a.fit,a.raw,a.output)
    if a.phase=='boundary':print(json.dumps({'fit':r['fit'],'validation':r['validation']},indent=2))


if __name__=='__main__':main()
