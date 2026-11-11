#!/usr/bin/env python3
"""Read-only Neptune parity, reconstruction and fixed CIViC context check.

This operator command queries an already loaded mirror. It does not provision,
load, alter IAM, prune records, contact a model or change source artifacts.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.civic_questions import answer_civic_question
from biograph_steward.file_utils import sha
from biograph_steward.neptune import Mirror
from biograph_steward.reviews import read_run

PROFILE = "CIViC.molecularprofile:81"
DISEASE = "DOID:9256"
THERAPY = "cetuximab"
BOUNDARY = (
    "This checks database/source parity and exact question context. It does not "
    "measure biological accuracy, independent validation or agent improvement. "
    "Off-scope evidence is not biologically false or globally removable."
)


class AcceptanceError(ValueError):
    """A bounded, operator-readable acceptance failure, without SDK details."""


def require(condition, message):
    if not condition:
        raise AcceptanceError(message)


def source_hashes(folder):
    result = {}
    for path in sorted(folder.rglob("*")):
        require(not path.is_symlink(), "Source artifacts must not contain symlinks.")
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = sha(path)
    require(bool(result), "The saved source directory is empty.")
    return result


def question(graph, source_run):
    return answer_civic_question(graph, profile=PROFILE, therapy=THERAPY,
        view="candidates", max_results=30, max_paths=10, source_run=source_run)


def selected_ids(answer):
    return {
        "assertion_ids": sorted(citation["assertion_id"] for citation in answer["citations"]),
        "evidence_edge_ids": sorted({edge_id for citation in answer["citations"]
                                     for edge_id in citation["used_evidence_edge_ids"]}),
    }


def untruncated(answer):
    return answer["omitted_profiles"] == 0 and all(row["omitted_paths"] == 0 for row in answer["results"])


def sealed(receipt):
    return (isinstance(receipt, dict) and receipt.get("content_sha256")
            == digest({key: value for key, value in receipt.items() if key != "content_sha256"}))


def reference_check(path, graph, source_answer, ids, off_scope):
    path = Path(path).resolve()
    if path.is_dir():
        path = path / "baseline.json"
    reference = json.loads(path.read_text(encoding="utf-8"))
    scope = reference.get("scope", {})
    require((scope.get("profile_id"), scope.get("disease_id"), scope.get("therapy_ingredient"), scope.get("view"))
            == (PROFILE, DISEASE, THERAPY, "candidates"), "Prepared reference has a different question scope.")
    require(reference.get("relevant_assertion_ids") == ids["assertion_ids"], "Prepared assertion IDs differ.")
    require(reference.get("relevant_evidence_edge_ids") == ids["evidence_edge_ids"], "Prepared relevant evidence IDs differ.")
    require(reference.get("off_scope_evidence_edge_ids") == off_scope, "Prepared off-scope evidence IDs differ.")
    require((len(ids["evidence_edge_ids"]), len(off_scope), reference.get("disagreement_group_count")) == (8, 38, 2),
            "The selected preparation must preserve the fixed 8/38 evidence split and two disagreement groups.")
    details = {"path": str(path), "sha256": sha(path), "status": "passed",
               "relevant_evidence_edges": 8, "off_scope_evidence_edges": 38}
    bindings_file = path.with_name("source_hashes.json")
    if bindings_file.is_file():
        bindings = json.loads(bindings_file.read_text(encoding="utf-8"))
        for key, actual in (("snapshot_sha256", graph["snapshot_sha256"]),
                            ("civic_snapshot_sha256", graph["civic_snapshot_sha256"]),
                            ("graph_basis_sha256", source_answer["graph_basis_sha256"])):
            require(bindings.get(key) == actual, "Prepared logical source bindings differ: " + key)
        details["logical_source_bindings"] = "passed"
        details["source_hashes_file_sha256"] = sha(bindings_file)
    groups_file = path.with_name("disagreement_groups.json")
    if groups_file.is_file():
        require(json.loads(groups_file.read_text(encoding="utf-8")) == source_answer["discordant_annotations"],
                "Prepared disagreement groups differ.")
        details["disagreement_groups_file_sha256"] = sha(groups_file)
    return details


def html_report(report):
    status = escape(report["status"])
    checks = "".join("<li>" + escape(name.replace("_", " ")) + ": " + escape(value) + "</li>"
                     for name, value in report["checks"].items())
    context = report.get("context", {})
    summary = (f"<p>{context.get('relevant_evidence_edges', '—')} relevant evidence records; "
               f"{context.get('off_scope_evidence_edges', '—')} other CIViC records off scope; "
               f"{context.get('disagreement_groups', '—')} disagreement groups preserved.</p>")
    failure = "<p>" + escape(report["error"]) + "</p>" if report.get("error") else ""
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Neptune source and context check</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:900px;margin:40px auto;padding:0 24px}code{overflow-wrap:anywhere}"
        "li{margin:.4em 0}.note{background:#eef4f7;padding:14px}</style><h1>Neptune source and context check</h1>"
        f"<p><strong>{status}</strong> · Backend: AWS Neptune</p>{failure}"
        f"<p>Complete KRAS G13D molecular profile, treatment sets containing cetuximab, colorectal cancer ({DISEASE}).</p>"
        + summary + "<ul>" + checks + "</ul><p>Dataset: <code>" + escape(str(report.get("dataset_id", "unverified")))
        + "</code></p><p class='note'>" + escape(BOUNDARY) + "</p>"
        "<p>Acceptance requires Neptune-provided assertion and evidence payloads for the question and a complete graph reconstructed from database records. "
        "Canonical saved metadata supplies labels, scope and source-overlap descriptions. No file evidence fallback is permitted.</p>"
        "<p><a href='report.json'>Detailed acceptance report</a> · <a href='neptune_question.json'>Database question and citations</a> · "
        "<a href='source_question.json'>Deterministic source question</a> · <a href='source_hashes.json'>Source byte hashes</a> · "
        "<a href='database_roundtrip/export_receipt.json'>Database export receipt</a></p></html>\n")


def check(run, endpoint, region, output, scope_reference=None, *, mirror=None):
    run = Path(run).absolute()
    output = Path(output).absolute()
    require(not run.is_symlink() and run.is_dir(), "Supply an existing ordinary saved run directory.")
    run = run.resolve()
    require(not output.exists() and not output.is_symlink(), "Choose a new output directory.")
    require(output.resolve() != run and run not in output.resolve().parents,
            "The output must be outside the immutable source run.")
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "failed", "backend": "neptune", "started_at": utcnow(), "source_run": str(run),
              "scope": {"profile_id": PROFILE, "disease_id": DISEASE, "therapy_ingredient": THERAPY, "view": "candidates"},
              "checks": {}, "model_calls": 0, "database_writes": 0, "source_writes": 0,
              "biological_validation_performed": False, "agent_improvement_measured": False,
              "interpretation": BOUNDARY, "implementation_sha256": sha(Path(__file__))}
    before = None
    stage = "source_verification"
    try:
        before = source_hashes(run)
        graph = read_run(run)[2]
        graph_sha = digest(graph)
        source_answer = question(graph, run.name)
        require(untruncated(source_answer), "The deterministic reference answer is truncated.")
        require(len(source_answer["discordant_annotations"]) == 2, "This fixed task requires two source disagreement groups.")
        report["source_counts"] = {key: len(graph[key]) for key in ("nodes", "edges", "assertions")}
        report["graph_sha256"] = graph_sha
        report["checks"][stage] = "passed"
        write_json(output / "source_question.json", source_answer)

        stage = "complete_neptune_parity"
        mirror = Mirror(endpoint, region) if mirror is None else mirror
        verification = mirror.verify(graph)
        require(sealed(verification) and verification.get("graph_sha256") == graph_sha
                and verification.get("complete_record_parity") is True, "Full Neptune source parity was not verified.")
        report["dataset_id"] = verification["dataset_id"]
        report["parity_receipt_sha256"] = verification["content_sha256"]
        report["full_parity_verified_at"] = verification["verified_at"]
        write_json(output / "parity_verification.json", verification)
        report["checks"][stage] = "passed"

        stage = "fresh_neptune_context_read"
        incident = mirror.inspect(graph, PROFILE, limit=1000)
        require(incident.get("graph_sha256") == graph_sha and incident.get("dataset_id") == verification["dataset_id"]
                and incident.get("node_id") == PROFILE and incident.get("truncated") is False
                and incident.get("verification_receipt_sha256") == verification["content_sha256"],
                "Neptune context read is incomplete or belongs to a different verified source.")
        # Only these two database-returned inventories supply qualifying records.
        # Other fields retain canonical labels, declared scope and source metadata.
        database_graph = {**graph, "edges": incident["edges"], "assertions": incident["assertions"]}
        database_answer = question(database_graph, run.name)
        require(untruncated(database_answer), "The Neptune-backed context answer is truncated.")
        ids = selected_ids(database_answer)
        require(ids == selected_ids(source_answer), "Neptune question selected different assertion/evidence IDs.")
        for field in ("citations", "results", "summary", "discordant_annotations", "nodes"):
            require(database_answer[field] == source_answer[field], "Neptune question differs in preserved " + field + ".")
        write_json(output / "neptune_inspection.json", incident)
        write_json(output / "neptune_question.json", database_answer)
        report["selected_ids"] = ids
        report["checks"][stage] = "passed"

        stage = "database_graph_roundtrip"
        export = mirror.export_graph(graph, output / "database_roundtrip")
        exported_file = output / "database_roundtrip" / "graph.json"
        exported = json.loads(exported_file.read_text(encoding="utf-8"))
        require(sealed(export) and export.get("graph_sha256") == graph_sha
                and export.get("dataset_id") == verification["dataset_id"]
                and export.get("reconstructed_from_database") is True and export.get("complete_graph_parity") is True,
                "A complete database reconstruction receipt is required.")
        require(sha(exported_file) == export["files"]["graph.json"], "Exported graph bytes differ from the export receipt.")
        require(exported == graph and digest(exported) == graph_sha, "The database graph does not reproduce the complete source graph.")
        report["roundtrip"] = {"graph_sha256": digest(exported), "export_file_sha256": sha(exported_file),
            "export_receipt_sha256": export["content_sha256"],
            "note": "Canonical graph content matches exactly. Raw file SHA is verified against its export receipt; serialization key order can differ from original source files."}
        report["checks"][stage] = "passed"

        universe = sorted({edge_id for assertion in exported["assertions"]
                           if assertion["kind"] == "variant_therapy_response"
                           for edge_id in assertion["evidence_edge_ids"]})
        off_scope = sorted(set(universe) - set(ids["evidence_edge_ids"]))
        report["context"] = {"relevant_assertions": len(ids["assertion_ids"]),
            "relevant_evidence_edges": len(ids["evidence_edge_ids"]), "off_scope_evidence_edges": len(off_scope),
            "disagreement_groups": len(database_answer["discordant_annotations"]),
            "off_scope_evidence_edge_ids": off_scope,
            "removal_decisions": 0, "pruning_performed": False,
            "note": "No decisions or removals are made. Matching structured context is not a biological truth label."}
        if scope_reference is not None:
            stage = "prepared_scope_reference"
            report["scope_reference"] = reference_check(scope_reference, graph, source_answer, ids, off_scope)
            report["checks"][stage] = "passed"
        report["status"] = "passed"
    except Exception as exc:
        report["checks"][stage] = "failed"
        # External failures must not dump signed requests or credential details.
        report["error"] = str(exc) if isinstance(exc, AcceptanceError) else stage.replace("_", " ") + " failed (" + type(exc).__name__ + ")."
    finally:
        if before is not None:
            try:
                after = source_hashes(run)
                unchanged = before == after
                write_json(output / "source_hashes.json", {"before": before, "after": after, "unchanged": unchanged})
                report["checks"]["source_bytes_unchanged"] = "passed" if unchanged else "failed"
                if not unchanged:
                    report["status"] = "failed"
                    report["error"] = "Source artifact bytes changed during the check."
            except Exception:
                report["checks"]["source_bytes_unchanged"] = "failed"
                report["status"] = "failed"
                report["error"] = "Source artifact bytes could not be verified after the check."
        report["finished_at"] = utcnow()
        write_json(output / "report.json", report)
        (output / "report.html").write_text(html_report(report), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="Verified saved CRC/CIViC workspace; never modified.")
    parser.add_argument("--neptune-endpoint", required=True, help="Credential-free HTTPS Neptune Database endpoint.")
    parser.add_argument("--aws-region", required=True)
    parser.add_argument("--out", required=True, type=Path, help="New local result directory outside the source run.")
    parser.add_argument("--scope-reference", type=Path, help="Prepared baseline.json, or its containing directory, for the fixed 8/38 context comparison.")
    args = parser.parse_args(argv)
    try:
        report = check(args.run, args.neptune_endpoint, args.aws_region, args.out, args.scope_reference)
    except AcceptanceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "backend": "neptune", "report": str(args.out.resolve() / "report.html")}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
