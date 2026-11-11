"""Offline bridge to the released OptimusKG literature-support audit.

This prepares consumed development cases, not biological truth labels. The
author's endpoint-only prompt is read as a literal from hash-pinned source;
third-party code is never imported or executed. Hosted submission remains a
separate, explicitly configured step in the author's runner.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from copy import deepcopy
import csv
from html import escape
import io
import json
from pathlib import Path
import re

from .client import digest, utcnow, write_json
from .file_utils import new_output, sha
from .questions import graph_basis
from .reviews import read_run

FORMAT = "biograph-steward.support-search-comparator.v1"
UPSTREAM_COMMIT = "4fb352919ef6d7ecc5093277b5daf08f44ce6d60"
UPSTREAM = "https://github.com/mims-harvard/OptimusKG"
UPSTREAM_FILES = {
    "cli/commands/evals/paperqa.py": "c644f197187c3faa701b958235a0e6836e9dac67b84add672a5c1dbdba5251f6",
    "cli/commands/evals/sample_edges.py": "d2929cc717fcc3b871b6156b4c6a0f867097021736adafa7b97e7a87816cec4a",
    "conf/base/evals.yml": "9026fb3c5701d4b3533c2d9ba9aa5a5372704415cbbe7ce4b699d2b481c4fd32",
    "LICENSE": "8331be831422b5915d317e9c7d81be59f410526fe29e34d8c3fc2c90655ffe0a",
}
# Explicit category translation to author-supplied evaluation node types. IDs
# remain unchanged; GEN's broad label does not merge gene and protein entities.
CATEGORY_TYPES = {"biolink:Protein": "GEN", "biolink:Gene": "GEN",
                  "biolink:Disease": "DIS", "biolink:Pathway": "PWY",
                  "biolink:BiologicalProcess": "BPO", "biolink:CellularComponent": "CCO",
                  "biolink:MolecularActivity": "MFN", "biolink:AnatomicalEntity": "ANA"}
LIMITATIONS = [
    "These are previously consumed development examples, not a representative or held-out scientific evaluation.",
    "The original query asks about endpoint association; it does not check the saved predicate, direction or qualifiers.",
    "An author's 1-5 support rating is not calibrated scientific accuracy, independence or an automatic pruning rule.",
    "No evidence found does not mean false; an unavailable search or malformed response is an unresolved access/result gap.",
    "Source publications may be rediscovered by the search. Repeated records and database names are not independent experiments.",
    "No negative biological labels are generated from graph nonedges.",
    "The released runner uses hosted Edison PaperQA3; open PaperQA2 and our Brev model are different systems.",
]


def _ordinary(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 20_000_000:
        raise ValueError("Expected an ordinary bounded input file.")
    return path.read_bytes()


def load_upstream(folder):
    """Verify the pinned author artifacts; extract constants without execution."""
    folder = Path(folder)
    for name, expected in UPSTREAM_FILES.items():
        _ordinary(folder / name)
        if sha(folder / name) != expected:
            raise ValueError("Pinned OptimusKG source changed: " + name)
    tree = ast.parse((folder / "cli/commands/evals/paperqa.py").read_text())
    values = {}
    for node in tree.body:
        target = (node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1
                  else node.target if isinstance(node, ast.AnnAssign) else None)
        if isinstance(target, ast.Name) and target.id in {"PROMPT_TEMPLATE", "NODE_TYPE_MAP"}:
            values[target.id] = ast.literal_eval(node.value)
    if not isinstance(values.get("PROMPT_TEMPLATE"), str) or not isinstance(values.get("NODE_TYPE_MAP"), dict):
        raise ValueError("Pinned author prompt constants are unavailable.")
    return values["PROMPT_TEMPLATE"], values["NODE_TYPE_MAP"]


def _reuse_context(source):
    """Retain an unchanged historical supplement without overriding its guard.

    A code-version mismatch is explicitly separate from replay verification.
    Every captured file still has to match the supplement's original inventory;
    any other integrity failure propagates rather than becoming unknown reuse.
    """
    from .assay_source_reuse import read_reuse, _implementation, _source_files, _sealed, FORMAT as REUSE_FORMAT
    try:
        report = read_reuse(source)
    except ValueError as exc:
        if str(exc) != "Source-reuse audit: manifest or implementation changed.":
            raise
        manifest = json.loads(_ordinary(source / "source_reuse_manifest.json"))
        if (not _sealed(manifest) or manifest.get("format") != REUSE_FORMAT
                or manifest.get("implementation_sha256") == _implementation()
                or _source_files(source) != {**manifest["workspace_files"], **manifest["supplement_files"],
                    "source_reuse_manifest.json": sha(source / "source_reuse_manifest.json")}):
            raise ValueError("Historical source-reuse supplement integrity failed.") from exc
        report = json.loads(_ordinary(source / "source_reuse.json"))
        if not _sealed(report) or report.get("format") != REUSE_FORMAT:
            raise ValueError("Historical source-reuse report seal changed.")
        return {"observations": report["observations"],
                "verification": "unchanged_historical_supplement_not_replayed",
                "manifest_sha256": sha(source / "source_reuse_manifest.json"),
                "note": "Saved report bytes are unchanged; its original implementation binding differs from current code. "
                        "Reuse descriptions below are preserved historical findings, not a new replay verification."}
    return {"observations": (report or {}).get("observations", []),
            "verification": "replay_verified" if report else "no_supplement_available",
            "note": "Unobserved reuse is unresolved; no independence is inferred."}


def _case(graph, assertion_id, source, reason, template, node_types, reuse):
    assertions = [a for a in graph["assertions"] if a["id"] == assertion_id]
    if len(assertions) != 1:
        raise ValueError("Choose one exact assertion from the saved run.")
    assertion = assertions[0]
    nodes = {n["id"]: n for n in graph["nodes"]}
    ends = [nodes.get(assertion[k]) for k in ("subject", "object")]
    if any(not n or n.get("category") not in CATEGORY_TYPES or not n.get("name") for n in ends):
        raise ValueError("Endpoint categories/names are outside this explicit upstream mapping.")
    row = {"seed_node_id": ends[0]["id"], "target_node_id": ends[1]["id"],
           "seed_node_type": CATEGORY_TYPES[ends[0]["category"]],
           "target_node_type": CATEGORY_TYPES[ends[1]["category"]],
           "seed_node_name": ends[0]["name"], "target_node_name": ends[1]["name"],
           "relation_type": assertion["predicate"]}
    query = template.format(seed_type=node_types[row["seed_node_type"]],
                            seed_name=row["seed_node_name"],
                            target_type=node_types[row["target_node_type"]],
                            target_name=row["target_node_name"])
    evidence_ids = set(assertion["evidence_edge_ids"])
    evidence = [deepcopy(e) for e in graph["edges"] if e["id"] in evidence_ids]
    if {e["id"] for e in evidence} != evidence_ids:
        raise ValueError("Saved assertion has missing evidence edges.")
    obs_id = assertion["qualifiers"].get("observation_id")
    reuse_rows = [deepcopy(r) for r in (reuse or {}).get("observations", [])
                  if r.get("observation_id") == obs_id]
    binding = {"run": str(Path(source).absolute()), "graph_basis_sha256": graph_basis(graph),
               "snapshot_sha256": graph["snapshot_sha256"], "assertion_id": assertion_id,
               "assertion_revision": assertion["revision"],
               "graph_file_sha256": sha(Path(source) / "graph.json")}
    case = {"case_id": "support-case:" + digest(binding)[:24], "source": binding,
            "selection_reason": reason, "partition": "consumed_development",
            "assertion": deepcopy(assertion), "evidence": evidence, "reuse": reuse_rows,
            "reuse_verification": {k: v for k, v in (reuse or {}).items() if k != "observations"},
            "upstream_row": row, "upstream_query": query, "upstream_query_sha256": digest(query),
            "qualified_scope_sent_to_upstream": False,
            "omitted_from_query": {"predicate": assertion["predicate"],
                "direction_and_symmetry": {"subject": assertion["subject"], "object": assertion["object"],
                                           "symmetric": assertion.get("symmetric", False)},
                "qualifiers": deepcopy(assertion["qualifiers"]),
                "source_publications": deepcopy(assertion.get("publications", []))},
            "scientific_truth_label": None, "independent_reference": False}
    case["request_sha256"] = digest(case)
    return case


def _csv(rows):
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    return handle.getvalue()


def prepare_comparator(selections, output, upstream):
    """Prepare 1-8 explicitly selected consumed cases, without a service call.

    Each selection supplies run, assertion_id and consumed_development_reason.
    No source filtering, random nonedges or held-out material is selected here.
    """
    if not isinstance(selections, list) or not 1 <= len(selections) <= 8:
        raise ValueError("Select 1-8 explicit consumed development assertions.")
    template, node_types = load_upstream(upstream)
    cases, loaded = [], {}
    for selection in selections:
        if not isinstance(selection, dict) or set(selection) != {"run", "assertion_id", "consumed_development_reason"}:
            raise ValueError("Explicit run, assertion and consumed-development reason are required.")
        reason = selection["consumed_development_reason"]
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
            raise ValueError("Document prior development use; do not select an unseen evaluation case.")
        source = Path(selection["run"]).absolute()
        if str(source) not in loaded:
            loaded[str(source)] = (read_run(source)[2], _reuse_context(source))
        graph, reuse = loaded[str(source)]
        cases.append(_case(graph, selection["assertion_id"], source, reason, template, node_types, reuse))
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("A development assertion was selected more than once.")
    queries = defaultdict(list)
    for case in cases:
        queries[case["upstream_query_sha256"]].append(case["case_id"])
    collisions = [{"query_sha256": key, "case_ids": ids} for key, ids in queries.items() if len(ids) > 1]
    report = {"format": FORMAT, "created_at": utcnow(), "status": "prepared_not_executed",
              "upstream_commit": UPSTREAM_COMMIT, "upstream_source_sha256": UPSTREAM_FILES,
              "upstream_repository": UPSTREAM, "partition": "consumed_development",
              "case_count": len(cases), "unique_query_count": len(queries),
              "identical_queries_for_different_assertions": collisions,
              "case_ids": [c["case_id"] for c in cases],
              "hosted_model_calls": 0, "graph_modified": False, "scientific_accuracy_measured": False,
              "hosted_requirements": {"service": "Edison hosted PaperQA3", "environment_key": "EDISON_API_KEY",
                  "author_job_selector": "JobNames.LITERATURE", "documented_dated_alias": "literature-20260216",
                  "underlying_agent_pinned_by_author_runner": False,
                  "current_price_and_access_verified": False,
                  "budget_note": "Author config records a historical $1/query assumption; current pricing is not established.",
                  "brev_is_equivalent": False},
              "limitations": LIMITATIONS}
    output = new_output(output, upstream, *loaded)
    write_json(output / "cases.json", cases)
    write_json(output / "report.json", report)
    rows = [{"case_id": c["case_id"], "request_sha256": c["request_sha256"], **c["upstream_row"]}
            for c in cases]
    (output / "sampled_edges_development.csv").write_text(_csv(rows), encoding="utf-8")
    # Keep the original MIT notice with the source-derived prompt text.
    (output / "OPTIMUSKG_LICENSE.txt").write_bytes(_ordinary(Path(upstream) / "LICENSE"))
    (output / "report.html").write_text(_html(report, cases), encoding="utf-8")
    manifest = {"format": FORMAT, "upstream_commit": UPSTREAM_COMMIT,
                "files": {p.name: sha(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / "manifest.json", {**manifest, "content_sha256": digest(manifest)})
    return report


def load_preparation(folder):
    folder = Path(folder)
    manifest = json.loads(_ordinary(folder / "manifest.json"))
    if manifest.get("format") != FORMAT or manifest.get("upstream_commit") != UPSTREAM_COMMIT or manifest.get("content_sha256") != digest(
            {k: v for k, v in manifest.items() if k != "content_sha256"}):
        raise ValueError("Comparator preparation manifest changed.")
    names = set(manifest.get("files", {}))
    if names != {"cases.json", "report.json", "sampled_edges_development.csv", "OPTIMUSKG_LICENSE.txt", "report.html"}:
        raise ValueError("Comparator inventory changed.")
    for name, expected in manifest["files"].items():
        if Path(name).name != name or sha(folder / name) != expected:
            raise ValueError("Prepared comparator bytes changed.")
        _ordinary(folder / name)
    cases = json.loads(_ordinary(folder / "cases.json"))
    for case in cases:
        if case["request_sha256"] != digest({k: v for k, v in case.items() if k != "request_sha256"}):
            raise ValueError("Prepared request binding changed.")
    return json.loads(_ordinary(folder / "report.json")), cases


def inspect_results(preparation, imported_csv, output):
    """Preserve a partial upstream submit/poll CSV and classify search status.

    Metadata fields pass through the author's CSV runner and bind each result
    to its exact prepared request. This does not authenticate the remote agent,
    citations or truth; provenance remains an externally supplied result.
    """
    report, cases = load_preparation(preparation)
    raw = _ordinary(imported_csv)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("Imported CSV has missing or duplicate column names.")
    records, seen, tasks = [], set(), set()
    expected = {c["case_id"]: c for c in cases}
    for row in reader:
        case_id = row.get("case_id")
        if case_id not in expected or case_id in seen:
            raise ValueError("Unknown or duplicate imported case identity.")
        case = expected[case_id]; seen.add(case_id)
        if row.get("request_sha256") != case["request_sha256"] or any(
                row.get(k) != str(v) for k, v in case["upstream_row"].items()):
            raise ValueError("Imported result belongs to a different request.")
        task_id = row.get("task_id", "").strip()
        if not task_id or task_id in tasks:
            raise ValueError("An imported task identity is missing or reused.")
        tasks.add(task_id)
        status = row.get("status", "")
        result = {"case_id": case_id, "task_id": task_id, "remote_status": status,
                  "qualified_assertion_verified": False, "scientific_truth_label": None,
                  "citations_independently_checked": False}
        if status == "success":
            answer = row.get("answer", "")
            reasoning = re.findall(r"<reasoning>\s*(.*?)\s*</reasoning>", answer, re.DOTALL)
            rating = re.findall(r"<rating>\s*(.*?)\s*</rating>", answer, re.DOTALL)
            valid = len(reasoning) == len(rating) == 1 and bool(reasoning[0]) and rating[0] in {"1", "2", "3", "4", "5"}
            result["search_status"] = ("no_support_reported" if rating == ["1"] else "support_reported") if valid else "invalid_response_unresolved"
            if row.get("has_successful_answer", "").strip().casefold() in {"false", "0"}:
                result["search_status"] = "no_successful_answer_unresolved"
            result["upstream_rating"] = int(rating[0]) if valid else None
            result["answer_sha256"] = digest(answer)
        elif status == "failed":
            result["search_status"] = "service_failure_unresolved"
        else:
            result["search_status"] = "pending_or_unknown_unresolved"
        records.append(result)
    if not records:
        raise ValueError("Imported CSV contains no result rows.")
    summary = {"format": FORMAT, "status": "external_partial_results_inspected",
               "preparation_manifest_sha256": sha(Path(preparation) / "manifest.json"),
               "imported_csv_sha256": sha(imported_csv), "results": records,
               "missing_case_ids": sorted(set(expected) - seen),
               "status_counts": dict(Counter(r["search_status"] for r in records)),
               "result_origin": "externally_supplied_not_authenticated", "hosted_calls_made_by_import": 0,
               "scientific_accuracy_measured": False, "graph_modified": False, "limitations": LIMITATIONS}
    output = new_output(output, preparation, imported_csv)
    (output / "upstream_results.csv").write_bytes(raw)
    write_json(output / "report.json", summary)
    return summary


def _html(report, cases):
    rows = "".join("<tr><td>" + escape(c["case_id"]) + "<br>" + escape(c["source"]["assertion_id"])
                   + "</td><td>" + escape(c["assertion"]["predicate"]) + "<pre>"
                   + escape(json.dumps(c["assertion"]["qualifiers"], indent=2))
                   + "</pre></td><td><details><summary>Author's exact endpoint query</summary><pre>"
                   + escape(c["upstream_query"]) + "</pre></details><p>Query: "
                   + escape(c["upstream_query_sha256"][:16]) + "</p></td><td>"
                   + escape(c["reuse_verification"].get("note", "")) + "<pre>"
                   + escape(json.dumps(c["reuse"], indent=2) if c["reuse"] else "Reuse unresolved; no independence inferred.") + "</pre>"
                   + "</td></tr>" for c in cases)
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Support-search comparator preparation</title>"
            "<style>body{font:16px system-ui;max-width:1300px;margin:32px auto;padding:0 20px;color:#173044}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:12px;vertical-align:top}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}td{overflow-wrap:anywhere}"
            ".note{background:#eef4f8;padding:18px}</style><h1>Support-search comparator</h1>"
            "<p class='note'>Prepared, not executed. These previously consumed examples test whether the released "
            "OptimusKG endpoint search fits our qualified assertions. No hosted calls, graph changes or accuracy scores.</p>"
            "<p>Method sources: <a href='https://arxiv.org/html/2604.27269v3'>OptimusKG paper</a> · "
            "<a href='https://github.com/mims-harvard/OptimusKG/blob/" + UPSTREAM_COMMIT +
            "/cli/commands/evals/paperqa.py'>Pinned author runner</a> · "
            "<a href='https://docs.edisonscientific.com/edison-client/readme'>Official service documentation</a>.</p>"
            f"<p>{report['case_count']} assertions; {report['unique_query_count']} distinct author queries; "
            f"{len(report['identical_queries_for_different_assertions'])} query groups collapse different assertions.</p>"
            "<table><thead><tr><th>Saved development case</th><th>Full assertion scope retained locally</th>"
            "<th>Upstream query</th><th>Source reuse</th></tr></thead><tbody>" + rows + "</tbody></table>"
            "<h2>What this can establish</h2><p>The upstream prompt can locate broad association literature. "
            "Its response does not by itself establish the predicate, assay or other qualifiers retained alongside it.</p>"
            "<ul>" + "".join("<li>" + escape(x) + "</li>" for x in LIMITATIONS) + "</ul>"
            "<p>The original runner requires an Edison API key and a separate current pricing/access check. "
            "Brev is not needed to inspect or prepare these files.</p><p>" +
            "<a href='cases.json'>Cases and provenance</a> · <a href='sampled_edges_development.csv'>Author-compatible CSV</a> · "
            "<a href='manifest.json'>File manifest</a> · <a href='OPTIMUSKG_LICENSE.txt'>Upstream MIT notice</a></p></html>")
