"""Pure, design-independent signature scoring and explicit eligibility checks.

The z-score is the equation in the unchanged MIT RoKAI ``rokai_inference.m``:
sum(measured targets)/(sample SD of all finite sites * sqrt(target count)).
No propagation, p-values, trained model, target labels or dataset lookup occurs
in inference. Kinase/site membership remains supplied evidence, not a claim of
direct catalysis. Study-specific readers and sample groups are separate inputs.
"""
from collections import defaultdict
from collections.abc import Mapping
import math
from numbers import Real
from statistics import fmean, stdev


def _finite(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("Supply numeric observations or explicit None; do not coerce strings/bools.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite values require an explicit upstream missing-value disposition.")
    return number


def log2_contrasts(sample_values, *, groups, control):
    """Difference of mean log2 intensities, requiring all declared replicates.

    Groups are arbitrary ordered names, not inferred from column substrings.
    Zero intensity is preserved in diagnostics but unavailable for a log;
    equal positive intensities yield an observed zero contrast. Replicate
    labels do not establish pairing, so no paired-replicate ratio is formed.
    """
    if (not isinstance(groups, Mapping) or not isinstance(sample_values, Mapping)
            or not isinstance(control, str) or control not in groups or len(groups) < 2):
        raise ValueError("Declare a control and at least one intervention group.")
    if any(not isinstance(members, (list, tuple)) or not members for members in groups.values()):
        raise ValueError("Explicit groups require nonempty lists of sample IDs.")
    samples = [sample for members in groups.values() for sample in members]
    if (any(not isinstance(name, str) or not name for name in groups)
            or any(not isinstance(sample, str) or not sample for sample in samples)
            or len(set(samples)) != len(samples) or set(sample_values) != set(samples)):
        raise ValueError("Explicit groups must be nonempty, disjoint and match the supplied sample fields.")
    values = {sample: _finite(sample_values[sample]) for sample in samples}
    diagnostics, log_means = {}, {}
    for group, members in groups.items():
        missing = [sample for sample in members if values[sample] is None]
        nonpositive = [sample for sample in members if values[sample] is not None and values[sample] <= 0]
        log_means[group] = (None if missing or nonpositive
                           else fmean(math.log2(values[sample]) for sample in members))
        diagnostics[group] = {"missing_samples": missing, "nonpositive_samples": nonpositive,
                              "declared_replicates": len(members), "all_replicates_usable": log_means[group] is not None}
    contrasts = {group: (None if log_means[group] is None or log_means[control] is None
                         else log_means[group] - log_means[control])
                 for group in groups if group != control}
    return {"contrasts": contrasts, "groups": diagnostics,
            "input_values": values, "replicate_pairing_assumed": False,
            "pseudocount_or_imputation_used": False}


def collapse_site_contrasts(records, *, conditions):
    """Collapse identical finite values; preserve conflicting groups as missing.

    Input records supply already-qualified literal site IDs and contrast
    values. Conflicting peptide/row summaries remain aggregation-unresolved;
    this is not evidence of biological disagreement. Raw records stay owned
    by the caller, and their identifiers are retained in the returned ledger.
    """
    conditions = tuple(conditions)
    if not conditions or len(set(conditions)) != len(conditions):
        raise ValueError("Declare unique condition IDs.")
    groups = defaultdict(list)
    for record in records:
        if (not isinstance(record.get("site_id"), str) or not record["site_id"]
                or set(record.get("contrasts", {})) != set(conditions)):
            raise ValueError("Qualified records require a site ID and every declared contrast field.")
        groups[record["site_id"]].append(record)
    output = {condition: {} for condition in conditions}
    ledger = []
    for site, rows in sorted(groups.items()):
        entry = {"site_id": site, "record_ids": [row.get("record_id") for row in rows], "conditions": {}}
        for condition in conditions:
            finite = sorted({number for row in rows
                             if (number := _finite(row["contrasts"][condition])) is not None})
            value = finite[0] if len(finite) == 1 else None
            state = ("one_unique_finite_value" if len(finite) == 1 else
                     "conflicting_finite_values_aggregation_unresolved" if finite else "no_usable_value")
            output[condition][site] = value
            entry["conditions"][condition] = {"status": state, "unique_finite_values": finite, "value": value}
        ledger.append(entry)
    return {"site_values": output, "aggregation": ledger}


def adjust_for_host_protein(site_values, *, site_hosts, protein_values):
    """Subtract same-qualified-host protein contrasts, without a fallback.

    A site without one supplied exact host, or a host without an eligible
    contrast, stays unavailable. This is a descriptive sensitivity, not a
    substitute for the published MSstatsPTM statistical model.
    """
    if set(site_values) != set(protein_values):
        raise ValueError("Protein and phosphosite condition rosters differ.")
    adjusted, ledger = {}, []
    for condition, sites in site_values.items():
        adjusted[condition] = {}
        for site, raw in sites.items():
            phospho = _finite(raw)
            host = site_hosts.get(site)
            host_available = isinstance(host, str) and bool(host.strip())
            protein = _finite(protein_values[condition].get(host)) if host_available else None
            value = phospho - protein if phospho is not None and protein is not None else None
            reason = (None if value is not None else "phosphosite_unavailable" if phospho is None else
                      "unique_host_unavailable" if not host_available else "host_protein_unavailable")
            adjusted[condition][site] = value
            ledger.append({"condition": condition, "site_id": site, "host": host,
                           "phosphosite_contrast": phospho, "protein_contrast": protein,
                           "adjusted_contrast": value, "unavailable_reason": reason})
    return {"site_values": adjusted, "adjustment": ledger, "unadjusted_fallback_used": False}


def infer_scores(site_values, signatures, *, min_sites=5):
    """Published raw RoKAI z-score, with a finite measured-site eligibility rule.

    Every profile in a comparison must receive the same site_values background.
    Duplicate signature membership adds no weight. No global mean is removed:
    centered KSEA is a distinct method and is not silently substituted here.
    """
    if type(min_sites) is not int or min_sites < 1:
        raise ValueError("min_sites must be a positive integer.")
    if not signatures or any(not isinstance(key, str) or not key for key in signatures):
        raise ValueError("Declare nonempty source/signature identifiers.")
    memberships = {}
    for source, sites in signatures.items():
        if isinstance(sites, str) or not isinstance(sites, (list, tuple, set, frozenset)):
            raise ValueError("Signature members must be an explicit site collection.")
        if any(not isinstance(site, str) or not site for site in sites):
            raise ValueError("Signature site identifiers must be nonempty strings.")
        memberships[source] = set(sites)
    scores, eligibility, backgrounds = {}, {}, {}
    for condition, sites in site_values.items():
        values = {site: _finite(value) for site, value in sites.items()}
        observed = [value for value in values.values() if value is not None]
        sd = stdev(observed) if len(observed) >= 2 else None
        valid_sd = sd is not None and sd > 0
        backgrounds[condition] = {"finite_sites": len(observed), "sample_sd": sd,
                                  "global_mean_subtracted": False}
        scores[condition], eligibility[condition] = {}, {}
        for source, members in memberships.items():
            used = sorted(site for site in members if values.get(site) is not None)
            n = len(used)
            reason = ("fewer_than_minimum_finite_distinct_sites" if n < min_sites else
                      "background_sample_SD_unavailable_or_zero" if not valid_sd else None)
            score = math.fsum(values[site] for site in used) / (sd * math.sqrt(n)) if reason is None else None
            scores[condition][source] = score
            eligibility[condition][source] = {"measured_distinct_sites": n, "used_site_ids": used,
                                               "eligible": reason is None, "unavailable_reason": reason}
    return {"scores": scores, "eligibility": eligibility, "backgrounds": backgrounds,
            "method": "published_RoKAI_raw_zscore", "minimum_finite_distinct_sites": min_sites}


def score_recovery(scores, expectations, *, candidate_ids, profile_kind="complete_candidate_universe"):
    """Signed average-tie ranks for an explicit complete candidate catalogue.

    Any number of conditions/studies/cells is allowed; expectation records
    carry that metadata rather than a fixed two-cell/drug naming convention.
    This function reports descriptive equal-case means only, no statistical
    test, confidence interval, global scientific accuracy or biological negatives.
    """
    if profile_kind != "complete_candidate_universe":
        raise ValueError("A partial signature catalogue cannot be ranked as a complete candidate universe.")
    candidates = tuple(candidate_ids)
    if not candidates or len(set(candidates)) != len(candidates) or any(not isinstance(c, str) or not c for c in candidates):
        raise ValueError("Declare one nonempty fixed candidate universe.")
    candidate_set, M = set(candidates), len(candidates)
    clean_scores = {}
    for condition, row in scores.items():
        if set(row) - candidate_set:
            raise ValueError("Predictions contain candidates outside the frozen universe.")
        clean_scores[condition] = {candidate: _finite(row.get(candidate)) for candidate in candidates}
    results, seen = [], set()
    for expected in expectations:
        condition, target, sign = (expected.get(key) for key in ("condition", "target", "sign"))
        if (not isinstance(condition, str) or not condition or not isinstance(target, str) or not target
                or type(sign) is not int or sign not in {-1, 1} or (condition, target) in seen):
            raise ValueError("Expectations need unique condition/target keys and explicit signs.")
        seen.add((condition, target))
        values = clean_scores.get(condition, {candidate: None for candidate in candidates})
        finite_candidates = sum(value is not None for value in values.values())
        value = values.get(target)
        missing = target not in candidate_set or value is None
        if missing:
            rank = float(M)
        else:
            target_signed = sign * value
            above = sum(v is not None and sign * v > target_signed for v in values.values())
            equal = sum(v is not None and sign * v == target_signed for v in values.values())
            rank = above + (equal + 1) / 2
        results.append({**expected, "score": value, "candidate_count": M, "rank": rank,
                        "finite_candidate_count": finite_candidates,
                        "rank_competition": ("no_finite_candidates" if finite_candidates == 0 else
                                             "single_finite_candidate" if finite_candidates == 1 else
                                             "multiple_finite_candidates"),
                        "more_than_five_finite_candidates": finite_candidates > 5,
                        "normalized_rank": rank / M, "abstained": missing,
                        "direction_agreement": bool(not missing and sign * value > 0),
                        "signed_top5": bool(not missing and rank <= 5)})
    return {"cases": results, "candidate_ids": list(candidates),
            "mean_normalized_rank": fmean(row["normalized_rank"] for row in results) if results else None,
            "direction_agreement": fmean(row["direction_agreement"] for row in results) if results else None,
            "signed_top5": fmean(row["signed_top5"] for row in results) if results else None,
            "target_score_coverage": fmean(not row["abstained"] for row in results) if results else None,
            "biological_negatives_assumed": False, "inferential_uncertainty_estimated": False}
