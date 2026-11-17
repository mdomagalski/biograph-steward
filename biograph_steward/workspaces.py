"""Discover saved work without rebuilding graphs, fetching sources or running models."""
import json
import hashlib
from collections import Counter
from pathlib import Path
import re

from .questions import verify_answer
from .client import digest


def qualification_summary(folder: Path, graph: dict) -> dict | None:
    """Read display reasons bound to an already-verified retained graph.

    Keep this outside the scientific graph/answer basis. Reuse the existing
    Gold report seal and ledger hash rather than introduce new policy labels.
    """
    qualified = graph.get('qualified_view')
    if not qualified:
        return None
    if not isinstance(qualified, dict):
        raise ValueError('Qualification display: invalid retained graph metadata.')
    package = Path(folder) / 'source_retained_package'
    report_path, ledger_path = package / 'report.json', package / 'edge_dispositions.jsonl'
    for path in (package, report_path, ledger_path):
        if path.is_symlink():
            raise ValueError('Qualification display: linked source is not allowed.')
    if report_path.stat().st_size > 20_000_000 or ledger_path.stat().st_size > 120_000_000:
        return {'available': False, 'interpretation': 'The full source decision ledger is available in the workspace export.'}
    report = json.loads(report_path.read_bytes())
    if (not isinstance(report, dict) or not isinstance(report.get('files'), dict)
            or not isinstance(report.get('counts'), dict)):
        raise ValueError('Qualification display: invalid report metadata.')
    pin = qualified['disposition_report_content_sha256']
    if report.get('content_sha256') != pin or digest({k: v for k, v in report.items() if k != 'content_sha256'}) != pin:
        raise ValueError('Qualification display: report does not match the loaded graph.')
    raw = ledger_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != report['files']['edge_dispositions.jsonl']:
        raise ValueError('Qualification display: decision ledger bytes changed.')
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    counts = Counter(row['decision'] for row in rows)
    if (set(counts) - {'keep', 'prune', 'abstain'} or
            any(counts[key] != report['counts'].get(key, 0) for key in ('keep', 'prune', 'abstain')) or
            len(rows) != qualified['baseline_evidence_edges'] or
            len(rows) - counts['prune'] != qualified['retained_evidence_edges']):
        raise ValueError('Qualification display: counts differ from the verified retained graph.')
    reasons = Counter(row['reason'] for row in rows if row['decision'] == 'prune')
    return {'available': True, 'baseline_records': len(rows),
            'retained_records': qualified['retained_evidence_edges'], 'excluded_records': counts['prune'],
            'abstained_records': counts['abstain'],
            'reason_groups': [{'decision': 'prune', 'reason': reason, 'records': count}
                              for reason, count in sorted(reasons.items())],
            'interpretation': 'These are the recorded source-qualification reasons. Exclusion does not itself establish false biology. Undecided records remain retained.',
            'disposition_report_content_sha256': pin,
            'decision_ledger_sha256': report['files']['edge_dispositions.jsonl']}


def reviewer_entry(runs: list[dict], example_url: str | None = None, *, native_question_ids=()) -> dict | None:
    """Describe a real saved entry point, never promote the offline fixture.

    This is a catalogue preference, not source or biological validation. The
    existing run/question routes still verify sources and sealed answer basis.
    """
    real = [run for run in runs if run['data_kind'] == 'live_pharos']
    native = next(((run, question) for run in real for question in run['questions']
                   if question['template'] == 'native_string_physical.v1'
                   and question['view'] == 'candidates'), None)
    if native:
        primary, question = native
        example_url = question['url']
    else:
        primary = next((run for run in real if example_url and
                        (example_url == run['url'] or
                         any(q['url'] == example_url for q in run['questions']))), None)
    if primary is None:
        return None
    examples = [{'label': 'Explore the cited evidence', 'url': example_url,
                 'description': 'Open a real saved question, its graph and the records behind its answer.'}]
    snapshot = primary.get('snapshot_sha256')
    same_snapshot = isinstance(snapshot, str) and re.fullmatch(r'[a-f0-9]{64}', snapshot)
    qualified = next(((run, question) for run in real if same_snapshot and run.get('qualified_view')
                      and run.get('snapshot_sha256') == snapshot
                      for question in run['questions']
                      if question['template'] == 'qualified_pathway_source_context.v1'
                      and question['view'] == 'candidates'
                      and question['question_id'] in native_question_ids), None)
    if qualified and qualified[1]['url'] != example_url:
        examples.append({'label': 'Review applied graph qualifications', 'url': qualified[1]['url'],
                         'description': 'Inspect the retained Pharos graph. Its export preserves exclusions, decisions and the original input.'})
    return {'example_url': example_url, 'display_title': 'Explore real Pharos evidence',
            'data_kind': primary['data_kind'], 'guided_examples': examples,
            'snapshot_sha256': snapshot,
            'assessment_id': None,
            'note': 'Real saved source data. Opening a question verifies its source basis. '
                    'The shared reviewer site uses saved data without model calls or new retrieval.'}



