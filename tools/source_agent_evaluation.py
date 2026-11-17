"""Frozen, stdlib-only current-source agent development runner.

prepare --plan PLAN --runs-dir RUNS --model-config CONFIG --runtime-attestation
ATTESTATION --output NEW_BINDING performs local source replay only. Then run
--prepared BINDING --prepared-sha256 SHA --runs-dir RUNS --output NEW_EXECUTION.
report --execution EXECUTION --output NEW_REPORT writes a source-free aggregate.
No command retries a model request or overwrites an existing artifact.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward.graph import build_graph
from biograph_steward.model_transport import JSONModelClient
from biograph_steward.questions import graph_basis
from biograph_steward.qualified_workspace import _workspace_fingerprint
from biograph_steward.saved_run_cache import read_run
from biograph_steward import source_agent as agent
from biograph_steward.source_agent_jobs import save_source_agent_job

ROOT = Path(__file__).resolve().parents[1]
PLAN_SHA256 = '10445acc307eb2bfff2d3edaff18ae5a44e6264563d66743499324143d349fb6'
PROTOCOL_SHA256 = '6b4724996b1dbd0d3ed55e967e96b86553077c6aaf444c7336953280454e5a36'
FORMAT = 'biograph-steward.source-agent-frozen-evaluation.v1'
MAX_CALLS, MAX_OUTPUT, MAX_TOTAL = 24, 1200, 28800
NAME = re.compile(r'[A-Za-z0-9_-]{1,80}')


def need(value, message):
    if not value:
        raise ValueError('Source-agent evaluation: ' + message)


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    """Immediate exclusive write; completion manifests are always written last."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def read(path, limit=32_000_000):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit,
         'an ordinary bounded JSON file is required.')
    return json.loads(path.read_text(encoding='utf-8'))


def sealed(value):
    return {**value, 'content_sha256': digest(value)}


def checked_seal(value):
    need(isinstance(value, dict) and value.get('content_sha256') ==
         digest({k: v for k, v in value.items() if k != 'content_sha256'}), 'manifest seal differs.')
    return value


def code_pins():
    paths = sorted((ROOT / 'biograph_steward').rglob('*.py')) + [Path(__file__).resolve()]
    need(all(p.is_file() and not p.is_symlink() for p in paths), 'ordinary implementation files required.')
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def folder_for(runs_dir, source_id):
    root = Path(runs_dir).resolve()
    need(NAME.fullmatch(source_id), 'invalid source workspace identifier.')
    folder = root / source_id
    need(root.is_dir() and folder.is_dir() and not folder.is_symlink()
         and folder.resolve().parent == root, 'source workspace must be an ordinary direct child.')
    return folder


def source_binding(folder, graph):
    # Reuse the established full-byte/inventory helper, omitting its process-
    # local function IDs. Cross-process implementation bytes are pinned above.
    rows, _ = _workspace_fingerprint(folder)
    binding = {'graph_sha256': digest(graph), 'graph_basis_sha256': graph_basis(graph),
        'snapshot_sha256': graph['snapshot_sha256'],
        'review_events_sha256': digest(graph.get('review_events', [])),
        'evidence_extension_sha256': graph.get('evidence_extension_sha256'),
        'qualified_view_sha256': digest(graph.get('qualified_view')),
        'source_inventory_sha256': digest(rows), 'source_inventory_entries': len(rows),
        'source_files': sum(r[1] == 'file' for r in rows)}
    return binding, rows


def load_graph(folder):
    from biograph_steward.webapp import verify_saved_refresh
    verify_saved_refresh(folder)
    value = read_run(folder)
    graph = value[2]
    del value
    return graph


