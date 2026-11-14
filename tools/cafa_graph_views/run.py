"""Apply existing frozen graph masks to one unchanged published predictor.

The primary model comparison remains untouched. This secondary comparison asks
whether previously defined graph interventions improve recovery of later GO
curations under the same algorithm, training labels, proteins and vocabulary.
No reference outcomes are accepted by preparation or prediction.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
from pathlib import Path
import time

from biograph_steward.client import digest as native_digest
from tools.cafa_prediction.core import adjacency, author_modules, need, run_term, sha
from tools.cafa_prediction.run import (digest, load_frozen, new_output, pin, read,
                                       timestamp, verify_pins, write)

FORMAT = 'biograph-steward.cafa5-frozen-graph-view-predictions.v1'
VIEWS = ('native_top80', 'human_experimental_top80', 'ne_top80')
MEMBERSHIP_HEADER = ['pair_id', 'unpruned', 'native_top80', 'pa_top80', 'ne_top80',
                     'human_experimental_top80', 'mps_top80', 'combined_experimental_top80']


def subset_graphs(graph, weighted_rows, membership, *, expected_source_rows):
    """Keep literal native weights and every node; require one common fixed mask frame."""
    rows = {r['pair_id']: r for r in weighted_rows}
    need(len(rows) == len(weighted_rows), 'weighted pair identities repeat.')
    before = {tuple(sorted((a, b))): float(w) for a, b, w in graph['pairs']}
    projected = {tuple(sorted((r['subject'], r['object']))): float(r['weight']) for r in weighted_rows}
    need(len(projected) == len(weighted_rows) and before == projected,
         'weighted source differs from the frozen parent graph.')
    masks = {r['pair_id']: r for r in membership}
    need(len(masks) == len(membership) == expected_source_rows and set(rows) <= set(masks),
         'membership is duplicated, partial or missing weighted source pairs.')
    need(all(set(r) == set(MEMBERSHIP_HEADER) and r['unpruned'] == 'true'
             and all(r[k] in {'true', 'false'} for k in MEMBERSHIP_HEADER[1:])
             for r in membership), 'invalid frozen membership schema or boolean.')
    result = {}
    for view in VIEWS:
        pairs = [[r['subject'], r['object'], float(r['weight'])] for r in weighted_rows
                 if masks[r['pair_id']][view] == 'true']
        need(pairs and len(pairs) < len(before), 'a graph intervention must retain a proper nonempty subset.')
        result[view] = {'nodes': graph['nodes'], 'pairs': pairs}
    need(len({len(g['pairs']) for g in result.values()}) == 1,
         'these fixed graph comparisons require equal retained weighted edge budgets.')
    return result


def prepare(parent, parent_sha256, mask_protocol, membership, output):
    parent = Path(parent).resolve()
    original = load_frozen(parent, parent_sha256)
    protocol, membership = Path(mask_protocol).resolve(), Path(membership).resolve()
    mask = read(protocol)
    need(mask.get('format') == 'biograph-steward.optional-source-connectivity-safeguard.v1'
         and mask.get('content_sha256') == native_digest({k: v for k, v in mask.items() if k != 'content_sha256'}),
         'the existing sealed source-connectivity policy is required.')
    need(mask['outputs_sha256']['membership.tsv'] == sha(membership), 'existing membership bytes differ.')
    source_pin = original['input_pins']['network_qualification']
    source_keys = [k for k in mask['inputs_sha256'] if k.endswith('/qualified_input/source_qualification.json')]
    need(len(source_keys) == 1 and mask['inputs_sha256'][source_keys[0]] == source_pin['sha256'],
         'mask policy and parent network qualifications differ.')
    qualification = read(source_pin['file'])
    with Path(original['input_pins']['weighted_pairs']['file']).open(newline='') as stream:
        weighted_rows = list(csv.DictReader(stream, delimiter='\t'))
    with membership.open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        need(reader.fieldnames == MEMBERSHIP_HEADER, 'existing membership header differs.')
        members = list(reader)
    graphs = subset_graphs(read(parent/'graph.json.gz'), weighted_rows, members,
                           expected_source_rows=qualification['original_source_pairs'])
    folder = new_output(output)
    write(folder/'graphs.json.gz', graphs)
    value = {'format': FORMAT + '.freeze', 'created_at': timestamp(),
        'parent_frozen': str(parent), 'parent_protocol_file_sha256': parent_sha256,
        'parent_protocol_content_sha256': original['content_sha256'],
        'input_pins': {'mask_protocol': pin(protocol), 'membership': pin(membership), 'adapter': pin(__file__)},
        'method': 'unchanged author FastSinkSourcePlus with exactly the parent defaults; native weights only',
        'graph_views': list(VIEWS), 'baseline': 'parent unpruned FastSinkSourcePlus output',
        'counts': {view: {'nodes': len(g['nodes']), 'weighted_edges': len(g['pairs'])} for view, g in graphs.items()},
        'future_GO_labels_opened': False, 'new_graph_thresholds_or_source_scores': False,
        'selection_history': 'Existing views were developed using earlier other-reference studies. Their CAFA5 transfer is tested here; they were not selected from CAFA5 outcomes.',
        'endpoint': 'Secondary paired CAFA5 PK BPO micro Fmax; MF/CC and weighted/macro metrics remain secondary.',
        'interpretation': 'Function-reference recovery under altered topology is not universal edge correctness or a justified biological pruning label.',
        'connectivity_scope': 'The old safeguard preserves full-source components. Numerical matrices include only qualified weighted STRING rows; their actual components and isolates are measured separately.',
        'files': {'graphs.json.gz': sha(folder/'graphs.json.gz')}}
    value['content_sha256'] = digest(value)
    write(folder/'protocol.json', value)
    return value


def load_view(folder, expected):
    folder = Path(folder)
    value = read(folder/'protocol.json')
    need(sha(folder/'protocol.json') == expected and value.get('format') == FORMAT + '.freeze'
         and value['content_sha256'] == digest({k: v for k, v in value.items() if k != 'content_sha256'}),
         'graph-view protocol binding differs.')
    verify_pins(value['input_pins'])
    need(set(p.name for p in folder.iterdir()) == {'protocol.json', *value['files']}, 'graph-view inventory differs.')
    for name, checksum in value['files'].items():
        need(sha(folder/name) == checksum, 'frozen graph-view bytes differ.')
    parent = load_frozen(value['parent_frozen'], value['parent_protocol_file_sha256'])
    need(parent['content_sha256'] == value['parent_protocol_content_sha256'], 'parent source seal differs.')
    return value, parent


def predict(frozen, protocol_sha256, output):
    import numpy as np
    from scipy.sparse.csgraph import connected_components
    frozen = Path(frozen)
    view, parent = load_view(frozen, protocol_sha256)
    base = Path(view['parent_frozen'])
    modules = author_modules(parent['author_directory'], parent['author_receipt'])
    labels = read(base/'training.json.gz')
    graphs = read(frozen/'graphs.json.gz')
    targets = (base/'targets.txt').read_text().splitlines()
    graph = read(base/'graph.json.gz')
    nodes = graph['nodes']; index = {p.split(':', 1)[1]: i for i, p in enumerate(nodes)}
    target_index = np.asarray([index[p] for p in targets], dtype=int)
    by_term = defaultdict(list)
    for protein, entries in labels.items():
        for aspect, term in entries:
            by_term[(aspect, term)].append(index[protein])
    folder = new_output(output)
    write(folder/'execution_started.json', {'at': timestamp(), 'protocol_file_sha256': protocol_sha256,
        'future_GO_labels_opened': False})
    diagnostics, summaries = [], {}
    for name in VIEWS:
        current = graphs[name]
        need(current['nodes'] == nodes, 'pruned view removed or reordered a node.')
        W = adjacency(nodes, current['pairs'])
        P = modules['alg_utils'].normalizeGraphEdgeWeights(W)
        degree = np.asarray(W.sum(axis=1)).reshape(-1)
        components = connected_components(W, directed=False, return_labels=False)
        start = time.time(); emitted = 0
        with gzip.GzipFile(filename=str(folder/(name+'.tsv.gz')), mode='wb', mtime=0) as stream:
            for step, ((aspect, term), positive) in enumerate(sorted(by_term.items()), 1):
                scores, diagnostic = run_term(modules, P, None, positive, 'fastsinksourceplus')
                for protein, score in zip(targets, scores[target_index]):
                    if score > 0:
                        stream.write((protein+'\t'+term+'\t'+format(float(score), '.17g')+'\n').encode())
                        emitted += 1
                diagnostics.append({'view': name, 'aspect': aspect, 'term': term, **diagnostic})
                if step % 2000 == 0:
                    print({'view': name, 'terms': step, 'total': len(by_term), 'seconds': time.time()-start}, flush=True)
        summaries[name] = {'nodes': len(nodes), 'weighted_edges': len(current['pairs']),
            'isolates': int((degree == 0).sum()), 'weighted_components': int(components),
            'target_IDs': len(targets), 'positive_scores_emitted': emitted, 'seconds': time.time()-start}
    write(folder/'algorithm_diagnostics.json.gz', diagnostics)
    load_view(frozen, protocol_sha256)
    result = {'format': FORMAT, 'at': timestamp(), 'protocol_file_sha256': protocol_sha256,
        'protocol_content_sha256': view['content_sha256'], 'summaries': summaries,
        'reference_labels_read': False, 'model_calls': 0, 'source_fetches': 0,
        'files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in folder.iterdir()}}
    result['content_sha256'] = digest(result); write(folder/'predictions.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    for name in ('parent', 'parent-sha256', 'mask-protocol', 'membership', 'output'):
        p.add_argument('--'+name, required=True)
    p = commands.add_parser('predict')
    for name in ('frozen', 'protocol-sha256', 'output'):
        p.add_argument('--'+name, required=True)
    values = vars(parser.parse_args()); command = values.pop('command')
    result = prepare(**values) if command == 'prepare' else predict(**values)
    print({'format': result['format'], 'content_sha256': result['content_sha256']})


if __name__ == '__main__': main()
