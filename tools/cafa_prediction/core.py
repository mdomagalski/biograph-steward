"""Thin data adapter for the published FastSinkSource/GeneMANIA implementation.

The GPL-3.0 author code stays in a separate, pinned directory and is not copied
into the application. This adapter supplies historical inputs and calls its
unchanged public functions. It reads no future annotation labels.
"""
from collections import Counter
import csv
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import re
import sys

AUTHOR_COMMIT = 'c45c21b9c937c3372eae03248f49fb008d4cb0cf'
AUTHOR_REPOSITORY = 'https://github.com/Murali-group/multi-species-GOA-prediction'
ASPECTS = {'BPO': 'biological_process', 'MFO': 'molecular_function', 'CCO': 'cellular_component'}
PARAMETERS = {'fastsinksourceplus': {'a': .8, 'max_iters': 1000, 'eps': .0001},
              'genemaniaplus': {'alpha': 1, 'tol': .00001}, 'localplus': {}}
RUNTIME = {'numpy': '1.26.4', 'scipy': '1.13.1', 'tqdm': '4.67.1'}


def need(value, message):
    if not value:
        raise ValueError('CAFA prediction: ' + message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def ontology_terms(path):
    """Read only ID/lifecycle/namespace from the frozen GO OBO, not future labels."""
    result, current = {}, None
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            line = line.rstrip('\n')
            if line.startswith('['):
                if current and 'id' in current:
                    result[current['id']] = current
                current = {} if line == '[Term]' else None
            elif current is not None and ': ' in line:
                key, value = line.split(': ', 1)
                if key in {'id', 'namespace', 'is_obsolete'}:
                    current[key] = value
        if current and 'id' in current:
            result[current['id']] = current
    need(result and all(re.fullmatch(r'GO:[0-9]{7}', t) for t in result), 'invalid GO term inventory.')
    return {t: row['namespace'] for t, row in result.items()
            if row.get('is_obsolete') != 'true' and row.get('namespace') in ASPECTS.values()}


def graph_frame(nodes_path, weighted_path):
    """Preserve every present graph protein; never invent weights for missing rows."""
    with Path(nodes_path).open(newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    nodes = [r['node_id'] for r in rows if r['canonical_graph_node_present'] == 'true']
    need(nodes and len(set(nodes)) == len(nodes) and all(re.fullmatch(r'UniProtKB:[A-Z0-9]+', n) for n in nodes),
         'expected unique exact canonical graph protein identities.')
    nodes = sorted(nodes)
    vocabulary = set(nodes)
    pairs, seen, pair_ids = [], set(), set()
    with Path(weighted_path).open(newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            a, b = row['subject'], row['object']
            need(a in vocabulary and b in vocabulary and a != b, 'weighted pair is outside the graph frame.')
            key = tuple(sorted((a, b)))
            need(key not in seen and row['pair_id'] not in pair_ids, 'duplicate weighted pair or source identity.')
            weight = float(row['weight'])
            need(0 < weight <= 1, 'native confidence must be finite and in (0,1].')
            seen.add(key); pair_ids.add(row['pair_id'])
            pairs.append((a, b, weight))
    need(pairs, 'empty qualified native weighted graph.')
    return nodes, pairs


def training_annotations(path, nodes, ontology):
    """Read the author's known-at-t0 table, retaining its already propagated labels.

    The published file need not group a protein's annotations together. A
    temporary SQLite primary key supplies order-independent set semantics
    without keeping all five million source pairs in memory.
    Graph target annotations known at t0 remain legal inputs for partial
    knowledge prediction; the official evaluator later masks those known terms.
    """
    graph_ids = {n.split(':', 1)[1] for n in nodes}
    labels = {n: set() for n in graph_ids}
    counts, denominators = {a: Counter() for a in ASPECTS}, Counter()
    rows, admitted, excluded = 0, 0, Counter()
    import sqlite3
    import tempfile
    with tempfile.TemporaryDirectory(prefix='biograph-cafa-known-') as temporary:
        db = sqlite3.connect(str(Path(temporary) / 'known.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('CREATE TABLE proteins(protein TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TABLE annotations(protein TEXT,aspect TEXT,term TEXT,PRIMARY KEY(protein,aspect,term)) WITHOUT ROWID')
            batch, protein_batch = [], []
            with Path(path).open(newline='', encoding='utf-8') as stream:
                reader = csv.DictReader(stream, delimiter='\t')
                need(reader.fieldnames == ['EntryID', 'term', 'aspect'], 'known_t0 header differs from the author artifact.')
                for row in reader:
                    identifier, term, aspect = row['EntryID'], row['term'], row['aspect']
                    need(aspect in ASPECTS, 'unknown historical GO aspect.')
                    rows += 1; protein_batch.append((identifier,))
                    if term not in ontology:
                        excluded['outside_active_frozen_ontology'] += 1
                    else:
                        need(ontology[term] == ASPECTS[aspect], 'known annotation aspect conflicts with frozen ontology.')
                        admitted += 1; batch.append((identifier, aspect, term))
                        if identifier in graph_ids:
                            labels[identifier].add((aspect, term))
                    if rows % 50000 == 0:
                        db.executemany('INSERT OR IGNORE INTO proteins VALUES (?)', protein_batch)
                        db.executemany('INSERT OR IGNORE INTO annotations VALUES (?,?,?)', batch)
                        db.commit(); batch, protein_batch = [], []
                db.executemany('INSERT OR IGNORE INTO proteins VALUES (?)', protein_batch)
                db.executemany('INSERT OR IGNORE INTO annotations VALUES (?,?,?)', batch)
                db.commit()
            proteins = db.execute('SELECT COUNT(*) FROM proteins').fetchone()[0]
            unique_pairs = db.execute('SELECT COUNT(*) FROM annotations').fetchone()[0]
            duplicate_rows = admitted - unique_pairs
            denominators.update({a: n for a, n in db.execute('SELECT aspect,COUNT(DISTINCT protein) FROM annotations GROUP BY aspect')})
            for a, t, n in db.execute('SELECT aspect,term,COUNT(*) FROM annotations GROUP BY aspect,term'):
                counts[a][t] = n
        finally:
            db.close()
    need(proteins and rows, 'no historical annotations.')
    return labels, {a: {t: n / denominators[a] for t, n in sorted(count.items())}
                    for a, count in counts.items()}, {
        'source_rows': rows, 'source_proteins': proteins,
        'aspect_annotated_protein_denominators': dict(denominators),
        'duplicate_rows_collapsed': duplicate_rows, 'excluded_rows': dict(excluded),
        'graph_proteins_with_known_labels': sum(bool(v) for v in labels.values()),
        'graph_known_annotation_pairs': sum(len(v) for v in labels.values()),
        'future_GO_labels_read': False}


def author_modules(directory, receipt_path):
    """Import the unchanged external implementation only after its file checks."""
    directory, receipt_path = Path(directory).resolve(), Path(receipt_path).resolve()
    receipt = json.loads(receipt_path.read_text())
    need(receipt.get('commit') == AUTHOR_COMMIT and receipt.get('repository') == AUTHOR_REPOSITORY,
         'use the reviewed author revision and repository.')
    for relative, pin in receipt['files'].items():
        path = directory / relative
        need(not path.is_symlink() and path.is_file() and directory in path.resolve().parents
             and sha(path) == pin['sha256'], 'author source differs: ' + relative)
    from importlib import metadata
    need(all(metadata.version(k) == v for k, v in RUNTIME.items()), 'use the pinned isolated numerical runtime.')
    package = directory / 'src/annotation_prediction/src'
    name = '_biograph_published_fss_' + AUTHOR_COMMIT[:12]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, package / '__init__.py',
                                                    submodule_search_locations=[str(package)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return {key: importlib.import_module(name + '.algorithms.' + value)
            for key, value in {'alg_utils': 'alg_utils', 'fss': 'fastsinksource', 'gm': 'genemania'}.items()}


def adjacency(nodes, pairs):
    import numpy as np
    from scipy.sparse import csr_matrix
    index = {n: i for i, n in enumerate(nodes)}
    ii, jj, ww = [], [], []
    for a, b, weight in pairs:
        i, j = index[a], index[b]
        ii.extend((i, j)); jj.extend((j, i)); ww.extend((weight, weight))
    return csr_matrix((np.asarray(ww, dtype=np.float64), (ii, jj)), shape=(len(nodes), len(nodes)))


def run_term(modules, P, L, positives, method):
    """Call author functions; check convergence without changing their scores."""
    import numpy as np
    from scipy.sparse import eye
    n = P.shape[0]
    positives = np.asarray(sorted(positives), dtype=int)
    need(len(positives) > 0 and len(set(positives)) == len(positives), 'nonempty unique training positives required.')
    need(all(0 <= p < n for p in positives), 'training index outside the graph.')
    if method == 'localplus':
        scores, process, wall = modules['fss'].runLocal(P, positives)
        diagnostic = {'iterations': 1, 'process_seconds': process, 'wall_seconds': wall}
    elif method == 'fastsinksourceplus':
        scores, process, wall, iterations = modules['fss'].runFastSinkSource(P, positives, **PARAMETERS[method])
        unknown = np.ones(n, dtype=bool); unknown[positives] = False
        residual = float(np.abs(scores[unknown] - .8 * P.dot(scores)[unknown]).max()) if unknown.any() else 0.
        need(residual <= .0001001, 'published FSS iteration did not reach its declared tolerance.')
        diagnostic = {'iterations': iterations, 'max_unknown_equation_residual': residual,
                      'process_seconds': process, 'wall_seconds': wall}
    elif method == 'genemaniaplus':
        y = np.zeros(n); y[positives] = 1
        scores, process, wall, iterations = modules['gm'].runGeneMANIA(L, y, **PARAMETERS[method])
        residual = float(np.linalg.norm((eye(n) + L).dot(scores) - y))
        need(residual <= .0000101 * float(np.linalg.norm(y)), 'published GM conjugate gradient did not converge.')
        diagnostic = {'iterations': iterations, 'equation_residual_norm': residual,
                      'process_seconds': process, 'wall_seconds': wall}
    else:
        raise ValueError('Unsupported published prediction method.')
    need(scores.shape == (n,) and np.isfinite(scores).all(), 'nonfinite or incomplete model scores.')
    need(scores.min() >= -1e-10 and scores.max() <= 1 + 1e-10, 'published positive-only scores outside probability-like bounds.')
    return scores, diagnostic
