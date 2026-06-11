"""Multi-agent pipeline with orchestrator integration and agent fallbacks."""
import json, urllib.request, urllib.error, urllib.parse
from .colours import *
from .ui import Spinner

_cfg: dict = {}
_plan_override: str = ''

def set_config(cfg: dict):
    global _cfg; _cfg = cfg

def set_plan_override(p: str):
    global _plan_override; _plan_override = p

def _groq_key():   return _cfg.get('groqKey', '')
def _gemini_key(): return _cfg.get('geminiKey', '')
def _ollama_url(): return _cfg.get('ollamaUrl', 'http://localhost:11434')
def _ollama_mdl(): return _cfg.get('ollamaModel', 'llama3.2')
def _groq_mdl():   return _cfg.get('groqModel', 'llama-3.3-70b-versatile')
def _gemini_mdl(): return _cfg.get('geminiModel', 'gemini-2.0-flash-lite')

def get_plan() -> str:
    if _plan_override:
        return _plan_override
    has_groq   = bool(_groq_key())
    has_gemini = bool(_gemini_key())
    if has_gemini and has_groq: return 'max'
    if has_gemini:              return 'oops06'
    if has_groq:                return 'pro'
    return 'free'

PLAN_LABELS = {
    'max':    'Oops 0.7      (Gemini + Groq + Ollama)',
    'oops06': 'Oops 0.6      (Gemini + Ollama)',
    'pro':    'Somenet 0.6   (Groq + Ollama)',
    'pro05':  'Somenet 0.5   (Groq only)',
    'free':   'HighKu 0.5    (Ollama only)',
}

# ── Identity system prompt ────────────────────────────────────────────────────
# Strong identity to prevent models from leaking their real identity
IDENTITY_SYS = """You are FraudeCode, a multi-agent AI coding assistant.
Your name is FraudeCode. You are NOT Claude, Gemini, ChatGPT, Llama, Qwen, or any other named AI.
If asked who you are, say "I am FraudeCode" and describe your capabilities.
You run as part of the Fraude platform."""

# ── API callers ────────────────────────────────────────────────────────────────
def call_ollama(messages: list, timeout: int = 60) -> str:
    # Extract system message — Ollama takes it as top-level field
    sys_content = ''
    chat_msgs = []
    for m in messages:
        if m.get('role') == 'system':
            sys_content += m.get('content', '') + '\n'
        else:
            chat_msgs.append(m)

    payload = {
        'model':   _ollama_mdl(),
        'messages': chat_msgs,
        'stream':  False,
    }
    if sys_content.strip():
        payload['system'] = sys_content.strip()

    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f'{_ollama_url()}/api/chat',
        data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())['message']['content']
    except urllib.error.URLError as e:
        raise RuntimeError(f'Ollama unreachable: {e.reason}')
    except Exception as e:
        raise RuntimeError(f'Ollama: {e}')

