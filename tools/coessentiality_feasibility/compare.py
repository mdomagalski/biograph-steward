"""Complete frozen top-N coannotation concordance curves, not biological truth.

Native GLS P ranks are unsigned/two-sided. No FDR threshold, inferred negative,
learner, fitted correlation or best-N selection is introduced here.
"""
from collections import Counter, defaultdict
import argparse
import gzip
import itertools
import json
import math
from pathlib import Path
import statistics
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import canonical, digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.reference_accuracy.design import need, write_jsonl
from tools.coessentiality_feasibility import matrix
from tools.coessentiality_feasibility.prepare import verify

FORMAT = 'biograph-steward.coessentiality-functional-concordance.v1'
SCOPES = ['nonsyntenic', 'all', 'syntenic', 'nonsyntenic_positive', 'nonsyntenic_negative']


def encoded(value):
    value = float(value)
    return {'value': value if math.isfinite(value) else None,
            'native_float64_little_endian_hex': struct.pack('<d', value).hex()}


def pair_values(packet, arrays):
    genes = {g['ncbi_gene_id']: g for g in packet['genes']}; rows = []
    for source in packet['pairs']:
        a, b = sorted(source['gene_pair'], key=lambda k: genes[k]['native_matrix_symbol'])
        i, j = genes[a]['native_matrix_index'], genes[b]['native_matrix_index']
        p = float(arrays[('GLS_p.npy', j)][i]); rev = float(arrays[('GLS_p.npy', i)][j])
        sign = float(arrays[('GLS_sign.npy', j)][i]); rev_sign = float(arrays[('GLS_sign.npy', i)][j])
        valid = math.isfinite(p) and 0 <= p <= 1
        rows.append({'gene_pair': sorted([a, b]), 'scope': source['scope'], 'native_row_gene': a, 'native_column_gene': b,
            'native_row_symbol': genes[a]['native_matrix_symbol'], 'native_column_symbol': genes[b]['native_matrix_symbol'],
            'native_row_index': i, 'native_column_index': j, 'p': encoded(p), 'reverse_p': encoded(rev),
            'sign': encoded(sign), 'reverse_sign': encoded(rev_sign),
            'p_status': 'usable_native_two_sided_p' if valid else 'UNKNOWN_nonfinite_or_out_of_range_native_p',
            'sign_status': 'native_sign' if sign in {-1.0, 0.0, 1.0} else 'UNKNOWN_invalid_native_sign',
            'p_direction_exactly_equal': p == rev, 'sign_direction_exactly_equal': sign == rev_sign})
    return rows


def reference_partners(genes, pairs, scope):
    partners = {g: [] for g in genes}
    for row in pairs:
        if row['p_status'] != 'usable_native_two_sided_p':
            continue
        if scope != 'all' and row['scope'] != ('nonsyntenic' if scope.startswith('nonsyntenic') else scope):
            continue
        if scope.endswith('_positive') and row['sign']['value'] != 1.0:
            continue
        if scope.endswith('_negative') and row['sign']['value'] != -1.0:
            continue
        a, b = row['gene_pair']; p = row['p']['value']
        need(a != b and a in partners and b in partners, 'reference pair outside fixed distinct-gene frame')
        partners[a].append((b, p)); partners[b].append((a, p))
    for gene, rows in partners.items():
        need(len(rows) == len({p for p, value in rows}), 'reference partner repeated')
        rows.sort(key=lambda r: (r[1], r[0]))
    return partners


def fractional_top(rows, n):
    """Boundary-tie inclusion, exactly N mass; no ID-based boundary preference."""
    need(type(n) is int and n >= 1, 'N must be a positive integer')
    if len(rows) < n:
        return None
    boundary = sorted(v for partner, v in rows)[n - 1]
    below = [(g, p) for g, p in rows if p < boundary]
    tied = [(g, p) for g, p in rows if p == boundary]
    fraction = (n - len(below)) / len(tied)
    selected = sorted([(g, 1.0) for g, p in below] + [(g, fraction) for g, p in tied])
    need(abs(sum(w for g, w in selected) - n) < 1e-10, 'fractional top-N mass differs')
    return {'selected': selected, 'boundary_p': boundary, 'boundary_tie_size': len(tied),
            'boundary_tie_weight': fraction, 'strictly_ahead': len(below)}


