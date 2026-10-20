"""Optional signed-in Codex CLI adapter for one isolated planning turn."""
from .codex_transport import CodexJSONClient, DISABLED_FEATURES
from .planning import planning_request, selected_protocol, validate_planned_output


class CodexPlanner(CodexJSONClient):
    def __init__(self, model=None, executable=None, runner=None, protocol=None):
        self.protocol = selected_protocol(protocol)
        super().__init__(model=model, executable=executable, runner=runner)

    def plan(self, question, graph):
        prompt, schema, policy, audit, resolution = planning_request(question, graph, self.protocol)
        trace = self.generate(prompt, schema, policy, audit)
        trace['planner_kind'] = trace.pop('provider_kind')
        proposed = trace.pop('output')
        trace['plan'] = None
        if trace['status'] != 'completed':
            trace['status'] = 'planner_error'
        else:
            trace['proposed_plan'] = proposed
            try:
                trace.update(status='validated', plan=validate_planned_output(proposed, graph, resolution))
            except (ValueError, TypeError):
                trace.update(status='invalid_plan', error='Codex output failed the supported plan schema or source scope.')
        return trace
