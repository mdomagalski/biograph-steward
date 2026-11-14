"""Seal all declared CAFA outcomes and checked uncertainty without selecting winners.

This consumes native-author aggregate exports only. It does not read reference
protein/term rows, make predictions, change thresholds or create missing scores.
"""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def seal(summary, denominators, base, output, confidence_reports=()):
    summary,denominators,base,output=map(Path,(summary,denominators,base,output))
    data=json.loads(summary.read_text());native=json.loads(denominators.read_text())
    assert data['expected_outcome_slots']==240 and len(data['rows'])==240
    assert data['runtime']=='Brev NumPy1.26.4/Pandas2.2.3'
    rows=data['rows'];keys=[tuple(r[k]for k in('frame','setting','method','namespace'))for r in rows]
    assert len(set(keys))==240
    for path,expected in data['source_files_sha256'].items():
        assert sha(path)==expected,('aggregate source changed',path)
    denoms=[]
    releases={frame:json.loads((base/f'released_{frame}_v1/report.json').read_text())
              for frame in ('primary','reserved')}
    aspect_codes={'biological_process':'BPO','molecular_function':'MFO','cellular_component':'CCO'}
    for frame,settings in native['frames'].items():
        for setting,namespaces in settings.items():
            for namespace,counts in namespaces.items():
                original=releases[frame]['counts'][setting]
                denoms.append({'frame':frame,'setting':setting,'namespace':namespace,
                    'eligible_proteins':counts['native_ordinary_ne'],
                    'IA_eligible_proteins':counts['native_IA_ne'],
                    'raw_released_target_IDs':original['raw_proteins_by_aspect'][aspect_codes[namespace]],
                    'raw_released_annotation_rows':original['raw_rows_by_aspect'][aspect_codes[namespace]],
                    'author_recognized_target_IDs':counts['author_recognized_target_IDs'],
                    'post_known_TOI_reference_pairs':counts['post_known_TOI_reference_pairs']})
    assert len(denoms)==12
    indexed={(r['frame'],r['setting'],r['namespace']):r for r in denoms}
    for row in rows:
        d=indexed[(row['frame'],row['setting'],row['namespace'])]
        row['eligible_proteins']=d['eligible_proteins'];row['IA_eligible_proteins']=d['IA_eligible_proteins']
        assert row['status']in{'scored','pending','no_native_curve','nonfinite_native_curve'}
        if row['status']=='scored':
            assert row['native_curve_rows']>0
            for k in['micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax']:
                assert 0<=row[k]<=1.000000000001
            fixed=row.get('fixed_0_5')
            if fixed:assert fixed['threshold']==.5
    pins={str(summary.resolve()):sha(summary),str(denominators.resolve()):sha(denominators)}
    paired=[];ci_reports=[]
    for path in map(Path,confidence_reports):
        report=json.loads(path.read_text())
        asserted=report['content_sha256']
        assert hashlib.sha256(canonical({k:v for k,v in report.items()if k!='content_sha256'})).hexdigest()==asserted
        assert report['draws']==2000 and report['seed']==20261113
        assert report['numpy']=='1.26.4'and report['shared_protein_samples_across_all_arms']is True
        contexts={833:('primary','partial'),2826:('reserved','partial'),
                  53:('primary','partial_publishedaftert0'),
                  129:('reserved','partial_publishedaftert0')}
        assert report['raw_proteins']in contexts
        frame,setting=contexts[report['raw_proteins']]
        pins[str(path.resolve())]=sha(path)
        ci_reports.append({'frame':frame,'setting':setting,'file':str(path.resolve()),'file_sha256':sha(path),
            'content_sha256':report['content_sha256'],'raw_proteins':report['raw_proteins'],
            'draws':report['draws'],'seed':report['seed'],'scores':report['scores']})
        for comparison in report['comparisons']:
            paired.append({'frame':frame,'setting':setting,'namespace':'biological_process',
                'reference_proteins':report['raw_proteins'],'source_report_sha256':sha(path),
                **comparison})
    context_files=['evaluation_primary_freeze_v1.json','evaluation_reserved_freeze_v1.json',
        'released_primary_v1/report.json','released_reserved_v1/report.json',
        'contrast_families_preoutcome.json','runtime_standardization_addendum.json',
        'annotation_semantics_addendum_v1.json','TDL_strata_preoutcome_v2.json',
        'fixed_operating_point_context_tradeoff_v1.json',
        'final_source_bindings_observation_v1.json','native_coverage_source_audit_v1.json',
        'stratified_aggregates_v1.json','strata_full_population_agreement_v1.json',
        'method_interpretation_notes_v1.json',
        'namespace_execution_v2/same_runtime_real_curve_equivalence.json',
        'namespace_execution_v2/native_namespace_equivalence.json']
    lineage={}
    for name in context_files:
        path=base/name;assert path.is_file(),name
        value=json.loads(path.read_text());pins[str(path.resolve())]=sha(path)
        lineage[name]={'file_sha256':sha(path),'content_sha256':value.get('content_sha256'),
            'format':value.get('format')}
    report={
        'format':'biograph-steward.cafa5-scientific-aggregate-projection.v1',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'status':'sealed_aggregate_snapshot_all_declared_slots',
        'scientific_task':'Retrospective CAFA5 temporal recovery of newly curated protein GO annotations from historical human Pharos/STRING context.',
        'scope':{'primary_exact_accessions':1294,'reserved_exact_accessions':4806,
            'edge_scope':'Qualified undirected weighted human STRING association projection represented by Pharos; not every predicate in the entire Pharos database.',
            'original_graph_nodes':3172,'original_graph_edges':87688,
            'full_graph_nodes':20412,'full_graph_edges':986091,
            'deployed_strict_alias_graph_nodes':20412,'deployed_strict_alias_graph_edges':985863,
            'whole_graph_biological_truth_or_clinical_utility_claimed':False,
            'no_raw_reference_or_prediction_rows_included':True},
        'roles':{
            'original_primary':{'candidate':'fastsinksourceplus','comparators':['localplus','cohort_frequency','official_naive','official_blast'],
                'frame':'primary','setting':'partial','namespace':'biological_process','metric':'micro_Fmax',
                'conclusion':'The original propagation candidate did not improve over the same-source Local comparator.'},
            'strong_resource_controls':['official_nonexperimental','official_prott5_cosine3'],
            'published_method_secondary':{'candidate':'genemaniaplus','comparator':'localplus',
                'interpretation':'Predeclared same-graph published-method comparison; retain its positive micro-Fmax result alongside the negative original FSS primary and mixed macro/fixed-threshold readouts.'},
            'context_secondary':{'candidate':'global_full_allseeds_local','comparator':'localplus',
                'interpretation':'Secondary same-method historical source-coverage comparison; no replacement of the negative original primary.'},
            'deployed_source_profile':'strict_alias_localplus',
            'retained_negative_controls':'Every declared pruning, sequence-fusion, propagation and resource-control outcome remains in rows.',
            'transfer':'Reserved target accessions were separately frozen before their future-reference decode; same-study transductive transfer, not an independent study or inductive unseen-gene experiment.'},
        'expected_outcome_slots':240,'status_counts':dict(Counter(r['status']for r in rows)),
        'rows':rows,'denominators':denoms,'paired_comparisons':paired,'uncertainty_reports':ci_reports,
        'runtime':{'python':'3.10.12','numpy':'1.26.4','scipy':'1.13.1','pandas':'2.2.3',
            'point_and_contribution_and_bootstrap_runtime_shared':True,
            'macOS_NumPy2_3_runs':'Preserved numerical-runtime sensitivities, excluded from reported outcomes and bootstrap.'},
        'evaluation_contract':{'official_evaluator_commit':'e386b085e204ccfbd75a4f52c1a8b25987d8b465',
            'native_ontology_parent_relations':['is_a','part_of'],'score_propagation':'fill,max',
            'normalization':'cafa','orphans':False,'threshold_grid':'unchanged native np.arange(.001,1,.001)',
            'Fmax_cutoffs':'Optimized over the native evaluation grid separately for each arm; not an adopted deployment threshold.',
            'fixed_operating_point':.5,'bootstrap':{'draws':2000,'seed':20261113,'unit':'paired protein',
                'interpretation':'Conditional descriptive paired percentile intervals; not independent study replication or a calibrated scientific-accuracy probability.'}},
        'reference':{'record':'https://zenodo.org/records/22381862','license':'CC-BY-4.0',
            'paper':'https://doi.org/10.64898/2026.04.27.716980',
            'evidence_policy':'Publisher curated benchmark admits experimental-family codes and TAS/IC; released rows do not supply per-row assay evidence or publication identifiers.',
            'negative_policy':'Unannotated functions are unknown biology. Scoring follows the fixed closed benchmark convention, without asserting comprehensive biological negatives.'},
        'caveats':[
            'Results concern annotation recovery, not scientific accuracy of every Pharos/PPI edge or whole-graph biological precision.',
            'Public retrospective labels and prior newer GOA exposure prevent a wholly developer-blind or prospective-2023 claim; all model inputs exclude future annotation values and recipes/predictions were sealed before each permitted future-reference release.',
            'Shared studies, genes, annotations and graph neighbors limit independence of protein bootstrap intervals.',
            'Intervals are descriptive and are not adjusted across all secondary method/metric/setting comparisons. Positive secondary findings do not replace the failed original primary superiority gate.',
            'The practical Local context gain is mixed across readouts: IA macro can decrease, and fixed0.5 F1/recall decrease while precision increases. Model scores are not calibrated probabilities.',
            'The added-context gain combines more historical topology and annotated neighbors; it does not prove that every added edge is correct or that the pruned edges are false.',
            'The full-versus-old Local contrast also includes global mapping requalification that removes 236 ambiguous old-old source pairs. The frozen FSS decomposition separates source, topology and seed changes for FSS, but no induced-Local arm was declared, so Local\'s gain is attributed to the profile bundle rather than one isolated cause.',
            'STRING functional-association support is not a universal direct-binding probability; function transfer does not validate direct physical contact.',
            'The old-to-full context comparison restores existing Pharos/STRING source coverage. It improves this application\'s earlier restricted retrieval; it does not establish a superior graph versus the complete original Pharos source network or newly discovered biological evidence.',
            'Primary and reserved populations are proteins gaining future annotation in this benchmark, not a probability sample of all human proteins or all graph assertions.',
            'Later-publication subsets are substantially smaller after native ontology/known/TOI eligibility; unsupported or pending outcomes are retained explicitly.',
            'Native coverage is the author\'s prediction-count/eligible-reference ratio. In some later-publication rows, prediction counts retain pre-known-exclusion targets while the eligible denominator shrinks, so this saved ratio can exceed 1. It is preserved, not clamped, and must not be described as a bounded biological coverage fraction.',
            'A no-native-curve outcome is not silently replaced by zero, and missing predictions never remove a reference target.',
            'Historical ontology classes can now be obsolete. Current source inspection retains version/context and does not turn historical model hypotheses into accepted GO annotations.',
        ],
        'lineage':lineage,'source_pins':pins,
        'native_aggregate_source_files_sha256':data['source_files_sha256'],
        'all_outcomes_including_negatives_and_unsupported_retained':True,
        'new_model_threshold_or_target_selection_from_this_projection':False,
    }
    report['content_sha256']=hashlib.sha256(canonical(report)).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=False)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--summary',required=True);p.add_argument('--denominators',required=True);p.add_argument('--base',required=True);p.add_argument('--output',required=True);p.add_argument('--confidence-report',action='append',default=[])
    a=p.parse_args();r=seal(a.summary,a.denominators,a.base,a.output,a.confidence_report)
    print(json.dumps({k:r[k]for k in['status','expected_outcome_slots','status_counts','content_sha256']}))

if __name__=='__main__':main()