def model_config(value):
    required = {'model', 'provider', 'endpoint', 'api', 'prompt_profile', 'max_output_tokens', 'timeout'}
    need(isinstance(value, dict) and required <= set(value)
         and not set(value) - required - {'model_revision', 'returned_model_aliases'}, 'model configuration fields differ.')
    need(type(value['max_output_tokens']) is int and value['max_output_tokens'] == MAX_OUTPUT,
         'freeze exactly1200 output tokens per call.')
    need(type(value['timeout']) is int and 1 <= value['timeout'] <= 300, 'invalid model timeout.')
    need(value['prompt_profile'] in {'standard', 'nemotron_nano_v1'}, 'unsupported prompt profile.')
    need(isinstance(value.get('model_revision', 'unknown'), str), 'model revision must be literal or unknown.')
    aliases = value.get('returned_model_aliases', [value['model']])
    need(isinstance(aliases, list) and 1 <= len(aliases) <= 3
         and all(isinstance(s, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,200}', s) for s in aliases),
         'freeze explicit returned-model names, never a wildcard.')
    normalized = {**value, 'model_revision': value.get('model_revision', 'unknown'),
                  'returned_model_aliases': aliases}
    client = make_client(normalized)  # Constructor validates URL/API; makes no request.
    del client
    return normalized


def make_client(config):
    client = JSONModelClient(role='planner', provider=config['provider'], model=config['model'],
                             endpoint=config['endpoint'], api=config['api'])
    client.max_output_tokens = config['max_output_tokens']
    client.timeout = config['timeout']
    client.prompt_profile = config['prompt_profile']
    return client


def no_credentials(value):
    forbidden = {'api_key', 'password', 'secret', 'access_token', 'refresh_token', 'authorization',
                 'aws_secret_access_key', 'aws_session_token'}
    if isinstance(value, dict):
        need(not {str(k).lower() for k in value} & forbidden, 'do not freeze credentials.')
        for item in value.values():
            no_credentials(item)
    elif isinstance(value, list):
        for item in value:
            no_credentials(item)


def learner_pins(values):
    result = {}
    suffixes = ('.json', '.jsonl', '.tsv', '.tsv.gz', '.csv', '.csv.gz', '.txt', '.npy', '.npz', '.pt', '.pth')
    for item in values:
        label, sep, raw = item.partition('=')
        need(sep and NAME.fullmatch(label) and label not in result, 'learner inputs use unique LABEL=PATH.')
        path = Path(raw).resolve()
        need(str(path).lower().endswith(suffixes) and path.is_file() and not Path(raw).is_symlink(),
             'learner inputs must be explicit ordinary numerical/source manifests; documents are not accepted.')
        result[label] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}
    return result


def verify_learner_pins(pins):
    for spec in pins.values():
        path = Path(spec['path'])
        need(path.is_file() and not path.is_symlink() and path.stat().st_size == spec['bytes']
             and sha(path) == spec['sha256'], 'a declared learner-input artifact changed.')


def plan_file(path, *, test_mode=False):
    plan = read(path, 200_000)
    need(test_mode or sha(path) == PLAN_SHA256, 'the approved eight-case machine plan changed.')
    need(isinstance(plan.get('cases'), list) and plan['cases'], 'case list is missing.')
    protocol = ROOT / plan['protocol_file'] if not test_mode else Path(plan['protocol_file'])
    need(protocol.is_file() and not protocol.is_symlink()
         and sha(protocol) == plan['protocol_file_sha256'], 'protocol bytes changed.')
    need(test_mode or sha(protocol) == PROTOCOL_SHA256, 'the approved tracked protocol changed.')
    need(test_mode or [c['case_id'] for c in plan['cases']] == [f'S{i:02}' for i in range(1, 9)], 'case order differs.')
    need(len({c['case_id'] for c in plan['cases']}) == len(plan['cases']), 'case identifiers repeat.')
    for case in plan['cases']:
        need(NAME.fullmatch(case['case_id']) and isinstance(case['question'], str)
             and len(case['question']) <= 3000, 'invalid fixed case.')
        c = case['constraints']
        need(set(c) == {'view', 'max_results', 'max_paths', 'go_limit'} and c['view'] in {'candidates', 'accepted'}
             and all(type(c[k]) is int and c[k] == v for k, v in
                     [('max_results', 8), ('max_paths', 2), ('go_limit', 10)]), 'frozen caller caps differ.')
    return plan, protocol


