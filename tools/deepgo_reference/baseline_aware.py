"""Fixed-budget recommendations excluding the dated annotation baseline.

Only ranking eligibility changes. Native scoring still uses the ORIGINAL
future reference, population and PK/None exclusion policy. The construction
retains every previously selected baseline-absent term, so nondecreasing own-
variant support is a containment property, not evidence of a better model.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .archive import need, sealed
from .overlap import (FRAMES, ASPECTS, METHODS, K, selections, score_lists,
                      parse_file, verify, paired_interval)

FORMAT = 'biograph-steward.baseline-aware.v1'
RUNTIME = {'python':'3.10.12', 'numpy':'1.26.4', 'scipy':'1.13.1', 'pandas':'2.2.3'}
NUMERIC_KEYS = ('ordinary', 'IA_weighted', 'eligible', 'eligible_IA_weighted',
                'returned', 'ancestor_related_pairs')


def matrix_sha(matrix):
    import numpy as np
    return hashlib.sha256(memoryview(np.ascontiguousarray(matrix))).hexdigest()


def before_top3(prediction, gt, original_exclude, ontology, baseline):
    """Reuse native-budget ordering with a label-free union ranking mask."""
    import numpy as np
    need(baseline.matrix.shape == gt.matrix.shape == prediction.matrix.shape,
         'baseline, prediction and native frame shapes differ.')
    blocked = baseline.matrix != 0
    if original_exclude is not None:
        need(original_exclude.matrix.shape == blocked.shape, 'original known-mask shape differs.')
        blocked = np.logical_or(blocked, original_exclude.matrix != 0)
    # selections() reads only gt.matrix.shape, never future reference values.
    return selections(prediction, gt, SimpleNamespace(matrix=blocked), ontology)


def after_top3(original, baseline):
    """Old recommendation with baseline-covered entries removed, leaving holes."""
    need(len(original) == baseline.matrix.shape[0], 'baseline row count differs.')
    return [[term for term in row if baseline.matrix[i, term] == 0]
            for i, row in enumerate(original)]


def selection_guards(original, postfiltered, aware, baseline):
    """All checks are independent of future-reference values."""
    need(len(original) == len(postfiltered) == len(aware) == baseline.matrix.shape[0],
         'selected frame inventory differs.')
    for i, (old, post, new) in enumerate(zip(original, postfiltered, aware)):
        need(post == [term for term in old if baseline.matrix[i, term] == 0],
             'after-selection control is not the exact original filtered list.')
        need(len(new) <= K and len(set(new)) == len(new)
             and set(post) <= set(new), 'original baseline-absent prediction was lost.')
        need(all(baseline.matrix[i, term] == 0 for term in new),
             'baseline-aware choice reuses a baseline-covered term.')
    return {'all_previous_baseline_absent_predictions_retained':True,
        'all_new_choices_disjoint_from_baseline_closure':True,
        'ranking_uses_future_reference_values':False,
        'before_and_after_use_same_model_scores':True,
        'containment_is_not_evidence_of_model_improvement':True}


def opportunity(gt, original_exclude, ontology, baseline, eligible):
    """Describe reference-space headroom; do not redefine eligible N or truth."""
    import numpy as np
    pairs = positive = cap = 0; weighted = 0.
    for i in np.flatnonzero(eligible):
        available = ontology.toi if original_exclude is None else np.setdiff1d(
            ontology.toi, original_exclude.matrix[i].nonzero()[0], assume_unique=True)
        residual = available[np.logical_and(gt.matrix[i, available], baseline.matrix[i, available] == 0)]
        pairs += len(residual); positive += bool(len(residual)); cap += min(K, len(residual))
        weighted += float(ontology.ia[residual].sum())
    n = int(eligible.sum())
    need(n > 1, 'original eligible population is empty/singleton.')
    return {'original_eligible_proteins':n,
        'future_reference_pairs_absent_from_baseline':int(pairs),
        'original_proteins_with_residual_reference_support':int(positive),
        'zero_residual_reference_proteins_retained':n-int(positive),
        'residual_reference_IA':weighted,
        'oracle_supported_cap3':int(cap),
        'oracle_supported_slots_per_original_fixed3_budget':cap/(K*n),
        'oracle_is_reference_aware_not_deployable':True,
        'original_population_and_future_reference_unchanged':True}


def utility(postfiltered, aware, post_counts, aware_counts):
    """Descriptive replenishment/cost; own-variant benefit is not a test."""
    import numpy as np
    need(np.array_equal(post_counts['eligible'], aware_counts['eligible'])
         and np.array_equal(post_counts['eligible_IA_weighted'], aware_counts['eligible_IA_weighted']),
         'own-variant original population differs.')
    mask = aware_counts['eligible']; n = int(mask.sum())
    old = post_counts['ordinary'][mask]; new = aware_counts['ordinary'][mask]
    need((new[:,1] >= old[:,1]).all(), 'contained predictions lost native support.')
    weighted_mask = aware_counts['eligible_IA_weighted']
    old_ia = post_counts['IA_weighted'][weighted_mask]
    new_ia = aware_counts['IA_weighted'][weighted_mask]
    need((new_ia[:,1]+1e-12 >= old_ia[:,1]).all(), 'contained predictions lost native IA support.')
    returned_old = int(post_counts['returned'][mask].sum())
    returned_new = int(aware_counts['returned'][mask].sum())
    added = returned_new-returned_old; added_tp = float((new[:,1]-old[:,1]).sum())
    added_unmatched = float((new[:,2]-old[:,2]).sum())
    need(added >= 0 and added_tp >= 0 and added_unmatched >= 0
         and added_tp+added_unmatched == added, 'replenishment partition identity differs.')
    return {'old_after_filter_returned_candidates':returned_old,
        'new_before_filter_returned_candidates':returned_new,
        'old_after_filter_unused_slots':K*n-returned_old,
        'new_before_filter_unused_slots':K*n-returned_new,
        'replenished_slots':added,
        'proteins_with_replenishment':int(sum(len(aware[i]) > len(postfiltered[i]) for i in np.flatnonzero(mask))),
        'old_baseline_absent_supported_pairs':float(old[:,1].sum()),
        'new_baseline_absent_supported_pairs':float(new[:,1].sum()),
        'old_baseline_absent_reference_unmatched_pairs':float(old[:,2].sum()),
        'new_baseline_absent_reference_unmatched_pairs':float(new[:,2].sum()),
        'added_curator_supported_pairs':added_tp,
        'added_reference_unmatched_pairs':added_unmatched,
        'old_baseline_absent_supported_IA':float(old_ia[:,1].sum()),
        'new_baseline_absent_supported_IA':float(new_ia[:,1].sum()),
        'added_curator_supported_IA':float((new_ia[:,1]-old_ia[:,1]).sum()),
        'marginal_added_curator_support_fraction':added_tp/added if added else None,
        'old_supported_slots_per_original_fixed3_budget':float(old[:,1].sum()/(K*n)),
        'new_supported_slots_per_original_fixed3_budget':float(new[:,1].sum()/(K*n)),
        'ordinary_support_non_decrease_is_containment_property':True,
        'own_variant_uncertainty_or_model_superiority_claimed':False}


def read_sealed(path, expected):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and sha(path) == expected, 'sealed parent FILE differs.')
    value = json.loads(path.read_text())
    need(value['content_sha256'] == digest({k:v for k,v in value.items() if k != 'content_sha256'}),
         'sealed parent content differs.')
    return value


def run(config, expected, output):
    need(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')),
         'bounded one-thread environment required before numeric imports.')
    import numpy as np
    import scipy, pandas, platform
    from cafaeval.parser import obo_parser, update_toi, gt_parser, gt_exclude_parser
    cfg = read_sealed(config, expected)
    need(cfg['format'] == FORMAT+'.freeze' and cfg['k'] == K and cfg['development_only'] is True
         and cfg['previous_reference_and_metric_exposure'] is True
         and cfg['focus_namespace'] == 'molecular_function' and set(cfg['frames']) == set(FRAMES),
         'frozen task, budget or exposure differs.')
    runtime = {'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'pandas':pandas.__version__}
    need(runtime == cfg['runtime'] == RUNTIME, 'pinned numeric runtime differs.')
    verify(cfg['input_files_sha256'])
    need(cfg['implementation_file'] == str(Path(__file__).resolve())
         and cfg['input_files_sha256'][cfg['implementation_file']] == sha(__file__), 'executed implementation differs.')
    import cafaeval, cafaeval.parser, cafaeval.evaluation, cafaeval.graph, cafaeval.tests
    for module in (cafaeval, cafaeval.parser, cafaeval.evaluation, cafaeval.graph, cafaeval.tests):
        name = str(Path(module.__file__).resolve())
        need(cfg['input_files_sha256'].get(name) == sha(name), 'actual native module differs.')
    parents = cfg['parent_overlap_report']; parent_freeze = cfg['parent_overlap_freeze']
    need(cfg['input_files_sha256'].get(parents['file']) == parents['sha256']
         and cfg['input_files_sha256'].get(parent_freeze['file']) == parent_freeze['sha256'],
         'parent contracts are not input-bound.')
    previous = read_sealed(parents['file'], parents['sha256'])
    previous_policy = read_sealed(parent_freeze['file'], parent_freeze['sha256'])
    need(previous['format'] == 'biograph-steward.method-overlap.v1.results'
         and previous_policy['format'] == 'biograph-steward.method-overlap.v1.freeze'
         and previous['source_freeze_file_sha256'] == parent_freeze['sha256']
         and previous['all12_declared_strata_preserved'] is True
         and len(previous['parent_points']) == 24
         and cfg['frames'] == previous_policy['frames']
         and all(cfg[key] == previous_policy[key] for key in ('ontology','ia','toi','runtime','k')),
         'parent/source frame, ontology or scoring contract differs.')
    need(all(cfg['input_files_sha256'].get(p) == h for p,h in previous_policy['input_files_sha256'].items()),
         'an earlier data/code pin was omitted or changed.')
    root = Path(parents['file']).parent
    out = new_output(output, config); temporary = out/'temporary'; temporary.mkdir()
    write_json(out/'STARTED.json', sealed({'created_at':utcnow(),'source_freeze_file_sha256':expected,
        'runtime':runtime,'new_model_or_reference_calls':0,'original_scoring_populations_and_truth_retained':True}))
    rows = []; opportunities = []; contrasts = []; numeric_files = {}
    try:
        ontologies = update_toi(obo_parser(cfg['ontology'], ('is_a','part_of'), cfg['ia'], False), cfg['toi'])
        for frame in FRAMES:
            spec = cfg['frames'][frame]
            need(set(spec['methods']) == set(METHODS) and set(spec['denominators']) == set(ASPECTS)
                 and spec['setting'] == ('partial' if frame in ('primary','reserved') else frame)
                 and ((spec['known'] is None) == (frame in ('no_knowledge','limited'))), 'native task semantics differ.')
            gt = gt_parser(spec['truth'], ontologies)
            known = gt_exclude_parser(spec['known'], gt, ontologies) if spec['known'] is not None else None
            before_gt = {ns:matrix_sha(gt[ns].matrix) for ns in ASPECTS}
            baseline = parse_file(spec['baseline'], ontologies, gt, 'fill', temporary)
            for ns in ASPECTS: need(ns in baseline, 'baseline namespace missing; do not invent coverage.')
            all_aware = {}
            for method in METHODS:
                prediction = parse_file(spec['methods'][method], ontologies, gt, 'fill', temporary)
                for ns in ASPECTS:
                    need(ns in prediction, 'prediction namespace missing; preserve failure.')
                    exclude = None if known is None else known[ns]
                    oldfile = root/frame/ns/'private_selections.json'
                    oldcounts = root/frame/ns/'private_counts.npz'
                    for path in (oldfile,oldcounts):
                        need(previous['numeric_artifact_files_sha256'].get(str(path)) == sha(path)
                             and path.is_file() and not path.is_symlink(), 'prior selected/numeric artifact differs.')
                    saved = json.loads(oldfile.read_text())
                    original = selections(prediction[ns], gt[ns], exclude, ontologies[ns])
                    order = [p for p,i in sorted(gt[ns].ids.items(), key=lambda item:item[1])]
                    need(original == saved[method] and digest(order) == saved['native_order_sha256'],
                         'original selections or native identity order failed exact reconstruction.')
                    post = after_top3(original, baseline[ns])
                    aware = before_top3(prediction[ns], gt[ns], exclude, ontologies[ns], baseline[ns])
                    guards = selection_guards(original,post,aware,baseline[ns])
                    post_summary, post_numeric = score_lists(post,gt[ns],exclude,ontologies[ns])
                    aware_summary, aware_numeric = score_lists(aware,gt[ns],exclude,ontologies[ns])
                    den = spec['denominators'][ns]
                    with np.load(oldcounts,allow_pickle=False) as old:
                        original_numeric = {key:old[method+'__'+key] for key in NUMERIC_KEYS}
                        need(np.array_equal(aware_numeric['eligible'],original_numeric['eligible'])
                             and np.array_equal(aware_numeric['eligible_IA_weighted'],original_numeric['eligible_IA_weighted']),
                             'original eligible population changed.')
                        need(np.allclose(post_numeric['ordinary'][:,1]/K,old[method+'__baseline_absent_yield'],
                                         rtol=1e-12,atol=1e-12), 'previous baseline-absent support differs.')
                    need(aware_summary['ordinary']['eligible_proteins'] == den['eligible_proteins']
                         and aware_summary['IA_weighted']['eligible_proteins'] == den['IA_eligible_proteins'],
                         'declared original denominator differs.')
                    original_point = next(row for row in previous['parent_points'] if
                        (row['frame'],row['namespace'],row['method']) == (frame,ns,method))
                    need(original_point['native_reference_protein_order_sha256'] == digest(order), 'parent point order differs.')
                    own_utility = utility(post,aware,post_numeric,aware_numeric)
                    for value in (post_summary,aware_summary): value['native_reference_protein_order_sha256'] = digest(order)
                    rows.append({'frame':frame,'setting':spec['setting'],'namespace':ns,'method':method,'k':K,
                        'eligible_proteins':den['eligible_proteins'],'IA_eligible_proteins':den['IA_eligible_proteins'],
                        'native_reference_protein_order_sha256':digest(order),
                        'original_top3':{key:original_point[key] for key in
                            ('ordinary','IA_weighted','native_batch_point_agreement','native_reference_protein_order_sha256')},
                        'filtered_after_top3':post_summary,'aware_before_top3':aware_summary,
                        'construction_guards':guards,'utility':own_utility,
                        'scoring_future_reference_unchanged_sha256':before_gt[ns]})
                    folder = out/frame/ns/method; folder.mkdir(parents=True)
                    file = folder/'private_selections.json'; write_json(file,{'opaque_row_ids':saved['opaque_row_ids'],
                        'native_order_sha256':digest(order),'original':original,
                        'filtered_after_top3':post,'aware_before_top3':aware})
                    numeric_files[str(file)] = sha(file)
                    file = folder/'private_counts.npz';np.savez_compressed(file,
                        **{'original__'+k:v for k,v in original_numeric.items()},
                        **{'postfilter__'+k:v for k,v in post_numeric.items()},
                        **{'aware__'+k:v for k,v in aware_numeric.items()})
                    numeric_files[str(file)] = sha(file)
                    all_aware[method,ns] = aware_numeric
                    if method == METHODS[0]:
                        opportunities.append({'frame':frame,'setting':spec['setting'],'namespace':ns,
                            **opportunity(gt[ns],exclude,ontologies[ns],baseline[ns],aware_numeric['eligible'])})
                del prediction
            for ns in ASPECTS:
                candidate, comparator = (all_aware[m,ns] for m in METHODS)
                need(np.array_equal(candidate['eligible'],comparator['eligible'])
                     and np.array_equal(candidate['eligible_IA_weighted'],comparator['eligible_IA_weighted']),
                     'genuine method comparison original masks differ.')
                mask = candidate['eligible']
                result,distribution = paired_interval(candidate['ordinary'][mask,1]/K,comparator['ordinary'][mask,1]/K)
                file = out/frame/ns/'paired_aware_deepgose_minus_aware_localplus.npy'
                np.save(file,distribution,allow_pickle=False);numeric_files[str(file)] = sha(file)
                contrasts.append({'frame':frame,'setting':spec['setting'],'namespace':ns,
                    'candidate':'baseline_aware_deepgose','comparator':'baseline_aware_strict_alias_localplus',
                    'metric':'baseline_absent_curator_supported_slots_per_original_fixed3_budget',
                    'eligible_proteins':int(mask.sum()),'role':'designated_focus' if ns=='molecular_function' else 'secondary',
                    'not_a_guaranteed_own_variant_containment_comparison':True,**result})
                need(matrix_sha(gt[ns].matrix) == before_gt[ns], 'future ground-truth matrix was modified.')
            del gt,known,baseline,all_aware
        need(len(rows)==24 and len(opportunities)==12 and len(contrasts)==12, 'all method/task/aspect outcomes required.')
        verify(cfg['input_files_sha256'])
        report = sealed({'format':FORMAT+'.results','created_at':utcnow(),'source_freeze_file_sha256':expected,
            'parent_overlap_report_file_sha256':parents['sha256'],'parent_overlap_freeze_file_sha256':parent_freeze['sha256'],
            'runtime':runtime,'k':K,'rows':rows,'opportunity':opportunities,'comparisons':contrasts,
            'original_selected_identities_exactly_reconstructed':True,
            'all_original_populations_and_future_groundtruth_retained':True,
            'all24_method_strata_preserved':True,'all12_opportunity_and_method_comparison_strata_preserved':True,
            'own_variant_utility_is_descriptive_containment_not_model_improvement':True,
            'development_only':True,'new_model_inference':False,'new_reference_release':False,
            'app_default_or_graph_changed':False,'automatic_adoption':False,
            'uncertainty':{'implementation':'scipy.stats.bootstrap','version':scipy.__version__,'paired':True,
                'draws':2000,'seed':20261113,'method':'percentile','confidence_level':.95,'batch':100,'multiplicity_adjusted':False},
            'source_files_sha256':cfg['input_files_sha256'],'numeric_artifact_files_sha256':numeric_files,
            'limitations':cfg['limitations']})
        write_json(out/'report.json',report);write_json(out/'DONE.json',sealed({'status':'complete',
            'report_file_sha256':sha(out/'report.json'),'report_content_sha256':report['content_sha256']}))
        return report
    except BaseException as error:
        write_json(out/'FAILURE.json',sealed({'status':'failed_preserved','error_type':type(error).__name__,
            'app_or_original_outputs_changed':False}));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('config','expected','output'):parser.add_argument('--'+key,required=True)
    value=run(**vars(parser.parse_args()));print(json.dumps({'status':'complete','content_sha256':value['content_sha256']}))
