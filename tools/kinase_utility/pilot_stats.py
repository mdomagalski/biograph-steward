"""Pure assessment of the seven frozen pilot arms; no file or reference access.

Implements plan ece0d709...a320 and pre-access amendment c2a72978...733.
Input is score_predictions output, after the driver's source-roster checks.
Bootstrap intervals are paired drug-resampling percentile95 intervals only;
other kinases are never assigned negative biological labels.
"""
from collections import Counter, defaultdict
from numbers import Real
from statistics import fmean
import math

import numpy as np

PLAN_SHA256 = "ece0d709d9b7a18109be0efe4bdc2afb47375830417cc3947d061f576275a320"
AMENDMENT_SHA256 = "c2a7297823b6a7fa493aafe9432bf358fefbc83f24b5cf12df50a69edae33733"
PRIMARY = "rokai_primary_zscore"
COMPARATORS = ("rokai_native_zscore", "rokai_unpruned_zscore")
ARMS = (PRIMARY, *COMPARATORS, "rokai_ne_zscore", "rokai_ks_only_zscore", "raw_zscore", "raw_mean")
FLOOR = {"primary_condition_target_cases": 20,
         "primary_distinct_resolved_target_genes": 5,
         "primary_cells": 2, "primary_complete_drugs": 5}
DRAWS = 10000
SEED = 20261112
METRICS = ("normalized_rank", "signed_top5_recovery", "sign_agreement", "target_score_coverage")


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    _need(isinstance(value, Real) and not isinstance(value, (bool, np.bool_))
          and math.isfinite(float(value)), "Expected a finite numeric value.")
    return float(value)


def _mean(rows, field):
    return fmean(row[field] for row in rows) if rows else None


def _same_number(actual, expected):
    if expected is None:
        return actual is None
    return isinstance(actual, Real) and not isinstance(actual, (bool, np.bool_)) and math.isclose(
        float(actual), expected, rel_tol=1e-12, abs_tol=1e-12)


def bootstrap_paired_rank_differences(differences):
    """Fixed two-comparator paired differences keyed by the same drug labels.

    Positive differences mean the preselected primary is worse. The same sorted
    drug resampling indices are shared by both comparisons. No CI for n<2.
    """
    _need(isinstance(differences, dict) and set(differences) == set(COMPARATORS),
          "Supply exactly the two fixed primary comparator difference maps.")
    _need(all(isinstance(differences[c], dict) for c in COMPARATORS), "Drug differences must be mappings.")
    drug_ids = tuple(sorted(differences[COMPARATORS[0]]))
    _need(all(isinstance(d, str) and d for d in drug_ids), "Drug labels must be nonempty strings.")
    _need(all(set(differences[c]) == set(drug_ids) for c in COMPARATORS),
          "Paired bootstrap drug labels differ between comparisons.")
    values = np.asarray([[_number(differences[c][d]) for d in drug_ids] for c in COMPARATORS])
    output = {"drug_ids": list(drug_ids), "n_drugs": len(drug_ids), "draws": DRAWS,
              "seed": SEED, "interval_method": "paired_drug_percentile_2.5_97.5_linear",
              "scope": "Descriptive resampling within this benchmark, not independent-study or clinical uncertainty.",
              "available": len(drug_ids) >= 2, "comparisons": {}}
    if len(drug_ids) >= 2:
        indices = np.random.default_rng(SEED).integers(0, len(drug_ids), size=(DRAWS, len(drug_ids)))
        means = values[:, indices].mean(axis=2)
    for i, comparator in enumerate(COMPARATORS):
        interval = (np.quantile(means[i], [0.025, 0.975], method="linear").tolist()
                    if output["available"] else None)
        output["comparisons"][comparator] = {
            "mean_primary_minus_comparator": float(values[i].mean()) if drug_ids else None,
            "percentile95_interval": interval,
            "upper95_bound_below_zero": bool(interval is not None and interval[1] < 0),
            "unavailable_reason": None if output["available"] else "fewer_than_two_complete_drugs"}
    return output


