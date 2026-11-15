"""Reversible, source-bound handoff pending the organizer's scoring contract.

This is a project-local interface, not a KGX export or a scientific gold set.
Unsigned hashes detect changed bytes relative to a receipt; they authenticate
neither an upstream publisher nor biological correctness. Loading a packet is
offline and never substitutes a graph rebuilt by the current implementation.
"""
from copy import deepcopy
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
DECISION_REPORT_FORMAT = 'biograph-steward.edge-dispositions.v2'
MANIFEST_FILE = 'packet_manifest.json'
_SOURCE_REQUIRED = ('snapshot.json', 'graph.json', 'run_manifest.json', 'review_events.json')
_SOURCE_OPTIONAL = ('civic_snapshot.json', 'source_licenses.json', 'construction_planner_trace.json')
_ASSAY_REQUIRED = ('assay_attachment.json', 'assay_observations.json')
_ASSAY_KEYS = ('assay_evidence', 'assay_observations', 'assay_publication_sha256', 'assay_attachment_sha256')
_EXTENSION_REQUIRED = ('evidence_extension.json', 'extension_observations.json')
_EXTENSION_KEYS = ('evidence_extension', 'evidence_extension_sha256', 'extension_observations')
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
        material = {name: (run / name).read_bytes() for name in names}
        if any((run / name).exists() or (run / name).is_symlink()
               for name in (*_ASSAY_REQUIRED, 'assay_source')):
            from .assay_attachment import read_assay, source_material, _ordinary
            attachment = read_assay(run)
            if attachment is None:
                raise ValueError('Assay observation ledger has no preserved attachment.')
            material.update({name: _ordinary(run / name) for name in _ASSAY_REQUIRED})
            files = source_material(_decode(material['snapshot.json']), attachment, run / 'assay_source')
            material.update({'assay_source/' + name: raw for name, raw in files.items()})
        if any((run / name).exists() or (run / name).is_symlink()
               for name in (*_EXTENSION_REQUIRED, 'extension_sources')):
            from .evidence_extension import read_extension, source_material as extension_material
            from .assay_attachment import _ordinary
            material.update({name: _ordinary(run / name) for name in _EXTENSION_REQUIRED})
            snapshot = _decode(material['snapshot.json'])
            civic = _decode(material['civic_snapshot.json']) if 'civic_snapshot.json' in material else None
            assay = _decode(material['assay_attachment.json']) if 'assay_attachment.json' in material else None
            recorded = _decode(material['evidence_extension.json'])
            baseline = _extension_baseline_view(_decode(material['graph.json']), recorded)
            extension = read_extension(run, snapshot=snapshot, civic=civic, assay=assay,
                                       baseline_graph=baseline)
            if extension is None:
                raise ValueError('Extension observation ledger has no preserved source extension.')
            files = extension_material(snapshot, extension, run / 'extension_sources', civic=civic,
                                       assay=assay, baseline_graph=baseline)
            material.update({'extension_sources/' + name: raw for name, raw in files.items()})
        return material
    except OSError as exc:
        raise ValueError('Could not preserve source inputs.') from exc


def _input_names_valid(names):
    names = set(names)
    allowed = set(_SOURCE_REQUIRED + _SOURCE_OPTIONAL)
    if not set(_SOURCE_REQUIRED) <= names or any(not _safe_relative(name) for name in names):
        return False
    assay = set(_ASSAY_REQUIRED)
    nested = {name for name in names if name.startswith('assay_source/')}
    if names & assay or nested:
        if not assay <= names or 'assay_source/publication.json' not in nested:
            return False
        allowed.update(assay | nested)
    extension = set(_EXTENSION_REQUIRED)
    nested = {name for name in names if name.startswith('extension_sources/')}
    if names & extension or nested:
        # Adapter-specific inventories and the nonempty source list are checked
        # against the sealed extension during the inner publication replay.
        if not extension <= names or not any(
                re.fullmatch(r'extension_sources/(string|string_physical|mapit|signor|bioplex|goa)/publication\.json', name)
                for name in nested):
            return False
        allowed.update(extension | nested)
    return names <= allowed


