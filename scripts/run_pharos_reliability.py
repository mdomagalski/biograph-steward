#!/usr/bin/env python3
"""Check retrieval reliability on the now-consumed, unchanged IntAct panel.

This reuses the ordinary Pharos client, its bounded retries and a new shared
cache, then the existing attachment/answer/export and raw-field oracle. It does
not reopen IntAct online, rerun the fresh assessment or create fresh validation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from biograph_steward.assay_attachment import attach_assay, load_publication
from biograph_steward.assay_questions import answer_assay_question
from biograph_steward.client import ENDPOINT, PharosClient, canonical, digest, utcnow
from biograph_steward.construction import run_construction, verify_construction_run
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.intact_final_publication import FRESH, FRESH_SPLIT, records_from_material
from biograph_steward.questions import save_answer
from biograph_steward.reviews import read_run
from scripts.evaluate_intact_evidence_fidelity import evaluate_rows, field_groups
from scripts.intact_final_common import output_inventory_checks, participant_pair, save_new, sha, summarize

FORMAT = "biograph-steward.pharos-reliability-consumed.v1"
SPLIT = "consumed_retrieval_reliability"
ORIGIN = ROOT / "runs/intact_fresh_assessment_20261027/execution"
ORIGIN_REPORT_SHA = "12b98cb5c3bcfd3b7b9e062c3470ebddb9ce3ffbbb80db306bfc3f3257d9a5ca"
PUBLICATION_SHA = "5ec96db501fe0b0f51bf3fadbe574c67d75d1c686b615e376b411fc9757bd769"
PAIRS = (('A0A1B0GWG4', 'O14649'), ('O14656', 'Q8NFQ8'),
         ('O95863', 'P0C2W1'), ('P06400', 'Q01094'))
POLICY = {"endpoint": ENDPOINT, "timeout_seconds": 30, "retries": 2,
          "cache_ttl_hours": 24, "cache_scope": "new empty directory shared only within this run",
          "maximum_logical_requests": 28, "maximum_logical_requests_per_pair": 7,
          "maximum_actual_attempts": 84, "maximum_actual_attempts_per_pair": 21,
          "maximum_response_bytes": 25_000_000,
          "attempt_accounting": "native urlopen invocations; urllib redirect hops are not separately counted",
          "redirects": "existing native urllib behavior; no replacement transport",
          "version_checks": "uncached before and after every cohort",
          "source_eligible_rows": 8, "exact_pairs": [list(pair) for pair in PAIRS]}
LIMITATION = ("Consumed-data engineering check of retrieval and supplied-source preservation. "
              "The original fresh 4/8 result remains unchanged. This is not new validation, "
              "scientific accuracy, independent biological evidence or prediction improvement.")


def append_event(path, event):
    """Flush each attempt boundary before its network operation can continue."""
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(canonical(event) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class ReliabilityBudgetExceeded(RuntimeError):
    pass


class ReliabilityClient(PharosClient):
    """Add accounting around the existing native client, never replace HTTP."""
    def __init__(self, folder, cache, total):
        self.folder, self.total = Path(folder), total
        self.logical_requests, self.actual_attempts = 0, 0
        super().__init__(endpoint=ENDPOINT, cache_dir=cache, timeout=30,
                         retries=2, ttl_hours=24, attempt_observer=self.observe)

    def observe(self, event):
        if event["phase"] == "started":
            if (self.actual_attempts >= POLICY["maximum_actual_attempts_per_pair"]
                    or self.total["actual_attempts"] >= POLICY["maximum_actual_attempts"]):
                raise ReliabilityBudgetExceeded("Actual HTTP attempt budget exhausted before opening a request.")
            self.actual_attempts += 1
            self.total["actual_attempts"] += 1
        append_event(self.folder / "http_attempts.jsonl", {
            **deepcopy(event), "recorded_at": utcnow(),
            "pair_attempt": self.actual_attempts, "run_attempt": self.total["actual_attempts"],
            "logical_request": self.logical_requests})

    def execute(self, query, variables=None, *, cache=True):
        if (self.logical_requests >= POLICY["maximum_logical_requests_per_pair"]
                or self.total["logical_requests"] >= POLICY["maximum_logical_requests"]):
            raise ReliabilityBudgetExceeded("Logical request budget exhausted before execution.")
        self.logical_requests += 1
        self.total["logical_requests"] += 1
        event = {"logical_request": self.logical_requests,
                 "run_logical_request": self.total["logical_requests"],
                 "request": {"query": query, "variables": variables or {}},
                 "cache_allowed": cache, "started_at": utcnow()}
        append_event(self.folder / "logical_requests.jsonl", {**event, "phase": "started"})
        previous = len(self.records)
        try:
            data = super().execute(query, variables, cache=cache)
        except BaseException as exc:
            append_event(self.folder / "logical_requests.jsonl", {
                **event, "phase": "finished", "outcome": "failed",
                "error_type": type(exc).__name__, "error": str(exc)})
            raise
        append_event(self.folder / "logical_requests.jsonl", {
            **event, "phase": "finished", "outcome": "validated_response",
            "record": deepcopy(self.records[previous])})
        return data


def load_panel():
    """Use the exact captured publication; do not rediscover or refetch sources."""
    if sha(ORIGIN / "report.json") != ORIGIN_REPORT_SHA or sha(ORIGIN / "publication/publication.json") != PUBLICATION_SHA:
        raise ValueError("Historical assessment or source publication changed.")
    origin = json.loads((ORIGIN / "report.json").read_text())
    manifest, evidence, files = load_publication(ORIGIN / "publication")
    if (manifest["bindings"]["assessment_split"] != FRESH_SPLIT
            or manifest["bindings"]["publication_ids"] != list(FRESH)):
        raise ValueError("Require the exact historical source panel; it is now consumed.")
    records = records_from_material(files, manifest["source_catalog"], manifest["bindings"])
    ledger = [json.loads(line) for line in files["row_ledger.jsonl"].splitlines()]
    references = [{"ledger": item, "reader_record": record["reader_record"]}
                  for item, record in zip(ledger, records)]
    eligible = [ref for ref in references if ref["ledger"]["eligible"]]
    observed = Counter(exact_pair(ref) for ref in eligible)
    if len(eligible) != 8 or observed != Counter({pair: 2 for pair in PAIRS}):
        raise ValueError("All four original exact pairs and eight eligible rows must remain in scope.")
    return origin, manifest, files, references


def exact_pair(reference):
    return tuple(sorted(accession for side in participant_pair(reference["reader_record"])
                        for database, accession in side if database == "uniprotkb"))


def evaluate_pair(references, all_references, publication, files, folder, client):
    """Existing native APIs and original independent field oracle only."""
    pair = exact_pair(references[0])
    request = {"accessions": list(pair), "focus_uniprot": pair[0],
               "profile": "ppi", "relations": ["interactions"]}
    save_new(folder / "construction_request.json", request)
    run_construction(client, request, folder / "cohort")
    verify_construction_run(folder / "cohort")
    attach_assay(folder / "cohort", publication, folder / "attached")
    _, _, graph = read_run(folder / "attached")
    answer = answer_assay_question(graph, source_run=str(folder / "attached"))
    save_answer(answer, folder / "answer")
    export_packet(folder / "attached", folder / "packet")
    load_packet(folder / "packet")
    packet = [json.loads(line) for line in (folder / "packet/assay_observations.jsonl").read_text().splitlines()]
    exported = [json.loads(line) for line in (folder / "answer/assay_evidence.jsonl").read_text().splitlines()]
    cohort = {target["id"] for target in graph["targets"]}
    oracle = [ref for ref in all_references if ref["ledger"]["eligible"]
              and {"UniProtKB:" + accession for accession in exact_pair(ref)} <= cohort]
    checks = output_inventory_checks(oracle, graph["assay_observations"], answer["results"], packet, exported)
    wanted = {tuple(ref["ledger"][key] for key in ("publication_id", "artifact_sha256", "source_line")) for ref in references}
    def chosen(row):
        return tuple(row.get("source", {}).get(key) for key in ("publication_id", "artifact_sha256", "source_line")) in wanted
    observations = [row for row in graph["assay_observations"] if chosen(row)]
    results = [row for row in answer["results"] if chosen(row["source_observation"])]
    edge_ids = {row["graph_edge_id"] for row in observations}
    evaluation = evaluate_rows(references, observations, results,
        [row for row in packet if chosen(row)], [row for row in exported if chosen(row["source_observation"])],
        (folder / "answer/report.html").read_text(),
        graph_edges=[edge for edge in graph["edges"] if edge.get("id") in edge_ids], columns=field_groups(),
        answer_bindings={key: answer[key] for key in ("answer_sha256", "graph_basis_sha256", "snapshot_sha256",
                        "assay_publication_sha256", "assay_attachment_sha256", "source_run")})
    for prefix in (folder / "attached/assay_source", folder / "packet/source/assay_source"):
        for name, raw in files.items():
            checks.append({"name": "preserved_source_copy", "path": str(prefix / name),
                           "passed": (prefix / name).read_bytes() == raw})
    return evaluation, checks


def _jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def execute(output):
    output = Path(output).absolute()
    if output.exists() or any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError("Choose a new ordinary output outside the historical assessment.")
    if output.resolve() == ORIGIN.parent.resolve() or ORIGIN.parent.resolve() in output.resolve().parents:
        raise ValueError("Never write reliability work inside the historical assessment.")
    origin, manifest, files, references = load_panel()
    output.mkdir(parents=True)
    cache = output / "cache"
    cache.mkdir()  # No old/global cache, imported successful responses or stale fallback.
    save_new(output / "started.json", {"format": FORMAT, "created_at": utcnow(), "assessment_split": SPLIT,
        "policy": POLICY, "source_publication_sha256": PUBLICATION_SHA, "origin_report_sha256": ORIGIN_REPORT_SHA,
        "historical_fresh_result_unchanged": True, "interpretation": LIMITATION,
        "implementation_sha256": {"runner": sha(__file__), "client": sha(ROOT / "biograph_steward/client.py")}})
    grouped = defaultdict(list)
    for ref in references:
        if ref["ledger"]["eligible"]:
            grouped[exact_pair(ref)].append(ref)
    rows, checks, failures, batches = [], [], [], []
    total = {"logical_requests": 0, "actual_attempts": 0}
    for number, pair in enumerate(sorted(grouped), 1):
        folder = output / ("batch_%04d" % number)
        folder.mkdir()
        refs = grouped[pair]
        client = ReliabilityClient(folder, cache, total)
        try:
            evaluation, pair_checks = evaluate_pair(refs, references, ORIGIN / "publication", files, folder, client)
            checks.extend(pair_checks)
        except Exception as exc:
            failure = {"pair": list(pair), "error_type": type(exc).__name__, "error": str(exc),
                       "eligible_rows_retained_in_denominator": len(refs)}
            save_new(folder / "failure.json", failure)
            failures.append(failure)
            evaluation = evaluate_rows(refs, [], [], [], [], "", graph_edges=[], columns=field_groups())
        save_new(folder / "evaluation.json", evaluation)
        rows.extend(evaluation["rows"])
        checks.extend(evaluation["global_checks"])
        batches.append({"pair": list(pair), "eligible_rows": len(refs),
                        "logical_requests": client.logical_requests, "actual_attempts": client.actual_attempts,
                        "offline_construction_replay_verified": (folder / "cohort/construction_receipt.json").is_file()})
    metrics = summarize({"rows": rows, "global_checks": checks}, references, list(FRESH))
    events = [event for folder in sorted(output.glob("batch_*")) for event in _jsonl(folder / "http_attempts.jsonl")]
    logical = [event for folder in sorted(output.glob("batch_*")) for event in _jsonl(folder / "logical_requests.jsonl")
               if event["phase"] == "finished"]
    successful = [event for event in logical if event["outcome"] == "validated_response"]
    license_records = [event["record"] for event in successful if "query SourceLicenses" in event["request"]["query"]]
    unchanged = sha(ORIGIN / "report.json") == ORIGIN_REPORT_SHA and sha(ORIGIN / "publication/publication.json") == PUBLICATION_SHA
    if not unchanged:
        raise ValueError("Historical inputs changed during reliability execution.")
    passed = not failures and all(check["passed"] for check in checks) and metrics["strict_fidelity"]["numerator"] == 8
    report = {"format": FORMAT, "created_at": utcnow(), "assessment_split": SPLIT,
        "status": "passed" if passed else "failed", "interpretation": LIMITATION, "policy": POLICY,
        "origin_fresh_result": {"report_sha256": ORIGIN_REPORT_SHA, "status": origin["status"],
            "coverage": origin["metrics"]["coverage"], "strict_fidelity": origin["metrics"]["strict_fidelity"]},
        "source_publication_sha256": PUBLICATION_SHA, "source_accounting": origin["source_accounting"],
        "metrics": metrics, "batches": batches, "failures": failures,
        "checks": {"performed": len(checks), "passed": sum(check["passed"] for check in checks)},
        "transport": {**total, "started_events": sum(event["phase"] == "started" for event in events),
            "finished_events": sum(event["phase"] == "finished" for event in events),
            "retry_scheduled": sum(event.get("outcome") == "retry_scheduled" for event in events),
            "attempt_outcomes": dict(Counter(event.get("outcome") for event in events if event["phase"] == "finished")),
            "validated_logical_responses": len(successful),
            "cache_hits": sum(event["record"]["loaded_from_cache"] for event in successful),
            "license_validated_responses": len(license_records),
            "license_cache_hits": sum(record["loaded_from_cache"] for record in license_records)},
        "empty_strata_unevaluated": [{"group": group, "stratum": key} for group, strata in metrics["strata"].items()
                                     for key, value in strata.items() if value["denominator"] == 0],
        "historical_fresh_result_unchanged": unchanged, "fresh_validation": False,
        "scientific_accuracy_measured": False, "biological_prediction_improvement_demonstrated": False,
        "new_IntAct_requests": 0, "Java_reader_runs": 0, "model_calls": 0, "GPU_runs": 0}
    report["content_sha256"] = digest(report)
    save_new(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = execute(args.output)
    except Exception as exc:
        print(json.dumps({"status": "stopped", "error_type": type(exc).__name__, "error": str(exc)}))
        return 2
    print(json.dumps({"status": report["status"], "coverage": report["metrics"]["coverage"],
                      "strict_fidelity": report["metrics"]["strict_fidelity"], "transport": report["transport"]}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
