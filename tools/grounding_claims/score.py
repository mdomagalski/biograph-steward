"""Score a bounded expert-curation grounding-error triage task.

This module assigns no new biological gold labels. ``label_pairs`` admits only
unanimous native ``correct`` or ``grounding`` tags for a selected statement /
source-hash pair. Duplicate curation rows are counted, not majority votes.
All other tags, absent tags and conflicts remain outside this endpoint.

IDs are canonical signed-decimal strings (an optional minus, no plus sign,
leading zeroes, whitespace or negative zero). Native Python ints are accepted
and rendered to that form; bools and floats are rejected. No source grounding
score is read, calibrated or interpreted as a truth probability.

Public functions:

* ``label_pairs(raw_curations, selected_pairs)`` returns a mapping from canonical
  ``(pa_hash, source_hash)`` tuples to records with ``label``, native tag counts,
  missing-tag count and total curation-row count. Only selected rows' tag fields
  are accessed. The caller can serialize these records into its private ledger.
* ``metrics(rows)`` accepts rows with ``gold`` and ``status``. Optional case IDs
  must be supplied for every row or no row. The native ``candidate_conflict``
  flag, when present, is True for a conflict, False for no conflict and None
  for unresolved/model-error abstentions. Other optional flat flags named
  ``resolved`` or after a status are strict booleans consistent with the status.
  Other metadata, including nested ``input`` and source-model scores, is not
  inspected.
* ``compare_methods(cases, predictions_by_arm, labels)`` accepts unique case rows
  with ``case_id``, ``pa_hash`` and ``source_hash``; each arm maps exactly those
  case IDs to a status string or a record with ``status``. Labels are the mapping
  produced above (direct endpoint-label strings are also accepted). Missing or
  outside-endpoint labels and missing/extra predictions fail rather than become
  negatives or silently disappear. Returned common-resolved metrics are an
  explicitly secondary all-arm intersection; full-denominator metrics remain
  primary. Pairwise changes are right arm minus left arm.
"""

from collections import Counter
from collections.abc import Mapping
from itertools import combinations
import re


GOLD_LABELS = ("grounding_error", "correctly_grounded")
STATUSES = ("candidate_conflict", "no_conflict", "unresolved", "model_error")
RESOLVED = frozenset(("candidate_conflict", "no_conflict"))
OUTSIDE_ENDPOINT = "outside_endpoint_or_conflict"
METRIC_NAMES = (
    "precision", "error_recall", "false_conflict_rate", "coverage",
    "resolved_accuracy",
)
_DECIMAL_ID = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_MISSING = object()


def _rows(value, name):
    if isinstance(value, (str, bytes, Mapping)):
        raise ValueError(name + " must be an iterable of rows.")
    try:
        return iter(value)
    except TypeError as exc:
        raise ValueError(name + " must be an iterable of rows.") from exc


def _decimal_id(value, name):
    if type(value) is int:
        return str(value)
    if (not isinstance(value, str) or not _DECIMAL_ID.fullmatch(value)
            or value == "-0"):
        raise ValueError(name + " must be a canonical signed-decimal ID.")
    return value


def _pair(value, name):
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError(name + " must be a two-item ID tuple.")
    return (_decimal_id(value[0], name + ".pa_hash"),
            _decimal_id(value[1], name + ".source_hash"))


def _row_pair(row, name):
    if not isinstance(row, Mapping):
        raise ValueError(name + " must be a mapping.")
    try:
        return _pair((row["pa_hash"], row["source_hash"]), name)
    except KeyError as exc:
        raise ValueError(name + " lacks a statement/source ID.") from exc


def _case_id(value, name):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(name + " must be a nonempty, unpadded string.")
    return value


def _gold(value):
    if value not in GOLD_LABELS or not isinstance(value, str):
        raise ValueError("Every scored case requires an admitted endpoint gold label.")
    return value


def _status(row):
    if not isinstance(row, Mapping):
        raise ValueError("A prediction/metric row must be a mapping.")
    value = row.get("status", _MISSING)
    if not isinstance(value, str) or value not in STATUSES:
        raise ValueError("Unknown or missing prediction status.")
    if "candidate_conflict" in row:
        expected = (True if value == "candidate_conflict" else
                    False if value == "no_conflict" else None)
        # Identity checks reject 0/1, which compare equal to False/True.
        if row["candidate_conflict"] is not expected:
            raise ValueError("Native candidate_conflict flag disagrees with status.")
    flags = {name: value == name for name in STATUSES if name != "candidate_conflict"}
    flags["resolved"] = value in RESOLVED
    for name, expected in flags.items():
        if name in row and (type(row[name]) is not bool or row[name] != expected):
            raise ValueError("Prediction boolean flag disagrees with status: " + name)
    return value


