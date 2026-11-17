"""Separate, source-bound Pharos detail and identity updates for a saved overlap.

The saved baseline, graph, decisions and overlap report are never rewritten.
Official pair details and a scoped 400 identity table answer different questions;
neither creates independent evidence or updates historical interaction records.
"""
from copy import deepcopy
from html import escape
import json
from pathlib import Path

from .client import ENDPOINT, VERSION, PharosClient, digest, utcnow, write_json
from .evidence_mapping import build_mapping_set, serialize_mapping_set
from .evidence_overlap import _source_files, verify_overlap
from .file_utils import new_output, sha
from .graph import UNIPROT

DETAIL_FORMAT = "biograph-steward.pharos-pair-details.v1"
FORMAT = "biograph-steward.pharos-source-update.v1"
POLICY = "separate-release-identity-and-pair-provenance.v1"


def _pair(overlap):
    pairs = set()
    for row in overlap["records"]:
        products = row.get("products")
        if (not isinstance(products, list) or len(products) != 2
                or any(not isinstance(p, str) or not p.startswith("UniProtKB:")
                       or not UNIPROT.fullmatch(p[10:]) for p in products)):
            raise ValueError("The details check requires exact primary protein pairs.")
        pairs.add(tuple(sorted(p[10:] for p in products)))
    if len(pairs) != 1:
        raise ValueError("This bounded details check requires exactly one saved protein pair.")
    return list(pairs.pop())


def _query(pair):
    # Accessions were checked by _pair; use the already verified official route.
    return ('query SavedPairDetails { forward: listCrossDetails(model:"Target",'
            'crossModel:"Target",modelID:"' + pair[0] + '",crossModelID:"' + pair[1]
            + '") reverse: listCrossDetails(model:"Target",crossModel:"Target",modelID:"'
            + pair[1] + '",crossModelID:"' + pair[0] + '") }')


def _validate_detail_data(details, pair):
    if not isinstance(details, dict) or set(details) != {"forward", "reverse"}:
        raise ValueError("Expected both recorded query directions.")
    for direction, expected in (("forward", pair), ("reverse", pair[::-1])):
        rows = details[direction]
        if not isinstance(rows, list):
            raise ValueError("Pair-details returned no usable list; absence remains unknown.")
        for row in rows:
            if not isinstance(row, dict) or [row.get("uniprot"), row.get("otherUniprot")] != expected:
                raise ValueError("Pair-details returned a different protein identity or direction.")


def capture_pair_details(overlap_path, output, client=None):
    """Three uncached official requests; failure artifacts are kept separately."""
    overlap_path = Path(overlap_path).absolute()
    before = _source_files(overlap_path)
    overlap = verify_overlap(overlap_path)
    pair = _pair(overlap)
    if overlap["pharos_endpoint"] != ENDPOINT:
        raise ValueError("This live check supports only the configured official Pharos endpoint.")
    client = client or PharosClient(cache_dir=None, retries=0, timeout=30)
    if client.endpoint != ENDPOINT or client.records:
        raise ValueError("Use a new client at the official endpoint.")
    contract = {"format": DETAIL_FORMAT, "overlap_report": str(overlap_path),
        "overlap_files_sha256": before, "requested_pair": pair, "endpoint": ENDPOINT,
        "queries": [VERSION, _query(pair), VERSION], "variables": {},
        "cache": False, "baseline_database_version": overlap["pharos_database_version"],
        "selection": "The sole exact pair in an already consumed saved workspace; no outcome-based selection.",
        "maximum_requests": 3, "model_calls": 0}
    folder = new_output(output, overlap_path, overlap["source_workspace"])
    write_json(folder / "request_contract.json", contract)
    receipt = {"format": DETAIL_FORMAT, "request_contract_sha256": sha(folder / "request_contract.json"),
               "started_at": utcnow(), "status": "failed"}
    try:
        first = client.execute(VERSION, cache=False)
        result = client.execute(_query(pair), cache=False)
        _validate_detail_data(result, pair)
        last = client.execute(VERSION, cache=False)
        if not isinstance(first.get("dbVersion"), str) or first != last:
            raise ValueError("Pharos database version changed or was not reported; no trusted supplement produced.")
        receipt.update(status="complete", db_version_before=first["dbVersion"], db_version_after=last["dbVersion"])
        if _source_files(overlap_path) != before:
            raise ValueError("Original overlap changed during source capture.")
    except Exception as exc:
        receipt.update(status="failed", error=str(exc))
        raise
    finally:
        receipt.update(completed_at=utcnow(), requests=deepcopy(client.records))
        receipt["content_sha256"] = digest(receipt)
        write_json(folder / "receipt.json", receipt)
    return verify_pair_details(folder, overlap_path)


