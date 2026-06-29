"""Slash command implementations for the FraudeCode REPL."""
import os, sys, re, subprocess, webbrowser, shutil, zipfile
from pathlib import Path
from .colours import *
from .ui import ask_permission, check_safety, clear_screen

# ─── Help system ──────────────────────────────────────────────────────────────
HELP_INDEX = f"""
  {bold('FraudeCode Help')}  {dim('— type /help <topic> for detail')}

  {c('/help chats',     ACC):<30} Managing chats & sessions
  {c('/help files',     ACC):<30} File operations in your workspace
  {c('/help navigate',  ACC):<30} Folder navigation (/cd, /back, /pwd)
  {c('/help agents',    ACC):<30} AI models & switching between them
  {c('/help git',       ACC):<30} Git & repo integration
  {c('/help packages',  ACC):<30} pip packages & virtual envs
  {c('/help ship',      ACC):<30} Exporting & downloading your work
  {c('/help docs',      ACC):<30} Generating README / handoff docs
  {c('/help shortcuts', ACC):<30} Natural language shortcuts
  {c('/help tips',      ACC):<30} Tips for new users
  {c('/help audit',     ACC):<30} Code audit & review tools
  {c('/help security',  ACC):<30} /pentest & /audit security testing
  {c('/help operate',   ACC):<30} Run project & /operate command
"""

