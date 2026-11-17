#!/usr/bin/env python3
"""Freeze and capture one fixed native STRING component comparison.

The original assay verifier remains in its pinned historical checkout. This
adapter preserves existing outcomes as reference bytes and never sends them
to a provider. Native scores are parsed using the official typed API contract.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
from biograph_steward.assay_attachment import _decode, _ordinary, _sealed
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.evidence_overlap import _source_files
from biograph_steward.file_utils import new_output, sha
from biograph_steward.string_component import parse_mapping, parse_network, project_predictions

PROTOCOL_FORMAT = 'biograph-steward.string-component-protocol.v1'
CAPTURE_FORMAT = 'biograph-steward.string-component-capture.v1'
BASE = 'https://version-12-5.string-db.org/api/tsv/'
CODE = ('scripts/run_string_component.py', 'scripts/score_string_component.py',
        'biograph_steward/string_component.py', 'biograph_steward/assay_attachment.py',
        'biograph_steward/client.py', 'biograph_steward/file_utils.py',
        'biograph_steward/evidence_overlap.py', 'biograph_steward/gold_packet.py')
RULES = {'species': 9606, 'mapping_batch_size': 100, 'candidate_batch_size': 25,
         'mapping_api': 'get_string_ids', 'mapping_echo_query': 1,
         'mapping_resolution': 'provider_best_match_not_exhaustive_sequence_identity',
         'network_api': 'network', 'required_score': 0, 'network_type': 'functional',
         'network_flavor': 'typed', 'typed_physical_edges': 1,
         'typed_regulatory_edges': 0, 'add_nodes': 0,
         'minimum_request_interval_seconds': 1.05, 'timeout_seconds': 60,
         'max_attempts_per_request': 3, 'max_body_bytes': 4 * 1024 * 1024,
         'max_total_body_bytes': 64 * 1024 * 1024,
         'max_logical_requests': 161, 'max_http_attempts': 483,
         'retry_statuses': [500, 502, 503, 504], 'rate_limit_response': 'stop_without_imputation',
         'ranking_unranked_sentinel': -1, 'primary': 'full_panel_average_precision_unranked_tied_last',
         'secondary': 'same_jointly_numeric_population_average_precision',
         'assay_eligible': 2676, 'candidate_pairs': 3222, 'accessions': 3173,
         'sklearn': '1.9.1', 'scoring_python': '3.12.4',
         'no_threshold_tuning': True, 'study_independence_established': False}
SOURCES = ('candidates.json', 'scope_report.json', 'accessions.json',
           'assessment_rows.json', 'assessment_report.json', 'historical_protocol.json',
           'reference_verification.json')


def seal(value):
    return {**value, 'content_sha256': digest(value)}


def read(path):
    return _decode(_ordinary(path))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def implementation():
    return {name: sha(ROOT / name) for name in CODE}


def chunks(values, size):
    return [values[i:i + size] for i in range(0, len(values), size)]


def validate_protocol(folder):
    folder = Path(folder).absolute()
    inventory = _source_files(folder)
    protocol = read(folder / 'protocol.json')
    need(_sealed(protocol) and protocol.get('format') == PROTOCOL_FORMAT,
         'Invalid component protocol content seal or format.')
    need(protocol.get('rules') == RULES and protocol.get('implementation_sha256') == implementation(),
         'Protocol rules or actual implementation changed.')
    expected = {**protocol['files'], 'protocol.json': sha(folder / 'protocol.json')}
    need(inventory == expected, 'Protocol file inventory differs.')
    files = {name: read(folder / name) for name in SOURCES}
    scope = files['scope_report.json']
    need(_sealed(scope) and scope.get('format') == 'biograph-steward.biological-comparison-scope.v1',
         'Expected the already prepared biological scope.')
    need(sha(folder / 'candidates.json') == scope['files']['candidates.json']
         and sha(folder / 'accessions.json') == scope['files']['accession_inventory.json'],
         'Candidate or accession scope changed.')
    candidates, accessions = files['candidates.json'], files['accessions.json']['uniprot_accessions']
    need(len(candidates) == RULES['candidate_pairs']
         and sum(c['assay_eligible'] is True for c in candidates) == RULES['assay_eligible']
         and len(accessions) == RULES['accessions']
         and accessions == sorted({p for c in candidates for p in c['products']}),
         'Fixed population/eligibility differs.')
    expected_mapping = [{'batch_id': 'mapping_%04d' % (i + 1), 'accessions': values}
                        for i, values in enumerate(chunks(accessions, RULES['mapping_batch_size']))]
    need(protocol['mapping_plan'] == expected_mapping, 'Mapping request plan differs.')
    result = files['assessment_report.json']
    need(_sealed(result) and result.get('outcomes_consumed_for_future_development') is True
         and sha(folder / 'assessment_rows.json') == result['files']['rows.json']
         and sha(folder / 'assessment_rows.json') == protocol['assessment_rows_sha256']
         and sha(folder / 'assessment_report.json') == protocol['assessment_report_sha256'],
         'Consumed reference bytes differ.')
    return protocol, files


def freeze(scope_dir, assessment_dir, reference_root, output):
    scope_dir, assessment_dir, reference_root = [Path(p).absolute() for p in
                                                (scope_dir, assessment_dir, reference_root)]
    scope = read(scope_dir / 'report.json')
    need(_sealed(scope), 'Scope report changed.')
    for name, fingerprint in scope['files'].items():
        need(sha(scope_dir / name) == fingerprint, 'Scope payload changed.')
    historical = read(assessment_dir / 'freeze/protocol.json')
    need(_sealed(historical) and platform.python_version() == historical['python'],
         'Historical verification requires its original Python runtime.')
    for name, fingerprint in historical['implementation_sha256'].items():
        need(sha(reference_root / name) == fingerprint, 'Historical implementation pin differs: ' + name)
    # Use the existing original verifier rather than weakening its current-tree guard.
    command = [sys.executable, str(reference_root / 'scripts/assess_lambourne_corroboration.py'),
               'verify', '--freeze', str(assessment_dir / 'freeze'), '--out', str(assessment_dir / 'results')]
    verified = subprocess.run(command, check=True, capture_output=True, text=True)
    source_paths = {'candidates.json': scope_dir / 'candidates.json',
        'scope_report.json': scope_dir / 'report.json', 'accessions.json': scope_dir / 'accession_inventory.json',
        'assessment_rows.json': assessment_dir / 'results/rows.json',
        'assessment_report.json': assessment_dir / 'results/report.json',
        'historical_protocol.json': assessment_dir / 'freeze/protocol.json'}
    for name, fingerprint in scope['source_input_sha256'].items():
        if name.startswith('assessment/'):
            need(sha(assessment_dir / name[len('assessment/'):]) == fingerprint,
                 'Scope source changed: ' + name)
    out = new_output(output, scope_dir, assessment_dir, reference_root)
    for name, path in source_paths.items():
        (out / name).write_bytes(_ordinary(path))
    write_json(out / 'reference_verification.json', {
        'command': command, 'python': platform.python_version(), 'returncode': verified.returncode,
        'stdout_sha256': hashlib.sha256(verified.stdout.encode()).hexdigest(),
        'historical_implementation_sha256': historical['implementation_sha256'],
        'reference_already_consumed': True})
    accessions = read(out / 'accessions.json')['uniprot_accessions']
    protocol = seal({'format': PROTOCOL_FORMAT, 'created_at': utcnow(), 'rules': RULES,
        'scope_report_sha256': sha(out / 'scope_report.json'),
        'assessment_rows_sha256': sha(out / 'assessment_rows.json'),
        'assessment_report_sha256': sha(out / 'assessment_report.json'),
        'implementation_sha256': implementation(),
        'mapping_plan': [{'batch_id': 'mapping_%04d' % (i + 1), 'accessions': values}
                         for i, values in enumerate(chunks(accessions, RULES['mapping_batch_size']))],
        'files': _source_files(out), 'new_predictor_access_before_freeze': False,
        'source_reuse_limit': 'Current source calibration/assay import lineage is unresolved; retrospective component only.'})
    write_json(out / 'protocol.json', protocol)
    validate_protocol(out)
    return protocol


def network_plan(candidates, mappings):
    result = []
    for i, indices in enumerate(chunks(list(range(len(candidates))), RULES['candidate_batch_size'])):
        ids = set()
        for index in indices:
            pair = [mappings[p] for p in candidates[index]['products']]
            if all(p['status'] == 'resolved' for p in pair) and pair[0]['string_id'] != pair[1]['string_id']:
                ids.update(p['string_id'] for p in pair)
        result.append({'batch_id': 'network_%04d' % (i + 1), 'candidate_indices': indices,
                       'string_ids': sorted(ids)})
    return result


def parameters(kind, identifiers):
    result = {'identifiers': '\r'.join(identifiers), 'species': str(RULES['species']),
              'caller_identity': 'biograph-steward'}
    if kind == 'mapping':
        result['echo_query'] = '1'
    else:
        result.update({key: str(RULES[key]) for key in ('required_score', 'network_type',
            'network_flavor', 'typed_physical_edges', 'typed_regulatory_edges', 'add_nodes')})
    return result


def check_response_headers(headers, body):
    # HTTP field names are case insensitive. A bounded read can return a short
    # fixed-length body, so validate framing before interpreting an absent row.
    lowered = {name.lower(): value for name, value in headers.items()}
    need(lowered.get('string-api-version') == '2', 'Provider API version differs.')
    need(lowered.get('content-type', '').lower().startswith('text/tab-separated-values'),
         'Provider response is not the supported TSV type.')
    need(lowered.get('content-encoding', 'identity').lower() == 'identity',
         'Unexpected provider content encoding.')
    length = lowered.get('content-length')
    if length is not None:
        need(isinstance(length, str) and length.isascii() and length.isdecimal()
             and int(length) == len(body), 'Provider Content-Length differs from captured bytes.')


class CaptureClient:
    """Bounded standard-library transport for the provider's documented GET API."""
    def __init__(self, output):
        self.output = output
        self.last_start = 0.0
        self.total_bytes = 0
        self.attempt_count = 0

    def fetch(self, kind, batch_id, identifiers):
        params = parameters(kind, identifiers)
        url = BASE + RULES[kind + '_api'] + '?' + urlencode(params)
        for attempt in range(1, RULES['max_attempts_per_request'] + 1):
            self.attempt_count += 1
            need(self.attempt_count <= RULES['max_http_attempts'], 'Provider HTTP attempt cap exceeded.')
            time.sleep(max(0, RULES['minimum_request_interval_seconds'] - (time.monotonic() - self.last_start)))
            self.last_start = time.monotonic()
            started = utcnow()
            body, error = b'', None
            status, headers, final_url = None, {}, None
            try:
                request = Request(url, headers={'User-Agent': 'BioGraph-Steward/0.8 source-component'})
                with urlopen(request, timeout=RULES['timeout_seconds']) as response:
                    status, headers, final_url = response.status, dict(response.headers), response.url
                    body = response.read(RULES['max_body_bytes'] + 1)
                need(status == 200, 'Provider returned a non-200 status.')
                need(final_url == url, 'Provider redirected a pinned request.')
                need(len(body) <= RULES['max_body_bytes'], 'Provider response exceeds its byte cap.')
                check_response_headers(headers, body)
            except Exception as exc:
                error = str(exc)
                if isinstance(exc, HTTPError):
                    status, headers, final_url = exc.code, dict(exc.headers), exc.url
                    body = exc.read(RULES['max_body_bytes'] + 1)
            self.total_bytes += len(body)
            prefix = batch_id + '_attempt_%02d' % attempt
            (self.output / (prefix + '.tsv')).write_bytes(body)
            receipt = {'started_at': started, 'kind': kind, 'batch_id': batch_id, 'attempt': attempt,
                'url': url, 'parameters': params, 'status': status, 'headers': headers,
                'final_url': final_url, 'error': error, 'body_file': prefix + '.tsv',
                'body_bytes': len(body), 'body_sha256': hashlib.sha256(body).hexdigest()}
            write_json(self.output / (prefix + '.json'), receipt)
            need(len(body) <= RULES['max_body_bytes'], 'Provider response exceeds its byte cap.')
            need(self.total_bytes <= RULES['max_total_body_bytes'], 'Total provider body cap exceeded.')
            if error is None:
                return body, prefix + '.json'
            # A 429 stops this capture instead of retrying before a server's
            # Retry-After window. Network/5xx retries retain every attempt.
            if status not in (None, *RULES['retry_statuses']) or attempt == RULES['max_attempts_per_request']:
                raise ValueError('Provider request failed; no missing-score imputation: ' + error)
            time.sleep(2 * attempt)


