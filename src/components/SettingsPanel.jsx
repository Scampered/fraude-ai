import { useState, useEffect } from 'react';

const Field = ({ label, k, local, set, type = 'text', placeholder = '', note }) => (
  <div style={{ marginBottom: 14 }}>
    <label style={{ display: 'block', fontSize: 12, color: 'var(--text2)', fontWeight: 500, marginBottom: 5 }}>{label}</label>
    <input type={type} value={local[k] || ''} onChange={e => set(k, e.target.value)} placeholder={placeholder}
      style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 7, padding: '8px 12px', color: 'var(--text)', fontSize: 13, fontFamily: type === 'password' ? 'monospace' : 'inherit', outline: 'none', transition: 'border-color .15s' }}
      onFocus={e => e.target.style.borderColor = '#4A9EFF'} onBlur={e => e.target.style.borderColor = '#30363d'} />
    {note && <p style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4, lineHeight: 1.5 }}>{note}</p>}
  </div>
);

const Sec = ({ title, accent, children }) => (
  <div style={{ marginBottom: 20, paddingBottom: 20, borderBottom: '1px solid #21262d' }}>
    <div style={{ fontSize: 11, fontWeight: 600, color: accent, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 12 }}>{title}</div>
    {children}
  </div>
);

const TABS = ['General', 'Models', 'Connections'];

