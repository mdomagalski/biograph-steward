from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .client import PharosClient, PharosError, ENDPOINT, VERSION, SEARCH, DISEASE, TARGETS, LICENSES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BioGraph Steward: inspect a small Pharos disease graph.")
    sub = parser.add_subparsers(dest="command")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--endpoint", default=ENDPOINT)
    common.add_argument("--cache-dir", type=Path, default=Path(".pharos_cache"))
    common.add_argument("--timeout", type=float, default=30)
    common.add_argument("--refresh", action="store_true")
    p = sub.add_parser("serve", parents=[common], help="Start the local browser interface (default).")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--runs-dir", type=Path, default=Path("runs"))
    p.add_argument("--no-browser", action="store_true")
    sub.add_parser("doctor", parents=[common], help="Test live connectivity and required GraphQL fields.")
    p = sub.add_parser("search", parents=[common], help="Search disease names; choose an exact returned term.")
    p.add_argument("term")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--skip", type=int, default=0)
    p = sub.add_parser("build", parents=[common], help="Build from LIVE Pharos (never falls back to demo).")
    p.add_argument("--disease", required=True)
    p.add_argument("--max-targets", type=int, default=25)
    p.add_argument("--page-size", type=int, default=25)
    p.add_argument("--pathways", type=int, default=5, help="Preview profile only: pathways per target.")
    p.add_argument("--profile", choices=["preview", "scoped"], default="preview")
    p.add_argument("--tissue-term", default="", help="Scoped expression search words, e.g. 'colon rectum'. Empty skips expression.")
    from .retrieval import DEFAULT_LIMITS
    for family, limit in DEFAULT_LIMITS.items():
        p.add_argument("--" + family + "-limit", type=int, default=limit, help="Scoped profile per-target cap (0 skips).")
    p.add_argument("--skip-schema-check", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("demo", help="Build the explicitly SYNTHETIC offline demo.")
    p.add_argument("--out", type=Path, default=Path("runs/demo"))
    p = sub.add_parser("replay", help="Rebuild a snapshot with the current transformer without network access.")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--reviews", type=Path, help="Preserve review events from this exact snapshot.")
    p.add_argument("--civic-snapshot", type=Path, help="Replay this verified CIViC sidecar without network access.")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("review", help="Record a human assertion decision in a new immutable run.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--assertion", required=True)
    p.add_argument("--state", choices=["candidate", "accepted", "provisional", "quarantined", "rejected", "obsolete"], required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("question", help="Answer a scoped protein-neighborhood question from a saved run.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--protein", required=True, help="Exact protein ID or unambiguous symbol in this cohort.")
    p.add_argument("--relations", choices=["interactions", "shared_pathways"], nargs="+", default=["interactions", "shared_pathways"])
    p.add_argument("--view", choices=["accepted", "candidates"], default="accepted")
    p.add_argument("--max-results", type=int, default=8)
    p.add_argument("--max-paths", type=int, default=2)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("civic", help="Add the bounded KRAS/DOID:9256 CIViC source to a new Pharos run.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--snapshot", type=Path, help="Use a saved CIViC snapshot instead of the live API.")
    p.add_argument("--max-items", type=int, default=100, help="Live retrieval cap per therapy, maximum 200.")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("therapy-question", help="Query whole molecular-profile/therapy evidence from a CIViC-enriched run.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--profile", default="all", help="Exact CIViC.molecularprofile:<id>, or all.")
    p.add_argument("--therapy", choices=["both","cetuximab","panitumumab"], default="both")
    p.add_argument("--view", choices=["accepted","candidates"], default="accepted")
    p.add_argument("--max-results", type=int, default=8)
    p.add_argument("--max-paths", type=int, default=3)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("queries", help="Export readable GraphQL requests used by this starter.")
    p.add_argument("--out", type=Path, default=Path("queries"))
    p = sub.add_parser("evaluation-init", help="Freeze Pharos/enriched sources and draft evaluation questions.")
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--enriched",type=Path,required=True)
    p.add_argument("--reviewed",type=Path)
    p.add_argument("--cases",type=Path)
    p.add_argument("--max-results",type=int,default=8)
    p.add_argument("--max-paths",type=int,default=3)
    p.add_argument("--out",type=Path,required=True)
    p = sub.add_parser("evaluation-run", help="Compare fixed-source deterministic tools and an optional single model planner.")
    p.add_argument("--suite",type=Path,required=True)
    p.add_argument("--planner",choices=['none','live','codex','replay'],default='none')
    p.add_argument("--replay",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p = sub.add_parser("evaluation-score", help="Score reviewer worksheets into a new result directory.")
    p.add_argument("--result",type=Path,required=True)
    p.add_argument("--case-reviews",type=Path)
    p.add_argument("--answer-reviews",type=Path)
    p.add_argument("--evidence-reviews",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p = sub.add_parser("plan-question", help="Plan and execute one research question through the bounded model planner.")
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--question",required=True)
    p.add_argument("--out",type=Path,required=True)
    p = sub.add_parser("audit", help="Prepare benchmark readiness and pair-level review files from a snapshot.")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser('verification-run', help='Evaluate a bounded source verifier against prepared SciFact expert annotations.')
    p.add_argument('--benchmark', type=Path, required=True)
    p.add_argument('--verifier', choices=['baselines', 'codex'], default='baselines')
    p.add_argument('--model', help='Explicit Codex model, or set BIOGRAPH_CODEX_MODEL.')
    p.add_argument('--limit', type=int, help='Fixed hash-selected pair limit for a smoke pilot; omit for the full input set.')
    p.add_argument('--workers', type=int, default=1, help='Concurrent independent verification turns, 1–4.')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('verification-score', help='Recompute metrics from a completed immutable verification result, without model calls.')
    p.add_argument('--result', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in {'verification-run', 'verification-score'}:
            from .verification_evaluation import run_verification, rescore_verification
            if args.command == 'verification-run':
                metrics = run_verification(args.benchmark, args.out, mode=args.verifier, model=args.model,
                                          limit=args.limit, workers=args.workers,
                                          progress=lambda message: print(message, file=sys.stderr, flush=True))
            else:
                metrics = rescore_verification(args.result, args.out)
            print(json.dumps({'status': metrics['status'], 'comparisons': metrics['comparisons'],
                              'report': str((args.out / 'report.html').resolve())}, indent=2))
            return 0
        if args.command is None:
            from .webapp import serve
            serve()
            return 0
        if args.command == "serve":
            from .webapp import serve
            serve(args.port, args.runs_dir, args.endpoint, args.cache_dir, not args.no_browser, args.timeout)
            return 0
        if args.command == 'evaluation-init':
            from .evaluation import freeze_suite
            cases=json.loads(args.cases.read_text()) if args.cases else None
            suite=freeze_suite(args.baseline,args.enriched,args.out,cases=cases,reviewed=args.reviewed,max_results=args.max_results,max_paths=args.max_paths)
            print(json.dumps({'suite_sha256':suite['suite_sha256'],'cases':len(suite['cases']),'reference_status':suite['reference_status']},indent=2))
            return 0
        if args.command == 'evaluation-run':
            from .evaluation import run_evaluation
            from .planning import configured_planner,RecordedPlanner,PlannerUnavailable
            planner=None;note=None
            if args.planner in {'live','codex'}:
                try:
                    if args.planner=='codex':
                        from .codex_planner import CodexPlanner
                        planner=CodexPlanner()
                    else:planner=configured_planner()
                except PlannerUnavailable as exc:note=str(exc)
            elif args.planner=='replay':
                if not args.replay:raise ValueError('Replay mode requires --replay; it is not live agent evidence.')
                planner=RecordedPlanner(json.loads(args.replay.read_text()))
            result,metrics=run_evaluation(args.suite,args.out,planner=planner,planner_note=note,
                                         progress=lambda message:print(message,file=sys.stderr,flush=True))
            print(json.dumps({'status':metrics['status'],'cases':metrics['cases'],'planner_kind':result['planner_kind'],
                              'scientific_improvement_established':False,'report':str((args.out/'report.html').resolve())},indent=2))
            return 0
        if args.command == 'evaluation-score':
            from .evaluation import score_evaluation
            metrics=score_evaluation(args.result,args.out,case_reviews=args.case_reviews,answer_reviews=args.answer_reviews,evidence_reviews=args.evidence_reviews)
            print(json.dumps(metrics,indent=2))
            return 0
        if args.command == 'plan-question':
            from .reviews import read_run
            from .planning import configured_planner,execute_plan
            from .evaluation import _new_directory
            from .client import write_json
            from .questions import save_answer
            _,_,graph=read_run(args.run)
            output=_new_directory(args.out)
            planner=configured_planner();trace=planner.plan(args.question,graph)
            write_json(output/'planner_trace.json',trace)
            if trace['status']!='validated':raise ValueError('Model plan failed validation; trace saved. No query was executed.')
            result=execute_plan(trace['plan'],graph,source_run=args.run.name)
            write_json(output/'execution.json',{k:v for k,v in result.items() if k!='answer'})
            if result['answer']:save_answer(result['answer'],output/'answer')
            print(json.dumps({'status':result['status'],'reason':result['reason'],'trace':str((output/'planner_trace.json').resolve())},indent=2))
            return 0
        if args.command == "question":
            from .reviews import read_run
            from .questions import answer_question, save_answer
            _, _, graph = read_run(args.run)
            answer = answer_question(graph, args.protein, relations=args.relations, view=args.view,
                                     max_results=args.max_results, max_paths=args.max_paths, source_run=args.run.name)
            save_answer(answer, args.out)
            print(json.dumps({"question": answer["question"], "overview": answer["overview"],
                              "availability": answer["availability"], "report": str((args.out / "report.html").resolve())}, indent=2))
            return 0
        if args.command == "civic":
            from .reviews import read_run
            from .graph import save_run
            from .civic import CivicClient
            snapshot, events, graph = read_run(args.run)
            if graph.get("civic"):
                raise ValueError("This run already has a CIViC source. Start from a Pharos-only run; refresh reconciliation is not implemented.")
            if snapshot["data_kind"] == "synthetic_demo" and not args.snapshot:
                raise ValueError("Live CIViC cannot be mixed with a synthetic Pharos source.")
            civic = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else CivicClient().retrieve(args.max_items)
            result = save_run(snapshot,args.out,run_mode="civic_enrichment",review_events=events,civic_snapshot=civic)
            print(json.dumps({k:result["civic"][k] for k in ['retrieved_items','normalized_items','coverage','mapping']},indent=2))
            return 0
        if args.command == "therapy-question":
            from .reviews import read_run
            from .civic_questions import answer_civic_question
            from .questions import save_answer
            _, _, graph = read_run(args.run)
            answer=answer_civic_question(graph,profile=args.profile,therapy=args.therapy,view=args.view,
                                         max_results=args.max_results,max_paths=args.max_paths,source_run=args.run.name)
            save_answer(answer,args.out)
            print(json.dumps({"question":answer["question"],"overview":answer["overview"],"availability":answer["availability"],
                              "discordant_groups":len(answer["discordant_annotations"]),"report":str((args.out/'report.html').resolve())},indent=2))
            return 0
        if args.command == "queries":
            args.out.mkdir(parents=True, exist_ok=True)
            for name, query in [("search_diseases", SEARCH), ("disease_info", DISEASE),
                                ("disease_targets", TARGETS), ("database_version", VERSION), ("source_licenses", LICENSES)]:
                (args.out / (name + ".graphql")).write_text(query + "\n", encoding="utf-8")
            from .retrieval import metadata_query, page_query, DEFAULT_LIMITS
            query, _ = metadata_query(["P01116"])
            (args.out / "scoped_metadata.graphql").write_text(query + "\n", encoding="utf-8")
            for family in DEFAULT_LIMITS:
                query, _ = page_query(family, [("P01116", 0, 25)], "colon rectum")
                (args.out / ("scoped_" + family + ".graphql")).write_text(query + "\n", encoding="utf-8")
            from .civic import RESOLVE, EVIDENCE
            (args.out / 'civic_scope.graphql').write_text(RESOLVE+'\n',encoding='utf-8')
            (args.out / 'civic_evidence.graphql').write_text(EVIDENCE+'\n',encoding='utf-8')
            print(args.out.resolve())
            return 0
        if args.command == "audit":
            from .benchmark import save_audit
            audit = save_audit(json.loads(args.snapshot.read_text(encoding="utf-8")), args.out)
            print(json.dumps({key: audit[key] for key in
                              ['status', 'data_kind', 'disease', 'counts', 'required_actions']}, indent=2))
            return 0
        if args.command == "review":
            from .reviews import review_run
            graph = review_run(args.run, args.out, args.assertion, args.state, args.reviewer, args.reason)
            print(json.dumps({"assertions": graph["assertion_summary"], "out": str(args.out.resolve())}, indent=2))
            return 0
        if args.command in {"doctor", "search", "build"}:
            client = PharosClient(args.endpoint, cache_dir=args.cache_dir, timeout=args.timeout, refresh=args.refresh)
            if args.command == "doctor":
                version = client.execute(VERSION, cache=False)
                check = client.check_schema()
                print(json.dumps({"endpoint": args.endpoint, "database_version": version.get("dbVersion"), **check}, indent=2))
                return 0
            if args.command == "search":
                result = client.search(args.term, args.top, args.skip)
                print(f"Showing {len(result['diseases'])} of {result.get('count')} matches")
                for d in result["diseases"]:
                    print(f"{d.get('mondoID') or '(no MONDO ID)'}\t{d['name']}")
                return 0
            snapshot = client.build_snapshot(args.disease, args.max_targets, args.page_size,
                                             args.pathways, not args.skip_schema_check, profile=args.profile,
                                             context_limits={family: getattr(args, family + "_limit") for family in DEFAULT_LIMITS},
                                             tissue_term=args.tissue_term,
                                             progress=lambda message: print(message, file=sys.stderr, flush=True))
        elif args.command == "demo":
            from .demo import demo_snapshot
            snapshot = demo_snapshot()
        else:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        from .graph import save_run
        events = (json.loads(args.reviews.read_text(encoding="utf-8"))
                  if args.command == "replay" and args.reviews else None)
        civic = (json.loads(args.civic_snapshot.read_text(encoding="utf-8"))
                 if args.command == "replay" and args.civic_snapshot else None)
        graph = save_run(snapshot, args.out, run_mode="replay" if args.command == "replay" else "build", review_events=events,civic_snapshot=civic)
        print(json.dumps({"data_kind": graph["data_kind"], "summary": graph["summary"],
                          "report": str((args.out / "report.html").resolve())}, indent=2))
        if graph["data_kind"] == "synthetic_demo":
            print("SYNTHETIC DEMO ONLY. Not retrieved Pharos data or scientific evidence.")
        return 0
    except (PharosError, ValueError, OSError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
