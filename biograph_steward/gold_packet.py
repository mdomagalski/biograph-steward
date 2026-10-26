"""Reversible, source-bound handoff pending the organizer's scoring contract.

This is a project-local interface, not a KGX export or a scientific gold set.
Unsigned hashes detect changed bytes relative to a receipt; they authenticate
neither an upstream publisher nor biological correctness. Loading a packet is
offline and never substitutes a graph rebuilt by the current implementation.
"""
from datetime import datetime
import json
import math
from pathlib import Path, PurePosixPath
import re

from . import file_utils, refresh
from .client import canonical, digest, utcnow, write_json
from .file_utils import new_output, sha
from .refresh_workflow import _code_hashes, refresh_artifact_required


FORMAT = 'biograph-steward.gold-interface-packet.v1'
DECISION_FORMAT = 'biograph-steward.edge-decisions.v1'
DECISION_REPORT_FORMAT = 'biograph-steward.edge-dispositions.v1'
MANIFEST_FILE = 'packet_manifest.json'
_SOURCE_REQUIRED = ('snapshot.json', 'graph.json', 'run_manifest.json', 'review_events.json')
_SOURCE_OPTIONAL = ('civic_snapshot.json', 'source_licenses.json')
_INVENTORIES = {'nodes.jsonl': 'nodes', 'edges.jsonl': 'edges',
                'assertions.jsonl': 'assertions', 'context.jsonl': 'context_records',
                'quarantine.jsonl': 'quarantine'}
_SHA = re.compile(r'[0-9a-f]{64}')
_MANIFEST_KEYS = {'format', 'packet_id', 'created_at', 'graph_sha256', 'snapshot_sha256',
                  'civic_snapshot_sha256', 'database_version', 'data_kind', 'files',
                  'counts', 'content_sha256', 'input_files', 'implementation_sha256',
                  'license_material', 'official_scoring_performed',
                  'biological_validation_performed', 'scope_note'}
_SCOPE_NOTE = ('Every normalized evidence edge is inventoried; original context and '
               'quarantine remain separate. An omitted raw record is not a pruning verdict. '
               'Local review states and structural checks are not gold labels.')


