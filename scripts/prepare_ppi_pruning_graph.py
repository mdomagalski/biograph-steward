#!/usr/bin/env python3
"""Publish an offline, source-bound PPI development graph without assay outcomes.

This adapts the already audited Pharos inventory to the existing ordinary-run
format. It does not extend the interactive construction tool's cohort limit.
Unresolved requested identities are isolated entries in the numerical node
index, never invented resolved proteins in the evidence graph.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
import gc
import hashlib
import io
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_lambourne_pharos_lookup import check_resolution, check_ppi_coverage
from audit_pharos_inventory import retained_rows, source_rows, verified_chunk
from retrieve_pharos_inventory import accession_inventory, read_json, verify_sealed
from biograph_steward.client import SCHEMA_SOURCE, digest, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.graph import save_run, verify_snapshot
from biograph_steward.gold_packet import export_packet

FORMAT = 'biograph-steward.ppi-pruning-source.v1'
CHECKPOINT = 'preparation_checkpoint.json'
PAIR_FIELDS = ['pair_id', 'subject', 'object', 'edge_id', 'source_bundle', 'weight', 'pruning_eligible']
WEIGHTED_FIELDS = ['subject', 'object', 'weight', 'pair_id', 'edge_id', 'source_bundle', 'pruning_eligible']
NODE_FIELDS = ['node_id', 'resolution_status', 'canonical_graph_node_present']
POLICY = {
    'task': 'retrospective_assay_specific_existing_edge_retention',
    'development_reference': 'previously_consumed_Lambourne_human_Y2H_v1',
    'reference_loaded_during_preparation': False,
    'source_network': 'STRINGDB-containing bundles, native Score only',
    'pruning_population': 'exact STRINGDB-only source bundles',
    'retention_fraction': 0.8,
    'other_bundles': 'abstain_and_retain_every_evidence_edge',
    'missing_or_conflicting_weight': 'stop; do not impute',
    'calibrated_confidence': False,
    'canonical_source_mutation': False,
    'interpretation': 'Task-specific graph selection; assay nondetection is not universal biological noninteraction.',
}


def header(folder, audit_path):
    """Bind the existing successful audit to untouched inventory/chunk manifests."""
    folder, audit_path = Path(folder), Path(audit_path)
    names = ('plan.json', 'source.json', 'summary.json', 'context_targets.json')
    if audit_path.is_symlink() or any((folder / n).is_symlink() for n in names):
        raise ValueError('Source inputs must be ordinary saved files.')
    plan, source, summary = [verify_sealed(read_json(folder / n)) for n in names[:3]]
    inventory, ids = accession_inventory(folder / names[3])
    audit = read_json(audit_path)
    expected = {'retrieval_plan_sha256': plan['content_sha256'],
                'retrieval_summary_sha256': summary['content_sha256'],
                'retrieval_source_sha256': sha(folder / 'source.json'),
                'inventory_sha256': sha(folder / 'context_targets.json'),
                'db_version': source['db_version'], 'endpoint': plan['endpoint']}
    if (audit.get('format') != 'biograph-steward.lambourne-pharos-lookup-audit.v1'
            or audit.get('outcome_fields_decoded') is not False
            or any(audit.get(k) != v for k, v in expected.items())):
        raise ValueError('The source-only lookup audit does not bind this retrieval.')
    if (inventory.get('format') != 'biograph-steward.lambourne-ppi-lookup-candidate-inventory.v1'
            or inventory.get('outcome_fields_decoded') is not False
            or plan.get('inventory_sha256') != expected['inventory_sha256']
            or plan.get('ppi_cohort') != ids or plan.get('profile') != 'ppi'
            or plan.get('ppi_confidence') != 400 or plan.get('limits', {}).get('ppis') != 5000
            or any(v for k, v in plan['limits'].items() if k != 'ppis')
            or source.get('plan_sha256') != plan['content_sha256']
            or summary.get('plan_sha256') != plan['content_sha256']
            or source.get('endpoint') != plan['endpoint']
            or not summary.get('retrieval_finished')
            or not summary.get('all_requested_families_count_reconciled')):
        raise ValueError('Expected a completed, count-reconciled exact-cohort PPI-only inventory.')
    size = plan.get('chunk_size')
    if type(size) is not int or size < 1:
        raise ValueError('Invalid source chunk size.')
    chunks = [f'chunks/{n:05d}.json' for n in range(0, len(ids), size)]
    if set(summary['files']) != set(chunks) or set(chunks) != {
            str(p.relative_to(folder)) for p in (folder / 'chunks').glob('*.json')}:
        raise ValueError('Source chunk population differs from the completed manifest.')
    for record in source['requests']:
        if (record.get('endpoint') != plan['endpoint']
                or record.get('response_sha256') != digest(record.get('response'))):
            raise ValueError('Source catalog/version response integrity failed.')
    return plan, source, summary, inventory, ids, chunks, audit


def project_snapshot(folder, audit_path, progress=None):
    """Reconcile every source row and offset its original response locators."""
    folder = Path(folder)
    plan, source, saved, inventory, ids, names, audit = header(folder, audit_path)
    requests = deepcopy(source['requests'])
    targets, resolutions, coverage_rows, chunks = [], [], [], []
    counts, statuses = Counter(), Counter()
    id_set, row_budget = set(ids), 0
    template = None
    for number, name in enumerate(names):
        chunk = verified_chunk(folder, name, plan, source, saved,
                               ids[number * plan['chunk_size']:(number + 1) * plan['chunk_size']])
        check_resolution(chunk)
        resolved = {r['requested_uniprot'] for r in chunk['target_resolution'] if r['status'] == 'resolved'}
        check_ppi_coverage(chunk, resolved)
        # Row equality and cohort retention are verified, not trusted merely
        # because the older successful audit describes the same file hashes.
        raw, wanted = Counter(), Counter()
        for uid, row, _ in source_rows(chunk, name, 'ppis'):
            key = uid, digest(row)
            raw[key] += 1
            counts['raw_source_views'] += 1
            if row['target']['uniprot'] in id_set:
                wanted[key] += 1
        for uid, row, _ in retained_rows(chunk, name, 'ppis'):
            key = uid, digest(row)
            if raw[key] < 1 or wanted[key] < 1:
                raise ValueError('Retained PPI row lacks an identical eligible raw response row.')
            raw[key] -= 1
            wanted[key] -= 1
            counts['retained_source_views'] += 1
        if any(wanted.values()):
            raise ValueError('Within-inventory raw PPI rows are missing from retained context.')
        offset = len(requests)
        for row in chunk['target_resolution']:
            r = deepcopy(row)
            r['returned_uniprot'] = (r['returned'] or {}).get('uniprot')
            r['request_index'] += offset
            resolutions.append(r)
            statuses[r['status']] += 1
        coverage = chunk['retrieval_coverage'] or {}
        for row in coverage.get('targets', []):
            r = deepcopy(row)
            for page in r['pages']:
                page['request_index'] += offset
            coverage_rows.append(r)
        chunks.append({'ordinal': number, 'path': name, 'sha256': saved['files'][name],
                       'request_offset': offset, 'request_count': len(chunk['requests']),
                       'target_offset': len(targets), 'resolved_targets': len(chunk['targets'])})
        targets.extend(chunk['targets'])
        requests.extend(chunk['requests'])
        row_budget += coverage.get('row_budget', 0)
        template = template or coverage
        if progress:
            progress(f'Verified source chunk {number + 1}/{len(names)}')
    if (dict(statuses) != saved['resolution_statuses']
            or any(counts[k] != audit['counts'][k] for k in counts)
            or len(targets) != audit['counts']['resolved_products']
            or len(ids) != audit['counts']['requested_products']):
        raise ValueError('Replayed inventory counts differ from the bound source audit.')
    if not template:
        raise ValueError('No resolved source coverage is available for graph publication.')
    context = {k: deepcopy(v) for k, v in template.items() if k not in {'targets', 'summary', 'scope'}}
    context.update({'targets': coverage_rows, 'summary': deepcopy(saved['families']),
                    'rows_retrieved': counts['raw_source_views'],
                    'row_budget': row_budget,
                    'scope': {**deepcopy(template['scope']), 'seed_uniprots': list(ids),
                              'ppi_cohort_uniprots': list(ids)}})
    bindings = {'retrieval_root': str(folder.resolve()), 'lookup_audit_sha256': sha(audit_path),
                'headers': {n: sha(folder / n) for n in ('plan.json', 'source.json', 'summary.json', 'context_targets.json')},
                'chunks': chunks, 'database_version': source['db_version'],
                'upstream_STRING_release': None,
                'upstream_study_independence_established': False}
    snapshot = {
        'snapshot_format': 'biograph-steward.pharos.v1', 'data_kind': 'live_pharos',
        'created_at': saved['created_at'], 'endpoint': plan['endpoint'], 'db_version': source['db_version'],
        'disease': None, 'scope': {'kind': 'protein_cohort', 'name': 'Frozen Pharos PPI development cohort',
                                  'requested_uniprot': list(ids), 'resolutions': resolutions},
        'targets': targets, 'requests': requests, 'source_licenses': deepcopy(source['source_catalog']),
        'schema_check': {'status': 'validated_by_successful_saved_queries', 'schema_source': SCHEMA_SOURCE},
        'query_settings': {'profile': 'ppi', 'context_limits': deepcopy(plan['limits']),
                           'accessions': list(ids), 'identity_policy': 'exact_no_alias_substitution'},
        'retrieval': {'requested_targets': len(ids), 'records_retrieved': len(targets),
                      'unresolved_targets': len(ids) - len(targets), 'context': context},
        'offline_inventory_projection': {'format': FORMAT, 'source_bindings': bindings,
                                         'outcome_values_loaded': False},
        'warnings': [
            'Retrospective development source projection; no assay outcomes are read during preparation.',
            'Source annotations remain candidates; source scores are not calibrated probabilities.',
            'STRING functional association and physical binding are different tasks; no universal false-edge labels are inferred.',
            'The upstream STRING release and source-study overlap of this frozen Pharos319 inventory are unresolved.',
            'Unresolved requested identities remain explicit scope records and isolated numerical inputs, not resolved graph proteins.',
            'Count reconciliation and version checks do not establish an atomic upstream snapshot.',
        ],
    }
    snapshot['content_sha256'] = digest(snapshot)
    verify_snapshot(snapshot)
    return snapshot, bindings


def native_string_score(edge):
    """Read the original STRING component; never substitute another provider's score."""
    bundle = edge['primary_source_raw']
    if 'STRINGDB' not in (bundle.split(',') if isinstance(bundle, str) else []):
        return None
    values, directions = [], set()
    for view in edge['evidence_record']['source_views']:
        directions.add(view['reported_subject'])
        props = [p['value'] for p in view['record'].get('props', []) if p.get('name') == 'Score']
        if len(props) != 1 or isinstance(props[0], bool):
            raise ValueError('Every STRING source view needs exactly one native Score.')
        try:
            value = float(props[0])
        except (TypeError, ValueError) as exc:
            raise ValueError('Nonnumeric native STRING Score.') from exc
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Native STRING Score is outside its checked 0..1 source scale.')
        values.append(value)
    if directions != {edge['subject'], edge['object']} or len(values) != 2 or len(set(values)) != 1:
        raise ValueError('STRING reciprocal source weights disagree or lack exactly two directions.')
    return values[0]


