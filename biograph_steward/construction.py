"""Bounded exact-cohort construction using the existing Pharos adapter.

Publication verifies a deterministic replay of the recorded GraphQL exchanges.
This verifies our transformation and trace, not the truth of source annotations.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile

from .client import (LICENSES, SCHEMA_SOURCE, VERSION, PharosClient, PharosError,
                     digest, utcnow, write_json)
from .file_utils import sha
from .graph import UNIPROT, build_graph, save_run, verify_snapshot
from .retrieval import BATCH_SIZE, MAX_LIMITS, ROW_BUDGET, retrieve_context

POLICY = "biograph-steward.cohort-construction.v1"
RECEIPT = "construction_receipt.json"
PROFILES = {
    "ppi": {key: 5000 if key == "ppis" else 0 for key in MAX_LIMITS},
    "context": {"pathways": 2000, "go": 500, "ppis": 5000,
                "drugs": 100, "expressions": 0, "publications": 20},
}


def plan_construction(request):
    """Resolve only supported tool choices; no source access or alias guessing."""
    allowed = {"accessions", "focus_uniprot", "profile", "relations"}
    if not isinstance(request, dict) or set(request) != allowed:
        raise ValueError("Construction requires accessions, focus_uniprot, profile and relations only.")
    ids = request["accessions"]
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 25
            or any(not isinstance(uid, str) or not UNIPROT.fullmatch(uid) for uid in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("Supply 1–25 unique exact UniProt accessions; aliases are not substituted.")
    if not isinstance(request["focus_uniprot"], str) or request["focus_uniprot"] not in ids:
        raise ValueError("The focus protein must be one of the requested accessions.")
    profile, relations = request["profile"], request["relations"]
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("Choose the ppi or context retrieval profile.")
    if (not isinstance(relations, list) or not relations
            or any(not isinstance(r, str) or r not in {"interactions", "shared_pathways"} for r in relations)
            or len(set(relations)) != len(relations)):
        raise ValueError("Choose distinct interactions and/or shared_pathways relations.")
    if profile == "ppi" and relations != ["interactions"]:
        raise ValueError("Shared pathway questions require the context profile.")
    return {"policy": POLICY, "profile": profile, "focus_uniprot": request["focus_uniprot"],
            "accessions": list(ids), "relations": list(relations),
            "limits_per_target": deepcopy(PROFILES[profile]), "row_budget": ROW_BUDGET,
            "tools": ["exact_pharos_identity", "retrieve_context", "build_graph", "answer_question"],
            "ppi_confidence": 400, "ppi_partners": "declared_cohort_only",
            "publication_state": "candidate", "llm_used": False,
            "biological_validation_performed": False}


def _identity_query(ids):
    # Same explicit-ID query as the audited inventory adapter. Kept here to avoid
    # a production dependency on a research script or changing frozen retrieval.
    definitions = ", ".join(f"$id{i}: String!" for i in range(len(ids)))
    fields = " ".join(f"t{i}: target(q: {{uniprot: $id{i}}}) {{ uniprot sym name tdl fam }}"
                      for i in range(len(ids)))
    return f"query ExplicitInventoryTargets({definitions}) {{ {fields} }}", {
        f"id{i}": uid for i, uid in enumerate(ids)}


def construct_snapshot(client, request, *, data_kind="live_pharos"):
    return _construct_snapshot(client, request, data_kind=data_kind, created_at=utcnow())


def _construct_snapshot(client, request, *, data_kind, created_at):
    plan = plan_construction(request)
    if data_kind not in {"live_pharos", "synthetic_demo"}:
        raise ValueError("Construction must identify live or synthetic source data.")
    start = len(client.records)
    before = client.execute(VERSION, cache=False).get("dbVersion")
    if not before:
        raise PharosError("Pharos did not report its database version.")
    licenses = client.execute(LICENSES).get("dataSourceCounts")
    if not isinstance(licenses, list):
        raise PharosError("Pharos did not return its source license inventory.")
    ids, targets, resolutions = request["accessions"], [], []
    for offset in range(0, len(ids), BATCH_SIZE):
        index = len(client.records) - start
        data = client.execute(*_identity_query(ids[offset:offset + BATCH_SIZE]))
        for i, uid in enumerate(ids[offset:offset + BATCH_SIZE]):
            key = f"t{i}"
            row = data.get(key)
            if key not in data or (row is not None and not isinstance(row, dict)):
                raise PharosError("Malformed explicit identity response.")
            status = ("not_found" if row is None else
                      "resolved" if row.get("uniprot") == uid else "identity_mismatch")
            resolutions.append({"requested_uniprot": uid, "status": status,
                                "returned_uniprot": row.get("uniprot") if row else None,
                                "returned": deepcopy(row), "request_index": index,
                                "response_pointer": f"/data/{key}"})
            if status == "resolved":
                targets.append(deepcopy(row))
    coverage = retrieve_context(client, targets, plan["limits_per_target"],
                                row_budget=plan["row_budget"], expression_scope="all",
                                ppi_cohort=ids, batch_sizes={"ppis": 1})
    for row in coverage["targets"]:
        for page in row["pages"]:
            page["request_index"] -= start
    after = client.execute(VERSION, cache=False).get("dbVersion")
    if before != after:
        raise PharosError("Pharos version changed during retrieval; no construction was published.")
    warnings = ["Source annotations remain candidates; publication does not validate their biological accuracy.",
                "PPI sources include functional associations; an interaction edge is not necessarily physical binding.",
                "Missing source annotations do not establish negative biological evidence.",
                "Version checks and row counts do not make offset pagination an atomic upstream snapshot."]
    if len(targets) != len(ids):
        warnings.append("Some requested identifiers did not resolve exactly; see target_resolution.json.")
    if any(r["status"] not in {"complete", "not_requested"} for r in coverage["targets"]):
        warnings.append("Some evidence families are incomplete; inspect retrieval_coverage.json.")
    if data_kind == "synthetic_demo":
        warnings.insert(0, "SYNTHETIC EXAMPLE: all source annotations are invented, not scientific evidence.")
    snapshot = {
        "snapshot_format": "biograph-steward.pharos.v1", "data_kind": data_kind,
        "created_at": created_at, "endpoint": client.endpoint, "db_version": before,
        "disease": None, "scope": {"kind": "protein_cohort", "name": "Explicit protein cohort",
            "requested_uniprot": list(ids), "resolutions": resolutions},
        "targets": targets, "requests": deepcopy(client.records[start:]),
        "source_licenses": licenses,
        "schema_check": {"status": "validated_by_successful_queries", "schema_source": SCHEMA_SOURCE},
        "query_settings": {"profile": request["profile"], "context_limits": plan["limits_per_target"],
                           "accessions": list(ids), "identity_policy": "exact_no_alias_substitution"},
        "retrieval": {"requested_targets": len(ids), "records_retrieved": len(targets),
                      "unresolved_targets": len(ids) - len(targets), "context": coverage},
        "construction": {"policy": POLICY, "request": deepcopy(request), "plan": plan},
        "warnings": warnings,
    }
    snapshot["content_sha256"] = digest(snapshot)
    verify_snapshot(snapshot)
    return snapshot


class _RecordedClient:
    """Replay only the recorded exchanges; never fetch or silently skip a call."""
    def __init__(self, snapshot):
        self.endpoint = snapshot["endpoint"]
        self.envelopes = snapshot["requests"]
        self.records = []

    def execute(self, query, variables=None, cache=True):
        index = len(self.records)
        if index >= len(self.envelopes):
            raise ValueError("Construction trace is missing a source response.")
        row = self.envelopes[index]
        if (row.get("endpoint") != self.endpoint
                or row.get("request") != {"query": query, "variables": variables or {}}
                or row.get("response_sha256") != digest(row.get("response"))):
            raise ValueError("Construction trace does not match the bounded retrieval plan.")
        PharosClient._validate_response(row["response"])
        self.records.append(deepcopy(row))
        return deepcopy(row["response"]["data"])


def verify_construction_snapshot(snapshot):
    try:
        verify_snapshot(snapshot)
        client = _RecordedClient(snapshot)
        rebuilt = _construct_snapshot(client, snapshot["construction"]["request"],
                                      data_kind=snapshot["data_kind"], created_at=snapshot["created_at"])
        if len(client.records) != len(client.envelopes) or rebuilt != snapshot:
            raise ValueError("Construction snapshot does not replay from its recorded source responses.")
    except (KeyError, TypeError, IndexError, PharosError) as exc:
        raise ValueError("Invalid construction source trace: " + str(exc)) from exc
    return snapshot


def _files(folder):
    return {p.relative_to(folder).as_posix(): sha(p)
            for p in sorted(folder.rglob("*")) if p.is_file() and p != folder / RECEIPT}


def _implementation():
    names = ("construction", "client", "retrieval", "graph", "context", "normalization",
             "assertions", "questions", "benchmark", "gold_packet", "file_utils")
    return {name: sha(Path(__file__).with_name(name + ".py")) for name in names}


def publish_construction(snapshot, out, *, planning_trace=None):
    """Verify offline, stage all artifacts, then publish the directory atomically."""
    out = Path(out).absolute()
    if out.exists() or out.is_symlink():
        raise ValueError("Choose a new immutable construction output directory.")
    verify_construction_snapshot(snapshot)
    if planning_trace is not None:
        from .construction_planning import verify_construction_plan_trace
        planned_request = verify_construction_plan_trace(planning_trace)
        if planned_request is None or planned_request != snapshot["construction"]["request"]:
            raise ValueError("The validated construction plan does not match this source request.")
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".construction-", dir=out.parent))
    packet_stage = stage.with_name(stage.name + "-packet")
    try:
        graph = save_run(snapshot, stage, run_mode="construction")
        if planning_trace is not None:
            write_json(stage / "construction_planner_trace.json", planning_trace)
            manifest = json.loads((stage / "run_manifest.json").read_text(encoding="utf-8"))
            manifest["construction_planner_trace_sha256"] = digest(planning_trace)
            write_json(stage / "run_manifest.json", manifest)
        if any(not row.get("source_response_locators") for row in graph["context_records"]):
            raise ValueError("A retained context record lacks a raw source locator.")
        if any(not (edge.get("retrieval_provenance") or {}).get("source_responses") for edge in graph["edges"]):
            raise ValueError("A published evidence edge lacks a raw source locator.")
        from .questions import answer_question, save_answer
        request = snapshot["construction"]["request"]
        resolved = {t["uniprot"] for t in snapshot["targets"]}
        answer = None
        if request["focus_uniprot"] in resolved:
            answer = answer_question(graph, protein="UniProtKB:" + request["focus_uniprot"],
                                     relations=request["relations"], view="candidates", source_run=out.name)
            save_answer(answer, stage / "answer")
            write_json(stage / "question.json", answer)
            report = stage / "report.html"
            report.write_text(report.read_text(encoding="utf-8").replace(
                '<body>', '<body><p class="notice"><a href="answer/report.html">Open the saved cited answer</a>'
                ' — candidate evidence for inspection.</p>', 1), encoding="utf-8")
        from .gold_packet import export_packet, load_packet
        export_packet(stage, packet_stage)
        packet_stage.rename(stage / "gold_packet")
        load_packet(stage / "gold_packet")
        receipt = {"format": POLICY, "status": "published", "created_at": utcnow(),
                   "snapshot_sha256": snapshot["content_sha256"], "graph_sha256": digest(graph),
                   "question_sha256": digest(answer) if answer else None,
                   "answer_status": "answered" if answer else "anchor_unresolved",
                   "request": deepcopy(request), "plan": snapshot["construction"]["plan"],
                   "source_envelopes": len(snapshot["requests"]),
                   "verification": "recorded_response_replay_and_graph_rebuild",
                   "llm_used": False, "biological_validation_performed": False,
                   "official_scoring_performed": False, "files": _files(stage)}
        receipt["implementation_sha256"] = _implementation()
        if planning_trace is not None:
            receipt["selection_mode"] = "validated_model_plan"
            receipt["llm_used"] = planning_trace.get("planner_kind", "").startswith("live_")
            receipt["execution_llm_used"] = False
            receipt["planning_trace_sha256"] = digest(planning_trace)
            receipt["planner_implementation_sha256"] = sha(Path(__file__).with_name("construction_planning.py"))
        receipt["content_sha256"] = digest(receipt)
        write_json(stage / RECEIPT, receipt)
        verify_construction_run(stage)
        # os.rename refuses an occupied nonempty destination; recheck also
        # rejects existing empty outputs instead of replacing user directories.
        if out.exists() or out.is_symlink():
            raise ValueError("Construction output appeared during publication; choose a new output.")
        stage.rename(out)
        return {"graph": graph, "question": answer, "construction": receipt}
    except BaseException:
        # Only directories created by this invocation are removed.
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(packet_stage, ignore_errors=True)
        raise


def run_construction(client, request, out):
    if Path(out).exists() or Path(out).is_symlink():
        raise ValueError("Choose a new immutable construction output directory.")
    return publish_construction(construct_snapshot(client, request), out)


def run_planned_construction(client, trace, out):
    """Execute only a validated bounded plan; the model never fetches evidence."""
    from .construction_planning import verify_construction_plan_trace
    request = verify_construction_plan_trace(trace)
    if request is None:
        raise ValueError("This construction plan cannot execute; inspect its abstention or error.")
    if Path(out).exists() or Path(out).is_symlink():
        raise ValueError("Choose a new immutable construction output directory.")
    return publish_construction(construct_snapshot(client, request), out, planning_trace=trace)


def verify_construction_run(directory):
    folder = Path(directory)
    if folder.is_symlink() or not folder.is_dir() or any(p.is_symlink() for p in folder.rglob("*")):
        raise ValueError("Construction publications must contain regular files, without symlinks.")
    try:
        receipt = json.loads((folder / RECEIPT).read_text())
        if (receipt.get("format") != POLICY or receipt.get("status") != "published"
                or receipt.get("content_sha256") != digest({k: v for k, v in receipt.items() if k != "content_sha256"})
                or receipt.get("files") != _files(folder)):
            raise ValueError("Construction receipt or its published files changed.")
        if receipt.get("implementation_sha256") != _implementation():
            raise ValueError("Construction implementation changed. Preserve this publication and republish its snapshot into a new directory to verify with the current code.")
        required = {"snapshot.json", "graph.json", "run_manifest.json", "review_events.json", "report.html",
                    "cohort_scope.json", "target_resolution.json", "retrieval_coverage.json", "source_licenses.json",
                    "pipeline_trace.json", "assertions.json", "context_records.json", "normalization_report.json",
                    "nodes.tsv", "edges.tsv"}
        if not required <= set(receipt["files"]):
            raise ValueError("Construction publication is missing required artifacts.")
        snapshot = verify_construction_snapshot(json.loads((folder / "snapshot.json").read_text()))
        graph = json.loads((folder / "graph.json").read_text())
        events = json.loads((folder / "review_events.json").read_text())
        manifest = json.loads((folder / "run_manifest.json").read_text())
        if (events != [] or build_graph(snapshot) != graph or receipt["graph_sha256"] != digest(graph)
                or receipt["snapshot_sha256"] != snapshot["content_sha256"]
                or manifest["run_mode"] != "construction"
                or manifest["snapshot_sha256"] != snapshot["content_sha256"]
                or receipt["request"] != snapshot["construction"]["request"]
                or receipt["plan"] != plan_construction(receipt["request"])
                or receipt.get("source_envelopes") != len(snapshot["requests"])
                or receipt.get("verification") != "recorded_response_replay_and_graph_rebuild"
                or any(receipt.get(key) is not False for key in
                       ("biological_validation_performed", "official_scoring_performed"))):
            raise ValueError("Published graph or plan does not match its recorded source.")
        from .questions import answer_question, verify_answer
        answer_path = folder / "question.json"
        resolved = {t["uniprot"] for t in snapshot["targets"]}
        request = receipt["request"]
        planning_path = folder / "construction_planner_trace.json"
        if planning_path.exists() or receipt.get("selection_mode") is not None:
            from .construction_planning import verify_construction_plan_trace
            trace = json.loads(planning_path.read_text())
            if (receipt.get("selection_mode") != "validated_model_plan"
                    or receipt.get("llm_used") is not trace.get("planner_kind", "").startswith("live_")
                    or receipt.get("execution_llm_used") is not False
                    or receipt.get("planning_trace_sha256") != digest(trace)
                    or manifest.get("construction_planner_trace_sha256") != digest(trace)
                    or receipt.get("planner_implementation_sha256") != sha(Path(__file__).with_name("construction_planning.py"))
                    or verify_construction_plan_trace(trace) != request):
                raise ValueError("Construction planner trace does not match the published request.")
        elif any(key in receipt for key in ("planning_trace_sha256", "planner_implementation_sha256")):
            raise ValueError("Construction planner trace is missing.")
        elif receipt.get("llm_used") is not False:
            raise ValueError("Deterministic construction cannot claim a model call.")
        if request["focus_uniprot"] in resolved:
            answer = json.loads(answer_path.read_text())
            verify_answer(answer)
            rebuilt = answer_question(graph, protein="UniProtKB:" + request["focus_uniprot"],
                                      relations=request["relations"], view="candidates", source_run=answer["source_run"])
            if (rebuilt != answer or receipt["question_sha256"] != digest(answer)
                    or receipt["answer_status"] != "answered"
                    or json.loads((folder / "answer/question.json").read_text()) != answer):
                raise ValueError("Published answer does not replay from its graph.")
        elif answer_path.exists() or receipt["question_sha256"] is not None or receipt["answer_status"] != "anchor_unresolved":
            raise ValueError("Unresolved focus cannot have a published answer.")
        from .gold_packet import load_packet
        _, packet_graph, *_ = load_packet(folder / "gold_packet")
        if packet_graph != graph:
            raise ValueError("Published graph and gold-interface packet differ.")
        return receipt
    except (KeyError, TypeError, IndexError, OSError, json.JSONDecodeError) as exc:
        raise ValueError("Incomplete or invalid construction publication: " + str(exc)) from exc


def demo_construction_snapshot():
    """Invented records served through the same adapter; never label them live."""
    ids = ["P00533", "P01116", "P15056"]
    identities = {uid: {"uniprot": uid, "sym": "SYNTHETIC_" + str(i + 1),
                       "name": "Invented protein record " + str(i + 1), "tdl": "Tbio", "fam": "TEST"}
                  for i, uid in enumerate(ids)}
    context = {uid: {key: [] for key in MAX_LIMITS} for uid in ids}
    for i, uid in enumerate(ids):
        context[uid]["pathways"] = [{"pwid": 1, "name": "Invented shared pathway", "type": "SYNTHETIC",
                                     "sourceID": "SYNTHETIC:1", "url": None}]
        context[uid]["ppis"] = [{"nid": i * 10 + j, "type": "SYNTHETIC", "props": [],
                                 "target": {k: identities[other][k] for k in ("uniprot", "sym", "name")}}
                                for j, other in enumerate(ids) if other != uid]

    def count(uid, family):
        n = len(context[uid][family])
        return n if family == "publications" else [{"name": "Total" if family == "ppis" else
                                                    "drug" if family == "drugs" else "SYNTHETIC", "value": n}]

    def transport(payload):
        query, variables = payload["query"], payload["variables"]
        if "DatabaseVersion" in query:
            return {"data": {"dbVersion": "synthetic-construction-v1"}}
        if "SourceLicenses" in query:
            return {"data": {"dataSourceCounts": [{"dataSource": "SYNTHETIC", "url": None,
                                                    "license": "Invented example only", "licenseURL": None}]}}
        result = {}
        for i in range(sum(k.startswith("id") for k in variables)):
            uid = variables[f"id{i}"]
            if "ExplicitInventoryTargets" in query:
                row = identities[uid]
            elif "ScopedMetadata" in query:
                row = {"uniprot": uid, "dataSources": ["SYNTHETIC"], "affiliate_links": [],
                       **{key: count(uid, family) for key, family in [
                           ("pathwayCounts", "pathways"), ("goCounts", "go"), ("ppiCounts", "ppis"),
                           ("ligandCounts", "drugs"), ("expressionCounts", "expressions"), ("publicationCount", "publications")]}}
            elif "Scoped_" in query:
                family = query.split("Scoped_")[1].split("(")[0]
                skip, top = variables[f"skip{i}"], variables[f"top{i}"]
                row = {"uniprot": uid, "reported": count(uid, family), "rows": context[uid][family][skip:skip + top]}
            else:
                raise ValueError("Unexpected synthetic construction query.")
            result[f"t{i}"] = deepcopy(row)
        return {"data": result}

    request = {"accessions": ids, "focus_uniprot": "P01116", "profile": "context",
               "relations": ["interactions", "shared_pathways"]}
    return construct_snapshot(PharosClient(transport=transport), request, data_kind="synthetic_demo")
