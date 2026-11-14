"""Source-frozen top-three complementarity and one fixed rank-fusion baseline.

Native CAFA identity/closure/count APIs and the earlier shortlist ordering and
paired bootstrap are reused. Library mode=None is a qualified no-propagation
adapter for the baseline footprint, not an advertised CAFA CLI option. No
future label enters ranking, fusion or the label-free execution gate.
"""
import argparse
from contextlib import redirect_stdout
from fractions import Fraction
import gzip
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .archive import need, sealed
from .shortlist import ASPECTS, K, METHODS, select_top3, ancestor_pairs, summarize, paired_interval

FORMAT = 'biograph-steward.method-overlap.v1'
FRAMES = ('primary', 'reserved', 'no_knowledge', 'limited')
OFFSET = 60
FUSION = 'rrf3'


def rrf3(left, right, term_ids):
    """Equal, truncated-list RRF; exact rational ties, then canonical GO ID."""
    weights = {}
    for values in (left, right):
        need(len(values) <= K and len(set(map(int, values))) == len(values), 'invalid ranked shortlist.')
        for rank, term in enumerate(values, 1):
            term = int(term)
            need(0 <= term < len(term_ids), 'ranked term is outside the native vocabulary.')
            weights[term] = weights.get(term, Fraction()) + Fraction(1, OFFSET + rank)
    return sorted(weights, key=lambda term: (-weights[term], term_ids[term]))[:K]


def names_for(ontology):
    names = [None] * len(ontology.terms_dict)
    for name, meta in ontology.terms_dict.items(): names[meta['index']] = name
    need(all(isinstance(name, str) for name in names), 'native ordered vocabulary is incomplete.')
    return names


def selections(prediction, gt, exclude, ontology):
    import numpy as np
    names = names_for(ontology)
    return [select_top3(prediction.matrix[i],
            ontology.toi if exclude is None else np.setdiff1d(
                ontology.toi, exclude.matrix[i].nonzero()[0], assume_unique=True), names).tolist()
            for i in range(gt.matrix.shape[0])]