HELP_TOPICS = {
'chats': (
    "\n  \033[1mChats & Sessions\033[0m  -- every session has its own workspace + venv\n\n"
    "  /save [name]    Save chat (optionally rename)\n"
    "  /rename <name>  Rename current session\n"
    "  /newchat [name] Start fresh chat\n"
    "  /chats          Dashboard -- switch or delete chats\n"
    "  /home           Go back to dashboard\n"
    "  /clear          Clear screen (keeps history)\n"
    "  /history [n]    Show last N turns\n\n"
    "  Dashboard: number=open  N=new  D<n>=delete  Q=quit\n"
),
'files': (
    "\n  \033[1mFile Management\033[0m  -- workspace = fraude-code-memory/workspace_<id>/\n\n"
    "  /files [*.ext]           List files (filter e.g. *.py, searches recursively)\n"
    "  /open <file>             View with line numbers (or browser for .html)\n"
    "  /run <file>              Run: .py in venv, .html in browser, .js in node\n"
    "  /edit <file>             Open in system editor\n"
    "  /delete <file>           Delete with permission prompt\n"
    "  /search <term>           Search text in all workspace files\n"
    "  /import <path>           Copy any file from your PC into workspace\n"
    "  /export <file|folder>    Copy to Downloads (folders get zipped)\n"
    "  /file-rename <old> <new> Rename file (keeps extension)\n"
    "  /ext-rename <file> <ext> Change file extension\n"
    "  /hide <file|folder>      Hide from /files listings (still accessible)\n"
    "  /unhide <file|folder>    Show hidden item again\n"
    "  /cd <folder>             Enter subfolder (see /help navigate)\n"
    "  /cleanup                 Remove junk files (.git, __pycache__, node_modules…)\n"
    "  directory list           List files (natural language)\n"
),
'navigate': (
    "\n  \033[1mFolder Navigation\033[0m  -- browse subfolders within your workspace\n\n"
    "  /cd <folder>  Enter a subfolder (e.g. /cd Money-Manager)\n"
    "  /cd ..        Go up one level\n"
    "  /back         Go up one level (same as /cd ..)\n"
    "  /pwd          Show current folder path\n\n"
    "  The prompt shows your current subfolder:\n"
    "    testing/Money-Manager ❯\n\n"
    "  All file commands (/open, /run, /files) work relative to current folder.\n"
    "  Tab completion shows files in the current folder.\n"
),
'agents': (
    "\n  \033[1mAgent Tiers\033[0m -- set automatically by which API keys you have\n\n"
    "  Oops 0.7  (Max)     Gemini codes + Groq explains + Ollama routes\n"
    "    Best quality. All 3 agents. For complex projects.\n\n"
    "  Oops 0.6            Gemini codes+explains + Ollama routes\n"
    "    Good quality. Only Gemini + Ollama needed.\n\n"
    "  Somenet 0.6         Groq codes+explains + Ollama routes\n"
    "    Fast. Great for frontend/UI/APIs.\n\n"
    "  Somenet 0.5         Groq only (no Ollama routing)\n"
    "    No local model needed. Groq handles everything.\n\n"
    "  HighKu 0.5  (Free)  Local Ollama only\n"
    "    Private, no cloud APIs. Slower, less capable.\n\n"
    "  /agent             Show current tier + key status\n"
    "  /agent max         Force Oops 0.7  (Gemini+Groq+Ollama)\n"
    "  /agent oops06      Force Oops 0.6  (Gemini+Ollama)\n"
    "  /agent pro         Force Somenet 0.6 (Groq+Ollama)\n"
    "  /agent somenet05   Force Somenet 0.5 (Groq only)\n"
    "  /agent free        Force HighKu 0.5  (Ollama only)\n"
    "  /lockin            Dual-coder: Gemini+Groq both generate, Ollama merges (Max plan only)\n"
    "  /operate           Run the project entry point (see /help operate)\n"
    "  /setup             Re-run setup wizard to change API keys\n\n"
    "  Keys sync from Fraude web → Settings → Models automatically.\n"
),
'git': (
    "\n  \033[1mGit & Repos\033[0m\n\n"
    "  /clone <url>   Clone a GitHub/GitLab repo into workspace\n"
    "  /requirements  Run requirements.txt in session venv\n\n"
    "  requirements.txt is run automatically after cloning.\n"
),
'packages': (
    "\n  \033[1mPackages & Virtual Envs\033[0m\n\n"
    "  /install <pkg>  pip install into this session's venv\n"
    "  /venv           Show / create session venv\n"
    "  /requirements   Install from requirements.txt\n"
    "  package list    List installed packages\n\n"
    "  Each session has its own isolated venv.\n"
),
'ship': (
    "\n  \033[1mExporting Your Work\033[0m\n\n"
    "  /ship                Zip workspace → opens download in browser\n"
    "  /export <file>       Copy file to ~/Downloads\n"
    "  /export <folder>     Zip folder → ~/Downloads\n\n"
    "  Zip excludes .venv and hidden files.\n"
),
'docs': (
    "\n  \033[1mDocumentation Generation\033[0m\n\n"
    "  /doc readme    Generate README.md from workspace code\n"
    "  /doc handoff   Generate HANDOFF.md (project summary)\n"
    "  make readme    Same as /doc readme\n"
    "  make handoff   Same as /doc handoff\n\n"
    "  AI reads your code and writes the docs automatically.\n"
),
'shortcuts': (
    "\n  \033[1mNatural Language Shortcuts\033[0m -- type as plain text\n\n"
    "  run <filename>   Find and run a file (e.g. 'run money manager')\n"
    "  open <filename>  Find and view a file\n"
    "  directory        Show workspace path\n"
    "  directory list   List workspace files\n"
    "  package list     List installed packages\n"
    "  make readme      Generate README.md\n"
    "  make handoff     Generate HANDOFF.md\n"
    "  ship it          Zip and prepare download\n"
    "  clean up         Remove junk files (interactive)\n"
    "  cleanup          Same as /cleanup\n"
),
'tips': (
    "\n  \033[1mTips for Getting Started\033[0m\n\n"
    "  1. Just describe what you want in plain English.\n"
    "     e.g. 'make a Flask API with login and a /profile endpoint'\n\n"
    "  2. FraudeCode saves generated .py files and asks to run them.\n"
    "     Type Y — it runs in an isolated environment for this chat.\n\n"
    "  3. If code crashes, FraudeCode asks: 'Diagnose error? [Y/n]'\n"
    "     Say Y — AI reads the error, fixes the code, saves a new version.\n\n"
    "  4. /clone pulls any GitHub repo into your workspace.\n"
    "     /cd <folder> to navigate inside it, /files *.py to list Python files.\n\n"
    "  5. /ship zips all files when done.\n\n"
    "  6. Tab completes commands and filenames.\n\n"
    "  7. Ctrl+C cancels the current AI request without quitting.\n\n"
    "  8. Each chat has its own isolated Python environment.\n\n"
    "  9. /lockin (Max plan) uses Gemini AND Groq together, Ollama merges.\n\n"
    "  10. /web opens the Fraude web UI and minimises this window.\n"
    "      From the web UI you can use image gen, canvas, PDF maker, etc.\n"
),
'audit': (
    "\n  \033[1mCode Audit & Review\033[0m  — AI-powered code analysis\n\n"
    "  /audit                   Review all .py files in current folder\n"
    "  /audit <file>            Review a specific file\n"
    "  /audit fix               Fix all bugs in .py files and save patched versions\n"
    "  /audit fix <file>        Fix a specific file\n"
    "  /audit help              Show this help page\n\n"
    "  Results saved to Audit.md (or Audit_<file>.md for single-file audits).\n\n"
    "  Output: BUGS · PERFORMANCE · QUALITY · FIXES with code snippets.\n"
    "  Model priority (respects /agent plan):\n"
    "    Max/Oops: Gemini/OpenRouter → Groq → Ollama\n"
    "    Oops06:   Gemini/OpenRouter → Ollama\n"
    "    Pro:      Groq → Ollama\n"
    "    Free:     Ollama only (may be slow on large files)\n\n"
    "  Tip: /cd into the relevant folder first to scope the audit.\n"
    "  See also: /help security (coming soon — /pentest for dynamic testing)\n"
),



'security': (
    "\n  \033[1mSecurity Testing\033[0m  — static audit + dynamic pentest\n\n"
    "  ── STATIC ANALYSIS (/audit) ────────────────────────────────\n"
    "  /audit                   Audit all code files in current folder\n"
    "  /audit <file>            Audit a specific file\n"
    "  /audit fix               Fix detected issues (saves patched files)\n"
    "  /audit fix <file>        Fix a specific file\n\n"
    "  ── DYNAMIC TESTING (/pentest) ──────────────────────────────\n"
    "  /pentest                 Full security scan (all test types)\n"
    "  /pentest <type>          Run a specific test:\n"
    "    sqli       SQL injection vulnerabilities\n"
    "    xss        Cross-site scripting\n"
    "    auth       Authentication & brute-force weaknesses\n"
    "    api        API endpoint security & IDOR\n"
    "    hardcoded  Hardcoded credentials & API key leaks\n"
    "    deps       Dependency vulnerability scan\n"
    "    headers    Missing HTTP security headers\n"
    "    ddos       Rate limiting & DDoS surface analysis\n"
    "    csrf       CSRF token validation\n"
    "    path       Path traversal vulnerabilities\n"
    "    injection  Command injection risks\n"
    "  /pentest <type> <file>   Test a specific file\n\n"
    "  Both save reports to Audit.md / Pentest_<type>.md.\n"
    "  Tip: /cd into the project folder first, then /pentest.\n"
    "  Coming: FraudeTemp virtual environment for safe dynamic testing.\n"
),
'operate': (
    "\n  \033[1mOperating Your Project\033[0m  — run, launch, and test\n\n"
    "  /operate               Auto-detect and run the project entry point\n"
    "                         Checks: main.py, app.py, server.py, index.html,\n"
    "                         start.bat, start.sh, run.bat\n"
    "  /run <file>            Run a specific file\n"
    "  /run <file.bat>        Run a Windows batch script (from its own folder)\n"
    "  /open <file> [app]     Open a file in a specific app:\n"
    "                         /open file.py vscode\n"
    "                         /open index.html browser\n"
    "                         /open config.json notepad\n\n"
    "  /audit                 Static code analysis before running\n"
    "  /pentest               Security scan before deploying\n\n"
    "  Note: Python files run in an isolated session venv.\n"
    "  .bat files run from their own directory so relative paths work.\n"
),
}
def show_help(topic: str = ''):
    t = topic.strip().lower()
    if not t:
        print(HELP_INDEX)
        return
    if t in ('all', 'everything', '*'):
        print(HELP_INDEX)
        for content in HELP_TOPICS.values():
            print(content)
        return
    matches = [key for key in HELP_TOPICS
               if key.startswith(t) or t.startswith(key[:-1]) or t in key]
    if matches:
        for key in matches:
            print(HELP_TOPICS[key])
        return
    print(f"\n  Unknown topic '{topic}'.\n"
          f"  Try: chats, files, navigate, agents, git, packages, ship, docs, shortcuts, tips, all\n")