def _parsed_capture(folder, protocol, files, requests):
    mappings, networks = {}, {}
    expected_ids = []
    for batch in protocol['mapping_plan']:
        name = requests.get(batch['batch_id'])
        need(isinstance(name, str), 'Mapping response receipt is missing.')
        raw = _verified_response(folder, name, 'mapping', batch['batch_id'], batch['accessions'])
        mappings.update(parse_mapping(raw, batch['accessions']))
        expected_ids.append(batch['batch_id'])
    batches = network_plan(files['candidates.json'], mappings)
    for batch in batches:
        if not batch['string_ids']:
            continue
        name = requests.get(batch['batch_id'])
        need(isinstance(name, str), 'Network response receipt is missing.')
        raw = _verified_response(folder, name, 'network', batch['batch_id'], batch['string_ids'])
        networks[batch['batch_id']] = parse_network(raw, batch['string_ids'])
        expected_ids.append(batch['batch_id'])
    need(set(requests) == set(expected_ids), 'Unexpected or omitted captured request.')
    predictions = project_predictions(files['candidates.json'], mappings, networks, batches)
    return mappings, batches, predictions


def _verified_response(folder, name, kind, batch_id, identifiers):
    need(isinstance(name, str) and Path(name).name == name and name.endswith('.json'), 'Unsafe receipt name.')
    receipt = read(folder / 'responses' / name)
    params = parameters(kind, identifiers)
    url = BASE + RULES[kind + '_api'] + '?' + urlencode(params)
    need(receipt.get('status') == 200 and receipt.get('error') is None
         and receipt.get('kind') == kind and receipt.get('batch_id') == batch_id
         and receipt.get('parameters') == params and receipt.get('url') == receipt.get('final_url') == url,
         'Captured response request/status binding differs.')
    body_name = receipt['body_file']
    need(Path(body_name).name == body_name, 'Unsafe provider body path.')
    raw = _ordinary(folder / 'responses' / body_name)
    need(len(raw) == receipt['body_bytes'] <= RULES['max_body_bytes']
         and hashlib.sha256(raw).hexdigest() == receipt['body_sha256'],
         'Captured response integrity/type differs.')
    check_response_headers(receipt['headers'], raw)
    return raw


