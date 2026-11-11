"""Offline adapter for a scoped copy of the official Pharos400 identity/TDL CSV.

The source release uses UniProt as its public identifier, but multiple product
rows can share that identifier. IFX IDs are release-row traceability identifiers,
not a new protein namespace. A grouping anchor is not necessarily canonical.
This adapter preserves these distinctions; it does not map symbols or xrefs,
replace graph relationships, or infer assay/experiment provenance.

Source field meanings: https://opendata.ncats.nih.gov/public/pharos/pharos400_readme.html
The generated endpoints use the existing evidence_mapping producer's narrow
source-primary identity contract, not a second mapping framework.
"""
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import io
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.request

from .graph import UNIPROT


SOURCE_URL = "https://opendata.ncats.nih.gov/public/pharos/pharos400_tdls_full.csv"
SOURCE_VERSION = "pharos400"
FORMAT = "biograph-steward.pharos400-selected-identity-rows.v1"
REQUIRED_FIELDS = ("id", "uniprot_id", "uniprot_isoform", "canonical_isoform_status", "tdl")
GROUP_FIELDS = ("canonical_isoform_status_source", "is_canonical", "protein_group_anchor")
SELECTION_FIELDS = ("uniprot_id", "uniprot_isoform")
MAX_BYTES = 150 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
INTAKE_FILES = {"request_contract.json", "http_receipt.json", "selected_rows.json"}


def _real_ancestors(path):
    absolute = Path(path).absolute()
    if any(p.is_symlink() for p in (absolute, *absolute.parents)):
        raise ValueError("Intake directory and its ancestors must not be symlinks.")
    return absolute


