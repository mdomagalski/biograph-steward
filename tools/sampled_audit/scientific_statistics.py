"""Conditional finite-population bounds for explicitly admitted claim labels.

Horowitz--Manski missing-outcome bounds: unknown binary outcomes may be zero
or one. These are exact logical completions of the supplied finite population,
not sample confidence intervals. The caller authenticates the census, graph
memberships, reference files and scientific judgments. This module cannot
establish reviewer expertise, source independence or biological truth.
Existing source/evidence audit statuses are deliberately not accepted as labels.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import re

from .audit_statistics import _mean_and_variance


FORMAT = 'biograph-steward.finite-population-scientific-bounds.v1'
METHOD_REFERENCE = 'https://doi.org/10.1080/01621459.2000.10473902'
LABELS = ('true', 'false', 'unknown')
REFERENCE_KINDS = ('primary_experiment', 'expert_curation', 'native_source_only', 'none')
INDEPENDENCE = ('independent', 'shared', 'unresolved')
IDENTITY_FIELDS = ('assertion_id', 'assertion_content_sha256', 'stored_predicate', 'claim_semantics')
CONTEXT_FLAGS = ('exact_claim_match', 'context_complete', 'qualifier_scope_complete')


def _need(value, message):
    if not value:
        raise ValueError('Scientific bounds: ' + message)


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _hash(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def _ids(values, universe, role):
    _need(isinstance(values, (list, tuple, set, frozenset)), role + ' needs explicit assertion IDs.')
    _need(all(_text(x) for x in values) and len(set(values)) == len(values), role + ' IDs differ or duplicate.')
    result = set(values)
    _need(result <= set(universe), role + ' contains assertions outside the original union.')
    return result


def _judgments(population, rows):
    _need(isinstance(rows, (list, tuple)), 'judgments must be explicit rows; missing rows remain unknown.')
    result = {}
    for row in rows:
        _need(isinstance(row, dict), 'judgment rows must be objects.')
        uid = row.get('assertion_id')
        _need(_text(uid) and uid in population and uid not in result, 'judgment identity is foreign or duplicated.')
        _need(all(row.get(k) == population[uid][k] for k in IDENTITY_FIELDS),
              'judgment hash, stored predicate or exact claim semantics changed.')
        label, kind, independence = (row.get(k) for k in
            ('scientific_label', 'reference_kind', 'reference_independence'))
        _need(label in LABELS and kind in REFERENCE_KINDS and independence in INDEPENDENCE,
              'explicit scientific true/false/unknown and reference provenance required.')
        _need(_text(row.get('reason')) and all(type(row.get(k)) is bool for k in CONTEXT_FLAGS),
              'reason and explicit exact-claim/context/qualifier flags required.')
        refs = row.get('reference_files')
        _need(isinstance(refs, list) and all(isinstance(r, dict) and set(r) == {'file', 'sha256'}
              and _text(r['file']) and _hash(r['sha256']) for r in refs),
              'reference files must carry explicit paths and SHA256 pins.')
        _need(len({r['file'] for r in refs}) == len(refs), 'reference paths duplicate or carry conflicting pins.')
        if label != 'unknown':
            _need(kind in ('primary_experiment', 'expert_curation') and bool(refs)
                  and all(row[k] for k in CONTEXT_FLAGS),
                  'true/false needs admitted primary/expert exact-claim context, not source presence.')
        result[uid] = row
    return result


def _graph_summary(ids, labels):
    counts = Counter(labels.get(uid, 'unknown') for uid in ids)
    n = len(ids)
    return {'population_assertions': n, 'labels': {k: counts[k] for k in LABELS},
        'logical_accuracy_bounds': {'lower': counts['true'] / n,
            'upper': 1 - counts['false'] / n} if n else None,
        'accuracy_point_estimate': counts['true'] / n if n and not counts['unknown'] else None,
        'confidence_interval': None, 'all_assertions_labelled': bool(n) and not counts['unknown'],
        'scientific_accuracy_independently_established': False}


def _comparison(before, after, labels):
    if not before or not after:
        return {'status': 'undefined_empty_graph', 'logical_accuracy_difference_bounds': None,
                'accuracy_difference_point_estimate': None, 'confidence_interval': None,
                'biological_improvement_claimed': False}
    low, high = Fraction(0), Fraction(0)
    affected_unknown = 0
    for uid in before | after:
        coefficient = Fraction(int(uid in after), len(after)) - Fraction(int(uid in before), len(before))
        label = labels.get(uid, 'unknown')
        if label == 'true':
            low += coefficient
            high += coefficient
        elif label == 'unknown':
            low += min(coefficient, 0)
            high += max(coefficient, 0)
            affected_unknown += int(bool(coefficient))
    return {'status': 'conditional_logical_completion',
        'baseline_assertions': len(before), 'candidate_assertions': len(after),
        'shared_assertions': len(before & after), 'removed_assertions': len(before - after),
        'added_assertions': len(after - before), 'unknown_assertions_with_nonzero_coefficient': affected_unknown,
        'logical_accuracy_difference_bounds': {'lower': float(low), 'upper': float(high)},
        'accuracy_difference_point_estimate': float(low) if low == high else None,
        'confidence_interval': None, 'same_assertion_truth_shared_between_graphs': True,
        'biological_improvement_claimed': False}


def _sampling_coverage(domains, population, labels):
    _need(isinstance(domains, dict), 'sampling domains must remain separately named.')
    summaries = {}
    for name, domain in domains.items():
        _need(_text(name) and isinstance(domain, dict), 'sampling domain differs.')
        _need(domain.get('purpose') in ('original_union_probability_sample', 'separate_removed_domain'),
              'declare original-union sample or separate removed-domain supplement.')
        ids = _ids(domain.get('population_ids'), population, 'sampling domain')
        _need(bool(ids), 'sampling population must be nonempty.')
        if domain['purpose'] == 'original_union_probability_sample':
            _need(ids == set(population), 'main sampling frame must be the original complete union.')
        sizes = Counter(population[uid].get('stratum') for uid in ids)
        _need(all(_text(k) for k in sizes), 'sampling needs the census stratum of every assertion.')
        strata = domain.get('strata')
        _need(isinstance(strata, dict) and set(strata) == set(sizes), 'sampling strata omit census families.')
        for key, d in strata.items():
            _need(isinstance(d, dict) and type(d.get('population_size')) is int
                  and d['population_size'] == sizes[key] and type(d.get('sample_size')) is int
                  and 1 <= d['sample_size'] <= d['population_size'], 'sampling allocation differs from its census.')
        rows = domain.get('sample_rows')
        _need(isinstance(rows, (list, tuple)), 'sample rows required.')
        seen, cases, by_stratum = set(), set(), defaultdict(list)
        for row in rows:
            _need(isinstance(row, dict), 'sample row must be an object.')
            uid, case, key = (row.get(k) for k in ('assertion_id', 'case_id', 'stratum'))
            _need(_text(uid) and uid in ids and uid not in seen and _text(case) and case not in cases
                  and key == population[uid]['stratum'], 'sample identity or stratum differs.')
            if 'inclusion_probability' in row:
                ip = row['inclusion_probability']
                _need(isinstance(ip, dict) and set(ip) == {'numerator', 'denominator'}
                      and all(type(ip[k]) is int for k in ip)
                      and ip == {'numerator': strata[key]['sample_size'],
                      'denominator': strata[key]['population_size']}, 'sample inclusion probability differs.')
            seen.add(uid); cases.add(case); by_stratum[key].append(uid)
        _need(all(len(by_stratum[k]) == d['sample_size'] for k, d in strata.items()), 'sample allocation incomplete.')
        statuses = {label: _mean_and_variance(strata, {k: [int(labels.get(uid, 'unknown') == label)
                    for uid in by_stratum[k]] for k in strata}) for label in LABELS}
        summaries[name] = {'purpose': domain['purpose'], 'population_assertions': len(ids),
            'sampled_assertions': len(rows), 'pool_with_other_sampling_domains': False,
            'design_weighted_supplied_label_statuses': statuses,
            'population_scientific_accuracy_estimate': None, 'biological_confidence_interval': None,
            'interpretation': 'Conditional SRSWOR summaries of supplied label availability/status only; '
                'not population truth bounds, credible-label validation or correction of adaptive label ascertainment.'}
    return summaries


def assess(population_rows, graph_memberships, judgment_rows, *, comparisons, sampling_domains=None):
    """Compare exact graph memberships, conditional on externally admitted labels.

    Population rows carry assertion_id/content hash, stored_predicate and an
    explicit claim_semantics string. Unobserved census assertions are UNKNOWN,
    including every unsampled row. Sampling domains are summarized separately;
    they do not convert a sampled label into a census observation elsewhere.
    Scientific labels and reference paths/hashes require caller admission.
    """
    _need(isinstance(population_rows, (list, tuple)) and bool(population_rows), 'nonempty original union census required.')
    population = {}
    for row in population_rows:
        _need(isinstance(row, dict) and all(_text(row.get(k)) for k in IDENTITY_FIELDS)
              and _hash(row['assertion_content_sha256']), 'exact census identity, hash and semantics required.')
        uid = row['assertion_id']
        _need(uid not in population, 'union assertion identity duplicates.')
        population[uid] = row
    _need(isinstance(graph_memberships, dict) and bool(graph_memberships)
          and all(_text(k) for k in graph_memberships), 'explicit graph memberships required.')
    graphs = {name: _ids(ids, population, 'graph membership') for name, ids in graph_memberships.items()}
    judgments = _judgments(population, judgment_rows)
    labels = {uid: row['scientific_label'] for uid, row in judgments.items()}
    _need(isinstance(comparisons, (list, tuple)), 'explicit fixed comparisons required.')
    paired, seen = [], set()
    for pair in comparisons:
        _need(isinstance(pair, dict) and set(pair) == {'baseline', 'candidate'}, 'comparison roles differ.')
        before, after = pair['baseline'], pair['candidate']
        _need(_text(before) and _text(after) and before in graphs and after in graphs
              and (before, after) not in seen, 'unknown or duplicate comparison.')
        seen.add((before, after))
        paired.append({**pair, **_comparison(graphs[before], graphs[after], labels)})
    return {'format': FORMAT, 'method_reference': METHOD_REFERENCE,
        'union_population_assertions': len(population), 'explicit_judgment_rows': len(judgments),
        'unreviewed_census_assertions': len(population) - len(judgments),
        'graphs': {name: _graph_summary(ids, labels) for name, ids in graphs.items()}, 'comparisons': paired,
        'sampling_domains': _sampling_coverage({} if sampling_domains is None else sampling_domains, population, labels),
        'reference_kind_counts': dict(Counter(row['reference_kind'] for row in judgments.values())),
        'reference_independence_counts': dict(Counter(row['reference_independence'] for row in judgments.values())),
        'reference_file_hashes_verified_by_statistics': False,
        'scientific_label_credibility_verified_by_statistics': False,
        'confidence_interval': None, 'biological_improvement_claimed': False,
        'limits': ['Bounds condition on correctness of externally admitted exact-claim labels and graph census.',
            'All unlabelled and unsampled assertions remain unknown; evidence support is not scientific truth.',
            'Shared assertions have one truth value across graphs, even with different population denominators.',
            'Logical bounds do not quantify sampling, annotation error, curator dependence or biological uncertainty.',
            'Separate sample-domain summaries are never pooled or substituted for census logical bounds.',
            'No independent whole-graph scientific accuracy, statistical significance or automatic graph change is established.']}
