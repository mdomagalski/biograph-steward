"""Operator checks for an existing deployment; only synthetic records are created."""
import json
import os
from pathlib import Path
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from . import __version__
from .client import digest, utcnow, write_json
from .model_transport import _NoRedirect
from .planning import semantic_plan, validate_plan
from .questions import answer_question, graph_basis, verify_answer
from .runtime import AccessPolicy, loopback_host, origin_identity

FORMAT = 'biograph-steward.deployment-smoke.v1'
QUESTION = ('Inspect candidate proteins sharing pathway annotations with DEMO_P1 '
            'in the saved Demo colorectal cancer cohort. Use shared pathways only.')
ID = re.compile(r'[A-Za-z0-9_-]{1,80}')
SHA = re.compile(r'[0-9a-f]{64}')


class SmokeFailure(ValueError):
    """A public diagnostic without remote response bodies or credentials."""


class DeploymentClient:
    def __init__(self, base_url, origin=None, timeout=120):
        scheme, host, _ = origin_identity(base_url)
        if scheme != 'https' and not loopback_host(host):
            raise ValueError('Deployment URL must use HTTPS or loopback HTTP.')
        self.base = base_url.rstrip('/')
        self.origin = origin or self.base
        origin_scheme, origin_host, _ = origin_identity(self.origin)
        if origin_scheme != 'https' and not loopback_host(origin_host):
            raise ValueError('Browser origin must use HTTPS or loopback HTTP.')
        self.token = os.environ.get('BIOGRAPH_ACCESS_TOKEN')
        AccessPolicy(allowed_origins=[self.origin], access_token=self.token)
        if not loopback_host(host) and self.token is None:
            raise ValueError('Remote deployment checks require BIOGRAPH_ACCESS_TOKEN.')
        if type(timeout) is not int or not 1 <= timeout <= 300:
            raise ValueError('Deployment timeout must be 1–300 seconds.')
        self.timeout = timeout
        context = ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or None)
        handlers = [_NoRedirect(), HTTPSHandler(context=context)]
        if loopback_host(host):
            handlers.append(ProxyHandler({}))
        self.opener = build_opener(*handlers)

    def request(self, path, body=None, *, authenticated=True, origin=None):
        headers = {'Accept': 'application/json'}
        if authenticated and self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=True, allow_nan=False).encode()
            headers.update({'Content-Type': 'application/json', 'Origin': origin or self.origin})
        req = Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise SmokeFailure('Deployment response exceeded the size bound.')
                return response.status, raw
        except HTTPError as exc:
            code = exc.code
            exc.close()  # Do not persist error pages, follow redirects or forward a key.
            return code, b''
        except (URLError, OSError, ValueError, TypeError):
            raise SmokeFailure('Deployment request failed; no retry or redirect was used.') from None

    def json(self, path, body=None):
        code, raw = self.request(path, body)
        if code != 200:
            raise SmokeFailure(f'Deployment returned HTTP {code}; response body was not saved.')
        try:
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError
            return result
        except (ValueError, TypeError):
            raise SmokeFailure('Deployment returned an invalid JSON object.') from None


