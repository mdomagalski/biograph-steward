"""Design-weighted summaries of fixed sampled audit outcomes.

This is a small adapter for stratified simple random sampling without
replacement, not a biological judge or a new uncertainty model. Every sampled
case remains in each denominator. UNKNOWN outcomes are separate categories.
The sampling and evidence provenance are checked by the caller; this module
checks complete case alignment, strata sizes and outcome vocabulary.
"""
from collections import Counter, defaultdict
import math


FORMAT = "biograph-steward.stratified-audit-statistics.v1"
AXES = ("source_relative_support", "primary_evidence_support")
STATUSES = ("supported", "contradicted", "unresolved")
METHOD = "Fixed stratified simple random sampling without replacement; design-weighted audit-status indicators."


def _need(value, message):
    if not value:
        raise ValueError("Sampled audit statistics: " + message)


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _mean_and_variance(strata, values):
    """Published stratified mean and unbiased SRSWOR variance estimator.

    Values are the observed binary audit indicators, not biological truth.
    For stratum h, variance contribution is
    W_h**2 * (1-n_h/N_h) * p_h*(1-p_h)/(n_h-1).
    A non-census singleton cannot estimate its sample variance.
    """
    total = sum(s["population_size"] for s in strata.values())
    mean, variance = 0.0, 0.0
    singleton, boundary = [], []
    per_stratum = {}
    for name, design in strata.items():
        population, sampled = design["population_size"], design["sample_size"]
        positive = sum(values[name])
        proportion = positive / sampled
        weight = population / total
        mean += weight * proportion
        per_stratum[name] = {"positive_sample_units": positive,
            "sample_units": sampled, "sample_proportion": proportion,
            "population_fraction": weight}
        if population == sampled:
            continue
        if sampled == 1:
            singleton.append(name)
            continue
        variance += weight**2 * (1 - sampled / population) * proportion * (1 - proportion) / (sampled - 1)
        if positive in (0, sampled):
            boundary.append(name)
    estimable = not singleton
    return {"weighted_fraction": mean,
        "estimated_design_variance": variance if estimable else None,
        "estimated_design_standard_error": math.sqrt(variance) if estimable else None,
        "variance_unavailable_non_census_singleton_strata": singleton,
        "non_census_strata_with_no_observed_indicator_variation": boundary,
        "zero_estimated_variance_is_not_certainty": bool(boundary),
        "confidence_interval": None,
        "per_stratum": per_stratum}


