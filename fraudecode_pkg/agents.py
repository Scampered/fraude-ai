"""Multi-agent pipeline — smart routing with explicit plan control and respecting overrides."""
import json, urllib.request, urllib.error, urllib.parse, threading
from .colours import *
from .ui import Spinner

_cfg: dict = {}
_plan_override: str = ''   # explicit user-set plan (persists per session)
_lockin_mode: bool = False
_cancel_flag: bool = False

def set_config(cfg: dict):    global _cfg; _cfg = cfg
def set_plan_override(p: str): global _plan_override; _plan_override = p
def set_lockin(v: bool):       global _lockin_mode; _lockin_mode = v
def get_lockin() -> bool:      return _lockin_mode
def cancel():                  global _cancel_flag; _cancel_flag = True
def reset_cancel():            global _cancel_flag; _cancel_flag = False

def _groq_key():         return (_cfg.get('groqKey') or '').strip()
def _gemini_key():       return (_cfg.get('geminiKey') or '').strip().rstrip(']')
def _openrouter_key():   return (_cfg.get('openrouterKey') or '').strip().rstrip(']')
def _openrouter_mdl():   return _cfg.get('openrouterModel', 'google/gemini-2.0-flash-001')
def _ollama_url():
    url = _cfg.get('ollamaUrl', 'http://localhost:11434')
    return url if url and url.startswith('http') else 'http://localhost:11434'
def _ollama_mdl(): return _cfg.get('ollamaModel', 'llama3.2')
def _groq_mdl():   return (_cfg.get('groqModel') or 'llama-3.3-70b-versatile').strip().rstrip(']')
def _gemini_mdl(): return _cfg.get('geminiModel', 'gemini-2.0-flash-lite')

def get_plan() -> str:
    if _plan_override: return _plan_override
    has_groq = bool(_groq_key()); has_smart = bool(_gemini_key() or _openrouter_key())
    if has_smart and has_groq: return 'max'
    if has_smart:              return 'oops06'
    if has_groq:               return 'pro'
    return 'free'

PLAN_LABELS = {
    'max':    'Oops 0.7      (Gemini + Groq + Ollama)',
    'oops06': 'Oops 0.6      (Gemini + Ollama)',
    'pro':    'Somenet 0.6   (Groq + Ollama)',
    'pro05':  'Somenet 0.5   (Groq only — no Ollama fallback)',
    'free':   'HighKu 0.5    (Ollama only)',
}

IDENTITY_SYS = (
    "You are FraudeCode, a multi-agent AI coding assistant built into the Fraude platform.\n"
    "You are NOT Claude, Gemini, ChatGPT, Llama, or any other named AI. "
    "If asked who you are, say 'I am FraudeCode'."
)
# Lightweight identity for cloud models — just enough so they don't introduce themselves
_CLOUD_IDENTITY = "You are FraudeCode, a coding assistant. Do NOT say 'I am FraudeCode' unless directly asked who you are. Just answer the question."

# ── API callers ────────────────────────────────────────────────────────────────
def call_ollama(messages: list, timeout: int = 60) -> str:
    sys_content = ''.join(m.get('content','') + '\n' for m in messages if m.get('role') == 'system')
    chat_msgs   = [m for m in messages if m.get('role') != 'system']
    payload = {'model': _ollama_mdl(), 'messages': chat_msgs, 'stream': False}
    if sys_content.strip(): payload['system'] = sys_content.strip()
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f'{_ollama_url()}/api/chat', data=body,
        headers={'Content-Type': 'application/json'}, method='POST')
    result = [None]; error = [None]
    def _do():
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                result[0] = json.loads(r.read())['message']['content']
        except urllib.error.URLError as e: error[0] = RuntimeError(f'Ollama unreachable: {e.reason}')
        except Exception as e:            error[0] = RuntimeError(f'Ollama: {e}')
    t = threading.Thread(target=_do, daemon=True); t.start()
    try: t.join(timeout + 5)
    except KeyboardInterrupt: raise RuntimeError('Cancelled (Ctrl+C)')
    if error[0]: raise error[0]
    if result[0] is None: raise RuntimeError('Ollama timed out')
    return result[0]

