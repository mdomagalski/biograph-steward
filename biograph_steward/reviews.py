"""Save review decisions as a new run without modifying source snapshots."""
import json
from pathlib import Path

from .assertions import new_review_event
from .client import digest, write_json
from .graph import build_graph, save_run


def read_assay(source: Path):
    from .assay_attachment import read_assay as read_attachment
    return read_attachment(source)


def read_civic(source: Path):
    path = Path(source) / 'civic_snapshot.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def _construction_trace(source, snapshot, graph, manifest):
    from .assay_attachment import _decode, _ordinary
    from .gold_packet import _construction_plan_binding
    path = Path(source) / 'construction_planner_trace.json'
    raw = _ordinary(path) if path.exists() or path.is_symlink() else None
    trace = _decode(raw) if raw is not None else None
    _construction_plan_binding(trace, snapshot, graph, manifest)
    return raw


def read_construction_plan(source: Path):
    """Validate optional recorded selection provenance before creating a new run."""
    from .gold_packet import _read
    source = Path(source)
    manifest_path = source / 'run_manifest.json'
    source_manifest = _read(manifest_path) if manifest_path.exists() else {}
    trace_path = source / 'construction_planner_trace.json'
    if (not trace_path.exists() and not trace_path.is_symlink()
            and 'construction_planner_trace_sha256' not in source_manifest):
        return None
    return _construction_trace(source, _read(source / 'snapshot.json'), _read(source / 'graph.json'),
                               source_manifest)


def preserve_construction_plan(source: Path, output: Path):
    """Carry an existing valid plan trace byte-for-byte into a new saved run."""
    from .gold_packet import _read, _decode, _construction_plan_binding
    source, output = Path(source), Path(output)
    raw = read_construction_plan(source)
    if raw is None:
        return
    snapshot, graph, manifest = (_read(output / name) for name in
                                 ('snapshot.json', 'graph.json', 'run_manifest.json'))
    trace = _decode(raw)
    _construction_plan_binding(trace, snapshot, graph)
    path = output / 'construction_planner_trace.json'
    if path.exists() or path.is_symlink():
        raise ValueError('A construction planner trace already exists in the output run.')
    path.write_bytes(raw)
    manifest['construction_planner_trace_sha256'] = digest(trace)
    write_json(output / 'run_manifest.json', manifest)


def read_run(source: Path) -> tuple[dict, list, dict]:
    source = Path(source)
    # A retained view has its own source packet and decision ledger. Never
    # silently rebuild it from the unfiltered snapshot as an ordinary run.
    qualified_marker = source / 'qualified_workspace.json'
    metadata_path = source / 'run_manifest.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.is_file() else {}
    if (qualified_marker.exists() or qualified_marker.is_symlink()
            or (source/'source_retained_package').exists() or (source/'source_retained_package').is_symlink()
            or metadata.get('run_mode') == 'qualified_workspace'):
        from .qualified_workspace import load_workspace
        return load_workspace(source)
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
        if saved.get('qualified_view'):
            raise ValueError('Qualified workspace publication marker is missing; the retained filter must not be discarded.')
        if (manifest.get('run_mode') == 'assay_attachment'
                or any(key in manifest or key in saved for key in assay_keys)):
            raise ValueError('Saved run is missing its recorded assay attachment.')
    else:
        saved_path = source / 'graph.json'
        saved = json.loads(saved_path.read_text(encoding='utf-8')) if saved_path.is_file() else {}
    extension_keys = ("evidence_extension", "evidence_extension_sha256")
    saved_extension_claim = (manifest.get('run_mode') == 'biological_extension'
        or any(k in manifest or k in saved for k in extension_keys)
        or any(e.get('extension_source_kind') for e in saved.get('edges', [])))
    del saved
    civic = read_civic(source)
    from .evidence_extension import read_extension, _ordinary, _decode
    extension = read_extension(source, snapshot, civic, assay)
    graph = build_graph(snapshot, events, civic, assay_attachment=assay, evidence_extension=extension)
    if extension is None:
        if saved_extension_claim:
            raise ValueError('Saved run is missing its biological source extension.')
    else:
        if any(manifest.get(k) != graph[k] for k in extension_keys):
            raise ValueError('Run manifest biological source bindings changed.')
        if _decode(_ordinary(source / 'graph.json')) != graph:
            raise ValueError('Saved biological graph does not replay from its complete sources.')
        if _decode(_ordinary(source / 'extension_observations.json')) != graph['extension_observations']:
            raise ValueError('Saved biological observation ledger changed.')
        licenses = snapshot.get('source_licenses', []) + ([civic['source_license']] if civic else [])
        licenses += ([assay['source_license']] if assay else []) + extension['source_licenses']
        if _decode(_ordinary(source / 'source_licenses.json')) != licenses:
            raise ValueError('Biological source licenses differ from their publications.')
    _construction_trace(source, snapshot, graph, manifest)
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
        if extension is not None:
            licenses += extension['source_licenses']
        if _decode(_ordinary(source / 'source_licenses.json')) != licenses:
            raise ValueError('Saved assay source licenses do not match the source attachment.')
    return snapshot, events, graph


def review_run(source: Path, output: Path, assertion_id: str, state: str,
               reviewer: str, reason: str) -> dict:
    source, output = Path(source).resolve(), Path(output).absolute()
    if source == output.resolve() or source in output.resolve().parents:
        raise ValueError("Save the reviewed run outside the original run directory.")
    snapshot, events, graph = read_run(source)
    if graph.get('qualified_view'):
        raise ValueError('This retained workspace is read-only. Review the preserved baseline source, then publish a new decision view.')
    event = new_review_event(graph, assertion_id, state, reviewer, reason)
    assay = read_assay(source)
    from .evidence_extension import read_extension
    extension = read_extension(source, snapshot)
    planning_bytes = read_construction_plan(source)
    stage = None
    if planning_bytes is not None:
        import tempfile
        if output.exists() or output.is_symlink():
            raise ValueError('Choose a new immutable reviewed output directory.')
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.planned-review-', dir=output.parent))
    destination = stage or output
    try:
        reviewed = save_run(snapshot, destination, run_mode='human_review', review_events=events + [event],
                            civic_snapshot=read_civic(source), assay_attachment=assay,
                            assay_source=source / 'assay_source' if assay is not None else None,
                            evidence_extension=extension,
                            extension_source=source / 'extension_sources' if extension is not None else None)
        preserve_construction_plan(source, destination)
        write_json(destination / 'review_parent.json', {'run_name': source.name,
                   'snapshot_sha256': graph['snapshot_sha256'], 'previous_event_count': len(events)})
        if stage is not None:
            if ((stage / 'construction_planner_trace.json').read_bytes() != planning_bytes
                    or read_run(stage)[2] != reviewed):
                raise ValueError('Planned review failed its unchanged source and provenance checks.')
            if output.exists() or output.is_symlink():
                raise ValueError('Reviewed output appeared during preparation; choose a new directory.')
            stage.rename(output)
        return reviewed
    finally:
        if stage is not None and stage.exists():
            import shutil
            shutil.rmtree(stage)
