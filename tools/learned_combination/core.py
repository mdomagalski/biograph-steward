"""Convex score mixing and selection from development objectives only.

The formula is adapted from DeepGOPlus; these are different component models
and a different, explicitly fixed development objective/grid. No labels,
ontology implementation, model inference, or final-test evaluation live here.
NumPy is an optional research-runtime dependency, imported only for arrays.
"""
from dataclasses import dataclass
import math
import re


ALPHA_GRID = tuple(i / 10 for i in range(11))
LOCALPLUS_UPPER_ROUNDOFF = 1e-10


def need(condition, message):
    if not condition:
        raise ValueError('Learned combination: ' + message)


def validate_axes(proteins, terms):
    """Preserve literal identities and their supplied order; never map aliases."""
    proteins, terms = tuple(proteins), tuple(terms)
    need(proteins and terms, 'nonempty protein and term axes are required.')
    need(all(isinstance(x, str) and x and not any(c.isspace() for c in x)
             for x in (*proteins, *terms)), 'invalid literal identity.')
    need(len(set(proteins)) == len(proteins) and len(set(terms)) == len(terms),
         'duplicate protein or term axis identity.')
    need(all(re.fullmatch(r'GO:[0-9]{7}', term) for term in terms),
         'term axis requires literal GO identifiers.')
    return proteins, terms


def validate_tolerance(tolerance):
    need(not isinstance(tolerance, bool)
         and tolerance in (0.0, LOCALPLUS_UPPER_ROUNDOFF),
         'only strict bounds or the qualified LocalPlus upper roundoff allowance are supported.')


@dataclass(frozen=True)
class ScoreMatrix:
    """An unpropagated score matrix on explicit, ordered, common axes.

    Values are represented as float64 without clipping or rescaling. Converting
    a float32 score to float64 retains its exact numerical value. The explicit
    upper allowance is for previously qualified LocalPlus roundoff only; it
    does not permit negative scores. Callers must not mutate ``values`` while
    the object is in use. Array construction does not copy an existing float64
    matrix, to avoid doubling the captured research matrices in memory.
    """

    proteins: tuple
    terms: tuple
    values: object
    upper_roundoff_tolerance: float = 0.0

    def __post_init__(self):
        import numpy as np

        proteins, terms = validate_axes(self.proteins, self.terms)
        validate_tolerance(self.upper_roundoff_tolerance)
        try:
            source = np.asarray(self.values)
            need(source.dtype.kind in 'fiu', 'scores must be real numeric values, not strings or booleans.')
            values = np.asarray(source, dtype=np.float64)
        except (TypeError, OverflowError) as error:
            raise ValueError('Learned combination: invalid numeric score array.') from error
        need(values.ndim == 2 and values.shape == (len(proteins), len(terms)),
             'score matrix shape differs from its ordered identity axes.')
        need(np.isfinite(values).all() and (values >= 0).all()
             and (values <= 1 + self.upper_roundoff_tolerance).all(),
             'scores require finite qualified [0,1] bounds; no clipping or rescaling.')
        object.__setattr__(self, 'proteins', proteins)
        object.__setattr__(self, 'terms', terms)
        object.__setattr__(self, 'values', values)


def convex_mix(localplus, deepgo, alpha):
    """Return raw ``alpha * LocalPlus + (1-alpha) * DeepGO`` scores.

    Both matrices must already use the same literal identities in the same
    order. Neither source receives this evaluator's ancestor propagation before
    this operation; base-model internals and propagated training seeds are retained.
    Missing cells must have been represented as zero for arithmetic
    only, never as biological-negative labels. Endpoints return exact copies
    of the corresponding validated source values.
    """
    need(isinstance(localplus, ScoreMatrix) and isinstance(deepgo, ScoreMatrix),
         'both inputs require explicit score matrices.')
    need(localplus.proteins == deepgo.proteins and localplus.terms == deepgo.terms,
         'ordered protein/term axes differ; no implicit sorting, alignment or alias mapping.')
    need(not isinstance(alpha, bool) and isinstance(alpha, (int, float))
         and math.isfinite(alpha) and 0 <= alpha <= 1,
         'alpha must be finite and in [0,1].')
    # Direct endpoint copies establish parity independently of multiplication,
    # summation, sparse missingness, or the unused component's dtype.
    if alpha == 0:
        values = deepgo.values.copy()
    elif alpha == 1:
        values = localplus.values.copy()
    else:
        values = alpha * localplus.values + (1 - alpha) * deepgo.values
    return ScoreMatrix(localplus.proteins, localplus.terms, values,
                       max(localplus.upper_roundoff_tolerance,
                           deepgo.upper_roundoff_tolerance))