def summarize(strata, sample_rows, review_rows, *, retained_assertion_ids=None):
    """Summarize complete, aligned AI-assisted audit outcomes.

    ``strata`` maps names to ``population_size`` and ``sample_size``. Each
    sample row supplies unique ``case_id``, unique ``assertion_id`` and a
    ``stratum``. Review rows supply one of supported/contradicted/unresolved
    for both supported axes and ``independent_scientific_correctness`` equal
    to ``unreviewed``. Extra metadata is preserved/verified by the caller.

    Optional retained IDs come from the caller's frozen intervention graph.
    An assertion is retained if any of its original evidence edges remains;
    computing and source-binding that decision is the caller's responsibility.
    Removal/loss summaries use the original population denominator and never
    infer biological error from a source-relative audit outcome.
    """
    _need(isinstance(strata, dict) and bool(strata), "provide nonempty fixed strata.")
    for name, design in strata.items():
        _need(_text(name) and isinstance(design, dict), "stratum names/designs are invalid.")
        population, sampled = design.get("population_size"), design.get("sample_size")
        _need(type(population) is int and type(sampled) is int
              and 1 <= sampled <= population,
              "every stratum needs positive integer population/sample sizes, with sample <= population.")
    _need(isinstance(sample_rows, (list, tuple)) and isinstance(review_rows, (list, tuple)),
          "sample and reviews must be complete row sequences.")
    sample, seen_assertions, by_stratum = {}, set(), defaultdict(list)
    for row in sample_rows:
        _need(isinstance(row, dict), "sample rows must be objects.")
        case, assertion, name = (row.get(k) for k in ("case_id", "assertion_id", "stratum"))
        _need(_text(case) and case not in sample and _text(assertion)
              and assertion not in seen_assertions and _text(name) and name in strata,
              "sample cases/assertions must be unique and belong to a declared stratum.")
        sample[case] = row
        seen_assertions.add(assertion)
        by_stratum[name].append(case)
    _need(all(len(by_stratum[name]) == design["sample_size"] for name, design in strata.items()),
          "sample counts differ from the fixed stratum allocation.")
    reviews = {}
    for row in review_rows:
        _need(isinstance(row, dict), "review rows must be objects.")
        case = row.get("case_id")
        _need(_text(case) and case in sample and case not in reviews,
              "review case is unknown or duplicated.")
        for name in ("assertion_id", "stratum"):
            _need(name not in row or row[name] == sample[case][name],
                  "review identity differs from its sampled case.")
        _need(all(type(row.get(axis)) is str and row[axis] in STATUSES for axis in AXES),
              "each audit axis needs supported, contradicted or unresolved; missing outcomes cannot be dropped.")
        _need(row.get("independent_scientific_correctness") == "unreviewed",
              "independent biological labels/scoring are not implemented by this AI-assisted adapter.")
        reviews[case] = row
    _need(set(reviews) == set(sample), "every sampled case needs an explicit review, including unresolved outcomes.")
    if retained_assertion_ids is not None:
        _need(isinstance(retained_assertion_ids, (set, frozenset))
              and all(_text(value) for value in retained_assertion_ids),
              "retained assertion IDs must be an explicit set from the verified intervention.")

    def indicator(predicate):
        return _mean_and_variance(strata, {name: [int(predicate(case)) for case in cases]
                                          for name, cases in by_stratum.items()})

    axes = {}
    for axis in AXES:
        counts = Counter(row[axis] for row in reviews.values())
        statuses = {status: indicator(lambda case, status=status: reviews[case][axis] == status)
                    for status in STATUSES}
        lower = statuses["supported"]["weighted_fraction"]
        upper = lower + statuses["unresolved"]["weighted_fraction"]
        output = {"sample_counts": {status: counts[status] for status in STATUSES},
            "statuses": statuses,
            "weighted_unresolved_fraction": statuses["unresolved"]["weighted_fraction"],
            "weighted_sample_completion_range": {"lower": lower, "upper": upper,
                "interpretation": "Range obtained by assigning all sampled unresolved outcomes to contradicted or supported. Not population accuracy bounds or a confidence interval."},
            "independent_biological_accuracy": None}
        if retained_assertion_ids is not None:
            removed = lambda case: sample[case]["assertion_id"] not in retained_assertion_ids
            output["paired_intervention"] = {
                "denominator": "original_frozen_population_of_assertions",
                "source_relative_audit_outcomes_are_not_scientific_error_labels": True,
                "sample_counts_removed": {status: sum(removed(case) and reviews[case][axis] == status
                                                       for case in sample) for status in STATUSES},
                "population_weighted_removed_status_fractions": {
                    status: indicator(lambda case, status=status: removed(case) and reviews[case][axis] == status)
                    for status in STATUSES},
                "population_weighted_retained_fraction": indicator(lambda case: not removed(case)),
                "biological_error_removal_or_valid_claim_loss_established": False}
        axes[axis] = output
    return {"format": FORMAT, "method": METHOD,
        "population_assertions": sum(s["population_size"] for s in strata.values()),
        "sampled_assertions": len(sample), "reviewed_sample_cases": len(reviews),
        "strata": {name: {"population_size": d["population_size"], "sample_size": d["sample_size"],
                    "inclusion_probability": {"numerator": d["sample_size"], "denominator": d["population_size"]},
                    "inverse_probability_weight": d["population_size"] / d["sample_size"]}
                   for name, d in strata.items()},
        "axes": axes,
        "independent_scientific_correctness": {"status": "not_assessed", "unreviewed_sample_cases": len(sample),
            "accuracy_estimate": None, "confidence_interval": None},
        "sampling_uncertainty_only": True,
        "biological_judge_calibration_or_label_error_uncertainty_quantified": False,
        "scientific_accuracy_measured": False,
        "limits": [
            "Audit-status fractions estimate outcomes of the declared AI-assisted review procedure, not independent biological truth.",
            "Design-based standard errors are conditional on supplied outcomes and the declared fixed stratified SRSWOR design.",
            "A zero estimated sample variance does not establish certainty, especially in small or homogeneous observed samples.",
            "Unresolved cases remain in the original denominator; completion ranges do not include sampling or annotation error.",
            "Source/primary-evidence labels are assessed separately; supplied retained IDs and evidence provenance need caller verification.",
            "No hypothesis test, calibrated biological confidence interval or independent scientific pruning gain is produced."]}
