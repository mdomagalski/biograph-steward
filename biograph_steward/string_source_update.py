"""Publish and replay a bounded, separately versioned STRING source update.

The existing typed API parsers establish source meaning. This adapter adds no
score formula, biological truth label or independent experiment count. A saved
whole-cohort fingerprint is the supported intake; nominated-pair captures are
not silently promoted to whole-network coverage.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from html import escape
from itertools import combinations
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from .assay_attachment import _capture, _decode, _ordinary, _sealed
from .client import digest, utcnow, write_json
from .file_utils import new_output
from .graph import UNIPROT
from .string_component import parse_mapping, parse_network

FORMAT = "biograph-steward.string-source-update-publication.v1"
PROJECTION_FORMAT = "biograph-steward.string-source-update-projection.v1"
POLICY = "string12.5-whole-declared-cohort-functional400.v1"
CAPTURE_FORMAT = "biograph-steward.current-string-source-fingerprint.v1"
RELEASE = "12.5"
THRESHOLD = 0.4
BASE = "https://version-12-5.string-db.org/api/tsv/"
PROFILE = {"required_score": "0", "network_type": "functional", "network_flavor": "typed",
           "typed_physical_edges": "1", "typed_regulatory_edges": "0", "add_nodes": "0"}
SOURCE_LICENSE = {"source": "STRING database version 12.5",
    "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "source_terms_url": "https://www.string-db.org/cgi/access",
    "note": "Attribute STRING and version 12.5. The workbench adds mappings and scope qualifications; material incorporated from other providers retains their original terms."}
LIMITATIONS = [
    "This is a versioned source supplement to an unchanged Pharos snapshot, not a replacement or independent experiment.",
    "STRING functional association is not direct binding, tissue-specific biology, clinical relevance or experimental validation.",
    "Native physical annotations describe proximity/co-complex support and do not establish direct binding.",
    "Mapping is STRING best-match locus correspondence, not sequence, isoform or construct equivalence.",
    "A missing row, unresolved identifier or score below the declared threshold is not evidence that an interaction is absent.",
    "The complete declared cohort is queried, but this typed functional profile is not a complete standalone physical network.",
    "STRING already contributes to Pharos. Study-level reuse remains unresolved; source records are not independent support counts.",
]
REQUIRED = {"protocol.json", "get_string_ids.tsv", "get_string_ids.receipt.json", "mappings.json",
            "resolved_network_request.json", "network.tsv", "network.receipt.json", "parsed_network.json"}


def _need(ok, message):
    if not ok:
        raise ValueError("STRING source update: " + message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(files, name):
    try:
        return _decode(files["capture/" + name])
    except KeyError as exc:
        raise ValueError("STRING source update: incomplete preserved source capture.") from exc


def _receipt(files, method, parameters):
    row = _json(files, method + ".receipt.json")
    url = BASE + method + "?" + urlencode(parameters)
    _need(_sealed(row) and row.get("parameters") == parameters and row.get("status") == 200
          and row.get("url") == row.get("final_url") == url
          and row.get("body_file") == method + ".tsv", "source request/receipt changed.")
    raw = files["capture/" + method + ".tsv"]
    _need(len(raw) == row.get("body_bytes") and len(raw) <= 4194304
          and _sha(raw) == row.get("body_sha256"), "source response bytes changed.")
    headers = row.get("headers")
    _need(isinstance(headers, dict) and all(isinstance(k, str) and isinstance(v, str)
          for k, v in headers.items()), "invalid source response headers.")
    lower = {key.lower(): value for key, value in headers.items()}
    _need(len(lower) == len(headers) and lower.get("string-api-version") == "2"
          and lower.get("content-type", "").lower().startswith("text/tab-separated-values")
          and lower.get("content-encoding", "identity").lower() == "identity",
          "unsupported source transport/version framing.")
    length = lower.get("content-length")
    _need(length is None or (length.isascii() and length.isdecimal() and int(length) == len(raw)),
          "source Content-Length changed.")
    return raw, row


def _projection(files):
    _need(REQUIRED <= {name[8:] for name in files if name.startswith("capture/")},
          "whole-cohort capture is incomplete.")
    protocol = _json(files, "protocol.json")
    _need(_sealed(protocol) and protocol.get("format") == CAPTURE_FORMAT,
          "expected a whole-declared-cohort fingerprint, not a candidate-only capture.")
    accessions = protocol.get("accessions")
    _need(isinstance(accessions, list) and 2 <= len(accessions) <= 250
          and accessions == sorted(set(accessions))
          and all(isinstance(a, str) and UNIPROT.fullmatch(a) for a in accessions),
          "invalid or unbounded source accession scope.")
    rules = protocol.get("rules", {})
    _need(all(rules.get(k) == v for k, v in {**PROFILE, "release": RELEASE, "species": "9606",
          "mapping_echo_query": "1"}.items()) and rules.get("max_requests") == 2
          and rules.get("assay_outcomes_loaded") is False and rules.get("inference_calls") == 0,
          "source capture profile changed.")
    historical = protocol.get("implementation_sha256")
    bindings = protocol.get("source_files_sha256")
    _need(isinstance(historical, dict) and historical and isinstance(bindings, dict)
          and {"graph.json", "snapshot.json", "targets.tsv", "run_manifest.json"} <= set(bindings)
          and all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
                  for v in [*historical.values(), *bindings.values()]), "historical source/code pins missing.")
    # Historical implementation pins describe the capture. Today's parser replay
    # is additional verification; a subsequent code edit is not source corruption.
    params = {"identifiers": "\r".join(accessions), "species": "9606", "echo_query": "1",
              "caller_identity": "biograph-steward"}
    _need(protocol.get("mapping_request") == {"method": "get_string_ids", "parameters": params},
          "mapping scope changed.")
    raw_mapping, mapping_receipt = _receipt(files, "get_string_ids", params)
    mappings = parse_mapping(raw_mapping, accessions)
    _need(_json(files, "mappings.json") == mappings, "saved mappings do not replay.")
    representatives = sorted({m["string_id"] for m in mappings.values() if m["status"] == "resolved"})
    _need(len(representatives) >= 2, "network capture has fewer than two mapped representatives.")
    params = {"identifiers": "\r".join(representatives), "species": "9606",
              "caller_identity": "biograph-steward", **PROFILE}
    request = _json(files, "resolved_network_request.json")
    _need(_sealed(request) and request.get("protocol_sha256") == protocol["content_sha256"]
          and request.get("string_ids") == representatives and request.get("parameters") == params
          and request.get("declared_before_network_request") is True,
          "whole-cohort network request changed.")
    raw_network, network_receipt = _receipt(files, "network", params)
    network = parse_network(raw_network, representatives)
    serialized = [{"pair": list(k), **v} for k, v in sorted(network.items())]
    _need(_json(files, "parsed_network.json") == serialized, "saved network does not replay.")
    by_sid = defaultdict(list)
    for accession, mapping in mappings.items():
        if mapping["status"] == "resolved":
            by_sid[mapping["string_id"]].append(accession)
    ledger = []
    for a, b in combinations(accessions, 2):
        mapped = [mappings[a], mappings[b]]
        sids = [m["string_id"] for m in mapped]
        row = None
        if any(m["status"] != "resolved" for m in mapped):
            state = "unresolved_endpoint"
        elif len(set(sids)) != 2:
            state = "collapsed_pair"
        elif any(len(by_sid[sid]) != 1 for sid in sids):
            state = "ambiguous_locus_correspondence"
        else:
            row = network.get(tuple(sorted(sids)))
            state = ("no_returned_functional_row" if row is None else
                     "functional_score_below400" if row["functional_combined_score"] < THRESHOLD else
                     "qualifying_functional_association")
        products = ["UniProtKB:" + a, "UniProtKB:" + b]
        ledger.append({"observation_id": "string-source:" + digest([RELEASE, products])[:24],
            "products": products, "state": state, "mapping_states": [m["status"] for m in mapped],
            "string_ids": sids, "functional_score": row["functional_combined_score"] if row else None,
            "physical_score": row["physical_combined_score"] if row else None,
            "network_row_numbers": row["source_row_numbers"] if row else [],
            "source_row": deepcopy(row),
            "mapping_proof": [deepcopy(m) for m in mapped]})
    value = {"format": PROJECTION_FORMAT, "policy": POLICY, "source_kind": "string_typed_network",
        "source_release": RELEASE, "scope": {"kind": "whole_declared_cohort_typed_functional_network",
            "accessions": accessions, "possible_unordered_pairs": len(ledger), "add_nodes": 0},
        "bindings": {"capture_protocol_sha256": protocol["content_sha256"],
            "historical_implementation_sha256": historical,
            "baseline_source_files_sha256": bindings,
            "source_sha256": {"mapping": _sha(raw_mapping), "network": _sha(raw_network)},
            "request_receipts_sha256": {m: _sha(files["capture/" + m + ".receipt.json"])
                                        for m in ("get_string_ids", "network")}},
        "retrieval": {"mapping_url": mapping_receipt["url"], "network_url": network_receipt["url"],
            "started_at": mapping_receipt.get("started_at"), "finished_at": network_receipt.get("finished_at")},
        "mappings": mappings, "pair_ledger": ledger,
        "summary": {"requested_accessions": len(accessions), "provider_representatives": len(representatives),
            "mapping_status_counts": dict(sorted(Counter(m["status"] for m in mappings.values()).items())),
            "source_network_pairs": len(network), "possible_unordered_pairs": len(ledger),
            "pair_states": dict(sorted(Counter(r["state"] for r in ledger).items())),
            "selection_threshold": THRESHOLD, "assay_outcomes_used_for_selection": False},
        "source_license": deepcopy(SOURCE_LICENSE), "limitations": list(LIMITATIONS)}
    value["content_sha256"] = digest(value)
    return value


def publish_capture(capture, output):
    """Publish an existing capture without retrieval, model calls or graph edits."""
    capture = Path(capture).absolute()
    _need(capture.is_dir() and not any(p.is_symlink() for p in (capture, *capture.parents)),
          "capture must be an ordinary directory.")
    material = {}
    for path in sorted(capture.iterdir()):
        _need(path.is_file() and not path.is_symlink(), "capture must contain ordinary flat source files.")
        material["capture/" + path.name] = _ordinary(path)
    projection = _projection(material)
    folder = new_output(output, capture)
    for name, raw in material.items():
        path = folder / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
    write_json(folder / "projection.json", projection)
    (folder / "LICENSE.txt").write_text("STRING 12.5 data: CC BY 4.0. Attribute STRING and version 12.5.\n"
        "https://creativecommons.org/licenses/by/4.0/\nhttps://www.string-db.org/cgi/access\n"
        "Projection and qualifications are added by BioGraph Steward. Incorporated third-party material retains its original terms.\n")
    (folder / "index.html").write_text("<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>STRING source supplement</title><h1>STRING 12.5 source supplement</h1>"
        "<p>Separate source evidence for the complete declared cohort; no Pharos records are replaced.</p>"
        "<pre>" + escape(json.dumps(projection["summary"], indent=2)) + "</pre>"
        "<p>Functional associations and native physical annotations do not establish direct binding or independent experimental support.</p>"
        "<a href='projection.json'>Complete source and pair ledger</a></html>")
    files = {p.relative_to(folder).as_posix(): _sha(p.read_bytes()) for p in sorted(folder.rglob("*")) if p.is_file()}
    manifest = {"format": FORMAT, "created_at": utcnow(), "policy": POLICY,
        "source_kind": projection["source_kind"], "source_release": RELEASE,
        "baseline_source_files_sha256": deepcopy(projection["bindings"]["baseline_source_files_sha256"]),
        "bindings": deepcopy(projection["bindings"]), "summary": deepcopy(projection["summary"]),
        "source_license": deepcopy(SOURCE_LICENSE), "files": files,
        "baseline_modified": False, "automatic_pruning": False,
        "independent_validation_performed": False, "model_calls": 0}
    manifest["content_sha256"] = digest(manifest)
    write_json(folder / "publication.json", manifest)
    return load_publication(folder)[0]


def load_publication(path):
    """Verify all saved bytes and repeat the dependency-backed projection."""
    manifest, files = _capture(path, "publication.json")
    _need(manifest.get("format") == FORMAT and manifest.get("policy") == POLICY
          and manifest.get("model_calls") == 0
          and all(manifest.get(k) is False for k in
                  ("baseline_modified", "automatic_pruning", "independent_validation_performed")),
          "unsupported publication contract.")
    _need({"projection.json", "index.html", "LICENSE.txt"} <= set(files), "publication is incomplete.")
    projection = _projection(files)
    _need(_decode(files["projection.json"]) == projection
          and manifest.get("bindings") == projection["bindings"]
          and manifest.get("summary") == projection["summary"]
          and manifest.get("source_kind") == projection["source_kind"]
          and manifest.get("source_release") == RELEASE
          and manifest.get("baseline_source_files_sha256") == projection["bindings"]["baseline_source_files_sha256"]
          and manifest.get("source_license") == SOURCE_LICENSE,
          "publication differs from source parser replay.")
    return manifest, projection, files


def prepare(snapshot, baseline_graph, manifest, projection):
    """Project source evidence onto existing exact cohort nodes; never mutate."""
    _need(_sealed(manifest) and _sealed(projection) and manifest.get("format") == FORMAT
          and manifest.get("bindings") == projection.get("bindings")
          and manifest.get("summary") == projection.get("summary")
          and projection.get("format") == PROJECTION_FORMAT and projection.get("policy") == POLICY,
          "projection and publication binding differs.")
    _need(_sealed(snapshot) and snapshot.get("data_kind") == "live_pharos"
          and baseline_graph.get("snapshot_sha256") == snapshot["content_sha256"],
          "expected the bound live Pharos snapshot and graph.")
    accessions = {row["uniprot"] for row in snapshot["targets"]}
    _need(accessions == set(projection["scope"]["accessions"]), "capture does not cover exactly this source cohort.")
    nodes = {row["id"] for row in baseline_graph["nodes"] if row.get("category") == "biolink:Protein"}
    old_pairs = {tuple(sorted((e["subject"], e["object"]))) for e in baseline_graph["edges"]
                 if e.get("record_kind") == "protein_interaction"}
    edges, observations = [], []
    for source in projection["pair_ledger"]:
        observation = deepcopy(source)
        pair = tuple(source["products"])
        observation["baseline_pair_present"] = pair in old_pairs
        observation["graph_edge_id"] = None
        if not set(pair) <= nodes:
            observation["integration_state"] = "endpoint_outside_resolved_cohort"
        elif source["state"] != "qualifying_functional_association":
            observation["integration_state"] = source["state"]
        else:
            observation["integration_state"] = "additional_versioned_source_record" if pair in old_pairs else "new_workspace_pair"
            record = {"source_release": RELEASE, "functional_score": source["functional_score"],
                "physical_score": source["physical_score"], "source_row": deepcopy(source["source_row"]),
                "mapping_proof": deepcopy(source["mapping_proof"]), "observation_id": source["observation_id"]}
            eid = "edge:" + digest({"source": "STRING", "release": RELEASE, "products": list(pair),
                "publication_sha256": manifest["content_sha256"], "record": record})[:20]
            observation["graph_edge_id"] = eid
            rownums = source["network_row_numbers"]
            locators = ["extension_sources/string/capture/network.tsv#row=" + str(n) for n in rownums]
            edges.append({"id": eid, "subject": pair[0], "object": pair[1],
                "predicate": "biograph:has_interaction_annotation", "record_kind": "protein_interaction",
                "status": "passed_structural_checks", "review_reasons": [],
                "aggregator": "STRING", "primary_source_raw": "STRINGDB", "evidence_sources": ["STRINGDB"],
                "reference_raw": None, "publications": [], "evidence_raw": None,
                "source_scores_raw": {"functional_combined_score": source["functional_score"],
                    "physical_combined_score": source["physical_score"]},
                "evidence_record": record, "record_locators": locators, "source_record_count": 1,
                "duplicate_count": 0, "symmetric": True,
                "qualifiers": {"evidence_type": "STRING12.5functional_association"},
                "snapshot_sha256": snapshot["content_sha256"], "data_kind": "published_database_annotations",
                "biologically_validated": False,
                "source_publication_sha256": manifest["content_sha256"],
                "extension_source_kind": "string",
                "extension_publication_sha256": manifest["content_sha256"],
                "retrieval_provenance": {"aggregator": "STRING", "database_version": RELEASE,
                    "source_responses": ["extension_sources/string/capture/network.receipt.json"],
                    "capture_protocol_sha256": projection["bindings"]["capture_protocol_sha256"]},
                "normalization_notes": ["Native versioned STRING functional annotation; physical overlay remains a source annotation. No direct binding or independent experiment is inferred.",
                    "Reciprocal TSV rows are two views of one source association; the original Pharos evidence and scores remain unchanged."]})
        observations.append(observation)
    summary = {**deepcopy(projection["summary"]),
        "publication_sha256": manifest["content_sha256"], "source_release": RELEASE,
        "additional_source_records": len(edges),
        "new_workspace_pairs": sum(o["integration_state"] == "new_workspace_pair" for o in observations),
        "existing_workspace_pairs_with_new_source_record": sum(o["integration_state"] == "additional_versioned_source_record" for o in observations),
        "integration_state_counts": dict(sorted(Counter(o["integration_state"] for o in observations).items())),
        "independent_evidence_count": None, "automatic_acceptance_performed": False,
        "automatic_pruning_performed": False, "biological_validation_performed": False,
        "source_license": deepcopy(SOURCE_LICENSE), "limitations": list(LIMITATIONS)}
    return {"nodes": [], "edges": edges, "observations": observations, "summary": summary}
