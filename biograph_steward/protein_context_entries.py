"""Append explicitly selected native InterPro entry metadata to a verified packet.

The existing immutable publication pattern is reused: verify the parent, copy
its original bytes, preserve its manifest, add separate source files and replay
the existing reader before registration. No protein or MD5 lookup is repeated.
The pinned upstream MCP getEntry implementation turns HTTP 410 into a truncated tool error; the
already qualified REST transport is used to retain the complete deletion body.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from .client import digest, utcnow, write_json
from .file_utils import sha
from .protein_context import MANIFEST, load_publication
from . import protein_context_source as source


def _inventory(folder):
    return {p.relative_to(folder).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in sorted(folder.rglob("*")) if p.is_file() and p.relative_to(folder).as_posix() != MANIFEST}


def extend_entries(parent, expected_manifest_sha256, entries, output, *, runs_dir="runs",
                   http_transport=None, register=False):
    """Copy a pinned source packet and add only explicit, separately dated entries."""
    parent = Path(parent).absolute()
    packet = load_publication(parent, expected_manifest_sha256)
    original = packet["manifest"]
    entries = list(entries)
    source._need(1 <= len(entries) <= 100 and all(isinstance(x, str) and source.ENTRY.fullmatch(x) for x in entries)
                 and len(set(entries)) == len(entries), "Select between 1 and 100 distinct exact InterPro entries.")
    existing = original.get("entry_files", {})
    existing_unavailable = original.get("entry_unavailable", {})
    source._need(len(set(entries) | set(existing) | set(existing_unavailable)) <= 100,
                 "Entry extension cannot exceed the 100-entry bound.")
    before = {name: pin["sha256"] for name, pin in original["files"].items()}
    before[MANIFEST] = expected_manifest_sha256
    parent_file = "source_parent/" + expected_manifest_sha256 + "/" + MANIFEST
    prefix = "entry_extension/" + expected_manifest_sha256
    requests_file = prefix + "/source_requests.json"
    source._need(parent_file not in original["files"] and requests_file not in original["files"],
                 "Entry extension would overwrite a preserved parent source file.")
    transport = http_transport or source._http
    requests = deepcopy(json.loads((parent / original["requests_file"]).read_text()))
    entry_files = deepcopy(existing)
    entry_unavailable = deepcopy(existing_unavailable)
    started = utcnow()
    folder = source._output(output, runs_dir)
    try:
        for name, pin in original["files"].items():
            destination = folder / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((parent / name).read_bytes())
            source._need(sha(destination) == pin["sha256"], "Parent source changed while copying.")
        path = folder / parent_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((parent / MANIFEST).read_bytes())
        source._need(sha(path) == expected_manifest_sha256, "Parent manifest changed while copying.")
        for entry in entries:
            relative = prefix + "/entries/" + entry + ".json"
            raw_file = relative[:-5] + ".raw"
            source._need(relative not in original["files"] and raw_file not in original["files"],
                         "Entry extension would overwrite original source bytes.")
            row = {"provider": "InterPro", "url": source.ENTRY_URL.format(entry), "method": "GET",
                   "started_at": utcnow(), "http_status": None, "request": None}
            requests["requests"].append(row)
            try:
                status, headers, raw = transport(row["url"], None)
            except Exception as exc:
                row.update(completed_at=utcnow(), error_type=type(exc).__name__, outcome="transport_failed")
                raise
            source._need(isinstance(raw, bytes), "Entry transport must preserve literal source bytes.")
            path = folder / raw_file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            row.update(completed_at=utcnow(), http_status=status, raw_file=raw_file, body_sha256=sha(path),
                       http_headers={k: v for k, v in headers.items() if k in
                                     {"Content-Type", "Date", "ETag", "Last-Modified", "Retry-After"}})
            source._need(type(status) is int and status in (200, 204, 410) and len(raw) <= 25_000_000,
                         "Native entry lookup failed or exceeded its bounded response size.")
            if status == 204:
                source.parse_entry_response(raw, status, entry)
                entry_files.pop(entry, None)
                entry_unavailable[entry] = raw_file
                continue
            body = source._json(raw)
            write_json(folder / relative, body)
            row.update(response_file=relative, file_sha256=sha(folder / relative))
            source.parse_entry_response(raw, status, entry)
            entry_files[entry] = relative
            entry_unavailable.pop(entry, None)
        write_json(folder / requests_file, requests)
        # The original ledger and every source body stay byte-identical. The
        # new manifest points to an appended ledger at a separate relative path.
        for name, pin in before.items():
            source._need(sha(parent / name) == pin, "Parent source changed during entry lookup.")
        child = deepcopy(original)
        child.update(created_at=utcnow(), entry_files=entry_files, entry_unavailable=entry_unavailable, requests_file=requests_file,
            derived_from={"manifest_file": parent_file, "manifest_sha256": expected_manifest_sha256,
                "manifest_content_sha256": original["content_sha256"], "created_at": original["created_at"],
                "source_files_layout": "Original relative paths retained at packet root."},
            entry_extension={"started_at": started, "completed_at": utcnow(), "requested_entries": entries,
                "producer_sha256": sha(__file__), "transport_sha256": sha(source.__file__),
                "new_pharos_requests": 0, "new_mcp_requests": 0, "new_model_calls": 0,
                "matches_info_scope": "Original Matches lookup only; not the release of this separately dated entry API lookup.",
                "automatic_identifier_remaps": 0})
        child["files"] = _inventory(folder)
        child.pop("content_sha256", None)
        child["content_sha256"] = digest(child)
        write_json(folder / MANIFEST, child)
        load_publication(folder, sha(folder / MANIFEST))
        if register:
            source.register_context(folder, runs_dir)
        return child
    except Exception as exc:
        write_json(folder / requests_file, requests)
        if (folder / MANIFEST).exists():
            (folder / MANIFEST).rename(folder / "unadmitted_protein_context.json")
        write_json(folder / "failure.json", {"format": source.FORMAT, "created_at": utcnow(),
            "status": "failed_entry_extension", "parent_manifest_sha256": expected_manifest_sha256,
            "error_type": type(exc).__name__, "error": str(exc), "model_calls": 0,
            "new_pharos_requests": 0, "new_mcp_requests": 0, "graph_changed": False,
            "biological_negative_inferred": False})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True, help="Existing verified source packet")
    parser.add_argument("--parent-manifest-sha256", required=True, help="Required exact parent manifest FILE SHA256")
    parser.add_argument("--entry", action="append", required=True, help="Explicit InterPro accession; repeat up to 100 times")
    parser.add_argument("--output", type=Path, required=True, help="New direct child of runs/")
    parser.add_argument("--register", action="store_true", help="Register only after the existing reader verifies the child")
    args = parser.parse_args(argv)
    value = extend_entries(args.parent, args.parent_manifest_sha256, args.entry, args.output, register=args.register)
    print(json.dumps({"output": str(args.output), "manifest_sha256": sha(args.output / MANIFEST),
                      "entries_added": len(value["entry_extension"]["requested_entries"]), "registered": args.register}))


if __name__ == "__main__":
    main()
