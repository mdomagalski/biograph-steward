"""Freeze the source-only gene-frame contrast before opening matrix values.

No new estimator, correlation pipeline or biological labels are introduced.
The author XSwap implementation is injected by the optional runtime.
"""
from collections import Counter, defaultdict
import argparse
import itertools
from pathlib import Path
import random
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.cohort_mapping import load_registry
from biograph_steward.file_utils import sha, new_output
from biograph_steward.human_gene_relation import gene_relationship
from tools.reference_accuracy.design import need
from tools.wiki_utility.prepare import verify as verify_wiki, RELATION
from tools.coessentiality_feasibility.identifiers import native_order, map_targets
from tools.coessentiality_feasibility.chromosome import canonical_chromosome

FORMAT = 'biograph-steward.coessentiality-frozen-comparison.v1'
REPLICATES = 20
IMPLEMENTATION = ['prepare.py', 'matrix.py', 'compare.py', 'contract.md', 'identifiers.py', 'chromosome.py']
SHARED_IMPLEMENTATION = ['biograph_steward/human_gene_relation.py', 'biograph_steward/cohort_mapping.py',
    'biograph_steward/gold_packet.py', 'biograph_steward/client.py', 'biograph_steward/file_utils.py',
    'biograph_steward/wiki_projection.py', 'biograph_steward/wiki_history.py',
    'tools/wiki_utility/prepare.py', 'tools/wiki_utility/historical.py']


def sealed(path):
    value = gold_packet._read(Path(path))
    need(gold_packet._sealed(value), 'source content seal differs: ' + str(path))
    return value


def degrees(rows):
    return {'gene': dict(sorted(Counter(a for a, b in rows).items())),
            'pathway': dict(sorted(Counter(b for a, b in rows).items()))}


def project(rows, registry, eligible):
    """Gene-product relationship projection, never protein identity."""
    result = set()
    for subject, relation, context in rows:
        if relation != RELATION:
            continue
        bridge = gene_relationship(subject, registry)
        need(bridge['qualified'], 'source protein lacks an unambiguous human gene relationship')
        if bridge['ncbi_gene_id'] in eligible:
            result.add((bridge['ncbi_gene_id'], context))
    return sorted(result)


def degree_control(rows, permute, seed):
    left, right = sorted({a for a, b in rows}), sorted({b for a, b in rows})
    li, ri = {a: i for i, a in enumerate(left)}, {b: i + len(left) for i, b in enumerate(right)}
    edges, stats = permute([(li[a], ri[b]) for a, b in rows], allow_self_loops=False,
        allow_antiparallel=True, multiplier=10, seed=seed, max_malloc=64 * 1024 * 1024)
    need(len(edges) == len(set(edges)) == len(rows), 'author degree null changed simple edge count')
    need(all(0 <= a < len(left) <= b < len(left) + len(right) for a, b in edges), 'degree null crossed types')
    result = sorted((left[a], right[b - len(left)]) for a, b in edges)
    need(degrees(result) == degrees(rows), 'degree null changed a measured-frame degree vector')
    need(result != rows, 'degree null did not change adjacency')
    return result, stats


def make_arms(current, historical, registry, eligible, permute):
    base = project(current['arms']['normalized_unqualified'], registry, eligible)
    need(base == project(historical['arms']['normalized_unqualified'], registry, eligible), 'source baselines differ')
    arms = {'normalized': {'role': 'baseline', 'memberships': base}}
    for label, packet in [('current', current), ('historical', historical)]:
        treatment = project(packet['arms']['fixed_qualified'], registry, eligible)
        need(set(treatment) < set(base), 'treatment must be a strict subset on the measured frame')
        arms[label] = {'role': 'treatment', 'memberships': treatment}
        for old in ['equal_count_random', 'qualified_degree_permutation']:
            rows = project(packet['arms'][old], registry, eligible)
            arms[label + '_legacy_' + old] = {'role': 'legacy_global_control_diagnostic', 'memberships': rows,
                'measured_count_matches': len(rows) == len(treatment),
                'measured_both_degrees_match': degrees(rows) == degrees(treatment)}
        for i in range(REPLICATES):
            seed = 2026111201 + i
            rows = sorted(random.Random(seed).sample(base, len(treatment)))
            arms[f'{label}_count_{i:02}'] = {'role': 'primary_count_control', 'treatment': label,
                'seed': seed, 'memberships': rows}
            seed = 2026111202 + i
            rows, stats = degree_control(treatment, permute, seed)
            arms[f'{label}_degree_{i:02}'] = {'role': 'primary_degree_control', 'treatment': label,
                'seed': seed, 'memberships': rows, 'author_xswap_statistics': stats,
                'membership_overlap_with_treatment': len(set(rows) & set(treatment)),
                'both_measured_degree_vectors_verified': True, 'mixing_or_uniformity_established': False}
    return arms


