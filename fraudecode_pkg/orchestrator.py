"""
orchestrator.py — FraudeCode Multi-Agent Orchestration Engine

For Oops 0.7 (Max): Gemini codes → Groq explains/implements → Ollama reviews
For Oops 0.6:       Gemini codes → Ollama reviews
For lower tiers:    Single-agent, no orchestration

Called from agents.run() when Ollama decides the task needs multi-agent treatment.
Also callable directly via /orchestrate command.
"""
import json, re
from datetime import datetime
from pathlib import Path
from .colours import *
from .ui import Spinner
from . import workspace as ws

# ── Progress callback (set by web UI or CLI) ───────────────────────────────────
_progress_cb = None  # fn(event_type, data) — called for UI updates

def set_progress_callback(cb):
    global _progress_cb
    _progress_cb = cb

def _emit(event: str, data: dict = None):
    if _progress_cb:
        try:
            _progress_cb(event, data or {})
        except Exception:
            pass

# ── File block parser ──────────────────────────────────────────────────────────
def parse_file_blocks(text: str) -> dict:
    """Extract ===FILE: name=== ... ===END=== blocks. Returns {filename: content}."""
    pattern = r'===FILE:\s*([^\n=]+)===\s*(.*?)===END==='
    matches = re.findall(pattern, text, re.DOTALL)
    return {m[0].strip(): m[1].strip() for m in matches}

def parse_json_response(text: str) -> dict | None:
    """Extract JSON from a model response, stripping markdown fences."""
    text = text.strip()
    # Strip ```json fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    # Find first { ... } block
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None

# ── Complexity check ───────────────────────────────────────────────────────────
ORCHESTRATE_PROMPT = """You are a task complexity classifier for a multi-agent coding tool.
The user said: "{request}"
Decide if this needs multiple AI agents working together (orchestration) or just one agent.

Rules:
- Orchestrate if: building a multi-file project, needs UI+logic separation, full-stack, complex algorithm with visualisation
- Single agent if: simple script, short function, explanation, debugging a single file, quick fix

Return JSON only:
{{"orchestrate": true or false, "reason": "one sentence"}}"""

def should_orchestrate(request: str, plan: str) -> bool:
    """Ask Ollama whether this task needs multi-agent orchestration."""
    from .agents import call_ollama, get_plan
    if plan in ('free', 'pro05'):
        return False  # only one model available
    if plan == 'oops06' and not request:
        return False
    try:
        resp = call_ollama([
            {'role': 'user', 'content': ORCHESTRATE_PROMPT.format(request=request[:500])}
        ], timeout=15)
        d = parse_json_response(resp)
        if d:
            return bool(d.get('orchestrate', False))
    except Exception:
        pass
    # Heuristic fallback
    multi_keywords = ['website', 'app', 'application', 'dashboard', 'full stack', 'fullstack',
                      'frontend', 'backend', 'api', 'gui', 'program with ui', 'tkinter',
                      'flask', 'fastapi', 'build me', 'create a', 'make a']
    req_lower = request.lower()
    return any(kw in req_lower for kw in multi_keywords)

# ── Project analysis ───────────────────────────────────────────────────────────
ANALYSIS_PROMPT = """You are a software project orchestrator. A user wants to build:
"{request}"

Analyze this and return a JSON object ONLY. No explanation. No markdown. Raw JSON.

{{
  "project_name": "short kebab-case name",
  "project_type": "layered or split",
  "rationale": "one sentence why",
  "steps": [
    {{
      "step": 1,
      "agent": "groq or gemini or ollama",
      "role": "short label e.g. Core Logic",
      "task": "detailed description of exactly what this agent should build",
      "output_files": ["suggested_filename.py"],
      "depends_on_step": null,
      "runs_parallel_with": null
    }}
  ],
  "contract_needed": true or false,
  "tech_stack": ["Python", "Tkinter"],
  "conventions": {{
    "variables": "snake_case",
    "files": "snake_case",
    "classes": "PascalCase",
    "functions": "snake_case"
  }}
}}

Rules:
- groq: fast logic, backend, data processing, algorithms, file I/O, APIs, CLI tools
- gemini: UI/frontend, design-heavy, complex reasoning, architecture, Tkinter/HTML/CSS
- ollama: review passes only — never primary code generation for large files
- Maximum 3 steps
- layered = sequential (each builds on last), split = parallel (separate domains)
- If split, set contract_needed true"""

