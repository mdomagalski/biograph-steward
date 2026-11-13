"""Fixed prospective gene-transfer RA readout with binary context diagnostic.

No learner, new significance threshold, negative truth labels or production
prune decision is introduced. Every fixed query and N remains represented.
"""
from collections import Counter
import argparse
import gzip
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import canonical, digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.reference_accuracy.design import need, write_jsonl
from tools.coessentiality_transfer import matrix
from tools.coessentiality_transfer.prepare import verify, inventory
from tools.coessentiality_feasibility.compare import pair_values, reference_partners, fractional_top, shared_partners, curve_point
from tools.coessentiality_feasibility.resource_allocation import native_runtime, native_scores, weighted_point

FORMAT = 'biograph-steward.prospective-gene-transfer-result.v1'


def envelopes(curves, metric):
    out = {}
    for kind in ['count', 'degree']:
        names = [f'historical_{kind}_{i:02}' for i in range(20)]
        points = []
        for index in range(10):
            values = [curves[arm][metric][index]['enrichment'] for arm in names]
            defined = [v for v in values if v is not None]
            points.append({'N': index + 1, 'draws': len(values), 'defined_draws': len(defined),
                'minimum': min(defined) if defined else None, 'median': statistics.median(defined) if defined else None,
                'maximum': max(defined) if defined else None, 'not_a_confidence_interval': True})
        out[kind] = points
    return out


def assessment(curves, metric):
    controls = ['normalized'] + [f'historical_{kind}_{i:02}' for kind in ['count', 'degree'] for i in range(20)]
    points = []
    for index in range(10):
        value = curves['historical'][metric][index]['enrichment']
        others = [curves[arm][metric][index]['enrichment'] for arm in controls]
        defined = value is not None and all(v is not None for v in others)
        points.append({'N': index + 1, 'all_defined': defined,
                       'historical_exceeds_normalized_and_all_40_draws': defined and all(value > v + 1e-12 for v in others)})
    return {'points': points, 'project_descriptive_full_curve_rule_met': all(
        p['historical_exceeds_normalized_and_all_40_draws'] for p in points),
        'is_primary': metric == 'RA', 'is_statistical_significance': False}


