"""Read-only native GOA inspection with selected-record source replay.

The sidecar's byte inventory is checked, then the existing optional Biopython
producer replays the requested preserved subject. This does not revalidate the
original Gold packet or identify historical Pharos annotation records.
"""
from collections import Counter
from copy import deepcopy
import gzip
from pathlib import Path
import re

from . import go_qualification, gold_packet
from .client import digest
from .file_utils import sha
from .graph import UNIPROT


FORMAT = "biograph-steward.native-go-inspection.v1"
REPORT = "go_context_qualification.json"
FILES = frozenset({"native_records.jsonl", "edge_compatibilities.jsonl",
                   "source/annotations.gaf.gz"})
SHA256 = re.compile(r"[0-9a-f]{64}")
GO_ID = re.compile(r"GO:[0-9]{7}")
_PARSED_LIST_FIELDS = frozenset({"Qualifier", "DB:Reference", "With", "Synonym", "Taxon_ID"})
LIMITATIONS = [
    "This verifies sidecar bytes and replays the queried native subject; the original Gold packet and graph are not revalidated.",
    "Returned qualifiers belong to their own native GOA records, not reconstructed historical Pharos annotations.",
    "Positive and NOT records, product forms and contextual alternatives remain separate; no preferred candidate is selected.",
    "References may be alternate identifiers for one study; returned records are not independent corroborating votes.",
    "No matching source records means no result in this preserved query scope, not biological absence.",
    "The pinned source is not guaranteed to be the latest GO release; publisher authenticity and experimental truth are not established here.",
]


def _need(condition, message):
    if not condition:
        raise ValueError("GO context inspection: " + message)


def _protein(value):
    return (isinstance(value, str) and value.startswith("UniProtKB:")
            and UNIPROT.fullmatch(value[len("UniProtKB:"):]) is not None)


def _rows(path):
    rows = []
    for raw in path.read_bytes().splitlines():
        value = gold_packet._decode(raw)
        _need(isinstance(value, dict), "sidecar inventory rows must be objects.")
        rows.append(value)
    return rows


