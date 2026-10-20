"""Exact mention binding to a frozen catalogue; no external aliases or inference."""
import re

POLICY = 'catalogue-exact-mentions.v1'


def _normal(value):
    return ' '.join(value.split()).casefold()


def _mentions(question, entries, *, longest=False):
    aliases = {}
    labels = {}
    for identifier, label, names in entries:
        labels[identifier] = label
        for name in names:
            if isinstance(name, str) and name.strip():
                aliases.setdefault(_normal(name), set()).add(identifier)
    matches = []
    for alias, identifiers in sorted(aliases.items()):
        pattern = r'(?<![\w])' + r'\s+'.join(re.escape(s) for s in alias.split()) + r'(?![\w])'
        for match in re.finditer(pattern, question, re.IGNORECASE):
            if _normal(match.group()) != alias:
                continue
            matches.append({'surface': match.group(), 'start': match.start(), 'end': match.end(),
                            'ids': sorted(identifiers)})
    if longest:
        # A complete complex profile wins over contained simpler profiles.
        matches = [m for m in matches if not any(
            n['start'] <= m['start'] and n['end'] >= m['end']
            and (n['start'], n['end']) != (m['start'], m['end']) for n in matches)]
    matches.sort(key=lambda m: (m['start'], -m['end'], m['ids']))
    ambiguous = [m for m in matches if len(m['ids']) != 1]
    resolved = sorted({m['ids'][0] for m in matches if len(m['ids']) == 1})
    # Do not infer that a recognised subprofile represents an unknown larger
    # expression. This catches explicit symbolic composition, not arbitrary NLP.
    incomplete = []
    if longest:
        for m in matches:
            left, right = question[:m['start']], question[m['end']:]
            if (re.search(r'\b(?:AND|OR|NOT)\s*$', left)
                    or re.match(r'\s+(?:AND|OR)\b', right)):
                incomplete.append(m)
        blocked = {i for m in incomplete for i in m['ids']}
        resolved = [i for i in resolved if i not in blocked]
    return {'resolved': [{'id': i, 'label': labels[i]} for i in resolved],
            'mentions': matches, 'ambiguous_mentions': ambiguous,
            'incomplete_compound_mentions': incomplete}


def resolve_mentions(question, catalogue):
    """Case-insensitive exact IDs/names/symbols, with whitespace flexibility.

    Symbols are protein identities, never aliases for variant profiles. Profile
    names preserve AND/OR/NOT. Distinct disease vocabularies remain distinct.
    Mentions are identity hints, not an answer, intent classification or plan.
    """
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 4000:
        raise ValueError('Planner question must contain 1–4000 characters.')
    proteins = [(p['id'], p.get('symbol') or p['id'], [p['id'], p.get('symbol')])
                for p in catalogue['proteins']]
    profiles = [(p['id'], p['name'], [p['id'], p['name']]) for p in catalogue['profiles']]
    diseases = [(d['id'], d['name'], [d['id'], d['name']])
                for d in [catalogue['pharos_disease'], catalogue.get('civic_disease')] if d]
    therapies = [(name, name, [name]) for name in ['cetuximab', 'panitumumab']]
    return {'policy': POLICY, 'matching': 'Exact IDs, symbols and complete names only; no fuzzy or ontology equivalence.',
            'proteins': _mentions(question, proteins), 'profiles': _mentions(question, profiles, longest=True),
            'diseases': _mentions(question, diseases), 'therapies': _mentions(question, therapies),
            'all_profiles_explicit': bool(re.search(r'\ball\s+(?:molecular\s+)?profiles\b', question, re.IGNORECASE))}


def resolved_ids(resolution, kind):
    return [item['id'] for item in resolution[kind]['resolved']]


def validate_bindings(plan, resolution):
    """Reject unmentioned selections; never silently repair the model's plan."""
    if plan['action'] == 'abstain':
        return
    diseases = resolved_ids(resolution, 'diseases')
    if resolution['diseases']['ambiguous_mentions'] or diseases and plan['disease_id'] not in diseases:
        raise ValueError('Planned disease does not match an exact question mention.')
    kind, field = ('proteins', 'protein_id') if plan['tool'] == 'protein_neighborhood' else ('profiles', 'profile_id')
    if resolution[kind]['ambiguous_mentions'] or resolution[kind]['incomplete_compound_mentions']:
        raise ValueError('Question entity is ambiguous or an incomplete compound profile.')
    if plan[field] == 'all' and kind == 'profiles':
        if not resolution['all_profiles_explicit']:
            raise ValueError('All profiles must be requested explicitly.')
    elif plan[field] not in resolved_ids(resolution, kind):
        raise ValueError('Planned entity does not match an exact question mention.')
    if kind == 'profiles':
        therapies = resolved_ids(resolution, 'therapies')
        required = ['cetuximab', 'panitumumab'] if plan['therapy'] == 'both' else [plan['therapy']]
        if sorted(required) != sorted(therapies):
            raise ValueError('Planned therapy does not preserve the explicit therapy scope.')
