import { useState, useEffect } from 'react';
import { PLANS } from '../constants.js';

export default function FraudeCode({ settings, currentPlan, onClose }) {
  const hasGroq   = !!settings.groqKey;
  const hasGemini = !!settings.geminiKey;
  const plan = currentPlan === 'max' ? 'max' : currentPlan === 'pro' ? 'pro' : 'free';

  const planLabel = { max:'Max — Oops 0.7 (3 agents)', pro:'Pro — Somenet 0.6 (2 agents)', free:'Free — HighKu 0.5' }[plan];

  const agentRows = plan === 'max' ? [
    ['Router',    'Local Ollama',   'Classifies task, keeps architecture private'],
    ['Coder',     'Gemini Flash',   'Generates clean, correct code'],
    ['Explainer', 'Groq Llama-3.3', 'Documents, explains, reviews output'],
  ] : plan === 'pro' ? [
    ['Router',    'Local Ollama',   'Classifies task'],
    ['Coder',     'Groq Llama-3.3', 'Generates code'],
    ['Explainer', 'Groq Llama-3.3', 'Documents and explains'],
  ] : [
    ['Assistant', 'Local Ollama',   'All tasks (slow)'],
  ];

  // Directory state
  const [codeDir, setCodeDir] = useState(() =>
    localStorage.getItem('fraudecode_dir') || ''
  );
  const [editingDir, setEditingDir] = useState(false);
  const [dirInput, setDirInput]     = useState(codeDir);
  const [installing, setInstalling] = useState(false);
  const [installDone, setInstallDone] = useState(false);
  const [installLog, setInstallLog] = useState('');

  const saveDir = () => {
    localStorage.setItem('fraudecode_dir', dirInput);
    setCodeDir(dirInput);
    setEditingDir(false);
  };

  const getInstallCommand = () => {
    const pkgs = 'requests google-generativeai groq colorama pyreadline3';
    const platform = (navigator.platform || '').toLowerCase();
    const isWin = platform.includes('win');
    return isWin ? `pip install ${pkgs}` : `python3 -m pip install ${pkgs}`;
  };

  const handleInstall = async () => {
    setInstalling(true);
    setInstallLog('');
    try {
      const res = await fetch('/api/terminal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: getInstallCommand() }),
      });
      const d = await res.json();
      setInstallLog((d.output || '') + (d.error ? '\n' + d.error : ''));
      setInstallDone(d.exitCode === 0);
    } catch (e) {
      setInstallLog(`Error: ${e.message}`);
    }
    setInstalling(false);
  };

  const [launching, setLaunching] = useState(false);
  const [launchMsg, setLaunchMsg] = useState('');

  const handleLaunch = async () => {
    setLaunching(true);
    setLaunchMsg('');
    try {
      const res = await fetch('/api/launch-terminal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dir: codeDir || null }),
      });
      const d = await res.json();
      if (d.ok) setLaunchMsg('✓ FraudeCode launched in a new terminal window.');
      else setLaunchMsg('⚠ Could not open terminal automatically. Launch manually: python fraudecode.py');
    } catch (e) {
      setLaunchMsg('⚠ Server error. Launch manually: python fraudecode.py');
    }
    setLaunching(false);
  };

  // CSS vars for theming
  const bg    = 'var(--bg)';
  const bg2   = 'var(--bg2)';
  const bg3   = 'var(--code-bg)';
  const bdr   = 'var(--border)';
  const bdrS  = 'var(--border-sub)';
  const txt   = 'var(--text)';
  const txt2  = 'var(--text2)';
  const txt3  = 'var(--text3)';
  const acc   = '#e8572a';   // FraudeCode brand orange
  const mono  = 'var(--font-mono)';
  const suc   = 'var(--success)';

  const Section = ({ title, children }) => (
    <div style={{ marginBottom: 22 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: txt3, textTransform: 'uppercase', letterSpacing: .8, marginBottom: 10 }}>{title}</div>
      {children}
    </div>
  );

  const ApiStatus = ({ label, ok, detail }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, marginBottom: 4 }}>
      <span style={{ color: ok ? suc : 'var(--danger)', width: 14 }}>{ok ? '✓' : '✗'}</span>
      <span style={{ color: ok ? txt : txt3, width: 56 }}>{label}</span>
      <span style={{ color: txt3, fontSize: 11 }}>{detail}</span>
    </div>
  );

  const Mono = ({ children }) => (
    <code style={{ fontFamily: mono, background: bg3, border: `1px solid ${bdr}`, borderRadius: 4, padding: '2px 6px', fontSize: 12, color: txt }}>{children}</code>
  );

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.4)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ background: bg, border: `1px solid ${bdr}`, borderRadius: 14, width: 'min(640px,96vw)', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 8px 40px rgba(0,0,0,.2)' }}>

        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: `1px solid ${bdrS}`, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontSize: 19, fontWeight: 700, color: acc, fontFamily: "'Georgia',serif", marginBottom: 3 }}>FraudeCode</div>
            <div style={{ fontSize: 12, color: txt2 }}>Multi-Agent Terminal Coding Tool</div>
          </div>
          <button onClick={onClose} style={{ color: txt2, background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, padding: 4, lineHeight: 1 }}>✕</button>
        </div>

        <div style={{ padding: '20px 24px' }}>

          {/* Plan badge */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: bg2, border: `1px solid ${bdr}`, borderRadius: 8, padding: '7px 14px', marginBottom: 22 }}>
            <span style={{ fontSize: 10, color: txt3, textTransform: 'uppercase', letterSpacing: .8 }}>Active plan</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: acc }}>{planLabel}</span>
          </div>

          {/* Agent table */}
          <Section title="Agent Pipeline">
            <div style={{ background: bg3, border: `1px solid ${bdrS}`, borderRadius: 8, overflow: 'hidden' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '90px 140px 1fr', background: bg2, padding: '7px 14px', fontSize: 11, color: txt3, textTransform: 'uppercase', letterSpacing: .5 }}>
                <div>Agent</div><div>Provider</div><div>Role</div>
              </div>
              {agentRows.map(([a, p, r], i) => (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '90px 140px 1fr', padding: '9px 14px', borderTop: `1px solid ${bdrS}`, fontSize: 13 }}>
                  <div style={{ color: acc, fontWeight: 600 }}>{a}</div>
                  <div style={{ color: txt2, fontFamily: mono, fontSize: 12 }}>{p}</div>
                  <div style={{ color: txt }}>{r}</div>
                </div>
              ))}
            </div>
          </Section>

          {/* API status */}
          <Section title="API Status">
            <ApiStatus label="Groq"   ok={hasGroq}   detail={hasGroq   ? settings.groqModel   || 'llama-3.3-70b-versatile' : 'Not set — add in Settings → Models'} />
            <ApiStatus label="Gemini" ok={hasGemini} detail={hasGemini ? settings.geminiModel || 'gemini-2.0-flash-lite'   : 'Not set — add in Settings → Models'} />
            <ApiStatus label="Ollama" ok={true}       detail={settings.ollamaUrl || 'http://localhost:11434'} />
          </Section>

          {/* FraudeCode directory */}
          <Section title="FraudeCode Location">
            <div style={{ background: bg2, border: `1px solid ${bdr}`, borderRadius: 8, padding: '12px 14px' }}>
              {editingDir ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <input value={dirInput} onChange={e => setDirInput(e.target.value)}
                    placeholder="e.g. C:\Users\you\Documents\fraude"
                    style={{ flex: 1, background: bg3, border: `1px solid ${bdr}`, borderRadius: 6, padding: '7px 10px', color: txt, fontSize: 13, fontFamily: mono, outline: 'none' }}
                    onFocus={e => e.target.style.borderColor = acc} onBlur={e => e.target.style.borderColor = bdr}
                    onKeyDown={e => e.key === 'Enter' && saveDir()} autoFocus />
                  <button onClick={saveDir}
                    style={{ background: acc, color: '#fff', border: 'none', borderRadius: 6, padding: '7px 14px', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>Save</button>
                  <button onClick={() => setEditingDir(false)}
                    style={{ background: 'none', border: `1px solid ${bdr}`, color: txt2, borderRadius: 6, padding: '7px 10px', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ flex: 1, fontSize: 13, color: codeDir ? txt : txt3, fontFamily: mono }}>
                    {codeDir || 'Not set — your fraude folder'}
                  </span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => { setDirInput(codeDir); setEditingDir(true); }}
                      style={{ background: 'none', border: `1px solid ${bdr}`, color: txt2, borderRadius: 5, padding: '4px 10px', fontSize: 12, cursor: 'pointer' }}
                      onMouseOver={e => e.currentTarget.style.borderColor = txt2}
                      onMouseOut={e => e.currentTarget.style.borderColor = bdr}>Edit</button>
                    <button onClick={async () => {
                        const res = await fetch('/api/browse-dir', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ start: codeDir || null }) });
                        const d = await res.json();
                        if (d.path) { setDirInput(d.path); localStorage.setItem('fraudecode_dir', d.path); setCodeDir(d.path); }
                      }}
                      style={{ background: 'none', border: `1px solid ${bdr}`, color: txt2, borderRadius: 5, padding: '4px 10px', fontSize: 12, cursor: 'pointer' }}
                      onMouseOver={e => e.currentTarget.style.borderColor = txt2}
                      onMouseOut={e => e.currentTarget.style.borderColor = bdr}>📂 Browse</button>
                  </div>
                </div>
              )}
              <div style={{ fontSize: 11, color: txt3, marginTop: 7, lineHeight: 1.5 }}>
                Set the folder where <Mono>fraudecode.py</Mono> is stored. Usually your <Mono>fraude</Mono> folder.
              </div>
            </div>
          </Section>

          {/* Install + Launch buttons */}
          <Section title="Setup">
            <div style={{ display: 'flex', gap: 10, marginBottom: installLog ? 12 : 0 }}>
              <button onClick={handleInstall} disabled={installing}
                style={{
                  flex: 1, padding: '11px', borderRadius: 8, border: `1px solid ${bdr}`, cursor: installing ? 'not-allowed' : 'pointer',
                  background: installing ? bg2 : bg3, color: installing ? txt3 : txt, fontSize: 13, fontWeight: 500,
                  transition: 'all .2s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                }}>
                {installing
                  ? <><span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', border: '2px solid var(--text3)', borderTopColor: acc, animation: 'spin 1s linear infinite' }} /> Installing…</>
                  : installDone ? '✓ Requirements installed' : '⬇ Install requirements'}
              </button>
              <button onClick={handleLaunch}
                style={{
                  flex: 1, padding: '11px', borderRadius: 8, border: 'none', cursor: 'pointer',
                  background: acc, color: '#fff', fontSize: 13, fontWeight: 600,
                  transition: 'opacity .2s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                }}
                onMouseOver={e => e.currentTarget.style.opacity = '.85'}
                onMouseOut={e => e.currentTarget.style.opacity = '1'}>
                ▶ Launch FraudeCode
              </button>
            </div>

            {installLog && (
              <div style={{ background: bg3, border: `1px solid ${bdrS}`, borderRadius: 7, padding: '10px 13px', maxHeight: 120, overflowY: 'auto', marginTop: 10 }}>
                <pre style={{ margin: 0, fontSize: 11, color: installDone ? 'var(--success)' : 'var(--danger)', fontFamily: mono, whiteSpace: 'pre-wrap' }}>
                  {installLog.trim()}
                </pre>
              </div>
            )}
            {launchMsg && (
              <div style={{ marginTop: 8, fontSize: 12, color: launchMsg.startsWith('✓') ? suc : 'var(--warning,#d29922)', padding: '6px 10px', background: bg3, borderRadius: 6, border: `1px solid ${bdrS}` }}>
                {launchMsg}
              </div>
            )}
          </Section>

          {/* Manual launch */}
          <Section title="Manual Launch">
            <div style={{ background: bg3, border: `1px solid ${bdrS}`, borderRadius: 8, padding: '12px 16px', fontFamily: mono, fontSize: 13, color: 'var(--success)' }}>
              cd {codeDir || '{your fraude folder}'}<br/>
              python fraudecode.py
            </div>
          </Section>

          {/* Requirements */}
          <Section title="Python Requirements">
            <div style={{ background: bg3, border: `1px solid ${bdrS}`, borderRadius: 8, padding: '12px 16px', fontFamily: mono, fontSize: 13, color: txt2 }}>
              pip install requests google-generativeai groq colorama pyreadline3
            </div>
            <div style={{ fontSize: 12, color: txt3, marginTop: 8, lineHeight: 1.6 }}>
              <span style={{ color: txt2, fontWeight: 500 }}>requests</span> — HTTP calls to Groq/Gemini/Ollama<br/>
              <span style={{ color: txt2, fontWeight: 500 }}>google-generativeai</span> — Gemini SDK<br/>
              <span style={{ color: txt2, fontWeight: 500 }}>groq</span> — Groq SDK (optional, uses urllib as fallback)<br/>
              <span style={{ color: txt2, fontWeight: 500 }}>colorama</span> — Windows terminal colours<br/>
              <span style={{ color: txt2, fontWeight: 500 }}>pyreadline3</span> — Tab completion on Windows
            </div>
          </Section>

          {/* Commands */}
          <Section title="Terminal Commands">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px' }}>
              {[
                ['/help', 'Show all commands'],
                ['/plan', 'Plan & API status'],
                ['/files', 'List workspace files'],
                ['/run [file]', 'Run a Python file'],
                ['/open <file>', 'View file with line numbers'],
                ['/edit <file>', 'Open in system editor'],
                ['/delete <file>', 'Delete with permission prompt'],
                ['/search <term>', 'Search inside all files'],
                ['/install <pkg>', 'pip install a package'],
                ['/history [n]', 'Show conversation history'],
                ['/save [name]', 'Save current chat'],
                ['/chats', 'Chat dashboard'],
                ['/newchat', 'Start fresh chat'],
                ['/clear', 'Clear screen + history'],
                ['/export <file>', 'Copy file to current dir'],
                ['/config', 'Show config values'],
              ].map(([cmd, desc]) => (
                <div key={cmd} style={{ display: 'flex', gap: 8, alignItems: 'baseline', padding: '3px 0' }}>
                  <span style={{ fontFamily: mono, fontSize: 11, color: acc, minWidth: 120, flexShrink: 0 }}>{cmd}</span>
                  <span style={{ fontSize: 12, color: txt3 }}>{desc}</span>
                </div>
              ))}
            </div>
          </Section>

          <div style={{ fontSize: 12, color: txt3, lineHeight: 1.7, marginTop: 4 }}>
            Files are saved to <Mono>fraude-code-memory/</Mono>. API keys sync automatically from Fraude web settings — no extra config needed if running from the same folder.
          </div>
        </div>
      </div>
    </div>
  );
}
