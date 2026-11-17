"""Pathway-only source capture for an already frozen metadata-only cohort.

Reuse the existing explicit-inventory transport, pagination, recorded-client
replay and ordinary protein-cohort/Gold formats. Failed or incomplete required
source makes the whole comparison UNKNOWN; missing records are never replaced
or silently turned into zero features. This module opens no fitness values.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import PharosClient, PharosError, VERSION, LICENSES, SCHEMA_SOURCE, digest, utcnow, write_json
from biograph_steward.construction import _RecordedClient
from biograph_steward.graph import UNIPROT, save_run, verify_snapshot
from biograph_steward import gold_packet
from biograph_steward.file_utils import new_output, sha
from biograph_steward.retrieval import MAX_LIMITS
from scripts.retrieve_pharos_inventory import build_chunk, verify_sealed

FORMAT = 'biograph-steward.prospective-pathway-source-capture.v1'
PLAN = 'biograph-steward.prospective-pathway-source-plan.v1'
LIMITS = {k: 5000 if k == 'pathways' else 0 for k in MAX_LIMITS}


def need(ok, message):
    if not ok:
        raise ValueError('Prospective pathway source: ' + message)


def sample_frame(directory, expected_content_sha256):
    from tools.coessentiality_transfer.sample import verify
    return verify(directory, expected_content_sha256=expected_content_sha256)


def code_pins():
    names = ['tools/coessentiality_feasibility/transfer_source.py', 'scripts/retrieve_pharos_inventory.py']
    names += ['biograph_steward/' + x + '.py' for x in ('client', 'retrieval', 'construction', 'graph',
              'context', 'normalization', 'assertions', 'questions', 'benchmark', 'gold_packet', 'file_utils')]
    sampler = 'tools/coessentiality_transfer/sample.py'
    if (ROOT / sampler).is_file():
        names.append(sampler)
    return {name: sha(ROOT / name) for name in names}


def replay_chunk(chunk, ids, all_ids, expected_version):
    """Rerun the unchanged adapter against its exact recorded exchanges only."""
    verify_sealed(chunk)
    need(chunk['requested_uniprots'] == ids and chunk['endpoint']
         and chunk['db_version_before'] == chunk['db_version_after'] == expected_version,
         'chunk accession/version scope differs.')
    recorded = _RecordedClient({'endpoint': chunk['endpoint'], 'requests': chunk['requests']})
    recorded.transport = object() if chunk['transport_kind'] == 'injected_test' else None
    replayed = build_chunk(recorded, ids, all_ids, expected_version, limits=LIMITS)
    ignored = {'created_at', 'content_sha256'}
    need({k: v for k, v in replayed.items() if k not in ignored}
         == {k: v for k, v in chunk.items() if k not in ignored}
         and len(recorded.records) == len(chunk['requests']), 'source chunk does not replay exactly.')


def coverage_ledger(selected, chunks):
    """Keep every frozen gene, distinguishing unavailable source from valid0."""
    resolution, coverage, targets = {}, {}, {}
    for chunk in chunks:
        for row in chunk['target_resolution']:
            need(row['requested_uniprot'] not in resolution, 'a requested product was captured twice.')
            resolution[row['requested_uniprot']] = row
        for row in (chunk['retrieval_coverage'] or {}).get('targets', []):
            coverage[(row['uniprot'], row['family'])] = row
        for row in chunk['targets']:
            targets[row['uniprot']] = row
    result = []
    for selected_row in selected:
        uid = selected_row['accession']
        resolved, scope = resolution.get(uid), coverage.get((uid, 'pathways'))
        complete = (resolved is not None and resolved['status'] == 'resolved'
            and (resolved['returned'] or {}).get('uniprot') == uid and scope is not None
            and scope['status'] == 'complete' and not scope['issues']
            and scope['available'] == scope['retrieved'] == scope['retained']
            and scope['excluded_by_scope'] == 0)
        wiki_rows = (sum(p.get('type') == 'WikiPathways' for p in targets[uid]['pathways'])
                     if complete else None)
        result.append({'ncbi_gene_id': selected_row['ncbi_gene_id'], 'accession': uid,
            'subject': selected_row['subject'], 'identity_status': resolved['status'] if resolved else 'not_captured',
            'pathway_coverage_status': scope['status'] if scope else 'not_captured',
            'pathway_issues': deepcopy(scope['issues']) if scope else ['required_source_unavailable'],
            'available_pathway_rows': scope['available'] if scope else None,
            'retrieved_pathway_rows': scope['retrieved'] if scope else None,
            'WikiPathways_rows': wiki_rows, 'required_source_complete': bool(complete),
            'complete_zero_Wiki_context': complete and wiki_rows == 0,
            'missing_source_imputed_as_zero': False, 'sample_replaced': False})
    return result


def assemble(selected, chunks, source, plan):
    """Adapt the established chunk-to-ordinary-snapshot locator rebasing."""
    ids = [r['accession'] for r in selected]
    ledger = coverage_ledger(selected, chunks)
    need(all(r['required_source_complete'] for r in ledger), 'required source is UNKNOWN; no graph may be published.')
    requests, targets, resolutions, coverage_rows = deepcopy(source['requests']), [], [], []
    families = {family: {'retrieved': 0, 'retained': 0, 'excluded_by_scope': 0,
        'available': 0, 'target_statuses': Counter()} for family in LIMITS}
    template = None
    for chunk in chunks:
        replay_chunk(chunk, chunk['requested_uniprots'], ids, source['db_version'])
        offset = len(requests)
        for row in chunk['target_resolution']:
            record = deepcopy(row)
            record['returned_uniprot'] = (record['returned'] or {}).get('uniprot')
            record['request_index'] += offset
            resolutions.append(record)
        coverage = chunk['retrieval_coverage']
        for row in coverage['targets']:
            record = deepcopy(row)
            for page in record['pages']:
                page['request_index'] += offset
            coverage_rows.append(record)
        for family, row in coverage['summary'].items():
            total = families[family]
            for field in ('retrieved', 'retained', 'excluded_by_scope'):
                total[field] += row[field]
            total['available'] = (None if total['available'] is None or row['available'] is None
                                  else total['available'] + row['available'])
            total['target_statuses'].update(row['target_statuses'])
        targets += deepcopy(chunk['targets'])
        requests += deepcopy(chunk['requests'])
        template = template or coverage
    need([r['requested_uniprot'] for r in resolutions] == ids, 'the complete frozen gene/product order differs.')
    context = {k: deepcopy(v) for k, v in template.items() if k not in {'targets', 'summary', 'scope'}}
    context.update({'targets': coverage_rows, 'summary': families,
        'rows_retrieved': sum(c['retrieval_coverage']['rows_retrieved'] for c in chunks),
        'row_budget': sum(c['retrieval_coverage']['row_budget'] for c in chunks),
        'scope': {**deepcopy(template['scope']), 'seed_uniprots': ids, 'ppi_cohort_uniprots': ids},
        'not_requested_for_this_capture': [k for k in LIMITS if k != 'pathways']})
    snapshot = {'snapshot_format': 'biograph-steward.pharos.v1', 'data_kind': source['data_kind'],
        'created_at': source['created_at'], 'endpoint': source['endpoint'], 'db_version': source['db_version'],
        'disease': None, 'scope': {'kind': 'protein_cohort', 'name': 'Frozen metadata-only unseen-gene pathway cohort',
            'requested_uniprot': ids, 'resolutions': resolutions}, 'targets': targets, 'requests': requests,
        'source_licenses': deepcopy(source['licenses']),
        'schema_check': {'status': 'actual_schema_preflight_and_successful_saved_queries', 'schema_source': SCHEMA_SOURCE,
                         'preflight_content_sha256': plan['capability_content_sha256']},
        'query_settings': {'profile': 'pathways_only', 'context_limits': LIMITS,
            'accessions': ids, 'identity_policy': 'exact_no_alias_substitution'},
        'retrieval': {'requested_targets': len(ids), 'records_retrieved': len(targets),
                      'unresolved_targets': 0, 'context': context},
        'offline_inventory_projection': {'format': FORMAT, 'plan_content_sha256': plan['content_sha256'],
            'sample_content_sha256': plan['sample_content_sha256'], 'outcome_values_loaded': False},
        'warnings': ['Only pathway rows were retrieved; all other annotation families are explicitly unretrieved.',
            'The frozen gene sample has no replacements. Complete zero Wiki context is distinct from unavailable source.',
            'Pathway annotations remain candidates; source membership is not independent biological truth.',
            'Same historical pan-cancer experimental study will be reused; this is not an independent-study validation.',
            'Counts and version checks do not establish a transactionally atomic upstream snapshot.']}
    snapshot['content_sha256'] = digest(snapshot)
    verify_snapshot(snapshot)
    return snapshot


def capture(sample_directory, expected_sample_seal, output, *, capability_report,
            capability_file_sha256, chunk_size=25, client_factory=None):
    """Capture source only; no reference values, biological scoring or fitting."""
    implementations = code_pins()
    sample_directory, capability_report = Path(sample_directory), Path(capability_report)
    sample_report, _, selected = sample_frame(sample_directory, expected_sample_seal)
    need(sample_report['content_sha256'] == expected_sample_seal and selected, 'sample seal differs or sample is empty.')
    ids = [row['accession'] for row in selected]
    need(len(set(ids)) == len(ids) and len({r['ncbi_gene_id'] for r in selected}) == len(selected)
         and all(UNIPROT.fullmatch(uid) and '-' not in uid for uid in ids)
         and all(row['subject'] == 'UniProtKB:' + row['accession'] for row in selected),
         'frozen sample requires distinct exact canonical gene/product relationships.')
    need(type(chunk_size) is int and 1 <= chunk_size <= 25, 'use bounded chunks of1–25 products.')
    need(sha(capability_report) == capability_file_sha256, 'capability metadata pin differs.')
    capability = json.loads(capability_report.read_bytes())
    need(capability.get('content_sha256') == digest({k: v for k, v in capability.items() if k != 'content_sha256'})
         and capability.get('all_required_capabilities_present') is True
         and capability.get('sample_IDs_queried') is False and capability.get('outcome_data_opened') is False,
         'actual metadata-only source capability must be verified before sample retrieval.')
    out = new_output(output, sample_directory, capability_report)
    plan = {'format': PLAN, 'created_at': utcnow(), 'sample_content_sha256': expected_sample_seal,
        'sample_directory': str(sample_directory.resolve()),
        'sample_report_file_sha256': sha(sample_directory / 'report.json'), 'gene_count': len(selected),
        'accessions': ids, 'capability_content_sha256': capability['content_sha256'],
        'capability_file_sha256': capability_file_sha256, 'database_version': capability['version_after'],
        'endpoint': capability['endpoint'], 'limits': LIMITS, 'chunk_size': chunk_size,
        'native_HTTP_attempt_budget': 400, 'implementation_sha256': implementations,
        'source_failure_policy': 'ANY required identity/pathway/count/version failure makes WHOLE comparison UNKNOWN before reference values.',
        'other_families_requested': False, 'sample_replacements_allowed': False, 'outcome_values_opened': False}
    plan['content_sha256'] = digest(plan)
    write_json(out / 'plan.json', plan)
    write_json(out / 'frozen_sample_binding.json', {'report': sample_report, 'selected': selected})
    write_json(out / 'capability.json', capability)
    native_attempts = 0
    def observe(event):
        nonlocal native_attempts
        if event['phase'] == 'started':
            if native_attempts >= plan['native_HTTP_attempt_budget']:
                raise PharosError('Native HTTP attempt budget exhausted; source remains UNKNOWN.')
            native_attempts += 1
        with (out / 'native_http_attempts.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event, ensure_ascii=True, allow_nan=False) + '\n')
            handle.flush()
    def client():
        return (client_factory() if client_factory else PharosClient(endpoint=plan['endpoint'], cache_dir=out / 'responses',
            timeout=45, retries=1, refresh=True, attempt_observer=observe))
    chunks, source, failure = [], None, None
    active = client()
    try:
        version = active.execute(VERSION, cache=False).get('dbVersion')
        licenses = active.execute(LICENSES, cache=False).get('dataSourceCounts')
        need(version == plan['database_version'] and isinstance(licenses, list), 'source version or licence catalogue differs.')
        source = {'db_version': version, 'licenses': licenses, 'endpoint': active.endpoint, 'created_at': utcnow(),
            'requests': deepcopy(active.records), 'data_kind': 'synthetic_demo' if active.transport else 'live_pharos'}
        write_json(out / 'source_header.json', source)
        for offset in range(0, len(ids), chunk_size):
            active = client()
            chunk = build_chunk(active, ids[offset:offset + chunk_size], ids, version, limits=LIMITS)
            replay_chunk(chunk, ids[offset:offset + chunk_size], ids, version)
            write_json(out / 'chunks' / f'{offset:05d}.json', chunk)
            chunks.append(chunk)
    except Exception as exc:
        failure = {'error_type': type(exc).__name__, 'error': str(exc), 'successful_requests': deepcopy(active.records)}
        write_json(out / 'source_failure.json', failure)
    ledger = coverage_ledger(selected, chunks)
    ready = failure is None and all(r['required_source_complete'] for r in ledger)
    write_json(out / 'source_coverage.json', ledger)
    if ready:
        snapshot = assemble(selected, chunks, source, plan)
        graph = save_run(snapshot, out / 'ordinary_run', run_mode='prospective_pathways')
        need(all(e.get('retrieval_provenance', {}).get('source_responses') for e in graph['edges']),
             'a pathway edge lacks exact raw response provenance.')
        packet = gold_packet.export_packet(out / 'ordinary_run', out / 'source_packet')
        need(gold_packet.load_packet(out / 'source_packet')[0] == packet, 'ordinary Gold source does not replay.')
    else:
        packet = None
    sample_frame(sample_directory, expected_sample_seal)
    need(code_pins() == implementations and sha(capability_report) == capability_file_sha256,
         'source implementation or capability changed during capture.')
    report = {'format': FORMAT, 'created_at': utcnow(), 'plan_content_sha256': plan['content_sha256'],
        'sample_content_sha256': expected_sample_seal, 'sample_gene_count': len(selected),
        'database_version': plan['database_version'], 'source_ready_for_comparison': ready,
        'whole_comparison_status': 'SOURCE_READY_REFERENCE_STILL_BLOCKED' if ready else 'UNKNOWN_REQUIRED_SOURCE',
        'required_source_complete_genes': sum(r['required_source_complete'] for r in ledger),
        'unknown_required_source_genes': sum(not r['required_source_complete'] for r in ledger),
        'complete_zero_Wiki_context_genes': sum(r['complete_zero_Wiki_context'] for r in ledger),
        'observed_WikiPathways_rows_from_complete_source': sum(r['WikiPathways_rows'] for r in ledger
                                                             if r['WikiPathways_rows'] is not None),
        'missing_source_imputed_as_zero': False, 'sample_replacements': 0,
        'other_families_retrieved': False, 'outcome_values_opened': False,
        'model_or_GPU_calls': 0, 'native_HTTP_attempts': native_attempts,
        'source_graph_exported': packet is not None, 'source_packet_id': packet['packet_id'] if packet else None,
        'source_graph_file_sha256': sha(out / 'source_packet/source/graph.json') if packet else None,
        'native_history_qualification_or_reference_capture_authorized_by_this_report': False,
        'files': {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()}}
    report['content_sha256'] = digest(report)
    write_json(out / 'report.json', report)
    return report


def verify_capture(directory, expected_content_sha256=None):
    """Rebind source-only evidence and ordinary Gold offline; never fetch."""
    directory = Path(directory)
    need(directory.is_dir() and not directory.is_symlink()
         and not any(p.is_symlink() for p in directory.rglob('*')), 'ordinary nonsymlink source files required.')
    report = verify_sealed(json.loads((directory / 'report.json').read_bytes()))
    need(report['format'] == FORMAT and (expected_content_sha256 is None
         or report['content_sha256'] == expected_content_sha256), 'source report format/seal differs.')
    need(report['files'] == {p.relative_to(directory).as_posix(): sha(p)
         for p in directory.rglob('*') if p.is_file() and p != directory / 'report.json'},
         'source file inventory differs.')
    plan = verify_sealed(json.loads((directory / 'plan.json').read_bytes()))
    need(plan['content_sha256'] == report['plan_content_sha256'] and plan['limits'] == LIMITS
         and plan['implementation_sha256'] == code_pins() and plan['format'] == PLAN
         and all(plan[k] is False for k in ('other_families_requested', 'sample_replacements_allowed', 'outcome_values_opened')),
         'source plan/profile/implementation differs.')
    capability = verify_sealed(json.loads((directory / 'capability.json').read_bytes()))
    need(sha(directory / 'capability.json') == plan['capability_file_sha256']
         and capability['content_sha256'] == plan['capability_content_sha256']
         and capability['all_required_capabilities_present'] is True
         and capability['sample_IDs_queried'] is False and capability['outcome_data_opened'] is False
         and capability['endpoint'] == plan['endpoint']
         and capability['version_before'] == capability['version_after'] == plan['database_version'],
         'copied capability is not bound to the declared source endpoint/version/profile.')
    sample, _, selected = sample_frame(plan['sample_directory'], plan['sample_content_sha256'])
    binding = json.loads((directory / 'frozen_sample_binding.json').read_bytes())
    need(binding == {'report': sample, 'selected': selected}
         and sha(Path(plan['sample_directory']) / 'report.json') == plan['sample_report_file_sha256'],
         'source sample binding differs.')
    ids = [r['accession'] for r in selected]
    chunks = []
    for offset in range(0, len(ids), plan['chunk_size']):
        path = directory / 'chunks' / f'{offset:05d}.json'
        if path.is_file():
            chunk = json.loads(path.read_bytes())
            replay_chunk(chunk, ids[offset:offset + plan['chunk_size']], ids, plan['database_version'])
            chunks.append(chunk)
    ledger = coverage_ledger(selected, chunks)
    need(ledger == json.loads((directory / 'source_coverage.json').read_bytes())
         and report['sample_gene_count'] == len(selected)
         and report['sample_content_sha256'] == sample['content_sha256']
         and report['required_source_complete_genes'] == sum(r['required_source_complete'] for r in ledger)
         and report['unknown_required_source_genes'] == sum(not r['required_source_complete'] for r in ledger)
         and report['complete_zero_Wiki_context_genes'] == sum(r['complete_zero_Wiki_context'] for r in ledger)
         and report['observed_WikiPathways_rows_from_complete_source'] == sum(r['WikiPathways_rows'] for r in ledger
                                                                           if r['WikiPathways_rows'] is not None)
         and all(report[k] is False for k in ('missing_source_imputed_as_zero', 'other_families_retrieved',
             'outcome_values_opened', 'native_history_qualification_or_reference_capture_authorized_by_this_report'))
         and report['sample_replacements'] == 0 and report['model_or_GPU_calls'] == 0
         and report['database_version'] == plan['database_version'], 'source coverage/population interpretation differs.')
    ready = not (directory / 'source_failure.json').exists() and all(r['required_source_complete'] for r in ledger)
    need(report['source_ready_for_comparison'] is ready and report['source_graph_exported'] is ready
         and report['whole_comparison_status'] == ('SOURCE_READY_REFERENCE_STILL_BLOCKED' if ready else 'UNKNOWN_REQUIRED_SOURCE'),
         'incomplete source cannot become a ready graph.')
    if ready:
        source = json.loads((directory / 'source_header.json').read_bytes())
        header = _RecordedClient(source)
        need(header.execute(VERSION, cache=False).get('dbVersion') == source['db_version'] == plan['database_version']
             and header.execute(LICENSES).get('dataSourceCounts') == source['licenses']
             and len(header.records) == len(source['requests']) and source['endpoint'] == plan['endpoint'],
             'source header does not replay its version/catalogue exchanges.')
        snapshot = assemble(selected, chunks, source, plan)
        need(snapshot == json.loads((directory / 'ordinary_run/snapshot.json').read_bytes()),
             'ordinary snapshot does not replay from source chunks.')
        packet, _ = gold_packet.load_packet(directory / 'source_packet')
        need(packet['packet_id'] == report['source_packet_id']
             and sha(directory / 'source_packet/source/graph.json') == report['source_graph_file_sha256']
             == sha(directory / 'ordinary_run/graph.json')
             and snapshot == json.loads((directory / 'source_packet/source/snapshot.json').read_bytes()),
             'Gold source packet differs.')
    else:
        need(not (directory / 'ordinary_run').exists() and not (directory / 'source_packet').exists(),
             'UNKNOWN source must not publish a learner-ready graph.')
    return report, selected, ledger


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True, type=Path)
    parser.add_argument('--sample-seal', required=True)
    parser.add_argument('--capability', required=True, type=Path)
    parser.add_argument('--capability-sha256', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = capture(args.sample, args.sample_seal, args.out, capability_report=args.capability,
                     capability_file_sha256=args.capability_sha256)
    print(result['content_sha256'], result['whole_comparison_status'])
