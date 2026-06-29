#!/usr/bin/env python3
"""
fraude_tray.py — Fraude System Tray App
Starts all local Fraude services and provides a tray icon for quick access.
Replaces start_ollama.bat entirely (or is started BY it).

Services managed:
  - Ollama (port 11434)
  - Fraude Proxy (port 11435) — ollama_proxy.py
  - FraudeRepo dashboard (port 7862) — frauderepo.py
  - Fraude Automations (port 7861) — fraude_automations.py

Run: pythonw fraude_tray.py  (Windows, hidden console)
  or python fraude_tray.py   (visible console for debug)
"""
import sys, os, time, threading, subprocess, json, webbrowser
from pathlib import Path

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))

# ── Dependencies ───────────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw
    import pystray
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pystray', 'Pillow',
                    '-q', '--disable-pip-version-check'], capture_output=True)
    from PIL import Image, ImageDraw
    import pystray

# ── Service status ─────────────────────────────────────────────────────────────
_status_lock = threading.Lock()
_status = {'ollama': False, 'proxy': False, 'repo': False, 'automations': False}
_procs = {}

def _check_port(port: int) -> bool:
    import socket
    try:
        with socket.create_connection(('localhost', port), timeout=1):
            return True
    except OSError:
        return False

def _update_status():
    with _status_lock:
        _status['ollama']      = _check_port(11434)
        _status['proxy']       = _check_port(11435)
        _status['repo']        = _check_port(7862)
        _status['automations'] = _check_port(7861)

def _snapshot():
    with _status_lock:
        return dict(_status)

# ── Start services ─────────────────────────────────────────────────────────────
def _popen_kwargs():
    """Platform kwargs so child processes can be cleanly killed as a tree."""
    if sys.platform == 'win32':
        return {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        return {'preexec_fn': os.setsid}  # new session/process group on POSIX

def _start_ollama():
    if _check_port(11434): return
    try:
        p = subprocess.Popen(['ollama', 'serve'], **_popen_kwargs())
        _procs['ollama'] = p
        for _ in range(15):
            time.sleep(1)
            if _check_port(11434): break
    except FileNotFoundError:
        pass  # Ollama not installed — proxy/automations still work without it

def _start_py(script_name: str, port: int):
    if _check_port(port): return
    script = HERE / script_name
    if not script.exists(): return
    p = subprocess.Popen([sys.executable, str(script)], cwd=str(HERE), **_popen_kwargs())
    _procs[script_name] = p

def start_all():
    threading.Thread(target=_start_ollama, daemon=True).start()
    time.sleep(1)
    threading.Thread(target=lambda: _start_py('ollama_proxy.py', 11435), daemon=True).start()
    threading.Thread(target=lambda: _start_py('frauderepo.py', 7862), daemon=True).start()
    threading.Thread(target=lambda: _start_py('fraude_automations.py', 7861), daemon=True).start()

def restart_all():
    for name, p in list(_procs.items()):
        _kill_proc_tree(p)
    _procs.clear()
    time.sleep(1)
    start_all()

# ── Tray icon drawing — matches the actual Fraude logo (FraudeLogo.jsx) ────────
# 12 dots orbiting a filled center dot, fading opacity, on a transparent background
import math

def _make_icon(online: bool = True) -> Image.Image:
    """Draw the real Fraude mark: ring of 12 dots + filled center, like the web logo."""
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx = cy = size / 2
    n = 12
    orbit_r = size * 0.38
    dot_r   = size * 0.052
    center_r = size * 0.14

    accent = (74, 158, 255) if online else (120, 120, 120)  # blue when healthy, grey when degraded

    # Faint outer ring guide (subtle, matches opacity .2 in the SVG)
    ring_r = size * 0.46
    d.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
              outline=accent + (50,), width=1)

    # 12 orbiting dots with the same fading-opacity pattern as the web logo
    for i in range(n):
        angle = (i / n) * 2 * math.pi - math.pi / 2
        opacity = 0.3 + 0.7 * (math.sin((i / n) * math.pi * 1.5 + 0.5) * 0.5 + 0.5)
        dx = cx + orbit_r * math.cos(angle)
        dy = cy + orbit_r * math.sin(angle)
        a = int(255 * opacity)
        d.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=accent + (a,))

    # Filled center dot with a small transparent hole (matches the SVG's two circles)
    d.ellipse([cx - center_r, cy - center_r, cx + center_r, cy + center_r], fill=accent + (255,))
    hole_r = center_r * 0.42
    d.ellipse([cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r], fill=(0, 0, 0, 0))

    return img