def _inventories(graph):
    return {**_INVENTORIES, **({'assay_observations.jsonl': 'assay_observations'}
                             if 'assay_observations' in graph else {}),
            **({'extension_observations.jsonl': 'extension_observations'}
               if 'extension_observations' in graph else {})}


def _construction_plan_binding(trace, snapshot, graph, run_manifest=None):
    marker = (run_manifest or {}).get('construction_planner_trace_sha256')
    if trace is None:
        if marker is not None or 'construction_planner_trace_sha256' in (run_manifest or {}):
            raise ValueError('Construction planner trace is missing from its saved run.')
        return
    from .construction_planning import verify_construction_plan_trace
    request = verify_construction_plan_trace(trace)
    construction = snapshot.get('construction')
    if (request is None or not isinstance(construction, dict)
            or request != construction.get('request') or graph.get('construction') != construction):
        raise ValueError('Construction planner trace does not match the preserved source request.')
    if 'construction_planner_trace_sha256' in (run_manifest or {}) and marker != digest(trace):
        raise ValueError('Construction planner trace does not match its saved run manifest.')


def _material_hashes(material):
    import hashlib
    return {name: hashlib.sha256(value).hexdigest() for name, value in material.items()}


def _packet_id(manifest):
    return 'packet:' + digest({key: manifest[key] for key in
                              ('format', 'input_files', 'graph_sha256', 'implementation_sha256')})


def _graph_inventory(graph):
    if not isinstance(graph, dict):
        raise ValueError('Packet graph must be an object.')
    for field in _inventories(graph).values():
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
    return {field: len(graph[field]) for field in _inventories(graph).values()}


def _template(packet_id, graph):
    return {'format': DECISION_FORMAT, 'packet_id': packet_id,
            'method': 'unassessed', 'actor': 'unassigned',
            'decisions': [{'edge_id': edge['id'], 'decision': 'abstain',
                           'reason': 'Not assessed', 'confidence': None}
                          for edge in graph['edges']]}


def _jsonl(path, rows):
    Path(path).write_text(''.join(canonical(row) + '\n' for row in rows), encoding='utf-8')


def _source_bindings(run_manifest, snapshot, civic, graph, assay=None, extension=None):
    """Check metadata against its saved sources without rebuilding the graph.

    The refresh loader intentionally reports only selected compatibility fields;
    an evaluation handoff must additionally reject contradictory source labels.
    Presence matters even when the expected source value is explicitly null.
    """
    if assay is None and (any(key in graph or key in run_manifest for key in _ASSAY_KEYS)
            or run_manifest.get('run_mode') == 'assay_attachment'
            or any(e.get('record_kind') == 'assay_observation' for e in graph['edges'])):
        raise ValueError('Assay graph is missing its complete preserved attachment.')
    if extension is None and (any(key in graph or key in run_manifest for key in _EXTENSION_KEYS)
            or any(e.get('record_kind') == 'tissue_proximity_observation'
                   or e.get('extension_source_kind') is not None for e in graph['edges'])):
        raise ValueError('Graph extension is missing its complete preserved sources.')

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
        if assay is not None:
            binding = {'assay_evidence': assay['summary'],
                       'assay_publication_sha256': assay['publication_sha256'],
                       'assay_attachment_sha256': assay['content_sha256']}
            require(graph, {**binding, 'assay_observations': assay['observations']}, 'Graph assay')
            require(run_manifest, binding, 'Run manifest assay')
            actual = [{k: v for k, v in edge.items() if k != 'assertion_id'}
                      for edge in graph['edges'] if edge.get('record_kind') == 'assay_observation']
            expected = [{k: v for k, v in edge.items() if k != 'assertion_id'} for edge in assay['edges']]
            if sorted(actual, key=lambda e: e['id']) != sorted(expected, key=lambda e: e['id']):
                raise ValueError('Graph assay edges disagree with their preserved observation projection.')
            # Verify qualified identities and review bindings without reconstructing
            # the source graph or replacing any saved record with current output.
            from .assertions import build_assertions
            checked = deepcopy(graph)
            assertions = build_assertions(checked, checked['review_events'])
            if assertions != graph['assertions'] or checked['edges'] != graph['edges']:
                raise ValueError('Graph assay assertion identities or review histories disagree.')
        if extension is not None:
            _extension_bindings(run_manifest, snapshot, graph, extension, require)
    except (KeyError, TypeError) as exc:
        raise ValueError('Required source metadata binding is missing or malformed.') from exc


