"""Read-only, conservative comparison of ordinary saved workbench runs.

Hashes bind local artifacts, not an authenticated upstream release or scientific
truth. Existing review replay rules remain unchanged. Carryover creates new,
explicitly attributed events and never silently reuses an old snapshot binding.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

from .assertions import new_review_event
from .client import digest, utcnow
from .graph import build_graph

POLICY = 'biograph-steward.refresh-comparison.v1'
DEFAULT_REVIEWER = 'BioGraph Steward review carryover'
DEFAULT_REASON = 'Carry forward prior decisions under the recorded compatibility policy.'
PARENT_FILES = ('snapshot.json', 'review_events.json', 'graph.json',
                'run_manifest.json', 'civic_snapshot.json')
_TRANSPORT_EDGE_FIELDS = {'snapshot_sha256', 'record_locators', 'retrieval_provenance',
                          'context_record_ids', 'assertion_id'}
_IDENTITY_FIELDS = ('subject', 'predicate', 'object', 'kind', 'qualifiers')
_ASSERTION_FIELDS = ('revision', 'evidence_edge_ids', 'structurally_usable_evidence_ids',
                     'validation_status', 'review_reasons', 'publications', 'source_names',
                     'normalization_notes', 'source_record_count', 'symmetric', 'data_kind')
_FAMILIES = {'pathway_membership': 'pathways', 'go_annotation': 'go',
             'protein_interaction': 'ppis', 'drug_listing': 'drugs',
             'expression_observation': 'expressions'}


def _read(path):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Duplicate JSON key.')
            result[key] = value
        return result

    def constant(value):
        raise ValueError('Nonfinite JSON number: ' + value)

    try:
        return json.loads(path.read_text(encoding='utf-8'),
                          object_pairs_hook=pairs, parse_constant=constant)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError('Cannot read refresh input: ' + path.name) from exc


def _edge_content(edge):
    # Includes duplicate/source cardinality, raw values and structural status.
    # Ordering and retrieval locations/times are deliberately not evidence drift.
    return {k: deepcopy(v) for k, v in edge.items() if k not in _TRANSPORT_EDGE_FIELDS}


def _index(graph):
    return ({e['id']: e for e in graph['edges']}, {n['id']: n for n in graph['nodes']})


def _assertion_content(assertion, graph, index=None):
    edges, nodes = index if index is not None else _index(graph)
    content = {k: deepcopy(assertion.get(k)) for k in _IDENTITY_FIELDS + _ASSERTION_FIELDS}
    content['evidence'] = sorted((_edge_content(edges[eid])
        for eid in assertion['evidence_edge_ids']), key=lambda e: e['id'])
    content['endpoint_nodes'] = [deepcopy(nodes[uid])
        for uid in sorted({assertion['subject'], assertion['object']})]
    return content


def _graph_semantics(graph):
    index = _index(graph)
    return {'graph_format': graph['graph_format'],
            'normalization_policy': graph.get('normalization', {}).get('policy'),
            'nodes': sorted(graph['nodes'], key=lambda n: n['id']),
            'assertions': [{'id': a['id'], 'content': _assertion_content(a, graph, index),
                'lifecycle_state': a['lifecycle_state'],
                'review_history': a['review_history']}
                for a in sorted(graph['assertions'], key=lambda a: a['id'])]}


def _metadata_shapes(snapshot):
    """Reject malformed containers before scope inspection can dereference them.

    Missing coverage remains unknown, never inferred complete. This guard does
    not upgrade incomplete metadata or repair source records.
    """
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get('query_settings'), dict)
            or not isinstance(snapshot.get('retrieval'), dict)
            or not isinstance(snapshot.get('targets'), list)
            or any(not isinstance(t, dict) for t in snapshot['targets'])
            or not isinstance(snapshot.get('warnings', []), list)
            or any(not isinstance(w, str) for w in snapshot.get('warnings', []))):
        raise ValueError('Refresh snapshot settings, retrieval, targets or warnings metadata is malformed.')
    settings = snapshot['query_settings']
    if 'context_limits' in settings and not isinstance(settings['context_limits'], dict):
        raise ValueError('Refresh context limit settings must be an object.')
    if 'tissue_term' in settings and not isinstance(settings['tissue_term'], str):
        raise ValueError('Refresh tissue settings must be text.')
    for target in snapshot['targets']:
        if target.get('uniprot') is not None and not isinstance(target['uniprot'], str):
            raise ValueError('Refresh target accession metadata must be text or null.')
        if 'pathways' in target and not isinstance(target['pathways'], list):
            raise ValueError('Refresh target pathways must be a list.')
        if 'pharos_context' in target and not isinstance(target['pharos_context'], dict):
            raise ValueError('Refresh target context metadata must be an object.')
        target_context = target.get('pharos_context', {})
        if any(family in target_context and not isinstance(target_context[family], list)
               for family in ('go', 'ppis', 'drugs', 'expressions', 'publications')):
            raise ValueError('Refresh target context families must be lists.')
        metadata = target_context.get('metadata', {})
        if not isinstance(metadata, dict):
            raise ValueError('Refresh target source metadata must be an object.')
    retrieval = snapshot['retrieval']
    if 'pages' in retrieval and (not isinstance(retrieval['pages'], list)
            or any(not isinstance(p, dict) for p in retrieval['pages'])):
        raise ValueError('Refresh target pagination metadata is malformed.')
    if 'context' not in retrieval:
        return
    context = retrieval['context']
    if (not isinstance(context, dict) or not isinstance(context.get('scope', {}), dict)
            or not isinstance(context.get('limits_per_target', {}), dict)
            or not isinstance(context.get('targets', []), list)
            or not isinstance(context.get('summary', {}), dict)
            or not isinstance(context.get('not_requested', {}), dict)):
        raise ValueError('Refresh context coverage, scope or limit metadata is malformed.')
    scope = context.get('scope', {})
    if ('seed_uniprots' in scope and (not isinstance(scope['seed_uniprots'], list)
            or any(not isinstance(uid, str) for uid in scope['seed_uniprots']))):
        raise ValueError('Refresh context seed identifiers must be a list of strings.')
    if 'tissue_search' in scope and scope['tissue_search'] is not None and not isinstance(scope['tissue_search'], str):
        raise ValueError('Refresh context tissue scope must be text or null.')
    for row in context.get('targets', []):
        if (not isinstance(row, dict) or not isinstance(row.get('issues', []), list)
                or not isinstance(row.get('pages', []), list)
                or not isinstance(row.get('family'), str) or not isinstance(row.get('uniprot'), str)
                or any(not isinstance(p, dict) for p in row.get('pages', []))
                or any(not isinstance(issue, str) for issue in row.get('issues', []))):
            raise ValueError('Refresh per-target family coverage metadata is malformed.')


def _load(directory):
    directory = Path(directory)
    try:
        files = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                 for name in PARENT_FILES if (directory / name).is_file()}
    except OSError as exc:
        raise ValueError('Cannot hash refresh parent input.') from exc
    if 'snapshot.json' not in files:
        raise ValueError('Refresh comparison requires an ordinary saved snapshot.json.')
    snapshot = _read(directory / 'snapshot.json')
    _metadata_shapes(snapshot)
    events = _read(directory / 'review_events.json') if 'review_events.json' in files else []
    if isinstance(events, list) and any(isinstance(event, dict) and 'migration' in event for event in events):
        raise ValueError('One-hop refresh comparison cannot reuse inherited migration histories; recursive provenance verification is deferred.')
    civic = _read(directory / 'civic_snapshot.json') if 'civic_snapshot.json' in files else None
    try:
        graph = build_graph(snapshot, events, civic)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError('Refresh parent has an invalid ordinary workbench structure.') from exc
    manifest = _read(directory / 'run_manifest.json') if 'run_manifest.json' in files else None
    saved = _read(directory / 'graph.json') if 'graph.json' in files else None
    if (isinstance(saved, dict) and isinstance(saved.get('review_events'), list)
            and any(isinstance(event, dict) and 'migration' in event for event in saved['review_events'])):
        raise ValueError('One-hop refresh comparison cannot reuse a graph with inherited migration histories.')
    if 'review_events.json' not in files and isinstance(saved, dict) and saved.get('review_events'):
        raise ValueError('Reviewed parent is missing its review_events.json history.')
    reasons = []
    if not isinstance(manifest, dict):
        reasons.append('saved_manifest_missing')
        manifest = {}
    for key, actual in [('snapshot_sha256', snapshot['content_sha256']),
                        ('graph_format', graph['graph_format']),
                        ('normalization_policy', graph['normalization']['policy'])]:
        if manifest.get(key) != actual:
            reasons.append('saved_manifest_' + key + '_mismatch')
    if not isinstance(manifest.get('starter_version'), str) or not manifest['starter_version']:
        reasons.append('saved_manifest_starter_version_unknown')
    try:
        if not isinstance(saved, dict) or _graph_semantics(saved) != _graph_semantics(graph):
            reasons.append('saved_graph_replay_semantics_mismatch')
    except (KeyError, TypeError, IndexError, AttributeError):
        reasons.append('saved_graph_replay_semantics_mismatch')
    coverage = snapshot.get('retrieval', {}).get('context', {})
    family_rows = {}
    if isinstance(coverage, dict):
        for row in coverage.get('targets', []):
            family_rows.setdefault((row.get('family'), row.get('uniprot')), []).append(row)
    targets_by_id = {}
    for row in snapshot['targets']:
        if isinstance(row, dict):
            targets_by_id.setdefault(row.get('uniprot'), []).append(row)
    return {'snapshot': snapshot, 'events': events, 'civic': civic, 'graph': graph, 'index': _index(graph),
            'family_rows': family_rows, 'targets_by_id': targets_by_id,
            'manifest': manifest, 'policy_reasons': reasons,
            'binding': {'snapshot_sha256': snapshot['content_sha256'],
                'civic_snapshot_sha256': civic['content_sha256'] if civic else None,
                'files': files, 'graph_semantics_sha256': digest(_graph_semantics(graph))}}


def _scope(snapshot):
    if (snapshot.get('scope') or {}).get('kind') == 'protein_cohort':
        raise ValueError('Cohort refresh comparison is not implemented. Publish a separate construction and preserve both runs.')
    context = snapshot.get('retrieval', {}).get('context')
    return {'data_kind': snapshot['data_kind'], 'endpoint': snapshot.get('endpoint'),
        'disease': {'id': snapshot['disease'].get('mondoID'),
                    'name': snapshot['disease'].get('name')},
        'query_settings': snapshot.get('query_settings'),
        'targets': sorted({t.get('uniprot') for t in snapshot['targets']
                           if isinstance(t, dict) and isinstance(t.get('uniprot'), str)}),
        'context': ({'profile': context.get('profile'),
            'limits_per_target': context.get('limits_per_target'),
            'row_budget': context.get('row_budget'),
            'scope': {k: sorted(v) if k == 'seed_uniprots' and isinstance(v, list) else v
                      for k, v in context.get('scope', {}).items()},
            'not_requested': context.get('not_requested')}
            if isinstance(context, dict) else None)}


def _target_complete(run):
    s = run['snapshot']; r = s.get('retrieval', {})
    count = r.get('total_targets_reported')
    if (r.get('truncated') is not False or type(count) is not int or count < 0
            or r.get('records_retrieved') != len(s['targets']) or count != len(s['targets'])):
        return False
    # Target-count changes and malformed/duplicate seed rows undermine absence.
    if any('Target count changed' in str(w) for w in s.get('warnings', [])):
        return False
    return len({t['id'] for t in run['graph']['targets']}) == len(s['targets'])


def _family_complete(run, family, uid):
    context = run['snapshot'].get('retrieval', {}).get('context')
    if not isinstance(context, dict):
        return False
    rows = run['family_rows'].get((family, uid), [])
    if len(rows) != 1:
        return False
    r = rows[0]
    targets = run['targets_by_id'].get(uid, [])
    if len(targets) != 1:
        return False
    retained = targets[0].get('pathways', []) if family == 'pathways' else targets[0].get('pharos_context', {}).get(family, [])
    return (r.get('status') == 'complete' and not r.get('issues')
        and type(r.get('available')) is int and r['available'] >= 0
        and type(r.get('retrieved')) is int and r['retrieved'] == r['available']
        and type(r.get('retained')) is int and r['retained'] == len(retained)
        and type(r.get('excluded_by_scope')) is int
        and r['excluded_by_scope'] >= 0
        and r['excluded_by_scope'] + r['retained'] == r['retrieved']
        and type(r.get('limit')) is int and r['limit'] > 0
        and r['limit'] == context.get('limits_per_target', {}).get(family))


def _civic_reasons(before, after):
    a, b = before['civic'], after['civic']
    if a is None or b is None:
        return ['civic_source_missing_on_one_side']
    reasons = []
    if a['content_sha256'] != b['content_sha256']:
        reasons.append('civic_exact_sidecar_changed_or_release_unknown')
    for run in (before, after):
        civic = run['civic']
        if (run['manifest'].get('civic', {}).get('snapshot_sha256') != civic['content_sha256']
                or not civic.get('coverage') or any(r.get('status') != 'complete'
                    or r.get('issues') or r.get('has_next_page') is not False
                    or type(r.get('reported')) is not int or r.get('reported') != r.get('retrieved')
                    for r in civic['coverage'])):
            reasons.append('civic_coverage_or_manifest_unverified')
    return sorted(set(reasons))


def _dependency_reasons(assertion, before, after):
    kind = assertion['kind']
    if kind == 'variant_therapy_response':
        return _civic_reasons(before, after)
    if kind in {'disease_association', 'disease_filtered_membership'}:
        return [] if all(_target_complete(r) for r in (before, after)) else ['target_retrieval_incomplete_or_unverified']
    family = _FAMILIES.get(kind)
    if family is None:
        return ['assertion_family_comparability_unsupported']
    ids = {assertion['subject']}
    if family == 'ppis':
        ids.add(assertion['object'])
    reasons = []
    for side, run in [('before', before), ('after', after)]:
        for pid in sorted(ids):
            if not pid.startswith('UniProtKB:'):
                reasons.append(side + '_family_identity_or_completeness_unverified')
            elif not _family_complete(run, family, pid.removeprefix('UniProtKB:')):
                reasons.append(side + '_' + family + '_incomplete_or_unverified')
    return sorted(set(reasons))


def _side(assertion, run):
    if assertion is None:
        return None
    edges, _ = run['index']
    return {'revision': assertion['revision'],
        'evidence_sha256': digest(_assertion_content(assertion, run['graph'], run['index'])),
        'evidence_edge_ids': assertion['evidence_edge_ids'],
        'source_record_count': assertion['source_record_count'],
        'lifecycle_state': assertion['lifecycle_state'],
        'review_event_count': len(assertion['review_history']),
        'source_records': [{'edge_id': eid,
            'record_sha256': digest(edges[eid]['evidence_record']),
            'record_locators': edges[eid]['record_locators'],
            'context_record_ids': edges[eid].get('context_record_ids', [])}
            for eid in assertion['evidence_edge_ids']]}


def compare_runs(before, after):
    """Compare verified parents without network calls or filesystem mutation.

    ``observed_change`` is an exact qualified-identity/content observation.
    ``status`` becomes ``not_comparable`` when absence/content is scope-confounded.
    ``removed`` means absent from a comparable pull, never a scientific retraction.
    """
    before, after = _load(before), _load(after)
    policy_reasons = ['before_' + r for r in before['policy_reasons']]
    policy_reasons += ['after_' + r for r in after['policy_reasons']]
    keys = ('starter_version', 'graph_format', 'normalization_policy')
    if any(before['manifest'].get(k) != after['manifest'].get(k) for k in keys):
        policy_reasons.append('saved_transformation_policy_changed')
    a_scope, b_scope = _scope(before['snapshot']), _scope(after['snapshot'])
    scope_reasons = [key + '_scope_changed' for key in a_scope if a_scope[key] != b_scope[key]]
    versions = [r['snapshot'].get('db_version') for r in (before, after)]
    release_reasons = []
    synthetic = all(r['snapshot']['data_kind'] == 'synthetic_demo' for r in (before, after))
    if synthetic:
        # Explicit invented fixtures have no upstream release to attest. This
        # exception must never permit a live/synthetic or live/unknown migration.
        if versions[0] != versions[1]:
            release_reasons.append('synthetic_fixture_version_changed')
    elif any(not isinstance(v, str) or not v.strip() for v in versions):
        release_reasons.append('pharos_source_release_unknown')
    elif versions[0] != versions[1]:
        release_reasons.append('pharos_source_release_changed')
    global_reasons = sorted(set(policy_reasons + scope_reasons))
    lookup = [{a['id']: a for a in r['graph']['assertions']} for r in (before, after)]
    rows = []
    for aid in sorted(set(lookup[0]) | set(lookup[1])):
        a, b = lookup[0].get(aid), lookup[1].get(aid)
        old, new = _side(a, before), _side(b, after)
        observed = ('added' if a is None else 'removed' if b is None else
                    'unchanged' if old['evidence_sha256'] == new['evidence_sha256'] else 'changed')
        reasons = sorted(set(global_reasons + _dependency_reasons(a or b, before, after)))
        blockers = list(reasons) + release_reasons
        if observed != 'unchanged':
            blockers.append('assertion_or_evidence_not_exactly_unchanged')
        if not a or not a['review_history']:
            blockers.append('no_prior_review_history')
        if b and b['review_history']:
            blockers.append('target_already_has_review_history')
        if a and b and a['revision'] != b['revision']:
            blockers.append('evidence_revision_changed')
        rows.append({'assertion_id': aid, 'kind': (a or b)['kind'],
            'observed_change': observed, 'status': 'not_comparable' if reasons else observed,
            'reasons': reasons, 'review_eligible': not blockers,
            'review_blockers': sorted(set(blockers)), 'before': old, 'after': new})
    statuses = Counter(r['status'] for r in rows); observed = Counter(r['observed_change'] for r in rows)
    result = {'format': POLICY, 'compatibility_policy': POLICY,
        'parents': {'before': before['binding'], 'after': after['binding']},
        'compatibility': {'policy_compatible': not policy_reasons,
            'scope_compatible': not scope_reasons,
            'source_release_compatible': not release_reasons,
            'reasons': sorted(set(global_reasons + release_reasons)),
            'before_scope': a_scope, 'after_scope': b_scope,
            'before_source_release': versions[0], 'after_source_release': versions[1],
            'source_release_basis': 'synthetic_fixture_only' if synthetic else 'reported_pharos_database_version',
            'historical_code_identity_attested': False},
        'target_changes': {'added': sorted(set(b_scope['targets']) - set(a_scope['targets'])),
            'not_observed': sorted(set(a_scope['targets']) - set(b_scope['targets']))},
        'assertions': rows,
        'summary': {'assertions': len(rows),
            'status_counts': {k: statuses[k] for k in ('unchanged', 'changed', 'added', 'removed', 'not_comparable')},
            'observed_change_counts': {k: observed[k] for k in ('unchanged', 'changed', 'added', 'removed')},
            'eligible_review_assertions': sum(r['review_eligible'] for r in rows),
            'reviewed_before_assertions': sum(bool(r['before'] and r['before']['review_event_count']) for r in rows)},
        'limitations': [
            'Exact qualified-identity deltas are not biological truth, retractions or independent-study counts.',
            'Expression value/context changes can create added and removed assertion IDs rather than a same-ID changed row.',
            'Local source IDs are not assumed durable across releases; no name-based source-record correspondence is inferred.',
            'Review compatibility uses matching saved policy metadata and replayed output semantics, not historical code attestation.',
            'Unknown or changed live source releases block review carryover; explicit synthetic fixtures attest no upstream biology.',
            'CIViC carryover requires the exact same complete sidecar; a newly retrieved unversioned sidecar requires review.',
            'Independent-study lineage and biological prediction improvement remain unresolved.']}
    result['comparison_sha256'] = digest(result)
    return result


def verify_comparison(comparison, before, after):
    """Reject edited receipts, changed parents or self-declared eligibility."""
    if (not isinstance(comparison, dict) or comparison.get('format') != POLICY
            or comparison.get('comparison_sha256') != digest({k: v for k, v in comparison.items()
                                                            if k != 'comparison_sha256'})):
        raise ValueError('Refresh comparison integrity check failed.')
    if comparison != compare_runs(before, after):
        raise ValueError('Refresh comparison no longer matches its parents or compatibility policy.')


def migrate_reviews(before, after, comparison, *, reviewer=DEFAULT_REVIEWER,
                    reason=DEFAULT_REASON, created_at=None):
    """Return target events plus separately attributed compatible prior chains.

    No files are written. Ineligible histories (including reviewed targets) are
    skipped and remain explained in the comparison. Repeating this function with
    the same parents, comparison, actor, reason and timestamp is deterministic.
    A workflow must retain these inputs and verify the complete generated events;
    ordinary legacy graph loading does not authenticate migration ancestry.
    """
    verify_comparison(comparison, before, after)
    source, target = _load(before), _load(after)
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 200:
        raise ValueError('A migration actor name of 1–200 characters is required.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ValueError('A migration reason of 1–4000 characters is required.')
    stamp = created_at if created_at is not None else utcnow()
    try:
        if not isinstance(stamp, str) or datetime.fromisoformat(stamp).utcoffset() is None:
            raise ValueError('Timezone is required.')
    except (TypeError, ValueError) as exc:
        raise ValueError('Migration timestamp must include a timezone.') from exc
    eligible = {r['assertion_id'] for r in comparison['assertions'] if r['review_eligible']}
    events = deepcopy(target['events']); graph = target['graph']
    for original in source['events']:
        if original['assertion_id'] not in eligible:
            continue
        event = new_review_event(graph, original['assertion_id'], original['to_state'], reviewer, reason)
        event['created_at'] = stamp
        event['migration'] = {'policy': POLICY, 'kind': 'inherited_review_decision',
            'fresh_human_adjudication': False,
            'comparison_sha256': comparison['comparison_sha256'],
            'source_parent': deepcopy(comparison['parents']['before']),
            'target_parent': deepcopy(comparison['parents']['after']),
            'original_event': deepcopy(original), 'original_event_sha256': digest(original)}
        events.append(event)
        graph = build_graph(target['snapshot'], events, target['civic'])
    return events