def shared_partners(genes, memberships):
    by_context = defaultdict(set); adjacent = {g: set() for g in genes}
    need(len(memberships) == len(set(map(tuple, memberships))), 'membership adjacency repeats')
    for gene, context in memberships:
        need(gene in adjacent, 'source feature outside fixed measured-gene frame')
        by_context[context].add(gene)
    for members in by_context.values():
        for a, b in itertools.combinations(sorted(members), 2):
            adjacent[a].add(b); adjacent[b].add(a)
    return adjacent


def curve_point(genes, partners, selections, adjacent, n, primary):
    queries = []; observed = expected = 0.0; available_queries = 0
    for gene in genes:
        candidates = partners[gene]; selected = selections[gene]
        context_count = sum(partner in adjacent[gene] for partner, p in candidates)
        if selected is None:
            queries.append({'gene': gene, 'available_partners': len(candidates), 'context_partners': context_count,
                'status': 'UNKNOWN_fewer_than_N_reference_partners', 'observed_hits': None, 'expected_hits': None})
            continue
        hit = math.fsum(weight for partner, weight in selected['selected'] if partner in adjacent[gene])
        exp = n * context_count / len(candidates)
        queries.append({'gene': gene, 'available_partners': len(candidates), 'context_partners': context_count,
            'status': 'scorable', 'observed_hits': hit, 'expected_hits': exp})
        observed += hit; expected += exp; available_queries += 1
    scorable = available_queries == len(genes) if primary else available_queries > 0
    slots = available_queries * n
    return {'N': n, 'query_frame': len(genes), 'reference_available_queries': available_queries,
        'unavailable_queries': len(genes) - available_queries,
        'aggregation': 'all_fixed_queries' if primary else 'conditional_reference_available_queries',
        'status': 'scorable' if scorable else 'UNKNOWN_incomplete_fixed_query_frame',
        'selected_slots_if_reference_available': slots,
        'observed_hits': observed if scorable else None, 'expected_hits': expected if scorable else None,
        'observed_hit_fraction': observed / slots if scorable and slots else None,
        'expected_hit_fraction': expected / slots if scorable and slots else None,
        'enrichment': observed / expected if scorable and expected > 0 else None,
        'zero_expected_enrichment_undefined': scorable and expected == 0, 'queries': queries}


