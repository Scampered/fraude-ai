#!/usr/bin/env python3
"""
Fraude Proxy — port 11435
- Forwards /api/* to Ollama (CORS)
- WebSocket /ws/fraudecode — real-time bridge between web UI and fraudecode.py
- /launch-fraudecode, /setup-fraudecode, /health
- /fraudecode-run  — runs a task via fraudecode pipeline and streams events
"""
import json, os, sys, subprocess, threading, time, webbrowser, queue
import urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PROXY_PORT  = 11435
OLLAMA_PORT = 11434
FRAUDE_URL  = 'https://fraude-ai.vercel.app'
USE_TRAY    = '--tray' in sys.argv

# ── Event bus for streaming pipeline progress to web ──────────────────────────
_event_queues: list = []  # list of Queue objects — one per connected web client
_event_lock = threading.Lock()

def broadcast(event: str, data: dict = None):
    """Send event to all connected web clients."""
    msg = json.dumps({'event': event, 'data': data or {}, 'ts': time.time()})
    with _event_lock:
        for q in _event_queues[:]:
            try: q.put_nowait(msg)
            except Exception: pass

def add_listener():
    q = queue.Queue(maxsize=200)
    with _event_lock:
        _event_queues.append(q)
    return q

def remove_listener(q):
    with _event_lock:
        if q in _event_queues:
            _event_queues.remove(q)

# ── Helpers ────────────────────────────────────────────────────────────────────
def json_resp(handler, status, data):
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    handler.end_headers()
    handler.wfile.write(body)

def read_body(handler):
    n = int(handler.headers.get('Content-Length', 0))
    raw = handler.rfile.read(n)
    try: return json.loads(raw or b'{}')
    except: return {}

def ollama_running():
    try:
        urllib.request.urlopen(f'http://localhost:{OLLAMA_PORT}/', timeout=2)
        return True
    except: return False

