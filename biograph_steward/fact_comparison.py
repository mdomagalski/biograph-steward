"""Conservative comparisons with source-linked, unreviewed fact records.

This is a deliberately small claim grammar, not a biomedical entailment engine.
Source grounding and field agreement do not establish association correctness.
Every result remains advisory and requires review; no graph state is changed.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re

from .client import digest
from .source_facts import validate_dossier


POLICY = 'source-fact-comparison.v1'
CLAIM_POLICY = 'source-fact-claim.v1'
_DRUGS = ('adagrasib', 'cetuximab', 'panitumumab', 'sotorasib', 'dasatinib',
          'irinotecan', 'folfox4', 'folfiri')
_ATOMIC_COMBINATIONS = {'folfox4', 'folfiri'}
_MOLECULAR = (r'(?:wild[ -]type|WT|mutant) (?:KRAS|NRAS|BRAF)|'
              r'(?:KRAS|NRAS|BRAF) (?:p\.)?[ACDEFGHIKLMNPQRSTVWY][1-9][0-9]{0,3}[ACDEFGHIKLMNPQRSTVWY]')
_RESPONSE = re.compile(
    r'(?:The )?(?P<arm>[A-Za-z0-9 -]+?) (?P<mode>combination group|monotherapy) '
    r'had a (?:reported )?(?P<endpoint>response rate) of (?P<value>(?:0|[1-9][0-9]*)(?:\.[0-9]+)?)% '
    r'in evaluable patients\.', re.I)
_SURVIVAL = re.compile(
    r'In the (?P<molecular>' + _MOLECULAR + r') stratum, the (?P<effect_direction>increase) in '
    r'(?P<endpoint>overall survival|progression-free survival) with '
    r'(?P<arm>[A-Za-z0-9 -]+?) compared with (?P<comparator>[A-Za-z0-9 -]+?) '
    r'was (?P<significance>nonsignificant|statistically significant)\.', re.I)


def _span(claim, match, name):
    start, end = match.span(name)
    return {'start': start, 'end': end, 'text': claim[start:end]}


def _facet(value, spans, rule):
    return {'value': value, 'claim_spans': spans, 'normalization_rule': rule}


def _arm(text, explicit_mode=None):
    """Resolve complete named sets only; a single mention is not monotherapy."""
    name = text.lower()
    mode = explicit_mode
    if name.endswith(' monotherapy'):
        name = name[:-len(' monotherapy')]
        mode = 'monotherapy'
    names = re.split(r' (?:and|plus) |-', name)
    if (any(n not in _DRUGS for n in names) or len(set(names)) != len(names)
            or not names):
        return None
    if mode == 'monotherapy':
        if len(names) != 1 or names[0] in _ATOMIC_COMBINATIONS:
            return None
    elif mode == 'combination group':
        if len(names) < 2 and names[0] not in _ATOMIC_COMBINATIONS:
            return None  # An unnamed combination partner is not a complete arm.
    elif len(names) == 1 and names[0] not in _ATOMIC_COMBINATIONS:
        return None
    return sorted(names)


def _molecular(text):
    lowered = text.lower()
    gene = next(g for g in ('KRAS', 'NRAS', 'BRAF') if re.search(r'\b' + g + r'\b', text, re.I))
    if lowered.startswith(('wild', 'wt')):
        return {'gene': gene, 'state': 'wild_type', 'variant': None}
    if lowered.startswith('mutant'):
        return {'gene': gene, 'state': 'mutant_unspecified', 'variant': None}
    variant = text.split(' ', 1)[1].removeprefix('p.').removeprefix('P.').upper()
    return {'gene': gene, 'state': 'variant', 'variant': variant}


def _decimal(text):
    value = format(Decimal(text), 'f')
    return value.rstrip('0').rstrip('.') if '.' in value else value


def parse_claim(claim):
    """Parse two complete public sentence forms; never infer missing qualifiers.

    Optional leading ``The`` and case changes preserve the same claim grammar.
    Unsupported syntax or additional qualifiers remain wholly unresolved.
    """
    result = {'format': CLAIM_POLICY, 'supported': False, 'rule_id': None, 'kind': None,
              'facets': {}, 'reason': 'Claim is outside the bounded response/survival grammar.'}
    if not isinstance(claim, str) or not claim or len(claim) > 10000:
        return result
    match = _RESPONSE.fullmatch(claim)
    if match:
        arm = _arm(match['arm'], match['mode'].lower())
        value = Decimal(match['value'])
        if arm is None or not 0 <= value <= 100:
            result['reason'] = 'The claim does not specify a supported complete named arm and percentage.'
            return result
        result.update(supported=True, rule_id='claim.response_rate.v1', kind='response_rate', reason=None,
            facets={
                'regimen': _facet(arm, [_span(claim, match, 'arm'), _span(claim, match, 'mode')],
                                  'named_complete_regimen.v1'),
                'endpoint': _facet('response_rate', [_span(claim, match, 'endpoint')], 'endpoint.response_rate.v1'),
                'value': _facet(_decimal(match['value']), [_span(claim, match, 'value')], 'decimal_percentage.v1')})
        return result
    match = _SURVIVAL.fullmatch(claim)
    if match:
        arm = _arm(match['arm']); comparator = _arm(match['comparator'])
        if arm is None or comparator is None:
            result['reason'] = 'A single drug mention does not establish the complete regimen or monotherapy.'
            return result
        result.update(supported=True, rule_id='claim.survival_significance.v1', kind='survival_significance', reason=None,
            facets={
                'molecular': _facet(_molecular(match['molecular']), [_span(claim, match, 'molecular')],
                                    'molecular.explicit_state_and_allele.v1'),
                'regimen': _facet(arm, [_span(claim, match, 'arm')], 'named_complete_regimen.v1'),
                'comparator': _facet(comparator, [_span(claim, match, 'comparator')], 'named_complete_regimen.v1'),
                'endpoint': _facet('OS' if match['endpoint'].lower() == 'overall survival' else 'PFS',
                                   [_span(claim, match, 'endpoint')], 'endpoint.named_survival.v1'),
                'effect_direction': _facet('increase', [_span(claim, match, 'effect_direction')],
                                           'direction.explicit_increase.v1'),
                'significance': _facet('not_significant' if match['significance'].lower() == 'nonsignificant' else 'significant',
                                       [_span(claim, match, 'significance')], 'qualification.authors_significance.v1')})
    return result


def _context_relation(field, claimed, observed):
    if observed is None:
        return 'unresolved', None, 'The selected source record does not establish this field.'
    if claimed == observed:
        return 'match', None, 'Values agree within this single linked source record.'
    if field == 'molecular':
        if claimed['gene'] != observed['gene']:
            return 'explicit_conflict', 'context_difference', 'The explicitly named genes differ.'
        if {claimed['state'], observed['state']} == {'variant', 'mutant_unspecified'}:
            return 'unresolved', None, 'An unspecified mutant group and a particular allele are different scopes.'
        if claimed['state'] == observed['state'] == 'mutant_unspecified':
            return 'match', None, 'The same unspecified mutant group is asserted.'
        return 'explicit_conflict', 'context_difference', 'The explicit molecular contexts differ.'
    return 'explicit_conflict', 'context_difference', 'The explicit contexts differ.'


def _candidate(parsed, record):
    rows = []
    for field, facet in parsed['facets'].items():
        if field in ('value', 'significance', 'effect_direction'):
            continue
        relation, conflict, reason = _context_relation(field, facet['value'], record.get(field))
        rows.append({'field': field, 'status': relation, 'conflict_kind': conflict,
                     'claim_value': deepcopy(facet['value']), 'source_value': deepcopy(record.get(field)),
                     'claim_spans': deepcopy(facet['claim_spans']),
                     'source_provenance': deepcopy(record['provenance'].get(field, [])), 'reason': reason})
    context_matches = all(row['status'] == 'match' for row in rows)
    for field in ('value', 'significance', 'effect_direction'):
        if field not in parsed['facets']:
            continue
        facet = parsed['facets'][field]; observed = record.get(field)
        relation = 'unresolved'; conflict = None
        reason = 'A report comparison requires matching asserted context and a stated source value.'
        if context_matches and observed is not None:
            try:
                equal = (Decimal(facet['value']) == Decimal(observed)) if field == 'value' else facet['value'] == observed
            except (InvalidOperation, TypeError, ValueError):
                equal = None
            if equal is not None:
                relation = 'match' if equal else 'explicit_conflict'
                conflict = None if equal else ('reported_value_difference' if field == 'value' else 'opposing_report')
                reason = 'The reported value agrees.' if equal else 'The report differs in the same asserted context.'
        rows.append({'field': field, 'status': relation, 'conflict_kind': conflict,
                     'claim_value': deepcopy(facet['value']), 'source_value': deepcopy(observed),
                     'claim_spans': deepcopy(facet['claim_spans']),
                     'source_provenance': deepcopy(record['provenance'].get(field, [])), 'reason': reason})
    if all(row['status'] == 'match' for row in rows):
        status = 'limited_context_compatible'
    elif context_matches and any(row['status'] == 'explicit_conflict' for row in rows):
        status = 'review_report_difference'
    elif any(row['conflict_kind'] == 'context_difference' for row in rows):
        status = 'review_context_difference'
    else:
        status = 'review_unresolved'
    return {'record_id': record['id'], 'source_id': record['source_id'], 'status': status,
            'asserted_context_matches': context_matches, 'facets': rows,
            'association_status': record['association_status']}


def compare_claim(claim, dossier):
    """Compare only supported claim forms to single records; never approve truth."""
    validate_dossier(dossier)
    parsed = parse_claim(claim)
    result = {'format': POLICY, 'claim': claim, 'claim_sha256': digest(claim),
              'source_id': dossier['source_id'], 'source_sha256': dossier['source_sha256'],
              'parsed_claim': parsed, 'status': 'review_unresolved', 'candidates': [],
              'matched_record_ids': [], 'auto_approval': False, 'entailment_established': False,
              'graph_mutations': 0, 'association_review_pending': True, 'action': 'request_review',
              'source_record_disagreement': False,
              'limitation': 'Exact grounding and compatible fields do not verify source association or full claim entailment.'}
    if not parsed['supported']:
        return result
    candidates = [_candidate(parsed, record) for record in dossier['records'] if record['kind'] == parsed['kind']]
    result['candidates'] = candidates
    result['matched_record_ids'] = [c['record_id'] for c in candidates if c['status'] == 'limited_context_compatible']
    if result['matched_record_ids'] and any(c['status'] == 'review_report_difference' for c in candidates):
        result['source_record_disagreement'] = True
    elif result['matched_record_ids']:
        result['status'] = 'limited_context_compatible'
    elif any(c['status'] == 'review_report_difference' for c in candidates):
        result['status'] = 'review_report_difference'
    elif any(c['status'] == 'review_unresolved' or c['asserted_context_matches'] for c in candidates):
        result['status'] = 'review_unresolved'
    elif candidates:
        result['status'] = 'review_context_difference'
    return result
