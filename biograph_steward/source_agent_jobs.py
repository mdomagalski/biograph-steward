"""Immutable, source-verified records of the current-source agent.

These records are separate from graph workspaces and review ledgers. Reading a
record validates the current saved source and replays only deterministic tools;
it never creates a model client or changes a graph or review decision.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from .client import canonical, digest

FORMAT = 'biograph.source-agent-job.v1'
MAX_RESULT_BYTES = 16_000_000
_ID = re.compile(r'source_agent_[A-Za-z0-9_-]{1,67}')
_RUN = re.compile(r'[A-Za-z0-9_-]{1,80}')
_PROGRESS = re.compile(r'\.source_agent_progress_[A-Za-z0-9_-]{1,55}')


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _source(result, runs_dir):
    identifier = result.get('source_run') if isinstance(result, dict) else None
    _need(isinstance(identifier, str) and _RUN.fullmatch(identifier), 'Invalid agent source workspace.')
    root = Path(runs_dir).resolve()
    folder = root / identifier
    _need(folder.is_dir() and not folder.is_symlink() and folder.resolve().parent == root,
          'The recorded agent source workspace is unavailable.')
    from .saved_run_cache import read_run
    from .source_agent import verify_source_agent_result
    from .webapp import verify_saved_refresh
    verify_saved_refresh(folder)
    graph = read_run(folder)[2]
    verify_source_agent_result(result, graph=graph, source_run=identifier, source_folder=folder)
    return folder


def _header(result):
    trace = result.get('trace', {})
    kind = trace.get('provider_kind', 'unknown')
    count = trace.get('model_calls')
    real = kind in {'live_nim', 'live_model'} and type(count) is int and count > 0
    calls = trace.get('tool_calls', [])
    return {'source_run': result['source_run'], 'question': result.get('question', ''),
            'status': result.get('status', 'unknown'), 'provider_kind': kind,
            'actual_model_run': real, 'model_calls': trace.get('model_calls', 0),
            'tool_calls': len(calls) if isinstance(calls, list) else calls}


def new_source_agent_progress(runs_dir):
    """Record bounded operator events immediately, outside published jobs."""
    identifier = '.source_agent_progress_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
    folder = Path(runs_dir).resolve() / identifier
    folder.mkdir()
    count = 0

    def record(event):
        nonlocal count
        _need(isinstance(event, dict), 'Agent progress events must be JSON objects.')
        raw = (canonical(event) + '\n').encode('utf-8')
        _need(count < 16 and len(raw) <= MAX_RESULT_BYTES, 'Agent progress event budget exceeded.')
        count += 1
        with (folder / ('event_%04d.json' % count)).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())

    return identifier, record


def save_source_agent_job(result, runs_dir, *, job_id=None, progress_id=None):
    """Publish a new record; an existing job is never replaced.

    The manifest is the publication marker and is renamed into place last. An
    interrupted write remains an unavailable record, rather than looking valid.
    """
    _source(result, runs_dir)
    created = datetime.now(timezone.utc).isoformat()
    job_id = job_id or 'source_agent_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
    _need(isinstance(job_id, str) and _ID.fullmatch(job_id), 'Invalid agent job identifier.')
    raw = (canonical(result) + '\n').encode('utf-8')
    _need(len(raw) <= MAX_RESULT_BYTES, 'Agent job exceeds its saved-result byte limit.')
    root = Path(runs_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    folder = root / job_id
    folder.mkdir()  # Exclusive reservation: no overwrite, including empty jobs.
    manifest = {'format': FORMAT, 'job_id': job_id, 'created_at': created,
                'result_sha256': hashlib.sha256(raw).hexdigest(), **_header(result)}
    if progress_id is not None:
        _need(isinstance(progress_id, str) and _PROGRESS.fullmatch(progress_id), 'Invalid agent progress identifier.')
        progress = root / progress_id
        _need(progress.is_dir() and not progress.is_symlink(), 'Agent progress directory is unavailable.')
        manifest['progress_id'] = progress_id
        manifest['progress_note'] = 'Immediate operator events are separate from the sealed published-result files.'
    manifest['content_sha256'] = digest(manifest)
    for name, data in (('result.json', raw), ('manifest.json', (canonical(manifest) + '\n').encode('utf-8'))):
        temp = folder / ('.' + name + '.tmp')
        with temp.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temp.rename(folder / name)
    return {**manifest, 'result': result}


def read_source_agent_job(folder, runs_dir):
    """Verify a published record against its exact current source, without LLMs."""
    root, folder = Path(runs_dir).resolve(), Path(folder)
    _need(_ID.fullmatch(folder.name) and folder.is_dir() and not folder.is_symlink()
          and folder.resolve().parent == root, 'Saved agent job not found.')
    _need({p.name for p in folder.iterdir()} == {'result.json', 'manifest.json'},
          'Agent job is incomplete or contains unexpected files.')
    for name, limit in (('result.json', MAX_RESULT_BYTES), ('manifest.json', 20_000)):
        item = folder / name
        _need(item.is_file() and not item.is_symlink() and item.stat().st_size <= limit,
              'Agent job files must be ordinary bounded files.')
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    _need(isinstance(manifest, dict) and manifest.get('format') == FORMAT
          and manifest.get('job_id') == folder.name,
          'Invalid agent job manifest.')
    seal = manifest.get('content_sha256')
    _need(seal == digest({k: v for k, v in manifest.items() if k != 'content_sha256'}),
          'Agent job manifest seal does not match.')
    raw = (folder / 'result.json').read_bytes()
    _need(hashlib.sha256(raw).hexdigest() == manifest.get('result_sha256'),
          'Agent job result differs from its saved manifest.')
    result = json.loads(raw)
    _source(result, root)
    _need(all(manifest.get(k) == v for k, v in _header(result).items()),
          'Agent job metadata differs from its recorded result.')
    return {**manifest, 'result': result}


def list_source_agent_jobs(runs_dir, *, source_run=None):
    """List bounded verified records; invalid records stay visible as unavailable."""
    if source_run is not None:
        _need(isinstance(source_run, str) and _RUN.fullmatch(source_run), 'Invalid agent source workspace.')
    root = Path(runs_dir).resolve()
    jobs, unavailable = [], []
    for folder in sorted(root.glob('source_agent_*'), reverse=True)[:100]:
        if not folder.is_dir() and not folder.is_symlink():
            continue
        try:
            if source_run is not None:
                # This bounded header is an exclusion hint, never a verified
                # result. Avoid replaying another workspace just to filter it
                # out, while malformed records remain visibly unavailable.
                _need(_ID.fullmatch(folder.name) and folder.is_dir() and not folder.is_symlink()
                      and folder.resolve().parent == root, 'Saved agent job not found.')
                metadata_file = folder / 'manifest.json'
                _need(metadata_file.is_file() and not metadata_file.is_symlink()
                      and metadata_file.stat().st_size <= 20_000,
                      'Agent job manifest must be an ordinary bounded file.')
                metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
                _need(isinstance(metadata, dict) and metadata.get('format') == FORMAT
                      and metadata.get('job_id') == folder.name,
                      'Invalid agent job manifest.')
                claimed_source = metadata.get('source_run')
                _need(isinstance(claimed_source, str) and _RUN.fullmatch(claimed_source),
                      'Invalid agent source workspace.')
                _need(metadata.get('content_sha256') == digest({k: v for k, v in metadata.items()
                                                              if k != 'content_sha256'}),
                      'Agent job manifest seal does not match.')
                if claimed_source != source_run:
                    continue
            job = read_source_agent_job(folder, root)
            if source_run is None or job['source_run'] == source_run:
                jobs.append({k: v for k, v in job.items() if k != 'result'})
        except (ValueError, TypeError, KeyError, OSError) as exc:
            unavailable.append({'job_id': folder.name, 'reason': str(exc)})
    return {'jobs': jobs, 'unavailable_jobs': unavailable}