# ── Handler ────────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        if self.path in ('/', '/health', '/fraude-proxy'):
            return json_resp(self, 200, {
                'ok': True, 'proxy': 'fraude-ollama',
                'port': PROXY_PORT, 'ollama_running': ollama_running(),
            })
        # SSE stream for pipeline events
        if self.path == '/events':
            return self._sse_stream()
        # Workspace file listing
        if self.path.startswith('/workspace-files?'):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            d  = qs.get('dir', [''])[0]
            if d and os.path.exists(d):
                try:
                    from fraudecode_pkg import workspace as ws
                    files = ws.list_files(d)
                    manifest = ws.get_manifest(d) if ws.has_workspace(d) else {}
                    log = ws.get_log(d) if ws.has_workspace(d) else []
                    return json_resp(self, 200, {'files': files, 'manifest': manifest, 'log': log})
                except ImportError:
                    pass
            return json_resp(self, 200, {'files': [], 'manifest': {}, 'log': []})
        self._forward('GET', b'')

    def do_POST(self):
        if self.path == '/health':
            return json_resp(self, 200, {'ok': True, 'proxy': 'fraude-ollama'})

        if self.path == '/launch-fraudecode':
            body = read_body(self)
            d    = (body.get('directory') or '').strip()
            if not d:
                return json_resp(self, 400, {'error': 'No directory provided.'})
            fc = os.path.join(d, 'fraudecode.py')
            if not os.path.exists(fc):
                return json_resp(self, 404, {'error': f'fraudecode.py not found in: {d}'})
            try:
                if sys.platform == 'win32':
                    subprocess.Popen(f'start cmd /k "cd /d {d} && python fraudecode.py"', shell=True)
                else:
                    subprocess.Popen(f'cd "{d}" && python3 fraudecode.py',
                        shell=True, start_new_session=True)
                return json_resp(self, 200, {'message': 'FraudeCode launched in new terminal.'})
            except Exception as e:
                return json_resp(self, 500, {'error': str(e)})

        if self.path == '/setup-fraudecode':
            body = read_body(self)
            d    = (body.get('directory') or '').strip()
            if not d or not os.path.exists(d):
                return json_resp(self, 400, {'error': f'Directory not found: {d}'})
            try:
                pkgs = ['requests','google-generativeai','groq','colorama','pyreadline3','pystray','pillow']
                r = subprocess.run(
                    [sys.executable,'-m','pip','install','--quiet','--upgrade'] + pkgs,
                    capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    return json_resp(self, 200, {'message': f'Done! Installed: {", ".join(pkgs)}'})
                return json_resp(self, 500, {'error': 'pip error: ' + r.stderr[:400]})
            except Exception as e:
                return json_resp(self, 500, {'error': str(e)})

        # Run a fraudecode task from web (streams events via /events SSE)
        if self.path == '/fraudecode-run':
            body = read_body(self)
            task   = body.get('task', '').strip()
            wdir   = body.get('workdir', '').strip()
            fc_dir = body.get('fc_dir', '').strip()
            if not task:
                return json_resp(self, 400, {'error': 'No task provided.'})
            threading.Thread(
                target=_run_fraudecode_task,
                args=(task, wdir, fc_dir),
                daemon=True
            ).start()
            return json_resp(self, 200, {'message': 'Task started — listen to /events for progress.'})

        # Orchestrate from web
        if self.path == '/orchestrate':
            body    = read_body(self)
            request = body.get('request', '').strip()
            wdir    = body.get('workdir', '').strip()
            fc_dir  = body.get('fc_dir', '').strip()
            if not request or not wdir:
                return json_resp(self, 400, {'error': 'request and workdir required'})
            threading.Thread(
                target=_run_orchestrator,
                args=(request, wdir, fc_dir),
                daemon=True
            ).start()
            return json_resp(self, 200, {'message': 'Orchestrator started — listen to /events.'})

        # Audit from web
        if self.path == '/audit':
            body = read_body(self)
            wdir = body.get('workdir', '').strip()
            fc_dir = body.get('fc_dir', '').strip()
            if not wdir:
                return json_resp(self, 400, {'error': 'workdir required'})
            threading.Thread(target=_run_audit, args=(wdir, fc_dir), daemon=True).start()
            return json_resp(self, 200, {'message': 'Audit started — listen to /events.'})

        # Default: forward to Ollama
        n    = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n)
        self._forward('POST', body)

    def _sse_stream(self):
        """Server-Sent Events endpoint — streams pipeline events to web UI."""
        q = add_listener()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    self.wfile.write(f'data: {msg}\n\n'.encode())
                    self.wfile.flush()
                except queue.Empty:
                    # Send keepalive
                    self.wfile.write(b': keepalive\n\n')
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            remove_listener(q)

    def _forward(self, method, body):
        target = f'http://localhost:{OLLAMA_PORT}{self.path}'
        try:
            req = urllib.request.Request(
                target, data=body or None,
                headers={'Content-Type': 'application/json'},
                method=method)
            with urllib.request.urlopen(req, timeout=120) as r:
                result = r.read()
                ct = r.headers.get('Content-Type', 'application/json')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self._cors()
            self.end_headers()
            self.wfile.write(result)
        except urllib.error.URLError as e:
            json_resp(self, 503, {'error': f'Ollama not reachable: {e.reason}'})
        except Exception as e:
            json_resp(self, 500, {'error': str(e)})

    def log_message(self, *a): pass

# ── Background task runners ────────────────────────────────────────────────────
def _setup_fraudecode_path(fc_dir: str):
    """Add fraudecode directory to Python path so we can import fraudecode_pkg."""
    if fc_dir and fc_dir not in sys.path:
        sys.path.insert(0, fc_dir)

def _run_fraudecode_task(task: str, workdir: str, fc_dir: str):
    """Run a single-agent fraudecode task and stream events."""
    _setup_fraudecode_path(fc_dir)
    broadcast('task_start', {'task': task[:100]})
    try:
        from fraudecode_pkg import agents, config
        cfg = config.load()
        agents.set_config(cfg)
        from fraudecode_pkg import orchestrator
        orchestrator.set_progress_callback(broadcast)
        result = agents.run(task, workdir=workdir or None)
        broadcast('task_done', {
            'code': result.code[:5000] if result.code else '',
            'explanation': result.explanation[:2000] if result.explanation else '',
            'orchestrated': result.orchestrated,
            'errors': result.errors,
        })
    except Exception as e:
        broadcast('task_error', {'error': str(e)})