def pharos_only(snapshot, graph):
    """Use the existing constructor, with no clinical/assay/native additions."""
    baseline = build_graph(snapshot)
    catalogue = agent.source_catalogue(baseline)
    result = {'status': 'captured_pharos_only_reconstructed', 'graph_sha256': digest(baseline),
        'snapshot_sha256': baseline['snapshot_sha256'],
        'primary_targets_equal': {t['id'] for t in baseline['targets']} == {t['id'] for t in graph['targets']},
        'nodes': len(baseline['nodes']), 'edges': len(baseline['edges']),
        'assertions': len(baseline.get('assertions', [])),
        'attached_current_source_tools': [t['name'] for t in catalogue['tools']],
        'membership': 'Existing build_graph(snapshot), no civic_snapshot, assay_attachment, extension or qualification overlays.',
        'interpretation': 'Unavailable exact native-source contracts are not biologically false Pharos answers.'}
    need(result['primary_targets_equal'], 'Pharos-only primary identity frame differs.')
    del baseline
    return result


def oracle(case, graph, folder):
    scope = agent.build_request_scope(case['question'], graph, case['constraints'])
    expected = case['expected']
    if expected['behavior'] not in {'execute', 'execute_empty_valid'}:
        return {'status': 'safe_refusal_expected', 'scope': scope, 'query': None,
                'answer': None, 'focus_graph': None, 'inspections': []}
    need(not scope['unsupported_requirements'], case['case_id'] + ' supported contract is blocked; qualify it before inference.')
    tool, uid = expected['tool'], expected['anchor_id']
    need(tool in scope['allowed_tools'] and uid in scope['protein_ids'], case['case_id'] + ' source/tool/identity unavailable.')
    chosen = {'action': 'query', 'tool': tool, 'arguments': agent._arguments(tool, uid, scope),
              'reason': 'Explicit deterministic control under the frozen request.'}
    query = agent._execute(chosen, graph, case['source_run'], folder)
    answer = agent._answer(query)
    focus = agent._focus_graph(graph, answer, query)
    inspections = []
    for citation in answer['citations'][:agent.MAX_INSPECTIONS]:
        inspections.append(agent._inspect_citation(graph, citation, case['source_run']))
    return {'status': 'deterministic_query_completed', 'scope': scope, 'plan': chosen,
            'query': query, 'answer': answer, 'focus_graph': focus, 'inspections': inspections}


