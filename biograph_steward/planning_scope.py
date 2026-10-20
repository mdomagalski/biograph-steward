"""Conservative request-scope checks and disjoint tool argument schemas.

These checks describe implemented tool limits, not biological truth. They are
deliberately lexical and may decline unfamiliar/ambiguous wording.
"""
import re

from .entity_resolution import resolved_ids

POLICY = 'bounded-request-scope.v1'


def request_scope(question, resolution, civic_available):
    question = ' '.join(question.split())
    def has(pattern):
        return re.search(pattern, question, re.IGNORECASE) is not None
    blocked = []
    rules = {
        'causal_proof': r'\b(?:prove|establish|demonstrate)\b.{0,120}\b(?:causes?|causal(?:ity)?|causation)\b',
        'clinical_recommendation': r'\bprescrib(?:e|ing)\b|\b(?:recommend|choose)\b.{0,50}\b(?:treatment|drug)\b',
        'prediction': r'\bpredict\b|\bforecast\b|\bmake\s+(?:a\s+)?prediction\b',
        'write_or_code': r'\b(?:run|execute)\b.{0,40}\b(?:shell|code|commands?)\b|\b(?:accept|reject|delete|edit|modify)\b.{0,45}\b(?:assertions?|graph|reviews?|data)\b',
        'disease_equivalence': r'\b(?:treat\w*|equat\w*|merge|consider)\b.{0,150}\b(?:same disease|equivalent|identical)\b',
        'monotherapy_filter': r'\b(?:only|solely|restrict\w*\s+to)\b.{0,35}\b(?:monotherapy|single[- ]drug)\b|\b(?:monotherapy|single[- ]drug)\s+only\b|\bexclud\w*\b.{0,35}\b(?:combinations?|multi[- ]therapy)\b',
        'direction_filter': r'\b(?:only|filter(?:ed)?(?:\s+by)?)\s+(?:(?:supports|does\s+not\s+support)\s+)?(?:resistance|sensitivity)\b|\bfilter\b.{0,20}\bdirection\b',
        'unsupported_condition_filter': r'\b(?:only|filter|restrict)\b.{0,45}\b(?:evidence\s+level|level\s+[A-E]|germline|somatic|assay|trial\s+phase)\b'}
    for name, pattern in rules.items():
        if has(pattern):
            blocked.append(name)
    relations = []
    if has(r'\binteract(?:ions?|s|ing)?\b'):
        relations.append('interactions')
    if has(r'\bshared\s+pathways?\b|\bpathway\s+annotations\b'):
        relations.append('shared_pathways')
    candidate = False
    for m in re.finditer(r'\b(?:candidates?|unreviewed)\b', question, re.IGNORECASE):
        prefix = question[max(0, m.start()-45):m.start()]
        if not re.search(r"\b(?:without|exclude|excluding|not|never|no|don't)\s+(?:\w+\s+){0,3}$", prefix, re.IGNORECASE):
            candidate = True
    if candidate and has(r'\bonly\b.{0,30}\baccepted\b|\baccepted\s+only\b'):
        blocked.append('conflicting_evidence_views')
    civic = has(r'\b(?:civic|therap(?:y|ies)|response|resistance|sensitivity|cetuximab|panitumumab)\b')
    kind = 'profiles' if civic else 'proteins'
    if resolution[kind]['ambiguous_mentions'] or resolution[kind]['incomplete_compound_mentions']:
        blocked.append('ambiguous_or_incomplete_entity')
    ids = resolved_ids(resolution, kind)
    if civic:
        if not civic_available:
            blocked.append('civic_source_unavailable')
        if not ids and not resolution['all_profiles_explicit']:
            blocked.append('unresolved_complete_profile')
        if len(ids) > 1 and not resolution['all_profiles_explicit']:
            blocked.append('multiple_profiles_require_a_subset_tool')
        if not resolved_ids(resolution, 'therapies'):
            blocked.append('no_explicit_supported_therapy')
        if relations:
            blocked.append('multiple_tool_requirements')
    else:
        if len(ids) != 1:
            blocked.append('unresolved_or_multiple_protein_anchors')
        if resolved_ids(resolution, 'profiles'):
            blocked.append('variant_qualified_protein_query')
    return {'policy': POLICY, 'family': 'civic_therapy' if civic else 'protein_neighborhood',
            'view': 'candidates' if candidate else 'accepted', 'explicit_relations': relations,
            'unsupported_requirements': sorted(set(blocked)),
            'basis': 'Conservative lexical capability checks; not a general intent or biological-validity classifier.'}


def tool_schema(graph, resolution, scope):
    """One complete shape per tool: irrelevant arguments cannot be populated."""
    reason = {'type': 'string'}
    null = {'type': 'null'}
    empty = {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 0}
    def value(item):
        return {'type': 'string', 'enum': [item]}
    def branch(properties):
        # One brief public explanation precedes the choice; no private reasoning.
        order = ['reason', 'action', 'tool', 'view', 'disease_id', 'protein_id', 'profile_id', 'therapy', 'relations']
        return {'type': 'object', 'additionalProperties': False, 'required': order,
                'properties': {k: properties[k] for k in order}}
    abstain = branch({'reason': reason, 'action': value('abstain'), 'tool': null,
                      'view': value('accepted'), 'disease_id': null, 'protein_id': null,
                      'profile_id': null, 'therapy': null, 'relations': empty})
    branches = [abstain]
    if not scope['unsupported_requirements']:
        common = {'reason': reason, 'action': value('query'), 'view': value(scope['view'])}
        if scope['family'] == 'protein_neighborhood':
            relations = scope['explicit_relations'] or ['interactions', 'shared_pathways']
            branches.append(branch({**common, 'tool': value('protein_neighborhood'),
                'disease_id': value(graph['disease_node_id']),
                'protein_id': {'type': 'string', 'enum': resolved_ids(resolution, 'proteins')},
                'profile_id': null, 'therapy': null,
                'relations': {'type': 'array', 'items': {'type': 'string', 'enum': relations},
                              'minItems': len(relations) if scope['explicit_relations'] else 1, 'maxItems': len(relations)}}))
        elif graph.get('civic'):
            profiles = ['all'] if resolution['all_profiles_explicit'] else resolved_ids(resolution, 'profiles')
            therapies = resolved_ids(resolution, 'therapies')
            therapy = 'both' if len(therapies) == 2 else therapies[0]
            branches.append(branch({**common, 'tool': value('civic_therapy'), 'disease_id': value('DOID:9256'),
                                   'protein_id': null, 'profile_id': {'type': 'string', 'enum': profiles},
                                   'therapy': value(therapy), 'relations': empty}))
    return {'anyOf': branches}


def validate_request_scope(plan, scope):
    if plan['action'] == 'abstain':
        return
    if scope['unsupported_requirements'] or plan['tool'] != scope['family'] or plan['view'] != scope['view']:
        raise ValueError('Plan violates the application request-scope constraints.')
    if plan['tool'] == 'protein_neighborhood' and scope['explicit_relations']:
        if sorted(plan['relations']) != sorted(scope['explicit_relations']):
            raise ValueError('Plan changes the explicit requested relation scope.')