def label_pairs(raw_curations, selected_pairs):
    """Admit unanimous native labels, reading tags only after the ID filter.

    ``native_tag_counts`` is a list of ``{tag, count}`` records so that a native
    null tag remains distinct from an absent tag field. Non-string/non-null
    tags in a selected row are source-format errors. Unselected tag values are
    never read or validated, even if malformed. Missing selected pairs remain
    explicit outside-endpoint records with zero rows.
    """
    selected = {}
    for value in _rows(selected_pairs, "selected_pairs"):
        pair = _pair(value, "selected pair")
        if pair in selected:
            raise ValueError("Duplicate selected statement/source pair.")
        selected[pair] = {"rows": 0, "missing": 0, "tags": Counter()}
    curations = _rows(raw_curations, "raw_curations")
    if selected:
        for row in curations:
            pair = _row_pair(row, "curation row")
            if pair not in selected:
                continue  # Do not inspect or validate a reserved row's tag.
            state = selected[pair]
            state["rows"] += 1
            tag = row.get("tag", _MISSING)
            if tag is _MISSING:
                state["missing"] += 1
            else:
                if tag is not None and not isinstance(tag, str):
                    raise ValueError("A selected native tag must be a string or null.")
                state["tags"][tag] += 1
    labels = {}
    for pair, state in selected.items():
        tags = state["tags"]
        label = OUTSIDE_ENDPOINT
        if state["rows"] and not state["missing"]:
            if set(tags) == {"correct"}:
                label = "correctly_grounded"
            elif set(tags) == {"grounding"}:
                label = "grounding_error"
        ordered = sorted(tags, key=lambda tag: (tag is not None, tag or ""))
        labels[pair] = {
            "label": label,
            "native_tags": ordered,
            "native_tag_counts": [{"tag": tag, "count": tags[tag]} for tag in ordered],
            "missing_tag_row_count": state["missing"],
            "curation_row_count": state["rows"],
        }
    return labels


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def metrics(rows):
    """Return full-denominator triage metrics and resolved-only confusion.

    Error recall and false-conflict rate use all cases of the relevant gold
    class, including abstentions. Resolved accuracy explicitly uses only the
    resolved denominator. Every undefined ratio is None, never a fabricated 0.
    """
    rows = list(_rows(rows, "metric rows"))
    gold_counts = dict.fromkeys(GOLD_LABELS, 0)
    status_counts = dict.fromkeys(STATUSES, 0)
    confusion = dict.fromkeys(("TP", "FP", "FN", "TN"), 0)
    abstentions = {gold: {"unresolved": 0, "model_error": 0} for gold in GOLD_LABELS}
    case_ids = set()
    with_ids = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("A metric row must be a mapping.")
        gold = _gold(row.get("gold", _MISSING))
        status = _status(row)
        if "case_id" in row:
            case_id = _case_id(row["case_id"], "metric case_id")
            if case_id in case_ids:
                raise ValueError("Duplicate metric case_id.")
            case_ids.add(case_id)
            with_ids += 1
        gold_counts[gold] += 1
        status_counts[status] += 1
        if status not in RESOLVED:
            abstentions[gold][status] += 1
        elif gold == "grounding_error":
            confusion["TP" if status == "candidate_conflict" else "FN"] += 1
        else:
            confusion["FP" if status == "candidate_conflict" else "TN"] += 1
    if with_ids not in (0, len(rows)):
        raise ValueError("Supply case_id on every metric row or no metric rows.")
    n = len(rows)
    resolved = sum(confusion.values())
    denominators = {
        "precision": confusion["TP"] + confusion["FP"],
        "error_recall": gold_counts["grounding_error"],
        "false_conflict_rate": gold_counts["correctly_grounded"],
        "coverage": n,
        "resolved_accuracy": resolved,
    }
    numerators = {
        "precision": confusion["TP"],
        "error_recall": confusion["TP"],
        "false_conflict_rate": confusion["FP"],
        "coverage": resolved,
        "resolved_accuracy": confusion["TP"] + confusion["TN"],
    }
    return {
        "n_cases": n,
        "gold_counts": gold_counts,
        "status_counts": status_counts,
        "resolved_cases": resolved,
        "abstention_cases": n - resolved,
        "confusion_resolved": confusion,
        "abstentions_by_gold": abstentions,
        "metric_numerators": numerators,
        "metric_denominators": denominators,
        **{name: _ratio(numerators[name], denominators[name]) for name in METRIC_NAMES},
    }


def _outcome(gold, status):
    if status not in RESOLVED:
        return "abstention"
    correct = ((gold == "grounding_error" and status == "candidate_conflict")
               or (gold == "correctly_grounded" and status == "no_conflict"))
    return "correct" if correct else "error"


