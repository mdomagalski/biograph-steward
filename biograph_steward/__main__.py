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
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("review", help="Record a human assertion decision in a new immutable run.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--assertion", required=True)
    p.add_argument("--state", choices=["candidate", "accepted", "provisional", "quarantined", "rejected", "obsolete"], required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("queries", help="Export readable GraphQL requests used by this starter.")
    p.add_argument("--out", type=Path, default=Path("queries"))
    p = sub.add_parser("audit", help="Prepare benchmark readiness and pair-level review files from a snapshot.")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command is None:
            from .webapp import serve
            serve()
            return 0
        if args.command == "serve":
            from .webapp import serve
            serve(args.port, args.runs_dir, args.endpoint, args.cache_dir, not args.no_browser, args.timeout)
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
        graph = save_run(snapshot, args.out, run_mode="replay" if args.command == "replay" else "build", review_events=events)
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
