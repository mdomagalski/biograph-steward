"""Lossless score export and exact native presentation checks, no evaluator.

DeepGO v1 predict.py writes only scores >=0.1 rounded to three decimals.
This adapter retains pre-presentation float32 model values for the already
specified common evaluator. It never chooses a threshold or calibrates scores.
"""
import math
import re


ENSEMBLES = {'mf': (0, 1, 2, 5, 6, 8), 'bp': (2, 5, 6, 7, 8, 9),
             'cc': (1, 3, 4, 5, 6, 7)}
NAMESPACES = {'mf': 'molecular_function', 'bp': 'biological_process',
              'cc': 'cellular_component'}
AUTHOR_ASPECT_ORDER = ('mf', 'cc', 'bp')


def need(value, message):
    if not value:
        raise ValueError('DeepGO scores: ' + message)


def validate_identity(proteins, terms):
    need(len(proteins) == len(set(proteins)) and len(terms) == len(set(terms)),
         'protein or ordered term identities repeat.')
    need(all(isinstance(x, str) and x and not any(c in x for c in '\t\n\r ')
             for x in (*proteins, *terms)), 'invalid literal identity.')
    need(all(re.fullmatch(r'GO:[0-9]{7}', term) for term in terms),
         'prediction head is not a literal GO identifier.')


def score(value):
    value = float(value)
    need(math.isfinite(value) and 0 <= value <= 1, 'invalid sigmoid score; no clipping/rescaling.')
    return value


def raw_rows(proteins, terms, matrix):
    """All cells, including exact zero; text preserves the float32 value."""
    validate_identity(proteins, terms)
    need(len(matrix) == len(proteins), 'prediction row/identity count differs.')
    for protein, values in zip(proteins, matrix):
        need(len(values) == len(terms), 'prediction column/head count differs.')
        for term, value in zip(terms, values):
            yield f'{protein}\t{term}\t{score(value):.17g}\n'


def native_rows(proteins, terms, matrix):
    """The literal default native CLI cutoff/format, for parity only."""
    validate_identity(proteins, terms)
    need(len(matrix) == len(proteins), 'prediction row/identity count differs.')
    for protein, values in zip(proteins, matrix):
        need(len(values) == len(terms), 'prediction column/head count differs.')
        for term, value in zip(terms, values):
            value = score(value)
            if value >= 0.1:
                yield f'{protein}\t{term}\t{value:0.3f}\n'


def average_author_models(aspect, indexed_arrays):
    """Same fixed order and sequential float32 additions as native predict.py."""
    import numpy as np
    need(aspect in ENSEMBLES and tuple(indexed_arrays) == ENSEMBLES[aspect],
         'published ensemble membership/order differs.')
    first = next(iter(indexed_arrays.values()))
    need(first.ndim == 2 and first.dtype == np.float32, 'author matrix must be 2D float32.')
    total = np.zeros(first.shape, dtype=np.float32)
    for values in indexed_arrays.values():
        need(values.shape == first.shape and values.dtype == np.float32,
             'model matrix shape/dtype differs; no implicit casts.')
        need(np.isfinite(values).all() and (values >= 0).all() and (values <= 1).all(),
             'invalid native model score.')
        total += values
    return total / len(indexed_arrays)