def analyze_project(request: str) -> dict | None:
    from .agents import call_ollama
    for attempt in range(2):
        try:
            prompt = ANALYSIS_PROMPT.format(request=request)
            if attempt == 1:
                prompt += '\n\nIMPORTANT: Return ONLY raw JSON, no other text.'
            _emit('status', {'message': 'Analyzing project structure...'})
            resp = call_ollama([{'role': 'user', 'content': prompt}], timeout=45)
            d = parse_json_response(resp)
            if d and 'steps' in d:
                return d
        except Exception as e:
            _emit('error', {'message': f'Analysis error: {e}'})
    # Fallback plan
    return {
        'project_name': 'project',
        'project_type': 'layered',
        'steps': [
            {'step': 1, 'agent': 'groq',   'role': 'Core Logic',
             'task': request, 'output_files': ['main.py'],
             'depends_on_step': None, 'runs_parallel_with': None},
            {'step': 2, 'agent': 'gemini', 'role': 'UI / Polish',
             'task': f'Build UI for: {request}', 'output_files': ['ui.py'],
             'depends_on_step': 1, 'runs_parallel_with': None},
        ],
        'contract_needed': False,
        'tech_stack': ['Python'],
        'conventions': {'variables': 'snake_case', 'files': 'snake_case',
                        'classes': 'PascalCase', 'functions': 'snake_case'},
    }

# ── Contract generation ────────────────────────────────────────────────────────
CONTRACT_PROMPT = """You are a software contract generator. Two AI agents will build different parts simultaneously.
Project: "{request}"
Tech stack: {tech_stack}
Steps: {steps_json}

Return JSON ONLY — the shared interface contract:
{{
  "shared_types": {{}},
  "shared_constants": {{}},
  "interfaces": {{}},
  "file_ownership": {{}},
  "import_rules": [],
  "do_not_cross": []
}}"""

def generate_contract(request: str, plan_data: dict) -> dict:
    from .agents import call_ollama
    try:
        prompt = CONTRACT_PROMPT.format(
            request=request,
            tech_stack=json.dumps(plan_data.get('tech_stack', [])),
            steps_json=json.dumps(plan_data.get('steps', []), indent=2),
        )
        _emit('status', {'message': 'Generating contract...'})
        resp = call_ollama([{'role': 'user', 'content': prompt}], timeout=45)
        d = parse_json_response(resp)
        return d or {}
    except Exception:
        return {}

# ── Agent system prompts ───────────────────────────────────────────────────────
def build_agent_prompt(step: dict, plan_data: dict, handoff: str = '', contract: dict = None) -> str:
    conv = plan_data.get('conventions', {})
    tech = ', '.join(plan_data.get('tech_stack', []))
    lines = [
        f"You are an AI coding agent in a multi-agent pipeline.",
        f"PROJECT: {plan_data.get('project_name', 'project')}",
        f"YOUR ROLE: {step['role']}",
        f"YOUR TASK: {step['task']}",
        f"TECH STACK: {tech}",
        f"",
        f"CONVENTIONS — follow exactly:",
        f"- Variables: {conv.get('variables', 'snake_case')}",
        f"- Files: {conv.get('files', 'snake_case')}",
        f"- Classes: {conv.get('classes', 'PascalCase')}",
        f"- Functions: {conv.get('functions', 'snake_case')}",
    ]

    if handoff:
        lines += [
            '', 'PREVIOUS WORK (do not modify these files — build on top of them):',
            handoff,
        ]

    if contract:
        lines += [
            '', 'CONTRACT (stay within your file ownership):',
            json.dumps(contract, indent=2),
        ]

    lines += [
        '',
        'OUTPUT RULES:',
        '- Write complete, working, production-ready code only',
        '- No placeholders, no TODOs, no "add your logic here"',
        '- Output each file using EXACTLY this format:',
        '',
        '===FILE: filename.ext===',
        '[complete file content]',
        '===END===',
        '',
        '- Repeat the block for each file',
        '- Write NOTHING outside the file blocks',
    ]
    return '\n'.join(lines)