def _extension_baseline_view(graph, extension):
    """Remove declared additions for adapter replay, without rebuilding Pharos.

    Adapters consume the saved node/edge/target inventories only. Their full
    raw-source replay then checks the declared additions, and _source_bindings
    rejects missing, extra or altered extension records in the final graph.
    """
    try:
        if not _sealed(extension):
            raise ValueError('Graph extension content binding changed.')
        node_ids = {r['id'] for s in extension['sources'].values() for r in s['prepared']['nodes']}
        edge_ids = {r['id'] for s in extension['sources'].values() for r in s['prepared']['edges']}
        return {**graph, 'nodes': [r for r in graph['nodes'] if r['id'] not in node_ids],
                'edges': [r for r in graph['edges'] if r['id'] not in edge_ids]}
    except (KeyError, TypeError) as exc:
        raise ValueError('Graph extension has no complete baseline projection.') from exc


def _extension_bindings(run_manifest, snapshot, graph, extension, require):
    """Bind the complete source-specific additions without normalizing Pharos."""
    if (not _sealed(extension) or extension.get('snapshot_sha256') != snapshot['content_sha256']
            or not isinstance(extension.get('sources'), dict) or not extension['sources']):
        raise ValueError('Graph extension source or content binding changed.')
    binding = {'evidence_extension': extension['summary'],
               'evidence_extension_sha256': extension['content_sha256']}
    require(graph, binding, 'Graph extension')
    require(run_manifest, binding, 'Run manifest extension')
    expected_nodes, expected_edges, observations = {}, {}, []
    for source, record in sorted(extension['sources'].items()):
        if source not in {'string', 'string_physical', 'mapit', 'signor', 'bioplex', 'goa'}:
            raise ValueError('Unsupported graph extension source kind.')
        prepared = record['prepared']
        for node in prepared['nodes']:
            if node['id'] in expected_nodes:
                raise ValueError('Graph extensions repeat a new node identity.')
            expected_nodes[node['id']] = node
        for edge in prepared['edges']:
            if edge['id'] in expected_edges:
                raise ValueError('Graph extensions repeat an evidence edge identity.')
            expected_edges[edge['id']] = {k: v for k, v in edge.items() if k != 'assertion_id'}
        observations.extend(prepared['observations'])
    require(graph, {'extension_observations': observations}, 'Graph extension observation ledger')
    nodes = {node['id']: node for node in graph['nodes']}
    if any(nodes.get(uid) != node for uid, node in expected_nodes.items()):
        raise ValueError('Graph extension nodes disagree with their preserved source projection.')
    actual_edges = {edge['id']: {k: v for k, v in edge.items() if k != 'assertion_id'}
                    for edge in graph['edges'] if edge['id'] in expected_edges
                    or edge.get('extension_source_kind') is not None
                    or edge.get('record_kind') == 'tissue_proximity_observation'}
    if actual_edges != expected_edges:
        raise ValueError('Graph extension edges disagree with their preserved source projection.')
    # Qualifier identities and review revisions are also part of the handoff.
    from .assertions import build_assertions
    checked = deepcopy(graph)
    assertions = build_assertions(checked, checked['review_events'])
    if assertions != graph['assertions'] or checked['edges'] != graph['edges']:
        raise ValueError('Graph extension assertion identities or review histories disagree.')


