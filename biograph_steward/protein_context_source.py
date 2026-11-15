"""Bounded, current-sequence source capture; no graph edits or scan submission.

The hosted InterPro MCP flow and its unchanged Apache-2.0 JSON/SSE parser
are reused. The recording transport retains evidence that the author's small
call_tool convenience function discards (raw RPC, HTTP status and isError).
Only sequence MD5 lookup is allowed; raw sequences are never sent to InterPro.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import client as client_module
from .client import ENDPOINT, PharosClient, digest, utcnow, write_json
from .file_utils import sha
from .graph import UNIPROT
from ._vendor.interpro_mcp import mcp_client

FORMAT = "biograph-steward.protein-context.v1"
INDEX_FORMAT = "biograph-steward.protein-context-index.v1"
MCP_URL = "https://www.ebi.ac.uk/interpro/mcp"
INFO_URL = "https://www.ebi.ac.uk/interpro/matches/api/info"
ENTRY_URL = "https://www.ebi.ac.uk/interpro/api/entry/interpro/{}/?format=json"
ENTRY = re.compile(r"^IPR[0-9]{6}$")
OFFICIAL_COMMIT = "ceb9b2177a5f8861634972fb8b2eacff64702890"
OFFICIAL_CLIENT_SHA256 = "ff14966eb5ceecbc5de15e68097a909c1faccb464f8c8ecadcedc447a1cac95d"
MD5 = re.compile(r"^[0-9A-Fa-f]{32}$")
ORDINARY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
INFO_FIELDS = ("api", "release", "release_date", "analyses")
FIELDS = '''uniprot sym name fam description seq dataSources
sequence_annotations { startResidue endResidue type name }
interpro: xrefs(source:"InterPro") { source name value }
pfam: xrefs(source:"Pfam") { source name value }
prosite: xrefs(source:"PROSITE") { source name value }
smart: xrefs(source:"SMART") { source name value }
panther: xrefs(source:"PANTHER") { source name value }'''
QUERY = ('query ProteinSequenceContext($id:String!) { dbVersion '
         'source_licenses: dataSourceCounts { dataSource url license licenseURL } '
         'target(q:{uniprot:$id}) { ' + FIELDS + ' } }')
DATA_TERMS = '''# Source context: attribution and data terms

This packet contains current public source context, not independently verified
biological truth. It is separate from historical Pharos graph records.

Pharos: NIH NCATS, https://pharos.nih.gov/ ; API endpoint, retrieval dates,
native database release and source-license fields are retained in each envelope.
Pharos aggregates sources with distinct terms; no blanket software license is
asserted for the complete Pharos response. Review original-owner terms before
redistributing this mixed-source packet.

UniProt Consortium (EMBL-EBI, SIB and PIR): copyrightable database parts are
CC BY 4.0, https://ftp.uniprot.org/pub/databases/uniprot/README . Sequences here
are obtained via Pharos; accession, exact sequence hash and retrieval time are
retained. The source does not supply a UniProt sequence-version or isoform proof.

InterPro / EMBL-EBI and named member databases: use is subject to EMBL-EBI
Terms of Use, https://www.ebi.ac.uk/about/terms-of-use/ , and original-owner
terms. InterPro's published data license covers downloadable InterPro, Pfam,
PRINTS and SFLD data under CC0 1.0:
https://interpro-documentation.readthedocs.io/en/latest/license.html . Included
tools/signature collections can have other terms; do not apply that grant to
every field of a complete heterogeneous Matches
response. Preserve source, signature-library release, provenance and attribution.

The included client SOFTWARE is Apache-2.0 (InterPro MCP contributors); BioGraph
Steward software is MIT. Neither software license licenses these source data.
'''


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def normalize_sequence(value):
    """Remove whitespace and uppercase only; missing stays unknown, not negative."""
    if value is None:
        return None
    _need(isinstance(value, str), "Source sequence must be a string or null.")
    value = "".join(value.split()).upper()
    if not value:
        return None
    _need(re.fullmatch(r"[A-Z]+", value), "Source sequence contains non-letter residues; no substitution made.")
    return value


def _json(text):
    def nonfinite(value):
        raise ValueError("Nonfinite JSON values are not native source data.")
    return json.loads(text, parse_constant=nonfinite)


def _span(row, message):
    _need(isinstance(row, dict) and type(row.get("start")) is int
          and type(row.get("end")) is int and 1 <= row["start"] <= row["end"], message)


def _match(row):
    """Check the documented Matches 0.6 shape without deleting future fields."""
    _need(isinstance(row, dict), "Native match must be an object.")
    sig = row.get("signature")
    _need(isinstance(sig, dict) and isinstance(sig.get("accession"), str)
          and bool(sig["accession"]), "Missing native signature accession.")
    library = sig.get("signatureLibraryRelease")
    _need(isinstance(library, dict) and all(isinstance(library.get(k), str)
          and library[k] for k in ("library", "version")), "Missing native library release.")
    _need(isinstance(row.get("source"), str) and row["source"], "Missing native method source.")
    _need("entry" in sig and (sig["entry"] is None or isinstance(sig["entry"], dict)),
          "Native integrated entry must be an object or explicit null.")
    if sig["entry"] is not None:
        _need(all(isinstance(sig["entry"].get(k), str) for k in
                  ("accession", "name", "description", "type")), "Malformed integrated entry.")
    _need(isinstance(row.get("locations"), list), "Native match locations must be a list.")
    for loc in row["locations"]:
        _span(loc, "Invalid native match coordinates.")
        _need(isinstance(loc.get("location-fragments"), list), "Missing native location fragments.")
        for fragment in loc["location-fragments"]:
            _span(fragment, "Invalid native fragment coordinates.")
            _need(isinstance(fragment.get("dc-status"), str), "Missing native discontinuity status.")
        if loc.get("sites") is not None:
            _need(isinstance(loc["sites"], list), "Invalid native sites.")
            for site in loc["sites"]:
                _need(isinstance(site, dict) and type(site.get("numLocations")) is int
                      and site["numLocations"] >= 0 and isinstance(site.get("siteLocations"), list),
                      "Invalid native site locations.")
                for position in site["siteLocations"]:
                    _span(position, "Invalid native site coordinates.")
                    _need(isinstance(position.get("residue"), str), "Missing native site residue.")
    # Keep nulls and optional score fields; nonfinite numbers cannot be displayed
    # as ordinary measurements, and canonical receipts cannot represent them.
    def finite(value):
        if isinstance(value, float):
            _need(math.isfinite(value), "Nonfinite native measurement.")
        elif isinstance(value, dict):
            for item in value.values():
                finite(item)
        elif isinstance(value, list):
            for item in value:
                finite(item)
    finite(row)


def parse_match_rpc(rpc, expected_md5s=None):
    """Return preserved native BatchResult rows keyed by canonical MD5.

    A failed/missing lookup is never converted into found-with-zero-matches.
    This helper is pure and is reused by the offline verified packet reader.
    """
    _need(isinstance(rpc, dict) and rpc.get("jsonrpc") == "2.0" and "error" not in rpc,
          "InterPro returned a JSON-RPC failure or invalid envelope.")
    result = rpc.get("result")
    _need(isinstance(result, dict) and result.get("isError") is False,
          "InterPro tool failed or did not explicitly report isError=false.")
    content = result.get("content")
    _need(isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict)
          and content[0].get("type") == "text" and isinstance(content[0].get("text"), str),
          "Expected exactly one native text JSON result.")
    payload = _json(content[0]["text"])
    _need(isinstance(payload, dict) and isinstance(payload.get("results"), list),
          "Expected native Matches BatchResponse results.")
    rows = {}
    for row in payload["results"]:
        _need(isinstance(row, dict) and isinstance(row.get("md5"), str)
              and MD5.fullmatch(row["md5"]) and type(row.get("found")) is bool
              and isinstance(row.get("matches"), list), "Malformed native MD5 result.")
        key = row["md5"].upper()
        _need(key not in rows, "Duplicate native MD5 result.")
        _need(row["found"] or not row["matches"], "Not-found MD5 cannot contain matches.")
        for match in row["matches"]:
            _match(match)
        rows[key] = deepcopy(row)
    if expected_md5s is not None:
        expected = list(expected_md5s)
        _need(all(isinstance(x, str) and MD5.fullmatch(x) for x in expected)
              and len(set(x.upper() for x in expected)) == len(expected), "Invalid expected MD5 set.")
        _need(set(rows) == {x.upper() for x in expected}, "Missing or unrequested native MD5 result.")
    return rows


def _http(url, payload=None):
    _need(url in {MCP_URL, INFO_URL} or re.fullmatch(
        r"https://www\.ebi\.ac\.uk/interpro/api/entry/interpro/IPR[0-9]{6}/\?format=json", url),
        "Only qualified official read endpoints are allowed.")
    body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    headers = {"User-Agent": "BioGraph-Steward/0.1 (sequence-MD5-context)",
               "Accept": "application/json, text/event-stream"}
    if body is not None:
        headers.update({"Content-Type": "application/json", "MCP-Protocol-Version": "2025-03-26"})
    request = Request(url, data=body, method="GET" if body is None else "POST", headers=headers)
    try:
        response = urlopen(request, timeout=60)
    except HTTPError as exc:
        return exc.code, {}, exc.read(25_000_001)
    with response:
        _need(response.geturl() == url, "Official source redirected; no context packet produced.")
        return response.status, {k: response.headers[k] for k in
            ("Content-Type", "Date", "ETag", "Last-Modified", "Retry-After") if k in response.headers}, response.read(25_000_001)


def _output(output, runs_dir):
    runs_dir, output = Path(runs_dir).absolute(), Path(output).absolute()
    _need(not runs_dir.is_symlink() and runs_dir.resolve() == runs_dir
          and output.parent == runs_dir and ORDINARY.fullmatch(output.name)
          and output.name not in {".", ".."} and not output.exists() and not output.is_symlink(),
          "Choose a new ordinary direct child of the runs directory.")
    output.mkdir(parents=True)
    return output


def _info(value):
    _need(isinstance(value, dict) and all(k in value for k in INFO_FIELDS)
          and all(isinstance(value[k], str) and value[k] for k in INFO_FIELDS[:3])
          and isinstance(value["analyses"], list), "Matches release metadata is incomplete.")
    return {k: value[k] for k in INFO_FIELDS}


def _tool(tools):
    _need(isinstance(tools, dict) and tools.get("jsonrpc") == "2.0" and "error" not in tools
          and isinstance(tools.get("result"), dict)
          and isinstance(tools["result"].get("tools"), list), "Invalid tools/list response.")
    selected = [row for row in tools["result"]["tools"] if isinstance(row, dict) and row.get("name") == "matchSequences"]
    _need(len(selected) == 1, "Native matchSequences tool is unavailable or duplicated.")
    schema = selected[0].get("inputSchema", {})
    _need(schema.get("type") == "object" and schema.get("required") == ["sequencesOrMd5s"]
          and schema.get("properties", {}).get("sequencesOrMd5s", {}).get("type") == "string",
          "Native matchSequences input contract changed.")
    return selected[0]


def register_context(folder, runs_dir="runs"):
    """Register an explicitly captured packet first; never auto-select by scores."""
    folder, runs_dir = Path(folder).absolute(), Path(runs_dir).absolute()
    _need(folder.parent == runs_dir and not folder.is_symlink() and ORDINARY.fullmatch(folder.name),
          "Register only an ordinary direct runs child.")
    manifest_path = folder / "protein_context.json"
    _need(manifest_path.is_file() and not manifest_path.is_symlink(), "A complete source manifest is required.")
    manifest = _json(manifest_path.read_text())
    _need(manifest.get("format") == FORMAT and manifest.get("content_sha256") ==
          digest({k: v for k, v in manifest.items() if k != "content_sha256"}), "Invalid complete source manifest.")
    for name, metadata in manifest.get("files", {}).items():
        path = folder / name
        _need(isinstance(name, str) and not Path(name).is_absolute() and ".." not in Path(name).parts
              and path.is_file() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents if p != folder.parent)
              and metadata == {"sha256": sha(path), "bytes": path.stat().st_size},
              "A source packet file changed before registration.")
    index_path = runs_dir / "protein_context_index.json"
    _need(not index_path.is_symlink(), "Index must be an ordinary file.")
    index = _json(index_path.read_text()) if index_path.exists() else {"format": INDEX_FORMAT, "contexts": []}
    _need(isinstance(index, dict) and index.get("format") == INDEX_FORMAT and isinstance(index.get("contexts"), list),
          "Invalid existing context index; it was not replaced.")
    for row in index["contexts"]:
        _need(isinstance(row, dict) and set(row) == {"id", "manifest_sha256"}
              and isinstance(row["id"], str) and ORDINARY.fullmatch(row["id"])
              and row["id"] not in {".", ".."} and isinstance(row["manifest_sha256"], str)
              and re.fullmatch(r"[0-9a-f]{64}", row["manifest_sha256"]), "Invalid existing context registration.")
    entry = {"id": folder.name, "manifest_sha256": sha(manifest_path)}
    write_json(index_path, {"format": INDEX_FORMAT,
        "contexts": [entry] + [r for r in index["contexts"] if r["id"] != folder.name]})
    return entry


def capture_context(proteins, output, *, runs_dir="runs", client=None, http_transport=None, register=False, entries=()):
    """Capture at most 100 exact proteins into a new immutable ignored packet.

    Test transports obey the same native wire contracts. A failed acquisition
    leaves raw received material and failure.json, never a usable manifest.
    """
    ids = []
    for protein in proteins:
        _need(isinstance(protein, str), "Use exact UniProt identifiers.")
        accession = protein[10:] if protein.startswith("UniProtKB:") else protein
        _need(UNIPROT.fullmatch(accession), "Use exact UniProt identifiers, preserving any isoform suffix.")
        _need(accession not in ids, "Duplicate requested protein.")
        ids.append(accession)
    _need(1 <= len(ids) <= 100, "Request between 1 and 100 exact proteins.")
    entries = list(entries)
    _need(len(entries) <= 100 and len(set(entries)) == len(entries)
          and all(isinstance(x, str) and ENTRY.fullmatch(x) for x in entries),
          "Select at most 100 distinct exact InterPro entry identifiers.")
    _need(sha(mcp_client.__file__) == OFFICIAL_CLIENT_SHA256, "The unchanged official parser source pin failed.")
    client = client or PharosClient(cache_dir=None, retries=0, refresh=True)
    _need(client.endpoint == ENDPOINT and not client.records and client.cache_dir is None,
          "Use a fresh uncached client at the official Pharos endpoint.")
    folder = _output(output, runs_dir)
    requests = []
    http_transport = http_transport or _http

    def request(url, file, payload=None, *, rpc=False, entry=None):
        started = utcnow()
        row = {"provider": "InterPro", "url": url, "method": "GET" if payload is None else "POST",
               "started_at": started, "request": payload, "http_status": None}
        requests.append(row)
        try:
            status, headers, raw = http_transport(url, payload)
        except Exception as exc:
            row.update(completed_at=utcnow(), error_type=type(exc).__name__, outcome="transport_failed")
            raise
        _need(isinstance(raw, bytes), "Source transport must preserve literal bytes.")
        raw_file = file.rsplit(".", 1)[0] + ".raw"
        path = folder / raw_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(completed_at=utcnow(), http_status=status, raw_file=raw_file, body_sha256=sha(path),
               http_headers={k: v for k, v in headers.items() if k in
                  {"Content-Type", "Date", "ETag", "Last-Modified", "Retry-After"}})
        allowed = ({200, 410} if entry is not None else {200, 202}
                   if payload and payload.get("method") == "notifications/initialized" else {200})
        _need(status in allowed and len(raw) <= 25_000_000, "Official lookup failed or exceeded its bounded response size.")
        if not raw and status == 202:
            return None
        value = mcp_client._parse_jsonrpc(raw.decode("utf-8")) if rpc else _json(raw)
        if rpc and payload is not None and "id" in payload:
            _need(value.get("id") == payload["id"], "MCP response identity does not match the recorded request.")
        write_json(folder / file, value)
        row.update(response_file=file, file_sha256=sha(folder / file))
        if entry is not None:
            _need(isinstance(value, dict), "Native entry metadata must be a JSON object.")
            metadata = value.get("metadata") if status == 200 else value
            _need(isinstance(metadata, dict) and isinstance(metadata.get("accession"), str)
                  and metadata["accession"].upper() == entry, "Native entry identity differs from the exact requested entry.")
            if status == 410:
                _need(isinstance(value.get("deletion_date"), str) and value["deletion_date"]
                      and value.get("source_database") == "interpro", "Deleted entry lacks native lifecycle metadata.")
            else:
                for field in ("is_llm", "is_reviewed_llm", "is_updated_llm"):
                    _need(field not in metadata or type(metadata[field]) is bool,
                          "Malformed native editorial-method flag.")
        return value

    try:
        before = request(INFO_URL, "interpro/info_before.json")
        _info(before)
        initialized = request(MCP_URL, "interpro/initialize.json", {"jsonrpc": "2.0", "id": 1,
            "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "BioGraph-Steward-source-capture", "version": "0.1"}}}, rpc=True)
        _need(isinstance(initialized.get("result"), dict) and "error" not in initialized
              and initialized["result"].get("protocolVersion") == "2025-03-26", "Unsupported MCP initialization.")
        request(MCP_URL, "interpro/initialized.json", {"jsonrpc": "2.0", "method": "notifications/initialized"}, rpc=True)
        tools = request(MCP_URL, "interpro/tools.json", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, rpc=True)
        tool = _tool(tools)
        rows, versions = [], set()
        for accession in ids:
            started = utcnow()
            request_row = {"provider": "Pharos", "url": ENDPOINT, "method": "POST", "started_at": started,
                "http_status": None, "http_status_provenance": "not_exposed_by_PharosClient",
                "request": {"query": QUERY, "variables": {"id": accession}}}
            requests.append(request_row)
            try:
                data = client.execute(QUERY, {"id": accession}, cache=False)
            except Exception as exc:
                request_row.update(completed_at=utcnow(), error_type=type(exc).__name__, outcome="request_failed")
                raise
            envelope = deepcopy(client.records[-1])
            file = "pharos/" + accession + ".json"
            write_json(folder / file, envelope)
            request_row.update(completed_at=utcnow(), response_file=file, file_sha256=sha(folder / file),
                               response_sha256=envelope["response_sha256"])
            target = data.get("target")
            _need(isinstance(target, dict) and target.get("uniprot") == accession,
                  "Pharos returned an absent or different exact protein identity.")
            _need(isinstance(data.get("dbVersion"), str) and data["dbVersion"], "Pharos did not report a database version.")
            versions.add(data["dbVersion"])
            sequence = normalize_sequence(target.get("seq"))
            encoded = sequence.encode("ascii") if sequence is not None else None
            rows.append({"protein": "UniProtKB:" + accession, "pharos_file": file,
                "matches_file": "interpro/matches_000.json" if sequence is not None else None,
                "query_md5": hashlib.md5(encoded).hexdigest().upper() if encoded is not None else None,
                "sequence_sha256": hashlib.sha256(encoded).hexdigest() if encoded is not None else None,
                "sequence_length": len(sequence) if sequence is not None else None,
                "status": "sequence_available" if sequence is not None else "sequence_unavailable"})
        _need(len(versions) == 1, "Pharos release changed during source capture.")
        md5s = list(dict.fromkeys(row["query_md5"] for row in rows if row["query_md5"] is not None))
        if md5s:
            rpc = request(MCP_URL, "interpro/matches_000.json", {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "matchSequences", "arguments": {"sequencesOrMd5s": "\n".join(md5s)}}}, rpc=True)
            matches = parse_match_rpc(rpc, md5s)
            for row in rows:
                if row["query_md5"] is None:
                    continue
                for match in matches[row["query_md5"]]["matches"]:
                    for location in match["locations"]:
                        spans = [location] + location["location-fragments"] + [p for s in location.get("sites") or [] for p in s["siteLocations"]]
                        _need(all(p["end"] <= row["sequence_length"] for p in spans), "Native match extends beyond the exact source sequence.")
        entry_files = {}
        for entry in entries:
            entry_files[entry] = "interpro/entries/" + entry + ".json"
            request(ENTRY_URL.format(entry), entry_files[entry], entry=entry)
        after = request(INFO_URL, "interpro/info_after.json")
        _need(_info(before) == _info(after), "Matches API/library release changed during source capture.")
        write_json(folder / "source_requests.json", {"requests": requests})
        (folder / "DATA_TERMS.md").write_text(DATA_TERMS, encoding="utf-8")
        files = {str(path.relative_to(folder)): {"sha256": sha(path), "bytes": path.stat().st_size}
                 for path in sorted(folder.rglob("*")) if path.is_file()}
        manifest = {"format": FORMAT, "created_at": utcnow(), "proteins": rows, "files": files,
            "entry_files": entry_files,
            "info_before_file": "interpro/info_before.json", "info_after_file": "interpro/info_after.json",
            "tools_file": "interpro/tools.json", "requests_file": "source_requests.json", "tool_name": "matchSequences",
            "tool_schema_sha256": digest(tool), "source_code": {"official_mcp_commit": OFFICIAL_COMMIT,
            "official_client_sha256": sha(mcp_client.__file__), "producer_sha256": sha(__file__),
            "pharos_client_sha256": sha(client_module.__file__)}, "attribution": {
            "pharos": "NIH NCATS; original-owner terms in native source_licenses",
            "sequence": "UniProt Consortium via Pharos; CC BY 4.0 copyrightable parts",
            "interpro": "InterPro / EMBL-EBI and named member databases; original-owner terms",
            "data_terms_file": "DATA_TERMS.md"}, "source_scope": "current_retrieved_sequence_context",
            "sequence_normalization": "whitespace removed, uppercase only; no residue substitutions",
            "app_or_graph_changed": False, "scientific_accuracy_assessed": False,
            "historical_pharos_record_identity_established": False, "model_calls": 0}
        manifest["content_sha256"] = digest(manifest)
        write_json(folder / "protein_context.json", manifest)
    except Exception as exc:
        write_json(folder / "source_requests.json", {"requests": requests})
        write_json(folder / "failure.json", {"format": FORMAT, "created_at": utcnow(), "status": "failed",
            "error_type": type(exc).__name__, "error": str(exc), "app_or_graph_changed": False,
            "model_calls": 0, "biological_negative_inferred": False})
        raise
    if register:
        register_context(folder, runs_dir)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protein", action="append", required=True, help="Exact UniProt accession; repeat up to 100 times")
    parser.add_argument("--output", type=Path, required=True, help="New direct child of runs/")
    parser.add_argument("--register", action="store_true", help="Explicitly make this pinned packet first in the local index")
    parser.add_argument("--entry", action="append", default=[], help="Optional exact IPR accession for native entry lifecycle/editorial metadata")
    args = parser.parse_args(argv)
    manifest = capture_context(args.protein, args.output, register=args.register, entries=args.entry)
    print(json.dumps({"output": str(args.output), "proteins": len(manifest["proteins"]),
                      "manifest_sha256": sha(args.output / "protein_context.json"), "registered": args.register}))


if __name__ == "__main__":
    main()
