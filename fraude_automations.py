#!/usr/bin/env python3
"""
fraude_automations.py — Fraude Automation Action Server
Runs on localhost:7861. Receives action requests from the web automations page
and executes them on the local machine.

Architecture:
  POST /action    { type, config } -> { ok, result }
  GET  /status                     -> { ok, version, tools }
  GET  /tools                      -> list of all supported action types
  POST /ai                         -> { prompt, model, context } -> { ok, result }
"""
import json, os, sys, time, subprocess, threading, platform
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))

PORT = 7861
VERSION = '1.0.0'
PLATFORM = platform.system()  # Windows / Darwin / Linux

# ── Tool implementations ───────────────────────────────────────────────────────

class MouseTools:
    @staticmethod
    def move_cursor(x: int, y: int) -> str:
        import pyautogui
        pyautogui.moveTo(x, y, duration=0.15)
        return f'Moved to {x},{y}'

    @staticmethod
    def click_at(x: int, y: int, button: str = 'left') -> str:
        import pyautogui
        pyautogui.click(x, y, button=button)
        return f'Clicked {button} at {x},{y}'

    @staticmethod
    def right_click_at(x: int, y: int) -> str:
        import pyautogui
        pyautogui.rightClick(x, y)
        return f'Right-clicked at {x},{y}'

    @staticmethod
    def double_click_at(x: int, y: int) -> str:
        import pyautogui
        pyautogui.doubleClick(x, y)
        return f'Double-clicked at {x},{y}'

    @staticmethod
    def drag_mouse(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
        import pyautogui
        pyautogui.dragTo(x2, y2, duration=duration, mouseDownCoords=(x1, y1))
        return f'Dragged from {x1},{y1} to {x2},{y2}'

    @staticmethod
    def scroll(direction: str = 'down', amount: int = 3) -> str:
        import pyautogui
        clicks = -amount if direction == 'down' else amount
        pyautogui.scroll(clicks)
        return f'Scrolled {direction} {amount}'

    @staticmethod
    def get_cursor_position() -> str:
        import pyautogui
        pos = pyautogui.position()
        return json.dumps({'x': pos.x, 'y': pos.y})


class KeyboardTools:
    # Cross-platform modifier key normalisation — let the user/frontend say
    # "win", "cmd", "command", "super", "meta" interchangeably and PyAutoGUI
    # gets the name it actually expects for the current OS.
    _MODIFIER_MAP = {
        'Windows': {'cmd': 'win', 'command': 'win', 'super': 'win', 'meta': 'win', 'option': 'alt'},
        'Darwin':  {'win': 'cmd', 'windows': 'cmd', 'super': 'cmd', 'meta': 'cmd', 'alt': 'option', 'ctrl': 'control'},
        'Linux':   {'cmd': 'super', 'command': 'super', 'win': 'super', 'meta': 'super', 'option': 'alt'},
    }

    @staticmethod
    def _normalize_key(key: str) -> str:
        k = key.strip().lower()
        return KeyboardTools._MODIFIER_MAP.get(PLATFORM, {}).get(k, k)

    @staticmethod
    def type_text(text: str, interval: float = 0.02) -> str:
        import pyautogui
        pyautogui.typewrite(text, interval=interval)
        return f'Typed {len(text)} chars'

    @staticmethod
    def press_key(key: str) -> str:
        import pyautogui
        pyautogui.press(KeyboardTools._normalize_key(key))
        return f'Pressed {key}'

    @staticmethod
    def hotkey(*keys) -> str:
        import pyautogui
        normalized = [KeyboardTools._normalize_key(k) for k in keys]
        pyautogui.hotkey(*normalized)
        return f'Hotkey: {"+".join(keys)}'


class AppTools:
    # Per-platform alias tables — same user-facing name resolves differently per OS
    _WIN_ALIASES = {
        'chrome': 'chrome', 'firefox': 'firefox', 'edge': 'msedge',
        'notepad': 'notepad', 'calculator': 'calc', 'explorer': 'explorer',
        'spotify': 'spotify', 'discord': 'discord', 'steam': 'steam',
        'vscode': 'code', 'code': 'code', 'terminal': 'cmd',
        'settings': 'ms-settings:', 'store': 'ms-windows-store:',
        'word': 'winword', 'excel': 'excel', 'powerpoint': 'powerpnt', 'paint': 'mspaint',
        'obs': 'obs64', 'vlc': 'vlc', 'zoom': 'zoom', 'teams': 'teams',
        'whatsapp': 'whatsapp', 'slack': 'slack', 'telegram': 'telegram',
    }
    # macOS uses the full .app display name with `open -a`
    _MAC_ALIASES = {
        'chrome': 'Google Chrome', 'firefox': 'Firefox', 'edge': 'Microsoft Edge', 'safari': 'Safari',
        'notepad': 'TextEdit', 'calculator': 'Calculator', 'explorer': 'Finder', 'finder': 'Finder',
        'spotify': 'Spotify', 'discord': 'Discord', 'steam': 'Steam',
        'vscode': 'Visual Studio Code', 'code': 'Visual Studio Code', 'terminal': 'Terminal',
        'settings': 'System Settings', 'store': 'App Store',
        'word': 'Microsoft Word', 'excel': 'Microsoft Excel', 'powerpoint': 'Microsoft PowerPoint',
        'paint': 'Preview', 'obs': 'OBS', 'vlc': 'VLC', 'zoom': 'zoom.us', 'teams': 'Microsoft Teams',
        'whatsapp': 'WhatsApp', 'slack': 'Slack', 'telegram': 'Telegram',
    }
    # Linux: tries common binary names (varies a lot by distro/desktop)
    _LINUX_ALIASES = {
        'chrome': 'google-chrome', 'firefox': 'firefox', 'edge': 'microsoft-edge',
        'notepad': 'gedit', 'calculator': 'gnome-calculator', 'explorer': 'nautilus',
        'spotify': 'spotify', 'discord': 'discord', 'steam': 'steam',
        'vscode': 'code', 'code': 'code', 'terminal': 'gnome-terminal',
        'settings': 'gnome-control-center',
        'paint': 'gimp', 'obs': 'obs', 'vlc': 'vlc', 'zoom': 'zoom',
        'slack': 'slack', 'telegram': 'telegram-desktop',
    }

    @staticmethod
    def _alias_table():
        if PLATFORM == 'Windows': return AppTools._WIN_ALIASES
        if PLATFORM == 'Darwin':  return AppTools._MAC_ALIASES
        return AppTools._LINUX_ALIASES

    @staticmethod
    def open_app(name: str) -> str:
        table = AppTools._alias_table()
        target = table.get(name.lower(), name)
        try:
            if PLATFORM == 'Windows':
                if '://' in target or target.endswith(':'):
                    os.startfile(target)
                else:
                    subprocess.Popen([target])
            elif PLATFORM == 'Darwin':
                subprocess.run(['open', '-a', target], check=True)
            else:
                subprocess.Popen([target])
            return f'Opened {name}'
        except Exception:
            try:
                if PLATFORM == 'Windows':
                    import pyautogui
                    pyautogui.hotkey('win', 's')
                    time.sleep(0.5)
                    pyautogui.typewrite(name, interval=0.05)
                    return f'Searching for {name}\u2026'
                elif PLATFORM == 'Darwin':
                    import pyautogui
                    pyautogui.hotkey('command', 'space')
                    time.sleep(0.4)
                    pyautogui.typewrite(name, interval=0.04)
                    time.sleep(0.3)
                    pyautogui.press('return')
                    return f'Opened via Spotlight: {name}'
                else:
                    for launcher in ('gtk-launch', 'xdg-open'):
                        try:
                            subprocess.Popen([launcher, name]); return f'Opened {name}'
                        except FileNotFoundError:
                            continue
                    return f'Could not open {name} \u2014 app not found'
            except Exception as e2:
                return f'Error opening {name}: {e2}'

    @staticmethod
    def close_app(name: str) -> str:
        table = AppTools._alias_table()
        target = table.get(name.lower(), name)
        if PLATFORM == 'Windows':
            exe = target if target.lower().endswith('.exe') else f'{target}.exe'
            r = subprocess.run(['taskkill', '/f', '/im', exe], capture_output=True, text=True)
            return r.stdout.strip() or r.stderr.strip() or f'Closed {name}'
        elif PLATFORM == 'Darwin':
            script = f'tell application "{target}" to quit'
            r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            if r.returncode == 0:
                return f'Closed {target}'
            subprocess.run(['pkill', '-f', target], capture_output=True, text=True)
            return f'Sent quit signal to {target}'
        else:
            r = subprocess.run(['pkill', '-f', target], capture_output=True, text=True)
            return f'Sent kill signal to {target}'

    @staticmethod
    def open_url(url: str) -> str:
        import webbrowser
        webbrowser.open(url)
        return f'Opened {url}'

    @staticmethod
    def run_file(path: str) -> str:
        p = Path(path).expanduser()
        if not p.exists(): return f'Not found: {path}'
        if PLATFORM == 'Windows':
            os.startfile(str(p))
        elif PLATFORM == 'Darwin':
            subprocess.Popen(['open', str(p)])
        else:
            subprocess.Popen(['xdg-open', str(p)])
        return f'Opened {p.name}'

    @staticmethod
    def run_command(cmd: str, timeout: int = 20) -> str:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            out = (r.stdout + r.stderr).strip()
            return out[:2000] if out else f'Exit {r.returncode}'
        except subprocess.TimeoutExpired:
            return 'Command timed out'
        except Exception as e:
            return f'Error: {e}'

class SystemTools:
    @staticmethod
    def get_system_info() -> str:
        import psutil
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return json.dumps({
                'cpu': f'{cpu}%',
                'ram': f'{ram.percent}% ({ram.used//1024//1024}MB / {ram.total//1024//1024}MB)',
                'disk': f'{disk.percent}% used',
                'platform': PLATFORM,
            })
        except Exception:
            return json.dumps({'platform': PLATFORM})

    @staticmethod
    def screenshot(path: str = '') -> str:
        try:
            save_path = path or str(Path.home() / 'Desktop' / f'fraude_screenshot_{int(time.time())}.png')
            if PLATFORM == 'Linux':
                # PIL.ImageGrab doesn't support Linux — shell out to scrot/gnome-screenshot
                for tool, args in (('scrot', [save_path]), ('gnome-screenshot', ['-f', save_path])):
                    try:
                        subprocess.run([tool, *args], check=True, capture_output=True)
                        return f'Screenshot saved to {save_path}'
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        continue
                return 'Screenshot failed: install scrot or gnome-screenshot'
            else:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(save_path)
                return f'Screenshot saved to {save_path}'
        except Exception as e:
            return f'Screenshot failed: {e}'

    @staticmethod
    def screenshot_b64() -> str:
        """Return screenshot as base64 PNG."""
        import base64, io
        try:
            if PLATFORM == 'Linux':
                tmp = f'/tmp/fraude_shot_{int(time.time())}.png'
                for tool, args in (('scrot', [tmp]), ('gnome-screenshot', ['-f', tmp])):
                    try:
                        subprocess.run([tool, *args], check=True, capture_output=True)
                        data = Path(tmp).read_bytes()
                        Path(tmp).unlink(missing_ok=True)
                        return base64.b64encode(data).decode()
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        continue
                return ''
            from PIL import ImageGrab
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return ''

    @staticmethod
    def notify(title: str, message: str) -> str:
        """Native, non-blocking notification per platform — never blocks the action server."""
        try:
            if PLATFORM == 'Windows':
                try:
                    from win10toast import ToastNotifier
                    ToastNotifier().show_toast(title, message, duration=4, threaded=True)
                    return 'Notification sent'
                except Exception:
                    pass
                # Fallback: PowerShell toast via BurntToast-free WinRT call
                ps = (f'[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,'
                      f'ContentType=WindowsRuntime] | Out-Null')
                subprocess.run(['powershell', '-NoProfile', '-Command',
                    f'New-BurntToastNotification -Text "{title}","{message}"'],
                    capture_output=True, timeout=3)
                return 'Notification sent'
            elif PLATFORM == 'Darwin':
                # Native macOS notification center — instant, non-blocking
                safe_title = title.replace('"', "'")
                safe_msg = message.replace('"', "'")
                subprocess.run(['osascript', '-e',
                    f'display notification "{safe_msg}" with title "{safe_title}"'],
                    capture_output=True, timeout=3)
                return 'Notification sent'
            else:
                # Linux desktop notification (works on GNOME/KDE/most DEs)
                try:
                    subprocess.run(['notify-send', title, message], capture_output=True, timeout=3, check=True)
                    return 'Notification sent'
                except (FileNotFoundError, subprocess.CalledProcessError):
                    pass
        except Exception:
            pass
        # Last-resort fallback: blocking tkinter messagebox (only if nothing native worked)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showinfo(title, message)
            root.destroy()
            return 'Alert shown (fallback)'
        except Exception as e:
            return f'Notify failed: {e}'

    @staticmethod
    def set_volume(level: int) -> str:
        level = max(0, min(100, int(level)))
        if PLATFORM == 'Windows':
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(level / 100, None)
                return f'Volume set to {level}%'
            except Exception:
                pass
        if PLATFORM == 'Darwin':
            subprocess.run(['osascript', '-e', f'set volume output volume {level}'])
            return f'Volume set to {level}%'
        # Linux: try pactl first (PulseAudio/PipeWire, more common now), fall back to amixer
        try:
            subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{level}%'], check=True, capture_output=True)
            return f'Volume set to {level}%'
        except (FileNotFoundError, subprocess.CalledProcessError):
            subprocess.run(['amixer', '-D', 'pulse', 'sset', 'Master', f'{level}%'], capture_output=True)
            return f'Volume set to {level}%'

    @staticmethod
    def lock_screen() -> str:
        if PLATFORM == 'Windows':
            subprocess.run(['rundll32', 'user32.dll,LockWorkStation'])
        elif PLATFORM == 'Darwin':
            # CGSession path varies by macOS version; pmset fallback always works
            cg_path = '/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession'
            if Path(cg_path).exists():
                subprocess.run([cg_path, '-suspend'])
            else:
                subprocess.run(['pmset', 'displaysleepnow'])
        else:
            # Try the most common Linux lock commands in order
            for cmd in (['xdg-screensaver', 'lock'], ['loginctl', 'lock-session'],
                       ['gnome-screensaver-command', '--lock'], ['dm-tool', 'lock']):
                try:
                    subprocess.run(cmd, check=True, capture_output=True); break
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
        return 'Screen locked'

    @staticmethod
    def shutdown_computer(delay_seconds: int = 0) -> str:
        if PLATFORM == 'Windows':
            subprocess.run(['shutdown', '/s', '/t', str(delay_seconds)])
        elif PLATFORM == 'Darwin':
            # macOS shutdown requires root; osascript can prompt for it via System Events
            subprocess.run(['osascript', '-e',
                f'delay {delay_seconds}' if delay_seconds else '',
                '-e', 'tell app "System Events" to shut down'])
        else:
            subprocess.run(['sudo', 'shutdown', '-h', f'+{max(1, delay_seconds // 60)}'])
        return f'Shutdown in {delay_seconds}s'


class FileTools:
    @staticmethod
    def read_file(path: str, max_chars: int = 8000) -> str:
        p = Path(path).expanduser()
        if not p.exists(): return f'Not found: {path}'
        return p.read_text('utf-8', errors='replace')[:max_chars]

    @staticmethod
    def write_file(path: str, content: str, mode: str = 'w') -> str:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.open(mode, encoding='utf-8').write(content)
        return f'Written: {p} ({len(content)} chars)'

    @staticmethod
    def delete_file(path: str) -> str:
        p = Path(path).expanduser()
        if not p.exists(): return f'Not found: {path}'
        if PLATFORM == 'Windows':
            try:
                import send2trash
                send2trash.send2trash(str(p))
                return f'Moved to recycle bin: {p.name}'
            except Exception:
                pass
        p.unlink()
        return f'Deleted: {p.name}'

    @staticmethod
    def copy_clipboard() -> str:
        try:
            import pyperclip
            return pyperclip.paste()
        except Exception:
            import subprocess
            if PLATFORM == 'Windows':
                r = subprocess.run(['powershell', 'Get-Clipboard'], capture_output=True, text=True)
                return r.stdout.strip()
            return ''

    @staticmethod
    def paste_clipboard(text: str = '') -> str:
        import pyautogui, pyperclip
        if text:
            pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        return 'Pasted'

    @staticmethod
    def find_file(query: str, path: str = '') -> str:
        search_root = Path(path).expanduser() if path else Path.home()
        results = []
        for p in search_root.rglob('*'):
            if query.lower() in p.name.lower():
                results.append(str(p))
                if len(results) >= 10: break
        return json.dumps(results) if results else f'No files matching "{query}"'


class ClipboardTools:
    @staticmethod
    def copy(text: str) -> str:
        import pyperclip
        pyperclip.copy(text)
        return f'Copied: {text[:40]}'

    @staticmethod
    def paste() -> str:
        import pyperclip
        t = pyperclip.paste()
        import pyautogui
        pyautogui.typewrite(t, interval=0.01)
        return f'Pasted {len(t)} chars'

# ── Dispatcher ─────────────────────────────────────────────────────────────────
def dispatch(action_type: str, cfg: dict) -> dict:
    """Route an action type to the correct tool method."""
    try:
        # Mouse
        if action_type == 'act_move':    return {'ok': True, 'result': MouseTools.move_cursor(int(cfg.get('x',0)), int(cfg.get('y',0)))}
        if action_type == 'act_click':   return {'ok': True, 'result': MouseTools.click_at(int(cfg.get('x',0)), int(cfg.get('y',0)), cfg.get('button','left'))}
        if action_type == 'act_scroll':  return {'ok': True, 'result': MouseTools.scroll(cfg.get('direction','down'), int(cfg.get('amount',3)))}
        if action_type == 'sys_mousepos':
            import pyautogui
            pos = pyautogui.position()
            return {'ok': True, 'result': f'{pos.x},{pos.y}', 'x': pos.x, 'y': pos.y}

        # Keyboard
        if action_type == 'act_type':    return {'ok': True, 'result': KeyboardTools.type_text(cfg.get('text',''))}
        if action_type == 'act_keys':    return {'ok': True, 'result': KeyboardTools.hotkey(*cfg.get('keys','ctrl+c').split('+'))}

        # Apps
        if action_type == 'act_open':    return {'ok': True, 'result': AppTools.open_app(cfg.get('app',''))}
        if action_type == 'act_close':   return {'ok': True, 'result': AppTools.close_app(cfg.get('app',''))}
        if action_type == 'act_browser': return {'ok': True, 'result': AppTools.open_url(cfg.get('url',''))}
        if action_type == 'act_run':     return {'ok': True, 'result': AppTools.run_file(cfg.get('path',''))}
        if action_type == 'sys_cmd':     return {'ok': True, 'result': AppTools.run_command(cfg.get('command',''))}

        # System
        if action_type == 'sys_notify':
            text = cfg.get('message', cfg.get('text', ''))
            return {'ok': True, 'result': SystemTools.notify(cfg.get('title','Fraude'), text)}
        if action_type == 'sys_screenshot': return {'ok': True, 'result': SystemTools.screenshot(cfg.get('path',''))}
        if action_type == 'sys_shutdown':
            action = cfg.get('action', 'shutdown')
            if action == 'shutdown': return {'ok': True, 'result': SystemTools.shutdown_computer(int(cfg.get('delay',1)))}
        if action_type == 'sys_sound':
            t = cfg.get('type', 'beep')
            if t == 'tts':
                text = cfg.get('text', '')
                try:
                    import edge_tts, asyncio, tempfile
                    async def _tts():
                        comm = edge_tts.Communicate(text, 'en-US-GuyNeural')
                        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                            path = f.name
                        await comm.save(path)
                        if PLATFORM == 'Windows':
                            # PowerShell MediaPlayer actually plays the file (previous version was a no-op)
                            ps_cmd = (
                                f'Add-Type -AssemblyName presentationCore; '
                                f'$p = New-Object System.Windows.Media.MediaPlayer; '
                                f'$p.Open([uri]"{path}"); $p.Play(); Start-Sleep -Seconds 5'
                            )
                            subprocess.Popen(['powershell', '-NoProfile', '-Command', ps_cmd],
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                        elif PLATFORM == 'Darwin':
                            subprocess.Popen(['afplay', path])
                        else:
                            for player in ('mpg123', 'ffplay', 'paplay'):
                                try:
                                    args = [player, '-nodisp', '-autoexit', path] if player == 'ffplay' else [player, path]
                                    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    break
                                except FileNotFoundError:
                                    continue
                    asyncio.run(_tts())
                    return {'ok': True, 'result': f'Speaking: {text[:40]}'}
                except Exception as e:
                    return {'ok': False, 'result': f'TTS failed: {e}'}
            if t in ('beep', 'ding'):
                freq = 440 if t == 'beep' else 880
                try:
                    if PLATFORM == 'Windows':
                        import winsound
                        winsound.Beep(freq, 300)
                    elif PLATFORM == 'Darwin':
                        # macOS has no programmatic beep API — play a built-in system sound
                        sound = '/System/Library/Sounds/Tink.aiff' if t == 'ding' else '/System/Library/Sounds/Pop.aiff'
                        subprocess.run(['afplay', sound], capture_output=True, timeout=2)
                    else:
                        # Linux: try the bell escape, then common sound tools
                        try:
                            print('\\a', end='', flush=True)
                        except Exception:
                            pass
                        for player, sound in (('paplay', '/usr/share/sounds/freedesktop/stereo/bell.oga'),
                                              ('aplay', '/usr/share/sounds/alsa/Front_Center.wav')):
                            try:
                                subprocess.run([player, sound], capture_output=True, timeout=2, check=True)
                                break
                            except (FileNotFoundError, subprocess.CalledProcessError):
                                continue
                    return {'ok': True, 'result': f'{t.capitalize()}ed'}
                except Exception as e:
                    return {'ok': False, 'result': f'Sound failed: {e}'}

        # Files
        if action_type == 'sys_file':
            op = cfg.get('op', 'read')
            path = cfg.get('path', '')
            if op == 'read':   return {'ok': True, 'result': FileTools.read_file(path)}
            if op == 'write':  return {'ok': True, 'result': FileTools.write_file(path, cfg.get('content',''))}
            if op == 'append': return {'ok': True, 'result': FileTools.write_file(path, cfg.get('content',''), 'a')}
            if op == 'delete': return {'ok': True, 'result': FileTools.delete_file(path)}
            if op == 'exists': return {'ok': True, 'result': str(Path(path).expanduser().exists())}
            if op == 'list':   return {'ok': True, 'result': json.dumps([str(p) for p in Path(path).expanduser().iterdir()][:50])}
        if action_type == 'sys_file_find': return {'ok': True, 'result': FileTools.find_file(cfg.get('search',''), cfg.get('dir',''))}
        if action_type == 'sys_file_make':
            path = cfg.get('path','output.py')
            content = cfg.get('content', f'# {path}\n')
            r = FileTools.write_file(path, content)
            if cfg.get('run_after') == 'yes':
                AppTools.run_command(f'python "{path}"')
            return {'ok': True, 'result': r}

        # Clipboard
        if action_type == 'sys_copy':  return {'ok': True, 'result': FileTools.copy_clipboard()}
        if action_type == 'sys_paste': return {'ok': True, 'result': ClipboardTools.paste()}

        # AI actions — forward to Fraude proxy
        if action_type in ('ai_think','ai_generate','ai_action','ai_screen','ai_ask','ai_context'):
            return _handle_ai_action(action_type, cfg)

        # Client-side handled — just acknowledge
        if action_type in ('evt_start','evt_stop','evt_wait','evt_time','logic_if','logic_loop',
                           'flow_split','flow_remote_s','flow_remote_r','flow_ratelimit',
                           'flow_checkpoint','ask_user','evt_hotkey'):
            return {'ok': True, 'result': 'acknowledged'}

        return {'ok': False, 'result': f'Unknown action: {action_type}'}

    except ImportError as e:
        pkg = str(e).replace('No module named ', '').strip("'")
        return {'ok': False, 'result': f'Missing package: {pkg} — run: pip install {pkg}'}
    except Exception as e:
        return {'ok': False, 'result': f'Error: {type(e).__name__}: {e}'}


def _handle_ai_action(action_type: str, cfg: dict) -> dict:
    """Forward AI actions to the Fraude Ollama proxy."""
    try:
        import urllib.request
        prompt = cfg.get('goal') or cfg.get('prompt') or cfg.get('text', '')
        if action_type == 'ai_screen':
            # Take screenshot and include in prompt
            b64 = SystemTools.screenshot_b64()
            if b64: prompt = f'[screenshot attached]\n{prompt}'

        # Try the local proxy
        body = json.dumps({
            'model': cfg.get('model', 'llama3.2'),
            'messages': [{'role': 'user', 'content': prompt}],
            'stream': False,
        }).encode()
        req = urllib.request.Request('http://localhost:11435/api/chat',
            data=body, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        result = d.get('message', {}).get('content', '') or d.get('content', '')

        # If ai_action, try to execute what the AI decided
        if action_type == 'ai_action' and result:
            return {'ok': True, 'result': result, 'ai_decided': True}
        return {'ok': True, 'result': result}
    except Exception as e:
        return {'ok': False, 'result': f'AI action failed: {e}'}


# ── HTTP Server ────────────────────────────────────────────────────────────────
CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Private-Network': 'true',
}

class AutomationHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, data, content_type='application/json'):
        body = (json.dumps(data) if isinstance(data, dict) else data).encode()
        self.send_response(code)
        for k, v in CORS.items(): self.send_header(k, v)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items(): self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/status':
            self._send(200, {
                'ok': True, 'version': VERSION, 'port': PORT,
                'platform': PLATFORM,
                'tools': len([m for m in dir(dispatch.__module__) if not m.startswith('_')]),
            })
        elif path == '/platform':
            # Lets the frontend adapt key labels, modifier names, etc. to the actual OS
            self._send(200, {
                'platform': PLATFORM,  # 'Windows' | 'Darwin' | 'Linux'
                'modifier_key': {'Windows': 'win', 'Darwin': 'cmd', 'Linux': 'super'}.get(PLATFORM, 'super'),
                'modifier_label': {'Windows': 'Win', 'Darwin': 'Cmd', 'Linux': 'Super'}.get(PLATFORM, 'Super'),
                'alt_label': {'Darwin': 'Option'}.get(PLATFORM, 'Alt'),
            })
        elif path == '/tools':
            tools = [
                {'type': 'act_move',    'label': 'Mouse Move',    'group': 'Mouse'},
                {'type': 'act_click',   'label': 'Click',         'group': 'Mouse'},
                {'type': 'act_scroll',  'label': 'Scroll',        'group': 'Mouse'},
                {'type': 'act_type',    'label': 'Type Text',     'group': 'Keyboard'},
                {'type': 'act_keys',    'label': 'Press Keys',    'group': 'Keyboard'},
                {'type': 'act_open',    'label': 'Open App',      'group': 'App'},
                {'type': 'act_close',   'label': 'Close App',     'group': 'App'},
                {'type': 'act_browser', 'label': 'Open URL',      'group': 'App'},
                {'type': 'act_run',     'label': 'Run File',      'group': 'App'},
                {'type': 'sys_cmd',     'label': 'Run Command',   'group': 'System'},
                {'type': 'sys_notify',  'label': 'Notify',        'group': 'System'},
                {'type': 'sys_screenshot','label':'Screenshot',   'group': 'System'},
                {'type': 'sys_file',    'label': 'File Op',       'group': 'Files'},
                {'type': 'sys_file_find','label':'Find File',     'group': 'Files'},
                {'type': 'ai_think',    'label': 'AI Think',      'group': 'AI'},
                {'type': 'ai_generate', 'label': 'AI Generate',   'group': 'AI'},
                {'type': 'ai_action',   'label': 'AI Action',     'group': 'AI'},
                {'type': 'ai_screen',   'label': 'Read Screen',   'group': 'AI'},
            ]
            self._send(200, tools)
        else:
            self._send(404, {'ok': False, 'result': 'Not found'})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if path == '/action':
            action_type = body.get('type', '')
            cfg = body.get('config', {})
            result = dispatch(action_type, cfg)
            self._send(200, result)
        elif path == '/record-keys':
            timeout = float(body.get('timeout', 10))
            result = _record_next_hotkey(timeout)
            self._send(200, result)
        else:
            self._send(404, {'ok': False, 'result': 'Not found'})


def _record_next_hotkey(timeout: float = 10.0) -> dict:
    """
    Block (briefly) listening for the next key combination the user presses,
    using a global keyboard listener (pynput). Returns the combo as a list of
    normalized key names ready to feed back into KeyboardTools.hotkey(*keys).
    Used by the web UI's "click then press keys" hotkey recorder.
    """
    try:
        from pynput import keyboard
    except ImportError:
        return {'ok': False, 'result': 'pynput not installed — run: pip install pynput'}

    pressed = set()
    result_combo = []
    done = threading.Event()

    # Map pynput key objects to friendly, cross-platform names
    def _key_name(key) -> str:
        try:
            # Character keys (letters, numbers, symbols)
            if hasattr(key, 'char') and key.char is not None:
                return key.char.lower()
        except Exception:
            pass
        name = str(key).replace('Key.', '').lower()
        ALIASES = {
            'cmd': 'cmd', 'cmd_l': 'cmd', 'cmd_r': 'cmd',
            'ctrl': 'ctrl', 'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
            'alt': 'alt', 'alt_l': 'alt', 'alt_r': 'alt', 'alt_gr': 'alt',
            'shift': 'shift', 'shift_l': 'shift', 'shift_r': 'shift',
            'cmd_l_super': 'win',
        }
        # pynput on Windows reports the Windows key as 'cmd' too in some versions —
        # disambiguate using the actual platform
        if name in ('cmd', 'cmd_l', 'cmd_r') and PLATFORM == 'Windows':
            return 'win'
        return ALIASES.get(name, name)

    def on_press(key):
        name = _key_name(key)
        pressed.add(name)
        result_combo.clear()
        result_combo.extend(sorted(pressed, key=lambda k: k not in ('ctrl','cmd','win','alt','shift')))

    def on_release(key):
        # Stop as soon as all keys are released (combo complete)
        name = _key_name(key)
        pressed.discard(name)
        if not pressed and result_combo:
            done.set()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    finished = done.wait(timeout=timeout)
    listener.stop()

    if not finished or not result_combo:
        return {'ok': False, 'result': 'No key combination captured (timed out)'}
    return {'ok': True, 'result': '+'.join(result_combo), 'keys': result_combo}


def main():
    server = HTTPServer(('localhost', PORT), AutomationHandler)
    print(f'Fraude Automations running at http://localhost:{PORT}')
    server.serve_forever()


if __name__ == '__main__':
    main()
