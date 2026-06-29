#!/usr/bin/env python3
"""FraudeCode v2.3 — run with: python fraudecode.py"""
import os, sys, re, subprocess, signal, shutil

# readline (cross-platform)
try:
    import readline as _rl; HAS_RL = True
except ImportError:
    try: import pyreadline3 as _rl; HAS_RL = True  # type: ignore
    except ImportError: _rl = None; HAS_RL = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fraudecode_pkg.colours  import *
from fraudecode_pkg.config   import load, save, first_run, CODE_DIR, run_setup
from fraudecode_pkg.ui       import BANNER, MINI, clear_screen, Spinner
from fraudecode_pkg.agents   import (run as run_pipeline, set_config, get_plan,
                                     PLAN_LABELS, cancel as cancel_pipeline,
                                     call_ollama, set_lockin, get_lockin,
                                     set_plan_override)
from fraudecode_pkg.session  import Session, PY
from fraudecode_pkg.commands import (
    show_help, list_files, view_file, open_file, delete_file, search_files,
    ship_workspace, install_pkg, edit_file, export_file, run_file_cmd, import_file,
    hide_path, run_pentest, PENTEST_TYPES,
)
from pathlib import Path
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────
_cfg = load()
if not _cfg:
    _cfg = first_run()

# Fix ollamaUrl if it was stored as a model name instead of a URL
_ollama_url = _cfg.get('ollamaUrl', '')
if not _ollama_url or not _ollama_url.startswith('http'):
    _cfg['ollamaUrl'] = 'http://localhost:11434'

set_config(_cfg)

# ── Tab completion ─────────────────────────────────────────────────────────────
CMDS = ['/help','/plan','/agent','/files','/run','/open','/edit','/delete',
        '/search','/history','/install','/venv','/clone','/requirements',
        '/save','/rename','/file-rename','/ext-rename','/chats','/newchat',
        '/home','/clear','/ship','/doc','/config','/download','/export',
        '/stop','/diagnose','/audit','/audit-fix','/hide','/unhide','/pentest','/operate','/repo','/exit','/quit','/lockin','/setup',
        '/web','/cd','/back','/pwd','/cleanup']
_file_cache: list = []
_folder_cache: list = []
_cwd_override: Path = None

def _refresh(session=None):
    global _file_cache, _folder_cache
    _file_cache = []; _folder_cache = []
    if session:
        root = _effective_cwd(session)
        SKIP = {'.venv','venv','__pycache__','node_modules','.git'}
        try:
            for f in root.iterdir():
                if f.is_file() and not f.name.startswith('.') and not any(j in f.parts for j in SKIP):
                    _file_cache.append(f.name)
                elif f.is_dir() and f.name not in SKIP and not f.name.startswith('.'):
                    _folder_cache.append(f.name + '/')
        except Exception:
            pass

def _effective_cwd(session) -> Path:
    global _cwd_override
    if _cwd_override and _cwd_override.is_dir():
        return _cwd_override
    return session.workdir

def _completer(text, state):
    try:
        if HAS_RL and _rl:
            buf = _rl.get_line_buffer()
        else:
            buf = text
        parts = buf.strip().split()
        cmd = parts[0].lower() if parts else ''
        # Context-aware: after /cd or navigation → folders
        nav_cmds = ('/cd','/folder','/back')
        file_cmds = ('/open','/run','/edit','/delete','/export','/file-rename','/ext-rename','/import')
        if cmd in nav_cmds and (len(parts) > 1 or buf.endswith(' ')):
            query = parts[1] if len(parts) > 1 else ''
            opts = [f for f in _folder_cache if f.startswith(query)]
        elif cmd in file_cmds and (len(parts) > 1 or buf.endswith(' ')):
            query = parts[1] if len(parts) > 1 else ''
            opts = [f for f in (_file_cache + _folder_cache) if f.startswith(query)]
        elif text.startswith('/'):
            opts = [x for x in CMDS if x.startswith(text)]
        else:
            opts = [f for f in (_file_cache + _folder_cache) if f.startswith(text)]
        return opts[state] if state < len(opts) else None
    except Exception:
        return None

if HAS_RL and _rl:
    try:
        _rl.set_completer(_completer)
        _rl.set_completer_delims(' \t\n')
        _rl.parse_and_bind('tab: complete')
    except Exception: pass

def rl_hist(t):
    if HAS_RL and _rl:
        try: _rl.add_history(t)
        except Exception: pass

# ── Plan display ───────────────────────────────────────────────────────────────
def show_plan():
    plan = get_plan()
    ok = c('✓', GRN); no = c('✗', RED)
    print(f"""
  {bold('Plan & Agents')}
  {c('Plan',  GRY)}    {c(PLAN_LABELS[plan], ACC)}
  {c('Groq',  GRY)}    {ok+' '+_cfg.get('groqModel','') if _cfg.get('groqKey') else no+' not set (add in Fraude web Settings)'}
  {c('Gemini',GRY)}  {ok+' '+_cfg.get('geminiModel','') if _cfg.get('geminiKey') else no+' not set (add in Fraude web Settings)'}
  {c('Ollama',GRY)}  {ok} {_cfg.get('ollamaUrl','')} / {_cfg.get('ollamaModel','')}
  {c('Python',GRY)}  {ok} {PY} ({sys.version.split()[0]})
""")

# ── Agent switch ───────────────────────────────────────────────────────────────
def do_agent(args):
    if not args: show_plan(); return
    mode = args[0].lower()
    valid_plans = {
        'max': 'max', 'oops': 'max', 'oops07': 'max',
        'oops06': 'oops06',
        'pro': 'pro', 'somenet': 'pro', 'somenet06': 'pro',
        'somenet05': 'pro05', 'pro05': 'pro05',
        'free': 'free', 'highku': 'free', 'local': 'free',
    }
    if mode not in valid_plans:
        print(c('  Usage: /agent [max|oops06|pro|somenet05|free]', YLW))
        print(f"  {GRY}max=Gemini+Groq+Ollama  oops06=Gemini+Ollama  pro=Groq+Ollama  somenet05=GroqOnly  free=OllamaOnly{R}")
        return
    plan_key = valid_plans[mode]
    # Check required keys for the requested plan
    has_smart = bool(_cfg.get('geminiKey','').strip() or _cfg.get('openrouterKey','').strip())
    has_groq  = bool(_cfg.get('groqKey','').strip())
    if plan_key in ('max', 'oops06') and not has_smart:
        print(c('  Gemini or OpenRouter key required — add in /setup or Fraude web Settings', YLW)); return
    if plan_key in ('max', 'pro', 'pro05') and not has_groq:
        print(c('  Groq key required — add in /setup or Fraude web Settings', YLW)); return
    # Use set_plan_override — never blanks keys, pipeline branches by plan string
    set_plan_override(plan_key)
    print(c(f'  Agent: {PLAN_LABELS[plan_key]}', GRN))


