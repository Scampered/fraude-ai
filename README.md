# Fraude

An AI chat interface. Runs locally. Supports Ollama, Groq, and Gemini.

Repository: https://github.com/Scampered/fraude-ai

See [setup.md](setup.md) for detailed setup steps, including Ollama installation and model downloads.

## Quick start

```bash
cd fraude
npm install
npm run dev
```

Open **http://localhost:5173**

If you prefer a platform-specific launcher:

- Windows: `start.bat`
- macOS / Linux: `start.sh`

If you want to use Ollama locally, follow the Ollama steps in [setup.md](setup.md). If Ollama is already running, Fraude will connect automatically; otherwise run `ollama serve`.

---

## Models

| Name | Provider | Unlock |
|------|----------|--------|
| HighKu | Ollama (local) | Free, always available |
| Somenet | Groq API | Pro — enter Groq key in Billing |
| Oops 6.7 | Gemini API | Max — enter Gemini key in Billing |
| Myth | AWARE-Lite | Max |

**Free API keys:**
- Groq: [console.groq.com](https://console.groq.com) → API Keys
- Gemini: [aistudio.google.com](https://aistudio.google.com) → Get API Key

**Ollama setup:**
```bash
# Install from ollama.com, then:
ollama pull qwen2.5:3b
```

---

## Features

- Conversation history saved to disk
- File upload (drag & drop or attach button)
- Skills: Code, Excel, PDF, Essay, Data, Web Scraper, SQL, API
- Generated files saved to `fraude-memory/` folder
- Settings and API keys stored in browser localStorage
- Billing page with plan upgrade flow

---

## Memory folder

`fraude-memory/{conversation-id}/` — each conversation has its own folder with messages, uploaded files, generated code, and memory notes.

---

## FraudeCode (CLI companion)

FraudeCode is an optional command-line AI coding environment that shares API keys and memory with Fraude web.

**To use FraudeCode:**

1. Install Python 3.9+ (if not already installed)
2. Run: `python fraudecode.py`
3. Set your Groq or Gemini API key when prompted (same keys as in Fraude web → Billing)
4. Type natural language prompts; FraudeCode generates and runs Python code
5. Use `/ship` to zip your code workspace for download

API keys set in Fraude web automatically sync to FraudeCode. You only need to enter them once.

**Learn more:** Type `/help` in FraudeCode for all available commands.

---
