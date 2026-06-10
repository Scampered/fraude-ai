
def import_file(session, source_path: str) -> bool:
    """Copy a file from anywhere on disk into this session workspace."""
    import shutil
    src = Path(source_path).expanduser().resolve()
    if not src.exists():
        print(c(f'  Not found: {source_path}', RED)); return False
    dest = session.workdir / src.name
    shutil.copy2(src, dest)
    print(c(f'  Imported: {src.name} → workspace', GRN))
    return True

"""Slash command implementations for the FraudeCode REPL."""
import os, sys, re, subprocess, webbrowser
from pathlib import Path
from .colours import *
from .ui import ask_permission, check_safety, clear_screen

# ─── Help system ──────────────────────────────────────────────────────────────
HELP_INDEX = f"""
  {bold('FraudeCode Help')}  {dim('— type /help <topic> for detail')}

  {c('/help chats',    ACC):<30} Managing chats & sessions
  {c('/help files',    ACC):<30} File operations in your workspace
  {c('/help agents',   ACC):<30} AI models & switching between them
  {c('/help git',      ACC):<30} Git & repo integration
  {c('/help packages', ACC):<30} pip packages & virtual envs
  {c('/help ship',     ACC):<30} Exporting & downloading your work
  {c('/help docs',     ACC):<30} Generating README / handoff docs
  {c('/help shortcuts',ACC):<30} Natural language shortcuts
  {c('/help tips',     ACC):<30} Tips for new users
"""



def list_files(session, pattern: str = '**/*'):
    """List files in session workspace."""
    if not pattern.startswith('**'):
        pattern = f'**/{pattern}' if '*' in pattern else f'**/{pattern}*' if pattern != '*' else '**/*'
    files = sorted(f for f in session.workdir.glob(pattern)
                   if f.is_file() and '.venv' not in str(f) and not f.name.startswith('_'))
    if not files:
        print(c('  No files.\n', GRY)); return
    print(f"\n  {bold('Workspace')}  {dim(str(session.workdir))}\n")
    for i, f in enumerate(files, 1):
        rel  = f.relative_to(session.workdir)
        size = f'{f.stat().st_size:,}B'
        print(f"  {c(str(i),GRY)}  {c(str(rel),WHT):<44} {GRY}{size}{R}")
    print()