def _write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def capture_intake(requested_accessions, output, opener=None):
    """Capture one official CSV download and retain only exact selected rows.

    ``opener`` may supply an urllib-compatible ``open(request, timeout=...)``
    method for offline tests. The normal opener never follows redirects. There
    is one GET, no retry, a 150 MiB body limit, a 60-second socket timeout and a
    120-second elapsed budget checked between reads. The complete body is hashed
    and scanned from a temporary file, then deleted. Failures retain the contract
    and HTTP/error receipt in their new output directory and raise ValueError.
    Existing output directories are never reused, even after a failed attempt.
    """
    requested = list(_ids(requested_accessions))
    directory = _real_ancestors(output)
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir(exist_ok=False)
    now = lambda: datetime.now(timezone.utc).isoformat()
    contract = {
        "format": "biograph-steward.scoped-source-intake-contract.v1",
        "url": SOURCE_URL, "method": "GET", "source_version": SOURCE_VERSION,
        "source_readme_url": "https://opendata.ncats.nih.gov/public/pharos/pharos400_readme.html",
        "allowed_exact_identifiers": requested, "selection_fields": list(SELECTION_FIELDS),
        "selection": "exact full-string identifier equality only; no suffix stripping or alias/symbol lookup",
        "network": {"timeout_seconds": 60, "wall_time_cap_seconds": 120,
                    "wall_time_budget_checked_between_reads": True,
                    "max_bytes": MAX_BYTES, "retries": 0, "follow_redirects": False},
        "retain": "HTTP headers, body hash/bytes/counts/header, complete selected CSV records and locators only; full download temporary then deleted",
        "out_of_scope": "No unrelated row contents exposed; no papers, interactions, abstracts or held-out records inspected",
        "created_utc": now(),
    }
    _write_json(directory / "request_contract.json", contract)
    receipt = {"request_contract_sha256": hashlib.sha256(
                   (directory / "request_contract.json").read_bytes()).hexdigest(),
               "url": SOURCE_URL, "started_utc": now(), "status": "failed"}
    started, failure = time.monotonic(), None

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        request = urllib.request.Request(
            SOURCE_URL, headers={"Accept": "text/csv", "Accept-Encoding": "identity",
                                 "User-Agent": "BioGraphSteward-scoped-identity-audit/1"}, method="GET")
        service = opener if opener is not None else urllib.request.build_opener(NoRedirect)
        with service.open(request, timeout=60) as response, tempfile.TemporaryFile("w+b") as raw:
            receipt.update(http_status=response.status, http_headers=dict(response.headers.items()),
                           final_url=response.geturl())
            if response.status != 200 or response.geturl() != SOURCE_URL:
                raise ValueError("Unexpected HTTP status or effective source URL.")
            encoding = response.headers.get("Content-Encoding", "identity")
            if encoding.lower() != "identity":
                raise ValueError("Unexpected source content encoding; no implicit decompression.")
            digest, size = hashlib.sha256(), 0
            read = getattr(response, "read1", response.read)
            while True:
                if time.monotonic() - started > 120:
                    raise TimeoutError("Elapsed download budget exceeded.")
                chunk = read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("Official source exceeds the bounded 150 MiB intake limit.")
                digest.update(chunk)
                raw.write(chunk)
            receipt.update(source_bytes=size, source_sha256=digest.hexdigest())
            content_length = response.headers.get("Content-Length")
            if content_length is not None and str(size) != str(content_length):
                raise ValueError("Content-Length differs from the complete received body size.")
            raw.seek(0)
            stream = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            try:
                subset = select_rows(stream, requested, source_sha256=digest.hexdigest(), source_bytes=size)
            finally:
                stream.detach()
            _check_subset(subset)
            _write_json(directory / "selected_rows.json", subset)
            receipt.update(status="complete", csv_header=subset["csv_header"],
                           source_data_row_count=subset["source_data_row_count"],
                           selected_row_count=len(subset["selected_rows"]), selected_ids=requested,
                           selected_rows_sha256=hashlib.sha256(
                               (directory / "selected_rows.json").read_bytes()).hexdigest())
    except Exception as error:
        failure = error
        receipt.update(error_type=type(error).__name__, error=str(error))
        if isinstance(error, urllib.error.HTTPError):
            receipt.update(http_status=error.code, http_headers=dict(error.headers.items()))
    finally:
        receipt.update(finished_utc=now(), elapsed_seconds=round(time.monotonic() - started, 3))
        _write_json(directory / "http_receipt.json", receipt)
    if failure is not None:
        raise ValueError("Pharos400 intake failed; immutable error receipt: "
                         + str(directory / "http_receipt.json")) from failure
    return verify_intake(directory)


def _ids(values):
    if (not isinstance(values, list) or not values
            or any(not isinstance(v, str) or not UNIPROT.fullmatch(v) for v in values)
            or len(set(values)) != len(values)):
        raise ValueError("Requested identifiers must be distinct exact UniProt accessions.")
    return values


def _header(value):
    if (not isinstance(value, list) or not value or len(value) != len(set(value))
            or any(not isinstance(v, str) or not v for v in value)
            or any(v not in value for v in REQUIRED_FIELDS)):
        raise ValueError("Missing, duplicate or invalid source CSV header fields.")


