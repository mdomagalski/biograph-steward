# SPDX-License-Identifier: GPL-3.0-only
"""Fixed training-freshness attribution controls; no tuning or new predictor.

Original global seeds remain intact. Exactly the frozen fit cohort's full
positive repertoire is unioned onto those seeds. Published runLocal, original
historical graph/P and fixed soft postprocessing stay unchanged. Existing full
fit marginal vectors are broadcast without recomputation. No validation/final
annotation, future reference, threshold fitting or model selection is accepted.
"""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path

from tools.learned_combination.core import need
from tools.learned_combination.reference import file_sha256,read_target_ids
from .prepare import _check_path,write_json

ASPECT={'biological_process':'BPO','molecular_function':'MFO','cellular_component':'CCO'}
RAW='localplus_updated_seeds';SOFT='localplus_updated_seeds_soft';FREQUENCY='fit_label_frequency'


def load_config(path):
    cfg=json.loads(Path(path).read_text())
    need(cfg['format']=='biograph-steward.training-freshness-controls.v1'
         and cfg['fresh_final_reference_opened'] is False,'label-free fixed controls configuration required.')
    for p,pin in cfg['input_pins'].items():
        _check_path(p);need(file_sha256(p)==pin,'changed freshness control source: '+p)
    required={cfg[k] for k in ('graph','original_training','fit_ids','ontology','localplus_author_receipt','old_pk_targets')}
    required.update(cfg['roles'].values())
    required.update(s['file'] for s in cfg['fit_manifests'].values())
    required.update(s['file'] for s in cfg['priors'].values())
    required.update(s['file'] for rows in cfg['old_localplus_files'].values() for s in rows)
    required.add(cfg['final_localplus_source']['file'])
    need(required<=set(cfg['input_pins']),'every direct freshness source must be explicitly pinned.')
    return cfg


def union_training(original,fit,allowed):
    """Set UNION, not replacement: retain every original global protein/cell."""
    allowed=set(allowed);need(set(fit)==allowed,'complete explicit fitting-only additions required.')
    result={p:{tuple(x) for x in rows} for p,rows in original.items()}
    before={p:set(rows) for p,rows in result.items()}
    need(allowed<=set(result),'all fitting proteins must already exist in unchanged graph seed frame.')
    for p,rows in fit.items():result[p].update(tuple(x) for x in rows)
    added={p:result[p]-before[p] for p in allowed}
    need(all(before[p]<=result[p] for p in before),'an original seed was removed.')
    need(all(result[p]==before[p] for p in before if p not in allowed),'nonfitting protein gained a seed.')
    return {p:sorted(rows) for p,rows in result.items()},added


def by_head(training,index):
    result=defaultdict(set)
    for protein,rows in training.items():
        need(protein in index,'seed protein outside immutable graph.')
        for aspect,term in rows:
            need(aspect in ASPECT.values(),'unqualified source aspect.')
            result[(aspect,term)].add(index[protein])
    return result