# ── Run one agent step ─────────────────────────────────────────────────────────
def run_agent_step(step: dict, system_prompt: str, plan: str) -> str:
    from .agents import call_gemini, call_groq, call_ollama, get_plan
    agent   = step['agent']
    role    = step['role']
    task    = step['task']
    timeout = 90

    _emit('step_start', {'step': step['step'], 'agent': agent, 'role': role})
    print(f"\n  {c(f'[step {step[\"step\"]}]', ACC)} {bold(role)} {GRY}→ {agent}{R}")

    for attempt in range(2):
        try:
            with Spinner(f'{agent.title()} working...'):
                if agent == 'gemini':
                    # Direct HTTP call — handles both AQ.A and AIzaSy
                    result = _gemini_direct(task, system_prompt, timeout)
                elif agent == 'groq':
                    result = call_groq(
                        [{'role': 'user', 'content': task}],
                        system=system_prompt, timeout=timeout
                    )
                else:
                    result = call_ollama(
                        [{'role': 'system', 'content': system_prompt},
                         {'role': 'user',   'content': task}],
                        timeout=timeout
                    )

            # Retry if no file blocks found
            if '===FILE:' not in result:
                if attempt == 0:
                    print(c(f'  ⚠ No file blocks, retrying...', YLW))
                    task_retry = task + '\n\nIMPORTANT: Your response MUST use ===FILE: filename=== ... ===END=== blocks only.'
                    step = {**step, 'task': task_retry}
                    continue
                else:
                    print(c(f'  ⚠ Still no file blocks — using raw response', YLW))

            _emit('step_done', {'step': step['step'], 'agent': agent})
            print(c(f'  ✓ {agent.title()} done', GRN))
            return result

        except Exception as e:
            msg = str(e)
            print(c(f'  ✗ {agent}: {msg[:80]}', RED))
            _emit('step_error', {'step': step['step'], 'agent': agent, 'error': msg})
            # Fallback logic
            if agent == 'gemini' and 'RATE_LIMIT' in msg:
                print(c('  Falling back to Groq...', YLW))
                step = {**step, 'agent': 'groq'}
                agent = 'groq'
            elif agent == 'groq' and attempt == 0:
                continue
            break

    _emit('step_failed', {'step': step['step']})
    return ''

def _gemini_direct(prompt: str, system: str, timeout: int = 90) -> str:
    """Call Gemini via direct HTTP — handles AQ.A and AIzaSy keys."""
    from .agents import _gemini_key, _gemini_mdl
    import urllib.request, urllib.error, urllib.parse
    key = _gemini_key().strip()
    mdl = _gemini_mdl()
    is_oauth = key.startswith('ya29.')
    url = (f'https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent'
           + ('' if is_oauth else f'?key={urllib.parse.quote(key, safe="")}'))
    headers = {'Content-Type': 'application/json'}
    if is_oauth:
        headers['Authorization'] = 'Bearer ' + key

    body = json.dumps({
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'systemInstruction': {'parts': [{'text': system}]} if system else None,
        'generationConfig': {'maxOutputTokens': 8192, 'temperature': 0.3},
    }).encode()
    # Remove null systemInstruction
    body_dict = json.loads(body)
    if not system:
        body_dict.pop('systemInstruction', None)
    body = json.dumps(body_dict).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
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

# ── Handoff generation ─────────────────────────────────────────────────────────
HANDOFF_PROMPT = """An AI agent just wrote code for a multi-step project.

Files written:
{files_content}

Write a precise technical handoff for the next agent. Include:
1. Every class and its public methods (with parameter types)
2. Every standalone function (params, return type)
3. Important constants/config values
4. What this code does NOT do (the next agent builds this)
5. Any assumptions the next agent must respect

Under 400 words. Plain markdown."""

def generate_handoff(dir_path: str, step: int, files_written: list) -> str:
    from .agents import call_ollama
    parts = []
    for fname in files_written:
        try:
            content = ws.read_file(dir_path, fname)
            parts.append(f'=== {fname} ===\n{content[:3000]}')
        except Exception:
            pass
    if not parts:
        return ''
    try:
        prompt = HANDOFF_PROMPT.format(files_content='\n\n'.join(parts))
        _emit('status', {'message': f'Generating handoff for step {step}...'})
        return call_ollama([{'role': 'user', 'content': prompt}], timeout=45)
    except Exception:
        return f'Step {step} wrote: {", ".join(files_written)}'

# ── Final review ───────────────────────────────────────────────────────────────
REVIEW_PROMPT = """You are a senior code reviewer. Multiple AI agents built this project.

Project: {project_name}
Files:
{files_content}

Review for:
1. Import errors — files importing non-existent modules
2. Interface mismatches — wrong parameter names/types
3. Logical gaps — something referenced but never implemented
4. Convention violations
5. Obvious runtime errors

Return JSON ONLY:
{{
  "status": "clean or issues_found",
  "issues": [
    {{
      "severity": "blocking or warning",
      "file": "filename",
      "description": "what is wrong",
      "suggestion": "how to fix it"
    }}
  ],
  "summary": "one paragraph overall assessment"
}}"""

