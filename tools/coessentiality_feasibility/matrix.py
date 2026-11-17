"""Bounded native Fortran-column transport and NumPy replay, not inference.

ETags bind the server representation. SHA256 binds each captured range only;
neither a header hash nor a collection of columns is a complete matrix hash.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import io
from pathlib import Path
import time
import urllib.request
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.reference_accuracy.design import need
from tools.coessentiality_feasibility.prepare import sealed, verify

FORMAT = 'biograph-steward.coessentiality-native-column-capture.v1'


def header_metadata(raw):
    import numpy as np
    f = io.BytesIO(raw)
    version = np.lib.format.read_magic(f)
    need(version == (1, 0), 'unsupported native NPY version')
    shape, fortran, dtype = np.lib.format.read_array_header_1_0(f)
    need(f.tell() == len(raw) and len(shape) == 2 and fortran and dtype.str == '<f8',
         'native column reader requires a complete float64 Fortran header')
    return {'shape': list(shape), 'dtype': dtype.str, 'fortran_order': fortran,
            'header_bytes': len(raw), 'itemsize': dtype.itemsize,
            'file_bytes': len(raw) + shape[0] * shape[1] * dtype.itemsize}


def column_range(meta, column):
    need(type(column) is int and 0 <= column < meta['shape'][1], 'matrix column outside native shape')
    length = meta['shape'][0] * meta['itemsize']
    start = meta['header_bytes'] + column * length
    return start, start + length - 1


def decode_column(raw, meta):
    import numpy as np
    need(len(raw) == meta['shape'][0] * meta['itemsize'], 'native column byte length differs')
    return np.frombuffer(raw, dtype=np.dtype(meta['dtype']))


def validate_response(status, headers, start, end, total, etag, body):
    need(status == 206, 'native host did not return HTTP206')
    need(headers.get('Content-Range') == f'bytes {start}-{end}/{total}', 'native response range differs')
    need(headers.get('ETag') == etag, 'native server representation ETag changed')
    need(len(body) == end - start + 1 and headers.get('Content-Length') == str(len(body)),
         'native response payload length differs')


def _fetch(url, etag, start, end, total, output):
    request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}', 'If-Match': etag,
        'User-Agent': 'BioGraphSteward-research-native-range/1.0', 'Accept-Encoding': 'identity'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read(end - start + 2)
                headers = {k: response.headers.get(k) for k in ['Content-Range', 'Content-Length', 'ETag', 'Last-Modified']}
                validate_response(response.status, headers, start, end, total, etag, body)
                receipt = {'url': url, 'response_url': response.url, 'retrieved_at': utcnow(), 'status': response.status,
                    'request_range': [start, end], 'native_total_bytes': total, 'expected_etag': etag,
                    'etag_is_not_cryptographic_hash': True, 'headers': headers, 'payload_bytes': len(body),
                    'payload_sha256': hashlib.sha256(body).hexdigest(), 'attempt': attempt + 1}
            Path(output).write_bytes(body)
            write_json(Path(str(output) + '.json'), receipt)
            return receipt
        except ValueError:
            raise  # Metadata mismatch is not a transient network failure.
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def capture(frozen, output):
    frozen = Path(frozen).absolute(); report, packet = verify(frozen)
    input_pin = sha(frozen / 'report.json'); code = sha(__file__)
    out = new_output(output, frozen); (out / 'columns').mkdir()
    descriptions = {}
    for name in ['GLS_p.npy', 'GLS_sign.npy']:
        proof = gold_packet._read(frozen / 'proof' / (name + '.header.receipt.json'))
        raw = (frozen / 'proof' / (name + '.header')).read_bytes(); meta = header_metadata(raw)
        need(meta['file_bytes'] == 2487663728 and meta['shape'] == [17634, 17634], 'released matrix shape differs')
        need(sha(frozen / 'proof' / (name + '.header')) == proof['header_sha256'], 'native header pin differs')
        descriptions[name] = {**meta, 'url': proof['url'], 'etag': proof['headers']['ETag'],
                              'native_header_sha256': proof['header_sha256']}
    indices = sorted({g['native_matrix_index'] for g in packet['genes']})
    plan = {'created_at': utcnow(), 'frozen_comparison_content_sha256': report['content_sha256'],
        'frozen_report_file_sha256': input_pin, 'matrix_metadata': descriptions,
        'column_indices': indices, 'workers': 4, 'maximum_attempts_per_column': 3,
        'scope': 'complete selected native columns only; not complete matrix files', 'implementation_sha256': code}
    plan['content_sha256'] = digest(plan); write_json(out / 'capture_plan.json', plan)
    receipts = []; failures = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {}
        for name, meta in descriptions.items():
            for index in indices:
                start, end = column_range(meta, index)
                target = out / 'columns' / (name + f'.column_{index:05}.bin')
                future = pool.submit(_fetch, meta['url'], meta['etag'], start, end, meta['file_bytes'], target)
                pending[future] = (name, index, target)
        for future in as_completed(pending):
            name, index, target = pending[future]
            try:
                receipt = future.result(); receipts.append({'matrix': name, 'column': index,
                    'file': target.relative_to(out).as_posix(), **receipt})
            except Exception as exc:
                failures.append({'matrix': name, 'column': index, 'error_type': type(exc).__name__, 'error': str(exc)})
    if failures:
        write_json(out / 'failures.json', {'created_at': utcnow(), 'failures': failures})
        raise ValueError('Native column capture failed; failed attempt and successful raw ranges preserved without success report.')
    verify(frozen)
    need(sha(frozen / 'report.json') == input_pin and sha(__file__) == code, 'input/code changed during capture')
    result = {'format': FORMAT, 'created_at': utcnow(), 'capture_plan_content_sha256': plan['content_sha256'],
        'frozen_comparison_content_sha256': report['content_sha256'], 'frozen_report_file_sha256': input_pin,
        'matrix_metadata': descriptions, 'columns': sorted(receipts, key=lambda r: (r['matrix'], r['column'])),
        'full_matrix_files_retrieved_or_hashed': False, 'range_payload_total_bytes': sum(r['payload_bytes'] for r in receipts),
        'implementation_sha256': code, 'files': {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()}}
    result['content_sha256'] = digest(result); write_json(out / 'report.json', result)
    return result


def load(frozen, captured):
    frozen, captured = Path(frozen), Path(captured)
    frozen_report, packet = verify(frozen); report = sealed(captured / 'report.json')
    need(report['format'] == FORMAT and report['frozen_comparison_content_sha256'] == frozen_report['content_sha256']
         and report['frozen_report_file_sha256'] == sha(frozen / 'report.json'), 'capture/frozen binding differs')
    need(not any(p.is_symlink() for p in [captured, *captured.rglob('*')]), 'symlink in capture')
    inventory = {p.relative_to(captured).as_posix(): sha(p) for p in captured.rglob('*') if p.is_file() and p != captured / 'report.json'}
    need(inventory == report['files'], 'capture byte inventory differs')
    expected = {(name, g['native_matrix_index']) for name in ['GLS_p.npy', 'GLS_sign.npy'] for g in packet['genes']}
    need(len(report['columns']) == len(expected) and {(r['matrix'], r['column']) for r in report['columns']} == expected,
         'capture omits or repeats a fixed native column')
    arrays = {}
    for row in report['columns']:
        name = row['matrix']; meta = report['matrix_metadata'][name]
        native = header_metadata((frozen / 'proof' / (name + '.header')).read_bytes())
        proof = gold_packet._read(frozen / 'proof' / (name + '.header.receipt.json'))
        need(all(meta[k] == v for k, v in native.items()) and meta['url'] == proof['url']
             and meta['etag'] == proof['headers']['ETag'], 'capture metadata differs from native source header')
        path = captured / row['file']; need(path.resolve().is_relative_to(captured.resolve()), 'range path escapes capture')
        raw = path.read_bytes(); start, end = column_range(meta, row['column'])
        validate_response(row['status'], row['headers'], start, end, meta['file_bytes'], meta['etag'], raw)
        need(row['request_range'] == [start, end] and row['url'] == meta['url']
             and sha(path) == row['payload_sha256'], 'range proof differs')
        arrays[(name, row['column'])] = decode_column(raw, meta)
    return report, packet, arrays


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--frozen', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path); a = p.parse_args()
    print(capture(a.frozen, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
