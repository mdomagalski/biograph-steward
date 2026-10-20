"""Bounded clause/target handling for scoped_targets_v4.

This is a conservative lexical interface, not a general language or biological
expression parser. Raw identities remain auditable; unknown required scopes
must not be replaced with a nearby supported query.
"""
from copy import deepcopy
import re

from .client import digest
from .entity_resolution import resolve_mentions, resolved_ids
from .planning_scope import request_scope as legacy_scope

POLICY = 'bounded-target-scope.v2'
BOUNDARY = re.compile(r'[;,\n]|[.!?](?=\s|$)|\b(?:but|instead|however)\b', re.I)
CUE = re.compile(
    r"\b(?P<retain>(?:do\s+not|don't|never)\s+exclud\w*)\b|"
    r"\b(?P<negative>(?:do\s+not|don't|never)\s+(?:include|query|show|use|select|inspect|return|retain)|exclude|excluding|without|not|no)\b|"
    r'\b(?P<positive>include|query|show|use|select|inspect|return|retain|request|list)\b', re.I)
ENTITY_NEGATION = re.compile(
    r"\b(?:(?:do\s+not|don't|never)\s+(?:include|query|show|use|select|inspect|return)|not|without|exclude|excluding)"
    r'\s+(?:(?:the|a|an|protein|gene|profile|molecular|therapy|drug|target|anchor)\s+)*$', re.I)
BACKGROUND = re.compile(
    r'\s+(?:is|are)\s+(?:(?:only|just)\s+)?(?:background\b|context\b|not\s+(?:(?:a|the|our|requested|selected|query)\s+)*(?:target|anchor)\b)', re.I)
RELATIONS = {'interactions': r'\binteract(?:ions?|s|ing)?\b',
             'shared_pathways': r'\bshared\s+pathways?\b|\bpathway\s+annotations\b'}


def _context(question, start, end):
    before = [m.end() for m in BOUNDARY.finditer(question) if m.end() <= start]
    after = [m.start() for m in BOUNDARY.finditer(question) if m.start() >= end]
    return question[max(before, default=0):start], question[end:min(after, default=len(question))]


def _role(question, start, end, *, entity=False):
    prefix, suffix = _context(question, start, end)
    if BACKGROUND.match(suffix) or re.search(r'\b(?:background|context)\s+(?:(?:drug|therapy|protein|profile|mention)\s+)?$', prefix, re.I):
        return 'background'
    if re.search(r"\b(?:not\s+not|without\s+not|do\s+not\s+(?:avoid|omit|deny))\b", prefix, re.I):
        return 'ambiguous'
    if entity:
        # A negative evidence-view/relation modifier does not negate its anchor:
        # "exclude candidate ALPHA interactions" still mentions anchor ALPHA.
        excluded = bool(ENTITY_NEGATION.search(prefix))
        if excluded and re.match(r'\s+(?:as|from)\s+(?:(?:a|the|our|query)\s+)*(?:target|anchor)\b', suffix, re.I):
            return 'background'
        return 'excluded' if excluded else 'requested'
    cues = list(CUE.finditer(prefix))
    return 'excluded' if cues and cues[-1].lastgroup == 'negative' else 'requested'


def _classified(question, pattern, *, relation=False):
    rows = []
    for match in re.finditer(pattern, question, re.I):
        role = _role(question, match.start(), match.end())
        if relation and role == 'excluded':
            prefix, _ = _context(question, match.start(), match.end())
            cues = list(CUE.finditer(prefix))
            # In "exclude candidate ALPHA interactions", the excluded object
            # is the candidate evidence view, not all interactions for ALPHA.
            if cues and re.search(r'\b(?:candidates?|unreviewed)\b', prefix[cues[-1].end():], re.I):
                role = 'requested'
        rows.append({'surface': match.group(), 'start': match.start(), 'end': match.end(), 'role': role})
    return rows


