"""New-cohort native-column capture using the existing bounded transport reader.

No calls to the old92-gene workflow verifier or fake learner packets are made.
Capture must only run after the fixed prospective source/control review gate.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.reference_accuracy.design import need
from tools.coessentiality_transfer.prepare import verify, sealed, inventory
from tools.coessentiality_transfer.sample import verify as verify_sample
from tools.coessentiality_feasibility.matrix import _fetch, column_range, header_metadata, decode_column, validate_response

FORMAT = 'biograph-steward.prospective-gene-transfer-native-capture.v1'


def fixed_columns(report, packet):
    indices = sorted({r['native_matrix_index'] for r in packet['genes']})
    need(len(indices) == len(packet['genes']) == 128, 'fixed128 unique native columns differ')
    sm, protocol, selected = verify_sample(report['source_paths']['sample'], report['sample_content_sha256'])
    need(not (set(indices) & set(protocol['reference_exposure']['old_raw_column_indices'])), 'new columns overlap prior raw exposure')
    return indices


def capture(frozen, expected_content_sha256, output):
    frozen = Path(frozen).absolute(); report, packet = verify(frozen, expected_content_sha256)
    indices = fixed_columns(report, packet); descriptors = report['reference_metadata']
    input_pin = sha(frozen / 'report.json'); code = sha(__file__)
    out = new_output(output, frozen); (out / 'columns').mkdir()
    plan = {'created_at': utcnow(), 'frozen_source_control_content_sha256': report['content_sha256'],
        'frozen_report_file_sha256': input_pin, 'column_indices': indices, 'matrix_metadata': descriptors,
        'scope': 'previously uncaptured new-new block within same published reference; full selected columns preserved',
        'at_source_control_freeze_new_reference_values_opened': False, 'independent_study': False,
        'workers': 4, 'maximum_attempts_per_column': 3, 'implementation_sha256': code}
    plan['content_sha256'] = digest(plan); write_json(out / 'capture_plan.json', plan)
    rows = []; failures = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        for name, meta in descriptors.items():
            for index in indices:
                start, end = column_range(meta, index); path = out / 'columns' / f'{name}.column_{index:05}.bin'
                future = pool.submit(_fetch, meta['url'], meta['etag'], start, end, meta['file_bytes'], path)
                futures[future] = name, index, path
        for future in as_completed(futures):
            name, index, path = futures[future]
            try:
                receipt = future.result(); rows.append({'matrix': name, 'column': index, 'file': path.relative_to(out).as_posix(), **receipt})
            except Exception as exc:
                failures.append({'matrix': name, 'column': index, 'type': type(exc).__name__, 'error': str(exc)})
    if failures:
        write_json(out / 'failures.json', {'created_at': utcnow(), 'failures': failures,
                   'comparison_status': 'UNKNOWN_TRANSPORT_FAILURE_NOT_BIOLOGICAL_MISSINGNESS'})
        raise ValueError('Prospective reference capture incomplete; raw attempts preserved, no success report or comparison allowed.')
    verify(frozen, expected_content_sha256)
    need(sha(frozen / 'report.json') == input_pin and sha(__file__) == code, 'frozen source/code changed during numeric capture')
    result = {'format': FORMAT, 'created_at': utcnow(), 'frozen_source_control_content_sha256': report['content_sha256'],
        'frozen_report_file_sha256': input_pin, 'capture_plan_content_sha256': plan['content_sha256'],
        'column_indices': indices, 'matrix_metadata': descriptors, 'columns': sorted(rows, key=lambda r: (r['matrix'], r['column'])),
        'range_payload_total_bytes': sum(r['payload_bytes'] for r in rows), 'full_matrix_files_retrieved_or_hashed': False,
        'all_required_ranges_complete': True, 'missing_transport_imputed': False, 'independent_study_confirmation': False,
        'implementation_sha256': code, 'files': inventory(out)}
    result['content_sha256'] = digest(result); write_json(out / 'report.json', result)
    return result


def load(frozen, captured):
    frozen, captured = Path(frozen), Path(captured)
    frozen_report, packet = verify(frozen); report = sealed(captured / 'report.json')
    need(report['format'] == FORMAT and report['frozen_source_control_content_sha256'] == frozen_report['content_sha256']
         and report['frozen_report_file_sha256'] == sha(frozen / 'report.json'), 'prospective native/source binding differs')
    need(inventory(captured) == report['files'], 'prospective raw column inventory differs')
    indices = fixed_columns(frozen_report, packet); descriptors = frozen_report['reference_metadata']
    expected = {(name, index) for name in descriptors for index in indices}
    need(report['column_indices'] == indices and report['matrix_metadata'] == descriptors and
         len(report['columns']) == len(expected) and {(r['matrix'], r['column']) for r in report['columns']} == expected,
         'fixed prospective column universe omitted/repeated/changed')
    plan = sealed(captured / 'capture_plan.json')
    need(plan['content_sha256'] == report['capture_plan_content_sha256'] and
         plan['frozen_source_control_content_sha256'] == frozen_report['content_sha256'] and
         plan['column_indices'] == indices and plan['matrix_metadata'] == descriptors, 'numeric transport plan differs')
    arrays = {}
    for row in report['columns']:
        meta = descriptors[row['matrix']]
        actual = header_metadata((frozen / 'reference_headers' / (row['matrix'] + '.header')).read_bytes())
        need(all(meta[k] == v for k, v in actual.items()), 'native shape/dtype/order metadata differs')
        path = captured / row['file']; need(path.resolve().is_relative_to(captured.resolve()), 'raw range path escapes captured artifact')
        receipt = gold_packet._read(Path(str(path) + '.json'))
        need(row == {'matrix': row['matrix'], 'column': row['column'], 'file': row['file'], **receipt},
             'native range report differs from its raw transport receipt')
        raw = path.read_bytes(); start, end = column_range(meta, row['column'])
        validate_response(row['status'], row['headers'], start, end, meta['file_bytes'], meta['etag'], raw)
        need(row['request_range'] == [start, end] and row['url'] == meta['url'] and sha(path) == row['payload_sha256'],
             'prospective range source proof differs')
        arrays[(row['matrix'], row['column'])] = decode_column(raw, meta)
    need(report['all_required_ranges_complete'] is True and report['missing_transport_imputed'] is False
         and report['independent_study_confirmation'] is False and report['range_payload_total_bytes'] == sum(
             r['payload_bytes'] for r in report['columns']), 'prospective capture interpretation/byte count differs')
    return report, packet, arrays


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frozen', type=Path, required=True); p.add_argument('--frozen-seal', required=True)
    p.add_argument('--out', type=Path, required=True); a = p.parse_args()
    print(capture(a.frozen, a.frozen_seal, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
