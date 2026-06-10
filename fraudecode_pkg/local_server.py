"""
local_server.py — Fraude Local Project Server

Exposes a managed project workspace as:
  1. HTTP file server (agents read/write via URL)
  2. MCP-compatible JSON-RPC endpoint (Claude, Claude Code, etc. connect here)
  3. Run/test/audit endpoints

Runs on a dedicated port per project (default 11436).
Started automatically by ollama_proxy.py when a project is activated.
"""
import json, sys, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from . import project_workspace as pw

DEFAULT_PORT = 11436
_servers: dict = {}  # source_path → HTTPServer


def json_ok(h, data):
    body = json.dumps(data, indent=2).encode()
    h.send_response(200)
    h.send_header('Content-Type', 'application/json')
    h.send_header('Access-Control-Allow-Origin', '*')
    h.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    h.send_header('Access-Control-Allow-Headers', 'Content-Type')
    h.end_headers()
    h.wfile.write(body)


def json_err(h, code, msg):
    body = json.dumps({'error': msg}).encode()
    h.send_response(code)
    h.send_header('Content-Type', 'application/json')
    h.send_header('Access-Control-Allow-Origin', '*')
    h.end_headers()
    h.wfile.write(body)


def read_body(h) -> dict:
    n = int(h.headers.get('Content-Length', 0))
    raw = h.rfile.read(n)
    try: return json.loads(raw or b'{}')
    except: return {}


class ProjectHandler(BaseHTTPRequestHandler):
    source_path: str = ''

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        path   = parsed.path.rstrip('/')
        sp     = self.source_path

        if path in ('', '/health'):
            return json_ok(self, {
                'ok': True, 'server': 'fraude-project',
                'project': pw.get_manifest(sp).get('project_name', ''),
                'source': sp,
            })

        if path == '/files':
            return json_ok(self, {'files': pw.list_files(sp)})

        if path == '/read':
            fn = qs.get('file', [''])[0]
            if not fn: return json_err(self, 400, 'file param required')
            try:
                return json_ok(self, {'filename': fn, 'content': pw.read_file(sp, fn)})
            except FileNotFoundError:
                return json_err(self, 404, f'File not found: {fn}')

        if path == '/handoff':
            return json_ok(self, {'content': pw.get_handoff(sp)})

        if path == '/summary':
            return json_ok(self, {'content': pw.get_summary(sp)})

        if path == '/manifest':
            return json_ok(self, pw.get_manifest(sp))

        if path == '/diff':
            return json_ok(self, {'changes': pw.get_diff(sp)})

        if path == '/log':
            return json_ok(self, {'log': pw.get_log(sp)})

        if path == '/context':
            return json_ok(self, pw.get_mcp_context(sp))

        json_err(self, 404, f'Unknown route: {path}')

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip('/')
        body   = read_body(self)
        sp     = self.source_path

        if path == '/write':
            fn       = body.get('filename', '')
            content  = body.get('content', '')
            agent    = body.get('agent', 'agent')
            step     = body.get('step', 0)
            summary  = body.get('summary', '')
            if not fn: return json_err(self, 400, 'filename required')
            dest = pw.write_file(sp, fn, content, agent, step, summary)
            return json_ok(self, {'ok': True, 'filename': fn, 'path': str(dest)})

        if path == '/append-handoff':
            content = body.get('content', '')
            pw.append_handoff(sp, content)
            return json_ok(self, {'ok': True})

        if path == '/write-summary':
            pw.write_summary(sp, body.get('content', ''))
            return json_ok(self, {'ok': True})

        if path == '/run':
            fn = body.get('filename', '')
            if not fn: return json_err(self, 400, 'filename required')
            result = pw.run_file(sp, fn, timeout=body.get('timeout', 30))
            return json_ok(self, result)

        if path == '/npm-audit':
            return json_ok(self, pw.run_npm_audit(sp))

        if path == '/pip-audit':
            return json_ok(self, pw.run_pip_audit(sp))

        if path == '/apply':
            files  = body.get('files', None)  # None = apply all
            result = pw.apply_changes(sp, files)
            return json_ok(self, result)

        if path == '/log-step':
            pw.log_step(sp, body)
            return json_ok(self, {'ok': True})

        # ── MCP JSON-RPC endpoint ──────────────────────────────────────────────
        if path == '/mcp':
            return self._handle_mcp(body)

        json_err(self, 404, f'Unknown route: {path}')

    def _handle_mcp(self, body: dict):
        """Handle MCP JSON-RPC 2.0 requests from Claude, Claude Code, etc."""
        sp      = self.source_path
        method  = body.get('method', '')
        params  = body.get('params', {})
        req_id  = body.get('id', 1)

        def ok(result):
            return json_ok(self, {'jsonrpc': '2.0', 'id': req_id, 'result': result})
        def err(code, msg):
            return json_err(self, 200, msg)  # MCP errors go in the result body

        if method == 'initialize':
            return ok({
                'protocolVersion': '2024-11-05',
                'capabilities': {'tools': {}},
                'serverInfo': {'name': 'fraude-project', 'version': '1.0'},
            })

        if method == 'tools/list':
            return ok({'tools': _MCP_TOOLS})

        if method == 'tools/call':
            tool_name = params.get('name', '')
            args      = params.get('arguments', {})
            result    = _dispatch_mcp_tool(sp, tool_name, args)
            return ok({'content': [{'type': 'text', 'text': json.dumps(result, indent=2)}]})

        return ok({'message': f'Unknown method: {method}'})

    def log_message(self, *a): pass


