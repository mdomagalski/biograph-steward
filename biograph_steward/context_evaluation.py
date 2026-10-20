"""Frozen paired comparison of legacy passage selection and context verification.

References are source-grounded AI-authored development judgments, not expert gold.
Fresh means excluded from supplied prior CRC literature inventories, not model
training or all prior project use. No graph or human-review mutation authority.
"""
from collections import Counter
from html import escape
import json
from pathlib import Path
import re
import shutil

from .client import digest, utcnow, write_json
from .context_verification import (AXES, INSTRUCTIONS, POLICY as VERIFIER_POLICY,
    schema, validate, verify_context, eligibility, literal_checks)
from .crc_pilot import assess_task, new_output, sha
from .evidence_quality import (TaskBoundVerifier, SELECTION_INSTRUCTIONS, selection_schema,
    bind_selection, engine)
from .literature import load_literature, source_document
from .verification import configured_verifier, binding, validate_task, validate_verdict

POLICY = 'context-comparison.v1'
ARMS = ('original', 'literal_checks', 'legacy_v2', 'context_raw', 'context_checked')
NOTICE = ('Fresh CRC development comparison with AI-authored, source-grounded references; '
          'no independent human scientific or rationale labels. Public papers may be in model training. '
          'Cases share three publications; case counts are not independent studies. '
          'Literal/spanning checks are eligibility safeguards, not entailment or biological truth. '
          'No automatic graph acceptance, pruning or quarantine.')
INPUT_FILES = {'inputs.json', 'references.json', 'selection.json', 'contract.json', 'previous_sources.json'}


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def signed(value, key):
    if value.get(key) != digest({k: v for k, v in value.items() if k != key}):
        raise ValueError('Context artifact digest changed: ' + key)


def inventory(folder, files):
    for name, fingerprint in files.items():
        p = Path(name)
        if p.is_absolute() or '..' in p.parts or any((folder / Path(*p.parts[:i])).is_symlink() for i in range(1, len(p.parts) + 1)):
            raise ValueError('Invalid context artifact path.')
        if sha(folder / name) != fingerprint:
            raise ValueError('Context artifact bytes changed.')


def prepare_context(literature, previous, output, *, specs=None):
    lm, papers = load_literature(literature)
    if not previous:
        raise ValueError('Supply prior CRC literature inventories for explicit source exclusion.')
    excluded = []; old = set()
    for path in previous:
        manifest, prior = load_literature(path); old.update(prior)
        excluded.append({'manifest_sha256': manifest['manifest_sha256'], 'pmids': sorted(prior)})
    if set(papers) & old:
        raise ValueError('Fresh publication overlaps supplied prior CRC sources.')
    specs = specs if specs is not None else read(Path(__file__).with_name('context_cases.json'))
    if not isinstance(specs, list) or not 2 <= len(specs) <= 60:
        raise ValueError('Use 2–60 predeclared context cases.')
    tasks = []; references = []; selections = []; ids = set()
    for spec in specs:
        if (not re.fullmatch(r'[a-z0-9-]{1,60}', spec['id']) or spec['id'] in ids
                or spec['pmid'] not in papers or spec['expected'] not in ('SUPPORT', 'CONTRADICT', 'NOT_ENOUGH_INFORMATION')
                or spec['axis'] not in (None, *AXES)):
            raise ValueError('Invalid context reference specification.')
        ids.add(spec['id'])
        doc, selection = source_document(papers[spec['pmid']], spec['claim'], 'abstract')
        task = {'id': 'task-' + digest(spec['id'])[:24], 'claim_id': len(tasks) + 1,
                'document_id': int(spec['pmid']), 'claim': spec['claim'], 'document': doc}
        validate_task(task)
        if spec['kind'] == 'paraphrase' and any(spec['claim'] in s['text'] for s in doc['sentences']):
            raise ValueError('Fresh positives must be paraphrases, not exact-excerpt controls.')
        for rationale in spec['rationale_sets']:
            if (not rationale or len(set(rationale)) != len(rationale)
                    or any(type(i) is not int or not 0 <= i < len(doc['sentences']) for i in rationale)):
                raise ValueError('Invalid reference passage set.')
        if not spec['rationale_sets']:
            raise ValueError('Reference requires source-grounded rationale passages.')
        tasks.append(task); selections.append({'id': task['id'], 'selection': selection})
        references.append({**spec, 'id': task['id'], 'reference_id': spec['id'], 'independent_human_review': False})
    if set(papers) != {str(t['document_id']) for t in tasks}:
        raise ValueError('Every fetched source must be represented in the fixed panel.')
    out = new_output(output, literature, *previous)
    shutil.copytree(literature, out / 'literature')
    contract = {'policy': POLICY, 'engine': engine(), 'created_at': utcnow(),
        'arms': list(ARMS), 'legacy_instructions': SELECTION_INSTRUCTIONS,
        'context_instructions': INSTRUCTIONS, 'context_policy': VERIFIER_POLICY,
        'context_schema_sha256': {t['id']: digest(schema(t)) for t in tasks},
        'legacy_schema_sha256': {t['id']: digest(selection_schema(t)) for t in tasks},
        'model_input_fields': ['id', 'claim_id', 'document_id', 'claim', 'document'],
        'calls': 'One legacy and one context turn per case; sequential, alternating arm order; no retries, repairs, tools or fallback.',
        'selection': 'Three predeclared trial publications outside supplied prior CRC literature inventories. Nine paraphrased controls and nine context edits; source and claim construction inspected before freeze.',
        'scoring': 'Identical task inventory. Invalid output remains in denominators. Source passage coverage is not reasoning correctness. Expected context-axis agreement uses AI references; expert reasoning correctness remains unscored.',
        'promotion': 'No scientific promotion, automatic lifecycle writes or parameter tuning from this run.',
        'human_scientific_labels': 0, 'graph_mutations': False, 'limitation': NOTICE}
    for name, value in [('inputs.json', tasks), ('references.json', references), ('selection.json', selections),
                         ('contract.json', contract), ('previous_sources.json', excluded)]:
        write_json(out / name, value)
    p = {'format': POLICY + '.packet', 'created_at': utcnow(), 'cases': len(tasks),
         'publications': len(papers), 'literature_manifest_sha256': lm['manifest_sha256'],
         'files': {str(f.relative_to(out)): sha(f) for f in sorted(out.rglob('*')) if f.is_file()}}
    p['packet_sha256'] = digest(p); write_json(out / 'packet.json', p)
    return p