def _compound_extension(question, mention, raw):
    """Detect logical composition outside a whole known profile span.

    AND/OR joining a profile to a drug, disease or record clause is a normal
    question conjunction. Unknown molecular operands are never discarded.
    """
    left, right = question[:mention['start']], question[mention['end']:]
    following = re.match(r'\s*[)\]]*\s+(?:and|or)\b\s*[(\[]*\s*', right, re.I)
    preceding = re.search(r'\b(and|or|not)\s*[(\[]*\s*$', left, re.I)
    other_mentions = [m for kind in ['therapies', 'diseases'] for m in raw[kind]['mentions']]
    if following:
        index = mention['end'] + following.end()
        natural = re.match(r'(?:records?|evidence|annotations?|therap(?:y|ies)|response|treatment|the\s+records?)\b', question[index:], re.I)
        if not natural and not any(m['start'] == index for m in other_mentions):
            return True
    if preceding:
        if preceding.group(1).casefold() == 'not':
            return True
        index = len(left[:preceding.start()].rstrip(' \t\r\n)]'))
        if not any(m['end'] == index for m in other_mentions):
            return True
    return False


def resolve_targets(question, catalogue):
    raw = resolve_mentions(question, catalogue)
    result = deepcopy(raw)
    roles, conflicts = {}, []
    labels = {
        'proteins': {p['id']: p.get('symbol') or p['id'] for p in catalogue['proteins']},
        'profiles': {p['id']: p['name'] for p in catalogue['profiles']},
        'diseases': {d['id']: d['name'] for d in [catalogue['pharos_disease'], catalogue.get('civic_disease')] if d},
        'therapies': {n: n for n in ['cetuximab', 'panitumumab']}}
    for kind in labels:
        roles[kind] = [{**m, 'role': _role(question, m['start'], m['end'], entity=True)} for m in raw[kind]['mentions']]
        active = [m for m in roles[kind] if m['role'] == 'requested']
        selected = {i for m in active if len(m['ids']) == 1 for i in m['ids']}
        suppressed = {i for m in roles[kind] if m['role'] in {'excluded', 'background'} for i in m['ids']}
        conflicts.extend({'kind': kind, 'id': i} for i in sorted(selected & suppressed))
        incomplete = [m for m in active if kind == 'profiles' and _compound_extension(question, m, raw)]
        blocked = {i for m in incomplete for i in m['ids']}
        result[kind]['resolved'] = [{'id': i, 'label': labels[kind][i]} for i in sorted(selected - blocked)]
        result[kind]['ambiguous_mentions'] = [m for m in active if len(m['ids']) != 1]
        result[kind]['incomplete_compound_mentions'] = incomplete
    all_profiles = _classified(question, r'\ball\s+(?:molecular\s+)?profiles\b')
    result['all_profiles_explicit'] = any(m['role'] == 'requested' for m in all_profiles)
    result['policy'] = 'catalogue-scoped-targets.v2'
    result['matching'] = 'Exact catalogue identities with bounded clause polarity; no fuzzy aliases or ontology equivalence.'
    result['target_selection'] = {'policy': POLICY, 'raw_resolution_sha256': digest(raw), 'mentions': roles,
                                  'all_profiles_mentions': all_profiles, 'conflicting_entities': conflicts,
                                  'source_diseases': {'protein_neighborhood': catalogue['pharos_disease']['id'],
                                                      'civic_therapy': catalogue.get('civic_disease', {}).get('id') if catalogue.get('civic_disease') else None}}
    return result


def _policy_text(question, resolution, roles):
    """Mask only explicit standalone disclaimers and non-target mentions.

    Positive instructions after a boundary remain visible. Coordinated or
    double-negated action wording stays unmasked and conservatively blocked.
    """
    spans = [(m['start'], m['end']) for mentions in roles.values() for m in mentions if m['role'] != 'requested']
    spans += [(m['start'], m['end']) for mentions in resolution['target_selection']['mentions'].values()
              for m in mentions if m['role'] != 'requested']
    start = 0
    for boundary in [*BOUNDARY.finditer(question), None]:
        end = boundary.start() if boundary else len(question)
        clause = question[start:end].strip()
        disclaimer = re.match(r"^(?:please\s+)?(?:do\s+not|don't|never)\s+(?:recommend|prescribe|prove|predict|forecast|run|execute|accept|reject|delete|edit|modify)\b", clause, re.I)
        coordinated = re.search(r'\b(?:and|or|then|also|fail|refuse|avoid)\b', clause, re.I)
        if disclaimer and not coordinated:
            spans.append((start, end))
        if boundary:
            start = boundary.end()
    chars = list(question)
    for begin, end in spans:
        chars[begin:end] = ' ' * (end - begin)
    return ''.join(chars)


