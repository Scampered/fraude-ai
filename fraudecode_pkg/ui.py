"""UI helpers: spinner, banners, permission prompts, file browser."""
import os, sys, threading, time
from pathlib import Path
from .colours import *

VERSION = "2.2"

BANNER = f"""
{ACC}╔══════════════════════════════════════════════════════════════╗{R}
{ACC}║{R}  {BOLD}FraudeCode{R}  {DIM}v{VERSION}{R}  ·  Multi-Agent Terminal Coding Tool      {ACC}║{R}
{ACC}║{R}  {DIM}Groq + Gemini + Ollama  ·  /help for commands{R}                {ACC}║{R}
{ACC}╚══════════════════════════════════════════════════════════════╝{R}"""

MINI = f"{ACC}┌─ FraudeCode v{VERSION} ────────────────────────────────────────┐{R}"

def clear_screen():
    os.system('cls' if sys.platform == 'win32' else 'clear')

class Spinner:
    FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    def __init__(self, msg=''):
        self.msg = msg
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
    def _run(self):
        i = 0
        while not self._stop.is_set():
            print(f"\r{GRY}{self.FRAMES[i%len(self.FRAMES)]} {self.msg}{R}  ", end='', flush=True)
            time.sleep(0.08); i += 1
        print('\r' + ' '*(len(self.msg)+6) + '\r', end='', flush=True)
    def __enter__(self): self._t.start(); return self
    def __exit__(self, *_): self._stop.set(); self._t.join()

DANGER_PATTERNS = ['os.remove','shutil.rmtree','os.rmdir','subprocess.call','eval(','exec(','os.system(']

def check_safety(code: str) -> list:
    return [p for p in DANGER_PATTERNS if p in code]

def ask_permission(action: str, detail: str = '') -> bool:
    print(f"\n  {YLW}⚠  Permission required{R}")
    print(f"  {WHT}{action}{R}")
    if detail: print(f"  {GRY}{detail}{R}")
    while True:
        try:
            ans = input(f"  {c('[Y] Allow',GRN)}  {c('[N] Deny',RED)}  > ").strip().lower()
        except (KeyboardInterrupt, EOFError): return False
        if ans in ('y','yes'): return True
        if ans in ('n','no',''): return False

def file_browser(start_dir: Path = None) -> Path | None:
    """Simple terminal file browser. Returns selected file or None."""
    cwd = start_dir or Path.home()
    while True:
        clear_screen()
        print(f"\n  {bold('File Browser')}  {dim(str(cwd))}\n")
        entries = []
        if cwd.parent != cwd:
            entries.append(('..', cwd.parent, True))
        try:
            dirs  = sorted([p for p in cwd.iterdir() if p.is_dir()  and not p.name.startswith('.')], key=lambda p: p.name.lower())
            files = sorted([p for p in cwd.iterdir() if p.is_file() and not p.name.startswith('.')], key=lambda p: p.name.lower())
        except PermissionError:
            print(c('  Permission denied', RED)); time.sleep(1); cwd = cwd.parent; continue
        for d in dirs:  entries.append((d.name + '/', d, True))
        for f in files: entries.append((f.name, f, False))
        for i, (name, _, is_dir) in enumerate(entries, 1):
            icon = c('📁', YLW) if is_dir else c('📄', GRY)
            print(f"  {c(str(i), GRY)}  {icon}  {WHT if is_dir else GRY}{name}{R}")
        print(f"\n  {GRY}Enter number to navigate, S to select current dir, Q to cancel{R}\n")
        try:
            ans = input(f"  {c('>',ACC)} ").strip().lower()
        except (KeyboardInterrupt, EOFError): return None
        if ans == 'q': return None
        if ans == 's': return cwd
        if ans.isdigit():
            idx = int(ans) - 1
            if 0 <= idx < len(entries):
                _, target, is_dir = entries[idx]
                if is_dir: cwd = target
                else: return target
