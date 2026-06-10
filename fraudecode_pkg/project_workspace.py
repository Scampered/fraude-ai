"""
project_workspace.py — Fraude Managed Project Workspace

Creates and manages a sandboxed copy of a user's project in AppData.
Agents read/write from this managed copy. User approves before changes
are applied back to the original directory.

AppData structure:
  %APPDATA%\fraude\projects\<project_id>\
    source\           ← copy of original project files
    .fraude\          ← manifest, handoffs, audit, logs
    .fraude\handoff.md  ← running handoff document (append-only)
    .fraude\summary.md  ← human-readable summary of all changes
    .fraude\audit\    ← security audit outputs
"""
import json, shutil, os, sys, hashlib, difflib, subprocess
from datetime import datetime
from pathlib import Path

# ── AppData location ───────────────────────────────────────────────────────────
def _appdata() -> Path:
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    p = base / 'fraude' / 'projects'
    p.mkdir(parents=True, exist_ok=True)
    return p

def _project_id(source_path: str) -> str:
    """Stable ID from the source path."""
    return hashlib.md5(str(Path(source_path).resolve()).encode()).hexdigest()[:12]

def _managed_root(source_path: str) -> Path:
    pid = _project_id(source_path)
    name = Path(source_path).name
    return _appdata() / f'{name}_{pid}'

FRAUDE_DIR  = '.fraude'
SOURCE_DIR  = 'source'

# ── Public API ─────────────────────────────────────────────────────────────────

def init(source_path: str, project_name: str = '') -> dict:
    """
    Create managed workspace from source_path.
    Copies all non-hidden, non-cache files into AppData.
    Returns info dict with managed_path, source_path, file_count.
    """
    src  = Path(source_path).resolve()
    root = _managed_root(source_path)
    dest = root / SOURCE_DIR

    root.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    (root / FRAUDE_DIR).mkdir(exist_ok=True)
    (root / FRAUDE_DIR / 'handoffs').mkdir(exist_ok=True)
    (root / FRAUDE_DIR / 'audit').mkdir(exist_ok=True)

    # Copy files from source
    file_count = 0
    skipped    = []
    SKIP_DIRS  = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                  'dist', 'build', '.next', '.cache'}

    for item in src.rglob('*'):
        if item.is_dir(): continue
        if any(p in item.parts for p in SKIP_DIRS): continue
        if item.name.startswith('.'): continue
        rel  = item.relative_to(src)
        out  = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, out)
        file_count += 1

    # Manifest
    m = {
        'project_name': project_name or src.name,
        'source_path':  str(src),
        'managed_path': str(root),
        'created_at':   datetime.now().isoformat(),
        'status':       'active',
        'files':        [],
        'steps':        [],
        'changes':      [],   # list of {filename, agent, step, summary}
    }
    _write_manifest(root, m)
    _write_log(root, [])
    _append_handoff(root, f'# Handoff — {m["project_name"]}\n\nProject copied from: `{src}`\n\n')

    return {
        'managed_path': str(root),
        'source_path':  str(src),
        'file_count':   file_count,
        'project_name': m['project_name'],
    }

def get_managed_path(source_path: str) -> Path | None:
    """Return managed path if it exists, else None."""
    root = _managed_root(source_path)
    return root if root.exists() else None

def has_workspace(source_path: str) -> bool:
    return _managed_root(source_path).exists()

def list_projects() -> list:
    """List all managed projects."""
    base = _appdata()
    out  = []
    for d in sorted(base.iterdir()):
        if not d.is_dir(): continue
        m = _read_manifest(d)
        if m:
            out.append({
                'managed_path':  str(d),
                'source_path':   m.get('source_path', ''),
                'project_name':  m.get('project_name', d.name),
                'status':        m.get('status', 'unknown'),
                'created_at':    m.get('created_at', ''),
            })
    return out

# ── File operations (agents use these) ─────────────────────────────────────────

def list_files(source_path: str, include_hidden: bool = False) -> list:
    dest = _managed_root(source_path) / SOURCE_DIR
    out  = []
    for f in sorted(dest.rglob('*')):
        if not f.is_file(): continue
        if not include_hidden and f.name.startswith('.'): continue
        out.append(str(f.relative_to(dest)))
    return out

def read_file(source_path: str, filename: str) -> str:
    path = _managed_root(source_path) / SOURCE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f'File not found in workspace: {filename}')
    return path.read_text('utf-8', errors='replace')

def write_file(source_path: str, filename: str, content: str,
               written_by: str = 'agent', step: int = 0, summary: str = '') -> Path:
    root = _managed_root(source_path)
    dest = root / SOURCE_DIR / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Record old content for diff
    old_content = dest.read_text('utf-8', errors='replace') if dest.exists() else None
    dest.write_text(content, 'utf-8')

    # Track change in manifest
    m = _read_manifest(root)
    changes = m.get('changes', [])
    changes.append({
        'filename':   filename,
        'agent':      written_by,
        'step':       step,
        'summary':    summary,
        'is_new':     old_content is None,
        'timestamp':  datetime.now().isoformat(),
    })
    _write_manifest(root, {**m, 'changes': changes})
    return dest

