# SPDX-License-Identifier: GPL-3.0-only
"""Descriptive strata of checked native CAFA per-protein contributions.

Published author normalization remains unchanged. Predeclared Pharos-TDL and
prior-source-exposure strata are retained alongside explicitly post-outcome
historical degree/known-annotation coverage diagnostics. No forecast or target
selection is performed and no stratum replaces the full benchmark result.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(config,output):
    import numpy as np
    import pandas as pd
    from cafaeval.evaluation import normalize
    assert np.__version__=='1.26.4'and pd.__version__=='2.2.3','Use the shared native scoring runtime.'
    cfg=json.loads(Path(config).read_text());pins={str(Path(__file__).resolve()):sha(__file__),str(Path(config).resolve()):sha(config)}
    for name,spec in cfg['metadata'].items():
        assert sha(spec['file'])==spec['sha256'];pins[spec['file']]=spec['sha256']
    def load(name):return Path(cfg['metadata'][name]['file'])
    tdl={r['uniprot']:r['tdl']for r in csv.DictReader(load('TDL').open(),delimiter='\t')}
    inmc=set(load('prior_INMC').read_text().split());crc=set(load('prior_CRC').read_text().split())
    graph=json.loads(gzip.decompress(load('historical_graph').read_bytes()))
    degree={n.removeprefix('UniProtKB:'):0 for n in graph['nodes']}
    for a,b,_ in graph['pairs']:
        degree[a.removeprefix('UniProtKB:')]+=1;degree[b.removeprefix('UniProtKB:')]+=1
    training=json.loads(gzip.decompress(load('historical_training').read_bytes()))
    known={p:sum(a=='BPO'for a,t in rows)for p,rows in training.items()}
    del graph,training
    rows=[];status=[]
    for method_key,spec in cfg['methods'].items():
        name=spec['method']
        p=Path(spec['counts']);agreement=Path(spec['agreement'])
        if not(p.exists()and agreement.exists()):
            status.append({'frame':spec['frame'],'method':name,'status':'pending_contributions'});continue
        a=json.loads(agreement.read_text());assert a['author_point_agreement_passed']is True
        assert all(v['max_absolute_curve_difference']<=1e-12 for v in a['checks'].values())
        pins[str(p)]=sha(p);pins[str(agreement)]=sha(agreement)
        with np.load(p,allow_pickle=False)as data:arrays={k:data[k]for k in data.files}
        ids=arrays['ids'];tau=arrays['tau'];assert len(ids)in(833,2826)
        groupings={'full_population':{'all':np.ones(len(ids),dtype=bool)},'predeclared_TDL':{label:np.asarray([tdl.get(p,'unknown')==label for p in ids])for label in ['Tdark','Tbio','Tchem','Tclin','unknown']},
                   'predeclared_source_exposure':{'CRC_native_GOA':np.asarray([p in crc for p in ids]),
                    'INMC_only_native_GOA':np.asarray([p in inmc and p not in crc for p in ids]),
                    'neither_prior_selected_GOA':np.asarray([p not in inmc and p not in crc for p in ids])}}
        diagnostics={}
        for category,values in [('post_outcome_historical_degree',[degree.get(p,0)for p in ids]),
                                ('post_outcome_known_BPO_count',[known.get(p,0)for p in ids])]:
            values=np.asarray(values);cuts=np.quantile(values,[.25,.5,.75]);assigned=np.searchsorted(cuts,values,side='left')
            groupings[category]={f'quartile_{i+1}':assigned==i for i in range(4)}
            diagnostics[category]={'cuts':cuts.tolist(),'range':[int(values.min()),int(values.max())],
                'ties_policy':'Assign ties to lower quartile; empty quartiles retained.'}
        for family,groups in groupings.items():
            assert sum(int(m.sum())for m in groups.values())==len(ids)
            for label,mask in groups.items():
                row={'frame':spec['frame'],'method':name,'namespace':'biological_process','setting':'partial',
                     'stratum_family':family,'stratum':label,'raw_proteins':int(mask.sum()),
                     'degree_or_annotation_metadata':diagnostics.get(family)}
                ordinary_coverage=np.zeros(len(tau),dtype=bool)
                for key,eligible_key,prefix in [('ordinary','eligible',''),('IA_weighted','eligible_IA_weighted','IA_')]:
                    ne=int(arrays[eligible_key][mask].sum());row[prefix+'eligible_proteins']=ne
                    if ne==0:
                        row[prefix+'status']='no_eligible_reference';continue
                    summed=arrays[key][mask].sum(axis=0)
                    native=normalize(pd.DataFrame(summed,columns=['n','tp','fp','fn','pr','rc']),
                                     'biological_process',tau,np.repeat(ne,len(tau)),'cafa')
                    # cafa_eval merges the two readouts and filters by ordinary
                    # coverage, retaining IA-zero rows at an ordinary-covered tau.
                    if key=='ordinary':ordinary_coverage=np.asarray(native['cov']>0)
                    curve=native.loc[ordinary_coverage]
                    if curve.empty:row[prefix+'status']='no_native_positive_coverage';continue
                    row[prefix+'status']='scored'
                    for column,name_,fn in [('f_micro','micro_Fmax','idxmax'),('f','macro_Fmax','idxmax'),('s','Smin','idxmin')]:
                        best=curve.loc[getattr(curve[column],fn)()];row[prefix+name_]=float(best[column]);row[prefix+name_+'_tau']=float(best['tau'])
                    fixed=native.loc[np.isclose(native['tau'],.5,rtol=0,atol=1e-15)].iloc[0]
                    if not ordinary_coverage[int(round(.5*1000))-1]:
                        row[prefix+'fixed_0_5']={'status':'author omits thresholds with zero prediction coverage',
                            'PPV':None,'recall':None,'F1':None,'coverage':0.0}
                    else:
                        row[prefix+'fixed_0_5']={'status':'unchanged author normalization at fixed threshold',
                            **{k:float(fixed[c])for k,c in [('PPV','pr_micro'),('recall','rc_micro'),('F1','f_micro'),('coverage','cov')]}}
                rows.append(row)
        status.append({'frame':spec['frame'],'method':name,'status':'scored_checked_contributions'})
    report={'format':'biograph-steward.cafa5-native-stratified-aggregates.v1','rows':rows,'methods':status,
        'runtime':{'numpy':np.__version__,'pandas':pd.__version__},
        'predeclared_strata':['native April2024 Pharos TDL','prior selected nativeGOA exposure identities'],
        'post_outcome_diagnostics':['historical source degree quartiles','known_t0 BPO annotation count quartiles'],
        'fixed_predictions_and_full_frames_unchanged':True,
        'native_author_normalization_unchanged':True,
        'small_strata_and_source_dependence_limit_inference':True,
        'no_stratum_used_for_model_threshold_or_target_selection':True,
        'source_files_sha256':pins,
        'caveats':['TDL is April2024 metadata after prediction t0, used only for analysis.',
                   'Quartile diagnostics are post-outcome descriptions, not independently validated biological subgroups.',
                   'Stratum-specific Fmax uses a benchmark-selected evaluation cutoff, not deployment calibration.',
                   'Same full reference and method outputs remain authoritative; unknown/missing source coverage is explicit.']}
    report['content_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    out=Path(output);assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=run(a.config,a.output);print(json.dumps({'rows':len(r['rows']),'content_sha256':r['content_sha256']}))
