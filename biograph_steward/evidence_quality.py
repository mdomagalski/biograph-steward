"""Source-consistency sandbox and read-only assertion passports.

Synthetic edit references are a text/binding contract, never biomedical gold.
No function in this module can write graph snapshots or human review events.
"""
from collections import Counter
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import re

from .client import digest, utcnow, write_json
from .crc_pilot import (assess_task, new_output, qualified_claim, sha,
                        INSTRUCTIONS)
from .literature import load_literature, source_document
from .verification import VERDICT_SCHEMA, binding, configured_verifier, validate_task, validate_verdict

POLICY = 'crc-source-consistency.v1'
ARMS = ('original', 'deterministic', 'assisted')
KEEP = 'retain_unverified'
SUPPORTED = 'retain_source_supported'
QUARANTINE = 'propose_quarantine'
REVIEW = 'request_review'
RETAINED = {KEEP, SUPPORTED}
FILES = {'cases.json', 'references.json', 'sources.json', 'contract.json'}
RESULT_FILES = FILES | {'packet.json', 'observations.json', 'reviewer_worksheet.json'}
LIMITATION = ('Development source-consistency pilot. Exact-excerpt controls and AI-authored synthetic-edit '
              'references are not independently reviewed biological gold. Original CIViC claims are unscored. '
              'Related cases share six publications; counts are not independent studies. '
              'Source support is not clinical truth. All changes are advisory previews; no graph state is changed.')


def engine():
    names = sorted(p.name for p in Path(__file__).parent.glob('*.py'))
    names += ['quality_cases.json', 'quality.js', 'ui.html']
    return {name: sha(Path(__file__).with_name(name)) for name in names}


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _signed(value, field):
    if value.get(field) != digest({k: v for k, v in value.items() if k != field}):
        raise ValueError('Evidence-quality integrity failed: ' + field)


def _inventory(path, manifest, expected):
    if set(manifest['files']) != expected:
        raise ValueError('Evidence-quality inventory changed.')
    for name, fingerprint in manifest['files'].items():
        if (Path(name).name != name or (path / name).is_symlink()
                or sha(path / name) != fingerprint):
            raise ValueError('Evidence-quality frozen bytes changed.')


def _default_specs():
    return _read(Path(__file__).with_name('quality_cases.json'))


