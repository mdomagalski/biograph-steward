"""Describe score/background shifts without interpreting or repairing biology.

This post-scoring diagnostic never receives expected intervention signs. It
does not center, normalize, impute, retune thresholds or change predictions.
Counts and summaries make globally shifted or nearly uniform score panels
visible; they cannot establish whether a shift is technical or biological.
"""
from statistics import fmean, median

from tools.kinase_utility.signature_comparison import _finite


def _summary(values):
    finite = [number for value in values if (number := _finite(value)) is not None]
    positive, negative, zero = (sum(value > 0 for value in finite),
                                sum(value < 0 for value in finite),
                                sum(value == 0 for value in finite))
    return {"finite_count": len(finite), "mean": fmean(finite) if finite else None,
            "median": median(finite) if finite else None,
            "positive": positive, "negative": negative, "zero": zero,
            "all_finite_values_positive": bool(finite) and positive == len(finite),
            "all_finite_values_negative": bool(finite) and negative == len(finite)}


def describe_signal_background(site_values, scores):
    """Summarize explicitly paired condition maps, preserving all inputs."""
    if set(site_values) != set(scores):
        raise ValueError("Site-background and score condition rosters differ.")
    return {"conditions": {condition: {"site_background": _summary(values.values()),
                "source_scores": _summary(scores[condition].values())}
            for condition, values in site_values.items()},
            "expected_target_signs_used": False, "predictions_changed": False,
            "technical_or_biological_cause_established": False,
            "normalization_recommended_automatically": False}
