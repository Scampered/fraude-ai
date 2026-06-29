# Building Fraude App Installers

## Windows

```bash
pip install pyinstaller
cd installer
pyinstaller fraude_tray.spec
# Produces ../dist/Fraude/  (folder with Fraude.exe + all dependencies)
```

Then compile the installer with [Inno Setup 6+](https://jrsoftware.org/isinfo.php):

```bash
ISCC.exe fraude_setup.iss
# Produces installer/output/Fraude-Setup.exe
```

**Assets needed before building:**
- `installer/icon.ico` — app icon (multi-resolution .ico, 16/32/48/256px)
- `installer/wizard_large.bmp` — 164×314px wizard sidebar image
- `installer/wizard_small.bmp` — 55×58px wizard header image

Both BMP files should use the Fraude brand colours (terracotta `#C15F3C` on cream `#FAF9F5` or dark `#141413`).

## macOS

```bash
pip install py2app
cd installer
python3 setup_mac.py py2app
# Produces ../dist/Fraude.app
```

Then package into a DMG:

```bash
brew install create-dmg
./make_dmg.sh
# Produces installer/Fraude.dmg
```

**Assets needed:**
- `installer/icon.icns` — app icon (use `iconutil` to convert from a 1024×1024 PNG)
- `installer/dmg_background.png` — 540×380px DMG window background

**Code signing note:** without an Apple Developer account ($99/yr), the app
will be unsigned and macOS Gatekeeper will block it on first launch. Users
can bypass this with right-click → Open. For wider distribution, signing +
notarization is recommended eventually.

## Linux

No compiled binary — `fraude-install.sh` is a self-contained shell script
that clones the repo, creates a venv, and installs dependencies directly
on the user's machine. This avoids the complexity of building `.deb`/`.rpm`/
AppImage packages for a first release, and works across distros since it
just uses `python3 -m venv` + `pip`.

To distribute: upload `fraude-install.sh` as a release asset. Users run:
```bash
curl -fsSL https://github.com/Scampered/fraude-ai/releases/latest/download/fraude-install.sh | bash
```

## Release checklist

1. Build all three installers
2. Create a GitHub Release with tag `v1.0.0`
3. Upload `Fraude-Setup.exe`, `Fraude.dmg`, `fraude-install.sh` as release assets
4. The Downloads page (`/downloads`) links to `releases/latest/download/<file>` —
   these URLs automatically resolve to whatever you tag as the latest release,
   so future updates just need a new tag + uploaded assets, no code changes.