def replay_scope(scope, mapping_rows, registry, gene_text, header_text):
    """Recheck native index/Entrez/gene relationship and canonical chromosome frame."""
    targets = [{'uniprot': row['subject'].removeprefix('UniProtKB:'), 'sym': row['source_target_symbol']}
               for row in mapping_rows]
    need(map_targets(targets, registry, native_order(gene_text, header_text)) == mapping_rows,
         'native header/registry source mapping replay differs')
    native = {}
    for row in mapping_rows:
        if row['native_matrix_gene'] is not None:
            bridge = row['gene_product_relation']; n = row['native_matrix_gene']
            hgnc = registry.genes[bridge['hgnc_id']]
            entry = {'ncbi_gene_id': bridge['ncbi_gene_id'], 'hgnc_id': bridge['hgnc_id'],
                'source_row': bridge['hgnc_source_row'], 'native_matrix_index': n['matrix_index'],
                'native_matrix_symbol': n['native_symbol'], 'current_HGNC_location_literal': hgnc['location'],
                'current_canonical_chromosome': canonical_chromosome(hgnc['location']),
                'chromosome_is_cellline_somatic_karyotype': False}
            need(entry['current_canonical_chromosome'] is not None, 'unresolved canonical chromosome')
            key = bridge['ncbi_gene_id']; need(key not in native or native[key] == entry, 'ambiguous native gene mapping')
            native[key] = entry
    need(sorted(native.values(), key=lambda r: r['ncbi_gene_id']) == sorted(scope['genes'], key=lambda r: r['ncbi_gene_id']),
         'frozen gene/chromosome metadata differs from native registry/header replay')
    pairs = [{'gene_pair': [a, b], 'scope': 'syntenic' if native[a]['current_canonical_chromosome'] ==
              native[b]['current_canonical_chromosome'] else 'nonsyntenic',
              'native_matrix_indices': [native[a]['native_matrix_index'], native[b]['native_matrix_index']]}
             for a, b in itertools.combinations(sorted(native), 2)]
    need(pairs == scope['pairs'], 'full native-index/chromosome pair frame replay differs')
    return set(native)


def make_packet(scope, arms):
    return {'genes': scope['genes'], 'pairs': scope['pairs'], 'arms': arms,
        'ranking': 'native_lexical_symbol_upper_triangle_two_sided_GLS_p_ascending',
        'boundary_ties': 'fractional_to_exact_N', 'N': list(range(1, 11)),
        'primary_scope': 'nonsyntenic', 'primary_queries': 'all_92_at_every_N_or_point_unscorable',
        'sensitivities': ['all', 'syntenic', 'nonsyntenic_positive', 'nonsyntenic_negative'],
        'sensitivity_queries': 'common_reference_available_at_N_conditional_with_all_query_rows_preserved',
        'control_replicates': REPLICATES, 'no_null_uniformity_or_significance_claim': True}