def request_scope(question, resolution, civic_available):
    roles = {name: _classified(question, pattern, relation=True) for name, pattern in RELATIONS.items()}
    roles['candidates'] = _classified(question, r'\b(?:candidates?|unreviewed)\b')
    roles['accepted'] = _classified(question, r'\baccepted\b')
    roles['civic_words'] = _classified(question, r'\b(?:civic|therap(?:y|ies)|response|resistance|sensitivity|cetuximab|panitumumab)\b')
    policy_text = _policy_text(question, resolution, roles)
    scope = legacy_scope(policy_text, resolution, civic_available)
    blocked = set(scope['unsupported_requirements']) - {'multiple_tool_requirements', 'conflicting_evidence_views'}
    positive = lambda name: any(m['role'] == 'requested' for m in roles[name])
    negative = lambda name: any(m['role'] == 'excluded' for m in roles[name])
    relations = [name for name in RELATIONS if positive(name)]
    excluded_relations = [name for name in RELATIONS if negative(name)]
    if any(positive(name) and negative(name) for name in RELATIONS):
        blocked.add('conflicting_relation_targets')
    candidate = positive('candidates')
    accepted_only = False
    for mention in roles['accepted']:
        prefix, suffix = _context(question, mention['start'], mention['end'])
        if mention['role'] == 'requested' and (re.search(r'\bonly\s+(?:(?:locally|local|human|reviewed|evidence|through|review)\s+){0,4}$', prefix, re.I)
                                               or re.match(r'\s+only\b', suffix, re.I)):
            accepted_only = True
    if candidate and (negative('candidates') or accepted_only):
        blocked.add('conflicting_evidence_views')
    if negative('accepted'):
        blocked.add('unsupported_accepted_evidence_exclusion')
    selection = resolution['target_selection']
    if selection['conflicting_entities'] or any(m['role'] == 'ambiguous' for mentions in [*roles.values(), *selection['mentions'].values(), selection['all_profiles_mentions']] for m in mentions):
        blocked.add('ambiguous_target_scope')
    family = scope['family']
    disease_ids = resolved_ids(resolution, 'diseases')
    expected = selection['source_diseases'][family]
    if len(disease_ids) > 1:
        blocked.add('multiple_disease_targets')
    if disease_ids and expected not in disease_ids:
        blocked.add('source_disease_mismatch')
    known_diseases = {i.casefold() for i in selection['source_diseases'].values() if i}
    if any(m.group().casefold() not in known_diseases for m in re.finditer(r'\b(?:MONDO|DOID):[\w-]+', policy_text, re.I)):
        blocked.add('unresolved_disease_identifier')
    if family == 'civic_therapy' and relations:
        blocked.add('multiple_tool_requirements')
    if family == 'protein_neighborhood':
        if excluded_relations and not relations:
            blocked.add('no_positive_relation_target')
        if any(m['role'] == 'excluded' for m in selection['mentions']['proteins']):
            blocked.add('unsupported_protein_exclusion')
    if family == 'civic_therapy':
        if any(m['role'] == 'excluded' for m in selection['mentions']['therapies']):
            blocked.add('unsupported_therapy_exclusion')
        if resolution['all_profiles_explicit'] and any(m['role'] == 'excluded' for m in selection['mentions']['profiles']):
            blocked.add('unsupported_profile_subset')
        if re.search(r'\b(?:exclude|excluding|without)\b[^.;\n]{0,50}\brecords?\s+(?:containing|with)\b', question, re.I):
            blocked.add('unsupported_record_exclusion')
    scope.update(policy=POLICY, view='candidates' if candidate else 'accepted', explicit_relations=relations,
                 excluded_relations=excluded_relations, unsupported_requirements=sorted(blocked),
                 target_mentions=roles, policy_text_sha256=digest(policy_text),
                 basis='Bounded clause/target rules; unfamiliar or ambiguous requirements still need clarification. Not biological validation.')
    return scope