def final_review(dir_path: str, project_name: str) -> dict:
    from .agents import call_ollama
    files = ws.list_files(dir_path)
    parts = []
    for fname in files[:8]:  # limit context
        try:
            content = ws.read_file(dir_path, fname)
            parts.append(f'===FILE: {fname}===\n{content[:2000]}\n===END===')
        except Exception:
            pass
    if not parts:
        return {'status': 'clean', 'issues': [], 'summary': 'No files to review.'}
    try:
        prompt = REVIEW_PROMPT.format(
            project_name=project_name,
            files_content='\n\n'.join(parts)
        )
        _emit('status', {'message': 'Running final review...'})
        resp = call_ollama([{'role': 'user', 'content': prompt}], timeout=60)
        d = parse_json_response(resp)
        return d or {'status': 'clean', 'issues': [], 'summary': resp[:500]}
    except Exception as e:
        return {'status': 'clean', 'issues': [], 'summary': f'Review skipped: {e}'}

# ── Main orchestration run ─────────────────────────────────────────────────────
class OrchestratorResult:
    def __init__(self):
        self.plan_data    = {}
        self.files_written= []
        self.review       = {}
        self.dir_path     = ''
        self.success      = False
        self.errors       = []

def run(request: str, dir_path: str, plan_override: str = None) -> OrchestratorResult:
    from .agents import get_plan
    result    = OrchestratorResult()
    result.dir_path = dir_path
    plan      = plan_override or get_plan()

    _emit('start', {'request': request[:100], 'plan': plan})
    print(f"\n  {bold('Fraude Orchestrator')} {GRY}({plan}){R}")
    print(f"  {dim(request[:80])}\n")

    # Step 1: Analyze
    plan_data = analyze_project(request)
    result.plan_data = plan_data
    project_name = plan_data.get('project_name', 'project')
    project_type = plan_data.get('project_type', 'layered')

    print(f"  {c('Plan:', ACC)} {project_type} — {len(plan_data.get('steps',[]))} steps")
    for s in plan_data.get('steps', []):
        files = ', '.join(s.get('output_files', []))
        print(f"  {GRY}  Step {s['step']}: [{s['agent']}] {s['role']} → {files}{R}")

    # Initialize workspace
    ws.init_workspace(dir_path, project_name, project_type)
    ws.update_manifest(dir_path, {'steps': [
        {**s, 'status': 'pending'} for s in plan_data.get('steps', [])
    ]})

    # Step 2: Contract (split projects)
    contract = {}
    if plan_data.get('contract_needed'):
        contract = generate_contract(request, plan_data)
        if contract:
            ws.write_contract(dir_path, contract)
            print(c('  ✓ Contract written', GRN))

    # Show preview and ask to confirm (CLI mode — web skips this)
    if _progress_cb is None:
        try:
            ans = input(f"\n  {YLW}Proceed with this plan? [Y/n]{R}: ").strip().lower()
            if ans not in ('', 'y', 'yes'):
                print(c('  Cancelled.', GRY))
                return result
        except (KeyboardInterrupt, EOFError):
            return result

    _emit('plan_confirmed', {'plan_data': plan_data})

    # Step 3: Dispatch agents
    steps     = plan_data.get('steps', [])
    handoff   = ''
    auto_fix_retries = 0

    for step in steps:
        step_num = step['step']

        # Update manifest status
        m = ws.get_manifest(dir_path)
        manifest_steps = m.get('steps', [])
        for ms in manifest_steps:
            if ms['step'] == step_num:
                ms['status'] = 'running'
        ws.update_manifest(dir_path, {'steps': manifest_steps})

        # Build prompt
        sys_prompt = build_agent_prompt(
            step, plan_data,
            handoff=handoff,
            contract=contract if project_type == 'split' else None
        )

        # Run agent
        raw_output = run_agent_step(step, sys_prompt, plan)

        if not raw_output:
            ws.log_step(dir_path, {
                'step': step_num, 'agent': step['agent'],
                'status': 'failed', 'files': []
            })
            for ms in manifest_steps:
                if ms['step'] == step_num:
                    ms['status'] = 'failed'
            ws.update_manifest(dir_path, {'steps': manifest_steps})
            result.errors.append(f'Step {step_num} ({step["agent"]}) failed')
            continue

        # Parse and write files
        file_blocks = parse_file_blocks(raw_output)
        files_this_step = []

        if not file_blocks:
            # Fallback: save raw output as a .py file
            fname = (step.get('output_files') or ['output.py'])[0]
            ws.write_file(dir_path, fname, raw_output, step['agent'], step_num)
            files_this_step.append(fname)
        else:
            for fname, content in file_blocks.items():
                ws.write_file(dir_path, fname, content, step['agent'], step_num)
                files_this_step.append(fname)
                print(f"  {c('  wrote:', GRN)} {fname}")

        result.files_written.extend(files_this_step)

        ws.log_step(dir_path, {
            'step': step_num, 'agent': step['agent'],
            'status': 'complete', 'files': files_this_step,
            'prompt_preview': sys_prompt[:500],
        })

        for ms in manifest_steps:
            if ms['step'] == step_num:
                ms['status'] = 'complete'
                ms['output_files'] = files_this_step
        ws.update_manifest(dir_path, {'steps': manifest_steps})
        _emit('files_written', {'step': step_num, 'files': files_this_step})

        # Step 4: Handoff (layered only)
        if project_type == 'layered' and step_num < len(steps):
            handoff = generate_handoff(dir_path, step_num, files_this_step)
            if handoff:
                ws.write_handoff(dir_path, step_num, handoff)

    # Step 5: Final review
    print(f"\n  {c('[reviewer]', ACC)} ", end='', flush=True)
    with Spinner('Ollama reviewing...'):
        review = final_review(dir_path, project_name)
    result.review = review

    blocking = [i for i in review.get('issues', []) if i.get('severity') == 'blocking']
    if blocking and auto_fix_retries < 2:
        print(c(f'  ⚠ {len(blocking)} blocking issue(s) — auto-fixing...', YLW))
        for issue in blocking[:2]:
            auto_fix_retries += 1
            fix_step = {
                'step': len(steps) + 1,
                'agent': 'groq',
                'role': 'Auto-fix',
                'task': f"Fix this issue in {issue['file']}: {issue['description']}\nSuggestion: {issue['suggestion']}\n\nCurrent file content:\n{ws.read_file(dir_path, issue['file'])[:3000]}",
                'output_files': [issue['file']],
            }
            fix_sys = build_agent_prompt(fix_step, plan_data)
            fix_out = run_agent_step(fix_step, fix_sys, plan)
            if fix_out:
                blocks = parse_file_blocks(fix_out)
                for fname, content in blocks.items():
                    ws.write_file(dir_path, fname, content, 'auto-fix', 99)
                    print(c(f'  ✓ Fixed {fname}', GRN))
    elif review.get('status') == 'clean':
        print(c('✓ Clean', GRN))
    else:
        warnings = [i for i in review.get('issues', []) if i.get('severity') == 'warning']
        print(c(f'✓ Done ({len(warnings)} warning(s))', YLW if warnings else GRN))

    ws.update_manifest(dir_path, {'status': 'complete'})
    result.success = True

    # Summary
    print(f"\n  {bold('Done!')} {c(str(len(result.files_written))+' files written', GRN)}")
    for f in result.files_written:
        print(f"  {GRY}  ·{R} {f}")
    if review.get('summary'):
        print(f"\n  {dim(review['summary'][:200])}")

    _emit('complete', {
        'files': result.files_written,
        'review': review,
        'dir_path': dir_path,
    })
    return result