def prepare(cfg,output):
    import numpy as np
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    fit_ids=read_target_ids(cfg['fit_ids']);validation=read_target_ids(cfg['roles']['validation']);final=read_target_ids(cfg['roles']['final'])
    need(len(fit_ids)==4040 and len(validation)==797 and len(final)==3300,'frozen role counts differ.')
    need(not(set(fit_ids)&(set(validation)|set(final))) and not(set(validation)&set(final)),
         'fitting-only label additions overlap validation/final identities.')
    with gzip.open(cfg['original_training'],'rt') as f:original=json.load(f)
    repertoire={p:set() for p in fit_ids};frame_pins={};fit_heads={}
    for ns,spec in cfg['fit_manifests'].items():
        m=json.loads(Path(spec['file']).read_text());need(file_sha256(spec['file'])==spec['sha256'],'fit manifest differs.')
        need(m['proteins']==list(fit_ids) and m['target_semantics']=='known_T0_union_allowed_development_additions_upward_closed',
             'full frozen fit repertoire required.')
        need(file_sha256(m['targets_file'])==m['file_pins'][m['targets_file']]
             and file_sha256(m['known_positive_mask_file'])==m['file_pins'][m['known_positive_mask_file']],
             'fit labels/known guard changed.')
        values=np.load(m['targets_file'],mmap_mode='r');known=np.load(m['known_positive_mask_file'],mmap_mode='r')
        need(values.shape==known.shape==(4040,len(m['terms'])) and np.isin(values,[0.,1.]).all()
             and known.dtype==bool and np.all(values[known]==1),'full known-positive guard differs.')
        rows,cols=np.nonzero(values)
        for row,col in zip(rows,cols):repertoire[fit_ids[int(row)]].add((ASPECT[ns],m['terms'][int(col)]))
        frame_pins[ns]=spec;fit_heads[ns]=m['terms']
    updated,added=union_training(original,repertoire,fit_ids)
    original_pairs=sum(len({tuple(x) for x in rows}) for rows in original.values())
    old_heads={tuple(x) for rows in original.values() for x in rows};new_heads={tuple(x) for rows in updated.values() for x in rows}
    added_counts={ns:sum(a==aspect for rows in added.values() for a,t in rows) for ns,aspect in ASPECT.items()}
    new_counts={ns:sum(a==aspect for a,t in new_heads-old_heads) for ns,aspect in ASPECT.items()}
    need(original_pairs==988439 and len(original)==20412,'original global seed universe differs.')
    need(added_counts==cfg['expected_added_cells'] and new_counts==cfg['expected_new_heads'],
         'fitting-only union differs from independent source-scope audit.')
    target=output/'updated_training.json.gz'
    with target.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,filename='',mtime=0,mode='wb') as f:f.write((json.dumps(updated,sort_keys=True,separators=(',',':'))+'\n').encode())
    result={'format':'biograph-steward.fitting-only-seed-union.v1','source_input_pins':cfg['input_pins'],
        'original_training_file':cfg['original_training'],'original_training_sha256':file_sha256(cfg['original_training']),
        'updated_training_file':str(target),'updated_training_sha256':file_sha256(target),
        'original_global_proteins':len(original),'original_global_pairs':original_pairs,
        'updated_global_pairs':sum(map(len,updated.values())),'original_pairs_removed':0,
        'only_allowed4040_proteins_gained_labels':True,'all_original_nonfitting_rows_retained':True,
        'added_cells':added_counts,'new_heads':new_counts,'old_head_count':len(old_heads),'updated_head_count':len(new_heads),
        'role_counts':{'fit':4040,'validation':797,'final':3300},'fit_manifest_sources':frame_pins,
        'fresh_final_reference_opened':False,'new_metric_predictor_or_hyperparameter_selection':False}
    write_json(output/'seed_union.json',result);return result


def _source_metadata(path,proteins,terms,values,*,arm,namespace,source):
    import numpy as np
    path=Path(path);need(not path.exists(),'preserve prior control arrays.')
    np.save(path,values,allow_pickle=False)
    result={'namespace':namespace,'arm':arm,'proteins':list(proteins),'terms':list(terms),
        'prediction_file':str(path),'prediction_sha256':file_sha256(path),
        'final_reference_labels_read_for_forecasting':False,
        'upper_roundoff_tolerance':1e-10 if arm==RAW else 0.,'source_provenance':source}
    meta=path.with_suffix('.json');write_json(meta,result)
    return {'file':str(meta),'sha256':file_sha256(meta)}


