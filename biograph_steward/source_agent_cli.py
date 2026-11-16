"""Operator CLI for the same bounded source-agent workflow used by the app."""
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4


def add_commands(sub):
    command = sub.add_parser('source-agent-catalogue', help='Inspect the actual current-source agent tools without inference.')
    command.add_argument('--run', type=Path, required=True)
    command = sub.add_parser('source-agent-run', help='Run the configured bounded agent on saved evidence and publish its source-linked job.')
    command.add_argument('--run', type=Path, required=True)
    command.add_argument('--question', required=True)
    command.add_argument('--constraints', type=Path, help='Optional JSON object of explicit source/view/identity limits.')
    command.add_argument('--view', choices=('candidates', 'accepted'))
    command.add_argument('--tool', choices=('native_physical', 'native_location', 'archived_pathway'))
    command.add_argument('--protein', help='Optional exact primary protein ID required by the request.')
    command.add_argument('--max-results', type=int)
    command.add_argument('--max-paths', type=int)
    command.add_argument('--go-limit', type=int)
    command.add_argument('--trace-dir', type=Path, help='New directory for immediate per-call events; never a source workspace.')
    command = sub.add_parser('source-agent-verify', help='Verify a saved agent job and replay its source tools without a model.')
    command.add_argument('--job', type=Path, required=True)
    command.add_argument('--runs-dir', type=Path)


def _ordinary_source(folder):
    folder = Path(folder)
    if not folder.is_dir() or folder.is_symlink() or any(p.is_symlink() for p in folder.parents):
        raise ValueError('Choose an ordinary saved source workspace directory.')
    from .webapp import verify_saved_refresh
    from .saved_run_cache import read_run
    verify_saved_refresh(folder)
    return folder.resolve(), read_run(folder)[2]


def _constraints(args):
    constraints = {}
    if args.constraints is not None:
        path = args.constraints
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 20_000:
            raise ValueError('Constraints must be an ordinary bounded JSON file.')
        constraints = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(constraints, dict):
            raise ValueError('Constraints must be a JSON object.')
    for flag, key in [('view', 'view'), ('tool', 'tool'), ('protein', 'protein_id'),
                      ('max_results', 'max_results'), ('max_paths', 'max_paths'), ('go_limit', 'go_limit')]:
        value = getattr(args, flag)
        if value is not None:
            if key in constraints and (type(constraints[key]) is not type(value) or constraints[key] != value):
                raise ValueError('Command-line constraints conflict with the JSON object: ' + key)
            constraints[key] = value
    return constraints


def run_command(args):
    from .source_agent_jobs import read_source_agent_job, save_source_agent_job
    if args.command == 'source-agent-verify':
        root = args.runs_dir or args.job.resolve().parent
        job = read_source_agent_job(args.job, root)
        return {'status': 'verified', 'job_id': job['job_id'], 'source_run': job['source_run'],
                'recorded_status': job['status'], 'recorded_model_calls': job['model_calls'],
                'verification_model_calls': 0, 'graph_or_review_changes': 0}, 0

    source, graph = _ordinary_source(args.run)
    from .source_agent import source_catalogue, run_source_agent
    if args.command == 'source-agent-catalogue':
        return source_catalogue(graph, source.name), 0

    constraints = _constraints(args)
    # An event directory is separate from both the immutable final job and the
    # source. Events survive an interrupted model request without looking like a
    # completed job in the app catalogue.
    trace_dir = args.trace_dir or source.parent / ('.source_agent_progress_' +
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8])
    trace_dir = Path(trace_dir)
    if trace_dir.exists() or trace_dir.is_symlink():
        raise ValueError('Choose a new trace directory; prior events are never overwritten.')
    if source == trace_dir.resolve() or source in trace_dir.resolve().parents:
        raise ValueError('Agent progress must be stored outside its source workspace.')
    trace_dir.mkdir(parents=True)
    count = 0

    def record(event):
        nonlocal count
        count += 1
        destination = trace_dir / ('event_%04d.json' % count)
        with destination.open('x', encoding='utf-8') as stream:
            json.dump(event, stream, indent=2, ensure_ascii=True, allow_nan=False)
            stream.write('\n')

    result = run_source_agent(args.question, graph, source_run=source.name,
        source_folder=source, constraints=constraints, event_callback=record)
    job = save_source_agent_job(result, source.parent)
    focused = result.get('focus_graph') or {}
    summary = {'status': result['status'], 'job_id': job['job_id'], 'source_run': source.name,
        'job': str(source.parent / job['job_id']), 'progress': str(trace_dir.resolve()),
        'provider_kind': job['provider_kind'], 'actual_model_run': job['actual_model_run'],
        'model_calls': result['trace']['model_calls'],
        'tool_calls': len(result['trace']['tool_calls']),
        'focused_nodes': len(focused.get('nodes', [])), 'focused_edges': len(focused.get('edges', [])),
        'review_proposals': len(result['proposals']), 'proposals_applied': False,
        'fresh_source_fetches': result['source_fetches'], 'graph_or_review_changes': 0}
    if result.get('error'):
        summary['error'] = result['error']
    good = result['status'] in {'completed', 'completed_empty', 'abstained', 'scope_rejected'}
    return summary, 0 if good else 1
