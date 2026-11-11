#!/usr/bin/env python3
"""One fixed archived-STRING temporal control on consumed assay nominations.

Adapts the existing sealed capture workflow to the documented STRING 12.0
native views. Original 12.5 implementation and packets remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
from biograph_steward.assay_attachment import _ordinary, _sealed
from biograph_steward.client import utcnow, write_json
from biograph_steward.evidence_overlap import _source_files
from biograph_steward.file_utils import new_output, sha
from biograph_steward.string_temporal import parse_mapping, parse_network, project_predictions
import run_string_component as original

read, need, seal = original.read, original.need, original.seal
PROTOCOL_FORMAT = 'biograph-steward.string-temporal-protocol.v1'
CAPTURE_FORMAT = 'biograph-steward.string-temporal-capture.v1'
BASE = 'https://version-12-0.string-db.org/api/tsv/'
VIEWS = ('functional', 'physical')
RULES = {**{key: original.RULES[key] for key in (
    'species', 'mapping_batch_size', 'candidate_batch_size', 'mapping_api',
    'mapping_echo_query', 'mapping_resolution', 'network_api', 'required_score',
    'add_nodes', 'minimum_request_interval_seconds', 'timeout_seconds',
    'max_attempts_per_request', 'max_body_bytes', 'max_total_body_bytes',
    'retry_statuses', 'rate_limit_response', 'ranking_unranked_sentinel',
    'primary', 'assay_eligible', 'candidate_pairs', 'accessions', 'sklearn',
    'scoring_python', 'no_threshold_tuning', 'study_independence_established')},
    'source_version': '12.0', 'network_types': list(VIEWS),
    'network_flavor': 'native_separate_requests_not_typed_overlay',
    'secondary': 'jointly_numeric_within_12_0_actual_denominator',
    'max_logical_requests': 291, 'max_http_attempts': 873,
    'reference_status': 'consumed_development',
    'version_sweep': False, 'threshold_sweep': False,
    'physical_subset_required': False,
    'selection': 'Post-result temporal development control; fixed 2023 source versus later assay-panel selection.'}
CODE = (*original.CODE, 'biograph_steward/string_temporal.py',
        'scripts/run_string_temporal.py', 'scripts/score_string_temporal.py')
METHOD_SOURCE = 'docs/evaluations/string_reference_independence_20261027_summary.json'


def implementation():
    return {name: sha(ROOT / name) for name in CODE}


def mapping_plan(accessions):
    return [{'batch_id': 'mapping_%04d' % (i + 1), 'accessions': items}
            for i, items in enumerate(original.chunks(accessions, RULES['mapping_batch_size']))]


def network_plan(candidates, mappings):
    # Same fixed 25-nomination plan as the completed comparison; no outcomes
    # or current/archived native scores participate in request selection.
    return original.network_plan(candidates, mappings)


def validate_protocol(folder):
    folder = Path(folder).absolute()
    protocol = read(folder / 'protocol.json')
    need(_sealed(protocol) and protocol.get('format') == PROTOCOL_FORMAT,
         'Temporal protocol seal/format differs.')
    need(protocol.get('rules') == RULES and protocol.get('implementation_sha256') == implementation(),
         'Temporal rules or actual implementation changed.')
    need(_source_files(folder) == {**protocol['files'], 'protocol.json': sha(folder / 'protocol.json')},
         'Temporal protocol inventory differs.')
    reference = original.verify_capture(folder / 'reference_capture')
    need(reference['report']['content_sha256'] == protocol['reference_capture_sha256'],
         'Original consumed reference capture changed.')
    files = {
        'candidates': reference['candidates'], 'label_rows': reference['label_rows'],
        'reference_predictions': reference['predictions'],
        'accessions': original.read(folder / 'reference_capture/protocol/accessions.json')['uniprot_accessions']}
    need(len(files['candidates']) == RULES['candidate_pairs']
         and len(files['accessions']) == RULES['accessions']
         and sum(row['assay_eligible'] for row in files['candidates']) == RULES['assay_eligible']
         and files['accessions'] == sorted({p for row in files['candidates'] for p in row['products']})
         and protocol['mapping_plan'] == mapping_plan(files['accessions']),
         'Fixed population or mapping plan differs.')
    return protocol, files


def freeze(reference_capture, output):
    reference_capture = Path(reference_capture).absolute()
    reference = original.verify_capture(reference_capture)
    # Validate unchanged constructs, labels and exposure flags through the
    # established scorer before freezing new source access.
    import score_string_component as scorer
    scorer._validate_join(reference['candidates'], reference['label_rows'], reference['predictions'])
    method = read(ROOT / METHOD_SOURCE)
    need(method['next_control']['source'] == 'Archived STRING12.0'
         and method['new_assay_outcome_files_opened'] == 0, 'Expected the recorded temporal decision.')
    out = new_output(output, reference_capture)
    shutil.copytree(reference_capture, out / 'reference_capture')
    (out / 'method_decision.json').write_bytes(_ordinary(ROOT / METHOD_SOURCE))
    accessions = read(out / 'reference_capture/protocol/accessions.json')['uniprot_accessions']
    protocol = seal({'format': PROTOCOL_FORMAT, 'created_at': utcnow(), 'rules': RULES,
        'implementation_sha256': implementation(), 'mapping_plan': mapping_plan(accessions),
        'reference_capture_sha256': reference['report']['content_sha256'],
        'reference_already_consumed': True, 'cohort_source_access_before_freeze': False,
        'known_pair_capability_probe_preceded_freeze': True,
        'source_reuse_limit': 'Temporal development control, not unseen confirmation, novel-pair evaluation or a Steward-specific intervention.',
        'files': _source_files(out)})
    write_json(out / 'protocol.json', protocol)
    validate_protocol(out)
    return protocol


def parameters(kind, identifiers):
    if kind == 'version':
        need(not identifiers, 'Version request cannot contain proteins.')
        return {}
    result = {'identifiers': '\r'.join(identifiers), 'species': str(RULES['species']),
              'caller_identity': 'biograph-steward'}
    if kind == 'mapping':
        result['echo_query'] = '1'
    else:
        need(kind in VIEWS, 'Unsupported native network view.')
        result.update({'network_type': kind, 'required_score': str(RULES['required_score']),
                       'add_nodes': str(RULES['add_nodes'])})
    return result


def request_url(kind, identifiers):
    method = 'version' if kind == 'version' else RULES['mapping_api' if kind == 'mapping' else 'network_api']
    params = parameters(kind, identifiers)
    return BASE + method + ('?' + urlencode(params) if params else ''), params


def parse_version(raw):
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8')), delimiter='\t'))
    need(rows == [['string_version', 'stable_address'],
                  ['12.0', 'https://version-12-0.string-db.org']],
         'Archived endpoint version response differs.')
    return {'string_version': '12.0', 'stable_address': 'https://version-12-0.string-db.org'}


class CaptureClient:
    """Version-specific adaptation of the existing bounded HTTP capture."""
    def __init__(self, output):
        self.output = Path(output)
        self.last_start = 0.0
        self.total_bytes = 0
        self.attempt_count = 0

    def fetch(self, kind, batch_id, identifiers):
        url, params = request_url(kind, identifiers)
        for attempt in range(1, RULES['max_attempts_per_request'] + 1):
            self.attempt_count += 1
            need(self.attempt_count <= RULES['max_http_attempts'], 'HTTP attempt cap exceeded.')
            time.sleep(max(0, RULES['minimum_request_interval_seconds'] - (time.monotonic() - self.last_start)))
            self.last_start = time.monotonic()
            started, body, error = utcnow(), b'', None
            status, headers, final_url = None, {}, None
            try:
                request = Request(url, headers={'User-Agent': 'BioGraph-Steward/0.8 temporal-control',
                                                'Accept-Encoding': 'identity'})
                with urlopen(request, timeout=RULES['timeout_seconds']) as response:
                    status, headers, final_url = response.status, dict(response.headers), response.url
                    body = response.read(RULES['max_body_bytes'] + 1)
                need(status == 200 and final_url == url, 'Pinned request status or URL differs.')
                need(len(body) <= RULES['max_body_bytes'], 'Response exceeds body cap.')
                original.check_response_headers(headers, body)
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
            need(len(body) <= RULES['max_body_bytes'] and self.total_bytes <= RULES['max_total_body_bytes'],
                 'Provider response/total byte cap exceeded.')
            if error is None:
                return body, prefix + '.json'
            if status not in (None, *RULES['retry_statuses']) or attempt == RULES['max_attempts_per_request']:
                raise ValueError('Provider request failed; no absent-score imputation: ' + error)
            time.sleep(2 * attempt)


def verified_response(folder, name, kind, batch_id, identifiers):
    need(isinstance(name, str) and Path(name).name == name and name.endswith('.json'), 'Unsafe receipt name.')
    receipt = read(folder / 'responses' / name)
    url, params = request_url(kind, identifiers)
    need(receipt.get('status') == 200 and receipt.get('error') is None
         and receipt.get('kind') == kind and receipt.get('batch_id') == batch_id
         and receipt.get('parameters') == params and receipt.get('url') == receipt.get('final_url') == url,
         'Captured native request/status binding differs.')
    body_name = receipt['body_file']
    need(Path(body_name).name == body_name, 'Unsafe provider body path.')
    raw = _ordinary(folder / 'responses' / body_name)
    need(len(raw) == receipt['body_bytes'] <= RULES['max_body_bytes']
         and hashlib.sha256(raw).hexdigest() == receipt['body_sha256'], 'Captured response changed.')
    original.check_response_headers(receipt['headers'], raw)
    return raw


def parsed_capture(folder, protocol, files, requests):
    mappings, networks = {}, {view: {} for view in VIEWS}
    expected = ['source_version']
    need('source_version' in requests, 'Captured archive version is missing.')
    version = parse_version(verified_response(folder, requests['source_version'], 'version', 'source_version', []))
    for batch in protocol['mapping_plan']:
        batch_id = batch['batch_id']
        need(batch_id in requests, 'Mapping receipt is missing.')
        raw = verified_response(folder, requests[batch_id], 'mapping', batch_id, batch['accessions'])
        mappings.update(parse_mapping(raw, batch['accessions']))
        expected.append(batch_id)
    batches = network_plan(files['candidates'], mappings)
    for batch in batches:
        if not batch['string_ids']:
            continue
        for view in VIEWS:
            batch_id = view + '_' + batch['batch_id']
            need(batch_id in requests, 'Native-view response is missing.')
            raw = verified_response(folder, requests[batch_id], view, batch_id, batch['string_ids'])
            networks[view][batch['batch_id']] = parse_network(raw, batch['string_ids'])
            expected.append(batch_id)
    need(set(requests) == set(expected), 'Unplanned or omitted native request.')
    predictions = project_predictions(files['candidates'], mappings, networks, batches)
    return version, mappings, batches, predictions


def audit_attempts(folder, requests):
    groups, body_files, total_bytes = {}, set(), 0
    for path in sorted((folder / 'responses').glob('*.json')):
        receipt = read(path)
        batch_id, attempt = receipt['batch_id'], receipt['attempt']
        need(batch_id in requests and type(attempt) is int and 1 <= attempt <= RULES['max_attempts_per_request'],
             'Unexpected captured transport attempt.')
        need(path.name == batch_id + '_attempt_%02d.json' % attempt, 'Attempt receipt name differs.')
        body_name = receipt['body_file']
        need(body_name == batch_id + '_attempt_%02d.tsv' % attempt, 'Attempt body name differs.')
        raw = _ordinary(folder / 'responses' / body_name)
        need(len(raw) == receipt['body_bytes'] <= RULES['max_body_bytes']
             and hashlib.sha256(raw).hexdigest() == receipt['body_sha256'], 'Attempt bytes changed.')
        total_bytes += len(raw); body_files.add(body_name)
        groups.setdefault(batch_id, []).append((attempt, path.name, receipt))
    count = 0
    for batch_id, rows in groups.items():
        rows.sort()
        need([row[0] for row in rows] == list(range(1, len(rows) + 1)) and rows[-1][1] == requests[batch_id],
             'Transport sequence differs.')
        last = rows[-1][2]
        for _, _, prior in rows[:-1]:
            need(prior['error'] is not None and prior['status'] in (None, *RULES['retry_statuses'])
                 and prior['url'] == last['url'] and prior['parameters'] == last['parameters']
                 and prior['kind'] == last['kind'], 'Unpermitted or changed retry.')
        count += len(rows)
    need(set(groups) == set(requests)
         and {p.name for p in (folder / 'responses').glob('*.tsv')} == body_files
         and len(requests) <= RULES['max_logical_requests'] and count <= RULES['max_http_attempts']
         and total_bytes <= RULES['max_total_body_bytes'], 'Transport accounting differs.')
    return count, total_bytes


def capture(protocol_dir, output):
    protocol_dir = Path(protocol_dir).absolute()
    protocol, files = validate_protocol(protocol_dir)
    marker = protocol_dir.with_name(protocol_dir.name + '_predictor_access.json')
    need(not marker.exists() and not marker.is_symlink(), 'This protocol already began access; preserve its result.')
    out = new_output(output, protocol_dir)
    with marker.open('x') as stream:
        json.dump({'started_at': utcnow(), 'protocol_sha256': protocol['content_sha256'], 'output': str(out)}, stream)
    shutil.copytree(protocol_dir, out / 'protocol'); (out / 'responses').mkdir()
    client = CaptureClient(out / 'responses')
    requests, mappings = {}, {}
    try:
        raw, name = client.fetch('version', 'source_version', [])
        version = parse_version(raw); requests['source_version'] = name
        for batch in protocol['mapping_plan']:
            raw, name = client.fetch('mapping', batch['batch_id'], batch['accessions'])
            mappings.update(parse_mapping(raw, batch['accessions']))
            requests[batch['batch_id']] = name
            print(batch['batch_id'] + ': captured', flush=True)
        batches = network_plan(files['candidates'], mappings)
        for batch in batches:
            if batch['string_ids']:
                for view in VIEWS:
                    batch_id = view + '_' + batch['batch_id']
                    raw, name = client.fetch(view, batch_id, batch['string_ids'])
                    parse_network(raw, batch['string_ids']); requests[batch_id] = name
            print(batch['batch_id'] + ': ' + ('both captured' if batch['string_ids'] else 'identity abstention'), flush=True)
        write_json(out / 'requests.json', requests)
        replay = parsed_capture(out, protocol, files, requests)
        need(replay[:3] == (version, mappings, batches), 'Capture/replay differs.')
        predictions = replay[3]
        write_json(out / 'mappings.json', mappings); write_json(out / 'network_plan.json', batches)
        write_json(out / 'predictions.json', predictions)
        report = seal({'format': CAPTURE_FORMAT, 'created_at': utcnow(), 'status': 'completed',
            'protocol_sha256': protocol['content_sha256'], 'reference_capture_sha256': protocol['reference_capture_sha256'],
            'source_version': version, 'candidate_count': len(predictions),
            'native_contrast': original.contrast(predictions), 'request_count': len(requests),
            'http_attempt_count': client.attempt_count, 'body_bytes': client.total_bytes,
            'mapping_states': dict(Counter(row['status'] for row in mappings.values())),
            'outcomes_used_to_select_requests': False, 'new_reference_outcomes_opened': False,
            'model_calls': 0, 'GPU_runs': 0, 'temporal_control_not_independent_confirmation': True,
            'files': _source_files(out)})
        write_json(out / 'report.json', report)
        verify_capture(out)
        return report
    except BaseException as exc:
        write_json(out / 'failure.json', {'status': 'stopped_without_scores', 'created_at': utcnow(),
            'error': str(exc), 'protocol_sha256': protocol['content_sha256'],
            'completed_requests': requests, 'files': _source_files(out)})
        raise


def verify_capture(folder):
    folder = Path(folder).absolute()
    report = read(folder / 'report.json')
    need(_sealed(report) and report.get('format') == CAPTURE_FORMAT and report.get('status') == 'completed',
         'Temporal capture is incomplete or changed.')
    need(_source_files(folder) == {**report['files'], 'report.json': sha(folder / 'report.json')},
         'Temporal capture inventory differs.')
    protocol, files = validate_protocol(folder / 'protocol')
    need(report['protocol_sha256'] == protocol['content_sha256']
         and report['reference_capture_sha256'] == protocol['reference_capture_sha256'],
         'Temporal source/protocol bindings differ.')
    requests = read(folder / 'requests.json')
    version, mappings, batches, predictions = parsed_capture(folder, protocol, files, requests)
    attempts, total_bytes = audit_attempts(folder, requests)
    need(report['source_version'] == version and report['http_attempt_count'] == attempts
         and report['body_bytes'] == total_bytes and report['request_count'] == len(requests)
         and report['mapping_states'] == dict(Counter(row['status'] for row in mappings.values()))
         and report['candidate_count'] == len(predictions) == RULES['candidate_pairs']
         and read(folder / 'mappings.json') == mappings and read(folder / 'network_plan.json') == batches
         and read(folder / 'predictions.json') == predictions
         and report['native_contrast'] == original.contrast(predictions), 'Temporal capture replay differs.')
    need(report.get('outcomes_used_to_select_requests') is False
         and report.get('new_reference_outcomes_opened') is False
         and report.get('model_calls') == report.get('GPU_runs') == 0
         and report.get('temporal_control_not_independent_confirmation') is True,
         'Temporal capture scientific scope differs.')
    return {**files, 'protocol': protocol, 'predictions': predictions, 'report': report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('freeze'); p.add_argument('--reference-capture', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('capture'); p.add_argument('--protocol', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('verify'); p.add_argument('--capture', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'freeze':
            result = freeze(args.reference_capture, args.out)
        elif args.command == 'capture':
            result = capture(args.protocol, args.out)
        else:
            result = verify_capture(args.capture)['report']
        print(json.dumps({key: result[key] for key in ('format', 'status', 'candidate_count', 'native_contrast', 'content_sha256') if key in result}, indent=2))
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        parser.exit(1, 'ERROR: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