def compare_methods(cases, predictions_by_arm, labels):
    """Compare exactly the selected eligible cases; never repair missing rows.

    Native label metadata for nonselected pairs and nested model ``input``
    metadata are not read. No threshold, confidence calibration, random
    negative, population-accuracy estimate or confidence interval is produced.
    """
    cases = list(_rows(cases, "cases"))
    selected = {}
    pairs = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("Every case must be a mapping.")
        case_id = _case_id(case.get("case_id", _MISSING), "case_id")
        pair = _row_pair(case, "case")
        if case_id in selected or pair in pairs:
            raise ValueError("Duplicate case_id or statement/source pair.")
        selected[case_id] = {"pair": pair, "case": case}
        pairs.add(pair)
    if not isinstance(labels, Mapping):
        raise ValueError("labels must map statement/source ID tuples to labels.")
    label_keys = {}
    for key in labels:
        pair = _pair(key, "label pair")
        if pair in label_keys:
            raise ValueError("Duplicate canonical label pair.")
        label_keys[pair] = key
    gold_by_case = {}
    for case_id, record in selected.items():
        if record["pair"] not in label_keys:
            raise ValueError("Missing label for selected case: " + case_id)
        value = labels[label_keys[record["pair"]]]
        gold = _gold(value.get("label", _MISSING) if isinstance(value, Mapping) else value)
        if "gold" in record["case"] and record["case"]["gold"] != gold:
            raise ValueError("Case gold disagrees with its statement/source label.")
        gold_by_case[case_id] = gold
    if not isinstance(predictions_by_arm, Mapping) or not predictions_by_arm:
        raise ValueError("At least one prediction arm is required.")
    arm_names = sorted(_case_id(name, "arm name") for name in predictions_by_arm)
    statuses = {}
    for arm in arm_names:
        predictions = predictions_by_arm[arm]
        if not isinstance(predictions, Mapping):
            raise ValueError("Each prediction arm must map exact case IDs to predictions.")
        prediction_ids = {_case_id(case_id, "prediction case_id") for case_id in predictions}
        if prediction_ids != set(selected):
            raise ValueError("Prediction case IDs differ from all selected cases: " + arm)
        statuses[arm] = {}
        for case_id, record in selected.items():
            prediction = predictions[case_id]
            row = {"status": prediction} if isinstance(prediction, str) else prediction
            status = _status(row)
            if "case_id" in row and row["case_id"] != case_id:
                raise ValueError("Prediction case_id disagrees with its mapping key.")
            if "pa_hash" in row or "source_hash" in row:
                if _row_pair(row, "prediction") != record["pair"]:
                    raise ValueError("Prediction statement/source IDs disagree with its case.")
            statuses[arm][case_id] = status
    ids = list(selected)
    # Declare the intersection before calculating conditional secondary metrics.
    common_ids = [case_id for case_id in ids
                  if all(statuses[arm][case_id] in RESOLVED for arm in arm_names)]

    def rows_for(arm, use_ids):
        return [{"case_id": case_id, "gold": gold_by_case[case_id],
                 "status": statuses[arm][case_id]} for case_id in use_ids]

    primary = {arm: metrics(rows_for(arm, ids)) for arm in arm_names}
    common = {
        "scope": "all_arms_resolved_intersection.secondary.v1",
        "primary": False,
        "case_ids": common_ids,
        "n_cases": len(common_ids),
        "not_a_replacement_for_full_denominator": True,
        "metrics_by_arm": {arm: metrics(rows_for(arm, common_ids)) for arm in arm_names},
    }
    paired = []
    outcomes = ("correct", "error", "abstention")
    for left, right in combinations(arm_names, 2):
        transitions = {a: dict.fromkeys(STATUSES, 0) for a in STATUSES}
        correctness = {a: dict.fromkeys(outcomes, 0) for a in outcomes}
        for case_id in ids:
            a, b = statuses[left][case_id], statuses[right][case_id]
            transitions[a][b] += 1
            correctness[_outcome(gold_by_case[case_id], a)][_outcome(gold_by_case[case_id], b)] += 1
        paired.append({
            "left_arm": left,
            "right_arm": right,
            "all_selected_case_count": len(ids),
            "status_transitions": transitions,
            "correctness_transitions": correctness,
            "change_direction": "right_minus_left",
            "confusion_count_changes": {
                key: primary[right]["confusion_resolved"][key] - primary[left]["confusion_resolved"][key]
                for key in ("TP", "FP", "FN", "TN")
            },
            "resolved_case_change": primary[right]["resolved_cases"] - primary[left]["resolved_cases"],
            "abstention_case_change": primary[right]["abstention_cases"] - primary[left]["abstention_cases"],
            "metric_changes": {
                name: (primary[right][name] - primary[left][name]
                       if primary[right][name] is not None and primary[left][name] is not None else None)
                for name in METRIC_NAMES
            },
        })
    return {
        "format": "biograph-steward.grounding-error-triage-comparison.v1",
        "all_selected_case_count": len(ids),
        "case_ids": ids,
        "common_resolved_secondary": common,
        "metrics_by_arm": primary,
        "paired_comparisons": paired,
        "new_gold_labels_created": False,
        "population_scientific_accuracy_or_confidence_intervals_claimed": False,
        "source_grounding_scores_treated_as_truth_probabilities": False,
    }
