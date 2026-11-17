"""Established paired protein resampling of already checked author micro-F counts.

The same protein multiplicities apply to every arm, retaining all terms of each
sampled protein together. This quantifies conditional benchmark variability;
it neither labels unknown biological functions false nor creates independent
experimental replications. No model or deployed threshold is selected here.
"""
import argparse
import json
from pathlib import Path

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .intake import need

DRAWS=2000
SEED=20261113


def micro_fmax(counts, weights):
    import numpy as np
    tp=counts[:,:,1]
    denominator=2*tp+counts[:,:,2]+counts[:,:,3]
    numerator=2*(weights@tp)
    denominator=weights@denominator
    curves=np.divide(numerator,denominator,out=np.zeros_like(numerator),where=denominator>0)
    return curves.max(axis=1)


def resample(arrays, *, draws=DRAWS, seed=SEED):
    """All input arrays must have one shared, identically ordered protein frame."""
    import numpy as np
    need(arrays and type(draws) is int and draws>0 and type(seed) is int, 'nonempty arrays/fixed resampling required.')
    first=next(iter(arrays.values()))
    ids,tau=first['ids'],first['tau']
    need(len(ids)>1 and len(set(ids))==len(ids), 'at least two unique raw reference proteins required.')
    for row in arrays.values():
        need(np.array_equal(row['ids'],ids) and np.array_equal(row['tau'],tau), 'method protein/threshold frames differ.')
        need(row['ordinary'].shape == row['IA_weighted'].shape == (len(ids),len(tau),6)
             and np.isfinite(row['ordinary']).all() and np.isfinite(row['IA_weighted']).all(),
             'nonfinite or malformed author contributions.')
    rng=np.random.default_rng(seed)
    weights=rng.multinomial(len(ids),np.repeat(1/len(ids),len(ids)),size=draws).astype(np.float64)
    results={}
    for name,row in arrays.items():
        results[name]={key:micro_fmax(row[key],weights) for key in ('ordinary','IA_weighted')}
    return weights,results


def run(config, output):
    import numpy as np
    config_path=Path(config);cfg=json.loads(config_path.read_text())
    need(cfg['draws']==DRAWS and cfg['seed']==SEED,'predeclared resampling differs.')
    arrays={};pins={}
    for method,source in cfg['methods'].items():
        path=Path(source['counts']);agreement=Path(source['agreement'])
        need(sha(path)==source['counts_sha256'] and sha(agreement)==source['agreement_sha256'],
             'author contribution/point agreement pin differs.')
        a=json.loads(agreement.read_text())
        need(a['author_point_agreement_passed'] is True,'author point agreement is required before resampling.')
        for value in a['checks'].values():
            need(value['max_absolute_curve_difference']<=1e-12,'exact author point curve agreement failed.')
        with np.load(path,allow_pickle=False) as f:arrays[method]={k:f[k] for k in f.files}
        pins[str(path)]=source['counts_sha256'];pins[str(agreement)]=source['agreement_sha256']
    weights,scores=resample(arrays,draws=cfg['draws'],seed=cfg['seed'])
    folder=new_output(output,config_path,*pins)
    np.save(folder/'protein_multiplicities.npy',weights.astype(np.int32),allow_pickle=False)
    serial={};comparisons=[]
    for name,by in scores.items():
        serial[name]={}
        for kind,values in by.items():
            serial[name][kind]={'bootstrap_95_percentile_interval':np.quantile(values,[.025,.975]).tolist(),
                                'bootstrap_mean':float(values.mean())}
            np.save(folder/(name+'_'+kind+'_Fmax.npy'),values,allow_pickle=False)
    for a,b in cfg['comparisons']:
        need(a in scores and b in scores,'declared comparison method absent.')
        for kind in ('ordinary','IA_weighted'):
            diff=scores[a][kind]-scores[b][kind]
            comparisons.append({'candidate':a,'comparator':b,'readout':kind,
                'difference_mean':float(diff.mean()),
                'paired_95_percentile_interval':np.quantile(diff,[.025,.975]).tolist(),
                'fraction_draws_above_zero':float((diff>0).mean()),
                'interpretation':'Conditional descriptive paired protein bootstrap; not a study-replication p-value.'})
    need(all(sha(p)==v for p,v in pins.items()),'contribution inputs changed during resampling.')
    report={'format':'biograph-steward.cafa5-paired-protein-bootstrap.v1','created_at':utcnow(),
        'config_sha256':sha(config_path),'draws':DRAWS,'seed':SEED,'raw_proteins':len(next(iter(arrays.values()))['ids']),
        'protein_frame_definition':'Author gt_parser protein IDs after ontology recognition, before per-protein TOI/known-term exclusions. Native release records the original source frame and any outside-ontology targets.',
        'metric':'author micro Fmax across fixed .001... .999 threshold grid; recomputed per resample',
        'shared_protein_samples_across_all_arms':True,'scores':serial,'comparisons':comparisons,
        'source_files_sha256':pins,'numpy':np.__version__,
        'limitations':['Proteins share graph neighbors, annotations and studies; these intervals do not establish independent biological replication.',
            'Incomplete curator annotation is treated by the fixed CAFA benchmark convention, not asserted to be comprehensive negative biology.',
            'Fmax optimizes an evaluation threshold; it is not a prospectively calibrated application acceptance threshold.'],
        'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
    report['content_sha256']=digest(report);write_json(folder/'report.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    r=run(**vars(p.parse_args()));print(json.dumps(r,indent=2))


if __name__=='__main__':main()