def _extract_arm(result):
    candidates, cells = tuple(result["candidate_genes"]), tuple(result["expected_cells"])
    _need(candidates and len(set(candidates)) == len(candidates)
          and all(isinstance(g, str) and g for g in candidates), "Invalid candidate gene roster.")
    _need(len(cells) == 2 and len(set(cells)) == 2
          and all(isinstance(c, str) and c for c in cells), "Exactly two declared cells are required.")
    M = len(candidates)
    _need(result["candidate_count_M"] == M, "Candidate-count commitment differs from roster.")
    by_condition = defaultdict(list)
    contexts, inventory, seen, gene_ids = {}, [], set(), {}
    directions = {}
    for original in result["per_target"]:
        condition, drug, cell, gene, gid = (original[k] for k in ("condition", "drug", "cell", "gene", "hgnc_id"))
        _need(all(isinstance(x, str) and x for x in (condition, drug, cell, gene, gid)), "Invalid qualified reference identity.")
        _need(cell in cells, "Qualified reference cell is outside the declared two-cell roster.")
        _need((condition, gene) not in seen, "Repeated condition/qualified-gene target.")
        seen.add((condition, gene))
        _need(condition not in contexts or contexts[condition] == (drug, cell), "Condition has conflicting reference context.")
        contexts[condition] = (drug, cell)
        _need(gene not in gene_ids or gene_ids[gene] == gid, "One gene maps to conflicting HGNC IDs.")
        gene_ids[gene] = gid
        sign = original["expected_sign"]
        _need(type(sign) is int and sign in {-1, 1}, "Invalid expected reference sign.")
        inventory.append((condition, drug, cell, gene, gid, sign))
        abstained = original["abstained"]
        _need(type(abstained) is bool, "Abstention flag must be explicit boolean.")
        activity = original["activity"]
        activity = None if activity is None else _number(activity)
        _need((activity is None) == abstained, "Activity and abstention disagree.")
        rank, normalized = _number(original["rank"]), _number(original["normalized_rank"])
        _need(original["candidate_count_M"] == M and 1 <= rank <= M
              and _same_number(normalized, rank / M), "Rank or fixed denominator is inconsistent.")
        _need(not abstained or rank == M, "Abstained target must receive worst rank M.")
        _need(abstained or gene in candidates, "Scored target is outside the fixed prediction universe.")
        agreement = bool(not abstained and sign * activity > 0)
        hit = bool(not abstained and rank <= 5)
        _need(type(original["sign_agreement"]) is bool and original["sign_agreement"] == agreement,
              "Direction agreement disagrees with signed activity.")
        _need(type(original["signed_top5_recovery"]) is bool and original["signed_top5_recovery"] == hit,
              "Top5 recovery disagrees with signed rank/abstention.")
        direction = ("missing" if abstained else "zero" if activity == 0 else
                     "agreement" if agreement else "opposite")
        directions[(condition, gene)] = direction
        by_condition[condition].append({"normalized_rank": normalized, "signed_top5_recovery": hit,
            "sign_agreement": agreement, "target_score_coverage": not abstained,
            "condition": condition, "drug": drug, "cell": cell, "gene": gene})
    by_drug = defaultdict(list)
    for condition, rows in by_condition.items():
        drug, cell = contexts[condition]
        by_drug[drug].append({"condition": condition, "drug": drug, "cell": cell,
                             **{k: _mean(rows, k) for k in METRICS}})
    complete, incomplete = {}, {}
    for drug, rows in sorted(by_drug.items()):
        counts = Counter(row["cell"] for row in rows)
        if set(counts) == set(cells) and all(counts[c] == 1 for c in cells):
            complete[drug] = rows
        else:
            incomplete[drug] = dict(counts)
    supplied = result["per_drug"]
    _need(len(supplied) == len({r["drug"] for r in supplied}) and {r["drug"] for r in supplied} == set(complete),
          "Declared primary drug IDs disagree with complete two-cell reference groups.")
    drug_metrics = {drug: {k: _mean(rows, k) for k in METRICS} for drug, rows in complete.items()}
    for row in supplied:
        _need(sorted(row["conditions"]) == sorted(x["condition"] for x in complete[row["drug"]]),
              "Declared primary drug conditions disagree with reference groups.")
        _need(all(_same_number(row[k], drug_metrics[row["drug"]][k]) for k in METRICS),
              "Declared primary drug metrics disagree with per-target aggregation.")
    macro = {k: _mean(list(drug_metrics.values()), k) for k in METRICS}
    result_fields = {"normalized_rank": "primary_macro_normalized_rank",
                    "signed_top5_recovery": "macro_signed_top5_recovery",
                    "sign_agreement": "macro_sign_agreement",
                    "target_score_coverage": "macro_target_score_coverage"}
    _need(all(_same_number(result[result_fields[k]], macro[k]) for k in METRICS),
          "Declared primary macro metrics disagree with complete-drug aggregation.")
    primary_conditions = {row["condition"] for rows in complete.values() for row in rows}
    primary_rows = [row for condition, rows in by_condition.items() if condition in primary_conditions for row in rows]
    cell_metrics = {cell: {k: _mean([row for rows in complete.values() for row in rows if row["cell"] == cell], k)
                           for k in METRICS} for cell in cells}
    return {"candidates": candidates, "cells": cells, "inventory": tuple(sorted(inventory)),
            "complete_drugs": tuple(sorted(complete)), "incomplete_drugs": incomplete,
            "primary_conditions": tuple(sorted(primary_conditions)), "primary_rows": primary_rows,
            "all_rows": [r for rows in by_condition.values() for r in rows], "directions": directions,
            "drug_metrics": drug_metrics, "macro": macro, "per_cell": cell_metrics,
            "reference_exclusions": result["reference_exclusions"],
            "duplicate_rows_collapsed": result["duplicate_condition_target_sign_rows_collapsed"]}