def pair_tables(graph, snapshot):
    """Expose existing edge IDs and one nonpooled native STRING component."""
    pairs, weighted = [], []
    for edge in sorted(graph['edges'], key=lambda e: (e['subject'], e['object'], e['id'])):
        if edge['record_kind'] != 'protein_interaction':
            raise ValueError('PPI-only graph unexpectedly contains another edge family.')
        subject, obj = edge['subject'], edge['object']
        if subject >= obj:
            raise ValueError('Expected nonself canonically ordered PPI endpoints.')
        bundle = edge['primary_source_raw']
        weight = native_string_score(edge)
        pair_id = 'ppi:' + digest({'subject': subject, 'object': obj})[:24]
        row = {'pair_id': pair_id, 'subject': subject, 'object': obj, 'edge_id': edge['id'],
               'source_bundle': bundle, 'weight': '' if weight is None else weight,
               'pruning_eligible': 'true' if bundle == 'STRINGDB' else 'false'}
        pairs.append(row)
        if weight is not None:
            weighted.append(row)
    if len({r['pair_id'] for r in pairs}) != len(pairs):
        raise ValueError('Multiple source bundles for one pair require an explicit grouped decision contract.')
    canonical_nodes = {n['id'] for n in graph['nodes']}
    nodes = [{'node_id': 'UniProtKB:' + r['requested_uniprot'], 'resolution_status': r['status'],
              'canonical_graph_node_present': 'true' if 'UniProtKB:' + r['requested_uniprot'] in canonical_nodes else 'false'}
             for r in snapshot['scope']['resolutions']]
    return nodes, pairs, weighted