def _receipt(path):
    if Path(path).stat().st_size > 100_000:
        raise ValueError('Deployment receipt exceeds the size bound.')
    receipt = json.loads(Path(path).read_text(encoding='utf-8'))
    if (not isinstance(receipt, dict) or receipt.get('format') != FORMAT or receipt.get('phase') != 'create'
            or receipt.get('status') != 'passed'
            or receipt.get('receipt_sha256') != digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'})):
        raise ValueError('Use an unchanged, successful initial deployment report as the receipt.')
    for key, pattern in [('source_run', ID), ('question_id', ID), ('snapshot_sha256', SHA),
                         ('graph_basis_sha256', SHA), ('answer_sha256', SHA)]:
        if not isinstance(receipt.get(key), str) or not pattern.fullmatch(receipt[key]):
            raise ValueError('Deployment receipt has invalid source bindings.')
    return receipt


def run_smoke(base_url, output, *, with_planner=False, receipt=None, origin=None, timeout=120):
    """Create/check synthetic data, or reopen a prior receipt after an operator restart.

    Restart is external. Passing a receipt proves reopening the same saved data;
    this client cannot attest that the operator actually restarted the service.
    """
    if receipt is not None and with_planner:
        raise ValueError('Receipt verification is read-only and cannot request another model turn.')
    prior = _receipt(receipt) if receipt is not None else None
    client = DeploymentClient(base_url, origin, timeout)
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'format': FORMAT, 'app_version': __version__, 'created_at': utcnow(),
              'phase': 'reopen' if prior else 'create', 'base_url': client.base, 'browser_origin': client.origin,
              'status': 'running', 'checks': [], 'planner_requested': bool(with_planner),
              'planner_http_requests': 0, 'reported_model_calls': 0, 'scientific_improvement_established': False,
              'data_kind': 'synthetic_demo', 'restart_independently_attested': False}
    phase = 'health'

    def require(condition, message):
        if not condition:
            raise SmokeFailure(message)

    def passed():
        report['checks'].append({'check': phase, 'status': 'passed'})

    try:
        health = client.json('/healthz')
        require(health.get('status') == 'ok' and health.get('version') == __version__,
                'Service health/version differs from this checkout.')
        report['service_version'] = health['version']; passed()
        phase = 'authentication'
        code, _ = client.request('/', authenticated=False)
        require(code == (401 if client.token else 200), 'Unexpected anonymous access policy.')
        code, ui = client.request('/')
        require(code == 200 and b'BioGraph' in ui, 'Authenticated UI could not be opened.')
        report['authentication_required'] = client.token is not None; passed()
        if prior:
            phase = 'saved_source_reopens'
            source_id = prior['source_run']
            loaded = client.json('/api/run/' + source_id)
            graph = loaded['graph']
            require(loaded.get('run_id') == source_id and graph.get('data_kind') == 'synthetic_demo',
                    'Reopened source is not the expected synthetic run.')
            require(graph.get('snapshot_sha256') == prior['snapshot_sha256']
                    and graph_basis(graph) == prior['graph_basis_sha256'], 'Saved source/review basis changed.')
            passed()
            phase = 'saved_answer_reopens'
            saved = client.json('/api/question/' + prior['question_id'])['answer']
            verify_answer(saved)
            require(saved['answer_sha256'] == prior['answer_sha256'], 'Saved question result changed.')
            report.update({k: prior[k] for k in ('source_run', 'question_id', 'snapshot_sha256',
                                               'graph_basis_sha256', 'answer_sha256')})
            report['initial_receipt_sha256'] = prior['receipt_sha256']; passed()
        else:
            phase = 'browser_origin_guard'
            code, _ = client.request('/api/build', {'mode': 'demo'}, origin='null')
            require(code == 403, 'Unapproved browser origin was not rejected.'); passed()
            phase = 'synthetic_source'
            created = client.json('/api/build', {'mode': 'demo'})
            source_id = created.get('run_id'); graph = created['graph']
            require(isinstance(source_id, str) and ID.fullmatch(source_id)
                    and graph.get('data_kind') == 'synthetic_demo', 'Expected an explicitly synthetic saved run.')
            report.update(source_run=source_id, snapshot_sha256=graph['snapshot_sha256'],
                          graph_basis_sha256=graph_basis(graph)); passed()
            phase = 'traceable_deterministic_question'
            result = client.json('/api/question', {'run_id': source_id, 'protein': 'DEMO_P1',
                                 'relations': ['shared_pathways'], 'view': 'candidates',
                                 'max_results': 8, 'max_paths': 3})
            answer = result['answer']; verify_answer(answer)
            expected = answer_question(graph, 'DEMO_P1', relations=['shared_pathways'], view='candidates',
                                       max_results=8, max_paths=3, source_run=source_id)
            require(answer['answer_sha256'] == expected['answer_sha256'] and bool(answer['citations']),
                    'Remote deterministic result differs from the local query or lacks source citations.')
            require(isinstance(result.get('question_id'), str) and ID.fullmatch(result['question_id']),
                    'Invalid saved question identity.')
            report.update(question_id=result['question_id'], answer_sha256=answer['answer_sha256'])
            write_json(out / 'deterministic_answer.json', answer); passed()
            if with_planner:
                phase = 'one_bounded_model_plan'
                report.update(planner_http_requests=1, reported_model_calls=None)
                result = client.json('/api/plan', {'run_id': source_id, 'question': QUESTION})
                trace = result['trace']
                report['reported_model_calls'] = trace.get('model_calls', 0)
                require(trace.get('status') == 'validated', 'Model plan failed validation; no second turn requested.')
                plan = validate_plan(trace['plan'], graph)
                required = {'action': 'query', 'tool': 'protein_neighborhood', 'disease_id': graph['disease_node_id'],
                            'protein_id': expected['plan']['protein']['id'], 'profile_id': None, 'therapy': None,
                            'relations': ['shared_pathways'], 'view': 'candidates', 'reason': 'Smoke scope.'}
                require(semantic_plan(plan) == semantic_plan(required), 'Model chose a different scope than the smoke question.')
                require(trace.get('model_calls') == 1 and trace.get('planner_kind') in {'live_model', 'live_nim', 'live_codex_cli'}
                        and result.get('tool_calls') == 1 and result.get('status') == 'answered',
                        'Expected one reported live model turn and one bounded local query.')
                verify_answer(result['answer'])
                require(result['answer']['answer_sha256'] == answer['answer_sha256'],
                        'Model execution differs from the equivalent deterministic query.')
                write_json(out / 'planner_trace.json', trace)
                report.update(planner_kind=trace['planner_kind'], model_requested=trace['model_requested'],
                              model_returned=trace.get('model_returned'), plan_id=result.get('plan_id'),
                              model_identity_basis='Service-reported metadata; no independent serving attestation.')
                passed()
            phase = 'source_unchanged'
            reopened = client.json('/api/run/' + source_id)['graph']
            require(graph_basis(reopened) == report['graph_basis_sha256'], 'Question execution changed the source.'); passed()
        report['status'] = 'passed'
    except (SmokeFailure, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Never save arbitrary response bodies or exception text from a proxy/model.
        report['status'] = 'failed'
        report['checks'].append({'check': phase, 'status': 'failed',
                                 'reason': str(exc) if isinstance(exc, SmokeFailure) else 'Invalid deployment response or source binding.'})
    report['receipt_sha256'] = digest(report)
    write_json(out / 'report.json', report)
    return report
