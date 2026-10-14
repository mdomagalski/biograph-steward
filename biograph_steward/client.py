"""Read-only Pharos GraphQL client. No credentials, LLM, or database required.

Queries follow the NCATS public schema. GraphQL errors, including partial errors,
are not silently accepted. Live failures NEVER fall back to demonstration data.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ENDPOINT = "https://pharos-api.ncats.io/graphql"
SCHEMA_SOURCE = "https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql"

SEARCH = """query SearchDiseases($term: String!, $top: Int!, $skip: Int!) {
  diseases(filter: {term: $term}) {
    count
    diseases(top: $top, skip: $skip) { name mondoID associationCount }
  }
}"""

DISEASE = """query DiseaseInfo($name: String!) {
  disease(name: $name) {
    name mondoID associationCount directAssociationCount
    mondoDescription doDescription
    dids { id dataSources doName }
    targetCounts { name value }
  }
}"""

TARGETS = """query DiseaseTargets($disease: String!, $top: Int!, $skip: Int!, $pathwayTop: Int!, $includePathways: Boolean!) {
  targets(filter: {associatedDisease: $disease}) {
    count
    targets(top: $top, skip: $skip) {
      uniprot sym name tdl fam
      diseaseAssociationDetails {
        name dataType evidence reference source score conf zscore log2foldchange pvalue
      }
      pathways(top: $pathwayTop) @include(if: $includePathways) { pwid name type sourceID url }
    }
  }
}"""

VERSION = "query DatabaseVersion { dbVersion }"
LICENSES = """query SourceLicenses {
  dataSourceCounts { dataSource url license licenseURL }
}"""

INSPECT_TYPE = """query InspectType($name: String!) {
  __type(name: $name) {
    name
    fields { name args { name } }
    inputFields { name }
  }
}"""

# Query fields are checked before a live build, unless the caller explicitly opts out.
REQUIRED_FIELDS = {
    "Query": {"dbVersion", "diseases", "disease", "targets"},
    "DiseaseResult": {"count", "diseases"},
    "TargetResult": {"count", "targets"},
    "Disease": {"name", "mondoID", "associationCount", "directAssociationCount",
                "mondoDescription", "doDescription", "dids", "targetCounts"},
    "Target": {"uniprot", "sym", "name", "tdl", "fam", "diseaseAssociationDetails", "pathways"},
    "AssociationDetails": {"name", "dataType", "evidence", "reference", "source", "score",
                           "conf", "zscore", "log2foldchange", "pvalue"},
    "Pathway": {"pwid", "name", "type", "sourceID", "url"},
    "IFilter": {"term", "associatedDisease"},
}


class PharosError(RuntimeError):
    """An actionable, user-facing service or schema error."""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + "." + uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class PharosClient:
    def __init__(self, endpoint: str = ENDPOINT, cache_dir: Path | None = None,
                 timeout: float = 30, retries: int = 2, refresh: bool = False,
                 ttl_hours: float = 24, transport: Callable | None = None):
        parsed = urlparse(endpoint)
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
            raise ValueError("Use HTTPS for Pharos; HTTP is permitted only for local test servers.")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("Endpoint must not contain credentials or a fragment.")
        if timeout <= 0 or retries < 0:
            raise ValueError("Timeout must be positive and retries must be non-negative.")
        self.endpoint = endpoint
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout = timeout
        self.retries = retries
        self.refresh = refresh
        self.ttl_hours = ttl_hours
        self.transport = transport
        self.records: list[dict] = []

    def _http(self, payload: dict) -> dict:
        request = Request(self.endpoint, data=canonical(payload).encode("utf-8"), method="POST",
                          headers={"Content-Type": "application/json", "Accept": "application/json",
                                   "User-Agent": "BioGraphSteward-PharosStarter/0.1"})
        # Python honors HTTPS_PROXY. SSL_CERT_FILE can specify an approved CA bundle.
        context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout, context=context) as response:
                    raw = response.read(25_000_001)
                    if len(raw) > 25_000_000:
                        raise PharosError("Response exceeded the 25 MB safety limit; reduce the page size.")
                    try:
                        return json.loads(raw)
                    except (ValueError, UnicodeDecodeError) as exc:
                        raise PharosError("Pharos returned non-JSON content. Check the endpoint or proxy.") from exc
            except HTTPError as exc:
                detail = exc.read(1000).decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    retry_after = exc.headers.get("Retry-After", "")
                    delay = min(float(retry_after), 15.0) if retry_after.isdigit() else 2 ** attempt
                    time.sleep(delay)
                    continue
                raise PharosError(f"Pharos HTTP {exc.code}: {detail[:300]}. No demo fallback was used.") from exc
            except (URLError, TimeoutError, socket.timeout, OSError) as exc:
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
                    continue
                raise PharosError(
                    f"Cannot reach Pharos ({exc}). Check network/VPN/proxy and run 'python app.py doctor'. "
                    "For the offline demonstration explicitly choose Demo; it is synthetic, not Pharos data."
                ) from exc
        raise PharosError("Pharos request failed.")

    def execute(self, query: str, variables: dict | None = None, *, cache: bool = True) -> dict:
        payload = {"query": query, "variables": variables or {}}
        key = digest({"endpoint": self.endpoint, **payload})
        path = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if path and path.exists() and cache and not self.refresh:
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                age = datetime.now(timezone.utc).timestamp() - datetime.fromisoformat(saved["retrieved_at"]).timestamp()
                if (0 <= age < self.ttl_hours * 3600 and saved["endpoint"] == self.endpoint
                        and saved["request"] == payload and saved["response_sha256"] == digest(saved["response"])):
                    self._validate_response(saved["response"])
                    self.records.append({**saved, "loaded_from_cache": True})
                    return saved["response"]["data"]
            except (ValueError, KeyError, TypeError, PharosError):
                pass  # A corrupt/expired cache is not trusted; fetch explicitly instead.
        response = self.transport(payload) if self.transport else self._http(payload)
        self._validate_response(response)
        record = {"endpoint": self.endpoint, "request": payload, "retrieved_at": utcnow(),
                  "response": response, "response_sha256": digest(response), "loaded_from_cache": False}
        self.records.append(record)
        if path and cache:
            write_json(path, record)
        return response["data"]

    @staticmethod
    def _validate_response(response: Any) -> None:
        if not isinstance(response, dict):
            raise PharosError("Expected a GraphQL JSON object.")
        if response.get("errors"):
            messages = [str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in response["errors"]]
            raise PharosError("GraphQL error; partial data rejected: " + "; ".join(messages))
        if not isinstance(response.get("data"), dict):
            raise PharosError("GraphQL response is missing a usable 'data' object.")

    def search(self, term: str, top: int = 20, skip: int = 0) -> dict:
        if not isinstance(term, str) or not term.strip() or len(term) > 200:
            raise ValueError("Enter a disease search term of 1-200 characters.")
        if not 1 <= top <= 100 or skip < 0:
            raise ValueError("Search top must be 1-100; skip must be non-negative.")
        result = self.execute(SEARCH, {"term": term.strip(), "top": top, "skip": skip}).get("diseases")
        if not isinstance(result, dict) or not isinstance(result.get("diseases"), list):
            raise PharosError("Disease search response does not match the expected Pharos schema.")
        return result

    def check_schema(self) -> dict:
        missing: dict[str, list[str]] = {}
        for name, required in REQUIRED_FIELDS.items():
            obj = self.execute(INSPECT_TYPE, {"name": name}).get("__type")
            fields = (obj or {}).get("inputFields" if name == "IFilter" else "fields") or []
            absent = sorted(required - {x.get("name") for x in fields})
            if absent:
                missing[name] = absent
        if missing:
            raise PharosError("Pharos schema differs from this starter: " + json.dumps(missing)
                              + ". Review client.py against the current schema; no records were relabeled.")
        return {"status": "required_fields_present", "schema_source": SCHEMA_SOURCE}

    def build_snapshot(self, disease: str, max_targets: int = 25, page_size: int = 25,
                       pathway_top: int = 5, check_schema: bool = True) -> dict:
        if not isinstance(disease, str) or not disease.strip() or len(disease) > 200:
            raise ValueError("Select an exact Pharos disease name (1-200 characters).")
        if not 1 <= max_targets <= 500 or not 1 <= page_size <= 100 or not 0 <= pathway_top <= 25:
            raise ValueError("Use 1-500 targets, 1-100 records/page, and 0-25 pathways/target.")
        start = len(self.records)
        schema_check = self.check_schema() if check_schema else {"status": "explicitly_skipped"}
        version = self.execute(VERSION).get("dbVersion")
        info = self.execute(DISEASE, {"name": disease.strip()}).get("disease")
        if not isinstance(info, dict) or not info.get("name"):
            raise PharosError("No disease found. Run disease search and choose an exact returned name.")
        if info["name"].strip().casefold() != disease.strip().casefold():
            raise PharosError(f"Pharos resolved the input to {info['name']!r}. Confirm that exact term before building.")
        canonical_name = info["name"]
        targets: list[dict] = []
        pages: list[dict] = []
        seen_pages: set[str] = set()
        total = None
        skip = 0
        exhausted = False
        warnings: list[str] = []
        while len(targets) < max_targets:
            top = min(page_size, max_targets - len(targets))
            variables = {"disease": canonical_name, "top": top, "skip": skip, "pathwayTop": pathway_top, "includePathways": pathway_top > 0}
            result = self.execute(TARGETS, variables).get("targets")
            if not isinstance(result, dict) or not isinstance(result.get("targets"), list):
                raise PharosError("Target list response does not match the Pharos schema.")
            rows = result["targets"]
            if any(not isinstance(row, dict) for row in rows):
                raise PharosError("Pharos returned a null or malformed target row; partial graph not published.")
            if len(rows) > top:
                raise PharosError("Pharos returned more rows than requested; pagination contract changed.")
            count = result.get("count")
            if isinstance(count, int) and count >= 0:
                if total is not None and total != count:
                    warnings.append("Target count changed between pages; refresh before using this run as a benchmark.")
                total = count
            if not rows:
                exhausted = True
                break
            fingerprint = digest(rows)
            if fingerprint in seen_pages:
                raise PharosError("Pharos repeated a target page; stopped to avoid silently duplicating results.")
            seen_pages.add(fingerprint)
            pages.append({"skip": skip, "requested": top, "returned": len(rows)})
            targets.extend(rows)
            skip += len(rows)
            if len(rows) < top or (total is not None and skip >= total):
                exhausted = True
                break
            if not self.transport:
                time.sleep(0.15)
        if total is not None and total > len(targets):
            truncated = True
        else:
            truncated = not exhausted and len(targets) == max_targets
        if truncated:
            warnings.append("Target cap reached: this is a bounded extract, not the complete Pharos disease graph.")
        if pathway_top:
            warnings.append(f"Pathway context is capped at {pathway_top} records per target in API order; it is not exhaustive.")
        source_licenses: list[dict] = []
        try:
            source_licenses = self.execute(LICENSES).get("dataSourceCounts") or []
        except PharosError as exc:
            warnings.append("Source-license metadata could not be retrieved; redistribution needs review. " + str(exc))
        snapshot = {
            "snapshot_format": "biograph-steward.pharos.v1", "data_kind": "live_pharos",
            "created_at": utcnow(), "endpoint": self.endpoint, "db_version": version,
            "disease": info, "targets": targets, "requests": self.records[start:],
            "source_licenses": source_licenses, "schema_check": schema_check,
            "query_settings": {"max_targets": max_targets, "page_size": page_size, "pathway_top": pathway_top},
            "retrieval": {"total_targets_reported": total, "records_retrieved": len(targets),
                          "truncated": truncated, "pages": pages}, "warnings": warnings,
        }
        snapshot["content_sha256"] = digest(snapshot)
        return snapshot
