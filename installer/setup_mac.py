"""
setup_mac.py — py2app build script for the Fraude.app macOS bundle.

Build with:
    pip install py2app
    python3 setup_mac.py py2app

Produces dist/Fraude.app — a real double-clickable macOS application
(not a Python script with a shebang). Package it into a .dmg afterwards
with make_dmg.sh.
"""
from setuptools import setup
from pathlib import Path

HERE = Path(__file__).parent.parent  # fraude-ai/ root

APP = [str(HERE / 'fraude_tray.py')]

DATA_FILES = [
    str(HERE / 'fraude_automations.py'),
    str(HERE / 'frauderepo.py'),
    str(HERE / 'ollama_proxy.py'),
    str(HERE / 'fraudecode.py'),
    (str(HERE / 'fraudecode_pkg'), 'fraudecode_pkg'),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': str(Path(__file__).parent / 'icon.icns'),
    'plist': {
        'CFBundleName': 'Fraude',
        'CFBundleDisplayName': 'Fraude',
        'CFBundleIdentifier': 'com.fraude.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,  # menu-bar-only app, no Dock icon clutter
        'NSHumanReadableCopyright': 'Fraude AI',
        # Required permission descriptions — macOS shows these in the
        # Accessibility / Screen Recording consent prompts
        'NSAppleEventsUsageDescription':
            'Fraude needs Accessibility access to control mouse, keyboard, and apps for automations.',
        'NSCameraUsageDescription': 'Not used — reserved for future vision features.',
    },
    'packages': ['pystray', 'PIL', 'pyautogui', 'pyperclip', 'psutil', 'pynput'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
