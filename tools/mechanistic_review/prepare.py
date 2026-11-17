"""Prepare a complete-source INDRA curation frame without class-based admission.

The source frame and model inputs are written before the separate native-tag
label projection. Original author JSON lines remain verbatim in a private
artifact; only the released top-level belief is removed from request inputs.
This is retrospective reuse of an already inspected corpus, not a new blind set.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path


POSITIVE_TAGS = frozenset(("correct", "hypothesis", "act_vs_amt"))


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode()


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def _write_jsonl(path, rows):
    with Path(path).open("xb") as stream:
        for row in rows:
            stream.write(encoded(row) + b"\n")


def _no_outcome_fields(value):
    if isinstance(value, dict):
        forbidden = {"belief", "curator", "curation", "curations", "correct",
                     "gold", "label", "tag"}
        if forbidden & value.keys():
            raise ValueError("Outcome field in model input.")
        for child in value.values():
            _no_outcome_fields(child)
    elif isinstance(value, list):
        for child in value:
            _no_outcome_fields(child)


def prepare(source_root, cohort_targets, output):
    source_root, cohort_targets, output = map(Path, (
        source_root, cohort_targets, output))
    if output.exists():
        raise ValueError("Preparation output must be new.")
    sources = {
        "native_statements": source_root / "data_capture/blind_join/selected_statements.jsonl",
        "pair_inventory": source_root / "data_capture/blind_join/pair_join_inventory.json",
        "human_frame": source_root / "frame_v3/cases.jsonl.gz",
        "exposure_groups": source_root / "data_capture/blind_join/exposure_groups.json",
        "group_splits": source_root / "frame_v3/group_splits.json",
        "native_curations": source_root / "data_capture/indra_assembly_curations.json",
        "author_policy": source_root / "source_audit/author_process_curations.py",
        "cohort_targets": cohort_targets,
    }
    pins = {}
    for name, path in sources.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError("Ordinary source file required: " + name)
        pins[name] = {"path": str(path), "sha256": file_sha(path),
                      "bytes": path.stat().st_size}
    with gzip.open(sources["human_frame"], "rt") as stream:
        human = {(r["pa_hash"], r["source_hash"]): r
                 for r in map(json.loads, stream)}
    inventory = json.loads(sources["pair_inventory"].read_text())
    pairs = {(str(r["pa_hash"]), str(r["source_hash"])): r
             for r in inventory["pairs"]}
    split_map = json.loads(sources["group_splits"].read_text())
    with cohort_targets.open() as stream:
        cohort = {r["id"].removeprefix("UniProtKB:")
                  for r in csv.DictReader(stream, delimiter="\t")}
    cases, raw_lines = [], []
    exclusions = Counter()
    for raw_line in sources["native_statements"].open("rb"):
        origin = json.loads(raw_line)
        native = origin["statement"]
        pa = str(native["matches_hash"])
        evidence = native.get("evidence", [])
        hashes = [str(ev["source_hash"]) for ev in evidence
                  if "source_hash" in ev]
        if not hashes or len(hashes) != len(evidence) or len(set(hashes)) != len(hashes):
            exclusions["missing_or_duplicate_original_source_hash"] += 1
            continue
        if not all((pa, h) in human for h in hashes):
            exclusions["not_all_original_sources_in_existing_human_frame"] += 1
            continue
        admitted = [human[(pa, h)] for h in hashes]
        groups = {row["group_id"] for row in admitted}
        splits = {row["split"] for row in admitted}
        if len(groups) != 1 or len(splits) != 1:
            raise ValueError("An original statement crosses source groups.")
        group, split = next(iter(groups)), next(iter(splits))
        if split_map[group] != split:
            raise ValueError("Existing group split differs.")
        source_rows, raw_up = [], []
        for ordinal, (ev, source) in enumerate(zip(evidence, admitted)):
            pair = pairs[(pa, str(ev["source_hash"]))]
            if not (pair["matched"]
                    and pair["evidence_payload_variant_count"] == 1
                    and pair["statement_payload_variant_count"] == 1):
                raise ValueError("A supposedly admitted source is ambiguous.")
            binding = source["source_origin"]
            if (binding["corpus_ordinal"] != origin["corpus_ordinal"]
                    or binding["evidence_ordinal"] != ordinal
                    or binding["canonical_statement_sha256"] != origin["canonical_statement_sha256"]):
                raise ValueError("Native source occurrence binding differs.")
            raw_up.extend(agent["raw_grounding"].get("UP")
                          for agent in source["input"]["agents"]
                          if agent["status"] != "neutral")
            source_rows.append({
                "ordinal": ordinal, "source_hash": str(ev["source_hash"]),
                "source_api": ev["source_api"],
                "validated_PMID": source["pmid"],
                "canonical_evidence_sha256": binding["canonical_evidence_sha256"],
                "original_grounding_case_id": source["case_id"],
                "text_characters": len(ev.get("text") or ""),
                "context_present": ev.get("context") is not None,
                "epistemics_present": ev.get("epistemics") is not None,
            })
        statement = deepcopy(native)
        if "belief" not in statement:
            raise ValueError("Expected native released-belief field absent.")
        statement.pop("belief")
        _no_outcome_fields(statement)
        input_bytes = encoded(statement)
        matched_up = {u for u in raw_up if isinstance(u, str) and u in cohort}
        cases.append({
            "case_id": "indra-statement:" + pa,
            "pa_hash": pa, "group_id": group, "split": split,
            "statement_type": native["type"], "statement": statement,
            "source_binding": {
                "corpus_ordinal": origin["corpus_ordinal"],
                "canonical_statement_sha256": origin["canonical_statement_sha256"],
                "raw_source_line_sha256": hashlib.sha256(raw_line).hexdigest(),
                "native_source_artifact": "native_source_statements.jsonl",
            },
            "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
            "input_utf8_bytes": len(input_bytes),
            "input_characters": len(input_bytes.decode()),
            "original_evidence_count": len(evidence),
            "unique_original_source_hash_count": len(hashes),
            "source_evidence": source_rows,
            "source_counts": dict(Counter(ev["source_api"] for ev in evidence)),
            "all_original_evidence_admitted": True,
            "eligibility_used_curator_correctness_tags": False,
            "cohort_linkage": {
                "any_raw_UP_among_current99": bool(matched_up),
                "all_actual_agent_raw_UPs_among_current99": bool(raw_up) and all(
                    isinstance(u, str) and u in cohort for u in raw_up),
                "matching_raw_UP_accessions": sorted(matched_up),
                "meaning": "Exact assigned-source accession linkage, not complete current-app claim equivalence or biological confirmation.",
            },
        })
        raw_lines.append(raw_line)
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate original statement case.")
    # Source membership and request inputs are materialized before label access.
    output.mkdir(parents=True)
    _write_jsonl(output / "source_cases.jsonl", cases)
    with (output / "native_source_statements.jsonl").open("xb") as stream:
        for line in raw_lines:
            stream.write(line)
    curation_pairs = defaultdict(list)
    for row in json.loads(sources["native_curations"].read_text()):
        curation_pairs[(str(row["pa_hash"]), str(row["source_hash"]))].append(row)
    labels = []
    for case in cases:
        evidence_labels = []
        for source in case["source_evidence"]:
            records = curation_pairs[(case["pa_hash"], source["source_hash"])]
            if not records:
                raise ValueError("An admitted original source lacks curations.")
            tags = Counter(row["tag"] for row in records)
            positive_flags = {tag in POSITIVE_TAGS for tag in tags}
            evidence_labels.append({
                "source_hash": source["source_hash"],
                "native_tag_counts": dict(sorted(tags.items())),
                "curation_row_count": len(records),
                "author_positive": all(tag in POSITIVE_TAGS for tag in tags),
                "mixed_author_binary_curations": len(positive_flags) > 1,
            })
        gold = "supported" if any(e["author_positive"] for e in evidence_labels) else "unsupported"
        labels.append({"case_id": case["case_id"], "gold": gold,
                       "all_original_evidence_curator_reviewed": True,
                       "native_evidence_labels": evidence_labels})
    _write_jsonl(output / "labels.private.jsonl", labels)
    gold = {row["case_id"]: row["gold"] for row in labels}
    counts, types, distributions, readers = (defaultdict(Counter) for _ in range(4))
    groups, publications, linked_accessions = (defaultdict(set) for _ in range(3))
    for case in cases:
        for scope in ("all", case["split"]):
            counts[scope]["claims"] += 1
            counts[scope][gold[case["case_id"]]] += 1
            counts[scope]["evidence_occurrences"] += case["original_evidence_count"]
            counts[scope]["cohort_linked_claims"] += case["cohort_linkage"]["any_raw_UP_among_current99"]
            counts[scope]["all_agents_cohort_linked_claims"] += case["cohort_linkage"]["all_actual_agent_raw_UPs_among_current99"]
            types[scope][case["statement_type"]] += 1
            distributions[scope][case["original_evidence_count"]] += 1
            readers[scope].update(case["source_counts"])
            groups[scope].add(case["group_id"])
            publications[scope].update(e["validated_PMID"] for e in case["source_evidence"])
            linked_accessions[scope].update(case["cohort_linkage"]["matching_raw_UP_accessions"])
    if groups["development"] & groups["test"] or publications["development"] & publications["test"]:
        raise ValueError("Development and reserve share an existing group or validated PMID.")
    if any(file_sha(path) != pins[name]["sha256"] for name, path in sources.items()):
        raise ValueError("An original source changed during preparation.")
    report = {
        "format": "biograph-steward.mechanistic-claim-source-frame.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "SOURCE_FRAME_PREPARED_RUNNER_PROTOCOL_PENDING",
        "task": "Expert-relative sentence/evidence-to-native-mechanistic-statement faithfulness, not independent experimental or whole-Pharos biological accuracy.",
        "primary_admission": "Every original evidence occurrence uniquely bound, admitted to the existing human-gene source frame and curator-reviewed; same label-independent admission for both classes. Original duplicate source hashes excluded.",
        "class_policy": "Author2023: a source is positive iff every native tag is in correct/hypothesis/act_vs_amt; binary disagreement is negative. Statement is positive if at least one complete admitted source is positive, otherwise unsupported since all original sources are admitted/reviewed.",
        "counts": {key: dict(value) for key, value in counts.items()},
        "statement_types": {key: dict(value) for key, value in types.items()},
        "evidence_count_distributions": {key: {str(n): value[n] for n in sorted(value)} for key, value in distributions.items()},
        "source_api_evidence_counts": {key: dict(value) for key, value in readers.items()},
        "group_counts": {key: len(value) for key, value in groups.items()},
        "distinct_validated_PMID_counts": {key: len(value) for key, value in publications.items()},
        "distinct_cohort_linked_accessions": {key: len(value) for key, value in linked_accessions.items()},
        "no_development_reserve_group_or_validated_PMID_overlap": True,
        "excluded_original_statement_counts": dict(exclusions),
        "input_projection": "Complete original native Statement JSON with only top-level released belief removed. No n-ary flattening, qualifier removal, evidence omission or identity repair. Original JSON lines including belief retained separately and excluded from model-request input.",
        "max_evidence_count": max(c["original_evidence_count"] for c in cases),
        "max_input_utf8_bytes": max(c["input_utf8_bytes"] for c in cases),
        "max_input_characters": max(c["input_characters"] for c in cases),
        "context_feasibility": "Exact final prompt/schema token count must be checked against the configured16000 context before inference; bytes/characters are not tokens. Oversized cases abstain without partial-evidence pruning.",
        "prior_use": "Existing corpus, split and grounding endpoint were previously inspected/evaluated; new endpoint is retrospective reuse, not a fresh blind gold set. Grounding predictions are not scientific truth labels.",
        "data_license": "CC BY-NC-SA4.0; native library BSD-2-Clause; no MIT relicensing of raw source data/text. Author analysis inspected, not copied or executed.",
        "model_calls": 0, "source_retrieval_calls": 0,
        "old_source_files_unchanged": True,
        "case_and_input_files_have_no_gold_or_curation_fields": True,
        "source_files": pins,
        "preparer_sha256": file_sha(__file__),
        "output_files": {path.name: {"sha256": file_sha(path), "bytes": path.stat().st_size}
                         for path in sorted(output.iterdir()) if path.is_file()},
    }
    (output / "frame_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--cohort-targets", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = prepare(args.source_root, args.cohort_targets, args.output)
    print(json.dumps({"counts": result["counts"], "max_evidence_count": result["max_evidence_count"],
                      "max_input_utf8_bytes": result["max_input_utf8_bytes"]}, sort_keys=True))
