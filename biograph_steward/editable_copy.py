"""Read-only delivery of operator-prepared editable workspace archives.

Reuse the saved-context registration pattern: the operator names a bounded
set of artifacts and pins their bytes. This does not export a directory on a
browser request, grant writes, rebuild a source graph or certify source terms.
The package preparation step must verify complete offline replay separately.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat


FORMAT = 'biograph-steward.editable-workspace-downloads.v1'
INDEX = 'index.json'
_ID = re.compile(r'[A-Za-z0-9_-]{1,80}')
_SHA = re.compile(r'[0-9a-f]{64}')
_FILENAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,179}\.zip')
_KEYS = {'run_id', 'filename', 'bytes', 'sha256', 'source_manifest_sha256',
         'source_graph_sha256', 'snapshot_sha256', 'question_id',
         'question_sha256', 'label'}
_UNEDITABLE = ('qualified_workspace.json', 'source_retained_package',
               'refresh_receipt.json', 'refresh_comparison.json', 'refresh_inputs')


class CopyNotRegistered(LookupError):
    """The operator has not enabled a prepared copy for this workspace."""


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def _ordinary(path):
    path = Path(path)
    _need(path.is_file() and not path.is_symlink(), 'Editable copy requires ordinary files.')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        _need(stat.S_ISREG(before.st_mode), 'Editable copy requires ordinary files.')
        yield stream, before


def _hash(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(block)
    return value.hexdigest()


def _pinned_file(path, expected, *, limit=None, decode=False):
    with _ordinary(path) as (stream, before):
        _need(limit is None or before.st_size <= limit, 'Editable copy metadata is too large.')
        if decode:
            raw = stream.read()
            pin = hashlib.sha256(raw).hexdigest()
        else:
            raw, pin = None, _hash(stream)
        _need(pin == expected and _identity(os.fstat(stream.fileno())) == _identity(before),
              'Editable copy source bytes changed.')
    return json.loads(raw) if decode else None


def _registration(directory, runs_dir, run_id):
    _need(isinstance(run_id, str) and _ID.fullmatch(run_id), 'Invalid editable workspace identifier.')
    if directory is None:
        return None
    root, sources = Path(directory), Path(runs_dir).resolve()
    _need(root.is_dir() and not root.is_symlink(), 'Editable copy directory is unavailable.')
    root = root.resolve()
    index = root / INDEX
    with _ordinary(index) as (stream, before):
        _need(before.st_size <= 100_000, 'Editable copy index is too large.')
        value = json.load(stream)
        _need(_identity(os.fstat(stream.fileno())) == _identity(before), 'Editable copy index changed.')
    _need(isinstance(value, dict) and set(value) == {'format', 'downloads'}
          and value['format'] == FORMAT and isinstance(value['downloads'], list)
          and len(value['downloads']) <= 25, 'Invalid editable copy index.')
    selected, seen = None, set()
    for row in value['downloads']:
        _need(isinstance(row, dict) and set(row) == _KEYS, 'Invalid editable copy registration.')
        identifier = row['run_id']
        _need(isinstance(identifier, str) and _ID.fullmatch(identifier) and identifier not in seen,
              'Invalid or duplicate editable copy identifier.')
        seen.add(identifier)
        _need(isinstance(row['filename'], str) and _FILENAME.fullmatch(row['filename'])
              and type(row['bytes']) is int and row['bytes'] > 0
              and isinstance(row['label'], str) and 1 <= len(row['label']) <= 200
              and not any(ord(c) < 32 for c in row['label']), 'Invalid editable copy artifact metadata.')
        _need(all(isinstance(row[key], str) and _SHA.fullmatch(row[key]) for key in
                  ('sha256', 'source_manifest_sha256', 'source_graph_sha256', 'snapshot_sha256')),
              'Invalid editable copy fingerprint.')
        question = row['question_id']
        _need((question is None and row['question_sha256'] is None)
              or (isinstance(question, str) and _ID.fullmatch(question)
                  and isinstance(row['question_sha256'], str) and _SHA.fullmatch(row['question_sha256'])),
              'Invalid editable copy question binding.')
        if identifier == run_id:
            selected = row
    if selected is None:
        return None
    folder = sources / run_id
    _need(folder.is_dir() and not folder.is_symlink() and folder.resolve().parent == sources,
          'Editable copy source workspace is unavailable.')
    _need(not any((folder / name).exists() or (folder / name).is_symlink() for name in _UNEDITABLE),
          'An applied or historical view is not an editable source workspace.')
    manifest = _pinned_file(folder / 'run_manifest.json', selected['source_manifest_sha256'],
                            limit=2_000_000, decode=True)
    _need(isinstance(manifest, dict) and manifest.get('snapshot_sha256') == selected['snapshot_sha256']
          and manifest.get('run_mode') in {'build', 'biological_extension', 'human_review',
                                          'construction', 'assay_attachment'},
          'Editable copy source identity differs.')
    _pinned_file(folder / 'graph.json', selected['source_graph_sha256'])
    if selected['question_id'] is not None:
        question_folder = sources / selected['question_id']
        _need(question_folder.is_dir() and not question_folder.is_symlink()
              and question_folder.resolve().parent == sources, 'Editable copy question is unavailable.')
        question = _pinned_file(question_folder / 'question.json', selected['question_sha256'],
                                limit=16_000_000, decode=True)
        _need(isinstance(question, dict) and question.get('source_run') == run_id,
              'Editable copy question belongs to another workspace.')
    return root, selected


def _metadata(row):
    identifier = row['run_id']
    local = '?run=' + identifier
    if row['question_id'] is not None:
        local += '&question=' + row['question_id']
    return {'available': True, 'run_id': identifier, 'label': row['label'],
            'filename': row['filename'], 'bytes': row['bytes'], 'sha256': row['sha256'],
            'source_graph_sha256': row['source_graph_sha256'], 'snapshot_sha256': row['snapshot_sha256'],
            'download_url': '/api/editable-copy/' + identifier + '/download',
            'launch_command': 'python3 START_EDITABLE_LOCAL.py',
            'local_entry_query': local + '&view=ask',
            'review_scope': 'Record evidence decisions and reasons in a new local run; the original workspace stays unchanged.',
            'requires': {'python': '3.10+', 'model': False, 'AWS': False}}


@contextmanager
def open_editable_copy(directory, runs_dir, run_id):
    """Yield metadata and a verified, rewound archive without allocating its bytes."""
    registration = _registration(directory, runs_dir, run_id)
    if registration is None:
        raise CopyNotRegistered('A complete editable copy is not registered for this workspace.')
    root, row = registration
    archive = root / row['filename']
    _need(archive.resolve().parent == root, 'Editable copy archive escaped its directory.')
    with _ordinary(archive) as (stream, before):
        _need(before.st_size == row['bytes'] and stream.read(4) == b'PK\x03\x04',
              'Editable copy archive size or format differs.')
        stream.seek(0)
        _need(_hash(stream) == row['sha256']
              and _identity(os.fstat(stream.fileno())) == _identity(before),
              'Editable copy archive bytes changed.')
        stream.seek(0)
        yield _metadata(row), stream


def describe_editable_copy(directory, runs_dir, run_id):
    try:
        with open_editable_copy(directory, runs_dir, run_id) as (metadata, _):
            return metadata
    except CopyNotRegistered:
        return {'available': False, 'run_id': run_id,
                'reason': 'A complete editable copy is not registered for this workspace.'}