def compare(frozen, captured, output):
    frozen, captured = Path(frozen).absolute(), Path(captured).absolute()
    frozen_report, packet = verify(frozen); capture_report, bound_packet, arrays = matrix.load(frozen, captured)
    need(packet == bound_packet, 'bound source packet differs')
    input_pins = {str(frozen / 'report.json'): sha(frozen / 'report.json'),
                  str(captured / 'report.json'): sha(captured / 'report.json')}
    code = sha(__file__); genes = sorted(g['ncbi_gene_id'] for g in packet['genes'])
    pairs = pair_values(packet, arrays)
    out = new_output(output, frozen, captured)
    write_jsonl(out / 'native_pair_values.jsonl', pairs)
    adjacencies = {arm: shared_partners(genes, data['memberships']) for arm, data in packet['arms'].items()}
    curves = {arm: {scope: [] for scope in SCOPES} for arm in packet['arms']}
    with gzip.GzipFile(filename=str(out / 'per_query_scores.jsonl.gz'), mode='wb', mtime=0) as details:
        selections_ledger = []
        for scope in SCOPES:
            partners = reference_partners(genes, pairs, scope)
            for n in packet['N']:
                selections = {g: fractional_top(partners[g], n) for g in genes}
                selections_ledger.append({'scope': scope, 'N': n, 'queries': [
                    {'gene': g, 'available_reference_partners': len(partners[g]), 'selection': selections[g]} for g in genes]})
                for arm in packet['arms']:
                    point = curve_point(genes, partners, selections, adjacencies[arm], n, scope == 'nonsyntenic')
                    queries = point.pop('queries')
                    details.write((canonical({'arm': arm, 'scope': scope, 'N': n, 'queries': queries}) + '\n').encode())
                    curves[arm][scope].append(point)
        write_jsonl(out / 'reference_rank_selections.jsonl', selections_ledger)
    controls = {}
    superiority = {}
    for treatment in ['current', 'historical']:
        controls[treatment] = {}
        for kind in ['count', 'degree']:
            names = [f'{treatment}_{kind}_{i:02}' for i in range(packet['control_replicates'])]
            controls[treatment][kind] = {}
            for scope in SCOPES:
                points = []
                for index, n in enumerate(packet['N']):
                    values = [curves[a][scope][index]['enrichment'] for a in names]
                    valid = [v for v in values if v is not None]
                    points.append({'N': n, 'draws': len(values), 'defined_draws': len(valid),
                        'minimum': min(valid) if valid else None, 'median': statistics.median(valid) if valid else None,
                        'maximum': max(valid) if valid else None, 'not_a_confidence_interval': True})
                controls[treatment][kind][scope] = points
        names = ['normalized'] + [f'{treatment}_{kind}_{i:02}' for kind in ['count', 'degree']
                                  for i in range(packet['control_replicates'])]
        comparisons = []
        for i, n in enumerate(packet['N']):
            value = curves[treatment]['nonsyntenic'][i]['enrichment']
            reference = [curves[a]['nonsyntenic'][i]['enrichment'] for a in names]
            defined = value is not None and all(v is not None for v in reference)
            comparisons.append({'N': n, 'all_enrichments_defined': defined,
                'exceeds_normalized_and_all_40_draws': defined and all(value > v + 1e-12 for v in reference)})
        superiority[treatment] = {'points': comparisons,
            'pointwise_above_baseline_and_all_controls_at_every_N': all(r['exceeds_normalized_and_all_40_draws'] for r in comparisons),
            'is_statistical_significance_or_generalized_biological_gain': False}
    write_json(out / 'curves.json', curves); write_json(out / 'descriptive_control_envelopes.json', controls)
    matrix.load(frozen, captured)
    need(all(sha(p) == h for p, h in input_pins.items()) and sha(__file__) == code, 'source/code changed during comparison')
    result = {'format': FORMAT, 'created_at': utcnow(), 'frozen_comparison_content_sha256': frozen_report['content_sha256'],
        'native_capture_content_sha256': capture_report['content_sha256'], 'input_report_file_sha256': input_pins,
        'implementation_sha256': code, 'query_genes': len(genes), 'pair_scope_counts': dict(Counter(r['scope'] for r in pairs)),
        'native_p_status_counts': dict(Counter(r['p_status'] for r in pairs)),
        'native_sign_status_counts': dict(Counter(r['sign_status'] for r in pairs)),
        'native_sign_counts': dict(Counter(str(r['sign']['value']) for r in pairs)),
        'p_direction_mismatch_pairs': sum(not r['p_direction_exactly_equal'] for r in pairs),
        'sign_direction_mismatch_pairs': sum(not r['sign_direction_exactly_equal'] for r in pairs),
        'full_curve_descriptive_assessment': superiority, 'all_N_and_all_arms_reported': True,
        'scientific_truth_labels_created': False, 'PPIs_or_causal_mechanisms_inferred': False,
        'model_fitted_or_graph_changed': False, 'FDR_or_significance_reconstructed': False,
        'limitations': ['Native experimental fitness concordance, not physical binding or whole-graph accuracy.',
            'Historical pan-cancer screens; not CRC-specific or universal functional truth.',
            'One exploratory endpoint frozen after earlier INMC outcomes and paper methods/examples were seen.',
            'Twenty algorithm draws describe frozen controls; mixing, uniformity, null probabilities and uncertainty are not established.',
            'Possible indirect curation/source reuse remains unresolved; GO-assisted original preprocessing is disclosed.',
            'Matrices were partially retrieved: per-range SHA256/ETags, not invented full-file checksums.',
            'Reference UNKNOWN values and source zero-context queries remain visible.'],
        'files': {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()}}
    result['content_sha256'] = digest(result); write_json(out / 'report.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['frozen', 'captured', 'out']:
        p.add_argument('--' + name, required=True, type=Path)
    a = p.parse_args(); print(compare(a.frozen, a.captured, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