def load_go_context(context):
    """Verify a native sidecar without optional dependencies or Gold replay.

    Every stored native row is rebound to its raw GAF line. The existing
    producer reconstructs native fields and compatibility candidates, but this
    does not authenticate the historical graph or run the full GAF validator.
    """
    folder = Path(context).absolute()
    _need(folder.is_dir() and not folder.is_symlink(), "context must be an ordinary nonsymlink directory.")
    paths = list(folder.rglob("*"))
    _need(not any(path.is_symlink() for path in paths), "sidecar paths must not be symlinks.")
    _need({p.relative_to(folder).as_posix() for p in paths if p.is_file()} == FILES | {REPORT}
          and {p.relative_to(folder).as_posix() for p in paths if p.is_dir()} == {"source"}
          and all(p.is_file() or p.is_dir() for p in paths), "sidecar file inventory differs.")
    report_file_sha256 = sha(folder / REPORT)
    report = gold_packet._read(folder / REPORT)
    _need(gold_packet._sealed(report) and report.get("format") == go_qualification.FORMAT,
          "sidecar report seal or format differs.")
    _need(all(report.get(key) is False for key in
              ("historical_native_identity_established", "original_qualifiers_backfilled",
               "complete_gaf_rules_and_ontology_validation_performed", "source_graph_mutated",
               "scientific_accuracy_measured", "independent_reference_validation_performed")),
          "sidecar scientific-scope policy differs.")
    _need(all(type(report.get(key)) is int and report[key] == 0 for key in ("model_calls", "source_fetches")),
          "sidecar offline-source policy differs.")
    files = report.get("files")
    _need(isinstance(files, dict) and set(files) == FILES
          and all(isinstance(value, str) and SHA256.fullmatch(value) for value in files.values()),
          "sidecar source-file pins differ.")
    _need(all(sha(folder / name) == expected for name, expected in files.items()),
          "sidecar source bytes differ from the report.")
    source = report.get("source")
    _need(isinstance(source, dict) and source.get("gaf_sha256") == files["source/annotations.gaf.gz"],
          "native GAF source pin differs.")
    _need(source.get("source_url_authentication_performed") is False
          and source.get("parser") == {"package": "biopython", "version": go_qualification.PARSER_VERSION,
                                     "function": "Bio.UniProt.GOA.gafiterator"},
          "native source/parser policy differs.")
    source_headers = source.get("headers")
    _need(isinstance(source_headers, list) and source_headers
          and all(isinstance(header, str) for header in source_headers)
          and source_headers[0] == "!gaf-version: 2.2"
          and any(header.startswith("!generated-by:") for header in source_headers)
          and any(header.startswith("!date-generated:") for header in source_headers)
          and type(source.get("total_source_rows")) is int and source["total_source_rows"] >= 0,
          "reviewed native GAF source metadata is missing.")
    _need(isinstance(report.get("packet_id"), str) and re.fullmatch(r"packet:[0-9a-f]{64}", report["packet_id"])
          and all(isinstance(report.get(key), str) and SHA256.fullmatch(report[key]) for key in
                  ("graph_sha256", "snapshot_sha256", "source_graph_file_sha256", "implementation_sha256")),
          "sidecar source-graph or implementation bindings are missing.")
    counts = report.get("counts")
    _need(isinstance(counts, dict), "sidecar counts are missing.")
    native = _rows(folder / "native_records.jsonl")
    compatible = _rows(folder / "edge_compatibilities.jsonl")
    _need(all(isinstance(row.get("id"), str) and row["id"] and _protein(row.get("subject"))
              and row.get("source_gaf_sha256") == source["gaf_sha256"]
              and type(row.get("source_line")) is int and row["source_line"] > 0 for row in native)
          and len({row["id"] for row in native}) == len(native), "native row identities or pins differ.")
    _need(len({row["source_line"] for row in native}) == len(native), "native source lines repeat.")
    for row in native:
        _need(isinstance(row.get("raw_line"), str) and isinstance(row.get("raw_fields"), list)
              and all(isinstance(value, str) for value in row["raw_fields"])
              and isinstance(row.get("parsed"), dict)
              and set(row["parsed"]) == set(go_qualification.GAF_FIELDS)
              and all(isinstance(value, list) and all(isinstance(item, str) for item in value)
                      if key in _PARSED_LIST_FIELDS else isinstance(value, str)
                      for key, value in row["parsed"].items()), "native row fields are missing or malformed.")
        rebuilt = go_qualification.native_record(row["source_line"], row["raw_line"],
                    row["raw_fields"], row["parsed"], source["gaf_sha256"])
        _need(row == rebuilt, "stored native row does not reconstruct from its raw fields.")
    _need(all(isinstance(row.get("edge_id"), str) and row["edge_id"]
              and isinstance(row.get("compatibility_key"), list) and len(row["compatibility_key"]) == 5
              and _protein(row["compatibility_key"][0])
              and isinstance(row["compatibility_key"][1], str) and GO_ID.fullmatch(row["compatibility_key"][1])
              and all(value is None or isinstance(value, str) for value in row["compatibility_key"][2:])
              for row in compatible)
          and len({row["edge_id"] for row in compatible}) == len(compatible),
          "original GO-edge scope is invalid or duplicated.")
    subjects = {row["compatibility_key"][0] for row in compatible}
    _need({row["subject"] for row in native} <= subjects
          and counts.get("original_go_edges") == len(compatible)
          and counts.get("exact_go_subjects") == len(subjects)
          and counts.get("native_rows") == len(native)
          and counts.get("native_subjects") == len({row["subject"] for row in native}),
          "sidecar subject scope or counts differ.")
    # Reuse the existing candidate producer; the original graph is not present
    # here, so only the sidecar's declared keys can be replayed.
    projected = []
    for row in compatible:
        subject, term, evidence, assigned_by, aspect = row["compatibility_key"]
        projected.append({"id": row["edge_id"], "assertion_id": row.get("assertion_id"),
            "record_kind": "go_annotation", "subject": subject, "object": term,
            "evidence_record": {"goid": term, "evidence": evidence,
                                "assigned_by": assigned_by, "type": aspect}})
    base = ("edge_id", "assertion_id", "compatibility_key", "status", "native_record_ids",
            "candidate_count", "candidate_polarities", "both_positive_and_not_candidates",
            "candidate_product_forms", "candidate_extension_literals", "historical_record_identity_established",
            "original_qualifiers_backfilled", "biological_truth_assessed", "pruning_decision")
    rebuilt_links = go_qualification.project_compatibilities({"edges": projected}, native)
    _need(all(all(key in saved and saved[key] == rebuilt[key] for key in base)
              and all(saved[key] == value for key, value in rebuilt.items() if key in saved and key not in base)
              for saved, rebuilt in zip(compatible, rebuilt_links)),
          "stored native compatibility candidates do not replay from their declared keys.")
    statuses = Counter(row["status"] for row in rebuilt_links)
    derived = {"original_go_edges": len(compatible), "exact_go_subjects": len(subjects),
        "native_rows": len(native), "native_subjects": len({row["subject"] for row in native}),
        "native_not_rows": sum(row["negated"] for row in native),
        "native_extension_rows": sum(bool(row["annotation_extension_raw"]) for row in native),
        "native_product_form_rows": sum(bool(row["gene_product_form_id"]) for row in native),
        "known_consumed_reference_rows": sum(bool(row["known_consumed_reference_ids"]) for row in native),
        "edges_with_positive_and_not_candidates": sum(row["both_positive_and_not_candidates"] for row in rebuilt_links),
        **{key: statuses[key] for key in ("no_compatible_native_record", "one_compatible_native_record",
                                        "multiple_compatible_native_records")}}
    for key, status in (("unmatched_with_exact_subject_go_native_records", "exact_subject_go_present_projection_fields_differ"),
                        ("unmatched_without_exact_subject_go_native_records", "no_exact_subject_go_native_record")):
        if key in counts:
            derived[key] = sum(row["diagnostic_status"] == status for row in rebuilt_links)
    _need(all(type(counts.get(key)) is int and counts[key] == value for key, value in derived.items()),
          "derived sidecar counts differ.")
    wanted = {row["source_line"]: row["raw_line"] for row in native}
    expected_lines, found, headers, total, leading_headers = set(), set(), [], 0, True
    accessions = {subject[len("UniProtKB:"):] for subject in subjects}
    try:
        with gzip.open(folder / "source/annotations.gaf.gz", "rt", encoding="utf-8", newline="") as stream:
            for number, line in enumerate(stream, 1):
                raw = line.rstrip("\r\n")
                if leading_headers and raw.startswith("!"):
                    headers.append(raw)
                else:
                    leading_headers = False
                if raw and not raw.startswith("!"):
                    total += 1
                    fields = raw.split("\t")
                    _need(len(fields) == 17, "native GAF source does not have 17 fields.")
                    if fields[0] == "UniProtKB" and fields[1] in accessions:
                        expected_lines.add(number)
                if number in wanted:
                    _need(raw == wanted[number], "native record differs from its original GAF line.")
                    found.add(number)
    except (OSError, EOFError, UnicodeError) as exc:
        raise ValueError("GO context inspection: preserved GAF cannot be read.") from exc
    _need(found == set(wanted) == expected_lines and source.get("headers") == headers
          and source.get("total_source_rows") == total, "native GAF line completeness or metadata binding differs.")
    _need(all(sha(folder / name) == expected for name, expected in files.items())
          and sha(folder / REPORT) == report_file_sha256, "sidecar changed during verification.")
    return report, native, compatible