def table(path, rows, fields):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t', lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def protocol_body(out, snapshot, graph, bindings, nodes, pairs, weighted):
    return {
        'format': FORMAT, 'policy': deepcopy(POLICY), 'source_bindings': bindings,
        'snapshot_sha256': snapshot['content_sha256'], 'graph_sha256': digest(graph),
        'packet_id': None, 'packet_manifest_sha256': None,
        'counts': {'requested_accessions': len(nodes), 'canonical_graph_nodes': len(graph['nodes']),
                   'unresolved_requested_accessions': sum(r['resolution_status'] != 'resolved' for r in nodes),
                   'evidence_edges': len(graph['edges']), 'retained_source_views': sum(e['source_record_count'] for e in graph['edges']),
                   'STRING_weighted_pairs': len(weighted),
                   'pruning_eligible_pairs': sum(r['pruning_eligible'] == 'true' for r in pairs),
                   'other_pairs_abstain_retain': sum(r['pruning_eligible'] != 'true' for r in pairs)},
        'files': {n: sha(out / n) for n in ('network_nodes.tsv', 'graph_pairs.tsv', 'weighted_pairs.tsv')},
        'code_sha256': {name: sha(ROOT / name) for name in (
            'scripts/prepare_ppi_pruning_graph.py', 'biograph_steward/graph.py',
            'biograph_steward/context.py', 'biograph_steward/normalization.py',
            'biograph_steward/client.py', 'biograph_steward/gold_packet.py',
            'scripts/audit_lambourne_pharos_lookup.py', 'scripts/audit_pharos_inventory.py')},
        'outcomes_loaded': False, 'scientific_improvement_measured': False,
        'new_source_requests': 0, 'model_calls': 0, 'graph_pruned': False,
    }


