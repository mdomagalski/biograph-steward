"""Immutable, offline comparison and review carryover for two saved Pharos runs.

This writes a new ordinary inspection run. It does not fetch source data,
withdraw assertions, or turn inherited review decisions into new judgments.
Version 1 accepts ordinary parents only: chained refreshes would require the
complete recursive ancestry proof, which this minimal portable packet omits.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
from html import escape
import json
from pathlib import Path
import re
from shutil import copyfile

from . import assertions, civic, civic_context, client, context, graph as graph_module, normalization, refresh
from .client import digest, utcnow, write_json

POLICY = 'biograph-steward.refresh-workflow.v1'
REQUIRED_INPUTS = ('snapshot.json', 'graph.json', 'run_manifest.json')
OPTIONAL_INPUTS = ('review_events.json', 'civic_snapshot.json')
COMPARISON_FILE = 'refresh_comparison.json'
REPORT_FILE = 'refresh_report.html'
RECEIPT_FILE = 'refresh_receipt.json'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate key in saved refresh JSON.')
            value[key] = item
        return value
    def constant(_):
        raise ValueError('Nonfinite value in saved refresh JSON.')
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=pairs, parse_constant=constant)


def _code_hashes():
    modules = {'workflow': __file__, 'comparison': refresh.__file__,
               'graph': graph_module.__file__, 'normalization': normalization.__file__,
               'assertions': assertions.__file__, 'context': context.__file__,
               'civic': civic.__file__, 'civic_context': civic_context.__file__, 'client': client.__file__}
    return {name: _sha(path) for name, path in modules.items()}


def _input_files(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Refresh inputs must be ordinary saved-run directories.')
    for name in REQUIRED_INPUTS:
        if not (path / name).is_file():
            raise ValueError('Refresh input is missing required ' + name + '.')
    names = [*REQUIRED_INPUTS, *(name for name in OPTIONAL_INPUTS
                               if (path / name).exists() or (path / name).is_symlink())]
    if any((path / name).is_symlink() or not (path / name).is_file() for name in names):
        raise ValueError('Refresh input files must be regular files, not symlinks.')
    return {name: _sha(path / name) for name in names}


def refresh_artifact_required(path: Path) -> bool:
    """Recognize a refresh even when its receipt was removed or never completed."""
    path = Path(path)
    if any((path / name).exists() for name in
           (RECEIPT_FILE, COMPARISON_FILE, REPORT_FILE, 'refresh_inputs')):
        return True
    manifest = path / 'run_manifest.json'
    if manifest.exists():
        value = _read(manifest)
        if not isinstance(value, dict):
            raise ValueError('Invalid saved run manifest.')
        if value.get('run_mode') == 'refresh':
            return True
    # Inherited events must not be laundered into an ordinary run by changing
    # its manifest mode or omitting its workflow marker files.
    for name in ('review_events.json', 'graph.json'):
        file = path / name
        if file.exists():
            value = _read(file)
            if name == 'graph.json' and not isinstance(value, dict):
                raise ValueError('Invalid saved run graph.')
            events = value if name == 'review_events.json' else value.get('review_events', [])
            if isinstance(events, list) and any(isinstance(event, dict) and 'migration' in event for event in events):
                return True
    return False


def _events(path, saved_graph):
    file = Path(path) / 'review_events.json'
    events = _read(file) if file.exists() else saved_graph.get('review_events', [])
    if not isinstance(events, list) or events != saved_graph.get('review_events', []):
        raise ValueError('Saved review events disagree with the source graph.')
    return deepcopy(events)


def _after_material(path):
    path = Path(path)
    snapshot, saved_graph = _read(path / 'snapshot.json'), _read(path / 'graph.json')
    if not isinstance(snapshot, dict) or not isinstance(saved_graph, dict):
        raise ValueError('Refresh target snapshot and graph must be JSON objects.')
    events = _events(path, saved_graph)
    civic_path = path / 'civic_snapshot.json'
    civic = _read(civic_path) if civic_path.exists() else None
    if graph_module.build_graph(snapshot, events, civic) != saved_graph:
        raise ValueError('The target saved graph does not replay from its source snapshot and reviews.')
    return snapshot, saved_graph, events, civic


def _output_inventory(snapshot, civic, inputs):
    names = {'snapshot.json', 'graph.json', 'assertions.json', 'context_records.json',
             'context_metadata.json', 'normalization_report.json', 'context_records.tsv',
             'review_events.json', 'question_scope.json', 'assertions.tsv', 'source_licenses.json',
             'nodes.tsv', 'edges.tsv', 'targets.tsv', 'quarantine.jsonl', 'pipeline_trace.json',
             'run_manifest.json', 'report.html', 'benchmark_readiness.json', 'review_candidates.tsv',
             COMPARISON_FILE, REPORT_FILE}
    if snapshot.get('retrieval', {}).get('context') is not None:
        names.update(('retrieval_coverage.json', 'retrieval_coverage.tsv'))
    names.update(f'raw_responses/{index:03d}.json' for index in range(len(snapshot.get('requests', []))))
    if civic is not None:
        names.update(('civic_snapshot.json', 'civic_report.json', 'civic_overlap.json'))
        names.update(f'civic_raw_responses/{index:03d}.json' for index in range(len(civic['requests'])))
    for label, files in inputs.items():
        names.update('refresh_inputs/' + label + '/' + name for name in files)
    return names


def _report(comparison, graph, receipt_metadata):
    def esc(value):
        return escape(str(value), quote=True)
    def details(value):
        return '<pre>' + esc(json.dumps(value, ensure_ascii=False, indent=2)) + '</pre>'
    before_graph = receipt_metadata['before_graph']
    graphs = {'before': before_graph, 'after': graph}
    def keyed(value, name):
        rows = value.get(name) if isinstance(value, dict) else None
        return {row['id']: row for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)} if isinstance(rows, list) else {}
    node_maps = {side: keyed(value, 'nodes') for side, value in graphs.items()}
    claim_maps = {side: keyed(value, 'assertions') for side, value in graphs.items()}
    edge_maps = {side: keyed(value, 'edges') for side, value in graphs.items()}
    relations = {'disease_association': 'associated with', 'disease_filtered_membership': 'listed under',
                 'pathway_membership': 'participates in pathway', 'go_annotation': 'has GO annotation',
                 'protein_interaction': 'has interaction annotation with', 'drug_listing': 'has drug listing',
                 'expression_observation': 'has expression observation in'}
    def label(identifier, side):
        node = node_maps[side].get(identifier, {})
        name, symbol = node.get('name'), node.get('sym')
        return (str(symbol) + ' — ' + str(name) if symbol and name and symbol != name else
                str(symbol or name or identifier))
    def qualified_claim(aid):
        side = 'after' if aid in claim_maps['after'] else 'before'
        claim = claim_maps[side].get(aid)
        if claim is None:
            return esc(aid)
        qualifiers = {key: value for key, value in claim.get('qualifiers', {}).items() if value is not None}
        context = '; '.join(key.replace('_', ' ') + ': ' + label(value, side) for key, value in qualifiers.items())
        return ('<strong>' + esc(label(claim['subject'], side)) + '</strong> '
                + esc(relations.get(claim['kind'], claim['predicate'])) + ' <strong>'
                + esc(label(claim['object'], side)) + '</strong>'
                + ('<p class="qualifiers">' + esc(context) + '</p>' if context else '')
                + '<small>' + esc(aid) + '</small>')
    def source_records(row, side):
        summary = row.get(side)
        if summary is None:
            return []
        return [{'edge_id': eid, 'source': edge_maps[side][eid].get('primary_source_raw'),
                 'source_record': edge_maps[side][eid].get('evidence_record'),
                 'record_locators': edge_maps[side][eid].get('record_locators', [])}
                for eid in summary.get('evidence_edge_ids', []) if eid in edge_maps[side]]
    summary = comparison.get('summary', {})
    counts = ''.join('<tr><th>' + esc(key) + '</th><td>' + esc(value) + '</td></tr>'
                     for key, value in summary.get('status_counts', {}).items())
    rows = []
    for row in comparison.get('assertions', []):
        aid = row.get('assertion_id', '')
        body = {'before': row.get('before'), 'after': row.get('after'),
                'reasons': row.get('reasons', []), 'review_blockers': row.get('review_blockers', [])}
        changed_source = ('<details><summary>Old and new source records</summary>'
                          + details({side: source_records(row, side) for side in ('before', 'after')})
                          + '</details>' if row.get('observed_change') != 'unchanged' else '')
        rows.append('<tr><td>' + qualified_claim(aid) + '</td><td>' + esc(row.get('kind', '')) + '</td><td>'
                    + esc(row.get('observed_change', '')) + '</td><td>' + esc(row.get('status', ''))
                    + '</td><td>' + esc(row.get('review_eligible', False)) + '</td><td><details><summary>Evidence and limits</summary>'
                    + details(body) + '</details>' + changed_source + '</td></tr>')
    original_events = receipt_metadata['after_review_events']
    carried = graph.get('review_events', [])[len(original_events):]
    review_details = ''.join('<details><summary>Inherited event ' + esc(event.get('sequence', ''))
                             + ' — ' + esc(event.get('assertion_id', '')) + '</summary>'
                             + details(event) + '</details>' for event in carried)
    parents = comparison.get('parents', {})
    limitations = ''.join('<li>' + esc(value) + '</li>' for value in comparison.get('limitations', []))
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Pharos refresh comparison</title>'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><style>'
            'body{font:16px/1.5 system-ui,sans-serif;max-width:1400px;margin:2rem auto;padding:0 1rem;color:#17212b}'
            'table{border-collapse:collapse;width:100%;margin:1rem 0}td,th{border:1px solid #ccd4dc;padding:.5rem;text-align:left;vertical-align:top}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin:.4rem 0}a{color:#075ca8}'
            'small{overflow-wrap:anywhere;color:#536171}.qualifiers{font-size:.9rem;margin:.4rem 0}</style>'
            '<h1>Pharos refresh comparison</h1><p>Observed differences between two preserved source snapshots. '
            'Absence does not establish withdrawal, contradiction or biological invalidity. No source data was fetched by this comparison.</p>'
            '<p>Created: ' + esc(receipt_metadata['created_at']) + '. Review carryover requested: '
            + esc(receipt_metadata['carry_reviews']) + '.</p><table><caption>Comparison statuses</caption>' + counts + '</table>'
            '<details><summary>Coverage, scope and policy compatibility</summary>' + details(comparison.get('compatibility', {}))
            + details(summary) + '</details><details><summary>Target membership observations</summary>'
            + details(comparison.get('target_changes', {})) + '</details><h2>Assertion observations</h2>'
            '<table><thead><tr><th>Qualified claim</th><th>Kind</th><th>Observed change</th><th>Status</th><th>Carryover eligible</th><th>Provenance</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table><h2>Review provenance</h2>'
            '<p>Inherited events preserve prior decisions under the recorded compatibility policy. '
            'They are tool-recorded carryovers, not fresh human judgments. Existing target-run reviews remain separate.</p>'
            '<p><a href="refresh_inputs/before/graph.json">Prior graph and review history</a> · '
            '<a href="refresh_inputs/after/graph.json">Target graph before carryover</a> · '
            '<a href="review_events.json">Result review events</a> · <a href="graph.json">Result graph</a> · '
            '<a href="refresh_comparison.json">Machine-readable comparison</a></p>'
            + (review_details or '<p>No inherited review events were added.</p>')
            + '<h2>Source identities and limitations</h2>' + details(parents) + '<ul>' + limitations + '</ul>'
            '<p>This version accepts ordinary parent runs only; chained refresh ancestry is not supported.</p>'
            '<p>Hashes detect changed saved bytes; they do not independently attest upstream truth or a fresh network retrieval.</p></html>')


def run_refresh(before: Path, after: Path, output: Path, *, carry_reviews: bool = False) -> dict:
    before, after, output = Path(before), Path(after), Path(output)
    if type(carry_reviews) is not bool:
        raise ValueError('carry_reviews must be a boolean.')
    if output.is_symlink() or any(output.resolve() == p.resolve() or output.resolve().is_relative_to(p.resolve())
                                  for p in (before, after)):
        raise ValueError('Refresh output must be outside both immutable source runs.')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Choose a new or empty refresh output directory.')
    for path in (before, after):
        if refresh_artifact_required(path):
            raise ValueError('Version 1 refresh requires ordinary parents without inherited reviews; '
                             'chained refresh ancestry is not supported.')
    inputs = {'before': _input_files(before), 'after': _input_files(after)}
    comparison = refresh.compare_runs(before, after)
    snapshot, _, after_events, civic = _after_material(after)
    created_at = utcnow()
    events = (refresh.migrate_reviews(before, after, comparison, created_at=created_at)
              if carry_reviews else after_events)
    if events[:len(after_events)] != after_events:
        raise ValueError('Review carryover must preserve the target run history unchanged.')
    saved_graph = graph_module.save_run(snapshot, output, run_mode='refresh', review_events=events, civic_snapshot=civic)
    for label, path in (('before', before), ('after', after)):
        destination = output / 'refresh_inputs' / label
        destination.mkdir(parents=True)
        for name, expected in inputs[label].items():
            copyfile(path / name, destination / name)
            if _sha(path / name) != expected or _sha(destination / name) != expected:
                raise ValueError('A refresh input changed during preservation; result is incomplete.')
    # Reconstruct comparison from the exact preserved inputs, not transient paths.
    if refresh.compare_runs(output / 'refresh_inputs/before', output / 'refresh_inputs/after') != comparison:
        raise ValueError('Preserved refresh inputs do not reproduce the comparison.')
    metadata = {'created_at': created_at, 'carry_reviews': carry_reviews, 'after_review_events': after_events,
                'before_graph': _read(output / 'refresh_inputs/before/graph.json')}
    write_json(output / COMPARISON_FILE, comparison)
    (output / REPORT_FILE).write_text(_report(comparison, saved_graph, metadata), encoding='utf-8')
    receipt = {'format': POLICY, 'created_at': created_at, 'carry_reviews': carry_reviews,
               'comparison_sha256': comparison['comparison_sha256'], 'inputs': inputs,
               'code_hashes': _code_hashes(), 'review_carryover_actor': refresh.DEFAULT_REVIEWER,
               'review_carryover_is_new_human_judgment': False,
               'network_requests': 0, 'llm_calls': 0, 'input_mutations': 0,
               'files': {p.relative_to(output).as_posix(): _sha(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    if set(receipt['files']) != _output_inventory(snapshot, civic, inputs):
        raise ValueError('Unexpected generated refresh output inventory.')
    receipt['receipt_sha256'] = digest(receipt)
    write_json(output / RECEIPT_FILE, receipt)
    return {'comparison': comparison, 'graph': saved_graph, 'receipt': receipt}


class RefreshRuntimeMismatch(ValueError):
    """Saved bytes passed integrity checks, but pinned implementation differs."""

    def __init__(self, changed_modules):
        self.changed_modules = sorted(changed_modules)
        super().__init__('Saved comparison files match their recorded hashes, but the current '
                         'implementation differs (' + ', '.join(self.changed_modules) + '). '
                         'Open the read-only comparison archive, or use the recorded implementation '
                         'for replay. No current replay was performed.')


def verify_refresh_files(output: Path) -> dict:
    """Check the saved packet without invoking current graph/comparison semantics.

    This is byte integrity relative to the unsigned receipt, not scientific
    validation, provenance authentication, or successful deterministic replay.
    """
    output = Path(output)
    if output.is_symlink() or any(p.is_symlink() for p in output.rglob('*')):
        raise ValueError('Refresh results may not contain symlinks.')
    receipt = _read(output / RECEIPT_FILE)
    if (not isinstance(receipt, dict)
            or any(not isinstance(receipt.get(name), dict) for name in ('files', 'inputs', 'code_hashes'))
            or set(receipt['inputs']) != {'before', 'after'}
            or any(not isinstance(value, dict) for value in receipt['inputs'].values())):
        raise ValueError('Malformed refresh receipt metadata.')
    hash_maps = [receipt['files'], receipt['code_hashes'], *receipt['inputs'].values()]
    if any(not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts
           or not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
           for mapping in hash_maps for name, value in mapping.items()):
        raise ValueError('Malformed refresh receipt hashes or file names.')
    try:
        if not isinstance(receipt.get('created_at'), str) or datetime.fromisoformat(receipt['created_at']).utcoffset() is None:
            raise ValueError('Timezone is required.')
    except (TypeError, ValueError) as exc:
        raise ValueError('Refresh receipt timestamp must include a timezone.') from exc
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()} - {RECEIPT_FILE}
    if (receipt.get('format') != POLICY
            or receipt.get('receipt_sha256') != digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
            or actual != set(receipt.get('files', {}))
            or any(_sha(output / name) != value for name, value in receipt['files'].items())):
        raise ValueError('Refresh receipt, inventory or saved bytes changed.')
    if (type(receipt.get('carry_reviews')) is not bool or receipt.get('network_requests') != 0
            or receipt.get('llm_calls') != 0 or receipt.get('input_mutations') != 0
            or receipt.get('review_carryover_actor') != refresh.DEFAULT_REVIEWER
            or receipt.get('review_carryover_is_new_human_judgment') is not False):
        raise ValueError('Refresh execution policy changed.')
    before, after = output / 'refresh_inputs/before', output / 'refresh_inputs/after'
    if receipt.get('inputs') != {'before': _input_files(before), 'after': _input_files(after)}:
        raise ValueError('Preserved refresh parent bytes changed.')
    for path in (before, after):
        if {p.name for p in path.iterdir()} != set(_input_files(path)):
            raise ValueError('Unexpected preserved refresh input files.')
    comparison = _read(output / COMPARISON_FILE)
    if (not isinstance(comparison, dict)
            or comparison.get('comparison_sha256') != digest({key: value for key, value in comparison.items()
                                                             if key != 'comparison_sha256'})
            or receipt.get('comparison_sha256') != comparison.get('comparison_sha256')):
        raise ValueError('Saved comparison identity disagrees with its receipt.')
    snapshot = _read(output / 'snapshot.json')
    civic_path = output / 'civic_snapshot.json'
    civic_snapshot = _read(civic_path) if civic_path.exists() else None
    if (not isinstance(snapshot, dict)
            or actual != _output_inventory(snapshot, civic_snapshot, receipt['inputs'])):
        raise ValueError('Refresh output inventory disagrees with its saved sources.')
    return receipt


def refresh_runtime_changes(receipt: dict) -> list[str]:
    current = _code_hashes()
    recorded = receipt['code_hashes']
    return sorted(name for name in set(current) | set(recorded) if current.get(name) != recorded.get(name))


def verify_refresh(output: Path) -> dict:
    output = Path(output)
    receipt = verify_refresh_files(output)
    changed = refresh_runtime_changes(receipt)
    if changed:
        raise RefreshRuntimeMismatch(changed)
    before, after = output / 'refresh_inputs/before', output / 'refresh_inputs/after'
    actual = set(receipt['files'])
    comparison = refresh.compare_runs(before, after)
    if (_read(output / COMPARISON_FILE) != comparison
            or receipt.get('comparison_sha256') != comparison['comparison_sha256']):
        raise ValueError('Refresh comparison does not replay from its preserved parents.')
    snapshot, _, after_events, civic = _after_material(after)
    events = (refresh.migrate_reviews(before, after, comparison, created_at=receipt['created_at'])
              if receipt['carry_reviews'] else after_events)
    expected_graph = graph_module.build_graph(snapshot, events, civic)
    if (actual != _output_inventory(snapshot, civic, receipt['inputs'])
            or events[:len(after_events)] != after_events
            or _read(output / 'snapshot.json') != snapshot or _read(output / 'graph.json') != expected_graph
            or _read(output / 'review_events.json') != events
            or (output / 'civic_snapshot.json').exists() != (civic is not None)
            or civic is not None and _read(output / 'civic_snapshot.json') != civic):
        raise ValueError('Refresh result graph, source or review inheritance does not replay.')
    manifest = _read(output / 'run_manifest.json')
    if (not isinstance(manifest, dict)
            or manifest.get('run_mode') != 'refresh' or manifest.get('snapshot_sha256') != snapshot['content_sha256']
            or manifest.get('review_event_count') != len(events)):
        raise ValueError('Refresh result manifest disagrees with its graph.')
    metadata = {'created_at': receipt['created_at'], 'carry_reviews': receipt['carry_reviews'],
                'after_review_events': after_events, 'before_graph': _read(before / 'graph.json')}
    if (output / REPORT_FILE).read_text(encoding='utf-8') != _report(comparison, expected_graph, metadata):
        raise ValueError('Refresh inspection report does not replay.')
    return receipt
