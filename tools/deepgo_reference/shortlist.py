"""Fixed-budget curator-supported shortlist comparison on sealed forecasts.

Task-specific top3 projection reuses the app's deterministic ordering. Native
CAFA parsers/confusion counts and SciPy paired bootstrap are unchanged. This is
not CAFA Fmax, a fresh holdout, biological truth, or an adoption rule.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .archive import need, sealed

K = 3
ASPECTS = ('biological_process', 'molecular_function', 'cellular_component')
METHODS = ('deepgose', 'strict_alias_localplus')


def select_top3(scores, allowed, term_ids):
    """Rank only source-qualified scores: no future truth enters this function."""
    import numpy as np
    scores = np.asarray(scores); allowed = np.asarray(allowed, dtype=int)
    need(np.isfinite(scores).all(), 'nonfinite ranking score.')
    candidates = allowed[scores[allowed] > 0]
    order = np.lexsort((np.asarray(term_ids)[candidates], -scores[candidates]))
    return candidates[order[:K]]


def ancestor_pairs(chosen, graph, cache):
    """Descriptive reachability only; never filter/reorder the shortlist."""
    from scipy.sparse.csgraph import breadth_first_order
    for term in chosen:
        term = int(term)
        if term not in cache:
            cache[term] = set(map(int, breadth_first_order(graph, term, directed=True,
                                                          return_predecessors=False)))
    return sum(int(int(b) in cache[int(a)] or int(a) in cache[int(b)])
               for i, a in enumerate(chosen) for b in chosen[i+1:])


def paired_interval(candidate, comparator):
    import numpy as np
    from scipy.stats import bootstrap
    need(len(candidate) == len(comparator) and len(candidate) > 1, 'paired eligible frame required.')
    def difference(a, b, axis=-1): return np.mean(a-b, axis=axis)
    result = bootstrap((candidate, comparator), difference, paired=True, vectorized=True,
        n_resamples=2000, batch=100, confidence_level=.95, method='percentile',
        random_state=np.random.default_rng(20261113))
    return {'point_difference': float(np.mean(candidate-comparator)),
        'paired_95_percentile_interval': [float(result.confidence_interval.low), float(result.confidence_interval.high)],
        'bootstrap_mean_difference': float(result.bootstrap_distribution.mean()),
        'fraction_draws_above_zero': float((result.bootstrap_distribution > 0).mean())}, result.bootstrap_distribution


def summarize(counts, eligible):
    """Only normalize the unchanged native one-threshold confusion columns."""
    import numpy as np
    from cafaeval.evaluation import compute_f
    selected = counts[eligible]; n = len(selected)
    need(n > 1, 'native eligible frame unexpectedly empty or singleton.')
    total = selected.sum(axis=0); tp, fp, fn = map(float, total[1:4])
    precision = tp/(tp+fp) if tp+fp else 0.; recall = tp/(tp+fn) if tp+fn else 0.
    return {'eligible_proteins': n, 'TP': tp, 'reference_unmatched_predictions': fp,
        'unrecovered_reference_annotations': fn, 'PPV_among_returned': precision, 'micro_recall': recall,
        'micro_F1': float(compute_f(np.asarray(precision), np.asarray(recall))),
        'macro_PPV_including_abstentions': float(selected[:,4].mean()),
        'macro_recall_including_abstentions': float(selected[:,5].mean()),
        'prediction_coverage': float(selected[:,0].sum()/n)}


def score_namespace(prediction, gt, exclude, ontology):
    import numpy as np
    from scipy.sparse import csr_matrix
    from cafaeval.evaluation import compute_confusion_matrix_exclude
    n, terms = gt.matrix.shape
    term_ids = [None]*terms
    for term, meta in ontology.terms_dict.items(): term_ids[meta['index']] = term
    ordinary = np.zeros((n,6)); weighted = np.zeros_like(ordinary)
    eligible = np.zeros(n,dtype=bool); eligible_w = np.zeros(n,dtype=bool)
    returned = np.zeros(n,dtype=int); related = np.zeros(n,dtype=int); information = np.zeros(n)
    selected_terms = []; graph = csr_matrix(ontology.dag); ancestors = {}
    selected_matrix = np.zeros_like(prediction.matrix)
    for i in range(n):
        known = exclude.matrix[i,:].nonzero()[0]
        allowed = np.setdiff1d(ontology.toi, known, assume_unique=True)
        chosen = select_top3(prediction.matrix[i], allowed, term_ids)
        returned[i] = len(chosen); related[i] = ancestor_pairs(chosen, graph, ancestors)
        information[i] = float(ontology.ia[chosen].sum())
        selected_terms.append(chosen.tolist())
        selected_matrix[i,chosen] = 1.
        binary = selected_matrix[i:i+1,:]
        for toi, dest, mask, ia in ((ontology.toi, ordinary, eligible, None),
                                   (ontology.toi_ia, weighted, eligible_w, ontology.ia)):
            available = np.setdiff1d(toi, known, assume_unique=True)
            truth = gt.matrix[i,available]
            n_gt = np.asarray([truth.sum() if ia is None else (truth*ia[available]).sum()])
            mask[i] = n_gt[0] > 0
            # The evaluated population is explicitly the earlier native
            # post-known eligible set. No prediction or case changes that set.
            if mask[i]:
                dest[i] = compute_confusion_matrix_exclude(np.asarray([.5]), [truth], binary,
                    [available], n_gt, ia)[0]
    # One complete eligible-frame native call checks all six confusion
    # columns against the per-protein calls. This point is binary membership,
    # not a score threshold chosen from data. The post-known eligible frame is
    # explicit for this fixed-budget endpoint, including its abstentions.
    batch_checks = {}
    columns = ('n','tp','fp','fn','pr','rc')
    for label, counts, mask, toi, ia in (
            ('ordinary',ordinary,eligible,ontology.toi,None),
            ('IA_weighted',weighted,eligible_w,ontology.toi_ia,ontology.ia)):
        indices = np.flatnonzero(mask)
        available = [np.setdiff1d(toi,exclude.matrix[i,:].nonzero()[0],assume_unique=True) for i in indices]
        truths = [gt.matrix[i,sel] for i,sel in zip(indices,available)]
        n_gt = np.asarray([t.sum() if ia is None else (t*ia[sel]).sum() for t,sel in zip(truths,available)])
        batch = compute_confusion_matrix_exclude(np.asarray([.5]),truths,
            selected_matrix[indices,:],available,n_gt,ia)[0]
        separate = counts[mask].sum(axis=0)
        need(np.isfinite(batch).all() and np.isfinite(separate).all()
             and np.allclose(batch,separate,rtol=1e-12,atol=1e-12),
             'native whole-frame and per-protein confusion columns differ.')
        batch_checks[label] = {'passed':True,'eligible_proteins':len(indices),
            'columns':list(columns),'max_absolute_column_difference':float(np.max(np.abs(batch-separate))),
            'per_column_absolute_differences':{c:float(abs(a-b)) for c,a,b in zip(columns,batch,separate)},
            'relative_tolerance':1e-12,'absolute_tolerance':1e-12,
            'same_native_function_same_post_known_eligible_frame':True}
    normal = summarize(ordinary, eligible); weighted_summary = summarize(weighted, eligible_w)
    n_eligible = int(eligible.sum()); emitted = int(returned[eligible].sum())
    normal['curator_supported_slots_per_fixed3_budget'] = float(ordinary[eligible,1].sum()/(K*n_eligible))
    normal['filled_slot_fraction'] = emitted/(K*n_eligible)
    normal['returned_candidates'] = emitted
    normal['unused_budget_slots'] = K*n_eligible-emitted
    normal['shortlists_with_ancestor_related_pair'] = int((related[eligible]>0).sum())
    normal['ancestor_related_pairs'] = int(related[eligible].sum())
    normal['mean_IA_per_returned_term'] = float(information[eligible].sum()/emitted) if emitted else None
    normal['curator_supported_IA_per_fixed3_budget'] = float(weighted[eligible,1].sum()/(K*n_eligible))
    normal['shortlist_is_ancestor_closed'] = False
    return {'ordinary': normal, 'IA_weighted': weighted_summary,
        'native_batch_point_agreement':batch_checks}, {
        'ordinary': ordinary, 'IA_weighted': weighted, 'eligible': eligible, 'eligible_IA_weighted': eligible_w,
        'returned': returned, 'ancestor_related_pairs': related, 'selected_term_indices': selected_terms}


def run(config, expected, output):
    need(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')),
         'bounded one-thread numeric environment required before import.')
    import numpy as np
    import scipy
    import pandas
    import platform
    config = Path(config)
    need(sha(config) == expected, 'shortlist frozen config FILE differs.')
    cfg = json.loads(config.read_text())
    need(cfg.get('format') == 'biograph-steward.deepgo-shortlist.v1.freeze'
         and cfg['content_sha256'] == digest({k:v for k,v in cfg.items() if k!='content_sha256'}), 'config seal differs.')
    need(cfg['k'] == K and cfg['previous_reference_and_metric_exposure'] is True
         and cfg['no_new_shortlist_endpoint_values_seen'] is True
         and cfg['focus_namespace'] == 'molecular_function' and cfg['propagation'] == 'fill'
         and set(cfg['frames']) == {'primary','reserved'}, 'fixed budget/development scope differs.')
    need(cfg['input_files_sha256'] and cfg['implementation_file'] == str(Path(__file__).resolve())
         and cfg['input_files_sha256'].get(cfg['implementation_file']) == sha(__file__), 'executed implementation differs.')
    runtime = {'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'pandas':pandas.__version__}
    need(runtime == cfg['runtime'] == {'python':'3.10.12','numpy':'1.26.4','scipy':'1.13.1','pandas':'2.2.3'}, 'numeric runtime differs.')
    for p,h in cfg['input_files_sha256'].items():
        need(Path(p).is_file() and not Path(p).is_symlink() and sha(p) == h, 'ordinary source/code/reference pin differs: '+p)
    import cafaeval.parser, cafaeval.evaluation, cafaeval.graph
    for module in (cafaeval.parser,cafaeval.evaluation,cafaeval.graph):
        path = str(Path(module.__file__).resolve())
        need(path in cfg['input_files_sha256'] and sha(path)==cfg['input_files_sha256'][path],
             'actual imported native evaluator source differs.')
    from cafaeval.parser import obo_parser, update_toi, gt_parser, gt_exclude_parser, pred_parser
    for spec in cfg['frames'].values():
        need(set(spec['methods']) == set(METHODS) and set(spec['denominators']) == set(ASPECTS), 'method/namespace inventory differs.')
        for path in (spec['truth'],spec['known'],cfg['ontology'],cfg['ia'],cfg['toi']):
            need(path in cfg['input_files_sha256'], 'declared source lacks a FILE pin.')
        for source in spec['methods'].values():
            need(cfg['input_files_sha256'].get(source['file']) == source['sha256'], 'forecast source pin differs.')
    out = new_output(output, config)
    write_json(out/'STARTED.json', sealed({'created_at':utcnow(),'freeze_file_sha256':expected,
        'runtime':runtime,'development_only':True,'new_model_calls':0,'new_reference_release':False}))
    try:
        ontologies = update_toi(obo_parser(cfg['ontology'], ('is_a','part_of'), cfg['ia'], False), cfg['toi'])
        rows = []; comparisons = []; pins = {}; eligibility = {}
        for frame,spec in cfg['frames'].items():
            gt = gt_parser(spec['truth'], ontologies); known = gt_exclude_parser(spec['known'], gt, ontologies)
            all_arrays = {}
            for method in METHODS:
                prediction_source = spec['methods'][method]
                with tempfile.TemporaryDirectory(prefix='shortlist-'+frame+'-'+method+'-', dir=str(out)) as tmp:
                    plain = Path(tmp)/'predictions.tsv'
                    with gzip.open(prediction_source['file'],'rb') as src, plain.open('xb') as dst: shutil.copyfileobj(src,dst)
                    prediction = pred_parser(str(plain), ontologies, gt, 'fill', None)
                    for namespace in ASPECTS:
                        need(namespace in prediction, 'missing native prediction namespace; retain failure, do not drop cases.')
                        summary, arrays = score_namespace(prediction[namespace], gt[namespace], known[namespace], ontologies[namespace])
                        protein_order = [p for p,i in sorted(gt[namespace].ids.items(),key=lambda item:item[1])]
                        summary['native_reference_protein_order_sha256'] = digest(protein_order)
                        expected_den = spec['denominators'][namespace]
                        need(summary['ordinary']['eligible_proteins'] == expected_den['eligible_proteins']
                             and summary['IA_weighted']['eligible_proteins'] == expected_den['IA_eligible_proteins'], 'prior native reference eligibility changed.')
                        rows.append({'frame':frame,'namespace':namespace,'method':method,'k':K,**summary})
                        all_arrays[method,namespace] = arrays
                        folder = out/frame/namespace/method; folder.mkdir(parents=True)
                        np.savez_compressed(folder/'private_counts.npz', **{k:v for k,v in arrays.items() if k!='selected_term_indices'})
                        # No selected protein/GO identity list is needed in the
                        # public result; only native-order private numeric rows.
                        pins[str(folder/'private_counts.npz')] = sha(folder/'private_counts.npz')
                    del prediction
            for namespace in ASPECTS:
                a, b = (all_arrays[m,namespace] for m in METHODS)
                need(np.array_equal(a['eligible'],b['eligible']), 'paired method eligibility differs.')
                mask = a['eligible']; av = a['ordinary'][mask,1]/K; bv = b['ordinary'][mask,1]/K
                result, distribution = paired_interval(av,bv)
                path = out/frame/namespace/'paired_fixed3_distribution.npy'; np.save(path,distribution,allow_pickle=False);pins[str(path)] = sha(path)
                comparisons.append({'frame':frame,'namespace':namespace,'candidate':'deepgose',
                    'comparator':'strict_alias_localplus','metric':'curator_supported_slots_per_fixed3_budget',
                    'role':'designated_focus' if namespace=='molecular_function' else 'secondary',
                    'eligible_proteins':int(mask.sum()),**result})
            del all_arrays,gt,known
        need(len(rows)==12 and len(comparisons)==6, 'complete two-profile six-cell inventory required.')
        for p,h in cfg['input_files_sha256'].items(): need(sha(p)==h,'input changed during shortlist evaluation.')
        report = sealed({'format':'biograph-steward.deepgo-shortlist.v1.results','created_at':utcnow(),
            'freeze_file_sha256':expected,'runtime':runtime,'scope':'DEVELOPMENT on previously exposed CAFA5 PK annotations; new fixed-budget endpoint, not fresh confirmation.',
            'k':K,'rows':rows,'paired_comparisons':comparisons,'source_files_sha256':cfg['input_files_sha256'],
            'numeric_artifact_files_sha256':pins,'uncertainty':{'implementation':'scipy.stats.bootstrap','version':scipy.__version__,
                'paired':True,'draws':2000,'seed':20261113,'method':'percentile','confidence_level':.95,'batch':100,
                'multiplicity_adjusted':False},'primary_BPO_adoption_rule_changed':False,'app_default_or_consumer_changed':False,
            'raw_reference_or_forecast_rows_included':False,'limitations':cfg['limitations']})
        write_json(out/'report.json',report);write_json(out/'DONE.json',sealed({'status':'complete',
            'report_file_sha256':sha(out/'report.json'),'report_content_sha256':report['content_sha256']}))
        return report
    except BaseException as e:
        write_json(out/'FAILURE.json',sealed({'status':'failed_preserved','error_type':type(e).__name__,
            'primary_outputs_changed':False}));raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('config','expected','output'):p.add_argument('--'+key,required=True)
    d = run(**vars(p.parse_args())); print(json.dumps({'status':'complete','content_sha256':d['content_sha256']}))
