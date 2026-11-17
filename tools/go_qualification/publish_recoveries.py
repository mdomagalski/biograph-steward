"""Publish qualified native GO rows without rewriting historical Pharos evidence.

This orchestration reuses source adapters, ordinary graph replay and the Gold
decision interface. Preparation and history-bound app publication are separate:
the old WikiPathways proof cannot be reused for different source graph bytes.
No retrieval, inference, biological acceptance or review migration is performed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import evidence_extension, gold_packet, qualified_workspace
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from biograph_steward.reviews import (preserve_construction_plan, read_assay,
                                      read_civic, read_run)

FORMAT = 'biograph-steward.native-go-recovery-preparation.v1'
REPORT = 'recovery_preparation.json'
FINAL_FORMAT = 'biograph-steward.native-go-recovery-publication.v1'


def need(condition, message):
    if not condition:
        raise ValueError('Native GO recovery publication: ' + message)


def inventory(folder, *, exclude=()):
    folder = Path(folder)
    need(folder.is_dir() and not folder.is_symlink()
         and not any(p.is_symlink() for p in folder.rglob('*')), 'ordinary files are required.')
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*'))
            if p.is_file() and p.relative_to(folder).as_posix() not in exclude}


def _seal(value):
    return {**value, 'content_sha256': digest(value)}


def _stage(output, sources):
    output = Path(output).resolve()
    need(not output.exists() and not output.is_symlink()
         and all(output != Path(s).resolve() and output not in Path(s).resolve().parents
                 and Path(s).resolve() not in output.parents for s in sources),
         'choose a new output outside every input directory.')
    output.parent.mkdir(parents=True, exist_ok=True)
    return output, Path(tempfile.mkdtemp(prefix='.native-go-recoveries-', dir=output.parent))


def _assertion_payload(row):
    row = deepcopy(row)
    # This envelope binds all source adapters together, even unchanged ones.
    # Assertion identity, revision, evidence, lifecycle and reviews stay exact.
    if row.get('extension_source_kind'):
        row.pop('evidence_extension_sha256', None)
    return row


def _reuse_publication(adapter, publication, census, qualification, context,
                       old_packet, old_report, old_graph, old_retained, census_sha256, destination):
    """Replay an already prepared adapter publication against these exact inputs."""
    manifest, projection, material = adapter.load_publication(publication)
    intake = gold_packet._decode(material[adapter.INTAKE])
    qualification_report = gold_packet._read(Path(qualification) / 'go_ontology_qualification.json')
    need(gold_packet._sealed(qualification_report), 'original GO qualification seal differs.')
    need(sha(Path(census) / 'report.json') == census_sha256
         and projection['bindings']['census_file_sha256'] == census_sha256
         and intake['original_packet_id'] == old_packet['packet_id']
         and intake['original_graph_sha256'] == old_packet['graph_sha256']
         and intake['baseline_go_edges_sha256'] == digest(adapter._go_edges(old_graph))
         and intake['retained_go_edges_sha256'] == digest(adapter._go_edges(old_retained)),
         'existing GOA publication belongs to different census, baseline or retained GO evidence.')
    need(qualification_report['packet_id'] == old_packet['packet_id']
         and qualification_report['graph_sha256'] == old_packet['graph_sha256']
         and old_report['packet_id'] == old_packet['packet_id'], 'qualification belongs to another packet.')
    expected = {
        adapter.CENSUS + 'report.json': Path(census) / 'report.json',
        adapter.PROPOSALS: Path(qualification) / 'replacement_proposals.json',
        adapter.ONTOLOGY: Path(qualification) / qualification_report['ontology']['source_file'],
        adapter.CONTEXT + adapter.CONTEXT_REPORT: Path(context) / adapter.CONTEXT_REPORT,
    }
    import hashlib
    need(all(hashlib.sha256(material[name]).hexdigest() == sha(path) for name, path in expected.items())
         and gold_packet._decode(material[adapter.ONTOLOGY_BINDING]) == qualification_report['ontology'],
         'existing GOA publication source captures differ from the supplied inputs.')
    destination.mkdir()
    for name, raw in material.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return manifest


def preserved_properties(old, new, old_decisions, new_decisions):
    """Reject any old payload/review change; permit only the declared envelope."""
    old_edges = {r['id']: r for r in old['edges']}
    new_edges = {r['id']: r for r in new['edges']}
    need(len(old_edges) == len(old['edges']) and len(new_edges) == len(new['edges']),
         'duplicate evidence IDs.')
    need(all(new_edges.get(uid) == row for uid, row in old_edges.items()),
         'an existing evidence payload or assertion identity changed.')
    added = [e for e in new['edges'] if e['id'] not in old_edges]
    need(added and all(e.get('extension_source_kind') == 'goa'
                      and e.get('record_kind') == 'native_go_annotation'
                      and e.get('biologically_validated') is False for e in added),
         'all additions must be unaccepted native GO evidence.')
    old_assertions = {r['id']: r for r in old['assertions']}
    new_assertions = {r['id']: r for r in new['assertions']}
    need(all(uid in new_assertions and _assertion_payload(row) == _assertion_payload(new_assertions[uid])
             for uid, row in old_assertions.items()),
         'an existing assertion, revision, lifecycle or review history changed.')
    old_nodes = {n['id']: n for n in old['nodes']}
    new_nodes = {n['id']: n for n in new['nodes']}
    need(len(new_nodes) == len(new['nodes'])
         and all(new_nodes.get(uid) == row for uid, row in old_nodes.items()),
         'an existing node changed or collided.')
    for field in ('review_events', 'context_records', 'quarantine'):
        need(old[field] == new[field], 'existing ' + field + ' changed.')
    old_rows = old_decisions['decisions']
    need(new_decisions['decisions'][:len(old_rows)] == old_rows,
         'existing decision rows were changed or reordered.')
    appended = new_decisions['decisions'][len(old_rows):]
    need(len(appended) == len(added)
         and {r['edge_id'] for r in appended} == {e['id'] for e in added}
         and all(r['decision'] == 'abstain' and r['confidence'] is None for r in appended),
         'new evidence requires one explicit abstention each.')
    return {
        'old_edges': len(old_edges), 'added_edges': len(added),
        'old_assertions': len(old_assertions), 'added_assertions': len(new_assertions) - len(old_assertions),
        'old_nodes': len(old_nodes), 'added_nodes': len(new_nodes) - len(old_nodes),
        'old_edge_payloads_sha256': digest([old_edges[k] for k in sorted(old_edges)]),
        'old_node_payloads_sha256': digest([old_nodes[k] for k in sorted(old_nodes)]),
        'old_assertion_payloads_except_extension_envelope_sha256': digest(
            [_assertion_payload(old_assertions[k]) for k in sorted(old_assertions)]),
        'old_decision_rows_sha256': digest(old_rows),
        'old_review_events_sha256': digest(old['review_events']),
        'old_context_records_sha256': digest(old['context_records']),
        'old_quarantine_sha256': digest(old['quarantine']),
        'old_payloads_preserved': True, 'old_decision_rows_preserved': True,
        'extension_container_binding_changed': old.get('evidence_extension_sha256') != new.get('evidence_extension_sha256'),
        'assertion_envelope_exception': 'evidence_extension_sha256 only, on existing extension assertions',
        'review_states_promoted': False,
    }


def build_recoveries(census, qualification, retained_package, context, output, *, census_sha256,
                     publication=None):
    """Prepare self-contained source/run/Gold/retained artifacts; do not publish an app yet."""
    from biograph_steward import goa_source
    retained_package = Path(retained_package).resolve()
    old_report, old_retained = gold_packet.load_decisions(retained_package)
    old_packet, old_graph = gold_packet.load_packet(retained_package / 'baseline_packet')
    source = retained_package / 'baseline_packet/source'
    before = inventory(retained_package)
    snapshot, events, replay = read_run(source)
    need(replay == old_graph, 'original ordinary baseline differs from its Gold packet.')
    old_extension = evidence_extension.read_extension(source, snapshot)
    need(old_extension is not None and 'goa' not in old_extension['sources'],
         'an existing extension without GOA is required.')
    need(not any(e.get('evidence_extension_sha256') is not None for e in events),
         'extension-bound review events cannot be migrated to a changed global extension binding.')
    old_decisions = gold_packet._read(retained_package / 'decisions.json')
    inputs = (census, qualification, retained_package, context, *([publication] if publication else []))
    output, stage = _stage(output, inputs)
    try:
        if publication is None:
            publication_manifest = goa_source.publish_recoveries(census, qualification, retained_package, context,
                stage / 'goa_publication', census_sha256=census_sha256)
        else:
            publication_manifest = _reuse_publication(goa_source, publication, census, qualification, context,
                old_packet, old_report, old_graph, old_retained, census_sha256, stage / 'goa_publication')
        publications = {k: source / 'extension_sources' / k for k in old_extension['sources']}
        publications['goa'] = stage / 'goa_publication'
        baseline = gold_packet._extension_baseline_view(old_graph, old_extension)
        extension = evidence_extension.prepare_extension(snapshot, baseline, publications)
        for kind in old_extension['sources']:
            need(extension['sources'][kind] == old_extension['sources'][kind],
                 'an existing source projection changed: ' + kind)
        civic, assay = read_civic(source), read_assay(source)
        # Use the existing adapter byte inventories; never recapture upstream data.
        source_stage = stage / '.extension_sources'
        source_stage.mkdir()
        for kind, folder in publications.items():
            _, _, files = evidence_extension._adapter(kind).load_publication(folder)
            for name, raw in files.items():
                path = source_stage / kind / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        evidence_extension.source_material(snapshot, extension, source_stage, civic, assay,
                                            baseline_graph=baseline)
        raw = stage / 'raw_run'
        new_graph = save_run(snapshot, raw, run_mode='biological_extension', review_events=events,
            civic_snapshot=civic, assay_attachment=assay,
            assay_source=source / 'assay_source' if assay else None,
            evidence_extension=extension, extension_source=source_stage)
        for name in ('snapshot.json', 'review_events.json', 'civic_snapshot.json', 'assay_attachment.json'):
            if (source / name).is_file():
                (raw / name).write_bytes((source / name).read_bytes())
        preserve_construction_plan(source, raw)
        need(read_run(raw)[2] == new_graph, 'new ordinary run does not replay.')
        old_sources = inventory(source / 'extension_sources')
        new_sources = inventory(raw / 'extension_sources')
        need(all(new_sources.get(k) == v for k, v in old_sources.items()),
             'original source publication bytes changed.')
        manifest = gold_packet.export_packet(raw, stage / 'packet')
        old_edge_ids = {r['id'] for r in old_graph['edges']}
        decisions = {**deepcopy(old_decisions), 'packet_id': manifest['packet_id'],
            'decisions': [*deepcopy(old_decisions['decisions']),
                *[{'edge_id': e['id'], 'decision': 'abstain',
                   'reason': 'New native GO source record; not independently adjudicated', 'confidence': None}
                  for e in new_graph['edges'] if e['id'] not in old_edge_ids]]}
        preservation = preserved_properties(old_graph, new_graph, old_decisions, decisions)
        write_json(stage / 'decisions.json', decisions)
        retained_report = gold_packet.save_decisions(stage / 'packet', stage / 'decisions.json', stage / 'retained')
        _, new_retained = gold_packet.load_decisions(stage / 'retained')
        old_retained_ids = {e['id'] for e in old_retained['edges']}
        need([e for e in new_retained['edges'] if e['id'] in old_retained_ids] == old_retained['edges'],
             'an existing retained evidence payload changed.')
        retained_assertions = {a['id']: a for a in new_retained['assertions']}
        need(all(a['id'] in retained_assertions
                 and _assertion_payload(a) == _assertion_payload(retained_assertions[a['id']])
                 for a in old_retained['assertions'])
             and old_retained['context_records'] == new_retained['context_records'],
             'an existing retained assertion, review state or context changed.')
        shutil.rmtree(source_stage)
        need(inventory(retained_package) == before, 'original retained package changed during publication.')
        receipt = _seal({'format': FORMAT, 'created_at': utcnow(),
            'source_retained_report_content_sha256': old_report['content_sha256'],
            'source_packet_id': old_packet['packet_id'], 'source_graph_sha256': digest(old_graph),
            'source_retained_inventory_sha256': digest(before),
            'census_file_sha256': census_sha256, 'goa_publication_content_sha256': publication_manifest['content_sha256'],
            'existing_goa_publication_reused': publication is not None,
            'old_extension_content_sha256': old_extension['content_sha256'],
            'new_extension_content_sha256': extension['content_sha256'],
            'source_publications_preserved': old_sources, 'preservation': preservation,
            'new_graph_sha256': digest(new_graph), 'new_packet_id': manifest['packet_id'],
            'retained_report_content_sha256': retained_report['content_sha256'],
            'counts': {'raw_edges': len(new_graph['edges']), 'raw_assertions': len(new_graph['assertions']),
                'raw_nodes': len(new_graph['nodes']), 'retained_edges': len(new_retained['edges']),
                'retained_assertions': len(new_retained['assertions'])},
            'workspace_published': False, 'next_step': 'Recompute native WikiPathways history against packet/source/graph.json, then finalize.',
            'source_fetches': 0, 'model_calls': 0, 'independent_biological_accuracy_established': False,
            'files': inventory(stage)})
        write_json(stage / REPORT, receipt)
        need(not output.exists(), 'output appeared during preparation.')
        stage.rename(output)
        return receipt
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def load_prepared(prepared):
    """Verify prepared files and the preservation claim without the old input tree."""
    prepared = Path(prepared)
    receipt = gold_packet._read(prepared / REPORT)
    need(gold_packet._sealed(receipt) and receipt.get('format') == FORMAT
         and inventory(prepared, exclude=(REPORT,)) == receipt['files'], 'prepared inventory or seal changed.')
    packet, graph = gold_packet.load_packet(prepared / 'packet')
    report, retained = gold_packet.load_decisions(prepared / 'retained')
    need(digest(graph) == receipt['new_graph_sha256'] and packet['packet_id'] == receipt['new_packet_id']
         and report['content_sha256'] == receipt['retained_report_content_sha256']
         and read_run(prepared / 'raw_run')[2] == graph, 'prepared graph or retained replay changed.')
    old = deepcopy(graph)
    old['edges'] = [e for e in graph['edges'] if e.get('extension_source_kind') != 'goa']
    old['assertions'] = [a for a in graph['assertions'] if a.get('extension_source_kind') != 'goa']
    added_nodes = {n['id'] for n in gold_packet._read(prepared / 'raw_run/evidence_extension.json')['sources']['goa']['prepared']['nodes']}
    old['nodes'] = [n for n in graph['nodes'] if n['id'] not in added_nodes]
    decisions = gold_packet._read(prepared / 'decisions.json')
    old_decisions = {**decisions, 'decisions': decisions['decisions'][:receipt['preservation']['old_edges']]}
    actual = preserved_properties(old, graph, old_decisions, decisions)
    for key, expected in receipt['preservation'].items():
        if key != 'extension_container_binding_changed':
            need(actual[key] == expected, 'preserved old payload digest changed: ' + key)
    sources = inventory(prepared / 'raw_run/extension_sources')
    need(all(sources.get(k) == v for k, v in receipt['source_publications_preserved'].items()),
         'preserved original source publication differs.')
    return receipt, graph, retained


def finalize_recoveries(prepared, history, history_sha, outputworkspace):
    """Publish the prepared retained view only with a newly bound native history proof."""
    prepared = Path(prepared)
    receipt, _, _ = load_prepared(prepared)
    need(history is not None and history_sha is not None, 'new graph-bound pathway history is required.')
    outputworkspace, stage = _stage(outputworkspace, (prepared, history))
    try:
        # The existing consumer verifies the proof's exact source graph file hash.
        published = qualified_workspace.publish_workspace(prepared / 'retained', stage / 'workspace',
            history=Path(history), history_content_sha256=history_sha)
        need(inventory(prepared, exclude=(REPORT,)) == receipt['files'],
             'prepared inputs changed during finalization.')
        need(not outputworkspace.exists(), 'workspace output appeared during publication.')
        (stage / 'workspace').rename(outputworkspace)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return _seal({'format': FINAL_FORMAT, 'created_at': utcnow(),
        'preparation_content_sha256': receipt['content_sha256'],
        'workspace_content_sha256': published['content_sha256'],
        'history_content_sha256': history_sha, 'counts': receipt['counts'],
        'old_decisions_preserved': True, 'source_fetches': 0, 'model_calls': 0,
        'independent_biological_accuracy_established': False})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('prepare')
    for flag in ('census', 'qualification', 'retained-package', 'context', 'output', 'census-sha256'):
        build.add_argument('--' + flag, required=True)
    build.add_argument('--publication', help='Reuse one fully verified GOA publication rather than package it again.')
    final = commands.add_parser('finalize')
    for flag in ('prepared', 'history', 'history-sha256', 'output'):
        final.add_argument('--' + flag, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    if command == 'prepare':
        result = build_recoveries(**args)
    else:
        result = finalize_recoveries(args['prepared'], args['history'], args['history_sha256'], args['output'])
    print(__import__('json').dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
