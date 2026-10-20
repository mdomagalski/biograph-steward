"""Prospective planning packets: review scope before running a live comparison.

No model or source network calls occur during preparation. Draft references are
never used to repair model output or to alter the planner's input constraints.
"""
from collections import Counter
import csv
import hashlib
from html import escape
from io import StringIO
import json
from pathlib import Path
import re
import unicodedata

from .client import digest, utcnow, write_json
from .evaluation import (CASE_FIELDS, SOURCE_FILES, SUITE_FORMAT, _file_sha, _new_directory,
                         engine_fingerprint, evaluation_html, freeze_suite,
                         load_suite, run_evaluation, score_result, validate_cases)
from .graph import _write_tsv
from .planning import planning_request, selected_protocol, validate_planned_output
from .questions import verify_answer

PACKET_FORMAT = 'biograph-steward.planning-packet.v1'
PLANNER_FILES = ('planning.py', 'entity_resolution.py', 'planning_scope.py',
                 'codex_planner.py', 'model_transport.py', 'codex_transport.py')
RUBRIC = [
    'Choose one implemented query or abstain; do not replace an unsupported request with a nearby query.',
    'Use only exact catalogue identities. Unlisted aliases need clarification; a typo is not a new identity.',
    'Preserve the complete molecular profile, including AND/OR/NOT. Do not substitute a contained gene or variant.',
    'Distinguish a mentioned entity from a requested target, especially in negated or background clauses.',
    'Preserve the exact source disease, requested therapy set, evidence view and relations. Do not infer ontology equivalence.',
    'A query containing a drug preserves complete treatment sets; it does not establish monotherapy or a drug-specific effect.',
    'Check that every required filter and action is implemented. If not, require abstention or revise the question in a new packet.',
    'A valid accepted-only query may return no evidence. No evidence is different from an unsupported request.',
    'Approve scope independently of what the current parser/schema happens to allow. Uncertainty stays unapproved.',
    'Scope approval is not biological validation. Scientific support needs source review and a publication locator.'
]


def _question_key(question):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', question).casefold()))


def _prior_manifest(path):
    manifest = json.loads((Path(path) / 'suite.json').read_text(encoding='utf-8'))
    if (manifest.get('suite_format') != SUITE_FORMAT or
            manifest.get('suite_sha256') != digest({k: v for k, v in manifest.items() if k != 'suite_sha256'})):
        raise ValueError('Prior suite integrity check failed.')
    validate_cases(manifest['cases'])
    # This is an immutable historical control. Its engine need not be today's
    # full package fingerprint; its frozen planner files are compared below.
    return manifest


