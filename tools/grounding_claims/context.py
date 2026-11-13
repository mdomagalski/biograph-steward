"""Immutable, bounded PubMed title/abstract context using the existing parser.

No PMC/full-text request, inference call or biological judgment is made here.
The current retrieved abstract is a separate corpus from native Evidence.text.
"""
from copy import deepcopy
from hashlib import sha256
from itertools import islice
import json
import math
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError

from biograph_steward import literature
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha


FORMAT = "biograph-steward.frozen-pubmed-abstract-context.v1"
MAX_PMIDS = 6000
BATCH_SIZE = 30
MAX_REQUESTS = 200
MAX_FETCH_BYTES = 20_000_000
MAX_TOTAL_BYTES = 100_000_000
POLICY = ("Current PubMed title and nonempty abstract for the exact PMID, joined "
          "from existing parsed fields. This is distinct from original native "
          "Evidence.text and is not oracle full text. Missing text or access is "
          "unavailable, never a biological negative. No PMC/full-text retrieval "
          "or automatic context fallback.")
CONTEXT_JOIN = "title + two newlines + abstract passages separated by two newlines"
LICENSE_NOTE = "Source copyright is retained; public access is not blanket redistribution permission."
REQUEST_KEYS = {"batch_index", "pmids", "url", "retrieved_at", "status", "reason",
                "attempted", "raw_file", "raw_sha256", "raw_bytes", "error_file",
                "error_type", "http_status"}


