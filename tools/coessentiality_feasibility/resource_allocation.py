"""One consumed-reference, native NetworkX RA context readout.

This weights observed shared source models, not edge truth or a prune policy.
The existing binary-context experiment and all its protected helpers stay fixed.
"""
from collections import Counter
import argparse
import gzip
import importlib
import importlib.metadata
import inspect
import math
import os
from pathlib import Path
import shutil
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import canonical, digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.reference_accuracy.design import need
from tools.coessentiality_feasibility.prepare import verify as verify_source, sealed
from tools.coessentiality_feasibility import matrix
from tools.coessentiality_feasibility.compare import pair_values, reference_partners, fractional_top

FROZEN = 'biograph-steward.exploratory-RA-context-freeze.v1'
SCORED = 'biograph-steward.exploratory-RA-context-result.v1'


def inventory(folder):
    folder = Path(folder)
    need(not any(p.is_symlink() for p in [folder, *folder.rglob('*')]), 'symlink in RA input')
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file() and p != folder / 'report.json'}


def checked_report(folder):
    report = sealed(Path(folder) / 'report.json')
    need(inventory(folder) == report['files'], 'RA input byte inventory differs')
    return report


def native_runtime():
    import networkx as nx
    need(nx.__version__ == '3.7', 'this frozen RA extension requires the reviewed NetworkX3.7 runtime')
    need(os.environ.get('PYTHONHASHSEED') == '2026111301', 'set PYTHONHASHSEED=2026111301 for native common-neighbor sum order')
    names = ['networkx.algorithms.link_prediction', 'networkx.classes.graph', 'networkx.classes.function',
             'networkx.utils.decorators', 'networkx.utils.backends']
    paths = [Path(importlib.import_module(name).__file__).absolute() for name in names]
    distribution = importlib.metadata.distribution('networkx')
    licenses = [Path(distribution.locate_file(name)).absolute() for name in distribution.files
                if 'licenses' in str(name) and Path(name).name.startswith('LICENSE')]
    need(licenses, 'native NetworkX license proof not found')
    return nx, {'version': nx.__version__, 'backend': 'networkx', 'PYTHONHASHSEED': os.environ['PYTHONHASHSEED'],
        'function': 'networkx.resource_allocation_index',
        'function_source_sha256': digest(inspect.getsource(inspect.unwrap(nx.resource_allocation_index))),
        'source_files_sha256': {str(path): sha(path) for path in paths + licenses},
        'license': 'BSD-3-Clause', 'license_files': [str(p) for p in licenses]}


def native_scores(genes, memberships, pairs, nx):
    """Native RA on full-frame simple bipartite incidence; no custom formula."""
    need(len(memberships) == len(set(map(tuple, memberships))), 'RA memberships repeat')
    need(len(genes) == len(set(genes)), 'RA query genes repeat')
    need(len(pairs) == len(set(map(tuple, pairs))) and all(a != b for a, b in pairs), 'RA pairs repeat or self-pair')
    graph = nx.Graph(); graph.add_nodes_from(('gene', g) for g in genes)
    for gene, context in memberships:
        need(gene in genes, 'RA membership outside fixed measured frame')
        graph.add_edge(('gene', gene), ('source_version', context))
    ebunch = [(('gene', a), ('gene', b)) for a, b in pairs]
    predictions = list(nx.resource_allocation_index(graph, ebunch=ebunch, backend='networkx'))
    need(len(predictions) == len(pairs), 'native RA omitted a requested pair')
    weights = {}
    for (u, v, value), (a, b) in zip(predictions, pairs):
        need(u == ('gene', a) and v == ('gene', b), 'native RA pair order/type differs')
        value = float(value)
        need(math.isfinite(value) and value >= 0, 'native RA produced an invalid affinity')
        weights[(a, b)] = value
    model_degrees = {node[1]: graph.degree(node) for node in graph if node[0] == 'source_version'}
    return weights, {'query_nodes_including_isolates': len(genes), 'membership_edges': graph.number_of_edges(),
        'model_nodes': len(model_degrees), 'full_frame_model_degrees': dict(sorted(model_degrees.items())),
        'degree_rebuilt_per_query_or_chromosome': False, 'degree_is_full_biological_pathway_size': False}


def weighted_point(genes, partners, selections, weights, n):
    observed = expected = 0.0; rows = []; available = 0
    for gene in genes:
        candidates = partners[gene]; selected = selections[gene]
        score = lambda other: weights[tuple(sorted([gene, other]))]
        if selected is None:
            rows.append({'gene': gene, 'reference_partners': len(candidates), 'status': 'UNKNOWN_fewer_than_N_partners',
                         'observed_weighted_sum': None, 'expected_weighted_sum': None})
            continue
        value = math.fsum(score(other) * fraction for other, fraction in selected['selected'])
        background = n * math.fsum(score(other) for other, p in candidates) / len(candidates)
        rows.append({'gene': gene, 'reference_partners': len(candidates), 'status': 'scorable',
                     'observed_weighted_sum': value, 'expected_weighted_sum': background})
        observed += value; expected += background; available += 1
    complete = available == len(genes); slots = len(genes) * n
    return {'N': n, 'fixed_queries': len(genes), 'available_queries': available,
        'status': 'scorable' if complete else 'UNKNOWN_incomplete_fixed_query_frame',
        'selected_slots': slots if complete else None,
        'observed_weighted_sum': observed if complete else None, 'expected_weighted_sum': expected if complete else None,
        'observed_mean_RA_per_slot': observed / slots if complete else None,
        'expected_mean_RA_per_slot': expected / slots if complete else None,
        'enrichment': observed / expected if complete and expected > 0 else None,
        'zero_expected_enrichment_undefined': complete and expected == 0, 'queries': rows}


