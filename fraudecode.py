#!/usr/bin/env python3
"""FraudeCode v2.2 — run with: python fraudecode.py"""
import os, sys, re, subprocess, signal

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
                                     call_ollama, set_lockin, get_lockin)
from fraudecode_pkg.session  import Session, PY
from fraudecode_pkg.commands import (
    show_help, list_files, view_file, open_file, delete_file, search_files,
    ship_workspace, install_pkg, edit_file, export_file, run_file_cmd, import_file,
)
from pathlib import Path
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────
_cfg = load()
if not _cfg:
    _cfg = first_run()
set_config(_cfg)

# ── Tab completion ─────────────────────────────────────────────────────────────
CMDS = ['/help','/plan','/agent','/files','/run','/open','/edit','/delete',
        '/search','/history','/install','/venv','/clone','/requirements',
        '/save','/rename','/chats','/newchat','/home','/clear','/ship',
        '/doc','/config','/download','/export','/stop','/diagnose',
        '/exit','/quit','/import','/lockin','/setup']
_file_cache: list = []

def _refresh(session=None):
    global _file_cache
    _file_cache = []
    if session:
        _file_cache = [f.name for f in session.workdir.glob('*')
                       if not f.name.startswith('.') and f.is_file()]

def _completer(text, state):
    opts = ([x for x in CMDS if x.startswith(text)] if text.startswith('/')
            else [f for f in _file_cache if f.startswith(text)])
    return opts[state] if state < len(opts) else None

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
    if mode in ('max','oops07','oops'):
        if not _cfg.get('geminiKey'): print(c('  Gemini key not set — add in Fraude web Settings', YLW)); return
        if not _cfg.get('groqKey'):   print(c('  Groq key also needed for Max. Adding Gemini-only mode.', YLW))
        set_config({**_cfg})
        print(c(f'  Agent: {PLAN_LABELS[get_plan()]}', GRN))
    elif mode in ('oops06',):
        if not _cfg.get('geminiKey'): print(c('  Gemini key not set', YLW)); return
        set_config({**_cfg, 'groqKey': ''})
        print(c(f'  Agent: Oops 0.6 (Gemini + Ollama)', GRN))
    elif mode in ('pro','somenet06','somenet'):
        if not _cfg.get('groqKey'): print(c('  Groq key not set — add in Fraude web Settings', YLW)); return
        set_config({**_cfg, 'geminiKey': ''})
        print(c(f'  Agent: {PLAN_LABELS["pro"]}', GRN))
    elif mode in ('somenet05','pro05'):
        if not _cfg.get('groqKey'): print(c('  Groq key not set', YLW)); return
        set_config({**_cfg, 'geminiKey': '', 'ollamaUrl': ''})
        print(c(f'  Agent: Somenet 0.5 (Groq only)', GRN))
    elif mode in ('free','highku','local'):
        set_config({**_cfg, 'geminiKey': '', 'groqKey': ''})
        print(c(f'  Agent: {PLAN_LABELS["free"]}', GRN))
    else:
        print(c('  Usage: /agent [max|oops06|pro|somenet05|free]', YLW))
        print(f"  {GRY}max=Gemini+Groq+Ollama  oops06=Gemini+Ollama  pro=Groq+Ollama  somenet05=GroqOnly  free=OllamaOnly{R}")

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

# ── Natural language ───────────────────────────────────────────────────────────
NL = {
    'directory list': lambda s: list_files(s),
    'directory':      lambda s: print(f"\n  {c('Workspace:',ACC)} {s.workdir}\n"),
    'package list':   lambda s: subprocess.run([s.ensure_venv(log=False),'-m','pip','list']),
    'make readme':    lambda s: generate_doc(s, 'readme'),
    'make doc':       lambda s: generate_doc(s, 'readme'),
    'make handoff':   lambda s: generate_doc(s, 'handoff'),
    'ship it':        lambda s: ship_workspace(s),
}

def check_nl(text: str, session) -> bool:
    tl = text.lower().strip()
    for phrase, fn in NL.items():
        if phrase in tl:
            fn(session)
            return True
    return False

# ── Output ─────────────────────────────────────────────────────────────────────
def _extract(text: str) -> list:
    return [(m.group(1), m.group(2).strip())
            for m in re.finditer(r'```(\w+)\n([\s\S]*?)```', text)]

def _print_result(code: str, explanation: str):
    sep = c('─'*64, GRY)
    print(f"\n{sep}")
    if code:
        for lang, blk in _extract(code):
            fm = re.search(r'^[#/]{1,2}\s*FILE:\s*(.+)', blk, re.MULTILINE)
            fname = fm.group(1).strip() if fm else f'output.{lang}'
            lines = blk.split('\n')
            print(f"\n  {c('FILE:',ACC)} {bold(fname)}  {dim(f'({len(lines)} lines)')}")
            for ln in lines[:35]: print(f"  {c(ln,CYN)}")
            if len(lines) > 35:
                print(f"  {GRY}  … {len(lines)-35} more lines (saved){R}")
    if explanation:
        print()
        for ln in explanation.split('\n'):
            s = ln.lstrip()
            if s.startswith(('## ','# ')): print(f"  {bold(s.lstrip('#').strip())}")
            elif s.startswith(('- ','* ')): print(f"  {c('·',ACC)} {s[2:]}")
            else: print(f"  {ln}")
    print(f"{sep}\n")

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
            s = Session(); 
            if name: s.name = name
            return s
        # Delete: "d 2" or "d2"
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

