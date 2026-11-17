#!/usr/bin/env python3
"""Offline exact publisher-revision coverage and literal historical membership.

Use official, checksum-pinned legacy GPML archives, the reviewed author schema
and existing human identifier registries. Original graphs/reviews are never
changed. This is source-content inspection, not independent biological gold.
"""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.cohort_mapping import SOURCES as REGISTRY_FILES, load_registry
from biograph_steward.file_utils import new_output, sha
from tools.pathway_history.models import (FULL_ID, archive_member_id, assess_subject,
                                         inspect_model, need, official_schema_validator)

FORMAT = "biograph-steward.historical-WikiPathways-content-verification.v1"
SOURCES_FORMAT = "biograph-steward.historical-WikiPathways-archive-inputs.v1"
INVENTORY_FORMAT = "biograph-steward.WikiPathways-historical-version-inventory.v1"
REVIEWED_PINS = {
    "archive_exporter": "b85b37cb30de8d4fd53576620e2b59d52617eefdd4ccd2ba7a1fbbab25efec6b",
    "monthly_release_producer": "7493c88ffcc77a720e8cbb4add8d613ed863c2b8d4e713bfaad0254fa3f54490",
    "gpml2013a_schema": "4a39d0b7b99489376f3c7dada8b9510899be653e5e2d859cebe81809c074c122",
}
STATUSES = ("explicitly_encoded_protein_xref", "compatible_gene_level_xref", "unresolved")
LIMITATIONS = [
    "Exact native archive-member revision binds publisher-supplied content; the GPML Version attribute is separate optional GenMAPP author/export metadata.",
    "The prior assumption that legacy XML Version must equal WPID_rREV was invalid under the released author schema and archive exporter.",
    "An absent model or matching identifier is unresolved, not a negative biological assertion or automatic pruning reason.",
    "Gene-level cross-reference compatibility uses current frozen human registries, not verified historical gene/protein or isoform equivalence.",
    "Literal protein encoding establishes presence of that identifier in the native model, not direct interaction, causation, an assayed construct or a true universal biological role.",
    "Groups, families, linked pathways, nonprotein entities, modifications and unsupported identifiers remain preserved without hierarchy expansion or orthology transfer.",
    "Source annotation/current-release disagreement can reflect release evolution; current-source exclusion does not refute historical content.",
    "Repeated evidence rows are preserved and counted separately from unique subject/version connections and distinct model versions.",
    "The publisher archives are source evidence, not an independent test reference; no scientific truth labels, predictive benefit or graph pruning are established.",
    "Source receipts/hash consistency do not independently authenticate an arbitrary asserted publisher or clear all downstream redistribution rights.",
]


def pinned(path, expected):
    path = Path(path)
    need(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "invalid input SHA256 pin.")
    need(path.is_file() and not path.is_symlink() and sha(path) == expected, "input missing or changed: " + path.name)
    return path


def sealed(path, expected, format_name):
    value = gold_packet._read(pinned(path, expected))
    need(gold_packet._sealed(value) and value.get("format") == format_name, "input format or seal differs.")
    return value