HELP_TOPICS = {
'chats': (
    "\n  \033[1mChats & Sessions\033[0m  -- every session has its own workspace + venv\n\n"
    "  /save [name]   Save chat (optionally rename)\n"
    "  /rename <name> Rename current chat\n"
    "  /newchat [name]Start fresh chat\n"
    "  /chats         Dashboard -- switch or delete chats\n"
    "  /home          Go back to dashboard\n"
    "  /clear         Clear screen (keeps history)\n"
    "  /history [n]   Show last N turns\n\n"
    "  Dashboard: number=open  N=new  D<n>=delete  Q=quit\n"
),
'files': (
    "\n  \033[1mFile Management\033[0m  -- workspace = fraude-code-memory/workspace_<id>/\n\n"
    "  /files [*.ext]  List files (filter e.g. *.py)\n"
    "  /open <file>    View with line numbers (or browser for .html)\n"
    "  /run <file>     Run: .py in venv, .html in browser, .js in node\n"
    "  /edit <file>    Open in system editor\n"
    "  /delete <file>  Delete with permission prompt\n"
    "  /search <term>  Search text in all workspace files\n"
    "  /import <path>  Copy any file from your PC into workspace\n"
    "  /export <file>  Copy file to Downloads folder\n"
    "  directory       Show workspace path (natural language)\n"
    "  directory list  List files (natural language)\n"
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
    "  /lockin            Dual-coder: Gemini+Groq both generate, Ollama merges\n"
    "  /setup             Re-run setup wizard to change API keys\n\n"
    "  Keys also sync from Fraude web -> Settings -> Models when web app is running.\n"
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
    "  /ship           Zip workspace -> opens download in browser\n"
    "  /export <file>  Copy file to ~/Downloads\n\n"
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
    "  directory       Show workspace path\n"
    "  directory list  List workspace files\n"
    "  package list    List installed packages\n"
    "  make readme     Generate README.md\n"
    "  make handoff    Generate HANDOFF.md\n"
    "  ship it         Zip and prepare download\n"
    "  diagnose        Re-diagnose last error\n"
),
'tips': (
    "\n  \033[1mTips for Getting Started\033[0m\n\n"
    "  1. Just describe what you want in plain English.\n"
    "     e.g. 'make a Flask API with login and a /profile endpoint'\n\n"
    "  2. FraudeCode saves generated .py files and asks to run them.\n"
    "     Type Y -- it runs in an isolated environment for this chat.\n\n"
    "  3. If code crashes, FraudeCode asks: 'Diagnose error? [Y/n]'\n"
    "     Say Y -- AI reads the error, fixes the code, saves a new version.\n\n"
    "  4. /clone pulls any GitHub repo into your workspace.\n\n"
    "  5. /ship zips all files when done. Opens a download link.\n\n"
    "  6. Tab completes commands and filenames.\n\n"
    "  7. Ctrl+C cancels the current AI request without quitting.\n\n"
    "  8. Each chat has its own isolated Python environment.\n\n"
    "  9. /lockin (Max plan) uses Gemini AND Groq together, Ollama merges.\n"
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
    print(f"\n  Unknown topic '{topic}'. Try: chats, files, agents, git, packages, ship, docs, shortcuts, tips, all\n")



    if not pattern.startswith('**'):
        pattern = f'**/{pattern}'
    files = sorted(f for f in session.workdir.glob(pattern)
                   if f.is_file() and '.venv' not in str(f) and not f.name.startswith('_'))
    if not files:
        print(c('  No files.\n', GRY)); return
    print(f"\n  {bold('Workspace')}  {dim(str(session.workdir))}\n")
    for i, f in enumerate(files, 1):
        rel  = f.relative_to(session.workdir)
        size = f'{f.stat().st_size:,}B'
        print(f"  {c(str(i),GRY)}  {c(str(rel),WHT):<44} {GRY}{size}{R}")
    print()
def view_file(session, name: str):
    t = _resolve(session, name)
    if not t: print(c(f'  Not found: {name}', RED)); return
    print(f"\n  {c(t.name,ACC)}  {dim(str(t.stat().st_size)+' bytes')}\n")
    for i, ln in enumerate(t.read_text('utf-8',errors='replace').split('\n'), 1):
        print(f"  {GRY}{i:4}{R}  {ln}")
    print()
def open_file(session, name: str):
    """Open a file: run HTML/JS in browser, Python in venv, others in editor."""
    t = _resolve(session, name)
    if not t: print(c(f'  Not found: {name}', RED)); return
    ext = t.suffix.lower()
    if ext == '.html':
        import webbrowser
        webbrowser.open(t.as_uri())
        print(c(f'  Opened {t.name} in browser', GRN))
    elif ext == '.py':
        run_file_cmd(session, name)
    elif ext in ('.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.env'):
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
    code_text = target.read_text('utf-8', errors='replace')
    dangers = check_safety(code_text)
    if dangers and not ask_permission(f'Run {target.name}', f'Contains: {", ".join(dangers)}'):
        return None
    print(f"\n  {c('▶',GRN)} {bold(target.name)}\n")
    try:
        if ext == '.html':
            import webbrowser
            webbrowser.open(target.as_uri())
            print(c('  Opened in browser\n', GRN))
            return {'exitCode': 0}
        elif ext == '.py':
            result = session.run_file(target)
        elif ext in ('.sh', '.bash'):
            result = subprocess.run(['bash', str(target)], capture_output=True, text=True, cwd=session.workdir, timeout=60)
        elif ext == '.js':
            result = subprocess.run(['node', str(target)], capture_output=True, text=True, cwd=session.workdir, timeout=60)
        elif ext == '.ts':
            result = subprocess.run(['npx', 'ts-node', str(target)], capture_output=True, text=True, cwd=session.workdir, timeout=60)
        elif ext in ('.bat', '.cmd'):
            result = subprocess.run([str(target)], shell=True, capture_output=True, text=True, cwd=session.workdir, timeout=60)
        else:
            # Try to open with system default
            if sys.platform == 'win32':
                os.startfile(str(target))
                print(c(f'  Opened {target.name} with system default\n', GRN))
            else:
                subprocess.run(['xdg-open', str(target)])
            return {'exitCode': 0}
        if result.stdout: print(result.stdout.rstrip())
        if result.stderr: print(c(result.stderr.rstrip(), RED))
        rc = result.returncode
        print(c(f'\n  Exit {rc}\n', GRN if rc==0 else RED))
        if rc != 0 and result.stderr:
            try:
                q = input(f"  {YLW}Exit {rc}. Diagnose error? [Y/n]{R}: ").strip().lower()
                if q in ('', 'y', 'yes'):
                    return {'diagnose': True, 'error': result.stderr, 'file': target}
            except (KeyboardInterrupt, EOFError): pass
        return {'exitCode': rc}
    except subprocess.TimeoutExpired:
        print(c('\n  Timed out (60s). Process killed.\n', RED))
    except FileNotFoundError as e:
        print(c(f'\n  Cannot run {ext} — runtime not found: {e}\n', RED))
    except Exception as e:
        print(c(f'\n  Run error: {e}\n', RED))
    return None
def delete_file(session, name: str):
    t = _resolve(session, name)
    if not t: print(c(f'  Not found: {name}', RED)); return
    if ask_permission(f'Delete {t.name}'):
        t.unlink(); print(c(f'  Deleted {t.name}', GRN))
def search_files(session, term: str):
    tl = term.lower(); hits = 0
    for f in session.workdir.glob('**/*'):
        if not f.is_file() or '.venv' in str(f): continue
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
    r = subprocess.run([venv_py, '-m', 'pip', 'install', pkg],
                       capture_output=True, text=True)
    if r.returncode == 0: print(c(f'  ✓ {pkg} installed', GRN))
    else: print(c(f'  ✗ {r.stderr.strip()[:300]}', RED))
def edit_file(session, name: str):
    t = _resolve(session, name)
    if not t: print(c(f'  Not found: {name}', RED)); return
    editor = os.environ.get('EDITOR', 'notepad' if sys.platform=='win32' else 'nano')
    subprocess.run([editor, str(t)])
def export_file(session, name: str, dest_dir: str = None):
    import shutil
    src = _resolve(session, name)
    if not src: print(c(f'  Not found: {name}', RED)); return
    if dest_dir:
        out_dir = Path(dest_dir).expanduser()
    else:
        # Use Downloads folder, fallback to home
        dl = Path.home() / 'Downloads'
        out_dir = dl if dl.exists() else Path.home()
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / src.name
    shutil.copy2(src, dest)
    print(c(f'  Exported to {dest}', GRN))
def _resolve(session, name: str) -> Path | None:
    """Find file in session workspace or global CODE_DIR."""
    from .config import CODE_DIR
    for base in [session.workdir, CODE_DIR]:
        t = base / name
        if t.exists(): return t
    return None