def audit_cases(cases, prior):
    cases = validate_cases(cases)
    if any(c['split'] != 'test' for c in cases):
        raise ValueError('Prospective comparison cases must all use the test split.')
    for field in ['id', 'group']:
        if any(not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', c[field]) for c in cases):
            raise ValueError('Packet IDs/groups must use bounded lowercase letters, digits, underscores or hyphens.')
    keys = [_question_key(c['question']) for c in cases]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate normalized question in the new packet.')
    audit = {'prior_suite_sha256': prior['suite_sha256'], 'cases': len(cases),
             'question_groups': len({c['group'] for c in cases}),
             'case_id_overlap': sorted({c['id'] for c in cases} & {c['id'] for c in prior['cases']}),
             'group_label_overlap': sorted({c['group'] for c in cases} & {c['group'] for c in prior['cases']}),
             'normalized_question_overlap': sorted(set(keys) & {_question_key(c['question']) for c in prior['cases']}),
             'semantic_independence_verified': False,
             'interpretation': 'Label/text checks detect simple reuse, not semantic independence. Same-source question families still need review.'}
    if any(audit[k] for k in ['case_id_overlap', 'group_label_overlap', 'normalized_question_overlap']):
        raise ValueError('New packet overlaps prior case IDs, group labels or normalized questions.')
    return audit


def _case_rows(cases):
    return [{'case_id': c['id'], 'case_sha256': digest(c), 'question': c['question'],
             'reference_plan': c['reference_plan'], 'reference_plan_correct': '',
             'reviewer': '', 'notes': ''} for c in cases]


def _sheet_text(value):
    value = json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else str(value)
    return "'" + value if value.startswith(('=', '+', '-', '@')) else value


def read_scope_reviews(cases, path=None):
    """Check immutable question/plan text as well as its claimed identity hash."""
    expected = {c['id']: row for c, row in zip(cases, _case_rows(cases))}
    counts = Counter()
    reviewers = set()
    seen = set()
    raw = None
    if path is not None:
        raw = Path(path).read_bytes()
        with StringIO(raw.decode('utf-8-sig'), newline='') as handle:
            reader = csv.DictReader(handle, delimiter='\t')
            if reader.fieldnames != CASE_FIELDS:
                raise ValueError('Scope-review worksheet columns changed.')
            for row in reader:
                identity = row.get('case_id')
                if (None in row or any(v is None for v in row.values()) or identity not in expected or identity in seen):
                    raise ValueError('Malformed, unknown or duplicate scope-review row.')
                for key in ['case_id', 'case_sha256', 'question', 'reference_plan']:
                    if row[key] != _sheet_text(expected[identity][key]):
                        raise ValueError('Scope-review question, reference plan or identity/hash changed.')
                seen.add(identity)
                verdict = row['reference_plan_correct']
                if verdict not in {'', 'yes', 'no', 'uncertain'}:
                    raise ValueError('Unsupported scope-review judgment.')
                if verdict and (not row['reviewer'].strip() or not row['notes'].strip()):
                    raise ValueError('Scope judgments require a reviewer and notes.')
                counts[verdict or 'pending'] += 1
                if verdict:
                    reviewers.add(row['reviewer'].strip())
    counts['pending'] += len(cases) - len(seen)
    return {'approved': counts['yes'], 'rejected': counts['no'], 'uncertain': counts['uncertain'],
            'pending': counts['pending'], 'reviewers': sorted(reviewers),
            'all_approved': counts['yes'] == len(cases),
            'worksheet_sha256': hashlib.sha256(raw).hexdigest() if raw is not None else None,
            'approval_meaning': 'Scope only; does not establish independent expertise or biological support.'}


def _tool_shape_allows(schema, value):
    """Check only the small JSON Schema subset emitted by tool_shapes_v3.

    This is a diagnostic of our own shapes, not a provider grammar validator.
    Unknown schema features fail the audit rather than being silently ignored.
    """
    allowed = {'anyOf', 'type', 'enum', 'properties', 'required', 'additionalProperties',
               'items', 'minItems', 'maxItems'}
    if set(schema) - allowed:
        raise ValueError('Output-shape audit encountered an unsupported schema feature.')
    if 'anyOf' in schema:
        return any(_tool_shape_allows(branch, value) for branch in schema['anyOf'])
    kind = schema.get('type')
    if kind == 'object':
        return (isinstance(value, dict) and schema.get('additionalProperties') is False
                and set(value) == set(schema['required']) == set(schema['properties'])
                and all(_tool_shape_allows(spec, value[key]) for key, spec in schema['properties'].items()))
    if kind == 'array':
        return (isinstance(value, list) and schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', len(value))
                and all(_tool_shape_allows(schema['items'], item) for item in value))
    if kind == 'string':
        return isinstance(value, str) and ('enum' not in schema or value in schema['enum'])
    if kind == 'null':
        return value is None
    raise ValueError('Output-shape audit encountered an unsupported schema type.')


def scope_audit(cases, graph, protocol):
    """Inspect application constraints, without generating or scoring model plans."""
    rows = []
    for case in cases:
        _, schema, _, audit, resolution = planning_request(case['question'], graph, protocol)
        scope = audit.get('request_scope')
        try:
            validate_planned_output(case['reference_plan'], graph, resolution, scope)
            compatible, error = True, None
        except (ValueError, TypeError) as exc:
            compatible, error = False, str(exc)
        shape_compatible = _tool_shape_allows(schema, case['reference_plan'])
        rows.append({'case_id': case['id'], 'reference_action': case['reference_plan']['action'],
                     'reference_passes_application_validation': compatible,
                     'reference_fits_output_schema': shape_compatible,
                     'reference_admissible': compatible and shape_compatible,
                     'reference_validation_error': error,
                     'application_forces_abstention': bool(scope and scope['unsupported_requirements']),
                     'request_scope': scope, 'entity_resolution': resolution,
                     'schema_sha256': digest(schema), 'instructions_sha256': audit['instructions_sha256']})
    return {'model_called': False, 'is_model_performance': False, 'cases': rows,
            'application_forced_abstentions': sum(r['application_forces_abstention'] for r in rows),
            'query_references_blocked_by_application': sum(r['reference_action'] == 'query' and not r['reference_admissible'] for r in rows),
            'abstention_references_not_forced': sum(r['reference_action'] == 'abstain' and not r['application_forces_abstention'] for r in rows),
            'interpretation': 'Constraint diagnostics against unapproved draft scope references. Not model accuracy; abstention is always permitted.'}


def _review_html(cases, inventory, overlap):
    esc = lambda value: escape(str(value), quote=True)
    sections = ''.join('<section><h2>' + esc(c['id']) + '</h2><p>Family: ' + esc(c['group']) +
                       '</p><p>' + esc(c['question']) + '</p><pre>' + esc(json.dumps(c['reference_plan'], indent=2)) +
                       '</pre></section>' for c in cases)
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Prospective planning scope review</title><style>body{max-width:1000px;margin:40px auto;padding:20px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f7;padding:14px}section{border-top:1px solid #ccd;padding:16px 0}</style>'
            '<h1>Prospective planning scope review</h1><p>AI-prepared drafts. No model inference has run. All judgments remain blank. '
            'Read the question and contract before inspecting scope_audit.json; parser behavior is not the reference standard.</p>'
            '<p>Edit a copy of case_reviews.tsv: yes / no / uncertain, reviewer and notes. Rejected scope requires a new packet. '
            'A live comparison requires every reference approved; software cannot attest reviewer independence or expertise.</p><ol>' +
            ''.join('<li>' + esc(item) + '</li>' for item in RUBRIC) + '</ol><details><summary>Source catalogue and tools</summary><pre>' +
            esc(json.dumps(inventory, indent=2)) + '</pre></details><details><summary>Reuse audit and limits</summary><pre>' +
            esc(json.dumps(overlap, indent=2)) + '</pre></details>' + sections + '</html>')


def prepare_comparison(baseline, enriched, output, *, cases, prior_suite, protocol='tool_shapes_v3'):
    from .planning import catalogue, tool_contracts
    output = Path(output).resolve()
    for source in [baseline, enriched, prior_suite]:
        source = Path(source).resolve()
        if output == source or source in output.parents or output in source.parents:
            raise ValueError('Save the packet outside source and historical control directories.')
    protocol = selected_protocol(protocol)
    if protocol != 'tool_shapes_v3':
        raise ValueError('This prospective packet freezes tool_shapes_v3; use a new protocol/version for subsequent tuning.')
    prior = _prior_manifest(prior_suite)
    overlap = audit_cases(cases, prior)
    current = engine_fingerprint()
    if any(current.get(name) != prior['engine_files'].get(name) for name in PLANNER_FILES):
        raise ValueError('Planner code differs from the prior control. Freeze the unchanged planner before authoring a prospective comparison.')
    for name, source in [('pharos', baseline), ('enriched', enriched)]:
        source = Path(source)
        files = {filename: _file_sha(source / filename) for filename in SOURCE_FILES if (source / filename).is_file()}
        if files != prior['sources'][name]['files']:
            raise ValueError('Source bytes/reviews differ from the prior control. No packet was created.')
    output = _new_directory(output)
    suite = freeze_suite(baseline, enriched, output / 'suite', cases=cases, **prior['budgets'])
    for name in ['pharos', 'enriched']:
        for key in ['files', 'graph_basis_sha256', 'pharos_snapshot_sha256', 'civic_snapshot_sha256', 'review_events_sha256']:
            if suite['sources'][name][key] != prior['sources'][name][key]:
                raise ValueError('Sources/reviews differ from the prior control; do not label this a fixed-source planning comparison.')
    _, graphs = load_suite(output / 'suite')
    inventory = {'catalogue': catalogue(graphs['enriched']), 'tool_contracts': tool_contracts(graphs['enriched'])}
    diagnostics = scope_audit(cases, graphs['enriched'], protocol)
    write_json(output / 'scope_audit.json', diagnostics)
    write_json(output / 'catalogue_and_tools.json', inventory)
    _write_tsv(output / 'case_reviews.tsv', _case_rows(cases), CASE_FIELDS)
    (output / 'review.html').write_text(_review_html(cases, inventory, overlap), encoding='utf-8')
    packet = {'packet_format': PACKET_FORMAT, 'created_at': utcnow(), 'suite_sha256': suite['suite_sha256'],
              'cases_sha256': digest(cases), 'planner_protocol': protocol,
              'planner_files': {name: current[name] for name in PLANNER_FILES},
              'planner_unchanged_from_prior': True, 'source_bytes_reviews_budgets_unchanged': True,
              'overlap_audit': overlap, 'rubric': RUBRIC, 'reference_status': 'AI_prepared_scope_drafts_review_pending',
              'independent_scope_review_verified': False, 'model_evaluation_run': False,
              'scientific_improvement_established': False,
              'artifacts': {name: _file_sha(output / name) for name in
                            ['suite/suite.json', 'scope_audit.json', 'catalogue_and_tools.json', 'case_reviews.tsv', 'review.html']}}
    packet['packet_sha256'] = digest(packet)
    write_json(output / 'packet.json', packet)
    return packet


def load_packet(path):
    path = Path(path)
    packet = json.loads((path / 'packet.json').read_text(encoding='utf-8'))
    if (packet.get('packet_format') != PACKET_FORMAT or
            packet.get('packet_sha256') != digest({k: v for k, v in packet.items() if k != 'packet_sha256'})):
        raise ValueError('Planning packet integrity check failed.')
    expected_artifacts = {'suite/suite.json', 'scope_audit.json', 'catalogue_and_tools.json', 'case_reviews.tsv', 'review.html'}
    if set(packet.get('artifacts', {})) != expected_artifacts:
        raise ValueError('Planning packet artifact inventory changed.')
    for name, sha in packet['artifacts'].items():
        if (path / name).is_symlink() or _file_sha(path / name) != sha:
            raise ValueError('Planning packet artifact changed; edit a copy of the review sheet.')
    suite, _ = load_suite(path / 'suite')
    if (suite['suite_sha256'] != packet['suite_sha256'] or digest(suite['cases']) != packet['cases_sha256'] or
            packet['planner_files'] != {name: suite['engine_files'][name] for name in PLANNER_FILES}):
        raise ValueError('Planning packet and suite bindings differ.')
    return packet, suite


def comparison_summary(result, packet, review):
    planners = [o for o in result['observations'] if o['arm'] == 'planner']
    enriched = {o['case_id']: o for o in result['observations'] if o['arm'] == 'enriched'}
    rows = []
    for obs in planners:
        baseline = enriched[obs['case_id']]
        comparable = obs['tool_calls'] == 1 and baseline['tool_calls'] == 1
        def content(answer):
            if answer is None:
                return None
            verify_answer(answer)
            return {k: v for k, v in answer.items() if k not in {'source_run', 'answer_sha256'}}
        equal = content(obs['answer']) == content(baseline['answer']) if comparable else None
        scope = (obs.get('trace') or {}).get('request_scope')
        rows.append({'case_id': obs['case_id'], 'group': obs['group'], 'status': obs['status'],
                     'draft_plan_match': obs['draft_plan_agreement'], 'tool_calls': obs['tool_calls'],
                     'application_forced_abstention': bool(scope and scope['unsupported_requirements']),
                     'output_comparable_to_enriched': comparable, 'output_equal_to_enriched': equal})
    matches = [r['draft_plan_match'] for r in rows if r['draft_plan_match'] is not None]
    by_group = {}
    for group in sorted({r['group'] for r in rows}):
        group_rows = [r for r in rows if r['group'] == group]
        values = [r['draft_plan_match'] for r in group_rows if r['draft_plan_match'] is not None]
        by_group[group] = {'cases': len(group_rows), 'compared': len(values), 'matches': sum(values),
                           'all_scope_plans_matched': all(values) if len(values) == len(group_rows) else None}
    summary = {'format': 'biograph-steward.prospective-comparison.v1', 'created_at': utcnow(),
               'packet_sha256': packet['packet_sha256'], 'suite_sha256': result['suite_sha256'],
               'evaluation_sha256': result['evaluation_sha256'], 'planner_kind': result['planner_kind'],
               'cases': len(rows), 'groups': by_group, 'scope_review': review,
               'draft_plan_comparisons': len(matches), 'draft_plan_matches': sum(matches),
               'draft_plan_agreement': sum(matches) / len(matches) if matches else None,
               'statuses': dict(Counter(r['status'] for r in rows)),
               'reported_model_calls': sum((o.get('trace') or {}).get('model_calls', 0) for o in planners),
               'query_output_pairs': sum(r['output_comparable_to_enriched'] for r in rows),
               'query_outputs_equal_to_enriched': sum(r['output_equal_to_enriched'] is True for r in rows),
               'output_comparison_excludes': ['source_run arm label', 'answer_sha256 derived from the arm-labelled payload'],
               'scientific_improvement_established': False, 'citation_support_accuracy': None,
               'interpretation': 'Hybrid planning on same-source prospective cases; scope approval does not establish biological accuracy or reviewer independence.',
               'case_results': rows}
    summary['comparison_sha256'] = digest(summary)
    return summary


def run_comparison(packet_dir, output, *, live=False, scope_reviews=None, planner=None, progress=None):
    packet_dir, output = Path(packet_dir).resolve(), Path(output).resolve()
    if output == packet_dir or packet_dir in output.parents or output in packet_dir.parents:
        raise ValueError('Save comparison results outside the immutable planning packet.')
    packet, suite = load_packet(packet_dir)
    review = read_scope_reviews(suite['cases'], scope_reviews)
    if (live or planner is not None) and not review['all_approved']:
        raise ValueError('Approve every scope reference in a separate worksheet before model inference. No model was called.')
    if live and planner is not None:
        raise ValueError('Select configured live inference or an injected test planner, not both.')
    if live:
        from .planning import configured_planner
        planner = configured_planner()
    if planner is not None and getattr(planner, 'protocol', None) != packet['planner_protocol']:
        raise ValueError('Configured planner protocol differs from the frozen packet. No model was called.')
    # Snapshot reviewed bytes before inference; those exact bytes are saved/scored later.
    if scope_reviews is not None:
        submitted = Path(scope_reviews).read_bytes()
        if hashlib.sha256(submitted).hexdigest() != review['worksheet_sha256']:
            raise ValueError('Scope-review worksheet changed during validation.')
    result, metrics = run_evaluation(packet_dir / 'suite', output, planner=planner,
                                    planner_note='Offline preparation only; no live or replay model was called.', progress=progress)
    if scope_reviews is not None:
        (output / 'scope_reviews_submitted.tsv').write_bytes(submitted)
        metrics = score_result(result, case_reviews=output / 'scope_reviews_submitted.tsv')
        write_json(output / 'metrics.json', metrics)
        (output / 'report.html').write_text(evaluation_html(result, metrics), encoding='utf-8')
    summary = comparison_summary(result, packet, review)
    write_json(output / 'comparison.json', summary)
    return summary