def _resolve(session, name: str) -> Path | None:
    """Find file in session workspace — handles subdirectory paths and fuzzy names."""
    from .config import CODE_DIR
    # Direct paths first
    for base in [session.workdir, CODE_DIR]:
        t = base / name
        if t.exists() and t.is_file():
            return t
    # Fuzzy: search recursively in workspace
    SKIP = {'.venv', '__pycache__', 'node_modules', '.git'}
    query_parts = name.lower().replace('-',' ').replace('_',' ').split()
    matches = []
    for p in session.workdir.rglob('*'):
        if p.is_file() and not any(j in p.parts for j in SKIP):
            name_lower = p.name.lower().replace('-',' ').replace('_',' ')
            if all(part in name_lower for part in query_parts):
                matches.append(p)
    if matches:
        return sorted(matches, key=lambda p: len(p.name))[0]
    return None


def list_files(session, pattern: str = '**/*', show_hidden=False):
    """List files (and folders) in session workspace. pattern can be *.py, 'folders', etc."""
    SKIP = {'.venv', 'venv', '__pycache__', 'node_modules', '.git', '.pytest_cache'}

    # Load hidden list
    hidden_cfg = _load_hidden(session)
    hidden_set = set(hidden_cfg.get('hidden', []))

    folders_only = pattern.strip().lower() in ('folder', 'folders', '/folders')
    if folders_only:
        # Show only top-level and nested dirs
        dirs = sorted(d for d in session.workdir.rglob('*')
                      if d.is_dir() and not any(s in d.parts for s in SKIP) and not d.name.startswith('.'))
        if not dirs:
            print(c('  No folders.\n', GRY)); return
        print(f"\n  {bold('Folders')}  {dim(str(session.workdir))}\n")
        for i, d in enumerate(dirs, 1):
            rel = str(d.relative_to(session.workdir))
            hidden = rel in hidden_set or any(rel.startswith(h) for h in hidden_set)
            marker = c(' [hidden]', GRY) if hidden else ''
            print(f"  {c(str(i), GRY)}  {c(rel + '/', ACC)}{marker}")
        print()
        return

    # Build recursive glob pattern
    if pattern in ('**/*', '*'):
        glob_pat = '**/*'
    elif pattern.startswith('*.'):
        glob_pat = f'**/{pattern}'
    elif pattern.startswith('/'):
        glob_pat = pattern.lstrip('/')
    else:
        glob_pat = f'**/*{pattern}*' if '.' not in pattern else f'**/{pattern}'

    files = sorted(
        f for f in session.workdir.glob(glob_pat)
        if f.is_file()
        and not any(skip in f.parts for skip in SKIP)
        and not f.name.startswith('.')
    )

    if not files:
        print(c('  No files.\n', GRY)); return

    print(f"\n  {bold('Workspace')}  {dim(str(session.workdir))}\n")
    hidden_count = 0
    shown = 0
    for f in files:
        rel = str(f.relative_to(session.workdir))
        # Check if this file or any parent dir is hidden
        is_hidden = rel in hidden_set or any(
            rel.startswith(h.rstrip('/') + ('/' if not h.endswith('/') else ''))
            for h in hidden_set if h
        )
        if is_hidden:
            hidden_count += 1
            continue
        shown += 1
        size = f'{f.stat().st_size:,}B'
        print(f"  {c(str(shown), GRY)}  {c(rel, WHT):<52} {GRY}{size}{R}")

    # Show hidden summary
    if hidden_count:
        print(f"\n  {dim(f'{hidden_count} hidden item(s) — use /hide to manage')}")
    print()


