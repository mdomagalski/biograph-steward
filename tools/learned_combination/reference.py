"""LAFA identity boundaries and an unchanged author GOA baseline runner.

This module does not load final GO labels or implement ontology projection.
LAFA release rows have author aspects F/P/C; the existing CAFA intake is reused
after translating only that independent aspect column. The native baseline is
executed from a separately qualified author checkout, not copied into this repo.
"""
from collections import Counter
import gzip
import hashlib
import re
import subprocess
from pathlib import Path

from tools.cafa_reference.intake import ACCESSION, future_identities
from .core import need


LAFA_COMMIT = 'c3fd5b9a5226348d88b9efadddb3214c803b80c4'
BASELINE_COMMIT = '0ab84edbaddf5fef11125dc8adbd19167c3cc038'
BASELINE_SELECTION = 'Computational,Phylogenetical,Electronic,ND,NAS'
NONEXPERIMENTAL = frozenset(('ISS', 'ISO', 'ISA', 'ISM', 'IGC', 'RCA',
                           'IBA', 'IBD', 'IKR', 'IRD', 'IEA', 'ND', 'NAS'))
NATIVE_FILES = frozenset(('goa_nonexp.py', 'retrieve_terms.py', 'ontology.py', 'config.yaml'))
LAFA_ASPECTS = {b'F': b'MFO', b'P': b'BPO', b'C': b'CCO'}


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _pin(path, expected):
    need(isinstance(expected, str) and re.fullmatch('[a-f0-9]{64}', expected),
         'an explicit lowercase SHA-256 file pin is required.')
    need(file_sha256(path) == expected, 'source file differs from its explicit SHA-256 pin.')


def _ids(values):
    values = tuple(values)
    need(values and len(set(values)) == len(values)
         and all(isinstance(x, str) and ACCESSION.fullmatch(x) for x in values),
         'nonempty unique exact canonical UniProt accessions are required.')
    return set(values)


def read_target_ids(path):
    """Read the native headerless accession-only release file, never aliases."""
    with Path(path).open('rb') as stream:
        raw = stream.read().splitlines()
    try:
        values = tuple(line.decode('ascii') for line in raw)
    except UnicodeDecodeError as error:
        raise ValueError('Learned combination: target identities must be ASCII.') from error
    _ids(values)
    return values


def lafa_future_identities(stream):
    """Return accession/aspect metadata while future GO bytes remain opaque.

    Author source writes ``EntryID\tterm\taspect`` and F/P/C. Only the third
    column is translated. The middle field may contain invalid UTF-8 without
    being interpreted, proving this is not a hidden final-label decoder.
    """
    def translated():
        first = next(stream, b'')
        need(first.rstrip(b'\r\n') == b'EntryID\tterm\taspect',
             'expected the native LAFA three-column header.')
        yield first
        for raw in stream:
            fields = raw.rstrip(b'\r\n').split(b'\t')
            need(len(fields) == 3 and fields[2] in LAFA_ASPECTS,
                 'expected native LAFA accession/opaque-term/F-P-C columns.')
            yield b'\t'.join((fields[0], fields[1], LAFA_ASPECTS[fields[2]])) + b'\n'
    return future_identities(iter(translated()))


def development_split(development_candidates, final_targets, *, sequence_sha256=None):
    """Exclude all declared final targets, optionally exact sequence duplicates.

    ``final_targets`` must be the complete declared LAFA target frame, rather
    than only targets for which a convenient model forecast exists. If supplied,
    sequence metadata must cover the complete union; partial hashes cannot
    silently create a claim of sequence-disjoint development.
    """
    candidates, final = _ids(development_candidates), _ids(final_targets)
    literal = candidates & final
    duplicate = set()
    if sequence_sha256 is not None:
        universe = candidates | final
        need(hasattr(sequence_sha256, 'items') and universe <= set(sequence_sha256),
             'sequence metadata must cover every development and final target.')
        need(all(isinstance(sequence_sha256[x], str)
                 and re.fullmatch('[a-f0-9]{64}', sequence_sha256[x]) for x in universe),
             'invalid exact-sequence SHA-256 metadata.')
        final_hashes = {sequence_sha256[x] for x in final}
        duplicate = {x for x in candidates - final if sequence_sha256[x] in final_hashes}
    retained = candidates - literal - duplicate
    need(retained, 'no development accessions remain after final-target exclusions.')
    return tuple(sorted(retained)), {
        'development_candidate_count': len(candidates),
        'declared_final_target_count': len(final),
        'exact_accessions_excluded': len(literal),
        'additional_exact_sequence_duplicates_excluded': len(duplicate),
        'retained_development_count': len(retained),
        'exact_sequence_disjointness_checked': sequence_sha256 is not None,
        'base_model_training_overlap_claim': 'not established by combiner-fit exclusions',
        'homology_disjointness_claim': 'not established by exact sequence hashes',
    }


def gaf_header(path):
    """Read only native comment lines; stop before decoding any data row."""
    opener = gzip.open if Path(path).suffix == '.gz' else open
    lines = []
    with opener(path, 'rb') as stream:
        for raw in stream:
            if not raw.startswith(b'!'):
                break
            lines.append(raw.decode('utf-8').rstrip('\r\n'))
    return lines


