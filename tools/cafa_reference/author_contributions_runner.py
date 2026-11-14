# SPDX-License-Identifier: GPL-3.0-only
"""Execute author per-protein confusion counts for a paired CAFA bootstrap.

Only the separately preserved GPL author implementation computes the scores.
Every resulting micro-F curve must reproduce the full author's exact curve
before these counts are admitted to any confidence interval.
"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path


def main():
    import numpy as np
    import pandas as pd
    from cafaeval.parser import obo_parser, gt_parser, gt_exclude_parser, pred_parser, update_toi
    from cafaeval.evaluation import compute_confusion_matrix_exclude
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job-json',required=True)
    a=p.parse_args();job=json.loads(Path(a.job_json).read_text())
    call=job['author_call'];ns='biological_process'
    ontologies=obo_parser(call['obo_file'],('is_a','part_of'),call['ia'],False)
    ontologies=update_toi(ontologies,call['toi_file'])
    gt=gt_parser(call['gt_file'],ontologies)
    exclude=gt_exclude_parser(call['exclude'],gt,ontologies)
    prediction=pred_parser(job['prediction'],ontologies,gt,'fill',None)
    if ns not in gt or ns not in prediction:raise ValueError('Primary BPO reference/prediction missing; do not impute an evaluated curve.')
    ontology=ontologies[ns];g=gt[ns].matrix;pred=prediction[ns].matrix;ex=exclude[ns].matrix
    ids=[None]*len(gt[ns].ids)
    for name,index in gt[ns].ids.items():ids[index]=name
    tau=np.arange(.001,1,.001)
    ordinary=np.zeros((len(ids),len(tau),6),dtype=np.float64)
    weighted=np.zeros_like(ordinary)
    eligible=np.zeros(len(ids),dtype=bool);eligible_w=np.zeros_like(eligible)
    out=Path(job['output_dir']);out.mkdir(parents=True,exist_ok=False)
    with (out/'author_counts.log').open('w') as log,redirect_stdout(log):
        for i in range(len(ids)):
            for toi,counts,mask,ic in ((ontology.toi,ordinary,eligible,None),
                                     (ontology.toi_ia,weighted,eligible_w,ontology.ia)):
                # This is exactly the author's pre-exclusion inclusion rule in
                # compute_metrics. Root/known-only rows are not silently fixed.
                if not np.any(g[i,toi]):continue
                selected=np.setdiff1d(toi,ex[i,:].nonzero()[0],assume_unique=True)
                truth=g[i,selected]
                n_gt=np.array([truth.sum() if ic is None else (truth*ic[selected]).sum()])
                mask[i]=n_gt[0]>0
                counts[i,:,:]=compute_confusion_matrix_exclude(tau,[truth],pred[i:i+1,:],
                    [selected],n_gt,ic)
    point=pd.read_csv(job['exact_point_curves'],sep='\t')
    point=point.loc[point['ns']==ns]
    if point.empty:raise ValueError('Exact author BPO curve is absent.')
    checks={}
    for counts,label,column in ((ordinary,'ordinary','f_micro'),(weighted,'IA_weighted','f_micro_w')):
        totals=counts.sum(axis=0)
        derived=np.divide(2*totals[:,1],2*totals[:,1]+totals[:,2]+totals[:,3],
                          out=np.zeros(len(tau)),where=(2*totals[:,1]+totals[:,2]+totals[:,3])>0)
        worst=0.0;seen=set()
        for row in point[['tau',column]].itertuples(index=False,name=None):
            index=int(round(row[0]*1000))-1
            if not 0<=index<len(tau):raise ValueError('Unrecognized author threshold grid.')
            seen.add(index)
            worst=max(worst,abs(float(derived[index])-row[1]))
        if any(value>0 and index not in seen for index,value in enumerate(derived)):
            raise ValueError('Nonzero derived micro-F threshold absent from author curve.')
        if worst>1e-12:raise ValueError('Per-protein counts do not reproduce exact author '+label+' micro curve: '+str(worst))
        checks[label]={'max_absolute_curve_difference':worst,'author_curve_rows':len(point),
                       'micro_Fmax_from_counts':float(derived.max())}
    np.savez_compressed(out/'counts.npz',ids=np.asarray(ids),tau=tau,
        ordinary=ordinary,IA_weighted=weighted,eligible=eligible,eligible_IA_weighted=eligible_w)
    (out/'agreement.json').write_text(json.dumps({'author_point_agreement_passed':True,
        'namespace':ns,'raw_reference_proteins':len(ids),'ordinary_eligible':int(eligible.sum()),
        'raw_reference_proteins_definition':'Author gt_parser protein IDs after ontology recognition, before TOI/known exclusions; raw source-target counts are recorded separately by reference release.',
        'IA_weighted_eligible':int(eligible_w.sum()),'checks':checks},indent=2)+'\n')
    print(json.dumps(checks,indent=2))


if __name__=='__main__':main()