def score_lists(choices, gt, exclude, ontology):
    """Score fixed membership using the actual native None/PK count branches."""
    import numpy as np
    from scipy.sparse import csr_matrix
    from cafaeval.evaluation import compute_confusion_matrix, compute_confusion_matrix_exclude
    n, terms = gt.matrix.shape
    need(len(choices) == n, 'native row inventory differs.')
    binary = np.zeros((n, terms), dtype=bool)
    returned = np.zeros(n, dtype=int); related = np.zeros(n, dtype=int); information = np.zeros(n)
    counts = {'ordinary': np.zeros((n, 6)), 'IA_weighted': np.zeros((n, 6))}
    masks = {name: np.zeros(n, dtype=bool) for name in counts}
    graph = csr_matrix(ontology.dag); cache = {}
    for i, selected in enumerate(choices):
        allowed = ontology.toi if exclude is None else np.setdiff1d(
            ontology.toi, exclude.matrix[i].nonzero()[0], assume_unique=True)
        need(len(selected) <= K and len(set(selected)) == len(selected)
             and set(selected) <= set(map(int, allowed)), 'unqualified or over-budget selection.')
        binary[i, selected] = True; returned[i] = len(selected)
        related[i] = ancestor_pairs(selected, graph, cache)
        information[i] = float(ontology.ia[selected].sum())
        for label, toi, ia in (('ordinary', ontology.toi, None),
                               ('IA_weighted', ontology.toi_ia, ontology.ia)):
            available = toi if exclude is None else np.setdiff1d(
                toi, exclude.matrix[i].nonzero()[0], assume_unique=True)
            truth = gt.matrix[i, available]
            n_gt = np.asarray([truth.sum() if ia is None else (truth * ia[available]).sum()])
            masks[label][i] = n_gt[0] > 0
            if not masks[label][i]: continue
            if exclude is None:
                counts[label][i] = compute_confusion_matrix(np.asarray([.5]), truth[None, :],
                    binary[i:i+1, available], available, n_gt, ia)[0]
            else:
                with redirect_stdout(io.StringIO()):
                    counts[label][i] = compute_confusion_matrix_exclude(np.asarray([.5]), [truth],
                        binary[i:i+1, :], [available], n_gt, ia)[0]
    checks = {}
    for label, toi, ia in (('ordinary', ontology.toi, None),
                           ('IA_weighted', ontology.toi_ia, ontology.ia)):
        mask = masks[label]; ids = np.flatnonzero(mask)
        need(len(ids) > 1, 'unexpected singleton/empty eligible population.')
        if exclude is None:
            truth = gt.matrix[ids, :][:, toi]
            n_gt = truth.sum(1) if ia is None else (truth * ia[toi]).sum(1)
            batch = compute_confusion_matrix(np.asarray([.5]), truth,
                binary[ids, :][:, toi], toi, n_gt, ia)[0]
        else:
            available = [np.setdiff1d(toi, exclude.matrix[i].nonzero()[0], assume_unique=True) for i in ids]
            truth = [gt.matrix[i, sel] for i, sel in zip(ids, available)]
            n_gt = np.asarray([t.sum() if ia is None else (t * ia[sel]).sum() for t, sel in zip(truth, available)])
            with redirect_stdout(io.StringIO()):
                batch = compute_confusion_matrix_exclude(np.asarray([.5]), truth, binary[ids, :], available, n_gt, ia)[0]
        separate = counts[label][mask].sum(0)
        need(np.isfinite(batch).all() and np.allclose(batch, separate, rtol=1e-12, atol=1e-12),
             'native full-frame/per-protein count mismatch.')
        checks[label] = {'passed': True, 'eligible_proteins': int(mask.sum()),
            'columns': ['n','tp','fp','fn','pr','rc'], 'same_native_function_same_eligible_frame':True,
            'known_exclusion': None if exclude is None else 'native_known_t0_closure',
            'relative_tolerance': 1e-12, 'absolute_tolerance': 1e-12,
            'max_absolute_column_difference': float(np.max(np.abs(batch-separate)))}
    ordinary = summarize(counts['ordinary'], masks['ordinary'])
    weighted = summarize(counts['IA_weighted'], masks['IA_weighted'])
    mask = masks['ordinary']; eligible = int(mask.sum()); emitted = int(returned[mask].sum())
    ordinary.update(curator_supported_slots_per_fixed3_budget=float(counts['ordinary'][mask, 1].sum()/(K*eligible)),
        filled_slot_fraction=emitted/(K*eligible), returned_candidates=emitted, unused_budget_slots=K*eligible-emitted,
        shortlists_with_ancestor_related_pair=int((related[mask] > 0).sum()),
        ancestor_related_pairs=int(related[mask].sum()),
        mean_IA_per_returned_term=float(information[mask].sum()/emitted) if emitted else None,
        curator_supported_IA_per_fixed3_budget=float(counts['IA_weighted'][mask, 1].sum()/(K*eligible)),
        shortlist_is_ancestor_closed=False)
    return {'ordinary': ordinary, 'IA_weighted': weighted, 'native_batch_point_agreement': checks}, {
        **counts, 'eligible': masks['ordinary'], 'eligible_IA_weighted': masks['IA_weighted'],
        'returned': returned, 'ancestor_related_pairs': related}


def bucket(selected, truth, literal, closure, ia):
    """Reference unmatched is not biologically false; baseline is not an assay."""
    selected, truth, literal, closure = map(set, (selected, truth, literal, closure))
    need(literal <= closure, 'literal baseline footprint is not contained in its fill closure.')
    result = {'selected_pairs': len(selected), 'curator_supported_pairs': len(selected & truth),
        'reference_unmatched_pairs': len(selected-truth),
        'curator_supported_IA': float(sum(ia[t] for t in selected & truth))}
    for label, subset in (('literal_released_baseline', selected & literal),
                          ('baseline_closure_only', (selected & closure)-literal),
                          ('baseline_absent', selected-closure)):
        result[label] = {'selected_pairs': len(subset), 'curator_supported_pairs': len(subset & truth)}
    return result


def add_numeric(target, source):
    for key, value in source.items():
        if isinstance(value, dict): add_numeric(target.setdefault(key, {}), value)
        else: target[key] = target.get(key, 0) + value