def _load_hidden(session) -> dict:
    """Load hidden files/folders list from workspace metadata."""
    meta = session.workdir / '.fraude_meta.json'
    if meta.exists():
        try:
            import json
            return json.loads(meta.read_text('utf-8'))
        except Exception:
            pass
    return {'hidden': []}


def _save_hidden(session, hidden: list):
    import json
    meta = session.workdir / '.fraude_meta.json'
    meta.write_text(json.dumps({'hidden': hidden}, indent=2), encoding='utf-8')


def hide_path(session, target: str, unhide=False, cwd=None):
    """Hide or unhide a file or folder from /files listings."""
    cfg = _load_hidden(session)
    hidden = cfg.get('hidden', [])
    cwd = cwd or session.workdir
    target_clean = target.rstrip('/')
    # Try relative to cwd first, then workdir, then recursive search
    p = None
    for base in [cwd, session.workdir]:
        candidate = base / target_clean
        if candidate.exists():
            p = candidate; break
    if p is None:
        for candidate in session.workdir.rglob('*'):
            if candidate.name == target_clean or str(candidate.relative_to(session.workdir)) == target_clean:
                p = candidate; break
    if p is None:
        print(c(f'  Not found: {target_clean}  (searched in {cwd})', RED)); return
    rel = str(p.relative_to(session.workdir))
    if p.is_dir():
        rel = rel + '/'
    if unhide:
        if rel in hidden:
            hidden.remove(rel)
            _save_hidden(session, hidden)
            print(c(f'  Unhidden: {rel}', GRN))
        else:
            print(c(f'  Not hidden: {rel}', YLW))
    else:
        if rel not in hidden:
            hidden.append(rel)
            _save_hidden(session, hidden)
            print(c(f'  Hidden: {rel}  (use /hide --show {rel} to unhide)', GRN))
        else:
            print(c(f'  Already hidden: {rel}', YLW))