def historical_inputs(packet):
    """Read verified historical *sources*, without re-running its frozen experiment.

    The original suite's engine check remains untouched. This new experiment
    records its own engine and only consumes source bytes and existing receipts.
    """
    from .evaluation import verify_result
    from .questions import graph_basis
    from .reviews import read_run
    path = Path(packet); p = _read(path / 'packet.json'); _signed(p, 'packet_sha256')
    if p['format'] != 'biograph-steward.crc-evidence-pilot.v1':
        raise ValueError('Expected a historical CRC source packet.')
    expected = {'panel.json', 'suite/suite.json', 'deterministic/evaluation.json'}
    if set(p['files']) != expected:
        raise ValueError('Historical packet inventory changed.')
    for name, value in p['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value:
            raise ValueError('Historical packet bytes changed.')
    suite = _read(path / 'suite/suite.json'); _signed(suite, 'suite_sha256')
    result = _read(path / 'deterministic/evaluation.json'); verify_result(result)
    if suite['suite_sha256'] != p['suite_sha256'] or result['evaluation_sha256'] != p['deterministic_evaluation_sha256']:
        raise ValueError('Historical source/control binding changed.')
    source = suite['sources']['enriched']; folder = path / 'suite/sources/enriched'
    if set(source['files']) - {'snapshot.json', 'civic_snapshot.json', 'review_events.json'}:
        raise ValueError('Unexpected historical source files.')
    _inventory(folder, source, set(source['files']))
    graph = read_run(folder)[2]
    if graph_basis(graph) != source['graph_basis_sha256']:
        raise ValueError('Historical graph basis changed under the current reader.')
    panel = _read(path / 'panel.json')
    for item in panel:
        _signed(item, 'panel_item_sha256')
        if item['record_sha256'] != digest(item['source_record']):
            raise ValueError('Historical source record changed.')
    return p, panel, graph


def make_cases(panel, papers, graph, specs):
    """References are constructed separately and never passed to the model."""
    if not isinstance(specs, list) or not 1 <= len(specs) <= 10:
        raise ValueError('Use 1–10 fixed publication anchors.')
    cases = []; references = []; used = set()
    by_assertion = {a['id']: a for a in graph['assertions']}
    item_assertions = {}
    for edge in graph['edges']:
        if edge['record_kind'] == 'variant_therapy_response':
            item_assertions.setdefault(edge['evidence_record']['id'], set()).add(edge['assertion_id'])
    for spec in specs:
        if (not re.fullmatch(r'[a-z0-9-]{1,60}', spec['id']) or spec['id'] in used
                or not isinstance(spec['changes'], list) or not 1 <= len(spec['changes']) <= 3):
            raise ValueError('Invalid or duplicate source anchor.')
        used.add(spec['id'])
        candidates = [p for p in panel if p['pmid'] == spec['pmid'] and p['filter_state'] == 'retained']
        if not candidates or spec['pmid'] not in papers:
            raise ValueError('Source anchor must have a retained original item and saved publication.')
        item = sorted(candidates, key=lambda p: digest(str(p['item_id'])))[0]
        matches = [by_assertion[aid] for aid in item_assertions.get(item['item_id'], [])]
        if len(matches) != 1:
            raise ValueError('Original source item must map to exactly one assertion.')
        parent = matches[0]
        document, selection = source_document(papers[spec['pmid']], spec['claim'], 'abstract')
        index = spec['passage_index']
        if (type(index) is not int or not 0 <= index < len(document['sentences'])
                or not spec['claim'] or spec['claim'] not in document['sentences'][index]['text']):
            raise ValueError('Positive control must be an exact contiguous source excerpt.')
        task = {'id': 'pending', 'claim_id': item['item_id'], 'document_id': int(spec['pmid']),
                'claim': spec['claim'], 'document': document}
        base = {'parent_assertion_id': parent['id'], 'parent_revision': parent['revision'],
                'item_id': item['item_id'], 'source_record_sha256': item['record_sha256'],
                'subject': 'UniProtKB:P01116', 'predicate': parent['predicate'],
                'object': parent['object'], 'profile': item['source_record']['molecularProfile']['name'],
                'therapy': ' | '.join(t['name'] for t in item['source_record']['therapies']),
                'source_pmid': spec['pmid'], 'citation_pmid': spec['pmid'],
                'citation_index': index, 'citation_quote': document['sentences'][index]['text'],
                'selection': selection, 'task': task, 'lifecycle_state': parent['lifecycle_state']}

        def add(suffix, kind, expected, reason, change=None):
            case = deepcopy(base); case['id'] = 'quality-' + spec['id'] + '-' + suffix
            # Neither control/edit names nor reference labels enter a model turn.
            case['task']['id'] = 'task-' + digest(case['id'])[:24]; case['kind'] = kind
            if change:
                change(case)
            case['changed_fields'] = {k: {'before': base[k], 'after': case[k]} for k in
                ['subject', 'citation_pmid', 'citation_quote'] if base[k] != case[k]}
            if base['task']['claim'] != case['task']['claim']:
                case['changed_fields']['claim'] = {'before': base['task']['claim'], 'after': case['task']['claim']}
            if kind == 'original_annotation':
                case['changed_fields'] = {}
            validate_task(case['task']); cases.append(case)
            references.append({'id': case['id'], 'expected': expected, 'reason': reason,
                               'reference_kind': 'unreviewed_original' if expected is None else
                               'exact_source_excerpt' if expected == 'retain' else 'synthetic_source_contract',
                               'independent_human_review': False})

        add('control', 'source_excerpt', 'retain', 'Exact excerpt, with its source identity and complete abstract supplied.')
        add('identifier', 'identifier_binding', 'flag', 'KRAS source record bound to a different protein identifier.',
            lambda c: c.update(subject='UniProtKB:P00533'))
        add('citation', 'citation_binding', 'flag', 'Citation identity does not match the supplied publication.',
            lambda c: c.update(citation_pmid='99999999'))
        add('quotation', 'citation_span', 'flag', 'Attributed quotation differs from the frozen source block.',
            lambda c: c.update(citation_quote=c['citation_quote'] + ' [altered test quotation]'))
        for i, change in enumerate(spec['changes']):
            before, after = change['before'], change['after']
            if not before or not after or before == after or before not in spec['claim']:
                raise ValueError('Synthetic edit must change a stated source excerpt.')
            add('edit-' + str(i + 1), change['type'], 'flag', change['reason'],
                lambda c, before=before, after=after: c['task'].update(
                    claim=c['task']['claim'].replace(before, after)))
        # Preserve the complete real annotation, without assuming it is supported.
        add('original', 'original_annotation', None, 'Scientific/source-support reference remains open.',
            lambda c: c['task'].update(claim=qualified_claim(item['source_record'])))
    return cases, references


def prepare_quality(packet, literature, output, *, specs=None):
    p, panel, graph = historical_inputs(packet)
    lm, papers = load_literature(literature)
    if set(lm['requested_pmids']) != set(p['pmids']):
        raise ValueError('Literature must match the frozen pilot source inventory.')
    cases, references = make_cases(panel, papers, graph, specs if specs is not None else _default_specs())
    sources = {'pilot_packet_sha256': p['packet_sha256'], 'literature_manifest': lm,
               'pharos_snapshot_sha256': graph['snapshot_sha256'],
               'civic_snapshot_sha256': graph['civic_snapshot_sha256'],
               'source_records': [r for r in panel if r['item_id'] in {c['item_id'] for c in cases}],
               'papers': [papers[pmid] for pmid in sorted({c['source_pmid'] for c in cases})]}
    contract = {'policy': POLICY, 'engine': engine(), 'arms': list(ARMS),
                'instructions_sha256': digest(INSTRUCTIONS), 'schema_sha256': digest(VERDICT_SCHEMA),
                'selection': 'Six predeclared saved-paper anchors; one retained annotation per paper in SHA order. Reused development sources.',
                'reference_scope': LIMITATION, 'human_scientific_labels': 0,
                'model_input_fields': ['id', 'claim_id', 'document_id', 'claim', 'document'],
                'inference': 'One turn per structurally usable case, no retries/repair/fallback/tools; labels and edit descriptions withheld.',
                'decision_policy': 'Binding failure -> propose quarantine. Valid SUPPORT -> retain source-supported. CONTRADICT -> propose quarantine. NEI/error -> request review. No lifecycle writes.',
                'metrics_policy': 'All three arms share inventory. Errors count as review, never support. Score retain-vs-flag references only; originals unscored. False quarantine and any false flag are separate.',
                'promotion_policy': 'No automatic promotion or pruning. Descriptive source-contract comparison only.',
                'graph_mutations': False, 'fresh_dependency_values_loaded': False}
    out = new_output(output, packet, literature)
    for name, data in [('cases.json', cases), ('references.json', references), ('sources.json', sources), ('contract.json', contract)]:
        write_json(out / name, data)
    manifest = {'format': POLICY + '.packet', 'created_at': utcnow(), 'cases': len(cases),
                'publications': len(sources['papers']), 'files': {n: sha(out / n) for n in sorted(FILES)}}
    manifest['packet_sha256'] = digest(manifest); write_json(out / 'packet.json', manifest)
    return manifest


def load_quality_packet(path, *, check_engine=True):
    path = Path(path); p = _read(path / 'packet.json'); _signed(p, 'packet_sha256')
    if p['format'] != POLICY + '.packet':
        raise ValueError('Unknown evidence-quality packet.')
    _inventory(path, p, FILES)
    cases, refs, sources, contract = [_read(path / n) for n in ['cases.json', 'references.json', 'sources.json', 'contract.json']]
    if check_engine and contract['engine'] != engine():
        raise ValueError('Evidence-quality engine changed after freeze; prepare a new packet.')
    if (len(cases) != p['cases'] or len({c['id'] for c in cases}) != len(cases)
            or {c['id'] for c in cases} != {r['id'] for r in refs} or len(refs) != len(cases)):
        raise ValueError('Evidence-quality case inventory changed.')
    # Re-bind every copied passage to the full saved paper; a file hash alone is insufficient.
    papers = {r['pmid']: r for r in sources['papers']}
    items = {r['item_id']: r for r in sources['source_records']}
    for c in cases:
        if not re.fullmatch(r'quality-[a-z0-9-]{1,90}', c['id']):
            raise ValueError('Invalid bounded quality case identity.')
        validate_task(c['task']); item = items[c['item_id']]
        if (c['task']['id'] != 'task-' + digest(c['id'])[:24] or c['task']['document_id'] != int(c['source_pmid'])
                or c['source_record_sha256'] != digest(item['source_record'])):
            raise ValueError('Evidence-quality case/source binding changed.')
        doc, selection = source_document(papers[c['source_pmid']], '', 'abstract')
        if c['task']['document'] != doc or c['selection'] != selection:
            raise ValueError('Evidence-quality source passages changed.')
    return p, cases, refs, sources, contract


def deterministic_findings(case):
    findings = []
    if case['subject'] != 'UniProtKB:P01116':
        findings.append({'code': 'identifier_binding', 'detail': 'Protein identifier does not match this frozen KRAS-only source scope.'})
    if case['citation_pmid'] != case['source_pmid']:
        findings.append({'code': 'citation_binding', 'detail': 'Attributed publication differs from the supplied source identity.'})
    index = case['citation_index']; sentences = case['task']['document']['sentences']
    if (type(index) is not int or not 0 <= index < len(sentences)
            or case['citation_quote'] != sentences[index]['text']):
        findings.append({'code': 'citation_span', 'detail': 'Attributed quotation is not the exact frozen source block.'})
    return findings


def decisions(case, trace):
    findings = deterministic_findings(case)
    deterministic = QUARANTINE if findings else KEEP
    if findings:
        assisted = QUARANTINE
    elif trace.get('status') == 'validated':
        assisted = {'SUPPORT': SUPPORTED, 'CONTRADICT': QUARANTINE,
                    'NOT_ENOUGH_INFORMATION': REVIEW}[trace['verdict']['verdict']]
    else:
        assisted = REVIEW
    return {'original': KEEP, 'deterministic': deterministic, 'assisted': assisted}


def score_quality(cases, references, observations, *, assisted_run=True):
    by_id = {r['id']: r for r in references}
    result = {}
    for arm in ARMS:
        scored = [(c, by_id[c['id']], o['decisions'][arm]) for c, o in zip(cases, observations)
                  if by_id[c['id']]['expected'] is not None]
        good = sum(r['expected'] == 'retain' for _, r, _ in scored)
        bad = len(scored) - good
        caught = sum(r['expected'] == 'flag' and a not in RETAINED for _, r, a in scored)
        false_flag = sum(r['expected'] == 'retain' and a not in RETAINED for _, r, a in scored)
        false_quarantine = sum(r['expected'] == 'retain' and a == QUARANTINE for _, r, a in scored)
        flagged = caught + false_flag
        result[arm] = {'status': 'completed', 'cases': len(cases), 'scored_source_contract_cases': len(scored),
                       'unscored_original_annotations': len(cases) - len(scored),
                       'supported_controls': good, 'injected_source_contract_errors': bad,
                       'supported_controls_retained': good - false_flag,
                       'unsupported_test_cases_retained': bad - caught,
                       'flag_precision': caught / flagged if flagged else None,
                       'flag_recall': caught / bad if bad else None,
                       'false_flag_count': false_flag, 'false_flag_rate': false_flag / good if good else None,
                       'false_quarantine_count': false_quarantine,
                       'false_quarantine_rate': false_quarantine / good if good else None,
                       'action_counts': dict(Counter(o['decisions'][arm] for o in observations)),
                       'by_case_kind': {kind: {
                           'cases': sum(c['kind'] == kind for c, _, _ in scored),
                           'flagged': sum(c['kind'] == kind and a not in RETAINED for c, _, a in scored)}
                           for kind in sorted({c['kind'] for c, _, _ in scored})}}
        if arm == 'assisted' and not assisted_run:
            result[arm].update(status='not_run', scored_source_contract_cases=0,
                supported_controls_retained=None, unsupported_test_cases_retained=None,
                flag_precision=None, flag_recall=None, false_flag_count=None, false_flag_rate=None,
                false_quarantine_count=None, false_quarantine_rate=None, by_case_kind={})
    return result


def run_quality(packet, output, *, mode='none', model=None, verifier=None, progress=None):
    if mode not in {'none', 'configured', 'api', 'nim', 'codex'} or (mode == 'none' and verifier is not None):
        raise ValueError('Select an explicit supported verifier mode.')
    p, cases, refs, sources, contract = load_quality_packet(packet)
    if mode != 'none' and verifier is None:
        verifier = configured_verifier(None if mode == 'configured' else mode, model=model)
    out = new_output(output, packet)
    for name in FILES | {'packet.json'}:
        (out / name).write_bytes((Path(packet) / name).read_bytes())
    execution = {'format': POLICY + '.execution', 'created_at': utcnow(), 'packet_sha256': p['packet_sha256'],
                 'mode': mode, 'model_requested': getattr(verifier, 'model', None),
                 'verifier_kind': getattr(verifier, 'kind', 'not_run'),
                 'eligible_model_turns': sum(not deterministic_findings(c) for c in cases),
                 'model_settings': {k: getattr(verifier, k, None) for k in
                     ['endpoint', 'api', 'prompt_profile', 'max_output_tokens', 'timeout']}}
    execution['execution_sha256'] = digest(execution); write_json(out / 'execution.json', execution)
    observations = []; (out / 'traces').mkdir()
    for i, c in enumerate(cases):
        findings = deterministic_findings(c)
        trace = {'status': 'blocked_integrity' if findings else 'not_run', 'model_calls': 0, 'verdict': None}
        if not findings and verifier is not None:
            try:
                trace = assess_task({'task': c['task']}, verifier)
            except Exception as exc:
                # Domain/provider failure consumes this case; never retry or claim success.
                trace = {'status': 'execution_error', 'model_calls': 1, 'verdict': None,
                         'error': type(exc).__name__, **binding(c['task'])}
        write_json(out / 'traces' / (c['id'] + '.json'), trace)
        observations.append({'id': c['id'], 'findings': findings, 'decisions': decisions(c, trace),
                             'status': trace['status'], 'assessment': trace.get('verdict'),
                             'trace_sha256': sha(out / 'traces' / (c['id'] + '.json')),
                             'model_calls': trace.get('model_calls', 0)})
        if progress:
            progress(f"Evidence-quality {i + 1}/{len(cases)}: {c['id']} {trace['status']}")
    write_json(out / 'observations.json', observations)
    write_json(out / 'reviewer_worksheet.json', [{'id': c['id'], 'source_support': None,
                'reference_agreement': None, 'reviewer': None, 'reason': None,
                'task_sha256': binding(c['task'])['task_sha256']} for c in cases])
    metrics = _metrics(p, cases, refs, sources, observations, execution)
    metrics['files'] = {n: sha(out / n) for n in sorted(RESULT_FILES | {'execution.json'})}
    metrics['trace_files'] = {c['id'] + '.json': o['trace_sha256'] for c, o in zip(cases, observations)}
    (out / 'report.html').write_text(render_quality_report(metrics, cases, refs, observations), encoding='utf-8')
    metrics['report_sha256'] = sha(out / 'report.html')
    metrics['result_sha256'] = digest(metrics); write_json(out / 'metrics.json', metrics)
    verify_quality_result(out)
    return metrics


def _metrics(p, cases, refs, sources, observations, execution):
    validated = [o for o in observations if o['status'] == 'validated']
    decisive = [o for o in validated if o['assessment']['verdict'] != 'NOT_ENOUGH_INFORMATION']
    return {'format': POLICY + '.result', 'packet_sha256': p['packet_sha256'],
            'execution_sha256': execution['execution_sha256'], 'cases': len(cases),
            'publications': len(sources['papers']), 'mode': execution['mode'],
            'model_requested': execution['model_requested'], 'verifier_kind': execution['verifier_kind'],
            'model_requests': sum(o['model_calls'] for o in observations),
            'status_counts': dict(Counter(o['status'] for o in observations)),
            'machine_verdict_counts': dict(Counter(o['assessment']['verdict'] for o in validated)),
            'decisive_assessments': len(decisive),
            'valid_exact_citation_assessments': len(decisive),
            'citation_note': 'Exact quotation fidelity only; citation correctness does not establish entailment.',
            'source_provenance_completeness': sum(bool(c['source_record_sha256'] and c['selection']['passages']) for c in cases) / len(cases),
            'binding_or_citation_integrity_failures': sum(bool(deterministic_findings(c)) for c in cases),
            'invalid_model_outputs': sum(o['status'] == 'invalid_output' for o in observations),
            'model_execution_errors': sum(o['status'] in {'model_error', 'execution_error', 'timeout'} for o in observations),
            'arms': score_quality(cases, refs, observations, assisted_run=execution['mode'] != 'none'), 'human_scientific_labels': 0,
            'scientific_accuracy': None, 'scientific_improvement_established': False,
            'graph_mutations': 0, 'interpretation': LIMITATION,
            'pharos_snapshot_sha256': sources['pharos_snapshot_sha256'],
            'civic_snapshot_sha256': sources['civic_snapshot_sha256']}


def verify_quality_result(path):
    """Offline replay of every decision, binding, citation and reported metric."""
    path = Path(path); m = _read(path / 'metrics.json'); _signed(m, 'result_sha256')
    if m['format'] != POLICY + '.result':
        raise ValueError('Unknown evidence-quality result.')
    _inventory(path, m, RESULT_FILES | {'execution.json'})
    p, cases, refs, sources, contract = load_quality_packet(path, check_engine=False)
    execution = _read(path / 'execution.json'); _signed(execution, 'execution_sha256')
    if execution['packet_sha256'] != p['packet_sha256']:
        raise ValueError('Quality execution/packet binding changed.')
    rows = _read(path / 'observations.json')
    if [r['id'] for r in rows] != [c['id'] for c in cases]:
        raise ValueError('Quality observation inventory changed.')
    if set(m['trace_files']) != {c['id'] + '.json' for c in cases}:
        raise ValueError('Quality trace inventory changed.')
    for c, o in zip(cases, rows):
        name = c['id'] + '.json'; f = path / 'traces' / name
        if f.is_symlink() or sha(f) != o['trace_sha256'] or sha(f) != m['trace_files'][name]:
            raise ValueError('Quality trace changed.')
        t = _read(f)
        if t['status'] == 'validated':
            if any(t.get(k) != v for k, v in binding(c['task']).items()):
                raise ValueError('Quality model input binding changed.')
            validate_verdict(t['verdict'], c['task'])
        if (o['assessment'] != t.get('verdict') or o['status'] != t['status']
                or o['model_calls'] != t.get('model_calls', 0)
                or o['decisions'] != decisions(c, t) or o['findings'] != deterministic_findings(c)):
            raise ValueError('Quality trace/decision mismatch.')
    expected = _metrics(p, cases, refs, sources, rows, execution)
    if any(m.get(k) != v for k, v in expected.items()):
        raise ValueError('Quality reported metrics do not replay.')
    if ((path / 'report.html').is_symlink() or sha(path / 'report.html') != m['report_sha256']
            or (path / 'report.html').read_text() != render_quality_report(m, cases, refs, rows)):
        raise ValueError('Quality report changed.')
    return m


def quality_passports(path, graph, assertion_id):
    """Only original annotations, never injected edits, can attach to real edges."""
    m = verify_quality_result(path)
    if (m['pharos_snapshot_sha256'] != graph['snapshot_sha256']
            or m['civic_snapshot_sha256'] != graph.get('civic_snapshot_sha256')):
        return []
    assertion = next((a for a in graph['assertions'] if a['id'] == assertion_id), None)
    if assertion is None:
        return []
    cases = _read(Path(path) / 'cases.json'); rows = _read(Path(path) / 'observations.json')
    return [{'result_sha256': m['result_sha256'], 'case': c, 'observation': o,
             'lifecycle_note': 'Advisory source assessment; existing human review state is unchanged.'}
            for c, o in zip(cases, rows) if c['kind'] == 'original_annotation'
            and c['parent_assertion_id'] == assertion_id and c['parent_revision'] == assertion['revision']]


def render_quality_report(metrics, cases, refs, rows):
    esc = lambda v: escape(str(v), quote=True)
    references = {r['id']: r for r in refs}
    arm_table = ''
    for arm in ARMS:
        s = metrics['arms'][arm]
        values = [arm, s['supported_controls_retained'], s['unsupported_test_cases_retained'],
                  s['flag_precision'], s['flag_recall'], s['false_flag_count'], s['false_quarantine_count']]
        arm_table += '<tr>' + ''.join('<td>' + esc(v if v is not None else 'undefined') + '</td>' for v in values) + '</tr>'
    sections = []
    for c, o in zip(cases, rows):
        assessment = o['assessment'] or {}; reference = references[c['id']]
        quote_html = ''.join('<blockquote>' + esc(e['quote']) + '</blockquote><p class="small">' +
                             esc(c['selection']['passages'][e['sentence_index']]['locator']) + '</p>'
                             for e in assessment.get('evidence', []))
        passages = ''.join('<p><b>[' + str(s['index']) + ']</b> ' + esc(s['text']) + '</p><small>' +
                           esc(c['selection']['passages'][s['index']]['locator']) + '</small>'
                           for s in c['task']['document']['sentences'])
        sections.append('<details class="case" data-original="' + ('yes' if c['kind'] == 'original_annotation' else 'no') +
            '" data-actions="' + ' '.join(esc(o['decisions'][a]) for a in ARMS) + '"><summary>' +
            esc(c['id']) + ' · ' + esc(c['kind']) + '</summary><p><b>' + esc(
            c['profile'] + ' → ' + c['therapy'] if c['kind'] == 'original_annotation' else 'Source-text test claim → PMID ' + c['source_pmid']) +
            '</b> · source PMID ' + esc(c['source_pmid']) + '</p><p class="claim">' + esc(c['task']['claim']) + '</p>' +
            '<p><b>Why present?</b> ' + esc('Original source annotation; support remains open.' if c['kind'] == 'original_annotation' else
            'Controlled source-consistency sandbox assertion linked to its unchanged parent record.') + '</p>' +
            '<ul>' + ''.join('<li><b>' + esc(a) + ':</b> ' + esc(o['decisions'][a]) + '</li>' for a in ARMS) + '</ul>' +
            '<p><b>Why flagged or retained?</b> ' + esc(assessment.get('explanation') or
            '; '.join(f['detail'] for f in o['findings']) or 'No semantic assessment in this view.') + '</p>' + quote_html +
            '<p><b>Context mismatches:</b> ' + esc(assessment.get('context_mismatches', [])) + '</p><p><b>Missing details:</b> ' +
            esc(assessment.get('missing_details', [])) + '</p><p><b>Reference:</b> ' + esc(reference['expected'] or 'unscored') +
            ' · ' + esc(reference['reason']) + ' Independent human review: no.</p><p><b>Review state:</b> ' + esc(c['lifecycle_state']) +
            '; unchanged. Proposed quarantine is reversible advice, not a saved decision.</p><details><summary>Exact supplied source passages</summary>' + passages +
            '</details><details><summary>What changed in this test case?</summary><pre>' + esc(json.dumps(c['changed_fields'], indent=2)) +
            '</pre></details><details><summary>Source and assertion identity</summary><pre>' + esc(json.dumps({k: c[k] for k in
            ['parent_assertion_id', 'parent_revision', 'source_record_sha256', 'subject', 'source_pmid', 'citation_pmid']}, indent=2)) +
            '</pre></details></details>')
    # No data interpolation into executable JavaScript; all source text is escaped HTML.
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>CRC evidence-quality comparison</title><style>body{max-width:1120px;margin:24px auto;padding:20px;font:16px/1.55 system-ui;color:#19303b}'
        'table{border-collapse:collapse;width:100%;display:block;overflow:auto}th,td{border:1px solid #cbd5db;padding:10px;text-align:left}'
        'details{border:1px solid #cbd5db;border-radius:8px;padding:12px;margin:12px 0}summary{cursor:pointer}blockquote,.claim{border-left:4px solid #147c83;padding:12px;background:#f1f7f7}'
        'pre,small{white-space:pre-wrap;overflow-wrap:anywhere}.notice{padding:15px;background:#fff4d9}.small{font-size:13px}select{font:inherit;padding:8px}svg{max-width:100%}</style>'
        '<h1>CRC evidence-quality comparison</h1><p class="notice">' + esc(LIMITATION) + '</p>'
        '<p>' + esc(metrics['cases']) + ' cases · ' + esc(metrics['publications']) + ' publications · ' + esc(metrics['model_requests']) +
        ' requested verifier turns · human scientific labels: zero · graph changes: zero.</p>'
        '<h2>Same assertions, three advisory views</h2><p>“Retained” describes a preview, not human acceptance. A request for review withholds an assertion from the supported preview; it does not declare the biological relationship false.</p>'
        '<table><tr><th>View</th><th>Supported controls retained</th><th>Injected errors retained</th><th>Flag precision</th><th>Flag recall</th><th>False flags</th><th>False quarantine proposals</th></tr>' + arm_table + '</table>'
        '<p>Flag metrics score exact-source controls and the known source-contract edits only. Quotation fidelity is distinct from entailment. Unscored original annotations stay visible below.</p>'
        '<h2>Inspect an evidence edge</h2><label for="view">Preview </label><select id="view"><option value="all">All assertions and findings</option><option value="original">Original view</option><option value="deterministic">Retained after deterministic checks</option><option value="assisted">Retained after checks + verifier</option><option value="annotations">Unmodified source annotations</option></select>'
        '<p id="visible" role="status"></p><svg viewBox="0 0 800 100" role="img" aria-label="Molecular profile to treatment assertion with traceable source passport"><rect x="5" y="18" width="240" height="60" rx="8" fill="#e2f2f1"/>'
        '<text x="125" y="54" text-anchor="middle">Molecular profile</text><path d="M245 48 H555" stroke="#147c83" stroke-width="3"/><text x="400" y="35" text-anchor="middle">qualified evidence</text>'
        '<rect x="555" y="18" width="240" height="60" rx="8" fill="#eeedf7"/><text x="675" y="54" text-anchor="middle">Treatment / context</text></svg>' + ''.join(sections) +
        '<script>document.getElementById("view").addEventListener("change",function(){const i={original:0,deterministic:1,assisted:2}[this.value];let n=0;document.querySelectorAll(".case").forEach(c=>{const a=c.dataset.actions.split(" ");c.hidden=this.value==="annotations"?c.dataset.original!=="yes":i!==undefined&&!a[i].startsWith("retain_");if(!c.hidden)n++;});document.getElementById("visible").textContent=n+" assertions visible. Hidden records remain in this report and its export.";});</script>'
        '<h2>Review and reproducibility</h2><p>The export contains blank reviewer worksheets, frozen inputs, source identities, exact quotations and all model traces. Independent scientific adjudication is still pending.</p></html>')
