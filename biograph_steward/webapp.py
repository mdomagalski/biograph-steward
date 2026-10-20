"""Standard-library HTTP interface; loopback by default, explicit protected hosting."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
import socket
from urllib.parse import parse_qs, urlparse, urlsplit
from uuid import uuid4
import webbrowser
import zipfile
from datetime import datetime, timezone

from .client import PharosClient, ENDPOINT, PharosError
from .runtime import AccessPolicy, BrowserSessions, runs_directory, cache_directory
from . import __version__


def report_html(graph: dict | None = None, *, protected=False) -> str:
    template = Path(__file__).with_name("ui.html").read_text(encoding="utf-8")
    data = json.dumps(graph, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    script = Path(__file__).with_name("guided.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("civic.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("planner.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("quality.js").read_text(encoding="utf-8")
    auth = '<form method="post" action="/auth/logout"><button type="submit">Sign out</button></form>' if protected else ''
    return template.replace("__AUTH_CONTROL__", auth).replace("__GUIDED_SCRIPT__", script).replace("__EMBEDDED_GRAPH__", data)


def login_return_path(value):
    """Preserve saved root/report links, never redirect to another site or API action."""
    if (not isinstance(value, str) or len(value) > 2048 or value.startswith('//') or '\\' in value
            or any(ord(c) < 32 or ord(c) > 126 for c in value)):
        return '/'
    try:
        parsed = urlsplit(value)
        report = re.fullmatch(r'/api/evaluation/[A-Za-z0-9_-]{1,80}/(?:report\.html)?', parsed.path)
        if (parsed.scheme or parsed.netloc or parsed.fragment or not value.startswith('/') or
                not (parsed.path == '/' or (report and not parsed.query))):
            return '/'
    except ValueError:
        return '/'
    return value


def create_server(port: int, runs_dir: Path, endpoint: str = ENDPOINT,
                  cache_dir: Path | None = None, timeout: float = 30, *, host='127.0.0.1',
                  allowed_origins=(), access_token=None) -> ThreadingHTTPServer:
    policy = AccessPolicy(host, allowed_origins, access_token)
    sessions = BrowserSessions()
    runs_dir = Path(runs_dir).resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def authenticated(self):
            return (policy.authenticated(self.headers.get('Authorization'))
                    or sessions.authenticated(self.headers.get('Cookie')))

        def authenticate(self):
            if self.authenticated():
                return True
            # Native Basic challenges fail in some embedded browsers. Explicit
            # Basic/Bearer API headers still work; browser users use the form.
            self.json_reply({'error': 'Sign in to the workspace to continue.'}, 401)
            return False

        def login_page(self, return_to='/', *, failed=False):
            html = Path(__file__).with_name('login.html').read_text(encoding='utf-8')
            error = '<p class="error" role="alert">Access token was not recognized. Try again.</p>' if failed else ''
            html = html.replace('__RETURN_TO__', escape(login_return_path(return_to), quote=True)).replace('__ERROR__', error)
            self.reply(html.encode(), 403 if failed else 200, 'text/html; charset=utf-8')

        def auth_form(self, path):
            origin = self.headers.get('Origin')
            if not origin or not policy.allows_origin(origin, self.server.server_port):
                self.json_reply({'error': 'Browser origin is not explicitly allowed.'}, 403)
                return
            secure = urlsplit(origin).scheme == 'https'
            if path == '/auth/logout':
                if not self.authenticate():
                    return
                sessions.revoke(self.headers.get('Cookie'))
                self.redirect('/', sessions.cookie_header(secure=secure))
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                self.json_reply({'error': 'Use the workspace sign-in form.'}, 415)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 8192:
                    raise ValueError
                fields = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True, max_num_fields=2)
                if set(fields) != {'token', 'return_to'} or any(len(v) != 1 for v in fields.values()):
                    raise ValueError
            except (ValueError, UnicodeError):
                self.json_reply({'error': 'Invalid sign-in form.'}, 400)
                return
            return_to = login_return_path(fields['return_to'][0])
            if not policy.authenticated('Bearer ' + fields['token'][0]):
                self.login_page(return_to, failed=True)
                return
            sessions.revoke(self.headers.get('Cookie'))
            self.redirect(return_to, sessions.cookie_header(sessions.issue(), secure=secure))

        def redirect(self, location, cookie):
            self.send_response(303)
            self.send_header('Location', location)
            self.send_header('Set-Cookie', cookie)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', '0')
            self.end_headers()

        def reply(self, payload: bytes, status: int = 200, content_type: str = "application/json", filename: str | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            # no-referrer turns native form POST origins into "null" in browsers,
            # defeating our explicit Origin check. Keep same-origin form context
            # while suppressing referrers entirely for external destinations.
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('X-Frame-Options', 'DENY')
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)

        def json_reply(self, obj: dict, status: int = 200):
            self.reply(json.dumps(obj, ensure_ascii=True, allow_nan=False).encode(), status)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/healthz':
                self.json_reply({'status': 'ok', 'version': __version__})
                return
            if path == '/auth/login':
                try:
                    fields = parse_qs(urlparse(self.path).query, max_num_fields=1)
                    return_to = fields.get('return_to', ['/'])[0]
                except ValueError:
                    return_to = '/'
                self.login_page(return_to)
                return
            report_navigation = (re.fullmatch(r'/api/evaluation/[A-Za-z0-9_-]{1,80}/(?:report\.html)?', path)
                                 and 'text/html' in self.headers.get('Accept', '').lower())
            if (path == '/' or report_navigation) and not self.authenticated():
                self.login_page(self.path)
                return
            if not self.authenticate():
                return
            if path == '/api/evidence-quality':
                from .evidence_quality import POLICY, verify_quality_result, quality_passports
                from .context_evaluation import POLICY as CONTEXT_POLICY, verify_context_result
                from .reviews import read_run
                try:
                    fields = parse_qs(urlparse(self.path).query, max_num_fields=2)
                    if set(fields) - {'run', 'assertion'} or any(len(v) != 1 for v in fields.values()):
                        raise ValueError('Invalid evidence-quality scope.')
                    graph = None
                    if fields:
                        if set(fields) != {'run', 'assertion'} or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', fields['run'][0]):
                            raise ValueError('Supply an exact run and assertion.')
                        folder = (runs_dir / fields['run'][0]).resolve()
                        if folder.parent != runs_dir:
                            raise ValueError('Invalid source run.')
                        graph = read_run(folder)[2]
                    reports = []; passports = []; invalid = 0
                    for folder in sorted(runs_dir.iterdir()):
                        if (not folder.is_dir() or folder.is_symlink() or
                                not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', folder.name) or
                                not (folder / 'metrics.json').is_file()):
                            continue
                        try:
                            m = json.loads((folder / 'metrics.json').read_text())
                            if m.get('format') not in {POLICY + '.result', CONTEXT_POLICY + '.result'}:
                                continue
                            is_context = m['format'] == CONTEXT_POLICY + '.result'
                            m = verify_context_result(folder) if is_context else verify_quality_result(folder)
                            reports.append({'name': folder.name, 'cases': m['cases'],
                                'model_requests': m['model_requests'], 'result_sha256': m['result_sha256'],
                                'report_url': '/api/evaluation/' + folder.name + '/',
                                'download_url': '/api/download/' + folder.name})
                            if graph is not None and not is_context:
                                passports.extend({'report_name': folder.name, **v} for v in
                                    quality_passports(folder, graph, fields['assertion'][0]))
                        except (ValueError, TypeError, KeyError, OSError):
                            invalid += 1
                    self.json_reply({'reports': reports, 'passports': passports,
                                     'invalid_reports_withheld': invalid, 'graph_mutations': 0})
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    self.json_reply({'error': str(exc)}, 400)
                return
            match=re.fullmatch(r"/api/evaluation/([A-Za-z0-9_-]{1,80})/(report\.html|case_reviews\.tsv|answer_reviews\.tsv|evidence_reviews\.tsv|metrics\.json)?",path)
            if match:
                folder=(runs_dir/match.group(1)).resolve();name=match.group(2) or 'report.html'
                if folder.parent!=runs_dir or not (folder/'metrics.json').is_file() or not (folder/name).is_file() or (folder/name).is_symlink():
                    self.json_reply({'error':'Evaluation artifact not found'},404);return
                try:
                    if json.loads((folder/'metrics.json').read_text()).get('format') == 'crc-source-consistency.v1.result':
                        from .evidence_quality import verify_quality_result
                        verify_quality_result(folder)
                    elif json.loads((folder/'metrics.json').read_text()).get('format') == 'context-comparison.v1.result':
                        from .context_evaluation import verify_context_result
                        verify_context_result(folder)
                except (ValueError, TypeError, KeyError, OSError):
                    self.json_reply({'error':'Evidence-quality artifact failed integrity checks.'},400);return
                content_type='text/html; charset=utf-8' if name=='report.html' else 'application/json' if name.endswith('.json') else 'text/tab-separated-values; charset=utf-8'
                self.reply((folder/name).read_bytes(),content_type=content_type,filename=name if name.endswith('.tsv') else None)
                return
            if path=='/api/planner':
                from .planning import configured_planner,PlannerUnavailable
                try:
                    planner=configured_planner();self.json_reply({'configured':True,'model':planner.model,'endpoint':planner.endpoint,'api':planner.api})
                except (ValueError,TypeError) as exc:self.json_reply({'configured':False,'reason':str(exc)})
                return
            if path == "/":
                self.reply(report_html(protected=policy.token is not None).encode(), content_type="text/html; charset=utf-8")
                return
            if path == "/health":
                self.json_reply({"status": "local_server_running", "live_pharos_checked": False})
                return
            match = re.fullmatch(r"/api/run/([A-Za-z0-9_-]{1,80})", path)
            if match:
                from .reviews import read_run
                folder = (runs_dir / match.group(1)).resolve()
                if folder.parent != runs_dir or not folder.is_dir():
                    self.json_reply({"error": "Run not found"}, 404)
                    return
                try:
                    _, _, graph = read_run(folder)
                    self.json_reply({"run_id": match.group(1), "graph": graph})
                except (ValueError, TypeError, OSError) as exc:
                    self.json_reply({"error": str(exc)}, 400)
                return
            match = re.fullmatch(r"/api/question/([A-Za-z0-9_-]{1,80})", path)
            if match:
                from .questions import verify_answer
                folder = (runs_dir / match.group(1)).resolve()
                if folder.parent != runs_dir or not (folder / "question.json").is_file():
                    self.json_reply({"error": "Question result not found"}, 404)
                    return
                try:
                    answer = json.loads((folder / "question.json").read_text(encoding="utf-8"))
                    verify_answer(answer)
                    self.json_reply({"question_id": match.group(1), "answer": answer})
                except (ValueError, TypeError, OSError) as exc:
                    self.json_reply({"error": str(exc)}, 400)
                return
            match = re.fullmatch(r"/api/download/([A-Za-z0-9_-]{1,80})", path)
            if match:
                folder = (runs_dir / match.group(1)).resolve()
                if not folder.is_dir() or folder.parent != runs_dir:
                    self.json_reply({"error": "Run not found"}, 404)
                    return
                if (folder / 'metrics.json').is_file():
                    try:
                        if json.loads((folder / 'metrics.json').read_text()).get('format') == 'crc-source-consistency.v1.result':
                            from .evidence_quality import verify_quality_result
                            verify_quality_result(folder)
                        elif json.loads((folder / 'metrics.json').read_text()).get('format') == 'context-comparison.v1.result':
                            from .context_evaluation import verify_context_result
                            verify_context_result(folder)
                    except (ValueError, TypeError, KeyError, OSError):
                        self.json_reply({'error': 'Evidence-quality artifact failed integrity checks.'}, 400)
                        return
                buffer = BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                    for file in sorted(folder.rglob("*")):
                        if file.is_file() and not file.is_symlink():
                            archive.write(file, str(Path(folder.name) / file.relative_to(folder)))
                self.reply(buffer.getvalue(), content_type="application/zip", filename=folder.name + ".zip")
                return
            self.json_reply({"error": "Not found"}, 404)

        def do_POST(self):
            path = urlparse(self.path).path
            if path in {'/auth/login', '/auth/logout'}:
                self.auth_form(path)
                return
            if not self.authenticate():
                return
            origin = self.headers.get("Origin")
            cookie_auth = policy.token is not None and not policy.authenticated(self.headers.get('Authorization'))
            if (cookie_auth and not origin) or not policy.allows_origin(origin, self.server.server_port):
                self.json_reply({"error": "Browser origin is not explicitly allowed."}, 403)
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.json_reply({"error": "Use application/json."}, 415)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 65536:
                    raise ValueError("Request must contain 1-65536 bytes of JSON.")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Expected a JSON object.")
                path = urlparse(self.path).path
                if path=='/api/plan':
                    from .planning import configured_planner,execute_plan
                    from .reviews import read_run
                    from .client import write_json
                    from .questions import save_answer
                    if set(body)!={'run_id','question'}:raise ValueError('Use only run_id and question for one bounded plan.')
                    source_id=body.get('run_id','')
                    if not isinstance(source_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',source_id):raise ValueError('Invalid source run ID.')
                    source=(runs_dir/source_id).resolve()
                    if source.parent!=runs_dir or not source.is_dir():raise ValueError('Source run not found.')
                    _,_,graph=read_run(source);planner=configured_planner();trace=planner.plan(body.get('question'),graph)
                    qid='plan_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid4().hex[:8]
                    folder=runs_dir/qid;folder.mkdir();write_json(folder/'planner_trace.json',trace)
                    if trace['status']!='validated':
                        self.json_reply({'plan_id':qid,'status':'invalid_plan','reason':trace.get('error'),'trace':trace,'answer':None});return
                    result=execute_plan(trace['plan'],graph,source_run=source_id)
                    write_json(folder/'execution.json',{k:v for k,v in result.items() if k!='answer'})
                    if result['answer']:save_answer(result['answer'],folder/'answer')
                    self.json_reply({'plan_id':qid,'trace':trace,**result});return
                if path == "/api/search":
                    client = PharosClient(endpoint, cache_dir=cache_dir, timeout=timeout)
                    self.json_reply(client.search(body.get("term", "")))
                    return
                if path == "/api/question":
                    from .questions import answer_question, save_answer
                    from .reviews import read_run
                    allowed = {"run_id", "protein", "relations", "view", "max_results", "max_paths", "template"}
                    if set(body) - allowed:
                        raise ValueError("Unsupported question fields; use the guided protein-neighborhood scope.")
                    source_id = body.get("run_id", "")
                    if not isinstance(source_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source_id):
                        raise ValueError("Invalid source run ID.")
                    source = (runs_dir / source_id).resolve()
                    if source.parent != runs_dir or not source.is_dir():
                        raise ValueError("Source run not found.")
                    _, _, graph = read_run(source)
                    options = {k: v for k, v in body.items() if k not in {"run_id", "protein"}}
                    answer = answer_question(graph, body.get("protein"), source_run=source_id, **options)
                    question_id = "question_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
                    save_answer(answer, runs_dir / question_id)
                    self.json_reply({"question_id": question_id, "answer": answer})
                    return
                if path in {"/api/civic", "/api/therapy-question"}:
                    from .reviews import read_run
                    from .civic import CivicClient
                    from .graph import save_run
                    from .civic_questions import answer_civic_question
                    from .questions import save_answer
                    allowed = {"run_id","max_items"} if path == "/api/civic" else {"run_id","profile","therapy","view","max_results","max_paths"}
                    if set(body) - allowed:
                        raise ValueError("Unsupported CIViC scope fields. Use the guided KRAS/DOID:9256 workflow.")
                    source_id=body.get("run_id", "")
                    if not isinstance(source_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",source_id):
                        raise ValueError("Invalid source run ID.")
                    source=(runs_dir/source_id).resolve()
                    if source.parent != runs_dir or not source.is_dir():
                        raise ValueError("Source run not found.")
                    snapshot, events, graph = read_run(source)
                    if path == "/api/civic":
                        if graph.get("civic"):
                            raise ValueError("This run already includes CIViC. Reopen its saved evidence; source refresh reconciliation is not implemented.")
                        if graph["data_kind"] == "synthetic_demo":
                            raise ValueError("Live CIViC cannot be mixed with a synthetic Pharos source.")
                        if not any(t["id"] == "UniProtKB:P01116" for t in graph["targets"]):
                            raise ValueError("This cohort does not contain the supported KRAS protein UniProtKB:P01116.")
                        civic=CivicClient(timeout=timeout).retrieve(body.get("max_items",100))
                        run_id="civic_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid4().hex[:8]
                        result=save_run(snapshot,runs_dir/run_id,run_mode="civic_enrichment",review_events=events,civic_snapshot=civic)
                        self.json_reply({"run_id":run_id,"graph":result})
                    else:
                        answer=answer_civic_question(graph,source_run=source_id,**{k:v for k,v in body.items() if k != "run_id"})
                        qid="therapy_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid4().hex[:8]
                        save_answer(answer,runs_dir/qid)
                        self.json_reply({"question_id":qid,"answer":answer})
                    return
                if path == "/api/review":
                    from .reviews import review_run
                    source_id = body.get("run_id", "")
                    if not isinstance(source_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source_id):
                        raise ValueError("Invalid source run ID.")
                    source = (runs_dir / source_id).resolve()
                    if source.parent != runs_dir or not source.is_dir():
                        raise ValueError("Source run not found.")
                    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
                    graph = review_run(source, runs_dir / run_id, body.get("assertion_id"),
                                       body.get("state"), body.get("reviewer"), body.get("reason"))
                    self.json_reply({"run_id": run_id, "graph": graph})
                    return
                if path != "/api/build":
                    self.json_reply({"error": "Not found"}, 404)
                    return
                from .demo import demo_snapshot
                from .graph import save_run
                if body.get("mode") == "demo":
                    snapshot = demo_snapshot()
                elif body.get("mode") == "live":
                    client = PharosClient(endpoint, cache_dir=cache_dir, timeout=timeout,
                                          refresh=bool(body.get("refresh", False)))
                    snapshot = client.build_snapshot(
                        disease=body.get("disease", ""), max_targets=int(body.get("max_targets", 25)),
                        pathway_top=int(body.get("pathway_top", 5)), check_schema=bool(body.get("check_schema", True)),
                        profile=body.get("profile", "preview"), tissue_term=body.get("tissue_term", ""))
                else:
                    raise ValueError("Choose 'demo' or 'live' explicitly.")
                run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
                graph = save_run(snapshot, runs_dir / run_id)
                self.json_reply({"run_id": run_id, "graph": graph})
            except (ValueError, TypeError, PharosError, OSError) as exc:
                self.json_reply({"error": str(exc)}, 400)

    if ':' in host:
        class IPv6Server(ThreadingHTTPServer):
            address_family = socket.AF_INET6
        return IPv6Server((host, port), Handler)
    return ThreadingHTTPServer((host, port), Handler)


def serve(port: int = 8765, runs_dir: Path | None = None, endpoint: str = ENDPOINT,
          cache_dir: Path | None = None, open_browser: bool = True,
          timeout: float = 30, *, host='127.0.0.1', allowed_origins=(), access_token=None):
    runs_dir = runs_directory() if runs_dir is None else runs_dir
    cache_dir = cache_directory() if cache_dir is None else cache_dir
    server = create_server(port, runs_dir, endpoint, cache_dir, timeout, host=host,
                           allowed_origins=allowed_origins, access_token=access_token)
    address = f'[{host}]' if ':' in host else host
    url = f"http://{address}:{server.server_port}"
    print(f"BioGraph Steward: {url}\nRuns: {Path(runs_dir).resolve()}\nCtrl+C stops it.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
