"""Read-only display of the existing byte-bound native GO QC output.

This consumer does not run or replace ontobio/GAFeRence rules. It binds the
producer's recorded changes and calls to the original native rows and keeps
normalization, taxon checks and extension satisfiability distinct.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import re

from . import gold_packet
from .file_utils import sha


FORMAT = "biograph-steward.official-native-go-qc.v1"
FILES = frozenset({"official_lifecycle_calls.jsonl", "base_validated_native.gaf",
    "native_row_changes.jsonl", "official_report.json", "taxon_rule.json",
    "official_rule_calls.jsonl", "validated_native.gaf"})
RULES = frozenset({"GORULE:0000022", "GORULE:0000061"})
FIELD_NAMES = {4: "relation", 5: "GO_ID", 6: "reference", 8: "with_from",
               16: "extensions", 17: "product_form"}


def _need(value, message):
    if not value:
        raise ValueError("Saved GO QC: " + message)


def _rows(path):
    return [gold_packet._decode(line) for line in path.read_bytes().splitlines()]


def _gaf_lines(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("!")]


def load_saved_qc(folder, context_report, native_rows):
    """Verify the existing producer packet and return per-native-row flags.

    Input/dependency pins and rule/reasoner execution remain producer receipts,
    not independently reexecuted science. No path named inside a report is
    opened; only the seven fixed local output names are read.
    """
    folder = Path(folder).absolute()
    _need(folder.is_dir() and not folder.is_symlink(), "ordinary nonsymlink directory required.")
    paths = list(folder.iterdir())
    _need({p.name for p in paths} == FILES | {"report.json"}
          and all(p.is_file() and not p.is_symlink() for p in paths), "output inventory differs.")
    report_sha = sha(folder/"report.json")
    report = gold_packet._read(folder/"report.json")
    _need(gold_packet._sealed(report) and report.get("format") == FORMAT
          and report.get("status") == "completed", "successful producer seal or format differs.")
    _need(report.get("source_context_report_sha256") == context_report["content_sha256"]
          and report.get("packet_id") == context_report["packet_id"], "native source frame differs.")
    _need(report.get("ontobio_version") == "2.9.12"
          and report.get("prefixcommons_version") == "0.1.12"
          and report.get("explicit_qc_rule_selectors") == ["0000022", "0000061"]
          and report.get("official_methods_recorded_without_rule_body_changes") is True
          and report.get("native_gaf_and_ontology_release_match") is True,
          "reviewed producer method differs.")
    _need(all(report.get(key) is False for key in ("scientific_accuracy_measured",
          "independent_biological_validation", "source_graph_changed",
          "historical_pharos_qualifiers_backfilled", "unrecorded_network_allowed")),
          "producer interpretation policy differs.")
    pins = report.get("files")
    _need(isinstance(pins, dict) and set(pins) == FILES
          and all(sha(folder/name) == value for name, value in pins.items()), "output bytes differ.")
    _need(report.get("base_validated_native_gaf_sha256") == pins["base_validated_native.gaf"],
          "prepared GAF pin differs.")
    originals = {row["id"]: row for row in native_rows}
    _need(len(originals) == len(native_rows), "native IDs repeat.")
    changes = _rows(folder/"native_row_changes.jsonl")
    _need(len(changes) == len(native_rows)
          and [row.get("native_record_id") for row in changes] == [row["id"] for row in native_rows],
          "native change frame differs.")
    displayed, base_lines = {}, []
    for source, change in zip(native_rows, changes):
        _need(change.get("source_line") == source["source_line"]
              and change.get("before") == source["raw_line"], "original row identity differs.")
        after = change.get("after_base_rules")
        _need(isinstance(after, list) and all(isinstance(line, str) and len(line.split("\t")) == 17
              for line in after), "normalized output rows malformed.")
        columns = sorted({i+1 for line in after for i, (old, new) in
                          enumerate(zip(source["raw_fields"], line.split("\t"))) if old != new})
        _need(change.get("changed_gaf_columns") == columns
              and change.get("base_rule_filtered") is (not bool(after))
              and change.get("base_literal_output_changed") is (bool(after) and after != [source["raw_line"]]),
              "normalization trace does not reproduce.")
        base_lines.extend(after)
        displayed[source["id"]] = {"normalization": {
            "base_rule_filtered": change["base_rule_filtered"],
            "changed_columns": [{"column": i, "field": FIELD_NAMES.get(i, "GAF column " + str(i)),
                "before": source["raw_fields"][i-1],
                "after_values": list(dict.fromkeys(line.split("\t")[i-1] for line in after))}
                for i in columns]}, "rule_results": [], "semantic_lookup_results": []}
    _need(_gaf_lines(folder/"base_validated_native.gaf") == base_lines,
          "normalized GAF does not match its source-row trace.")
    rule_calls = _rows(folder/"official_rule_calls.jsonl")
    seen_rules = set()
    for call in rule_calls:
        rid, rule = call.get("native_record_id"), call.get("rule")
        _need(rid in originals and rule in RULES and (rid, rule) not in seen_rules
              and call.get("result_type") in {"PASS", "WARNING", "ERROR"}
              and isinstance(call.get("message"), str), "recorded rule calls differ.")
        seen_rules.add((rid, rule))
        displayed[rid]["rule_results"].append(deepcopy(call))
    _need(seen_rules == {(rid, rule) for rid in originals for rule in RULES},
          "selected native rule-call coverage differs.")
    taxon = gold_packet._read(folder/"taxon_rule.json")
    _need(report.get("taxon_rule_status") == taxon.get("status")
          == "executed_with_proven_sparse_delta_parser_coverage"
          and taxon.get("requested") is True
          and taxon.get("published_inference_entries_modified") is False,
          "bound taxon execution status differs.")
    proof, inputs = taxon.get("sparse_proof"), report.get("input_files")
    _need(isinstance(proof, dict) and isinstance(inputs, dict)
          and proof.get("coverage_file_sha256") == inputs.get("parser_coverage", {}).get("sha256")
          # The first two are execution-receipt CONTENT seals. input_files
          # contains their FILE byte hashes; those are distinct digest domains.
          # The original producer checked both receipts. This output consumer
          # preserves that recorded proof without following report-named paths.
          and all(isinstance(proof.get(key), str) and re.fullmatch(r"[a-f0-9]{64}", proof[key])
                  for key in ("producer_execution_sha256", "coverage_execution_sha256"))
          and all(isinstance(inputs.get(key), dict)
                  and isinstance(inputs[key].get("sha256"), str)
                  and re.fullmatch(r"[a-f0-9]{64}", inputs[key]["sha256"])
                  for key in ("inference_execution", "parser_execution", "parser_coverage"))
          and proof.get("normal_absent_keys_materialized_as_pass_entries") is False
          and proof.get("covered_non_not_associations") == sum(not row["negated"] for row in native_rows)
          and proof.get("negated_exempt_associations") == sum(row["negated"] for row in native_rows),
          "saved sparse execution/coverage proof differs.")
    taxon_results = taxon.get("results")
    _need(isinstance(taxon_results, list) and len(taxon_results) == len(native_rows)
          and [row.get("native_record_id") for row in taxon_results] == [row["id"] for row in native_rows],
          "taxon result frame differs.")
    for row in taxon_results:
        rid = row["native_record_id"]
        _need(row.get("negated_annotation_exempt") is originals[rid]["negated"]
              and row.get("result_type") in {"PASS", "WARNING", "ERROR"},
              "taxon exemption or result differs.")
        displayed[rid]["taxon_result"] = deepcopy(row)
    lookups = taxon.get("actual_lookup_calls")
    _need(isinstance(lookups, list), "semantic lookup traces unavailable.")
    for row in lookups:
        rid = row.get("native_record_id")
        _need(rid in originals and type(row.get("explicit_sparse_delta_match")) is bool
              and type(row.get("typed_extension_key_converted")) is bool
              and all(value is None or type(value) is bool for value in
                      (row.get("satisfiable"), row.get("taxon_problem"))), "semantic lookup frame differs.")
        if row["explicit_sparse_delta_match"]:
            _need(type(row.get("satisfiable")) is bool and type(row.get("taxon_problem")) is bool
                  and type(row.get("additional_inferences")) is int and row["additional_inferences"] >= 0,
                  "matched semantic lookup is incomplete.")
        else:
            _need(all(row.get(key) is None for key in ("satisfiable", "taxon_problem", "additional_inferences")),
                  "missing sparse entries cannot become satisfiability labels.")
        displayed[rid]["semantic_lookup_results"].append(deepcopy(row))
    _need({row["native_record_id"] for row in lookups} ==
          {row["id"] for row in native_rows if not row["negated"]}
          and taxon.get("non_not_associations") == sum(not row["negated"] for row in native_rows)
          and taxon.get("negated_exempt_associations") == sum(row["negated"] for row in native_rows)
          and taxon.get("missing_key_associations") == 0,
          "semantic lookup coverage or NOT exemptions differ.")
    for value in displayed.values():
        value["extension_unsatisfiable"] = any(row["satisfiable"] is False and row["taxon_problem"] is False
            for row in value["semantic_lookup_results"])
    counts = report.get("counts", {})
    _need(counts.get("native_input_records") == len(native_rows)
          and counts.get("base_output_associations") == len(base_lines)
          and counts.get("base_filtered_native_records") == sum(not row["after_base_rules"] for row in changes)
          and counts.get("base_literal_changed_native_records") == sum(row["base_literal_output_changed"] for row in changes),
          "producer counts differ.")
    _need(counts.get("field_change_records") == {name: sum(i in row["changed_gaf_columns"] for row in changes)
          for i, name in FIELD_NAMES.items()}
          and counts.get("rule_invocations") == {rule: dict(Counter(row["result_type"]
              for row in rule_calls if row["rule"] == rule)) for rule in RULES}, "field/rule counts differ.")
    # A consumer must not silently assume final output equals the base output.
    # This completed sparse run retains every association; reject another mode
    # until its final-rule transformation has an explicit display adapter.
    _need(_gaf_lines(folder/"validated_native.gaf") == base_lines
          and counts.get("final_output_associations") == len(base_lines),
          "this display adapter requires the recorded all-retained final derivative.")
    _need(all(sha(folder/name) == value for name, value in pins.items())
          and sha(folder/"report.json") == report_sha, "QC output changed during verification.")
    summary = {"status": "verified_saved_output", "report_content_sha256": report["content_sha256"],
        "report_file_sha256": report_sha, "ontobio_version": report["ontobio_version"],
        "native_gaf_go_version": report["native_gaf_go_version"],
        "ontology": deepcopy(report.get("ontology")),
        "retracted_reference_headers": deepcopy(report.get("retracted_reference_headers")),
        "method_note": "Recorded native ontobio and GAFeRence output, byte-bound to these source rows; rules and reasoner were not reexecuted by this view.",
        "counts": deepcopy(counts), "limits": deepcopy(report["limits"]),
        "historical_record_repaired": False, "source_graph_changed": False,
        "independent_biological_accuracy_established": False}
    return summary, displayed
