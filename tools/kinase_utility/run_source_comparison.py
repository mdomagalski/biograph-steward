"""Pinned, one-shot retrospective source-choice comparison; no network.

Measurements and source memberships are prepared before reference target/sign
decoding. Reuses retained mapping, eligibility, scoring and diagnostics. Source
study overlap remains unresolved; seals document execution, not biological truth.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import csv
import gzip
import hashlib
import json
import platform
from pathlib import Path
from statistics import fmean

import numpy
import scipy

from biograph_steward.client import digest
from biograph_steward.cohort_mapping import load_registry, Registry
from pilot_methods import approved_gene, map_measurement_identifier, parse_numeric_cell, parse_sequence_reference
from signature_comparison import infer_scores, score_recovery
from signal_diagnostics import describe_signal_background
from library_adapter import map_ensembl_measurement_identifier


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    data = {**value, "content_sha256": digest(value)}
    with Path(path).open("x") as stream:
        json.dump(data, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write("\n")
    return data


def macro(cases):
    fields = ("normalized_rank", "direction_agreement", "signed_top5", "target_score_coverage")
    groups = defaultdict(lambda: defaultdict(list))
    for original in cases:
        row = {**original, "target_score_coverage": not original["abstained"]}
        groups[row["parent"]][row["condition"]].append(row)
    parents = {}
    for parent, conditions in sorted(groups.items()):
        parents[parent] = {field: fmean(fmean(r[field] for r in rows) for rows in conditions.values()) for field in fields}
        parents[parent].update(conditions=len(conditions), cases=sum(map(len, conditions.values())))
    return {"parents": parents, "parent_count": len(parents), "case_count": len(cases),
            "condition_count": len({r["condition"] for r in cases}),
            "macro": {field: fmean(p[field] for p in parents.values()) if parents else None for field in fields}}


def main(plan_path, output):
    plan_path, output = Path(plan_path), Path(output)
    plan = json.loads(plan_path.read_text())
    seal = plan.pop("content_sha256")
    assert digest(plan) == seal
    assert plan["runtime"] == {"python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__}
    for path, expected in plan["files_sha256"].items():
        assert Path(path).is_file() and not Path(path).is_symlink() and sha(path) == expected, path
    assert not output.exists()
    profiles = {name: json.loads(Path(path).read_text()) for name, path in plan["signature_paths"].items()}
    candidates = plan["candidate_genes"]
    assert sorted(set().union(*(set(p) for p in profiles.values()))) == candidates
    conditions = plan["selected_conditions"]
    assert len(set(conditions)) == len(conditions)
    _, registry = load_registry(plan["registry_directory"])
    assert isinstance(registry, Registry)
    sequences = parse_sequence_reference(Path(plan["sequence_reference"]).read_bytes())
    output.mkdir()
    write(output / "numeric_access_started.json", {"created_at": now(), "plan_sha256": sha(plan_path),
                                                  "plan_content_sha256": seal, "reference_labels_accessed": False})
    observed, reasons = defaultdict(list), Counter()
    with Path(plan["measurement_csv"]).open(encoding="utf-8-sig", newline="") as stream, gzip.open(output / "measurement_mapping.jsonl.gz", "wt") as ledger:
        reader = csv.DictReader(stream, strict=True)
        assert reader.fieldnames == plan["measurement_header"]
        for ordinal, raw in enumerate(reader, 1):
            assert None not in raw and all(v is not None for v in raw.values())
            mapping = map_ensembl_measurement_identifier(raw["ID"], registry=registry, sequence_reference=sequences)
            entry = {"ordinal": ordinal, "raw_row_sha256": digest(raw), "mapping": mapping}
            ledger.write(json.dumps(entry, ensure_ascii=True, allow_nan=False) + "\n")
            reasons[mapping["status"]] += 1
            if mapping["status"] == "qualified":
                values = [parse_numeric_cell(raw[c]) for c in conditions]
                observed[mapping["protein_id"] + "|" + mapping["site"]].append((ordinal, values))
    assert observed, "No qualified measurement sites: stop before inference or reference access."
    site_values = {condition: {} for condition in conditions}
    aggregation_counts = Counter()
    with gzip.open(output / "aggregation.jsonl.gz", "wt") as ledger:
        for site, rows in sorted(observed.items()):
            entry = {"site_id": site, "rows": [r[0] for r in rows], "conditions": {}}
            for i, condition in enumerate(conditions):
                unique = sorted({r[1][i] for r in rows if r[1][i] is not None})
                value = unique[0] if len(unique) == 1 else None
                state = "one_unique_finite_value" if len(unique) == 1 else "conflicting_finite_values" if unique else "unavailable"
                site_values[condition][site] = value
                entry["conditions"][condition] = {"value": value, "state": state}
                aggregation_counts[state] += 1
            ledger.write(json.dumps(entry, ensure_ascii=True, allow_nan=False) + "\n")
    results, backgrounds = {}, {}
    for name, profile in profiles.items():
        result = infer_scores(site_values, {gene: profile.get(gene, []) for gene in candidates}, min_sites=plan["minimum_sites"])
        results[name] = result
        backgrounds[name] = describe_signal_background(site_values, result["scores"])
    predictions = write(output / "predictions_sealed.private.json", {"created_at": now(), "plan_content_sha256": seal,
        "reference_target_signs_accessed": False, "candidate_genes": candidates, "predictions": results,
        "background_diagnostics": backgrounds, "measurement_mapping": dict(reasons),
        "aggregation": dict(aggregation_counts), "qualified_unique_site_groups": len(observed)})
    write(output / "reference_access_started.json", {"created_at": now(), "prediction_content_sha256": predictions["content_sha256"],
        "reference_sha256": sha(plan["reference_csv"]), "plan_content_sha256": seal})
    by_key, exclusions, supplied = defaultdict(list), [], 0
    selected_parents = set(plan["selected_parents"])
    with Path(plan["reference_csv"]).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        assert reader.fieldnames == ["id", "Description", "Control", "Time_min", "PMID", "target", "sign"]
        for ordinal, raw in enumerate(reader, 1):
            assert None not in raw and all(v is not None for v in raw.values())
            if raw["id"] not in conditions:
                continue
            supplied += 1
            assert raw["PMID"] in selected_parents and raw["PMID"].isascii() and raw["PMID"].isdigit()
            gene = approved_gene(raw["target"].strip(), registry)
            try:
                sign = Decimal(raw["sign"])
            except InvalidOperation:
                sign = None
            if not gene["eligible"] or sign is None or not sign.is_finite() or sign not in {Decimal(-1), Decimal(1)}:
                exclusions.append({"ordinal": ordinal, "row": raw, "reason": "atomic_gene_or_direction_unresolved", "gene_mapping": gene})
                continue
            by_key[(raw["id"], gene["approved_symbol"])].append({"condition": raw["id"], "target": gene["approved_symbol"],
                "sign": int(sign), "parent": raw["PMID"], "reference_row": ordinal, "raw_row": raw, "gene_mapping": gene})
    cases, duplicates = [], 0
    for key, rows in sorted(by_key.items()):
        if len({(r["sign"], r["parent"]) for r in rows}) != 1:
            exclusions.append({"key": key, "rows": rows, "reason": "conflicting_direction_or_parent"})
        else:
            cases.append({k: v for k, v in rows[0].items() if k not in {"raw_row", "gene_mapping"}})
            duplicates += len(rows) - 1
    scores, summaries = {}, {}
    for name, result in results.items():
        scored = score_recovery(result["scores"], cases, candidate_ids=candidates)
        scores[name] = scored
        summaries[name] = macro(scored["cases"])
    common_cases, common_counts, common_scored = [], {}, {name: [] for name in profiles}
    for condition in conditions:
        common = sorted(gene for gene in candidates if all(results[name]["scores"][condition][gene] is not None for name in profiles))
        common_counts[condition] = len(common)
        selected = [case for case in cases if case["condition"] == condition and case["target"] in common]
        common_cases.extend(selected)
        if not selected:
            continue
        for name, result in results.items():
            values = {gene: result["scores"][condition][gene] for gene in common}
            common_scored[name].extend(score_recovery({condition: values}, selected, candidate_ids=common)["cases"])
    common_summary = {name: macro(rows) for name, rows in common_scored.items()}
    result = write(output / "results.private.json", {"created_at": now(), "plan_content_sha256": seal,
        "prediction_content_sha256": predictions["content_sha256"], "candidate_count": len(candidates),
        "supplied_selected_reference_rows": supplied, "qualified_cases": cases, "reference_exclusions": exclusions,
        "duplicates_collapsed": duplicates, "source_scores": scores, "parent_macros": summaries,
        "common_finite_sensitivity": {"candidate_counts": common_counts, "case_count": len(common_cases), "parent_macros": common_summary},
        "limitations": plan["limitations"], "scientific_accuracy_percentage_established": False})
    print(json.dumps({"result_content_sha256": result["content_sha256"], "case_count": len(cases), "candidate_count": len(candidates),
                      "parent_macros": {name: r["macro"] for name, r in summaries.items()}}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.plan, args.output)
