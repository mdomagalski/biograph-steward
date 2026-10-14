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
    return template.replace("__EMBEDDED_GRAPH__", data)


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
            if path == "/":
                self.reply(report_html().encode(), content_type="text/html; charset=utf-8")
                return
            if path == "/health":
                self.json_reply({"status": "local_server_running", "live_pharos_checked": False})
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
                if path == "/api/search":
                    client = PharosClient(endpoint, cache_dir=cache_dir, timeout=timeout)
                    self.json_reply(client.search(body.get("term", "")))
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
                        pathway_top=int(body.get("pathway_top", 5)), check_schema=bool(body.get("check_schema", True)))
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