def registered_source_agent_entry(root, runs, entry):
    """An operator-pinned recorded example, separate from source workspaces.

    Registration is a presentation preference. It cannot promote an injected
    test, a failed attempt, a different cohort, or an unverified source result.
    """
    registration = Path(root) / 'reviewer_agent_entry.json'
    if not registration.exists() and not registration.is_symlink():
        return entry
    try:
        if registration.is_symlink() or not registration.is_file() or registration.stat().st_size > 10_000:
            raise ValueError('Reviewer agent registration must be an ordinary bounded file.')
        value = json.loads(registration.read_text(encoding='utf-8'))
        keys = {'format', 'source_run', 'question_id', 'job_id', 'job_manifest_sha256'}
        if (not isinstance(value, dict) or set(value) != keys
                or value['format'] != 'biograph-steward.source-agent-reviewer-entry.v1'
                or any(not isinstance(value[key], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value[key])
                       for key in ('source_run', 'question_id'))
                or not isinstance(value['job_id'], str) or not re.fullmatch(r'source_agent_[A-Za-z0-9_-]{1,67}', value['job_id'])
                or not isinstance(value['job_manifest_sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['job_manifest_sha256'])):
            raise ValueError('Invalid reviewer agent registration.')
        source = next((run for run in runs if run['run_id'] == value['source_run'] and run['data_kind'] == 'live_pharos'), None)
        question = next((q for q in (source or {}).get('questions', [])
                         if q['question_id'] == value['question_id'] and q['template'] == 'native_string_physical.v1'
                         and q['view'] == 'candidates'), None)
        if (entry is None or source is None or question is None
                or question['url'] != entry['example_url']
                or source.get('snapshot_sha256') != entry.get('snapshot_sha256')):
            raise ValueError('Registered agent example differs from the current source cohort and cited question.')
        folder = Path(root) / value['job_id']
        manifest = folder / 'manifest.json'
        if folder.is_symlink() or manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 20_000:
            raise ValueError('Registered agent manifest is unavailable.')
        if hashlib.sha256(manifest.read_bytes()).hexdigest() != value['job_manifest_sha256']:
            raise ValueError('Registered agent manifest bytes changed.')
        from .source_agent_jobs import read_source_agent_job
        job = read_source_agent_job(folder, root)
        result, plan = job['result'], job['result'].get('plan') or {}
        question_file = Path(root) / value['question_id'] / 'question.json'
        if question_file.is_symlink() or not question_file.is_file() or question_file.stat().st_size > 16_000_000:
            raise ValueError('Registered manual source question is unavailable.')
        manual = json.loads(question_file.read_text(encoding='utf-8'))
        verify_answer(manual)
        if (job['actual_model_run'] is not True or job['status'] != 'completed' or job['source_run'] != source['run_id']
                or result.get('data_kind') != 'live_pharos' or plan.get('tool') != 'native_physical'
                or plan.get('arguments', {}).get('view') != 'candidates'
                or manual.get('source_run') != source['run_id']
                or manual.get('graph_basis_sha256') != result['source_bindings']['graph_basis_sha256']
                or manual.get('plan', {}).get('protein', {}).get('id') != plan.get('arguments', {}).get('protein_id')):
            raise ValueError('Registered agent is not a completed actual-model run for this exact source question.')
        return {**entry, 'example_url': question['url'] + '&agent_job=' + value['job_id'] + '&view=data',
                'display_title': 'Follow a recorded source-agent workflow', 'agent_job_id': value['job_id'],
                'agent_manifest_sha256': value['job_manifest_sha256'],
                'note': 'Recorded model-directed query and source inspection. Replaying verifies saved sources without new inference; proposals are not applied.'}
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        if entry is None:
            return None
        return {**entry, 'agent_entry_unavailable': True,
                'note': 'The featured agent record could not be verified. The guided source reader remains available; no other model run was selected.'}

def saved_workspaces(root: Path) -> dict:
    root = Path(root).resolve()
    folders = [p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
               and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', p.name)]
    runs = []
    withheld = 0
    for folder in folders:
        manifest_file = folder / 'run_manifest.json'
        if not manifest_file.exists():
            continue
        try:
            if any((folder / name).is_symlink() or not (folder / name).is_file()
                   for name in ('run_manifest.json', 'snapshot.json', 'graph.json')):
                raise ValueError('Incomplete saved workspace')
            manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
            # Comparisons have separate archive access and strict replay checks.
            if manifest.get('run_mode') == 'refresh' or any((folder / name).exists()
                    for name in ('refresh_receipt.json', 'refresh_comparison.json', 'refresh_inputs')):
                continue
            if (manifest.get('data_kind') not in ('live_pharos', 'synthetic_demo')
                    or not str(manifest.get('graph_format', '')).startswith('biograph-steward.evidence-graph.')
                    or not isinstance(manifest.get('created_at'), str)):
                raise ValueError('Unsupported workspace metadata')
            if manifest.get('run_mode') == 'construction':
                receipt_file = folder / 'construction_receipt.json'
                if receipt_file.is_symlink():
                    raise ValueError('Invalid construction receipt')
                receipt = json.loads(receipt_file.read_text(encoding='utf-8'))
                if (receipt.get('status') != 'published'
                        or receipt.get('snapshot_sha256') != manifest.get('snapshot_sha256')
                        or receipt.get('content_sha256') != digest({k: v for k, v in receipt.items()
                                                                    if k != 'content_sha256'})):
                    raise ValueError('Incomplete construction publication')
            runs.append({'run_id': folder.name, 'created_at': manifest['created_at'],
                         'data_kind': manifest['data_kind'], 'has_civic': bool(manifest.get('civic')),
                         'snapshot_sha256': manifest.get('snapshot_sha256'),
                         'qualified_view': manifest.get('run_mode') == 'qualified_workspace',
                         'url': '/?run=' + folder.name, 'questions': []})
        except (ValueError, TypeError, AttributeError, OSError):
            withheld += 1
    by_id = {r['run_id']: r for r in runs}
    native_questions = set()
    for folder in folders:
        path = folder / 'question.json'
        if not path.exists():
            continue
        try:
            if path.is_symlink():
                raise ValueError('Question must be a regular file')
            answer = json.loads(path.read_text(encoding='utf-8'))
            verify_answer(answer)
            source = by_id.get(answer.get('source_run'))
            if source is None:
                continue
            question = {'question_id': folder.name, 'question': answer['question'],
                'view': answer['plan']['view'], 'template': answer['template'],
                'url': source['url'] + '&question=' + folder.name}
            source['questions'].append(question)
            if (question['template'] == 'qualified_pathway_source_context.v1'
                    and question['view'] in ('accepted', 'candidates')
                    and answer['plan'].get('source_support') == 'native_supported'):
                native_questions.add(folder.name)
        except (ValueError, TypeError, AttributeError, KeyError, OSError):
            withheld += 1
    runs.sort(key=lambda r: (r['created_at'], r['run_id']), reverse=True)
    for run in runs:
        run['questions'].sort(key=lambda q: q['question_id'], reverse=True)
    real = [r for r in runs if r['data_kind'] == 'live_pharos']
    example_url = None
    # Prefer the current retained-source workflow when it has a saved native
    # question. This is catalogue selection only; opening still replays sources.
    for run in real:
        native = [q for q in run['questions'] if q['question_id'] in native_questions]
        if run['qualified_view'] and native:
            question = next((q for q in native if q['view'] == 'candidates'), native[0])
            example_url = question['url']
            break
    if example_url is None:
        example = next((r for r in real if r['has_civic'] and r['questions']),
                       next((r for r in real if r['has_civic']), real[0] if real else None))
        if example:
            question = next((q for q in example['questions'] if q['view'] == 'candidates'), None)
            example_url = question['url'] if question else example['url']
    entry = reviewer_entry(runs, example_url, native_question_ids=native_questions)
    entry = registered_source_agent_entry(root, runs, entry)
    if entry:
        example_url = entry['example_url']
    return {'runs': runs, 'example_url': example_url, 'reviewer_entry': entry, 'withheld': withheld,
            'note': 'Saved-run metadata only. Opening a run checks its sources and answer basis. '
                    'Historical answers may require their recorded implementation.'}