def verify_pair_details(folder, overlap_path):
    folder, overlap_path = Path(folder).absolute(), Path(overlap_path).absolute()
    inventory = _source_files(folder)
    if set(inventory) != {"request_contract.json", "receipt.json"}:
        raise ValueError("Unexpected pair-details intake files.")
    contract = json.loads((folder / "request_contract.json").read_text())
    value = json.loads((folder / "receipt.json").read_text())
    overlap = verify_overlap(overlap_path)
    pair = _pair(overlap)
    if (value.get("format") != DETAIL_FORMAT or value.get("status") != "complete"
            or value.get("content_sha256") != digest({k: v for k, v in value.items() if k != "content_sha256"})
            or value.get("request_contract_sha256") != inventory["request_contract.json"]
            or contract.get("format") != DETAIL_FORMAT or contract.get("endpoint") != ENDPOINT
            or overlap["pharos_endpoint"] != ENDPOINT
            or contract.get("requested_pair") != pair
            or contract.get("overlap_report") != str(overlap_path)
            or contract.get("overlap_files_sha256") != _source_files(overlap_path)
            or contract.get("queries") != [VERSION, _query(pair), VERSION]
            or contract.get("variables") != {} or contract.get("cache") is not False
            or contract.get("maximum_requests") != 3
            or contract.get("baseline_database_version") != overlap["pharos_database_version"]):
        raise ValueError("Pair-details receipt or original overlap binding changed.")
    requests = value.get("requests")
    if not isinstance(requests, list) or len(requests) != 3:
        raise ValueError("Pair-details request sequence is incomplete.")
    for row, query in zip(requests, contract["queries"]):
        if (row.get("endpoint") != ENDPOINT or row.get("request") != {"query": query, "variables": {}}
                or row.get("loaded_from_cache") is not False
                or row.get("response_sha256") != digest(row.get("response"))):
            raise ValueError("Pair-details request/response integrity failed.")
        PharosClient._validate_response(row["response"])
    version = requests[0]["response"]["data"].get("dbVersion")
    if (not isinstance(version, str) or not version
            or requests[2]["response"]["data"] != {"dbVersion": version}
            or value.get("db_version_before") != version or value.get("db_version_after") != version):
        raise ValueError("Pair-details database version drift.")
    _validate_detail_data(requests[1]["response"]["data"], pair)
    return value


def _implementation():
    from . import pharos400_identity, evidence_mapping, client, file_utils
    return {"pharos_source_update": sha(__file__), "pharos400_identity": sha(pharos400_identity.__file__),
            "evidence_mapping": sha(evidence_mapping.__file__), "client": sha(client.__file__),
            "file_utils": sha(file_utils.__file__)}


