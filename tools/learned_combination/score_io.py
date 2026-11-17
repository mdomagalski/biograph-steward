"""Plain/gzip three-column scores; literal identity matching, duplicate MAX."""
import gzip
import math
from pathlib import Path

from .core import ScoreMatrix, need, validate_axes, validate_tolerance


def load_scores(path, proteins, terms, *, upper_roundoff_tolerance=0.0):
    """Read scores on explicit axes, returning ``(ScoreMatrix, diagnostics)``.

    Exactly three whitespace-delimited fields are accepted per nonblank line.
    Unknown identities are rejected; canonical/alternative-ID resolution, if
    needed, belongs to the existing native ontology reader before this stage.
    Literal repeated cells retain MAX, matching the native CAFA score reader.
    Omitted cells become zero only for the mixture arithmetic. They do not
    establish absent biology, a negative reference label, or model coverage.
    """
    import numpy as np

    proteins, terms = validate_axes(proteins, terms)
    validate_tolerance(upper_roundoff_tolerance)
    protein_index = {value: index for index, value in enumerate(proteins)}
    term_index = {value: index for index, value in enumerate(terms)}
    values = np.zeros((len(proteins), len(terms)), dtype=np.float64)
    # One boolean per cell distinguishes an explicit zero from an omission
    # and supports literal duplicate diagnostics without a Python tuple set.
    seen = np.zeros(values.shape, dtype=np.bool_)
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    rows = duplicates = roundoff = zero_rows = 0
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            fields = line.split()
            if not fields:
                continue
            prefix = f'{path.name}:{line_number}: '
            need(len(fields) == 3, prefix + 'expected accession, GO ID and score.')
            protein, term, text = fields
            need(protein in protein_index and term in term_index,
                 prefix + 'score identity is outside the exact supplied axes.')
            try:
                score = float(text)
            except ValueError as error:
                raise ValueError('Learned combination: ' + prefix + 'invalid numeric score.') from error
            need(math.isfinite(score) and 0 <= score <= 1 + upper_roundoff_tolerance,
                 prefix + 'score is outside finite qualified bounds; no clipping or rescaling.')
            row, column = protein_index[protein], term_index[term]
            rows += 1
            duplicates += int(seen[row, column])
            roundoff += int(score > 1)
            zero_rows += int(score == 0)
            values[row, column] = max(values[row, column], score)
            seen[row, column] = True
    observed_cells = int(np.count_nonzero(seen))
    diagnostics = {
        'source_rows': rows,
        'literal_duplicate_rows': duplicates,
        'literal_duplicate_policy': 'MAX, never sum or last-row overwrite',
        'explicit_zero_rows': zero_rows,
        'observed_cells': observed_cells,
        'omitted_cells_filled_with_arithmetic_zero': int(values.size - observed_cells),
        'targets_with_source_rows': int(np.count_nonzero(np.any(seen, axis=1))),
        'targets_without_source_rows': int(np.count_nonzero(~np.any(seen, axis=1))),
        'scores_in_upper_roundoff_band': roundoff,
        'maximum_source_score': float(values.max()),
        'upper_roundoff_tolerance': upper_roundoff_tolerance,
        'score_transformation': 'none; finite raw source scores retained',
        'missing_score_meaning': 'zero for arithmetic only; not a biological-negative label',
    }
    return ScoreMatrix(proteins, terms, values, upper_roundoff_tolerance), diagnostics


def write_scores(path, scores, *, include_zero=False):
    """Write exact numerical values in supplied axis order without overwriting.

    Seventeen significant digits round-trip float64. Gzip has fixed time and no
    embedded source filename, making identical score exports byte-reproducible.
    Exact-zero rows may be omitted because the loader uses arithmetic zero;
    the supplied axes, rather than file membership, retain the target frame.
    """
    need(isinstance(scores, ScoreMatrix), 'an explicit score matrix is required.')
    need(isinstance(include_zero, bool), 'include_zero must be boolean.')
    path = Path(path)
    count = 0
    with path.open('xb') as raw:
        compressed = gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) if path.suffix == '.gz' else None
        stream = compressed if compressed is not None else raw
        try:
            for protein, row in zip(scores.proteins, scores.values):
                for term, score in zip(scores.terms, row):
                    if include_zero or score != 0:
                        stream.write(f'{protein}\t{term}\t{score:.17g}\n'.encode('utf-8'))
                        count += 1
        finally:
            if compressed is not None:
                compressed.close()
    return count