def select_rows(stream, requested_identifiers, *, source_sha256, source_bytes):
    """Select exact source IDs from a complete UTF-8 CSV text stream.

    Hashing/downloads happen outside this offline adapter. The stream must be
    opened with newline='' so selected original CSV records retain line endings.
    Unrelated row contents are neither returned nor interpreted. Only columns
    needed for exact selection are read on unselected rows. No suffix is removed.
    """
    requested = _ids(requested_identifiers)
    if not isinstance(source_sha256, str) or not SHA256.fullmatch(source_sha256):
        raise ValueError("A complete source SHA-256 is required.")
    if type(source_bytes) is not int or not 0 < source_bytes <= MAX_BYTES:
        raise ValueError("Source byte count is outside the bounded intake contract.")

    class Lines:
        def __init__(self):
            self.current = []

        def __iter__(self):
            return self

        def __next__(self):
            line = next(stream)
            self.current.append(line)
            return line

    lines = Lines()
    reader = csv.reader(lines)
    header = next(reader)
    _header(header)
    lines.current = []
    indices = {field: header.index(field) for field in SELECTION_FIELDS}
    selected, total, previous = [], 0, reader.line_num
    for cells in reader:
        total += 1
        if len(cells) != len(header):
            raise ValueError("CSV record width differs from its source header.")
        start, end = previous + 1, reader.line_num
        previous = end
        matches = [{"field": field, "identifier": cells[index]}
                   for field, index in indices.items() if cells[index] in requested]
        if matches:
            selected.append({"logical_data_row": total, "source_csv_row": total + 1,
                             "physical_line_start": start, "physical_line_end": end,
                             "matched_identifiers": matches,
                             "row": dict(zip(header, cells)),
                             "original_csv_record": "".join(lines.current)})
        lines.current = []
    return {"format": FORMAT, "source_url": SOURCE_URL, "source_version": SOURCE_VERSION,
            "source_sha256": source_sha256, "source_bytes": source_bytes,
            "csv_header": header, "requested_identifiers": list(requested),
            "source_data_row_count": total, "selected_rows": selected}


def _check_subset(subset):
    if (not isinstance(subset, dict) or subset.get("format") != FORMAT
            or subset.get("source_url") != SOURCE_URL
            or subset.get("source_version") != SOURCE_VERSION):
        raise ValueError("Expected the official Pharos400 scoped source format.")
    requested = _ids(subset.get("requested_identifiers"))
    header = subset.get("csv_header")
    _header(header)
    if not isinstance(subset.get("source_sha256"), str) or not SHA256.fullmatch(subset["source_sha256"]):
        raise ValueError("Missing complete source SHA-256.")
    if type(subset.get("source_bytes")) is not int or not 0 < subset["source_bytes"] <= MAX_BYTES:
        raise ValueError("Invalid complete source byte count.")
    rows, total = subset.get("selected_rows"), subset.get("source_data_row_count")
    if not isinstance(rows, list) or type(total) is not int or not len(rows) <= total:
        raise ValueError("Invalid source or selected row counts.")
    previous_row, previous_line = 0, 1
    for record in rows:
        if not isinstance(record, dict):
            raise ValueError("A selected record must be an object.")
        row = record.get("row")
        if (not isinstance(row, dict) or set(row) != set(header)
                or any(not isinstance(v, str) for v in row.values())):
            raise ValueError("Selected rows must retain every original source column as text.")
        logical = record.get("logical_data_row")
        first, last = record.get("physical_line_start"), record.get("physical_line_end")
        if (type(logical) is not int or not previous_row < logical <= total
                or record.get("source_csv_row") != logical + 1
                or type(first) is not int or type(last) is not int
                or not previous_line < first <= last or first < logical + 1):
            raise ValueError("Invalid or duplicate absolute CSV row/physical-line locator.")
        previous_row, previous_line = logical, last
        matches = [{"field": field, "identifier": row[field]}
                   for field in SELECTION_FIELDS if row[field] in requested]
        if not matches or record.get("matched_identifiers") != matches:
            raise ValueError("Selected records must match an allowed exact identifier.")
        raw = record.get("original_csv_record")
        if not isinstance(raw, str) or not raw:
            raise ValueError("The selected original CSV record must be retained.")
        parsed = list(csv.reader(StringIO(raw, newline="")))
        if parsed != [[row[field] for field in header]]:
            raise ValueError("Original selected CSV bytes disagree with parsed source columns.")
        if len(list(StringIO(raw, newline=""))) != last - first + 1:
            raise ValueError("Original record disagrees with its physical-line extent.")
    return subset


