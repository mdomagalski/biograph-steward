#!/usr/bin/env python3
"""Freeze a metadata-selected IntAct panel and save opaque, bounded source bytes.

This preparation tool never decodes MITAB, extracts reference labels, invokes a
model, builds a graph or scores fidelity. Use the official JAMI evidence reader
for the separate, not-yet-implemented parsing increment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import sha

FORMAT = "biograph-steward.intact-fidelity-preparation.v1"
BASE = "https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psimitab/pmid/2025/"
SALT = "biograph-intact-fidelity-v1\n"
MAX_BYTES = 65536
COUNT = 8
ROW = re.compile(
    r'href="([0-9]+\.txt)".*?align="right">\s*([0-9-]+ [0-9:]+)\s*</td>'
    r'<td align="right">\s*([0-9.]+)([KM]?)\s*</td>', re.S)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Reference retrieval must use the exact frozen official URL.")


def metadata_selection(raw):
    """Parse only the pinned Apache directory's filename/date/size metadata."""
    candidates = []
    seen = set()
    for fragment in raw.decode("utf-8").split("<tr>"):
        match = ROW.search(fragment)
        if not match:
            continue
        name, modified, number, suffix = match.groups()
        if name in seen:
            raise ValueError("Duplicate publication filename in directory metadata.")
        seen.add(name)
        approximate = float(number) * {"": 1, "K": 1024, "M": 1048576}[suffix]
        if 4096 <= approximate <= MAX_BYTES:
            candidates.append({
                "filename": name, "publication_id": "pubmed:" + name[:-4],
                "url": BASE + name, "directory_modified_display": modified,
                "directory_size_display": number + suffix,
                "rank_sha256": hashlib.sha256((SALT + name).encode()).hexdigest(),
            })
    candidates.sort(key=lambda row: (row["rank_sha256"], row["filename"]))
    if len(candidates) < COUNT:
        raise ValueError("Fewer than eight metadata-eligible publications; stop without substitution.")
    selected = candidates[:COUNT]
    for index, row in enumerate(selected):
        row["split"] = "development" if index < 4 else "reserved_final"
    return {"directory_publication_files": len(seen),
            "metadata_eligible_publications": len(candidates), "selected": selected}


def freeze(directory, receipt, protocol, output):
    directory, receipt, protocol, output = map(Path, (directory, receipt, protocol, output))
    if output.exists():
        raise ValueError("Freeze output already exists; preserve it.")
    metadata_receipt = json.loads(receipt.read_text())
    if (metadata_receipt["url"] != BASE or metadata_receipt["sha256"] != sha(directory)
            or metadata_receipt["access_kind"] != "source_code_or_directory_metadata"
            or metadata_receipt["interaction_rows_inspected"] is not False):
        raise ValueError("Directory metadata receipt does not bind the declared release.")
    contract = json.loads(protocol.read_text())
    if (contract["format"] != FORMAT or contract["selection"]["directory"] != BASE
            or contract["selection"]["salt"] != SALT
            or contract["selection"]["publication_count"] != COUNT
            or contract["selection"]["maximum_source_bytes"] != MAX_BYTES):
        raise ValueError("This preparer supports only the fixed v1 contract.")
    result = {"format": FORMAT, "created_at": utcnow(), "status": "frozen_before_source_body_access",
              "protocol": {"path": str(protocol), "sha256": sha(protocol)},
              "preparer": {"path": str(Path(__file__).resolve().relative_to(ROOT)),
                           "sha256": sha(__file__)},
              "directory": {"path": str(directory), "sha256": sha(directory)},
              "directory_receipt": {"path": str(receipt), "sha256": sha(receipt)},
              **metadata_selection(directory.read_bytes()),
              "candidate_rows_decoded": False, "source_bodies_downloaded": False,
              "study_relation_audit": "pending; publication grouping alone is not independence"}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


def verify_freeze(panel_path, expected_sha):
    panel_path = Path(panel_path)
    if sha(panel_path) != expected_sha:
        raise ValueError("Frozen panel SHA-256 mismatch.")
    panel = json.loads(panel_path.read_text())
    if panel["format"] != FORMAT or panel["status"] != "frozen_before_source_body_access":
        raise ValueError("Unsupported preparation receipt.")
    for key in ("protocol", "preparer", "directory", "directory_receipt"):
        if sha(ROOT / panel[key]["path"]) != panel[key]["sha256"]:
            raise ValueError("Frozen input changed: " + key)
    original = metadata_selection((ROOT / panel["directory"]["path"]).read_bytes())
    if any(panel[key] != original[key] for key in original):
        raise ValueError("Panel selection does not replay from frozen directory metadata.")
    return panel


def fetch(panel_path, expected_sha, output):
    panel = verify_freeze(panel_path, expected_sha)
    output = Path(output)
    # Exclusive creation means no retries can silently replace a consumed input.
    output.mkdir(parents=True, exist_ok=False)
    opener = build_opener(HTTPSHandler(), NoRedirect())
    receipt = {"format": FORMAT, "created_at": utcnow(), "panel_sha256": expected_sha,
               "status": "fetching", "sources": [], "candidate_rows_decoded": False,
               "eligibility_audited": False, "reference_labels_materialized": False,
               "fidelity_evaluation_executed": False, "model_calls": 0, "graph_changes": 0}
    try:
        for selected in panel["selected"]:
            url = selected["url"]
            if url != BASE + selected["filename"] or not re.fullmatch(r"[0-9]+\.txt", selected["filename"]):
                raise ValueError("Source URL or filename is outside the frozen official directory.")
            request = Request(url, headers={"Accept": "text/plain", "Accept-Encoding": "identity"})
            with opener.open(request, timeout=30) as response:
                if response.status != 200 or response.geturl() != url:
                    raise ValueError("Unexpected reference HTTP response.")
                raw = response.read(MAX_BYTES + 1)
                if not raw or len(raw) > MAX_BYTES:
                    raise ValueError("Selected artifact violates the frozen nonempty/64 KiB bound.")
                # Bytes stay opaque: no text decoding, line splitting or parser use.
                with (output / selected["filename"]).open("xb") as stream:
                    stream.write(raw)
                receipt["sources"].append({**selected, "retrieved_at": utcnow(),
                    "status": response.status, "headers": dict(response.headers),
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                    "access_kind": "opaque_source_bytes_after_protocol_freeze"})
        receipt["status"] = "source_bytes_pinned_not_parsed"
    except Exception as exc:
        receipt["status"] = "stopped_partial_no_replacement"
        receipt["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        write_json(output / "retrieval_receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("freeze")
    for name in ("directory", "receipt", "protocol", "output"):
        prepare.add_argument("--" + name, required=True)
    download = commands.add_parser("fetch")
    for name in ("panel", "expected-sha256", "output"):
        download.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze(args.directory, args.receipt, args.protocol, args.output)
    else:
        result = fetch(args.panel, args.expected_sha256, args.output)
    print(json.dumps({"status": result["status"],
                      "publications": len(result.get("selected", result.get("sources", []))),
                      "candidate_rows_decoded": False}))


if __name__ == "__main__":
    main()