def contrast(predictions):
    numeric = {arm: sum(r['views'][arm]['state'] == 'numeric' for r in predictions)
               for arm in ('functional', 'physical')}
    vectors = {arm: [r['views'][arm]['ranking_score'] for r in predictions] for arm in numeric}
    return {'numeric_support': numeric,
        'ranking_input_sha256': {arm: digest(values) for arm, values in vectors.items()},
        'identical_ranking_inputs': vectors['functional'] == vectors['physical'],
        'different_ranking_values': sum(a != b for a, b in zip(vectors['functional'], vectors['physical'])),
        'different_source_states': sum(r['views']['functional']['state'] != r['views']['physical']['state'] for r in predictions)}


def audit_attempts(folder, requests):
    """Account for failed transports as well as successful logical requests."""
    groups, total_bytes = {}, 0
    for path in sorted((folder / 'responses').glob('*.json')):
        receipt = read(path)
        batch_id, attempt = receipt['batch_id'], receipt['attempt']
        need(batch_id in requests and type(attempt) is int and 1 <= attempt <= RULES['max_attempts_per_request'],
             'Unexpected captured transport attempt.')
        need(path.name == batch_id + '_attempt_%02d.json' % attempt, 'Attempt receipt name differs.')
        name = receipt['body_file']
        need(name == batch_id + '_attempt_%02d.tsv' % attempt, 'Attempt body name differs.')
        raw = _ordinary(folder / 'responses' / name)
        need(len(raw) == receipt['body_bytes'] <= RULES['max_body_bytes']
             and hashlib.sha256(raw).hexdigest() == receipt['body_sha256'], 'Attempt body changed.')
        total_bytes += len(raw)
        groups.setdefault(batch_id, []).append((attempt, path.name, receipt))
    count = 0
    for batch_id, rows in groups.items():
        rows.sort()
        need([row[0] for row in rows] == list(range(1, len(rows) + 1))
             and rows[-1][1] == requests[batch_id], 'Transport attempt sequence differs.')
        last = rows[-1][2]
        for _, _, prior in rows[:-1]:
            need(prior['error'] is not None and prior['status'] in (None, *RULES['retry_statuses'])
                 and prior['url'] == last['url'] and prior['parameters'] == last['parameters'],
                 'Unpermitted or changed transport retry.')
        count += len(rows)
    need(set(groups) == set(requests) and len(requests) <= RULES['max_logical_requests']
         and count <= RULES['max_http_attempts'] and total_bytes <= RULES['max_total_body_bytes'],
         'Transport request/byte accounting differs.')
    return count, total_bytes


