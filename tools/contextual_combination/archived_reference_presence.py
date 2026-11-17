"""Optional, local-only bibliography presence in a dated SwissProt archive.

Streams the publisher's DAT member through the official Biopython reader.
No bibliographic requests, citation-year inference or scientific scoring.
"""
import argparse
from collections import Counter
from datetime import date, datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import tarfile
import time

from biograph_steward.client import digest
from tools.deepgo_reference.archive import fingerprints, member_record


def need(value, message):
    if not value:
        raise ValueError('Archived reference presence: ' + message)


def file_sha(path):
    return fingerprints(path)['sha256']


def write(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def release_proof(notes, *, release, expected_date, cutoff):
    """Only parse the explicit publisher release announcement, never citations."""
    match = re.search(re.escape(release) + r' \((\d{2}-[A-Z][a-z]{2}-\d{4})\)', notes)
    need(match is not None, 'official release announcement is missing.')
    published = datetime.strptime(match.group(1), '%d-%b-%Y').date()
    need(published.isoformat() == expected_date and published <= date.fromisoformat(cutoff),
         'release date differs from the reviewed pre-cutoff proof.')
    return published.isoformat()


def inventory_records(records, *, expected_records=None, seconds=3600, progress=None):
    """Read all records before matching any project-specific identifiers."""
    started = time.monotonic(); pmids = set(); classes = Counter()
    counts = Counter(total_records=0, reviewed_human_records=0,
                     reviewed_human_records_with_PubMed=0,
                     human_reference_objects=0, human_PubMed_occurrences=0)
    for record in records:
        counts['total_records'] += 1; classes[record.data_class] += 1
        need(time.monotonic() - started <= seconds, 'CPU stream exceeded its fixed time bound.')
        if record.taxonomy_id == ['9606']:
            need(record.data_class == 'Reviewed', 'a human record is not reviewed.')
            counts['reviewed_human_records'] += 1; found = False
            for reference in record.references:
                counts['human_reference_objects'] += 1
                for database, identifier in reference.references:
                    if database != 'PubMed':
                        continue
                    need(re.fullmatch(r'[0-9]+', identifier) is not None,
                         'native PubMed identifier is not numeric.')
                    pmids.add(identifier); counts['human_PubMed_occurrences'] += 1; found = True
            counts['reviewed_human_records_with_PubMed'] += found
        if progress is not None and counts['total_records'] % 50000 == 0:
            progress(dict(counts))
    if expected_records is not None:
        need(counts['total_records'] == expected_records, 'publisher entry count differs.')
    counts['distinct_human_PubMed_identifiers'] = len(pmids)
    return pmids, {**dict(counts), 'record_classes': dict(classes)}


def support_references(paths):
    """All positive-support rows from the fixed completed provenance files."""
    result = {}
    for view, spec in paths.items():
        need(file_sha(spec['file']) == spec['sha256'], 'completed support file changed.')
        pmids = set(); rows = set(); pairs = 0
        with Path(spec['file']).open() as handle:
            for line in handle:
                record = json.loads(line); pairs += 1
                for support in record['positive_support']:
                    rows.add(support['native_record_id'])
                    for reference in support['references']:
                        if reference.startswith('PMID:'):
                            identifier = reference[5:]
                            need(re.fullmatch(r'[0-9]+', identifier) is not None,
                                 'support PubMed identifier is not numeric.')
                            pmids.add(identifier)
        need(len(pmids) == spec['expected_distinct_PMIDs']
             and len(rows) == spec['expected_support_rows'], 'complete support scope differs.')
        result[view] = {'pmids': pmids, 'distinct_support_rows': len(rows),
                        'residual_reference_pairs': pairs, 'support_file_sha256': spec['sha256']}
    return result


class _HashedReader:
    def __init__(self, source):
        self.source = source; self.hash = hashlib.sha256(); self.bytes = 0

    def read(self, size=-1):
        value = self.source.read(size)
        self.hash.update(value); self.bytes += len(value)
        return value


def run(config, output):
    from Bio import SwissProt
    import Bio
    output = Path(output); need(not output.exists(), 'choose a new output directory.')
    notes = Path(config['release_notes']['file'])
    need(file_sha(notes) == config['release_notes']['sha256'], 'official release-note bytes changed.')
    qualified_date = release_proof(notes.read_text(), release=config['release'],
        expected_date=config['release_date'], cutoff=config['cutoff_date'])
    need(Bio.__version__ == '1.85' and file_sha(SwissProt.__file__) == config['SwissProt_reader_sha256'],
         'qualified official Biopython reader differs.')
    index_path = Path(config['archive_index']['file'])
    need(file_sha(index_path) == config['archive_index']['sha256'], 'sealed member index changed.')
    index = json.loads(index_path.read_text())
    need(index['content_sha256'] == digest({k: v for k, v in index.items() if k != 'content_sha256'}),
         'member-index content seal differs.')
    archive = Path(config['archive']['file']); archive_pin = fingerprints(archive)
    need(archive_pin == index['archive'] == {k: config['archive'][k] for k in archive_pin},
         'archive bytes/checksums differ from the original reviewed source.')
    selected = [m for m in index['members'] if m['canonical_name'] == config['dat_member']]
    need(len(selected) == 1 and selected[0]['ordinary_file']
         and not any(selected[0][k] for k in ('sparse', 'symbolic_link', 'hard_link')),
         'exact ordinary DAT member is absent.')
    output.mkdir(parents=True)
    write(output / 'configuration.json', config)
    with (output / 'progress.jsonl').open('x') as log:
        def progress(value):
            log.write(json.dumps(value, sort_keys=True) + '\n'); log.flush()
        with tarfile.open(archive, 'r|gz') as stream:
            for member in stream:
                if member.name != config['dat_member']:
                    continue
                need(member_record(member) == selected[0], 'DAT member metadata changed.')
                with stream.extractfile(member) as source:
                    reader = _HashedReader(source)
                    with gzip.GzipFile(fileobj=reader, mode='rb') as zipped:
                        with io.TextIOWrapper(zipped, encoding='utf-8') as text:
                            pmids, counts = inventory_records(SwissProt.parse(text),
                                expected_records=config['expected_records'],
                                seconds=config.get('seconds', 3600), progress=progress)
                    while reader.read(1024 * 1024):
                        pass
                    need(reader.bytes == member.size, 'compressed DAT member is incomplete.')
                    member_pin = {'file': member.name, 'bytes': reader.bytes,
                                  'sha256': reader.hash.hexdigest()}
                break
            else:
                raise ValueError('Archived reference presence: DAT stream was not found.')
    inventory = output / 'all_reviewed_human_PMIDs.private.json'
    write(inventory, {'archive_sha256': archive_pin['sha256'], 'dat_member': member_pin,
        'taxonomy_filter': "record.taxonomy_id == ['9606']; host taxonomy is not used",
        'reader': 'Bio.SwissProt.parse; Record.references; Reference.references',
        'counts': counts, 'PubMed_identifiers': sorted(pmids, key=int)})
    # This intersection follows complete inventory construction, not vice versa.
    supports = support_references(config['support_files']); views = {}; private = {}
    for view, support in supports.items():
        present = support['pmids'] & pmids; absent = support['pmids'] - pmids
        views[view] = {key: value for key, value in support.items() if key != 'pmids'}
        views[view].update(distinct_support_PMIDs=len(support['pmids']),
            present_in_dated_reviewed_human_references=len(present),
            absent_from_dated_reviewed_human_references=len(absent))
        private[view] = {'present': sorted(present, key=int), 'absent': sorted(absent, key=int)}
    write(output / 'support_reference_membership.private.json', private)
    result = {'format': 'biograph-steward.archived-reference-presence.v1',
        'status': 'complete', 'release': config['release'], 'release_date': qualified_date,
        'before_reference_start': config['cutoff_date'], 'archive': archive_pin,
        'release_notes_sha256': config['release_notes']['sha256'],
        'archive_index_sha256': config['archive_index']['sha256'], 'dat_member': member_pin,
        'runtime': {'python': platform.python_version(), 'Bio': Bio.__version__,
                    'SwissProt_reader_sha256': file_sha(SwissProt.__file__)},
        'inventory_counts': counts, 'private_inventory_sha256': file_sha(inventory),
        'views': views, 'network_requests': 0, 'selected_identifier_export': False,
        'publication_years_or_experiment_dates_inferred': False,
        'models_labels_exclusions_or_scores_changed': False,
        'interpretation': 'Presence establishes citation in an exact pre-T0 reviewed-human publisher archive, not availability of the evaluated claim or newly performed experiments. Absence does not establish publication novelty or lack of earlier public availability.'}
    write(output / 'aggregate_report.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(json.loads(Path(args.config).read_text()), args.output), indent=2))
