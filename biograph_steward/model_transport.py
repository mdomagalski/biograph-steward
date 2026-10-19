"""One bounded JSON request to an explicitly configured model endpoint.

No automatic provider selection, retries, redirects, tool execution or JSON repair.
Domain adapters retain responsibility for scope and exact source validation.
"""
from copy import deepcopy
import json
import os
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from .client import digest


class ModelUnavailable(ValueError):
    pass


def setting(role, name, default=None):
    """Role overrides shared model settings. Empty explicit values do not fall back."""
    shared_name = 'BIOGRAPH_MODEL_ID' if name == 'MODEL' else f'BIOGRAPH_MODEL_{name}'
    return os.environ.get(f'BIOGRAPH_{role.upper()}_{name}', os.environ.get(shared_name, default))


def selected_provider(role, default):
    provider = setting(role, 'PROVIDER', default)
    if provider not in {'api', 'nim', 'codex'}:
        raise ModelUnavailable('Model provider must be api, nim or codex. No model was called.')
    return provider


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An inference key must never be forwarded to a redirected host.
        return None


class JSONModelClient:
    def __init__(self, *, role, provider='api', model=None, endpoint=None, api=None, transport=None):
        if role not in {'planner', 'verifier'} or provider not in {'api', 'nim'}:
            raise ModelUnavailable('Unsupported model role or HTTP provider.')
        self.role = role; self.provider = provider; self.transport = transport
        self.model = model if model is not None else setting(role, 'MODEL')
        self.endpoint = endpoint if endpoint is not None else setting(role, 'ENDPOINT',
            'https://api.openai.com/v1/responses' if provider == 'api' else None)
        self.api = api if api is not None else setting(role, 'API', 'nim_chat' if provider == 'nim' else 'responses')
        if not isinstance(self.model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,200}', self.model):
            raise ModelUnavailable('Configure an explicit model ID. No model was called.')
        if not isinstance(self.endpoint, str) or self.api not in {'responses', 'chat_completions', 'nim_chat'}:
            raise ModelUnavailable('Configure a full endpoint and a supported model API. No model was called.')
        try:
            u = urlparse(self.endpoint); u.port  # Validate malformed/out-of-range ports.
        except ValueError:
            raise ModelUnavailable('Invalid model endpoint.') from None
        if (not u.hostname or u.username is not None or u.password is not None or u.query or u.fragment
                or any(c.isspace() for c in self.endpoint)
                or (u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in {'localhost', '127.0.0.1', '::1'}))):
            raise ModelUnavailable('Model endpoint must use HTTPS or loopback HTTP, without URL credentials, query or fragment.')
        self.loopback = u.hostname in {'localhost', '127.0.0.1', '::1'}
        if u.hostname == 'api.openai.com':
            self.key = os.environ.get('OPENAI_API_KEY')
        else:
            self.key = setting(role, 'API_KEY')
            if self.key is None and provider == 'nim':
                self.key = os.environ.get('NVIDIA_API_KEY')
        if u.hostname in {'api.openai.com', 'integrate.api.nvidia.com'} and not self.key and transport is None:
            raise ModelUnavailable('The selected model service requires its API key. Configure it in the environment; no model was called.')
        if self.key is not None and (not isinstance(self.key, str) or any(c in self.key for c in '\r\n')):
            raise ModelUnavailable('Invalid model credential configuration.')
        try:
            self.max_output_tokens = int(setting(role, 'MAX_OUTPUT_TOKENS', '1600' if role == 'planner' else '3000'))
            self.timeout = int(setting(role, 'TIMEOUT', '45' if role == 'planner' else '90'))
        except (ValueError, TypeError):
            raise ModelUnavailable('Model token/timeout budgets must be integers.') from None
        if not 128 <= self.max_output_tokens <= 8192 or not 1 <= self.timeout <= 300:
            raise ModelUnavailable('Model budgets must be 128–8192 output tokens and 1–300 seconds.')
        self.kind = ('live_nim' if provider == 'nim' else 'live_model') if transport is None else 'injected_test_model'

    def generate(self, prompt, schema_definition, policy, audit=None):
        instructions, marker, data = prompt.partition('\nUntrusted input data:\n')
        messages = ([{'role': 'system', 'content': instructions}, {'role': 'user', 'content': data}]
                    if marker else [{'role': 'user', 'content': prompt}])
        fmt = {'type': 'json_schema', 'name': re.sub(r'[^A-Za-z0-9_]', '_', policy)[:64],
               'strict': True, 'schema': schema_definition}
        payload = {'model': self.model}
        if self.api == 'responses':
            payload.update(input=messages, store=False, text={'format': fmt}, max_output_tokens=self.max_output_tokens)
        elif self.api == 'chat_completions':
            payload.update(messages=messages, store=False, stream=False,
                           response_format={'type': 'json_schema', 'json_schema': {k: v for k, v in fmt.items() if k != 'type'}},
                           max_completion_tokens=self.max_output_tokens)
        else:
            # NIM's guided-json protocol differs from standard Chat Completions.
            payload.update(messages=messages, stream=False, temperature=0,
                           guided_json=schema_definition, max_tokens=self.max_output_tokens)
        trace = {'provider_kind': self.kind, 'provider_requested': self.provider, 'policy': policy,
                 'model_requested': self.model, 'model_returned': None, 'endpoint': self.endpoint, 'api': self.api,
                 'model_calls': 1, 'transport_requests': 1, 'usage': None, 'cost': None,
                 'cost_note': 'No price table assumed; returned token counts are recorded.',
                 **(audit or {}), 'schema_sha256': digest(schema_definition), 'request_sha256': digest(payload),
                 'request_settings': {'max_output_tokens': self.max_output_tokens, 'timeout_seconds': self.timeout},
                 'execution_guard': {'tools_supplied': False, 'redirects': False, 'retries': 0, 'repair_calls': 0,
                                     'conversation_history': False, 'loopback_bypasses_proxy': self.loopback},
                 'status': 'model_error', 'output': None}
        started = time.perf_counter()
        try:
            if self.transport is not None:
                raw = self.transport(deepcopy(payload))
            else:
                headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
                if self.key:
                    headers['Authorization'] = 'Bearer ' + self.key
                req = Request(self.endpoint, data=json.dumps(payload, ensure_ascii=True, allow_nan=False).encode(), headers=headers)
                context = ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or None)
                handlers = [_NoRedirect(), HTTPSHandler(context=context)]
                if self.loopback:
                    handlers.append(ProxyHandler({}))
                opener = build_opener(*handlers)
                with opener.open(req, timeout=self.timeout) as response:
                    body = response.read(1_000_001)
                if len(body) > 1_000_000:
                    raise ValueError('Bounded model response exceeded.')
                raw = json.loads(body)
        except (HTTPError, URLError, OSError, ValueError, TypeError) as exc:
            if isinstance(exc, HTTPError):
                exc.close()
            trace['error'] = 'Model request failed; no retry, redirect or fallback was used.'
        else:
            try:
                trace['response_sha256'] = digest(raw)
                if not isinstance(raw, dict):
                    raise ValueError('Invalid response envelope.')
                if isinstance(raw.get('model'), str):
                    trace['model_returned'] = raw['model'][:200]
                if isinstance(raw.get('usage'), dict):
                    # Do not persist unknown provider metadata or private reasoning.
                    trace['usage'] = {k: v for k, v in raw['usage'].items()
                                      if k in {'input_tokens', 'output_tokens', 'prompt_tokens', 'completion_tokens', 'total_tokens'}
                                      and type(v) is int and v >= 0}
                text = self._content(raw)
                if not isinstance(text, str) or len(text.encode('utf-8')) > 20_000:
                    raise ValueError('Final model JSON exceeds the output bound.')
                trace.update(status='completed', output=json.loads(text))
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                trace.update(status='invalid_output', error='Model returned malformed, refused, incomplete or disallowed output.')
        trace['latency_ms'] = round((time.perf_counter() - started) * 1000, 3)
        return trace

    def _content(self, raw):
        if self.api == 'responses':
            if raw.get('status') != 'completed' or not isinstance(raw.get('output'), list):
                raise ValueError('Incomplete response.')
            items = raw['output']
            if any(not isinstance(i, dict) or i.get('type') not in {'reasoning', 'message'} for i in items):
                raise ValueError('Tool output is not permitted.')
            messages = [i for i in items if i['type'] == 'message']
            if len(messages) != 1:
                raise ValueError('Exactly one final message required.')
            if messages[0].get('role', 'assistant') != 'assistant' or messages[0].get('status', 'completed') != 'completed':
                raise ValueError('Invalid final message role/status.')
            content = messages[0]['content']
            if not isinstance(content, list) or not content or any(c.get('type') != 'output_text' for c in content):
                raise ValueError('Refused or invalid message.')
            return ''.join(c['text'] for c in content)
        choices = raw['choices']
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError('Exactly one choice required.')
        choice = choices[0]; message = choice['message']
        if (choice.get('finish_reason') != 'stop' or message.get('role', 'assistant') != 'assistant'
                or message.get('refusal') or message.get('tool_calls') or message.get('function_call')):
            raise ValueError('Refused, incomplete or tool output.')
        return message['content']