def checkpoint(out, body):
    value = {'format': FORMAT + '.checkpoint', 'source_protocol': body,
             'ordinary_run_files': {n: sha(out / 'ordinary_run' / n) for n in (
                 'snapshot.json', 'graph.json', 'run_manifest.json', 'review_events.json')}}
    value['content_sha256'] = digest(value)
    write_json(out / CHECKPOINT, value)


def complete_publication(output, *, progress=None, packet=True):
    """Finish the unchanged exporter after releasing the initial large objects."""
    out = Path(output)
    if (out / 'source_protocol.json').exists():
        raise ValueError('A sealed source preparation cannot be completed again.')
    saved = verify_sealed(read_json(out / CHECKPOINT))
    source_protocol = saved['source_protocol']
    if saved.get('format') != FORMAT + '.checkpoint' or source_protocol['policy'] != POLICY:
        raise ValueError('Preparation checkpoint policy differs from this executable.')
    for name, expected in saved['ordinary_run_files'].items():
        if sha(out / 'ordinary_run' / name) != expected:
            raise ValueError('Ordinary source run changed after its preparation checkpoint.')
    for name, expected in source_protocol['files'].items():
        if sha(out / name) != expected:
            raise ValueError('Prepared source table changed after checkpoint.')
    if packet:
        if progress:
            progress('Exporting and verifying existing gold-interface packet')
        manifest = export_packet(out / 'ordinary_run', out / 'gold_packet')
        if (manifest['graph_sha256'] != source_protocol['graph_sha256']
                or manifest['snapshot_sha256'] != source_protocol['snapshot_sha256']):
            raise ValueError('Exported packet differs from the checkpointed source graph.')
        source_protocol.update({'packet_id': manifest['packet_id'],
                                'packet_manifest_sha256': sha(out / 'gold_packet/packet_manifest.json')})
    # Construction hashes remain the checkpoint's historical execution record.
    # Publication can resume after an equivalent memory-lifetime fix without
    # claiming that the original graph was constructed by the newer exporter.
    source_protocol['export_stage_code_sha256'] = {name: sha(ROOT / name) for name in (
        'scripts/prepare_ppi_pruning_graph.py', 'biograph_steward/refresh.py',
        'biograph_steward/gold_packet.py', 'biograph_steward/file_utils.py')}
    source_protocol['content_sha256'] = digest(source_protocol)
    write_json(out / 'source_protocol.json', source_protocol)
    return source_protocol


