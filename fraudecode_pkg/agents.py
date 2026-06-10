"""Multi-agent pipeline with orchestrator integration."""
import json, urllib.request, urllib.error, urllib.parse
from .colours import *
from .ui import Spinner

_cfg: dict = {}
_plan_override: str = ''

def set_config(cfg: dict):
    global _cfg; _cfg = cfg

def set_plan_override(p: str):
    global _plan_override; _plan_override = p

def _groq_key():   return _cfg.get('groqKey','')
def _gemini_key(): return _cfg.get('geminiKey','')
def _ollama_url(): return _cfg.get('ollamaUrl','http://localhost:11434')
def _ollama_mdl(): return _cfg.get('ollamaModel','llama3.2')
def _groq_mdl():   return _cfg.get('groqModel','llama-3.3-70b-versatile')
def _gemini_mdl(): return _cfg.get('geminiModel','gemini-2.0-flash-lite')

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

# ── API callers ────────────────────────────────────────────────────────────────
def call_ollama(messages: list, timeout: int = 60) -> str:
    body = json.dumps({'model': _ollama_mdl(), 'messages': messages, 'stream': False}).encode()
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
    """Direct HTTP call — handles AQ.A (Google AI Studio) and AIzaSy keys."""
    if not _gemini_key():
        raise RuntimeError('No Gemini key')
    key = _gemini_key().strip()
    mdl = _gemini_mdl()
    is_oauth = key.startswith('ya29.')
    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent'
        + ('' if is_oauth else f'?key={urllib.parse.quote(key, safe="")}')
    )
    headers = {'Content-Type': 'application/json'}
    if is_oauth:
        headers['Authorization'] = 'Bearer ' + key

    body_dict = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {'maxOutputTokens': 8192, 'temperature': 0.3},
    }
    if system:
        body_dict['systemInstruction'] = {'parts': [{'text': system}]}

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
        raise RuntimeError(f'Gemini HTTP {e.code}: {msg}')
    except Exception as e:
        raise RuntimeError(f'Gemini: {e}')

def call_groq(messages: list, system: str = '', timeout: int = 30) -> str:
    if not _groq_key():
        raise RuntimeError('No Groq key')
    msgs = ([{'role':'system','content':system}] if system else []) + messages
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

# ── Routing ────────────────────────────────────────────────────────────────────
ROUTER_SYS = "Route to ONE of: CODE_GENERATION, DEBUG, REFACTOR, ARCHITECTURE, DOCUMENTATION, GENERAL_EXPLANATION. Output label only."

CODER_SYS = (
    "Expert software engineer. Output ONLY code in ```lang block. "
    "First line: # FILE: filename.ext. Complete, production-ready, full error handling."
)
GROQ_CODER_SYS = (
    "Expert engineer — fast, clean, efficient code. "
    "Output ONLY code in ```lang block. First line: # FILE: filename.ext. "
    "Complete implementation, no placeholders."
)
EXPLAINER_SYS = (
    "Senior dev. Given code+task: 1)Summary 2)Key functions 3)Usage 4)pip needs 5)Issues. "
    "Markdown. Concise."
)
DOC_SYS = "Technical writer. Create README.md or HANDOFF.md from code. Clear markdown."

def route(prompt: str) -> str:
    try:
        r = call_ollama([
            {'role':'system','content': ROUTER_SYS},
            {'role':'user',  'content': prompt}
        ], timeout=15).strip().upper()
        for v in ['CODE_GENERATION','DEBUG','REFACTOR','ARCHITECTURE','DOCUMENTATION','GENERAL_EXPLANATION']:
            if v in r: return v
    except Exception:
        pass
    return 'GENERAL_EXPLANATION'