def export_packet(run, output):
    """Strictly replay one ordinary run, then preserve an immutable handoff."""
    run = Path(run)
    material = _source_material(run)
    if refresh_artifact_required(run):
        raise ValueError('Refresh and inherited-review runs require ancestry verification and are not supported here.')
    assay, extension = None, None
    if 'assay_attachment.json' in material or 'evidence_extension.json' in material:
        from .assay_attachment import read_assay
        from .reviews import read_run
        assay = read_assay(run)
        if 'evidence_extension.json' in material:
            from .evidence_extension import read_extension
            extension = read_extension(run)
        snapshot, _, replay = read_run(run)
        refresh._metadata_shapes(snapshot)
        source_manifest = _decode(material['run_manifest.json'])
        reasons = ([] if isinstance(source_manifest.get('starter_version'), str)
                   and source_manifest['starter_version'] else ['saved_manifest_starter_version_unknown'])
        loaded = {'graph': replay, 'policy_reasons': reasons}
    else:
        loaded = refresh._load(run)
    if loaded['policy_reasons']:
        raise ValueError('Source run failed replay checks: ' + ', '.join(loaded['policy_reasons']))
    graph = _decode(material['graph.json'])
    if canonical(graph) != canonical(loaded['graph']):
        raise ValueError('Saved graph does not exactly replay from its source and review history.')
    # The replay passed exact equality. Its graph, snapshot and indexes need not
    # coexist with the next source and packet copies.
    del loaded
    counts = _graph_inventory(graph)
    snapshot = _decode(material['snapshot.json'])
    civic = _decode(material['civic_snapshot.json']) if 'civic_snapshot.json' in material else None
    _construction_plan_binding(_decode(material['construction_planner_trace.json'])
                               if 'construction_planner_trace.json' in material else None, snapshot, graph,
                               _decode(material['run_manifest.json']))
    _source_bindings(_decode(material['run_manifest.json']), snapshot, civic, graph, assay, extension)
    licenses = (snapshot.get('source_licenses', []) + ([civic['source_license']] if civic else [])
                + ([assay['source_license']] if assay else [])
                + (extension['source_licenses'] if extension else []))
    if ('source_licenses.json' in material
            and _decode(material['source_licenses.json']) != licenses):
        raise ValueError('Saved source licenses disagree with the source snapshots.')
    if material != _source_material(run):
        raise ValueError('Source inputs changed during export preparation.')
    implementation = {**_code_hashes(), 'gold_packet': sha(__file__), 'file_utils': sha(file_utils.__file__)}
    if assay is not None:
        from . import assay_attachment, lambourne_evidence
        from . import intact_evidence, intact_publication
        projection = (intact_evidence if assay["summary"].get("source_kind") == "intact_mitab27"
                      else lambourne_evidence)
        implementation.update({'assay_attachment': sha(assay_attachment.__file__),
                               'assay_observation_projection': sha(projection.__file__)})
        if projection is intact_evidence:
            implementation['intact_publication'] = sha(intact_publication.__file__)
            from . import intact_final_publication
            if _decode(material['assay_source/publication.json']).get('format') in {
                    intact_final_publication.FORMAT, intact_final_publication.CONSUMED_FORMAT}:
                implementation['intact_final_publication'] = sha(intact_final_publication.__file__)
    if extension is not None:
        from . import evidence_extension
        implementation['evidence_extension'] = sha(evidence_extension.__file__)
        for source in extension['sources']:
            module = evidence_extension._adapter(source)
            implementation[source + '_source_projection'] = sha(module.__file__)
    if 'construction_planner_trace.json' in material:
        from . import construction_planning
        implementation['construction_planning'] = sha(construction_planning.__file__)
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
        target = output / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
    if 'source_licenses.json' not in material:
        write_json(output / 'source/source_licenses.json', licenses)
    for name, field in _inventories(graph).items():
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
            or not _input_names_valid(manifest['input_files'])
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
    inventory_names = {*_INVENTORIES, *({'assay_observations.jsonl'}
                       if 'assay_attachment.json' in manifest['input_files'] else set()),
                       *({'extension_observations.jsonl'}
                       if 'evidence_extension.json' in manifest['input_files'] else set())}
    expected = {*inventory_names, 'decisions.template.json',
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
    _construction_plan_binding(_read(folder / 'source/construction_planner_trace.json')
                               if 'construction_planner_trace.json' in manifest['input_files'] else None,
                               snapshot, graph, run_manifest)
    assay = None
    if 'assay_attachment.json' in manifest['input_files']:
        from .assay_attachment import read_assay
        assay = read_assay(folder / 'source')
        if _read(folder / 'source/assay_observations.json') != assay['observations']:
            raise ValueError('Preserved assay observation ledger disagrees with its source projection.')
    extension = None
    if 'evidence_extension.json' in manifest['input_files']:
        from .evidence_extension import read_extension
        recorded = _read(folder / 'source/evidence_extension.json')
        extension = read_extension(folder / 'source', snapshot=snapshot, civic=civic, assay=assay,
                                   baseline_graph=_extension_baseline_view(graph, recorded))
        if _read(folder / 'source/extension_observations.json') != graph.get('extension_observations'):
            raise ValueError('Preserved extension observation ledger disagrees with its graph.')
    _source_bindings(run_manifest, snapshot, civic, graph, assay, extension)
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
    licenses = (snapshot.get('source_licenses', []) + ([civic['source_license']] if civic else [])
                + ([assay['source_license']] if assay else [])
                + (extension['source_licenses'] if extension else []))
    origin = 'copied_saved_run' if 'source_licenses.json' in manifest['input_files'] else 'derived_from_preserved_snapshots'
    # All full-source bindings above are checked before inventory replay. Keep
    # only the small license projection while loading potentially large JSONL.
    del snapshot, civic, assay, extension, run_manifest, events
    for name, field in _inventories(graph).items():
        try:
            rows = [_decode(line) for line in (folder / name).read_bytes().splitlines()]
        except OSError as exc:
            raise ValueError('Cannot read packet inventory.') from exc
        if canonical(rows) != canonical(graph[field]):
            raise ValueError('Packet JSONL inventory disagrees with its graph: ' + name)
        del rows
    if (manifest['license_material'] != origin or _read(folder / 'source/source_licenses.json') != licenses
            or _read(folder / 'decisions.template.json') != _template(manifest['packet_id'], graph)):
        raise ValueError('Packet license record or default decisions changed.')
    return manifest, graph


RETAINED_FORMAT = 'biograph-steward.retained-evidence-graph.v1'
RETENTION_POLICY = 'remove_explicit_prune_keep_abstain_preserve_all_nodes.v1'
_REVIEW_POLICY = ('Unchanged assertions retain their recorded review state. Changed evidence '
                  'support creates a candidate revision; original reviews remain in baseline_packet.')
_DECISION_NOTE = ('Local explicit dispositions only. The retained graph removes explicit prune edges; '
                  'abstentions and all original nodes remain. The complete retrieved baseline is preserved. '
                  'Confidence and scientific scoring require a declared reference contract.')


def _decision_value(value, manifest, graph):
    """Validate one complete ledger without interpreting source/review statuses."""
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
    return dispositions


def _retained_graph(manifest, graph, value):
    """Materialize a local view using the existing qualified assertion builder.

    This is not a new saved-run snapshot or a biological classifier. Source
    metadata/counters stay in the preserved baseline, avoiding stale counts in
    the derived view. Qualified source edge/node records are copied unchanged.
    """
    from collections import Counter
    from copy import deepcopy
    from .assertions import build_assertions, assertion_summary

    dispositions = _decision_value(value, manifest, graph)
    by_id = {row['id']: row for row in graph['edges']}
    # Verify the saved evidence grouping before deriving a different support set.
    # This reuses assertion construction only; it never normalizes/retrieves data.
    try:
        source_copy = deepcopy(graph)
        rebuilt = build_assertions(source_copy, graph['review_events'])
        if rebuilt != graph['assertions'] or source_copy['edges'] != graph['edges']:
            raise ValueError('Baseline assertion/support mapping does not reproduce from its evidence and reviews.')
        del source_copy, rebuilt
        for record in graph['context_records']:
            ids = record['normalized_evidence_edge_ids']
            if (not isinstance(ids, list) or len(ids) != len(set(ids))
                    or any(eid not in by_id for eid in ids)
                    or record['assertion_ids'] != sorted({by_id[eid]['assertion_id'] for eid in ids})
                    or any(record['id'] not in by_id[eid].get('context_record_ids', []) for eid in ids)):
                raise ValueError('Baseline context support mapping is inconsistent.')
        context_by_id = {row['id']: row for row in graph['context_records']}
        for edge in graph['edges']:
            if any(cid not in context_by_id or edge['id'] not in context_by_id[cid]['normalized_evidence_edge_ids']
                   for cid in edge.get('context_record_ids', [])):
                raise ValueError('Baseline evidence/context mapping is inconsistent.')
    except (KeyError, TypeError) as exc:
        raise ValueError('Baseline assertion or context support mapping is malformed.') from exc

    pruned = set(dispositions['prune'])
    working = deepcopy(graph)
    working['edges'] = [row for row in working['edges'] if row['id'] not in pruned]
    assertions = build_assertions(working)
    baseline_assertions = {row['id']: row for row in graph['assertions']}
    retained_assertions = {row['id']: row for row in assertions}
    changes = []
    for original in graph['assertions']:
        current = retained_assertions.get(original['id'])
        retained_ids = current['evidence_edge_ids'] if current else []
        changed = retained_ids != original['evidence_edge_ids']
        changes.append({'assertion_id': original['id'],
                        'status': 'removed' if current is None else 'evidence_changed' if changed else 'unchanged',
                        'baseline_revision': original['revision'],
                        'retained_revision': current['revision'] if current else None,
                        'baseline_lifecycle_state': original['lifecycle_state'],
                        'retained_lifecycle_state': (current['lifecycle_state'] if changed else original['lifecycle_state'])
                            if current else None,
                        'baseline_evidence_edge_ids': original['evidence_edge_ids'],
                        'retained_evidence_edge_ids': retained_ids,
                        'pruned_evidence_edge_ids': sorted(set(original['evidence_edge_ids']) & pruned),
                        'review_history_carried': bool(current and not changed),
                        'baseline_review_event_count': len(original['review_history'])})
    assertions = [deepcopy(baseline_assertions[row['id']])
                  if row['evidence_edge_ids'] == baseline_assertions[row['id']]['evidence_edge_ids'] else row
                  for row in assertions]
    edges = working['edges']
    # Assertion construction mutates the copied edges only. The other copied
    # baseline inventories are no longer used; contexts are projected below.
    del working, baseline_assertions, retained_assertions
    retained_ids = {row['id'] for row in edges}
    contexts = deepcopy(graph['context_records'])
    for record in contexts:
        baseline_ids = list(record['normalized_evidence_edge_ids'])
        record['normalized_evidence_edge_ids'] = [eid for eid in baseline_ids if eid in retained_ids]
        record['retention'] = {'baseline_evidence_edge_ids': baseline_ids,
                               'baseline_assertion_ids': list(record['assertion_ids']),
                               'pruned_evidence_edge_ids': [eid for eid in baseline_ids if eid in pruned]}
        record['assertion_ids'] = sorted({by_id[eid]['assertion_id']
                                         for eid in record['normalized_evidence_edge_ids']})
    connected = {row[k] for row in edges for k in ('subject', 'object')}
    statuses = Counter(row['status'] for row in edges)
    projection = {'graph_format': RETAINED_FORMAT, 'data_kind': graph['data_kind'],
                  'snapshot_sha256': graph['snapshot_sha256'],
                  'baseline': {'packet_id': manifest['packet_id'], 'graph_sha256': manifest['graph_sha256'],
                               'packet_path': 'baseline_packet', 'source_graph_format': graph['graph_format']},
                  'retention_policy': RETENTION_POLICY, 'review_policy': _REVIEW_POLICY,
                  'decision_sha256': digest(value),
                  'nodes': deepcopy(graph['nodes']), 'edges': edges, 'assertions': assertions,
                  'context_records': contexts, 'quarantine': deepcopy(graph['quarantine']),
                  'assertion_changes': changes, 'assertion_summary': assertion_summary(assertions),
                  'summary': {'nodes': len(graph['nodes']), 'evidence_edges': len(edges), 'assertions': len(assertions),
                              'context_records': len(contexts), 'quarantined_records': len(graph['quarantine']),
                              'isolated_nodes': sum(row['id'] not in connected for row in graph['nodes']),
                              'edge_status_counts': dict(sorted(statuses.items())),
                              'dispositions': {key: len(rows) for key, rows in dispositions.items()}},
                  'interpretation': ('Retained evidence after explicit local decisions; abstain means unassessed, not validated. '
                      'Edge statuses and context normalization statuses describe original structural processing, not decision labels. '
                      'No new biological validation, confidence calibration, source retrieval or identifier mapping is performed. '
                      'Out-of-scope records are not pruning decisions; scope, source summaries and review events remain in baseline_packet.')}
    for key in ('civic_snapshot_sha256', 'assay_publication_sha256', 'assay_attachment_sha256',
                'evidence_extension_sha256'):
        if key in graph:
            projection[key] = graph[key]
    if 'assay_observations' in graph:
        projection['assay_observations'] = deepcopy(graph['assay_observations'])
        by_decision = {row['edge_id']: row['decision'] for row in value['decisions']}
        for observation in projection['assay_observations']:
            baseline_id = observation['graph_edge_id']
            if baseline_id is not None and baseline_id not in by_id:
                raise ValueError('Baseline assay observation refers to missing evidence.')
            observation['retention'] = {'baseline_graph_edge_id': baseline_id,
                                        'decision': by_decision.get(baseline_id)}
            if baseline_id in pruned:
                observation['graph_edge_id'] = None
    if 'extension_observations' in graph:
        projection['extension_observations'] = deepcopy(graph['extension_observations'])
        by_decision = {row['edge_id']: row['decision'] for row in value['decisions']}
        for observation in projection['extension_observations']:
            if 'graph_edge_id' not in observation:
                continue
            baseline_id = observation['graph_edge_id']
            if baseline_id is not None and baseline_id not in by_id:
                raise ValueError('Baseline extension observation refers to missing evidence.')
            observation['retention'] = {'baseline_graph_edge_id': baseline_id,
                                        'decision': by_decision.get(baseline_id)}
            if baseline_id in pruned:
                observation['graph_edge_id'] = None
    _graph_inventory(projection)
    return projection


def _decision_report_fields(manifest, graph, value, retained):
    dispositions = _decision_value(value, manifest, graph)
    return {'format': DECISION_REPORT_FORMAT,
            'packet_id': manifest['packet_id'], 'packet_manifest_sha256': manifest['content_sha256'],
            'graph_sha256': manifest['graph_sha256'], 'method': value['method'], 'actor': value['actor'],
            'baseline_packet': 'baseline_packet', 'retained_graph': 'retained_graph.json',
            'retained_graph_sha256': digest(retained), 'retention_policy': RETENTION_POLICY,
            'review_policy': _REVIEW_POLICY, 'retained_summary': retained['summary'],
            'counts': {key: len(rows) for key, rows in dispositions.items()},
            'node_ids': [row['id'] for row in graph['nodes']],
            'edge_ids': {key: sorted(rows) for key, rows in dispositions.items()},
            'source_mutations': 0, 'official_scoring_performed': False,
            'biological_validation_performed': False, 'note': _DECISION_NOTE}


def save_decisions(packet, decisions_path, output):
    """Preserve every baseline edge and materialize explicit non-pruned evidence."""
    packet, decisions_path = Path(packet), Path(decisions_path)
    manifest, graph = load_packet(packet)
    if decisions_path.is_symlink() or not decisions_path.is_file():
        raise ValueError('Decision input must be a regular JSON file.')
    decision_bytes = decisions_path.read_bytes()
    value = _decode(decision_bytes)
    retained = _retained_graph(manifest, graph, value)
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
    del copied_manifest, copied_graph
    _jsonl(output / 'nodes.jsonl', graph['nodes'])
    _jsonl(output / 'edge_dispositions.jsonl', value['decisions'])
    write_json(output / 'retained_graph.json', retained)
    for name, field in _inventories(retained).items():
        _jsonl(output / ('retained_' + name), retained[field])
    _jsonl(output / 'assertion_changes.jsonl', retained['assertion_changes'])
    current, current_graph = load_packet(packet)
    del current_graph
    if current != manifest or decisions_path.read_bytes() != decision_bytes:
        raise ValueError('Packet or decisions changed while saving; disposition report was not sealed.')
    report = {**_decision_report_fields(manifest, graph, value, retained), 'created_at': utcnow(),
              'files': {p.relative_to(output).as_posix(): sha(p)
                        for p in sorted(output.rglob('*')) if p.is_file()}}
    write_json(output / 'report.json', _seal(report))
    # Final replay is unchanged; release construction inputs before it creates
    # its own fully validated baseline and retained graph.
    del graph, retained, value
    load_decisions(output)
    return report


def load_decisions(folder):
    """Verify the full ledger and regenerate retained support from preserved inputs.

    Hashes alone do not establish support consistency. Also compare the derived
    graph and its inventories with the preserved baseline and complete ledger.
    No network access or scientific adjudication occurs.
    """
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir() or any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('Disposition package must contain regular files and no symlinks.')
    report = _read(folder / 'report.json')
    if (not _sealed(report) or report.get('format') != DECISION_REPORT_FORMAT
            or not _hashmap(report.get('files'))
            or any(not _safe_relative(name) for name in report['files'])):
        raise ValueError('Disposition report identity or file manifest is invalid.')
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    if (actual != set(report['files']) | {'report.json'}
            or any(not (folder / name).is_file() or sha(folder / name) != expected
                   for name, expected in report['files'].items())):
        raise ValueError('Disposition package file inventory or saved bytes changed.')
    try:
        if datetime.fromisoformat(report['created_at']).utcoffset() is None:
            raise ValueError('Timezone required.')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Disposition report timestamp must include a timezone.') from exc
    manifest, graph = load_packet(folder / 'baseline_packet')
    expected_files = {'decisions.json', 'packet_manifest.json', 'nodes.jsonl', 'edge_dispositions.jsonl',
                      'retained_graph.json', 'assertion_changes.jsonl',
                      *('retained_' + name for name in _inventories(graph)),
                      'baseline_packet/' + MANIFEST_FILE,
                      *('baseline_packet/' + name for name in manifest['files'])}
    if (set(report['files']) != expected_files
            or (folder / 'packet_manifest.json').read_bytes() != (folder / 'baseline_packet' / MANIFEST_FILE).read_bytes()):
        raise ValueError('Disposition package inventory does not match its preserved baseline.')
    value = _read(folder / 'decisions.json')
    retained = _retained_graph(manifest, graph, value)
    fields = _decision_report_fields(manifest, graph, value, retained)
    if (set(report) != set(fields) | {'created_at', 'files', 'content_sha256'}
            or any(canonical(report.get(key)) != canonical(expected) for key, expected in fields.items())
            or _read(folder / 'retained_graph.json') != retained):
        raise ValueError('Retained graph or disposition summary disagrees with the baseline and decisions.')
    projections = {'nodes.jsonl': graph['nodes'], 'edge_dispositions.jsonl': value['decisions'],
                   'assertion_changes.jsonl': retained['assertion_changes'],
                   **{'retained_' + name: retained[field] for name, field in _inventories(retained).items()}}
    del graph
    for name, rows in projections.items():
        saved = [_decode(line) for line in (folder / name).read_bytes().splitlines()]
        if saved != rows:
            raise ValueError('Disposition JSONL inventory disagrees with its materialized graph: ' + name)
        del saved
    return report, retained