def evaluate(frozen, captured, output):
    frozen, captured = Path(frozen).absolute(), Path(captured).absolute()
    code = sha(__file__); frozen_report, packet = verify(frozen)
    capture_report, bound, arrays = matrix.load(frozen, captured)
    need(digest(packet) == digest(bound), 'prospective source/reference frame binding differs')
    nx, runtime = native_runtime(); need(runtime == frozen_report['native_NetworkX'], 'prospective RA runtime differs')
    pins = {str(frozen / 'report.json'): sha(frozen / 'report.json'), str(captured / 'report.json'): sha(captured / 'report.json')}
    genes = sorted(g['ncbi_gene_id'] for g in packet['genes'])
    pairs = pair_values(packet, arrays); primary = [p['gene_pair'] for p in packet['pairs'] if p['scope'] == 'nonsyntenic']
    partners = reference_partners(genes, pairs, 'nonsyntenic')
    selections = {n: {g: fractional_top(partners[g], n) for g in genes} for n in packet['N']}
    rank_ledger = [{'N': n, 'scope': 'nonsyntenic', 'ranking_universe': 'within fixed sampled128 genes, not genomewide',
        'queries': [{'gene': g, 'reference_available_partners': len(partners[g]), 'selection': selections[n][g]} for g in genes]}
        for n in packet['N']]
    out = new_output(output, frozen, captured)
    write_jsonl(out / 'native_pair_values.jsonl', pairs); write_jsonl(out / 'reference_rank_selections.jsonl', rank_ledger)
    curves = {}; degree_ledger = {}
    with gzip.GzipFile(filename=str(out / 'native_RA_scores.jsonl.gz'), mode='wb', mtime=0) as score_file, \
         gzip.GzipFile(filename=str(out / 'per_query_scores.jsonl.gz'), mode='wb', mtime=0) as query_file:
        for arm, data in packet['arms'].items():
            weights, metadata = native_scores(genes, data['memberships'], primary, nx)
            degree_ledger[arm] = metadata; curves[arm] = {'RA': [], 'binary_diagnostic': []}
            adjacency = shared_partners(genes, data['memberships'])
            for (a, b), value in weights.items():
                score_file.write((canonical({'arm': arm, 'gene_pair': [a, b], 'RA': value}) + '\n').encode())
            for n in packet['N']:
                ra = weighted_point(genes, partners, selections[n], weights, n)
                binary = curve_point(genes, partners, selections[n], adjacency, n, True)
                for metric, point in [('RA', ra), ('binary_diagnostic', binary)]:
                    rows = point.pop('queries'); curves[arm][metric].append(point)
                    query_file.write((canonical({'arm': arm, 'metric': metric, 'N': n, 'queries': rows}) + '\n').encode())
    control_envelopes = {metric: envelopes(curves, metric) for metric in ['RA', 'binary_diagnostic']}
    checks = {metric: assessment(curves, metric) for metric in ['RA', 'binary_diagnostic']}
    write_json(out / 'curves.json', curves); write_json(out / 'control_envelopes.json', control_envelopes)
    write_json(out / 'full_frame_model_degrees.json', degree_ledger)
    # Preserve reference-direction diagnostics; do not alter locked orientation.
    diffs = [abs(r['p']['value'] - r['reverse_p']['value']) for r in pairs
             if r['p']['value'] is not None and r['reverse_p']['value'] is not None]
    source_coverage = gold_packet._read(frozen / 'source_coverage.json')
    matrix.load(frozen, captured)
    need(all(sha(p) == pin for p, pin in pins.items()) and sha(__file__) == code, 'source/reference/code changed during prospective evaluation')
    result = {'format': FORMAT, 'created_at': utcnow(), 'frozen_source_control_content_sha256': frozen_report['content_sha256'],
        'native_capture_content_sha256': capture_report['content_sha256'], 'sample_content_sha256': frozen_report['sample_content_sha256'],
        'input_report_file_sha256': pins, 'implementation_sha256': code, 'native_NetworkX': runtime,
        'fixed_queries': len(genes), 'all_unordered_pairs': len(pairs), 'primary_pairs': len(primary), 'source_arms': len(curves),
        'N': packet['N'], 'native_P_status_counts': dict(Counter(r['p_status'] for r in pairs)),
        'native_sign_status_counts': dict(Counter(r['sign_status'] for r in pairs)),
        'native_P_direction_numeric_mismatches': sum(not r['p_direction_exactly_equal'] for r in pairs),
        'max_native_P_direction_absolute_difference': max(diffs) if diffs else None,
        'source_only_coverage': {k: source_coverage[k] for k in ['normalized', 'historical']},
        'full_curve_descriptive_assessment': checks,
        'prospective_gene_transfer_within_same_published_reference': True,
        'independent_experimental_confirmation_or_whole_proteome_accuracy': False,
        'source_based_replacement_or_postoutcome_reframing': False,
        'new_model_or_production_graph_change': False, 'calibrated_negative_truth_or_prune_labels_created': False,
        'limitations': ['Metadata-uniform128-gene sample from a reviewed uniquely mapped17,231-gene subset, not the whole proteome.',
            'Reference ranks are among sampled128 eligible partners, not genomewide topN or significance-defined positive labels.',
            'OldBroad/RA results informed this selected method; new-new pair values were held until the prospective source/control freeze.',
            'Source-only degree/affinity algebra was inspected during pre-value coverage review; no reference outcomes or method choices changed.',
            'Sparse source support: all128 queries remain, including historical queries with zero RA context.',
            'Greater relative enrichment may accompany lower absolute affinity; all sums/means and control curves are retained.',
            'Twenty native null draws, query pairs and correlated N points do not establish independent replicates, uncertainty or statistical significance.',
            'Same historical pan-cancer experimental reference and possible source/evidence reuse; no new study, PPI/causal truth or clinical claim.'],
        'files': inventory(out)}
    result['content_sha256'] = digest(result); write_json(out / 'report.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['frozen', 'captured', 'out']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); print(evaluate(a.frozen, a.captured, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