def diagnose(left, right, gt, exclude, ontology, literal, closure, eligible):
    import numpy as np
    from scipy.sparse import csr_matrix
    totals = {}; graph = csr_matrix(ontology.dag); cache = {}
    related = {'nonidentical_cross_method_related_pairs': 0, 'proteins_with_cross_method_related_pair': 0}
    oracle = {'union_supported_cap3': 0, 'best_parent_supported_per_protein': 0,
        'union_baseline_absent_supported_cap3': 0, 'best_parent_baseline_absent_supported_per_protein': 0}
    equal_sets = equal_order = any_returned = union_returned = intersection_returned = 0
    native_absent_yields = {m: np.zeros(gt.matrix.shape[0]) for m in (*METHODS, FUSION)}
    names = names_for(ontology)
    for i in np.flatnonzero(eligible):
        d, l = set(left[i]), set(right[i]); union = d | l; shared = d & l
        fused = set(rrf3(left[i], right[i], names))
        available = ontology.toi if exclude is None else np.setdiff1d(
            ontology.toi, exclude.matrix[i].nonzero()[0], assume_unique=True)
        truth = set(map(int, available[gt.matrix[i, available].astype(bool)]))
        raw = set(map(int, literal[i].nonzero()[0])); closed = set(map(int, closure[i].nonzero()[0]))
        for key, values in (('both_methods', shared), ('deepgose_only', d-l),
                            ('strict_alias_localplus_only', l-d), ('union', union)):
            add_numeric(totals.setdefault(key, {}), bucket(values, truth, raw, closed, ontology.ia))
        equal_sets += d == l; equal_order += left[i] == right[i]
        any_returned += bool(union); union_returned += len(union); intersection_returned += len(shared)
        cross = {tuple(sorted((a, b))) for a in d for b in l if a != b
                 and ancestor_pairs([a, b], graph, cache)}
        related['nonidentical_cross_method_related_pairs'] += len(cross)
        related['proteins_with_cross_method_related_pair'] += bool(cross)
        oracle['union_supported_cap3'] += min(K, len(union & truth))
        oracle['best_parent_supported_per_protein'] += max(len(d & truth), len(l & truth))
        oracle['union_baseline_absent_supported_cap3'] += min(K, len((union & truth)-closed))
        oracle['best_parent_baseline_absent_supported_per_protein'] += max(
            len((d & truth)-closed), len((l & truth)-closed))
        for method, values in zip((*METHODS, FUSION), (d, l, fused)):
            native_absent_yields[method][i] = len((values & truth)-closed)/K
    n = int(eligible.sum())
    exact = {'proteins_with_identical_sets': int(equal_sets), 'proteins_with_identical_order': int(equal_order),
        'proteins_with_different_sets': n-int(equal_sets), 'proteins_with_any_returned': int(any_returned),
        'intersection_pairs': intersection_returned, 'union_pairs': union_returned,
        'pooled_Jaccard': intersection_returned/union_returned if union_returned else None,
        'buckets': totals}
    oracle.update(extra_supported_slots_over_best_parent_per_protein=
        oracle['union_supported_cap3']-oracle['best_parent_supported_per_protein'],
        extra_baseline_absent_supported_slots_over_best_parent_per_protein=
        oracle['union_baseline_absent_supported_cap3']-oracle['best_parent_baseline_absent_supported_per_protein'],
        ground_truth_aware_ceiling_not_a_deployable_result=True,
        fixed3_budget_yield=oracle['union_supported_cap3']/(K*n))
    return {'exact_overlap': exact, 'ancestor_overlap': related, 'oracle': oracle}, native_absent_yields


def verify(pins):
    need(pins, 'source pins required.')
    for name, value in pins.items():
        path = Path(name)
        need(path.is_file() and not path.is_symlink() and sha(path) == value, 'source FILE pin differs: '+name)


def pk_reproduction(summary, expected):
    import numpy as np
    for label in ('ordinary', 'IA_weighted'):
        for key, value in expected[label].items():
            actual = summary[label][key]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                need(np.isclose(actual, value, rtol=1e-12, atol=1e-12), 'prior PK shortlist marginal differs: '+key)
            else: need(actual == value, 'prior PK shortlist metadata differs: '+key)