def load_packet(folder, *, check_engine=True):
    folder = Path(folder); p = read(folder / 'packet.json'); signed(p, 'packet_sha256')
    if p['format'] != POLICY + '.packet' or set(p['files']) - INPUT_FILES - {n for n in p['files'] if n.startswith('literature/')}:
        raise ValueError('Unknown context packet or inventory.')
    if not INPUT_FILES <= set(p['files']):
        raise ValueError('Incomplete context packet.')
    inventory(folder, p['files'])
    lm, papers = load_literature(folder / 'literature')
    if lm['manifest_sha256'] != p['literature_manifest_sha256']:
        raise ValueError('Context literature binding changed.')
    contract = read(folder / 'contract.json')
    if check_engine and contract['engine'] != engine():
        raise ValueError('Context engine changed after freeze; prepare a new packet before inference.')
    previous = read(folder / 'previous_sources.json')
    if set(papers) & {pmid for row in previous for pmid in row['pmids']}:
        raise ValueError('Context publication overlaps recorded prior sources.')
    tasks = read(folder / 'inputs.json'); selections = read(folder / 'selection.json')
    if len(tasks) != p['cases'] or len({t['id'] for t in tasks}) != len(tasks) or len(selections) != len(tasks):
        raise ValueError('Context case inventory changed.')
    for task, row in zip(tasks, selections):
        validate_task(task)
        doc, selection = source_document(papers[str(task['document_id'])], '', 'abstract')
        if row != {'id': task['id'], 'selection': selection} or task['document'] != doc:
            raise ValueError('Context supplied source binding changed.')
        if (contract['context_schema_sha256'][task['id']] != digest(schema(task)) or
                contract['legacy_schema_sha256'][task['id']] != digest(selection_schema(task))):
            raise ValueError('Context schema differs from frozen protocol.')
    return p, tasks, contract


def actions(task, legacy, context):
    checked = context.get('gate') or eligibility(task, None)
    return {'original': True,
            'literal_checks': not any(not r['source_hits'] for r in literal_checks(task)),
            'legacy_v2': legacy['status'] == 'validated' and legacy['verdict']['verdict'] == 'SUPPORT',
            'context_raw': context['status'] == 'validated' and context['assessment']['verdict'] == 'SUPPORT',
            'context_checked': context['status'] == 'validated' and checked['support_eligible']}