def prepare(plan_path, runs_dir, config_path, attestation_path, output, *, learner_inputs=(), test_mode=False):
    """Bind actual local sources and B artifacts; no model generation/network."""
    plan, protocol = plan_file(plan_path, test_mode=test_mode)
    config = model_config(read(config_path, 100_000))
    attestation = read(attestation_path, 200_000)
    need(isinstance(attestation, dict), 'runtime attestation must be an existing operator JSON record.')
    no_credentials(attestation)
    pins = code_pins()
    output = Path(output); output.mkdir(parents=True)  # Exclusive, including empty prior attempts.
    write(output / 'plan.json', plan)
    write(output / 'model_config.json', config)
    write(output / 'runtime_attestation.json', attestation)
    (output / 'protocol.md').write_bytes(protocol.read_bytes())
    sources, cases = {}, {}
    order = [c['case_id'] for source in dict.fromkeys(c['source_run'] for c in plan['cases'])
             for c in plan['cases'] if c['source_run'] == source]
    try:
        for source in dict.fromkeys(c['source_run'] for c in plan['cases']):
            folder = folder_for(runs_dir, source)
            from biograph_steward.webapp import verify_saved_refresh
            verify_saved_refresh(folder)
            snapshot, events, graph = read_run(folder)
            baseline = pharos_only(snapshot, graph)
            del snapshot, events
            binding, inventory = source_binding(folder, graph)
            source_rel = 'sources/' + source + '.json'
            write(output / source_rel, {'binding': binding, 'inventory': inventory, 'pharos_only': baseline,
                    'catalogue': agent.source_catalogue(graph, source)})
            sources[source] = {'file': source_rel, 'sha256': sha(output / source_rel), 'binding': binding,
                               'pharos_only': baseline}
            for case in plan['cases']:
                if case['source_run'] != source:
                    continue
                control = oracle(case, graph, folder)
                relative = 'deterministic/' + case['case_id'] + '.json'
                write(output / relative, control)
                cases[case['case_id']] = {'file': relative, 'sha256': sha(output / relative),
                    'scope_sha256': digest(control['scope']), 'oracle_sha256': digest(control),
                    'controller_policy_sha256': digest(agent.GUIDANCE),
                    'plan_schema_sha256': digest(agent._plan_schema(control['scope']))}
            need(source_binding(folder, graph)[0] == binding, 'source changed during preparation.')
            del graph, control
            gc.collect()
        need(code_pins() == pins, 'implementation changed during preparation.')
        manifest = sealed({'format': FORMAT, 'created_at': now(),
            'execution_kind': 'invented_fixture' if test_mode else 'frozen_real_sources',
            'plan_sha256': sha(output / 'plan.json'), 'original_plan_file_sha256': sha(plan_path),
            'protocol_sha256': sha(output / 'protocol.md'), 'implementation': pins,
            'model_config_sha256': sha(output / 'model_config.json'),
            'original_model_config_file_sha256': sha(config_path),
            'runtime_attestation_sha256': sha(output / 'runtime_attestation.json'),
            'original_runtime_attestation_file_sha256': sha(attestation_path),
            'runtime_attestation_interpretation': 'Operator-supplied record pinned byte-for-byte after JSON copy; runner makes no serving probe.',
            'sources': sources, 'cases': cases, 'execution_order': order,
            'learner_inputs': learner_pins(learner_inputs), 'budget': {'max_calls': MAX_CALLS,
                'max_output_tokens_per_call': MAX_OUTPUT, 'maximum_requested_output_tokens': MAX_TOTAL},
            'model_calls_during_prepare': 0, 'fresh_source_retrievals': 0,
            'scientific_accuracy_or_prediction_gain_claimed': False})
        write(output / 'prepared.json', manifest)
        return manifest
    except Exception as exc:
        write(output / 'preparation_failed.json', {'at': now(), 'error_type': type(exc).__name__,
              'error': str(exc), 'model_calls': 0, 'status': 'not_ready_for_inference'})
        raise


def checked_prepared(folder, expected_sha):
    folder = Path(folder)
    need(sha(folder / 'prepared.json') == expected_sha, 'prepared receipt file hash differs.')
    bound = checked_seal(read(folder / 'prepared.json'))
    need(bound['format'] == FORMAT, 'unsupported prepared format.')
    for name, key in [('plan.json', 'plan_sha256'), ('protocol.md', 'protocol_sha256'),
                      ('model_config.json', 'model_config_sha256'), ('runtime_attestation.json', 'runtime_attestation_sha256')]:
        need(sha(folder / name) == bound[key], 'prepared ' + name + ' changed.')
    need(code_pins() == bound['implementation'], 'implementation changed after source binding.')
    for spec in list(bound['sources'].values()) + list(bound['cases'].values()):
        need(sha(folder / spec['file']) == spec['sha256'], 'prepared source/control artifact changed.')
    verify_learner_pins(bound['learner_inputs'])
    return bound, read(folder / 'plan.json'), read(folder / 'model_config.json')


class Budget:
    def __init__(self, directory):
        self.folder = Path(directory); self.folder.mkdir()
        self.calls = 0; self.reported_tokens = []; self.blocked = False

    def reserve(self, case_id, phase):
        need(not self.blocked and self.calls < MAX_CALLS
             and (self.calls + 1) * MAX_OUTPUT <= MAX_TOTAL, 'total model budget exhausted.')
        number = self.calls + 1
        write(self.folder / f'{number:04}_request_intent.json', {'at': now(), 'case_id': case_id,
              'phase': phase, 'call': number, 'max_output_tokens': MAX_OUTPUT, 'retries': 0, 'repairs': 0})
        self.calls = number
        return number