def _object(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('Duplicate JSON key: ' + key)
        value[key] = item
    return value


def _constant(value):
    raise ValueError('Nonfinite JSON number: ' + value)


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        _constant(value)
    return number


def _decode(value):
    try:
        return json.loads(value, object_pairs_hook=_object, parse_constant=_constant, parse_float=_float)
    except (UnicodeError, TypeError, ValueError) as exc:
        raise ValueError('Invalid strict JSON input: ' + str(exc)) from exc


def _read(path):
    try:
        return _decode(Path(path).read_bytes())
    except OSError as exc:
        raise ValueError('Cannot read input: ' + Path(path).name) from exc


def _seal(value):
    value['content_sha256'] = digest(value)
    return value


def _sealed(value):
    return (isinstance(value, dict) and isinstance(value.get('content_sha256'), str)
            and value['content_sha256'] == digest({k: v for k, v in value.items()
                                                  if k != 'content_sha256'}))


def _hashmap(value):
    return (isinstance(value, dict) and bool(value)
            and all(isinstance(k, str) and bool(k) and isinstance(v, str)
                    and _SHA.fullmatch(v) for k, v in value.items()))


def _safe_relative(name):
    if not isinstance(name, str) or not name or '\\' in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and str(path) == name and not any(p in {'.', '..'} for p in path.parts)


def _source_material(run):
    run = Path(run)
    if run.is_symlink() or not run.is_dir():
        raise ValueError('Source must be an ordinary saved-run directory.')
    names = [*_SOURCE_REQUIRED, *(n for n in _SOURCE_OPTIONAL
                                if (run / n).exists() or (run / n).is_symlink())]
    if any((run / n).is_symlink() or not (run / n).is_file() for n in names):
        raise ValueError('Source inputs must be regular files; a required saved-run file is missing.')
    try:
        return {name: (run / name).read_bytes() for name in names}
    except OSError as exc:
        raise ValueError('Could not preserve source inputs.') from exc


def _material_hashes(material):
    import hashlib
    return {name: hashlib.sha256(value).hexdigest() for name, value in material.items()}


def _packet_id(manifest):
    return 'packet:' + digest({key: manifest[key] for key in
                              ('format', 'input_files', 'graph_sha256', 'implementation_sha256')})


def _graph_inventory(graph):
    if not isinstance(graph, dict):
        raise ValueError('Packet graph must be an object.')
    for field in _INVENTORIES.values():
        if not isinstance(graph.get(field), list) or any(not isinstance(r, dict) for r in graph[field]):
            raise ValueError('Packet graph inventory is malformed: ' + field)
    indexes = {}
    for field in ('nodes', 'edges', 'assertions', 'context_records'):
        ids = [row.get('id') for row in graph[field]]
        if any(not isinstance(uid, str) or not uid for uid in ids) or len(ids) != len(set(ids)):
            raise ValueError('Packet graph has missing or duplicate identifiers: ' + field)
        indexes[field] = set(ids)
    for edge in graph['edges']:
        if (any(not isinstance(edge.get(k), str) for k in ('subject', 'object', 'assertion_id'))
                or edge.get('subject') not in indexes['nodes'] or edge.get('object') not in indexes['nodes']
                or edge.get('assertion_id') not in indexes['assertions']):
            raise ValueError('Packet edge refers to missing nodes or assertions.')
    for assertion in graph['assertions']:
        if (any(not isinstance(assertion.get(k), str) for k in ('subject', 'object'))
                or assertion.get('subject') not in indexes['nodes'] or assertion.get('object') not in indexes['nodes']
                or not isinstance(assertion.get('evidence_edge_ids'), list)
                or any(not isinstance(uid, str) or uid not in indexes['edges'] for uid in assertion['evidence_edge_ids'])):
            raise ValueError('Packet assertion has incomplete graph references.')
    return {field: len(graph[field]) for field in _INVENTORIES.values()}


def _template(packet_id, graph):
    return {'format': DECISION_FORMAT, 'packet_id': packet_id,
            'method': 'unassessed', 'actor': 'unassigned',
            'decisions': [{'edge_id': edge['id'], 'decision': 'abstain',
                           'reason': 'Not assessed', 'confidence': None}
                          for edge in graph['edges']]}


def _jsonl(path, rows):
    Path(path).write_text(''.join(canonical(row) + '\n' for row in rows), encoding='utf-8')


def _source_bindings(run_manifest, snapshot, civic, graph):
    """Check metadata against its saved sources without rebuilding the graph.

    The refresh loader intentionally reports only selected compatibility fields;
    an evaluation handoff must additionally reject contradictory source labels.
    Presence matters even when the expected source value is explicitly null.
    """
    if any(key in graph or key in run_manifest for key in
           ('assay_evidence', 'assay_observations', 'assay_publication_sha256', 'assay_attachment_sha256')):
        raise ValueError('Assay attachments are outside this gold-interface packet version. Use the complete ordinary run export.')

    def require(actual, expected, label):
        if (not isinstance(actual, dict)
                or any(key not in actual or canonical(actual[key]) != canonical(value)
                       for key, value in expected.items())):
            raise ValueError(label + ' metadata disagrees with its source bindings.')

    try:
        require(graph, {'snapshot_sha256': snapshot['content_sha256'],
                        'snapshot_created_at': snapshot['created_at'],
                        'db_version': snapshot['db_version'], 'data_kind': snapshot['data_kind'],
                        'retrieval': snapshot['retrieval'], 'warnings': snapshot.get('warnings', [])},
                'Graph')
        require(run_manifest, {'snapshot_sha256': snapshot['content_sha256'],
                               'database_version': snapshot['db_version'], 'endpoint': snapshot['endpoint'],
                               'data_kind': snapshot['data_kind'], 'graph_format': graph['graph_format'],
                               'normalization_policy': graph['normalization']['policy'],
                               'query_settings': snapshot['query_settings'], 'retrieval': snapshot['retrieval'],
                               'schema_check': snapshot.get('schema_check'), 'warnings': snapshot.get('warnings', []),
                               'summary': graph['summary'], 'assertion_summary': graph['assertion_summary'],
                               'review_event_count': len(graph['review_events'])}, 'Run manifest')
        if civic is None:
            if 'civic' in run_manifest or 'civic' in graph or 'civic_snapshot_sha256' in graph:
                raise ValueError('CIViC metadata has no preserved source snapshot.')
        else:
            require(graph, {'civic_snapshot_sha256': civic['content_sha256']}, 'Graph CIViC')
            require(graph['civic'], {'source_snapshot_sha256': civic['content_sha256'],
                                    'created_at': civic['created_at'], 'source_version': civic['source_version'],
                                    'policy': civic['policy'], 'scope': civic['scope'],
                                    'coverage': civic['coverage'], 'source_license': civic['source_license']},
                    'Graph CIViC')
            require(run_manifest['civic'], {'snapshot_sha256': civic['content_sha256'],
                                           'created_at': civic['created_at'], 'source_version': civic['source_version'],
                                           'policy': civic['policy'], 'coverage': graph['civic']['coverage'],
                                           'mapping': graph['civic']['mapping']}, 'Run manifest CIViC')
    except (KeyError, TypeError) as exc:
        raise ValueError('Required source metadata binding is missing or malformed.') from exc


def export_packet(run, output):
    """Strictly replay one ordinary run, then preserve an immutable handoff."""
    run = Path(run)
    material = _source_material(run)
    if refresh_artifact_required(run):
        raise ValueError('Refresh and inherited-review runs require ancestry verification and are not supported here.')
    loaded = refresh._load(run)
    if loaded['policy_reasons']:
        raise ValueError('Source run failed replay checks: ' + ', '.join(loaded['policy_reasons']))
    graph = _decode(material['graph.json'])
    if canonical(graph) != canonical(loaded['graph']):
        raise ValueError('Saved graph does not exactly replay from its source and review history.')
    counts = _graph_inventory(graph)
    snapshot = _decode(material['snapshot.json'])
    civic = _decode(material['civic_snapshot.json']) if 'civic_snapshot.json' in material else None
    _source_bindings(_decode(material['run_manifest.json']), snapshot, civic, graph)
    licenses = snapshot.get('source_licenses', []) + ([civic['source_license']] if civic else [])
    if ('source_licenses.json' in material
            and _decode(material['source_licenses.json']) != licenses):
        raise ValueError('Saved source licenses disagree with the source snapshots.')
    if material != _source_material(run):
        raise ValueError('Source inputs changed during export preparation.')
    implementation = {**_code_hashes(), 'gold_packet': sha(__file__), 'file_utils': sha(file_utils.__file__)}
    manifest = {'format': FORMAT, 'created_at': utcnow(),
                'graph_sha256': digest(graph), 'snapshot_sha256': snapshot['content_sha256'],
                'civic_snapshot_sha256': civic['content_sha256'] if civic else None,
                'database_version': snapshot.get('db_version'), 'data_kind': graph['data_kind'],
                'input_files': _material_hashes(material), 'implementation_sha256': implementation,
                'counts': counts, 'license_material': 'copied_saved_run' if 'source_licenses.json' in material
                    else 'derived_from_preserved_snapshots',
                'official_scoring_performed': False, 'biological_validation_performed': False,
                'scope_note': _SCOPE_NOTE}
    manifest['packet_id'] = _packet_id(manifest)
    output = new_output(output, run)
    (output / 'source').mkdir()
    for name, value in material.items():
        (output / 'source' / name).write_bytes(value)
    if 'source_licenses.json' not in material:
        write_json(output / 'source/source_licenses.json', licenses)
    for name, field in _INVENTORIES.items():
        _jsonl(output / name, graph[field])
    write_json(output / 'decisions.template.json', _template(manifest['packet_id'], graph))
    if material != _source_material(run):
        raise ValueError('Source inputs changed while copying; incomplete packet was not sealed.')
    manifest['files'] = {p.relative_to(output).as_posix(): sha(p)
                         for p in sorted(output.rglob('*')) if p.is_file()}
    write_json(output / MANIFEST_FILE, _seal(manifest))
    load_packet(output)
    return manifest


def load_packet(folder):
    """Verify preserved bytes and identities offline; do not rebuild the graph."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir() or any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('Packet must contain regular files and no symlinks.')
    manifest = _read(folder / MANIFEST_FILE)
    if (not _sealed(manifest) or set(manifest) != _MANIFEST_KEYS or manifest.get('format') != FORMAT
            or not _hashmap(manifest.get('files')) or not _hashmap(manifest.get('input_files'))
            or not _hashmap(manifest.get('implementation_sha256'))
            or any(not _safe_relative(name) for name in manifest['files'])
            or not set(_SOURCE_REQUIRED) <= set(manifest['input_files']) <= set(_SOURCE_REQUIRED + _SOURCE_OPTIONAL)
            or manifest.get('packet_id') != _packet_id(manifest)
            or manifest.get('official_scoring_performed') is not False
            or manifest.get('biological_validation_performed') is not False
            or manifest.get('scope_note') != _SCOPE_NOTE):
        raise ValueError('Packet manifest, identity or policy is invalid.')
    try:
        if datetime.fromisoformat(manifest['created_at']).utcoffset() is None:
            raise ValueError('Timezone required.')
    except (TypeError, ValueError) as exc:
        raise ValueError('Packet timestamp must include a timezone.') from exc
    expected = {*_INVENTORIES, 'decisions.template.json',
                *('source/' + name for name in manifest['input_files']), 'source/source_licenses.json'}
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    if (set(manifest['files']) != expected or actual != expected | {MANIFEST_FILE}
            or any(not (folder / name).is_file() or sha(folder / name) != value
                   for name, value in manifest['files'].items())
            or any(manifest['files'].get('source/' + name) != value
                   for name, value in manifest['input_files'].items())):
        raise ValueError('Packet file inventory or saved bytes changed.')
    graph = _read(folder / 'source/graph.json')
    counts = _graph_inventory(graph)
    snapshot = _read(folder / 'source/snapshot.json')
    civic = (_read(folder / 'source/civic_snapshot.json')
             if 'civic_snapshot.json' in manifest['input_files'] else None)
    run_manifest = _read(folder / 'source/run_manifest.json')
    events = _read(folder / 'source/review_events.json')
    _source_bindings(run_manifest, snapshot, civic, graph)
    if (not _sealed(snapshot) or civic is not None and not _sealed(civic)
            or not isinstance(run_manifest, dict) or not isinstance(events, list)
            or any(isinstance(e, dict) and 'migration' in e for e in events)
            or run_manifest.get('run_mode') == 'refresh'
            or digest(graph) != manifest['graph_sha256']
            or manifest['snapshot_sha256'] != snapshot['content_sha256']
            or graph.get('snapshot_sha256') != manifest['snapshot_sha256']
            or graph.get('civic_snapshot_sha256') != manifest['civic_snapshot_sha256']
            or (civic['content_sha256'] if civic else None) != manifest['civic_snapshot_sha256']
            or graph.get('data_kind') != manifest['data_kind'] or snapshot.get('data_kind') != manifest['data_kind']
            or snapshot.get('db_version') != manifest['database_version']
            or graph.get('review_events') != events
            or run_manifest.get('snapshot_sha256') != manifest['snapshot_sha256']
            or run_manifest.get('graph_format') != graph.get('graph_format')
            or not isinstance(manifest['counts'], dict)
            or any(type(n) is not int for n in manifest['counts'].values())
            or counts != manifest['counts']):
        raise ValueError('Packet graph or source identities disagree with the manifest.')
    for name, field in _INVENTORIES.items():
        try:
            rows = [_decode(line) for line in (folder / name).read_bytes().splitlines()]
        except OSError as exc:
            raise ValueError('Cannot read packet inventory.') from exc
        if canonical(rows) != canonical(graph[field]):
            raise ValueError('Packet JSONL inventory disagrees with its graph: ' + name)
    licenses = snapshot.get('source_licenses', []) + ([civic['source_license']] if civic else [])
    origin = 'copied_saved_run' if 'source_licenses.json' in manifest['input_files'] else 'derived_from_preserved_snapshots'
    if (manifest['license_material'] != origin or _read(folder / 'source/source_licenses.json') != licenses
            or _read(folder / 'decisions.template.json') != _template(manifest['packet_id'], graph)):
        raise ValueError('Packet license record or default decisions changed.')
    return manifest, graph


def save_decisions(packet, decisions_path, output):
    """Validate complete explicit dispositions; retain every node and edge ID."""
    packet, decisions_path = Path(packet), Path(decisions_path)
    manifest, graph = load_packet(packet)
    if decisions_path.is_symlink() or not decisions_path.is_file():
        raise ValueError('Decision input must be a regular JSON file.')
    decision_bytes = decisions_path.read_bytes()
    value = _decode(decision_bytes)
    if (not isinstance(value, dict) or set(value) != {'format', 'packet_id', 'method', 'actor', 'decisions'}
            or value.get('format') != DECISION_FORMAT or value.get('packet_id') != manifest['packet_id']
            or any(not isinstance(value.get(k), str) or not value[k].strip() for k in ('method', 'actor'))
            or not isinstance(value.get('decisions'), list)):
        raise ValueError('Decision format, packet binding, method or actor is invalid.')
    ids, dispositions = set(), {'keep': [], 'prune': [], 'abstain': []}
    for row in value['decisions']:
        if (not isinstance(row, dict) or set(row) != {'edge_id', 'decision', 'reason', 'confidence'}
                or not isinstance(row.get('edge_id'), str) or row['edge_id'] in ids
                or not isinstance(row.get('decision'), str) or row.get('decision') not in dispositions
                or not isinstance(row.get('reason'), str) or not row['reason'].strip()
                or row.get('confidence') is not None):
            raise ValueError('Decision row is malformed, duplicated or supplies an unsupported confidence.')
        ids.add(row['edge_id'])
        dispositions[row['decision']].append(row['edge_id'])
        if row['decision'] != 'abstain' and (value['method'].strip().casefold() == 'unassessed'
                                            or value['actor'].strip().casefold() == 'unassigned'
                                            or row['reason'].strip().casefold() == 'not assessed'):
            raise ValueError('An actual disposition requires an explicit method, actor and reason.')
    if ids != {edge['id'] for edge in graph['edges']}:
        raise ValueError('Decision coverage must contain every packet edge exactly once, with no unknown edges.')
    output = new_output(output, packet, decisions_path)
    (output / 'decisions.json').write_bytes(decision_bytes)
    (output / 'packet_manifest.json').write_bytes((packet / MANIFEST_FILE).read_bytes())
    baseline = output / 'baseline_packet'
    baseline.mkdir()
    for name in [MANIFEST_FILE, *manifest['files']]:
        target = baseline / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((packet / name).read_bytes())
    copied_manifest, copied_graph = load_packet(baseline)
    if copied_manifest != manifest or copied_graph != graph:
        raise ValueError('Preserved baseline packet changed while copying; disposition report was not sealed.')
    _jsonl(output / 'nodes.jsonl', graph['nodes'])
    _jsonl(output / 'edge_dispositions.jsonl', value['decisions'])
    current, _ = load_packet(packet)
    if current != manifest or decisions_path.read_bytes() != decision_bytes:
        raise ValueError('Packet or decisions changed while saving; disposition report was not sealed.')
    report = {'format': DECISION_REPORT_FORMAT, 'created_at': utcnow(),
              'packet_id': manifest['packet_id'], 'packet_manifest_sha256': manifest['content_sha256'],
              'graph_sha256': manifest['graph_sha256'], 'method': value['method'], 'actor': value['actor'],
              'baseline_packet': 'baseline_packet',
              'counts': {key: len(rows) for key, rows in dispositions.items()},
              'node_ids': [row['id'] for row in graph['nodes']],
              'edge_ids': {key: sorted(rows) for key, rows in dispositions.items()},
              'source_mutations': 0, 'official_scoring_performed': False,
              'biological_validation_performed': False,
              'note': 'Local dispositions only. No source records or nodes were deleted. Confidence and scientific scoring require a declared reference contract.',
              'files': {p.relative_to(output).as_posix(): sha(p)
                        for p in sorted(output.rglob('*')) if p.is_file()}}
    write_json(output / 'report.json', _seal(report))
    return report
