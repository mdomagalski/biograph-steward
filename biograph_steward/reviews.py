"""Save review decisions as a new run without modifying source snapshots."""
import json
from pathlib import Path

from .assertions import new_review_event
from .client import write_json
from .graph import build_graph, save_run


def read_assay(source: Path):
    from .assay_attachment import read_assay as read_attachment
    return read_attachment(source)


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
    assay = read_assay(source)
    assay_keys = ('assay_evidence', 'assay_publication_sha256', 'assay_attachment_sha256')
    if assay is None:
        saved_path = source / 'graph.json'
        saved = json.loads(saved_path.read_text(encoding='utf-8')) if saved_path.is_file() else {}
        if (manifest.get('run_mode') == 'assay_attachment'
                or any(key in manifest or key in saved for key in assay_keys)):
            raise ValueError('Saved run is missing its recorded assay attachment.')
    graph = build_graph(snapshot, events, read_civic(source), assay_attachment=assay)
    if assay is not None:
        if any(manifest.get(key) != graph[key] for key in assay_keys):
            raise ValueError('Run manifest assay source bindings changed.')
        saved = json.loads((source / 'graph.json').read_text(encoding='utf-8'))
        if saved != graph:
            raise ValueError('Saved assay graph does not replay from its complete sources and reviews.')
        from .assay_attachment import _decode, _ordinary
        if _decode(_ordinary(source / 'assay_observations.json')) != graph['assay_observations']:
            raise ValueError('Saved assay observation ledger does not match the preserved source projection.')
        licenses = snapshot.get('source_licenses', []) + [assay['source_license']]
        if _decode(_ordinary(source / 'source_licenses.json')) != licenses:
            raise ValueError('Saved assay source licenses do not match the source attachment.')
    return snapshot, events, graph


def review_run(source: Path, output: Path, assertion_id: str, state: str,
               reviewer: str, reason: str) -> dict:
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents:
        raise ValueError("Save the reviewed run outside the original run directory.")
    snapshot, events, graph = read_run(source)
    event = new_review_event(graph, assertion_id, state, reviewer, reason)
    assay = read_assay(source)
    reviewed = save_run(snapshot, output, run_mode='human_review', review_events=events + [event],
                        civic_snapshot=read_civic(source), assay_attachment=assay,
                        assay_source=source / 'assay_source' if assay is not None else None)
    write_json(output / 'review_parent.json', {'run_name': source.name,
               'snapshot_sha256': graph['snapshot_sha256'], 'previous_event_count': len(events)})
    return reviewed