class BudgetClient:
    def __init__(self, client, budget, case_id, aliases, *, fixture=False):
        self.client, self.budget, self.case_id, self.aliases = client, budget, case_id, aliases
        need(getattr(client, 'max_output_tokens', None) == MAX_OUTPUT, 'client output budget differs.')
        allowed = {'injected_test_model'} if fixture else {'live_model', 'live_nim'}
        need(client.kind in allowed, 'test and actual serving clients must remain distinct.')

    def __getattr__(self, key):
        return getattr(self.client, key)

    def generate(self, prompt, schema, policy, audit=None):
        number = self.budget.reserve(self.case_id, (audit or {}).get('phase'))
        try:
            trace = self.client.generate(prompt, schema, policy, audit=audit)
        except Exception as exc:
            write(self.budget.folder / f'{number:04}_transport_exception.json',
                  {'at': now(), 'error_type': type(exc).__name__, 'error': str(exc)})
            raise
        write(self.budget.folder / f'{number:04}_transport_response.json', trace)
        need(type(trace.get('model_calls')) is int and trace['model_calls'] == 1, 'transport did not attest exactly one request.')
        if trace.get('model_returned') is not None:
            if trace['model_returned'] not in self.aliases:
                self.budget.blocked = True
                raise ValueError('Source-agent evaluation: returned model identity differs from the frozen aliases.')
        usage = trace.get('usage') or {}
        tokens = usage.get('output_tokens', usage.get('completion_tokens')) if isinstance(usage, dict) else None
        self.budget.reported_tokens.append(tokens)
        if tokens is not None and (type(tokens) is not int or not 0 <= tokens <= MAX_OUTPUT):
            self.budget.blocked = True
            raise ValueError('Source-agent evaluation: serving response violated the requested output-token cap.')
        return trace


def agency(result):
    steps = result['trace']['steps']
    branches = steps[0]['request']['schema'].get('anyOf', []) if steps else []
    query = [b['properties'] for b in branches if b.get('properties', {}).get('action', {}).get('const') == 'query']
    tools = {p['tool']['const'] for p in query}
    anchors = {p['arguments']['properties']['protein_id']['const'] for p in query}
    origin = ('preflight_guard' if not steps and result['trace']['preflight_blocked'] else
              'model_abstention' if result['status'] == 'abstained' and query else
              'forced_abstention_schema' if result['status'] == 'abstained' else 'model_output' if steps else 'no_model_output')
    return {'decision_origin': origin, 'actual_plan_query_branches': len(query),
            'actual_plan_tool_choices': sorted(tools), 'actual_plan_anchor_choices': sorted(anchors),
            'model_multi_tool_selection_opportunity': len(tools) > 1,
            'model_entity_selection_opportunity': len(anchors) > 1,
            'model_refusal_credit': origin == 'model_abstention'}


def comparison(case, result, control):
    expected = case['expected']; behavior = expected['behavior']
    base = {'case_id': case['case_id'], 'source_run': case['source_run'], 'status': result['status'],
        'model_calls': result['trace']['model_calls'], 'agency': agency(result),
        'graph_changes': result['graph_changes'], 'review_changes': result['review_changes'],
        'proposals_applied': result['proposals_applied'], 'scientific_accuracy_evaluated': False}
    if behavior in {'execute', 'execute_empty_valid'}:
        plan = result.get('plan') or {}; args = plan.get('arguments') or {}
        intent = plan.get('action') == 'query' and plan.get('tool') == expected['tool'] and args.get('protein_id') == expected['anchor_id']
        parity = {name: digest(result.get(key)) == digest(control.get(other)) for name, key, other in
                  [('query', 'query_result', 'query'), ('answer', 'answer', 'answer'), ('focused_graph', 'focus_graph', 'focus_graph')]}
        complete = result['status'] in {'completed', 'completed_empty'}
        chosen = [p['citation_id'] for p in result['inspections']]
        fixed = [p['citation_id'] for p in control['inspections']]
        base.update(intent_matches_frozen_request=intent, deterministic_parity=parity,
            all_query_results_retained=parity['answer'], inspection_priority=chosen,
            fixed_deterministic_priority=fixed, priority_differs_from_fixed_order=chosen != fixed,
            source_passports_replayed=True,
            query_sha256=digest(result.get('query_result')), answer_sha256=digest(result.get('answer')),
            focus_graph_sha256=digest(result.get('focus_graph')),
            case_passed=bool(intent and complete and all(parity.values())))
    else:
        safe = result['status'] in {'scope_rejected', 'abstained'} and result.get('query_result') is None
        if behavior == 'unresolved_identity_preflight':
            safe = safe and result['status'] == 'scope_rejected' and result['trace']['model_calls'] == 0
        base.update(safe_refusal=safe, case_passed=bool(safe))
    return base


