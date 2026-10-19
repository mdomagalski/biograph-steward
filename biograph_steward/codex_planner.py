"""Optional signed-in Codex CLI adapter for one isolated planning turn."""
import json

from .client import digest
from .codex_transport import CodexJSONClient, DISABLED_FEATURES
from .planning import INSTRUCTIONS, PLAN_SCHEMA, POLICY, catalogue, validate_plan


class CodexPlanner(CodexJSONClient):
    def plan(self, question, graph):
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 4000:
            raise ValueError('Planner question must contain 1–4000 characters.')
        context = catalogue(graph)
        prompt = INSTRUCTIONS + '\nUntrusted input data:\n' + json.dumps({'question': question, 'catalogue': context}, ensure_ascii=True)
        trace = self.generate(prompt, PLAN_SCHEMA, POLICY, {
            'question_sha256': digest(question), 'catalogue_sha256': digest(context),
            'instructions_sha256': digest(INSTRUCTIONS)})
        trace['planner_kind'] = trace.pop('provider_kind')
        proposed = trace.pop('output')
        trace['plan'] = None
        if trace['status'] != 'completed':
            trace['status'] = 'planner_error'
        else:
            trace['proposed_plan'] = proposed
            try:
                trace.update(status='validated', plan=validate_plan(proposed, graph))
            except (ValueError, TypeError):
                trace.update(status='invalid_plan', error='Codex output failed the supported plan schema or source scope.')
        return trace