def mix_then_propagate(localplus, deepgo, alpha, native_propagate):
    """Mix raw scores first, then call the supplied native propagation once.

    This module deliberately provides no replacement GO traversal or closure.
    ``native_propagate`` receives the mixed array, may modify it in place, and
    must return its result on exactly the same axes. The official evaluator's
    masks, roots, ontology and threshold policy remain outside this core.
    """
    need(callable(native_propagate), 'a native propagation callback is required.')
    mixed = convex_mix(localplus, deepgo, alpha)
    result = native_propagate(mixed.values)
    return ScoreMatrix(mixed.proteins, mixed.terms, result,
                       mixed.upper_roundoff_tolerance)


@dataclass(frozen=True)
class AlphaSelection:
    aspect: str
    development_id: str
    alpha: float
    development_micro_fmax: float
    objectives: tuple

    def to_dict(self):
        return {
            'aspect': self.aspect,
            'development_id': self.development_id,
            'alpha': self.alpha,
            'development_micro_fmax': self.development_micro_fmax,
            'alpha_grid': list(ALPHA_GRID),
            'development_objectives': [
                {'alpha': alpha, 'micro_fmax': value}
                for alpha, value in self.objectives
            ],
            'objective': 'maximum native development micro-Fmax',
            'tie_rule': 'smallest alpha on the fixed grid',
            'split_role': 'development',
        }


def select_development_alpha(aspect, development_micro_fmax, *, development_id,
                             split_role='development'):
    """Choose an alpha from all 11 native development objective values.

    This selector accepts scalar development objectives, not reference labels
    or final-test scores. The caller computes them with the existing native
    evaluator and records the development provenance before this selection.
    A role check prevents accidentally supplying a declared final-test split;
    it cannot independently verify how caller-provided objectives were made.
    """
    need(aspect in ('mf', 'bp', 'cc'), 'aspect must be exactly mf, bp or cc.')
    need(split_role == 'development', 'only development objectives may fit alpha; final-test input is forbidden.')
    need(isinstance(development_id, str) and development_id
         and development_id == development_id.strip(), 'a literal development provenance ID is required.')
    need(hasattr(development_micro_fmax, 'items'), 'development objective mapping is required.')
    need(len(development_micro_fmax) == len(ALPHA_GRID)
         and set(development_micro_fmax) == set(ALPHA_GRID)
         and not any(isinstance(key, bool) for key in development_micro_fmax),
         'exact fixed alpha grid 0.0 through 1.0 in steps of 0.1 is required.')
    objectives = []
    for alpha in ALPHA_GRID:
        value = development_micro_fmax[alpha]
        need(not isinstance(value, bool) and isinstance(value, (int, float))
             and math.isfinite(value) and 0 <= value <= 1,
             'native development micro-Fmax must be finite and in [0,1].')
        objectives.append((alpha, float(value)))
    # Iteration is always ascending, regardless of the input mapping order.
    # Only a strictly greater objective replaces the current choice.
    best_alpha, best_value = objectives[0]
    for alpha, value in objectives[1:]:
        if value > best_value:
            best_alpha, best_value = alpha, value
    return AlphaSelection(aspect, development_id, best_alpha, best_value,
                          tuple(objectives))