def inventory(folder, exclude=()):
    result = {}
    for path in sorted(Path(folder).rglob('*')):
        need(not path.is_symlink(), 'evaluation artifacts must not contain symlinks.')
        if path.is_file():
            name = path.relative_to(folder).as_posix()
            if name in exclude:
                continue
            need(path.suffix == '.json', 'case artifacts must be generated JSON files.')
            result[name] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    return result


def run(prepared, prepared_sha, runs_dir, output, *, client_factory=None):
    bound, plan, config = checked_prepared(prepared, prepared_sha)
    fixture = bound['execution_kind'] == 'invented_fixture'
    need(fixture == (client_factory is not None), 'actual runs use the frozen HTTP client; fixture runs require explicit injection.')
    output = Path(output); output.mkdir(parents=True)
    budget = Budget(output / 'transport')
    execution_id = uuid4().hex[:12]
    write(output / 'execution_intent.json', {'format': FORMAT, 'created_at': now(),
        'execution_id': execution_id, 'execution_kind': bound['execution_kind'],
        'prepared_file_sha256': prepared_sha, 'budget': bound['budget'],
        'execution_order': bound['execution_order'], 'retries': 0, 'repairs': 0})
    by_id = {c['case_id']: c for c in plan['cases']}; summaries = []; records = []
    try:
        client = client_factory(config) if client_factory else make_client(config)
        for identifier in bound['execution_order']:
            case = by_id[identifier]; folder = folder_for(runs_dir, case['source_run'])
            case_dir = output / identifier; case_dir.mkdir(); events_dir = case_dir / 'events'; events_dir.mkdir()
            graph = None; before = None; event_number = 0; result = None; job = None; control = None
            case_calls_before = budget.calls
            def event_callback(event):
                nonlocal event_number
                event_number += 1
                write(events_dir / f'{event_number:04}_{event["event"]}.json', {'recorded_at': now(), **event})
            try:
                need(code_pins() == bound['implementation'], 'implementation changed during execution.')
                graph = load_graph(folder); before = source_binding(folder, graph)[0]
                need(before == bound['sources'][case['source_run']]['binding'], 'source changed after preparation.')
                write(case_dir / 'source_before.json', before)
                wrapper = BudgetClient(client, budget, identifier, config['returned_model_aliases'], fixture=fixture)
                # Deliberately pass only question and caller constraints, never
                # expected routes, deterministic controls or reference labels.
                result = agent.run_source_agent(case['question'], graph, source_run=case['source_run'],
                    client=wrapper, source_folder=folder, constraints=case['constraints'], event_callback=event_callback)
                write(case_dir / 'agent_result.json', result)
                agent.verify_source_agent_result(result, graph, case['source_run'], folder)
                control = oracle(case, graph, folder)
                need(digest(control) == bound['cases'][identifier]['oracle_sha256'], 'deterministic B replay changed.')
                summary = comparison(case, result, control)
                write(case_dir / 'deterministic_replay.json', {'oracle_sha256': digest(control),
                    'query_sha256': digest(control.get('query')), 'answer_sha256': digest(control.get('answer')),
                    'focus_graph_sha256': digest(control.get('focus_graph')),
                    'interpretation': 'Actual post-agent replay under identical source/view/caps, not a repaired agent answer.'})
            except Exception as exc:
                write(case_dir / 'case_exception.json', {'at': now(), 'error_type': type(exc).__name__, 'error': str(exc)})
                summary = {'case_id': identifier, 'source_run': case['source_run'], 'status': 'runner_exception',
                           'case_passed': False, 'error_type': type(exc).__name__, 'scientific_accuracy_evaluated': False}
            finally:
                if graph is not None:
                    after = source_binding(folder, graph)[0]
                    write(case_dir / 'source_after.json', after)
                    summary['source_binding_unchanged'] = before == after
                    summary['prepared_source_binding_matched'] = before == bound['sources'][case['source_run']]['binding']
                    if before != after or not summary['prepared_source_binding_matched']:
                        budget.blocked = True; summary['case_passed'] = False
                    del graph
                gc.collect()
            # Release our complete graph before the existing store performs
            # its independent ordinary-source load/verification.
            if result is not None:
                try:
                    job = save_source_agent_job(result, runs_dir,
                        job_id='source_agent_eval_' + execution_id + '_' + identifier)
                    summary['saved_job_id'] = job['job_id']
                    summary['saved_job_manifest_sha256'] = sha(Path(runs_dir) / job['job_id'] / 'manifest.json')
                except Exception as exc:
                    write(case_dir / 'job_save_failure.json', {'at': now(), 'error_type': type(exc).__name__, 'error': str(exc)})
                    summary.update(case_passed=False, job_save_failed=True)
            original = bound['sources'][case['source_run']]['pharos_only']
            requested = case['expected']['tool']
            summary['captured_pharos_only'] = {
                'status': 'native_source_contract_unavailable' if requested and requested not in original['attached_current_source_tools']
                    else 'unsupported_or_unresolved_request' if requested is None else 'source_contract_available',
                'graph_sha256': original['graph_sha256'], 'snapshot_sha256': original['snapshot_sha256'],
                'primary_targets_equal': original['primary_targets_equal'],
                'biological_correctness_scored': False}
            summary['reserved_transport_calls'] = budget.calls - case_calls_before
            if result is not None:
                summary['trace_transport_accounting_matches'] = result['trace']['model_calls'] == summary['reserved_transport_calls']
                if not summary['trace_transport_accounting_matches']:
                    summary['case_passed'] = False
            summary['event_files'] = event_number
            write(case_dir / 'case_summary.json', summary)
            manifest = sealed({'case_id': identifier, 'files': inventory(case_dir)})
            write(case_dir / 'case_manifest.json', manifest)
            records.append({'case_id': identifier, 'manifest_sha256': sha(case_dir / 'case_manifest.json')})
            summaries.append(summary)
            print(json.dumps({'case': identifier, 'status': summary['status'], 'passed': summary['case_passed'],
                  'reserved_model_calls': budget.calls}), flush=True)
            del result, job, control
            gc.collect()
            if budget.blocked:
                break
        verify_learner_pins(bound['learner_inputs'])
        need(code_pins() == bound['implementation'], 'implementation changed before completion.')
        finished = sealed({'format': FORMAT, 'created_at': now(), 'execution_id': execution_id,
            'execution_kind': bound['execution_kind'], 'status': 'completed' if len(records) == len(plan['cases']) else 'stopped',
            'prepared_file_sha256': prepared_sha, 'case_order': [c['case_id'] for c in plan['cases']],
            'case_records': records, 'reserved_model_calls': budget.calls,
            'requested_output_token_ceiling': budget.calls * MAX_OUTPUT,
            'reported_output_tokens': sum(budget.reported_tokens) if all(type(t) is int for t in budget.reported_tokens)
                and len(budget.reported_tokens) == budget.calls else None,
            'learner_inputs_unchanged': True, 'learner_input_artifacts': len(bound['learner_inputs']),
            'prediction_input_applicability': 'identity_only_no_predictor_invoked' if bound['learner_inputs']
                else 'not_applicable_no_source_compatible_prediction_artifact',
            'predictor_invoked': False, 'prediction_gain_evaluated': False,
            'scientific_accuracy_evaluated': False, 'new_source_retrievals': 0,
            'transport_files': inventory(output / 'transport')})
        write(output / 'execution.json', finished)
        return finished
    except Exception as exc:
        write(output / 'execution_failure.json', {'at': now(), 'error_type': type(exc).__name__, 'error': str(exc),
              'completed_cases': len(records), 'reserved_model_calls': budget.calls,
              'requested_output_token_ceiling': budget.calls * MAX_OUTPUT, 'retries': 0, 'repairs': 0})
        raise