def inspect_go_context(context, protein, *, go_id=None):
    """Return all native records for one exact preserved protein and optional GO ID.

    The optional source parser is invoked only during inspection. Nothing is
    written and no alias, isoform collapse, term hierarchy or winner is inferred.
    """
    _need(_protein(protein), "provide an exact UniProtKB protein CURIE.")
    _need(go_id is None or isinstance(go_id, str) and GO_ID.fullmatch(go_id),
          "provide an exact GO CURIE or no GO filter.")
    report, native, compatible = load_go_context(context)
    folder = Path(context).absolute()
    report_file_sha256 = sha(folder / REPORT)
    subjects = {row["compatibility_key"][0] for row in compatible}
    in_scope = protein in subjects
    # Do not expand the preserved cohort if the full GAF happens to contain an
    # otherwise valid requested identifier. Out-of-scope queries select no rows.
    selected = {protein[len("UniProtKB:"):]} if in_scope else set()
    replayed, source = go_qualification.read_native_gaf(
        folder / "source/annotations.gaf.gz", selected, report["source"]["gaf_sha256"])
    _need(all(report["source"].get(key) == source.get(key) for key in
              ("headers", "total_source_rows", "gaf_sha256", "parser")),
          "native parser metadata differs from the preserved report.")
    stored = [row for row in native if row["subject"] == protein]
    _need(stored == replayed, "queried native rows do not replay from the original GAF.")
    _need(all(sha(folder / name) == expected for name, expected in report["files"].items())
          and sha(folder / REPORT) == report_file_sha256, "sidecar changed during inspection.")
    records = [deepcopy(row) for row in replayed if go_id is None or row["go_id"] == go_id]
    polarities = Counter("NOT" if row["negated"] else "positive" for row in records)
    result = {"format": FORMAT, "query": {"protein": protein, "go_id": go_id},
        "status": "source_records_available" if records else "no_matching_source_records",
        "record_count": len(records), "records": records,
        "protein_in_preserved_scope": in_scope, "protein_native_record_count": len(replayed),
        "counts": {"positive_records": polarities["positive"], "not_records": polarities["NOT"]},
        "source": deepcopy(report["source"]),
        "baseline_bindings": {key: report[key] for key in
            ("packet_id", "graph_sha256", "snapshot_sha256", "source_graph_file_sha256")},
        "context_report_content_sha256": report["content_sha256"],
        "context_report_file_sha256": sha(folder / REPORT), "context_files_sha256": deepcopy(report["files"]),
        "context_producer_implementation_sha256": report["implementation_sha256"],
        "native_parser_adapter_sha256": sha(go_qualification.__file__),
        "inspection_implementation_sha256": sha(__file__),
        "original_gold_packet_revalidated": False, "queried_native_rows_replayed": True,
        "historical_record_identity_established": False, "original_qualifiers_backfilled": False,
        "independent_biological_accuracy_established": False, "biological_absence_inferred": False,
        "source_graph_mutated": False, "model_calls": 0, "source_fetches": 0,
        "limitations": deepcopy(LIMITATIONS)}
    result["content_sha256"] = digest(result)
    return result
