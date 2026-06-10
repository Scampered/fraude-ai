"""
workspace.py — Fraude Orchestrator Workspace Manager
Manages project directories, manifest, handoffs, contracts, and logs.
"""
import json, shutil
from datetime import datetime
from pathlib import Path

FRAUDE_DIR = '.fraude'

# ── Init ───────────────────────────────────────────────────────────────────────
def init_workspace(dir_path: str, project_name: str, project_type: str) -> Path:
    root = Path(dir_path)
    root.mkdir(parents=True, exist_ok=True)
    fraude = root / FRAUDE_DIR
    (fraude / 'handoffs').mkdir(parents=True, exist_ok=True)
    (fraude / 'audit').mkdir(parents=True, exist_ok=True)

    manifest = {
        'project_name': project_name,
        'project_type': project_type,
        'created_at':   datetime.now().isoformat(),
        'status':       'in_progress',
        'files':        [],
        'steps':        [],
    }
    mf = fraude / 'manifest.json'
    if not mf.exists():
        mf.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    log = fraude / 'pipeline_log.json'
    if not log.exists():
        log.write_text('[]', encoding='utf-8')

    return root

def get_manifest(dir_path: str) -> dict:
    p = Path(dir_path) / FRAUDE_DIR / 'manifest.json'
    if not p.exists():
        return {}
    return json.loads(p.read_text('utf-8'))

def update_manifest(dir_path: str, updates: dict):
    p = Path(dir_path) / FRAUDE_DIR / 'manifest.json'
    m = get_manifest(dir_path)
    m.update(updates)
    p.write_text(json.dumps(m, indent=2), encoding='utf-8')

def write_file(dir_path: str, filename: str, content: str, written_by: str, step: int) -> Path:
    root = Path(dir_path)
    dest = root / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding='utf-8')

    m = get_manifest(dir_path)
    files = m.get('files', [])
    # Update or append
    for f in files:
        if f['filename'] == filename:
            f['last_updated'] = datetime.now().isoformat()
            f['written_by']   = written_by
            break
    else:
        files.append({
            'filename':     filename,
            'written_by':   written_by,
            'step':         step,
            'summary':      '',
            'last_updated': datetime.now().isoformat(),
        })
    update_manifest(dir_path, {'files': files})
    return dest

def read_file(dir_path: str, filename: str) -> str:
    return (Path(dir_path) / filename).read_text('utf-8', errors='replace')

def list_files(dir_path: str) -> list:
    root = Path(dir_path)
    return sorted(
        str(f.relative_to(root))
        for f in root.rglob('*')
        if f.is_file() and FRAUDE_DIR not in f.parts
    )

def write_handoff(dir_path: str, step: int, content: str):
    p = Path(dir_path) / FRAUDE_DIR / 'handoffs' / f'step_{step}.md'
    p.write_text(content, encoding='utf-8')

def get_handoff(dir_path: str, step: int) -> str:
    p = Path(dir_path) / FRAUDE_DIR / 'handoffs' / f'step_{step}.md'
    return p.read_text('utf-8') if p.exists() else ''

def write_contract(dir_path: str, content: dict):
    p = Path(dir_path) / FRAUDE_DIR / 'contract.json'
    p.write_text(json.dumps(content, indent=2), encoding='utf-8')

def get_contract(dir_path: str) -> dict:
    p = Path(dir_path) / FRAUDE_DIR / 'contract.json'
    return json.loads(p.read_text('utf-8')) if p.exists() else {}

def log_step(dir_path: str, entry: dict):
    p = Path(dir_path) / FRAUDE_DIR / 'pipeline_log.json'
    try:
        log = json.loads(p.read_text('utf-8'))
    except Exception:
        log = []
    entry['timestamp'] = datetime.now().isoformat()
    log.append(entry)
    p.write_text(json.dumps(log, indent=2), encoding='utf-8')

def write_audit(dir_path: str, name: str, content: str):
    p = Path(dir_path) / FRAUDE_DIR / 'audit' / name
    p.write_text(content, encoding='utf-8')

def read_audit(dir_path: str, name: str) -> str:
    p = Path(dir_path) / FRAUDE_DIR / 'audit' / name
    return p.read_text('utf-8') if p.exists() else ''

def has_workspace(dir_path: str) -> bool:
    return (Path(dir_path) / FRAUDE_DIR / 'manifest.json').exists()

def get_log(dir_path: str) -> list:
    p = Path(dir_path) / FRAUDE_DIR / 'pipeline_log.json'
    try: return json.loads(p.read_text('utf-8'))
    except: return []