def report(execution, output):
    """Read-only artifact verification and a source-free behavioral aggregate."""
    folder = Path(execution); run_info = checked_seal(read(folder / 'execution.json'))
    need(inventory(folder / 'transport') == run_info['transport_files'], 'transport event bytes changed.')
    summaries = {}
    for spec in run_info['case_records']:
        case = folder / spec['case_id']; manifest = case / 'case_manifest.json'
        need(sha(manifest) == spec['manifest_sha256'], 'case completion manifest changed.')
        record = checked_seal(read(manifest))
        need(inventory(case, exclude=('case_manifest.json',)) == record['files'], 'case event/result bytes changed.')
        summaries[spec['case_id']] = read(case / 'case_summary.json')
    rows = [summaries[c] for c in run_info['case_order'] if c in summaries]
    value = sealed({'format': FORMAT + '.report', 'created_at': now(), 'status': run_info['status'],
        'execution_kind': run_info['execution_kind'], 'execution_file_sha256': sha(folder / 'execution.json'),
        'prepared_file_sha256': run_info['prepared_file_sha256'], 'cases_expected': len(run_info['case_order']),
        'cases_recorded': len(rows), 'behavioral_cases_passed': sum(r['case_passed'] for r in rows),
        'result_statuses': dict(Counter(r['status'] for r in rows)), 'cases': rows,
        'captured_pharos_native_contract_statuses': dict(Counter(r['captured_pharos_only']['status'] for r in rows)),
        'deterministic_agent_exact_answer_and_focus_parity_cases': sum(
            all(r.get('deterministic_parity', {}).values()) for r in rows if 'deterministic_parity' in r),
        'model_calls_reserved': run_info['reserved_model_calls'],
        'maximum_requested_output_tokens': run_info['requested_output_token_ceiling'],
        'reported_output_tokens': run_info['reported_output_tokens'],
        'learner_input_artifacts_unchanged': run_info['learner_inputs_unchanged'],
        'learner_input_artifacts': run_info['learner_input_artifacts'],
        'prediction_input_applicability': run_info['prediction_input_applicability'],
        'predictor_invoked': False, 'prediction_gain_evaluated': False, 'scientific_accuracy_evaluated': False,
        'interpretation': 'Fixed development task/source parity and guard behavior. Unavailable native semantics in captured Pharos are not biological falsehoods. No new accuracy, independence or prediction-gain claim.',
        'raw_source_or_model_text_included': False})
    write(output, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for name in ('plan', 'runs-dir', 'model-config', 'runtime-attestation', 'output'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--learner-input', action='append', default=[])
    p = sub.add_parser('run')
    for name in ('prepared', 'prepared-sha256', 'runs-dir', 'output'):
        p.add_argument('--' + name, required=True)
    p = sub.add_parser('report'); p.add_argument('--execution', required=True); p.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        value = prepare(args.plan, args.runs_dir, args.model_config, args.runtime_attestation, args.output,
                        learner_inputs=args.learner_input)
    elif args.command == 'run':
        value = run(args.prepared, args.prepared_sha256, args.runs_dir, args.output)
    else:
        value = report(args.execution, args.output)
    print(json.dumps({k: value[k] for k in ('format', 'status', 'content_sha256') if k in value}, indent=2))


if __name__ == '__main__':
    main()
