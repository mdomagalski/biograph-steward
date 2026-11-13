"""Design-weighted reference agreement with explicit unresolved identification.

The existing, tested survey estimator is reused. Reference provenance and
semantic applicability are checked by the source-specific scorer, not inferred
from a verdict string here. This module never outputs biological truth.
"""
from collections import Counter, defaultdict
from tools.sampled_audit.audit_statistics import _mean_and_variance

VERDICTS = ("agree", "disagree", "unknown")
FORMAT = "biograph-steward.reference-agreement-estimation.v1"


def need(condition, message):
    if not condition:
        raise ValueError("Reference estimation: " + message)


def estimate(strata, sample, labels):
    """Estimate three reference-status indicators on the full sampled frame.

    The input must contain one verdict for every selected case, including
    unknown. The secondary resolved-only ratio is explicitly conditional and
    never replaces the complete-frame denominator. Identification endpoints
    are exact only for a complete census of the supplied reference outcomes.
    """
    need(isinstance(strata, dict) and strata, "nonempty fixed strata are required.")
    for name, row in strata.items():
        need(isinstance(name, str) and name and isinstance(row, dict), "invalid stratum.")
        N, n = row.get("population_size"), row.get("sample_size")
        need(type(N) is int and type(n) is int and 1 <= n <= N, "invalid finite population/sample allocation.")
    need(isinstance(sample, (list, tuple)) and isinstance(labels, (list, tuple)), "complete row sequences required.")
    cases, assertions, groups = {}, set(), defaultdict(list)
    for row in sample:
        need(isinstance(row, dict), "sample rows must be objects.")
        case, aid, name = (row.get(k) for k in ("case_id", "assertion_id", "stratum"))
        need(isinstance(case, str) and case and case not in cases and isinstance(aid, str) and aid
             and aid not in assertions and name in strata, "sample identities repeat or are undeclared.")
        need(isinstance(row.get("family"), str) and row["family"]
             and row.get("disposition") in {"retained", "pruned", "not_intervened"}, "family/disposition missing.")
        cases[case] = row
        assertions.add(aid)
        groups[name].append(case)
    need(all(len(groups[name]) == design["sample_size"] for name, design in strata.items()),
         "case counts differ from the frozen allocation.")
    judged = {}
    for row in labels:
        need(isinstance(row, dict), "label rows must be objects.")
        case = row.get("case_id")
        need(case in cases and case not in judged and row.get("assertion_id") == cases[case]["assertion_id"]
             and row.get("stratum") == cases[case]["stratum"], "label is duplicate or belongs to a different case.")
        need(isinstance(row.get("verdict"), str) and row["verdict"] in VERDICTS,
             "use explicit agree/disagree/unknown; missing references cannot be dropped.")
        judged[case] = row
    need(set(judged) == set(cases), "every sampled case requires a verdict, including unknown.")

    def summary(names):
        selected_strata = {name: strata[name] for name in names}
        chosen = [case for name in names for case in groups[name]]
        rates = {verdict: _mean_and_variance(selected_strata, {
                    name: [int(judged[case]["verdict"] == verdict) for case in groups[name]] for name in names})
                 for verdict in VERDICTS}
        counts = Counter(judged[case]["verdict"] for case in chosen)
        a, d, u = (rates[key]["weighted_fraction"] for key in VERDICTS)
        census = all(row["population_size"] == row["sample_size"] for row in selected_strata.values())
        return {"population_units": sum(row["population_size"] for row in selected_strata.values()),
            "sampled_units": len(chosen), "sample_counts": {key: counts[key] for key in VERDICTS},
            "rates": rates, "resolved_reference_mass": a + d, "unknown_reference_mass": u,
            "resolved_only_agreement_ratio": {"value": a / (a + d) if a + d else None,
                "estimator": "Ratio of design-weighted agreement and resolved-reference totals",
                "conditional_population": "reference-resolved units only, not the full evaluation frame",
                "unknown_excluded_only_from_this_secondary_ratio": True,
                "variance_or_confidence_interval": None},
            "identification": {"lower": a, "upper": 1 - d,
                "endpoint_status": "exact_census_reference_identification_bounds" if census else
                                   "estimated_reference_identification_bound_endpoints",
                "lower_endpoint_design_SE": rates["agree"]["estimated_design_standard_error"],
                "upper_endpoint_design_SE": rates["disagree"]["estimated_design_standard_error"],
                "assumption": "Unresolved units may agree or disagree with the declared reference; supplied resolved labels are held fixed.",
                "biological_accuracy_bounds": False, "confidence_interval": None},
            "census": census}

    families, dispositions = defaultdict(set), defaultdict(set)
    for case in sample:
        families[case["family"]].add(case["stratum"])
        dispositions[case["disposition"]].add(case["stratum"])
    # Every atomic stratum must have one family and one disposition.
    for name, chosen in groups.items():
        need(len({cases[c]["family"] for c in chosen}) == len({cases[c]["disposition"] for c in chosen}) == 1,
             "an atomic stratum mixes family/disposition definitions.")
    return {"format": FORMAT, "unit": "qualified_assertion", "overall": summary(list(strata)),
        "by_family": {name: summary(sorted(names)) for name, names in sorted(families.items())},
        "by_disposition": {name: summary(sorted(names)) for name, names in sorted(dispositions.items())},
        "independent_biological_accuracy_estimate": None,
        "reference_error_or_expert_label_uncertainty_quantified": False,
        "unknown_dropped_from_full_frame_denominator": False,
        "limitations": ["Reference agreement depends on the source-specific, explicitly declared claim and label semantics.",
            "External expert labels are distinct from independent experiments and are not infallible biological truth.",
            "Design standard errors condition on supplied labels and exclude reference or matching errors.",
            "Zero observed variance is not certainty; small homogeneous samples retain the estimator's warning.",
            "Resolved-only agreement can be uninformative for positive-only references and is not a full-frame accuracy score.",
            "Sampled identification endpoints are estimates, not guaranteed population bounds or biological confidence intervals."]}