def _run_orchestrator(request: str, workdir: str, fc_dir: str):
    _setup_fraudecode_path(fc_dir)
    broadcast('orch_start', {'request': request[:100]})
    try:
        from fraudecode_pkg import agents, config, orchestrator
        cfg = config.load()
        agents.set_config(cfg)
        orchestrator.set_progress_callback(broadcast)
        result = orchestrator.run(request, workdir)
        broadcast('orch_complete', {
            'files': result.files_written,
            'review': result.review,
            'success': result.success,
        })
    except Exception as e:
        broadcast('orch_error', {'error': str(e)})

def _run_audit(workdir: str, fc_dir: str):
    _setup_fraudecode_path(fc_dir)
    broadcast('audit_start', {})
    try:
        from fraudecode_pkg import agents, config, orchestrator
        cfg = config.load()
        agents.set_config(cfg)
        orchestrator.set_progress_callback(broadcast)
        report = orchestrator.run_cybersec_audit(workdir)
        broadcast('audit_complete', {'report': report})
    except Exception as e:
        broadcast('audit_error', {'error': str(e)})

# ── Tray ───────────────────────────────────────────────────────────────────────
def run_tray(server):
    try:
        import pystray
        from PIL import Image, ImageDraw
        img = Image.new('RGBA', (64,64),(0,0,0,0))
        d = ImageDraw.Draw(img)
        d.ellipse([2,2,62,62], fill=(232,87,42))
        d.text((20,16),'F',fill='white')
        menu = pystray.Menu(
            pystray.MenuItem('Open Fraude', lambda *a: webbrowser.open(
                f'{FRAUDE_URL}?ollamaProxy=1&ollamaPort={PROXY_PORT}'), default=True),
            pystray.MenuItem(f'Proxy :11435', lambda *a: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit', lambda icon, *a: (icon.stop(), server.shutdown(), os._exit(0))),
        )
        pystray.Icon('fraude', img, 'Fraude — Local AI', menu).run()
    except Exception:
        try:
            while True: time.sleep(60)
        except KeyboardInterrupt:
            server.shutdown()

BANNER = """
  ███████╗██████╗  █████╗ ██╗   ██╗██████╗ ███████╗
  ██╔════╝██╔══██╗██╔══██╗██║   ██║██╔══██╗██╔════╝
  █████╗  ██████╔╝███████║██║   ██║██║  ██║█████╗
  ██╔══╝  ██╔══██╗██╔══██║██║   ██║██║  ██║██╔══╝
  ██║     ██║  ██║██║  ██║╚██████╔╝██████╔╝███████╗
  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
  Proxy :11435  |  Ollama :11434  |  FraudeCode Web Bridge
"""

def start_ollama():
    try:
        kw = {'creationflags': 0x08000000} if sys.platform=='win32' else {'start_new_session': True}
        subprocess.Popen(['ollama','serve'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        for _ in range(20):
            if ollama_running(): return True
            time.sleep(1)
        return False
    except FileNotFoundError: return False

def main():
    if not USE_TRAY: print(BANNER)
    if not ollama_running():
        if not USE_TRAY: print('  Starting Ollama...', end='', flush=True)
        ok = start_ollama()
        if not USE_TRAY: print(' ✓' if ok else ' ✗ (install from ollama.com)')
    elif not USE_TRAY:
        print(f'  ✓ Ollama :{OLLAMA_PORT}')

    server = HTTPServer(('localhost', PROXY_PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    if not USE_TRAY:
        print(f'  ✓ Proxy :11435  (Ctrl+C to stop)\n')

    threading.Thread(
        target=lambda: (time.sleep(1.5),
            webbrowser.open(f'{FRAUDE_URL}?ollamaProxy=1&ollamaPort={PROXY_PORT}')),
        daemon=True
    ).start()

    if USE_TRAY: run_tray(server)
    else:
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print('\n  Stopped.')

if __name__ == '__main__': main()