def _payload(overlap_path, details_path, identities_path, mapping_date):
    from .pharos400_identity import verify_intake, build_endpoints
    overlap = verify_overlap(overlap_path)
    details = verify_pair_details(details_path, overlap_path)
    intake = verify_intake(identities_path)
    identity = build_endpoints(intake, role="added")
    pair = _pair(overlap)
    # The producer must not silently widen the requested biological cohort.
    if sorted(intake["requested_accessions"]) != sorted(set(pair)):
        raise ValueError("The 400 intake must cover exactly the saved development pair.")
    source = Path(overlap["source_workspace"])
    snapshot = json.loads((source / "snapshot.json").read_text())
    endpoints = [{"endpoint_id": "snapshot_target:" + str(i), "role": "baseline",
        "resource_id": snapshot["endpoint"], "resource_version": snapshot["db_version"],
        "record_locator": "urn:sha256:" + sha(source / "snapshot.json") + "#/targets/" + str(i),
        "entity_type": "protein", "identity_role": "source_primary", "primary_ids": ["UniProtKB:" + r["uniprot"]]}
        for i, r in enumerate(snapshot["targets"]) if r["uniprot"] in pair]
    mappings = build_mapping_set(endpoints + identity["endpoints"],
        mapping_set_id="urn:sha256:" + digest([overlap["content_sha256"], intake]),
        mapping_set_version=POLICY, license_url="https://opensource.org/licenses/MIT", mapping_date=mapping_date)
    raw_details = details["requests"][1]["response"]["data"]
    detail_rows = [dict(direction=d, **r) for d, rows in raw_details.items() for r in rows]
    nulls = {key: sum(key in r and r[key] is None for r in detail_rows) for key in ("evidence", "interaction_type")}
    detail_status = {
        "requested_pair": pair, "database_version": details["db_version_before"],
        "baseline_database_version": overlap["pharos_database_version"],
        "same_release_label": details["db_version_before"] == overlap["pharos_database_version"],
        "capture_is_separate_from_baseline": True, "directional_rows": len(detail_rows),
        "explicit_null_counts": nulls, "rows": detail_rows,
        "evidence_interpretation": "No free text or provider name was promoted to an interaction or experiment identifier.",
        "baseline_record_identity_overlap": None, "baseline_experiment_identity_overlap": None,
        "experiment_lineage": "unresolved", "independent_evidence_count": None}
    records = [{k: deepcopy(row[k]) for k in ("observation_id", "products", "pair_representation",
        "shared_supporting_publication_identifiers", "baseline_record_identity_overlap",
        "baseline_experiment_identity_overlap", "additional_context_fields_available", "experiment_lineage")}
        for row in overlap["records"]]
    annotations = []
    for endpoint in identity["endpoints"]:
        row = endpoint["source_row"]["row"]
        # Compare annotations only where the adapter authorized exact primary
        # identity. A shared base or label cannot select a baseline product.
        exact = (endpoint["primary_ids"][0][10:] if endpoint["identity_role"] == "source_primary" else None)
        matches = [r for r in snapshot["targets"] if r["uniprot"] == exact]
        annotations.append({"source_record_locator": endpoint["record_locator"],
            "source_internal_row_id": row["id"], "source_uniprot_id": row["uniprot_id"],
            "source_isoform": row["uniprot_isoform"], "source_grouping": row["canonical_isoform_status"],
            "pharos400_tdl": row["tdl"], "pharos400_version": "pharos400",
            "baseline_tdl": matches[0].get("tdl") if len(matches) == 1 else None,
            "baseline_version": snapshot["db_version"], "exact_identifier_correspondence": len(matches) == 1,
            "unresolved_reasons": deepcopy(endpoint["identity_resolution"]["unresolved_reasons"])})
    return {"format": FORMAT, "policy": POLICY, "mapping_date": mapping_date,
        "original_overlap_content_sha256": overlap["content_sha256"],
        "original_overlap_summary": deepcopy(overlap["summary"]), "records": records,
        "pair_details": detail_status, "identity_intake": intake, "identity_projection": identity,
        "identity_tdl_comparison": annotations,
        "baseline_target_annotations": [{"uniprot": r["uniprot"], "tdl": r.get("tdl"),
            "source_version": snapshot["db_version"]} for r in snapshot["targets"] if r["uniprot"] in pair],
        "mappings": mappings,
        "summary": {"workspace_observations": len(records), "pair_details_directional_rows": len(detail_rows),
            "pair_details_null_evidence_rows": nulls["evidence"],
            "mapping_rows": mappings["summary"]["mapping_rows"],
            "unresolved_mapping_endpoints": mappings["summary"]["unresolved_endpoints"],
            "experiment_lineage": "unresolved", "independent_evidence_count": None,
            "baseline_modified": False, "graph_relationships_updated": 0,
            "automatic_merges": 0, "automatic_pruning": 0, "model_calls": 0,
            "scientific_accuracy_measured": False},
        "limitations": [
            "The original baseline and overlap report remain unchanged; these are separately captured source supplements.",
            "Matching database release labels do not certify an atomic snapshot or identical upstream records.",
            "Reciprocal detail views are not independent experiments. Null evidence does not prove absence of supporting studies.",
            "Nonempty free-text evidence would need verified identifier semantics before it could resolve overlap.",
            "400 identity/TDL annotation rows do not refresh 319 interaction evidence or establish isoform-specific activity.",
            "Unmapped product rows remain unresolved. A shared base accession does not establish product equivalence.",
            "Independent experimental support, biological accuracy and predictive benefit remain unverified."]}