def prepare(folder, audit_path, output, *, progress=None, packet=True):
    snapshot, bindings = project_snapshot(folder, audit_path, progress)
    out = new_output(output, folder, audit_path)
    if progress:
        progress('Publishing ordinary replayable evidence graph')
    graph = save_run(snapshot, out / 'ordinary_run', run_mode='offline_ppi_inventory_projection')
    nodes, pairs, weighted = pair_tables(graph, snapshot)
    table(out / 'network_nodes.tsv', nodes, NODE_FIELDS)
    table(out / 'graph_pairs.tsv', pairs, PAIR_FIELDS)
    table(out / 'weighted_pairs.tsv', weighted, WEIGHTED_FIELDS)
    checkpoint(out, protocol_body(out, snapshot, graph, bindings, nodes, pairs, weighted))
    del snapshot, graph, nodes, pairs, weighted
    gc.collect()
    return complete_publication(out, progress=progress, packet=packet)


def resume_existing(folder, audit_path, output, *, progress=None):
    """Resume only complete ordinary files; compare derived tables before reuse."""
    out = Path(output)
    if (out / 'source_protocol.json').exists() or (out / 'gold_packet').exists():
        raise ValueError('Resume requires an unsealed ordinary preparation without an existing packet.')
    if not (out / CHECKPOINT).exists():
        # The first implementation retained its initial objects during packet
        # replay. Recover that completed ordinary run without rebuilding it.
        if progress:
            progress('Checking completed ordinary snapshot and original source bindings')
        snapshot = read_json(out / 'ordinary_run/snapshot.json')
        verify_snapshot(snapshot)
        bindings = snapshot['offline_inventory_projection']['source_bindings']
        plan, source, saved, _, _, names, _ = header(folder, audit_path)
        if (bindings['lookup_audit_sha256'] != sha(audit_path)
                or bindings['headers'] != {n: sha(Path(folder) / n) for n in bindings['headers']}
                or {r['path']: r['sha256'] for r in bindings['chunks']} != saved['files']
                or any(sha(Path(folder) / n) != saved['files'][n] for n in names)):
            raise ValueError('Original source bindings changed before recovery.')
        # Preserve only small source/scope metadata while checking the saved graph.
        minimal = {'content_sha256': snapshot['content_sha256'],
                   'scope': {'resolutions': snapshot['scope']['resolutions']}}
        del snapshot
        gc.collect()
        if progress:
            progress('Checking saved graph and exact table reconstruction')
        graph = read_json(out / 'ordinary_run/graph.json')
        if graph['snapshot_sha256'] != minimal['content_sha256']:
            raise ValueError('Saved graph snapshot binding differs.')
        nodes, pairs, weighted = pair_tables(graph, minimal)
        for name, rows, fields in (('network_nodes.tsv', nodes, NODE_FIELDS),
                                   ('graph_pairs.tsv', pairs, PAIR_FIELDS),
                                   ('weighted_pairs.tsv', weighted, WEIGHTED_FIELDS)):
            stream = io.StringIO(newline='')
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t', lineterminator='\n', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
            if hashlib.sha256(stream.getvalue().encode()).hexdigest() != sha(out / name):
                raise ValueError('Existing source table does not reproduce from the saved graph.')
        checkpoint(out, protocol_body(out, minimal, graph, bindings, nodes, pairs, weighted))
        del graph, minimal, nodes, pairs, weighted
        gc.collect()
    return complete_publication(out, progress=progress)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retrieval', type=Path, required=True)
    parser.add_argument('--lookup-audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-packet', action='store_true', help='Prepare the ordinary run/tables without the additional packet export.')
    parser.add_argument('--resume-existing', action='store_true', help='Complete an unsealed ordinary preparation without rebuilding or replacing its saved source files.')
    args = parser.parse_args()
    if args.resume_existing:
        if args.no_packet:
            parser.error('--resume-existing completes the packet; do not combine with --no-packet.')
        result = resume_existing(args.retrieval, args.lookup_audit, args.output,
                                 progress=lambda s: print(s, flush=True))
    else:
        result = prepare(args.retrieval, args.lookup_audit, args.output,
                         progress=lambda s: print(s, flush=True), packet=not args.no_packet)
    print(json.dumps({'output': str(args.output), 'counts': result['counts'], 'source_protocol_sha256': result['content_sha256']}))


if __name__ == '__main__':
    main()
