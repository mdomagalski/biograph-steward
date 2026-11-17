#!/usr/bin/env python3
"""Freeze, then inspect exactly four development-only IntAct PSI-MI XML files.

The prepare command never accesses selected XML. The inspect command requires
the exact pre-access receipt SHA and records critical-field differences without
repairing either official format or opening reserved studies.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from http.client import HTTPException, IncompleteRead
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow
from scripts.evaluate_intact_evidence_fidelity import load_reference
from scripts.validate_intact_xml_provenance import (assess_xml_summary, inventory,
    parse_transport, references, runtime_bindings, save_new, sha, term_id,
    verify_controls, xref_tuple)

DEVELOPMENT = ("40075158", "40404733", "40071126", "40739265")
DIRECTORY = "https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psi25/pmid/2025/"
MAX_BYTES = 2 * 1024 * 1024
CONTRACT = ROOT / "docs/evaluations/intact_xml_20261026_contract.json"
CONTRACT_SHA = "fa305464e1b80288773ac7bebe46c5905801c47e01b715ee012d63e9cf22f1dc"
INSPECTION = ROOT / "runs/intact_development_inspection_20261026"
FORMAT = "biograph-steward.intact-xml-development-inspection.v1"


def contract():
    if sha(CONTRACT) != CONTRACT_SHA:
        raise ValueError("The pre-access XML contract changed; preserve and version amendments.")
    data = json.loads(CONTRACT.read_text())
    allowed = [{"publication_id": p, "url": DIRECTORY + p + ".xml"} for p in DEVELOPMENT]
    if data["release"]["allowlist"] != allowed or data["release"]["maximum_source_bytes"] != MAX_BYTES:
        raise ValueError("Only the exact four development URLs and original byte bound are allowed.")
    for name, expected in data["frozen_dependencies"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("Frozen metadata/original reference dependency changed: " + name)
    return data


def code_bindings():
    return {str(path): sha(path) for path in (Path(__file__).resolve(),
            ROOT / "scripts/validate_intact_xml_provenance.py",
            ROOT / "scripts/validate_intact_reader_controls.py",
            ROOT / "scripts/evaluate_intact_evidence_fidelity.py")}


def reference_bindings():
    """Finite already-consumed reference paths; no reserved path is enumerated."""
    paths = [INSPECTION / "report.json", INSPECTION / "row_ledger.jsonl"]
    paths.extend(INSPECTION / (pmid + "_reader.jsonl") for pmid in DEVELOPMENT)
    paths.extend(ROOT / "runs/intact_fidelity_preparation_20261026/opaque_sources" / (pmid + ".txt") for pmid in DEVELOPMENT)
    return {str(path): sha(path) for path in paths}


def prepare(classes, classpath_file, controls_report, output, java="java"):
    data = contract()
    inventory()
    controls_path = Path(controls_report).resolve()
    controls = json.loads(controls_path.read_text())
    verify_controls(controls)
    bindings = runtime_bindings(classes, classpath_file, java)
    if controls["runtime_bindings"] != bindings:
        raise ValueError("Use exactly the official XML implementation tested by controls.")
    original, ledger, _ = load_reference(INSPECTION)
    if len(original) != 18 or sum(x["kind"] == "evidence" for x in ledger) != 14 or sum(x["eligible"] for x in ledger) != 4:
        raise ValueError("Original development denominator changed.")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"format": FORMAT, "phase": "pre_access", "created_at": utcnow(),
               "selected_xml_bodies_accessed": False, "reserved_bodies_accessed": False,
               "contract_path": str(CONTRACT), "contract_sha256": CONTRACT_SHA,
               "allowlist": data["release"]["allowlist"], "maximum_source_bytes": MAX_BYTES,
               "runtime_bindings": bindings, "code_bindings": code_bindings(),
               "controls_report": str(controls_path), "controls_report_sha256": sha(controls_path),
               "reference_bindings": reference_bindings(),
               "original_denominators": {"physical_rows": 18, "evidence_rows": 14, "eligible_rows": 4},
               "scope": data["claim"]}
    receipt["content_sha256"] = digest(receipt)
    save_new(output / "pre_access.json", receipt)
    (output / "contract.json").write_bytes(CONTRACT.read_bytes())
    return receipt


def verify_preaccess(path, expected_sha):
    path = Path(path).resolve()
    if sha(path) != expected_sha:
        raise ValueError("Explicit pre-access SHA does not match the frozen receipt.")
    receipt = json.loads(path.read_text())
    core = deepcopy(receipt); supplied = core.pop("content_sha256", None)
    if digest(core) != supplied or receipt.get("phase") != "pre_access":
        raise ValueError("Pre-access content seal/phase is invalid.")
    data = contract()
    if (receipt.get("contract_sha256") != CONTRACT_SHA or receipt.get("allowlist") != data["release"]["allowlist"]
            or receipt.get("maximum_source_bytes") != MAX_BYTES
            or receipt.get("selected_xml_bodies_accessed") is not False
            or receipt.get("reserved_bodies_accessed") is not False
            or receipt.get("code_bindings") != code_bindings()
            or receipt.get("reference_bindings") != reference_bindings()):
        raise ValueError("Contract, allowlist, original reference or code changed after pre-access freeze.")
    controls_path = Path(receipt["controls_report"])
    if sha(controls_path) != receipt["controls_report_sha256"]:
        raise ValueError("Frozen XML controls changed.")
    controls = json.loads(controls_path.read_text()); verify_controls(controls)
    runtime = receipt["runtime_bindings"]
    current = runtime_bindings(runtime["classes_directory"], runtime["classpath_file"], runtime["java"]["executable"])
    if current != runtime or controls["runtime_bindings"] != runtime:
        raise ValueError("Official XML reader/runtime no longer matches passing controls.")
    return receipt


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirects are forbidden by the exact-source XML contract.")


def fetch_exact(pmid, url, output, opener=None):
    """One allowlisted bounded request; save opaque bytes and receipt before parse."""
    if pmid not in DEVELOPMENT or url != DIRECTORY + pmid + ".xml":
        raise ValueError("Reserved/unknown source or alternate URL is forbidden.")
    output = Path(output)
    start = {"publication_id": pmid, "url": url, "started_at": utcnow(),
             "maximum_bytes": MAX_BYTES, "attempt": 1, "redirects": False, "retries": False}
    save_new(output / (pmid + "_retrieval_started.json"), start)
    receipt = deepcopy(start)
    body = b""
    try:
        opener = opener or build_opener(NoRedirect())
        request = Request(url, headers={"User-Agent": "BioGraph-Steward/IntAct-dev-provenance", "Accept-Encoding": "identity"})
        with opener.open(request, timeout=60) as response:
            receipt["status"] = response.status
            receipt["headers"] = dict(response.headers.items())
            receipt["final_url"] = response.geturl()
            if response.status != 200 or response.geturl() != url:
                raise ValueError("Exact source did not return HTTP200 without redirect.")
            if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
                raise ValueError("Compressed transport is outside the bounded opaque-byte contract.")
            declared = response.headers.get("Content-Length")
            if declared is not None and (not declared.isdigit() or int(declared) > MAX_BYTES):
                raise ValueError("Declared XML size exceeds the fixed bound or is invalid.")
            try:
                body = response.read(MAX_BYTES + 1)
            except IncompleteRead as error:
                body = error.partial[:MAX_BYTES + 1]
                with (output / (pmid + ".partial.xml")).open("xb") as stream:
                    stream.write(body)
                receipt["partial_bytes"] = len(body)
                receipt["partial_sha256"] = hashlib.sha256(body).hexdigest()
                raise ValueError("Incomplete HTTP body; partial opaque bytes retained.") from error
            with (output / (pmid + ".xml")).open("xb") as stream:
                stream.write(body)
            receipt["bytes"] = len(body); receipt["sha256"] = hashlib.sha256(body).hexdigest()
            if len(body) > MAX_BYTES:
                raise ValueError("XML body exceeds the fixed bound; truncated opaque evidence preserved.")
            if declared is not None and int(declared) != len(body):
                raise ValueError("XML byte count differs from HTTP Content-Length.")
            receipt["outcome"] = "opaque_bytes_saved_not_decoded"
    except (OSError, ValueError, HTTPError, HTTPException) as error:
        receipt["outcome"] = "failed"; receipt["error"] = str(error)
        if isinstance(error, HTTPError):
            receipt["status"] = error.code; receipt["headers"] = dict(error.headers.items())
        save_new(output / (pmid + "_http_receipt.json"), receipt)
        raise
    save_new(output / (pmid + "_http_receipt.json"), receipt)
    return receipt


def values(row, name):
    return ((row.get("source_fields") or {}).get(name) or {}).get("values", [])


def ids(items):
    return sorted({term_id(x) for x in items}, key=str)


def identity_pairs(items):
    return sorted({(xref_tuple(x)[0], x.get("id")) for x in items})


def xml_evidence_ids(evidence):
    """Only identity-qualified aliases; generic see-also never becomes identity."""
    result = set()
    for xref in references(evidence):
        database, accession, qualifier = xref_tuple(xref)
        if database == "intact" and qualifier == "MI:0356":
            result.add((database, accession))
        if database == "imex" and qualifier == "MI:0662":
            result.add((database, accession))
    if evidence.get("imex_id"):
        result.add(("imex", evidence["imex_id"]))
    return result


def provenance_record(pmid, row):
    evidence = row["evidence"]
    return {"publication_id": pmid, "evidence_sequence": row["evidence_sequence"],
            "xml_id": evidence.get("xml_id"), "source_locator": evidence.get("source_locator"),
            "identifiers": evidence.get("identifiers"), "xrefs": evidence.get("xrefs"),
            "annotations": evidence.get("annotations"), "imex_id": evidence.get("imex_id"),
            "experiments": [{key: exp.get(key) for key in ("xml_id", "source_locator", "xrefs", "annotations", "publication")} for exp in evidence.get("experiments") or []],
            "study_reuse": "not_determined", "study_independence": "not_determined",
            "interpretation": "Qualified source statements preserved. See-also/method citation or absent annotation alone does not establish reuse or independence."}


def verify_source_bytes(source, receipt):
    """Bind each parser access to the retained opaque HTTP bytes, without decode."""
    source = Path(source)
    if source.is_symlink() or source.stat().st_size != receipt.get("bytes") or sha(source) != receipt.get("sha256"):
        raise ValueError("Retained XML bytes changed relative to their HTTP receipt.")


def assess_development_xml(summary, records, returncode):
    gate = assess_xml_summary(summary, returncode)
    if summary.get("xml_version") != "v2_5_4" or any(row.get("xml_version") != "v2_5_4" for row in records):
        gate["reasons"].append("xml_version_not_tested_2_5_4")
    gate["reasons"] = sorted(set(gate["reasons"]))
    gate["quarantined"] = bool(gate["reasons"])
    return gate


def compare_study(pmid, original_records, xml_records):
    """Compare critical official-reader fields without parsing biological XML."""
    original = [item for item in original_records if item["ledger"]["kind"] == "evidence"
                and item["ledger"]["publication_id"] == "pubmed:" + pmid]
    by_id = defaultdict(list)
    for index, row in enumerate(xml_records):
        for identity in xml_evidence_ids(row["evidence"]):
            by_id[identity].append(index)
    rows, matched_xml = [], Counter()
    for item in original:
        ledger, mitab = item["ledger"], item["reader_record"]
        primary_ids = identity_pairs([x for x in values(mitab, "evidence_ids") if xref_tuple(x)[0] == "intact"])
        candidates = sorted({index for identity in primary_ids for index in by_id.get(tuple(identity), [])})
        result = {"source": {k: ledger[k] for k in ("publication_id", "artifact_sha256", "source_line")}, "original_eligible": ledger["eligible"],
                  "original_evidence_ids": values(mitab, "evidence_ids"), "xml_candidates": candidates,
                  "alignment": "unique" if len(candidates) == 1 else "missing" if not candidates else "ambiguous_multiple_xml_records",
                  "checks": [], "format_differences": []}
        rows.append(result)
        if len(candidates) != 1:
            result["checks"].append({"field": "evidence_identity_alignment", "status": "unresolved",
                                      "mitab": primary_ids, "xml": candidates})
            continue
        index = candidates[0]; matched_xml[index] += 1
        xml = xml_records[index]["evidence"]
        result["xml_evidence_sequence"] = xml_records[index]["evidence_sequence"]
        def compare(name, expected, observed, unresolved=False):
            result["checks"].append({"field": name, "status": "unresolved" if unresolved else "equal" if expected == observed else "different", "mitab": deepcopy(expected), "xml": deepcopy(observed)})
        expected_ids = set(identity_pairs(values(mitab, "evidence_ids")))
        observed_ids = xml_evidence_ids(xml)
        compare("evidence_identity_aliases", sorted(expected_ids), sorted(observed_ids))
        experiments = xml.get("experiments") or []
        compare("publication_pmids", sorted({x.get("id") for x in values(mitab, "publication_ids") if xref_tuple(x)[0] == "pubmed"}), sorted({(exp.get("publication") or {}).get("pubmed_id") for exp in experiments}, key=str))
        compare("detection_method_ids", ids(values(mitab, "detection_methods")), ids([exp.get("detection_method") or {} for exp in experiments]))
        compare("interaction_type_ids", ids(values(mitab, "interaction_types")), ids(xml.get("interaction_types") or []))
        compare("negative_reader_value", mitab.get("interaction", {}).get("negative"), xml.get("negative"))
        compare("host_taxids", sorted({x.get("taxid") for x in values(mitab, "host_taxa")}, key=str), sorted({host.get("taxid") for exp in experiments for host in exp.get("host_organisms") or []}, key=str))
        expected_labels = sorted({label for host in values(mitab, "host_taxa") for label in (host.get("scientific_name"), host.get("common_name")) if label})
        observed_labels = sorted({label for exp in experiments for host in exp.get("host_organisms") or [] for label in (host.get("scientific_name"), host.get("common_name")) if label})
        compare("host_source_labels", expected_labels, observed_labels)
        if len(experiments) != 1:
            result["format_differences"].append("xml_experiment_count_" + str(len(experiments)) + "; no first-experiment collapse")
        participants = xml.get("participants") or []
        if len(participants) != 2:
            result["format_differences"].append("xml_participant_count_" + str(len(participants)) + "; no binary expansion invented")
        primary_by_side = {side: identity_pairs(values(mitab, "primary_ids_" + side)) for side in ("a", "b")}
        duplicate_identity = primary_by_side["a"] == primary_by_side["b"]
        used = []
        for side in ("a", "b"):
            expected_primary = primary_by_side[side]
            matches, actual_identities = [], {}
            for number, participant in enumerate(participants):
                databases = {db for db, _ in expected_primary}
                typed_identity = [x for x in references(participant.get("interactor") or {})
                                  if term_id(x.get("qualifier")) == "MI:0356"
                                  and xref_tuple(x)[0] in databases]
                actual_identities[number] = identity_pairs(typed_identity)
                if actual_identities[number] == expected_primary:
                    matches.append(number)
            unresolved = duplicate_identity or len(matches) != 1
            compare("participant_" + side.upper() + ".typed_identity", expected_primary,
                    [actual_identities[n] for n in matches] if unresolved else actual_identities[matches[0]], unresolved)
            if unresolved:
                result["checks"][-1]["status"] = "unresolved"
                result["format_differences"].append("participant_" + side.upper() + "_identity_alignment_unresolved")
                continue
            n = matches[0]; used.append(n); participant = participants[n]; interactor = participant.get("interactor") or {}
            result.setdefault("participant_alignment", []).append({"mitab_side": side.upper(), "xml_source_index": participant.get("source_index"), "xml_id": participant.get("xml_id")})
            compare("participant_" + side.upper() + ".taxids", sorted({x.get("taxid") for x in values(mitab, "taxa_" + side)}, key=str), [(interactor.get("organism") or {}).get("taxid")])
            compare("participant_" + side.upper() + ".type_ids", ids(values(mitab, "interactor_types_" + side)), [term_id(interactor.get("type"))])
            compare("participant_" + side.upper() + ".biological_role_ids", ids(values(mitab, "biological_roles_" + side)), [term_id(participant.get("biological_role"))])
            compare("participant_" + side.upper() + ".experimental_role_ids", ids(values(mitab, "experimental_roles_" + side)), ids([role.get("term") or {} for role in participant.get("experimental_roles") or []]))
        if len(used) == 2 and len(set(used)) != 2:
            result["format_differences"].append("participant_alignment_not_bijective")
        result["format_differences"].extend(["Negative comparison is reader-value parity; explicit/default XML markup provenance is not inferred.", "MITAB expansion annotation remains separately preserved; absent annotation does not establish binary origin."])
    one_to_one = (len(rows) == len(xml_records) and all(row["alignment"] == "unique" for row in rows)
                  and all(matched_xml[i] == 1 for i in range(len(xml_records))))
    return {"publication_id": pmid, "original_evidence_rows": len(original),
            "original_eligible_rows": sum(item["ledger"]["eligible"] for item in original),
            "xml_evidence_records": len(xml_records), "exact_evidence_id_bijection": one_to_one,
            "unmatched_xml_sequences": [xml_records[i]["evidence_sequence"] for i in range(len(xml_records)) if not matched_xml[i]],
            "multiple_mitab_rows_per_xml_record": [{"xml_sequence": xml_records[i]["evidence_sequence"], "mitab_rows": count} for i, count in matched_xml.items() if count != 1],
            "critical_unassessed_rows": sum(row["alignment"] != "unique" for row in rows),
            "rows": rows, "critical_field_counts": dict(Counter(check["status"] for row in rows for check in row["checks"])),
            "study_independence": "not_determined", "study_reuse": "not_determined"}


def inspect(pre_access, pre_access_sha256, output):
    receipt = verify_preaccess(pre_access, pre_access_sha256)
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    (output / "pre_access.json").write_bytes(Path(pre_access).read_bytes())
    report = {"format": FORMAT, "phase": "development_inspection", "created_at": utcnow(),
              "status": "running", "pre_access_sha256": pre_access_sha256, "contract_sha256": CONTRACT_SHA,
              "selected_xml_bodies_accessed": [], "reserved_bodies_accessed": False, "studies": [],
              "scope": "Development-only provenance/context parity; no reserved, study-independence, full-format-losslessness or biological-accuracy result."}
    save_new(output / "execution_started.json", report)
    runtime = receipt["runtime_bindings"]
    classpath = os.pathsep.join([runtime["classes_directory"], *[x["path"] for x in runtime["dependency_jars"]]])
    provenance = []
    try:
        originals, ledger, _ = load_reference(INSPECTION)
        for selected in receipt["allowlist"]:
            verify_preaccess(pre_access, pre_access_sha256)
            pmid, url = selected["publication_id"], selected["url"]
            report["selected_xml_bodies_accessed"].append(pmid)
            http = fetch_exact(pmid, url, output)
            source = output / (pmid + ".xml")
            save_new(output / (pmid + "_exposure_started.json"), {"publication_id": pmid, "started_at": utcnow(), "source_sha256": http["sha256"], "source_bytes": http["bytes"], "status": "consumed_even_if_parser_fails", "pre_access_sha256": pre_access_sha256})
            verify_preaccess(pre_access, pre_access_sha256)
            verify_source_bytes(source, http)
            stdout, stderr = output / (pmid + "_reader.jsonl"), output / (pmid + "_reader.stderr")
            try:
                result = subprocess.run([runtime["java"]["executable"], "-cp", classpath, "org.biograph.IntactXmlReader", str(source)], capture_output=True, timeout=120, check=False)
            except subprocess.TimeoutExpired as error:
                stdout.write_bytes(error.stdout or b""); stderr.write_bytes(error.stderr or b"")
                raise ValueError("Official XML reader timed out; study consumed; partial streams preserved: " + pmid)
            stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
            verify_source_bytes(source, http)
            records, summary, _ = parse_transport(result.stdout)
            verify_source_bytes(source, http)
            if summary.get("input_sha256") != http["sha256"] or summary.get("input_bytes") != http["bytes"]:
                raise ValueError("Official XML reader source digest differs from retained opaque bytes.")
            gate = assess_development_xml(summary, records, result.returncode)
            study = {"publication_id": pmid, "http_receipt_sha256": sha(output / (pmid + "_http_receipt.json")), "source_sha256": sha(source), "reader_sha256": sha(stdout), "stderr_sha256": sha(stderr), "reader_gate": gate, "reader_summary": summary}
            report["studies"].append(study)
            if gate["quarantined"]:
                raise ValueError("Official XML reader failed or emitted invalid diagnostic; preserve this study without replacement: " + pmid)
            study["parity"] = compare_study(pmid, originals, records)
            provenance.extend(provenance_record(pmid, row) for row in records)
        verify_preaccess(pre_access, pre_access_sha256)
        with (output / "qualified_provenance.jsonl").open("x", encoding="utf-8") as stream:
            for row in provenance:
                stream.write(json.dumps(row, ensure_ascii=True) + "\n")
        parity = [study["parity"] for study in report["studies"]]
        report["original_denominators"] = {"physical_rows": len(ledger), "evidence_rows": sum(p["original_evidence_rows"] for p in parity), "eligible_rows": sum(p["original_eligible_rows"] for p in parity)}
        report["exact_evidence_id_bijection"] = all(p["exact_evidence_id_bijection"] for p in parity)
        report["critical_field_counts"] = dict(sum((Counter(p["critical_field_counts"]) for p in parity), Counter()))
        report["status"] = "inspection_completed_differences_reported"
        report["provenance_audit_conclusion"] = "Qualified source records available for review; study reuse and independence remain not_determined. No reserved assessment was performed."
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, subprocess.SubprocessError) as error:
        report["status"] = "failed"; report["error"] = str(error)
    report["content_sha256"] = digest(report)
    save_new(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Freeze controls/code/runtime before any selected XML request.")
    prep.add_argument("--classes", type=Path, default=ROOT / "tools/intact_xml_reader/target/classes")
    prep.add_argument("--classpath-file", type=Path, required=True)
    prep.add_argument("--controls-report", type=Path, required=True)
    prep.add_argument("--java", default="java")
    prep.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("inspect", help="Make only the four frozen development requests and report parity.")
    run.add_argument("--pre-access", type=Path, required=True)
    run.add_argument("--pre-access-sha256", required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.classes, args.classpath_file, args.controls_report, args.output, args.java) if args.command == "prepare" else inspect(args.pre_access, args.pre_access_sha256, args.output)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps({"phase": result["phase"], "status": result.get("status", "prepared_no_selected_access"), "output": str(args.output), "pre_access_sha256": sha(args.output / "pre_access.json")}))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