def capture(protocol_dir, output):
    protocol_dir = Path(protocol_dir).absolute()
    protocol, files = validate_protocol(protocol_dir)
    marker = protocol_dir.with_name(protocol_dir.name + '_predictor_access.json')
    need(not marker.exists() and not marker.is_symlink(), 'This protocol already began predictor access; preserve its result.')
    out = new_output(output, protocol_dir)
    with marker.open('x') as stream:
        json.dump({'started_at': utcnow(), 'protocol_sha256': protocol['content_sha256'], 'output': str(out)}, stream)
    (out / 'protocol').mkdir(); (out / 'responses').mkdir()
    for name in (*SOURCES, 'protocol.json'):
        (out / 'protocol' / name).write_bytes(_ordinary(protocol_dir / name))
    client = CaptureClient(out / 'responses')
    receipts, mappings = {}, {}
    try:
        for batch in protocol['mapping_plan']:
            raw, receipt = client.fetch('mapping', batch['batch_id'], batch['accessions'])
            mappings.update(parse_mapping(raw, batch['accessions']))
            receipts[batch['batch_id']] = receipt
            print(batch['batch_id'] + ': captured', flush=True)
        batches = network_plan(files['candidates.json'], mappings)
        for batch in batches:
            if batch['string_ids']:
                raw, receipt = client.fetch('network', batch['batch_id'], batch['string_ids'])
                parse_network(raw, batch['string_ids'])
                receipts[batch['batch_id']] = receipt
            print(batch['batch_id'] + ': ' + ('captured' if batch['string_ids'] else 'identity abstention'), flush=True)
        write_json(out / 'requests.json', receipts)
        replay_mappings, replay_batches, predictions = _parsed_capture(out, protocol, files, receipts)
        need(replay_mappings == mappings and replay_batches == batches, 'Capture replay differs.')
        write_json(out / 'mappings.json', mappings)
        write_json(out / 'network_plan.json', batches)
        write_json(out / 'predictions.json', predictions)
        report = seal({'format': CAPTURE_FORMAT, 'created_at': utcnow(), 'status': 'completed',
            'protocol_sha256': protocol['content_sha256'], 'scope_report_sha256': protocol['scope_report_sha256'],
            'assessment_rows_sha256': protocol['assessment_rows_sha256'],
            'assessment_report_sha256': protocol['assessment_report_sha256'],
            'predictions_file': 'predictions.json', 'candidate_count': len(predictions),
            'native_contrast': contrast(predictions), 'request_count': len(receipts),
            'http_attempt_count': client.attempt_count,
            'mapping_states': dict(Counter(row['status'] for row in mappings.values())),
            'body_bytes': client.total_bytes, 'outcomes_used_to_select_requests': False,
            'new_reference_outcomes_opened': False, 'model_calls': 0, 'GPU_runs': 0,
            'files': _source_files(out)})
        write_json(out / 'report.json', report)
        verify_capture(out)
        return report
    except BaseException as exc:
        write_json(out / 'failure.json', {'status': 'stopped_without_scores', 'error': str(exc),
            'created_at': utcnow(), 'protocol_sha256': protocol['content_sha256'],
            'completed_requests': receipts, 'files': _source_files(out)})
        raise


