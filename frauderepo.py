#!/usr/bin/env python3
"""
FraudeRepo — Local development dashboard for FraudeCode.
Starts automatically with fraudecode.py on port 7862.
Open http://localhost:7862 in browser.
"""
import json, os, sys, threading, time
from pathlib import Path
from datetime import datetime

# Try to use http.server (stdlib, no deps)
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent))
from fraudecode_pkg.config import CODE_DIR

PORT = 7862
_sessions_cache = []
_last_refresh = 0

def _load_sessions():
    global _sessions_cache, _last_refresh
    if time.time() - _last_refresh < 3:
        return _sessions_cache
    chats_dir = CODE_DIR.parent / 'chats'
    sessions = []
    if chats_dir.exists():
        for f in sorted(chats_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                d = json.loads(f.read_text('utf-8'))
                ws = CODE_DIR / f'workspace_{d.get("id","")}'
                files = []
                if ws.exists():
                    SKIP = {'.venv','venv','__pycache__','node_modules','.git','.pytest_cache'}
                    files = [str(p.relative_to(ws)) for p in ws.rglob('*')
                             if p.is_file() and not any(s in p.parts for s in SKIP)]
                sessions.append({
                    'id': d.get('id',''),
                    'name': d.get('name', 'Unnamed'),
                    'updated': d.get('updated',''),
                    'history_count': len(d.get('history', [])),
                    'agent_override': d.get('agent_override','auto'),
                    'files': files,
                    'file_count': len(files),
                    'workspace': str(ws) if ws.exists() else None,
                })
            except Exception:
                pass
    _sessions_cache = sessions
    _last_refresh = time.time()
    return sessions

def _html_page(body: str, title: str = 'FraudeRepo') -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#0d1117;--bg2:#161b22;--bg3:#21262d;--border:#30363d;--text:#e6edf3;--text2:#8b949e;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--yellow:#d29922;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
a{{color:var(--accent);text-decoration:none;}}a:hover{{text-decoration:underline;}}
.header{{background:var(--bg2);border-bottom:1px solid var(--border);padding:0 24px;display:flex;align-items:center;gap:16px;height:56px;}}
.header .logo{{font-size:17px;font-weight:600;color:var(--text);}}
.header .logo span{{color:var(--accent);}}
.nav a{{font-size:14px;color:var(--text2);padding:4px 8px;border-radius:6px;}}
.nav a:hover{{color:var(--text);background:var(--bg3);text-decoration:none;}}
.main{{max-width:1200px;margin:0 auto;padding:24px;}}
.card{{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:20px;margin-bottom:16px;}}
.card h2{{font-size:15px;font-weight:600;margin-bottom:12px;color:var(--text);}}
.session-row{{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);}}
.session-row:last-child{{border-bottom:none;}}
.badge{{font-size:11px;padding:2px 7px;border-radius:12px;font-weight:500;}}
.badge-green{{background:#1a4a2e;color:var(--green);}}
.badge-blue{{background:#0d2340;color:var(--accent);}}
.badge-grey{{background:var(--bg3);color:var(--text2);}}
.stat{{display:inline-flex;align-items:center;gap:4px;font-size:12px;color:var(--text2);margin-right:14px;}}
.file-tree{{font-family:"Cascadia Code","Fira Code",monospace;font-size:12px;color:var(--text2);line-height:1.7;max-height:200px;overflow-y:auto;margin-top:8px;}}
.file-tree .py{{color:#79c0ff;}} .file-tree .js{{color:#e3b341;}} .file-tree .html{{color:#f97316;}} .file-tree .other{{color:var(--text2);}}
.tag{{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;background:var(--bg3);color:var(--text2);margin-right:4px;}}
h1{{font-size:22px;font-weight:600;margin-bottom:6px;}}
.sub{{color:var(--text2);font-size:14px;margin-bottom:24px;}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;}}
@media(max-width:768px){{.grid{{grid-template-columns:1fr;}}}}
.empty{{color:var(--text2);font-size:14px;padding:20px 0;text-align:center;}}
</style>
</head>
<body>
<div class="header">
  <span class="logo">Fraude<span>Repo</span></span>
  <nav class="nav" style="margin-left:16px;display:flex;gap:4px;">
    <a href="/">Chats</a>
    <a href="/files">Files</a>
    <a href="/log">Log</a>
  </nav>
  <span style="margin-left:auto;font-size:12px;color:var(--text2);">localhost:{PORT} · FraudeCode running</span>
</div>
<div class="main">{body}</div>
</body></html>'''

def _index_page(sessions):
    if not sessions:
        body = '''<h1>FraudeRepo</h1><p class="sub">Local AI code repository</p>
<div class="card"><p class="empty">No chats yet. Start FraudeCode and create a chat.</p></div>'''
    else:
        rows = ''
        for s in sessions:
            agent = s.get('agent_override','') or 'auto'
            badge_cls = 'badge-green' if 'max' in agent else 'badge-blue' if 'free' not in agent else 'badge-grey'
            updated = s['updated'][:16].replace('T',' ') if s.get('updated') else '—'
            files_preview = ' '.join(
                f'<span class="tag">{Path(f).name}</span>'
                for f in s['files'][:6]
            ) + (f'<span class="tag">+{s["file_count"]-6} more</span>' if s['file_count'] > 6 else '')
            rows += f'''
<div class="session-row">
  <div style="flex:1;min-width:0;">
    <a href="/chat/{s["id"]}" style="font-weight:500;font-size:14px;">{s["name"]}</a>
    <div style="margin-top:4px;">{files_preview}</div>
  </div>
  <div style="text-align:right;flex-shrink:0;">
    <span class="badge {badge_cls}">{agent}</span><br>
    <span class="stat" style="margin-top:4px;">{s["history_count"]} msgs · {s["file_count"]} files · {updated}</span>
  </div>
</div>'''
        body = f'''<h1>FraudeRepo</h1>
<p class="sub">{len(sessions)} chat workspace(s) — local AI code repository</p>
<div class="card"><h2>Recent Chats</h2>{rows}</div>'''
    return _html_page(body)

def _chat_page(session_id, sessions):
    s = next((x for x in sessions if x['id'] == session_id), None)
    if not s:
        return _html_page('<h1>Chat not found</h1>', 'Not found')
    # File tree
    files_by_dir = {}
    for f in sorted(s['files']):
        parts = Path(f).parts
        d = parts[0] if len(parts) > 1 else '.'
        files_by_dir.setdefault(d, []).append(f)
    tree_html = ''
    for d, files in sorted(files_by_dir.items()):
        if d != '.':
            tree_html += f'<div style="color:var(--accent);margin-top:6px;">📁 {d}/</div>'
        for f in files:
            ext = Path(f).suffix.lstrip('.')
            cls = ext if ext in ('py','js','html','ts','css','md') else 'other'
            tree_html += f'<div class="{cls}" style="padding-left:{16 if d!="." else 0}px;">📄 {Path(f).name}</div>'
    body = f'''
<div style="margin-bottom:16px;"><a href="/" style="color:var(--text2);font-size:13px;">← All chats</a></div>
<h1>{s["name"]}</h1>
<p class="sub" style="margin-bottom:16px;">{s["history_count"]} messages · {s["file_count"]} files · Agent: {s.get("agent_override","auto") or "auto"}</p>
<div class="grid">
  <div class="card"><h2>File Tree</h2>
    <div class="file-tree">{"<div class='empty'>No files yet.</div>" if not s["files"] else tree_html}</div>
  </div>
  <div class="card"><h2>Workspace Path</h2>
    <div style="font-family:monospace;font-size:12px;color:var(--text2);margin-bottom:12px;">{s.get("workspace","—")}</div>
    <h2 style="margin-top:12px;">Stats</h2>
    <div class="stat">💬 {s["history_count"]} messages</div>
    <div class="stat">📁 {s["file_count"]} files</div>
  </div>
</div>'''
    return _html_page(body, s['name'] + ' — FraudeRepo')

class FraudeRepoHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # Suppress request logs

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        sessions = _load_sessions()

        if path == '/' or path == '':
            content = _index_page(sessions).encode()
        elif path.startswith('/chat/'):
            sid = path[6:]
            content = _chat_page(sid, sessions).encode()
        elif path == '/api/sessions':
            content = json.dumps(sessions, default=str).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers(); self.wfile.write(content); return
        else:
            content = _html_page('<h1>Not found</h1>').encode()
            self.send_response(404)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers(); self.wfile.write(content); return

        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def start_server():
    """Start FraudeRepo in a background daemon thread."""
    def _run():
        try:
            server = HTTPServer(('localhost', PORT), FraudeRepoHandler)
            server.serve_forever()
        except OSError:
            pass  # Port already in use — another instance running
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return PORT


if __name__ == '__main__':
    print(f'FraudeRepo running at http://localhost:{PORT}')
    HTTPServer(('localhost', PORT), FraudeRepoHandler).serve_forever()