def verify_intake(path):
    """Verify saved contract/receipt/subset bindings without network access.

    The intake retains only selected original records. The full-source hash and
    complete-scan counts are capture-time assertions; this verifier cannot replay
    selection completeness against a full CSV that was intentionally not kept.
    It validates all preserved records, locators, exact selection and hash links.
    """
    directory = _real_ancestors(path)
    if not directory.is_dir():
        raise ValueError("The intake must be a real directory.")
    if {p.name for p in directory.iterdir()} != INTAKE_FILES:
        raise ValueError("The intake inventory must contain exactly its three receipt/source files.")
    files = {}
    for name in ("request_contract.json", "http_receipt.json", "selected_rows.json"):
        source = directory / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("The intake requires regular, nonsymlink receipt files.")
        files[name] = source.read_bytes()
    contract, receipt, subset = (json.loads(files[name]) for name in
                                 ("request_contract.json", "http_receipt.json", "selected_rows.json"))
    _check_subset(subset)
    digest = lambda value: hashlib.sha256(value).hexdigest()
    if (contract.get("url") != SOURCE_URL or contract.get("method") != "GET"
            or contract.get("source_version") != SOURCE_VERSION
            or contract.get("allowed_exact_identifiers") != subset["requested_identifiers"]
            or contract.get("selection_fields") != list(SELECTION_FIELDS)
            or contract.get("network", {}).get("retries") != 0
            or contract.get("network", {}).get("follow_redirects") is not False):
        raise ValueError("The saved source request is not the bounded exact-identity contract.")
    if (receipt.get("status") != "complete" or receipt.get("http_status") != 200
            or receipt.get("url") != SOURCE_URL or receipt.get("final_url") != SOURCE_URL
            or receipt.get("request_contract_sha256") != digest(files["request_contract.json"])
            or receipt.get("selected_rows_sha256") != digest(files["selected_rows.json"])):
        raise ValueError("HTTP receipt status, source or artifact bindings do not match.")
    pairs = {"source_sha256": "source_sha256", "source_bytes": "source_bytes",
             "source_data_row_count": "source_data_row_count", "csv_header": "csv_header",
             "selected_ids": "requested_identifiers"}
    if (any(receipt.get(a) != subset[b] for a, b in pairs.items())
            or receipt.get("selected_row_count") != len(subset["selected_rows"])):
        raise ValueError("HTTP receipt and selected source metadata disagree.")
    headers = receipt.get("http_headers")
    if not isinstance(headers, dict):
        raise ValueError("Original HTTP response headers are required.")
    content_length = next((v for k, v in headers.items() if k.lower() == "content-length"), None)
    if content_length is not None and str(subset["source_bytes"]) != str(content_length):
        raise ValueError("Content-Length differs from the recorded complete body size.")
    return {"format": "biograph-steward.pharos400-verified-intake.v1",
            "requested_accessions": list(subset["requested_identifiers"]),
            "subset": deepcopy(subset), "receipt": deepcopy(receipt),
            "integrity": {"preserved_selected_records_verified": True,
                          "full_source_csv_retained": False,
                          "selection_completeness_replayed_offline": False,
                          "source_hash_and_complete_scan_counts": "capture-time assertions"},
            "artifact_bindings": {name: {"sha256": digest(raw), "bytes": len(raw)}
                                  for name, raw in files.items()}}