# ── Doc generator ──────────────────────────────────────────────────────────────
def generate_doc(session, doc_type='readme'):
    files = session.list_files()
    if not files: print(c('  No files to document.', YLW)); return
    ctx = ''
    for f in files[:10]:
        try: ctx += f'\n\n# {f.name}\n' + f.read_text('utf-8',errors='replace')[:2000]
        except Exception: pass
    fname = 'README.md' if 'readme' in doc_type.lower() else 'HANDOFF.md'
    prompt = f"Generate {fname} for this project:\n{ctx}"
    print(f"\n  {GRY}Generating {fname}…{R}")
    result = run_pipeline(prompt)
    content = result.code or result.explanation or ''
    m = re.search(r'```(?:markdown|md)?\n([\s\S]*?)```', content)
    if m: content = m.group(1)
    if content:
        dest = session.workdir / fname
        dest.write_text(content, encoding='utf-8')
        print(c(f'\n  ✓ Written: {fname}', GRN))
    else:
        print(c('  Failed.', RED))

# ── Diagnose ───────────────────────────────────────────────────────────────────
def diagnose(session, error: str, file_path=None):
    print(f"\n  {c('[diagnosing]', ACC)}")
    ctx = f"Error:\n{error}"
    if file_path and Path(str(file_path)).exists():
        try: ctx += f"\n\nCode:\n{Path(str(file_path)).read_text('utf-8',errors='replace')[:3000]}"
        except Exception: pass
    result = run_pipeline(f"Diagnose and fix:\n{ctx}")
    _print_result(result.code, result.explanation)
    for lang, blk in _extract(result.code or ''):
        dest = session.save_code(lang, blk)
        print(c(f'  💾 Fixed: {dest.name}', GRN))

# ── Cleanup junk files ─────────────────────────────────────────────────────────
JUNK_DIRS  = {'.git', '__pycache__', 'node_modules', '.pytest_cache',
              '.mypy_cache', 'dist', 'build', '.next', '.nuxt', 'target'}
JUNK_EXTS  = {'.pyc', '.pyo', '.pyd', '.class', '.o', '.obj', '.log', '.DS_Store',
              '.swp', '.swo', '~', '.bak', '.tmp'}
JUNK_NAMES = {'.DS_Store', 'Thumbs.db', 'desktop.ini', '.gitkeep'}

def cleanup_workspace(session, dry_run=False):
    root = session.workdir
    removed = []
    skipped = []
    total_bytes = 0
    for p in sorted(root.rglob('*')):
        if not p.exists(): continue
        rel = p.relative_to(root)
        parts = rel.parts
        # Never touch .venv — it's managed by the session
        if '.venv' in parts or 'venv' in parts:
            continue
        # Skip if inside already-marked junk dir
        if any(part in JUNK_DIRS for part in parts[:-1]):
            continue
        is_junk = (
            p.name in JUNK_NAMES or
            p.suffix in JUNK_EXTS or
            (p.is_dir() and p.name in JUNK_DIRS)
        )
        if is_junk:
            try:
                size = sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) if p.is_dir() else p.stat().st_size
                total_bytes += size
                removed.append((str(rel), size))
                if not dry_run:
                    if p.is_dir():
                        def _on_err(fn, path, exc):
                            import stat as _stat
                            try:
                                os.chmod(path, _stat.S_IWRITE)
                                fn(path)
                            except Exception: pass
                        shutil.rmtree(p, onerror=_on_err)
                    else:
                        try: p.unlink()
                        except PermissionError:
                            import stat as _stat
                            os.chmod(p, _stat.S_IWRITE); p.unlink()
            except Exception as e:
                skipped.append((str(rel), str(e)))
    # Deduplicate: find files with same name+size in same dir
    seen = {}
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        key = (p.parent, p.name, p.stat().st_size if p.exists() else 0)
        if key in seen:
            rel = str(p.relative_to(root))
            removed.append((rel + ' (duplicate)', p.stat().st_size))
            total_bytes += p.stat().st_size
            if not dry_run:
                try: p.unlink()
                except Exception as e: skipped.append((rel, str(e)))
        else:
            seen[key] = p
    prefix = dim('Would remove') if dry_run else c('Removed', GRN)
    if removed:
        print(f"\n  {prefix} {len(removed)} items ({total_bytes//1024}KB):")
        for name, size in removed[:20]:
            print(f"  {c('·',RED)} {name} {dim(str(size)+'B')}")
        if len(removed) > 20:
            print(f"  {GRY}  … and {len(removed)-20} more{R}")
    else:
        print(c('  Workspace is already clean!', GRN))
    if skipped:
        print(f"\n  {c('Skipped (permission denied):',YLW)}")
        for name, err in skipped:
            print(f"  {c('·',YLW)} {name}: {err}")
    if dry_run and removed:
        confirm = input(f"\n  {c('Remove all?',YLW)} [Y/n]: ").strip().lower()
        if confirm in ('','y','yes'):
            cleanup_workspace(session, dry_run=False)
    elif not dry_run:
        _refresh(session)

# ── Natural language ───────────────────────────────────────────────────────────
NL = {
    'directory list': lambda s: list_files(s),
    'directory':      lambda s: print(f"\n  {c('Workspace:',ACC)} {s.workdir}\n"),
    'package list':   lambda s: subprocess.run([s.ensure_venv(log=False),'-m','pip','list']),
    'make readme':    lambda s: generate_doc(s, 'readme'),
    'make doc':       lambda s: generate_doc(s, 'readme'),
    'make handoff':   lambda s: generate_doc(s, 'handoff'),
    'ship it':        lambda s: ship_workspace(s),
    'list files':     lambda s: list_files(s),
    'clean up':       lambda s: cleanup_workspace(s, dry_run=True),
    'cleanup':        lambda s: cleanup_workspace(s, dry_run=True),
}

