"""Pure INMC outcome/scoring adapter for use only after the external freeze gate.

This module performs no filesystem/network access and cannot authenticate the
source archive or authorize opening it. Its caller must enforce the freeze and
source fingerprints. The fixed eligibility rule is the declared narrower
complete-scored adaptation in inmc_assay_contract_20261022.json.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
import hashlib
import json
import math
from numbers import Real
import re

HEADER = b"source\ttarget\tfreq\tscore_assay1\tscore_assay2\tscore_assay3"
GENE = re.compile(r"ENSG[0-9]{11}\Z")
DEFINITIVE = {"Positive", "Negative"}
EXCLUDED = {"Auto-activator", "Not tested", "Not scored"}
METRICS = ("average_precision", "roc_auc")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _pair(value):
    if (not isinstance(value, (tuple, list)) or len(value) != 2 or
            any(not isinstance(g, str) or not GENE.fullmatch(g) for g in value)):
        raise ValueError("Expected two exact original ENSG identifiers, without alias or version repair.")
    return tuple(sorted(value))


def _candidates(rows):
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError("Expected the complete nonempty frozen candidate identity list.")
    result, identifiers = {}, set()
    for index, row in enumerate(rows):
        pair = _pair(row.get("original_genes") if isinstance(row, Mapping) else row)
        identifier = row.get("id") if isinstance(row, Mapping) else f"candidate:{index:05d}"
        if (not isinstance(identifier, str) or not identifier or identifier != identifier.strip() or
                identifier in identifiers or pair in result):
            raise ValueError("Candidate identifiers and unordered pairs must be unique.")
        if isinstance(row, Mapping) and "self_pair" in row and row["self_pair"] is not (pair[0] == pair[1]):
            raise ValueError("Candidate self-pair flag disagrees with original identity.")
        result[pair] = identifier
        identifiers.add(identifier)
    return result


def materialize(panel_bytes, expected_candidates, author_positive_pairs):
    """Validate fixed identities, derive complete-assay labels and reconcile Fig.6.

    Author positives are a required independent reconciliation input, never the
    source of negative labels. Positives outside the eligible subset are allowed.
    Duplicate/reverse panel rows must have identical ordered assay code triples;
    each raw orientation and opaque freq value remains in source_rows.
    """
    if not isinstance(panel_bytes, bytes):
        raise ValueError("Panel input must be explicit source bytes.")
    expected = _candidates(expected_candidates)
    lines = panel_bytes.splitlines()
    if not lines or lines[0] != HEADER:
        raise ValueError("Unexpected INMC source header.")
    staged = []
    for number, raw in enumerate(lines[1:], 2):
        fields = raw.split(b"\t")
        if len(fields) != 6:
            raise ValueError(f"Unexpected source width at row {number}.")
        try:
            original = [v.decode("ascii") for v in fields[:2]]
        except UnicodeDecodeError as error:
            raise ValueError("Non-ASCII original gene identity.") from error
        staged.append((number, _pair(original), original, fields, raw))
    actual = {pair for _, pair, _, _, _ in staged}
    if actual != set(expected):
        raise ValueError("Full candidate identity population mismatch; outcome fields were not decoded.")
    if author_positive_pairs is None:
        raise ValueError("The author-positive reference is required; its complement is not a negative set.")
    try:
        author = {_pair(row.get("original_genes") if isinstance(row, Mapping) else row)
                  for row in author_positive_pairs}
    except TypeError as error:
        raise ValueError("Author-positive reference must be an explicit pair iterable.") from error
    groups = defaultdict(list)
    for number, pair, original, fields, raw in staged:
        try:
            codes = tuple(v.decode("utf-8") for v in fields[3:])
            freq = fields[2].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"Invalid text encoding at source row {number}.") from error
        if any(code not in DEFINITIVE | EXCLUDED for code in codes):
            raise ValueError(f"Unexpected or empty assay code at source row {number}; source review required.")
        if groups[pair] and tuple(groups[pair][0]["assay_codes"]) != codes:
            raise ValueError("Duplicate/reverse rows have contradictory assay codes; source review required.")
        groups[pair].append({"source_row": number, "source": original[0], "target": original[1],
                             "freq_raw": freq, "assay_codes": list(codes),
                             "raw_record_sha256": hashlib.sha256(raw).hexdigest()})
    rows, eligible = [], set()
    for pair, source_rows in sorted(groups.items()):
        codes = source_rows[0]["assay_codes"]
        complete = all(code in DEFINITIVE for code in codes)
        label = int("Positive" in codes) if complete else None
        if complete:
            eligible.add(pair)
            if (pair in author) != bool(label):
                raise ValueError("Eligible assay label disagrees with author-positive reference; reporting blocked.")
        self_pair = pair[0] == pair[1]
        rows.append({"id": expected[pair], "original_genes": list(pair), "self_pair": self_pair,
                     "assay_codes": codes, "eligible_complete_assays": complete,
                     "eligible_primary_off_diagonal": complete and not self_pair, "label": label,
                     "outcome": ("assay_detected" if label == 1 else "assay_not_detected" if label == 0 else None),
                     "exclusion_codes": sorted(set(codes) & EXCLUDED), "source_rows": source_rows,
                     "duplicate_source_rows": len(source_rows) - 1,
                     "author_reference_reconciled": complete})
    coverage = _population(rows)
    coverage.update({"source_rows": len(staged), "duplicate_source_rows": len(staged) - len(rows),
                     "pairs_with_duplicate_source_rows": sum(len(v) > 1 for v in groups.values()),
                     "source_code_patterns": dict(Counter(" | ".join(row["assay_codes"])
                         for values in groups.values() for row in values))})
    return {"format": "biograph-steward.inmc-materialized-outcomes.v1", "rows": rows,
            "panel_sha256": hashlib.sha256(panel_bytes).hexdigest(),
            "candidate_identity_sha256": _digest(sorted((list(pair), key) for pair, key in expected.items())),
            "author_positive_identity_sha256": _digest(sorted(author)), "coverage": coverage,
            "reference_reconciliation": {"status": "passed", "eligible_pairs_checked": len(eligible),
                "eligible_positive_pairs": sum(r["label"] == 1 for r in rows),
                "eligible_negative_pairs": sum(r["label"] == 0 for r in rows),
                "author_positives_outside_eligible_subset": len(author - eligible),
                "author_complement_used_for_negatives": False},
            "limitations": ["Complete-scored subset; not the authors' full-panel adjudication.",
                "Assay non-detection is not universal biological noninteraction.",
                "Original gene identities do not establish assayed construct or isoform identity.",
                "Caller must enforce full protocol freeze and authenticate source artifacts before this pure function."]}


def _population(rows):
    strata = defaultdict(list)
    for row in rows:
        diagonal = "self" if row["self_pair"] else "off_diagonal"
        status = "complete" if row["eligible_complete_assays"] else "excluded"
        strata[f"{diagonal}_{status}"].append(row)
    return {"nominated_pairs": len(rows), "off_diagonal_pairs": sum(not r["self_pair"] for r in rows),
            "self_pairs": sum(r["self_pair"] for r in rows),
            "primary_eligible_pairs": sum(r["eligible_primary_off_diagonal"] for r in rows),
            "excluded_code_patterns": dict(Counter(" | ".join(r["assay_codes"]) for r in rows
                                                   if not r["eligible_complete_assays"])),
            "strata": {name: {"pairs": len(values), "positives": sum(r["label"] == 1 for r in values),
                               "negatives": sum(r["label"] == 0 for r in values)}
                       for name, values in sorted(strata.items())}}


def _validated_rows(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected complete materialized candidate rows.")
    seen_ids, seen_pairs = set(), set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("Malformed materialized row.")
        pair = _pair(row.get("original_genes"))
        key = row.get("id")
        codes = row.get("assay_codes")
        if (not isinstance(key, str) or not key or key in seen_ids or pair in seen_pairs or
                not isinstance(codes, list) or len(codes) != 3 or
                any(not isinstance(c, str) or c not in DEFINITIVE | EXCLUDED for c in codes)):
            raise ValueError("Duplicate or malformed materialized candidate.")
        complete = all(code in DEFINITIVE for code in codes)
        self_pair = pair[0] == pair[1]
        label = int("Positive" in codes) if complete else None
        if (row.get("self_pair") is not self_pair or row.get("eligible_complete_assays") is not complete or
                row.get("eligible_primary_off_diagonal") is not (complete and not self_pair) or
                row.get("label") != label or (label is not None and type(row.get("label")) is not int) or
                row.get("author_reference_reconciled") is not complete):
            raise ValueError("Materialized row violates eligibility or author-reference reconciliation.")
        seen_ids.add(key); seen_pairs.add(pair)
    return rows


def score_comparison(rows, scores_by_arm_seed, *, baseline_arm="rgcn_baseline",
                     enriched_arm="rgcn_enriched", coverage_by_gene=None):
    """Score identical eligible off-diagonal populations using native sklearn.

    scores_by_arm_seed maps arm -> seed -> candidate ID -> score. Scores are
    already the frozen arithmetic mean of both orientations. Known excluded or
    self-pair scores may be supplied, but are never primary evaluation records.
    Leave-one-gene-out calculations are influence diagnostics, not confidence
    intervals, independent resamples, or retraining.
    """
    rows = _validated_rows(rows)
    if (not isinstance(scores_by_arm_seed, Mapping) or baseline_arm == enriched_arm or
            not {baseline_arm, enriched_arm} <= scores_by_arm_seed.keys()):
        raise ValueError("Both distinct paired comparison arms are required.")
    known = {r["id"] for r in rows}
    eligible = sorted((r for r in rows if r["eligible_primary_off_diagonal"]), key=lambda r: r["id"])
    keys = [r["id"] for r in eligible]
    labels = [r["label"] for r in eligible]
    if set(labels) != {0, 1}:
        raise ValueError("Primary evaluation requires both observed assay classes.")
    normalized, seeds, scored_ids = {}, None, None
    for arm, values in scores_by_arm_seed.items():
        if not isinstance(arm, str) or not arm or not isinstance(values, Mapping) or not values:
            raise ValueError("Malformed arm/seed score mapping.")
        by_seed = {}
        for seed, scores in values.items():
            if (type(seed) not in (str, int) or not str(seed).isdigit() or
                    str(int(seed)) != str(seed) or str(seed) in by_seed or not isinstance(scores, Mapping)):
                raise ValueError("Seed identifiers must be unique canonical nonnegative integers.")
            if (not set(keys) <= scores.keys() or not scores.keys() <= known or
                    any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in scores.values())):
                raise ValueError("Missing, unknown or nonfinite candidate score; primary reporting blocked.")
            if scored_ids is None:
                scored_ids = set(scores)
            if set(scores) != scored_ids:
                raise ValueError("Candidate score population differs between arms or seeds.")
            by_seed[str(seed)] = {key: float(value) for key, value in scores.items()}
        if seeds is None:
            seeds = set(by_seed)
        if set(by_seed) != seeds:
            raise ValueError("Paired seed sets differ between arms.")
        normalized[arm] = by_seed
    from sklearn import __version__ as sklearn_version
    from sklearn.metrics import average_precision_score, roc_auc_score

    def metric(subset, arm, seed):
        y = [r["label"] for r in subset]
        if set(y) != {0, 1}:
            return None
        predictions = [normalized[arm][seed][r["id"]] for r in subset]
        return {"average_precision": float(average_precision_score(y, predictions)),
                "roc_auc": float(roc_auc_score(y, predictions))}

    seeds = sorted(seeds, key=int)
    metrics = {arm: {seed: metric(eligible, arm, seed) for seed in seeds} for arm in sorted(normalized)}
    deltas = {seed: {key: metrics[enriched_arm][seed][key] - metrics[baseline_arm][seed][key]
                     for key in METRICS} for seed in seeds}
    influence = []
    for gene in sorted({g for r in eligible for g in r["original_genes"]}):
        retained = [r for r in eligible if gene not in r["original_genes"]]
        value = {"omitted_original_gene": gene, "remaining_pairs": len(retained),
                 "removed_pairs": len(eligible) - len(retained),
                 "status": "scored" if {r["label"] for r in retained} == {0, 1} else "insufficient_class_support",
                 "paired_seed_deltas": {}}
        if value["status"] == "scored":
            for seed in seeds:
                a, b = metric(retained, baseline_arm, seed), metric(retained, enriched_arm, seed)
                delta = {key: b[key] - a[key] for key in METRICS}
                value["paired_seed_deltas"][seed] = {"delta": delta,
                    "change_from_full_delta": {key: delta[key] - deltas[seed][key] for key in METRICS}}
        influence.append(value)
    ranges = {}
    for seed in seeds:
        ranges[seed] = {}
        for key in METRICS:
            values = [r["paired_seed_deltas"][seed]["delta"][key] for r in influence if r["status"] == "scored"]
            ranges[seed][key] = {"minimum": min(values), "maximum": max(values)} if values else None
    coverage = _population(rows)
    coverage["primary_scored_pairs_per_arm_seed"] = len(eligible)
    coverage["optional_gene_metadata"] = _gene_coverage(rows, coverage_by_gene)
    return {"format": "biograph-steward.inmc-scored-comparison.v1", "sklearn_version": sklearn_version,
            "task": "retrospective recorded assay-detection recovery", "eligible_candidate_ids": keys,
            "eligible_population_sha256": _digest([(r["id"], r["original_genes"], r["label"]) for r in eligible]),
            "coverage": coverage, "metrics_by_arm_seed": metrics,
            "paired_comparison": {"baseline_arm": baseline_arm, "enriched_arm": enriched_arm,
                                  "deltas_by_seed": deltas},
            "leave_one_original_gene_out": {"interpretation": "descriptive influence only; no formal confidence interval",
                "retraining_performed": False, "records": influence, "delta_ranges_by_seed": ranges},
            "formal_confidence_interval": None, "statistical_significance_claimed": False,
            "metrics_implementation": {"average_precision": "sklearn.metrics.average_precision_score (non-interpolated)",
                                       "roc_auc": "sklearn.metrics.roc_auc_score"}}


def _gene_coverage(rows, metadata):
    if metadata is None:
        return {"status": "not_supplied"}
    if not isinstance(metadata, Mapping):
        raise ValueError("Optional gene metadata must be a mapping.")
    for gene, value in metadata.items():
        if (not isinstance(gene, str) or not GENE.fullmatch(gene) or not isinstance(value, Mapping) or
                not value.keys() <= {"mapping", "context", "training_degree"}):
            raise ValueError("Malformed optional gene coverage metadata.")
        for name in ("mapping", "context"):
            if value.get(name) is not None and type(value[name]) is not bool:
                raise ValueError("Mapping/context coverage must be true, false or unknown.")
        degree = value.get("training_degree")
        if degree is not None and (type(degree) is not int or degree < 0):
            raise ValueError("Training degree must be a nonnegative integer or unknown.")
    strata = defaultdict(lambda: {"pairs": 0, "mapping_endpoints": Counter(), "context_endpoints": Counter(),
                                  "degree_by_endpoint": Counter()})
    for row in rows:
        name = ("self" if row["self_pair"] else "off_diagonal") + ("_complete" if row["eligible_complete_assays"] else "_excluded")
        group = strata[name]; group["pairs"] += 1
        for gene in row["original_genes"]:
            value = metadata.get(gene, {})
            for field in ("mapping", "context"):
                label = "unknown" if value.get(field) is None else "present" if value[field] else "absent"
                group[field + "_endpoints"][label] += 1
            degree = value.get("training_degree")
            group["degree_by_endpoint"]["unknown" if degree is None else str(degree)] += 1
    return {"status": "supplied", "unit": "pair endpoints; self-pair endpoint appears twice",
            "strata": {name: {key: dict(value) if isinstance(value, Counter) else value for key, value in group.items()}
                       for name, group in sorted(strata.items())}}
