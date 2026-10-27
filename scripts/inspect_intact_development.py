#!/usr/bin/env python3
"""Inspect only the four frozen IntAct development studies after reader controls.

This is a row-accounting/eligibility diagnostic, not an importer or fidelity score.
Biological fields come from the unmodified official JAMI grammar. Raw framing and
negative-literal checks implement the already pinned MITAB27 format constraint.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_intact_fidelity_preparation import replay, PANEL_SHA
from scripts.validate_intact_reader_controls import assess_reader_row
from biograph_steward.graph import UNIPROT
from biograph_steward.client import digest as canonical_digest

DEVELOPMENT = ("40075158", "40404733", "40071126", "40739265")
RESERVED = frozenset(("39833857", "40211762", "39972491", "40555359"))
AMENDMENT_SHA = "2cd2cb485836228ce71dd9d62201c61dd5de45d18563894ac883f188f245e98c"
PREPARATION_SHA = "e5c35e3f927e62d2c1094c4d19edaf33406940fba26eeadd397c6f156c2af5ea"
BASE = ROOT / "runs/intact_fidelity_preparation_20261026"
PREPARATION = ROOT / "docs/evaluations/intact_fidelity_20261026_preparation.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def values(row, field):
    """Only official field-parser results, never an alternative MITAB parser."""
    return ((row.get("source_fields") or {}).get(field) or {}).get("values", [])


def dbname(xref):
    return ((xref.get("database") or {}).get("name") or "").lower()


def cv_ids(items):
    return [item.get("mi_id") for item in items]


def assess(row, pmid):
    """Apply the frozen explicit-human-protein eligibility, preserving losses.

    Several-value reader warnings are NOT a blanket eligibility exclusion. A row
    with eligible source identities remains in the eligible denominator even when
    the JAMI evidence object cannot preserve its experimental context.
    """
    reasons, losses, diagnostics = [], [], []
    status = row["row_status"]
    if status in {"header", "comment", "blank"}:
        return {"kind": status, "eligible": False, "exclusion_reasons": [],
                "object_projection_limitations": []}
    cells = row["raw_cells"]
    reasons.extend(assess_reader_row(row)["quarantine_reasons"])
    fields = row.get("source_fields") or {}
    diagnostics.extend(row.get("diagnostics", []))
    for field in fields.values():
        diagnostics.extend(field.get("diagnostics", []))
    callbacks = Counter(event["callback"] for event in diagnostics)
    negative = cells[35] if len(cells) > 35 else None

    participants = []
    for side in ("a", "b"):
        primary = values(row, "primary_ids_" + side)
        uniprot = [x for x in primary if dbname(x) == "uniprotkb"]
        exact = sorted({x.get("id") for x in uniprot if x.get("id")})
        if len(exact) != 1 or any(not UNIPROT.fullmatch(accession) for accession in exact):
            reasons.append("primary_identifier_missing_or_ambiguous_" + side)
        taxa = values(row, "taxa_" + side)
        taxids = sorted({x.get("taxid") for x in taxa}, key=str)
        if taxids != [9606]:
            reasons.append("participant_taxonomy_not_only_explicit_human_" + side)
        types = cv_ids(values(row, "interactor_types_" + side))
        if not types or set(types) != {"MI:0326"}:
            reasons.append("participant_type_not_only_explicit_protein_" + side)
        participants.append({"side": side.upper(), "primary_ids": primary,
                             "uniprot_accessions": exact, "taxids": taxids,
                             "explicit_type_ids": types})

    publications = values(row, "publication_ids")
    pmids = sorted({x.get("id") for x in publications if dbname(x) == "pubmed"})
    if pmid not in pmids:
        reasons.append("publication_missing_selected_pmid")
    sources = values(row, "source_databases")
    if not sources or any(not x.get("mi_id") and not x.get("name") for x in sources):
        reasons.append("source_database_missing_or_untraceable")
    evidence = values(row, "evidence_ids")
    if not evidence or any(not dbname(x) or not x.get("id") for x in evidence):
        reasons.append("evidence_identity_missing_or_untraceable")

    # Document object reductions independently of source eligibility. Raw cells
    # and full official field collections are retained alongside this diagnosis.
    for name, count in callbacks.items():
        if name.startswith("onSeveral") or name.startswith("onParticipantWithout"):
            losses.append({"callback": name, "count": count})
    model = row.get("interaction") or {}
    model_participants = model.get("participants", [])
    if row.get("parsed_count") == 1 and (
            len(model_participants) != 2
            or sorted(str(p.get("side")) for p in model_participants) != ["A", "B"]):
        losses.append({"callback": "object_source_side_mapping_incomplete", "count": 1})
    return {
        "kind": "evidence", "eligible": not reasons,
        "exclusion_reasons": list(dict.fromkeys(reasons)),
        "object_projection_limitations": losses,
        "source_participants": participants,
        "publication_ids": publications, "source_databases": sources,
        "evidence_ids": evidence,
        "negative_literal": negative,
        "negative_value": None if negative not in {"true", "false", "-"} else negative == "true",
        "negative_origin": "mitab27_default_false" if negative == "-" else
                           "explicit" if negative in {"true", "false"} else "invalid_or_unavailable",
        "expansion_literal": cells[15] if len(cells) > 15 else None,
        "expansion_origin": "not_supplied" if len(cells) > 15 and cells[15] == "-" else
                            "supplied" if len(cells) > 15 else "unavailable",
        "binary_origin": "unknown_no_inference",
        "source_detection_methods": values(row, "detection_methods"),
        "source_interaction_types": values(row, "interaction_types"),
        "source_hosts": values(row, "host_taxa"),
        "reader_callbacks": dict(callbacks),
        "provenance_multiplicity_requires_grouping_audit":
            len(pmids) > 1 or len(sources) > 1 or len(evidence) > 1,
    }


def source_lines(blob):
    """Mirror BufferedReader physical LF/CRLF framing without changing cells."""
    lines = blob.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    result = []
    for line in lines:
        if line.endswith(b"\r"):
            line = line[:-1]
        if b"\r" in line:
            raise ValueError("Standalone CR framing needs separate investigation, not silent normalization.")
        result.append(line.decode("utf-8", errors="strict"))
    return result


def verify_controls_report(controls):
    from scripts.validate_intact_reader_controls import CONTROLS, EXPECTED_CONTROLS_SHA256
    unsigned = {key: value for key, value in controls.items() if key != "content_sha256"}
    checks = [check for case in controls.get("cases", []) for check in case.get("checks", [])]
    if (controls.get("content_sha256") != canonical_digest(unsigned)
            or controls.get("status") != "passed" or controls.get("all_checks_passed") is not True
            or not checks or any(check.get("passed") is not True for check in checks)
            or controls.get("original_control_count") != 30 or len(controls.get("cases", [])) != 32
            or controls.get("runner_sha256") != digest(ROOT / "scripts/validate_intact_reader_controls.py")
            or controls.get("controls_inventory_sha256") != EXPECTED_CONTROLS_SHA256
            or digest(CONTROLS) != EXPECTED_CONTROLS_SHA256):
        raise ValueError("An intact, current, passing official-reader synthetic report is required.")


def inspect(args):
    # Import the validator only to compare the exact already-tested runtime.
    from scripts.validate_intact_reader_controls import runtime_bindings
    controls_path = Path(args.controls_report).resolve()
    controls = json.loads(controls_path.read_text())
    verify_controls_report(controls)
    current = runtime_bindings(Path(args.classes).resolve(), Path(args.classpath_file).resolve(), args.java)
    if current != controls["runtime_bindings"]:
        raise ValueError("Reader/runtime differs from the synthetic control run.")
    replay(BASE / "panel.json", PANEL_SHA,
           ROOT / "docs/evaluations/intact_fidelity_20261026_semantic_amendment.json", AMENDMENT_SHA)
    if digest(PREPARATION) != PREPARATION_SHA:
        raise ValueError("Frozen preparation receipt changed.")
    preparation = json.loads(PREPARATION.read_text())
    panel = json.loads((BASE / "panel.json").read_text())
    if digest(BASE / "opaque_sources/retrieval_receipt.json") != preparation["bindings"]["retrieval_receipt"]["sha256"]:
        raise ValueError("Retrieval receipt changed.")
    selected = [x for x in panel["selected"] if x["split"] == "development"]
    if tuple(x["publication_id"].split(":")[1] for x in selected) != DEVELOPMENT:
        raise ValueError("Development allowlist changed.")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    bindings = {"runtime_bindings": current, "controls_report": str(controls_path),
                "controls_report_sha256": digest(controls_path),
                "inspection_script_sha256": digest(__file__), "panel_sha256": PANEL_SHA,
                "amendment_sha256": AMENDMENT_SHA,
                "eligibility_dependencies": {str(Path(path).resolve()): digest(path) for path in
                    (ROOT / "scripts/validate_intact_reader_controls.py", ROOT / "biograph_steward/graph.py")}}
    save_new(output / "pre_exposure_bindings.json", bindings)
    def unchanged():
        if (runtime_bindings(Path(args.classes).resolve(), Path(args.classpath_file).resolve(), args.java) != current
                or digest(controls_path) != bindings["controls_report_sha256"]
                or digest(__file__) != bindings["inspection_script_sha256"]
                or any(digest(path) != expected for path, expected in bindings["eligibility_dependencies"].items())):
            raise ValueError("Reader/runtime/control/eligibility code changed during inspection; stop.")
    classpath = str(Path(args.classes).resolve()) + ":" + Path(args.classpath_file).read_text().strip()
    studies, ledger = [], []
    for chosen in selected:
        unchanged()
        pmid = chosen["publication_id"].split(":")[1]
        if pmid not in DEVELOPMENT or pmid in RESERVED:
            raise ValueError("Reserved or unknown study is forbidden in this diagnostic.")
        receipt = next(x for x in preparation["sources"] if x["publication_id"] == chosen["publication_id"])
        unresolved = ROOT / receipt["local_path"]
        source = unresolved.resolve()
        if source != (BASE / "opaque_sources" / (pmid + ".txt")).resolve() or unresolved.is_symlink():
            raise ValueError("Unexpected source path.")
        blob = source.read_bytes()  # Opaque hash validation; no decoding yet.
        if len(blob) != receipt["bytes"] or hashlib.sha256(blob).hexdigest() != receipt["sha256"]:
            raise ValueError("Frozen source bytes changed: " + pmid)
        exposure = {"format": "biograph-steward.intact-development-exposure.v1", "started_at": now(),
                    "publication_id": chosen["publication_id"], "split": "development",
                    "source_sha256": receipt["sha256"], "source_bytes": len(blob),
                    "source_url": chosen["url"], "pre_exposure_bindings_sha256": digest(output / "pre_exposure_bindings.json"),
                    "status": "exposure_started_before_decode; consumed_even_if_subsequent_failure"}
        save_new(output / (pmid + "_exposure_started.json"), exposure)
        lines = source_lines(blob)  # First decoding occurs after exclusive receipt.
        unchanged()
        result = subprocess.run([args.java, "-cp", classpath, "org.biograph.IntactReader", str(source)],
                                capture_output=True, text=True, timeout=120, check=False)
        (output / (pmid + "_reader.jsonl")).write_text(result.stdout)
        (output / (pmid + "_reader.stderr")).write_text(result.stderr)
        unchanged()
        if result.returncode:
            raise RuntimeError("Official reader failed; study consumed; see stderr for " + pmid)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        if len(rows) != len(lines):
            raise ValueError("Physical row-accounting mismatch: " + pmid)
        counts, exclusions, losses, callbacks, negatives, expansions = (Counter() for _ in range(6))
        for number, (raw, row) in enumerate(zip(lines, rows), 1):
            if row["line_number"] != number or row["raw_line"] != raw or row["raw_cells"] != raw.split("\t"):
                raise ValueError("Raw field/orientation/locator preservation failed: " + pmid)
            assessment = assess(row, pmid)
            counts[assessment["kind"]] += 1
            counts["eligible"] += int(assessment["eligible"])
            if assessment["kind"] == "evidence":
                counts["excluded_evidence"] += int(not assessment["eligible"])
                exclusions.update(assessment["exclusion_reasons"])
                callbacks.update(assessment["reader_callbacks"])
                losses.update(x["callback"] for x in assessment["object_projection_limitations"])
                if assessment["eligible"]:
                    negatives.update([assessment["negative_literal"]])
                    expansions.update([assessment["expansion_origin"]])
            ledger.append({"publication_id": chosen["publication_id"], "artifact_sha256": receipt["sha256"],
                           "release": "2026-10-17", "source_line": number,
                           "raw_row_sha256": hashlib.sha256(raw.encode()).hexdigest(), **assessment})
        studies.append({"publication_id": chosen["publication_id"], "physical_rows": len(rows),
                        "source_sha256": receipt["sha256"], "counts": dict(counts),
                        "exclusion_reasons": dict(exclusions), "object_projection_limitations": dict(losses),
                        "reader_callbacks": dict(callbacks), "eligible_negative_literals": dict(negatives),
                        "eligible_expansion_annotation": dict(expansions)})
    with (output / "row_ledger.jsonl").open("x") as stream:
        for row in ledger:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    totals = Counter()
    for study in studies:
        totals.update(study["counts"])
        totals["physical_rows"] += study["physical_rows"]
    report = {"format": "biograph-steward.intact-development-diagnostic.v1", "created_at": now(),
              "status": "development_inspected_not_fidelity_scored", "bindings": bindings,
              "studies": studies, "totals": dict(totals),
              "reserved_final_rows_opened": False, "model_calls": 0, "gpu_runs": 0,
              "interpretation": "Eligibility and reader diagnostics only. A complete deterministic import/answer/export comparison is still required; these counts are not biological accuracy.",
              "eligibility_interpretation": "One distinct explicit, syntax-valid UniProtKB source primary identity per side (additional non-UniProt cross-references retained); sole explicit taxid9606 and sole MI:0326 type; publication list contains selected PMID (other publication provenance retained for later grouping audit); nonempty explicit database-qualified evidence identifiers and source terms. Multiple explicit sources/IDs are preserved as provided, with no invented preferred/main ID or IntAct-only requirement. Optional context and several-value object reductions are not blanket exclusions.",
              "remaining": ["Implement and freeze source-faithful answer/export adapter on development data.",
                            "Audit study provenance and exact participant/pair overlap before reserved evaluation.",
                            "Reserved access only after separate output/evaluator commitment; no independence or scientific-accuracy claim."]}
    save_new(output / "report.json", report)
    table = "".join("<tr><td>" + html.escape(s["publication_id"]) + "</td><td>" +
                    str(s["physical_rows"]) + "</td><td>" + str(s["counts"].get("eligible", 0)) +
                    "</td><td><pre>" + html.escape(json.dumps(s["exclusion_reasons"], indent=2)) +
                    "</pre></td><td><pre>" + html.escape(json.dumps(s["object_projection_limitations"], indent=2)) +
                    "</pre></td></tr>" for s in studies)
    (output / "index.html").write_text("<!doctype html><meta charset='utf-8'><title>IntAct development reader inspection</title>"
        "<style>body{font:16px system-ui;margin:3rem;max-width:1200px;color:#182d37}td,th{padding:12px;border:1px solid #ccd6dd;text-align:left}table{border-collapse:collapse}pre{white-space:pre-wrap}</style>"
        "<h1>IntAct development reader inspection</h1><p>Official JAMI reader validated on synthetic controls before these four studies were opened. Four reserved studies remain unopened.</p>"
        "<p><strong>Source eligibility and reader diagnostics; no biological accuracy or answer/export fidelity score.</strong></p>"
        "<table><tr><th>Study</th><th>Physical rows</th><th>Eligible evidence rows</th><th>Exclusions (overlap)</th><th>Object projection limitations</th></tr>" + table + "</table>"
        "<p>Raw cells, exact A/B orientation, source hashes and every listener event remain in the per-study JSONL. Missing expansion does not establish binary origin or direct binding. Qualified negatives would be retained; absent pairs never become negative evidence.</p>"
        "<p><a href='report.json'>Report JSON</a> · <a href='row_ledger.jsonl'>All-row ledger</a></p>")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls-report", required=True)
    parser.add_argument("--classpath-file", required=True)
    parser.add_argument("--classes", default=str(ROOT / "tools/intact_reader/target/classes"))
    parser.add_argument("--java", default="java")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = inspect(args)
    print(json.dumps({"status": report["status"], "totals": report["totals"], "studies": report["studies"]}, indent=2))


if __name__ == "__main__":
    main()