def check_nl(text: str, session) -> bool:
    tl = text.lower().strip()
    for phrase, fn in NL.items():
        if phrase in tl:
            fn(session)
            return True

    # Natural language → slash command suggestions
    # "run money manager" → find file and run it
    run_match = re.match(r'^run\s+(.+)', tl)
    if run_match:
        query = run_match.group(1).strip()
        matches = _find_files(session, query)
        if matches:
            print(c(f'  Running: {matches[0].name}', GRN))
            res = run_file_cmd(session, matches[0].name, [matches[0]])
            if res and res.get('diagnose'):
                diagnose(session, res['error'], res.get('file'))
        else:
            print(c(f'  No file matching "{query}" found. Use /files to list.', YLW))
        return True

    # "open money manager" / "show money manager"
    open_match = re.match(r'^(?:open|show|view)\s+(.+)', tl)
    if open_match:
        query = open_match.group(1).strip()
        matches = _find_files(session, query)
        if matches:
            open_file(session, matches[0].name)
        else:
            print(c(f'  No file matching "{query}" found.', YLW))
        return True

    return False

def _find_files(session, query: str) -> list:
    """Fuzzy-find files in workspace matching a natural language query."""
    root = _effective_cwd(session)
    query_parts = query.lower().replace('-',' ').replace('_',' ').split()
    results = []
    for p in root.rglob('*'):
        if p.is_file() and not any(junk in p.parts for junk in JUNK_DIRS):
            name_lower = p.name.lower().replace('-',' ').replace('_',' ')
            if all(part in name_lower for part in query_parts):
                results.append(p)
    return sorted(results, key=lambda p: len(p.name))

# ── Output ─────────────────────────────────────────────────────────────────────
def _extract(text: str) -> list:
    return [(m.group(1), m.group(2).strip())
            for m in re.finditer(r'```(\w+)\n([\s\S]*?)```', text)]

def _render_md(text: str) -> str:
    """Convert markdown to ANSI-styled terminal text. Strips ** and applies bold."""
    import re as _re
    out = []
    for ln in text.split('\n'):
        s = ln.lstrip()
        # Headings
        if s.startswith('### '): out.append(f"  {bold(s[4:].strip())}"); continue
        if s.startswith('## '):  out.append(f"  {bold(s[3:].strip())}"); continue
        if s.startswith('# '):   out.append(f"  {bold(s[2:].strip())}"); continue
        # Bullet points
        if s.startswith(('- ','* ','· ')):
            body = s[2:]
            # Apply inline bold within bullet body
            body = _re.sub(r'\*\*(.+?)\*\*', lambda m: bold(m.group(1)), body)
            body = _re.sub(r'`(.+?)`', lambda m: c(m.group(1), CYN), body)
            out.append(f"  {c('·', ACC)} {body}")
            continue
        # Regular line — apply inline bold/code
        ln2 = _re.sub(r'\*\*(.+?)\*\*', lambda m: bold(m.group(1)), ln)
        ln2 = _re.sub(r'`(.+?)`', lambda m: c(m.group(1), CYN), ln2)
        out.append(f"  {ln2}")
    return '\n'.join(out)

def _print_result(code: str, explanation: str):
    sep = c('─'*64, GRY)
    print(f"\n{sep}")

    # Pure explanation (no code) — render as markdown text
    if explanation and not code:
        print()
        print(_render_md(explanation))

    # Code blocks
    if code:
        blocks = _extract(code)
        if blocks:
            for lang, blk in blocks:
                fm = re.search(r'^[#/]{1,2}\s*FILE:\s*(.+)', blk, re.MULTILINE)
                fname = fm.group(1).strip() if fm else f'output.{lang}'
                lines = blk.split('\n')
                print(f"\n  {c('FILE:', ACC)} {bold(fname)}  {dim(f'({len(lines)} lines)')}")
                for ln in lines[:35]:
                    print(f"  {c(ln, CYN)}")
                if len(lines) > 35:
                    print(f"  {GRY}  … {len(lines)-35} more lines (saved){R}")
        else:
            # Raw text in code field — render as markdown
            print()
            print(_render_md(code))

    # Explanation as supplement when there's also code
    if explanation and code:
        print()
        print(_render_md(explanation))

    print(f"\n{sep}\n")

# ── File rename helpers ────────────────────────────────────────────────────────
def file_rename(session, args: list, change_ext=False):
    """Rename a file keeping extension (or changing it with change_ext=True)."""
    if len(args) < 2:
        usage = '/file-rename <old> <new_name>  (extension kept automatically)' if not change_ext else '/ext-rename <file> <new_ext>  (e.g. /ext-rename file.py .txt)'
        print(c(f'  Usage: {usage}', YLW)); return
    root = _effective_cwd(session)
    old_name = args[0]
    new_arg  = args[1]

    # Resolve source
    src = root / old_name
    if not src.exists():
        matches = _find_files(session, old_name)
        if matches: src = matches[0]
        else: print(c(f'  File not found: {old_name}', RED)); return

    if change_ext:
        # /ext-rename: change the extension
        new_ext = new_arg if new_arg.startswith('.') else '.'+new_arg
        # Warn if extension looks unusual (typo check)
        common_exts = {'.py','.js','.ts','.html','.css','.json','.txt','.md','.csv','.sh','.bat','.yml','.yaml','.xml','.sql','.r','.rb','.go','.rs','.cpp','.c','.h','.java','.kt'}
        if new_ext not in common_exts and len(new_ext) > 5:
            confirm = input(f"  {YLW}Unusual extension '{new_ext}'. Sure? [y/N]{R}: ").strip().lower()
            if confirm not in ('y','yes'): print(c('  Cancelled.', GRY)); return
        dst = src.with_suffix(new_ext)
    else:
        # /file-rename: keep the original extension
        # Strip any extension the user accidentally included in the new name
        new_stem = new_arg
        if '.' in new_arg:
            # User included an extension — check if it matches original
            provided_ext = Path(new_arg).suffix
            if provided_ext != src.suffix:
                confirm = input(f"  {YLW}New name has extension '{provided_ext}' but original is '{src.suffix}'. Keep '{provided_ext}'? [y/N]{R}: ").strip().lower()
                if confirm in ('y','yes'):
                    # Use exactly what they typed
                    dst = src.parent / new_arg
                else:
                    # Strip extension, keep original
                    new_stem = Path(new_arg).stem
                    dst = src.parent / (new_stem + src.suffix)
            else:
                # Same extension — use as-is but don't double it
                dst = src.parent / new_arg
        else:
            # No extension in new name — keep original extension (normal case)
            dst = src.parent / (new_stem + src.suffix)

    if dst.exists():
        confirm = input(f"  {YLW}{dst.name} already exists. Overwrite? [y/N]{R}: ").strip().lower()
        if confirm not in ('y','yes'): print(c('  Cancelled.', GRY)); return
    src.rename(dst)
    print(c(f'  Renamed: {src.name} → {dst.name}', GRN))
    _refresh(session)