def audit_t0_gaf(path, targets, *, expected_generated_date):
    """Audit the native source admission scope without changing its semantics.

    Source date is checked from comments before annotation records are decoded.
    Form IDs, taxa, positive qualifiers and extensions are counted, not silently
    discarded or treated as isoform-aware evidence. Ontology projection remains
    the upstream baseline's responsibility.
    """
    targets = _ids(targets)
    header = gaf_header(path)
    dates = [line.split(':', 1)[1].strip() for line in header
             if line.startswith('!date-generated:')]
    need(len(dates) == 1 and dates[0].split()[0] == expected_generated_date,
         'GAF native generated date differs from the frozen T0 date.')
    need('!gaf-version: 2.2' in header, 'only the qualified native GAF 2.2 format is supported.')
    count, codes, qualifiers, taxa, forms = Counter(), Counter(), Counter(), Counter(), Counter()
    opener = gzip.open if Path(path).suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            if line.startswith('!'):
                continue
            fields = line.rstrip('\r\n').split('\t')
            need(len(fields) == 17, 'GAF 2.2 requires exactly 17 native fields.')
            count['source_rows'] += 1
            if fields[1] not in targets:
                continue
            count['exact_target_rows'] += 1
            row_qualifiers = fields[3].split('|')
            if fields[0] != 'UniProtKB' or 'NOT' in row_qualifiers or fields[6] not in NONEXPERIMENTAL:
                count['native_admission_rejected_rows'] += 1
                continue
            count['native_admitted_rows_before_ontology_projection'] += 1
            codes[fields[6]] += 1
            qualifiers[fields[3]] += 1
            taxa[fields[12]] += 1
            forms[fields[16]] += 1
            count['admitted_rows_with_gene_product_form_id'] += bool(fields[16])
            count['admitted_rows_with_annotation_extension'] += bool(fields[15])
    return {
        'native_header': header, 'expected_generated_date': expected_generated_date,
        'counts': dict(count), 'native_admitted_evidence_codes': dict(sorted(codes.items())),
        'native_admitted_qualifiers': dict(sorted(qualifiers.items())),
        'native_admitted_taxa': dict(sorted(taxa.items())),
        'native_admitted_gene_product_form_ids': dict(sorted(forms.items())),
        'source_admission': 'exact DB_Object_ID, DB=UniProtKB, no NOT, fixed author evidence list',
        'form_taxon_extension_policy': 'preserved and counted; unchanged author baseline does not filter these fields',
        'reference_role': 'historical source baseline, not independent biological truth',
    }


def prepare_t0_nonexperimental(*, gaf, graph, targets, native_directory, python,
                              output, gaf_sha256, graph_sha256, native_sha256,
                              expected_generated_date='2025-09-04'):
    """Run the original author CLI after source pins and T0 header checks.

    ``native_sha256`` must pin the four source/config files. Runtime dependency
    qualification remains the caller's responsibility. No network, installation,
    shell invocation, final-reference access or custom ontology code occurs here.
    Existing output directories are rejected so a retry cannot overwrite a seal.
    """
    gaf, graph, native_directory, output = map(Path, (gaf, graph, native_directory, output))
    targets = tuple(sorted(_ids(targets)))
    target_set = set(targets)
    _pin(gaf, gaf_sha256); _pin(graph, graph_sha256)
    need(set(native_sha256) == NATIVE_FILES, 'pin exactly the four qualified native baseline source/config files.')
    for name, expected in native_sha256.items():
        _pin(native_directory / name, expected)
    audit = audit_t0_gaf(gaf, targets, expected_generated_date=expected_generated_date)
    output.mkdir(parents=True, exist_ok=False)
    query = output / 'query_ids.txt'
    query.write_text('\n'.join(targets) + '\n', encoding='ascii')
    predictions = output / 'goa_nonexp_predictions.tsv'
    command = [str(python), str((native_directory / 'goa_nonexp.py').resolve()),
               '--annot_file', str(gaf.resolve()), '--selected_go', BASELINE_SELECTION,
               '--query_file', str(query.resolve()), '--graph', str(graph.resolve()),
               '--output_baseline', str(predictions.resolve())]
    subprocess.run(command, cwd=native_directory.resolve(), check=True)
    rows, cells = 0, set()
    with predictions.open(encoding='utf-8') as stream:
        for line in stream:
            fields = line.rstrip('\r\n').split('\t')
            need(len(fields) == 3 and fields[0] in target_set
                 and re.fullmatch(r'GO:[0-9]{7}', fields[1]) and fields[2] == '1',
                 'native baseline output differs from exact target/GO/score=1 contract.')
            rows += 1; cells.add((fields[0], fields[1]))
    return {
        'prediction_file': str(predictions), 'prediction_sha256': file_sha256(predictions),
        'native_output_rows': rows, 'native_unique_prediction_cells': len(cells),
        'native_output_duplicate_rows': rows - len(cells),
        'targets_with_native_predictions': len({p for p, _ in cells}),
        'target_frame_size': len(targets), 'selected_go': BASELINE_SELECTION,
        'gaf_sha256': gaf_sha256, 'graph_sha256': graph_sha256,
        'native_sha256': dict(native_sha256), 'native_command': command,
        'source_audit': audit, 'final_GO_labels_read': False,
    }
