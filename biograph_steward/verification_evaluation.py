"""Immutable given-document evaluation, with gold read after prediction closes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re

from . import __version__
from .client import digest, write_json
from .verification import (POLICY, INSTRUCTIONS, VERDICT_SCHEMA, LABELS, CodexVerifier,
                           VerificationOutputError, baseline_verdict, binding,
                           validate_task, validate_verdict)

BASELINES = ('accept_all', 'always_insufficient', 'lexical_overlap')


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def write_rows(path, records):
    Path(path).write_text(''.join(json.dumps(r, ensure_ascii=True) + '\n' for r in records), encoding='utf-8')


def _new_output(output, source):
    output, source = Path(output).resolve(), Path(source).resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('Keep results separate from their frozen input directory.')
    if output.exists():
        raise ValueError('Choose a new result directory; verification runs are immutable.')
    output.mkdir(parents=True)
    return output


def _gold_map(tasks, records):
    by_id = {r['id']: r for r in records}
    if len(by_id) != len(records) or set(by_id) != {t['id'] for t in tasks}:
        raise ValueError('Gold identities must match the selected inputs exactly.')
    for task in tasks:
        row = by_id[task['id']]; label = row['label']; sets = row['rationale_sets']
        if label not in LABELS or not isinstance(sets, list) or (label == LABELS[2]) != (len(sets) == 0):
            raise ValueError('Invalid source-support label or rationale inventory.')
        for indices in sets:
            if (not isinstance(indices, list) or not indices
                    or any(type(i) is not int or not 0 <= i < len(task['document']['sentences']) for i in indices)
                    or len(set(indices)) != len(indices)):
                raise ValueError('Invalid gold rationale sentence indices.')
    return by_id


def score_predictions(tasks, gold_records, predictions):
    """Local component metrics. Errors remain false negatives in all class scores."""
    gold = _gold_map(tasks, gold_records)
    predicted = {p['id']: p for p in predictions}
    if len(predicted) != len(predictions) or set(predicted) != set(gold):
        raise ValueError('Prediction identities must match the selected inputs exactly.')
    confusion = {label: {p: 0 for p in (*LABELS, 'ERROR')} for label in LABELS}
    complete = correct_complete = sentence_tp = sentence_pred = sentence_gold = 0
    statuses = Counter(); invalid_reference_tasks = invalid_references = 0
    for task in tasks:
        g = gold[task['id']]; row = predicted[task['id']]
        status = row['status']; verdict = row.get('verdict'); statuses[status] += 1
        if any(row.get(k) != v for k, v in binding(task).items()):
            raise ValueError('Prediction source/claim binding changed.')
        if status == 'validated':
            validate_verdict(verdict, task)
            label = verdict['verdict']; indices = {e['sentence_index'] for e in verdict['evidence']}
        else:
            label = 'ERROR'; indices = set()
        bad = row.get('invalid_references', 0)
        if type(bad) is not int or bad < 0:
            raise ValueError('Invalid reference failure count.')
        invalid_reference_tasks += int(bad > 0); invalid_references += bad
        confusion[g['label']][label] += 1
        sets = [set(s) for s in g['rationale_sets']]
        covered = [s for s in sets if s <= indices]
        complete += int(bool(covered))
        correct_complete += int(label == g['label'] and (bool(covered) or g['label'] == LABELS[2]))
        sentence_pred += len(indices)
        sentence_gold += len(set().union(*sets)) if sets else 0
        if label == g['label'] and covered:
            sentence_tp += len(set().union(*covered))
    def ratio(a, b):
        return a / b if b else None
    classes = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[g][label] for g in LABELS if g != label)
        fn = sum(v for p, v in confusion[label].items() if p != label)
        classes[label] = {'precision': ratio(tp, tp + fp), 'recall': ratio(tp, tp + fn),
                          'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
                          'gold_pairs': sum(confusion[label].values()), 'true_positive': tp,
                          'false_positive': fp, 'false_negative': fn}
    n = len(tasks); decisive = n - sum(confusion[LABELS[2]].values())
    return {'pairs': n, 'claims': len({t['claim_id'] for t in tasks}),
            'accuracy': sum(confusion[l][l] for l in LABELS) / n,
            'macro_f1': sum(c['f1'] for c in classes.values()) / len(LABELS),
            'per_class': classes, 'confusion_matrix': confusion,
            'support_precision': classes['SUPPORT']['precision'],
            'false_support_rate': ratio(sum(confusion[g]['SUPPORT'] for g in LABELS if g != 'SUPPORT'),
                                        sum(sum(confusion[g].values()) for g in LABELS if g != 'SUPPORT')),
            'complete_rationale_coverage': ratio(complete, decisive),
            'label_and_complete_rationale_accuracy': correct_complete / n,
            'evidence_sentence_precision': ratio(sentence_tp, sentence_pred),
            'evidence_sentence_recall': ratio(sentence_tp, sentence_gold),
            'evidence_sentence_counts': {'correct': sentence_tp, 'predicted': sentence_pred, 'gold_union': sentence_gold},
            'status_counts': dict(statuses),
            'error_rate': sum(v for k, v in statuses.items() if k != 'validated') / n,
            'insufficient_predictions': sum(confusion[g][LABELS[2]] for g in LABELS),
            'invalid_reference_rate': invalid_reference_tasks / n,
            'invalid_reference_tasks': invalid_reference_tasks, 'invalid_references': invalid_references}


def _prediction(task, trace):
    """Revalidate even injected adapters: model output cannot assert its own validity."""
    if trace.get('status') == 'validated':
        try:
            validate_verdict(trace.get('verdict'), task)
        except VerificationOutputError as exc:
            trace.update(status='invalid_output', verdict=None, error=str(exc), invalid_references=exc.invalid_references)
    if any(trace.get(k) != v for k, v in binding(task).items()):
        trace.update(status='invalid_output', verdict=None, error='Verifier returned mismatched input bindings.')
    return {'id': task['id'], **binding(task), 'status': trace['status'],
            'verdict': trace.get('verdict') if trace['status'] == 'validated' else None,
            'invalid_references': trace.get('invalid_references', 0)}


def run_verification(benchmark, output, mode='baselines', model=None, limit=None,
                     verifier=None, progress=None, workers=1):
    if mode not in {'baselines', 'codex'} or type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError('Choose baselines/codex and 1–4 workers.')
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError('Limit must be a positive number of claim/abstract pairs.')
    source = Path(benchmark).resolve()
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['format'] != 'biograph-steward.provided-document-verification.v1':
        raise ValueError('Unsupported provided-document benchmark format.')
    for filename, key in [('inputs.jsonl', 'inputs_sha256'), ('gold.jsonl', 'gold_sha256')]:
        if file_sha(source / filename) != manifest[key]:
            raise ValueError('Frozen benchmark bytes changed: ' + filename)
    tasks = read_rows(source / 'inputs.jsonl')
    for task in tasks:
        validate_task(task)
    if not tasks or len({t['id'] for t in tasks}) != len(tasks) or len(tasks) != manifest['claim_abstract_pairs']:
        raise ValueError('Invalid benchmark input inventory.')
    # Stable hash selection never consults expert labels. A limit is a smoke pilot.
    tasks = sorted(tasks, key=lambda t: (digest(t['id']), t['id']))[:limit]
    out = _new_output(output, source)
    if mode == 'codex' and verifier is None:
        verifier = CodexVerifier(model=model)
    write_rows(out / 'inputs.jsonl', tasks)
    write_json(out / 'benchmark_manifest.json', manifest)
    contract = {'policy': POLICY, 'instructions': INSTRUCTIONS, 'schema': VERDICT_SCHEMA,
                'max_sentences': 3, 'max_turns_per_pair': 1, 'timeout_seconds': 90,
                'baselines': {'accept_all': 'SUPPORT, first sentence as arbitrary citation',
                              'always_insufficient': 'NOT_ENOUGH_INFORMATION, no citations',
                              'lexical_overlap': 'SUPPORT if best sentence covers >=0.5 of non-stopword claim tokens; otherwise insufficient'}}
    write_json(out / 'contract.json', contract)
    run = {'format': 'biograph-steward.source-verifier-result.v1', 'status': 'predicting',
           'created_at': datetime.now(timezone.utc).isoformat(), 'app_version': __version__,
           'mode': mode, 'model_requested': getattr(verifier, 'model', None),
           'verifier_kind': getattr(verifier, 'kind', 'not_run'), 'workers': workers,
           'benchmark_manifest_sha256': file_sha(source / 'manifest.json'),
           'benchmark_manifest_copy_sha256': file_sha(out / 'benchmark_manifest.json'),
           'benchmark_inputs_sha256': manifest['inputs_sha256'], 'benchmark_gold_sha256': manifest['gold_sha256'],
           'selected_inputs_sha256': file_sha(out / 'inputs.jsonl'), 'contract_sha256': file_sha(out / 'contract.json'),
           'selection': {'method': 'ascending_sha256_of_task_id', 'limit_pairs': limit,
                         'available_pairs': manifest['claim_abstract_pairs'], 'selected_pairs': len(tasks)},
           'engine': {p.name: file_sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
           'scientific_improvement_established': False}
    write_json(out / 'run_manifest.json', run)
    traces = out / 'traces'; traces.mkdir()
    predictions = []; baseline_rows = {b: [] for b in BASELINES}
    for task in tasks:
        for baseline in BASELINES:
            baseline_rows[baseline].append({'id': task['id'], **binding(task), 'status': 'validated',
                                            'verdict': baseline_verdict(task, baseline)})
    if mode == 'codex':
        def verify(index, task):
            try:
                trace = verifier.verify(task)
            except Exception:
                # Failures consume this case. Do not retry, expose exception secrets, or silently substitute a baseline.
                trace = {**binding(task), 'status': 'model_error', 'verdict': None,
                         'error': 'Verifier adapter failed; no retry or fallback was used.', 'model_calls': 1}
            row = _prediction(task, trace)
            path = traces / f'{index:05d}.json'
            write_json(path, trace)
            row.update(trace_file='traces/' + path.name, trace_sha256=file_sha(path))
            return row
        with (out / 'predictions.jsonl').open('w', encoding='utf-8') as stream:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(verify, i, task) for i, task in enumerate(tasks)]
                for future in as_completed(futures):
                    row = future.result(); predictions.append(row)
                    stream.write(json.dumps(row, ensure_ascii=True) + '\n'); stream.flush()
                    if progress:
                        progress(f'Verified {len(predictions)}/{len(tasks)}: {row["id"]} — {row["status"]}')
    else:
        write_rows(out / 'predictions.jsonl', [])
    write_json(out / 'baseline_predictions.json', baseline_rows)
    # Close and hash predictions before parsing any expert label/rationale.
    run.update(status='predictions_closed', predictions_sha256=file_sha(out / 'predictions.jsonl'),
               baseline_predictions_sha256=file_sha(out / 'baseline_predictions.json'))
    write_json(out / 'run_manifest.json', run)
    if file_sha(source / 'gold.jsonl') != manifest['gold_sha256'] or file_sha(source / 'inputs.jsonl') != manifest['inputs_sha256']:
        raise ValueError('Benchmark changed during prediction; predictions saved but not scored.')
    gold = [g for g in read_rows(source / 'gold.jsonl') if g['id'] in {t['id'] for t in tasks}]
    _gold_map(tasks, gold)
    write_rows(out / 'gold.jsonl', gold)
    run.update(status='completed', selected_gold_sha256=file_sha(out / 'gold.jsonl'))
    write_json(out / 'run_manifest.json', run)
    metrics = _score_run(out)
    write_json(out / 'metrics.json', metrics)
    (out / 'report.html').write_text(report_html(tasks, gold, predictions, metrics), encoding='utf-8')
    return metrics


def _score_run(result):
    result = Path(result)
    run = json.loads((result / 'run_manifest.json').read_text())
    if run.get('status') != 'completed':
        raise ValueError('Only completed prediction runs can be rescored.')
    for name, key in [('inputs.jsonl', 'selected_inputs_sha256'), ('gold.jsonl', 'selected_gold_sha256'),
                      ('benchmark_manifest.json', 'benchmark_manifest_copy_sha256'),
                      ('contract.json', 'contract_sha256'), ('predictions.jsonl', 'predictions_sha256'),
                      ('baseline_predictions.json', 'baseline_predictions_sha256')]:
        # The first training smoke run predates this metadata-only copy hash.
        # Selected input/gold/contract/prediction/trace hashes remain mandatory.
        if key == 'benchmark_manifest_copy_sha256' and key not in run:
            continue
        if file_sha(result / name) != run[key]:
            raise ValueError('Saved result bytes changed: ' + name)
    tasks = read_rows(result / 'inputs.jsonl'); gold = read_rows(result / 'gold.jsonl')
    for task in tasks:
        validate_task(task)
    baselines = json.loads((result / 'baseline_predictions.json').read_text())
    metrics = {'format': 'biograph-steward.source-verifier-metrics.v1', 'status': 'completed',
               'run_manifest_sha256': file_sha(result / 'run_manifest.json'),
               'selection': run['selection'], 'model_requested': run['model_requested'],
               'verifier_kind': run['verifier_kind'], 'comparisons': {},
               'metric_basis': 'Provided claim/abstract pairs; complete alternative rationale sets, three-sentence cap; errors retained in denominators.',
               'scientific_improvement_established': False,
               'limitations': ['Development component evaluation, not an official SciFact leaderboard score.',
                               'Citation candidates supplied; no retrieval quality measured.',
                               'Claims and documents repeat; pairs are not independent experiments.',
                               'Public benchmark pretraining exposure cannot be excluded.',
                               'Source entailment is not clinical truth or improved graph prediction.']}
    for baseline in BASELINES:
        metrics['comparisons'][baseline] = score_predictions(tasks, gold, baselines[baseline])
    if run['mode'] == 'codex':
        predictions = read_rows(result / 'predictions.jsonl')
        usage = Counter(); usage_pairs = 0; latency = []; model_calls = 0
        for row in predictions:
            relative = row['trace_file']
            if not isinstance(relative, str) or not re.fullmatch(r'traces/[0-9]{5}\.json', relative):
                raise ValueError('Invalid trace file identity.')
            path = result / relative
            if path.is_symlink() or file_sha(path) != row['trace_sha256']:
                raise ValueError('Saved model trace bytes changed.')
            trace = json.loads(path.read_text())
            model_calls += trace.get('model_calls', 0)
            if trace.get('usage') is not None:
                usage.update(trace['usage']); usage_pairs += 1
            if isinstance(trace.get('latency_ms'), (float, int)):
                latency.append(trace['latency_ms'])
        metrics['comparisons']['verifier'] = score_predictions(tasks, gold, predictions)
        metrics['execution'] = {'requested_model_turns': model_calls, 'usage_reported_pairs': usage_pairs,
                                'usage_totals': dict(usage), 'cost': None,
                                'call_count_basis': 'Requested CLI turns; internal HTTP attempts are not exposed.',
                                'mean_turn_latency_ms': sum(latency) / len(latency) if latency else None,
                                'model_identity_basis': 'Requested model; CLI does not independently return served model identity.'}
    return metrics


def rescore_verification(result, output):
    metrics = _score_run(result)
    out = _new_output(output, result)
    write_json(out / 'metrics.json', metrics)
    tasks = read_rows(Path(result) / 'inputs.jsonl'); gold = read_rows(Path(result) / 'gold.jsonl')
    predictions = read_rows(Path(result) / 'predictions.jsonl')
    (out / 'report.html').write_text(report_html(tasks, gold, predictions, metrics), encoding='utf-8')
    return metrics


def report_html(tasks, gold, predictions, metrics):
    esc = lambda value: html.escape(str(value))
    pct = lambda value: '—' if value is None else f'{value:.1%}'
    rows = ''
    for name, scores in metrics['comparisons'].items():
        rows += '<tr><th>' + esc(name) + '</th>' + ''.join('<td>' + pct(scores[k]) + '</td>' for k in (
            'accuracy', 'macro_f1', 'support_precision', 'false_support_rate',
            'complete_rationale_coverage', 'label_and_complete_rationale_accuracy', 'error_rate')) + '</tr>'
    details = ''; pmap = {p['id']: p for p in predictions}; gmap = {g['id']: g for g in gold}
    for task in tasks:
        p = pmap.get(task['id']); g = gmap[task['id']]
        if p is None:
            continue
        verdict = p.get('verdict'); label = verdict['verdict'] if verdict else p['status']
        evidence = ''.join(f'<li>[{e["sentence_index"]}] {esc(e["quote"])}</li>' for e in verdict['evidence']) if verdict else ''
        document = ''.join(f'<li value="{s["index"]}">{esc(s["text"])}</li>' for s in task['document']['sentences'])
        explanation = esc(verdict['explanation']) if verdict else 'No validated model assessment.'
        context = ''
        if verdict:
            for key, label_text in [('reason_codes', 'Reasons'), ('context_matches', 'Context matches'),
                                    ('context_mismatches', 'Context mismatches'), ('missing_details', 'Missing details')]:
                if verdict[key]:
                    context += f'<p><strong>{label_text}:</strong> {esc("; ".join(verdict[key]))}</p>'
            if verdict['follow_up']:
                context += f'<p><strong>Follow-up:</strong> {esc(verdict["follow_up"])}</p>'
        details += (f'<details><summary>{esc(task["id"])} · {esc(label)} · expert: {esc(g["label"])}</summary>'
                    f'<h3>{esc(task["claim"])}</h3><p>{explanation}</p><ul>{evidence}</ul>{context}'
                    f'<p>Expert rationale alternatives: {esc(g["rationale_sets"])}</p>'
                    f'<h4>{esc(task["document"]["title"])}</h4><ol start="0">{document}</ol></details>')
    diagnostics = ''.join(f'<h3>{esc(name)}</h3><pre>{esc(json.dumps(s, indent=2))}</pre>' for name, s in metrics['comparisons'].items())
    limits = ''.join(f'<li>{esc(line)}</li>' for line in metrics['limitations'])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Source verifier evaluation</title><style>body{{font:16px system-ui;max-width:1200px;margin:36px auto;padding:0 20px;color:#183342;background:#f6f8fa}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #c8d4dc;padding:10px;text-align:left}}details{{background:white;margin:12px 0;padding:16px;border:1px solid #c8d4dc;border-radius:8px}}summary{{cursor:pointer;font-weight:600}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}li{{margin:8px 0}}.table{{overflow:auto}}@media(max-width:800px){{body{{font-size:14px;padding:0 12px;margin:24px auto}}table{{table-layout:fixed}}th,td{{font-size:12px;padding:6px;overflow-wrap:anywhere}}th:first-child{{width:22%}}}}</style>
<h1>Source verifier evaluation</h1><p>Machine judgments compared with SciFact expert annotations. No graph assertions or human reviews are changed.</p>
<p>Selected pairs: {len(tasks)} · Claims: {len({t['claim_id'] for t in tasks})} · Requested model: {esc(metrics['model_requested'])} · Provider: {esc(metrics['verifier_kind'])}</p>
<div class="table"><table><thead><tr><th>Workflow</th><th>Label accuracy</th><th>Macro F1</th><th>Support precision</th><th>False support</th><th>Complete rationale</th><th>Label + rationale accuracy</th><th>Errors</th></tr></thead><tbody>{rows}</tbody></table></div>
<p>False support: predicted SUPPORT among expert non-SUPPORT pairs. Complete rationale: at least one entire expert rationale among gold SUPPORT/CONTRADICT pairs, irrespective of predicted label. Label + rationale accuracy also requires the correct label; correct insufficient verdicts count without citations. Errors stay in denominators. Sentence scores require correct labels and whole rationale sets; recall uses the union of gold rationale sentences.</p>
<ul>{limits}</ul><p>Source: Wadden et al. (2020), <a href="https://aclanthology.org/2020.emnlp-main.609/">Fact or Fiction: Verifying Scientific Claims</a>. Claims/annotations CC BY 4.0; corpus abstracts ODC-By 1.0. See the preserved benchmark source manifest.</p>
<h2>Per-pair assessments</h2>{details}<details><summary>Confusion matrices and metric details</summary>{diagnostics}</details></html>'''