def predict(cfg,prepared,output):
    import numpy as np
    from tools.cafa_prediction import core
    from tools.cafa_prediction.run import read
    from .forecast import query_frame,saved_sparse_scores
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    union=json.loads((Path(prepared)/'seed_union.json').read_text())
    need(union['source_input_pins']==cfg['input_pins'] and union['fresh_final_reference_opened'] is False,'union source boundary changed.')
    need(file_sha256(union['updated_training_file'])==union['updated_training_sha256'],'updated fitting-only seed table changed.')
    modules=core.author_modules(cfg['localplus_author'],cfg['localplus_author_receipt'])
    graph=read(cfg['graph']);index={n.removeprefix('UniProtKB:'):i for i,n in enumerate(graph['nodes'])}
    P=modules['alg_utils'].normalizeGraphEdgeWeights(core.adjacency(graph['nodes'],graph['pairs']));del graph
    need((P.data>=0).all(),'source monotonicity requires unchanged nonnegative P.')
    roles={r:read_target_ids(p) for r,p in cfg['roles'].items()};queries=tuple(sorted(set().union(*map(set,roles.values()))))
    need(len(queries)==4097 and set(roles)=={'validation','final'},'complete unchanged forecast identity union required.')
    present,missing=query_frame(queries,index);positions={p:i for i,p in enumerate(queries)}
    present_rows=np.asarray([positions[p] for p in present]);indices=np.asarray([index[p] for p in present],dtype=int)
    original=read(cfg['original_training']);updated=read(union['updated_training_file'])
    old_heads=by_head(original,index);new_heads=by_head(updated,index)
    # Existing literal sparse reader enforces score precision and identical repeats.
    pk=set(read_target_ids(cfg['old_pk_targets']));val=set(roles['validation'])
    previous=saved_sparse_scores(cfg['old_localplus_files']['PK'],val&pk)
    previous.update(saved_sparse_scores(cfg['old_localplus_files']['nonPK'],val-pk))
    previous.update(saved_sparse_scores([cfg['final_localplus_source']],set(roles['final'])))
    old_axes={ns:sorted(t for a,t in old_heads if a==aspect) for ns,aspect in ASPECT.items()}
    new_axes={ns:sorted(t for a,t in new_heads if a==aspect) for ns,aspect in ASPECT.items()}
    baselines={};raw={}
    for ns in ASPECT:
        baselines[ns]=np.lib.format.open_memmap(output/(ns+'_original_replay.npy'),mode='w+',dtype=np.float64,shape=(len(queries),len(old_axes[ns])))
        raw[ns]=np.lib.format.open_memmap(output/(ns+'_updated_raw.npy'),mode='w+',dtype=np.float64,shape=(len(queries),len(new_axes[ns])))
        baselines[ns][:]=0;raw[ns][:]=0
    replayed=0
    for ns,aspect in ASPECT.items():
        for column,term in enumerate(old_axes[ns]):
            scores,_=core.run_term(modules,P,None,old_heads[(aspect,term)],'localplus')
            values=np.zeros(len(queries),dtype=np.float64);values[present_rows]=scores[indices]
            for protein,value in zip(queries,values):
                need(float(value)==previous.pop((protein,term),0.),'original global seed replay differs from preserved literal forecasts.')
            baselines[ns][:,column]=values;replayed+=len(queries)
        baselines[ns].flush();print('ORIGINAL_SEED_REPLAY_COMPLETE',ns,len(old_axes[ns]),flush=True)
    need(not previous,'preserved original score head was omitted from replay.')
    write_json(output/'original_replay_gate.json',{'all_original_cells_exact':True,'cells':replayed,'queries':len(queries),
        'seed_source':cfg['original_training'],'graph_P_or_runtime_changed':False,'new_reference_opened':False})
    changed,reused=0,0
    for ns,aspect in ASPECT.items():
        old_index={t:i for i,t in enumerate(old_axes[ns])}
        for column,term in enumerate(new_axes[ns]):
            key=(aspect,term);old_positive=old_heads.get(key,set());new_positive=new_heads[key]
            if old_positive==new_positive:
                values=baselines[ns][:,old_index[term]];reused+=1
            else:
                scores,_=core.run_term(modules,P,None,new_positive,'localplus');values=np.zeros(len(queries),dtype=np.float64);values[present_rows]=scores[indices];changed+=1
            if term in old_index:need(np.all(values>=baselines[ns][:,old_index[term]]),'add-only nonnegative native LocalPlus scores decreased.')
            raw[ns][:,column]=values
        raw[ns].flush();print('UPDATED_SOURCE_HEADS_COMPLETE',ns,len(new_axes[ns]),flush=True)
    result={'format':'biograph-steward.fixed-freshness-forecasts.v1','roles':{},'source_input_pins':cfg['input_pins'],
        'seed_union_sha256':file_sha256(Path(prepared)/'seed_union.json'),'graph_absent_queries':missing,
        'original_replay_exact_cells':replayed,'changed_or_new_head_calls':changed,'unchanged_head_reuses':reused,
        'native_add_only_monotonicity_passed':True,'new_reference_opened':False}
    for role,targets in roles.items():
        folder=output/role;folder.mkdir();rows=np.asarray([positions[p] for p in targets]);result['roles'][role]={RAW:{},FREQUENCY:{}}
        for ns in ASPECT:
            result['roles'][role][RAW][ns]=_source_metadata(folder/(RAW+'_'+ns+'.npy'),targets,new_axes[ns],raw[ns][rows],arm=RAW,namespace=ns,
                source={'published_predictor':'unchanged runLocal','original_global_seeds_retained':True,'only4040_fitting_additions':True,'original_replay_gate':str(output/'original_replay_gate.json'),'graph_absent_targets':sorted(set(targets)&set(missing))})
            prior_spec=cfg['priors'][ns];prior=np.load(prior_spec['file'],allow_pickle=False)
            need(file_sha256(prior_spec['file'])==prior_spec['sha256'],'frozen marginal prior bytes changed.')
            m=json.loads(Path(cfg['fit_manifests'][ns]['file']).read_text());need(prior.shape==(len(m['terms']),),'frozen full-fit marginal axis differs.')
            values=np.broadcast_to(prior,(len(targets),len(prior)))
            artifact=_source_metadata(folder/(FREQUENCY+'_'+ns+'.npy'),targets,m['terms'],values,arm=FREQUENCY,namespace=ns,
                source={'frozen_prior_source':prior_spec,'prior_recomputed':False,'statistical_meaning':'Existing full4040 marginal label prevalence; no experimental-negative truth claim.'})
            saved=np.load(json.loads(Path(artifact['file']).read_text())['prediction_file'],mmap_mode='r')
            need(saved.dtype==prior.dtype and saved[0].tobytes()==prior.tobytes() and saved[-1].tobytes()==prior.tobytes(),'prior broadcast changed exact values/dtype.')
            result['roles'][role][FREQUENCY][ns]=artifact
    write_json(output/'forecasts.json',result);return result