# ── Export fix: handle directories ─────────────────────────────────────────────
def export_path(session, target: str):
    """Export a file or directory to Downloads. Zips directories automatically."""
    root = session.workdir
    src = root / target
    if not src.exists():
        matches = _find_files(session, target)
        if matches: src = matches[0]
        else: print(c(f'  Not found: {target}', RED)); return
    downloads = Path.home() / 'Downloads'
    downloads.mkdir(exist_ok=True)
    if src.is_dir():
        zip_path = downloads / (src.name + '.zip')
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in src.rglob('*'):
                if f.is_file() and not any(j in f.parts for j in JUNK_DIRS):
                    zf.write(f, f.relative_to(src))
        print(c(f'  Exported (zipped): {zip_path}', GRN))
    else:
        dst = downloads / src.name
        shutil.copy2(src, dst)
        print(c(f'  Exported: {dst}', GRN))

# ── Dashboard ──────────────────────────────────────────────────────────────────
def dashboard() -> Session:
    while True:
        sessions = Session.all()
        clear_screen()
        print(BANNER)
        print(f"\n  {bold('Chats')}  {dim('select a chat or start new')}\n")
        if sessions:
            for i, s in enumerate(sessions, 1):
                turns = len([m for m in s.history if m['role']=='user'])
                repo  = dim(f'  {s.repo_url[:28]}') if s.repo_url else ''
                print(f"  {c(str(i),ACC)}  {WHT}{s.name:<40}{R} {GRY}{turns} msgs{R}{repo}")
        else:
            print(f"  {GRY}No saved chats yet.{R}")
        print(f"\n  {dim('Plan: '+PLAN_LABELS[get_plan()])}")
        print(f"  {GRY}Number to open · N new chat · D <n> delete · Q quit{R}\n")
        try:
            ans = input(f"  {c('>',ACC)} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(c('\n  Bye!',GRY)); sys.exit(0)
        al = ans.lower()
        if al in ('q','quit'): print(c('\n  Bye!',GRY)); sys.exit(0)
        if al == 'n':
            name = input(f"  {c('Name',ACC)} {GRY}(Enter for auto): {R}").strip()
            s = Session()
            if name: s.name = name
            return s
        dm = re.match(r'^d\s*(\d+)$', al)
        if dm:
            idx = int(dm.group(1)) - 1
            if sessions and 0 <= idx < len(sessions):
                target = sessions[idx]
                confirm = input(f"  {YLW}Delete \"{target.name}\"? [Y/n]{R}: ").strip().lower()
                if confirm in ('','y','yes'):
                    target.path.unlink(missing_ok=True)
                    print(c(f'  Deleted "{target.name}"',GRN))
                    import time; time.sleep(0.6)
            else:
                print(c(f'  Invalid number',YLW))
            continue
        if ans.isdigit():
            idx = int(ans) - 1
            if sessions and 0 <= idx < len(sessions):
                return sessions[idx]
            print(c(f'  Enter 1-{len(sessions)}', YLW))

# ── Cancel ─────────────────────────────────────────────────────────────────────
def _sigint(sig, frame):
    cancel_pipeline()
    print(c('\n  Cancelled. Press Enter.', YLW))

# ── System prompt for AI ───────────────────────────────────────────────────────
def _make_system_prompt(session, user_input: str = '', last_run_output: str = '') -> str:
    cwd = _effective_cwd(session)
    SKIP = {'.venv','venv','__pycache__','node_modules','.git'}
    max_files = 10 if get_plan() == 'free' else 30
    all_files = [str(p.relative_to(session.workdir)) for p in session.workdir.rglob('*')
                 if p.is_file() and not any(j in p.parts for j in SKIP)][:max_files]
    file_list = '\n'.join(f'  - {f}' for f in all_files) if all_files else '  (empty)'

    # Inject file contents — but limit to small files for Ollama (HighKu is slow with large context)
    is_free_plan = get_plan() == 'free'
    max_file_chars = 800 if is_free_plan else 4000
    injected_files = ''
    if user_input:
        user_lower = user_input.lower()
        for p in cwd.rglob('*'):
            if p.is_file() and not any(j in p.parts for j in SKIP):
                rel = str(p.relative_to(session.workdir))
                name_clean = p.name.lower().replace('$','').replace('-',' ').replace('_',' ')
                if (p.name.lower() in user_lower or
                    name_clean in user_lower or
                    rel.lower() in user_lower or
                    any(word in user_lower for word in name_clean.split() if len(word) > 3)):
                    try:
                        content = p.read_text('utf-8', errors='replace')
                        injected_files += f'\n\n--- Contents of {rel} ---\n{content[:max_file_chars]}\n--- End of {rel} ---'
                    except Exception:
                        pass

    run_ctx = f'\n\nLAST RUN OUTPUT (use this if the user asks about errors or results):\n{last_run_output}' if last_run_output else ''
    return f"""You are FraudeCode, an expert coding assistant in a terminal.
WORKSPACE: {session.workdir}
CURRENT FOLDER: {cwd}
WORKSPACE FILES:
{file_list}{injected_files}{run_ctx}

IMPORTANT: USE the file contents provided above — do NOT ask the user to share code again.
If the user asks to fix an error from the last run, use the LAST RUN OUTPUT above.
Suggest slash commands when appropriate. Be direct and concise."""

# ── REPL ───────────────────────────────────────────────────────────────────────
def repl(session: Session):
    global _cwd_override
    _cwd_override = None
    _refresh(session)
    session.ensure_venv()
    session.run_requirements()
    _last_error: dict = {}
    _last_run_output: str = ''

    while True:
        cwd = _effective_cwd(session)
        cwd_display = str(cwd.relative_to(session.workdir)) if cwd != session.workdir else ''
        cwd_suffix = c(f'/{cwd_display}', CYN) if cwd_display else ''
        try:
            lockin_indicator = c(' ⚡',YLW) if get_lockin() else ''
            inp = input(f"{c(session.name,GRY)}{cwd_suffix}{lockin_indicator}{c(' ❯ ',ACC)}").strip()
        except KeyboardInterrupt:
            print(); continue
        except EOFError:
            print(c('\n  Bye!',GRY)); break
        if not inp: continue
        rl_hist(inp)

        parts = inp.split()
        cmd   = parts[0].lower()
        args  = parts[1:]

        # ── Slash commands ──────────────────────────────────────────────────
        if cmd in ('/exit','/quit'):
            print(c('  Bye!',GRY)); break

        elif cmd == '/repo':
            import webbrowser as _wb
            _wb.open('http://localhost:7862')
            print(c('  Opened FraudeRepo in browser → http://localhost:7862', GRN))

        elif cmd == '/web':
            import webbrowser, ctypes
            url = 'https://fraude-ai.vercel.app/code'
            print(c(f'  Opening {url} ...', GRN))
            webbrowser.open(url)
            try:
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd: ctypes.windll.user32.ShowWindow(hwnd, 6)
            except Exception: pass
            print(c('  Web UI opened. Type /web again to restore this window.', GRY))

        elif cmd == '/help':
            show_help(' '.join(args) if args else '')

        elif args and args[-1].lower() in ('help','?'):
            show_help(cmd.lstrip('/'))

        elif cmd in ('/plan','/agent'):
            if cmd == '/plan' and not args: show_plan()
            else:
                do_agent(args if cmd == '/agent' else [])
                # Persist the agent choice to this session
                session.agent_override = get_plan()
                session.save()

        elif cmd == '/clear':
            clear_screen(); print(MINI+'\n')

        elif cmd == '/pwd':
            print(f"\n  {c('Current folder:',ACC)} {_effective_cwd(session)}\n")

        elif cmd in ('/cd', '/folder'):
            if not args:
                print(c('  Usage: /cd <folder>  or  /cd ..  to go up', YLW)); continue
            target = ' '.join(args)
            if target == '..':
                # go up
                current = _effective_cwd(session)
                if current != session.workdir:
                    _cwd_override = current.parent if current.parent >= session.workdir else session.workdir
                    print(c(f'  ↑ {_effective_cwd(session).relative_to(session.workdir) or "(workspace root)"}', GRN))
                else:
                    print(c('  Already at workspace root.', YLW))
            else:
                candidate = _effective_cwd(session) / target
                if not candidate.is_dir():
                    # try case-insensitive search
                    matches = [p for p in _effective_cwd(session).iterdir()
                               if p.is_dir() and p.name.lower() == target.lower()]
                    if matches: candidate = matches[0]
                    else:
                        print(c(f'  Folder not found: {target}', RED)); continue
                _cwd_override = candidate
                _refresh(session)  # updates _folder_cache and _file_cache from new cwd
                print(c(f'  → {candidate.relative_to(session.workdir)}', GRN))

        elif cmd in ('/back',):
            current = _effective_cwd(session)
            if current != session.workdir:
                _cwd_override = current.parent if current.parent >= session.workdir else None
                print(c(f'  ↑ {_effective_cwd(session).relative_to(session.workdir) or "(workspace root)"}', GRN))
            else:
                print(c('  Already at workspace root.', YLW))

        elif cmd in ('/home','/chats'):
            session.save()
            new_s = dashboard()
            session.__dict__.update(new_s.__dict__)
            _cwd_override = None
            clear_screen(); print(MINI+'\n')
            print(c(f'  Opened: {session.name}\n',GRN))
            session.ensure_venv(); session.run_requirements(); _refresh(session)

        elif cmd == '/newchat':
            session.save()
            name = ' '.join(args) if args else ''
            ns = Session()
            if name: ns.name = name
            session.__dict__.update(ns.__dict__)
            _cwd_override = None
            clear_screen(); print(MINI+'\n')
            print(c(f'  New chat: {session.name}\n',GRN))
            session.ensure_venv(); _refresh(session)

        elif cmd == '/rename':
            # Session rename (no args = show usage, args = rename session)
            if not args: print(c('  Usage: /rename <new session name>  |  /file-rename <old> <new>',YLW)); continue
            session.name = ' '.join(args)
            session.save()
            print(c(f'  Session renamed to "{session.name}"',GRN))

        elif cmd == '/file-rename':
            file_rename(session, args, change_ext=False)

        elif cmd == '/ext-rename':
            file_rename(session, args, change_ext=True)

        elif cmd == '/save':
            if args: session.name = ' '.join(args)
            session.save()
            print(c(f'  Saved as "{session.name}"',GRN))

        elif cmd == '/files':
            pat = args[0] if args else '*'
            cwd = _effective_cwd(session)
            # 'folders' or 'folder' arg: show only directories
            if pat.lower() in ('folder', 'folders'):
                list_files(session, 'folders')
                continue
            # If in a subdirectory, list only that dir; otherwise recurse from workspace
            if cwd != session.workdir:
                # In a subfolder: show just this folder's files (non-recursive by default)
                from fraudecode_pkg.commands import list_files as _lf
                import os
                SKIP = {'.venv','venv','__pycache__','node_modules','.git'}
                files = sorted(f for f in cwd.rglob('**/*' if pat.startswith('*.') else f'**/{pat}*' if pat != '*' else '*')
                    if f.is_file() and not any(j in f.parts for j in SKIP) and not f.name.startswith('.'))
                if pat != '*' and pat.startswith('*.'):
                    files = [f for f in cwd.rglob(f'**/{pat}') if f.is_file() and not any(j in f.parts for j in SKIP)]
                elif pat == '*':
                    # Show both files and subdirectories when in a subfolder
                    SKIP2 = {'.venv','venv','__pycache__','node_modules','.git'}
                    entries = sorted(cwd.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                    dirs2  = [e for e in entries if e.is_dir() and e.name not in SKIP2 and not e.name.startswith('.')]
                    files  = [e for e in entries if e.is_file() and not e.name.startswith('.')]
                    if dirs2:
                        print(f"\n  {bold('Subfolders')}  {dim(str(cwd))}\n")
                        for d in dirs2: print(f"  {c('📁', ACC)} {c(d.name+'/', ACC)}")
                        print()
                    if not files and not dirs2: files = []  # triggers no-files message
                if not files:
                    print(c('  No files.\n', GRY))
                else:
                    print(f"\n  {bold('Folder')}  {dim(str(cwd))}\n")
                    for i,f in enumerate(files,1):
                        print(f"  {c(str(i),GRY)}  {c(f.name,WHT):<48} {GRY}{f.stat().st_size:,}B{R}")
                    print()
            else:
                if pat.startswith('*.'):
                    glob_pat = f'**/{pat}'
                elif '.' in pat and not pat.startswith('*'):
                    glob_pat = f'**/*{pat}*'
                else:
                    glob_pat = '**/*'
                list_files(session, glob_pat)

        elif cmd == '/run':
            fname = ' '.join(args) if args else ''
            if not fname:
                print(c('  Usage: /run <file>',YLW)); continue
            # Search in effective cwd first, then whole workspace
            p = _effective_cwd(session) / fname
            if not p.exists():
                matches = _find_files(session, fname)
                if matches: fname = str(matches[0].relative_to(session.workdir))
            res = run_file_cmd(session, fname, session.last_files)
            if res and res.get('diagnose'):
                _last_error = res
                diagnose(session, res['error'], res.get('file'))

        elif cmd == '/open':
            if args:
                # /open <file> [app]   — optional app: notepad, vscode, browser, nano, vim, etc.
                app_name = None
                fname_parts = list(args)
                known_apps = {'notepad','code','vscode','browser','nano','vim','explorer','subl','atom','notepad++'}
                if len(fname_parts) > 1 and fname_parts[-1].lower() in known_apps:
                    app_name = fname_parts.pop()
                fname = ' '.join(fname_parts)
                p = _effective_cwd(session) / fname
                if not p.exists():
                    matches = _find_files(session, fname)
                    if matches: fname = str(matches[0].relative_to(session.workdir))
                open_file(session, fname, app=app_name)
            else: print(c('  Usage: /open <file> [app]  — e.g. /open main.py vscode',YLW))

        elif cmd == '/edit':
            if args: edit_file(session, ' '.join(args))
            else: print(c('  Usage: /edit <file>',YLW))

        elif cmd == '/delete':
            if args: delete_file(session, ' '.join(args)); _refresh(session)
            else: print(c('  Usage: /delete <file>',YLW))

        elif cmd == '/search':
            if args: search_files(session, ' '.join(args))
            else: print(c('  Usage: /search <term>',YLW))

        elif cmd == '/cleanup':
            cleanup_workspace(session, dry_run=True)

        elif cmd == '/history':
            n = int(args[0]) if args and args[0].isdigit() else 6
            print()
            for m in session.history[-(n*2):]:
                role = c('You',BLU) if m['role']=='user' else c('AI',ACC)
                print(f"  {role}  {GRY}{m['content'][:180].replace(chr(10),' ')}…{R}")
            print()

        elif cmd == '/install':
            if args: install_pkg(session, args[0])
            else: print(c('  Usage: /install <package>',YLW))

        elif cmd == '/venv':
            vp = session.ensure_venv()
            print(f"\n  {bold('Session venv')}\n  {c('Python:',GRY)} {vp}\n  {c('Dir:',GRY)} {session.venv_dir}\n")

        elif cmd == '/clone':
            if args:
                session.clone_repo(args[0])
                session.run_requirements()
                _refresh(session)
            else: print(c('  Usage: /clone <git-url>',YLW))

        elif cmd == '/requirements':
            session.run_requirements()

        elif cmd == '/ship':
            ship_workspace(session)

        elif cmd == '/doc':
            generate_doc(session, args[0] if args else 'readme')

        elif cmd == '/export':
            if args: export_path(session, ' '.join(args))
            else: print(c('  Usage: /export <file or folder>',YLW))

        elif cmd == '/config':
            print(f"\n  {bold('Config')}\n")
            for k, v in _cfg.items():
                val = ('*'*8+str(v)[-4:]) if 'key' in k.lower() and v else (v or dim('not set'))
                print(f"  {c(k,ACC):<22} {val}")
            print()

        elif cmd == '/diagnose':
            if _last_error: diagnose(session, _last_error.get('error',''), _last_error.get('file'))
            else: print(c('  No recent error to diagnose.',YLW))

        elif cmd == '/audit':
            # /audit [filename]      — audit specific file or whole project
            # /audit fix [filename]  — same, then apply reviewable fixes (asks y/n)
            #
            # Delegates to the FraudeTest engine (a separate, standalone tool —
            # see fraudetest/ alongside fraude-ai/). FraudeCode's only job here is
            # to copy the current workspace into a fresh FraudeTest project under
            # %localappdata%/FraudeTest/projects/<id>/src and trigger a scan there;
            # FraudeTest has no knowledge of FraudeCode and never reads/writes
            # back into the FraudeCode workspace except for the explicit
            # "copy fixed files back" confirmation step below.
            cwd = _effective_cwd(session)
            fix_mode = bool(args) and args[0].lower() == 'fix'
            file_arg = (args[1] if len(args) > 1 else None) if fix_mode else (args[0] if args else None)

            try:
                fraudetest_dir = Path(__file__).parent.parent / 'fraudetest'
                if not fraudetest_dir.exists():
                    # Also check alongside fraudecode.py itself (same folder layout as fraude-ai/)
                    fraudetest_dir = Path(__file__).parent / 'fraudetest'
                if not fraudetest_dir.exists():
                    print(c('  FraudeTest not found. Expected at ../fraudetest or ./fraudetest', RED))
                    continue
                if str(fraudetest_dir) not in sys.path:
                    sys.path.insert(0, str(fraudetest_dir))
                from engine import workspace as ft_workspace, unify as ft_unify, report as ft_report
                from engine import tool_detect as ft_tool_detect
            except Exception as e:
                print(c(f'  Could not load FraudeTest engine: {e}', RED))
                continue

            # If targeting a single file, copy just that file's containing folder context
            # is unnecessary — FraudeTest scans whatever folder it's given, so for a single
            # file we still copy the whole project (most static tools need surrounding
            # context — imports, requirements.txt, etc.) and filter the report afterward.
            source_dir = cwd
            project_name = f'{session.name}-{cwd.name}' if cwd != session.workdir else session.name

            print(f'\n  {c("[audit]", ACC)} Copying project into FraudeTest…')
            proj, err = ft_workspace.import_from_path(str(source_dir), name=project_name)
            if err:
                print(c(f'  ✗ {err}', RED)); continue

            stack_label = ', '.join(ft_tool_detect.detect_stack(proj.src_dir)) or 'unknown stack'
            print(f'  {c("[audit]", ACC)} Scanning with FraudeTest ({stack_label})…')
            try:
                with Spinner('Running scanners…'):
                    result = ft_unify.run_audit(proj)
            except Exception as e:
                print(c(f'  ✗ Scan failed: {e}', RED)); continue

            saved = ft_report.save_report(proj, result)

            # If a specific file was requested, filter the displayed findings to it —
            # the saved report still covers the whole project for full context.
            display_result = result
            if file_arg:
                target = _resolve(session, file_arg)
                target_rel = str(target.relative_to(session.workdir)) if target else file_arg
                filtered = [f for f in result['findings'] if f.get('file') and target_rel.endswith(f['file'])]
                display_result = {**result, 'findings': filtered, 'total_findings': len(filtered)}

            sep = c('─'*64, GRY)
            print(f'\n{sep}')
            print(_render_md(ft_report.render_markdown(display_result, project_name)))
            print(f'\n{sep}\n')

            # Copy the report back into the FraudeCode workspace for visibility/git tracking
            local_audit_path = cwd / ('Audit.md' if not file_arg else f'Audit_{Path(file_arg).stem}.md')
            local_audit_path.write_text(saved['markdown'], encoding='utf-8')
            print(c(f'  ✓ Report: {local_audit_path.name}  (full FraudeTest project: {proj.dir})', GRN))
            _refresh(session)

            if fix_mode:
                fixable = [f for f in result['findings'] if f.get('fix')]
                if not fixable:
                    print(c('  No auto-fixable findings in this report.', YLW))
                else:
                    print(f'\n  {bold(str(len(fixable)) + " finding(s) have a suggested fix:")}')
                    for i, f in enumerate(fixable, 1):
                        print(f"  {i}. [{f['severity']}] {f['title']} — {f.get('file','?')}:{f.get('line','?')}")
                        print(f"     {dim('Fix: ' + f['fix'][:100])}")
                    print(f"\n  {YLW}FraudeTest's fixes are suggestions (URLs/guidance from the underlying scanners),{R}")
                    print(f"  {YLW}not auto-applied diffs yet — review each one manually for now.{R}")

        elif cmd in ('/operate', '/run-project', '/start'):
            # Find and run the "main" entry point for the project
            cwd = _effective_cwd(session)
            SKIP = {'.venv','venv','__pycache__','node_modules','.git'}
            # Priority: main.py, app.py, server.py, index.html, *.bat, *.sh
            entry_points = [
                cwd / 'main.py', cwd / 'app.py', cwd / 'server.py', cwd / 'run.py',
                cwd / 'index.html', cwd / 'index.htm',
            ]
            # Also check start.bat / start.sh
            for bat in ['start.bat','start.sh','run.bat','serve.bat']:
                entry_points.append(cwd / bat)
            target_file = next((p for p in entry_points if p.exists()), None)
            if not target_file:
                # Fall back to first .py or .html found
                pys = sorted(f for f in cwd.glob('*.py') if not f.name.startswith('_'))
                htmls = list(cwd.glob('*.html'))
                target_file = pys[0] if pys else (htmls[0] if htmls else None)
            if not target_file:
                print(c('  No entry point found. Try /run <filename> directly.', YLW))
            else:
                print(c(f'  Starting: {target_file.name}', GRN))
                fname = str(target_file.relative_to(session.workdir))
                run_file_cmd(session, fname, session.last_files)

        elif cmd == '/pentest':
            # /pentest [type] [filename]
            # types: all sqli xss auth api hardcoded deps headers ddos csrf path injection
            test_type = 'all'
            target_file = None
            if args:
                if args[0].lower() in PENTEST_TYPES:
                    test_type = args[0].lower()
                    target_file = args[1] if len(args) > 1 else None
                else:
                    target_file = args[0]
            run_pentest(session, test_type=test_type, target_file=target_file, cwd_path=_effective_cwd(session))

        elif cmd == '/stop':
            cancel_pipeline(); print(c('  Pipeline cancelled.',YLW))

        elif cmd in ('/hide', '/unhide'):
            unhide = cmd == '/unhide'
            if not args and not unhide:
                # List hidden items
                from fraudecode_pkg.commands import _load_hidden
                cfg = _load_hidden(session)
                hidden = cfg.get('hidden', [])
                if not hidden: print(c('  Nothing hidden.', GRY))
                else:
                    print(f'\n  {bold("Hidden items:")}')
                    for h in hidden: print(f'  {c("·", ACC)} {h}')
                    print(f'  {dim("Use /unhide <name> to show again.")}\n')
            elif args:
                target = ' '.join(args)
                # Support --show flag
                if args[0] == '--show':
                    hide_path(session, ' '.join(args[1:]), unhide=True)
                else:
                    hide_path(session, target, unhide=unhide)
            else:
                print(c('  Usage: /hide <file|folder>  or  /unhide <file|folder>', YLW))

        elif cmd == '/import':
            if not args: print(c('  Usage: /import <filepath>',YLW)); continue
            src = ' '.join(args)
            if import_file(session, src): _refresh(session)

        elif cmd == '/lockin':
            if get_lockin():
                set_lockin(False)
                print(c('  LOCKIN mode OFF — back to normal pipeline', GRY))
            else:
                if not (_cfg.get('groqKey') and _cfg.get('geminiKey')):
                    print(c('  LOCKIN needs both Groq + Gemini keys (Max plan)', YLW)); continue
                set_lockin(True)
                print(c('  LOCKIN mode ON — Gemini + Groq both generate code, Ollama merges', GRN))
                print(f"  {dim('Slower but produces higher quality, validated code')}")

        elif cmd == '/setup':
            new_cfg = run_setup(_cfg)
            _cfg.update(new_cfg)
            set_config(_cfg)
            print(c('  Keys updated and saved.', GRN))

        elif cmd == '/download':
            this = Path(__file__).resolve()
            print(f"\n  {bold('FraudeCode:')}\n  {c(str(this),ACC)}\n  {c(f'python {this.name}',GRN)}\n")

        elif cmd.startswith('/'):
            # Check for /directory as natural language alias
            if cmd == '/directory':
                arg = ' '.join(args).lower()
                if 'list' in arg:
                    cwd2 = _effective_cwd(session)
                    SKIP2 = {'.venv','venv','__pycache__','node_modules','.git'}
                    files2 = sorted(f for f in cwd2.iterdir() if f.is_file() and not f.name.startswith('.'))
                    if not files2: print(c('  No files.\n',GRY))
                    else:
                        print(f"\n  {bold('Folder')}  {dim(str(cwd2))}\n")
                        for i,f in enumerate(files2,1): print(f"  {c(str(i),GRY)}  {c(f.name,WHT):<48} {GRY}{f.stat().st_size:,}B{R}")
                        print()
                else:
                    print(f"\n  {c('Folder:',ACC)} {_effective_cwd(session)}\n")
            else:
                # Unknown slash command — suggest closest match
                closest = min(CMDS, key=lambda x: sum(a!=b for a,b in zip(x,cmd+'?'*20)))
                print(c(f'  Unknown command: {cmd}', RED))
                print(c(f'  Did you mean: {closest}?', YLW))

        else:
            # ── Natural language handling ────────────────────────────────
            if check_nl(inp, session): continue

            # ── AI pipeline ─────────────────────────────────────────────
            session.history.append({'role':'user','content':inp})
            print()
            try:
                if get_plan() == 'free':
                    ollama_url = _cfg.get('ollamaUrl','')
                    if not ollama_url or not ollama_url.startswith('http'):
                        ollama_url = 'http://localhost:11434'
                        _cfg['ollamaUrl'] = ollama_url
                    msgs = [{'role':'system','content':_make_system_prompt(session, user_input=inp, last_run_output=_last_run_output)}]
                    msgs += session.history[-10:]
                    with Spinner('HighKu thinking (may be slow)…'):
                        reply = call_ollama(msgs)
                    session.history.append({'role':'assistant','content':reply})
                    _print_result('', reply)
                else:
                    result = run_pipeline(inp, context=_make_system_prompt(session, user_input=inp, last_run_output=_last_run_output))
                    if result is None:
                        print(c('  Pipeline returned no result. Check your API keys with /agent', YLW))
                        session.history.pop(); continue
                    if result.cancelled:
                        print(c('\n  Cancelled.\n',YLW))
                        session.history.pop(); continue
                    if result.errors:
                        for agent, err in result.errors:
                            print(c(f'  [{agent}] {err[:100]}', YLW))
                    combined = '\n\n'.join(filter(None,[result.code,result.explanation]))
                    session.history.append({'role':'assistant','content':combined})
                    _print_result(result.code, result.explanation)

                    session.last_files = []
                    for lang, blk in _extract(result.code or ''):
                        dest = session.save_code(lang, blk)
                        session.last_files.append(dest)
                        _refresh(session)
                        print(c(f'  💾 {dest.name}', GRN))

                    py_files = [f for f in session.last_files if f.suffix=='.py']
                    if py_files:
                        try:
                            q = input(f"  {c('▶ Run',GRN)} {py_files[-1].name}? {GRY}[Y/n]{R}: ").strip().lower()
                            if q in ('','y','yes'):
                                import io, contextlib
                                _last_run_output = f'[Running {py_files[-1].name}]'
                                res = run_file_cmd(session, py_files[-1].name, session.last_files)
                                if res:
                                    _last_run_output += f'\nExit code: {res.get("exitCode", "?")}\nOutput: {res.get("stdout","")[:1000]}\nErrors: {res.get("stderr","")[:500]}'
                                if res and res.get('diagnose'):
                                    _last_error = res
                                    diagnose(session, res['error'], res.get('file'))
                        except (KeyboardInterrupt,EOFError): pass

            except RuntimeError as e:
                msg = str(e)
                if 'RATE_LIMIT' in msg:
                    print(c(f'\n  ⚠ Rate limit: {msg.split("RATE_LIMIT:")[-1].strip()}\n',YLW))
                else:
                    print(c(f'\n  ✗ {msg}\n',RED))
            except Exception as e:
                print(c(f'\n  ✗ Unexpected: {e}\n',RED))

        try: session.save()
        except Exception: pass

# ── Entry ───────────────────────────────────────────────────────────────────────
def main():
    signal.signal(signal.SIGINT, _sigint)
    # Start FraudeRepo dashboard in background
    try:
        import frauderepo
        repo_port = frauderepo.start_server()
        print(f"  {dim(f'FraudeRepo →  http://localhost:{repo_port}')}")
    except Exception:
        pass
    if not HAS_RL:
        print(c('  ⚠ pip install pyreadline3  for tab completion on Windows\n', YLW))
    session = dashboard()
    clear_screen(); print(MINI+'\n')
    # Restore per-session agent override
    if hasattr(session, 'agent_override') and session.agent_override:
        set_plan_override(session.agent_override)
    else:
        set_plan_override('')
    print(f"  {bold('Chat:')} {c(session.name,ACC)}")
    plan_now = get_plan()
    print(f"  {bold('Plan:')} {c(PLAN_LABELS[plan_now],GRN)}")
    if plan_now == 'free' and not (_cfg.get('groqKey') or _cfg.get('geminiKey')):
        print(f"  {YLW}No API keys found. Run /setup or set keys in Fraude web app.{R}")
    print(f"  {dim('Type /help for commands  ·  /agent to check plan  ·  Ctrl+C cancels AI')}\n")
    repl(session)

if __name__ == '__main__':
    main()
