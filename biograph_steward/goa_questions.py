"""Read-only questions over independently source-replayed native GO additions.

The annotations retain their own GO relations, references and review states.
They do not repair the historical Pharos rows, imply a disease context or
represent independent experiments merely because another provider lists them.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import json
import re

from .assertions import assertion_identity
from .client import digest
from .inspection import _external_url
from .normalization import GO_CATEGORIES
from .questions import graph_basis

FORMAT = 'biograph-steward.native-go-question.v1'
TEMPLATE = 'native_go_evidence.v1'
KIND = 'native_go_annotation'
PREDICATE = 'biograph:has_native_go_annotation'
INTERPRETATION = ('Native GO annotations with their recorded relation, evidence code and supporting reference. '
    'These are separately sourced additions, not rewritten Pharos records or independent experimental validation. '
    'Membership in this protein cohort does not make the annotation disease-specific.')
INSPECTABLE = frozenset({'candidate', 'provisional', 'accepted'})


def _need(value, message):
    if not value:
        raise ValueError('Native GO question: ' + message)


def _index(rows, label):
    _need(isinstance(rows, list) and all(isinstance(r, dict) and isinstance(r.get('id'), str)
          and r['id'] for r in rows), 'saved ' + label + ' identities are missing.')
    result = {r['id']: r for r in rows}
    _need(len(result) == len(rows), 'saved ' + label + ' identities repeat.')
    return result


def _source_copy(observation):
    """Gold retention metadata describes the view, not the native source body."""
    retention = observation.get('retention')
    if retention is not None:
        _need(isinstance(retention, dict) and set(retention) == {'baseline_graph_edge_id', 'decision'}
              and isinstance(retention['baseline_graph_edge_id'], str)
              and retention['decision'] in {'keep', 'prune', 'abstain'}, 'saved retention metadata differs.')
        expected = None if retention['decision'] == 'prune' else retention['baseline_graph_edge_id']
        _need(observation.get('graph_edge_id') == expected, 'retention and current graph edge disagree.')
    return {k: deepcopy(v) for k, v in observation.items() if k != 'retention'}


def _record(original, graph, nodes, edges, assertions, primary, publication, policy):
    from .goa_source import _citation, validate_native_record
    saved = _source_copy(original)
    native = saved.get('native_record')
    _need(isinstance(native, dict), 'complete native annotation is missing.')
    validate_native_record(native, policy=policy)
    subject, term = native['subject'], native['go_id']
    _need(subject in primary and subject in nodes and nodes[subject].get('category') == 'biolink:Protein'
          and term in nodes and nodes[term].get('category') == GO_CATEGORIES[native['aspect']],
          'native annotation endpoints differ from the exact saved protein/GO scope.')
    _need(saved.get('source_kind') == 'goa' and saved.get('subject') == subject and saved.get('go_id') == term
          and saved.get('relation_literal') == native['relation_literal']
          and saved.get('evidence_code') == native['evidence_code']
          and saved.get('assigned_by') == native['assigned_by']
          and isinstance(saved.get('go_label'), str) and saved['go_label']
          and saved.get('publications') == native['reference_identifiers'],
          'annotation fields differ from the complete native row.')
    _need(saved.get('source_publication_sha256') == publication
          and isinstance(saved.get('source'), dict)
          and saved['source'].get('publication_sha256') == publication,
          'native source publication binding differs.')
    eid = saved.get('graph_edge_id')
    if eid is None:
        _need(original.get('retention', {}).get('decision') == 'prune',
              'source annotation lacks a retained edge or explicit prune disposition.')
        return None
    edge = edges.get(eid)
    qualifiers = {'go_aspect': native['aspect'], 'species': 'NCBITaxon:9606',
                  'go_relation': native['relation_literal']}
    _need(edge is not None and edge.get('record_kind') == KIND and edge.get('extension_source_kind') == 'goa'
          and edge.get('predicate') == PREDICATE and edge.get('subject') == subject and edge.get('object') == term
          and edge.get('qualifiers') == qualifiers and edge.get('symmetric', False) is False
          and edge.get('snapshot_sha256') == graph['snapshot_sha256']
          and edge.get('extension_publication_sha256') == publication
          and edge.get('source_publication_sha256') == publication
          and edge.get('evidence_record') == saved and edge.get('observation') == saved
          and edge.get('publications') == native['reference_identifiers'],
          'saved evidence edge does not reproduce the source-qualified annotation.')
    assertion = assertions.get(edge.get('assertion_id'))
    identity = assertion_identity(subject, PREDICATE, term, KIND, qualifiers)
    aid = 'assertion:' + digest(identity)[:24]
    _need(assertion is not None and assertion.get('id') == aid
          and all(assertion.get(k) == value for k, value in identity.items())
          and assertion.get('extension_source_kind') == 'goa'
          and assertion.get('evidence_extension_sha256') == graph['evidence_extension_sha256']
          and eid in assertion.get('evidence_edge_ids', [])
          and assertion.get('revision') == digest({'identity': aid, 'evidence': assertion['evidence_edge_ids']})
          and assertion.get('lifecycle_state') in {'candidate', 'provisional', 'accepted', 'quarantined', 'rejected', 'obsolete'},
          'native assertion identity, source binding or review state differs.')
    citations = saved.get('citations')
    _need(isinstance(citations, list)
          and citations == [_citation(ref) for ref in native['reference_identifiers']]
          and all(c['url'] is None or _external_url(c['url']) for c in citations),
          'native citations must preserve exact reference identifiers and their supported source URLs.')
    return {'observation_id': saved['id'], 'native_record_id': native['id'],
        'graph_edge_id': eid, 'assertion_id': aid, 'assertion_revision': assertion['revision'],
        'subject': subject, 'subject_label': nodes[subject].get('sym') or nodes[subject].get('name') or subject,
        'go_id': term, 'go_label': saved['go_label'], 'graph_go_label': nodes[term].get('name'),
        'aspect': native['aspect'], 'relation_literal': native['relation_literal'],
        'evidence_code': native['evidence_code'], 'assigned_by': native['assigned_by'],
        'reference_identifiers': deepcopy(native['reference_identifiers']),
        'reference_group_semantics': 'Identifiers on one native line may be aliases for one reference, not independent experiments.',
        'source_line': native['source_line'], 'source_gaf_sha256': native['source_gaf_sha256'],
        'local_review_state': assertion['lifecycle_state'], 'citations': deepcopy(citations),
        'source_observation': saved, 'native_record': deepcopy(native),
        'retention': deepcopy(original.get('retention')), 'interpretation': INTERPRETATION}


def answer_native_go_question(graph, protein, *, view='candidates', search='', offset=0,
                              limit=25, source_run=None):
    """Return complete native source records, grouped only by saved assertion."""
    _need(isinstance(graph, dict) and graph.get('graph_format'), 'choose a verified saved graph.')
    _need(isinstance(view, str) and view in {'candidates', 'accepted'}, 'choose candidate or accepted evidence.')
    _need(isinstance(search, str) and len(search) <= 200, 'use a search string of at most 200 characters.')
    _need(type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 25,
          'use a nonnegative offset and a page limit from 1 to 25.')
    _need(source_run is None or isinstance(source_run, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', source_run),
          'invalid saved workspace identifier.')
    nodes = _index(graph.get('nodes'), 'node')
    targets = _index(graph.get('targets'), 'primary target')
    _need(isinstance(protein, str) and protein in targets and protein in nodes
          and protein.startswith('UniProtKB:') and nodes[protein].get('category') == 'biolink:Protein',
          'choose an exact UniProtKB identifier from the primary graph targets.')
    extension = graph.get('evidence_extension')
    summary = extension.get('sources', {}).get('goa') if isinstance(extension, dict) else None
    _need(isinstance(summary, dict) and isinstance(summary.get('publication_sha256'), str)
          and summary['publication_sha256'] and graph.get('evidence_extension_sha256')
          and graph.get('snapshot_sha256'), 'this workspace has no verified native GO source addition.')
    edges, assertions = _index(graph.get('edges'), 'edge'), _index(graph.get('assertions'), 'assertion')
    observations = graph.get('extension_observations')
    _need(isinstance(observations, list) and all(isinstance(r, dict) for r in observations),
          'source observation ledger is missing.')
    source = [r for r in observations if r.get('source_kind') == 'goa']
    _need(all(isinstance(r.get('id'), str) and r['id'] for r in source)
          and len({r['id'] for r in source}) == len(source), 'native observation identities repeat or are missing.')
    from .goa_source import POLICY
    policy = summary.get('policy', POLICY)
    records = [_record(r, graph, nodes, edges, assertions, set(targets), summary['publication_sha256'], policy) for r in source]
    present = [r for r in records if r is not None]
    _need({r['graph_edge_id'] for r in present} == {e['id'] for e in edges.values()
          if e.get('extension_source_kind') == 'goa'}, 'native source ledger and current evidence inventory differ.')
    anchored = [r for r in present if r['subject'] == protein]
    allowed = {'accepted'} if view == 'accepted' else INSPECTABLE
    eligible = [r for r in anchored if r['local_review_state'] in allowed]
    query = search.strip().casefold()
    matching = [r for r in eligible if not query or query in json.dumps(
        [r['subject'], r['subject_label'], r['go_id'], r['go_label'], r['relation_literal'],
         r['evidence_code'], r['assigned_by'], r['reference_identifiers']], ensure_ascii=False).casefold()]
    grouped = defaultdict(list)
    for r in matching:
        grouped[r['assertion_id']].append(r)
    concepts = []
    for aid, group in grouped.items():
        group.sort(key=lambda r: (r['source_line'], r['native_record_id']))
        first = group[0]
        concepts.append({'assertion_id': aid, 'subject': first['subject'], 'subject_label': first['subject_label'],
            'go_id': first['go_id'], 'go_label': first['go_label'], 'relation_literal': first['relation_literal'],
            'local_review_state': first['local_review_state'], 'native_record_count': len(group),
            'records': group})
    concepts.sort(key=lambda r: (r['go_label'].casefold(), r['go_id'], r['relation_literal'], r['assertion_id']))
    page = concepts[offset:offset + limit]
    result = {'format': FORMAT, 'template': TEMPLATE, 'source_kind': 'goa', 'source_run': source_run,
        'question': 'Which native GO annotations describe ' + (nodes[protein].get('sym') or nodes[protein].get('name') or protein) + '?',
        'anchor': protein, 'view': view, 'read_only': True, 'model_calls': 0, 'source_fetches': 0,
        'graph_basis_sha256': graph_basis(graph), 'snapshot_sha256': graph['snapshot_sha256'],
        'evidence_extension_sha256': graph['evidence_extension_sha256'],
        'source_publication_sha256': summary['publication_sha256'],
        'source_observations_sha256': digest(source), 'review_events_sha256': digest(graph.get('review_events', [])),
        'source_summary': deepcopy(summary),
        'summary': {'source_observations': len(source), 'retained_source_observations': len(present),
            'pruned_source_observations': len(source) - len(present), 'anchored_source_records': len(anchored),
            'inspectable_records_in_view': len(eligible), 'matching_native_records': len(matching),
            'matching_concepts': len(concepts), 'returned_concepts': len(page),
            'offset': offset, 'limit': limit, 'next_offset': offset + limit if offset + limit < len(concepts) else None,
            'search': search, 'local_review_states': dict(sorted(Counter(r['local_review_state'] for r in anchored).items())),
            'counts_scope': 'Native source records and saved relation-qualified assertions; never independent experiment counts.'},
        'concepts': page, 'records': [r for c in page for r in c['records']],
        'interpretation': INTERPRETATION,
        'limitations': ['These current native annotations do not identify the historical Pharos source rows or restore their omitted qualifiers.',
            'Native relation literals remain distinct: acts_upstream_of is not converted to involved_in or enables.',
            'Candidate annotations appear only in the candidate view; source support never accepts an assertion automatically.',
            'References can alias the same study and may be reused by Pharos or another database.',
            'The source does not supply a disease condition here. Cohort membership does not establish disease applicability.',
            'A missing result is absence from this qualified addition/view, not biological absence or lack of evidence elsewhere.']}
    result['content_sha256'] = digest(result)
    return result
