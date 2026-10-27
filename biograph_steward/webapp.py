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


def verify_saved_refresh(folder: Path) -> None:
    """A missing receipt must not turn an incomplete refresh into an ordinary run."""
    markers = ('refresh_receipt.json', 'refresh_comparison.json', 'refresh_report.html', 'refresh_inputs')
    required = any((folder / name).exists() or (folder / name).is_symlink() for name in markers)
    manifest_file = folder / 'run_manifest.json'
    if manifest_file.is_file():
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        required = required or isinstance(manifest, dict) and manifest.get('run_mode') == 'refresh'
    if required:
        from .refresh_workflow import verify_refresh
        verify_refresh(folder)


def verify_qualified_question_source(answer, runs_dir):
    """A saved qualified answer cannot outlive changed or missing source bytes."""
    if answer.get('template') != 'qualified_assay_evidence.v1':
        return
    from .reviews import read_run
    from .questions import graph_basis
    source_id = answer.get('source_run')
    if not isinstance(source_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', source_id):
        raise ValueError('Qualified answer source run is missing or invalid.')
    source = Path(runs_dir) / source_id
    if source.is_symlink() or source.resolve().parent != Path(runs_dir).resolve() or not source.is_dir():
        raise ValueError('Qualified answer source run is unavailable.')
    graph = read_run(source)[2]
    if (answer.get('graph_basis_sha256') != graph_basis(graph)
            or any(answer.get(key) != graph.get(key) for key in
                   ('snapshot_sha256', 'assay_attachment_sha256', 'assay_publication_sha256'))):
        raise ValueError('Qualified answer belongs to different source evidence or review state.')


def report_html(graph: dict | None = None, *, protected=False) -> str:
    template = Path(__file__).with_name("ui.html").read_text(encoding="utf-8")
    data = json.dumps(graph, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    script = Path(__file__).with_name("guided.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("civic.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("planner.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("refresh.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("workspaces.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("construction.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("assay.js").read_text(encoding="utf-8")
    auth = '<form method="post" action="/auth/logout"><button type="submit">Sign out</button></form>' if protected else ''
    return template.replace("__AUTH_CONTROL__", auth).replace("__GUIDED_SCRIPT__", script).replace("__EMBEDDED_GRAPH__", data)


def login_return_path(value):
    """Preserve saved root/report links, never redirect to another site or API action."""
    if (not isinstance(value, str) or len(value) > 2048 or value.startswith('//') or '\\' in value
            or any(ord(c) < 32 or ord(c) > 126 for c in value)):
        return '/'
    try:
        parsed = urlsplit(value)
        report = re.fullmatch(r'/api/(?:refresh|refresh-archive)/[A-Za-z0-9_-]{1,80}/(?:report\.html)?', parsed.path)
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

        def reply(self, payload: bytes, status: int = 200, content_type: str = "application/json", filename: str | None = None, *, content_security_policy: str | None = None):
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
            if content_security_policy:
                self.send_header("Content-Security-Policy", content_security_policy)
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)

        def json_reply(self, obj: dict, status: int = 200):
            self.reply(json.dumps(obj, ensure_ascii=True, allow_nan=False).encode(), status)

        def refresh_failure(self, folder, exc):
            from .refresh_archive import archive_id
            from .refresh_workflow import RefreshRuntimeMismatch
            if isinstance(exc, RefreshRuntimeMismatch):
                identifier = archive_id(folder.relative_to(runs_dir).as_posix())
                self.json_reply({'error': str(exc), 'error_code': 'refresh_runtime_mismatch',
                                 'saved_files_integrity': 'passed', 'current_replay': 'not_performed',
                                 'archive_url': '/api/refresh-archive/' + identifier + '/'}, 409)
            else:
                self.json_reply({'error': 'Snapshot comparison failed saved-file integrity or replay checks.',
                                 'error_code': 'refresh_verification_failed'}, 400)

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
            report_navigation = (re.fullmatch(r'/api/(?:refresh|refresh-archive)/[A-Za-z0-9_-]{1,80}/(?:report\.html)?', path)
                                 and 'text/html' in self.headers.get('Accept', '').lower())
            if (path == '/' or report_navigation) and not self.authenticated():
                self.login_page(self.path)
                return
            if not self.authenticate():
                return
            if path == '/api/workspaces':
                from .workspaces import saved_workspaces
                self.json_reply(saved_workspaces(runs_dir))
                return
            if path == '/api/assay-publications':
                from .client import digest
                publications = []
                for folder in sorted(runs_dir.iterdir()):
                    if (folder.is_symlink() or not folder.is_dir()
                            or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', folder.name)):
                        continue
                    receipt = folder / 'publication.json'
                    if receipt.is_symlink() or not receipt.is_file():
                        continue
                    try:
                        manifest = json.loads(receipt.read_text(encoding='utf-8'))
                        if (manifest.get('format') not in {'biograph-steward.lambourne-evidence-publication.v1',
                                                         'biograph-steward.intact-evidence-publication.v1'}
                                or manifest.get('content_sha256') != digest({k: v for k, v in manifest.items()
                                                                            if k != 'content_sha256'})):
                            continue
                        publications.append({'publication_id': folder.name,
                                             'publication_sha256': manifest['content_sha256']})
                    except (ValueError, TypeError, AttributeError, OSError):
                        continue
                self.json_reply({'publications': publications,
                                 'verification': 'Receipt metadata only; full verification occurs on attachment.'})
                return
            match = re.fullmatch(r'/api/assay-source/([A-Za-z0-9_-]{1,80})/(.+)', path)
            if match:
                from .reviews import read_run
                folder = runs_dir / match.group(1)
                relative = Path(match.group(2))
                try:
                    if (folder.is_symlink() or not folder.is_dir() or relative.is_absolute()
                            or not re.fullmatch(r'[A-Za-z0-9_./-]+', match.group(2))
                            or any(part in {'.', '..'} for part in match.group(2).split('/'))):
                        raise ValueError('Invalid assay source path.')
                    _, _, graph = read_run(folder)
                    if not graph.get('assay_evidence'):
                        raise ValueError('This run has no attached assay publication.')
                    source = folder / 'assay_source'
                    manifest = json.loads((source / 'publication.json').read_text(encoding='utf-8'))
                    if relative.as_posix() not in {'publication.json', *manifest['files']}:
                        raise ValueError('File is outside the attached publication.')
                    file = source / relative
                    if file.is_symlink() or not file.is_file() or source.resolve() not in file.resolve().parents:
                        raise ValueError('Assay source is not a regular published file.')
                    # Source files are data, never active same-origin HTML or scripts.
                    self.reply(file.read_bytes(), content_type='application/json' if file.suffix == '.json'
                               else 'text/plain; charset=utf-8', filename=file.name)
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    self.json_reply({'error': str(exc)}, 400)
                return
            if path == '/api/refresh-history':
                from .refresh_archive import list_archives
                self.json_reply(list_archives(runs_dir))
                return
            match = re.fullmatch(r'/api/refresh-archive/([0-9a-f]{64})/(report\.html|comparison\.json|refresh_comparison\.json|graph\.json|review_events\.json|refresh_receipt\.json|refresh_inputs/(?:before|after)/(?:snapshot|graph|review_events|run_manifest|civic_snapshot)\.json)?', path)
            if match:
                from .refresh_archive import archived_report, find_archive
                from .refresh_workflow import verify_refresh_files
                folder = find_archive(runs_dir, match.group(1))
                if folder is None:
                    self.json_reply({'error': 'Comparison archive not found.'}, 404); return
                try:
                    receipt = verify_refresh_files(folder)
                    name = match.group(2) or 'report.html'
                    if name == 'report.html':
                        self.reply(archived_report(folder, receipt).encode(), content_type='text/html; charset=utf-8',
                                   content_security_policy="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'")
                    else:
                        name = {'comparison.json': 'refresh_comparison.json'}.get(name, name)
                        if name != 'refresh_receipt.json' and name not in receipt['files']:
                            self.json_reply({'error': 'Archived file not found.'}, 404); return
                        self.reply((folder / name).read_bytes(), content_type='application/json')
                except (ValueError, TypeError, KeyError, OSError):
                    self.json_reply({'error': 'Comparison archive failed saved-file integrity checks; contents withheld.',
                                     'error_code': 'refresh_archive_integrity_failed'}, 400)
                return
            if path == '/api/refresh-runs':
                choices = []
                for folder in sorted(runs_dir.iterdir(), key=lambda p: p.name, reverse=True):
                    if (folder.is_symlink() or not folder.is_dir() or
                            not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', folder.name)):
                        continue
                    try:
                        if any((folder / name).is_symlink() for name in ('run_manifest.json', 'snapshot.json', 'graph.json')):
                            continue
                        manifest = json.loads((folder / 'run_manifest.json').read_text(encoding='utf-8'))
                        if (not isinstance(manifest, dict) or not (folder / 'snapshot.json').is_file() or
                                manifest.get('data_kind') not in {'live_pharos', 'synthetic_demo'} or
                                manifest.get('run_mode') == 'refresh' or
                                not isinstance(manifest.get('graph_format'), str) or
                                type(manifest.get('review_event_count')) is not int or manifest['review_event_count'] < 0 or
                                not isinstance(manifest.get('created_at'), str)):
                            continue
                        verify_saved_refresh(folder)
                        choices.append({'run_id': folder.name, 'data_kind': manifest['data_kind'],
                                        'created_at': manifest.get('created_at'),
                                        'reviews': manifest.get('review_event_count', 0)})
                    except (ValueError, TypeError, KeyError, OSError):
                        continue
                self.json_reply({'runs': choices, 'note': 'Selection metadata only; comparison verifies the saved inputs.'})
                return
            match = re.fullmatch(r'/api/refresh/([A-Za-z0-9_-]{1,80})/(report\.html|comparison\.json|refresh_comparison\.json|graph\.json|review_events\.json|refresh_receipt\.json|refresh_inputs/(?:before|after)/(?:snapshot|graph|review_events|run_manifest|civic_snapshot)\.json)?', path)
            if match:
                from .refresh_workflow import verify_refresh
                folder = runs_dir / match.group(1)
                if folder.is_symlink() or folder.resolve().parent != runs_dir or not folder.is_dir():
                    self.json_reply({'error': 'Snapshot comparison not found.'}, 404); return
                try:
                    verify_refresh(folder)
                    name = match.group(2) or 'refresh_report.html'
                    name = {'comparison.json':'refresh_comparison.json', 'report.html':'refresh_report.html'}.get(name, name)
                    self.reply((folder / name).read_bytes(), content_type=(
                        'application/json' if name.endswith('.json') else 'text/html; charset=utf-8'))
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    self.refresh_failure(folder, exc)
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
                from .refresh_workflow import RefreshRuntimeMismatch
                try:
                    verify_saved_refresh(folder)
                    _, _, graph = read_run(folder)
                    self.json_reply({"run_id": match.group(1), "graph": graph})
                except RefreshRuntimeMismatch as exc:
                    self.refresh_failure(folder, exc)
                except (ValueError, TypeError, OSError) as exc:
                    self.json_reply({"error": str(exc)}, 400)
                return
            match = re.fullmatch(r"/api/question/([A-Za-z0-9_-]{1,80})", path)
            if match:
                from .questions import verify_answer
                from .reviews import read_run
                if (runs_dir / match.group(1)).is_symlink():
                    self.json_reply({"error": "Question result not found"}, 404)
                    return
                folder = (runs_dir / match.group(1)).resolve()
                if folder.parent != runs_dir or not (folder / "question.json").is_file():
                    self.json_reply({"error": "Question result not found"}, 404)
                    return
                try:
                    answer = json.loads((folder / "question.json").read_text(encoding="utf-8"))
                    verify_answer(answer)
                    verify_qualified_question_source(answer, runs_dir)
                    if answer.get('source_run') == folder.name:
                        # Construction publishes the graph and initial answer in
                        # one immutable run. Its receipt must be checked even if
                        # the question alone has a valid content hash.
                        read_run(folder)
                    self.json_reply({"question_id": match.group(1), "answer": answer})
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    self.json_reply({"error": str(exc)}, 400)
                return
            match = re.fullmatch(r"/api/download/([A-Za-z0-9_-]{1,80})", path)
            if match:
                if (runs_dir / match.group(1)).is_symlink():
                    self.json_reply({'error': 'Run not found'}, 404); return
                folder = (runs_dir / match.group(1)).resolve()
                if not folder.is_dir() or folder.parent != runs_dir:
                    self.json_reply({"error": "Run not found"}, 404)
                    return
                try:
                    verify_saved_refresh(folder)
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    self.refresh_failure(folder, exc)
                    return
                # Only current product artifacts are downloadable. Historical
                # studies require their archived implementation and integrity checks.
                try:
                    if any((folder / name).exists() or (folder / name).is_symlink()
                           for name in ('source_fact_manifest.json', 'biomedbert_manifest.json', 'metrics.json')):
                        raise ValueError('Historical study artifacts are available through the research archive.')
                    if (folder / 'run_manifest.json').is_file():
                        from .reviews import read_run
                        read_run(folder)
                    elif (folder / 'question.json').is_file():
                        from .questions import verify_answer
                        answer = json.loads((folder / 'question.json').read_text(encoding='utf-8'))
                        verify_answer(answer)
                        verify_qualified_question_source(answer, runs_dir)
                        if answer.get('source_run') == folder.name:
                            from .reviews import read_run
                            read_run(folder)
                    elif (folder / 'retained_graph.json').is_file():
                        from .gold_packet import load_decisions
                        load_decisions(folder)
                    elif (folder / 'construction_planner_trace.json').is_file():
                        from .construction_planning import verify_construction_plan_trace
                        verify_construction_plan_trace(json.loads(
                            (folder / 'construction_planner_trace.json').read_text(encoding='utf-8')))
                    elif (folder / 'planner_trace.json').is_file():
                        trace = json.loads((folder / 'planner_trace.json').read_text(encoding='utf-8'))
                        if not isinstance(trace, dict) or trace.get('status') not in {'validated', 'invalid_plan', 'planner_error'}:
                            raise ValueError('Unsupported planner trace.')
                        answer_file = folder / 'answer' / 'question.json'
                        if answer_file.is_file():
                            from .questions import verify_answer
                            verify_answer(json.loads(answer_file.read_text(encoding='utf-8')))
                    else:
                        raise ValueError('This is not a current graph, question or planner artifact.')
                    if any(file.is_symlink() for file in folder.rglob('*')):
                        raise ValueError('Artifact exports must not contain symbolic links.')
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    self.json_reply({'error': str(exc)}, 400)
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
                if path == '/api/construction-plan':
                    from .construction_planning import (validate_construction_scope,
                        configured_construction_planner, save_construction_plan)
                    from .guided_construction import validate_guided_selection, guard_construction_trace
                    if set(body) != {'question', 'accessions', 'focus_uniprot', 'exact_selection'}:
                        raise ValueError('Supply the cohort question and its complete explicit selection.')
                    scope = validate_construction_scope({key: body[key] for key in
                                                        ('question', 'accessions', 'focus_uniprot')})
                    selection = validate_guided_selection(scope, body['exact_selection'])
                    model_trace = configured_construction_planner().plan(scope)
                    if model_trace.get('scope') != scope:
                        raise ValueError('The returned plan differs from the supplied question or cohort.')
                    trace = guard_construction_trace(model_trace, selection)
                    plan_id = 'construction_plan_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
                    save_construction_plan(trace, runs_dir / plan_id / 'construction_planner_trace.json')
                    self.json_reply({'plan_id': plan_id, 'trace': trace})
                    return
                if path == '/api/submission-export':
                    from .gold_packet import export_packet, save_decisions, load_decisions
                    import tempfile
                    import shutil
                    if set(body) != {'run_id'}:
                        raise ValueError('Use a saved run_id to export the graph and unassessed decisions.')
                    source_id = body['run_id']
                    if not isinstance(source_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', source_id):
                        raise ValueError('Invalid source run ID.')
                    source = runs_dir / source_id
                    if source.is_symlink() or not source.is_dir() or source.resolve().parent != runs_dir:
                        raise ValueError('Saved source run not found.')
                    run_id = 'submission_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
                    stage = Path(tempfile.mkdtemp(prefix='.submission-', dir=runs_dir))
                    try:
                        packet = stage / 'packet'
                        export_packet(source, packet)
                        save_decisions(packet, packet / 'decisions.template.json', runs_dir / run_id)
                        report, _ = load_decisions(runs_dir / run_id)
                    finally:
                        shutil.rmtree(stage)
                    self.json_reply({'run_id': run_id, 'report': report,
                                     'download_url': '/api/download/' + run_id})
                    return
                if path == '/api/assay-attach':
                    from .assay_attachment import attach_assay
                    if set(body) != {'run_id', 'publication_id'}:
                        raise ValueError('Use only run_id and publication_id for a saved assay attachment.')
                    sources = []
                    for key in ('run_id', 'publication_id'):
                        value = body[key]
                        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value):
                            raise ValueError('Invalid saved workspace identifier.')
                        folder = runs_dir / value
                        if folder.is_symlink() or not folder.is_dir() or folder.resolve().parent != runs_dir:
                            raise ValueError('Saved workspace source not found.')
                        sources.append(folder)
                    run_id = 'assay_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
                    graph = attach_assay(*sources, runs_dir / run_id)
                    self.json_reply({'run_id': run_id, 'graph': graph})
                    return
                if path == '/api/assay-question':
                    from .assay_questions import answer_assay_question
                    from .questions import save_answer
                    from .reviews import read_run
                    if set(body) - {'run_id', 'protein'}:
                        raise ValueError('Use only run_id and an optional exact protein for qualified evidence.')
                    source_id = body.get('run_id', '')
                    if not isinstance(source_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', source_id):
                        raise ValueError('Invalid source run ID.')
                    source = runs_dir / source_id
                    if source.is_symlink() or source.resolve().parent != runs_dir or not source.is_dir():
                        raise ValueError('Source run not found.')
                    answer = answer_assay_question(read_run(source)[2], body.get('protein'), source_run=source_id)
                    question_id = 'assay_question_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
                    save_answer(answer, runs_dir / question_id)
                    self.json_reply({'question_id': question_id, 'answer': answer})
                    return
                if path == '/api/refresh-compare':
                    from .refresh_workflow import run_refresh
                    if set(body) != {'before_run', 'after_run', 'carry_reviews'} or type(body['carry_reviews']) is not bool:
                        raise ValueError('Use before_run, after_run and a boolean carry_reviews.')
                    sources = []
                    for field in ('before_run', 'after_run'):
                        value = body[field]
                        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value):
                            raise ValueError('Invalid saved run ID.')
                        folder = runs_dir / value
                        if folder.is_symlink() or folder.resolve().parent != runs_dir or not folder.is_dir():
                            raise ValueError('Saved run not found.')
                        verify_saved_refresh(folder)
                        sources.append(folder)
                    run_id = 'refresh_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
                    result = run_refresh(*sources, runs_dir / run_id, carry_reviews=body['carry_reviews'])
                    self.json_reply({'run_id': run_id, 'graph': result['graph'],
                                     'comparison': result['comparison'],
                                     'report_url': '/api/refresh/' + run_id + '/',
                                     'download_url': '/api/download/' + run_id})
                    return
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
                    _,_,graph=read_run(source)
                    if graph.get('scope', {}).get('kind') == 'protein_cohort':
                        raise ValueError('Use the guided protein-cohort question. Model planning for construction cohorts is not supported.')
                    planner=configured_planner();trace=planner.plan(body.get('question'),graph)
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
                if path == '/api/construct':
                    from .construction import (demo_construction_snapshot, plan_construction,
                                               publish_construction, run_construction, run_planned_construction)
                    allowed = {'mode', 'accessions', 'focus_uniprot', 'profile', 'relations', 'refresh', 'plan_id',
                               'exact_selection', 'plan_reviewed'}
                    if set(body) - allowed:
                        raise ValueError('Unsupported construction fields. Use a bounded protein cohort, focus protein and retrieval profile.')
                    mode = body.get('mode', 'live')
                    if mode not in {'live', 'demo', 'planned'}:
                        raise ValueError("Choose 'demo', 'live' or 'planned' explicitly.")
                    if 'refresh' in body and type(body['refresh']) is not bool:
                        raise ValueError('refresh must be a boolean.')
                    if mode == 'demo':
                        if set(body) != {'mode'}:
                            raise ValueError('The synthetic construction example has a fixed cohort and scope. Use only mode: demo.')
                        snapshot = demo_construction_snapshot()
                    elif mode == 'planned':
                        from .construction_planning import verify_construction_plan_trace
                        from .guided_construction import (POLICY as GUIDED_POLICY,
                                                          validate_guided_selection)
                        if (set(body) - {'mode', 'plan_id', 'refresh', 'exact_selection', 'plan_reviewed'}
                                or not {'plan_id', 'exact_selection', 'plan_reviewed'} <= set(body)
                                or body['plan_reviewed'] is not True):
                            raise ValueError('Review the saved plan and supply its current explicit selection before building.')
                        plan_id = body['plan_id']
                        if not isinstance(plan_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', plan_id):
                            raise ValueError('Invalid saved construction plan ID.')
                        folder = runs_dir / plan_id
                        if folder.is_symlink() or not folder.is_dir() or folder.resolve().parent != runs_dir or any(p.is_symlink() for p in folder.rglob('*')):
                            raise ValueError('Saved construction plan not found.')
                        trace = json.loads((folder / 'construction_planner_trace.json').read_text(encoding='utf-8'))
                        if trace.get('format') != GUIDED_POLICY:
                            raise ValueError('Create a guided plan with explicit choices before building through this interface.')
                        if verify_construction_plan_trace(trace) is None:
                            raise ValueError('This plan abstained or failed; no source retrieval was performed.')
                        if validate_guided_selection(trace['scope'], body['exact_selection']) != trace['exact_selection']:
                            raise ValueError('The current choices differ from the saved plan. Plan and review again.')
                    else:
                        request = {key: value for key, value in body.items() if key not in {'mode', 'refresh'}}
                        # Validate every scope field before creating a transport
                        # or accessing the public source.
                        plan_construction(request)
                    run_id = 'construct_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
                    if mode == 'demo':
                        result = publish_construction(snapshot, runs_dir / run_id)
                    else:
                        client = PharosClient(endpoint, cache_dir=cache_dir, timeout=timeout,
                                              refresh=body.get('refresh', False))
                        result = (run_planned_construction(client, trace, runs_dir / run_id)
                                  if mode == 'planned' else run_construction(client, request, runs_dir / run_id))
                    self.json_reply({'run_id': run_id, 'graph': result['graph'],
                                     'question_id': run_id if result['question'] is not None else None,
                                     'question': result['question'], 'construction': result['construction']})
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
                    if graph.get('scope', {}).get('kind') == 'protein_cohort':
                        raise ValueError('CIViC retrieval and therapy questions require the existing disease-cohort workflow.')
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
                    verify_saved_refresh(source)
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
