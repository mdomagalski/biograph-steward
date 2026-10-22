"""Read-only discovery of recorded comparison reports, separate from replay."""
from hashlib import sha256
from html import escape
from pathlib import Path
import re

from .refresh_workflow import (COMPARISON_FILE, RECEIPT_FILE, REPORT_FILE, _read,
                               refresh_runtime_changes, verify_refresh_files)

SAFE_PART = re.compile(r'[A-Za-z0-9_-]{1,80}')
MAX_DEPTH = 3  # run; run/returned; run/returned/comparison


def archive_id(relative_path: str) -> str:
    return sha256(relative_path.encode('utf-8')).hexdigest()


def comparison_folders(root: Path):
    """Bounded traversal beneath runs, never following directory symlinks."""
    root = Path(root).resolve()

    def walk(parent, depth):
        if depth >= MAX_DEPTH:
            return
        for folder in sorted(parent.iterdir(), key=lambda item: item.name, reverse=True):
            if folder.is_symlink() or not folder.is_dir() or not SAFE_PART.fullmatch(folder.name):
                continue
            if any((folder / name).exists() or (folder / name).is_symlink()
                   for name in (RECEIPT_FILE, COMPARISON_FILE, REPORT_FILE)):
                yield folder
                # A comparison owns its preserved parents, which are not archives.
                continue
            yield from walk(folder, depth + 1)

    yield from walk(root, 0)


def find_archive(root: Path, identifier: str) -> Path | None:
    for folder in comparison_folders(root):
        if archive_id(folder.relative_to(root).as_posix()) == identifier:
            return folder
    return None


def archive_metadata(root: Path, folder: Path) -> dict:
    relative = folder.relative_to(root).as_posix()
    identifier = archive_id(relative)
    item = {'archive_id': identifier, 'name': relative,
            'integrity': 'failed', 'current_replay': 'not_performed'}
    try:
        receipt = verify_refresh_files(folder)
        changes = refresh_runtime_changes(receipt)
        comparison = _read(folder / COMPARISON_FILE)
        item.update(integrity='passed', created_at=receipt['created_at'],
                    status_counts=comparison.get('summary', {}).get('status_counts', {}),
                    changed_implementation_modules=changes, runtime_compatible=not changes,
                    report_url='/api/refresh-archive/' + identifier + '/',
                    message=('Saved files match recorded hashes. ' +
                             ('Matching implementation required for replay.' if changes else
                              'Current replay has not been performed.')))
        if folder.parent == root:
            item['run_id'] = folder.name
            if not changes:
                item['replay_report_url'] = '/api/refresh/' + folder.name + '/'
    except (ValueError, TypeError, KeyError, OSError):
        item['message'] = 'Saved packet failed integrity checks; archive withheld.'
    return item


def list_archives(root: Path) -> dict:
    root = Path(root).resolve()
    items = [archive_metadata(root, folder) for folder in comparison_folders(root)]
    return {'comparisons': sorted(items, key=lambda row: row.get('created_at', ''), reverse=True),
            'note': 'Read-only archives; file hashes do not establish scientific accuracy or authenticate the source. '
                    'Current replay is separate and still requires the recorded implementation.',
            'discovery_depth': MAX_DEPTH}


def archived_report(folder: Path, receipt: dict) -> str:
    """Add a response-only notice; never edit or reseal the recorded report."""
    changes = refresh_runtime_changes(receipt)
    message = ('Current implementation differs (' + ', '.join(changes) + '). Use the recorded '
               'implementation for deterministic replay.' if changes else
               'Current implementation hashes match. This archive view does not run deterministic replay.')
    banner = ('<aside role="note" style="border:2px solid #976b00;padding:1rem;margin:1rem 0;background:#fff8df">'
              '<strong>Read-only comparison archive</strong><p>Saved files match their recorded hashes. '
              + escape(message) + '</p><p>This is the historical report, not a newly verified current graph. '
              'Hashes do not authenticate the source or establish scientific accuracy.</p>'
              '<a href="/#refreshPanel">Return to saved comparison history</a></aside>')
    html = (folder / REPORT_FILE).read_text(encoding='utf-8')
    return re.sub(r'(?=<h1(?:\s|>))', lambda _: banner, html, count=1) if re.search(r'<h1(?:\s|>)', html) else banner + html
