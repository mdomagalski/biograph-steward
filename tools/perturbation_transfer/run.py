"""Freeze a source-only ranking, then evaluate a separate perturbation study.

The optional AnnData/NumPy dependencies are imported only at the evaluation
stage. No retrieval, model inference, production graph edits or fitted scores.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re

from .core import (complex_pairs, gene_mapping, macro_scores, paired_query_bootstrap,
                   profile_correlations, read_extended_sif, sha, top_neighbors,
                   tsv, write_json)

CANDIDATE = 'reactome_complex_then_human_experimental'
OLD_ARMS = ('human_experimental_top80', 'native_top80', 'ne_top80', 'pa_top80',
            'mps_top80', 'combined_experimental_top80')


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def md5(path):
    h = hashlib.md5()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def prepare(config_path, output):
    config = json.loads(Path(config_path).read_text())
    names = [r['name'] for r in config['references']]
    if sorted(names) != ['K562', 'RPE1']:
        raise ValueError('This fixed two-context assessment requires exactly K562 and RPE1.')
    output = Path(output)
    output.mkdir(exist_ok=False, parents=True)
    source, ranks = Path(config['source_dir']), Path(config['rankings_dir'])
    pairs = tsv(source / 'graph_pairs.tsv')
    endpoints = [tuple(sorted((r['subject'], r['object']))) for r in pairs]
    if len(set(endpoints)) != len(pairs) or any(a == b for a, b in endpoints):
        raise ValueError('Expected unique unordered nonself source pairs.')
    eligible = [r for r in pairs if r['pruning_eligible'] == 'true']
    ids = {r['pair_id'] for r in eligible}
    if len(eligible) != len(ids):
        raise ValueError('Duplicate source pairs.')
    node_rows = tsv(source / 'network_nodes.tsv')
    nodes = {r['node_id'] for r in node_rows}
    present_nodes = {r['node_id'] for r in node_rows
                     if r['resolution_status'] == 'resolved' and r['canonical_graph_node_present'] == 'true'}
    if any(a not in nodes or b not in nodes for a, b in endpoints):
        raise ValueError('Source endpoint missing from declared nodes.')
    mapping, exclusions = gene_mapping(config['registry'], present_nodes)
    edges, context_nodes = read_extended_sif(config['context'])
    if any(row['INTERACTION_DATA_SOURCE'] != 'Reactome' for row in edges):
        raise ValueError('Context must be the released Reactome-only projection.')
    contexts, eligible_context_nodes = complex_pairs(edges, context_nodes)
    supported = {}
    for row in eligible:
        a, b = mapping.get(row['subject']), mapping.get(row['object'])
        if a and b:
            records = contexts.get(tuple(sorted((a['symbol'], b['symbol']))))
            if records:
                supported[row['pair_id']] = records
    rankings = {}
    inputs = [Path(config_path), Path(config['registry']), Path(config['context']),
              Path(config['context_metadata']), source / 'source_qualification.json',
              source / 'graph_pairs.tsv', source / 'network_nodes.tsv', Path(config['forest'])]
    for arm in OLD_ARMS:
        path = ranks / (arm + '_ranking.tsv')
        table = tsv(path)
        order = [r['pair_id'] for r in sorted(table, key=lambda r: int(r['rank']))]
        if len(order) != len(ids) or set(order) != ids:
            raise ValueError('Rankings must cover the identical eligible source pairs.')
        rankings[arm] = order
        inputs.append(path)
    native_position = {uid: i for i, uid in enumerate(rankings['human_experimental_top80'])}
    rankings[CANDIDATE] = sorted(ids, key=lambda uid: (uid not in supported, native_position[uid]))
    forest = {r['pair_id'] for r in tsv(config['forest'])}
    if not forest <= ids:
        raise ValueError('Source forest must be eligible.')
    budget = json.loads((source / 'source_qualification.json').read_text())['retained_rankable_budget']
    if len(forest) > budget:
        raise ValueError('Forest exceeds the fixed budget.')
    retained = {}
    for arm, order in rankings.items():
        chosen = list(forest) + [uid for uid in order if uid not in forest][:budget - len(forest)]
        if len(chosen) != budget:
            raise ValueError('Unequal graph budget.')
        retained[arm] = sorted(chosen)
    write_json(output / 'rankings.json', rankings)
    write_json(output / 'retained_eligible.json', retained)
    write_json(output / 'gene_mapping.json', mapping)
    write_json(output / 'context_pair_provenance.json', supported)
    for path in Path(__file__).parent.glob('*.py'):
        inputs.append(path)
    inputs.append(Path(__file__).with_name('requirements.txt'))
    for ref in config['references']:
        if md5(ref['file']) != ref['md5']:
            raise ValueError('Author file checksum mismatch: ' + ref['name'])
        inputs.append(Path(ref['file']))
    for name in ('rankings.json', 'retained_eligible.json', 'gene_mapping.json', 'context_pair_provenance.json'):
        inputs.append(output / name)
    protocol = {
        'format': 'biograph-steward.perturbation-transfer.v1', 'created_at': utcnow(),
        'status': 'frozen_before_expression_matrix_values', 'config': config,
        'inputs_sha256': {str(p.resolve()): sha(p) for p in inputs},
        'source_counts': {'declared_query_nodes': len(nodes), 'present_graph_nodes': len(present_nodes), 'all_source_pairs': len(pairs),
                          'eligible_pairs': len(ids), 'eligible_retained_per_view': budget,
                          'protected_source_pairs_retained': len(pairs) - len(ids),
                          'unique_gene_mapped_nodes': len(mapping), 'mapping_exclusions': exclusions,
                          'strict_context_nodes': len(eligible_context_nodes),
                          'eligible_pairs_with_co_complex_context': len(supported)},
        'candidate': 'One binary prior: released 2019 Reactome/Paxtools in-complex-with support, then the complete unchanged human-experimental/combined/ID order. No complex counts, weights or label fitting.',
        'primary': 'Per query mean signed Pearson r among top min(10,eligible measured degree) graph neighbors; macro average over the same queries for every arm. K562 primary; RPE1 separate cell-context replication.',
        'comparators': list(OLD_ARMS),
        'features': 'All genes retained in each author-normalized pseudobulk file (>0.01 UMI/cell per author catalog). Set the exact Ensembl target feature to zero in its own profile, following the published self-target masking convention. This broader feature panel is an explicit adapter, not exact reproduction of the paper\'s selected strong-perturbation/HVG analysis.',
        'eligibility': 'Unique Ensembl-target perturbation row, >=25 author-filtered cells, one-to-one approved HGNC/protein mapping; every finite nonconstant profile retained regardless of DE strength, knockdown efficacy or graph support. Do not rescue duplicate guide/target rows or unresolved aliases. Nominal target identity does not certify every guide on-target.',
        'secondary': ['k=1 and k=5 signed Pearson, fixed before values', 'absolute Pearson for the same k=10 predictions', 'same fixed global 80% eligible budget with the same native spanning forest; conditional mean r and query/edge coverage, not edge precision'],
        'uncertainty': '2000 paired query bootstrap draws, seed2026111307, descriptive only: partners overlap and both cell lines belong to one study. No IID-edge p-values or independent-study replication claim.',
        'success_boundary': 'A useful transferable signal requires positive k10 signed differences versus human-experimental, native combined and Network Enhancement in BOTH cell contexts; show every comparison and descriptive interval. No outcome-selected replacement primary. Whole-graph truth and clinical/catalytic/direct-binding claims remain outside scope.',
        'lineage': 'Historical source STRING v11 Dec2018; PathwayCommons12 Reactome69 May2019, released2019; experimental study preprint Dec2021, final2022. The 2019 input cannot ingest these later measurements. Earlier biology and overlapping original studies are expected: context is an input prior, never an independent evidence vote. Replogle paper aggregate/examples and QC metadata were read before freeze; normalized X values were not. Paper itself compares STRING/CORUM, so the task is literature-informed rather than whole-study blind.',
        'prior_exposure': 'Earlier OpenCell, BioPlex, Wainberg, kinase and grounding comparisons remain consumed and unchanged. This Replogle expression endpoint was not previously evaluated. No raw cells, new model or production graph modification.',
    }
    write_json(output / 'protocol.json', protocol)
    print(json.dumps({'frozen': str(output / 'protocol.json'), 'protocol_sha256': sha(output / 'protocol.json'), 'source_counts': protocol['source_counts']}))


def evaluate(frozen, output, expected_protocol_sha256):
    import anndata as ad
    import numpy as np
    frozen, output = Path(frozen), Path(output)
    if sha(frozen / 'protocol.json') != expected_protocol_sha256:
        raise ValueError('Protocol hash differs from the separately recorded pre-exposure freeze.')
    protocol = json.loads((frozen / 'protocol.json').read_text())
    for path, expected in protocol['inputs_sha256'].items():
        if sha(path) != expected:
            raise ValueError('Frozen input changed: ' + path)
    output.mkdir(exist_ok=False, parents=True)
    write_json(output / 'exposure_started.json', {'created_at': utcnow(), 'protocol_sha256': sha(frozen / 'protocol.json')})
    config = protocol['config']
    pairs = [r for r in tsv(Path(config['source_dir']) / 'graph_pairs.tsv') if r['pruning_eligible'] == 'true']
    rankings = json.loads((frozen / 'rankings.json').read_text())
    retained = json.loads((frozen / 'retained_eligible.json').read_text())
    mapping = json.loads((frozen / 'gene_mapping.json').read_text())
    gene_to_node = {r['ensembl_gene']: n for n, r in mapping.items()}
    results = {'format': protocol['format'], 'protocol_sha256': sha(frozen / 'protocol.json'),
               'created_at': utcnow(), 'dependencies': {name: importlib.metadata.version(name) for name in ('anndata', 'numpy', 'h5py', 'scipy')}, 'cells': {}}
    for ref in config['references']:
        data = ad.read_h5ad(ref['file'], backed='r')
        targets = []
        for label in data.obs_names:
            match = re.search(r'_(ENSG\d+)$', label)
            targets.append(match.group(1) if match else None)
        counts = Counter(gene for gene in targets if gene)
        rows, nodes, exclusions = [], [], Counter()
        for i, gene in enumerate(targets):
            if gene is None or gene not in gene_to_node:
                exclusions['no_unique_graph_gene_mapping'] += 1
            elif counts[gene] != 1:
                exclusions['duplicate_target_rows'] += 1
            elif not np.isfinite(data.obs.iloc[i]['num_cells_filtered']) or data.obs.iloc[i]['num_cells_filtered'] < 25:
                exclusions['fewer_than_25_filtered_cells_or_unknown'] += 1
            else:
                rows.append(i); nodes.append(gene_to_node[gene])
        # Backed slicing reads only the declared rows, not the full matrix.
        values = np.asarray(data.X[rows, :], dtype=np.float64)
        feature_ids = list(data.var_names)
        feature_index = defaultdict(list)
        for i, gene in enumerate(feature_ids):
            feature_index[gene].append(i)
        own = [feature_index[mapping[node]['ensembl_gene']] for node in nodes]
        corr, finite = profile_correlations(values, own)
        discarded = [n for i, n in enumerate(nodes) if not finite[i]]
        if discarded:
            corr = corr[np.ix_(finite, finite)]
            nodes = [n for i, n in enumerate(nodes) if finite[i]]
        index = {n: i for i, n in enumerate(nodes)}
        measured = set(nodes)
        cell = {'author_shape': list(data.shape), 'author_features_used': len(feature_ids),
                'mapped_eligible_perturbations': len(rows), 'finite_nonconstant_profiles': len(nodes),
                'constant_or_nonfinite_exclusions': discarded, 'row_exclusions': dict(exclusions),
                'target_feature_present': sum(bool(x) for x in own), 'readouts': {}}
        query_rows = {}
        for k in (10, 1, 5):
            per_arm = {}
            for arm, order in rankings.items():
                neighbors = top_neighbors(pairs, order, measured, k)
                per_arm[arm] = macro_scores(neighbors, corr, index)
            query_sets = [set(v) for v in per_arm.values()]
            if any(s != query_sets[0] for s in query_sets):
                raise ValueError('Different query universe between complete rankings.')
            queries = sorted(query_sets[0])
            means = {arm: float(np.mean([scores[q] for q in queries])) for arm, scores in per_arm.items()}
            comparisons = {arm: paired_query_bootstrap(per_arm[CANDIDATE], per_arm[arm], queries, 2026111307) for arm in OLD_ARMS}
            cell['readouts']['signed_k' + str(k)] = {'queries': len(queries), 'mean_query_r': means, 'candidate_minus_comparator': comparisons}
            if k == 10:
                query_rows = per_arm
                absolute = {arm: macro_scores(top_neighbors(pairs, order, measured, k), corr, index, True) for arm, order in rankings.items()}
                cell['readouts']['absolute_k10'] = {'mean_query_absolute_r': {arm: float(np.mean(list(v.values()))) for arm, v in absolute.items()},
                    'candidate_minus_comparator': {arm: paired_query_bootstrap(absolute[CANDIDATE], absolute[arm], queries, 2026111307) for arm in OLD_ARMS}}
        by_id = {r['pair_id']: r for r in pairs}
        budget_metrics = {}
        for arm, selected in retained.items():
            vals, covered_queries = [], set()
            for uid in selected:
                a, b = by_id[uid]['subject'], by_id[uid]['object']
                if a in measured and b in measured:
                    vals.append(float(corr[index[a], index[b]])); covered_queries.update((a, b))
            budget_metrics[arm] = {'eligible_source_pairs_retained': len(selected), 'measured_pairs_retained': len(vals),
                                   'measured_queries_covered': len(covered_queries), 'conditional_mean_r': float(np.mean(vals)) if vals else None}
        cell['global_budget_secondary'] = budget_metrics
        cell['all_measured_eligible_source_pairs'] = sum(r['subject'] in measured and r['object'] in measured for r in pairs)
        cell['measured_graph_node_ids'] = nodes
        write_json(output / (ref['name'] + '_query_scores.json'), query_rows)
        results['cells'][ref['name']] = cell
        data.file.close()
        write_json(output / 'results.json', results)
        print(json.dumps({'cell': ref['name'], 'queries': cell['readouts']['signed_k10']['queries'], 'signed_k10': cell['readouts']['signed_k10']['mean_query_r']}), flush=True)
    important = ('human_experimental_top80', 'native_top80', 'ne_top80')
    results['predeclared_both_context_positive_rule_met'] = all(
        cell['readouts']['signed_k10']['candidate_minus_comparator'][arm]['mean_difference'] > 0
        for cell in results['cells'].values() for arm in important)
    results['whole_graph_accuracy_established'] = False
    results['production_graph_changed'] = False
    write_json(output / 'results.json', results)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare'); a.add_argument('--config', required=True); a.add_argument('--output', required=True)
    a = sub.add_parser('evaluate'); a.add_argument('--frozen', required=True); a.add_argument('--output', required=True)
    a.add_argument('--protocol-sha256', required=True)
    args = p.parse_args()
    if args.command == 'prepare':
        prepare(args.config, args.output)
    else:
        evaluate(args.frozen, args.output, args.protocol_sha256)


if __name__ == '__main__':
    main()
