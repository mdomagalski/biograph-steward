"""Narrow, source-only pattern extraction; exact grounding is not scientific truth.

No proposed claim, reference answer, model, retrieval or graph lifecycle is read.
Unsupported or ambiguous language remains a documented coverage gap.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import re

from .client import digest

FORMAT = 'source-facts.v1'
THERAPIES = ('adagrasib', 'cetuximab', 'dasatinib', 'FOLFIRI', 'FOLFOX4',
             'irinotecan', 'panitumumab', 'sotorasib')
CANONICAL = {name.casefold(): name.casefold() for name in THERAPIES}
DRUG = r'\b(?:' + '|'.join(re.escape(name) for name in THERAPIES) + r')\b'
DRUG_RX = re.compile(DRUG, re.I)
CONNECTOR = r'(?:[-+\u2013]|and|plus|(?:in\s+)?combination\s+with)'
REGIMEN_RX = re.compile(DRUG + r'(?:(?:\s*\([^)]*\))?\s*' + CONNECTOR +
                       r'\s*(?:(?:intravenous|oral)\s+)?' + DRUG + r')*', re.I)
RESPONSE_RX = re.compile(
    r'\bIn\s+the\s+(?P<mode>monotherapy|combination[- ]therapy)\s+group\s*'
    r'\(\s*(?P<n>[1-9][0-9]*)\s+evaluable\s+patients?\s*\)\s*,\s*'
    r'(?:a\s+|the\s+)?(?P<endpoint>(?:objective\s+)?response)\s+was\s+'
    r'(?:reported\s+in\s+)?(?P<rate>[0-9]+(?:\.[0-9]+)?)\s*%', re.I)
ENDPOINT_RX = re.compile(r'\b(?:PFS|OS|progression[- ]free survival|overall survival)\b', re.I)
NOT_SIGNIFICANT_RX = re.compile(r'\b(?:nonsignificant|non-significant|not(?:\s+statistically)?\s+significant|no\s+significant)\b', re.I)
SIGNIFICANT_RX = re.compile(r'\b(?:significantly|statistically\s+significant|significant)\b', re.I)
DIRECTION_RX = re.compile(r'\b(?:(?P<increase>improved|increase(?:d|s)?)|(?P<decrease>reduced|decrease(?:d|s)?))\b', re.I)
P_VALUE_RX = re.compile(r'\bP\s*=\s*(?P<value>(?:[0-9]*\.[0-9]+|[0-9]+))\b', re.I)
COMPARISON_RX = re.compile(r'\b(?:versus|vs\.?|compared\s+with|compared\s+to)\b', re.I)
UNSUPPORTED_REPORT_RX = re.compile(
    r'\b(?:(?:no|without)\s+(?:(?:clear|convincing)\s+)?evidence'
    r'|(?:did|does|do)\s+not|(?:was|were|is|are|has|have|had)\s+not\s+'
    r'(?:observed|reported|demonstrated|shown|found|associated)'
    r'|(?:failed|fails)\s+to|not\s+(?:significantly|improved|increased|reduced|decreased|compared)'
    r'|may|might|could|would|hypothesized|hypothesised|hypothesis|expected|anticipated|neither|nor)\b', re.I)
MOLECULAR_RX = re.compile(
    r'\b(?:(?P<wt>(?:wild[- ]type(?:\s*\(WT\))?|WT)\s+KRAS|KRAS\s+(?:wild[- ]type|WT))'
    r'|(?P<variant>(?:(?:mutant|mutated)\s+)?KRAS\s+(?P<code>[A-Z][1-9][0-9]{0,3}[A-Z]))'
    r'|(?P<mutant>(?:mutant|mutated)\s+KRAS))\b', re.I)
LIMITATIONS = [
    'Pattern extraction and exact source spans do not establish scientific truth or authorize graph acceptance.',
    'Only abstract paragraphs and two declared result-language families are supported; full text is not compiled.',
    'Therapy names use a disclosed finite vocabulary. FOLFOX4 and FOLFIRI are atomic named regimens, not single-drug or monotherapy assertions.',
    'Regimen members joined by supported AND connectors form one arm. Alternative OR arms are never merged.',
    'Survival requires one endpoint, one explicit author significance qualifier, one equality P value and an explicit treatment comparison in the sentence.',
    'Survival effect direction is mapped only from an unambiguous explicit improved/increase or reduced/decrease phrase; it is not a causal or treatment-benefit judgment.',
    'Explicit denial of a reported finding, conditional or hypothetical language is outside the supported result grammar; authors\' nonsignificance qualifiers remain distinct from denial of a finding.',
    'Molecular inheritance uses the nearest explicit stratum marker within one paragraph; response rates may use a single unambiguous METHODS KRAS variant.',
    'Missing or unsupported text is a coverage gap, never a biological negative; no significance is inferred from a numeric P value.']


def _check_paper(paper):
    if (not isinstance(paper, dict) or not isinstance(paper.get('pmid'), str)
            or not re.fullmatch(r'[1-9][0-9]{0,9}', paper['pmid'])
            or not isinstance(paper.get('title'), str) or not isinstance(paper.get('abstract'), list)):
        raise ValueError('Expected a parsed PubMed paper with exact identity, title and abstract blocks.')
    for passage in paper['abstract']:
        if (not isinstance(passage, dict) or not all(isinstance(passage.get(k), str) for k in ('text', 'locator', 'section'))
                or not passage['locator']):
            raise ValueError('Abstract blocks require text, locator and section strings.')
    try:
        digest(paper)
    except (TypeError, ValueError):
        raise ValueError('Source paper must contain finite JSON data.') from None


def _span(paper, index, start, end):
    passage = paper['abstract'][index]
    text = passage['text'][start:end]
    return {'passage_index': index, 'locator': passage['locator'], 'start': start, 'end': end,
            'text': text, 'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'offset_unit': 'unicode_codepoints'}


def _units(text):
    """Simple sentence units, retaining parent offsets and decimal punctuation."""
    start = 0
    for boundary in re.finditer(r'(?<=[.!?])\s+(?=[A-Z(])', text):
        # A comparison abbreviation is not a sentence boundary.
        if re.search(r'\bvs\.$', text[start:boundary.start()], re.I):
            continue
        end = boundary.start()
        while start < end and text[start].isspace():
            start += 1
        if start < end:
            yield start, end
        start = boundary.end()
    end = len(text)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        yield start, end


def _decimal(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError('Unsupported decimal source value.') from None
    if not value.is_finite():
        raise ValueError('Source value must be finite.')
    return format(value, 'f')


def _molecules(text):
    for match in MOLECULAR_RX.finditer(text):
        molecular = {'gene': 'KRAS', 'state': 'wild_type' if match['wt'] else
                     'variant' if match['variant'] else 'mutant_unspecified',
                     'variant': match['code'].upper() if match['code'] else None}
        yield match.start(), match.end(), molecular


def _scope(paper, index, before):
    text = paper['abstract'][index]['text']
    scoped = []
    for start, end, molecular in _molecules(text):
        marker = re.match(r'\s+(?:stratum|subgroup)\b', text[end:], re.I)
        if marker and end + marker.end() <= before:
            containing = next(text[a:b] for a, b in _units(text) if a <= start < b)
            excluded = (UNSUPPORTED_REPORT_RX.search(containing) or
                        re.search(r'\b(?:without|excluded|excluding|ineligible)\b', containing, re.I))
            # An invalid nearest marker blocks inheritance; do not fall through
            # to an earlier genotype or a generic METHODS fallback.
            scoped.append((None if excluded else molecular, _span(paper, index, start, end + marker.end())))
    return scoped[-1] if scoped else (None, None)


def _method_variant(paper):
    found = []
    for index, passage in enumerate(paper['abstract']):
        if 'METHOD' not in passage['section'].upper():
            continue
        for unit_start, unit_end in _units(passage['text']):
            unit = passage['text'][unit_start:unit_end]
            if UNSUPPORTED_REPORT_RX.search(unit) or re.search(r'\b(?:without|excluded|excluding|ineligible)\b', unit, re.I):
                continue
            for start, end, molecular in _molecules(unit):
                found.append((molecular, _span(paper, index, unit_start + start, unit_start + end)))
    if found and len({digest(m) for m, _ in found}) == 1 and found[0][0]['state'] == 'variant':
        return found[0]
    return None, None


def _expressions(text):
    for match in REGIMEN_RX.finditer(text):
        names = list(DRUG_RX.finditer(match.group()))
        regimen = sorted({CANONICAL[m.group().casefold()] for m in names})
        before = text[:match.start()]
        after = text[match.end():]
        # Do not interpret an adjacent OR alternative as a complete AND arm.
        adjacent = r'(?:plus|and|or|[-+\u2013]|(?:in\s+)?combination\s+with)'
        unknown_name = r'[A-Za-z][A-Za-z0-9_-]*'
        separate_mono_arm = re.search(DRUG + r'\s+(?:as\s+)?monotherapy\s+or\s*$', before, re.I)
        ambiguous = bool((not separate_mono_arm and re.search(unknown_name + r'\s+' + adjacent + r'\s*$', before, re.I))
                         or re.match(r'(?:\s*\([^)]*\))?\s*' + adjacent + r'\s*' + unknown_name, after, re.I)
                         or re.search(r'\bmodified\s*$', before, re.I))
        yield {'start': match.start(), 'end': match.end(), 'regimen': regimen,
               'names': [(match.start() + m.start(), match.start() + m.end()) for m in names],
               'ambiguous': ambiguous}


def _arm_definitions(paper):
    definitions = {'monotherapy': {}, 'combination-therapy': {}}
    blocked = set()
    methods = [i for i, p in enumerate(paper['abstract']) if 'METHOD' in p['section'].upper()]
    indices = methods if methods else list(range(len(paper['abstract'])))
    for index in indices:
        text = paper['abstract'][index]['text']
        for unit_start, unit_end in _units(text):
            unit = text[unit_start:unit_end]
            if UNSUPPORTED_REPORT_RX.search(unit):
                continue
            for expression in _expressions(unit):
                names = expression['regimen']
                prefix, suffix = unit[:expression['start']], unit[expression['end']:]
                mono = bool(re.match(r'\s+(?:as\s+)?monotherapy\b', suffix, re.I)
                            or re.search(r'\bmonotherapy\s+(?:with|of)\s*$', prefix, re.I))
                mode = 'monotherapy' if mono and len(names) == 1 else 'combination-therapy' if len(names) >= 2 else None
                if mode is None:
                    continue
                if expression['ambiguous'] or (mode == 'combination-therapy' and len(names) != 2):
                    blocked.add(mode)
                    continue
                definitions[mode].setdefault(tuple(names), [_span(paper, index, unit_start + a, unit_start + b)
                                                           for a, b in expression['names']])
    return definitions, blocked


def _comparison(paper, index, start, end):
    text = paper['abstract'][index]['text'][start:end]
    comparisons = list(COMPARISON_RX.finditer(text))
    if len(comparisons) != 1:
        return None
    comparison = comparisons[0]
    left = list(_expressions(text[:comparison.start()]))
    right = list(_expressions(text[comparison.end():]))
    if not left or not right:
        return None
    a, b = left[-1], right[0]
    if a['ambiguous'] or b['ambiguous'] or len(a['regimen']) > 2 or len(b['regimen']) > 2:
        return None
    # Multiple alternative named arms on either side cannot be disambiguated.
    if re.search(r'\bor\b', text[a['start']:comparison.start()], re.I):
        return None
    after_right = text[comparison.end() + b['end']:].split('(', 1)[0]
    if re.search(r'\bor\b', after_right, re.I):
        return None
    return (a['regimen'], b['regimen'],
            [_span(paper, index, start + x, start + y) for x, y in a['names']],
            [_span(paper, index, start + comparison.end() + x, start + comparison.end() + y) for x, y in b['names']])


def _unsupported_survival_clause(text):
    """Allow numeric parentheticals, not additional top-level result clauses."""
    visible = list(text)
    depth = 0
    for index, character in enumerate(text):
        if character == '(':
            depth += 1
        if depth:
            visible[index] = ' '
        if character == ')':
            depth -= 1
            if depth < 0:
                return True
    if depth:
        return True
    for expression in _expressions(text):
        visible[expression['start']:expression['end']] = [' '] * (expression['end'] - expression['start'])
    return re.search(r';|\b(?:and|or|while|whereas|although|however|but)\b', ''.join(visible), re.I) is not None


def _local_direction(unit, match):
    endpoint = ENDPOINT_RX.pattern
    after = unit[match.end():]
    before = unit[:match.start()]
    return bool(re.match(r'\s+(?:in\s+)?(?:median\s+)?' + endpoint, after, re.I)
                or re.search(endpoint + r'\s+(?:(?:was|were|is|has|had|been|also|significantly|statistically)\s+){0,4}$', before, re.I))


def _local_qualification(unit, qualifier, endpoints):
    for endpoint in endpoints:
        if qualifier.end() <= endpoint.start():
            between = unit[qualifier.end():endpoint.start()].strip()
            if re.fullmatch(r'(?:(?:increase|decrease|difference|improved|increased|reduced|decreased|improvement|reduction|benefit)\s*(?:in\s*)?)?(?:median\s*)?', between, re.I):
                return True
        elif endpoint.end() <= qualifier.start():
            between = unit[endpoint.end():qualifier.start()].strip()
            # An endpoint may precede its explicit named-arm comparison and
            # predicate, but another outcome's words must not be discarded.
            bridge = COMPARISON_RX.sub('', REGIMEN_RX.sub('', between))
            if re.fullmatch(r'\s*(?:(?:with|for|was|were|is|also|showed|had|a)\s*){0,8}', bridge, re.I):
                return True
    return False


def compile_source(paper):
    """Compile every supported abstract result, without any proposed claim."""
    _check_paper(paper)
    source_id = 'PubMed:' + paper['pmid']
    fingerprint = digest(paper)
    records, gaps = [], []
    definitions, blocked = _arm_definitions(paper)
    fallback_molecular, fallback_span = _method_variant(paper)

    def gap(code, index=None, start=None, end=None, detail=None):
        row = {'code': code, 'action': 'review', 'detail': detail or code}
        if index is not None:
            row['provenance'] = [_span(paper, index, start, end)]
        gaps.append(row)

    def add(kind, regimen, comparator, molecular, endpoint, value=None, n=None,
            significance=None, p_value=None, effect_direction=None, provenance=None):
        row = {'source_id': source_id, 'kind': kind, 'regimen': regimen, 'comparator': comparator,
               'molecular': molecular, 'endpoint': endpoint, 'value': value, 'evaluable_n': n,
               'significance': significance, 'p_value': p_value,
               'effect_direction': effect_direction,
               'association_status': 'pattern_extracted_unreviewed', 'provenance': provenance}
        row['id'] = 'source-fact-' + digest({'source_sha256': fingerprint, **row})[:24]
        records.append(row)

    for index, passage in enumerate(paper['abstract']):
        text = passage['text']
        for start, end in _units(text):
            unit = text[start:end]
            if UNSUPPORTED_REPORT_RX.search(unit) and (RESPONSE_RX.search(unit) or ENDPOINT_RX.search(unit)):
                gap('unsupported_negated_or_uncertain_report', index, start, end)
                continue
            responses = list(RESPONSE_RX.finditer(unit))
            for response in responses:
                mode = response['mode'].casefold().replace(' ', '-')
                options = definitions[mode]
                if mode in blocked or len(options) != 1:
                    gap('ambiguous_or_missing_regimen_definition', index, start, end, mode)
                elif not 0 <= Decimal(response['rate']) <= 100:
                    gap('response_percentage_out_of_range', index, start, end)
                else:
                    molecular, molecular_span = _scope(paper, index, start + response.start())
                    if molecular is None and molecular_span is None:
                        molecular, molecular_span = fallback_molecular, fallback_span
                    provenance = {'source_unit': [_span(paper, index, start, end)],
                        'regimen': deepcopy(next(iter(options.values()))) +
                            [_span(paper, index, start + response.start('mode'), start + response.end('mode'))],
                        'endpoint': [_span(paper, index, start + response.start('endpoint'), start + response.end('endpoint'))],
                        'value': [_span(paper, index, start + response.start('rate'), start + response.end('rate'))],
                        'evaluable_n': [_span(paper, index, start + response.start('n'), start + response.end('n'))]}
                    if molecular is not None and molecular_span:
                        provenance['molecular'] = [deepcopy(molecular_span)]
                    else:
                        gap('molecular_scope_unresolved', index, start, end)
                    add('response_rate', list(next(iter(options))), None, deepcopy(molecular),
                        'response_rate', _decimal(response['rate']), int(response['n']), provenance=provenance)
            if not responses and re.search(r'\bresponse\b', unit, re.I) and re.search(r'\bevaluable\b|\b(?:monotherapy|combination[- ]therapy)\s+group\b', unit, re.I):
                gap('unsupported_response_language', index, start, end)

            endpoints = list(ENDPOINT_RX.finditer(unit))
            if not endpoints:
                continue
            types = {'PFS' if m.group().casefold() in ('pfs', 'progression-free survival', 'progression free survival') else 'OS'
                     for m in endpoints}
            if len(types) != 1:
                gap('ambiguous_multiple_endpoints', index, start, end)
                continue
            if _unsupported_survival_clause(unit):
                gap('unsupported_multiple_result_clauses', index, start, end)
                continue
            negative = list(NOT_SIGNIFICANT_RX.finditer(unit))
            positive = [m for m in SIGNIFICANT_RX.finditer(unit)
                        if not any(n.start() <= m.start() < n.end() for n in negative)]
            qualifiers = [('not_significant', m) for m in negative] + [('significant', m) for m in positive]
            p_values = list(P_VALUE_RX.finditer(unit))
            comparison = _comparison(paper, index, start, end)
            if len(qualifiers) != 1 or len(p_values) != 1 or comparison is None:
                gap('unsupported_survival_language', index, start, end)
                continue
            if not _local_qualification(unit, qualifiers[0][1], endpoints):
                gap('unsupported_survival_qualification_binding', index, start, end)
                continue
            molecular, molecular_span = _scope(paper, index, start + endpoints[0].start())
            if molecular is None:
                gap('molecular_scope_unresolved', index, start, end)
            significance, qualifier = qualifiers[0]
            directions = [m for m in DIRECTION_RX.finditer(unit) if _local_direction(unit, m)
                          if not re.search(r'\b(?:no|not|without|failed\s+to)\s+(?:\w+\s+){0,3}$', unit[:m.start()], re.I)]
            direction = None
            if len(directions) == 1:
                direction = 'increase' if directions[0]['increase'] else 'decrease'
            else:
                gap('effect_direction_unresolved', index, start, end)
            p_match = p_values[0]
            if not 0 <= Decimal(p_match['value']) <= 1:
                gap('p_value_out_of_range', index, start, end)
                continue
            regimen, comparator, regimen_spans, comparator_spans = comparison
            provenance = {'source_unit': [_span(paper, index, start, end)],
                'regimen': regimen_spans, 'comparator': comparator_spans,
                'endpoint': [_span(paper, index, start + endpoints[0].start(), start + endpoints[0].end())],
                'significance': [_span(paper, index, start + qualifier.start(), start + qualifier.end())],
                'p_value': [_span(paper, index, start + p_match.start('value'), start + p_match.end('value'))]}
            if molecular is not None and molecular_span:
                provenance['molecular'] = [molecular_span]
            if direction:
                provenance['effect_direction'] = [_span(paper, index,
                    start + directions[0].start(), start + directions[0].end())]
            add('survival_significance', regimen, comparator, molecular, next(iter(types)),
                significance=significance, p_value=_decimal(p_match['value']), effect_direction=direction, provenance=provenance)
    if not records:
        gap('no_supported_facts', detail='No result matched the two declared source-pattern families.')
    return {'format': FORMAT, 'source_id': source_id, 'source_sha256': fingerprint,
            'paper': deepcopy(paper), 'records': records, 'coverage_gaps': gaps,
            'compiler': {'policy': 'source-patterns.v1', 'therapy_vocabulary': list(THERAPIES),
                         'limitations': LIMITATIONS[:]}}


def validate_dossier(dossier, paper=None):
    """Strict deterministic replay rejects semantic field swaps and span edits."""
    if not isinstance(dossier, dict) or dossier.get('format') != FORMAT or not isinstance(dossier.get('paper'), dict):
        raise ValueError('Invalid source-fact dossier.')
    embedded = dossier['paper']
    if paper is not None and embedded != paper:
        raise ValueError('Source-fact dossier does not bind the supplied paper.')
    if dossier != compile_source(embedded):
        raise ValueError('Source-fact dossier changed or fails deterministic source replay.')
    return dossier