def _inventory(pmids):
    if isinstance(pmids, (str, bytes)):
        raise ValueError("Supply a collection of exact PMID strings.")
    try:
        values = list(islice(iter(pmids), MAX_PMIDS + 1))
    except TypeError:
        raise ValueError("Supply a collection of exact PMID strings.") from None
    if (not 1 <= len(values) <= MAX_PMIDS
            or any(not isinstance(p, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", p) for p in values)
            or len(set(values)) != len(values)):
        raise ValueError("Use 1-6000 unique exact PMID strings, without aliases or leading zeros.")
    return sorted(values, key=int)


def _limits():
    return {"max_pmids": MAX_PMIDS, "batch_size": BATCH_SIZE,
            "max_requests": MAX_REQUESTS, "per_fetch_raw_bytes": MAX_FETCH_BYTES,
            "total_raw_bytes": MAX_TOTAL_BYTES}


def _code_pins():
    return {"adapter_sha256": sha(__file__),
            "native_parser_module_sha256": sha(literature.__file__),
            "parser": "biograph_steward.literature.parse_pubmed",
            "fetch": "biograph_steward.literature.fetch"}


def _batches(pmids):
    return [pmids[i:i + BATCH_SIZE] for i in range(0, len(pmids), BATCH_SIZE)]


def _rows(request, parsed):
    result = []
    for pmid in request["pmids"]:
        paper = parsed.get(pmid)
        reasons = []
        if request["status"] == "unavailable":
            reasons.append(request["reason"])
        elif paper is None:
            reasons.append("pubmed_identity_missing")
        title = paper["title"] if paper is not None else ""
        abstract = paper["abstract"] if paper is not None else []
        if paper is not None:
            if not title.strip():
                reasons.append("title_unavailable")
            if not abstract:
                reasons.append("abstract_unavailable")
        available = not reasons
        context = title + "\n\n" + "\n\n".join(p["text"] for p in abstract) if available else None
        result.append({"pmid": pmid, "status": "available" if available else "unavailable",
                       "reasons": reasons, "context_kind": "current_pubmed_title_abstract",
                       "context_text": context,
                       "context_sha256": sha256(context.encode("utf-8")).hexdigest() if context is not None else None,
                       "title": title, "abstract": deepcopy(abstract),
                       "copyright": paper.get("copyright") if paper is not None else None,
                       "source_record": deepcopy(paper), "source_url": request["url"],
                       "publication_url": "https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/",
                       "raw_file": request.get("raw_file"), "raw_sha256": request.get("raw_sha256"),
                       "retrieved_at": request["retrieved_at"],
                       "locators": ({"title": f"PubmedArticle[PMID={pmid}]/MedlineCitation/Article/ArticleTitle",
                                     "abstract": [p["locator"] for p in abstract]} if paper is not None else None)})
    return result


def _reject(out, requests, pmids, code, reason):
    value = {"format": FORMAT + ".rejected", "created_at": utcnow(),
             "requested_pmids": pmids, "requests": requests,
             "code": code, "reason": reason, "usable_context_capture": False}
    value["content_sha256"] = digest(value)
    write_json(out / "capture_rejected.json", value)


def capture_context(pmids, out, *, transport=None, pace=.4):
    """Capture exact PubMed abstracts into a new ordinary-file packet.

    HTTP/access failure and missing articles remain unavailable. Invalid XML,
    duplicate or unrequested response identities reject the capture while
    preserving returned bytes and a rejection receipt. Native retrieval uses
    the existing 20 MB fetch. A whole-fetch reserve conservatively prevents
    the fixed total raw-byte budget from being exceeded; remaining IDs stay
    unavailable instead of triggering an adaptive budget extension.
    """
    pmids = _inventory(pmids)
    if (type(pace) not in (int, float) or not math.isfinite(pace) or not 0 <= pace <= 60
            or transport is None and pace < 1 / 3):
        raise ValueError("Use a finite 0-60 second pace; native retrieval requires at least one third second.")
    if transport is not None and not callable(transport):
        raise ValueError("Transport must be callable.")
    batches = _batches(pmids)
    if len(batches) > MAX_REQUESTS:
        raise ValueError("PubMed request budget exceeded.")
    code = _code_pins()
    out = new_output(out, __file__, literature.__file__)
    write_json(out / "requested_pmids.json", pmids)
    fetch = transport or literature.fetch
    requests, contexts, total, attempted = [], [], 0, 0
    for number, batch in enumerate(batches, 1):
        request = {"batch_index": number, "pmids": batch,
                   "url": literature.PUBMED + ",".join(batch), "retrieved_at": utcnow(),
                   "status": "unavailable", "reason": None, "attempted": False,
                   "raw_file": None, "raw_sha256": None, "raw_bytes": 0,
                   "error_file": None, "error_type": None, "http_status": None}
        requests.append(request)
        raw = None
        if MAX_TOTAL_BYTES - total < MAX_FETCH_BYTES:
            request["reason"] = "remaining_total_budget_below_fetch_bound"
        else:
            if attempted and pace:
                time.sleep(pace)
            attempted += 1
            request["attempted"] = True
            try:
                raw = fetch(request["url"])
                if not isinstance(raw, bytes) or len(raw) > MAX_FETCH_BYTES:
                    raise ValueError("Invalid or over-budget PubMed response.")
            except (HTTPError, URLError, OSError, ValueError) as exc:
                raw = None
                request.update(reason="transport_unavailable", error_type=type(exc).__name__)
                if isinstance(exc, HTTPError):
                    request["http_status"] = exc.code
                    exc.close()
        if raw is None:
            request["error_file"] = f"pubmed_batch_{number:04d}.error.json"
            write_json(out / request["error_file"], request)
            contexts.extend(_rows(request, {}))
            continue
        name = f"pubmed_batch_{number:04d}.xml"
        (out / name).write_bytes(raw)
        request.update(status="downloaded", raw_file=name,
                       raw_sha256=sha256(raw).hexdigest(), raw_bytes=len(raw))
        total += len(raw)
        try:
            parsed = literature.parse_pubmed(raw)
            if set(parsed) - set(batch):
                raise ValueError("PubMed returned unrequested identities.")
        except ValueError as exc:
            request.update(status="rejected", reason="invalid_pubmed_source", error_type=type(exc).__name__)
            _reject(out, requests, pmids, code, str(exc))
            raise ValueError("PubMed source rejected; raw bytes and rejection receipt were preserved.") from exc
        contexts.extend(_rows(request, parsed))
    if code != _code_pins():
        _reject(out, requests, pmids, code, "Capture/parser source changed during retrieval.")
        raise ValueError("Capture/parser source changed during retrieval.")
    write_json(out / "contexts.json", contexts)
    manifest = {"format": FORMAT, "created_at": utcnow(), "requested_pmids": pmids,
                "requested_pmids_sha256": digest(pmids), "code": code,
                "limits": _limits(), "pace_seconds": pace,
                "transport": "native_fetch" if transport is None else "injected_transport",
                "policy": POLICY, "context_join": CONTEXT_JOIN,
                "license_note": LICENSE_NOTE,
                "requests": requests, "requests_attempted": attempted, "total_raw_bytes": total,
                "available_contexts": sum(c["status"] == "available" for c in contexts),
                "unavailable_contexts": sum(c["status"] == "unavailable" for c in contexts),
                "contexts_sha256": digest(contexts),
                "files": {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    manifest["content_sha256"] = digest(manifest)
    write_json(out / "manifest.json", manifest)
    return manifest


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("Frozen PubMed context JSON is unavailable or invalid.") from exc


def load_context(path):
    """Replay byte pins and native PubMed parsing offline; return a PMID map."""
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Use an ordinary frozen PubMed context directory.")
    if (path / "manifest.json").is_symlink() or not (path / "manifest.json").is_file():
        raise ValueError("Frozen context manifest is not an ordinary file.")
    manifest = _read_json(path / "manifest.json")
    if (not isinstance(manifest, dict) or manifest.get("format") != FORMAT
            or manifest.get("content_sha256") != digest({k: v for k, v in manifest.items() if k != "content_sha256"})
            or manifest.get("code") != _code_pins() or manifest.get("limits") != _limits()
            or manifest.get("policy") != POLICY or manifest.get("context_join") != CONTEXT_JOIN
            or manifest.get("license_note") != LICENSE_NOTE):
        raise ValueError("Frozen PubMed manifest, code or policy differs.")
    pace, transport = manifest.get("pace_seconds"), manifest.get("transport")
    if (transport not in {"native_fetch", "injected_transport"}
            or type(pace) not in (int, float) or not math.isfinite(pace) or not 0 <= pace <= 60
            or transport == "native_fetch" and pace < 1 / 3
            or any(type(manifest.get(key)) is not int for key in
                   ("requests_attempted", "total_raw_bytes", "available_contexts", "unavailable_contexts"))):
        raise ValueError("Frozen PubMed transport/count metadata differs.")
    pmids = _inventory(manifest.get("requested_pmids"))
    if pmids != manifest["requested_pmids"] or digest(pmids) != manifest.get("requested_pmids_sha256"):
        raise ValueError("Frozen PMID inventory differs.")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("Frozen PubMed file inventory is invalid.")
    actual = set()
    for p in path.iterdir():
        if p.is_symlink() or not p.is_file():
            raise ValueError("Frozen PubMed sources must be ordinary files.")
        if p.name != "manifest.json":
            actual.add(p.name)
    if actual != set(files):
        raise ValueError("Frozen PubMed source inventory differs.")
    for name, pin in files.items():
        if Path(name).name != name or not isinstance(pin, str) or sha(path / name) != pin:
            raise ValueError("Frozen PubMed source bytes differ.")
    if _read_json(path / "requested_pmids.json") != pmids:
        raise ValueError("Frozen PMID input bytes differ.")
    batches, requests = _batches(pmids), manifest.get("requests")
    if not isinstance(requests, list) or len(requests) != len(batches) or len(requests) > MAX_REQUESTS:
        raise ValueError("Frozen PubMed batch inventory differs.")
    expected_files = {"requested_pmids.json", "contexts.json"}
    contexts, total, attempted = [], 0, 0
    for number, (batch, request) in enumerate(zip(batches, requests), 1):
        if (not isinstance(request, dict) or set(request) != REQUEST_KEYS
                or type(request.get("batch_index")) is not int or request.get("batch_index") != number
                or request.get("pmids") != batch or request.get("url") != literature.PUBMED + ",".join(batch)
                or not isinstance(request.get("retrieved_at"), str)
                or not request["retrieved_at"] or type(request.get("attempted")) is not bool
                or type(request.get("raw_bytes")) is not int or request["raw_bytes"] < 0):
            raise ValueError("Frozen PubMed request identity differs.")
        attempted += request["attempted"]
        if request.get("status") == "downloaded":
            name = f"pubmed_batch_{number:04d}.xml"
            if (request.get("raw_file") != name or request.get("raw_sha256") != files.get(name)
                    or request.get("error_file") is not None or not request["attempted"]
                    or request.get("reason") is not None or request.get("error_type") is not None
                    or request.get("http_status") is not None
                    or MAX_TOTAL_BYTES - total < MAX_FETCH_BYTES):
                raise ValueError("Frozen PubMed raw-source binding differs.")
            expected_files.add(name)
            raw = (path / name).read_bytes()
            if len(raw) != request.get("raw_bytes") or len(raw) > MAX_FETCH_BYTES:
                raise ValueError("Frozen PubMed byte count differs.")
            total += len(raw)
            parsed = literature.parse_pubmed(raw)
            if set(parsed) - set(batch):
                raise ValueError("Frozen PubMed has unrequested identities.")
        elif request.get("status") == "unavailable":
            name = f"pubmed_batch_{number:04d}.error.json"
            if (request.get("error_file") != name or request.get("raw_file") is not None
                    or request.get("raw_sha256") is not None or request.get("raw_bytes") != 0
                    or request.get("reason") not in {"transport_unavailable", "remaining_total_budget_below_fetch_bound"}
                    or _read_json(path / name) != request):
                raise ValueError("Frozen PubMed failure binding differs.")
            if ((request["reason"] == "transport_unavailable" and not request["attempted"])
                    or (request["reason"] == "remaining_total_budget_below_fetch_bound"
                        and (request["attempted"] or MAX_TOTAL_BYTES - total >= MAX_FETCH_BYTES))):
                raise ValueError("Frozen PubMed failure/budget disposition differs.")
            if ((request["reason"] == "transport_unavailable"
                 and (not isinstance(request["error_type"], str) or not request["error_type"]))
                    or (request["reason"] == "remaining_total_budget_below_fetch_bound"
                        and (request["error_type"] is not None or request["http_status"] is not None))
                    or request["http_status"] is not None
                    and (type(request["http_status"]) is not int or not 100 <= request["http_status"] <= 599)):
                raise ValueError("Frozen PubMed error metadata differs.")
            expected_files.add(name)
            parsed = {}
        else:
            raise ValueError("Rejected PubMed sources cannot supply context.")
        contexts.extend(_rows(request, parsed))
    if (expected_files != set(files) or total > MAX_TOTAL_BYTES
            or manifest.get("total_raw_bytes") != total or manifest.get("requests_attempted") != attempted
            or manifest.get("available_contexts") != sum(c["status"] == "available" for c in contexts)
            or manifest.get("unavailable_contexts") != sum(c["status"] == "unavailable" for c in contexts)
            or manifest.get("contexts_sha256") != digest(contexts)
            or _read_json(path / "contexts.json") != contexts):
        raise ValueError("Frozen PubMed contexts differ from native source replay.")
    return {row["pmid"]: row for row in contexts}
