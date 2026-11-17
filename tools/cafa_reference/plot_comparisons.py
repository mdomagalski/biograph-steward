"""Plot fixed, sealed aggregate contrasts; no models or reference rows are read."""
import argparse
import json
import math
from pathlib import Path

from biograph_steward.client import digest,utcnow,write_json
from biograph_steward.file_utils import new_output,sha

METHODS=('fastsinksourceplus','localplus','genemaniaplus','strict_alias_localplus')
LABELS=('FastSinkSource+ · primary','LocalPlus · comparator','GeneMANIA+ · secondary','Full-context LocalPlus · strict')


def render(source,source_sha256,output):
    source=Path(source)
    if source.is_symlink() or not source.is_file() or source.stat().st_size>10_000_000 or sha(source)!=source_sha256:
        raise ValueError('Use the explicitly pinned aggregate projection.')
    report=json.loads(source.read_bytes())
    if (report.get('format')!='biograph-steward.cafa5-scientific-aggregate-projection.v1'
        or report.get('content_sha256')!=digest({k:v for k,v in report.items() if k!='content_sha256'})
        or len(report['rows'])!=240 or report['status_counts'].get('pending',0)):
        raise ValueError('A complete, correctly sealed fixed-outcome projection is required.')
    points={};comparisons={}
    for method in METHODS:
        rows=[r for r in report['rows'] if (r['frame'],r['setting'],r['namespace'],r['method'])==
            ('primary','partial','biological_process',method)]
        if len(rows)!=1 or rows[0]['status']!='scored' or rows[0]['eligible_proteins']!=833 or rows[0]['IA_eligible_proteins']!=832:
            raise ValueError('The fixed original BPO point or denominator is unavailable.')
        point={k:rows[0][k] for k in ('micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax','fixed_0_5')}
        if not all(type(point[k]) in (int,float) and math.isfinite(point[k]) and 0<=point[k]<=1
                   for k in ('micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax')):
            raise ValueError('Invalid saved native Fmax point.')
        points[method]=point
    for method in (METHODS[0],METHODS[2],METHODS[3]):
        rows=[r for r in report['paired_comparisons'] if
            (r['frame'],r['setting'],r['namespace'],r['candidate'],r['comparator'],r['readout'])==
            ('primary','partial','biological_process',method,'localplus','ordinary')]
        if len(rows)!=1:raise ValueError('Missing or duplicate predeclared paired contrast.')
        interval=rows[0]['paired_95_percentile_interval']
        observed=points[method]['micro_Fmax']-points['localplus']['micro_Fmax']
        if len(interval)!=2 or not all(math.isfinite(x) for x in interval) or not interval[0]<=observed<=interval[1]:
            raise ValueError('Saved difference interval is invalid.')
        comparisons[method]={'observed_difference':observed,'paired_interval':interval,
            'source_report_sha256':rows[0]['source_report_sha256']}
    folder=new_output(output,source)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':source_sha256,'pdf.fonttype':42})
    fig,(left,right)=plt.subplots(1,2,figsize=(14,7.1),gridspec_kw={'width_ratios':[1.1,1]})
    fig.subplots_adjust(left=.25,right=.97,top=.74,bottom=.30,wspace=.72)
    ink,teal,amber,gray='#172b3a','#147c83','#ae6b18','#71818e'
    fig.suptitle('Measured gains in function recovery',x=.035,y=.96,ha='left',fontsize=18,fontweight='bold',color=ink)
    fig.text(.035,.91,'CAFA5 temporal curator reference · biological process · partial knowledge · fixed published methods',fontsize=11,color=ink)
    for y,(method,label) in enumerate(zip(METHODS,LABELS)):
        a,b=points[method]['micro_Fmax'],points[method]['IA_micro_Fmax']
        left.plot([a,b],[y,y],color='#cbd5dc',zorder=1)
        left.scatter([a],[y],color=teal,s=48,zorder=3)
        left.scatter([b],[y],color=amber,marker='D',s=40,zorder=3)
        left.annotate(f'{a:.4f} / {b:.4f}',(max(a,b),y),xytext=(0,-20),textcoords='offset points',ha='right',fontsize=9)
    left.set(yticks=range(4),yticklabels=LABELS,xlim=(.095,.145),ylim=(3.6,-.5),
        xlabel='Native benchmark Fmax (higher is better)',title='Primary candidate and selected fixed comparators')
    left.grid(axis='x',alpha=.16)
    contrast_labels=('FSS primary − Local','GeneMANIA+ − Local','Full-context Local − Local')
    for y,(method,label) in enumerate(zip(comparisons,contrast_labels)):
        row=comparisons[method];point=row['observed_difference'];lo,hi=row['paired_interval']
        right.errorbar(point,y,xerr=[[point-lo],[hi-point]],fmt='o',color=gray if y==0 else teal,capsize=5,markersize=6)
        right.annotate(f'{point:+.4f} [{lo:+.4f}, {hi:+.4f}]',(point,y),xytext=(0,-23),
            textcoords='offset points',ha='center',fontsize=9,color=ink)
    right.axvline(0,color=gray,linestyle='--',linewidth=1)
    right.set(yticks=range(3),yticklabels=contrast_labels,xlim=(-.015,.027),ylim=(2.65,-.5),
        xlabel='Observed micro-Fmax difference',title='Paired difference and conditional 95% interval')
    right.grid(axis='x',alpha=.16)
    fig.legend(handles=[Line2D([],[],marker='o',color=teal,linestyle='',label='Ordinary micro Fmax'),
        Line2D([],[],marker='D',color=amber,linestyle='',label='Information-weighted micro Fmax')],
        loc='upper left',bbox_to_anchor=(.03,.875),ncol=2,frameon=False)
    fig.text(.035,.205,'The original FSS primary did not improve. Positive method and source-profile findings are secondary.',fontsize=11,fontweight='bold',color=ink)
    fig.text(.035,.16,'Fuller context also changes historical seed coverage and source qualification; this is not a gain over the complete original Pharos graph.',fontsize=9.5,color=ink)
    fig.text(.035,.125,'IA-macro decreases slightly. At fixed 0.5, full-context Local F1 falls (0.0614 → 0.0502); benchmark Fmax does not calibrate acceptance.',fontsize=9.5,color=ink)
    fig.text(.035,.09,'Reference N=833 (IA:832). Intervals use 2,000 paired protein draws; secondary intervals are descriptive and not multiplicity-adjusted.',fontsize=9,color=ink)
    fig.text(.035,.055,'Shared genes, neighbors and studies remain. These are function-annotation results, separate from PPI precision or whole-graph biological truth.',fontsize=9,color=ink)
    for suffix in ('png','svg','pdf'):fig.savefig(folder/('function_recovery_comparisons.'+suffix),dpi=180,facecolor='white')
    plt.close(fig)
    write_json(folder/'plotted_aggregates.json',{'points':points,'comparisons':comparisons,
        'source_content_sha256':report['content_sha256'],'source_status_counts':report['status_counts']})
    if sha(source)!=source_sha256:raise ValueError('Aggregate changed while rendering.')
    receipt={'format':'biograph-steward.cafa-fixed-comparisons-figure.v1','created_at':utcnow(),
        'source_file_sha256':source_sha256,'source_content_sha256':report['content_sha256'],
        'implementation_sha256':sha(__file__),'matplotlib':matplotlib.__version__,
        'raw_reference_or_prediction_rows_read':False,'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
    receipt['content_sha256']=digest(receipt);write_json(folder/'report.json',receipt);return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','source-sha256','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(render(**vars(parser.parse_args())),indent=2))
