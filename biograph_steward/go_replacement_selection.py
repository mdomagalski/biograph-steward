"""Shared source-only GO replacement selection for portable native-GOA replay.

These deterministic policies and selectors are the existing census code moved
into the installed application; the tool remains its source-verifying wrapper.
No graph edit, qualifier backfill or experimental truth label is introduced.
"""
from collections import Counter, defaultdict
from . import go_ontology_qualification, go_qualification
from .go_native_support import exclusion_reasons, POLICY as REFERENCE_POLICY

FORMAT = 'biograph-steward.go-replacement-census.v1'
REPORT = 'go_ontology_qualification.json'
METHOD = {
    'replacement_scope': 'Only one explicit active replaced_by for an obsolete main annotation term; never consider, aliases, ancestors or guessed replacements.',
    'native_compatibility': ['exact_UniProt_accession', 'replacement_GO_ID', 'evidence_code', 'assigned_by', 'aspect'],
    'experimental_scope': REFERENCE_POLICY,
    'concept_overlap': 'Exact subject and replacement GO ID among retained GO annotation edges. This does not assert equal native relation, reference, polarity, context or evidence identity.',
    'convergence': 'Multiple old edges can converge on one subject/replacement concept or one native record. Count and list each level separately.',
    'application': 'Audit only. No proposal is applied and no old review state or missing qualifier is inherited.',
}


def need(condition, message):
    if not condition:
        raise ValueError('GO replacement audit: ' + message)


def projection(edge, term=None):
    r = edge['evidence_record']
    return (edge['subject'], term or edge['object'], r.get('evidence'), r.get('assigned_by'), r.get('type'))


def candidate_gaf(headers, records, source_sha256):
    """Standard subset with exact native annotation bodies, never repaired rows."""
    need(headers and headers[0] == '!gaf-version: 2.2', 'expected original GAF2.2 headers.')
    need(len({r['id'] for r in records}) == len(records)
         and len({r['source_line'] for r in records}) == len(records), 'duplicate export record.')
    body = []
    for row in sorted(records, key=lambda r: r['source_line']):
        need(row['source_gaf_sha256'] == source_sha256 and not row['negated']
             and not exclusion_reasons(row) and len(row['raw_line'].split('\t')) == 17,
             'native candidate export is outside qualified scope.')
        body.append(row['raw_line'])
    comments = ['!subset: BioGraph Steward qualified GO replacement candidates; not the complete source release',
                '!source-gaf-sha256: ' + source_sha256]
    return '\n'.join([*headers, *comments, *body]) + '\n'