class PipelineResult:
    def __init__(self):
        self.task_type   = ''
        self.code        = ''
        self.explanation = ''
        self.errors      = []
        self.fallbacks   = []
        self.cancelled   = False
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
    CODE_TASKS = {'CODE_GENERATION','DEBUG','REFACTOR'}

    # ── Step 1: Route ─────────────────────────────────────────────────────────
    print(f"  {GRY}[router]   {R}", end='', flush=True)
    try:
        with Spinner('Routing...'):
            result.task_type = route(prompt)
        print(c(f'→ {result.task_type}', ACC))
    except Exception as e:
        result.task_type = 'GENERAL_EXPLANATION'
        result.errors.append(('router', str(e)))
        print(c(f'→ offline, skipping routing', YLW))

    if _cancel_flag:
        result.cancelled = True; return result

    # ── Orchestrator check (Max / Oops 0.6 only) ─────────────────────────────
    if (result.task_type in CODE_TASKS and
        plan in ('max', 'oops06') and
        workdir is not None):
        from . import orchestrator
        try:
            should = orchestrator.should_orchestrate(prompt, plan)
        except Exception:
            should = False
        if should:
            print(f"  {c('[orchestrator]', ACC)} Multi-agent pipeline starting...\n")
            orch_result = orchestrator.run(prompt, workdir)
            result.orchestrated = True
            result.code = f'[Orchestrator] {len(orch_result.files_written)} files written to {workdir}'
            if orch_result.review.get('summary'):
                result.explanation = orch_result.review['summary']
            return result

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
                    groq_code = call_groq([{'role':'user','content':prompt}], system=GROQ_CODER_SYS)
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
                        result.code = call_ollama([{'role':'user','content':merge_prompt}], timeout=90)
                    print(c('✓', GRN))
                except RuntimeError:
                    result.code = gem_code
                    print(c('Ollama offline — using Gemini version', YLW))
            else:
                result.code = gem_code or groq_code

        elif plan in ('max', 'oops06') and _gemini_key():
            try:
                with Spinner('Gemini coding...'):
                    result.code = call_gemini(prompt, system=CODER_SYS)
                print(c('✓ Gemini', GRN))
            except RuntimeError as e:
                msg = str(e)
                print(c(f'⚠ {msg[:80]}', YLW))
                result.errors.append(('coder:gemini', msg))
                if _groq_key():
                    try:
                        ans = input(f"\n  {YLW}Gemini unavailable. Use Groq? [Y/n]{R}: ").strip().lower()
                        if ans in ('','y','yes'):
                            result.fallbacks.append(('gemini','groq'))
                            with Spinner('Groq fallback...'):
                                result.code = call_groq([{'role':'user','content':prompt}], system=GROQ_CODER_SYS)
                            print(c('✓ Groq fallback', GRN))
                    except RuntimeError as e2:
                        result.errors.append(('coder:groq', str(e2)))
                        print(c(f'  ✗ {str(e2)[:80]}', RED))
                    except (KeyboardInterrupt, EOFError): pass

        elif plan in ('pro', 'pro05') and _groq_key():
            try:
                with Spinner('Groq coding...'):
                    result.code = call_groq([{'role':'user','content':prompt}], system=GROQ_CODER_SYS)
                print(c('✓ Groq', GRN))
            except RuntimeError as e:
                print(c(f'⚠ {str(e)[:80]}', YLW))
                result.errors.append(('coder:groq', str(e)))

        else:  # free / highku
            try:
                with Spinner('Ollama coding...'):
                    result.code = call_ollama([
                        {'role':'system','content': CODER_SYS},
                        {'role':'user',  'content': prompt}
                    ], timeout=120)
                print(c('✓ Ollama', GRN))
            except RuntimeError as e:
                print(c(f'✗ {str(e)[:80]}', RED))
                result.errors.append(('coder:ollama', str(e)))

    elif result.task_type == 'DOCUMENTATION':
        print(f"  {GRY}[docs]     {R}", end='', flush=True)
        try:
            with Spinner('Writing docs...'):
                result.code = call_groq([{'role':'user','content':prompt}], system=DOC_SYS) if _groq_key() else call_gemini(prompt, system=DOC_SYS)
            print(c('✓', GRN))
        except Exception as e:
            result.errors.append(('docs', str(e)))
            print(c('✗', RED))
    else:
        print(f"  {GRY}[coder]    skipped (explanation task){R}")

    if _cancel_flag:
        result.cancelled = True; return result

    # ── Explainer (single agent — max/oops06 uses Groq to explain, others skip) ──
    if plan in ('max', 'pro') and _groq_key() and result.task_type in CODE_TASKS:
        print(f"  {GRY}[explainer]{R} ", end='', flush=True)
        try:
            ep = f"Task: {prompt}\n\n" + (f"Code:\n{result.code}" if result.code else '')
            with Spinner('Explaining...'):
                result.explanation = call_groq([{'role':'user','content':ep}], system=EXPLAINER_SYS)
            print(c('✓ Groq', GRN))
        except RuntimeError as e:
            msg = str(e)
            if 'RATE_LIMIT' in msg: print(c(f'⚠ rate limited', YLW))
            elif 'No Groq' in msg:  print(c('skipped', GRY))
            else: print(c(f'⚠ {msg[:60]}', YLW))
            result.errors.append(('explainer', msg))
    else:
        print(f"  {GRY}[explainer] skipped{R}")

    return result