def file_exists(source_path: str, filename: str) -> bool:
    return (_managed_root(source_path) / SOURCE_DIR / filename).exists()

# ── Handoff document ────────────────────────────────────────────────────────────

def append_handoff(source_path: str, content: str):
    _append_handoff(_managed_root(source_path), content)

def get_handoff(source_path: str) -> str:
    p = _managed_root(source_path) / FRAUDE_DIR / 'handoff.md'
    return p.read_text('utf-8') if p.exists() else ''

def write_summary(source_path: str, content: str):
    p = _managed_root(source_path) / FRAUDE_DIR / 'summary.md'
    p.write_text(content, 'utf-8')

def get_summary(source_path: str) -> str:
    p = _managed_root(source_path) / FRAUDE_DIR / 'summary.md'
    return p.read_text('utf-8') if p.exists() else ''

# ── Audit ───────────────────────────────────────────────────────────────────────

def write_audit(source_path: str, name: str, content: str):
    p = _managed_root(source_path) / FRAUDE_DIR / 'audit' / name
    p.write_text(content, 'utf-8')

def read_audit(source_path: str, name: str) -> str:
    p = _managed_root(source_path) / FRAUDE_DIR / 'audit' / name
    return p.read_text('utf-8') if p.exists() else ''

# ── Diff & approval ─────────────────────────────────────────────────────────────

def get_diff(source_path: str) -> list:
    """
    Compare managed workspace to original source.
    Returns list of {filename, status, diff_text, is_new, lines_added, lines_removed}.
    """
    src  = Path(source_path).resolve()
    dest = _managed_root(source_path) / SOURCE_DIR
    results = []
    managed_files = list_files(source_path)

    for rel in managed_files:
        managed_f = dest / rel
        source_f  = src / rel
        managed_content = managed_f.read_text('utf-8', errors='replace')

        if not source_f.exists():
            results.append({
                'filename':       rel,
                'status':         'new',
                'diff_text':      '',
                'is_new':         True,
                'lines_added':    len(managed_content.splitlines()),
                'lines_removed':  0,
                'content':        managed_content,
            })
            continue

        source_content = source_f.read_text('utf-8', errors='replace')
        if managed_content == source_content:
            continue  # unchanged

        diff = list(difflib.unified_diff(
            source_content.splitlines(keepends=True),
            managed_content.splitlines(keepends=True),
            fromfile=f'original/{rel}',
            tofile=f'managed/{rel}',
            n=3,
        ))
        added   = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
        results.append({
            'filename':      rel,
            'status':        'modified',
            'diff_text':     ''.join(diff),
            'is_new':        False,
            'lines_added':   added,
            'lines_removed': removed,
        })

    # Deleted files (in source but not in managed)
    SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.venv'}
    for item in src.rglob('*'):
        if not item.is_file(): continue
        if any(p in item.parts for p in SKIP_DIRS): continue
        rel = str(item.relative_to(src))
        if not (dest / rel).exists():
            results.append({
                'filename':      rel,
                'status':        'deleted',
                'diff_text':     '',
                'is_new':        False,
                'lines_added':   0,
                'lines_removed': 0,
            })

    return results

def apply_changes(source_path: str, filenames: list = None) -> dict:
    """
    Copy approved files from managed workspace back to source.
    filenames=None means apply all changed files.
    Creates a timestamped backup of originals first.
    Returns {applied: [files], backup_path: str}.
    """
    src  = Path(source_path).resolve()
    dest = _managed_root(source_path) / SOURCE_DIR

    # Backup originals
    ts     = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = _appdata() / f'_backup_{src.name}_{ts}'
    backup.mkdir(parents=True, exist_ok=True)
    for item in src.rglob('*'):
        if item.is_file():
            rel = item.relative_to(src)
            b   = backup / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, b)

    # Apply changes
    diff    = get_diff(source_path)
    applied = []
    for entry in diff:
        fn = entry['filename']
        if filenames is not None and fn not in filenames:
            continue
        if entry['status'] in ('new', 'modified'):
            src_f = src / fn
            src_f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest / fn, src_f)
            applied.append(fn)
        elif entry['status'] == 'deleted':
            src_f = src / fn
            if src_f.exists(): src_f.unlink()
            applied.append(fn)

    # Update manifest
    m = _read_manifest(_managed_root(source_path))
    _write_manifest(_managed_root(source_path), {
        **m, 'status': 'applied', 'applied_at': datetime.now().isoformat(),
        'applied_files': applied,
    })

    return {'applied': applied, 'backup_path': str(backup)}

# ── Run & test ──────────────────────────────────────────────────────────────────