# ── CyberSec Audit ─────────────────────────────────────────────────────────────
THREAT_PROMPT = """You are a cybersecurity threat modeler. Analyze this codebase.
Files:
{files}

Return JSON ONLY:
{{
  "attack_surfaces": [],
  "vulnerability_categories": [
    {{"category": "e.g. SQL Injection", "likelihood": "high|medium|low",
      "affected_files": [], "lines_of_interest": []}}
  ],
  "test_cases_to_run": [
    {{"test_id": "T01", "description": "what to test",
      "target_file": "filename", "input_to_try": "input",
      "expected_safe_behavior": "what should happen"}}
  ]
}}"""

LOGIC_REVIEW_PROMPT = """You are a security code auditor.
Files:
{files}

Threat Model:
{threat_model}

Return JSON ONLY:
{{
  "findings": [
    {{"test_id": "T01", "confirmed": true, "file": "filename",
      "location": "function name", "exploitability": "high|medium|low|none",
      "impact": "description", "code_snippet": "20 word description",
      "remediation": "specific fix"}}
  ]
}}"""

INPUT_TEST_PROMPT = """You are a penetration tester.
Confirmed Findings:
{findings}

Files:
{files}

Return JSON ONLY:
{{
  "tests": [
    {{"test_id": "T01", "payload": "exact input",
      "execution_trace": "step by step",
      "exploit_succeeds": true, "severity": "Critical|High|Medium|Low",
      "cvss_estimate": "7.5"}}
  ]
}}"""

