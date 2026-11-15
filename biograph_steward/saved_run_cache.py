"""Byte-bound reuse of ordinary biological-source replay for HTTP requests only.

The unchanged ordinary reader remains authoritative. This adapts the retained
workspace loader's single-entry, locked fingerprint/copy policy; it does not
cache validation by path or mtime, stage sources or alter saved publications.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import threading

from . import qualified_workspace, reviews
from .file_utils import sha

_LOCK = threading.Lock()
_KEY = None


def _eligible(folder):
    if not folder.is_dir() or folder.is_symlink():
        return False
    if any((folder / name).exists() or (folder / name).is_symlink()
           for name in ('qualified_workspace.json', 'source_retained_package')):
        return False
    manifest = folder / 'run_manifest.json'
    if manifest.is_symlink() or not manifest.is_file():
        return False
    try:
        value = json.loads(manifest.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return False
    return (isinstance(value, dict) and value.get('run_mode') == 'biological_extension'
            and (folder / 'evidence_extension.json').is_file()
            and not (folder / 'evidence_extension.json').is_symlink()
            and (folder / 'extension_sources').is_dir()
            and not (folder / 'extension_sources').is_symlink())


def _reader_code_pins():
    # Include every core Python helper, including dynamic source adapters. The
    # older qualified helper allowlist alone predates the new native profiles.
    package = Path(__file__).resolve().parent
    pins = []
    for path in sorted(package.rglob('*.py')):
        if not path.is_file() or path.is_symlink():
            raise ValueError('Saved source replay: ordinary reader helper files are required.')
        pins.append((path.relative_to(package).as_posix(), sha(path)))
    pins.extend((name, id(value)) for name, value in (
        ('ordinary_reader', reviews.read_run), ('graph_builder', reviews.build_graph),
        ('read_assay', reviews.read_assay), ('read_civic', reviews.read_civic)))
    return tuple(pins)


def _fingerprint(folder):
    # Reuse the existing complete file/directory/source-code fingerprint. Add
    # all core helpers and the actual ordinary-reader bindings to that key.
    return qualified_workspace._workspace_fingerprint(folder), _reader_code_pins()


def _clear_locked():
    global _KEY
    _cached_full_read.cache_clear()
    _KEY = None


@lru_cache(maxsize=1)
def _cached_full_read(folder, fingerprint):
    return reviews.read_run(Path(folder))


def read_run(source):
    """Return a private copy only after unchanged complete sources revalidate.

    Qualified workspaces retain their existing loader. Other ordinary modes
    retain uncached behavior. A single outer lock prevents duplicate cold
    replays; functools' cache alone does not guarantee one in-flight call.
    """
    global _KEY
    folder = Path(source)
    if not _eligible(folder):
        try:
            return reviews.read_run(folder)
        except Exception:
            with _LOCK:
                _clear_locked()
            raise
    with _LOCK:
        try:
            if not _eligible(folder):
                return reviews.read_run(folder)
            folder = folder.resolve()
            before = _fingerprint(folder)
            if not _eligible(folder):
                raise ValueError('Saved source replay: workspace mode changed during the request.')
            key = (str(folder), before)
            if _KEY != key:
                # Release the old parsed workspace before allocating another.
                _clear_locked()
            result = deepcopy(_cached_full_read(str(folder), before))
            if _fingerprint(folder) != before or not _eligible(folder):
                raise ValueError('Saved source replay: source bytes, inventory or reader code changed during the request.')
            _KEY = key
            return result
        except Exception:
            _clear_locked()
            raise