def assess_pilot(arm_results):
    """Assess exactly seven fixed arms; return population, summaries and gates.

    Does not authorize reference access or check the driver's source roster.
    Missing model targets count within both the primary denominator and coverage.
    """
    _need(isinstance(arm_results, dict) and set(arm_results) == set(ARMS), "Supply exactly the seven frozen arms.")
    arms = {arm: _extract_arm(arm_results[arm]) for arm in ARMS}
    primary = arms[PRIMARY]
    for arm, result in arms.items():
        for field in ("candidates", "cells", "inventory", "complete_drugs", "primary_conditions",
                      "reference_exclusions", "duplicate_rows_collapsed"):
            _need(result[field] == primary[field], "Arm differs in fixed candidate/reference population: " + arm + "/" + field)
    primary_rows, all_rows = primary["primary_rows"], primary["all_rows"]
    counts = {"primary_condition_target_cases": len(primary_rows),
              "primary_distinct_resolved_target_genes": len({r["gene"] for r in primary_rows}),
              "primary_cells": len({r["cell"] for r in primary_rows}),
              "primary_complete_drugs": len(primary["complete_drugs"])}
    checks = {key: counts[key] >= value for key, value in FLOOR.items()}
    differences = {comparator: {drug: primary["drug_metrics"][drug]["normalized_rank"]
                    - arms[comparator]["drug_metrics"][drug]["normalized_rank"]
                    for drug in primary["complete_drugs"]} for comparator in COMPARATORS}
    bootstrap = bootstrap_paired_rank_differences(differences)
    comparisons = {}
    for comparator in COMPARATORS:
        other = arms[comparator]
        available = bool(primary["complete_drugs"])
        comparisons[comparator] = {
            "rank_lower": bool(available and primary["macro"]["normalized_rank"] < other["macro"]["normalized_rank"]),
            **{metric + "_not_worse": bool(available and primary["macro"][metric] >= other["macro"][metric])
               for metric in ("signed_top5_recovery", "sign_agreement", "target_score_coverage")},
            "per_cell_rank_not_worse": {cell: bool(available and primary["per_cell"][cell]["normalized_rank"]
                <= other["per_cell"][cell]["normalized_rank"]) for cell in primary["cells"]}}
        comparisons[comparator]["all_point_checks_pass"] = (all(v for k, v in comparisons[comparator].items()
            if k != "per_cell_rank_not_worse") and all(comparisons[comparator]["per_cell_rank_not_worse"].values()))
    point_gate = all(checks.values()) and all(r["all_point_checks_pass"] for r in comparisons.values())
    interval_gate = all(bootstrap["comparisons"][c]["upper95_bound_below_zero"] for c in COMPARATORS)
    direction_counts = Counter(primary["directions"][(r["condition"], r["gene"])] for r in primary_rows)
    direction_macro = {}
    for category in ("agreement", "zero", "opposite", "missing"):
        per_drug = []
        for drug in primary["complete_drugs"]:
            per_cell = []
            for cell in primary["cells"]:
                rows = [r for r in primary_rows if r["drug"] == drug and r["cell"] == cell]
                per_cell.append(fmean(primary["directions"][(r["condition"], r["gene"])] == category for r in rows))
            per_drug.append(fmean(per_cell))
        direction_macro[category] = fmean(per_drug) if per_drug else None
    summaries = {arm: {"macro": arms[arm]["macro"], "per_cell": arms[arm]["per_cell"],
                      "per_drug": arms[arm]["drug_metrics"]} for arm in ARMS}
    ne = arms["rokai_ne_zscore"]["macro"]["normalized_rank"]
    primary_rank = primary["macro"]["normalized_rank"]
    return {"plan_sha256": PLAN_SHA256, "amendment_sha256": AMENDMENT_SHA256,
        "preselected_primary": PRIMARY, "primary_comparators": list(COMPARATORS),
        "primary_population": {**counts, "condition_ids": list(primary["primary_conditions"]),
                               "drug_ids": list(primary["complete_drugs"])},
        "all_qualified_reference_population": {"condition_target_cases": len(all_rows),
            "distinct_target_genes": len({r["gene"] for r in all_rows}),
            "condition_ids": sorted({r["condition"] for r in all_rows}),
            "drug_ids": sorted({r["drug"] for r in all_rows}),
            "cells": sorted({r["cell"] for r in all_rows}),
            "reference_exclusion_records": len(primary["reference_exclusions"]),
            "duplicate_condition_target_sign_rows_collapsed": primary["duplicate_rows_collapsed"]},
        "incomplete_reference_drug_groups": primary["incomplete_drugs"],
        "coverage_floor": {"requirements": dict(FLOOR), "checks": checks, "passed": all(checks.values())},
        "arm_summaries": summaries, "primary_comparison_checks": comparisons,
        "paired_rank_bootstrap": bootstrap,
        "primary_direction_categories": {"counts": {k: direction_counts[k] for k in direction_macro},
                                         "same_population_drug_macro_fractions": direction_macro},
        "point_estimate_benefit_gate_passed": bool(point_gate),
        "both_rank_intervals_upper95_below_zero": bool(interval_gate),
        "stronger_within_benchmark_support_gate_passed": bool(point_gate and interval_gate),
        "NE_mean_rank_lower_than_primary": bool(ne is not None and primary_rank is not None and ne < primary_rank),
        "limits": ["Expected intervention-target recovery, not measured kinase activity or PPI truth.",
                   "Other kinases are ranking alternatives, not confirmed biological negatives.",
                   "Drug resampling describes this benchmark; it is not independent-study or clinical uncertainty."]}