def write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def verify_inventory(value):
    graph_path = pinned(value["source_graph_path"], value["source_graph_file_sha256"])
    graph = gold_packet._read(graph_path)
    current_path = pinned(value["current_source_view_report_path"], value["current_source_view_report_file_sha256"])
    current = gold_packet._read(current_path)
    need(gold_packet._sealed(current) and current.get("format") == "biograph-steward.current-wikipathways-view.v1"
         and current["content_sha256"] == value["current_source_view_content_sha256"],
         "current-source decision report binding differs.")
    current_decisions = {r["edge_id"]: r["decision"] for r in current["source_decisions"]}
    rows = {e["id"]: e for e in graph["edges"] if e.get("record_kind") == "pathway_membership"
            and e.get("evidence_record", {}).get("type") == "WikiPathways"}
    seen, full_ids = set(), set()
    for resource in value["versions"]:
        full_id = resource.get("full_source_id")
        need(isinstance(full_id, str) and FULL_ID.fullmatch(full_id) and full_id not in full_ids
             and resource.get("provider") == "WikiPathways" and resource.get("evidence_edges")
             and isinstance(resource.get("canonical_wpid"), str)
             and isinstance(resource.get("requested_revision"), str)
             and resource["canonical_wpid"] + "_r" + resource["requested_revision"] == full_id,
             "invalid or repeated full source version.")
        full_ids.add(full_id)
        for row in resource["evidence_edges"]:
            edge = rows.get(row["edge_id"])
            need(edge is not None and row["edge_id"] not in seen
                 and edge["subject"] == row["subject"] and edge["assertion_id"] == row["assertion_id"]
                 and edge["object"] == row["local_object"]
                 and edge["evidence_record"]["sourceID"] == full_id
                 and digest(edge["evidence_record"]) == row["raw_record_sha256"]
                 and edge["record_locators"] == row["source_locators"]
                 and row["current_membership_decision"] in {"keep", "prune", "abstain"}
                 and current_decisions.get(row["edge_id"]) == row["current_membership_decision"],
                 "inventory row does not bind its exact original source edge.")
            seen.add(row["edge_id"])
    need(seen == set(rows) and len(full_ids) == value["distinct_version_count"]
         and len(rows) == value["native_edge_count"], "inventory is not the complete original Wiki scope.")
    return graph_path


def _input_path(root, item):
    need(gold_packet._safe_relative(item.get("file")), "unsafe input relative path.")
    return pinned(root / item["file"], item.get("sha256"))


