"""One isolated, tool-disabled Codex CLI turn returning bounded JSON.

Authentication stays with the CLI. No repository, history or private event text
is exposed to callers. Domain adapters validate the returned JSON separately.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from .client import digest
from .planning import PlannerUnavailable

DISABLED_FEATURES = ('shell_tool', 'multi_agent', 'apps', 'hooks', 'remote_plugin',
                     'shell_snapshot', 'memories')
SAFE_ENV = {'HOME', 'CODEX_HOME', 'PATH', 'LANG', 'USER', 'TMPDIR', 'SSL_CERT_FILE',
            'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY',
            'https_proxy', 'http_proxy', 'all_proxy', 'no_proxy'}


class CodexJSONClient:
    def __init__(self, model=None, executable=None, runner=None):
        self.model = model or os.environ.get('BIOGRAPH_CODEX_MODEL')
        if not isinstance(self.model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,200}', self.model):
            raise PlannerUnavailable('Set BIOGRAPH_CODEX_MODEL explicitly to an available Codex model. No model was called.')
        self.executable = shutil.which(executable or os.environ.get('BIOGRAPH_CODEX_BIN', 'codex'))
        if not self.executable:
            raise PlannerUnavailable('Codex CLI was not found. Configure BIOGRAPH_CODEX_BIN or use the API planner. No model was called.')
        self.runner = runner or subprocess.run
        self.kind = 'live_codex_cli' if runner is None else 'injected_test_model'
        self.endpoint = 'local Codex CLI'
        self.api = 'codex_exec'
        try:
            version = self.runner([self.executable, '--version'], capture_output=True, text=True, timeout=10)
            if version.returncode != 0 or not re.fullmatch(r'[A-Za-z0-9 ._+/-]{1,120}', version.stdout.strip()):
                raise ValueError('Unsupported version output.')
            self.cli_version = version.stdout.strip()
        except (OSError, subprocess.SubprocessError, ValueError):
            raise PlannerUnavailable('Codex CLI version check failed. No model was called.') from None

    def generate(self, prompt, schema_definition, policy, audit=None):
        trace = {'provider_kind': self.kind, 'policy': policy, 'model_requested': self.model,
                 'model_returned': None, 'cli_version': self.cli_version, 'endpoint': self.endpoint, 'api': self.api,
                 'model_calls': 1, 'model_call_count_basis': 'One requested CLI turn; internal HTTP attempts are not exposed.',
                 'transport_requests': None, 'usage': None, 'cost': None,
                 'cost_note': 'No price table assumed; CLI usage is recorded when returned.',
                 **(audit or {}), 'schema_sha256': digest(schema_definition),
                 'request_sha256': digest({'prompt': prompt, 'model': self.model, 'schema': schema_definition,
                                           'disabled_features': DISABLED_FEATURES, 'web_search': 'disabled',
                                           'sandbox': 'read-only', 'ephemeral': True, 'ignore_user_config': True}),
                 'execution_guard': {'sandbox': 'read-only', 'disabled_features': list(DISABLED_FEATURES),
                                     'web_search': 'disabled', 'empty_working_directory': True,
                                     'ephemeral': True, 'ignore_user_config': True},
                 'status': 'model_error', 'output': None}
        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix='biograph-isolated-') as directory:
                root = Path(directory)
                schema = root / 'schema.json'; output = root / 'output.json'
                schema.write_text(json.dumps(schema_definition), encoding='utf-8')
                args = [self.executable, '--no-daemon', 'exec', '--ignore-user-config', '--ephemeral',
                        '--skip-git-repo-check', '--sandbox', 'read-only', '--model', self.model]
                for feature in DISABLED_FEATURES:
                    args.extend(['--disable', feature])
                args.extend(['-c', 'web_search="disabled"', '--output-schema', str(schema),
                             '--output-last-message', str(output), '--json', '--cd', directory, '-'])
                result = self.runner(args, input=prompt, text=True, capture_output=True, timeout=90,
                                     env={k: v for k, v in os.environ.items() if k in SAFE_ENV})
                # Never include stderr/authentication material or private reasoning in saved traces/errors.
                if result.returncode != 0:
                    raise ValueError('Codex process failed. No retry or fallback was used.')
                if len(result.stdout) > 1_000_000:
                    raise ValueError('Codex event stream exceeds 1 MB.')
                events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
                self._check_events(events, trace)
                if not output.is_file() or output.stat().st_size > 20_000:
                    raise ValueError('Codex did not return a bounded final JSON object.')
                raw = output.read_text(encoding='utf-8')
                trace['response_sha256'] = digest(raw)
                trace.update(status='completed', output=json.loads(raw))
        except subprocess.TimeoutExpired:
            trace['error'] = 'Codex turn timed out after 90 seconds. No retry or fallback was used.'
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
            trace['error'] = 'Codex returned an incomplete, malformed, or disallowed turn.'
        trace['latency_ms'] = round((time.perf_counter() - started) * 1000, 3)
        return trace

    @staticmethod
    def _check_events(events, trace):
        allowed = {'thread.started', 'turn.started', 'item.started', 'item.updated', 'item.completed', 'turn.completed'}
        if any(not isinstance(e, dict) or not isinstance(e.get('type'), str) for e in events):
            raise ValueError('Invalid event format.')
        types = [e.get('type') for e in events]
        items = [e.get('item', {}) for e in events if e.get('type', '').startswith('item.')]
        if any(not isinstance(i, dict) for i in items):
            raise ValueError('Invalid item format.')
        item_types = [i.get('type') for i in items]
        # Save only event/type labels; never persist raw event contents or reasoning.
        if any(t not in allowed for t in types) or any(t not in {'reasoning', 'agent_message'} for t in item_types):
            raise ValueError('Disallowed CLI event or tool item.')
        trace['event_types'] = types
        trace['item_types'] = item_types
        if types.count('thread.started') != 1 or types.count('turn.started') != 1 or types.count('turn.completed') != 1:
            raise ValueError('Expected exactly one completed turn.')
        if sum(e['type'] == 'item.completed' and e.get('item', {}).get('type') == 'agent_message' for e in events) != 1:
            raise ValueError('Expected one final message.')
        usage = next(e.get('usage', {}) for e in events if e['type'] == 'turn.completed')
        if not isinstance(usage, dict):
            raise ValueError('Invalid usage format.')
        trace['usage'] = {k: v for k, v in usage.items() if k in {
            'input_tokens', 'output_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
            'reasoning_output_tokens'} and type(v) is int and v >= 0}
