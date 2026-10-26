"""Deployment diagnostics and a reusable bounded question workflow."""
import os
from pathlib import Path

from . import __version__
from .model_transport import selected_provider
from .planning import configured_planner, execute_plan
from .runtime import AccessPolicy, runs_directory, cache_directory


def runtime_status():
    status = {'version': __version__, 'inference_performed': False,
              'paths': {'runs': str(runs_directory().resolve()), 'cache': str(cache_directory().resolve())}}
    try:
        host = os.environ.get('BIOGRAPH_HOST', '127.0.0.1')
        port = int(os.environ.get('BIOGRAPH_PORT', '8765'))
        if not 1 <= port <= 65535:
            raise ValueError('BIOGRAPH_PORT must be 1–65535.')
        policy = AccessPolicy(host, os.environ.get('BIOGRAPH_ALLOWED_ORIGINS', ''), os.environ.get('BIOGRAPH_ACCESS_TOKEN'))
        status['hosting'] = {'valid': True, 'host': host, 'port': port,
                             'authentication_required': policy.token is not None,
                             'allowed_origins': [list(o) for o in sorted(policy.origins)]}
    except ValueError as exc:
        status['hosting'] = {'valid': False, 'reason': str(exc)}
    try:
        client = configured_planner()
        status['planner'] = {'configuration_valid': True, 'provider': selected_provider('planner', 'api'),
                             'model': client.model, 'endpoint': client.endpoint, 'api': client.api,
                             'prompt_profile': getattr(client, 'prompt_profile', None),
                             'planner_protocol': getattr(client, 'protocol', None),
                             'availability_checked': False}
    except ValueError as exc:
        status['planner'] = {'configuration_valid': False, 'reason': str(exc), 'availability_checked': False}
    return status


class BoundedQuestionWorkflow:
    """A fixed source run, one validated plan and at most one read-only query.

    User input is a question only. It cannot choose files, tools or graph writes.
    Results include their trace; the caller decides how to retain that artifact.
    """
    def __init__(self, source_run, planner=None, max_results=8, max_paths=3):
        from .reviews import read_run
        if type(max_results) is not int or not 1 <= max_results <= 30 or type(max_paths) is not int or not 1 <= max_paths <= 5:
            raise ValueError('Workflow budgets are 1–30 results and 1–5 paths.')
        self.source = Path(source_run).resolve()
        self.snapshot, self.events, self.graph = read_run(self.source)
        if self.graph.get('scope', {}).get('kind') == 'protein_cohort':
            raise ValueError('The model workflow supports disease-scoped saved graphs only. Use the deterministic protein-cohort question; no model was called.')
        self.planner = planner if planner is not None else configured_planner()
        self.budgets = {'max_results': max_results, 'max_paths': max_paths}

    def run(self, question):
        # Detect source or review changes instead of silently using an old graph.
        from .reviews import read_run
        from .questions import graph_basis
        _, _, current = read_run(self.source)
        if graph_basis(current) != graph_basis(self.graph):
            raise ValueError('Workflow source changed; reload the configured workflow.')
        trace = self.planner.plan(question, self.graph)
        if trace.get('status') != 'validated' or trace.get('plan') is None:
            return {'status': 'invalid_plan', 'reason': trace.get('error', 'Model plan failed validation.'),
                    'answer': None, 'tool_calls': 0, 'trace': trace}
        result = execute_plan(trace['plan'], self.graph, source_run=self.source.name, **self.budgets)
        return {**result, 'trace': trace}
