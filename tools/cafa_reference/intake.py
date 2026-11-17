"""Qualify official CAFA5 artifacts without opening future GO term labels.

Only target identity and the independent aspect column are interpreted from
future files. Historical annotations and ontology are legitimate model inputs;
the current GOA source used by the application is never a model input here.
"""
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha

FORMAT = 'biograph-steward.cafa5-reference-intake.v1'
HEADER = b'EntryID\tterm\taspect'
ASPECTS = {'BPO', 'MFO', 'CCO'}
SETTINGS = ('no_knowledge', 'limited', 'partial')
ACCESSION = re.compile(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\Z')
HISTORICAL = {'known_t0.tsv': 'training/known_t0.tsv', 'go-basic.obo': 'ontology/go-basic.obo',
              'IA_t0.tsv': 'evaluation_context/IA_t0.tsv', 'toi_2025_03.tsv': 'evaluation_context/toi_2025_03.tsv'}


def need(condition, text):
    if not condition:
        raise ValueError('CAFA5 intake: ' + text)


def check_archive(path, metadata, key):
    """Match the actual author archive to its publisher metadata before parsing."""
    rows = [x for x in metadata['files'] if x['key'] == key]
    need(len(rows) == 1, 'publisher artifact identity is ambiguous.')
    expected = rows[0]
    need(expected['checksum'].startswith('md5:'), 'unreviewed publisher checksum algorithm.')
    h = hashlib.md5()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    need(Path(path).stat().st_size == expected['size'] and h.hexdigest() == expected['checksum'][4:],
         'author size/checksum differs.')
    return {'key': key, 'bytes': expected['size'], 'publisher_checksum': expected['checksum'],
            'sha256': sha(path), 'source_url': expected['links']['self']}


def regular_members(archive):
    members = archive.getmembers()
    names = [m.name for m in members]
    need(len(names) == len(set(names)), 'archive member names repeat.')
    for m in members:
        need(not m.name.startswith('/') and not any(p in {'.', '..'} for p in PurePosixPath(m.name).parts)
             and (m.isfile() or m.isdir()) and not m.issym() and not m.islnk(),
             'archive contains a path or member type outside the ordinary-file scope.')
    return {m.name: m for m in members if m.isfile()}


def future_identities(stream):
    """Decode first/third columns only; a future term can remain opaque bytes.

    The aspect column is supplied by the author, rather than inferred by
    decoding the withheld GO term. Repeated rows carry no additional weight.
    """
    need(next(stream).rstrip(b'\r\n') == HEADER, 'expected native three-column header.')
    by_aspect = {a: set() for a in ASPECTS}
    rows = 0
    for raw in stream:
        parts = raw.rstrip(b'\r\n').split(b'\t')
        need(len(parts) == 3, 'future metadata requires three native columns.')
        target, aspect = parts[0].decode('ascii'), parts[2].decode('ascii')
        need(ACCESSION.fullmatch(target) and aspect in ASPECTS, 'unsupported exact accession/aspect metadata.')
        by_aspect[aspect].add(target)
        rows += 1
    return by_aspect, rows


def node_frame(path):
    with Path(path).open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    ids = [r['node_id'][len('UniProtKB:'):] for r in rows if r['node_id'].startswith('UniProtKB:')
           and r['resolution_status'] == 'resolved' and r['canonical_graph_node_present'] == 'true']
    need(ids and len(ids) == len(set(ids)) and all(ACCESSION.fullmatch(i) for i in ids),
         'node frame must contain unique exact resolved canonical accessions.')
    return set(ids)


def prepare(metadata, archive, nodes, output):
    metadata, archive, nodes = map(Path, (metadata, archive, nodes))
    meta = json.loads(metadata.read_text())
    need(meta['metadata']['doi'] == '10.5281/zenodo.22381862'
         and meta['metadata']['license']['id'] == 'cc-by-4.0'
         and meta['metadata']['access_right'] == 'open', 'unreviewed official record/license.')
    source = check_archive(archive, meta, 'full_evaluation.tar.gz')
    frame = node_frame(nodes)
    folder = new_output(output, metadata, archive, nodes)
    write_json(folder/'intake_boundary.json', {'created_at': utcnow(), 'future_GO_columns_decoded': False,
        'future_metadata_scope': 'Literal first-column accession and third-column aspect only.',
        'forbidden_feature_sources': ['current application GOA2026', 'future GO term columns',
                                     'known_publishedaftert0 evaluation exclusion file'],
        'benchmark_scope': 'Retrospective author-curated temporal annotation prediction, not all-graph biological truth.'})
    coverage, members = {}, {}
    with tarfile.open(archive, 'r:gz') as tar:
        selected = regular_members(tar)
        need(set(selected) == {'full_evaluation/'+s for s in HISTORICAL} | {
            'full_evaluation/eval_terms_'+s+'_2025_03.tsv' for s in SETTINGS},
            'native archive member set differs.')
        for name, target in HISTORICAL.items():
            path = folder/target; path.parent.mkdir(parents=True, exist_ok=True)
            raw = tar.extractfile(selected['full_evaluation/'+name]).read(); path.write_bytes(raw)
            members[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'output': target}
        for setting in SETTINGS:
            by_aspect, count = future_identities(tar.extractfile(
                selected['full_evaluation/eval_terms_'+setting+'_2025_03.tsv']))
            counts = {}
            for aspect, values in sorted(by_aspect.items()):
                path = folder/'target_identity_only'/(setting+'_'+aspect+'.txt')
                path.parent.mkdir(exist_ok=True)
                path.write_text('\n'.join(sorted(values & frame))+'\n')
                counts[aspect] = {'all_source_targets': len(values), 'frame_targets': len(values & frame)}
            union = set.union(*by_aspect.values())
            coverage[setting] = {'aspects': counts, 'raw_rows_excluding_header': count,
                                 'all_source_targets': len(union), 'frame_targets': len(union & frame)}
    known_ids, known_count, known_aspects = set(), 0, Counter()
    with (folder/'training/known_t0.tsv').open() as f:
        reader = csv.DictReader(f, delimiter='\t')
        need(reader.fieldnames == ['EntryID', 'term', 'aspect'], 'historical header differs.')
        for row in reader:
            need(ACCESSION.fullmatch(row['EntryID']) and row['term'].startswith('GO:') and row['aspect'] in ASPECTS,
                 'historical annotation shape differs.')
            known_ids.add(row['EntryID']); known_count += 1
            if row['EntryID'] in frame: known_aspects[row['aspect']] += 1
    report = {'format': FORMAT, 'created_at': utcnow(), 'source': source,
        'metadata_sha256': sha(metadata), 'nodes_sha256': sha(nodes), 'frame_proteins': len(frame),
        'historical_known_proteins': len(known_ids), 'historical_annotation_rows': known_count,
        'frame_proteins_with_historical_annotations': len(known_ids & frame),
        'frame_historical_rows_by_aspect': dict(known_aspects), 'coverage': coverage,
        'historical_members': members, 'future_GO_columns_decoded': False,
        'source_dates': {'ontology': '2023-01-01', 'known_annotations': 'UniProt2023_03; author known_t0',
                         'evaluation': 'UniProt2025_03; future terms remain sealed'},
        'limitations': ['Target/aspect coverage precedes TOI, orphan and per-protein known-term filtering.',
            'Author label admission includes experimental-family, TAS and IC curator annotations; unannotated functions are not exhaustive biological negatives.',
            'This source corpus overlaps previously examined GOA releases; strict temporal feature exclusion does not make developers wholly blind.',
            'The historical Pharos node cohort was selected retrospectively; this is not a prospective2023 submission.'],
        'files': {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}}
    report['content_sha256'] = digest(report); write_json(folder/'report.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('metadata', 'archive', 'nodes', 'output'): p.add_argument('--'+name, required=True)
    args = vars(p.parse_args())
    r = prepare(**args)
    print(json.dumps({k:r[k] for k in ('format','frame_proteins','coverage','content_sha256')}, indent=2))


if __name__ == '__main__':
    main()
