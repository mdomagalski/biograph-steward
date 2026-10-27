"""Reopen a source-bound IntAct evidence publication through the assay framework.

This checks preserved bytes and repeats the local projection. It does not parse
MITAB biology in Python, authenticate a publisher or rerun the Java reader.
"""
from copy import deepcopy
import hashlib
import re

FORMAT = "biograph-steward.intact-evidence-publication.v1"
DEVELOPMENT = frozenset(("40075158", "40404733", "40071126", "40739265"))


def records_from_material(files, catalog, bindings):
    from .assay_attachment import _decode
    if not isinstance(catalog, list) or not catalog:
        raise ValueError("IntAct publication requires an explicit source catalog.")
    if ({entry.get("publication_id") for entry in catalog} != {"pubmed:" + p for p in DEVELOPMENT}
            or len(catalog) != len(DEVELOPMENT)
            or set(bindings.get("source_sha256", {})) != DEVELOPMENT
            or set(bindings.get("reader_sha256", {})) != DEVELOPMENT):
        raise ValueError("This increment requires all four development studies; reserved or replacement sources are forbidden.")
    records, seen, source_names = [], set(), set()
    for entry in catalog:
        publication = entry.get("publication_id", "")
        if not isinstance(publication, str) or not re.fullmatch(r"pubmed:[0-9]+", publication):
            raise ValueError("IntAct publication identifier is missing.")
        pmid = publication.split(":")[1]
        if publication in seen:
            raise ValueError("Duplicate IntAct publication catalog entry.")
        seen.add(publication)
        source_name, reader_name = "source/" + pmid + ".txt", "reader/" + pmid + ".jsonl"
        if entry.get("source_file") != source_name or entry.get("reader_file") != reader_name:
            raise ValueError("Unexpected IntAct source path.")
        try:
            source, reader = files[source_name], files[reader_name]
            if (hashlib.sha256(source).hexdigest() != entry["artifact_sha256"]
                    or bindings["source_sha256"][pmid] != entry["artifact_sha256"]
                    or hashlib.sha256(reader).hexdigest() != entry["reader_sha256"]
                    or bindings["reader_sha256"][pmid] != entry["reader_sha256"]):
                raise ValueError("IntAct source or official-reader bytes changed.")
            lines = source.decode("utf-8").splitlines()
            parsed = [_decode(line) for line in reader.splitlines()]
            if len(lines) != len(parsed):
                raise ValueError("IntAct raw/reader physical-row counts differ.")
            for number, (line, row) in enumerate(zip(lines, parsed), 1):
                if (row["line_number"] != number or row["raw_line"] != line
                        or row["raw_cells"] != line.split("\t")):
                    raise ValueError("IntAct raw cells or source-side order changed.")
                records.append({"publication_id": publication, "artifact_sha256": entry["artifact_sha256"],
                                "source_file": source_name, "reader_file": reader_name,
                                "reader_record": row})
            source_names.update((source_name, reader_name))
        except (KeyError, TypeError, UnicodeError) as exc:
            raise ValueError("Incomplete IntAct source catalog or official-reader rows.") from exc
    if {name for name in files if name.startswith(("source/", "reader/"))} != source_names:
        raise ValueError("Uncatalogued IntAct source files are not permitted.")
    return records


def load_projection(manifest, files):
    from .assay_attachment import _decode, _sealed
    from .intact_evidence import build_evidence
    required = {"LICENSE.md", "row_ledger.jsonl", "protocol.json", "semantic_amendment.json",
                "inspection_report.json", "controls_report.json", "evidence.json", "graph.json"}
    implementation = manifest.get("implementation_sha256")
    if (manifest.get("format") != FORMAT or not required <= set(files)
            or not isinstance(implementation, dict) or not implementation
            or any(not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
                   for value in implementation.values())
            or any(manifest.get(key) is not False for key in
                   ("baseline_modified", "automatic_pruning", "independent_validation_performed",
                    "standard_conformance_claimed"))):
        raise ValueError("Unsupported IntAct evidence publication or interpretation policy.")
    try:
        bindings = manifest["bindings"]
        controls_sha = hashlib.sha256(files["controls_report.json"]).hexdigest()
        controls = _decode(files["controls_report.json"])
        inspection = _decode(files["inspection_report.json"])
        if (controls_sha != bindings["controls_report_sha256"] or not _sealed(controls)
                or controls.get("format") != "biograph-steward.intact-reader-controls-result.v1"
                or controls.get("status") != "passed" or controls.get("all_checks_passed") is not True
                or controls.get("synthetic_only") is not True or controls.get("reference_rows_accessed") is not False
                or controls.get("runtime_bindings") != bindings["reader_runtime"]
                or inspection.get("status") != "development_inspected_not_fidelity_scored"
                or inspection.get("bindings", {}).get("controls_report_sha256") != controls_sha
                or inspection.get("bindings", {}).get("runtime_bindings") != bindings["reader_runtime"]):
            raise ValueError("IntAct reader controls and development inspection do not bind the same preserved runtime.")
        for name, key in (("row_ledger.jsonl", "ledger_sha256"),
                          ("protocol.json", "protocol_sha256"),
                          ("semantic_amendment.json", "amendment_sha256"),
                          ("inspection_report.json", "result_sha256")):
            if hashlib.sha256(files[name]).hexdigest() != bindings[key]:
                raise ValueError("IntAct frozen input binding changed: " + name)
        records = records_from_material(files, manifest["source_catalog"], bindings)
        ledger = [_decode(line) for line in files["row_ledger.jsonl"].splitlines()]
        evidence = build_evidence(records, ledger, deepcopy(bindings))
        if (evidence != _decode(files["evidence.json"])
                or evidence["graph"] != _decode(files["graph.json"])
                or evidence["summary"] != manifest["summary"]):
            raise ValueError("IntAct evidence does not reproduce from its preserved source records.")
    except (KeyError, TypeError, UnicodeError) as exc:
        raise ValueError("Incomplete IntAct source-bound publication.") from exc
    return manifest, evidence, files
