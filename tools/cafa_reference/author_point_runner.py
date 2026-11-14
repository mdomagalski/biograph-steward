# SPDX-License-Identifier: GPL-3.0-only
"""Isolated adapter for the separately preserved GPL author CAFA evaluator.

No scoring implementation is copied or modified. The extra CSV preserves the
returned author's floating-point curves before its normal four-decimal export,
so subsequent uncertainty checks can verify exact point-score agreement.
"""
import argparse
import json
from pathlib import Path


def main():
    from cafaeval.evaluation import cafa_eval, write_results
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job-json',required=True)
    a=p.parse_args();job=json.loads(Path(a.job_json).read_text())
    df,best=cafa_eval(**job['author_call'])
    if df is None:raise ValueError('Author evaluator returned no scored prediction; do not invent zero-valued results.')
    write_results(df,best,out_dir=job['output_dir'],th_step=job['author_call']['th_step'])
    df.to_csv(Path(job['output_dir'])/'evaluation_all_exact.tsv',sep='\t',float_format='%.17g')
    # A predeclared operating point avoids presenting a threshold maximized
    # over test labels as a calibrated, deployable confidence.
    rows=[]
    for (filename,namespace),group in df.reset_index().groupby(['filename','ns']):
        chosen=group[(group['tau']-0.5).abs()<1e-12]
        if chosen.empty:
            rows.append({'filename':filename,'namespace':namespace,'threshold':0.5,
                         'status':'author omits thresholds with zero prediction coverage',
                         'PPV':None,'recall':None,'F1':None})
        else:
            if len(chosen)!=1:raise ValueError('Native fixed-threshold row is not unique.')
            row=chosen.iloc[0]
            rows.append({'filename':filename,'namespace':namespace,'threshold':0.5,
                         'status':'unchanged author curve at predeclared threshold',
                         'PPV':float(row['pr_micro']),'recall':float(row['rc_micro']),
                         'F1':float(row['f_micro']),'coverage':float(row['cov'])})
    (Path(job['output_dir'])/'fixed_threshold_0_5.json').write_text(json.dumps({
        'threshold_selected_using_test_labels':False,'rows':rows,
        'interpretation':'Annotation-reference operating point; scores are not calibrated probabilities.'},indent=2)+'\n')


if __name__=='__main__':main()