def metrics(tasks, refs, traces, observations, execution):
    if len(refs) != len(tasks) or {r['id'] for r in refs} != {t['id'] for t in tasks}:
        raise ValueError('Context references do not match the fixed inputs.')
    reference = {r['id']: r for r in refs}; positive = sum(r['expected'] == 'SUPPORT' for r in refs)
    result = {'format': POLICY + '.result', 'packet_sha256': execution['packet_sha256'],
        'cases': len(tasks), 'publications': len({t['document_id'] for t in tasks}),
        'model_requests': sum(t.get('model_calls', 0) for pair in traces.values() for t in pair.values()),
        'mode': execution['mode'], 'model_requested': execution['model_requested'], 'arms': {},
        'outputs': {}, 'graph_mutations': 0, 'human_scientific_labels': 0,
        'human_rationale_labels': 0, 'scientific_accuracy': None,
        'scientific_improvement_established': False, 'interpretation': NOTICE}
    for arm in ARMS:
        retained = [reference[o['id']] for o in observations if o['actions'][arm]]
        good = sum(r['expected'] == 'SUPPORT' for r in retained)
        result['arms'][arm] = {'supported_controls': positive, 'context_errors': len(tasks) - positive,
            'supported_controls_retained': good, 'context_errors_retained': len(retained) - good,
            'false_flags': positive - good,
            'context_error_flag_rate': 1 - (len(retained) - good) / (len(tasks) - positive) if len(tasks) != positive else None}
        if execution['mode'] == 'none' and arm in ('legacy_v2', 'context_raw', 'context_checked'):
            result['arms'][arm] = {'status': 'not_run'}
    for arm in ('legacy_v2', 'context_v3'):
        rows = [traces[t['id']][arm] for t in tasks]
        valid = [(t, r) for t, r in zip(tasks, rows) if r['status'] == 'validated']
        def assessment(r): return r['verdict'] if arm == 'legacy_v2' else r['assessment']
        exact = sum(assessment(r)['verdict'] == reference[t['id']]['expected'] for t, r in valid)
        coverage = 0; aligned = 0; axis_cases = 0
        for t, r in valid:
            ref = reference[t['id']]; a = assessment(r)
            selected = {e['sentence_index'] for e in a['evidence']} if arm == 'legacy_v2' else set(a['evidence'])
            coverage += any(set(rs) <= selected for rs in ref['rationale_sets'])
            if arm == 'context_v3' and ref['axis']:
                axis_cases += 1; slot = a['context'][ref['axis']]
                aligned += slot['relation'] in {'mismatch', 'unknown'} and any(slot['index'] in rs for rs in ref['rationale_sets'])
        result['outputs'][arm] = {'status_counts': dict(Counter(r['status'] for r in rows)),
            'validated_outputs': len(valid), 'reference_verdict_matches': exact,
            'reference_verdict_match_rate_all_cases': exact / len(tasks),
            'reference_passage_sets_covered': coverage,
            'passage_coverage_note': 'Passage selection overlap only; not entailment or rationale correctness.',
            'expected_context_axis_aligned': aligned if arm == 'context_v3' else None,
            'validated_context_error_cases': axis_cases if arm == 'context_v3' else None,
            'expert_reasoning_correctness': None}
    return result


