"""Small adapters around native extended SIF, HGNC and NumPy statistics.

These functions never infer binding from a co-complex projection, fabricate a
negative label, fit a score or retrieve a source. Numeric libraries are optional.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def tsv(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def gene_mapping(registry, graph_nodes):
    """Only unique approved HGNC protein -> Ensembl gene assignments.

    Gene-level assays cannot distinguish two graph proteins for the same gene;
    exclude those genes rather than silently choosing one protein.
    """
    up_rows = defaultdict(set)
    for row in tsv(registry):
        if row['status'] != 'Approved' or row['locus_group'] != 'protein-coding gene':
            continue
        ens = row['ensembl_gene_id'].split('|')
        if len(ens) != 1 or not re.fullmatch(r'ENSG\d+', ens[0]):
            continue
        for up in row['uniprot_ids'].split('|'):
            if up:
                up_rows['UniProtKB:' + up].add((ens[0], row['symbol'], row['hgnc_id']))
    result, exclusions = {}, Counter()
    for node in graph_nodes:
        rows = up_rows.get(node, set())
        if len(rows) == 1:
            ens, symbol, hgnc = next(iter(rows))
            result[node] = {'ensembl_gene': ens, 'symbol': symbol, 'hgnc_id': hgnc}
        else:
            exclusions['no_unique_approved_HGNC_gene'] += 1
    counts = Counter(row['ensembl_gene'] for row in result.values())
    for node in list(result):
        if counts[result[node]['ensembl_gene']] != 1:
            del result[node]
            exclusions['multiple_graph_proteins_for_gene'] += 1
    return result, dict(exclusions)


def read_extended_sif(path):
    """Read the released two-table TSV, preserving source mediator IDs.

    The standard Pathway Commons format has a seven-column edge table and,
    after a blank line, a five-column node table. No BioPAX parsing/expansion.
    """
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        tables = f.read().split('\n\n')
    tables = [table for table in tables if table.strip()]
    if len(tables) != 2:
        raise ValueError('Expected the two native extended-SIF tables.')
    import io
    edges = list(csv.DictReader(io.StringIO(tables[0]), delimiter='\t'))
    nodes = list(csv.DictReader(io.StringIO(tables[1]), delimiter='\t'))
    return edges, nodes


def complex_pairs(edges, nodes):
    """Exact released ProteinReference/HGNC-symbol nodes, no alias repair."""
    eligible = set()
    for row in nodes:
        if row['PARTICIPANT_TYPE'] != 'ProteinReference':
            continue
        symbols = set()
        for key in ('UNIFICATION_XREF', 'RELATIONSHIP_XREF'):
            for value in (row.get(key) or '').split(';'):
                if value.strip().lower().startswith('hgnc symbol:'):
                    symbols.add(value.strip().split(':', 1)[1])
        if symbols == {row['PARTICIPANT']}:
            eligible.add(row['PARTICIPANT'])
    pairs = {}
    for row in edges:
        a, b = row['PARTICIPANT_A'], row['PARTICIPANT_B']
        if (row['INTERACTION_TYPE'] == 'in-complex-with' and a != b
                and a in eligible and b in eligible):
            key = tuple(sorted((a, b)))
            pairs.setdefault(key, []).append(row)
    return pairs, eligible


def top_neighbors(pair_rows, ranking, measured_nodes, k):
    """Same min(k,degree) predictions per query for every complete ranking."""
    neighbors = defaultdict(list)
    by_id = {r['pair_id']: r for r in pair_rows}
    for pair_id in ranking:
        row = by_id[pair_id]
        a, b = row['subject'], row['object']
        if a in measured_nodes and b in measured_nodes:
            neighbors[a].append(b)
            neighbors[b].append(a)
    return {node: values[:k] for node, values in neighbors.items()}


def profile_correlations(values, target_feature_indices):
    """Native Pearson r, own-target feature zeroed as in Replogle methods.

    Return NaN for a constant/nonfinite profile; never substitute a negative.
    """
    import numpy as np
    x = np.asarray(values, dtype=np.float64).copy()
    for i, columns in enumerate(target_feature_indices):
        x[i, columns] = 0.0
    x -= x.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(x, axis=1)
    good = np.isfinite(x).all(axis=1) & (norms > 0)
    z = np.full_like(x, np.nan)
    z[good] = x[good] / norms[good, None]
    return np.clip(z @ z.T, -1.0, 1.0), good


def macro_scores(neighbors, correlation, node_index, absolute=False):
    import numpy as np
    result = {}
    for node, others in neighbors.items():
        vals = correlation[node_index[node], [node_index[o] for o in others]]
        if absolute:
            vals = np.abs(vals)
        result[node] = float(np.mean(vals))
    return result


def paired_query_bootstrap(candidate, baseline, queries, seed, repeats=2000):
    """Descriptive paired query resampling, not independent edge/study trials."""
    import numpy as np
    delta = np.array([candidate[q] - baseline[q] for q in queries])
    if not len(delta) or not np.isfinite(delta).all():
        raise ValueError('Need finite paired query scores.')
    rng = np.random.default_rng(seed)
    means = np.array([np.mean(delta[rng.integers(len(delta), size=len(delta))])
                      for _ in range(repeats)])
    return {'queries': len(delta), 'mean_difference': float(delta.mean()),
            'query_bootstrap_95_interval': np.quantile(means, [.025, .975]).tolist(),
            'candidate_higher_queries': int((delta > 1e-12).sum()),
            'candidate_lower_queries': int((delta < -1e-12).sum()),
            'tied_queries': int((abs(delta) <= 1e-12).sum()),
            'scope': 'Descriptive query bootstrap; shared partners and one study limit independence.'}