def call_groq(messages: list, system: str = '', timeout: int = 45) -> str:
    if not _groq_key(): raise RuntimeError('Groq key not set')
    # Only add system msg if explicitly provided — don't force identity on every call
    sys_msgs = [{'role': 'system', 'content': system}] if system else []
    msgs = sys_msgs + [m for m in messages if m.get('role') != 'system']
    body = json.dumps({'model': _groq_mdl(), 'messages': msgs, 'max_tokens': 8192, 'temperature': 0.3}).encode()
    req  = urllib.request.Request('https://api.groq.com/openai/v1/chat/completions',
        data=body, headers={'Content-Type':'application/json','Authorization':f'Bearer {_groq_key()}'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        body_t = e.read().decode('utf-8', errors='replace')
        d = json.loads(body_t) if body_t.startswith('{') else {}
        msg = d.get('error', {}).get('message', body_t[:200])
        if e.code == 429:  raise RuntimeError(f'RATE_LIMIT: Groq — {msg}')
        if e.code == 401:  raise RuntimeError(f'Groq auth error (401) — check API key')
        if e.code == 403:  raise RuntimeError(f'Groq auth error (403) — check API key')
        raise RuntimeError(f'Groq HTTP {e.code}: {msg}')
    except Exception as e: raise RuntimeError(f'Groq: {e}')

def call_gemini(prompt_or_messages, system: str = '', timeout: int = 45) -> str:
    key = _gemini_key()
    if not key: raise RuntimeError('Gemini key not set')
    if isinstance(prompt_or_messages, str):
        contents = [{'role': 'user', 'parts': [{'text': prompt_or_messages}]}]
    else:
        role_map = {'user': 'user', 'assistant': 'model'}
        contents = [{'role': role_map.get(m['role'], 'user'), 'parts': [{'text': m.get('content','')}]}
                    for m in prompt_or_messages if m.get('role') not in ('system',)]
    # Only inject system if provided — don't force identity prefix on every response
    full_sys = system if system else None
    gemini_body = {'contents': contents, 'generationConfig': {'maxOutputTokens': 8192, 'temperature': 0.3}}
    if full_sys: gemini_body['systemInstruction'] = {'parts': [{'text': full_sys}]}
    body = json.dumps(gemini_body,
).encode()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{_gemini_mdl()}:generateContent?key={key}'
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
        return d['candidates'][0]['content']['parts'][0]['text']
    except urllib.error.HTTPError as e:
        body_t = e.read().decode('utf-8', errors='replace')
        d = json.loads(body_t) if body_t.startswith('{') else {}
        msg = d.get('error', {}).get('message', body_t[:200])
        if e.code in (401, 403): raise RuntimeError(f'Gemini auth failed — {msg}')
        if e.code == 429:        raise RuntimeError(f'RATE_LIMIT: Gemini — {msg}')
        raise RuntimeError(f'Gemini HTTP {e.code}: {msg}')
    except Exception as e: raise RuntimeError(f'Gemini: {e}')

def call_openrouter(prompt_or_messages, system: str = '', timeout: int = 45) -> str:
    if not _openrouter_key(): raise RuntimeError('OpenRouter key not set')
    if isinstance(prompt_or_messages, str):
        msgs = [{'role':'system','content':IDENTITY_SYS+('\n\n'+system if system else '')},
                {'role':'user','content':prompt_or_messages}]
    else:
        sys_content = system if system else _CLOUD_IDENTITY
    msgs = [{'role':'system','content':sys_content}] + \
               [m for m in prompt_or_messages if m.get('role') != 'system']
    body = json.dumps({'model': _openrouter_mdl(), 'messages': msgs,
                       'max_tokens': 8192, 'temperature': 0.3}).encode()
    req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', data=body,
        headers={'Authorization':f'Bearer {_openrouter_key()}',
                 'Content-Type':'application/json',
                 'HTTP-Referer':'https://fraude-ai.vercel.app','X-Title':'FraudeCode'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        body_t = e.read().decode('utf-8', errors='replace')
        d = json.loads(body_t) if body_t.startswith('{') else {}
        msg = d.get('error', {}).get('message', body_t[:200])
        if e.code == 429: raise RuntimeError(f'RATE_LIMIT: OpenRouter — {msg}')
        if e.code in (401,403): raise RuntimeError(f'OpenRouter auth failed — check sk-or-... key')
        raise RuntimeError(f'OpenRouter HTTP {e.code}: {msg}')
    except Exception as e: raise RuntimeError(f'OpenRouter: {e}')

# ── Smart caller: tries Gemini → OpenRouter ───────────────────────────────────
def call_smart(prompt, system='', label='Smart'):
    """Try Gemini first, fall back to OpenRouter. Raises if both fail."""
    if _gemini_key():
        try:
            return call_gemini(prompt, system=system)
        except RuntimeError as e:
            if _openrouter_key():
                print(c(f'  Gemini failed ({str(e)[:50]}), trying OpenRouter…', YLW))
                return call_openrouter(prompt, system=system)
            raise
    if _openrouter_key():
        return call_openrouter(prompt, system=system)
    raise RuntimeError('No Gemini or OpenRouter key configured')

# ── Router ─────────────────────────────────────────────────────────────────────
ROUTER_SYS = (
    "Classify this message into EXACTLY ONE label:\n"
    "CODE_GENERATION - writing new code, scripts, programs, websites, apps, APIs, tools\n"
    "DEBUG           - fixing bugs, errors, tracebacks, crashes\n"
    "REFACTOR        - improving, cleaning, optimising existing code\n"
    "ARCHITECTURE    - system design, planning, structure decisions\n"
    "DOCUMENTATION   - writing docs, README, comments, handoff notes\n"
    "AUDIT           - code review, security check, quality analysis\n"
    "GENERAL_EXPLANATION - greetings, conversation, conceptual questions, explanations with no code needed\n\n"
    "RULES:\n"
    "- Greetings (hi, hello, hey, thanks, how are you) → GENERAL_EXPLANATION\n"
    "- 'what is X' or 'explain X' with no code → GENERAL_EXPLANATION\n"
    "- 'fix this error' or 'why does this crash' → DEBUG\n"
    "- 'improve / clean / optimise / refactor this code' → REFACTOR\n"
    "- 'review / audit / check my code' → AUDIT\n"
    "- 'write / make / create / build X' → CODE_GENERATION\n"
    "Output the label ONLY. Nothing else."
)

def _local_classify(prompt: str) -> str | None:
    """Fast local classification — no API needed. Returns label or None to use API."""
    import re
    tl = prompt.strip().lower()

    # Definite greetings — skip API entirely
    greet_pats = re.compile(r'^(hi|hello|hey|thanks|thank you|ok|okay|got it|sure|cool|great|nothing|bye|exit|quit|yes|no|yep|nope|nah)\s*[!.?]?\s*$')
    if greet_pats.match(tl): return 'GENERAL_EXPLANATION'

    # Strong code creation signals — override everything
    code_langs = r'(python|javascript|js|typescript|html|css|react|flask|fastapi|django|node|sql|bash|shell|c\+\+|java|rust|go)'
    code_actions = r'(write|create|make|build|generate|code|implement|develop|design|give me|show me|write me|create me|make me|build me)'
    code_obj = r'(function|script|program|app|application|website|webpage|api|server|class|module|file|tool|calculator|dashboard|game|bot|cli|utility)'

    # "write a python X", "create a X in python", "make a X", "write me a function"
    if re.search(rf'{code_actions}\s+(a\s+)?{code_langs}', tl): return 'CODE_GENERATION'
    if re.search(rf'{code_actions}\s+(a\s+)?{code_obj}', tl): return 'CODE_GENERATION'
    if re.search(rf'{code_actions}\s+\w+\s+(in|using|with)\s+{code_langs}', tl): return 'CODE_GENERATION'
    # "hello world", "prime number function", "fibonacci" etc as standalone requests
    if re.search(r'(hello world|prime|fibonacci|palindrome|factorial|sorting|linked list)', tl) and len(tl) < 60:
        return 'CODE_GENERATION'

    # Debug signals
    if re.search(r'(fix|debug|error|traceback|exception|crash|broken|not working|fails)', tl) and re.search(r'(code|function|script|program|line)', tl):
        return 'DEBUG'

    # Refactor signals
    if re.search(r'(refactor|clean up|improve|optimise|optimize|make.*faster|make.*efficient)', tl) and re.search(r'(code|function|script|this)', tl):
        return 'REFACTOR'

    # Pure explanation — no code needed
    if re.search(r'^(what is|what are|explain|how does|why does|tell me about|describe)\s', tl) and not re.search(r'code|function|class|api', tl):
        return 'GENERAL_EXPLANATION'

    return None  # Uncertain — use API

def route(prompt: str) -> str:
    # 1. Fast local pre-classification — no API call
    local = _local_classify(prompt)
    if local: return local

    # 2. API routing — use Groq first (fast, cheap), then OpenRouter, then Ollama
    # Note: send as user message ONLY — no system prompt for routing (avoids 403 issues)
    router_user_msg = f'Classify this into one label only (CODE_GENERATION/DEBUG/REFACTOR/ARCHITECTURE/DOCUMENTATION/AUDIT/GENERAL_EXPLANATION):\n{prompt[:400]}'

    for fn in [
        # Groq: NO system prompt — just user message with label list embedded
        (lambda: call_groq([{'role':'user','content':router_user_msg + "\n\nRULES: write/make/create/build = CODE_GENERATION. greetings/questions = GENERAL_EXPLANATION. Output label ONLY."}])) if _groq_key() else None,
        # OpenRouter: same
        (lambda: call_smart(router_user_msg + "\n\nRULES: write/make/create/build = CODE_GENERATION. greetings/questions = GENERAL_EXPLANATION. Output label ONLY.")) if (_gemini_key() or _openrouter_key()) else None,
        # Ollama: with system prompt
        (lambda: call_ollama([{'role':'system','content':ROUTER_SYS},{'role':'user','content':f'Classify: {prompt[:300]}'}], timeout=20)),
    ]:
        if fn is None: continue
        try:
            result = fn().strip().upper().split()[0]  # take first word only
            valid = {'CODE_GENERATION','DEBUG','REFACTOR','ARCHITECTURE','DOCUMENTATION','AUDIT','GENERAL_EXPLANATION'}
            for label in valid:
                if label in result: return label
        except Exception: continue

    # 3. Final local fallback — if API routing failed, use heuristics
    tl = prompt.strip().lower()
    if any(w in tl for w in ['write','create','make','build','generate','code','function','script','program']):
        return 'CODE_GENERATION'
    return 'GENERAL_EXPLANATION'

# ── System prompts ─────────────────────────────────────────────────────────────
CODER_SYS = (
    "You are FraudeCode Coder. Write complete, working code. "
    "Output each file using this EXACT format — # FILE: filename.ext on the very first line of the code block, then the complete file contents. "
    "Include all imports. Add brief comments. No placeholders."
)
GROQ_CODER_SYS = CODER_SYS + "\nUse Python 3.12+ syntax. Prefer stdlib when possible."
EXPLAINER_SYS = (
    "You are FraudeCode Explainer. Given a task and generated code, "
    "write a brief explanation: what it does, how to use it, any caveats. "
    "Max 150 words. Plain text, no code blocks."
)
DOC_SYS = (
    "You are FraudeCode Docs writer. Generate clear, professional documentation. "
    "Use markdown. Be thorough but concise."
)
GENERAL_SYS = (
    _CLOUD_IDENTITY + "\n\nAnswer conversationally and concisely. "
    "Do NOT introduce yourself in every message. "
    "If relevant, suggest slash commands (/run, /audit, /files). "
    "Keep responses under 150 words unless detail is needed."
)
AUDIT_SYS = (
    "You are FraudeCode Auditor. Review the provided code and give structured feedback:\n"
    "1. BUGS: Critical errors or logic flaws\n"
    "2. PERFORMANCE: Inefficiencies, unnecessary complexity\n"
    "3. QUALITY: Readability, naming, structure\n"
    "4. FIXES: Specific improved code snippets\n"
    "Be concrete — quote the problematic lines and show the fix."
)

# ── Pipeline result ────────────────────────────────────────────────────────────
class PipelineResult:
    def __init__(self):
        self.task_type    = ''
        self.code         = ''        # generated code (shown as FILE blocks)
        self.explanation  = ''        # conversational explanation (shown as text)
        self.errors       = []
        self.fallbacks    = []
        self.orchestrated = False
        self.cancelled    = False

# ── Main pipeline ──────────────────────────────────────────────────────────────
def run(prompt: str, workdir: str = None, context: str = None) -> PipelineResult:
    reset_cancel()
    result = PipelineResult()
    plan   = get_plan()  # respects explicit override
    if context:
        prompt = context + '\n\nUser request: ' + prompt

    CODE_TASKS = {'CODE_GENERATION', 'DEBUG', 'REFACTOR', 'ARCHITECTURE'}

    # ── Step 1: Route ──────────────────────────────────────────────────────────
    print(f"  {GRY}[router]   {R}", end='', flush=True)
    try:
        with Spinner('Routing…'):
            result.task_type = route(prompt)
        print(c(f'→ {result.task_type}', ACC))
    except Exception as e:
        result.task_type = 'GENERAL_EXPLANATION'
        result.errors.append(('router', str(e)))
        print(c('→ offline, defaulting to GENERAL_EXPLANATION', YLW))

    if _cancel_flag: result.cancelled = True; return result

    # ── Step 2: Execute ────────────────────────────────────────────────────────

    # ── AUDIT ─────────────────────────────────────────────────────────────────
    if result.task_type == 'AUDIT':
        print(f"  {GRY}[auditor]  {R}", end='', flush=True)
        # Audit needs smart model — Ollama can't do thorough reviews
        has_smart = bool(_gemini_key() or _openrouter_key())
        audit_chain = []
        if plan == 'free':
            audit_chain.append(((lambda: call_ollama([{'role':'system','content':AUDIT_SYS},{'role':'user','content':prompt}], timeout=120)), 'Ollama'))
        elif plan in ('oops06',):
            if has_smart: audit_chain.append(((lambda: call_smart(prompt, system=AUDIT_SYS)), 'Gemini/OR'))
            audit_chain.append(((lambda: call_ollama([{'role':'system','content':AUDIT_SYS},{'role':'user','content':prompt}], timeout=120)), 'Ollama'))
        elif plan in ('pro', 'pro05'):
            if _groq_key(): audit_chain.append(((lambda: call_groq([{'role':'user','content':prompt}], system=AUDIT_SYS)), 'Groq'))
            if plan != 'pro05': audit_chain.append(((lambda: call_ollama([{'role':'system','content':AUDIT_SYS},{'role':'user','content':prompt}], timeout=120)), 'Ollama'))
        else:  # max
            if has_smart: audit_chain.append(((lambda: call_smart(prompt, system=AUDIT_SYS)), 'Gemini/OR'))
            if _groq_key(): audit_chain.append(((lambda: call_groq([{'role':'user','content':prompt}], system=AUDIT_SYS)), 'Groq'))
            audit_chain.append(((lambda: call_ollama([{'role':'system','content':AUDIT_SYS},{'role':'user','content':prompt}], timeout=120)), 'Ollama'))
        for fn, label in audit_chain:
            try:
                with Spinner(f'{label} auditing…'): result.explanation = fn()
                print(c(f'✓ {label}', GRN)); break
            except Exception as e:
                result.errors.append(('auditor', str(e)))
                print(c(f'⚠ {label}: {str(e)[:60]}', YLW))

    # ── GENERAL_EXPLANATION ───────────────────────────────────────────────────
    elif result.task_type == 'GENERAL_EXPLANATION':
        print(f"  {GRY}[answer]   {R}", end='', flush=True)
        # Build fallback chain based on plan — don't try Groq on oops06, don't try smart on pro05/free
        has_smart = bool(_gemini_key() or _openrouter_key())
        answer_chain = []
        if plan in ('max',):              # Max: Groq first (fast), then Smart, then Ollama
            if _groq_key():   answer_chain.append(((lambda: call_groq([{'role':'user','content':prompt}], system=GENERAL_SYS)), 'Groq'))
            if has_smart:     answer_chain.append(((lambda: call_smart(prompt, system=GENERAL_SYS)), 'Gemini/OR'))
        elif plan in ('oops06',):         # Oops06: Smart then Ollama — no Groq
            if has_smart:     answer_chain.append(((lambda: call_smart(prompt, system=GENERAL_SYS)), 'Gemini/OR'))
        elif plan in ('pro', 'pro05'):    # Pro: Groq only (pro05 never falls to smart)
            if _groq_key():   answer_chain.append(((lambda: call_groq([{'role':'user','content':prompt}], system=GENERAL_SYS)), 'Groq'))
        # Ollama always last resort (except pro05 explicit Groq-only)
        if plan != 'pro05':
            answer_chain.append(((lambda: call_ollama([{'role':'system','content':IDENTITY_SYS+'\n\n'+GENERAL_SYS},{'role':'user','content':prompt}], timeout=60)), 'Ollama'))
        for fn, label in answer_chain:
            try:
                with Spinner(f'{label}…'): result.explanation = fn()
                print(c(f'✓ {label}', GRN)); break
            except Exception as e:
                result.errors.append(('answer', str(e)))
                print(c(f'⚠ {label}: {str(e)[:60]}', YLW))

    # ── DOCUMENTATION ─────────────────────────────────────────────────────────
    elif result.task_type == 'DOCUMENTATION':
        print(f"  {GRY}[docs]     {R}", end='', flush=True)
        for fn, label in [
            ((lambda: call_smart(prompt, system=DOC_SYS)), 'Gemini/OR') if (_gemini_key() or _openrouter_key()) else None,
            ((lambda: call_groq([{'role':'user','content':prompt}], system=DOC_SYS)), 'Groq') if _groq_key() else None,
            ((lambda: call_ollama([{'role':'system','content':DOC_SYS},{'role':'user','content':prompt}], timeout=120)), 'Ollama'),
        ]:
            if fn is None: continue
            try:
                with Spinner(f'{label} writing…'): result.explanation = fn()
                print(c(f'✓ {label}', GRN)); break
            except Exception as e:
                result.errors.append(('docs', str(e)))
                print(c(f'⚠ {label}: {str(e)[:40]}', YLW))

    # ── CODE TASKS ─────────────────────────────────────────────────────────────
    elif result.task_type in CODE_TASKS:
        print(f"  {GRY}[coder]    {R}", end='', flush=True)

        # LOCKIN mode: both Gemini AND Groq generate, Ollama merges
        if _lockin_mode and _groq_key() and (_gemini_key() or _openrouter_key()):
            print(c('LOCKIN — dual coder', ACC))
            gem_code = groq_code = ''
            try:
                with Spinner('Smart coding…'): gem_code = call_smart(prompt, system=CODER_SYS)
                print(c('  ✓ Gemini/OR', GRN))
            except RuntimeError as e: print(c(f'  ⚠ Smart: {str(e)[:60]}', YLW))
            try:
                with Spinner('Groq drafting…'): groq_code = call_groq([{'role':'user','content':prompt}], system=GROQ_CODER_SYS)
                print(c('  ✓ Groq', GRN))
            except RuntimeError as e: print(c(f'  ⚠ Groq: {str(e)[:60]}', YLW))
            if gem_code and groq_code:
                print(f"  {GRY}[merger]   {R}", end='', flush=True)
                merge = (f"Merge these two implementations for: {prompt}\n\nVersion A:\n{gem_code}\n\nVersion B:\n{groq_code}\n\nOutput the best merged version only.")
                try:
                    with Spinner('Merging…'): result.code = call_ollama([{'role':'user','content':merge}], timeout=90)
                    print(c('✓ merged', GRN))
                except RuntimeError:
                    result.code = gem_code; print(c('Ollama offline — using Gemini version', YLW))
            else:
                result.code = gem_code or groq_code

        # MAX plan: Smart (Gemini/OR) → Groq → Ollama
        elif plan == 'max':
            try:
                with Spinner('Gemini/OR coding…'): result.code = call_smart(prompt, system=CODER_SYS)
                print(c('✓ Gemini/OR', GRN))
            except RuntimeError as e:
                msg = str(e); print(c(f'⚠ Smart failed: {msg[:70]}', YLW)); result.errors.append(('coder:smart', msg))
                if _groq_key():
                    print(f"  {GRY}→ Groq fallback{R}", end=' ', flush=True)
                    try:
                        with Spinner('Groq…'): result.code = call_groq([{'role':'user','content':prompt}], system=GROQ_CODER_SYS)
                        result.fallbacks.append(('smart','groq')); print(c('✓ Groq', GRN))
                    except RuntimeError as e2:
                        print(c(f'⚠ Groq: {str(e2)[:60]}', YLW)); result.errors.append(('coder:groq', str(e2)))
                        print(f"  {GRY}→ Ollama last resort{R}", end=' ', flush=True)
                        try:
                            with Spinner('Ollama…'): result.code = call_ollama([{'role':'system','content':IDENTITY_SYS+'\n\n'+CODER_SYS},{'role':'user','content':prompt}], timeout=120)
                            result.fallbacks.append(('groq','ollama')); print(c('✓ Ollama', GRN))
                        except RuntimeError as e3: result.errors.append(('coder:ollama', str(e3))); print(c('✗ All agents failed', RED))
                else:
                    print(f"  {GRY}→ Ollama fallback{R}", end=' ', flush=True)
                    try:
                        with Spinner('Ollama…'): result.code = call_ollama([{'role':'system','content':IDENTITY_SYS+'\n\n'+CODER_SYS},{'role':'user','content':prompt}], timeout=120)
                        result.fallbacks.append(('smart','ollama')); print(c('✓ Ollama', GRN))
                    except RuntimeError as e3: result.errors.append(('coder:ollama', str(e3))); print(c('✗ Failed', RED))

        # OOPS06 plan: Smart (Gemini/OR) → Ollama only (no Groq)
        elif plan == 'oops06':
            try:
                with Spinner('Gemini/OR coding…'): result.code = call_smart(prompt, system=CODER_SYS)
                print(c('✓ Gemini/OR', GRN))
            except RuntimeError as e:
                msg = str(e); print(c(f'⚠ {msg[:70]}', YLW)); result.errors.append(('coder:smart', msg))
                print(f"  {GRY}→ Ollama fallback{R}", end=' ', flush=True)
                try:
                    with Spinner('Ollama…'): result.code = call_ollama([{'role':'system','content':IDENTITY_SYS+'\n\n'+CODER_SYS},{'role':'user','content':prompt}], timeout=120)
                    result.fallbacks.append(('smart','ollama')); print(c('✓ Ollama', GRN))
                except RuntimeError as e2: result.errors.append(('coder:ollama', str(e2))); print(c('✗ Failed', RED))

        # PRO plan: Groq → Ollama
        elif plan == 'pro':
            try:
                with Spinner('Groq coding…'): result.code = call_groq([{'role':'user','content':prompt}], system=GROQ_CODER_SYS)
                print(c('✓ Groq', GRN))
            except RuntimeError as e:
                msg = str(e); print(c(f'⚠ {msg[:70]}', YLW)); result.errors.append(('coder:groq', msg))
                print(f"  {GRY}→ Ollama fallback{R}", end=' ', flush=True)
                try:
                    with Spinner('Ollama…'): result.code = call_ollama([{'role':'system','content':IDENTITY_SYS+'\n\n'+CODER_SYS},{'role':'user','content':prompt}], timeout=120)
                    result.fallbacks.append(('groq','ollama')); print(c('✓ Ollama', GRN))
                except RuntimeError as e2: result.errors.append(('coder:ollama', str(e2))); print(c('✗ Failed', RED))

        # PRO05 plan: Groq ONLY — no Ollama fallback
        elif plan == 'pro05':
            try:
                with Spinner('Groq coding…'): result.code = call_groq([{'role':'user','content':prompt}], system=GROQ_CODER_SYS)
                print(c('✓ Groq', GRN))
            except RuntimeError as e:
                msg = str(e); print(c(f'✗ {msg[:80]}', RED))
                print(c('  Somenet 0.5 uses Groq only — no fallback. Add Gemini/Ollama for fallback.', YLW))
                result.errors.append(('coder:groq', msg))

        else:  # FREE / HighKu — Ollama only
            try:
                with Spinner('Ollama coding…'): result.code = call_ollama([{'role':'system','content':IDENTITY_SYS+'\n\n'+CODER_SYS},{'role':'user','content':prompt}], timeout=120)
                print(c('✓ Ollama', GRN))
            except RuntimeError as e:
                print(c(f'✗ {str(e)[:80]}', RED)); result.errors.append(('coder:ollama', str(e)))

    if _cancel_flag: result.cancelled = True; return result

    # ── Step 3: Explainer (only for code tasks on Max/Pro, and only if code was generated) ──
    if result.code and result.task_type in CODE_TASKS and plan in ('max', 'pro') and not _lockin_mode:
        print(f"  {GRY}[explainer]{R} ", end='', flush=True)
        try:
            ep = f"Task: {prompt[:300]}\n\nCode:\n{result.code[:3000]}"
            with Spinner('Explaining…'):
                result.explanation = call_groq([{'role':'user','content':ep}], system=EXPLAINER_SYS)
            print(c('✓ Groq', GRN))
        except RuntimeError as e:
            msg = str(e)
            print(c('⚠ rate limited' if 'RATE_LIMIT' in msg else 'skipped', YLW))
            result.errors.append(('explainer', msg))
    elif result.task_type in CODE_TASKS:
        print(f"  {GRY}[explainer] skipped{R}")

    return result