export default function SettingsPanel({ settings, onSave, onClose, inline }) {
  const [local, setLocal] = useState({ ...settings });
  const [showKeys, setShowKeys] = useState({});
  const toggleKeyVis = (field) => setShowKeys(p => ({...p, [field]: !p[field]}));
  const [saved, setSaved] = useState(false);
  const isDirty = JSON.stringify(local) !== JSON.stringify(settings);
  const [tab, setTab] = useState('Models');
  const [customSkills, setCustomSkills] = useState([]);
  const [newSkill, setNewSkill] = useState({ name: '', prompt: '', icon: '⚡' });
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState(null);

  const set = (k, v) => setLocal(p => ({ ...p, [k]: v }));

  useEffect(() => {
    fetch('/api/skills').then(r => r.json()).then(setCustomSkills).catch(() => {});
  }, []);

  const generateSkill = async () => {
    if (!newSkill.name || !newSkill.prompt) return;
    setGenerating(true);
    setGenResult(null);
    // Pick best available model
    const model = local.geminiKey ? 'oops' : local.groqKey ? 'somenet' : 'highku';
    const sysPrompt = `You are a skill generator. Given a skill name and description, output ONLY valid JSON with these exact fields:
{
  "prompt": "a system prompt that will be prepended to any user message when this skill is active, guiding the AI to behave appropriately for this skill",
  "imports": ["python_package1", "python_package2"],
  "slash": "slashcommandname"
}
No explanation, no markdown, just the JSON object.`;
    const userMsg = `Skill name: ${newSkill.name}\nDescription: ${newSkill.prompt}\nGenerate the skill configuration.`;
    try {
      const endpoint = model === 'oops' ? '/api/proxy/gemini' : model === 'somenet' ? '/api/proxy/groq' : '/api/proxy/ollama';
      const body = model === 'oops'
        ? { messages: [{ role: 'user', content: userMsg }], model: local.geminiModel || 'gemini-1.5-flash', apiKey: local.geminiKey }
        : model === 'somenet'
          ? { messages: [{ role: 'user', content: sysPrompt + '\n\n' + userMsg }], model: local.groqModel || 'llama3-8b-8192', apiKey: local.groqKey }
          : { messages: [{ role: 'system', content: sysPrompt }, { role: 'user', content: userMsg }], model: local.ollamaModel || 'llama3.2', baseUrl: local.ollamaUrl };
      if (model === 'oops') body.messages = [{ role: 'user', content: sysPrompt + '\n\n' + userMsg }];
      const res = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await res.json();
      const text = data.content || '';
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        setGenResult(parsed);
      }
    } catch (e) {
      setGenResult({ error: e.message });
    }
    setGenerating(false);
  };

  const saveSkill = async () => {
    if (!genResult || genResult.error) return;
    const skill = {
      id: newSkill.name.toLowerCase().replace(/\s+/g, '_'),
      name: newSkill.name, icon: newSkill.icon,
      prompt: genResult.prompt, imports: genResult.imports || [],
      slash: genResult.slash || newSkill.name.toLowerCase().replace(/\s+/g,''),
    };
    await fetch('/api/skills', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(skill) });
    setCustomSkills(prev => [...prev.filter(s => s.id !== skill.id), skill]);
    setNewSkill({ name: '', prompt: '', icon: '⚡' });
    setGenResult(null);
  };

  const deleteSkill = async (id) => {
    await fetch(`/api/skills/${id}`, { method: 'DELETE' });
    setCustomSkills(prev => prev.filter(s => s.id !== id));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: inline ? '100%' : '100vh', background: 'var(--bg)', position: inline ? 'relative' : 'fixed', inset: inline ? 'auto' : 0, zIndex: inline ? 'auto' : 200, overflow: 'hidden' }}>
      <div style={{ padding: '16px 26px', borderBottom: '1px solid var(--border-sub)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <h1 style={{ fontSize: 17, fontWeight: 600, color: 'var(--text)' }}>Settings</h1>
        <button onClick={() => { onSave(local); onClose(); }} style={{ color: 'var(--text2)', fontSize: 13, padding: '5px 12px', cursor: 'pointer', border: '1px solid var(--border)', borderRadius: 6, background: 'none', transition: 'all .15s' }}
          onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--text2)'; }}
          onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--border)'; }}>
          ✕ Close
        </button>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar nav */}
        <div style={{ width: 200, borderRight: '1px solid #21262d', padding: '16px 12px', flexShrink: 0 }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              style={{ display: 'block', width: '100%', padding: '8px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', textAlign: 'left', fontSize: 13, background: tab === t ? 'var(--bg-active)' : 'none', color: tab === t ? 'var(--text)' : 'var(--text2)', transition: 'all .12s', marginBottom: 1 }}
              onMouseOver={e => { if (tab !== t) e.currentTarget.style.background = '#161b22'; }}
              onMouseOut={e => { if (tab !== t) e.currentTarget.style.background = 'none'; }}>
              {t}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 32px', maxWidth: 600, WebkitOverflowScrolling: 'touch' }}>
          {tab === 'General' && (
            <>
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: .8, marginBottom: 12 }}>Appearance</div>
                <div style={{ display: 'flex', gap: 10 }}>
                  {['light', 'dark'].map(t => (
                    <button key={t} onClick={() => set('theme', t)}
                      style={{ flex: 1, padding: '10px', borderRadius: 8, cursor: 'pointer', textAlign: 'center', fontSize: 13,
                        background: local.theme === t ? 'var(--accent-dim)' : 'var(--bg2)',
                        border: `1px solid ${local.theme === t ? 'var(--accent)' : 'var(--border)'}`,
                        color: local.theme === t ? 'var(--accent)' : 'var(--text2)',
                        fontWeight: local.theme === t ? 500 : 400, transition: 'all .12s' }}>
                      {t === 'light' ? '☀ Light' : '☾ Dark'}
                    </button>
                  ))}
                </div>
              </div>
              <button onClick={() => { onSave(local); setSaved(true); setTimeout(()=>setSaved(false),2000); }}
                disabled={!isDirty && !saved}
                style={{ background: isDirty ? 'var(--accent)' : saved ? 'var(--success)' : 'var(--bg3)', color: isDirty || saved ? '#fff' : 'var(--text3)', border: 'none', borderRadius: 7, padding: '9px 22px', fontSize: 13, fontWeight: 500, cursor: isDirty ? 'pointer' : 'default', transition: 'all .2s' }}>
                {saved ? '✓ Saved' : 'Save'}
              </button>
            </>
          )}

          {tab === 'Models' && (
            <>
              <Sec title="HighKu — Local Ollama" accent="#a371f7">
                <Field label="Ollama URL" k="ollamaUrl" local={local} set={set} placeholder="http://localhost:11434" note="Default. Fraude auto-starts Ollama if installed." />
                <Field label="Model" k="ollamaModel" local={local} set={set} placeholder="llama3.2" note="Install with: ollama pull llama3.2" />
              </Sec>
              <Sec title="Somenet — Groq" accent="#3fb950">
                <Field label="API Key" k="groqKey" local={local} set={set} type="password" placeholder="gsk_..." note="Free key at console.groq.com" />
                <Field label="Model" k="groqModel" local={local} set={set} placeholder="llama3-8b-8192" />
              </Sec>
              <Sec title="Oops 6.7 — Gemini" accent="#4A9EFF">
                <Field label="API Key" k="geminiKey" local={local} set={set} type="password" placeholder="AIza..." note="Free key at aistudio.google.com" />
                <Field label="Model" k="geminiModel" local={local} set={set} placeholder="gemini-1.5-flash" />
              </Sec>
              <Sec title="AWARE — Group Node" accent="#d29922">
                <Field label="Base URL" k="awareUrl" local={local} set={set} placeholder="http://your-server:8000" note="Your group's AWARE node URL (OpenAI-compatible endpoint)." />
                <Field label="API Key" k="awareKey" local={local} set={set} type="password" placeholder="group-shared-key" note="Shared key from your AWARE group." />
                <Field label="Model" k="awareModel" local={local} set={set} placeholder="AWARE-I" note="Model name served by the AWARE node." />
              </Sec>
              <button onClick={() => { onSave(local); setSaved(true); setTimeout(()=>setSaved(false),2000); }}
                disabled={!isDirty && !saved}
                style={{ background: isDirty ? 'var(--accent)' : saved ? 'var(--success)' : 'var(--bg3)', color: isDirty || saved ? '#fff' : 'var(--text3)', border: 'none', borderRadius: 8, padding: '10px 24px', fontSize: 14, fontWeight: 500, cursor: isDirty ? 'pointer' : 'default', transition: 'all .2s' }}>
                {saved ? '✓ Saved' : 'Save changes'}
              </button>
            </>
          )}

          {tab === 'Connections' && (
            <>
              <div style={{ marginBottom: 24 }}>
                <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>Custom Skills</h2>
                <p style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 20, lineHeight: 1.5 }}>
                  Create skills that get activated with a slash command. The AI finds the right Python imports and builds the system prompt for you.
                </p>

                {/* Existing custom skills */}
                {customSkills.length > 0 && (
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 10 }}>Your skills</div>
                    {customSkills.map(skill => (
                      <div key={skill.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', background: 'var(--bg2)', border: '1px solid var(--border-sub)', borderRadius: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 18 }}>{skill.icon}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 14, color: 'var(--text)', fontWeight: 500 }}>{skill.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text3)', fontFamily: 'monospace' }}>/{skill.slash} · {skill.imports.join(', ') || 'no imports'}</div>
                        </div>
                        <button onClick={() => deleteSkill(skill.id)} style={{ color: 'var(--text3)', background: 'none', border: '1px solid var(--border)', borderRadius: 5, padding: '4px 10px', fontSize: 12, cursor: 'pointer' }}>Remove</button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Create new skill */}
                <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 14 }}>+ Add skill</div>
                  <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ display: 'block', fontSize: 12, color: 'var(--text2)', marginBottom: 5 }}>Skill name</label>
                      <input value={newSkill.name} onChange={e => setNewSkill(p => ({ ...p, name: e.target.value }))}
                        placeholder="e.g. Resume Writer"
                        style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 10px', color: 'var(--text)', fontSize: 13, outline: 'none' }}
                        onFocus={e => e.target.style.borderColor = '#4A9EFF'} onBlur={e => e.target.style.borderColor = '#30363d'} />
                    </div>
                    <div style={{ width: 80 }}>
                      <label style={{ display: 'block', fontSize: 12, color: 'var(--text2)', marginBottom: 5 }}>Icon</label>
                      <input value={newSkill.icon} onChange={e => setNewSkill(p => ({ ...p, icon: e.target.value }))}
                        placeholder="⚡"
                        style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 10px', color: 'var(--text)', fontSize: 16, outline: 'none', textAlign: 'center' }}
                        onFocus={e => e.target.style.borderColor = '#4A9EFF'} onBlur={e => e.target.style.borderColor = '#30363d'} />
                    </div>
                  </div>
                  <div style={{ marginBottom: 14 }}>
                    <label style={{ display: 'block', fontSize: 12, color: 'var(--text2)', marginBottom: 5 }}>What does this skill do?</label>
                    <textarea value={newSkill.prompt} onChange={e => setNewSkill(p => ({ ...p, prompt: e.target.value }))}
                      placeholder="e.g. Helps write professional resumes and cover letters in different formats"
                      rows={3}
                      style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 10px', color: 'var(--text)', fontSize: 13, outline: 'none', resize: 'none', fontFamily: 'inherit' }}
                      onFocus={e => e.target.style.borderColor = '#4A9EFF'} onBlur={e => e.target.style.borderColor = '#30363d'} />
                  </div>

                  {genResult && !genResult.error && (
                    <div style={{ background: 'var(--bg)', border: '1px solid var(--success)', borderRadius: 7, padding: '12px 14px', marginBottom: 14 }}>
                      <div style={{ fontSize: 11, color: 'var(--success)', fontWeight: 600, marginBottom: 6 }}>Generated skill config</div>
                      <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 4 }}>Slash: <code style={{ color: 'var(--accent)' }}>/{genResult.slash}</code></div>
                      <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 4 }}>Imports: {genResult.imports?.join(', ') || 'none'}</div>
                      <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.5 }}>Prompt: {genResult.prompt?.slice(0, 100)}…</div>
                    </div>
                  )}
                  {genResult?.error && (
                    <div style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 14 }}>Generation failed: {genResult.error}</div>
                  )}

                  <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={generateSkill} disabled={generating || !newSkill.name || !newSkill.prompt}
                      style={{ flex: 1, background: generating ? '#21262d' : '#4A9EFF', color: generating ? '#484f58' : '#fff', border: 'none', borderRadius: 7, padding: '9px', fontSize: 13, fontWeight: 500, cursor: generating ? 'not-allowed' : 'pointer' }}>
                      {generating ? 'Generating...' : '✨ Generate'}
                    </button>
                    {genResult && !genResult.error && (
                      <button onClick={saveSkill}
                        style={{ background: 'var(--bg2)', color: 'var(--success)', border: '1px solid var(--success)', borderRadius: 7, padding: '9px 16px', fontSize: 13, cursor: 'pointer' }}>
                        Save skill
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
