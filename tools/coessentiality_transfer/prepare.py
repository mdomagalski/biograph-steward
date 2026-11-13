"""Generic true-Gold/history source adapter for one prospective gene transfer.

Only generic native projection, historical qualification and control functions
are reused. No old learner packet, supervision, masks or proof format is faked.
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
from biograph_steward.file_utils import new_output, sha
from tools.reference_accuracy.design import need, read_rows, write_jsonl
from tools.coessentiality_transfer import sample
from tools.coessentiality_feasibility.transfer_source import verify_capture
from tools.coessentiality_feasibility.prepare import project, degree_control, degrees
from tools.coessentiality_feasibility.resource_allocation import native_runtime
from tools.coessentiality_feasibility.matrix import header_metadata
from tools.wiki_utility.prepare import memberships
from tools.wiki_utility.historical import select_history

FORMAT = 'biograph-steward.prospective-gene-transfer-context.v1'
COUNT_SEEDS = list(range(2026111303, 2026111323))
DEGREE_SEEDS = list(range(2026111304, 2026111324))
CODE = ['tools/coessentiality_transfer/sample.py', 'tools/coessentiality_transfer/prepare.py',
    'tools/coessentiality_transfer/__init__.py',
    'tools/coessentiality_transfer/matrix.py', 'tools/coessentiality_transfer/evaluate.py', 'tools/coessentiality_transfer/contract.md',
    'tools/coessentiality_feasibility/transfer_source.py', 'tools/coessentiality_feasibility/prepare.py',
    'tools/coessentiality_feasibility/compare.py', 'tools/coessentiality_feasibility/matrix.py',
    'tools/coessentiality_feasibility/resource_allocation.py', 'tools/wiki_utility/prepare.py', 'tools/wiki_utility/historical.py',
    'biograph_steward/wiki_history.py', 'biograph_steward/wiki_projection.py', 'biograph_steward/gold_packet.py',
    'biograph_steward/human_gene_relation.py', 'biograph_steward/cohort_mapping.py', 'biograph_steward/file_utils.py',
    'biograph_steward/client.py', 'tools/reference_accuracy/design.py', 'tools/sampled_audit/prepare.py']


def sealed(path):
    value = gold_packet._read(Path(path)); need(gold_packet._sealed(value), 'transfer source content seal differs')
    return value


def inventory(folder, report_name='report.json'):
    folder = Path(folder)
    need(not any(p.is_symlink() for p in [folder, *folder.rglob('*')]), 'symlink in transfer artifact')
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*')
            if p.is_file() and p != folder / report_name}


def co_context_coverage(genes, rows, primary_pairs):
    by_model = defaultdict(set)
    for gene, model in rows:
        by_model[model].add(gene)
    pairs = set()
    for members in by_model.values():
        pairs.update(itertools.combinations(sorted(members), 2))
    primary = pairs & set(map(tuple, primary_pairs))
    return {'membership_links': len(rows), 'genes_with_memberships': len({a for a, b in rows}),
        'model_nodes': len(by_model), 'co_context_pairs_all': len(pairs), 'co_context_pairs_primary': len(primary),
        'queries_with_any_co_context_partner': len({g for pair in pairs for g in pair}),
        'queries_with_primary_co_context_partner': len({g for pair in primary for g in pair}),
        'fixed_query_count': len(genes), 'zero_context_queries_retained': len(genes) - len({g for pair in primary for g in pair}),
        'is_reference_outcome_or_power_estimate': False}


def build_arms(ordinary, historical, permute):
    need(ordinary == sorted(set(map(tuple, ordinary))) and historical == sorted(set(map(tuple, historical))),
         'source membership lists are not normalized simple incidences')
    need(set(historical) <= set(ordinary), 'historical source view is not a subset of actual normalized source')
    need(historical and historical != ordinary, 'empty/identical source view is noninformative; do not reframe or force a comparison')
    arms = {'normalized': {'role': 'baseline', 'memberships': ordinary},
            'historical': {'role': 'treatment', 'memberships': historical}}
    for i, seed in enumerate(COUNT_SEEDS):
        arms[f'historical_count_{i:02}'] = {'role': 'primary_count_control', 'seed': seed,
            'memberships': sorted(random.Random(seed).sample(ordinary, len(historical)))}
    for i, seed in enumerate(DEGREE_SEEDS):
        rows, stats = degree_control(historical, permute, seed)
        arms[f'historical_degree_{i:02}'] = {'role': 'primary_degree_control', 'seed': seed, 'memberships': rows,
            'author_xswap_statistics': stats, 'both_full_frame_degree_vectors_verified': degrees(rows) == degrees(historical),
            'membership_overlap_with_historical': len(set(rows) & set(historical)), 'mixing_or_uniformity_established': False}
    need(len(arms) == 42, 'fixed42-arm design differs')
    return arms


def source_inputs(sample_directory, sample_seal, capture_directory, capture_seal, history_directory, history_seal, xswap_directory, reference_headers):
    paths = {k: Path(v).absolute() for k, v in dict(sample=sample_directory, capture=capture_directory,
                                                  history=history_directory, xswap=xswap_directory,
                                                  reference_headers=reference_headers).items()}
    sm, protocol, chosen = sample.verify(paths['sample'], expected_content_sha256=sample_seal)
    capture, source_chosen, ledger = verify_capture(paths['capture'], expected_content_sha256=capture_seal)
    need(source_chosen == chosen and capture['sample_content_sha256'] == sm['content_sha256']
         and capture['source_ready_for_comparison'] is True and capture['required_source_complete_genes'] == 128,
         'any required Pharos source failure/notfound/truncation/version drift makes comparison UNKNOWN')
    packet_manifest, graph = gold_packet.load_packet(paths['capture'] / 'source_packet')
    need(sha(paths['capture'] / 'source_packet/source/graph.json') == capture['source_graph_file_sha256'], 'actual Gold source graph differs')
    history_report = sealed(paths['history'] / 'historical_verification.json')
    need(history_report['content_sha256'] == history_seal and history_report['registry_sha256'] == protocol['registry_sha256']
         and history_report['source_graph_file_sha256'] == capture['source_graph_file_sha256']
         == sha(paths['history'].parent / 'original_graph.json'), 'history is not bound to the actual Gold graph/registry')
    need(inventory(paths['history'], 'historical_verification.json') == history_report['files'], 'native history byte inventory differs')
    registry_path = Path(sm['source_paths']['registry']); reg_manifest, registry = load_registry(registry_path)
    need(reg_manifest['registry_sha256'] == protocol['registry_sha256'], 'sample/history current registry differs')
    ordinary, projection_counts = memberships(graph)
    need(all(subject in {r['subject'] for r in chosen} for subject, relation, context in ordinary), 'source adds a non-sampled subject')
    qualified, qualified_counts, selection = select_history(paths['history'], history_seal, graph, ordinary)
    eligible = {r['ncbi_gene_id'] for r in chosen}
    normalized = project(ordinary, registry, eligible); historical = project(qualified, registry, eligible)
    build_receipt = sealed(ROOT / 'runs/wiki_utility_20261112/xswap_source_v1/build_receipt.json')
    for name, pin in build_receipt['installed_source_and_binary_sha256'].items():
        need(sha(paths['xswap'] / name) == pin, 'pinned native XSwap source/backend differs')
    sys.path.insert(0, str(paths['xswap'])); from xswap.permute import permute_edge_list
    pins = {str(paths['sample'] / 'report.json'): sha(paths['sample'] / 'report.json'),
        str(paths['capture'] / 'report.json'): sha(paths['capture'] / 'report.json'),
        str(paths['history'] / 'historical_verification.json'): sha(paths['history'] / 'historical_verification.json'),
        str(paths['history'].parent / 'original_graph.json'): capture['source_graph_file_sha256'],
        **{str(paths['capture'] / name): pin for name, pin in capture['files'].items()},
        **{str(paths['history'] / name): pin for name, pin in history_report['files'].items()},
        **{str(paths['xswap'] / name): pin for name, pin in build_receipt['installed_source_and_binary_sha256'].items()}}
    return paths, sm, protocol, chosen, capture, history_report, normalized, historical, selection, projection_counts, qualified_counts, pins, permute_edge_list


def packet_for(chosen, pairs, arms):
    genes = [{**r, 'current_canonical_chromosome': r['canonical_chromosome']} for r in chosen]
    return {'genes': genes, 'pairs': pairs, 'arms': arms, 'N': list(range(1, 11)), 'primary_scope': 'nonsyntenic',
        'reference_ranking': 'unsigned_native_two_sided_GLS_p_lexical_native_symbol_upper_triangle',
        'ranking_universe': 'eligible nonsyntenic partners within the sampled128 genes; not genomewide topN or significant positives',
        'ties': 'fractional_boundary_to_exact_N', 'all_queries_or_whole_N_UNKNOWN': True,
        'source_failure_or_notfound_is_not_valid_zero': True, 'count_seeds': COUNT_SEEDS, 'degree_seeds': DEGREE_SEEDS,
        'control_replicates_per_type': 20, 'RA_primary_binary_diagnostic': True,
        'current_GMT_or_other_method_arms': False, 'independent_experimental_confirmation': False}


def reference_proof(paths, sample_report):
    previous = sealed(Path(sample_report['source_paths']['old_capture']) / 'report.json')
    metadata = previous['matrix_metadata']; pins = {}
    for name in ['GLS_p.npy', 'GLS_sign.npy']:
        header = paths['reference_headers'] / (name + '.header')
        receipt_path = paths['reference_headers'] / (name + '.header.receipt.json')
        need(header.is_file() and receipt_path.is_file() and not header.is_symlink() and not receipt_path.is_symlink(),
             'native reference header/receipt is missing or symlinked')
        pins.update({str(header): sha(header), str(receipt_path): sha(receipt_path)})
        meta = header_metadata(header.read_bytes()); receipt = gold_packet._read(receipt_path)
        need(all(metadata[name][k] == v for k, v in meta.items()) and
             sha(header) == metadata[name]['native_header_sha256'] == receipt['header_sha256'] and
             receipt['url'] == metadata[name]['url'] and receipt['headers']['ETag'] == metadata[name]['etag'],
             'new reference headers do not bind the same original published matrices')
    return metadata, pins


def prepare(sample_directory, sample_seal, capture_directory, capture_seal, history_directory, history_seal, xswap_directory, reference_headers, output):
    code = {str(ROOT / name): sha(ROOT / name) for name in CODE}
    values = source_inputs(sample_directory, sample_seal, capture_directory, capture_seal, history_directory, history_seal, xswap_directory, reference_headers)
    paths, sm, protocol, chosen, capture, hist, ordinary, historical, selection, projection, qualification, pins, permute = values
    nx, runtime = native_runtime()  # Native code/version metadata only; no RA weights.
    reference_metadata, header_pins = reference_proof(paths, sm); pins.update(header_pins)
    pairs = read_rows(paths['sample'] / 'pairs.jsonl'); arms = build_arms(ordinary, historical, permute)
    genes = [r['ncbi_gene_id'] for r in chosen]; primary = [r['gene_pair'] for r in pairs if r['scope'] == 'nonsyntenic']
    coverage = {name: co_context_coverage(genes, data['memberships'], primary) for name, data in arms.items()}
    need(coverage['historical']['co_context_pairs_primary'] > 0, 'no nonzero historical primary co-context: enrichment is undefined; do not open new reference values')
    out = new_output(output, *paths.values())
    packet = packet_for(chosen, pairs, arms)
    write_json(out / 'packet.json', packet); write_json(out / 'source_coverage.json', coverage)
    write_json(out / 'source_historical_selection.json', selection)
    write_json(out / 'native_projection_and_qualification.json', {'projection': projection, 'historical': qualification})
    shutil.copyfile(Path(__file__).with_name('contract.md'), out / 'contract.md')
    proof = out / 'reference_headers'; proof.mkdir()
    for name, original in [('genes.txt', sm['source_paths']['genes']), ('gene_effect_header.csv', sm['source_paths']['header']),
        *[(name, str(paths['reference_headers'] / name)) for name in ['GLS_p.npy.header', 'GLS_p.npy.header.receipt.json',
                                                                'GLS_sign.npy.header', 'GLS_sign.npy.header.receipt.json']]]:
        shutil.copyfile(original, proof / name); pins[str(Path(original))] = sha(original)
    need(all(sha(p) == pin for p, pin in {**code, **pins}.items()), 'prospective source/code changed during pre-value freeze')
    report = {'format': FORMAT, 'created_at': utcnow(), 'sample_content_sha256': sample_seal,
        'capture_content_sha256': capture_seal, 'history_content_sha256': history_seal,
        'source_paths': {k: str(v) for k, v in paths.items()}, 'source_files_sha256': pins, 'implementation_sha256': code,
        'native_NetworkX': runtime, 'fixed_genes': len(chosen), 'all_pairs': len(pairs), 'primary_pairs': len(primary),
        'reference_metadata': reference_metadata,
        'arm_count': len(arms), 'source_ready': True, 'new_reference_values_opened_before_freeze': False,
        'source_only_analytic_RA_features_computed_during_coverage_review': True,
        'source_weighting_policy_changed_after_review': False, 'native_RA_reference_readout_executed_before_freeze': False,
        'prospective_new_genes_same_previously_consumed_reference': True, 'independent_study_confirmation': False,
        'biological_truth_or_production_pruning_measured': False, 'files': inventory(out)}
    report['content_sha256'] = digest(report); write_json(out / 'report.json', report)
    return report


def verify(directory, expected_content_sha256=None):
    directory = Path(directory); report = sealed(directory / 'report.json')
    need(report['format'] == FORMAT and (expected_content_sha256 is None or report['content_sha256'] == expected_content_sha256),
         'prospective transfer format/content pin differs')
    need(inventory(directory) == report['files'] and all(sha(p) == pin for p, pin in
         {**report['source_files_sha256'], **report['implementation_sha256']}.items()), 'transfer source/code/byte inventory differs')
    loc = report['source_paths']
    values = source_inputs(loc['sample'], report['sample_content_sha256'], loc['capture'], report['capture_content_sha256'],
                          loc['history'], report['history_content_sha256'], loc['xswap'], loc['reference_headers'])
    paths, sm, protocol, chosen, cap, hist, ordinary, historical, selection, projection, qualification, pins, permute = values
    reference_metadata, header_pins = reference_proof(paths, sm); pins.update(header_pins)
    need(reference_metadata == report['reference_metadata'], 'reference source/version metadata differs')
    for name, original in [('genes.txt', sm['source_paths']['genes']), ('gene_effect_header.csv', sm['source_paths']['header']),
        *[(name, str(paths['reference_headers'] / name)) for name in ['GLS_p.npy.header', 'GLS_p.npy.header.receipt.json',
                                                                'GLS_sign.npy.header', 'GLS_sign.npy.header.receipt.json']]]:
        need(sha(directory / 'reference_headers' / name) == sha(original), 'copied native gene/header source differs')
    need(all(report['source_files_sha256'].get(k) == v for k, v in pins.items()), 'transfer source inventory replay differs')
    pairs = read_rows(paths['sample'] / 'pairs.jsonl'); arms = build_arms(ordinary, historical, permute)
    replay = packet_for(chosen, pairs, arms); packet = gold_packet._read(directory / 'packet.json')
    need(digest(replay) == digest(packet), 'actual Gold/history gene-frame source/control/seed/role replay differs')
    genes = [r['ncbi_gene_id'] for r in chosen]; primary = [r['gene_pair'] for r in pairs if r['scope'] == 'nonsyntenic']
    need(gold_packet._read(directory / 'source_coverage.json') == {a: co_context_coverage(genes, d['memberships'], primary) for a, d in arms.items()}
         and selection == gold_packet._read(directory / 'source_historical_selection.json')
         and {'projection': projection, 'historical': qualification} == gold_packet._read(directory / 'native_projection_and_qualification.json'),
         'source-only coverage/native history ledger replay differs')
    nx, runtime = native_runtime()
    need(runtime == report['native_NetworkX'] and report['fixed_genes'] == 128 and report['arm_count'] == 42
         and report['primary_pairs'] == len(primary) and report['all_pairs'] == len(pairs)
         and report['new_reference_values_opened_before_freeze'] is False
         and report['source_only_analytic_RA_features_computed_during_coverage_review'] is True
         and report['source_weighting_policy_changed_after_review'] is False
         and report['native_RA_reference_readout_executed_before_freeze'] is False
         and report['independent_study_confirmation'] is False and report['source_ready'] is True,
         'prospective source/exposure/claim scope differs')
    return report, packet


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['sample', 'capture', 'history', 'xswap', 'reference-headers', 'out']:
        p.add_argument('--' + name, type=Path, required=True)
    for name in ['sample-seal', 'capture-seal', 'history-seal']:
        p.add_argument('--' + name, required=True)
    a = p.parse_args(); print(prepare(a.sample, a.sample_seal, a.capture, a.capture_seal, a.history, a.history_seal,
                                    a.xswap, a.reference_headers, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