def verify_capture(folder):
    folder = Path(folder).absolute()
    report = read(folder / 'report.json')
    need(_sealed(report) and report.get('format') == CAPTURE_FORMAT and report.get('status') == 'completed',
         'Capture is incomplete or changed.')
    need(_source_files(folder) == {**report['files'], 'report.json': sha(folder / 'report.json')},
         'Capture file inventory differs.')
    protocol, files = validate_protocol(folder / 'protocol')
    for key in ('scope_report_sha256', 'assessment_rows_sha256', 'assessment_report_sha256'):
        need(report.get(key) == protocol[key], 'Capture source binding differs.')
    need(report.get('protocol_sha256') == protocol['content_sha256'], 'Capture protocol differs.')
    mappings, batches, predictions = _parsed_capture(folder, protocol, files, read(folder / 'requests.json'))
    attempts, total_bytes = audit_attempts(folder, read(folder / 'requests.json'))
    need(report['http_attempt_count'] == attempts and report['body_bytes'] == total_bytes
         and report['request_count'] == len(read(folder / 'requests.json')), 'Capture transport totals differ.')
    need(read(folder / 'mappings.json') == mappings and read(folder / 'network_plan.json') == batches
         and read(folder / 'predictions.json') == predictions and report['native_contrast'] == contrast(predictions)
         and report.get('candidate_count') == len(predictions) == RULES['candidate_pairs'],
         'Native prediction replay or pre-outcome contrast differs.')
    return {'protocol': protocol, 'predictions': predictions, 'candidates': files['candidates.json'],
            'label_rows': files['assessment_rows.json'], 'report': report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('freeze')
    for name in ('scope', 'assessment', 'reference-root', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p = sub.add_parser('capture'); p.add_argument('--protocol', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('verify'); p.add_argument('--capture', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'freeze':
            result = freeze(args.scope, args.assessment, args.reference_root, args.out)
        elif args.command == 'capture':
            result = capture(args.protocol, args.out)
        else:
            result = verify_capture(args.capture)['report']
        print(json.dumps({key: result[key] for key in ('format', 'status', 'candidate_count', 'native_contrast', 'content_sha256') if key in result}, indent=2))
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, 'ERROR: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