def run_context(packet, output, *, mode='none', model=None, verifier=None, progress=None):
    if mode not in {'none', 'configured', 'api', 'nim', 'codex'} or (mode == 'none' and verifier is not None):
        raise ValueError('Select an explicit supported context verifier mode.')
    p, tasks, contract = load_packet(packet)
    if mode != 'none' and verifier is None:
        verifier = configured_verifier(None if mode == 'configured' else mode, model=model)
    out = new_output(output, packet)
    for name in set(p['files']) | {'packet.json'}:
        target = out / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(packet) / name, target)
    (out / 'traces').mkdir()
    execution = {'packet_sha256': p['packet_sha256'], 'created_at': utcnow(), 'mode': mode,
        'model_requested': getattr(verifier, 'model', None), 'verifier_kind': getattr(verifier, 'kind', 'not_run'),
        'settings': {k: getattr(verifier, k, None) for k in ['endpoint', 'api', 'prompt_profile', 'max_output_tokens', 'timeout']},
        'requested_turn_budget': len(tasks) * 2 if verifier else 0, 'status': 'predictions_open'}
    write_json(out / 'execution.json', execution)
    traces = {}; observations = []
    for n, task in enumerate(tasks):
        pair = {}; order = ['legacy_v2', 'context_v3'] if n % 2 == 0 else ['context_v3', 'legacy_v2']
        for arm in order:
            trace = {**binding(task), 'status': 'not_run', 'model_calls': 0,
                     'verdict': None} if arm == 'legacy_v2' else {
                         **binding(task), 'status': 'not_run', 'model_calls': 0,
                         'assessment': None, 'gate': eligibility(task, None)}
            if verifier is not None:
                try:
                    trace = (assess_task({'task': task}, TaskBoundVerifier(verifier, task['id'], task=task))
                             if arm == 'legacy_v2' else verify_context(task, verifier))
                except Exception as exc:
                    trace.update(status='execution_error', model_calls=1, error=type(exc).__name__)
            pair[arm] = trace
            write_json(out / 'traces' / (task['id'] + '-' + arm + '.json'), trace)
            if progress: progress(f"Context comparison {n + 1}/{len(tasks)} {arm}: {trace['status']}")
        traces[task['id']] = pair
        observations.append({'id': task['id'], 'actions': actions(task, pair['legacy_v2'], pair['context_v3'])})
    # Parse reference labels only after all predictions have closed.
    execution['status'] = 'predictions_closed'; execution['closed_at'] = utcnow()
    execution['execution_sha256'] = digest(execution); write_json(out / 'execution.json', execution)
    refs = read(out / 'references.json')
    write_json(out / 'observations.json', observations)
    write_json(out / 'reviewer_worksheet.json', [{'id': t['id'], **binding(t), 'reviewer': None,
        'source_support': None, 'reference_agreement': None, 'rationale_correctness': None,
        'notes': None} for t in tasks])
    m = metrics(tasks, refs, traces, observations, execution)
    (out / 'report.html').write_text(render_report(m, tasks, refs, traces, observations), encoding='utf-8')
    m['files'] = {str(f.relative_to(out)): sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
    m['execution_sha256'] = execution['execution_sha256']; m['result_sha256'] = digest(m)
    write_json(out / 'metrics.json', m); verify_context_result(out)
    return m


def verify_context_result(folder):
    folder = Path(folder); m = read(folder / 'metrics.json'); signed(m, 'result_sha256')
    if m['format'] != POLICY + '.result': raise ValueError('Unknown context comparison result.')
    inventory(folder, m['files']); p, tasks, contract = load_packet(folder, check_engine=False)
    execution = read(folder / 'execution.json'); signed(execution, 'execution_sha256')
    if execution['status'] != 'predictions_closed' or execution['packet_sha256'] != p['packet_sha256']:
        raise ValueError('Context execution binding changed.')
    traces = {}; rows = read(folder / 'observations.json')
    expected_files = set(p['files']) | {'packet.json', 'execution.json', 'observations.json',
                                       'reviewer_worksheet.json', 'report.html'} | {
        'traces/' + t['id'] + '-' + arm + '.json' for t in tasks for arm in ('legacy_v2', 'context_v3')}
    if set(m['files']) != expected_files:
        raise ValueError('Context result inventory changed.')
    if [r['id'] for r in rows] != [t['id'] for t in tasks]:
        raise ValueError('Context observation inventory changed.')
    for task, row in zip(tasks, rows):
        pair = {arm: read(folder / 'traces' / (task['id'] + '-' + arm + '.json')) for arm in ('legacy_v2', 'context_v3')}
        for arm, trace in pair.items():
            if any(trace.get(k) != v for k, v in binding(task).items()):
                raise ValueError('Context trace input binding changed.')
            if trace.get('schema_sha256') is not None and trace['schema_sha256'] != contract[
                    'legacy_schema_sha256' if arm == 'legacy_v2' else 'context_schema_sha256'][task['id']]:
                raise ValueError('Context trace schema changed.')
            if trace.get('instructions_sha256') is not None and trace['instructions_sha256'] != digest(
                    contract['legacy_instructions' if arm == 'legacy_v2' else 'context_instructions']):
                raise ValueError('Context trace instructions changed.')
            if trace['status'] == 'validated':
                if arm == 'legacy_v2':
                    validate_verdict(trace['verdict'], task)
                    if bind_selection(task, trace['raw_selection_output']) != trace['verdict']:
                        raise ValueError('Legacy citation binding changed.')
                else:
                    validate(trace['assessment'], task)
                    if trace['assessment'] != trace['raw_output']:
                        raise ValueError('Context output was repaired.')
            if arm == 'context_v3' and trace['gate'] != eligibility(task, trace['assessment']):
                raise ValueError('Context eligibility check does not replay.')
        if row['actions'] != actions(task, pair['legacy_v2'], pair['context_v3']):
            raise ValueError('Context action does not replay.')
        traces[task['id']] = pair
    refs = read(folder / 'references.json'); expected = metrics(tasks, refs, traces, rows, execution)
    if any(m.get(k) != v for k, v in expected.items()) or m['execution_sha256'] != execution['execution_sha256']:
        raise ValueError('Context metrics do not replay.')
    if (folder / 'report.html').read_text() != render_report(m, tasks, refs, traces, rows):
        raise ValueError('Context report does not replay.')
    return m


def render_report(m, tasks, refs, traces, observations):
    esc = lambda v: escape(str(v), quote=True)
    reference = {r['id']: r for r in refs}
    table = ''.join('<tr>' + ''.join('<td>' + esc(v) + '</td>' for v in [arm,
        r.get('supported_controls_retained', 'not run'), r.get('context_errors_retained', 'not run'),
        r.get('false_flags', 'not run')]) + '</tr>' for arm, r in m['arms'].items())
    cases = []
    for task, row in zip(tasks, observations):
        pair = traces[task['id']]; ref = reference[task['id']]
        passages = ''.join('<p><b>[' + str(s['index']) + ']</b> ' + esc(s['text']) + '</p>' for s in task['document']['sentences'])
        trace = pair['context_v3']; a = trace.get('assessment') or {}; gate = trace['gate']
        context_table = ''.join('<tr><td>' + esc(axis) + '</td><td>' + esc(v['relation']) +
            '</td><td>' + esc(v['claim_span']) + '</td><td>' + esc(v['source_span']) +
            (' [' + str(v['index']) + ']' if v['index'] >= 0 else '') + '</td></tr>'
            for axis, v in a.get('context', {}).items())
        findings = ''.join('<li>' + esc(f['axis'] + ': ' + f['code'] + ' — ' + f['detail']) + '</li>' for f in gate['findings'])
        cases.append('<details><summary>' + esc(ref['reference_id']) + ' · PMID ' + str(task['document_id']) +
            '</summary><p class="claim">' + esc(task['claim']) + '</p><p>Reference (AI-authored): ' + esc(ref['expected']) +
            ' · ' + esc(ref['reason']) + '</p><p>Retained in advisory previews: ' + esc(row['actions']) + '</p>' +
            '<h3>Context extraction and eligibility</h3><p>Model: ' + esc(a.get('verdict', trace['status'])) +
            ' · Application recommendation: ' + esc(gate['action']) + '</p><p>' + esc(a.get('explanation', trace.get('error', 'Not run.'))) +
            '</p><div class="scroll"><table><tr><th>Dimension</th><th>Model relation</th><th>Exact claim span</th><th>Exact source span and passage</th></tr>' +
            context_table + '</table></div><ul>' + findings + '</ul><p>' + esc(gate['limitation']) +
            '</p><details><summary>Complete unchanged context response and checks</summary><pre>' + esc(json.dumps(trace, indent=2)) +
            '</pre></details><details><summary>Legacy output</summary><pre>' + esc(json.dumps(pair['legacy_v2'], indent=2)) +
            '</pre></details><details><summary>Exact source passages</summary>' + passages +
            '</details><p><a href="https://pubmed.ncbi.nlm.nih.gov/' + str(task['document_id']) + '/">Publication</a></p></details>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Context verification comparison</title><style>body{max-width:1100px;margin:25px auto;padding:20px;font:16px/1.55 system-ui;color:#19303b}'
        'table{border-collapse:collapse;width:100%}td,th{padding:10px;border:1px solid #ccd;text-align:left}details{padding:12px;margin:12px 0;border:1px solid #ccd;border-radius:8px}'
        'summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere}.scroll{overflow:auto}.claim{padding:15px;background:#edf6f6}.notice{padding:15px;background:#fff3d7}</style>'
        '<h1>Context verification comparison</h1><p class="notice">' + esc(NOTICE) + '</p><p>' + str(m['cases']) +
        ' cases · ' + str(m['publications']) + ' publications · ' + str(m['model_requests']) + ' model requests · graph changes: zero.</p>'
        '<p>Original and literal views retain unverified claims. Model views require SUPPORT. Context checked uses the same raw context outputs with additional eligibility checks; it makes no extra model calls. A review request is not a biological negative.</p>'
        '<table><tr><th>View</th><th>Valid controls retained</th><th>Context errors retained</th><th>False flags</th></tr>' + table + '</table>'
        '<h2>Output and rationale checks</h2><p>Passage coverage and expected-axis alignment are mechanical checks against AI references. Independent reasoning correctness remains unscored. Output failures stay in all-case denominators.</p><pre>' +
        esc(json.dumps(m['outputs'], indent=2)) + '</pre><h2>Inspect claims, contexts and source passages</h2>' + ''.join(cases) +
        '<p>The download includes frozen sources, protocol, both raw traces per case and a blank reviewer worksheet. No synthetic case attaches to a real graph assertion.</p></html>')