def soft(cfg,raw_directory,output):
    import numpy as np
    from tools.learned_combination.native_adapter import native_ontologies
    from .postprocessing import published_soft_closure
    raw_directory=Path(raw_directory);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    receipt=json.loads((raw_directory/'forecasts.json').read_text());ont=native_ontologies(cfg['ontology']);result={'roles':{},'new_reference_opened':False}
    for role,arms in receipt['roles'].items():
        folder=output/role;folder.mkdir();result['roles'][role]={SOFT:{}}
        for ns,row in arms[RAW].items():
            m=json.loads(Path(row['file']).read_text());need(file_sha256(row['file'])==row['sha256'] and file_sha256(m['prediction_file'])==m['prediction_sha256'],'raw freshness forecast changed.')
            source=np.load(m['prediction_file'],mmap_mode='r');terms=tuple(n['id'] for n in ont[ns].terms_list);mapping={t:i for i,t in enumerate(terms)}
            need(set(m['terms'])<=set(terms),'updated source head outside fixed qualified graph.')
            values=np.zeros((len(m['proteins']),len(terms)),dtype=np.float32)
            for i,term in enumerate(m['terms']):values[:,mapping[term]]=source[:,i]
            fixed,audit=published_soft_closure(cfg['postprocessing_author_root'],ont[ns],terms,values)
            result['roles'][role][SOFT][ns]=_source_metadata(folder/(SOFT+'_'+ns+'.npy'),m['proteins'],terms,fixed,arm=SOFT,namespace=ns,
                source={'raw_source_metadata':row,'postprocessing':audit,'raw_float64_to_float32_cast':'same one-time cast as existing soft controls; no clipping/tuning','original_source_head_count':len(m['terms'])})
    write_json(output/'forecasts.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('prepare','predict','soft'));p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--prepared');p.add_argument('--raw')
    a=p.parse_args();cfg=load_config(a.config)
    if a.phase=='prepare':prepare(cfg,a.output)
    elif a.phase=='predict':predict(cfg,a.prepared,a.output)
    else:soft(cfg,a.raw,a.output)


if __name__=='__main__':main()
