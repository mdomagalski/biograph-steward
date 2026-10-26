"""Save review decisions as a new run without modifying source snapshots."""
import json
from pathlib import Path

from .assertions import new_review_event
from .client import write_json
from .graph import build_graph, save_run


def read_civic(source: Path):
    path = Path(source) / 'civic_snapshot.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def read_run(source: Path) -> tuple[dict, list, dict]:
    source = Path(source)
    snapshot = json.loads((source / 'snapshot.json').read_text(encoding='utf-8'))
    manifest_path = source / 'run_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    if (manifest.get('run_mode') == 'construction' or (source / 'construction_receipt.json').exists()
            or (snapshot.get('construction') and not manifest)):
        from .construction import verify_construction_run
        verify_construction_run(source)
    events_file = source / 'review_events.json'
    events = json.loads(events_file.read_text(encoding='utf-8')) if events_file.exists() else []
    return snapshot, events, build_graph(snapshot, events, read_civic(source))


def review_run(source: Path, output: Path, assertion_id: str, state: str,
               reviewer: str, reason: str) -> dict:
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents:
        raise ValueError("Save the reviewed run outside the original run directory.")
    snapshot, events, graph = read_run(source)
    event = new_review_event(graph, assertion_id, state, reviewer, reason)
    reviewed = save_run(snapshot, output, run_mode='human_review', review_events=events + [event], civic_snapshot=read_civic(source))
    write_json(output / 'review_parent.json', {'run_name': source.name,
               'snapshot_sha256': graph['snapshot_sha256'], 'previous_event_count': len(events)})
    return reviewed
