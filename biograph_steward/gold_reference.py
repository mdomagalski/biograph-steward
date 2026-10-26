"""Exact, outcome-agnostic reference alignment; not an official gold evaluator.

Reuse the saved graph's identities and qualifications. Reference labels remain
opaque strings. Missing/ambiguous matches never become scientific negatives.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from shutil import copyfile

from .assertions import QUALIFIERS, assertion_identity
from .client import digest, utcnow, write_json
from .file_utils import new_output, sha
from .gold_packet import _decode, load_packet

FORMAT = "biograph-steward.reference-mapping.v1"
REPORT_FORMAT = "biograph-steward.reference-alignment.v1"
SHA256 = re.compile(r"[0-9a-f]{64}")
BASELINE_KEYS = ("packet_id", "graph_sha256", "snapshot_sha256", "civic_snapshot_sha256", "database_version")


def _exact_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + " has missing or unsupported fields.")


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be nonempty text.")
    return value


def mapping_template(packet, output):
    manifest, _ = load_packet(packet)
    value = {
        "format": FORMAT, "purpose": "alignment_only", "label_semantics": "uninterpreted",
        "baseline": {key: manifest.get(key) for key in BASELINE_KEYS},
        "reference": {"name": None, "source": None, "version": None, "sha256": None,
                      "kind": None, "baseline_version": None},
        "delimiter": "tab", "unit": "evidence_edge", "match_mode": "id",
        "columns": {"reference_id": "reference_id", "label": "label", "target_id": "edge_id"},
    }
    out = new_output(output, packet)
    write_json(out / "reference_mapping.template.json", value)
    return value


def _contract(value, manifest, reference_sha256):
    _exact_keys(value, ("format", "purpose", "label_semantics", "baseline", "reference",
                        "delimiter", "unit", "match_mode", "columns"), "Reference mapping")
    if (value["format"] != FORMAT or value["purpose"] != "alignment_only" or
            value["label_semantics"] != "uninterpreted"):
        raise ValueError("Only the local alignment-only contract is supported; scoring semantics are unknown.")
    _exact_keys(value["baseline"], BASELINE_KEYS, "Baseline binding")
    if value["baseline"] != {key: manifest.get(key) for key in BASELINE_KEYS}:
        raise ValueError("Reference mapping belongs to another baseline packet or source version.")
    ref = value["reference"]
    _exact_keys(ref, ("name", "source", "version", "sha256", "kind", "baseline_version"), "Reference metadata")
    for key in ("name", "source"):
        _text(ref[key], "Reference " + key)
    for key in ("version", "baseline_version"):
        if ref[key] is not None:
            _text(ref[key], "Reference " + key)
    if ref["kind"] not in {"synthetic_fixture", "organizer_reference", "external_reference"}:
        raise ValueError("Declare the reference kind; it is a supplied description, not authenticated provenance.")
    if ref["kind"] == "synthetic_fixture" and manifest["data_kind"] != "synthetic_demo":
        raise ValueError("Synthetic reference labels require an explicitly synthetic graph packet.")
    if ref["kind"] != "synthetic_fixture" and manifest["data_kind"] == "synthetic_demo":
        raise ValueError("A synthetic demo cannot serve as the baseline for a biological reference.")
    if ref["baseline_version"] is not None and ref["baseline_version"] != manifest.get("database_version"):
        raise ValueError("Declared reference baseline version differs from the packet's database version.")
    if not isinstance(ref["sha256"], str) or not SHA256.fullmatch(ref["sha256"]) or reference_sha256 != ref["sha256"]:
        raise ValueError("Reference artifact hash is missing or differs from the mapping contract.")
    if value["delimiter"] not in {"tab", "comma"} or value["unit"] not in {"evidence_edge", "assertion"}:
        raise ValueError("Declare a supported delimiter and evaluation unit; pair-level scoring is not inferred.")
    if value["match_mode"] not in {"id", "qualified_identity"}:
        raise ValueError("Only exact local ID or complete qualified-identity matching is supported.")
    required = {"reference_id", "label"}
    required |= {"target_id"} if value["match_mode"] == "id" else {"subject", "predicate", "object", "kind", "qualifiers"}
    _exact_keys(value["columns"], required, "Column mapping")
    names = []
    for key, column in value["columns"].items():
        if key == "label" and column is None:
            continue
        names.append(_text(column, "Column " + key))
    if len(names) != len(set(names)):
        raise ValueError("Mapped columns must be distinct.")


def _rows(material, contract):
    try:
        content = material.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content, newline=""),
                                delimiter="\t" if contract["delimiter"] == "tab" else ",", strict=True)
        names = reader.fieldnames
        if not names or any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError("Reference header is absent, empty or duplicated.")
        if not {v for v in contract["columns"].values() if v is not None} <= set(names):
            raise ValueError("Reference file lacks mapped columns.")
        rows, seen = [], set()
        for number, row in enumerate(reader, 1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Reference row width differs from its header.")
            rid = _text(row[contract["columns"]["reference_id"]], "Reference row ID")
            if rid != rid.strip():
                raise ValueError("Reference IDs may not contain surrounding whitespace.")
            if rid in seen:
                raise ValueError("Duplicate reference row ID: " + rid)
            seen.add(rid)
            rows.append((number, rid, row))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Reference is not a valid UTF-8 delimited table.") from exc


def _identity(row, unit):
    return assertion_identity(row["subject"], row["predicate"], row["object"],
                              row["record_kind" if unit == "evidence_edge" else "kind"],
                              row["qualifiers"])


def align_rows(graph, rows, contract):
    """Alignment coverage only. No label interpretation, direction reversal or aliases."""
    unit = contract["unit"]
    targets = graph["edges" if unit == "evidence_edge" else "assertions"]
    by_id = {r["id"]: r for r in targets}
    if len(by_id) != len(targets):
        raise ValueError("Baseline contains repeated target IDs.")
    identities = defaultdict(list)
    for target in targets:
        identities[digest(_identity(target, unit))].append(target["id"])
    nodes = {node["id"] for node in graph["nodes"]}
    columns, matched, result = contract["columns"], defaultdict(list), []
    for number, rid, raw in rows:
        label = raw[columns["label"]] if columns["label"] is not None else None
        identity, reason = None, None
        if contract["match_mode"] == "id":
            identifier = _text(raw[columns["target_id"]], "Target ID")
            matches = [identifier] if identifier in by_id else []
            if not matches:
                reason = "exact_local_id_not_found"
        else:
            try:
                qualifiers = _decode(raw[columns["qualifiers"]])
                if not isinstance(qualifiers, dict) or not set(QUALIFIERS) <= set(qualifiers):
                    raise ValueError("All core qualifier slots must be explicit, including nulls.")
                identity = assertion_identity(*(raw[columns[key]] for key in
                    ("subject", "predicate", "object", "kind")), qualifiers)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Reference {rid} has an incomplete or unsupported qualified identity: {exc}") from exc
            matches = sorted(identities.get(digest(identity), []))
            if not matches:
                reason = ("endpoint_not_in_baseline" if not {identity["subject"], identity["object"]} <= nodes
                          else "complete_qualified_identity_not_found")
        status = "matched" if len(matches) == 1 else "ambiguous" if matches else "unmatched"
        if status == "ambiguous":
            reason = "multiple_evidence_records_share_the_qualified_identity"
        if status == "matched":
            matched[matches[0]].append(len(result))
        result.append({"reference_id": rid, "record_number": number, "raw_label": label,
                       "raw_reference_row": raw, "qualified_identity": identity,
                       "status": status, "reason": reason, "matched_target_ids": matches,
                       "matched_evidence_edge_ids": sorted({eid for mid in matches for eid in
                           ([mid] if unit == "evidence_edge" else by_id[mid]["evidence_edge_ids"])}),
                       "label_interpreted": False, "scored": False})
    collisions = []
    for target_id, indices in matched.items():
        if len(indices) < 2:
            continue
        collisions.append({"target_id": target_id, "reference_ids": [result[i]["reference_id"] for i in indices],
                           "different_raw_labels": len({result[i]["raw_label"] for i in indices}) > 1})
        for index in indices:
            result[index]["status"] = "reference_collision"
            result[index]["reason"] = "multiple_reference_rows_map_to_one_target"
    counts = Counter(row["status"] for row in result)
    unique = {row["matched_target_ids"][0] for row in result if row["status"] == "matched"}
    summary = {"reference_rows": len(result), "baseline_units": len(targets),
               "status_counts": {key: counts[key] for key in ("matched", "unmatched", "ambiguous", "reference_collision")},
               "uniquely_matched_baseline_units": len(unique), "baseline_units_without_unique_reference_match": len(targets) - len(unique),
               "reference_match_fraction": len(unique) / len(result) if result else None,
               "baseline_match_fraction": len(unique) / len(targets) if targets else None,
               "empty_label_rows": sum(row["raw_label"] in (None, "") for row in result),
               "rows_scored": 0}
    return result, summary, collisions


def align_reference(packet, reference, mapping, output):
    packet, reference, mapping = Path(packet), Path(reference), Path(mapping)
    for path in (reference, mapping):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Reference and mapping must be ordinary files, not symlinks.")
    manifest, graph = load_packet(packet)
    reference_bytes, mapping_bytes = reference.read_bytes(), mapping.read_bytes()
    contract = _decode(mapping_bytes)
    hashes = {"reference": hashlib.sha256(reference_bytes).hexdigest(),
              "mapping": hashlib.sha256(mapping_bytes).hexdigest()}
    _contract(contract, manifest, hashes["reference"])
    records, summary, collisions = align_rows(graph, _rows(reference_bytes, contract), contract)
    out = new_output(output, packet, reference, mapping)
    # The validated packet and original reference bytes travel with the report.
    for name in ("packet_manifest.json", *manifest["files"]):
        destination = out / "baseline_packet" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        copyfile(packet / name, destination)
    copied, _ = load_packet(out / "baseline_packet")
    if copied != manifest:
        raise ValueError("Packet changed during export; incomplete output must not be used.")
    (out / "reference_input.txt").write_bytes(reference_bytes)
    (out / "reference_mapping.json").write_bytes(mapping_bytes)
    if (sha(out / "reference_input.txt") != hashes["reference"] or sha(reference) != hashes["reference"] or
            sha(out / "reference_mapping.json") != hashes["mapping"] or sha(mapping) != hashes["mapping"]):
        raise ValueError("Reference inputs changed while exporting; incomplete output must not be used.")
    with (out / "alignment.jsonl").open("w", encoding="utf-8") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    report = {"format": REPORT_FORMAT, "created_at": utcnow(), "status": "alignment_only",
              "packet_id": manifest["packet_id"], "baseline": contract["baseline"],
              "reference": contract["reference"], "reference_description_authenticated": False,
              "reference_baseline_version_status": "unknown" if contract["reference"]["baseline_version"] is None else "declared_match",
              "unit": contract["unit"], "match_mode": contract["match_mode"],
              "summary": summary, "target_collisions": collisions,
              "official_protocol_available": False, "biological_accuracy_measured": False,
              "label_semantics": "uninterpreted", "metrics": None,
              "implementation_sha256": sha(__file__),
              "files": {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
              "limitations": ["This is a project-local adapter, not the official challenge evaluator or a KGX conformance claim.",
                  "Coverage is identity alignment, not scientific agreement; missing reference rows are not negative labels.",
                  "A matched assertion does not adjudicate each supporting evidence record.",
                  "No name/symbol matching, identifier equivalence, relation reversal or qualifier dropping is performed.",
                  "Source hashes bind local bytes, not organizer authenticity or independence of evidence.",
                  "Official reference scope, label meanings, split rules and required output schema remain to be supplied."]}
    report["content_sha256"] = digest(report)
    write_json(out / "report.json", report)
    return report
