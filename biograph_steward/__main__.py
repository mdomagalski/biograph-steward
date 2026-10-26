from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from .runtime import runs_directory, cache_directory
from .client import PharosClient, PharosError, ENDPOINT, VERSION, SEARCH, DISEASE, TARGETS, LICENSES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BioGraph Steward: inspect and trace bounded biomedical evidence.")
    sub = parser.add_subparsers(dest="command")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--endpoint", default=ENDPOINT)
    common.add_argument("--cache-dir", type=Path, default=cache_directory())
    common.add_argument("--timeout", type=float, default=30)
    common.add_argument("--refresh", action="store_true")
    p = sub.add_parser("serve", parents=[common], help="Start the local browser interface (default).")
    p.add_argument("--port", type=int, default=os.environ.get("BIOGRAPH_PORT", "8765"))
    p.add_argument("--host", default=os.environ.get("BIOGRAPH_HOST", "127.0.0.1"))
    p.add_argument("--allowed-origin", action="append", default=None, help="Exact HTTPS origin allowed for a protected reverse proxy; repeat for multiple origins.")
    p.add_argument("--runs-dir", type=Path, default=runs_directory())
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
    p = sub.add_parser("construct", parents=[common],
                       help="Construct and publish a bounded exact-accession Pharos graph and cited inspection answer.")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--accessions", nargs="+", help="1–25 exact UniProt accessions; no symbol or fuzzy resolution.")
    source.add_argument("--snapshot", type=Path, help="Publish a saved construction snapshot offline with its original request.")
    source.add_argument("--demo", action="store_true", help="Use the explicitly synthetic construction fixture; no network.")
    p.add_argument("--focus-uniprot", help="Exact accession within --accessions for the cited neighborhood answer.")
    p.add_argument("--profile", choices=["ppi", "context"], default="ppi")
    p.add_argument("--relations", choices=["interactions", "shared_pathways"], nargs="+", default=["interactions"])
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("construction-verify", help="Verify a saved construction publication and its source/answer bindings offline.")
    p.add_argument("--run", type=Path, required=True)
    p = sub.add_parser("assay-attach", help="Attach a saved qualified assay publication to an exact Pharos protein cohort offline.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--publication", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("standards-resources", help="Download hash-pinned official Biolink resources into a new folder.")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("standards-export", help="Publish a bounded KGX projection and actual upstream validation audit; requires optional audit environment.")
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--resources", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("standards-verify", help="Verify export integrity and mapping replay offline; does not rerun upstream validators.")
    p.add_argument("--run", type=Path, required=True)
    p = sub.add_parser("demo", help="Build the explicitly SYNTHETIC offline demo.")
    p.add_argument("--out", type=Path, default=runs_directory()/"demo")
    p = sub.add_parser("replay", help="Rebuild a snapshot with the current transformer without network access.")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--reviews", type=Path, help="Preserve review events from this exact snapshot.")
    p.add_argument("--civic-snapshot", type=Path, help="Replay this verified CIViC sidecar without network access.")
    p.add_argument("--assay-run", type=Path, help="Preserve the validated assay sidecar and complete source publication from this run.")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("review", help="Record a human assertion decision in a new immutable run.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--assertion", required=True)
    p.add_argument("--state", choices=["candidate", "accepted", "provisional", "quarantined", "rejected", "obsolete"], required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("refresh-compare", help="Compare saved evidence snapshots and optionally carry compatible prior reviews into a new run.")
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--carry-reviews", action="store_true", help="Preserve eligible prior decisions with explicit carryover provenance; no new scientific judgment.")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("refresh-verify", help="Replay a saved snapshot comparison and review carryover without network access.")
    p.add_argument("--run", type=Path, required=True)
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
    p = sub.add_parser("plan-question", help="Plan and execute one research question through the bounded model planner.")
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--question",required=True)
    p.add_argument("--out",type=Path,required=True)
    p = sub.add_parser('cptac-inspect', help='Freeze a processed CPTAC colon matrix and report exact cohort mappings.')
    p.add_argument('--pharos-run', type=Path, required=True)
    p.add_argument('--matrix', type=Path, help='Optional existing source file; otherwise download the declared matrix.')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('identifier-registry', help='Freeze the official HGNC and reviewed human UniProt identifier tables.')
    p.add_argument('--downloads', type=Path, help='Optional existing downloads with hash-checked retrieval.json receipts.')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('cptac-map', help='Account for every measured gene and preserve ambiguous gene/product mappings.')
    p.add_argument('--cptac', type=Path, required=True)
    p.add_argument('--pharos-run', type=Path, required=True)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser("audit", help="Prepare benchmark readiness and pair-level review files from a snapshot.")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("gold-export", help="Export a verified source-bound graph packet; no official gold scoring.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("gold-verify", help="Verify saved gold-interface packet files without fetching or inference.")
    p.add_argument("--packet", type=Path, required=True)
    p = sub.add_parser("gold-decisions", help="Validate explicit edge dispositions separately from review states.")
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--decisions", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("gold-reference-template", help="Create a baseline-bound mapping template for a future reference.")
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("gold-align", help="Align a declared reference exactly; preserve raw labels without scoring.")
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--mapping", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    sub.add_parser('runtime-check', help='Inspect deployment/model configuration without inference or source requests.')
    p = sub.add_parser('deployment-smoke', help='Check a running app with synthetic data; optionally request one model plan.')
    p.add_argument('--base-url', required=True, help='Root HTTPS deployment URL or loopback HTTP URL.')
    p.add_argument('--browser-origin', help='Exact browser origin; defaults to the deployment URL.')
    p.add_argument('--with-planner', action='store_true', help='Explicitly request one live model plan against the synthetic run.')
    p.add_argument('--receipt', type=Path, help='Reopen the same saved data from an earlier successful report; no writes/model calls.')
    p.add_argument('--timeout', type=int, default=120)
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'assay-attach':
            from .assay_attachment import attach_assay
            graph = attach_assay(args.run, args.publication, args.out)
            print(json.dumps({'output': str(args.out.resolve()), 'assay_evidence': graph['assay_evidence']}, indent=2))
            return 0
        if args.command == "standards-resources":
            from .standards_validation import prepare_resources
            result = prepare_resources(args.out)
            print(json.dumps({"biolink_model_version": result["biolink_model_version"],
                              "resources": str(args.out.resolve())}, indent=2))
            return 0
        if args.command in {"standards-export", "standards-verify"}:
            from .standard_export import export_standard, verify_standard
            result = (export_standard(args.packet, args.out, args.resources)
                      if args.command == "standards-export" else verify_standard(args.run))
            validation = result["validation"]
            print(json.dumps({"operation": args.command, "counts": result["counts"],
                "recorded_validation_status": {key: validation[key]["status"] for key in
                    ("kgx", "published_json_schema", "kgx_jsonl_roundtrip", "declared_domain_range_and_predicate_audit")},
                "full_standard_conformance_claimed": False, "biological_validation_performed": False,
                "report": str(((args.out if args.command == "standards-export" else args.run) / "report.json").resolve())}, indent=2))
            return 0
        if args.command == "construct":
            from .construction import (demo_construction_snapshot, publish_construction,
                                       run_construction)
            if args.accessions is not None:
                request = {"accessions": args.accessions, "focus_uniprot": args.focus_uniprot,
                           "profile": args.profile, "relations": args.relations}
                client = PharosClient(args.endpoint, cache_dir=args.cache_dir,
                                      timeout=args.timeout, refresh=args.refresh)
                result = run_construction(client, request, args.out)
            else:
                if args.focus_uniprot is not None or args.profile != "ppi" or args.relations != ["interactions"] or args.refresh:
                    raise ValueError("Offline snapshot and demo publication preserve their saved/fixed request; live scope and refresh options do not apply.")
                if args.demo:
                    snapshot = demo_construction_snapshot()
                else:
                    from .gold_packet import _read
                    source_directory = args.snapshot.resolve().parent
                    destination = args.out.resolve()
                    if ((source_directory / 'run_manifest.json').exists()
                            and (destination == source_directory or source_directory in destination.parents)):
                        raise ValueError("Republish outside the saved source run to preserve its immutable files.")
                    snapshot = _read(args.snapshot)
                result = publish_construction(snapshot, args.out)
            graph, question = result["graph"], result["question"]
            summary = {"data_kind": graph["data_kind"], "summary": graph["summary"],
                       "answer_status": result["construction"]["answer_status"],
                       "answer": question["overview"] if question is not None else None,
                       "report": str((args.out / "report.html").resolve()),
                       "publication": str(args.out.resolve())}
            if question is not None:
                summary["answer_report"] = str((args.out / "answer/report.html").resolve())
            print(json.dumps(summary, indent=2))
            return 0
        if args.command == "construction-verify":
            from .construction import verify_construction_run
            receipt = verify_construction_run(args.run)
            print(json.dumps({"status": "construction_publication_verified",
                              "answer_status": receipt["answer_status"],
                              "run": str(args.run.resolve())}, indent=2))
            return 0
        if args.command in {"gold-export", "gold-verify", "gold-decisions", "gold-reference-template", "gold-align"}:
            if args.command == "gold-export":
                from .gold_packet import export_packet
                result = export_packet(args.run, args.out)
                summary = {key: result[key] for key in ("packet_id", "data_kind", "counts")}
            elif args.command == "gold-verify":
                from .gold_packet import load_packet
                result, _ = load_packet(args.packet)
                summary = {"status": "packet_integrity_verified", "packet_id": result["packet_id"],
                           "official_scoring_performed": False}
            elif args.command == "gold-decisions":
                from .gold_packet import save_decisions
                result = save_decisions(args.packet, args.decisions, args.out)
                summary = {"packet_id": result["packet_id"], "counts": result["counts"]}
            elif args.command == "gold-reference-template":
                from .gold_reference import mapping_template
                result = mapping_template(args.packet, args.out)
                summary = {"status": "template_requires_reference_metadata", "baseline": result["baseline"]}
            else:
                from .gold_reference import align_reference
                result = align_reference(args.packet, args.reference, args.mapping, args.out)
                summary = {"status": result["status"], "summary": result["summary"], "metrics": None}
            if args.command != "gold-verify":
                summary["output"] = str(args.out.resolve())
            print(json.dumps(summary, indent=2))
            return 0
        if args.command == 'identifier-registry':
            from .cohort_mapping import collect_registry
            r = collect_registry(args.out, downloads=args.downloads)
            print(json.dumps({k: r[k] for k in ['registry_sha256', 'hgnc_records', 'uniprot_records']}, indent=2))
            return 0
        if args.command == 'cptac-map':
            from .cohort_mapping import map_cohort
            r = map_cohort(args.cptac, args.pharos_run, args.registry, args.out)
            print(json.dumps({'result_sha256': r['result_sha256'], **r['summary']}, indent=2))
            return 0
        if args.command == 'cptac-inspect':
            from .cptac import prepare_cptac
            r = prepare_cptac(args.pharos_run, args.out, matrix=args.matrix)
            print(json.dumps({'sidecar_sha256': r['sidecar_sha256'], 'genes': r['analysis']['gene_rows'],
                              'samples': r['analysis']['sample_columns'], 'matched_pharos_genes': r['analysis']['cohort_gene_rows_matching_pharos']}, indent=2))
            return 0
        if args.command == 'deployment-smoke':
            from .deployment_smoke import run_smoke
            report = run_smoke(args.base_url, args.out, with_planner=args.with_planner, receipt=args.receipt,
                               origin=args.browser_origin, timeout=args.timeout)
            print(json.dumps({'status': report['status'], 'checks': report['checks'],
                              'reported_model_calls': report['reported_model_calls'],
                              'report': str((args.out / 'report.json').resolve())}, indent=2))
            return 0 if report['status'] == 'passed' else 1
        if args.command == 'runtime-check':
            from .portability import runtime_status
            status = runtime_status()
            print(json.dumps(status, indent=2))
            return 0 if status['hosting']['valid'] else 2
        if args.command is None or args.command == 'serve':
            from .webapp import serve
            host = args.host if args.command else os.environ.get('BIOGRAPH_HOST', '127.0.0.1')
            origins = ((args.allowed_origin if args.allowed_origin is not None else os.environ.get('BIOGRAPH_ALLOWED_ORIGINS', ''))
                       if args.command else os.environ.get('BIOGRAPH_ALLOWED_ORIGINS', ''))
            options = {'host': host, 'allowed_origins': origins, 'access_token': os.environ.get('BIOGRAPH_ACCESS_TOKEN')}
            if args.command:
                serve(args.port, args.runs_dir, args.endpoint, args.cache_dir, not args.no_browser, args.timeout, **options)
            else:
                serve(port=int(os.environ.get('BIOGRAPH_PORT', '8765')), **options)
            return 0
        if args.command == 'plan-question':
            from .reviews import read_run
            from .planning import configured_planner,execute_plan
            from .file_utils import new_output
            from .client import write_json
            from .questions import save_answer
            _,_,graph=read_run(args.run)
            if graph.get('scope', {}).get('kind') == 'protein_cohort':
                raise ValueError('The model planner supports disease-scoped saved graphs only. Use the deterministic question command for this protein cohort; no model was called.')
            output=new_output(args.out, args.run)
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
            if graph.get('scope', {}).get('kind') == 'protein_cohort':
                raise ValueError('The CIViC adapter requires its declared disease scope and cannot enrich a disease-free protein cohort. No CIViC request was made.')
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
        if args.command == "refresh-compare":
            from .refresh_workflow import run_refresh
            result = run_refresh(args.before, args.after, args.out, carry_reviews=args.carry_reviews)
            print(json.dumps({"summary": result["comparison"]["summary"],
                              "report": str((args.out / "refresh_report.html").resolve()),
                              "review_carryover_requested": args.carry_reviews}, indent=2))
            return 0
        if args.command == "refresh-verify":
            from .refresh_workflow import verify_refresh
            print(json.dumps(verify_refresh(args.run), indent=2))
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
        assay, assay_source = None, None
        if args.command == 'replay':
            if args.assay_run:
                from .assay_attachment import read_assay
                assay = read_assay(args.assay_run)
                if assay is None:
                    raise ValueError('The supplied assay run has no qualified assay attachment.')
                assay_source = args.assay_run / 'assay_source'
            elif any((args.snapshot.parent / name).exists() or (args.snapshot.parent / name).is_symlink()
                     for name in ('assay_attachment.json', 'assay_source')):
                raise ValueError('Use --assay-run to preserve this snapshot’s attached assay source during replay.')
        graph = save_run(snapshot, args.out, run_mode="replay" if args.command == "replay" else "build", review_events=events,
                         civic_snapshot=civic, assay_attachment=assay, assay_source=assay_source)
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