def _html(value):
    e = lambda v: escape(str(v))
    detail = value["pair_details"]
    inputs = value["input_directories"]
    source_links = " · ".join("<a href='" + e((Path(inputs[key]) / name).as_uri()) + "'>" + label + "</a>"
        for key, name, label in (("overlap", "index.html", "Original overlap report"),
            ("details", "receipt.json", "Pharos details receipt"),
            ("identities", "selected_rows.json", "Selected 400 rows"),
            ("identities", "http_receipt.json", "400 download receipt")))
    body = ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Pharos source update</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:1100px;margin:36px auto;padding:0 20px;color:#182734}"
        "table{border-collapse:collapse;width:100%;margin:18px 0}td,th{padding:10px;border:1px solid #ccd5de;text-align:left}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;padding:14px}a{color:#075b9a}</style>"
        "<h1>Pharos source update</h1><p>A separate identity and provenance supplement to the saved evidence graph.</p>"
        "<p><strong>Experimental independence remains unresolved. The original graph and its relationships are unchanged.</strong></p>"
        "<p>Captured inputs: " + source_links + "</p>"
        "<p><a href='report.json'>Full report</a> · <a href='records.jsonl'>Observation overlap</a> · "
        "<a href='mappings.sssom.tsv'>319–400 SSSOM correspondence</a> · "
        "<a href='mappings.json'>Mapping decisions and unresolved identifiers</a></p>"
        "<h2>Current pair: richer Pharos details</h2><p>" + e(" ↔ ".join(detail["requested_pair"]))
        + ". Source release: " + e(detail["database_version"]) + ". Separate current capture; "
        + e(detail["directional_rows"]) + " directional views, not independent evidence.</p><pre>"
        + e(json.dumps(detail["rows"], indent=2)) + "</pre>"
        "<h2>Pharos400 identity / TDL source</h2><p>Internal row IDs locate source records; "
        "they are not new public protein identifiers. These annotations do not change the interaction graph.</p>"
        "<table><thead><tr><th>400 accession / isoform</th><th>400 grouping</th><th>Baseline TDL</th>"
        "<th>400 TDL</th><th>Identifier correspondence</th></tr></thead><tbody>"
        + "".join("<tr><td>" + e(r["source_uniprot_id"] + (" / " + r["source_isoform"] if r["source_isoform"] else ""))
            + "</td><td>" + e(r["source_grouping"]) + "</td><td>" + e(r["baseline_tdl"] or "Unresolved")
            + " (" + e(r["baseline_version"]) + ")</td><td>" + e(r["pharos400_tdl"])
            + " (pharos400)</td><td>" + e("Exact primary identifier" if r["exact_identifier_correspondence"] else "Unresolved")
            + "</td></tr>" for r in value["identity_tdl_comparison"])
        + "</tbody></table><p>The complete-source SHA and scan counts were recorded during download. "
        "The full CSV was not retained; offline verification checks preserved selected records, not selection completeness.</p>"
        "<details><summary>Selected source records and download receipt</summary><pre>"
        + e(json.dumps(value["identity_intake"], indent=2)) + "</pre></details>"
        "<h3>Source-specific annotation and mapping account</h3><pre>"
        + e(json.dumps({"baseline": value["baseline_target_annotations"],
            "400_identity_projection": value["identity_projection"], "mapping_summary": value["mappings"]["summary"]}, indent=2))
        + "</pre><h2>What happened to the existing evidence overlap?</h2><table><thead><tr><th>Observation</th><th>Pair representation</th><th>Experiment lineage</th></tr></thead><tbody>")
    body += "".join("<tr><td>" + e(r["observation_id"]) + "</td><td>" + e(r["pair_representation"])
                    + "</td><td>" + e(r["experiment_lineage"]) + "</td></tr>" for r in value["records"])
    return body + "</tbody></table><h2>Limits</h2><ul>" + "".join("<li>" + e(s) + "</li>" for s in value["limitations"]) + "</ul></html>"