def freeze(source_frozen, captured, prior_scored, output):
    source_frozen, captured, prior_scored = map(lambda p: Path(p).absolute(), (source_frozen, captured, prior_scored))
    source_report, packet = verify_source(source_frozen)
    capture_report, original = checked_report(captured), checked_report(prior_scored)
    need(original['format'] == 'biograph-steward.coessentiality-functional-concordance.v1' and
         original['frozen_comparison_content_sha256'] == source_report['content_sha256'] and
         original['native_capture_content_sha256'] == capture_report['content_sha256'], 'consumed source/reference lineage differs')
    nx, runtime = native_runtime()  # Only inspect native code/version; no RA computed here.
    out = new_output(output, source_frozen, captured, prior_scored)
    shutil.copyfile(source_frozen / 'packet.json', out / 'source_packet.json')
    for name in ['native_pair_values.jsonl', 'reference_rank_selections.jsonl']:
        shutil.copyfile(prior_scored / name, out / name)
    shutil.copyfile(Path(__file__).with_name('ra_contract.md'), out / 'contract.md')
    locations = {'source_frozen': str(source_frozen), 'captured': str(captured), 'prior_scored': str(prior_scored)}
    source_pins = {str(Path(path) / 'report.json'): sha(Path(path) / 'report.json') for path in locations.values()}
    for folder in [captured, prior_scored]:
        source_pins.update({str(folder / name): pin for name, pin in checked_report(folder)['files'].items()})
    code = {str(Path(__file__).absolute()): sha(__file__),
            str(Path(__file__).with_name('ra_contract.md').absolute()): sha(Path(__file__).with_name('ra_contract.md'))}
    need(digest(packet) == digest(gold_packet._read(out / 'source_packet.json')), 'copied source packet differs')
    need(all(sha(p) == pin for p, pin in source_pins.items()), 'source changed during RA freeze')
    report = {'format': FROZEN, 'created_at': utcnow(), 'source_locations': locations,
        'source_frozen_content_sha256': source_report['content_sha256'],
        'initial_pre_value_scientific_freeze': source_report.get('original_pre_value_scientific_freeze_content_sha256'),
        'already_consumed_binary_result_content_sha256': original['content_sha256'],
        'reference_previously_inspected': True, 'new_RA_weights_computed_before_this_freeze': False,
        'native_NetworkX': runtime, 'query_genes': len(packet['genes']),
        'primary_pairs': sum(p['scope'] == 'nonsyntenic' for p in packet['pairs']),
        'source_arm_count': len(packet['arms']), 'N': list(range(1, 11)),
        'source_files_sha256': source_pins, 'implementation_sha256': code, 'files': inventory(out),
        'production_graph_or_prior_results_changed': False}
    report['content_sha256'] = digest(report); write_json(out / 'report.json', report)
    return report


def verify(folder):
    folder = Path(folder); report = checked_report(folder)
    need(report['format'] == FROZEN, 'RA frozen format differs')
    need(all(sha(p) == h for p, h in {**report['source_files_sha256'], **report['implementation_sha256']}.items()),
         'RA source/code pin differs')
    nx, runtime = native_runtime(); need(runtime == report['native_NetworkX'], 'native RA runtime differs')
    source, packet = verify_source(report['source_locations']['source_frozen'])
    need(source['content_sha256'] == report['source_frozen_content_sha256'] and
         digest(packet) == digest(gold_packet._read(folder / 'source_packet.json')), 'RA source frame/arms differ')
    return report, packet, nx


