"""Discover saved work without rebuilding graphs, fetching sources or running models."""
import json
from pathlib import Path
import re

from .questions import verify_answer
from .client import digest


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
    return {'runs': runs, 'example_url': example_url, 'withheld': withheld,
            'note': 'Saved-run metadata only. Opening a run checks its sources and answer basis. '
                    'Historical answers may require their recorded implementation.'}