def classify(baseline, retained, proposals, native, ontology_nodes):
    """Source-only census; overlap and qualified experimental support are distinct."""
    by_edge = {e['id']: e for e in baseline['edges']}
    need(len(by_edge) == len(baseline['edges']), 'duplicate baseline edge ID.')
    expected = []
    for edge in baseline['edges']:
        if edge.get('record_kind') == 'go_annotation':
            result = go_ontology_qualification.classify_term(edge['object'], ontology_nodes)
            if result['replacement_proposal'] is not None:
                expected.append({'edge_id': edge['id'], **result['replacement_proposal']})
    need(proposals == expected, 'proposal inventory differs from exact ontology replay.')
    need(len({p['edge_id'] for p in proposals}) == len(proposals), 'duplicate proposal edge.')
    retained_ids = {e['id'] for e in retained['edges']}
    concepts, projections = defaultdict(list), defaultdict(list)
    for edge in retained['edges']:
        if edge.get('record_kind') == 'go_annotation':
            concepts[(edge['subject'], edge['object'])].append(edge['id'])
            projections[projection(edge)].append(edge['id'])
    # This transient key projection is NOT a new annotation or graph. It only
    # asks the existing matcher about an explicitly declared replacement key.
    queries = []
    for p in proposals:
        edge = by_edge[p['edge_id']]
        need(edge.get('record_kind') == 'go_annotation' and p['from_id'] == edge['object']
             and edge['evidence_record'].get('goid') == edge['object'], 'proposal source mismatch.')
        need(p['edge_id'] not in retained_ids, 'obsolete proposal source remains in retained graph.')
        queries.append({'id': edge['id'], 'assertion_id': edge.get('assertion_id'),
            'record_kind': 'go_annotation', 'subject': edge['subject'], 'object': p['to_id'],
            'evidence_record': {'goid': p['to_id'], 'evidence': edge['evidence_record'].get('evidence'),
                'assigned_by': edge['evidence_record'].get('assigned_by'), 'type': edge['evidence_record'].get('type')}})
    links = go_qualification.project_compatibilities({'edges': queries}, native)
    native_by_id = {r['id']: r for r in native}
    need(len(native_by_id) == len(native), 'duplicate native record ID.')
    rows = []
    for p, link in zip(proposals, links):
        edge = by_edge[p['edge_id']]
        candidates = [native_by_id[uid] for uid in link['native_record_ids']]
        gates = [{'native_record_id': r['id'], 'excluded_because': exclusion_reasons(r),
                  'negated': r['negated']} for r in candidates]
        admitted = [r for r, g in zip(candidates, gates) if not g['excluded_because']]
        positive = sorted(r['id'] for r in admitted if not r['negated'])
        negative = sorted(r['id'] for r in admitted if r['negated'])
        qualified = bool(positive) and not negative
        key = (edge['subject'], p['to_id'])
        concept_present = bool(concepts[key])
        status = ('qualified_experimental_concept_already_present' if concept_present else
                  'qualified_experimental_concept_not_present') if qualified else (
                  'opposing_eligible_NOT_held_unresolved' if negative else
                  'strict_native_candidates_outside_experimental_context_scope' if candidates else
                  'same_subject_term_only_projection_fields_differ' if link['exact_subject_go_native_record_ids'] else
                  'no_native_subject_replacement_term')
        rows.append({'original_edge_id': edge['id'], 'original_assertion_id': edge.get('assertion_id'),
            'subject': edge['subject'], 'from_id': p['from_id'], 'to_id': p['to_id'],
            'proposal': p, 'hypothetical_compatibility_key': link['compatibility_key'],
            'native_projection_status': link['status'],
            'same_subject_term_native_record_ids': link['exact_subject_go_native_record_ids'],
            'strict_native_record_ids': link['native_record_ids'],
            'same_subject_term_projection_differences': link['unmatched_projection_field_differences'],
            'native_context_eligibility': gates, 'eligible_positive_record_ids': positive,
            'eligible_NOT_record_ids': negative, 'qualified_unopposed_experimental_support': qualified,
            'retained_same_concept_edge_ids': sorted(concepts[key]),
            'retained_same_projection_edge_ids': sorted(projections[projection(edge, p['to_id'])]),
            'concept_already_present': concept_present, 'status': status,
            'proposal_applied': False, 'historical_native_record_identity_established': False,
            'original_qualifiers_backfilled': False, 'biological_truth_assessed': False})
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['subject'], row['to_id'])].append(row)
    concept_rows, additions = [], set()
    for (subject, term), group in sorted(grouped.items()):
        qualified_ids = sorted({uid for r in group if r['qualified_unopposed_experimental_support']
                                for uid in r['eligible_positive_record_ids']})
        opposing_ids = sorted({uid for r in group for uid in r['eligible_NOT_record_ids']})
        present = bool(concepts[(subject, term)])
        concept_rows.append({'subject': subject, 'to_id': term,
            'original_edge_ids': sorted(r['original_edge_id'] for r in group),
            'original_term_ids': sorted({r['from_id'] for r in group}),
            'qualified_positive_native_record_ids': qualified_ids,
            'eligible_NOT_native_record_ids': opposing_ids,
            'retained_same_concept_edge_ids': sorted(concepts[(subject, term)]),
            'qualified_nonduplicate_concept': bool(qualified_ids) and not opposing_ids and not present})
        if qualified_ids and not opposing_ids and not present:
            additions.update(qualified_ids)
    counts = {'proposals': len(rows), 'distinct_subject_replacement_concepts': len(grouped),
        'converging_proposals_beyond_distinct_concepts': len(rows) - len(grouped),
        'proposals_with_native_subject_term': sum(bool(r['same_subject_term_native_record_ids']) for r in rows),
        'proposals_with_strict_projection_candidates': sum(bool(r['strict_native_record_ids']) for r in rows),
        'proposals_with_qualified_experimental_support': sum(r['qualified_unopposed_experimental_support'] for r in rows),
        'proposals_with_eligible_opposing_NOT': sum(bool(r['eligible_NOT_record_ids']) for r in rows),
        'proposals_with_concept_already_present': sum(r['concept_already_present'] for r in rows),
        'proposals_with_same_projection_already_present': sum(bool(r['retained_same_projection_edge_ids']) for r in rows),
        'distinct_qualified_experimental_concepts': sum(bool(r['qualified_positive_native_record_ids']) and not r['eligible_NOT_native_record_ids'] for r in concept_rows),
        'qualified_nonduplicate_concepts': sum(r['qualified_nonduplicate_concept'] for r in concept_rows),
        'qualified_nonduplicate_native_records': len(additions),
        'distinct_strict_native_records': len({uid for r in rows for uid in r['strict_native_record_ids']}),
        'distinct_qualified_positive_native_records': len({uid for r in rows if r['qualified_unopposed_experimental_support'] for uid in r['eligible_positive_record_ids']}),
        'status_counts': dict(Counter(r['status'] for r in rows)),
        'strict_candidate_context_exclusions': dict(Counter(reason for r in rows for g in r['native_context_eligibility'] for reason in g['excluded_because']))}
    return rows, concept_rows, [native_by_id[uid] for uid in sorted(additions)], counts
