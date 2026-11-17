"""Post-exposure sensitivity using the author's nonfinite-column policy.

The frozen primary is not changed/relabelled. This independently loads the same
fixed cohorts/rankings, removing nonfinite features across the complete author
file before selecting graph targets. No values are imputed or capped.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .core import (macro_scores, paired_query_bootstrap, profile_correlations,
                   sha, top_neighbors, tsv, write_json)
from .run import CANDIDATE, OLD_ARMS


def finite_columns(dataset, block_size=128):
    import numpy as np
    mask = np.ones(dataset.shape[1], dtype=bool)
    for start in range(0, dataset.shape[0], block_size):
        mask &= np.isfinite(np.asarray(dataset[start:start + block_size, :])).all(axis=0)
    return mask


def run(frozen, prior_results, expected_protocol, output):
    import anndata as ad
    import numpy as np
    frozen, prior_results, output = Path(frozen), Path(prior_results), Path(output)
    if sha(frozen / 'protocol.json') != expected_protocol:
        raise ValueError('Unexpected consumed primary protocol.')
    protocol = json.loads((frozen / 'protocol.json').read_text())
    for p, expected in protocol['inputs_sha256'].items():
        if sha(p) != expected:
            raise ValueError('Original frozen input changed: ' + p)
    prior = json.loads(prior_results.read_text())
    if prior['protocol_sha256'] != expected_protocol:
        raise ValueError('Prior assessment belongs to another freeze.')
    output.mkdir(exist_ok=False, parents=True)
    policy = {
        'format': 'biograph-steward.perturbation-nonfinite-column-sensitivity.v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'post_exposure_technical_sensitivity_not_fresh_confirmation',
        'original_protocol_sha256': expected_protocol,
        'original_results_sha256': sha(prior_results),
        'adapter_sha256': sha(__file__),
        'policy': 'Exclude every gene column containing any nonfinite value across ALL rows of each full author file. Then retain identical original eligibility, own-target masking, fixed rankings, k10 signed readout and query bootstrap; report global-budget coverage separately. Never impute/cap values or optimize feature selection by graph/reference concordance.',
        'upstream': 'https://github.com/thomasmaxwellnorman/Perturbseq_GI/blob/3b25109aeb9c0c2026bd70abd50304a0ad4e5395/perturbseq/cell_population.py#L316-L318',
        'qualification': 'Matches the documented replace Inf->NaN then dropna(axis=1) operation on the full population. It discards potentially informative features; missingness is not assumed random. The exact cause of author bulk Inf values is unverified.',
        'promotion': 'No result from this consumed-reference sensitivity establishes independent confirmation or triggers a production ranking/pruning change.',
    }
    write_json(output / 'sensitivity_policy.json', policy)
    config = protocol['config']
    mappings = json.loads((frozen / 'gene_mapping.json').read_text())
    gene_to_node = {r['ensembl_gene']: n for n, r in mappings.items()}
    ranks = json.loads((frozen / 'rankings.json').read_text())
    retained = json.loads((frozen / 'retained_eligible.json').read_text())
    pairs = [r for r in tsv(Path(config['source_dir']) / 'graph_pairs.tsv') if r['pruning_eligible'] == 'true']
    by_id = {r['pair_id']: r for r in pairs}
    result = {'status': policy['status'], 'sensitivity_policy_sha256': sha(output / 'sensitivity_policy.json'),
              'original_protocol_sha256': expected_protocol, 'cells': {}, 'production_graph_changed': False}
    for ref in config['references']:
        data = ad.read_h5ad(ref['file'], backed='r')
        mask = finite_columns(data.X)
        targets = [re.search(r'_(ENSG\d+)$', label) for label in data.obs_names]
        targets = [m.group(1) if m else None for m in targets]
        counts = Counter(g for g in targets if g)
        rows, nodes = [], []
        for i, gene in enumerate(targets):
            if (gene in gene_to_node and counts[gene] == 1
                    and np.isfinite(data.obs.iloc[i]['num_cells_filtered'])
                    and data.obs.iloc[i]['num_cells_filtered'] >= 25):
                rows.append(i); nodes.append(gene_to_node[gene])
        x = np.asarray(data.X[rows, :], dtype=np.float64)[:, mask]
        features = list(data.var_names[mask])
        feature_index = defaultdict(list)
        for i, gene in enumerate(features):
            feature_index[gene].append(i)
        own = [feature_index[mappings[n]['ensembl_gene']] for n in nodes]
        r, finite = profile_correlations(x, own)
        excluded = [n for i, n in enumerate(nodes) if not finite[i]]
        if excluded:
            r = r[np.ix_(finite, finite)]
            nodes = [n for i, n in enumerate(nodes) if finite[i]]
        index = {n: i for i, n in enumerate(nodes)}
        scores = {arm: macro_scores(top_neighbors(pairs, order, set(nodes), 10), r, index)
                  for arm, order in ranks.items()}
        query_sets = [set(v) for v in scores.values()]
        if any(s != query_sets[0] for s in query_sets):
            raise ValueError('Inconsistent sensitivity query denominators.')
        queries = sorted(query_sets[0])
        cell = {'all_author_rows_used_for_feature_QC': data.shape[0], 'original_features': data.shape[1],
                'finite_features_retained': int(mask.sum()), 'nonfinite_feature_columns_excluded': int((~mask).sum()),
                'mapped_eligible_perturbations': len(rows), 'finite_nonconstant_profiles': len(nodes),
                'constant_or_nonfinite_remaining': excluded, 'queries': len(queries),
                'original_primary_queries': prior['cells'][ref['name']]['readouts']['signed_k10']['queries'],
                'mean_query_r': {arm: float(np.mean(list(v.values()))) for arm, v in scores.items()},
                'candidate_minus_comparator': {arm: paired_query_bootstrap(scores[CANDIDATE], scores[arm], queries, 2026111307) for arm in OLD_ARMS}}
        budgets = {}
        for arm, selected in retained.items():
            vals, covered = [], set()
            for uid in selected:
                a, b = by_id[uid]['subject'], by_id[uid]['object']
                if a in index and b in index:
                    vals.append(float(r[index[a], index[b]])); covered.update((a, b))
            budgets[arm] = {'eligible_source_pairs_retained': len(selected), 'measured_pairs_retained': len(vals),
                            'measured_queries_covered': len(covered), 'conditional_mean_r': float(np.mean(vals)) if vals else None}
        cell['global_budget_secondary'] = budgets
        write_json(output / (ref['name'] + '_query_scores.json'), scores)
        result['cells'][ref['name']] = cell
        data.file.close()
        write_json(output / 'results.json', result)
        print(json.dumps({'cell': ref['name'], 'queries': len(queries), 'finite_features': int(mask.sum()), 'mean_query_r': cell['mean_query_r']}), flush=True)
    write_json(output / 'results.json', result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frozen', required=True); p.add_argument('--prior-results', required=True)
    p.add_argument('--protocol-sha256', required=True); p.add_argument('--output', required=True)
    a = p.parse_args()
    run(a.frozen, a.prior_results, a.protocol_sha256, a.output)


if __name__ == '__main__':
    main()
