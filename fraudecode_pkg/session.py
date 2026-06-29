"""Chat session management with virtual environments."""
import json, subprocess, sys, os
from pathlib import Path
from datetime import datetime
from .colours import *
from .config import CODE_DIR

def _find_python() -> str:
    order = ['python','py','python3'] if sys.platform=='win32' else ['python3','python']
    for cmd in order:
        try:
            r = subprocess.run([cmd,'--version'], capture_output=True, timeout=3)
            if r.returncode == 0: return cmd
        except Exception: pass
    return 'python'

PY = _find_python()

class Session:
    def __init__(self, sid: str = None, name: str = None):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.id          = sid or ts
        self.name        = name or f'chat-{ts[-6:]}'
        self.history: list = []
        self.last_files: list = []
        self.repo_url    = ''
        self.path        = CODE_DIR / f'_session_{self.id}.json'
        # Each session gets its own subdirectory
        self.workdir     = CODE_DIR / f'workspace_{self.id}'
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.venv_dir    = self.workdir / '.venv'
        self._venv_ready = False

    # ── Persistence ───────────────────────────────────────────────────────────
    def save(self):
        self.path.write_text(json.dumps({
            'id': self.id, 'name': self.name,
            'history': self.history,
            'repo_url': self.repo_url,
            'agent_override': getattr(self, 'agent_override', ''),
            'updated': datetime.now().isoformat()
        }, indent=2, ensure_ascii=False), encoding='utf-8')

    @staticmethod
    def load(p: Path) -> 'Session':
        d = json.loads(p.read_text('utf-8'))
        s = Session(d['id'], d.get('name'))
        s.history        = d.get('history', [])
        s.repo_url       = d.get('repo_url', '')
        s.agent_override = d.get('agent_override', '')
        s.workdir  = CODE_DIR / f'workspace_{s.id}'
        s.workdir.mkdir(parents=True, exist_ok=True)
        s.venv_dir = s.workdir / '.venv'
        s._venv_ready = s.venv_dir.exists()
        return s

    @staticmethod
    def all() -> list:
        out = []
        for p in sorted(CODE_DIR.glob('_session_*.json'), reverse=True):
            try: out.append(Session.load(p))
            except Exception: pass
        return out

    # ── Virtual environment ───────────────────────────────────────────────────
    def ensure_venv(self, log=True) -> str:
        """Create venv if not exists. Returns venv python path."""
        venv_py = (self.venv_dir / 'Scripts' / 'python.exe') if sys.platform=='win32' \
                  else (self.venv_dir / 'bin' / 'python')
        if not venv_py.exists():
            if log: print(c(f'\n  Creating virtual environment for {self.name}…', GRY))
            r = subprocess.run([PY, '-m', 'venv', str(self.venv_dir)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                print(c(f'  venv failed: {r.stderr[:200]}', RED))
                return PY
            if log: print(c('  ✓ venv created', GRN))
        self._venv_ready = True
        return str(venv_py)

    def venv_pip_install(self, packages: list, quiet=True) -> bool:
        venv_py = self.ensure_venv(log=False)
        args = [venv_py, '-m', 'pip', 'install'] + packages
        if quiet: args.append('--quiet')
        r = subprocess.run(args, capture_output=True, text=True, cwd=self.workdir)
        return r.returncode == 0

    def run_requirements(self) -> bool:
        req = self.workdir / 'requirements.txt'
        if not req.exists(): return True
        print(c(f'  Installing requirements.txt…', GRY))
        venv_py = self.ensure_venv()
        r = subprocess.run([venv_py, '-m', 'pip', 'install', '-r', str(req), '--quiet'],
                           capture_output=True, text=True, cwd=self.workdir)
        if r.returncode == 0:
            print(c('  ✓ requirements installed', GRN))
        else:
            print(c(f'  ✗ {r.stderr.strip()[:300]}', RED))
        return r.returncode == 0

    def run_file(self, path: Path) -> subprocess.CompletedProcess:
        """Run a file in this session's venv — interactive mode (no output capture)."""
        venv_py = self.ensure_venv(log=False)
        ext = path.suffix.lower()
        if ext == '.py':
            cmd = [venv_py, str(path)]
        elif ext in ('.sh','.bash'):
            cmd = ['bash', str(path)]
        elif ext in ('.js',):
            cmd = ['node', str(path)]
        else:
            raise ValueError(f'Cannot run {ext} files automatically')
        # Run interactively — stdout/stderr go directly to terminal, stdin from terminal
        # This lets the user see prompts and type input in real time
        r = subprocess.run(cmd, cwd=self.workdir, timeout=300)
        # Return a minimal result object for compatibility
        return type('Result', (), {'returncode': r.returncode, 'stdout': '', 'stderr': ''})()

    def clone_repo(self, url: str) -> bool:
        """Clone a git repo into a subdirectory of this session's workspace."""
        import re as _re
        print(c(f'\n  Cloning {url}…', GRY))
        # Extract repo name for subfolder
        repo_name = _re.sub(r'\.git$','', url.rstrip('/').split('/')[-1]) or 'repo'
        clone_dir = self.workdir / repo_name
        if clone_dir.exists():
            import shutil as _sh
            print(c(f'  Removing existing {repo_name}/ to reclone…', GRY))
            _sh.rmtree(clone_dir, ignore_errors=True)
        clone_dir.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(['git', 'clone', url, str(clone_dir)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            self.repo_url = url
            print(c(f'  ✓ Cloned into {repo_name}/', GRN))
            # Move requirements.txt to workdir level if found
            req = clone_dir / 'requirements.txt'
            if req.exists():
                import shutil as _sh
                _sh.copy2(req, self.workdir / 'requirements.txt')
            return True
        print(c(f'  ✗ {r.stderr.strip()[:300]}', RED))
        return False

    def list_files(self) -> list:
        return sorted(f for f in self.workdir.glob('**/*')
                      if f.is_file() and '.venv' not in str(f) and not f.name.startswith('_'))

    def save_code(self, lang: str, code: str) -> Path:
        import re
        ext = {'python':'py','javascript':'js','typescript':'ts','html':'html',
               'css':'css','bash':'sh','sql':'sql','json':'json','markdown':'md'}.get(lang,lang)
        fm = re.search(r'^[#/]{1,2}\s*FILE:\s*(.+)', code, re.MULTILINE)
        fname = fm.group(1).strip() if fm else f'output_{__import__("time").time():.0f}.{ext}'
        dest = self.workdir / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(code, encoding='utf-8')
        return dest

    def zip_workspace(self) -> Path | None:
        """Package all non-venv files as a zip. Returns path."""
        import zipfile
        files = self.list_files()
        if not files: return None
        out = CODE_DIR / f'{self.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in files:
                arcname = f.relative_to(self.workdir)
                z.write(f, arcname)
        return out
