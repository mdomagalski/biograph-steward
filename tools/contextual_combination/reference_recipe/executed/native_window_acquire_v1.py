"""Operator-only acquisition. Annotation bodies stay gzip-opaque in this phase."""
from pathlib import Path
import gzip
import hashlib
import importlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone

BASE = Path('/data/biograph_steward_research_20261114/contextual_gain_20261115/reference_apr_nov_2026_v1')
PYTHON = '/home/ubuntu/workspace/scientific-overnight-20261113/cafa-venv/bin/python'
OLD_DEPS = '/data/biograph_steward_research_20261114/learned_combination_v1/reference_v1/native_deps'
CAFA_DEPS = '/home/ubuntu/workspace/scientific-overnight-20261113/cafa-deps'
ARCHIVE_CODE = '/data/biograph_steward_research_20261114/learned_combination_v1/operator_source_v1'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(path):
    h = hashlib.md5()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return {'bytes': Path(path).stat().st_size, 'sha256': sha(path), 'md5': h.hexdigest()}


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def headers_only(path):
    """Stop at the first non-comment byte, never decode an annotation row."""
    rows = []
    with gzip.open(path, 'rb') as stream:
        while True:
            first = stream.read(1)
            if first != b'!':
                break
            rows.append((first + stream.readline()).decode('utf-8').rstrip())
    return rows


def fetch(role, url, name, size=None, md5=None):
    path = BASE / 'public_sources' / name
    with (BASE / 'download_logs' / (role + '.log')).open('x') as log:
        result = subprocess.run(['curl', '--fail', '--location', '--proto', '=https',
            '--proto-redir', '=https', '--connect-timeout', '30', '--max-time', '2400',
            '--retry', '2', '--silent', '--show-error', '--output', str(path), url],
            stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('Public source acquisition failed: ' + role)
    fp = fingerprint(path)
    if size is not None:
        assert fp['bytes'] == size, 'Publisher length changed: ' + role
    if md5 is not None:
        assert fp['md5'] == md5, 'Publisher checksum changed: ' + role
    row = {'file': str(path), 'url': url, **fp}
    print(json.dumps({'phase': 'source_acquired_opaque', 'role': role, **fp}), flush=True)
    return row


def main():
    assert BASE.is_dir() and (BASE / 'operator_source').is_dir()
    for name in ('public_sources', 'download_logs'):
        (BASE / name).mkdir()
    sources = {}
    sources['gaf_t0'] = fetch('gaf_t0',
        'https://ftp.ebi.ac.uk/pub/databases/GO/goa/old/HUMAN/goa_human.gaf.232.gz',
        'goa_human_t0_20260410.gaf.gz', 10822793)
    sources['gaf_t1'] = fetch('gaf_t1',
        'https://ftp.ebi.ac.uk/pub/databases/GO/goa/HUMAN/goa_human.gaf.gz',
        'goa_human_t1_20261104.gaf.gz', 11061135)
    for epoch, date in (('t0', '2026-04-10 09:40'), ('t1', '2026-11-04 15:05')):
        header = headers_only(sources['gaf_' + epoch]['file'])
        assert '!date-generated: ' + date in header
        sources['gaf_' + epoch]['header'] = header
        sources['gaf_' + epoch]['annotation_rows_decoded'] = False
    sources['obo_t0'] = fetch('obo_t0',
        'https://release.geneontology.org/2026-03-25/ontology/go-basic.obo',
        'go-basic_t0_20260325.obo', 32126692)
    sources['obo_t1'] = fetch('obo_t1',
        'https://release.geneontology.org/2026-08-05/ontology/go-basic.obo',
        'go-basic_t1_build20260805_content20260726.obo', 32227785)
    for epoch, content in (('t0', '2026-03-25'), ('t1', '2026-07-26')):
        with Path(sources['obo_' + epoch]['file']).open() as stream:
            header = [next(stream).strip() for _ in range(2)]
        assert header == ['format-version: 1.2', 'data-version: releases/' + content]
        sources['obo_' + epoch]['native_header'] = header
    sources['swissprot_t0_archive'] = fetch('swissprot_t0_archive',
        'https://ftp.uniprot.org/pub/databases/uniprot/previous_releases/release-2026_01/knowledgebase/uniprot_sprot-only2026_01.tar.gz',
        'uniprot_sprot-only2026_01.tar.gz', 1722763542, '6042adf20dad1ab62112c9053bdebd20')
    sources['swissprot_t1_fasta'] = fetch('swissprot_t1_fasta',
        'https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz',
        'uniprot_sprot_2026_04.fasta.gz', 93867502, '1be1a2a9a44d67f799bac78caa005a10')
    # Existing allowlisted, streaming archive intake; DAT/XML never decoded.
    sys.path.insert(0, ARCHIVE_CODE)
    from tools.deepgo_reference.archive import index, extract
    archive = Path(sources['swissprot_t0_archive']['file'])
    idx = BASE / 'swissprot_t0_archive_index.json'
    inventory = index(archive, 1722763542, '6042adf20dad1ab62112c9053bdebd20', idx)
    selected = [x for x in inventory['members']
                if Path(x['canonical_name']).name == 'uniprot_sprot.fasta.gz']
    assert len(selected) == 1
    selection = BASE / 'swissprot_t0_selection.json'
    dump(selection, {selected[0]['canonical_name']: 'uniprot_sprot_2026_01.fasta.gz'})
    extraction = BASE / 'swissprot_t0_fasta'
    extracted = extract(archive, idx, sha(idx), selection, extraction)
    p = extraction / 'uniprot_sprot_2026_01.fasta.gz'
    sources['swissprot_t0_fasta'] = {'file': str(p), **fingerprint(p),
        'extraction_receipt_sha256': sha(extraction / 'extraction.json')}
    dump(BASE / 'opaque_sources_v1.json', {'sources': sources,
        'T0_GAF_annotation_rows_decoded': False, 'T1_GAF_annotation_rows_decoded': False,
        'DAT_XML_payload_decoded': False})
    print(json.dumps({'phase': 'all_sources_acquired_opaque', 'receipt': str(BASE / 'opaque_sources_v1.json'),
                      'receipt_sha256': sha(BASE / 'opaque_sources_v1.json')}), flush=True)


if __name__ == '__main__':
    main()
