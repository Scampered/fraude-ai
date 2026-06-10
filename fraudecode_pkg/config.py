"""Config loading — reads from multiple sources with clear priority."""
import os, json, sys
from pathlib import Path
from .colours import c, bold, dim, ACC, GRN, YLW, GRY, RED, R

BASE_DIR    = Path(__file__).parent.parent.resolve()
MEMORY_ROOT = BASE_DIR / 'fraude-memory'
CODE_DIR    = BASE_DIR / 'fraude-code-memory'
CONFIG_FILE = BASE_DIR / 'fraudecode_config.json'
CODE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULTS = {
    'ollamaUrl':    'http://localhost:11434',
    'ollamaModel':  'llama3.2',
    'groqModel':    'llama-3.3-70b-versatile',
    'geminiModel':  'gemini-2.0-flash-lite',
    'fraudeWebUrl': 'http://localhost:3001',
}

def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text('utf-8'))
    except Exception:
        pass
    return {}

def _fetch_from_web_server(url: str) -> dict:
    """Try to pull settings directly from the running Fraude web server."""
    try:
        import urllib.request
        req = urllib.request.Request(f'{url}/api/settings',
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return {}

def load() -> dict:
    """
    Priority (highest wins):
      1. Env vars  (GROQ_API_KEY, GEMINI_API_KEY)
      2. Fraude web server live fetch (if running)
      3. fraude-memory/_settings.json  (written by web app on every save)
      4. fraudecode_config.json        (local override)
      5. Built-in defaults
    """
    result = {**DEFAULTS}

    # 4. Local config
    result.update({k: v for k, v in _read_json(CONFIG_FILE).items() if v})

    # 3. _settings.json (synced from web app)
    result.update({k: v for k, v in _read_json(MEMORY_ROOT / '_settings.json').items() if v})

    # 2. Live web server (catches case where _settings.json hasn't been written yet)
    web_url = result.get('fraudeWebUrl', DEFAULTS['fraudeWebUrl'])
    live = _fetch_from_web_server(web_url)
    result.update({k: v for k, v in live.items() if v})

    # 1. Env vars (highest priority)
    if os.getenv('GROQ_API_KEY'):   result['groqKey']   = os.getenv('GROQ_API_KEY')
    if os.getenv('GEMINI_API_KEY'): result['geminiKey'] = os.getenv('GEMINI_API_KEY')
    if os.getenv('OLLAMA_URL'):     result['ollamaUrl'] = os.getenv('OLLAMA_URL')

    return result

def save(cfg: dict):
    """Save to local config file."""
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding='utf-8')

def save_and_push(cfg: dict):
    """Save locally AND push to web server if running."""
    save(cfg)
    # Also write directly to _settings.json so web app picks it up
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    (MEMORY_ROOT / '_settings.json').write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    # Try live push to web server
    web_url = cfg.get('fraudeWebUrl', DEFAULTS['fraudeWebUrl'])
    try:
        import urllib.request
        body = json.dumps(cfg).encode()
        req = urllib.request.Request(f'{web_url}/api/settings', data=body,
            headers={'Content-Type': 'application/json'}, method='POST')
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass

def run_setup(existing: dict = None) -> dict:
    """Interactive /setup wizard."""
    from .ui import clear_screen, BANNER, MINI
    clear_screen()
    print(MINI)
    print(f"\n  {bold('FraudeCode Setup')}\n")
    print(f"  {dim('Keys from the Fraude web app sync automatically.')}")
    print(f"  {dim('Use this wizard if running FraudeCode standalone.\n')}")

    cfg = dict(existing or {})

    def prompt_key(label, env_var, cfg_key, hint, prefix=''):
        current = cfg.get(cfg_key) or os.getenv(env_var, '')
        masked = ('*' * 8 + current[-4:]) if current else dim('not set')
        val = input(f"  {c(label, ACC)} {GRY}[{masked}]{R} {dim(hint)}\n  > ").strip()
        if val:
            cfg[cfg_key] = val
        elif current:
            cfg[cfg_key] = current  # keep existing
        return cfg.get(cfg_key, '')

    print(f"  {bold('── API Keys ──────────────────────────────────────────')}\n")
    groq   = prompt_key('Groq API Key',   'GROQ_API_KEY',   'groqKey',   '(gsk_...) — free at console.groq.com/keys')
    gemini = prompt_key('Gemini API Key', 'GEMINI_API_KEY', 'geminiKey', '(AIza...) — free at aistudio.google.com/api-keys')

    print(f"\n  {bold('── Models ────────────────────────────────────────────')}\n")
    ollama_url = input(f"  {c('Ollama URL',ACC)} {GRY}[{cfg.get('ollamaUrl', DEFAULTS['ollamaUrl'])}]{R}\n  > ").strip()
    cfg['ollamaUrl'] = ollama_url or cfg.get('ollamaUrl', DEFAULTS['ollamaUrl'])

    ollama_mdl = input(f"  {c('Ollama Model',ACC)} {GRY}[{cfg.get('ollamaModel', DEFAULTS['ollamaModel'])}]{R}\n  > ").strip()
    cfg['ollamaModel'] = ollama_mdl or cfg.get('ollamaModel', DEFAULTS['ollamaModel'])

    groq_mdl = input(f"  {c('Groq Model',ACC)} {GRY}[{cfg.get('groqModel', DEFAULTS['groqModel'])}]{R}\n  > ").strip()
    cfg['groqModel'] = groq_mdl or cfg.get('groqModel', DEFAULTS['groqModel'])

    gemini_mdl = input(f"  {c('Gemini Model',ACC)} {GRY}[{cfg.get('geminiModel', DEFAULTS['geminiModel'])}]{R}\n  > ").strip()
    cfg['geminiModel'] = gemini_mdl or cfg.get('geminiModel', DEFAULTS['geminiModel'])

    print(f"\n  {bold('── Fraude Web ────────────────────────────────────────')}\n")
    web_url = input(f"  {c('Fraude Web Server URL',ACC)} {GRY}[{cfg.get('fraudeWebUrl', DEFAULTS['fraudeWebUrl'])}]{R}\n  > ").strip()
    cfg['fraudeWebUrl'] = web_url or cfg.get('fraudeWebUrl', DEFAULTS['fraudeWebUrl'])

    # Determine plan
    has_groq   = bool(cfg.get('groqKey'))
    has_gemini = bool(cfg.get('geminiKey'))
    if has_gemini and has_groq:
        plan_name = 'Max — Oops 0.7 (Gemini + Groq + Ollama)'
    elif has_gemini:
        plan_name = 'Oops 0.6 (Gemini + Ollama)'
    elif has_groq:
        plan_name = 'Somenet 0.6 (Groq + Ollama)'
    else:
        plan_name = 'Free — HighKu 0.5 (Ollama only)'

    save_and_push(cfg)
    print(f"\n  {c('✓ Saved!', GRN)}")
    print(f"  Plan: {c(plan_name, ACC)}")
    print(f"  Config: {dim(str(CONFIG_FILE))}\n")
    return cfg

def first_run() -> dict:
    """Called on very first launch when no config exists at all."""
    return run_setup({})