def evaluate(frozen, output):
    frozen = Path(frozen).absolute(); report, packet, nx = verify(frozen)
    locations = report['source_locations']
    capture, bound_packet, arrays = matrix.load(locations['source_frozen'], locations['captured'])
    need(digest(bound_packet) == digest(packet), 'RA raw reference/source binding differs')
    pairs = pair_values(packet, arrays)
    saved = [gold_packet._decode(line) for line in (frozen / 'native_pair_values.jsonl').read_bytes().splitlines()]
    need(pairs == saved, 'RA consumed native pair ledger differs from raw range replay')
    rank_rows = [gold_packet._decode(line) for line in (frozen / 'reference_rank_selections.jsonl').read_bytes().splitlines()]
    native_ranks = {row['N']: row for row in rank_rows if row['scope'] == 'nonsyntenic'}
    genes = sorted(g['ncbi_gene_id'] for g in packet['genes'])
    primary = [p['gene_pair'] for p in packet['pairs'] if p['scope'] == 'nonsyntenic']
    partners = reference_partners(genes, pairs, 'nonsyntenic')
    selections = {n: {g: fractional_top(partners[g], n) for g in genes} for n in report['N']}
    for n in report['N']:
        expected = {'scope': 'nonsyntenic', 'N': n, 'queries': [
            {'gene': g, 'available_reference_partners': len(partners[g]), 'selection': selections[n][g]} for g in genes]}
        need(digest(expected) == digest(native_ranks[n]), 'RA changed a consumed native GLS selection or availability mask')
    out = new_output(output, frozen, *locations.values())
    curves = {}; model_degrees = {}
    with gzip.GzipFile(filename=str(out / 'native_RA_scores.jsonl.gz'), mode='wb', mtime=0) as weights_file, \
         gzip.GzipFile(filename=str(out / 'per_query_scores.jsonl.gz'), mode='wb', mtime=0) as query_file:
        for arm, data in packet['arms'].items():
            weights, metadata = native_scores(genes, data['memberships'], primary, nx)
            model_degrees[arm] = metadata; curves[arm] = []
            for (a, b), value in weights.items():
                weights_file.write((canonical({'arm': arm, 'gene_pair': [a, b], 'RA': value}) + '\n').encode())
            for n in report['N']:
                point = weighted_point(genes, partners, selections[n], weights, n)
                rows = point.pop('queries'); curves[arm].append(point)
                query_file.write((canonical({'arm': arm, 'N': n, 'queries': rows}) + '\n').encode())
    envelopes = {}; assessment = {}
    for treatment in ['current', 'historical']:
        envelopes[treatment] = {}
        for kind in ['count', 'degree']:
            names = [f'{treatment}_{kind}_{i:02}' for i in range(packet['control_replicates'])]
            envelope = []
            for index, n in enumerate(report['N']):
                values = [curves[arm][index]['enrichment'] for arm in names]
                finite = [v for v in values if v is not None]
                envelope.append({'N': n, 'draws': len(values), 'defined_draws': len(finite),
                    'minimum': min(finite) if finite else None, 'median': statistics.median(finite) if finite else None,
                    'maximum': max(finite) if finite else None, 'not_a_confidence_interval': True})
            envelopes[treatment][kind] = envelope
        names = ['normalized'] + [f'{treatment}_{kind}_{i:02}' for kind in ['count', 'degree']
                                   for i in range(packet['control_replicates'])]
        points = []
        for index, n in enumerate(report['N']):
            value = curves[treatment][index]['enrichment']; other = [curves[a][index]['enrichment'] for a in names]
            defined = value is not None and all(v is not None for v in other)
            points.append({'N': n, 'all_defined': defined,
                'exceeds_normalized_and_all_40_draws': defined and all(value > v + 1e-12 for v in other)})
        assessment[treatment] = {'points': points, 'project_descriptive_full_curve_rule_met': all(
            p['exceeds_normalized_and_all_40_draws'] for p in points), 'statistical_significance': False}
    write_json(out / 'curves.json', curves); write_json(out / 'control_envelopes.json', envelopes)
    write_json(out / 'full_frame_model_degrees.json', model_degrees)
    verify(frozen)
    result = {'format': SCORED, 'created_at': utcnow(), 'frozen_RA_content_sha256': report['content_sha256'],
        'frozen_RA_report_file_sha256': sha(frozen / 'report.json'), 'already_consumed_binary_result':
        report['already_consumed_binary_result_content_sha256'], 'reference_status': 'consumed_exploratory_extension',
        'reference_raw_and_original_GLS_rank_replay_passed': True, 'native_NetworkX': report['native_NetworkX'],
        'query_genes': len(genes), 'primary_pairs': len(primary), 'source_arms': len(curves), 'N': report['N'],
        'full_curve_descriptive_assessment': assessment, 'code_file_sha256': sha(__file__),
        'calibrated_accuracy_negative_or_prune_labels_created': False, 'production_graph_changed': False,
        'limitations': ['RA is cohort-local weighted co-context affinity, not biological probability or full pathway specificity.',
            'Same native GLS reference was consumed before this extension; this is not fresh confirmation.',
            'Fixed20draw control envelopes do not establish uniform null, mixing, uncertainty or statistical significance.',
            'Observed source degree is incomplete and correlated source versions do not constitute independent evidence.',
            'Pan-cancer fitness association does not establish physical binding, CRC-specific causal mechanism or clinical usefulness.'],
        'files': inventory(out)}
    result['content_sha256'] = digest(result); write_json(out / 'report.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze')
    for name in ['source-frozen', 'captured', 'prior-scored', 'out']:
        f.add_argument('--' + name, type=Path, required=True)
    s = sub.add_parser('evaluate'); s.add_argument('--frozen', type=Path, required=True); s.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    value = freeze(a.source_frozen, a.captured, a.prior_scored, a.out) if a.command == 'freeze' else evaluate(a.frozen, a.out)
    print(value['content_sha256'])


if __name__ == '__main__':
    main()