# ── Actions ─────────────────────────────────────────────────────────────────────
def open_fraude(icon=None, item=None): webbrowser.open('https://fraude-ai.vercel.app')
def open_repo(icon=None, item=None):   webbrowser.open('http://localhost:7862')

def open_cli(icon=None, item=None):
    script = HERE / 'fraudecode.py'
    if not script.exists(): return
    if sys.platform == 'win32':
        subprocess.Popen(['cmd', '/k', f'python "{script}"'], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen(['bash', '-c', f'python "{script}"; read'])

def do_restart(icon=None, item=None):
    restart_all()

def _kill_proc_tree(proc):
    """Terminate a process and any children it spawned (e.g. ollama serve, python servers)."""
    try:
        pid = proc.pid
    except Exception:
        return
    if sys.platform == 'win32':
        # /T kills the whole process tree (parent + children), /F forces it
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            import signal as _signal
            os.killpg(os.getpgid(pid), _signal.SIGTERM)
        except Exception:
            try: proc.terminate()
            except Exception: pass

def do_quit(icon=None, item=None):
    """Quit Fraude — terminates every service this tray started before exiting."""
    for name, p in list(_procs.items()):
        _kill_proc_tree(p)
    _procs.clear()
    if icon: icon.stop()

# ── Dynamic menu text — pystray calls these with the MenuItem as sole argument ──
def _status_text(name, port, label):
    def _inner(item):
        ok = _snapshot().get(name, False)
        return ('✓ ' if ok else '✗ ') + f'{label} :{port}'
    return _inner

def _summary_text(item):
    s = _snapshot()
    ok = sum(s.values())
    return f'Fraude  —  {ok}/{len(s)} services online'

def build_menu():
    return pystray.Menu(
        pystray.MenuItem(_summary_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Open Fraude Web',   open_fraude),
        pystray.MenuItem('Open FraudeRepo',   open_repo),
        pystray.MenuItem('Launch FraudeCode', open_cli),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_status_text('proxy', 11435, 'Proxy'),             None, enabled=False),
        pystray.MenuItem(_status_text('repo', 7862, 'FraudeRepo'),         None, enabled=False),
        pystray.MenuItem(_status_text('automations', 7861, 'Automations'), None, enabled=False),
        pystray.MenuItem(_status_text('ollama', 11434, 'Ollama'),          None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Restart All Services', do_restart),
        pystray.MenuItem('Quit Fraude',           do_quit),
    )

# ── Status polling — updates icon colour and forces menu redraw ────────────────
def _poll_loop(icon):
    while True:
        time.sleep(10)
        _update_status()
        s = _snapshot()
        all_ok = all(s.values())
        try:
            icon.icon = _make_icon(all_ok)
            icon.update_menu()  # forces dynamic text (_summary_text etc) to refresh
        except Exception:
            pass

import atexit, signal as _signal_mod

def _cleanup_on_exit():
    """Safety net: runs even if the tray is killed abruptly (not via the Quit menu item)."""
    for name, p in list(_procs.items()):
        _kill_proc_tree(p)

atexit.register(_cleanup_on_exit)
try:
    _signal_mod.signal(_signal_mod.SIGTERM, lambda *a: (_cleanup_on_exit(), sys.exit(0)))
    if sys.platform != 'win32':
        _signal_mod.signal(_signal_mod.SIGINT, lambda *a: (_cleanup_on_exit(), sys.exit(0)))
except Exception:
    pass  # Some signals aren't available on all platforms

# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    print('Starting Fraude services...')
    start_all()
    time.sleep(2)
    _update_status()

    icon = pystray.Icon(
        'Fraude',
        icon=_make_icon(any(_snapshot().values())),
        title='Fraude AI — Running',
        menu=build_menu(),
    )

    threading.Thread(target=_poll_loop, args=(icon,), daemon=True).start()

    print('Fraude tray running. Look for the blue F icon in your taskbar tray')
    print('(click the ^ arrow to show hidden icons if you don\'t see it).')
    icon.run()

if __name__ == '__main__':
    main()