def _files(value):
    encode = lambda v: (json.dumps(v, indent=2, ensure_ascii=True) + "\n").encode()
    return {"report.json": encode(value), "mappings.json": encode(value["mappings"]),
            "mappings.sssom.tsv": serialize_mapping_set(value["mappings"]),
            "records.jsonl": b"".join((json.dumps(r, sort_keys=True) + "\n").encode() for r in value["records"]),
            "index.html": _html(value).encode()}


def publish_source_update(overlap, details, identities, output):
    paths = {name: str(Path(path).absolute()) for name, path in
             (("overlap", overlap), ("details", details), ("identities", identities))}
    before = {name: _source_files(Path(path)) for name, path in paths.items()}
    value = _payload(*(Path(paths[n]) for n in ("overlap", "details", "identities")), utcnow()[:10])
    value.update(input_directories=paths, input_files_sha256=before)
    value["content_sha256"] = digest(value)
    if before != {name: _source_files(Path(path)) for name, path in paths.items()}:
        raise ValueError("Source update inputs changed during publication.")
    original = json.loads((Path(paths["overlap"]) / "report.json").read_text())["source_workspace"]
    folder = new_output(output, *paths.values(), original)
    files = _files(value)
    for name, raw in files.items():
        (folder / name).write_bytes(raw)
    manifest = {"format": FORMAT, "implementation_sha256": _implementation(),
                "files": {name: sha(folder / name) for name in files}}
    manifest["content_sha256"] = digest(manifest)
    write_json(folder / "manifest.json", manifest)
    verify_source_update(folder)
    return value


def verify_source_update(output):
    folder = Path(output).absolute()
    inventory = _source_files(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    if (manifest.get("format") != FORMAT or manifest.get("content_sha256") != digest({k: v for k, v in manifest.items() if k != "content_sha256"})
            or manifest.get("implementation_sha256") != _implementation()
            or set(inventory) != set(manifest["files"]) | {"manifest.json"}
            or any(inventory[name] != pin for name, pin in manifest["files"].items())):
        raise ValueError("Source update inventory or implementation changed.")
    recorded = json.loads((folder / "report.json").read_text())
    paths = recorded["input_directories"]
    before = {name: _source_files(Path(path)) for name, path in paths.items()}
    if before != recorded["input_files_sha256"]:
        raise ValueError("Source update input files changed.")
    value = _payload(*(Path(paths[n]) for n in ("overlap", "details", "identities")), recorded["mapping_date"])
    value.update(input_directories=paths, input_files_sha256=before)
    value["content_sha256"] = digest(value)
    if (value != recorded or any((folder / name).read_bytes() != raw for name, raw in _files(value).items())
            or before != {name: _source_files(Path(path)) for name, path in paths.items()}):
        raise ValueError("Source update classifications do not replay from the recorded inputs.")
    return recorded