def parse_file(source, ontologies, gt, mode, temporary):
    from cafaeval.parser import pred_parser
    with tempfile.TemporaryDirectory(prefix='forecast-', dir=str(temporary)) as folder:
        path = Path(folder)/'predictions.tsv'
        with gzip.open(source['file'], 'rb') as src, path.open('xb') as dst: shutil.copyfileobj(src, dst)
        return pred_parser(str(path), ontologies, gt, mode, None)


def run(config, expected, output):
    need(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')),
         'bounded one-thread environment required before numeric imports.')
    import numpy as np
    import scipy, pandas, platform
    from cafaeval.parser import obo_parser, update_toi, gt_parser, gt_exclude_parser
    cfg = json.loads(Path(config).read_text())
    need(sha(config) == expected and cfg['format'] == FORMAT+'.freeze'
         and cfg['content_sha256'] == digest({k:v for k,v in cfg.items() if k != 'content_sha256'}), 'frozen configuration differs.')
    need(cfg['k'] == K and cfg['rrf_offset'] == OFFSET and cfg['development_only'] is True
         and cfg['previous_reference_and_metric_exposure'] is True
         and cfg['focus_namespace'] == 'molecular_function' and set(cfg['frames']) == set(FRAMES),
         'fixed algorithm/complete frame inventory differs.')
    runtime = {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'pandas': pandas.__version__}
    need(runtime == cfg['runtime'] == {'python':'3.10.12', 'numpy':'1.26.4', 'scipy':'1.13.1', 'pandas':'2.2.3'}, 'runtime differs.')
    verify(cfg['input_files_sha256'])
    need(cfg['implementation_file'] == str(Path(__file__).resolve())
         and cfg['input_files_sha256'][cfg['implementation_file']] == sha(__file__), 'executed implementation differs.')
    import cafaeval, cafaeval.parser, cafaeval.evaluation, cafaeval.graph, cafaeval.tests
    for module in (cafaeval, cafaeval.parser, cafaeval.evaluation, cafaeval.graph, cafaeval.tests):
        path = str(Path(module.__file__).resolve())
        need(cfg['input_files_sha256'].get(path) == sha(path), 'actual native import differs.')
    previous = json.loads(Path(cfg['previous_shortlist_report']).read_text())
    need(cfg['previous_shortlist_report'] in cfg['input_files_sha256'], 'prior marginal contract is not source-bound.')
    need(previous['format'] == 'biograph-steward.deepgo-shortlist.v1.results'
         and len(previous['rows']) == 12 and previous['content_sha256'] == digest(
             {k:v for k,v in previous.items() if k != 'content_sha256'}), 'prior PK marginal contract differs.')
    out = new_output(output, config); temporary = out/'temporary'; temporary.mkdir()
    descriptors = {name:{'frame':name, 'setting':spec['setting'],
        'known_exclusion':None if spec['known'] is None else 'native_known_t0_closure'} for name,spec in cfg['frames'].items()}
    write_json(out/'STARTED.json', sealed({'created_at':utcnow(), 'source_freeze_file_sha256':expected,
        'runtime':runtime, 'new_inference_or_reference_calls':0, 'frames':descriptors}))
    rows = []; parent_points = []; private = {}; pins = {}; gate = False
    try:
        ontologies = update_toi(obo_parser(cfg['ontology'], ('is_a','part_of'), cfg['ia'], False), cfg['toi'])
        for frame, spec in cfg['frames'].items():
            need(set(spec['methods']) == set(METHODS), 'complete two-parent inventory required.')
            need(spec['setting'] == ('partial' if frame in ('primary','reserved') else frame)
                 and set(spec['denominators']) == set(ASPECTS), 'native task/aspect contract differs.')
            need((spec['known'] is None) == (frame in ('no_knowledge','limited')), 'PK/None exclusion semantics differ.')
            for path in (spec['truth'], spec['known'], cfg['ontology'], cfg['ia'], cfg['toi']):
                if path is not None: need(path in cfg['input_files_sha256'], 'unbound data source.')
            for source in (*spec['methods'].values(), spec['baseline']):
                need(cfg['input_files_sha256'].get(source['file']) == source['sha256'], 'unbound forecast source.')
            gt = gt_parser(spec['truth'], ontologies)
            known = gt_exclude_parser(spec['known'], gt, ontologies) if spec['known'] is not None else None
            choices = {}; arrays = {}; points = {}
            for method in METHODS:
                prediction = parse_file(spec['methods'][method], ontologies, gt, 'fill', temporary)
                for namespace in ASPECTS:
                    need(namespace in prediction, 'missing prediction namespace; do not impute a successful case.')
                    exclude = None if known is None else known[namespace]
                    selected = selections(prediction[namespace], gt[namespace], exclude, ontologies[namespace])
                    summary, numeric = score_lists(selected, gt[namespace], exclude, ontologies[namespace])
                    order = [p for p,i in sorted(gt[namespace].ids.items(), key=lambda item:item[1])]
                    summary['native_reference_protein_order_sha256'] = digest(order)
                    den = spec['denominators'][namespace]
                    need(summary['ordinary']['eligible_proteins'] == den['eligible_proteins']
                         and summary['IA_weighted']['eligible_proteins'] == den['IA_eligible_proteins'], 'native population differs.')
                    if frame in ('primary','reserved'):
                        old = next(r for r in previous['rows'] if (r['frame'],r['namespace'],r['method']) == (frame,namespace,method))
                        need(summary['native_reference_protein_order_sha256'] == old['native_reference_protein_order_sha256'], 'PK row identity order differs.')
                        pk_reproduction(summary, old)
                    choices[method, namespace] = selected; arrays[method, namespace] = numeric; points[method, namespace] = summary
                    parent_points.append({'frame':frame, 'setting':spec['setting'], 'namespace':namespace, 'method':method, 'k':K, **summary})
                del prediction
            literal = parse_file(spec['baseline'], ontologies, gt, None, temporary)
            closure = parse_file(spec['baseline'], ontologies, gt, 'fill', temporary)
            for namespace in ASPECTS:
                need(namespace in literal and namespace in closure, 'missing baseline namespace; preserve failure.')
                left, right = (choices[m, namespace] for m in METHODS)
                a, b = (arrays[m, namespace] for m in METHODS)
                need(np.array_equal(a['eligible'], b['eligible']) and np.array_equal(
                    a['eligible_IA_weighted'], b['eligible_IA_weighted']), 'parent eligible frames differ.')
                exclude = None if known is None else known[namespace]
                detail, novelty = diagnose(left, right, gt[namespace], exclude, ontologies[namespace],
                    literal[namespace].matrix, closure[namespace].matrix, a['eligible'])
                rows.append({'frame':frame, 'setting':spec['setting'], 'namespace':namespace,
                    'eligible_proteins':int(a['eligible'].sum()), 'IA_eligible_proteins':int(a['eligible_IA_weighted'].sum()), **detail})
                if namespace == 'molecular_function': gate |= detail['exact_overlap']['proteins_with_different_sets'] > 0
                names = names_for(ontologies[namespace]); fused = [rrf3(d,l,names) for d,l in zip(left,right)]
                folder = out/frame/namespace; folder.mkdir(parents=True)
                opaque = [digest({'frozen_run':expected, 'frame':frame, 'index':i}) for i in range(len(left))]
                file = folder/'private_selections.json'; write_json(file, {'opaque_row_ids':opaque,
                    'native_order_sha256':points[METHODS[0],namespace]['native_reference_protein_order_sha256'],
                    'deepgose':left, 'strict_alias_localplus':right, 'rrf3':fused})
                pins[str(file)] = sha(file)
                file = folder/'private_counts.npz'; np.savez_compressed(file,
                    **{method+'__'+key:value for (method,ns), values in arrays.items() if ns == namespace for key,value in values.items()},
                    **{method+'__baseline_absent_yield':value for method,value in novelty.items()})
                pins[str(file)] = sha(file)
                private[frame, namespace] = {'folder':folder, 'selected':fused}
            del gt, known, choices, arrays, points, literal, closure
        need(len(rows) == 12 and len(parent_points) == 24, 'complete twelve-stratum diagnostic required.')
        execution_gate = {'kind':'any_MFO_qualified_top3_set_differs', 'passed':bool(gate), 'not_truth_aware':True}
        diagnostic = sealed({'format':FORMAT+'.diagnostic', 'created_at':utcnow(),
            'source_freeze_file_sha256':expected, 'rows':rows, 'execution_gate':execution_gate,
            'parent_points':parent_points, 'PK_parent_reproduction_gate_passed':True})
        write_json(out/'DIAGNOSTIC_DONE.json', diagnostic)
        fusion_points = []; comparisons = []
        if gate:
            for frame, spec in cfg['frames'].items():
                gt = gt_parser(spec['truth'], ontologies)
                known = gt_exclude_parser(spec['known'], gt, ontologies) if spec['known'] is not None else None
                for namespace in ASPECTS:
                    item = private[frame, namespace]; exclude = None if known is None else known[namespace]
                    summary, numeric = score_lists(item['selected'], gt[namespace], exclude, ontologies[namespace])
                    order = [p for p,i in sorted(gt[namespace].ids.items(), key=lambda item:item[1])]
                    summary['native_reference_protein_order_sha256'] = digest(order)
                    with np.load(item['folder']/'private_counts.npz', allow_pickle=False) as old:
                        need(np.array_equal(numeric['eligible'], old[METHODS[0]+'__eligible'])
                             and np.array_equal(numeric['eligible_IA_weighted'], old[METHODS[0]+'__eligible_IA_weighted']), 'fusion population differs.')
                        mask = numeric['eligible']
                        for comparator in METHODS:
                            result, distribution = paired_interval(numeric['ordinary'][mask,1]/K,
                                old[comparator+'__ordinary'][mask,1]/K)
                            file = item['folder']/('paired_rrf3_minus_'+comparator+'.npy')
                            np.save(file, distribution, allow_pickle=False); pins[str(file)] = sha(file)
                            comparisons.append({'frame':frame, 'setting':spec['setting'], 'namespace':namespace,
                                'candidate':FUSION, 'comparator':comparator, 'eligible_proteins':int(mask.sum()),
                                'metric':'curator_supported_slots_per_fixed3_budget',
                                'role':'designated_focus' if namespace == 'molecular_function' else 'secondary', **result})
                        summary['baseline_absent_supported_slots_per_fixed3_budget'] = {
                            m:float(old[m+'__baseline_absent_yield'][mask].mean()) for m in (*METHODS,FUSION)}
                    file = item['folder']/'private_rrf3_counts.npz'; np.savez_compressed(file, **numeric); pins[str(file)] = sha(file)
                    fusion_points.append({'frame':frame, 'setting':spec['setting'], 'namespace':namespace, 'method':FUSION, 'k':K, **summary})
                del gt, known
        need(len(fusion_points) == (12 if gate else 0) and len(comparisons) == (24 if gate else 0), 'incomplete fixed combination inventory.')
        verify(cfg['input_files_sha256'])
        report = sealed({'format':FORMAT+'.results', 'created_at':utcnow(), 'source_freeze_file_sha256':expected,
            'runtime':runtime, 'k':K, 'rrf_offset':OFFSET, 'frames':descriptors, 'rows':rows,
            'parent_points':parent_points, 'fusion_points':fusion_points, 'comparisons':comparisons,
            'execution_gate':execution_gate, 'diagnostic_file_sha256':sha(out/'DIAGNOSTIC_DONE.json'),
            'uncertainty':{'implementation':'scipy.stats.bootstrap', 'version':scipy.__version__, 'paired':True,
                'draws':2000, 'seed':20261113, 'method':'percentile', 'confidence_level':.95,
                'batch':100, 'multiplicity_adjusted':False},
            'PK_parent_reproduction_gate_passed':True, 'all12_declared_strata_preserved':True,
            'development_only':True, 'app_default_or_consumer_changed':False,
            'source_files_sha256':cfg['input_files_sha256'], 'numeric_artifact_files_sha256':pins,
            'limitations':cfg['limitations']})
        write_json(out/'report.json',report); write_json(out/'DONE.json',sealed({'status':'complete',
            'report_file_sha256':sha(out/'report.json'), 'report_content_sha256':report['content_sha256']}))
        return report
    except BaseException as error:
        write_json(out/'FAILURE.json', sealed({'status':'failed_preserved', 'error_type':type(error).__name__,
            'app_or_original_outputs_changed':False})); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config','expected','output'): parser.add_argument('--'+key,required=True)
    result = run(**vars(parser.parse_args()))
    print(json.dumps({'status':'complete', 'content_sha256':result['content_sha256']}))
