#!/usr/bin/env python3
"""
Fraude Ollama Proxy — runs on :11435
Bridges fraude-ai.vercel.app ↔ local Ollama (:11434) and FraudeCode tools.
"""
import json, os, sys, threading, subprocess, time, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import argparse

PROXY_PORT  = 11435
OLLAMA_PORT = 11434
OLLAMA_URL  = f"http://localhost:{OLLAMA_PORT}"

# ── CORS headers ────────────────────────────────────────────────────────────
CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Allow-Private-Network": "true",
    "X-Content-Type-Options": "nosniff",
}

def json_resp(handler, code, data):
    body = json.dumps(data, ensure_ascii=False).encode()
    try:
        handler.send_response(code)
        for k, v in CORS.items():
            handler.send_header(k, v)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        pass  # Client disconnected — normal browser behaviour

def read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length > 0:
        try:
            return json.loads(handler.rfile.read(length))
        except Exception:
            return {}
    return {}

# ── SSE event bus ───────────────────────────────────────────────────────────
_sse_clients = []
_sse_lock    = threading.Lock()

def sse_push(event: str, data: dict):
    msg = f"data: {json.dumps({'event': event, 'data': data})}\n\n".encode()
    with _sse_lock:
        dead = []
        for w in _sse_clients:
            try:
                w.write(msg)
                w.flush()
            except Exception:
                dead.append(w)
        for w in dead:
            _sse_clients.remove(w)

# ── Check Ollama ─────────────────────────────────────────────────────────────
def ollama_ok():
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False

