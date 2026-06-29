#!/usr/bin/env bash
# fraude-install.sh — Linux installer for Fraude App
# Installs into ~/.local/share/fraude, sets up a Python venv, and adds a
# desktop launcher entry so Fraude shows up in the applications menu.

set -e
INSTALL_DIR="$HOME/.local/share/fraude"
DESKTOP_FILE="$HOME/.local/share/applications/fraude.desktop"
REPO_URL="https://github.com/Scampered/fraude-ai.git"

echo "════════════════════════════════════════"
echo "  Fraude App — Linux Installer"
echo "════════════════════════════════════════"
echo ""

# ── Check Python ────────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
    echo "✗ python3 not found. Install it first:"
    echo "    Debian/Ubuntu:  sudo apt install python3 python3-venv python3-pip"
    echo "    Fedora:         sudo dnf install python3 python3-pip"
    echo "    Arch:           sudo pacman -S python python-pip"
    exit 1
fi
echo "✓ Python found: $(python3 --version)"

# ── Clone or update ─────────────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    echo "Existing install found — updating..."
    cd "$INSTALL_DIR" && git pull --quiet
else
    echo "Cloning Fraude..."
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR/fraude-ai"

# ── Virtual environment ─────────────────────────────────────────────────────────
echo "Setting up virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet pystray Pillow pyautogui pyperclip psutil pynput requests

# ── Desktop entry ────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Fraude
Comment=Local AI automation and code assistant
Exec=$INSTALL_DIR/fraude-ai/.venv/bin/python $INSTALL_DIR/fraude-ai/fraude_tray.py
Icon=$INSTALL_DIR/fraude-ai/installer/icon.png
Terminal=false
Categories=Development;Utility;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "════════════════════════════════════════"
echo "✓ Fraude installed to $INSTALL_DIR"
echo "✓ Find 'Fraude' in your applications menu"
echo ""
echo "GNOME users: install the AppIndicator extension for the"
echo "tray icon to appear in the top bar:"
echo "  https://extensions.gnome.org/extension/615/appindicator-support/"
echo "════════════════════════════════════════"
echo ""
read -p "Launch Fraude now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    nohup "$INSTALL_DIR/fraude-ai/.venv/bin/python" "$INSTALL_DIR/fraude-ai/fraude_tray.py" >/tmp/fraude.log 2>&1 &
    disown
    echo "Fraude is starting — look for the icon in your system tray."
fi
