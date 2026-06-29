#!/usr/bin/env bash
# make_dmg.sh — packages dist/Fraude.app into a distributable Fraude.dmg
# with a proper drag-to-Applications installer window.
#
# Requires: create-dmg (brew install create-dmg)
# Run from the installer/ directory after `python3 setup_mac.py py2app`

set -e
APP_PATH="../dist/Fraude.app"
DMG_NAME="Fraude.dmg"
VOL_NAME="Install Fraude"

if [ ! -d "$APP_PATH" ]; then
    echo "✗ $APP_PATH not found. Run: python3 setup_mac.py py2app   first."
    exit 1
fi

if ! command -v create-dmg >/dev/null 2>&1; then
    echo "Installing create-dmg via Homebrew..."
    brew install create-dmg
fi

rm -f "$DMG_NAME"

create-dmg \
  --volname "$VOL_NAME" \
  --window-pos 200 120 \
  --window-size 540 380 \
  --icon-size 100 \
  --icon "Fraude.app" 140 170 \
  --hide-extension "Fraude.app" \
  --app-drop-link 400 170 \
  --background "dmg_background.png" \
  "$DMG_NAME" \
  "$APP_PATH" || true   # create-dmg returns non-zero on some benign warnings

echo "✓ Built $DMG_NAME"