AUDIT_REPORT_PROMPT = """You are a cybersecurity report writer. Synthesize these findings.
Threat Model: {threat_model}
Logic Review: {logic_review}
Input Tests: {input_tests}

Write a security audit report in markdown:
# Security Audit Report
## Executive Summary
## Critical Findings
## High Severity Findings
## Medium Severity Findings
## Low / Informational Findings
## Remediation Priority List
## What Was Tested
## What Was NOT Tested

For each finding: what it is, where it is, risk, specific fix. Be direct."""

def run_cybersec_audit(dir_path: str) -> str:
    from .agents import call_ollama, call_gemini, call_groq
    files = ws.list_files(dir_path)
    if not files:
        return 'No files to audit.'

    files_content = '\n\n'.join(
        f'=== {f} ===\n{ws.read_file(dir_path, f)[:2000]}'
        for f in files[:6]
    )

    print(f"\n  {bold('CyberSec Audit')} {GRY}— 4 agents{R}\n")

    # Step 1: Threat model (Ollama)
    print(f"  {c('[1/4]', ACC)} Threat modeling (Ollama)...", flush=True)
    try:
        with Spinner():
            threat_raw = call_ollama([{'role': 'user', 'content':
                THREAT_PROMPT.format(files=files_content)}], timeout=90)
        ws.write_audit(dir_path, 'threat_model.md', threat_raw)
        _emit('audit_step', {'step': 1, 'name': 'threat_model'})
        print(c('  ✓', GRN))
    except Exception as e:
        threat_raw = '{}'
        print(c(f'  ✗ {e}', RED))

    # Step 2: Logic review (Gemini)
    print(f"  {c('[2/4]', ACC)} Logic review (Gemini)...", flush=True)
    try:
        with Spinner():
            logic_raw = _gemini_direct(
                LOGIC_REVIEW_PROMPT.format(files=files_content, threat_model=threat_raw[:2000]),
                system='You are a security code auditor. Return JSON only.',
                timeout=60
            )
        ws.write_audit(dir_path, 'logic_review.md', logic_raw)
        _emit('audit_step', {'step': 2, 'name': 'logic_review'})
        print(c('  ✓', GRN))
    except Exception as e:
        logic_raw = '{"findings": []}'
        print(c(f'  ✗ {e} — falling back to Ollama', YLW))
        try:
            with Spinner():
                logic_raw = call_ollama([{'role': 'user', 'content':
                    LOGIC_REVIEW_PROMPT.format(files=files_content[:3000], threat_model=threat_raw[:1000])
                }], timeout=60)
        except Exception: pass

    # Step 3: Input testing (Groq) — only confirmed findings
    print(f"  {c('[3/4]', ACC)} Input testing (Groq)...", flush=True)
    try:
        logic_d = parse_json_response(logic_raw) or {}
        confirmed = [f for f in logic_d.get('findings', []) if f.get('confirmed')]
        with Spinner():
            test_raw = call_groq([{'role': 'user', 'content':
                INPUT_TEST_PROMPT.format(
                    findings=json.dumps(confirmed, indent=2),
                    files=files_content[:2000]
                )
            }], timeout=60)
        ws.write_audit(dir_path, 'input_test.md', test_raw)
        _emit('audit_step', {'step': 3, 'name': 'input_test'})
        print(c('  ✓', GRN))
    except Exception as e:
        test_raw = '{"tests": []}'
        print(c(f'  ✗ {e}', RED))

    # Step 4: Final report (Ollama)
    print(f"  {c('[4/4]', ACC)} Final report (Ollama)...", flush=True)
    try:
        with Spinner():
            report = call_ollama([{'role': 'user', 'content':
                AUDIT_REPORT_PROMPT.format(
                    threat_model=threat_raw[:2000],
                    logic_review=logic_raw[:2000],
                    input_tests=test_raw[:2000],
                )
            }], timeout=90)
        ws.write_audit(dir_path, 'final_report.md', report)
        _emit('audit_complete', {'report': report[:500]})
        print(c('  ✓ Report written to .fraude/audit/final_report.md', GRN))
        return report
    except Exception as e:
        print(c(f'  ✗ {e}', RED))
        return f'Audit failed at final report: {e}'
