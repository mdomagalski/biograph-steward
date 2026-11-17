"""Score the predeclared complete gene-pair specialist secondary.

The independently fixed primary agent comparison must have a complete prediction
seal before this module can open any secondary relation outcomes. All scoring
uses the same native-label join and metrics as that primary comparison.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import statistics

from biograph_steward.client import digest,utcnow,write_json
from biograph_steward.file_utils import sha
from .prepare import need,RELATIONS
from .predict import load_frame
from .evaluate import sealed,code_pins,native_labels,metrics,ALLOWED_GENE_RELATIONS


def clustered_intervals(pmids,gold,arms,repeats=5000):
    """Paired publication cluster bootstrap, preserving every within-paper row.

    Only additive confusion counts are cached; resampling those counts is
    exactly equivalent to resampling complete publications and recomputing the
    shared micro metrics. See Field & Welsh (2007), doi:10.1111/j.1467-9868.2007.00593.x.
    """
    need(len(pmids)==len(gold) and len(set(pmids))>=2,'cluster intervals require at least two aligned publications.')
    groups={}
    for i,pmid in enumerate(pmids):groups.setdefault(pmid,[]).append(i)
    def vector(m):
        e,p=m['exact_positive_relation'],m['entity_pair']
        return [m['cases'],m['exact_correct'],m['cases']-m['unresolved'],
                e['tp'],e['fp'],e['fn'],p['tp'],p['fp'],p['fn']]
    def measures(v):
        n,correct,covered,tp,fp,fn,ptp,pfp,pfn=v
        ratio=lambda a,b:a/b if b else 0.
        return {'exact_accuracy':correct/n,'coverage':covered/n,
            'exact_positive_precision':ratio(tp,tp+fp),'exact_positive_recall':ratio(tp,tp+fn),
            'exact_positive_F1':ratio(2*tp,2*tp+fp+fn),
            'pair_precision':ratio(ptp,ptp+pfp),'pair_recall':ratio(ptp,ptp+pfn),
            'pair_F1':ratio(2*ptp,2*ptp+pfp+pfn)}
    cached=[]
    for pmid in sorted(groups):
        take=groups[pmid]
        cached.append({name:vector(metrics([gold[i] for i in take],[pred[i] for i in take]))
                       for name,pred in arms.items()})
    names=list(arms);samples={name:[] for name in names}
    comparisons=[('specialist_native','typed_co_mention'),('specialist_type_guard','specialist_native')]
    comparisons=[pair for pair in comparisons if all(name in arms for name in pair)]
    deltas={a+' minus '+b:[] for a,b in comparisons}
    rng=random.Random('biograph-biored-publication-cluster-v1')
    for _ in range(repeats):
        weights=Counter(rng.randrange(len(cached)) for _ in range(len(cached)))
        totals={name:[0]*9 for name in names}
        for index,weight in weights.items():
            for name in names:
                for j,count in enumerate(cached[index][name]):totals[name][j]+=weight*count
        values={name:measures(total) for name,total in totals.items()}
        for name in names:samples[name].append(values[name])
        for a,b in comparisons:deltas[a+' minus '+b].append({key:values[a][key]-values[b][key] for key in values[a]})
    def intervals(rows):
        result={}
        for key in rows[0]:
            xs=sorted(r[key] for r in rows)
            result[key]=[xs[int(.025*repeats)],xs[min(repeats-1,int(.975*repeats))]]
        return result
    return {'method':'Paired nonparametric publication cluster percentile bootstrap; whole papers sampled with replacement, all their candidate rows retained.',
        'reference':'https://doi.org/10.1111/j.1467-9868.2007.00593.x','publications':len(cached),'replicates':repeats,
        'seed':'biograph-biored-publication-cluster-v1','confidence_level':.95,
        'arm_intervals':{name:intervals(rows) for name,rows in samples.items()},
        'paired_delta_intervals':{name:intervals(rows) for name,rows in deltas.items()},
        'interpretation':'Descriptive uncertainty across benchmark publications, not independent candidate-row intervals or a whole-Pharos accuracy guarantee. Cross-publication entity/evidence reuse can remain.'}


def primary_boundary(predeclaration,primary_freeze):
    proof=sealed(primary_freeze)
    need(proof['format']=='biograph-steward.biored-prediction-freeze.v1'
         and proof['completed_cases']==predeclaration['primary_cases']
         and proof['frame_content_sha256']==predeclaration['primary_frame_content_sha256'],
         'all primary specialist/agent/flat predictions must be sealed before secondary labels open.')
    need(proof['code_sha256']==code_pins(),'primary frozen method changed before secondary label access.')
    return proof


def score(frame_dir,predeclaration,execution_freeze,analysis_freeze,primary_freeze,specialist,data_zip,output):
    frame,cases=load_frame(frame_dir);pre=sealed(predeclaration);execution=sealed(execution_freeze)
    analysis=sealed(analysis_freeze)
    output=Path(output);specialist=Path(specialist)
    need(not output.exists(),'choose a new secondary assessment output.')
    need(frame['partition']=='test_secondary_full_gene' and pre['cases']==len(cases)
         and pre['publications']==len({c['pmid'] for c in cases}), 'secondary full candidate inventory differs.')
    need(pre['frame_content_sha256']==frame['content_sha256']==execution['frame_content_sha256']
         and execution['predeclaration_content_sha256']==pre['content_sha256'], 'secondary method/frame differs.')
    need(execution['code_sha256']==code_pins(),'secondary native scoring/inference method changed.')
    need(analysis['execution_freeze_content_sha256']==execution['content_sha256']
         and analysis['analysis_code_sha256']==sha(__file__)
         and analysis['shared_native_metrics_code_sha256']==code_pins()
         and not analysis['reference_outcomes_opened'],'secondary outcome-blind analysis freeze differs.')
    primary=primary_boundary(pre,primary_freeze)
    native_report=sealed(specialist/'execution.json')
    need(native_report['status']=='completed' and native_report['completed_cases']==len(cases)
         and native_report['frame_content_sha256']==frame['content_sha256'], 'finish every secondary prediction before labels open.')
    need(native_report['implementation_sha256']==execution['code_sha256']['tools/biored_agent/predict.py']
         and native_report['model_files_sha256']==frame['model_files_sha256']
         and native_report['author_implementation_sha256']==frame['author_code_files_sha256'],
         'secondary specialist implementation/artifact changed.')
    need(sha(specialist/'predictions.jsonl')==native_report['predictions_sha256'],'secondary predictions changed.')
    predictions=[json.loads(line) for line in (specialist/'predictions.jsonl').read_text().splitlines()]
    need([r['case_id'] for r in predictions]==[c['id'] for c in cases]
         and all(r['relation'] in RELATIONS for r in predictions), 'secondary prediction inventory or labels differ.')
    # Outcomes remain closed until both the complete primary seal and this full
    # specialist output have passed the immutable method and inventory checks.
    opened=utcnow();gold=native_labels(data_zip,frame,cases)
    native=[p['relation'] for p in predictions];guarded=[]
    for c,p in zip(cases,native):
        allowed=ALLOWED_GENE_RELATIONS-({'Bind'} if c['type1']=='DiseaseOrPhenotypicFeature' else set())
        guarded.append(p if p in allowed else 'Unresolved')
    arms={'always_None':['None']*len(cases),'typed_co_mention':['Association']*len(cases),
          'specialist_native':native,'specialist_type_guard':guarded}
    scores={name:metrics(gold,pred) for name,pred in arms.items()};groups={}
    for group in sorted({c['type1']+'--'+c['type2'] for c in cases}):
        take=[i for i,c in enumerate(cases) if c['type1']+'--'+c['type2']==group]
        groups[group]={name:metrics([gold[i] for i in take],[pred[i] for i in take]) for name,pred in arms.items()}
    per_pub=list(Counter(c['pmid'] for c in cases).values())
    report={'format':'biograph-steward.biored-full-gene-source-assessment.v1','created_at':utcnow(),
        'labels_first_opened_at':opened,'frame_content_sha256':frame['content_sha256'],
        'predeclaration_content_sha256':pre['content_sha256'],'execution_freeze_content_sha256':execution['content_sha256'],
        'analysis_freeze_content_sha256':analysis['content_sha256'],
        'primary_prediction_freeze_content_sha256':primary['content_sha256'],
        'specialist_execution_content_sha256':native_report['content_sha256'],'predictions_sha256':native_report['predictions_sha256'],
        'analysis_implementation_sha256':sha(__file__),'cases':len(cases),'publications':len(per_pub),
        'native_gold_label_counts':dict(Counter(gold)),'metrics':scores,'per_entity_type_metrics':groups,
        'publication_cluster_uncertainty':clustered_intervals([c['pmid'] for c in cases],gold,arms),
        'candidate_pairs_per_publication':{'minimum':min(per_pub),'median':statistics.median(per_pub),'maximum':max(per_pub)},
        'runtime':native_report['runtime'],'device':native_report['device'],
        'reported_specialist_elapsed_seconds':native_report['elapsed_seconds'],
        'comparison_interpretation':'Published specialist source-relation extraction against weak co-mention/type controls, not a measured gain over the original Pharos graph.',
        'label_scope':'Expert abstract-relative native BioRED annotations; None is no qualifying relation in that abstract, not biological irrelevance.',
        'sampling_scope':'Complete eligible native gene-pair benchmark, weighted by candidate rows. The primary agent assessment instead has one pair per publication; their point estimates have different denominators.',
        'uncertainty_scope':'Correlated candidate rows are not counted as independent publication replicates. No whole-Pharos population confidence interval is inferred.',
        'reference_limitations':['Gold entity spans/IDs are supplied; entity detection and canonical human-protein grounding are not tested.',
            'Public model/pretraining/checkpoint exposure cannot be fully independently audited.',
            'Native Bind is preserved as a corpus category and is not automatically direct physical binding.',
            'No additional language-model arm or automatic graph acceptance/pruning was introduced.'],
        'source_graph_changes':0,'training_performed':False}
    report['content_sha256']=digest(report);output.mkdir(parents=True);write_json(output/'report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('frame','predeclaration','execution-freeze','analysis-freeze','primary-prediction-freeze','specialist','data-zip','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args();r=score(args.frame,args.predeclaration,args.execution_freeze,args.analysis_freeze,args.primary_prediction_freeze,
        args.specialist,args.data_zip,args.output)
    print(json.dumps({k:r[k] for k in ('cases','publications','content_sha256')},indent=2))


if __name__=='__main__':main()
