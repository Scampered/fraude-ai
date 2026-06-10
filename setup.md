# Fraude Local Setup Guide

This guide shows how to set up and run the Fraude project locally. It also explains which files to include in a shareable GitHub upload and which files to keep private.

## What to include in the zip

Include these repository files and folders:

- `index.html`
- `package.json`
- `package-lock.json`
- `README.md`
- `setup.md`
- `start.bat`
- `start.sh`
- `vite.config.js`
- `.gitignore`
- `public/`
- `server/`
- `src/`

Do not include these items:

- `node_modules/`
- `fraude-memory/`
- `.env`
- any local or private files containing secrets
- browser localStorage data or API keys

> `fraude-memory/` contains your own chat history, conversation files, uploaded documents, generated artifacts, and memory notes. Do not share it.

## Prerequisites

1. Node.js 18+ or 20+ installed
2. npm (comes with Node)
3. Recommended: Git for cloning the repository
4. Optional: Ollama if you want to run the local HighKu model

## Install dependencies

Open a terminal in the project folder and run:

```bash
npm install
```

If you want to install dependencies from scratch after removing `node_modules`, use:

```bash
rm -rf node_modules package-lock.json
npm install
```

## Ollama setup (HighKu local model)

Fraude supports a local Ollama model for the `HighKu` plan. If you want to use it:

1. Install Ollama from https://ollama.com
2. Open a terminal and run:

```bash
ollama pull qwen2.5:3b
```

3. Start Ollama if it is not started automatically:

```bash
ollama serve
```

If Ollama is installed and available on your path, Fraude can use it locally.

## Run the app locally

Start the app with one of these commands:

```bash
npm run dev
```

Or use the provided platform-specific starter scripts:

- Windows: `start.bat`
- macOS / Linux: `start.sh`

Then open the app in your browser at:

```text
http://localhost:5173
```

## API keys and billing

Fraude stores API keys in the browser localStorage, not in the repository. Do not commit or share your API keys.

- Groq API key: enter it under the `Billing` section when upgrading to the `Pro` plan.
- Gemini API key: enter it under the `Billing` section when upgrading to the `Max` plan.

Helpful links:
- Groq: [console.groq.com](https://console.groq.com) → API Keys
- Gemini: [aistudio.google.com](https://aistudio.google.com) → Get API Key

---

## FraudeCode setup (optional CLI)

FraudeCode is an AI coding environment that runs alongside Fraude web. It shares your API keys, memory folder, and settings.

### Prerequisites for FraudeCode

- Python 3.9 or higher
- pip (Windows) or python3 / pip3 (macOS and Linux)
- Same Groq or Gemini API keys used in Fraude web

### Check Python installation

On Windows, use:

```bash
python --version
```

On macOS / Linux, if `python` is not available, use:

```bash
python3 --version
```

If Python is not installed, download from [python.org](https://www.python.org/).

### Launch FraudeCode

Open a terminal in the project folder and run:

```bash
# Windows
python fraudecode.py
```

```bash
# macOS / Linux
python3 fraudecode.py
```

If your system uses `python` for Python 3 on macOS/Linux, use the first command instead.

The web install button should also work, but on macOS/Linux it runs `python3 -m pip install ...` under the hood. If that fails, use the manual command below.

On first launch, FraudeCode will prompt you for:
1. **Groq API key** (optional, for Pro plan)
2. **Gemini API key** (optional, for Main plan)

These keys are saved locally in `fraude-memory/_settings.json` and shared with Fraude web.

### FraudeCode basic usage

- Type a prompt: `"Make a script that downloads weather data"`
- FraudeCode generates Python code, asks for permission, and runs it
- Type `/help` to see all commands
- Type `/ship` to download all your code as a zip file
- Type `/home` to return to the chat dashboard

### Key commands

| Command | What it does |
|---------|------|
| `/help` | Show all available commands |
| `/files` | List files in current session |
| `/export <file>` | Copy a file to your Downloads folder |
| `/ship` | Zip everything and open download |
| `/run <file>` | Execute a Python file |
| `/clone <url>` | Clone a GitHub repo into the session |
| `/install <pkg>` | pip install a Python package |
| `/save [name]` | Save current chat session |
| `/chats` | Open dashboard to switch sessions |

### How API keys sync

1. You enter API keys in Fraude web → Settings → Models
2. Fraude web saves them to browser localStorage
3. On page load, Fraude web syncs them to `fraude-memory/_settings.json` on the server
4. When you run `python fraudecode.py`, it reads the same `_settings.json` file
5. Both tools use the same keys—no need to enter them twice

### Troubleshooting

**"python: command not found"**
- Python is not in your PATH. Reinstall from [python.org](https://www.python.org/) and check "Add Python to PATH" during installation.

**"ModuleNotFoundError" when running FraudeCode**
- FraudeCode creates its own isolated Python environment for each chat session (in `fraude-code-memory/`). This is normal and does not affect your system Python.

**API key not recognized**
- Make sure you entered it correctly in Fraude web first, then close and reopen FraudeCode.
- Check that the key matches the provider (Groq key for Groq, Gemini key for Gemini).

---

- Groq: https://console.groq.com/keys
- Gemini: https://aistudio.google.com/api-keys

## What to configure after first launch

1. Open the app in your browser.
2. Go to `Billing` and choose the plan you want.
3. Enter your API key in the prompt.
4. If you want local Ollama support, make sure Ollama is running.

## Notes for friends and collaborators

- They should clone or extract the zip.
- Run `npm install` once.
- Run `npm run dev`.
- Set their own API keys in the app.
- Do not include `fraude-memory/` or any `.env` files when sharing.

## Recommended GitHub upload

For GitHub, upload the project root contents except:

- `node_modules/`
- `fraude-memory/`
- `.env`

Keep these files in the repo or zip:

- `package.json`
- `package-lock.json`
- `README.md`
- `setup.md`
- source files under `src/`
- `server/`
- `public/`
- `start.bat` / `start.sh`

That gives a clean, reproducible project for anyone who wants to run Fraude locally.