def prepare(current, historical, registry, readiness, xswap, output):
    current, historical, registry, readiness, xswap = map(lambda p: Path(p).absolute(),
        (current, historical, registry, readiness, xswap))
    # Existing native source verifiers replay source qualification, arm construction,
    # graph canonical digests, masks and complete byte inventories; no outcomes.
    cr, cp = verify_wiki(current, code=False)
    hr, hp = verify_wiki(historical, code=False)
    reg_manifest, reg = load_registry(registry)
    source = sealed(readiness / 'readiness_v2.json')
    scope = sealed(readiness / 'chromosome_scope_v2.json')
    need(scope['registry_content_sha256'] == reg_manifest['registry_sha256'], 'chromosome/registry pin differs')
    build = sealed(ROOT / 'runs/wiki_utility_20261112/xswap_source_v1/build_receipt.json')
    for name, pin in build['installed_source_and_binary_sha256'].items():
        need(sha(xswap / name) == pin, 'native author XSwap installation differs')
    sys.path.insert(0, str(xswap))
    from xswap.permute import permute_edge_list
    mapping_rows = [gold_packet._decode(line) for line in
                    (readiness / 'identifier_gate_v1/primary_target_mapping.jsonl').read_bytes().splitlines()]
    eligible = replay_scope(scope, mapping_rows, reg, (readiness / 'genes.txt').read_text(),
                            (readiness / 'gene_effect_header.csv').read_text())
    need(len(eligible) == 92 and len(scope['pairs']) == 4186, 'fixed source/task population differs')
    need(source['matrix_values_read_or_saved'] is False, 'readiness already exposed matrix values')
    source_paths = [current / 'report.json', current / 'packet.json', historical / 'report.json', historical / 'packet.json',
        registry / 'manifest.json', readiness / 'readiness_v2.json', readiness / 'chromosome_scope_v2.json',
        readiness / 'identifier_gate_v1/report.json', readiness / 'identifier_gate_v1/primary_target_mapping.jsonl',
        readiness / 'genes.txt', readiness / 'gene_effect_header.csv', readiness / 'native_numpy_header_replay_v1.json',
        readiness / 'article_bioc.json', readiness / 'gene_pairs.py', readiness / 'modules.py', readiness / 'load_screens.py',
        readiness / 'LICENSE', readiness / 'known_issue_5.json',
        *[readiness / (n + suffix) for n in ['GLS_p.npy', 'GLS_sign.npy'] for suffix in ['.header', '.header.receipt.json']],
        *[xswap / name for name in build['installed_source_and_binary_sha256']]]
    pins = {str(p): sha(p) for p in source_paths}
    pins.update({str(registry / name): pin for name, pin in reg_manifest['files'].items()})
    implementations = {str(Path(__file__).parent / p): sha(Path(__file__).parent / p) for p in IMPLEMENTATION}
    implementations.update({str(ROOT / p): sha(ROOT / p) for p in SHARED_IMPLEMENTATION})
    arms = make_arms(cp, hp, reg, eligible, permute_edge_list)
    need([len(arms[a]['memberships']) for a in ['normalized', 'current', 'historical']] == [1922, 1275, 1020],
         'expected outcome-free source frame differs')
    out = new_output(output, current, historical, registry, readiness, xswap)
    proof = out / 'proof'; proof.mkdir()
    for name in ['readiness_v2.json', 'chromosome_scope_v2.json', 'genes.txt', 'gene_effect_header.csv',
                 'GLS_p.npy.header', 'GLS_sign.npy.header', 'GLS_p.npy.header.receipt.json', 'GLS_sign.npy.header.receipt.json',
                 'native_numpy_header_replay_v1.json', 'article_bioc.json', 'gene_pairs.py', 'modules.py', 'load_screens.py',
                 'LICENSE', 'known_issue_5.json']:
        shutil.copyfile(readiness / name, proof / name)
    shutil.copyfile(readiness / 'identifier_gate_v1/primary_target_mapping.jsonl', proof / 'primary_target_mapping.jsonl')
    shutil.copyfile(Path(__file__).parent / 'contract.md', out / 'contract.md')
    packet = make_packet(scope, arms)
    write_json(out / 'packet.json', packet)
    need(all(sha(p) == h for p, h in {**pins, **implementations}.items()), 'source/code changed during pre-value freeze')
    report = {'format': FORMAT, 'created_at': utcnow(), 'source_current_content_sha256': cr['content_sha256'],
        'source_historical_content_sha256': hr['content_sha256'], 'registry_sha256': reg_manifest['registry_sha256'],
        'source_deep_replay_completed': True, 'source_files_sha256': pins, 'implementation_sha256': implementations,
        'source_locations': {'current': str(current), 'historical': str(historical), 'registry': str(registry), 'xswap': str(xswap)},
        'matrix_values_decoded_or_persisted_before_freeze': False, 'essentiality_observation_rows_loaded': False,
        'supersedes_readiness_full_frame_control_claim': True,
        'header_scope_clarification': 'Only80headerbytes retained; no numeric values decoded/persisted; transport buffering not claimed.',
        'native_XSwap_build': build, 'arm_membership_counts': {a: len(v['memberships']) for a, v in arms.items()},
        'files': {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()}}
    report['content_sha256'] = digest(report); write_json(out / 'report.json', report)
    return report


def verify(folder, code=True):
    folder = Path(folder); report = sealed(folder / 'report.json')
    need(report['format'] == FORMAT, 'frozen comparison format differs')
    need(not any(p.is_symlink() for p in [folder, *folder.rglob('*')]), 'symlink in frozen comparison')
    inventory = {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file() and p != folder / 'report.json'}
    need(inventory == report['files'], 'frozen comparison file inventory differs')
    if code:
        need(all(sha(p) == h for p, h in report['implementation_sha256'].items()), 'frozen implementation differs')
    need(all(Path(p).is_file() and not Path(p).is_symlink() and sha(p) == h
             for p, h in report['source_files_sha256'].items()), 'frozen source input pins differ')
    locations = {k: Path(v) for k, v in report['source_locations'].items()}
    reg_manifest, registry = load_registry(locations['registry'])
    need(reg_manifest['registry_sha256'] == report['registry_sha256'], 'registry content pin differs')
    packets = {}
    for key in ['current', 'historical']:
        source = sealed(locations[key] / 'report.json')
        need(source['content_sha256'] == report['source_' + key + '_content_sha256'], 'source packet content differs')
        need(sha(locations[key] / 'packet.json') == source['files']['packet.json'], 'source packet byte pin differs')
        packets[key] = gold_packet._read(locations[key] / 'packet.json')
    scope = sealed(folder / 'proof/chromosome_scope_v2.json')
    mapping_rows = [gold_packet._decode(line) for line in (folder / 'proof/primary_target_mapping.jsonl').read_bytes().splitlines()]
    eligible = replay_scope(scope, mapping_rows, registry, (folder / 'proof/genes.txt').read_text(),
                            (folder / 'proof/gene_effect_header.csv').read_text())
    sys.path.insert(0, str(locations['xswap']))
    from xswap.permute import permute_edge_list
    replayed = make_packet(scope, make_arms(packets['current'], packets['historical'], registry, eligible, permute_edge_list))
    packet = gold_packet._read(folder / 'packet.json')
    # JSON serializes native tuples as lists; canonical bytes compare equivalent types.
    need(digest(packet) == digest(replayed), 'source gene frame, arm, seed, role or scoring contract replay differs')
    return report, packet


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['current', 'historical', 'registry', 'readiness', 'xswap', 'out']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); print(prepare(a.current, a.historical, a.registry, a.readiness, a.xswap, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