def view_file(session, name: str):
    t = _resolve(session, name)
    if not t: print(c(f'  Not found: {name}', RED)); return
    print(f"\n  {c(t.name,ACC)}  {dim(str(t.stat().st_size)+' bytes')}\n")
    for i, ln in enumerate(t.read_text('utf-8',errors='replace').split('\n'), 1):
        print(f"  {GRY}{i:4}{R}  {ln}")
    print()


def open_file(session, name: str, app: str = None):
    """Open a file — optionally in a specific app (notepad, vscode, browser, nano, etc.)."""
    t = _resolve(session, name)
    if not t: print(c(f'  Not found: {name}', RED)); return
    ext = t.suffix.lower()

    if app:
        app_lower = app.lower().strip()
        try:
            if app_lower in ('browser', 'chrome', 'firefox', 'edge'):
                webbrowser.open(t.as_uri()); print(c(f'  Opened {t.name} in browser', GRN))
            elif app_lower in ('explorer', 'finder'):
                subprocess.Popen(['explorer', str(t.parent)] if sys.platform == 'win32' else ['open', str(t.parent)])
            elif app_lower in ('notepad',):
                subprocess.Popen(['notepad', str(t)]); print(c(f'  Opened in Notepad', GRN))
            elif app_lower in ('code', 'vscode'):
                subprocess.Popen(['code', str(t)]); print(c(f'  Opened in VS Code', GRN))
            else:
                subprocess.Popen([app_lower, str(t)]); print(c(f'  Opened {t.name} in {app}', GRN))
        except FileNotFoundError:
            print(c(f'  App not found: {app} — opening with default', YLW))
            open_file(session, name)  # fallback to default
        return

    # Default behaviour
    if ext == '.html':
        webbrowser.open(t.as_uri()); print(c(f'  Opened {t.name} in browser', GRN))
    elif ext == '.py':
        run_file_cmd(session, name)
    elif ext in ('.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.env', '.log'):
        view_file(session, name)
    else:
        edit_file(session, name)