# ── Handler ──────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # Suppress default access log spam

    def do_OPTIONS(self):
        try:
            self.send_response(204)
            for k, v in CORS.items():
                self.send_header(k, v)
            # Explicit PNA preflight header — required for Chrome targetAddressSpace:'private'
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.end_headers()
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def do_GET(self):
        if self.path.startswith("/events"):
            self._sse_stream()
            return
        if self.path.startswith("/health"):
            json_resp(self, 200, {"proxy": "fraude-ollama", "ollama": ollama_ok(), "port": PROXY_PORT})
            return
        if self.path.startswith("/workspace-files"):
            self._workspace_files()
            return
        json_resp(self, 404, {"error": "Not found"})

    def _sse_stream(self):
        try:
            self.send_response(200)
            for k, v in CORS.items():
                self.send_header(k, v)
            self.send_header("Content-Type",  "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection",    "keep-alive")
            self.end_headers()
            with _sse_lock:
                _sse_clients.append(self.wfile)
            # Keep connection open
            while True:
                try:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    time.sleep(15)
                except Exception:
                    break
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass
        finally:
            with _sse_lock:
                if self.wfile in _sse_clients:
                    _sse_clients.remove(self.wfile)

    def _workspace_files(self):
        from urllib.parse import urlparse, parse_qs
        qs  = parse_qs(urlparse(self.path).query)
        d   = qs.get("dir", [""])[0]
        if not d or not os.path.isdir(d):
            json_resp(self, 200, {"files": [], "manifest": {}})
            return
        SKIP = {".venv", "__pycache__", "node_modules", ".git"}
        files = []
        for root, dirs, fs in os.walk(d):
            dirs[:] = [x for x in dirs if x not in SKIP and not x.startswith(".")]
            for f in fs:
                if not f.startswith("."):
                    files.append(os.path.relpath(os.path.join(root, f), d))
        json_resp(self, 200, {"files": files, "manifest": {}})

    def do_POST(self):
        body = read_body(self)
        p    = self.path.split("?")[0]

        # ── Ollama API pass-through ──────────────────────────────────────
        if p in ("/api/chat", "/api/generate", "/api/tags", "/api/pull"):
            self._forward_ollama(p, body)
            return

        # ── Health / proxy status ─────────────────────────────────────────
        if p == "/health":
            json_resp(self, 200, {"proxy": "fraude-ollama", "ollama": ollama_ok()})
            return

        # ── Launch Fraude App (automations server) ─────────────────────────────
        if p == "/launch-fraude-app":
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fraude_automations.py")
            if not os.path.exists(script):
                json_resp(self, 400, {"error": "fraude_automations.py not found in fraude-ai folder"})
                return
            try:
                python = sys.executable
                subprocess.Popen(
                    [python, script],
                    cwd=os.path.dirname(script),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                json_resp(self, 200, {"message": "Fraude Automations started."})
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})
            return
        if p == "/launch-jarvis":
            directory = body.get("directory", "").strip()
            # Default to same directory as proxy script if not specified
            if not directory or not os.path.isdir(directory):
                directory = os.path.dirname(os.path.abspath(__file__))
            script = os.path.join(directory, "jarvis.py")
            if not os.path.exists(script):
                # Try common locations
                for try_dir in [os.path.dirname(os.path.abspath(__file__)), os.path.expanduser("~")]:
                    candidate = os.path.join(try_dir, "jarvis.py")
                    if os.path.exists(candidate):
                        script = candidate; directory = try_dir; break
                else:
                    json_resp(self, 400, {"error": "jarvis.py not found. Set the JARVIS folder in Automations."})
                    return
            try:
                python = sys.executable
                subprocess.Popen(
                    [python, script],
                    cwd=directory,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                json_resp(self, 200, {"message": "JARVIS started in background."})
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})
            return
        if p == "/launch-fraudecode":
            directory = body.get("directory", "").strip()
            if not directory or not os.path.isdir(directory):
                json_resp(self, 400, {"error": f"Directory not found: {directory}"})
                return
            script = os.path.join(directory, "fraudecode.py")
            if not os.path.exists(script):
                json_resp(self, 400, {"error": f"fraudecode.py not found in {directory}"})
                return
            try:
                python = sys.executable
                # Hidden: CREATE_NO_WINDOW — no console appears at all
                subprocess.Popen(
                    [python, script],
                    cwd=directory,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                json_resp(self, 200, {"message": "FraudeCode CLI started in background (hidden)."})
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})
            return

        # ── Show FraudeCode CLI (visible terminal window on demand) ───────────
        if p == "/show-fraudecode":
            directory = body.get("directory", "").strip()
            if not directory or not os.path.isdir(directory):
                json_resp(self, 400, {"error": f"Directory not found: {directory}"})
                return
            script = os.path.join(directory, "fraudecode.py")
            if not os.path.exists(script):
                json_resp(self, 400, {"error": f"fraudecode.py not found in {directory}"})
                return
            try:
                python = sys.executable
                # Visible: CREATE_NEW_CONSOLE — opens a proper terminal window
                subprocess.Popen(
                    ["cmd", "/k", python, script],
                    cwd=directory,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                json_resp(self, 200, {"message": "FraudeCode CLI terminal opened."})
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})
            return

        # ── Setup FraudeCode deps ──────────────────────────────────────────
        if p == "/setup-fraudecode":
            directory = body.get("directory", "").strip()
            if not directory:
                json_resp(self, 400, {"error": "No directory provided"})
                return
            req = os.path.join(directory, "requirements.txt")
            try:
                python = sys.executable
                if os.path.exists(req):
                    subprocess.run([python, "-m", "pip", "install", "-r", req, "-q"], timeout=120)
                else:
                    subprocess.run([python, "-m", "pip", "install",
                                    "requests", "colorama", "pyreadline3", "-q"], timeout=120)
                json_resp(self, 200, {"message": "Dependencies installed."})
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})
            return

        # ── Run FraudeCode task ────────────────────────────────────────────
        if p == "/fraudecode-run":
            task    = body.get("task", "")
            workdir = body.get("workdir", "") or ""
            fc_dir  = body.get("fc_dir",  "") or ""
            if not fc_dir or not os.path.isdir(fc_dir):
                json_resp(self, 400, {"error": "FraudeCode folder not set. Go to Setup in FraudeCode."})
                return
            threading.Thread(target=self._run_task, args=(task, workdir, fc_dir), daemon=True).start()
            json_resp(self, 200, {"queued": True})
            return

        # ── Orchestrate ────────────────────────────────────────────────────
        if p == "/orchestrate":
            request = body.get("request", "")
            workdir = body.get("workdir", "") or ""
            fc_dir  = body.get("fc_dir",  "") or ""
            if not fc_dir or not os.path.isdir(fc_dir):
                json_resp(self, 400, {"error": "FraudeCode folder not set."})
                return
            threading.Thread(target=self._orchestrate, args=(request, workdir, fc_dir), daemon=True).start()
            json_resp(self, 200, {"queued": True})
            return

        # ── Audit ──────────────────────────────────────────────────────────
        if p == "/audit":
            workdir = body.get("workdir", "") or ""
            fc_dir  = body.get("fc_dir",  "") or ""
            threading.Thread(target=self._audit, args=(workdir, fc_dir), daemon=True).start()
            json_resp(self, 200, {"queued": True})
            return

        # ── Package workspace ──────────────────────────────────────────────
        if p == "/package-workspace":
            self._package(body)
            return

        json_resp(self, 404, {"error": f"Unknown route: {p}"})

    def _forward_ollama(self, path, body):
        """Pass request directly to local Ollama."""
        try:
            data = json.dumps(body).encode()
            req  = urllib.request.Request(
                OLLAMA_URL + path, data=data,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as r:
                resp_body = r.read()
            try:
                self.send_response(200)
                for k, v in CORS.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
            except (BrokenPipeError, ConnectionAbortedError):
                pass
        except Exception as e:
            json_resp(self, 502, {"error": f"Ollama: {e}"})

    def _run_task(self, task, workdir, fc_dir):
        try:
            sys.path.insert(0, fc_dir)
            from fraudecode_pkg.agents import run as run_pipeline, set_config
            from fraudecode_pkg.config import load
            cfg = load() or {}
            set_config(cfg)
            sse_push("task_start", {"task": task})
            result = run_pipeline(task, workdir or None)
            sse_push("task_done", {
                "code": result.code,
                "explanation": result.explanation,
                "task_type": result.task_type,
                "fallbacks": result.fallbacks,
            })
        except Exception as e:
            sse_push("task_error", {"error": str(e)})

    def _orchestrate(self, request, workdir, fc_dir):
        try:
            sys.path.insert(0, fc_dir)
            from fraudecode_pkg import orchestrator
            from fraudecode_pkg.agents import set_config
            from fraudecode_pkg.config import load
            cfg = load() or {}
            set_config(cfg)
            sse_push("orch_start", {"request": request})
            result = orchestrator.run(request, workdir or fc_dir)
            sse_push("orch_complete", {
                "orchestrated": True,
                "files": result.files_written,
                "summary": getattr(result.review, "get", lambda k, d=None: d)("summary", ""),
            })
        except Exception as e:
            sse_push("orch_error", {"error": str(e)})

    def _audit(self, workdir, fc_dir):
        try:
            if not workdir or not os.path.isdir(workdir):
                sse_push("audit_complete", {"report": "No workspace set."})
                return
            sys.path.insert(0, fc_dir or ".")
            from fraudecode_pkg.agents import run as run_pipeline, set_config
            from fraudecode_pkg.config import load
            cfg = load() or {}
            set_config(cfg)
            audit_prompt = (
                f"Security audit of workspace at {workdir}. "
                "Check for: hardcoded secrets, SQL injection, path traversal, "
                "insecure dependencies, input validation issues. "
                "List all issues found with severity (HIGH/MED/LOW)."
            )
            result = run_pipeline(audit_prompt, workdir)
            sse_push("audit_complete", {"report": result.code or result.explanation or "Audit complete."})
        except Exception as e:
            sse_push("audit_complete", {"report": f"Audit error: {e}"})

    def _package(self, body):
        import zipfile, tempfile
        workdir = (body.get("workdir") or "").strip()
        if not workdir or not os.path.isdir(workdir):
            json_resp(self, 400, {"error": f"Workspace not found: {workdir}"})
            return
        try:
            ts       = time.strftime("%Y%m%d_%H%M%S")
            name     = os.path.basename(workdir.rstrip("/\\")) or "workspace"
            zip_name = f"{name}_{ts}.zip"
            tmp_dir  = os.path.join(os.environ.get("TEMP", "/tmp"), "fraude_packages")
            os.makedirs(tmp_dir, exist_ok=True)
            zip_path = os.path.join(tmp_dir, zip_name)
            SKIP = {".venv", "__pycache__", "node_modules", ".git"}
            count = 0
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(workdir):
                    dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
                    for f in files:
                        if not f.startswith("."):
                            abs_p = os.path.join(root, f)
                            zf.write(abs_p, os.path.relpath(abs_p, workdir))
                            count += 1
            # Send zip directly as download
            with open(zip_path, "rb") as f:
                data = f.read()
            try:
                self.send_response(200)
                for k, v in CORS.items():
                    self.send_header(k, v)
                self.send_header("Content-Type",        "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{zip_name}"')
                self.send_header("Content-Length",      str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionAbortedError):
                pass
            try:
                os.unlink(zip_path)
            except Exception:
                pass
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tray", action="store_true")
    args = parser.parse_args()

    server = HTTPServer(("localhost", PROXY_PORT), Handler)
    server.allow_reuse_address = True

    print(f"""
  ███████╗██████╗  █████╗ ██╗   ██╗██████╗ ███████╗
  ██╔════╝██╔══██╗██╔══██╗██║   ██║██╔══██╗██╔════╝
  █████╗  ██████╔╝███████║██║   ██║██║  ██║█████╗
  ██╔══╝  ██╔══██╗██╔══██║██║   ██║██║  ██║██╔══╝
  ██║     ██║  ██║██║  ██║╚██████╔╝██████╔╝███████╗
  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
  Proxy :{PROXY_PORT}  |  Ollama :{OLLAMA_PORT}  |  FraudeCode Web Bridge

  {"✓" if ollama_ok() else "✗"} Ollama :{OLLAMA_PORT}
  ✓ Proxy :{PROXY_PORT}  (Ctrl+C to stop)
""")

    if args.tray:
        try:
            _run_tray(server)
            return
        except Exception:
            pass  # tray failed, fall through to normal serve

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")

def _run_tray(server):
    import pystray
    from PIL import Image, ImageDraw
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # Create a simple icon
    img = Image.new("RGB", (64, 64), "#e8572a")
    d   = ImageDraw.Draw(img)
    d.text((10, 16), "F", fill="white")
    icon = pystray.Icon(
        "fraude-proxy",
        img,
        "Fraude Proxy",
        menu=pystray.Menu(
            pystray.MenuItem("Fraude Proxy running", None, enabled=False),
            pystray.MenuItem("Stop", lambda: icon.stop()),
        ),
    )
    icon.run()
    server.shutdown()

if __name__ == "__main__":
    main()