def verify_history(inventory_path, sources_path, registry_directory, output, *, inventory_sha256,
                   sources_sha256, registry_sha256):
    """Materialize all version resources, unique connections and original rows."""
    implementation = {name: sha(ROOT / name) for name in (
        "tools/pathway_history/verify.py", "tools/pathway_history/models.py",
        "biograph_steward/wiki_history.py", "biograph_steward/human_gene_relation.py",
        "biograph_steward/cohort_mapping.py", "biograph_steward/gold_packet.py",
        "biograph_steward/client.py", "biograph_steward/file_utils.py")}
    inventory = sealed(inventory_path, inventory_sha256, INVENTORY_FORMAT)
    graph_path = verify_inventory(inventory)
    sources = sealed(sources_path, sources_sha256, SOURCES_FORMAT)
    source_root = Path(sources_path).parent
    documents = sources.get("source_documents", {})
    need(set(REVIEWED_PINS) <= set(documents), "reviewed exporter, producer and schema proof are required.")
    for key, item in documents.items():
        _input_path(source_root, item)
        if item.get("capture_metadata_file"):
            pinned(source_root / item["capture_metadata_file"], item.get("capture_metadata_sha256"))
        if key in REVIEWED_PINS:
            need(item["sha256"] == REVIEWED_PINS[key], "reviewed official implementation/schema differs: " + key)
    need({"bridgedb_datasources", "bridgedb_datasource_columns", "bridgedb_system_codes"} <= set(documents),
         "official BridgeDb datasource namespace proof is required.")
    # Check actual namespace declarations instead of treating a table's label as
    # protein identity or confusing the HGNC symbol and accession namespaces.
    import csv
    with _input_path(source_root, documents["bridgedb_datasources"]).open(encoding="utf-8") as stream:
        datasource_rows = list(csv.reader(stream, delimiter="\t"))
    declared = {row[1]: row for row in datasource_rows if len(row) >= 14}
    need(all(code in declared for code in ("S", "L", "H", "Hac", "En"))
         and declared["H"][8] == "urn:miriam:hgnc.symbol"
         and declared["Hac"][8] == "urn:miriam:hgnc"
         and declared["S"][5] == "protein" and declared["L"][5] == "gene",
         "BridgeDb namespace roles differ from this reviewed scope.")
    validator = official_schema_validator(_input_path(source_root, documents["gpml2013a_schema"]),
                                           documents["gpml2013a_schema"]["sha256"])
    registry_manifest, registry = load_registry(registry_directory)
    need(registry_manifest["registry_sha256"] == registry_sha256, "human registry seal differs.")
    metadata_index = {}
    need(sources.get("metadata_pages"), "native publisher record metadata pages are required.")
    for page in sources["metadata_pages"]:
        native_metadata = gold_packet._read(_input_path(source_root, page))
        for record_index, record in enumerate(native_metadata["hits"]["hits"]):
            for file_index, item in enumerate(record.get("files", [])):
                metadata_index[(record["doi"], item["key"])] = {
                    "publisher_checksum": item["checksum"], "file_bytes": item["size"],
                    "url": item["links"]["self"], "license": record["metadata"]["license"],
                    "metadata_page_file": "source_metadata/" + Path(page["file"]).name,
                    "metadata_page_sha256": page["sha256"],
                    "metadata_json_pointer": "/hits/hits/%d/files/%d" % (record_index, file_index)}
    requested = {r["full_source_id"]: r for r in inventory["versions"]}
    candidates, parsed, archive_proofs = defaultdict(list), {}, []
    for archive in sources.get("archives", []):
        archive_path = _input_path(source_root, archive)
        raw_archive = archive_path.read_bytes()
        publisher = metadata_index.get((archive.get("record_DOI"), archive_path.name))
        need(publisher is not None and all(archive.get(k) == publisher[k]
             for k in ("publisher_checksum", "url", "license")) and len(raw_archive) == publisher["file_bytes"],
             "archive does not match its exact native publisher metadata.")
        need(archive.get("publisher_checksum") == "md5:" + hashlib.md5(raw_archive).hexdigest(),
             "archive differs from published checksum.")
        need(archive.get("license") == {"id": "cc-zero"} and isinstance(archive.get("record_DOI"), str)
             and archive["record_DOI"].startswith("10.5281/zenodo."), "archive DOI/declared data terms are missing.")
        with zipfile.ZipFile(archive_path) as z:
            entries = z.infolist()
            need(len(entries) <= 10_000 and sum(e.file_size for e in entries) <= 600_000_000
                 and all(e.file_size <= 20_000_000 for e in entries), "archive exceeds declared extraction budget.")
            need(len({e.filename for e in entries}) == len(entries), "archive member names repeat.")
            for entry in entries:
                full_id = archive_member_id(entry.filename)
                if full_id not in requested:
                    continue
                raw = z.read(entry)
                file_pin = hashlib.sha256(raw).hexdigest()
                model_key = (full_id, file_pin)
                if model_key not in parsed:
                    parsed[model_key] = (inspect_model(raw, full_source_id=full_id,
                        archive_member=entry.filename, validate=validator), raw)
                model = parsed[model_key][0]
                candidates[full_id].append({"archive_file": archive["file"], "archive_sha256": archive["sha256"],
                    "portable_archive_file": "archives/" + archive_path.name,
                    "archive_publisher_checksum": archive["publisher_checksum"], "archive_bytes": len(raw_archive),
                    "archive_release": archive["archive_release"], "archive_member": entry.filename,
                    "record_DOI": archive["record_DOI"], "source_url": archive["url"],
                    "archive_license": archive["license"], "gpml_sha256": file_pin,
                    "xml_author_version": model["xml_author_version"], "native_organism": model["native_organism"],
                    **{k: publisher[k] for k in ("metadata_page_file", "metadata_page_sha256", "metadata_json_pointer")}})
        archive_proofs.append(archive)
    input_files = [source_root / item["file"] for item in
                   [*sources.get("archives", []), *documents.values(), *sources["metadata_pages"]]]
    folder = new_output(output, inventory_path, sources_path, registry_directory, graph_path, *input_files)
    (folder / "models").mkdir()
    resources, models, connections, edges = [], [], [], []
    for full_id, requested_resource in requested.items():
        hits = sorted(candidates.get(full_id, []), key=lambda x: (x["archive_release"], x["archive_file"], x["archive_member"]))
        unique_pins = {h["gpml_sha256"] for h in hits}
        model = parsed[(full_id, hits[0]["gpml_sha256"])][0] if len(unique_pins) == 1 else None
        state = ("exact_publisher_revision_content_available" if model is not None else
                 "conflicting_model_bytes_under_same_publisher_revision" if hits else "no_exact_model_in_examined_archives")
        resource = {"full_source_id": full_id, "provider": "WikiPathways", "status": state,
            "canonical_wpid": requested_resource["canonical_wpid"], "requested_revision": requested_resource["requested_revision"],
            "candidates": hits, "archived_occurrences": len(hits), "distinct_candidate_model_hashes": len(unique_pins),
            "gpml_sha256": model["gpml_sha256"] if model else None,
            "native_model_file": "models/" + full_id + ".gpml" if model else None,
            "xml_author_version": model["xml_author_version"] if model else None,
            "native_organism": model["native_organism"] if model else None,
            "official_schema_validation": model["author_schema_validation"] if model else None,
            "biological_truth_assessed": False}
        resources.append(resource)
        if model:
            (folder / resource["native_model_file"]).write_bytes(parsed[(full_id, model["gpml_sha256"])][1])
            models.append(model)
        by_subject = defaultdict(list)
        for row in requested_resource["evidence_edges"]:
            by_subject[row["subject"]].append(row)
        for subject, rows in sorted(by_subject.items()):
            assessed = assess_subject(subject, model, registry) if model else {"subject": subject,
                "status": "unresolved", "unresolved_context": [state], "exact_protein_matches": [],
                "compatible_gene_matches": [], "absence_is_biological_negative": False,
                "independent_scientific_correctness": "unreviewed"}
            connection = {"full_source_id": full_id, **assessed, "native_model_file": resource["native_model_file"],
                "native_model_sha256": resource["gpml_sha256"], "native_model_status": state,
                "original_edge_ids": [r["edge_id"] for r in rows],
                "original_assertion_ids": [r["assertion_id"] for r in rows],
                "native_pwids": [r["native_pwid"] for r in rows],
                "current_decision_counts": dict(Counter(r["current_membership_decision"] for r in rows))}
            connection["content_sha256"] = digest(connection)
            connections.append(connection)
            for row in rows:
                edges.append({**row, "full_source_id": full_id, "historical_member_status": assessed["status"],
                    "historical_resource_status": state, "connection_content_sha256": connection["content_sha256"],
                    "native_model_sha256": resource["gpml_sha256"], "native_model_file": resource["native_model_file"],
                    "biological_negative_asserted": False, "automatic_pruning_decision": "abstain"})
    need(len(edges) == inventory["native_edge_count"], "original edge denominator changed.")
    write_jsonl(folder / "resource_coverage.jsonl", resources)
    write_jsonl(folder / "native_models.jsonl", models)
    write_jsonl(folder / "claim_assessments.jsonl", connections)
    write_jsonl(folder / "edge_assessments.jsonl", edges)
    shutil.copyfile(inventory_path, folder / "inventory.json")
    shutil.copyfile(sources_path, folder / "source_inputs.json")
    write_json(folder / "registry_manifest.json", registry_manifest)
    (folder / "registry").mkdir()
    for name in ("manifest.json", *REGISTRY_FILES):
        shutil.copyfile(Path(registry_directory) / name, folder / "registry" / name)
    (folder / "archives").mkdir()
    for archive in archive_proofs:
        shutil.copyfile(_input_path(source_root, archive), folder / "archives" / Path(archive["file"]).name)
    for key, item in documents.items():
        target = folder / "source_documents" / (key + Path(item["file"]).suffix)
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(_input_path(source_root, item), target)
        if item.get("capture_metadata_file"):
            shutil.copyfile(pinned(source_root / item["capture_metadata_file"], item["capture_metadata_sha256"]),
                            folder / "source_documents" / (key + ".capture.json"))
    (folder / "source_metadata").mkdir()
    for page in sources["metadata_pages"]:
        shutil.copyfile(_input_path(source_root, page), folder / "source_metadata" / Path(page["file"]).name)
    cross_rows = {d: {s: 0 for s in STATUSES} for d in ("keep", "prune", "abstain")}
    cross_connections = {d: {s: 0 for s in STATUSES} for d in ("keep", "prune", "abstain")}
    for edge in edges:
        cross_rows[edge["current_membership_decision"]][edge["historical_member_status"]] += 1
    for connection in connections:
        for decision in connection["current_decision_counts"]:
            cross_connections[decision][connection["status"]] += 1
    exact_versions = {r["full_source_id"] for r in resources if r["status"] == "exact_publisher_revision_content_available"}
    counts = {"requested_distinct_versions": len(resources), "exact_publisher_bound_versions": len(exact_versions),
        "literal_XML_full_sourceID_version_matches": sum(m["xml_author_version_equals_full_source_id"] for m in models),
        "archived_exact_version_occurrences": sum(len(r["candidates"]) for r in resources),
        "models_with_conflicting_byte_hashes": sum(r["distinct_candidate_model_hashes"] > 1 for r in resources),
        "author_schema_passed_models": sum(m["author_schema_validation"]["passed"] for m in models),
        "original_rows": len(edges), "original_unique_subject_version_connections": len(connections),
        "rows_with_exact_historical_model": sum(e["full_source_id"] in exact_versions for e in edges),
        "unique_connections_with_exact_historical_model": sum(c["full_source_id"] in exact_versions for c in connections),
        "retained_original_rows": sum(e["current_membership_decision"] != "prune" for e in edges),
        "retained_rows_with_exact_historical_model": sum(e["current_membership_decision"] != "prune" and e["full_source_id"] in exact_versions for e in edges),
        "unique_connection_statuses": dict(Counter(c["status"] for c in connections)),
        "original_row_statuses": dict(Counter(e["historical_member_status"] for e in edges))}
    # No successful report is written unless all source bytes are still pinned.
    pinned(inventory_path, inventory_sha256)
    pinned(sources_path, sources_sha256)
    pinned(graph_path, inventory["source_graph_file_sha256"])
    pinned(inventory["current_source_view_report_path"], inventory["current_source_view_report_file_sha256"])
    need(load_registry(registry_directory)[0] == registry_manifest, "human registry changed.")
    for archive in archive_proofs:
        _input_path(source_root, archive)
    for item in documents.values():
        _input_path(source_root, item)
        if item.get("capture_metadata_file"):
            pinned(source_root / item["capture_metadata_file"], item["capture_metadata_sha256"])
    for page in sources["metadata_pages"]:
        _input_path(source_root, page)
    for name, pin in implementation.items():
        pinned(ROOT / name, pin)
    report = {"format": FORMAT, "created_at": utcnow(), "inventory_content_sha256": inventory["content_sha256"],
        "inventory_file_sha256": inventory_sha256, "sources_content_sha256": sources["content_sha256"],
        "sources_file_sha256": sources_sha256, "source_graph_file_sha256": inventory["source_graph_file_sha256"],
        "registry_sha256": registry_sha256, "registry_files": registry_manifest["files"],
        "portable_registry_directory": "registry", "portable_archives_included": True,
        "producer_schema_execution": "lxml actual released author GPML2013a XSD; core replay attaches this byte-bound receipt without claiming reexecution",
        "source_documents": documents, "archives": archive_proofs, "counts": counts,
        "portable_source_documents": {key: {**item,
            "portable_file": "source_documents/" + key + Path(item["file"]).suffix,
            "portable_capture_metadata_file": "source_documents/" + key + ".capture.json" if item.get("capture_metadata_file") else None}
            for key, item in documents.items()},
        "current_decision_by_historical_status_original_rows": cross_rows,
        "current_decision_by_historical_status_unique_connections": cross_connections,
        "no_original_graph_or_reviews_changed": True, "no_native_rows_merged": True,
        "current_decisions_changed": False, "new_biological_truth_labels_created": False,
        "scientific_accuracy_measured": False, "independent_reference": False,
        "automatic_graph_pruning_performed": False, "source_fetches_during_verification": 0, "model_calls": 0,
        "limitations": LIMITATIONS, "implementation_sha256": implementation,
        "files": {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*") if p.is_file()}}
    report["content_sha256"] = digest(report)
    write_json(folder / "historical_verification.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--sources-sha256", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = verify_history(args.inventory, args.sources, args.registry, args.out,
        inventory_sha256=args.inventory_sha256, sources_sha256=args.sources_sha256, registry_sha256=args.registry_sha256)
    print(json.dumps({"report": str(Path(args.out) / "historical_verification.json"),
                      "content_sha256": report["content_sha256"], "counts": report["counts"]}, indent=2))


if __name__ == "__main__":
    main()