def run_file_cmd(session, name: str = '', last_files=None):
    target = None
    if name:
        target = _resolve(session, name)
        if not target: print(c(f'  Not found: {name}', RED)); return None
    elif last_files:
        target = last_files[-1]
    else:
        py_files = sorted(session.workdir.glob('*.py'))
        if py_files: target = py_files[-1]
    if not target:
        print(c('  No file to run.', YLW)); return None

    ext = target.suffix.lower()
    if ext not in ('.bat','.cmd','.sh','.bash'):
        code_text = target.read_text('utf-8', errors='replace')
        dangers = check_safety(code_text)
        if dangers and not ask_permission(f'Run {target.name}', f'Contains: {", ".join(dangers)}'):
            return None

    print(f'\n  {c("▶", GRN)} {bold(target.name)}\n')
    # Batch files run from their own directory so relative paths work
    run_cwd = str(target.parent) if ext in ('.bat','.cmd') else str(session.workdir)

    try:
        if ext == '.html':
            webbrowser.open(target.as_uri())
            print(c('  Opened in browser\n', GRN)); return {'exitCode': 0}
        elif ext == '.py':
            result = session.run_file(target)
        elif ext in ('.bat', '.cmd'):
            # Run interactively (no capture) from file's own directory
            result = subprocess.run(str(target), shell=True, cwd=run_cwd)
        elif ext in ('.sh', '.bash'):
            result = subprocess.run(['bash', str(target)], cwd=session.workdir, timeout=60)
        elif ext == '.js':
            result = subprocess.run(['node', str(target)], capture_output=True, text=True, cwd=session.workdir, timeout=60)
        else:
            if sys.platform == 'win32':
                os.startfile(str(target))
                print(c(f'  Opened {target.name} with system default\n', GRN))
            else:
                subprocess.run(['xdg-open', str(target)])
            return {'exitCode': 0}

        rc = getattr(result, 'returncode', 0)
        stdout = getattr(result, 'stdout', '') or ''
        stderr = getattr(result, 'stderr', '') or ''
        if stdout: print(stdout.rstrip())
        if stderr: print(c(stderr.rstrip(), RED))
        print(c(f'\n  Exit {rc}\n', GRN if rc == 0 else RED))
        if rc != 0 and stderr:
            try:
                q = input(f'  {YLW}Exit {rc}. Diagnose error? [Y/n]{R}: ').strip().lower()
                if q in ('','y','yes'):
                    return {'diagnose': True, 'error': stderr, 'file': target}
            except (KeyboardInterrupt, EOFError): pass
        return {'exitCode': rc}
    except subprocess.TimeoutExpired:
        print(c('\n  Timed out. Process killed.\n', RED))
    except FileNotFoundError as e:
        print(c(f'\n  Runtime not found: {e}\n', RED))
    except Exception as e:
        print(c(f'\n  Run error: {e}\n', RED))
    return None

def delete_file(session, name: str):
    t = _resolve(session, name)
    if not t: print(c(f'  Not found: {name}', RED)); return
    if ask_permission(f'Delete {t.name}'):
        t.unlink(); print(c(f'  Deleted {t.name}', GRN))


def search_files(session, term: str):
    SKIP = {'.venv', 'venv', '__pycache__', 'node_modules', '.git'}
    tl = term.lower(); hits = 0
    for f in session.workdir.glob('**/*'):
        if not f.is_file() or any(s in f.parts for s in SKIP): continue
        try:
            for i, ln in enumerate(f.read_text('utf-8',errors='replace').split('\n'), 1):
                if tl in ln.lower():
                    if hits == 0: print()
                    rel = f.relative_to(session.workdir)
                    print(f"  {c(str(rel),ACC)}:{c(str(i),GRY)}  {ln.strip()[:120]}")
                    hits += 1
        except Exception: pass
    if hits == 0: print(c(f'  No matches for "{term}"', GRY))
    else: print(f"\n  {c(str(hits)+' match(es)',GRN)}\n")


def ship_workspace(session) -> bool:
    zp = session.zip_workspace()
    if not zp: print(c('  No files to ship.', YLW)); return False
    print(c(f'\n  ✓ Packaged: {zp.name}', GRN))
    print(f"  {GRY}Path: {zp}{R}")
    url = f"http://localhost:3001/api/download-zip?path={zp}"
    try:
        webbrowser.open(url)
        print(c('  ↗ Opening download in browser…', BLU))
    except Exception:
        print(f"  {dim('Open manually:')} {zp}")
    return True


def install_pkg(session, pkg: str):
    venv_py = session.ensure_venv()
    print(f"  {c('Installing',ACC)} {pkg}…")
    r = subprocess.run([venv_py, '-m', 'pip', 'install', pkg], capture_output=True, text=True)
    if r.returncode == 0: print(c(f'  ✓ {pkg} installed', GRN))
    else: print(c(f'  ✗ {r.stderr.strip()[:300]}', RED))


def edit_file(session, name: str):
    t = _resolve(session, name)
    if not t: print(c(f'  Not found: {name}', RED)); return
    editor = os.environ.get('EDITOR', 'notepad' if sys.platform=='win32' else 'nano')
    subprocess.run([editor, str(t)])


