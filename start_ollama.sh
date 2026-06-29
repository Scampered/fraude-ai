#!/usr/bin/env bash
# start_ollama.sh — macOS / Linux equivalent of start_ollama.bat
# Launches fraude_tray.py, which itself starts Ollama, the proxy,
# FraudeRepo, and Fraude Automations, then shows a tray icon.

set -e
cd "$(dirname "$0")"

# ── Check Python ────────────────────────────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Python not found. Install from python.org or your package manager:"
    echo "  macOS:  brew install python3"
    echo "  Linux:  sudo apt install python3 python3-pip   (Debian/Ubuntu)"
    echo "          sudo dnf install python3 python3-pip   (Fedora)"
    read -p "Press Enter to exit..."
    exit 1
fi

# ── fraude_tray.py is the single entry point ────────────────────────────────────
if [ -f "fraude_tray.py" ]; then
    # Run detached so closing the terminal doesn't kill the tray app
    nohup "$PYTHON" fraude_tray.py > /tmp/fraude_tray.log 2>&1 &
    disown
    echo "Fraude services starting."
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Look for the Fraude icon in your menu bar (top-right, near the clock)."
        echo "If you don't see it, check System Settings > Control Center for hidden menu bar items."
    else
        echo "Look for the Fraude icon in your system tray."
        echo "On GNOME you may need the 'AppIndicator' extension for tray icons to show:"
        echo "  https://extensions.gnome.org/extension/615/appindicator-support/"
    fi
    sleep 2
    exit 0
fi

# ── Fallback: start services individually if fraude_tray.py is missing ─────────
echo "fraude_tray.py not found — starting services individually."

if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama not found. Install from https://ollama.com/download"
else
    if ! curl -s http://localhost:11434 >/dev/null 2>&1; then
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        disown
        sleep 2
    fi
fi

[ -f "ollama_proxy.py" ]        && { nohup "$PYTHON" ollama_proxy.py        > /tmp/fraude_proxy.log 2>&1 & disown; }
[ -f "frauderepo.py" ]          && { nohup "$PYTHON" frauderepo.py          > /tmp/frauderepo.log 2>&1 & disown; }
[ -f "fraude_automations.py" ]  && { nohup "$PYTHON" fraude_automations.py  > /tmp/fraude_automations.log 2>&1 & disown; }

echo "Services started (no tray icon — fraude_tray.py was missing)."
sleep 1