# ── MCP tool definitions ───────────────────────────────────────────────────────
_MCP_TOOLS = [
    {
        'name': 'list_files',
        'description': 'List all files in the Fraude project workspace',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'read_file',
        'description': 'Read the content of a file in the workspace',
        'inputSchema': {
            'type': 'object',
            'required': ['filename'],
            'properties': {'filename': {'type': 'string', 'description': 'Relative file path'}},
        },
    },
    {
        'name': 'write_file',
        'description': 'Write or update a file in the workspace',
        'inputSchema': {
            'type': 'object',
            'required': ['filename', 'content'],
            'properties': {
                'filename': {'type': 'string'},
                'content':  {'type': 'string'},
                'summary':  {'type': 'string', 'description': 'One-line description of the change'},
            },
        },
    },
    {
        'name': 'run_file',
        'description': 'Execute a Python, JS, or shell file and return output',
        'inputSchema': {
            'type': 'object',
            'required': ['filename'],
            'properties': {
                'filename': {'type': 'string'},
                'timeout':  {'type': 'integer', 'default': 30},
            },
        },
    },
    {
        'name': 'get_diff',
        'description': 'Show all changes made to the workspace vs the original project',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_handoff',
        'description': 'Read the running handoff document — describes all changes agents have made',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'append_handoff',
        'description': 'Append a section to the handoff document',
        'inputSchema': {
            'type': 'object',
            'required': ['content'],
            'properties': {'content': {'type': 'string', 'description': 'Markdown content to append'}},
        },
    },
    {
        'name': 'get_summary',
        'description': 'Get the human-readable summary of all changes made in this session',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'apply_changes',
        'description': 'Apply approved changes back to the original project directory',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'files': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of filenames to apply. Omit to apply all.',
                },
            },
        },
    },
]


def _dispatch_mcp_tool(source_path: str, name: str, args: dict) -> dict:
    if name == 'list_files':
        return {'files': pw.list_files(source_path)}

    if name == 'read_file':
        fn = args.get('filename', '')
        try:
            return {'filename': fn, 'content': pw.read_file(source_path, fn)}
        except FileNotFoundError:
            return {'error': f'File not found: {fn}'}

    if name == 'write_file':
        fn      = args.get('filename', '')
        content = args.get('content', '')
        summary = args.get('summary', '')
        if not fn: return {'error': 'filename required'}
        pw.write_file(source_path, fn, content, written_by='mcp_client', summary=summary)
        return {'ok': True, 'filename': fn}

    if name == 'run_file':
        fn = args.get('filename', '')
        return pw.run_file(source_path, fn, args.get('timeout', 30))

    if name == 'get_diff':
        return {'changes': pw.get_diff(source_path)}

    if name == 'get_handoff':
        return {'content': pw.get_handoff(source_path)}

    if name == 'append_handoff':
        pw.append_handoff(source_path, args.get('content', ''))
        return {'ok': True}

    if name == 'get_summary':
        return {'content': pw.get_summary(source_path)}

    if name == 'apply_changes':
        files  = args.get('files', None)
        result = pw.apply_changes(source_path, files)
        return result

    return {'error': f'Unknown tool: {name}'}


# ── Server lifecycle ───────────────────────────────────────────────────────────

def start(source_path: str, port: int = DEFAULT_PORT) -> int:
    """Start the project server for a given source path. Returns the port."""
    if source_path in _servers:
        return _servers[source_path]['port']

    # Create a handler class bound to this source path
    class BoundHandler(ProjectHandler):
        pass
    BoundHandler.source_path = source_path

    # Find available port
    while True:
        try:
            server = HTTPServer(('localhost', port), BoundHandler)
            break
        except OSError:
            port += 1

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    _servers[source_path] = {'server': server, 'port': port, 'thread': t}
    return port


def stop(source_path: str):
    if source_path in _servers:
        _servers[source_path]['server'].shutdown()
        del _servers[source_path]


def get_port(source_path: str) -> int | None:
    entry = _servers.get(source_path)
    return entry['port'] if entry else None


def get_server_url(source_path: str) -> str | None:
    port = get_port(source_path)
    return f'http://localhost:{port}' if port else None