def run_file(source_path: str, filename: str, timeout: int = 30) -> dict:
    """Run a file inside the managed workspace and return {stdout, stderr, returncode}."""
    dest = _managed_root(source_path) / SOURCE_DIR
    path = dest / filename
    if not path.exists():
        return {'stdout': '', 'stderr': f'File not found: {filename}', 'returncode': 1}
    ext = path.suffix.lower()
    if ext == '.py':
        cmd = [sys.executable, str(path)]
    elif ext == '.js':
        cmd = ['node', str(path)]
    elif ext in ('.sh', '.bash'):
        cmd = ['bash', str(path)]
    else:
        return {'stdout': '', 'stderr': f'Cannot run {ext} files', 'returncode': 1}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=str(dest))
        return {'stdout': r.stdout[:4000], 'stderr': r.stderr[:2000], 'returncode': r.returncode}
    except subprocess.TimeoutExpired:
        return {'stdout': '', 'stderr': f'Timed out after {timeout}s', 'returncode': -1}
    except Exception as e:
        return {'stdout': '', 'stderr': str(e), 'returncode': 1}

def run_npm_audit(source_path: str) -> dict:
    """Run npm audit in the managed workspace if package.json exists."""
    dest = _managed_root(source_path) / SOURCE_DIR
    if not (dest / 'package.json').exists():
        return {'output': 'No package.json found.', 'vulnerabilities': []}
    try:
        r = subprocess.run(['npm', 'audit', '--json'],
                           capture_output=True, text=True, timeout=60, cwd=str(dest))
        try:
            d = json.loads(r.stdout)
            vulns = []
            for name, info in d.get('vulnerabilities', {}).items():
                vulns.append({
                    'package':   name,
                    'severity':  info.get('severity', 'unknown'),
                    'via':       [v if isinstance(v, str) else v.get('title', '') for v in info.get('via', [])],
                    'fixable':   bool(info.get('fixAvailable')),
                    'range':     info.get('range', ''),
                })
            return {'output': r.stdout, 'vulnerabilities': vulns, 'raw': d}
        except json.JSONDecodeError:
            return {'output': r.stdout or r.stderr, 'vulnerabilities': []}
    except FileNotFoundError:
        return {'output': 'npm not found.', 'vulnerabilities': []}
    except Exception as e:
        return {'output': str(e), 'vulnerabilities': []}

def run_pip_audit(source_path: str) -> dict:
    """Run pip-audit or safety check on requirements.txt."""
    dest = _managed_root(source_path) / SOURCE_DIR
    req  = dest / 'requirements.txt'
    if not req.exists():
        return {'output': 'No requirements.txt found.', 'vulnerabilities': []}
    try:
        r = subprocess.run(
            [sys.executable, '-m', 'pip_audit', '-r', str(req), '--format', 'json'],
            capture_output=True, text=True, timeout=60, cwd=str(dest))
        try:
            d = json.loads(r.stdout)
            vulns = [
                {'package': dep.get('name'), 'version': dep.get('version'),
                 'vulns': dep.get('vulns', [])}
                for dep in d.get('dependencies', [])
                if dep.get('vulns')
            ]
            return {'output': r.stdout, 'vulnerabilities': vulns}
        except json.JSONDecodeError:
            return {'output': r.stdout or r.stderr, 'vulnerabilities': []}
    except Exception as e:
        return {'output': str(e), 'vulnerabilities': []}

# ── MCP file server data (used by local_server.py) ─────────────────────────────

def get_mcp_context(source_path: str) -> dict:
    """Return all data needed for an MCP tool call response."""
    return {
        'files':      list_files(source_path),
        'handoff':    get_handoff(source_path),
        'summary':    get_summary(source_path),
        'manifest':   get_manifest(source_path),
        'diff_count': len(get_diff(source_path)),
    }

def get_manifest(source_path: str) -> dict:
    root = _managed_root(source_path)
    return _read_manifest(root)

def log_step(source_path: str, entry: dict):
    root = _managed_root(source_path)
    log  = _read_log(root)
    entry['timestamp'] = datetime.now().isoformat()
    log.append(entry)
    _write_log(root, log)

def get_log(source_path: str) -> list:
    return _read_log(_managed_root(source_path))

# ── Internal helpers ────────────────────────────────────────────────────────────
def _manifest_path(root: Path) -> Path:
    return root / FRAUDE_DIR / 'manifest.json'

def _read_manifest(root: Path) -> dict:
    p = _manifest_path(root)
    try: return json.loads(p.read_text('utf-8'))
    except: return {}

def _write_manifest(root: Path, data: dict):
    _manifest_path(root).write_text(json.dumps(data, indent=2), 'utf-8')

def _log_path(root: Path) -> Path:
    return root / FRAUDE_DIR / 'pipeline_log.json'

def _read_log(root: Path) -> list:
    p = _log_path(root)
    try: return json.loads(p.read_text('utf-8'))
    except: return []

def _write_log(root: Path, data: list):
    _log_path(root).write_text(json.dumps(data, indent=2), 'utf-8')

def _append_handoff(root: Path, content: str):
    p = root / FRAUDE_DIR / 'handoff.md'
    existing = p.read_text('utf-8') if p.exists() else ''
    p.write_text(existing + content, 'utf-8')
