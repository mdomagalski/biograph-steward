"""Bounded STRING source ordering for an existing protein-neighborhood answer.

This is a reusable REST capture, not a new confidence formula or graph assertion.
The existing typed STRING parsers retain source coverage and mapping limitations.
Packets contain every response needed for offline replay and portable answers.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
import csv
from datetime import datetime, timezone
import hashlib
import io
import math
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .client import digest, utcnow
from .string_component import parse_mapping, parse_network, project_predictions


FORMAT = "biograph-steward.question-physical-ranking.v1"
BASE = "https://version-12-5.string-db.org/api/tsv/"
RELEASE = "12.5"
LIMITS = {
    "max_interaction_neighbors": 100, "mapping_batch_size": 100,
    "neighbor_batch_size": 25, "minimum_request_interval_seconds": 1.05,
    "timeout_seconds": 60, "max_attempts_per_request": 3,
    "max_logical_requests": 7, "max_http_attempts": 21,
    "max_body_bytes": 4 * 1024 * 1024,
    "max_total_body_bytes": 32 * 1024 * 1024,
    "retry_statuses": [500, 502, 503, 504],
}
PROFILE = {"species": "9606", "required_score": "0", "add_nodes": "0",
           "network_type": "functional", "network_flavor": "typed",
           "typed_physical_edges": "1", "typed_regulatory_edges": "0"}
LIMITATIONS = [
    "Optional native STRING ordering does not change assertions, paths, review status or graph contents.",
    "STRING is already a Pharos provider; this is not additional independent evidence.",
    "A physical overlay is task-specific source ranking, not proof of direct binding, scientific accuracy or clinical relevance.",
    "Mapping selects STRING's best-match locus representative, not exact sequence or construct identity; alternatives are not exhaustively searched.",
    "No returned row and a missing physical overlay are coverage states, not evidence of absence.",
    "The typed functional profile may omit physical interactions; this is not a complete standalone physical network.",
]
ACCESSION = re.compile(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?")
# The HTTP app handles requests on several threads. The provider cooldown must
# survive a completed answer and apply to other live captures in this process.
_SOURCE_LOCK = threading.Lock()
_SOURCE_LAST_START = None


def _need(condition, message):
    if not condition:
        raise ValueError("Physical ranking: " + message)


def _seal(value):
    return {**value, "content_sha256": digest(value)}


def _basis(graph):
    # Lazy import keeps question construction free to use this adapter.
    from .questions import graph_basis
    return graph_basis(graph)


def _accession(uid):
    _need(isinstance(uid, str) and uid.startswith("UniProtKB:")
          and ACCESSION.fullmatch(uid[10:]) is not None,
          "an exact canonical UniProtKB accession or isoform node ID is required.")
    return uid[10:]


def _chunks(values, size):
    return [values[i:i + size] for i in range(0, len(values), size)]


def _label(node):
    return node.get("sym") or node.get("label") or node.get("name") or node.get("id")


def _binding(candidates):
    """Bind the complete candidate set without duplicating each evidence path."""
    _need(isinstance(candidates, list), "candidate rows must be a complete list.")
    result = []
    for row in candidates:
        _need(isinstance(row, dict) and isinstance(row.get("protein"), dict),
              "candidate protein row differs.")
        relations = row.get("matched_relations")
        _need(isinstance(relations, dict)
              and all(isinstance(key, str) and type(count) is int and count >= 0
                      for key, count in relations.items()), "candidate relation counts differ.")
        result.append({"protein_id": row["protein"].get("id"),
                       "label": _label(row["protein"]),
                       "has_interaction": relations.get("interaction", 0) > 0})
    return result


def _candidates(anchor, candidates, graph=None):
    _accession(anchor)
    _need(isinstance(candidates, list), "candidate rows must be a complete list.")
    identifiers, eligible = [], []
    nodes = None
    if graph is not None:
        _need(isinstance(graph, dict) and graph.get("data_kind") == "live_pharos",
              "only saved live Pharos graphs may request source ordering.")
        nodes = {node["id"]: node for node in graph["nodes"]}
        _need(anchor in nodes, "anchor is not in the saved graph.")
    for row in candidates:
        _need(isinstance(row, dict) and set(row) == {"protein_id", "label", "has_interaction"}
              and isinstance(row["label"], str) and bool(row["label"])
              and type(row["has_interaction"]) is bool, "candidate binding differs.")
        uid = row["protein_id"]
        _accession(uid)
        _need(uid != anchor and uid not in identifiers,
              "candidate identifiers must be distinct neighbors of the anchor.")
        if nodes is not None:
            _need(uid in nodes and row["label"] == _label(nodes[uid]),
                  "candidate protein does not match its saved graph node.")
        identifiers.append(uid)
        if row["has_interaction"]:
            eligible.append(uid)
    _need(len(eligible) <= LIMITS["max_interaction_neighbors"],
          "more than 100 interaction neighbors; narrow the question before retrieving.")
    # Existing answer rows stay untouched; only the external query plan is sorted.
    return identifiers, sorted(eligible)


def _parameters(kind, identifiers):
    if kind == "version":
        _need(not identifiers, "version requests do not take identifiers.")
        return {}
    params = {"identifiers": "\r".join(identifiers), "species": "9606",
              "caller_identity": "biograph-steward"}
    if kind == "mapping":
        params["echo_query"] = "1"
    else:
        _need(kind == "network", "unknown request kind.")
        params.update(PROFILE)
    return params


def _request_spec(kind, batch_id, identifiers):
    params = _parameters(kind, identifiers)
    method = {"version": "version", "mapping": "get_string_ids", "network": "network"}[kind]
    return {"kind": kind, "batch_id": batch_id, "identifiers": list(identifiers),
            "parameters": params, "url": BASE + method + ("?" + urlencode(params) if params else "")}


def _version(raw):
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8")), delimiter="\t"))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Physical ranking: invalid version response.") from exc
    _need(rows == [["string_version", "stable_address"],
                   [RELEASE, "https://version-12-5.string-db.org"]],
          "provider release differs from STRING 12.5.")
    return {"string_version": RELEASE, "stable_address": "https://version-12-5.string-db.org"}


def _headers(headers, raw, success):
    _need(isinstance(headers, dict)
          and all(isinstance(key, str) and isinstance(value, str) for key, value in headers.items()),
          "response header schema differs.")
    lowered = {key.lower(): value for key, value in headers.items()}
    _need(len(lowered) == len(headers), "duplicate case-insensitive response header.")
    _need(lowered.get("content-encoding", "identity").lower() == "identity",
          "unexpected response encoding.")
    length = lowered.get("content-length")
    if length is not None:
        _need(length.isascii() and length.isdecimal() and int(length) == len(raw),
              "response Content-Length does not match preserved bytes.")
    if success:
        _need(lowered.get("string-api-version") == "2"
              and lowered.get("content-type", "").lower().startswith("text/tab-separated-values"),
              "unsupported provider API or response content type.")


def _fetch(url, *, timeout, max_bytes):
    request = Request(url, headers={"User-Agent": "BioGraph-Steward/0.8 question-source-ranking"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return {"status": response.status, "headers": dict(response.headers),
                    "url": response.url, "body": response.read(max_bytes + 1)}
    except HTTPError as exc:
        return {"status": exc.code, "headers": dict(exc.headers), "url": exc.url,
                "body": exc.read(max_bytes + 1)}


class _Client:
    def __init__(self, fetcher, clock, sleep, *, shared_rate=False):
        self.fetcher, self.clock, self.sleep = fetcher, clock, sleep
        self.shared_rate = shared_rate
        self.requests, self.last_start = [], None
        self.total_bytes, self.attempt_count = 0, 0

    def request(self, kind, batch_id, identifiers):
        global _SOURCE_LAST_START
        _need(len(self.requests) < LIMITS["max_logical_requests"], "logical request cap exceeded.")
        request = {**_request_spec(kind, batch_id, identifiers), "attempts": []}
        self.requests.append(request)
        for number in range(1, LIMITS["max_attempts_per_request"] + 1):
            self.attempt_count += 1
            _need(self.attempt_count <= LIMITS["max_http_attempts"], "HTTP attempt cap exceeded.")
            status, headers, final_url, raw, error = None, {}, None, b"", None
            # Serializing each default transport through its bounded read also
            # prevents simultaneous live calls; injected test transports retain
            # their local clocks without sharing global simulation state.
            with _SOURCE_LOCK if self.shared_rate else nullcontext():
                previous = [value for value in (self.last_start,
                            _SOURCE_LAST_START if self.shared_rate else None) if value is not None]
                if previous:
                    self.sleep(max(0.0, LIMITS["minimum_request_interval_seconds"] - (self.clock() - max(previous))))
                started = self.clock()
                _need(isinstance(started, (int, float)) and not isinstance(started, bool)
                      and math.isfinite(started) and started >= 0,
                      "transport clock must be finite and monotonic.")
                _need(not previous or started - max(previous) + 1e-9 >= LIMITS["minimum_request_interval_seconds"],
                      "request interval below the source rate limit.")
                self.last_start = started
                if self.shared_rate:
                    _SOURCE_LAST_START = started
                try:
                    response = self.fetcher(request["url"], timeout=LIMITS["timeout_seconds"],
                                            max_bytes=LIMITS["max_body_bytes"])
                    _need(isinstance(response, dict), "transport response is not an object.")
                    status, headers, final_url, raw = (response.get(key) for key in ("status", "headers", "url", "body"))
                except (OSError, URLError) as exc:
                    error = str(exc) or type(exc).__name__
            _need(isinstance(raw, bytes), "response must preserve raw bytes.")
            _need(len(raw) <= LIMITS["max_body_bytes"], "response exceeds body byte cap.")
            self.total_bytes += len(raw)
            _need(self.total_bytes <= LIMITS["max_total_body_bytes"], "total response byte cap exceeded.")
            try:
                body_text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Physical ranking: source response is not preservable UTF-8.") from exc
            if status is not None:
                _need(type(status) is int and 100 <= status <= 599, "invalid HTTP status.")
                _need(final_url == request["url"], "a pinned source request was redirected.")
                _headers(headers, raw, status == 200)
                if status != 200:
                    error = "HTTP " + str(status)
            receipt = {"attempt": number, "started_monotonic": started,
                       "status": status, "headers": headers, "final_url": final_url,
                       "error": error, "body_text": body_text, "body_bytes": len(raw),
                       "body_sha256": hashlib.sha256(raw).hexdigest()}
            request["attempts"].append(receipt)
            if status == 200 and error is None:
                return raw
            _need(error is not None, "transport returned no HTTP status or network error.")
            _need((status is None or status in LIMITS["retry_statuses"])
                  and number < LIMITS["max_attempts_per_request"],
                  "provider request failed; source scores were not imputed: " + error)
            self.sleep(2 * number)
        raise AssertionError("unreachable transport attempt")


def _mapping_plan(anchor, eligible):
    if not eligible:
        return []
    accessions = sorted({_accession(anchor), *(_accession(uid) for uid in eligible)})
    return [_request_spec("mapping", "mapping_%02d" % (index + 1), values)
            for index, values in enumerate(_chunks(accessions, LIMITS["mapping_batch_size"]))]


def _network_plan(anchor, eligible, mapping):
    pairs = [{"products": [_accession(anchor), _accession(uid)], "source_row": index + 1}
             for index, uid in enumerate(eligible)]
    plan = []
    for number, indices in enumerate(_chunks(list(range(len(pairs))), LIMITS["neighbor_batch_size"])):
        ids = set()
        for index in indices:
            values = [mapping[product] for product in pairs[index]["products"]]
            if all(value["status"] == "resolved" for value in values):
                endpoints = {value["string_id"] for value in values}
                if len(endpoints) == 2:
                    ids.update(endpoints)
        plan.append({"batch_id": "network_%02d" % (number + 1),
                     "candidate_indices": indices, "string_ids": sorted(ids)})
    return pairs, plan


def _annotations(anchor, identifiers, eligible, mapping, networks, plan):
    pairs, expected_plan = _network_plan(anchor, eligible, mapping)
    _need(expected_plan == plan, "network plan differs from exact mapped candidates.")
    predictions = project_predictions(pairs, mapping, networks, plan)
    by_id = {}
    for uid, prediction in zip(eligible, predictions):
        row = {"protein_id": uid, **prediction}
        batch_id = row["query_batch"]
        row["network_source_row_numbers"] = []
        if batch_id:
            pair = tuple(sorted(mapping[product]["string_id"] for product in row["products"]))
            native = networks[batch_id].get(pair)
            if native is not None:
                row["network_source_row_numbers"] = list(native["source_row_numbers"])
        by_id[uid] = row
    for uid in identifiers:
        if uid not in by_id:
            view = {"state": "not_interaction_path", "native_score": None, "ranking_score": -1.0}
            by_id[uid] = {"protein_id": uid, "products": [_accession(anchor), _accession(uid)],
                         "mapping_states": [], "mapping_proof": [], "query_batch": None,
                         "network_source_row_numbers": [],
                         "views": {"functional": dict(view), "physical": dict(view)}}
    return {uid: by_id[uid] for uid in identifiers}


def collect_ranking(graph, anchor_id, candidates, *, fetcher=None,
                    clock=time.monotonic, sleep=time.sleep):
    """Retrieve optional native ordering; fail on errors rather than ranking failure.

    ``fetcher(url, *, timeout, max_bytes)`` may be injected for tests and returns
    ``{status, headers, url, body: bytes}``. It never receives assay outcomes.
    A complete question's candidate binding includes unqueried pathway rows;
    evidence paths remain in the answer rather than duplicated in this packet.
    """
    binding = _binding(candidates)
    identifiers, eligible = _candidates(anchor_id, binding, graph)
    client = _Client(fetcher or _fetch, clock, sleep, shared_rate=fetcher is None)
    version, mapping, networks = None, {}, {}
    if eligible:
        version = _version(client.request("version", "source_version", []))
    for request in _mapping_plan(anchor_id, eligible):
        raw = client.request("mapping", request["batch_id"], request["identifiers"])
        mapping.update(parse_mapping(raw, request["identifiers"]))
    _, plan = _network_plan(anchor_id, eligible, mapping)
    for batch in plan:
        if batch["string_ids"]:
            raw = client.request("network", batch["batch_id"], batch["string_ids"])
            networks[batch["batch_id"]] = parse_network(raw, batch["string_ids"])
    packet = _seal({
        "format": FORMAT, "source_release": RELEASE, "source_version": version,
        "created_at": utcnow(), "graph_basis_sha256": _basis(graph),
        "snapshot_sha256": graph["snapshot_sha256"], "anchor": anchor_id,
        "requested_candidates": binding, "requested_candidate_ids": identifiers,
        "queried_candidate_ids": eligible, "limits": deepcopy(LIMITS), "profile": dict(PROFILE),
        "mappings": mapping, "network_plan": plan, "requests": client.requests,
        "annotations": _annotations(anchor_id, identifiers, eligible, mapping, networks, plan),
        "limitations": list(LIMITATIONS),
    })
    return verify_packet(packet, graph=graph, candidates=candidates, anchor=anchor_id)


def _verified_body(request, expected, accounting):
    _need(isinstance(request, dict) and set(request) == {*expected, "attempts"}
          and all(request.get(key) == value for key, value in expected.items()),
          "captured request is not bound to the exact supported query.")
    attempts = request["attempts"]
    _need(isinstance(attempts, list) and 1 <= len(attempts) <= LIMITS["max_attempts_per_request"],
          "attempt sequence differs.")
    final_body = None
    fields = {"attempt", "started_monotonic", "status", "headers", "final_url", "error",
              "body_text", "body_bytes", "body_sha256"}
    for number, receipt in enumerate(attempts, 1):
        _need(isinstance(receipt, dict) and set(receipt) == fields and receipt["attempt"] == number,
              "attempt receipt schema or numbering differs.")
        started = receipt["started_monotonic"]
        _need(isinstance(started, (int, float)) and not isinstance(started, bool)
              and math.isfinite(started) and started >= 0, "attempt start time differs.")
        if accounting["last"] is not None:
            _need(started - accounting["last"] + 1e-9 >= LIMITS["minimum_request_interval_seconds"],
                  "captured attempt violates the source request rate.")
        accounting["last"] = started
        _need(isinstance(receipt["body_text"], str), "raw body text is missing.")
        try:
            raw = receipt["body_text"].encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("Physical ranking: invalid preserved UTF-8 response.") from exc
        _need(type(receipt["body_bytes"]) is int and len(raw) == receipt["body_bytes"]
              <= LIMITS["max_body_bytes"] and hashlib.sha256(raw).hexdigest() == receipt["body_sha256"],
              "raw response byte count or checksum differs.")
        accounting["bytes"] += len(raw)
        accounting["attempts"] += 1
        _need(accounting["bytes"] <= LIMITS["max_total_body_bytes"]
              and accounting["attempts"] <= LIMITS["max_http_attempts"],
              "captured transport budget exceeded.")
        status, error = receipt["status"], receipt["error"]
        if status is None:
            _need(receipt["headers"] == {} and receipt["final_url"] is None and raw == b""
                  and isinstance(error, str) and bool(error), "network-error receipt differs.")
        else:
            _need(type(status) is int and 100 <= status <= 599
                  and receipt["final_url"] == expected["url"],
                  "captured HTTP status or redirect differs.")
            _headers(receipt["headers"], raw, status == 200)
        if number == len(attempts):
            _need(status == 200 and error is None, "logical request never completed successfully.")
            final_body = raw
        else:
            _need(status is None or status in LIMITS["retry_statuses"],
                  "nonretryable status was retried.")
            _need((status is None and isinstance(error, str) and bool(error))
                  or error == "HTTP " + str(status), "retry error receipt differs.")
    return final_body


def verify_packet(packet, graph=None, candidates=None, anchor=None):
    """Replay query binding, mappings and annotations from portable raw responses.

    The seal proves content consistency, not remote authenticity. Providing the
    saved graph and complete candidate rows additionally binds their exact basis.
    No code hash pins a packet to an obsolete app implementation.
    """
    fields = {"format", "source_release", "source_version", "created_at", "graph_basis_sha256",
              "snapshot_sha256", "anchor", "requested_candidates", "requested_candidate_ids",
              "queried_candidate_ids", "limits", "profile", "mappings", "network_plan", "requests",
              "annotations", "limitations", "content_sha256"}
    _need(isinstance(packet, dict) and set(packet) == fields, "packet schema differs.")
    payload = {key: value for key, value in packet.items() if key != "content_sha256"}
    _need(packet["format"] == FORMAT and packet["content_sha256"] == digest(payload),
          "packet format or content seal differs.")
    _need(packet["source_release"] == RELEASE and packet["limits"] == LIMITS
          and packet["profile"] == PROFILE and packet["limitations"] == LIMITATIONS,
          "source profile, limits or interpretation differs.")
    try:
        created = datetime.fromisoformat(packet["created_at"].replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Physical ranking: invalid capture time.") from exc
    _need(created.tzinfo is not None and created.utcoffset() == timezone.utc.utcoffset(created),
          "capture time must be UTC.")
    for key in ("graph_basis_sha256", "snapshot_sha256"):
        _need(isinstance(packet[key], str) and re.fullmatch(r"[0-9a-f]{64}", packet[key]),
              "saved graph fingerprint differs.")
    if graph is not None:
        _need(packet["graph_basis_sha256"] == _basis(graph)
              and packet["snapshot_sha256"] == graph["snapshot_sha256"],
              "packet belongs to a different graph or review state.")
    if candidates is not None:
        _need(packet["requested_candidates"] == _binding(candidates), "packet candidate rows differ.")
    if anchor is not None:
        _need(packet["anchor"] == anchor, "packet anchor differs.")
    identifiers, eligible = _candidates(packet["anchor"], packet["requested_candidates"], graph)
    _need(packet["requested_candidate_ids"] == identifiers
          and packet["queried_candidate_ids"] == eligible, "candidate/query coverage differs.")
    requests = packet["requests"]
    _need(isinstance(requests, list) and len(requests) <= LIMITS["max_logical_requests"],
          "logical request collection exceeds its limit.")
    cursor, accounting = 0, {"last": None, "bytes": 0, "attempts": 0}

    def consume(expected):
        nonlocal cursor
        _need(cursor < len(requests), "a planned response is missing.")
        value = _verified_body(requests[cursor], expected, accounting)
        cursor += 1
        return value

    version, mapping, networks = None, {}, {}
    if eligible:
        version = _version(consume(_request_spec("version", "source_version", [])))
    for request in _mapping_plan(packet["anchor"], eligible):
        mapping.update(parse_mapping(consume(request), request["identifiers"]))
    _, plan = _network_plan(packet["anchor"], eligible, mapping)
    for batch in plan:
        if batch["string_ids"]:
            spec = _request_spec("network", batch["batch_id"], batch["string_ids"])
            networks[batch["batch_id"]] = parse_network(consume(spec), batch["string_ids"])
    _need(cursor == len(requests), "packet contains an unplanned extra request.")
    _need(packet["source_version"] == version and packet["mappings"] == mapping
          and packet["network_plan"] == plan, "source replay differs from recorded mapping or plan.")
    annotations = _annotations(packet["anchor"], identifiers, eligible, mapping, networks, plan)
    _need(packet["annotations"] == annotations, "raw source replay differs from ranking annotations.")
    return packet