def build_endpoints(intake, role="added"):
    """Return existing-mapper endpoints plus unresolved source-product reasons.

    Bare accessions are accepted only for a unique canonical row in the selected
    complete-scan scope. A shared base accession never identifies several product
    rows. An explicit, unique isoform identifier may identify an isoform row; its
    suffix is retained exactly. Xrefs, symbols, IFX row IDs and grouping anchors
    are never protein identity assertions. Every selected source row is retained.
    """
    if role not in {"baseline", "added"}:
        raise ValueError("Endpoint role must be baseline or added.")
    if not isinstance(intake, dict):
        raise ValueError("Expected a verified intake or scoped selected-row object.")
    subset = _check_subset(intake.get("subset", intake))
    rows = subset["selected_rows"]
    base_counts = Counter(r["row"]["uniprot_id"] for r in rows)
    source_ids = Counter(r["row"]["id"] for r in rows)
    iso_counts = Counter(r["row"]["uniprot_isoform"] for r in rows
                         if r["row"]["uniprot_isoform"])
    endpoints, unresolved = [], []
    for record in rows:
        row = record["row"]
        base, iso, status = (row[k] for k in
                              ("uniprot_id", "uniprot_isoform", "canonical_isoform_status"))
        reasons, identity = [], None
        if not row["id"] or source_ids[row["id"]] != 1:
            reasons.append("missing_or_duplicate_internal_source_row_id")
        if not UNIPROT.fullmatch(base):
            reasons.append("invalid_public_primary_uniprot_identifier")
        if status == "canonical":
            if iso or "-" in base:
                reasons.append("canonical_row_has_unresolved_explicit_isoform_context")
            elif base_counts[base] != 1:
                reasons.append("shared_base_accession_does_not_identify_product")
            else:
                identity = base
        elif status == "isoform":
            candidate = iso or (base if "-" in base else "")
            if not candidate or not UNIPROT.fullmatch(candidate) or "-" not in candidate:
                reasons.append("isoform_product_lacks_explicit_valid_isoform_identifier")
            elif iso and "-" in base and base != iso:
                reasons.append("conflicting_primary_and_explicit_isoform_identifiers")
            elif iso and "-" not in base and not iso.startswith(base + "-"):
                reasons.append("explicit_isoform_not_consistent_with_source_base_accession")
            elif (iso and iso_counts[iso] != 1) or (not iso and base_counts[base] != 1):
                reasons.append("explicit_isoform_identifier_shared_by_source_products")
            else:
                identity = candidate
        elif status == "alternate_product":
            reasons.append("alternate_product_has_no_public_product_specific_identity")
        else:
            reasons.append("missing_or_unsupported_source_grouping_state")
        if row["tdl"] not in {"Tclin", "Tchem", "Tbio", "Tdark"}:
            reasons.append("invalid_source_tdl_category")
        if reasons:
            identity = None
        line = record["source_csv_row"]
        locator = ("urn:sha256:" + subset["source_sha256"] + "#csv-row=" + str(line)
                   + "&physical-lines=" + str(record["physical_line_start"])
                   + "-" + str(record["physical_line_end"]))
        endpoint = {"endpoint_id": "pharos400:csv-row:" + str(line), "role": role,
                    "resource_id": SOURCE_URL, "resource_version": SOURCE_VERSION,
                    "record_locator": locator, "entity_type": "protein",
                    "identity_role": "source_primary" if identity else "unresolved_product_identity",
                    "primary_ids": ["UniProtKB:" + identity] if identity else [],
                    "source_row": deepcopy(record),
                    "source_internal_id_is_public_protein_identifier": False,
                    "identity_resolution": {"identifier": identity, "unresolved_reasons": reasons,
                                            "scope": "exact_source_primary_identifier_only"},
                    "unavailable_grouping_columns": [k for k in GROUP_FIELDS if k not in row]}
        endpoints.append(endpoint)
        if reasons:
            unresolved.append({"endpoint_id": endpoint["endpoint_id"], "reasons": reasons,
                               "record_locator": locator, "source_row": deepcopy(record)})
    present = {m["identifier"] for r in rows for m in r["matched_identifiers"]}
    return {"format": "biograph-steward.pharos400-identity-endpoints.v1",
            "endpoints": endpoints, "unresolved": unresolved,
            "summary": {"source_version": SOURCE_VERSION, "selected_rows": len(rows),
                        "source_primary_endpoints": sum(e["identity_role"] == "source_primary" for e in endpoints),
                        "unresolved_product_rows": len(unresolved),
                        "requested_ids_without_selected_rows": [v for v in subset["requested_identifiers"] if v not in present],
                        "source_data_row_count": subset["source_data_row_count"],
                        "full_source_selection_completeness_replayed_offline": False,
                        "graph_relationships_or_experiment_lineage_updated": False}}