def call_gemini(prompt: str, system: str = '', timeout: int = 60) -> str:
    """Direct HTTP call — handles AQ.A (OAuth) and AIzaSy (API key)."""
    if not _gemini_key():
        raise RuntimeError('No Gemini key')
    key = _gemini_key().strip()
    mdl = _gemini_mdl()
    # Only AIzaSy is a permanent API key; AQ.A/ya29 are OAuth tokens
    is_api_key = key.startswith('AIzaSy')
    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent'
        + (f'?key={urllib.parse.quote(key, safe="")}' if is_api_key else '')
    )
    headers = {'Content-Type': 'application/json'}
    if not is_api_key:
        headers['Authorization'] = 'Bearer ' + key

    # Combine identity + custom system
    full_sys = IDENTITY_SYS + ('\n\n' + system if system else '')

    body_dict = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {'maxOutputTokens': 8192, 'temperature': 0.3},
        'systemInstruction': {'parts': [{'text': full_sys}]},
    }
    req = urllib.request.Request(url, data=json.dumps(body_dict).encode(), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
        return d['candidates'][0]['content']['parts'][0]['text']
    except urllib.error.HTTPError as e:
        body_t = e.read().decode('utf-8', errors='replace')
        d = json.loads(body_t) if body_t.startswith('{') else {}
        msg = d.get('error', {}).get('message', body_t[:200])
        if e.code == 429:
            raise RuntimeError(f'RATE_LIMIT: Gemini — {msg}')
        if e.code == 401:
            raise RuntimeError(f'Gemini auth failed — if your key starts with AQ.A it is an OAuth token that has expired. Get a permanent AIzaSy key at aistudio.google.com/apikey')
        raise RuntimeError(f'Gemini HTTP {e.code}: {msg}')

def call_groq(messages: list, system: str = '', timeout: int = 30) -> str:
    if not _groq_key():
        raise RuntimeError('No Groq key')
    # Prepend identity to system
    full_sys = IDENTITY_SYS + ('\n\n' + system if system else '')
    msgs = ([{'role': 'system', 'content': full_sys}] if full_sys else []) + messages
    body = json.dumps({'model': _groq_mdl(), 'messages': msgs, 'max_tokens': 4096}).encode()
    req  = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=body,
        headers={'Authorization': f'Bearer {_groq_key()}', 'Content-Type': 'application/json'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        body_t = e.read().decode('utf-8', errors='replace')
        if e.code == 429:
            raise RuntimeError('RATE_LIMIT: Groq — retry after a moment')
        if e.code == 403:
            raise RuntimeError(f'Groq auth error (403) — check API key')
        raise RuntimeError(f'Groq HTTP {e.code}: {body_t[:200]}')
    except Exception as e:
        raise RuntimeError(f'Groq: {e}')

# ── System prompts ────────────────────────────────────────────────────────────
ROUTER_SYS = (
    "Classify this coding request into EXACTLY ONE of these labels:\n"
    "CODE_GENERATION - writing new code, scripts, programs, websites, apps, tools, dashboards, APIs\n"
    "DEBUG - fixing errors, debugging, troubleshooting\n"
    "REFACTOR - improving existing code\n"
    "ARCHITECTURE - system design, planning\n"
    "DOCUMENTATION - writing docs, README\n"
    "GENERAL_EXPLANATION - pure explanations with no code needed\n"
    "Output the label ONLY. Nothing else. When in doubt, choose CODE_GENERATION."
)

CODER_SYS = (
    IDENTITY_SYS + "\n\n"
    "You are the Coder agent. Output ONLY code in ```lang block. "
    "First line: # FILE: filename.ext. Complete, production-ready, full error handling. "
    "No explanations outside code blocks."
)
GROQ_CODER_SYS = (
    IDENTITY_SYS + "\n\n"
    "You are the Coder agent specialising in fast, clean implementation. "
    "Output ONLY code in ```lang block. First line: # FILE: filename.ext. "
    "Complete implementation, no placeholders, no TODOs."
)
EXPLAINER_SYS = (
    IDENTITY_SYS + "\n\n"
    "Given code and a task, write: 1)Summary 2)Key functions 3)Usage example "
    "4)pip install needs 5)Issues/warnings. Markdown. Be concise."
)
DOC_SYS = (
    IDENTITY_SYS + "\n\n"
    "Technical writer. Create README.md or HANDOFF.md from code. Clear markdown."
)
GENERAL_SYS = (
    IDENTITY_SYS + "\n\n"
    "You are a helpful coding assistant. Answer questions clearly and directly. "
    "Include code examples when helpful."
)

# ── Routing ───────────────────────────────────────────────────────────────────
def route(prompt: str) -> str:
    try:
        r = call_ollama([
            {'role': 'system', 'content': ROUTER_SYS},
            {'role': 'user',   'content': f'Classify: {prompt[:400]}'}
        ], timeout=15).strip().upper()
        for v in ['CODE_GENERATION', 'DEBUG', 'REFACTOR', 'ARCHITECTURE', 'DOCUMENTATION', 'GENERAL_EXPLANATION']:
            if v in r: return v
    except Exception:
        pass
    # Heuristic fallback — most requests are code tasks
    lower = prompt.lower()
    code_hints = ['make', 'build', 'create', 'write', 'generate', 'html', 'python', 'script',
                  'app', 'website', 'dashboard', 'api', 'function', 'class', 'program',
                  'tool', 'tracker', 'calculator', 'game', 'bot', 'fix', 'debug', 'error']
    if any(h in lower for h in code_hints):
        return 'CODE_GENERATION'
    return 'GENERAL_EXPLANATION'

class PipelineResult:
    def __init__(self):
        self.task_type    = ''
        self.code         = ''
        self.explanation  = ''
        self.errors       = []
        self.fallbacks    = []
        self.cancelled    = False
        self.orchestrated = False

_cancel_flag = False
_lockin_mode = False

def cancel():       global _cancel_flag; _cancel_flag = True
def reset_cancel(): global _cancel_flag; _cancel_flag = False
def set_lockin(v):  global _lockin_mode; _lockin_mode = v
def get_lockin():   return _lockin_mode

def run(prompt: str, workdir: str = None) -> PipelineResult:
    reset_cancel()
    result = PipelineResult()
    plan   = get_plan()

    # Tasks that produce code
    CODE_TASKS = {'CODE_GENERATION', 'DEBUG', 'REFACTOR', 'ARCHITECTURE'}

    # ── Step 1: Route ─────────────────────────────────────────────────────────
    print(f"  {GRY}[router]   {R}", end='', flush=True)
    try:
        with Spinner('Routing...'):
            result.task_type = route(prompt)
        print(c(f'→ {result.task_type}', ACC))
    except Exception as e:
        result.task_type = 'CODE_GENERATION'  # Default to coding, not explanation
        result.errors.append(('router', str(e)))
        print(c(f'→ offline, defaulting to CODE_GENERATION', YLW))

    if _cancel_flag:
        result.cancelled = True; return result

    # ── Orchestrator check ────────────────────────────────────────────────────
    if result.task_type in CODE_TASKS and plan in ('max', 'oops06') and workdir is not None:
        try:
            from . import orchestrator
            should = orchestrator.should_orchestrate(prompt, plan)
        except Exception:
            should = False
        if should:
            print(f"  {c('[orchestrator]', ACC)} Multi-agent pipeline starting...\n")
            try:
                orch_result = orchestrator.run(prompt, workdir)
                result.orchestrated = True
                result.code = f'[Orchestrator] {len(orch_result.files_written)} files written'
                if orch_result.review.get('summary'):
                    result.explanation = orch_result.review['summary']
                return result
            except Exception as e:
                print(c(f'  Orchestrator failed: {e}. Falling back to single agent.', YLW))

    # ── Single-agent path ─────────────────────────────────────────────────────
    if result.task_type in CODE_TASKS:
        print(f"  {GRY}[coder]    {R}", end='', flush=True)

        if _lockin_mode and _groq_key() and _gemini_key():
            # LOCKIN: both generate, Ollama merges
            print(c('LOCKIN — dual coder', ACC))
            gem_code = groq_code = ''
            try:
                with Spinner('Gemini drafting...'):
                    gem_code = call_gemini(prompt, system=CODER_SYS)
                print(c('  ✓ Gemini', GRN))
            except RuntimeError as e:
                print(c(f'  ⚠ Gemini: {str(e)[:60]}', YLW))
            try:
                with Spinner('Groq drafting...'):
                    groq_code = call_groq([{'role': 'user', 'content': prompt}], system=GROQ_CODER_SYS)
                print(c('  ✓ Groq', GRN))
            except RuntimeError as e:
                print(c(f'  ⚠ Groq: {str(e)[:60]}', YLW))
            if gem_code and groq_code:
                print(f"  {GRY}[merger]   {R}", end='', flush=True)
                merge_prompt = (
                    f"Two agents wrote code for: {prompt}\n\n"
                    f"Version A (Gemini):\n{gem_code}\n\n"
                    f"Version B (Groq):\n{groq_code}\n\n"
                    f"Merge into one optimal implementation. Fix conflicts. Output merged code only."
                )
                try:
                    with Spinner('Merging...'):
                        result.code = call_ollama([{'role': 'user', 'content': merge_prompt}], timeout=90)
                    print(c('✓', GRN))
                except RuntimeError:
                    result.code = gem_code
                    print(c('Ollama offline — using Gemini version', YLW))
            else:
                result.code = gem_code or groq_code

        elif plan in ('max', 'oops06') and _gemini_key():
            # Gemini primary, Groq fallback, Ollama last resort
            try:
                with Spinner('Gemini coding...'):
                    result.code = call_gemini(prompt, system=CODER_SYS)
                print(c('✓ Gemini', GRN))
            except RuntimeError as e:
                msg = str(e)
                print(c(f'⚠ Gemini: {msg[:80]}', YLW))
                result.errors.append(('coder:gemini', msg))
                # Try Groq fallback
                if _groq_key():
                    print(f"  {GRY}→ falling back to Groq{R}")
                    try:
                        with Spinner('Groq fallback...'):
                            result.code = call_groq([{'role': 'user', 'content': prompt}], system=GROQ_CODER_SYS)
                        result.fallbacks.append(('gemini', 'groq'))
                        print(c('✓ Groq fallback', GRN))
                    except RuntimeError as e2:
                        result.errors.append(('coder:groq', str(e2)))
                        print(c(f'  ✗ {str(e2)[:80]}', RED))
                        # Last resort: Ollama
                        print(f"  {GRY}→ falling back to Ollama{R}")
                        try:
                            with Spinner('Ollama fallback...'):
                                result.code = call_ollama([
                                    {'role': 'system', 'content': CODER_SYS},
                                    {'role': 'user',   'content': prompt}
                                ], timeout=120)
                            result.fallbacks.append(('groq', 'ollama'))
                            print(c('✓ Ollama fallback', GRN))
                        except RuntimeError as e3:
                            result.errors.append(('coder:ollama', str(e3)))
                            print(c(f'  ✗ All agents failed', RED))
                else:
                    # Try Ollama directly
                    print(f"  {GRY}→ falling back to Ollama{R}")
                    try:
                        with Spinner('Ollama fallback...'):
                            result.code = call_ollama([
                                {'role': 'system', 'content': CODER_SYS},
                                {'role': 'user',   'content': prompt}
                            ], timeout=120)
                        result.fallbacks.append(('gemini', 'ollama'))
                        print(c('✓ Ollama fallback', GRN))
                    except RuntimeError as e3:
                        result.errors.append(('coder:ollama', str(e3)))

        elif plan in ('pro', 'pro05') and _groq_key():
            # Groq primary, Ollama fallback
            try:
                with Spinner('Groq coding...'):
                    result.code = call_groq([{'role': 'user', 'content': prompt}], system=GROQ_CODER_SYS)
                print(c('✓ Groq', GRN))
            except RuntimeError as e:
                msg = str(e)
                print(c(f'⚠ {msg[:80]}', YLW))
                result.errors.append(('coder:groq', msg))
                # Fallback to Ollama
                print(f"  {GRY}→ falling back to Ollama{R}")
                try:
                    with Spinner('Ollama fallback...'):
                        result.code = call_ollama([
                            {'role': 'system', 'content': CODER_SYS},
                            {'role': 'user',   'content': prompt}
                        ], timeout=120)
                    result.fallbacks.append(('groq', 'ollama'))
                    print(c('✓ Ollama fallback', GRN))
                except RuntimeError as e2:
                    result.errors.append(('coder:ollama', str(e2)))
                    print(c(f'  ✗ All agents failed', RED))

        else:  # free / highku — Ollama only
            try:
                with Spinner('Ollama coding...'):
                    result.code = call_ollama([
                        {'role': 'system', 'content': CODER_SYS},
                        {'role': 'user',   'content': prompt}
                    ], timeout=120)
                print(c('✓ Ollama', GRN))
            except RuntimeError as e:
                print(c(f'✗ {str(e)[:80]}', RED))
                result.errors.append(('coder:ollama', str(e)))

    elif result.task_type == 'DOCUMENTATION':
        print(f"  {GRY}[docs]     {R}", end='', flush=True)
        for fn, label in [(lambda: call_groq([{'role':'user','content':prompt}], system=DOC_SYS), 'Groq'),
                           (lambda: call_gemini(prompt, system=DOC_SYS), 'Gemini'),
                           (lambda: call_ollama([{'role':'system','content':DOC_SYS},{'role':'user','content':prompt}], timeout=120), 'Ollama')]:
            try:
                with Spinner(f'{label} writing docs...'):
                    result.code = fn()
                print(c(f'✓ {label}', GRN)); break
            except Exception as e:
                result.errors.append(('docs', str(e)))
                print(c(f'⚠ {label}: {str(e)[:40]}', YLW))

    else:
        # GENERAL_EXPLANATION — use best available model
        print(f"  {GRY}[answer]   {R}", end='', flush=True)
        general_msgs = [{'role': 'system', 'content': GENERAL_SYS}, {'role': 'user', 'content': prompt}]
        for fn, label in [
            (lambda: call_groq([{'role':'user','content':prompt}], system=GENERAL_SYS), 'Groq') if _groq_key() else None,
            (lambda: call_gemini(prompt, system=GENERAL_SYS), 'Gemini') if _gemini_key() else None,
            (lambda: call_ollama(general_msgs, timeout=90), 'Ollama'),
        ]:
            if fn is None: continue
            try:
                with Spinner(f'{label}...'):
                    result.code = fn()
                print(c(f'✓ {label}', GRN)); break
            except Exception as e:
                result.errors.append(('answer', str(e)))

    if _cancel_flag:
        result.cancelled = True; return result

    # ── Explainer (Max plan only, only for code tasks) ────────────────────────
    if plan in ('max', 'pro') and _groq_key() and result.task_type in CODE_TASKS and result.code:
        print(f"  {GRY}[explainer]{R} ", end='', flush=True)
        try:
            ep = f"Task: {prompt}\n\nCode:\n{result.code[:3000]}"
            with Spinner('Explaining...'):
                result.explanation = call_groq([{'role': 'user', 'content': ep}], system=EXPLAINER_SYS)
            print(c('✓ Groq', GRN))
        except RuntimeError as e:
            msg = str(e)
            print(c('⚠ rate limited' if 'RATE_LIMIT' in msg else 'skipped', YLW))
            result.errors.append(('explainer', msg))
    else:
        print(f"  {GRY}[explainer] skipped{R}")

    return result
