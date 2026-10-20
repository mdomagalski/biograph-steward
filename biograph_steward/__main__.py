from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from .runtime import runs_directory, cache_directory
from .client import PharosClient, PharosError, ENDPOINT, VERSION, SEARCH, DISEASE, TARGETS, LICENSES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BioGraph Steward: inspect a small Pharos disease graph.")
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
    p = sub.add_parser("demo", help="Build the explicitly SYNTHETIC offline demo.")
    p.add_argument("--out", type=Path, default=runs_directory()/"demo")
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
    p.add_argument("--planner",choices=['none','live','codex','nim','replay'],default='none')
    p.add_argument("--replay",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p = sub.add_parser("evaluation-score", help="Score reviewer worksheets into a new result directory.")
    p.add_argument("--result",type=Path,required=True)
    p.add_argument("--case-reviews",type=Path)
    p.add_argument("--answer-reviews",type=Path)
    p.add_argument("--evidence-reviews",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p = sub.add_parser('planning-prepare', help='Freeze fresh scope-review cases against the unchanged planner; no model calls.')
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--enriched', type=Path, required=True)
    p.add_argument('--cases', type=Path, default=Path(__file__).with_name('planning_challenge_cases.json'))
    p.add_argument('--prior-suite', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('planning-regression-prepare', help='Freeze a changed planner against identical control cases, sources and scope review.')
    p.add_argument('--control-result', type=Path, required=True)
    p.add_argument('--source-suite', type=Path, required=True)
    p.add_argument('--scope-reviews', type=Path, required=True)
    p.add_argument('--protocol', choices=['scoped_targets_v4'], default='scoped_targets_v4')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('planning-compare', help='Run an offline baseline or scope-reviewed live planning comparison.')
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--scope-reviews', type=Path, help='Completed copy of the packet worksheet; all scopes must be approved for inference.')
    p.add_argument('--planner', choices=['none', 'live'], default='none')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser("plan-question", help="Plan and execute one research question through the bounded model planner.")
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--question",required=True)
    p.add_argument("--out",type=Path,required=True)
    p = sub.add_parser('crc-pilot-prepare', help='Freeze deterministic CRC queries and a disclosed source-evidence panel.')
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--enriched', type=Path, required=True)
    p.add_argument('--items', type=int, default=20)
    p.add_argument('--cases', type=Path, help='Optional deterministic query specifications; not scientific gold labels.')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('crc-pilot-literature', help='Retrieve bounded PubMed and linked PMC text for the frozen panel.')
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('cptac-inspect', help='Freeze a processed CPTAC colon matrix and report exact cohort mappings.')
    p.add_argument('--pharos-run', type=Path, required=True)
    p.add_argument('--matrix', type=Path, help='Optional existing source file; otherwise download the declared matrix.')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('crc-pilot-run', help='Report source value with optional advisory passage verification; no gold labels or graph writes.')
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--literature', type=Path, required=True)
    p.add_argument('--cptac', type=Path)
    p.add_argument('--verifier', choices=['none', 'codex', 'configured', 'api', 'nim'], default='none')
    p.add_argument('--model')
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('identifier-registry', help='Freeze the official HGNC and reviewed human UniProt identifier tables.')
    p.add_argument('--downloads', type=Path, help='Optional existing downloads with hash-checked retrieval.json receipts.')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('cptac-map', help='Account for every measured gene and preserve ambiguous gene/product mappings.')
    p.add_argument('--cptac', type=Path, required=True)
    p.add_argument('--pharos-run', type=Path, required=True)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('source-adjudicate', help='Record an AI-authored source-context overlay without changing original verdicts or graph states.')
    p.add_argument('--pilot', type=Path, required=True)
    p.add_argument('--literature', type=Path, required=True)
    p.add_argument('--decision', type=Path, required=True)
    p.add_argument('--mapping', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('depmap-freeze', help='Verify and freeze the explicitly pinned public 24Q4 v1 archive downloads.')
    p.add_argument('--downloads', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('depmap-audit', help='Audit colorectal CRISPR coverage and source leakage without biological rankings or model calls.')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--mapping', type=Path, required=True)
    p.add_argument('--pharos-run', type=Path, required=True)
    p.add_argument('--enriched-run', type=Path)
    p.add_argument('--probe', type=Path, help='Optional verified historical Pharos response envelope.')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser("audit", help="Prepare benchmark readiness and pair-level review files from a snapshot.")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser('matched-panel-prepare', help='Freeze an outcome-blind hash-selected measured-gene panel before Pharos retrieval.')
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--mapping', type=Path, required=True)
    p.add_argument('--size', type=int, default=256)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('matched-panel-retrieve', help='Retrieve explicit-ID Pharos context for a frozen panel, without disease filtering or outcome values.')
    p.add_argument('--panel', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('comparison-freeze', help='Review source channels and freeze features/partitions/scoring rules without opening dependency values.')
    p.add_argument('--panel', type=Path, required=True)
    p.add_argument('--retrieval', type=Path, required=True)
    p.add_argument('--mapping', type=Path, required=True)
    p.add_argument('--pharos-code', type=Path, required=True)
    p.add_argument('--repository-tree', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('growth-compare', help='Execute the exact frozen growth pilot, sealing predictions before one test-outcome access.')
    p.add_argument('--protocol', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('growth-diagnose', help='Ablate source blocks using already exposed saved pilot outcomes; no fresh test.')
    p.add_argument('--comparison', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('fresh-cohort', help='Bind the original development panel and untouched gene reserve into one Pharos scope.')
    p.add_argument('--panel', type=Path, required=True)
    p.add_argument('--reservation', type=Path, required=True)
    p.add_argument('--diagnostics', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('fresh-retrieve', help='Retrieve and verify consistent Pharos context over the complete development/reserve union.')
    p.add_argument('--cohort', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('fresh-freeze', help='Freeze the pathway primary hypothesis, secondary arms and controls before reserved outcome access.')
    p.add_argument('--cohort', type=Path, required=True)
    p.add_argument('--retrieval', type=Path, required=True)
    p.add_argument('--mapping', type=Path, required=True)
    p.add_argument('--reference-protocol', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('fresh-compare', help='Execute one frozen reserved-gene comparison with source-bound exposure protection.')
    p.add_argument('--protocol', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('growth-reserve', help='Reserve untouched gene/product components after a completed pilot without opening experimental scores.')
    p.add_argument('--panel', type=Path, required=True)
    p.add_argument('--comparison', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('quality-prepare', help='Freeze a source-consistency panel and explicit synthetic edits from saved CRC papers.')
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--literature', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('quality-run', help='Compare unfiltered, deterministic and advisory-verifier views without changing graph states.')
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--verifier', choices=['none', 'configured', 'api', 'nim', 'codex'], default='none')
    p.add_argument('--model')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('quality-verify', help='Replay saved evidence-quality metrics, citations and findings without inference.')
    p.add_argument('--result', type=Path, required=True)
    p = sub.add_parser('context-prepare', help='Freeze fresh publication claims and a paired context-verifier protocol.')
    p.add_argument('--literature', type=Path, required=True)
    p.add_argument('--previous-literature', type=Path, action='append', required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('context-run', help='Compare legacy and context verification on identical frozen source windows.')
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--verifier', choices=['none', 'configured', 'api', 'nim', 'codex'], default='none')
    p.add_argument('--model')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('context-verify', help='Replay the context comparison without inference.')
    p.add_argument('--result', type=Path, required=True)
    p = sub.add_parser('context-assess', help='Check one provided claim/source task with exact context spans; advisory only.')
    p.add_argument('--task', type=Path, required=True)
    p.add_argument('--verifier', choices=['configured', 'api', 'nim', 'codex'], default='configured')
    p.add_argument('--model')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('verification-run', help='Evaluate a bounded source verifier against prepared SciFact expert annotations.')
    p.add_argument('--benchmark', type=Path, required=True)
    p.add_argument('--verifier', choices=['baselines', 'codex', 'nim', 'api', 'configured'], default='baselines')
    p.add_argument('--model', help='Explicit model ID; otherwise use role/shared model configuration.')
    p.add_argument('--limit', type=int, help='Fixed hash-selected pair limit for a smoke pilot; omit for the full input set.')
    p.add_argument('--workers', type=int, default=1, help='Concurrent independent verification turns, 1–4.')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('verification-score', help='Recompute metrics from a completed immutable verification result, without model calls.')
    p.add_argument('--result', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
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
        if args.command == 'context-prepare':
            from .context_evaluation import prepare_context
            print(json.dumps(prepare_context(args.literature, args.previous_literature, args.out), indent=2))
            return 0
        if args.command == 'context-run':
            from .context_evaluation import run_context
            r = run_context(args.packet, args.out, mode=args.verifier, model=args.model,
                            progress=lambda s: print(s, file=sys.stderr, flush=True))
            print(json.dumps(r, indent=2))
            return 0
        if args.command == 'context-verify':
            from .context_evaluation import verify_context_result
            r = verify_context_result(args.result)
            print(json.dumps({'result_sha256': r['result_sha256'], 'status': 'verified',
                              'graph_mutations': 0, 'model_requests_replayed': 0}, indent=2))
            return 0
        if args.command == 'context-assess':
            from .context_verification import verify_context
            from .verification import configured_verifier, validate_task
            from .crc_pilot import new_output
            from .client import write_json
            task = json.loads(args.task.read_text()); validate_task(task)
            verifier = configured_verifier(None if args.verifier == 'configured' else args.verifier, model=args.model)
            out = new_output(args.out, args.task)
            trace = verify_context(task, verifier)
            write_json(out / 'task.json', task); write_json(out / 'trace.json', trace)
            print(json.dumps({'status': trace['status'], 'gate': trace['gate'], 'graph_mutations': 0}, indent=2))
            return 0
        if args.command == 'quality-prepare':
            from .evidence_quality import prepare_quality
            print(json.dumps(prepare_quality(args.packet, args.literature, args.out), indent=2))
            return 0
        if args.command == 'quality-run':
            from .evidence_quality import run_quality
            r = run_quality(args.packet, args.out, mode=args.verifier, model=args.model,
                            progress=lambda s: print(s, file=sys.stderr, flush=True))
            print(json.dumps(r, indent=2))
            return 0
        if args.command == 'quality-verify':
            from .evidence_quality import verify_quality_result
            r = verify_quality_result(args.result)
            print(json.dumps({'result_sha256': r['result_sha256'], 'status': 'verified',
                              'graph_mutations': r['graph_mutations'], 'model_requests_replayed': 0}, indent=2))
            return 0
        if args.command == 'fresh-cohort':
            from .fresh_retrieval import prepare_union
            r = prepare_union(args.panel, args.reservation, args.diagnostics, args.out)
            print(json.dumps({k: r[k] for k in ['panel_sha256', 'selected_genes', 'requested_proteins', 'fresh_dependency_values_loaded']}, indent=2))
            return 0
        if args.command == 'fresh-retrieve':
            from .fresh_retrieval import retrieve_union
            r = retrieve_union(args.cohort, args.out, progress=lambda s: print(s, file=sys.stderr, flush=True))
            print(json.dumps({k: r[k] for k in ['result_sha256', 'selected_genes', 'requested_proteins', 'version_consistent', 'retrieval']}, indent=2))
            return 0
        if args.command == 'fresh-freeze':
            from .fresh_growth import freeze_fresh
            r = freeze_fresh(args.cohort, args.retrieval, args.mapping, args.reference_protocol, args.out)
            print(json.dumps({k: r[k] for k in ['result_sha256', 'partition_counts', 'primary_candidate', 'fresh_dependency_values_loaded']}, indent=2))
            return 0
        if args.command == 'fresh-compare':
            from .fresh_growth import run_fresh
            r = run_fresh(args.protocol, args.source, args.out, progress=lambda s: print(s, file=sys.stderr, flush=True))
            print(json.dumps({k: r[k] for k in ['result_sha256', 'primary_spearman_delta', 'paired_interval', 'decision', 'arms']}, indent=2))
            return 0
        if args.command == 'growth-diagnose':
            from .growth_diagnostics import run_diagnostics
            r = run_diagnostics(args.comparison, args.out,
                                progress=lambda message: print(message, file=sys.stderr, flush=True))
            print(json.dumps({k: r[k] for k in ['result_sha256', 'arms', 'ranking_error', 'development_proposal', 'fresh_test_executed']}, indent=2))
            return 0
        if args.command == 'growth-reserve':
            from .growth_diagnostics import reserve_fresh
            r = reserve_fresh(args.panel, args.comparison, args.out)
            print(json.dumps({k: r[k] for k in ['result_sha256', 'reserved_genes', 'gene_overlap_with_previous', 'protein_overlap_with_previous', 'fresh_dependency_values_loaded']}, indent=2))
            return 0
        if args.command == 'growth-compare':
            from .growth_comparison import run_comparison
            r = run_comparison(args.protocol, args.source, args.out,
                               progress=lambda message: print(message, file=sys.stderr, flush=True))
            print(json.dumps({k: r[k] for k in ['result_sha256', 'arms', 'primary_spearman_delta', 'paired_interval', 'decision']}, indent=2))
            return 0
        if args.command == 'comparison-freeze':
            from .comparison_protocol import freeze_protocol
            r = freeze_protocol(args.panel, args.retrieval, args.mapping, args.out,
                                pharos_code=args.pharos_code, repository_tree=args.repository_tree)
            print(json.dumps({k: r[k] for k in ['result_sha256', 'genes', 'models', 'source_review', 'partition_counts', 'protocol_frozen', 'dependency_values_loaded']}, indent=2))
            return 0
        if args.command == 'matched-panel-prepare':
            from .matched_panel import prepare_panel
            r = prepare_panel(args.audit, args.mapping, args.out, size=args.size)
            print(json.dumps({k: r[k] for k in ['panel_sha256', 'eligible_genes', 'selected_genes', 'unique_protein_candidates']}, indent=2))
            return 0
        if args.command == 'matched-panel-retrieve':
            from .matched_panel import retrieve_panel
            r = retrieve_panel(args.panel, args.out, progress=lambda message: print(message, file=sys.stderr, flush=True))
            print(json.dumps({k: r[k] for k in ['result_sha256', 'selected_genes', 'target_resolution_counts', 'provisional_feature_counts', 'retrieval', 'ready_for_prediction_comparison']}, indent=2))
            return 0
        if args.command == 'depmap-freeze':
            from .depmap_audit import freeze_depmap
            r = freeze_depmap(args.downloads, args.out)
            print(json.dumps({k: r[k] for k in ['source_sha256', 'release', 'doi']}, indent=2))
            return 0
        if args.command == 'depmap-audit':
            from .depmap_audit import run_audit
            r = run_audit(args.source, args.mapping, args.pharos_run, args.out,
                          enriched_run=args.enriched_run, probe_file=args.probe)
            print(json.dumps({k: r[k] for k in ['result_sha256', 'coverage_feasible', 'ready_for_prediction_comparison', 'coverage', 'leakage']}, indent=2))
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
        if args.command == 'source-adjudicate':
            from .source_adjudication import adjudicate_source
            r = adjudicate_source(args.pilot, args.literature, args.decision, args.out, mapping=args.mapping)
            print(json.dumps({k: r[k] for k in ['result_sha256', 'item_id', 'decision', 'human_scientific_labels', 'graph_assertions_changed']}, indent=2))
            return 0
        if args.command == 'crc-pilot-prepare':
            from .crc_pilot import prepare_pilot
            r = prepare_pilot(args.baseline, args.enriched, args.out, size=args.items,
                              cases=json.loads(args.cases.read_text()) if args.cases else None)
            print(json.dumps({'packet_sha256': r['packet_sha256'], 'selection': r['selection'], 'model_calls': 0}, indent=2))
            return 0
        if args.command == 'crc-pilot-literature':
            from .crc_pilot import retrieve_pilot_literature
            r = retrieve_pilot_literature(args.packet, args.out)
            print(json.dumps({'manifest_sha256': r['manifest_sha256'], 'publications': len(r['requested_pmids']), 'model_calls': 0}, indent=2))
            return 0
        if args.command == 'cptac-inspect':
            from .cptac import prepare_cptac
            r = prepare_cptac(args.pharos_run, args.out, matrix=args.matrix)
            print(json.dumps({'sidecar_sha256': r['sidecar_sha256'], 'genes': r['analysis']['gene_rows'],
                              'samples': r['analysis']['sample_columns'], 'matched_pharos_genes': r['analysis']['cohort_gene_rows_matching_pharos']}, indent=2))
            return 0
        if args.command == 'crc-pilot-run':
            from .crc_pilot import run_pilot
            r = run_pilot(args.packet, args.literature, args.out, cptac=args.cptac, mode=args.verifier,
                          model=args.model, workers=args.workers,
                          progress=lambda msg: print(msg, file=sys.stderr, flush=True))
            print(json.dumps({k: r[k] for k in ['panel_items', 'unique_publications', 'views', 'model_requests',
                                               'scientific_accuracy', 'scientific_improvement_established']}, indent=2))
            return 0
        if args.command == 'planning-regression-prepare':
            from .planning_comparison import prepare_regression
            packet = prepare_regression(args.control_result, args.source_suite, args.out,
                                        scope_reviews=args.scope_reviews, protocol=args.protocol)
            print(json.dumps({'packet_sha256': packet['packet_sha256'], 'experiment_kind': packet['experiment_kind'],
                              'control_evaluation_sha256': packet['control_evaluation_sha256'],
                              'model_called': False}, indent=2))
            return 0
        if args.command == 'planning-prepare':
            from .planning_comparison import prepare_comparison
            packet = prepare_comparison(args.baseline, args.enriched, args.out,
                                        cases=json.loads(args.cases.read_text(encoding='utf-8')), prior_suite=args.prior_suite)
            print(json.dumps({'packet_sha256': packet['packet_sha256'], 'cases': packet['overlap_audit']['cases'],
                              'reference_status': packet['reference_status'], 'model_called': False,
                              'review': str((args.out / 'review.html').resolve())}, indent=2))
            return 0
        if args.command == 'planning-compare':
            from .planning_comparison import run_comparison
            summary = run_comparison(args.packet, args.out, live=args.planner == 'live', scope_reviews=args.scope_reviews,
                                     progress=lambda message: print(message, file=sys.stderr, flush=True))
            print(json.dumps({k: summary[k] for k in ['planner_kind', 'cases', 'draft_plan_comparisons',
                                                    'draft_plan_matches', 'reported_model_calls',
                                                    'scientific_improvement_established']}, indent=2))
            return 0
        if args.command == 'deployment-smoke':
            from .deployment_smoke import run_smoke
            report = run_smoke(args.base_url, args.out, with_planner=args.with_planner, receipt=args.receipt,
                               origin=args.browser_origin, timeout=args.timeout)
            print(json.dumps({'status': report['status'], 'checks': report['checks'],
                              'reported_model_calls': report['reported_model_calls'],
                              'report': str((args.out / 'report.json').resolve())}, indent=2))
            return 0 if report['status'] == 'passed' else 1
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
            if args.planner in {'live','codex','nim'}:
                try:
                    if args.planner=='codex':
                        from .codex_planner import CodexPlanner
                        planner=CodexPlanner()
                    elif args.planner=='nim':planner=configured_planner(provider='nim')
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