def export_file(session, name: str, dest_dir: str = None):
    """Export a file OR directory to Downloads. Directories are zipped."""
    from .config import CODE_DIR
    # Try as file first
    src = _resolve(session, name)
    if src is None:
        # Maybe it's a directory
        dir_candidate = session.workdir / name
        if dir_candidate.is_dir():
            src = dir_candidate
        else:
            print(c(f'  Not found: {name}', RED)); return

    out_dir = Path(dest_dir).expanduser() if dest_dir else (Path.home()/'Downloads' if (Path.home()/'Downloads').exists() else Path.home())
    out_dir.mkdir(parents=True, exist_ok=True)

    SKIP = {'.venv', 'venv', '__pycache__', '.git'}

    if src.is_dir():
        # Zip the directory
        zip_path = out_dir / (src.name + '.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in src.rglob('*'):
                if f.is_file() and not any(j in f.parts for j in SKIP):
                    zf.write(f, f.relative_to(src))
        print(c(f'  Exported (zipped): {zip_path}', GRN))
    else:
        dest = out_dir / src.name
        shutil.copy2(str(src), str(dest))
        print(c(f'  Exported to {dest}', GRN))


def import_file(session, source_path: str) -> bool:
    """Copy a file from anywhere on disk into this session workspace."""
    src = Path(source_path).expanduser().resolve()
    if not src.exists():
        print(c(f'  Not found: {source_path}', RED)); return False
    dest = session.workdir / src.name
    shutil.copy2(str(src), str(dest))
    print(c(f'  Imported: {src.name} → workspace', GRN))
    return True


# ─── /pentest ─────────────────────────────────────────────────────────────────
PENTEST_TYPES = {
    'all':        'Full pentest suite (all tests)',
    'sqli':       'SQL injection testing',
    'xss':        'Cross-site scripting (XSS)',
    'auth':       'Authentication & brute-force testing',
    'api':        'API endpoint enumeration & abuse',
    'hardcoded':  'Hardcoded credentials & API key detection',
    'deps':       'Dependency vulnerability scan',
    'headers':    'HTTP security headers check',
    'ddos':       'DDoS simulation (miniature, local only)',
    'csrf':       'CSRF token validation',
    'path':       'Path traversal & directory listing',
    'injection':  'Command injection testing',
}

PENTEST_SYS = (
    "You are FraudeCode Pentester (static analysis mode). Analyse the provided code for security vulnerabilities.\n"
    "Focus on dynamic security issues that could be exploited at runtime.\n"
    "Output structured findings:\n"
    "### CRITICAL — exploitable vulnerabilities\n"
    "### HIGH — serious weaknesses\n"
    "### MEDIUM — moderate risks\n"
    "### LOW — best practice violations\n"
    "For each: location, attack vector, proof-of-concept, remediation code.\n"
    "Be specific — show exact lines and exploitation paths."
)

def run_pentest(session, test_type: str = 'all', target_file: str = None, cwd_path=None):
    """Static security analysis — the dynamic /pentest suite."""
    # colours already imported at module level
    from .agents import call_smart, call_groq, call_ollama, get_plan, _gemini_key, _openrouter_key, _groq_key

    cwd = cwd_path or session.workdir
    SKIP = {'.venv','venv','__pycache__','node_modules','.git'}

    # Collect target files
    if target_file:
        p = cwd / target_file
        if not p.exists():
            # search
            for candidate in session.workdir.rglob('*'):
                if candidate.name == target_file:
                    p = candidate; break
        if not p.exists():
            print(c(f'  Not found: {target_file}', RED)); return
        scan_files = [p]
    else:
        # All source files (not binary/data)
        CODE_EXTS = {'.py','.js','.ts','.jsx','.tsx','.php','.rb','.go','.rs','.java',
                     '.cs','.cpp','.c','.h','.html','.env','.json','.yml','.yaml','.toml','.sh','.bat'}
        scan_files = [f for f in cwd.rglob('*')
                      if f.is_file() and f.suffix.lower() in CODE_EXTS
                      and not any(j in f.parts for j in SKIP)][:15]

    if not scan_files:
        print(c('  No source files found to scan.', YLW)); return

    # Build code context
    code_ctx = ''
    for sf in scan_files[:8]:
        try:
            content = sf.read_text('utf-8', errors='replace')[:3000]
            code_ctx += f'\n\n# FILE: {sf.relative_to(session.workdir)}\n{content}'
        except Exception: pass

    # Build test-specific prompt
    test_focus = {
        'sqli':      'SQL injection: unsanitised string interpolation in queries, ORM misuse, raw execute() calls',
        'xss':       'XSS: unescaped user input rendered in HTML, dangerous innerHTML, template injection',
        'auth':      'Auth weaknesses: weak passwords, no rate limiting, insecure session handling, JWT issues',
        'api':       'API security: missing auth on endpoints, IDOR, mass assignment, verbose error messages',
        'hardcoded': 'Hardcoded secrets: API keys, passwords, tokens, private keys in source code or .env files',
        'deps':      'Dependency issues: outdated packages with known CVEs, use of deprecated/vulnerable libs',
        'headers':   'Missing security headers: CSP, HSTS, X-Frame-Options, CORS misconfiguration',
        'ddos':      'DDoS vectors: no rate limiting, unbounded loops/queries, expensive unauthenticated endpoints',
        'csrf':      'CSRF: missing CSRF tokens on state-changing endpoints, SameSite cookie attributes',
        'path':      'Path traversal: unsanitised file paths, directory listing, /../ traversal',
        'injection': 'Command injection: subprocess with user input, eval/exec, shell=True with user data',
    }.get(test_type, 'all security vulnerabilities')

    prompt = (
        f'Perform a {"full security audit" if test_type == "all" else test_type.upper() + " security test"} '
        f'on the following code.\n'
        f'Focus specifically on: {test_focus}\n'
        f'{code_ctx}\n\n'
        f'Also check for hardcoded API keys, credentials, or secrets in any file.\n'
        f'Provide: vulnerability location, severity, attack vector, and remediation code.'
    )

    type_label = PENTEST_TYPES.get(test_type, test_type)
    print(f'\n  {c("[pentest]", RED)} {type_label} — scanning {len(scan_files)} file(s)…')

    # Use best available model
    plan = get_plan()
    result_text = None
    has_smart = bool(_gemini_key() or _openrouter_key())

    if plan == 'free':
        try:
            from .ui import Spinner as _Spinner
            with _Spinner('Ollama scanning…'):
                result_text = call_ollama([{'role':'system','content':PENTEST_SYS},{'role':'user','content':prompt}], timeout=120)
        except Exception as e:
            print(c(f'  ✗ Ollama: {e}', RED)); return
    elif has_smart:
        try:
            from .ui import Spinner as _Spinner
            with _Spinner('Smart scanning…'):
                result_text = call_smart(prompt, system=PENTEST_SYS)
        except Exception as e:
            if _groq_key():
                try:
                    with _Spinner('Groq scanning…'):
                        result_text = call_groq([{'role':'user','content':prompt}], system=PENTEST_SYS)
                except Exception as e2:
                    print(c(f'  ✗ {e2}', RED)); return
            else:
                print(c(f'  ✗ {e}', RED)); return
    elif _groq_key():
        try:
            from .ui import Spinner
            with Spinner('Groq scanning…'):
                result_text = call_groq([{'role':'user','content':prompt}], system=PENTEST_SYS)
        except Exception as e:
            print(c(f'  ✗ {e}', RED)); return
    else:
        print(c('  No API key available. Use /setup to add keys.', YLW)); return

    if not result_text:
        print(c('  Empty result.', YLW)); return

    # Render and save
    sep = c('─'*64, GRY)
    print(f'\n{sep}')
    # Simple render
    for ln in result_text.split('\n'):
        s = ln.lstrip()
        if s.startswith('###') or s.startswith('##'):
            sev = s.lstrip('#').strip()
            colour = RED if 'CRITICAL' in sev else YLW if 'HIGH' in sev else ACC if 'MEDIUM' in sev else GRY
            print(f'\n  {c(sev, colour)}')
        elif s.startswith('- ') or s.startswith('* '):
            body = s[2:]
            import re
            body = re.sub(r'\*\*(.+?)\*\*', lambda m: bold(m.group(1)), body)
            print(f'  {c("·", RED)} {body}')
        else:
            print(f'  {ln}')
    print(f'\n{sep}\n')

    # Save report
    report_name = f'Pentest_{test_type}_{scan_files[0].stem}.md' if target_file else f'Pentest_{test_type}.md'
    report_path = cwd / report_name
    report_path.write_text(result_text, encoding='utf-8')
    print(c(f'  ✓ Report saved: {report_name}', GRN))