# ── REPL ───────────────────────────────────────────────────────────────────────
def repl(session: Session):
    _refresh(session)
    session.ensure_venv()
    session.run_requirements()
    _last_error: dict = {}

    while True:
        try:
            lockin_indicator = c(' ⚡',YLW) if get_lockin() else ''
            inp = input(f"{c(session.name,GRY)}{lockin_indicator}{c(' ❯ ',ACC)}").strip()
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

        elif cmd == '/help':
            show_help(' '.join(args))

        elif args and args[-1].lower() in ('help','?'):
            # "/agents help" or "/files ?" → same as "/help agents"
            show_help(cmd.lstrip('/'))

        elif cmd in ('/plan','/agent'):
            if cmd == '/plan' and not args: show_plan()
            else: do_agent(args if cmd == '/agent' else [])

        elif cmd == '/clear':
            # Only clear screen, keep history
            clear_screen(); print(MINI+'\n')

        elif cmd in ('/home','/chats'):
            session.save()
            new_s = dashboard()
            session.__dict__.update(new_s.__dict__)
            clear_screen(); print(MINI+'\n')
            print(c(f'  Opened: {session.name}\n',GRN))
            session.ensure_venv(); session.run_requirements(); _refresh(session)

        elif cmd == '/newchat':
            session.save()
            name = ' '.join(args) if args else ''
            ns = Session()
            if name: ns.name = name
            session.__dict__.update(ns.__dict__)
            clear_screen(); print(MINI+'\n')
            print(c(f'  New chat: {session.name}\n',GRN))
            session.ensure_venv(); _refresh(session)

        elif cmd == '/rename':
            if not args: print(c('  Usage: /rename <new name>',YLW)); continue
            session.name = ' '.join(args)
            session.save()
            print(c(f'  Renamed to "{session.name}"',GRN))

        elif cmd == '/save':
            if args: session.name = ' '.join(args)
            session.save()
            print(c(f'  Saved as "{session.name}"',GRN))

        elif cmd == '/files':
            pat = args[0] if args else '*'
            list_files(session, f'**/{pat}' if '*' in pat else f'**/{pat}*' if pat != '*' else '**/*')

        elif cmd == '/run':
            res = run_file_cmd(session, args[0] if args else '', session.last_files)
            if res and res.get('diagnose'):
                _last_error = res
                diagnose(session, res['error'], res.get('file'))

        elif cmd == '/open':
            if args: open_file(session, args[0])
            else: print(c('  Usage: /open <file>',YLW))

        elif cmd == '/edit':
            if args: edit_file(session, args[0])
            else: print(c('  Usage: /edit <file>',YLW))

        elif cmd == '/delete':
            if args: delete_file(session, args[0]); _refresh(session)
            else: print(c('  Usage: /delete <file>',YLW))

        elif cmd == '/search':
            if args: search_files(session, ' '.join(args))
            else: print(c('  Usage: /search <term>',YLW))

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
            if args: export_file(session, args[0])
            else: print(c('  Usage: /export <file>',YLW))

        elif cmd == '/config':
            print(f"\n  {bold('Config')}\n")
            for k, v in _cfg.items():
                val = ('*'*8+str(v)[-4:]) if 'key' in k.lower() and v else (v or dim('not set'))
                print(f"  {c(k,ACC):<22} {val}")
            print()

        elif cmd == '/diagnose':
            if _last_error: diagnose(session, _last_error.get('error',''), _last_error.get('file'))
            else: print(c('  No recent error to diagnose.',YLW))

        elif cmd == '/stop':
            cancel_pipeline(); print(c('  Pipeline cancelled.',YLW))

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

        else:
            # Natural language shortcuts
            if check_nl(inp, session): continue

            # AI pipeline
            session.history.append({'role':'user','content':inp})
            print()
            try:
                if get_plan() == 'free':
                    msgs = [{'role':'system','content':'You are FraudeCode, a coding assistant.'}]
                    msgs += session.history[-10:]
                    with Spinner('HighKu thinking (may be slow)…'):
                        reply = call_ollama(msgs)
                    session.history.append({'role':'assistant','content':reply})
                    _print_result('', reply)
                else:
                    result = run_pipeline(inp)
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
                                res = run_file_cmd(session, py_files[-1].name, session.last_files)
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
    if not HAS_RL:
        print(c('  ⚠ pip install pyreadline3  for tab completion on Windows\n', YLW))
    session = dashboard()
    clear_screen(); print(MINI+'\n')
    print(f"  {bold('Chat:')} {c(session.name,ACC)}")
    plan_now = get_plan()
    print(f"  {bold('Plan:')} {c(PLAN_LABELS[plan_now],GRN)}")
    if plan_now == 'free' and not (_cfg.get('groqKey') or _cfg.get('geminiKey')):
        print(f"  {YLW}No API keys found. Run /setup or set keys in Fraude web app.{R}")
    print(f"  {dim('Type /help for commands  ·  Ctrl+C cancels AI request')}\n")
    repl(session)

if __name__ == '__main__':
    main()
