"""Stage exact dated Swiss-Prot FASTA identities using author-required Bio.SeqIO.

Only the pinned FASTA and fixed target lists enter this adapter. No annotation,
reference labels, current UniProt lookups or fallback identifiers are read.
"""
import argparse
import gzip
import hashlib
from pathlib import Path
import re

from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output
from tools.cafa_reference.intake import ACCESSION
from .archive import fingerprints, need, sealed


def frame(path, expected_sha256):
    need(fingerprints(path)['sha256'] == expected_sha256, 'target FILE pin differs.')
    values = Path(path).read_text().splitlines()
    need(values and len(values) == len(set(values))
         and all(ACCESSION.fullmatch(x) for x in values), 'invalid/repeated literal target accession.')
    return values


def collect(records, wanted):
    """Inspect only requested accession records; retain literal full sequences."""
    found = {}
    for record in records:
        columns = record.id.split('|')
        if len(columns) != 3 or columns[1] not in wanted:
            continue
        accession = columns[1]
        need(columns[0] == 'sp' and ACCESSION.fullmatch(accession), 'selected record is not canonical Swiss-Prot.')
        need(accession not in found, 'selected accession repeats in the dated source.')
        taxon = re.search(r'(?:^| )OX=([0-9]+)(?: |$)', record.description)
        need(taxon and taxon[1] == '9606', 'selected source record is not explicitly human.')
        sequence = str(record.seq)
        need(sequence and re.fullmatch(r'[A-Z]+', sequence), 'invalid source sequence; no normalization/replacement.')
        found[accession] = {'sequence': sequence, 'original_header': record.description,
            'sequence_sha256': hashlib.sha256(sequence.encode('ascii')).hexdigest(),
            'residues': len(sequence), 'native_residues_used': min(1022, len(sequence)),
            'native_first1022_truncation': len(sequence) > 1022, 'taxon': 'NCBITaxon:9606'}
    return found


def stage(fasta, fasta_sha256, primary, primary_sha256, reserved, reserved_sha256, output):
    fasta = Path(fasta)
    need(fingerprints(fasta)['sha256'] == fasta_sha256, 'dated FASTA FILE pin differs.')
    original = frame(primary, primary_sha256); additional = frame(reserved, reserved_sha256)
    need(len(original) == 1294 and len(additional) == 4806 and not set(original) & set(additional),
         'existing 1294/4806 disjoint target frames differ.')
    targets = sorted(set(original) | set(additional))
    # Reuse the published predictor's parser dependency instead of implementing
    # a new FASTA parser. It is loaded only in the isolated optional runtime.
    from Bio import SeqIO
    opener = gzip.open if fasta.suffix == '.gz' else open
    with opener(fasta, 'rt') as stream:
        found = collect(SeqIO.parse(stream, 'fasta'), set(targets))
    missing = sorted(set(targets) - set(found))
    out = new_output(output, fasta, primary, reserved)
    staged = out / 'targets_2023_03.fasta'
    with staged.open('w') as stream:
        for accession in targets:
            if accession in found:
                stream.write('>' + accession + '\n' + found[accession]['sequence'] + '\n')
    rows = {accession: {k: v for k, v in value.items() if k != 'sequence'}
            for accession, value in found.items()}
    result = sealed({'format': 'biograph-steward.deepgo-dated-target-sequences.v1',
        'created_at': utcnow(), 'source_release': 'UniProtKB/Swiss-Prot 2023_03',
        'source_release_date': '2023-06-28', 'source_fasta_file_sha256': fasta_sha256,
        'primary_target_file_sha256': primary_sha256, 'reserved_target_file_sha256': reserved_sha256,
        'fixed_targets': len(targets), 'primary_targets': len(original), 'reserved_targets': len(additional),
        'sequence_coverage': len(found), 'missing_target_ids': missing,
        'status': 'complete' if not missing else 'incomplete_requires_explicit_qualification',
        'missing_targets_removed_from_evaluation': False, 'current_sequence_fallback_used': False,
        'source_records': rows, 'staged_fasta': fingerprints(staged),
        'header_policy': 'Literal accession only for native emitted IDs; original source headers retained here.',
        'ordering': 'Staged accession order is fixed; author length-batched output must be joined by exact ID, never row position.',
        'future_reference_annotations_read': False})
    write_json(out / 'sequences.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('fasta', 'fasta-sha256', 'primary', 'primary-sha256',
                'reserved', 'reserved-sha256', 'output'):
        parser.add_argument('--' + key, required=True)
    value = stage(**vars(parser.parse_args()))
    print(value['status'], value['sequence_coverage'], value['content_sha256'])
