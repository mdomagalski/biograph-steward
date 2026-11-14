"""Keep exact target rows from the byte-verified official CAFA5 baselines.

No future annotation file is an input. Unselected large archive members are
streamed past, never extracted. The admitted prediction records retain their
native scores; any incompatible score scale fails rather than being guessed.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha

MEMBERS = {'official_blast': 'baselines/BLAST/blast_CAFA5.tsv',
           'official_prott5_cosine1': 'baselines/prott5/prott5_cosine_1.tsv',
           'official_nonexperimental': 'baselines/all_evidence.tsv'}
FREQUENCY = 'baselines/Naive/cafa5_naive_frequencies.tsv'
EXPECTED_MD5 = '46c41b3e449288724130c7dbed95b599'


def need(value, text):
    if not value: raise ValueError('CAFA baseline intake: ' + text)


def selected_rows(source, target_ids, output):
    """Filter on the exact first column, retaining complete native row bytes."""
    checksum = hashlib.sha256(); count = kept = 0; seen = set(); minimum = math.inf; maximum = -math.inf
    for raw in source:
        count += 1; checksum.update(raw)
        accession = raw.split(b'\t', 1)[0].decode('ascii')
        if accession not in target_ids: continue
        columns = raw.rstrip(b'\r\n').split(b'\t')
        need(len(columns) == 3 and re.fullmatch(rb'GO:[0-9]{7}', columns[1]), 'invalid selected prediction row.')
        score = float(columns[2])
        need(math.isfinite(score) and 0 <= score <= 1 + 1e-10,
             'selected native score is incompatible with [0,1]; no heuristic scaling is permitted.')
        minimum = min(minimum, score); maximum = max(maximum, score)
        seen.add(accession); output.write(raw); kept += 1
    return {'source_rows': count, 'selected_rows': kept, 'targets_represented': len(seen),
            'targets_unrepresented': sorted(target_ids - seen),
            'native_min_score': minimum if kept else None, 'native_max_score': maximum if kept else None,
            'full_member_sha256': checksum.hexdigest(), 'raw_rows_preserved': True}


def naive_predictions(raw, targets, output):
    """Stream the official naive.py's identical Cartesian-product operation."""
    records = []; terms = set()
    for line in raw.splitlines():
        columns = line.split(b'\t')
        need(len(columns) == 2 and re.fullmatch(rb'GO:[0-9]{7}', columns[0]), 'invalid official term-frequency row.')
        value = float(columns[1])
        need(math.isfinite(value) and 0 <= value <= 1 and columns[0] not in terms,
             'duplicate/invalid official term frequency.')
        terms.add(columns[0]); records.append(line)
    need(records and targets, 'empty official frequency or target frame.')
    for accession in sorted(targets):
        prefix = accession.encode() + b'\t'
        output.write(b''.join(prefix + row + b'\n' for row in records))
    return {'frequency_terms': len(terms), 'selected_rows': len(terms) * len(targets),
            'targets_represented': len(targets), 'operation': 'official naive.py: every target x every supplied frequency; streamed instead of materialized pandas concat',
            'native_frequency_strings_preserved': True}


def prepare(archive, metadata, targets, output):
    archive, metadata, targets = map(Path, (archive, metadata, targets))
    need(all(p.is_file() and not p.is_symlink() for p in (archive, metadata, targets)), 'ordinary source files required.')
    details = json.loads(metadata.read_text())
    need(str(details.get('id')) == '22381862', 'use the fixed official CAFA5 v2 Zenodo record.')
    item = next((f for f in details['files'] if f['key'] == 'baselines.tar.gz'), None)
    need(item is not None and item['checksum'] == 'md5:' + EXPECTED_MD5
         and archive.stat().st_size == item['size'], 'official baseline size/checksum metadata differs.')
    md5, strong = hashlib.md5(), hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            md5.update(chunk); strong.update(chunk)
    need(md5.hexdigest() == EXPECTED_MD5, 'baseline archive does not match the publisher checksum.')
    ids = targets.read_text().splitlines()
    need(ids and ids == sorted(set(ids)) and all(re.fullmatch(r'[A-Z0-9]+', s) for s in ids),
         'exact sorted opaque accession frame required.')
    target_ids = set(ids)
    folder = new_output(output, archive, metadata, targets)
    header = {'format': 'biograph-steward.official-cafa5-baseline-intake.v1', 'created_at': utcnow(),
        'status': 'running', 'source_record': 'https://zenodo.org/records/22381862',
        'archive_sha256': strong.hexdigest(), 'publisher_md5': EXPECTED_MD5,
        'metadata_sha256': sha(metadata), 'target_file_sha256': sha(targets), 'target_count': len(ids),
        'implementation_sha256': sha(__file__), 'selected_members': MEMBERS,
        'future_GO_labels_opened': False, 'score_rescaling': False,
        'choice_policy': 'Predeclared official BLAST, weighted ProtT5 cosine1, nonexperimental source and official naive; no neighbor-count sweep.'}
    write_json(folder/'started.json', header)
    reverse = {v: k for k, v in MEMBERS.items()}; stats = {}; raw_frequency = None; script = None
    with tarfile.open(archive, mode='r|gz') as source:
        for member in source:
            if member.name not in {*reverse, FREQUENCY, 'baselines/naive.py'}: continue
            need(member.isfile(), 'selected archive member is not an ordinary file.')
            stream = source.extractfile(member)
            if member.name == FREQUENCY:
                need(raw_frequency is None and member.size < 10000000, 'duplicate/oversize official frequency table.')
                raw_frequency = stream.read(); (folder/'cafa5_naive_frequencies.tsv').write_bytes(raw_frequency)
            elif member.name == 'baselines/naive.py':
                need(script is None and member.size < 100000, 'duplicate/oversize official script.')
                script = stream.read(); (folder/'naive.author.py.txt').write_bytes(script)
            else:
                name = reverse[member.name]; need(name not in stats, 'selected baseline member repeats.')
                with gzip.GzipFile(filename=str(folder/(name+'.tsv.gz')), mode='wb', mtime=0) as output_stream:
                    stats[name] = selected_rows(stream, target_ids, output_stream)
                print(json.dumps({'method': name, **stats[name]}), flush=True)
    need(set(stats) == set(MEMBERS) and raw_frequency is not None and script is not None,
         'required predeclared baseline member is missing.')
    with gzip.GzipFile(filename=str(folder/'official_naive.tsv.gz'), mode='wb', mtime=0) as output_stream:
        stats['official_naive'] = naive_predictions(raw_frequency, target_ids, output_stream)
    result = {**header, 'status': 'completed', 'created_at': utcnow(), 'members': stats,
        'files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(folder.iterdir())}}
    result['content_sha256'] = digest(result); write_json(folder/'qualification.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive','metadata','targets','output'): parser.add_argument('--'+name, required=True)
    result = prepare(**vars(parser.parse_args()))
    print(json.dumps({'content_sha256': result['content_sha256'], 'methods': list(result['members'])}))


if __name__ == '__main__': main()
