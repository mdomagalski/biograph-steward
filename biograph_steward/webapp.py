"""Small local browser interface. Standard library only; bind to loopback only."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from uuid import uuid4
import webbrowser
import zipfile
from datetime import datetime, timezone

from .client import PharosClient, ENDPOINT, PharosError


def report_html(graph: dict | None = None) -> str:
    template = Path(__file__).with_name("ui.html").read_text(encoding="utf-8")
    data = json.dumps(graph, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    script = Path(__file__).with_name("guided.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("civic.js").read_text(encoding="utf-8")
    script += '\n' + Path(__file__).with_name("planner.js").read_text(encoding="utf-8")
    return template.replace("__GUIDED_SCRIPT__", script).replace("__EMBEDDED_GRAPH__", data)


def create_server(port: int, runs_dir: Path, endpoint: str = ENDPOINT,
                  cache_dir: Path | None = None, timeout: float = 30) -> ThreadingHTTPServer:
    runs_dir = Path(runs_dir).resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, payload: bytes, status: int = 200, content_type: str = "application/json", filename: str | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)

        def json_reply(self, obj: dict, status: int = 200):
            self.reply(json.dumps(obj, ensure_ascii=True, allow_nan=False).encode(), status)

        def do_GET(self):
            path = urlparse(self.path).path
            match=re.fullmatch(r"/api/evaluation/([A-Za-z0-9_-]{1,80})/(report\.html|case_reviews\.tsv|answer_reviews\.tsv|evidence_reviews\.tsv|metrics\.json)?",path)
            if match:
                folder=(runs_dir/match.group(1)).resolve();name=match.group(2) or 'report.html'
                if folder.parent!=runs_dir or not (folder/'metrics.json').is_file() or not (folder/name).is_file() or (folder/name).is_symlink():
                    self.json_reply({'error':'Evaluation artifact not found'},404);return
                content_type='text/html; charset=utf-8' if name=='report.html' else 'application/json' if name.endswith('.json') else 'text/tab-separated-values; charset=utf-8'
                self.reply((folder/name).read_bytes(),content_type=content_type,filename=name if name.endswith('.tsv') else None)
                return
            if path=='/api/planner':
                from .planning import ModelPlanner,PlannerUnavailable
                try:
                    planner=ModelPlanner();self.json_reply({'configured':True,'model':planner.model,'endpoint':planner.endpoint,'api':planner.api})
                except (ValueError,TypeError) as exc:self.json_reply({'configured':False,'reason':str(exc)})
                return
            if path == "/":
                self.reply(report_html().encode(), content_type="text/html; charset=utf-8")
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
                folder = runs_dir / match.group(1)
                if not folder.is_dir() or folder.parent != runs_dir:
                    self.json_reply({"error": "Run not found"}, 404)
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
            origin = self.headers.get("Origin")
            if origin:
                parsed = urlparse(origin)
                if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.port != self.server.server_port:
                    self.json_reply({"error": "Only same-local-server requests are allowed."}, 403)
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
                    from .planning import ModelPlanner,execute_plan
                    from .reviews import read_run
                    from .client import write_json
                    from .questions import save_answer
                    if set(body)!={'run_id','question'}:raise ValueError('Use only run_id and question for one bounded plan.')
                    source_id=body.get('run_id','')
                    if not isinstance(source_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',source_id):raise ValueError('Invalid source run ID.')
                    source=(runs_dir/source_id).resolve()
                    if source.parent!=runs_dir or not source.is_dir():raise ValueError('Source run not found.')
                    _,_,graph=read_run(source);planner=ModelPlanner();trace=planner.plan(body.get('question'),graph)
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

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port: int = 8765, runs_dir: Path = Path("runs"), endpoint: str = ENDPOINT,
          cache_dir: Path | None = Path(".pharos_cache"), open_browser: bool = True,
          timeout: float = 30):
    server = create_server(port, runs_dir, endpoint, cache_dir, timeout)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"BioGraph Steward: {url}\nLocal-only server. Ctrl+C stops it.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
