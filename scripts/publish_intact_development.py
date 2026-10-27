#!/usr/bin/env python3
"""Publish only the already-consumed four-study IntAct development reference.

Uses the validated official-reader outputs; no Java/model invocation and no
reserved file access. A whole preparation directory must never be copied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.intact_publication import FORMAT, records_from_material

PMIDS = ("40075158", "40404733", "40071126", "40739265")
INSPECTION_SHA = "f329ef329ce23eaf3ac403890208fa5526a57124999251e7c746f3da667719c2"
LEDGER_SHA = "232ad603873331a0f19e3447ec8c430e93dd7b5802367190be8cd956c6a16a2b"
PREPARATION_SHA = "e5c35e3f927e62d2c1094c4d19edaf33406940fba26eeadd397c6f156c2af5ea"
READER_SHA = {
    "40075158": "e9389e26b9169d46aff2f44d106dcc15d6f19667ce872ef47fe1eb17ff3a1cbb",
    "40404733": "c588b5ebac1791957ee80f9d4f38228980c15cf65e65830c037656a3f740781c",
    "40071126": "a81d210892ea39df01391a632c1c62dab33d2d59d4943d9ddf7b6d8c676f82ae",
    "40739265": "f3481bdbf7d34393aabb2c6be8f6ac10dff4fae3454efbfac9ce632e142e4615",
}


def publish(inspection, output):
    from biograph_steward import intact_evidence
    from biograph_steward.assay_attachment import load_publication
    inspection = Path(inspection).resolve()
    preparation = ROOT / "docs/evaluations/intact_fidelity_20261026_preparation.json"
    if (sha(inspection / "report.json") != INSPECTION_SHA
            or sha(inspection / "row_ledger.jsonl") != LEDGER_SHA
            or sha(preparation) != PREPARATION_SHA):
        raise ValueError("Use the unchanged, consumed development inspection and preparation.")
    report = json.loads((inspection / "report.json").read_text())
    original = json.loads(preparation.read_text())
    controls = Path(report["bindings"]["controls_report"])
    if sha(controls) != report["bindings"]["controls_report_sha256"]:
        raise ValueError("Passing official-reader control report changed.")
    files = {"row_ledger.jsonl": (inspection / "row_ledger.jsonl").read_bytes(),
             "inspection_report.json": (inspection / "report.json").read_bytes(),
             "controls_report.json": controls.read_bytes(),
             "protocol.json": (ROOT / "docs/evaluations/intact_fidelity_20261026_protocol.json").read_bytes(),
             "semantic_amendment.json": (ROOT / "docs/evaluations/intact_fidelity_20261026_semantic_amendment.json").read_bytes(),
             "LICENSE.md": (ROOT / "runs/intact_fidelity_preparation_20261026/sources/IntAct_license.md").read_bytes()}
    catalog, source_hashes, reader_hashes = [], {}, {}
    for pmid in PMIDS:  # Explicit allowlist; never scan/copy the opaque directory.
        entry = next(x for x in original["sources"] if x["publication_id"] == "pubmed:" + pmid)
        if entry["split"] != "development":
            raise ValueError("Reserved source is forbidden.")
        source = ROOT / entry["local_path"]
        if source.is_symlink() or sha(source) != entry["sha256"]:
            raise ValueError("Frozen development source changed.")
        reader = inspection / (pmid + "_reader.jsonl")
        if reader.is_symlink() or sha(reader) != READER_SHA[pmid]:
            raise ValueError("Original official-reader observation bytes changed.")
        source_file, reader_file = "source/" + pmid + ".txt", "reader/" + pmid + ".jsonl"
        files[source_file], files[reader_file] = source.read_bytes(), reader.read_bytes()
        source_hashes[pmid], reader_hashes[pmid] = sha(source), sha(reader)
        catalog.append({"publication_id": "pubmed:" + pmid, "artifact_sha256": sha(source),
                        "source_file": source_file, "reader_file": reader_file,
                        "reader_sha256": sha(reader)})
        files["exposure/" + pmid + ".json"] = (inspection / (pmid + "_exposure_started.json")).read_bytes()
    bindings = {"protocol_sha256": hashlib.sha256(files["protocol.json"]).hexdigest(),
                "amendment_sha256": hashlib.sha256(files["semantic_amendment.json"]).hexdigest(),
                "result_sha256": INSPECTION_SHA, "ledger_sha256": LEDGER_SHA,
                "source_sha256": source_hashes, "reader_sha256": reader_hashes,
                "reader_runtime": report["bindings"]["runtime_bindings"],
                "controls_report_sha256": sha(controls), "release": "2026-10-17"}
    records = records_from_material(files, catalog, bindings)
    ledger = [json.loads(line) for line in files["row_ledger.jsonl"].splitlines()]
    evidence = intact_evidence.build_evidence(records, ledger, bindings)
    output = new_output(output, inspection, ROOT / "runs/intact_fidelity_preparation_20261026")
    for name, raw in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    write_json(output / "evidence.json", evidence)
    write_json(output / "graph.json", evidence["graph"])
    (output / "index.html").write_text(intact_evidence.publication_html(evidence), encoding="utf-8")
    manifest = {"format": FORMAT, "created_at": utcnow(), "bindings": bindings,
                "source_catalog": catalog, "summary": evidence["summary"],
                "implementation_sha256": {"projection": sha(intact_evidence.__file__), "publisher": sha(__file__)},
                "baseline_modified": False, "automatic_pruning": False,
                "independent_validation_performed": False, "standard_conformance_claimed": False,
                "scope": "Four frozen, consumed development studies only; no reserved bodies.",
                "files": {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}}
    manifest["content_sha256"] = digest(manifest)
    write_json(output / "publication.json", manifest)
    load_publication(output)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspection", type=Path, default=ROOT / "runs/intact_development_inspection_20261026")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = publish(args.inspection, args.out)
    print(json.dumps({"output": str(args.out.resolve()), "summary": result["summary"]}, indent=2))
