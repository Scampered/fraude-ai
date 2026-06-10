import { useState, useRef, useEffect, useCallback } from 'react';
import FraudeLogo from './components/FraudeLogo.jsx';
import MessageRenderer from './components/MessageRenderer.jsx';
import StepsDisplay from './components/StepsDisplay.jsx';
import ErrorBanner from './components/ErrorBanner.jsx';
import BillingModal from './components/BillingModal.jsx';
import SettingsPanel from './components/SettingsPanel.jsx';
import SkillsPanel from './components/SkillsPanel.jsx';
import ArtifactPanel from './components/ArtifactPanel.jsx';
import MemoryPanel from './components/MemoryPanel.jsx';
import ProjectsPanel from './components/ProjectsPanel.jsx';
import ProjectsPage from './components/ProjectsPage.jsx';
import AutomationsPage from './components/AutomationsPage.jsx';
import QuizModal from './components/QuizModal.jsx';
import FraudeCode from './components/FraudeCode.jsx';
import { MODELS, PLANS, BUILTIN_SKILLS, STEPS, FRAUDE_SELF_KNOWLEDGE, randFrom, sleep, detectAutoSkills } from './constants.js';
import { callModel } from './hooks/useApi.js';

const DEFAULT_SETTINGS = {
  groqKey:'', geminiKey:'',
  ollamaUrl:'http://localhost:11434', ollamaModel:'llama3.2',
  groqModel:'llama-3.3-70b-versatile', geminiModel:'gemini-2.0-flash-lite',
  awareKey:'', awareUrl:'', awareModel:'AWARE-I',
  theme:'light',
};
const DEFAULT_USER = { name:'User' };

function load(key, def) { try { return { ...def, ...JSON.parse(localStorage.getItem(key)||'{}') }; } catch { return def; } }
const loadSettings = () => load('fraude_settings', DEFAULT_SETTINGS);
const loadUser = () => load('fraude_user', DEFAULT_USER);

function getCurrentPlan(s) {
  if (s.geminiKey || s.awareKey) return 'max';
  if (s.groqKey) return 'pro';
  return 'free';
}
function getAvailableModels(s) {
  const plan = getCurrentPlan(s);
  return (PLANS[plan] || PLANS.free).models;
}

function detectIntent(text) {
  if (/(make|create|generate|write).*(\\.py|python script|code|script|function|class)/i.test(text)) return 'code';
  if (/(make|create|generate|write).*(pdf|document|report)/i.test(text)) return 'pdf';
  if (/(write|draft|compose).*(essay|article|blog)/i.test(text)) return 'essay';
  if (/(analyse|analyze|plot|chart|graph|visuali)/i.test(text)) return 'data';
  if (/(remember|note that|don.t forget)/i.test(text)) return 'memory';
  return 'general';
}

function extractCode(text) {
  const m = text.match(/```(\w+)\n([\s\S]*?)```/);
  return m ? { lang: m[1], code: m[2].trim() } : null;
}
function titleFrom(msgs) {
  const first = msgs.find(m => m.role === 'user');
  if (!first) return 'New chat';
  const t = (first.displayContent||first.content).trim();
  return t.slice(0,50)+(t.length>50?'…':'');
}
function initials(name) { return name.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2); }

const Icon = ({ path, size=16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d={path} />
  </svg>
);
const P = {
  newChat:  'M12 5v14M5 12h14',
  search:   'M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z',
  chats:    'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
  skills:   'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
  memory:   'M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2v-4M9 21H5a2 2 0 0 1-2-2v-4m0 0h18',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm6.93-3c0-.28-.02-.55-.05-.81l1.76-1.38-1.68-2.9-2.06.83a6.97 6.97 0 0 0-1.4-.81L15.26 5h-3.46l-.24 2.13c-.51.2-.98.47-1.4.81L8.1 7.11 6.42 10l1.76 1.38c-.03.26-.05.53-.05.81s.02.55.05.81L6.42 14.19l1.68 2.9 2.06-.83c.43.34.9.61 1.4.81L11.8 19h3.46l.24-2.13c.51-.2.98-.47 1.4-.81l2.06.83 1.68-2.9-1.76-1.38c.03-.26.05-.53.05-.81z',
  upgrade:  'M13 10V3L4 14h7v7l9-11h-7z',
  attach:   'M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48',
  chevDown: 'M6 9l6 6 6-6',
  send:     'M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z',
  copy:     'M8 17.929H6c-1.105 0-2-.912-2-2.036V5.036C4 3.91 4.895 3 6 3h8c1.105 0 2 .911 2 2.036v1.866m-6 .17h8c1.105 0 2 .91 2 2.035v10.857C20 21.09 19.105 22 18 22h-8c-1.105 0-2-.911-2-2.036V9.107c0-1.124.895-2.036 2-2.036z',
  refresh:  'M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15',
  plus:     'M12 5v14M5 12h14',
  thumbUp:  'M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z',
  thumbDn:  'M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z',
};

// ─── Nav item ─────────────────────────────────────────────────────────────────
function NavItem({ icon, label, active, onClick, badge, collapsed }) {
  const [hov, setHov] = useState(false);
  return (
    <button onClick={onClick} onMouseOver={()=>setHov(true)} onMouseOut={()=>setHov(false)}
      title={collapsed ? label : undefined}
      style={{ display:'flex', alignItems:'center', gap:10, width:'100%', padding:'7px 10px', borderRadius:7, border:'none',
        justifyContent: collapsed ? 'center' : 'flex-start',
        background: active ? 'var(--bg-active)' : hov ? 'var(--bg-hover)' : 'none',
        color: active ? 'var(--text)' : 'var(--text2)', cursor:'pointer', textAlign:'left', fontSize:14, fontWeight: active?500:400, transition:'all .12s', position:'relative', flexShrink:0 }}>
      <span style={{ color: active ? 'var(--text)' : hov ? 'var(--text)' : 'var(--text2)', transition:'color .12s', flexShrink:0 }}>{icon}</span>
      {!collapsed && <span style={{ flex:1, whiteSpace:'nowrap', overflow:'hidden' }}>{label}</span>}
      {!collapsed && badge && <span style={{ fontSize:10, background:'var(--accent-dim)', color:'var(--accent)', border:'1px solid var(--accent)', borderRadius:4, padding:'1px 5px' }}>{badge}</span>}
      {collapsed && badge && <span style={{ position:'absolute', top:5, right:5, width:6, height:6, borderRadius:'50%', background:'var(--accent)' }} />}
    </button>
  );
}

// ─── Model selector ───────────────────────────────────────────────────────────
function ModelSelector({ model, setModel, availableModels, onOpenBilling }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const cur = MODELS[model];
  useEffect(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  return (
    <div ref={ref} style={{ position:'relative' }}>
      <button onClick={()=>setOpen(o=>!o)}
        style={{ display:'flex', alignItems:'center', gap:5, padding:'5px 10px', background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:7, color:'var(--text)', cursor:'pointer', fontSize:13, fontWeight:500, whiteSpace:'nowrap' }}>
        <span style={{ color:cur.color, fontSize:8 }}>●</span>{cur.label}<Icon path={P.chevDown} size={12} />
      </button>
      {open && (
        <div className="anim-fadeup" style={{ position:'absolute', bottom:'100%', left:0, marginBottom:5, background:'var(--bg)', border:'1px solid var(--border)', borderRadius:9, minWidth:200, zIndex:50, boxShadow:'0 6px 24px rgba(0,0,0,.12)', padding:'5px' }}>
          {Object.values(MODELS).map(m => {
            const locked = !availableModels.includes(m.id);
            return (
              <button key={m.id} onClick={() => { if (locked) onOpenBilling(); else {
              setModel(m.id);
              setOpen(false);
              if (m.id === 'highku') {
                setCompacting(true);
                // Check ollama is up before allowing chat
                fetch('/api/proxy/ollama', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ messages:[{role:'user',content:'hi'}], model: 'llama3.2', baseUrl:'http://localhost:11434' }) })
                  .catch(()=>{}).finally(()=>setCompacting(false));
                // Fallback clear after 8s
                setTimeout(()=>setCompacting(false), 8000);
              }
            } }}
                style={{ display:'flex', alignItems:'center', gap:9, width:'100%', padding:'8px 10px', borderRadius:6, border:'none', cursor:'pointer',
                  background: model===m.id ? 'var(--bg-active)' : 'none', color: locked ? 'var(--text3)' : 'var(--text)', fontSize:13, textAlign:'left', transition:'background .1s' }}
                onMouseOver={e=>{ if(model!==m.id) e.currentTarget.style.background='var(--bg-hover)'; }}
                onMouseOut={e=>{ if(model!==m.id) e.currentTarget.style.background='none'; }}>
                <span style={{ color:locked?'var(--text3)':m.color, fontSize:8 }}>●</span>
                <div style={{ flex:1 }}>
                  <div style={{display:'flex',alignItems:'center',gap:5}}>{m.label}{m.version&&<span style={{fontSize:10,color:'var(--text3)',background:'var(--bg3)',border:'1px solid var(--border)',borderRadius:3,padding:'0 4px'}}>{m.version}</span>}</div>
                  <div style={{ fontSize:11, color:'var(--text3)' }}>{m.sublabel}</div>
                </div>
                {model===m.id && <span style={{ fontSize:11, color:'var(--accent)' }}>✓</span>}
                {locked && <span style={{ fontSize:10, color:'var(--text3)', border:'1px solid var(--border)', borderRadius:3, padding:'1px 5px' }}>Upgrade</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Account popover ──────────────────────────────────────────────────────────
function AccountPopover({ user, setUser, plan, onSettings, onBilling, onClose }) {
  const [edit, setEdit] = useState(false);
  const [name, setName] = useState(user.name);
  const save = () => {
    const u = { ...user, name:name||'User' };
    setUser(u); try { localStorage.setItem('fraude_user', JSON.stringify(u)); } catch {}
    setEdit(false);
  };
  return (
    <div className="anim-fadeup" style={{ position:'absolute', bottom:'100%', left:0, right:0, marginBottom:5, background:'var(--bg)', border:'1px solid var(--border)', borderRadius:9, zIndex:100, boxShadow:'0 6px 24px rgba(0,0,0,.12)', overflow:'hidden' }}>
      <div style={{ padding:'12px 14px', borderBottom:'1px solid var(--border-sub)' }}>
        <div style={{ display:'flex', alignItems:'center', gap:9 }}>
          <div style={{ width:30, height:30, borderRadius:'50%', background:'var(--accent-dim)', border:'1px solid var(--accent)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:11, fontWeight:600, color:'var(--accent)', flexShrink:0 }}>
            {initials(user.name)}
          </div>
          <div style={{ flex:1 }}>
            {edit
              ? <div style={{ display:'flex', gap:5 }}>
                  <input value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')save();if(e.key==='Escape')setEdit(false);}} autoFocus
                    style={{ flex:1, background:'var(--bg2)', border:'1px solid var(--accent)', borderRadius:5, padding:'3px 7px', color:'var(--text)', fontSize:12, outline:'none' }} />
                  <button onClick={save} style={{ background:'var(--accent)', color:'#fff', border:'none', borderRadius:5, padding:'3px 7px', fontSize:11, cursor:'pointer' }}>✓</button>
                </div>
              : <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                  <span style={{ fontSize:13, fontWeight:500, color:'var(--text)' }}>{user.name}</span>
                  <button onClick={()=>setEdit(true)} style={{ fontSize:10, color:'var(--text3)', background:'none', border:'none', cursor:'pointer' }}>Edit</button>
                </div>
            }
            <div style={{ fontSize:11, color:'var(--accent)', marginTop:1 }}>{PLANS[plan].label} plan</div>
          </div>
        </div>
      </div>
      <div style={{ padding:'4px' }}>
        {[
          { label:'Settings', icon:<Icon path={P.settings} size={14}/>, action:()=>{onSettings();onClose();} },
          { label:'Upgrade plan', icon:<Icon path={P.upgrade} size={14}/>, action:()=>{onBilling();onClose();}, accent:true },
        ].map(item => (
          <button key={item.label} onClick={item.action}
            style={{ display:'flex', alignItems:'center', gap:9, width:'100%', padding:'8px 10px', borderRadius:6, border:'none', cursor:'pointer', background:'none', color: item.accent?'var(--accent)':'var(--text)', fontSize:13, textAlign:'left' }}
            onMouseOver={e=>e.currentTarget.style.background='var(--bg-hover)'} onMouseOut={e=>e.currentTarget.style.background='none'}>
            {item.icon} {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Slash menu ───────────────────────────────────────────────────────────────
function SlashMenu({ query, skills, onSelect }) {
  const q = query.toLowerCase();
  const matches = skills.filter(s => (s.slash||'').startsWith(q) || s.name.toLowerCase().startsWith(q) || s.name.toLowerCase().replace(/\s+/g,'').startsWith(q));
  if (!matches.length) return null;
  return (
    <div style={{ position:'absolute', bottom:'100%', left:0, marginBottom:5, background:'var(--bg)', border:'1px solid var(--border)', borderRadius:8, minWidth:210, zIndex:60, boxShadow:'0 6px 20px rgba(0,0,0,.12)', padding:'4px' }}>
      {matches.map(s => (
        <button key={s.id} onClick={()=>onSelect(s)}
          style={{ display:'flex', alignItems:'center', gap:10, width:'100%', padding:'8px 10px', borderRadius:6, border:'none', cursor:'pointer', background:'none', color:'var(--text)', fontSize:13, textAlign:'left' }}
          onMouseOver={e=>e.currentTarget.style.background='var(--bg-hover)'} onMouseOut={e=>e.currentTarget.style.background='none'}>
          <span style={{ fontSize:15, color:'var(--text)' }}>{s.icon}</span>
          <div>
            <div style={{ color:'var(--text)' }}>{s.name}</div>
            <div style={{ fontSize:11, color:'var(--text3)', fontFamily:'var(--font-mono)' }}>/{s.slash}</div>
          </div>
        </button>
      ))}
    </div>
  );
}

// ─── Message actions ──────────────────────────────────────────────────────────
function MsgActions({ onCopy, onRerun }) {
  const [copied, setCopied] = useState(false);
  const [thumbed, setThumbed] = useState(null);
  const btn = (content, action, active, title) => (
    <button onClick={action} title={title}
      style={{ display:'flex', alignItems:'center', gap:3, fontSize:11, color: active?'var(--accent)':'var(--text3)', background:'none', border:'none', cursor:'pointer', padding:'3px 6px', borderRadius:5, transition:'color .12s' }}
      onMouseOver={e=>e.currentTarget.style.color='var(--text2)'} onMouseOut={e=>e.currentTarget.style.color=active?'var(--accent)':'var(--text3)'}>
      {content}
    </button>
  );
  return (
    <div style={{ display:'flex', gap:1, marginTop:6 }}>
      {btn(<><Icon path={P.copy} size={11}/> {copied?'Copied':'Copy'}</>, ()=>{onCopy();setCopied(true);setTimeout(()=>setCopied(false),2000);}, copied, 'Copy')}
      {btn(<><Icon path={P.thumbUp} size={11}/></>, ()=>setThumbed('up'), thumbed==='up', 'Good response')}
      {btn(<><Icon path={P.thumbDn} size={11}/></>, ()=>setThumbed('down'), thumbed==='down', 'Bad response')}
      {btn(<><Icon path={P.refresh} size={11}/> Retry</>, onRerun, false, 'Retry')}
    </div>
  );
}

// ─── Search modal ─────────────────────────────────────────────────────────────
function SearchModal({ conversations, onSelect, onClose }) {
  const [q, setQ] = useState('');
  const results = conversations.filter(c => c.title.toLowerCase().includes(q.toLowerCase()));
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.3)', zIndex:200, display:'flex', alignItems:'flex-start', justifyContent:'center', paddingTop:72 }} onClick={onClose}>
      <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:11, width:'min(500px,90vw)', maxHeight:'65vh', display:'flex', flexDirection:'column', overflow:'hidden', boxShadow:'0 8px 30px rgba(0,0,0,.15)' }} onClick={e=>e.stopPropagation()}>
        <div style={{ padding:'11px 15px', borderBottom:'1px solid var(--border-sub)', display:'flex', alignItems:'center', gap:9 }}>
          <Icon path={P.search} size={15} /><input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="Search conversations..."
            style={{ flex:1, background:'none', border:'none', outline:'none', color:'var(--text)', fontSize:14 }} />
          <button onClick={onClose} style={{ color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:12 }}>Esc</button>
        </div>
        <div style={{ overflowY:'auto', padding:'5px' }}>
          {results.length===0 ? <p style={{ fontSize:13, color:'var(--text3)', padding:'12px 14px' }}>No results.</p>
            : results.map(c => (
              <button key={c.id} onClick={()=>{onSelect(c.id);onClose();}}
                style={{ display:'block', width:'100%', padding:'9px 13px', borderRadius:6, border:'none', cursor:'pointer', background:'none', color:'var(--text)', fontSize:13, textAlign:'left' }}
                onMouseOver={e=>e.currentTarget.style.background='var(--bg-hover)'} onMouseOut={e=>e.currentTarget.style.background='none'}>
                {c.title}
              </button>
            ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [model, setModel] = useState('oops');
  const [loading, setLoading] = useState(false);
  const [steps, setSteps] = useState([]);
  const [settings, setSettings] = useState(loadSettings);
  const [user, setUser] = useState(loadUser);
  const [activeError, setActiveError] = useState(null);
  const [artifact, setArtifact] = useState(null);
  const [pdfPreview, setPdfPreview] = useState(null);
  const [chatSkills, setChatSkills] = useState({});
  const activeSkills = activeConvId ? (chatSkills[activeConvId] || []) : [];
  const activeSkill = activeSkills[0] || null;
  const setActiveSkill = (skill) => {
    const cid = activeConvId; if (!cid) return;
    setChatSkills(p => ({ ...p, [cid]: skill ? [skill] : [] }));
  };
  const toggleSkill = (skill) => {
    const cid = activeConvId; if (!cid) return;
    setChatSkills(p => {
      const cur = p[cid] || [];
      const exists = cur.find(sk => sk.id === skill.id);
      return { ...p, [cid]: exists ? cur.filter(sk => sk.id !== skill.id) : [...cur, skill] };
    });
  };
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [memoryNotes, setMemoryNotes] = useState([]);
  const [memRefresh, setMemRefresh] = useState(0);
  const [projects, setProjects] = useState([]);
  const [showProjects, setShowProjects] = useState(false);
  const [rateToast, setRateToast] = useState(null);
  const [updateInfo, setUpdateInfo] = useState(null);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showArtifacts, setShowArtifacts] = useState(false);
  const [showQuiz, setShowQuiz] = useState(false);
  const [showFraudeCode, setShowFraudeCode] = useState(false);
  const [suggestionChips] = useState(() => {
    const POOLS = {
      Code:    ['Code me a program that...','Write a script that...','Build a function that...','Make a tool that...','Create an automation that...','Write a bot that...'],
      Write:   ['Write me an essay about...','Write a letter on...','Draft a blog post about...','Write a short story about...','Compose an email for...','Write a report on...'],
      Create:  ['Create a PDF that explains...','Make a spreadsheet for...','Generate a document about...','Build a presentation on...','Create a chart showing...','Make a template for...'],
      Analyse: ['Analyse this data for me...','Summarise this file...','Find patterns in...','Compare these two things:...','Break down the key points of...','Evaluate and critique...'],
    };
    return Object.entries(POOLS).map(([label,pool])=>({
      label, prompt: pool[Math.floor(Math.random()*pool.length)],
      icon: {Code:'⌥',Write:'✍',Create:'⬡',Analyse:'∿'}[label],
    }));
  });
  const [compacting, setCompacting] = useState(false); // HighKu loading screen
  const [profiles, setProfiles] = useState([]);
  const [webSearch, setWebSearch] = useState(false);
  const [allSkills, setAllSkills] = useState(BUILTIN_SKILLS);
  const [slashQuery, setSlashQuery] = useState(null);
  const [mainView, setMainView] = useState('chat'); // 'chat' | 'settings'
  const [showBilling, setShowBilling] = useState(false);
  const [showSkills, setShowSkills] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [pendingCmd, setPendingCmd] = useState(null); // {command, resolve, reject}
  const [terminalLog, setTerminalLog] = useState([]); // {cmd, output, error, exitCode}

  const bottomRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const accountRef = useRef(null);
  const attachRef = useRef(null);

  const currentPlan = getCurrentPlan(settings);
  const availableModels = getAvailableModels(settings);
  const activeModelDef = MODELS[model];

  // Apply theme
  useEffect(() => {
    document.body.className = settings.theme === 'dark' ? 'dark' : '';
  }, [settings.theme]);

  useEffect(() => {
    fetch('/api/conversations').then(r=>r.json()).then(setConversations).catch(()=>{});
    fetch('/api/projects').then(r=>r.json()).then(setProjects).catch(()=>{});
    fetch('/api/update-check').then(r=>r.json()).then(d=>{ if(d.hasUpdate) setUpdateInfo(d); }).catch(()=>{});
    fetch('/api/profiles').then(r=>r.json()).then(d=>setProfiles(d.profiles||[])).catch(()=>{});
    // Sync saved settings to server so fraude_code.py has API keys
    const savedSettings = loadSettings();
    fetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(savedSettings) }).catch(()=>{});
    fetch('/api/skills').then(r=>r.json()).then(cs => {
      const norm = cs.map(sk => ({ ...sk, slash: sk.slash||sk.name.toLowerCase().replace(/\s+/g,''), icon: sk.icon||'⚡' }));
      setAllSkills([...BUILTIN_SKILLS, ...norm]);
    }).catch(()=>{});
  }, []);

  // WebSocket sync
  useEffect(() => {
    let ws;
    const connect = () => {
      try {
        ws = new WebSocket('ws://localhost:3001');
        ws.onerror = () => {}; // silent
        ws.onmessage = e => {
          try {
            const msg = JSON.parse(e.data);
            if (msg.type==='conv_created') setConversations(p=>{ if(p.some(c=>c.id===msg.conv.id)) return p; return [msg.conv,...p]; });
            if (msg.type==='conv_updated') setConversations(p=>p.map(c=>c.id===msg.conv.id?msg.conv:c).sort((a,b)=>b.updatedAt-a.updatedAt));
            if (msg.type==='conv_deleted') setConversations(p=>p.filter(c=>c.id!==msg.id));
          } catch {}
        };
        ws.onerror=()=>{}; ws.onclose=()=>setTimeout(connect,3000);
      } catch {}
    };
    connect();
    return () => { try { ws?.close(); } catch {} };
  }, []);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }); }, [messages, steps]);

  useEffect(() => {
    if (!activeConvId) { setMessages([]); setMemoryNotes([]); setInput(''); setUploadedFiles([]); return; }
    fetch(`/api/conversations/${activeConvId}/messages`).then(r=>r.json()).then(setMessages).catch(()=>{});
    fetch(`/api/conversations/${activeConvId}/memory`).then(r=>r.json()).then(setMemoryNotes).catch(()=>{});
    const draft = loadDraft(activeConvId);
    if (draft) {
      setInput(draft.input || '');
      setUploadedFiles(draft.uploadedFiles || []);
    } else {
      setInput('');
      setUploadedFiles([]);
    }
    setArtifact(null); setSteps([]);
  }, [activeConvId]);

  useEffect(() => {
    const av = getAvailableModels(settings);
    if (!av.includes(model)) setModel(av[av.length-1]);
  }, [settings]);

  useEffect(() => {
    const h = e => {
      if (accountRef.current && !accountRef.current.contains(e.target)) setShowAccount(false);
      if (attachRef.current && !attachRef.current.contains(e.target)) setShowAttachMenu(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const saveSettings = s => {
    setSettings(s);
    try { localStorage.setItem('fraude_settings', JSON.stringify(s)); } catch {}
    // Also persist to server so fraude_code.py can read API keys
    fetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(s) }).catch(()=>{});
  };

  const draftKey = id => `fraude_draft_${id}`;
  const loadDraft = id => {
    if (!id) return null;
    try { return JSON.parse(localStorage.getItem(draftKey(id)) || 'null'); } catch { return null; }
  };
  const saveDraft = (id, draft) => {
    if (!id) return;
    try { localStorage.setItem(draftKey(id), JSON.stringify(draft)); } catch {}
  };
  const clearDraft = id => {
    if (!id) return;
    try { localStorage.removeItem(draftKey(id)); } catch {}
  };

  const createConv = async (mdl) => {
    const res = await fetch('/api/conversations', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ title:'New chat', model:mdl||model }) });
    const conv = await res.json();
    setConversations(p=>[conv,...p]);
    setActiveConvId(conv.id);
    setMessages([]); setMemoryNotes([]); setArtifact(null); setUploadedFiles([]); setActiveSkill(null);
    return conv.id;
  };

  const saveMessages = async (cid, msgs) => {
    const title = titleFrom(msgs);
    await fetch(`/api/conversations/${cid}/messages`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ messages:msgs, title }) });
    setConversations(p=>p.map(c=>c.id===cid?{...c,title,messageCount:msgs.length,updatedAt:Date.now()}:c).sort((a,b)=>b.updatedAt-a.updatedAt));
  };

  const deleteConv = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this conversation?')) return;
    await fetch(`/api/conversations/${id}`, { method:'DELETE' });
    setConversations(p=>p.filter(c=>c.id!==id));
    if (activeConvId===id) { setActiveConvId(null); setMessages([]); }
  };

  const handleFileUpload = async file => {
    let cid = activeConvId;
    if (!cid) cid = await createConv();
    const fd = new FormData(); fd.append('file', file);
    const res = await fetch(`/api/conversations/${cid}/upload`, { method:'POST', body:fd });
    const data = await res.json();
    if (data.ok) {
      setUploadedFiles(p=>[...p, { ...data, mimeType: file.type || 'application/octet-stream' }]);
      setMemRefresh(x=>x+1);
    }
  };

  const addStep = useCallback(text => {
    setSteps(p=>[...p.map(s=>s.active?{...s,active:false,done:true}:s),{text,active:true,done:false}]);
  }, []);
  const finishSteps = useCallback(() => setSteps(p=>p.map(s=>({...s,active:false,done:true}))), []);

  const saveToMemory = async (cid, code, lang, skill) => {
    const ext={python:'py',javascript:'js',js:'js',html:'html',css:'css',sql:'sql',bash:'sh'}[lang]||'txt';
    const filename = `${skill?.id||'output'}_${Date.now()}.${ext}`;
    const res = await fetch(`/api/conversations/${cid}/files`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ filename, content:code, type:lang }) });
    const data = await res.json();
    setMemRefresh(x=>x+1);
    return { filename, savedPath: data.path };
  };

  // Run terminal command with user permission
  const runWithPermission = useCallback((command) => {
    return new Promise((resolve, reject) => {
      setPendingCmd({ command, resolve, reject });
    });
  }, []);

  // Run Python code and return output string
  const runPython = async (code, cid) => {
    const res = await fetch('/api/run', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ code, convId:cid }) });
    return await res.json();
  };

  // Fetch titles/snippets of other conversations for cross-chat context
  const getCrossContext = async (text) => {
    const lower = text.toLowerCase();
    const contextKeywords = ['other chat','previous chat','last time','earlier','we discussed','you mentioned','from before','remember when','last conversation'];
    if (!contextKeywords.some(k => lower.includes(k))) return '';
    try {
      const convos = await fetch('/api/conversations').then(r=>r.json());
      const others = convos.filter(c => c.id !== activeConvId).slice(0, 5);
      if (!others.length) return '';
      const snippets = await Promise.all(others.map(async c => {
        try {
          const msgs = await fetch(`/api/conversations/${c.id}/messages`).then(r=>r.json());
          const last = msgs.filter(m=>m.role==='assistant').slice(-1)[0];
          return `[Chat: "${c.title}"]\n${last?.content?.slice(0,300)||'(no content)'}`;
        } catch { return ''; }
      }));
      return '\n\n[Context from other conversations for reference:]\n' + snippets.filter(Boolean).join('\n\n');
    } catch { return ''; }
  };

  const handleInputChange = e => {
    const val = e.target.value;
    setInput(val);
    const m = val.match(/(?:^|\s)\/(\w*)$/);
    setSlashQuery(m ? m[1] : null);
  };

  const handlePaste = async e => {
    const items = Array.from(e.clipboardData?.items || []);
    const imageItems = items.filter(item => item.type.startsWith('image/'));
    if (!imageItems.length) return;
    e.preventDefault();
    for (const item of imageItems) {
      const file = item.getAsFile();
      if (file) await handleFileUpload(file);
    }
  };

  useEffect(() => {
    if (!activeConvId) return;
    saveDraft(activeConvId, { input, uploadedFiles });
  }, [activeConvId, input, uploadedFiles]);

  const applySlashSkill = skill => {
    setActiveSkill(skill);
    setInput(p => p.replace(/\/\w*$/, '').trim());
    setSlashQuery(null);
    textareaRef.current?.focus();
  };

  const doSend = async (textOverride, messagesOverride) => {
    const text = (textOverride || input).trim();
    if ((!text && uploadedFiles.length === 0) || loading) return;
    if (!textOverride) setInput('');
    setSteps([]); setArtifact(null); setSlashQuery(null);

    let cid = activeConvId;
    if (!cid) cid = await createConv();

    const intent = detectIntent(text);
    const isPdf = intent==='pdf' || activeSkill?.id==='pdf';
    const isCode = intent==='code' || activeSkill?.id==='code';
    const hasImageAttachments = uploadedFiles.some(f => ['.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg'].includes((f.ext||'').toLowerCase()));
    const imageAttachmentInstruction = hasImageAttachments
      ? 'IMPORTANT: The user has attached image files. Analyze the images and answer in plain text. Do NOT write code or scripts unless the user explicitly asks for code to process the images.'
      : '';
    // Auto-inject PDF skill system prompt even without explicit skill selection
    const autoSkills = activeSkills.length === 0 ? detectAutoSkills(text, allSkills) : [];
    const allActiveSkills = [...activeSkills, ...autoSkills];
    const pdfSkill = allActiveSkills.find(s=>s.id==='pdf') || (isPdf ? { id:'pdf', name:'PDF Maker', icon:'⬡', imports:['fpdf2'], prompt:'PDF creation — use fpdf2 or reportlab, save to output.pdf.' } : null);
    const effectiveSkill = pdfSkill || allActiveSkills[0] || null;

    // Check for empty uploaded files
    const emptyFiles = uploadedFiles.filter(f => f.content !== null && f.content !== undefined && f.content.trim().length === 0);

    let userContent = text;
    const origin = window.location?.origin || '';
    if (hasImageAttachments) {
      userContent = '[Attached image(s) are included for analysis. Do not provide code unless explicitly requested.]\n\n' + userContent;
    }
    if (uploadedFiles.length > 0) {
      userContent += uploadedFiles.map(f => {
        const isImage = ['.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg'].includes((f.ext||'').toLowerCase());
        if (f.content !== null && f.content !== undefined && f.content.trim().length === 0)
          return `\n\n[File: ${f.originalname} — WARNING: this file appears to be empty]`;
        if (f.content) return `\n\n[File: ${f.originalname}]\n\`\`\`\n${f.content.slice(0,4000)}\n\`\`\``;
        if (isImage) return `\n\n[Image: ${f.originalname}]\nView image at: ${origin}${f.url}`;
        return `\n\n[File: ${f.originalname} — binary]`;
      }).join('');
    }
    if (webSearch) userContent += '\n\n[Hint: If this question benefits from current or factual information, note that you should search the web.]';

    // Cross-chat context
    const crossCtx = await getCrossContext(text);
    if (crossCtx) userContent += crossCtx;

    const baseMessages = messagesOverride || messages;
    const attachments = uploadedFiles.map(f => ({
      originalname: f.originalname,
      filename: f.filename,
      url: f.url,
      ext: f.ext,
      mimeType: f.mimeType,
      size: f.size,
    }));
    const userMsg = { role:'user', content:userContent, displayContent:text, files:attachments.map(f=>f.originalname), attachments };
    const newMessages = [...baseMessages, userMsg];
    setMessages(newMessages);
    setUploadedFiles([]);
    setLoading(true);

    // System prompt with critical thinking
    const sys = [
      FRAUDE_SELF_KNOWLEDGE,
      `Currently active model: ${MODELS[model]?.label} ${MODELS[model]?.version} (${MODELS[model]?.sublabel})`,
      'Be genuinely helpful and produce correct, complete, working output.',
      hasImageAttachments ? imageAttachmentInstruction : '',
      'Critical thinking rules you MUST follow:',
      '- If an uploaded file appears empty or has no meaningful content, tell the user clearly before proceeding.',
      '- If code you generate has a logical error or will likely fail, point it out.',
      '- If the user\'s request is ambiguous, state your interpretation before answering.',
      '- If you reference something from a previous message that doesn\'t exist in context, say so.',
      '- When writing Python code, always produce complete, runnable code with a main() function.',
      // Use effectiveSkill for PDF context
      isPdf ? `IMPORTANT: You MUST generate a PDF using Python. Write COMPLETE, RUNNABLE Python code that:
1. Uses reportlab (preferred) OR fpdf2 — always add "from reportlab.lib.pagesizes import letter; from reportlab.pdfgen import canvas" or "from fpdf import FPDF"
2. Creates a VISUALLY APPEALING PDF with proper fonts, headers, sections, spacing
3. Saves the PDF to a file named output.pdf in the current directory
4. Includes a main() function called at the bottom
The code will be auto-executed. If a module is missing it will be auto-installed. Do NOT use pandoc.` : '',
      memoryNotes.length>0 ? `Memory notes:\n${memoryNotes.map((n,i)=>`${i+1}. ${n}`).join('\n')}` : '',
      ...allActiveSkills.filter(sk=>!isPdf||sk.id!=='pdf').map(sk=>`Active skill: ${sk.name}\n${sk.prompt}${sk.imports?.length?`\nRequired imports: ${sk.imports.join(', ')}`:''}`),
      '',
      emptyFiles.length>0 ? `Note: The following uploaded files appear to be empty: ${emptyFiles.map(f=>f.originalname).join(', ')}. Alert the user about this.` : '',
    ].filter(Boolean).join('\n\n');

    const apiMsgs = [{ role:'system', content:sys }, ...newMessages.map(m=>({ role:m.role, content:m.content }))];

    try {
      addStep(randFrom(STEPS.think));
      if (uploadedFiles.length>0) { await sleep(300); addStep(randFrom(STEPS.read)); }
      if (memoryNotes.length>0 && uploadedFiles.length===0) { await sleep(200); addStep(randFrom(STEPS.memory)); }
      const [dMin,dMax] = activeModelDef.delay;
      if (model==='highku') await sleep(dMin + Math.random()*(dMax-dMin)*.5);
      if (!['general','memory'].includes(intent)) { await sleep(280); addStep(randFrom(['code','pdf','data'].includes(intent)?STEPS.code:STEPS.plan)); }
      if (model==='highku') await sleep((dMax-dMin)*.4); else await sleep(350);
      addStep(randFrom(STEPS.write));

      const response = await callModel(model, apiMsgs, settings);

      if (intent==='memory') {
        const note = text.replace(/remember (that )?/i,'').replace(/note that /i,'').trim();
        if (note) {
          const updated = [...memoryNotes, note];
          await fetch(`/api/conversations/${cid}/memory`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ memories:updated }) });
          setMemoryNotes(updated);
        }
      }

      const codeMatch = extractCode(response);
      let artifactObj = null;
      const shouldArtifact = codeMatch && (['code','pdf','data'].includes(intent) || activeSkill?.imports?.length>0 || isPdf);

      if (shouldArtifact) {
        addStep(randFrom(STEPS.file));
        await sleep(220);
        const { filename, savedPath } = await saveToMemory(cid, codeMatch.code, codeMatch.lang, effectiveSkill || activeSkill);
        artifactObj = { title:filename, content:codeMatch.code, lang:codeMatch.lang, filename, savedPath, type:'code' };

        if (isPdf && ['python','py'].includes(codeMatch.lang)) {
          addStep('Running PDF generation...');
          await sleep(200);
          const runRes = await runPython(codeMatch.code, cid);
          if (runRes.exitCode === 0) {
            addStep('PDF generated ✓');
            try {
              const copyRes = await fetch(`/api/conversations/${cid}/pdf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sourcePyFile: artifactObj.filename }),
              });
              const copyData = await copyRes.json();
              if (copyData.ok && copyData.pdfUrl) {
                artifactObj = {
                  ...artifactObj,
                  type: 'pdf',
                  pdfUrl: copyData.pdfUrl,
                  pdfFilename: copyData.filename,
                  savedPath: copyData.pdfUrl,
                };
                setPdfPreview(artifactObj);
              }
            } catch (_) {}
          } else {
            artifactObj = { ...artifactObj, runError: runRes.error };
          }
        }
      }

      finishSteps();
      const aMsg = { role:'assistant', content:response, model, artifact: artifactObj };
      const finalMsgs = [...newMessages, aMsg];
      setMessages(finalMsgs);
      await saveMessages(cid, finalMsgs);
      clearDraft(cid);
      setMemRefresh(x=>x+1);
    } catch (err) {
      finishSteps();
      const fraude = err.fraude || { title:'Something went wrong', body:err.message, detail:String(err.stack||err), code:'ERR' };
      if (fraude.code === 'RATE' || fraude.code === 'QUOTA') {
        setRateToast(fraude);
        setTimeout(() => setRateToast(null), fraude.clearAfter || 20000);
      } else {
        setActiveError(fraude);
      }
      const errMsg = { role:'assistant', content:`**${fraude.title}**\n\n${fraude.body}`, model, error:true };
      const finalMsgs = [...newMessages, errMsg];
      setMessages(finalMsgs);
      await saveMessages(cid, finalMsgs);
    } finally {
      setLoading(false); setSteps([]);
    }
  };

  const handleSend = () => {
    // If message mentions clone and no clone skill active, trigger quiz
    const t = input.trim().toLowerCase();
    if (/\bclone\b|personality clone|write like|sound like/i.test(t) && !activeSkills.some(s=>s.id==='clone')) {
      setShowQuiz(true);
      return;
    }
    doSend();
  };
  const handleKeyDown = e => {
    if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
    if (e.key==='Escape') setSlashQuery(null);
  };
  const handleRerun = i => {
    const prev = messages.slice(0, i);
    const userMsg = messages[i-1];
    if (!userMsg || userMsg.role!=='user') return;
    doSend(userMsg.displayContent||userMsg.content, prev);
  };

  // ── Sidebar styles shared
  const SB = 'var(--sidebar-bg)';

  return (
    <div className="app-layout" style={{ height:'100vh', display:'flex', overflow:'hidden', background:'var(--bg)' }}
      onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();Array.from(e.dataTransfer.files).forEach(handleFileUpload);}}>
      <ErrorBanner error={activeError} onDismiss={()=>setActiveError(null)} />

      {/* ── Sidebar ── */}
      <div className="sidebar" style={{ width:sidebarCollapsed?52:256, background:SB, borderRight:'1px solid var(--border-sub)', display:'flex', flexDirection:'column', flexShrink:0, transition:'width .2s ease', overflow:'hidden' }}>
        <div style={{ padding:'8px 8px 6px', display:'flex', alignItems:'center', gap:6, flexShrink:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, flex:1, minWidth:0, cursor:'pointer', overflow:'hidden' }}
            onClick={()=>{ setActiveConvId(null); setMessages([]); setMainView('chat'); }}>
            <FraudeLogo size={22} style={{ flexShrink:0 }} />
            <span className="fraude-logo-text" style={{ color:'var(--text)', opacity:sidebarCollapsed?0:1, transition:'opacity .15s', whiteSpace:'nowrap', overflow:'hidden' }}>Fraude</span>
          </div>
          <button onClick={()=>setSidebarCollapsed(o=>!o)}
            style={{ flexShrink:0, background:'none', border:'none', cursor:'pointer', color:'var(--text3)', padding:'3px 5px', borderRadius:5, fontSize:16, lineHeight:1, transition:'color .12s' }}
            onMouseOver={e=>e.currentTarget.style.color='var(--text)'} onMouseOut={e=>e.currentTarget.style.color='var(--text3)'}
            title={sidebarCollapsed?'Expand':'Collapse'}>
            {sidebarCollapsed ? '›' : '‹'}
          </button>
        </div>
        <div style={{ padding:'2px 4px', display:'flex', flexDirection:'column', gap:1 }}>
          <NavItem collapsed={sidebarCollapsed} icon={<Icon path={P.newChat} size={15}/>} label="New chat" onClick={()=>{setActiveConvId(null);setMessages([]);setMainView('chat');}} />
          <NavItem collapsed={sidebarCollapsed} icon={<Icon path={P.search} size={15}/>} label="Search" onClick={()=>setShowSearch(true)} />
          <NavItem collapsed={sidebarCollapsed} icon={<Icon path={P.chats} size={15}/>} label="Chats" active={mainView==='chat'} onClick={()=>setMainView('chat')} />
          <NavItem collapsed={sidebarCollapsed} icon={<Icon path="M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7zM8 11h8M8 15h5" size={15}/>} label="Projects" active={mainView==='projects'} onClick={()=>setMainView('projects')} />
          <NavItem collapsed={sidebarCollapsed} icon={<Icon path="M8 3H4a1 1 0 0 0-1 1v4m5-5h8a1 1 0 0 1 1 1v4M8 3v18m0 0h8a1 1 0 0 0 1-1V8M8 21H4a1 1 0 0 1-1-1V8m0 0h18" size={15}/>} label="Code" badge={currentPlan==='free'?'Pro':null} onClick={()=>{if(currentPlan==='free')setShowBilling(true);else setShowFraudeCode(true);}} />
          <NavItem collapsed={sidebarCollapsed} icon={<Icon path={P.skills} size={15}/>} label="Skills" onClick={()=>setShowSkills(true)} badge={activeSkills.length>0?String(activeSkills.length):null} />
          <NavItem collapsed={sidebarCollapsed} icon={<Icon path="M13 10V3L4 14h7v7l9-11h-7z" size={15}/>} label="Automations" active={mainView==='automations'} onClick={()=>{setMainView('automations');setSidebarCollapsed(true);}} />
          <NavItem collapsed={sidebarCollapsed} icon={<Icon path="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" size={15}/>} label="Artifacts" onClick={()=>setShowArtifacts(true)} />
        </div>

        {/* Recent chats */}
        {!sidebarCollapsed && <div className="sidebar-convlist" style={{ flex:1, overflowY:'auto', padding:'6px 8px' }}>
          {conversations.length>0 && <div style={{ fontSize:11, fontWeight:600, color:'var(--text3)', textTransform:'uppercase', letterSpacing:.8, padding:'5px 3px 3px', marginBottom:1 }}>Recent</div>}
          {[...new Map(conversations.map(c=>[c.id,c])).values()].map(conv => {
            const isActive = conv.id===activeConvId;
            return (
              <div key={conv.id} style={{ position:'relative', marginBottom:1 }}
                onMouseOver={e=>{const b=e.currentTarget.querySelector('.db');if(b)b.style.opacity='1';}}
                onMouseOut={e=>{const b=e.currentTarget.querySelector('.db');if(b)b.style.opacity='0';}}>
                <button onClick={()=>{setActiveConvId(conv.id);setMainView('chat');}}
                  style={{ display:'block', width:'100%', padding:'6px 24px 6px 10px', borderRadius:6, border:'none', cursor:'pointer', textAlign:'left',
                    background: isActive?'var(--bg-active)':'none', color: isActive?'var(--text)':'var(--text2)',
                    fontSize:13, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', transition:'all .12s' }}
                  onMouseOver={e=>{if(!isActive){e.currentTarget.style.background='var(--bg-hover)';e.currentTarget.style.color='var(--text)';}}}
                  onMouseOut={e=>{if(!isActive){e.currentTarget.style.background='none';e.currentTarget.style.color='var(--text2)';}}}>{conv.title}</button>
                <button className="db" onClick={e=>deleteConv(conv.id,e)}
                  style={{ position:'absolute', right:4, top:'50%', transform:'translateY(-50%)', background:'none', border:'none', color:'var(--text3)', cursor:'pointer', fontSize:12, padding:'2px 4px', borderRadius:3, opacity:0, transition:'opacity .12s' }}>✕</button>
              </div>
            );
          })}
        </div>

        } {/* end sidebar-convlist */}
        {/* Account */}
        <div className="sidebar-account" style={{ padding:'7px 8px 10px', borderTop:'1px solid var(--border-sub)', position:'relative' }} ref={accountRef}>
          {showAccount && <AccountPopover user={user} setUser={setUser} plan={currentPlan} onSettings={()=>setMainView('settings')} onBilling={()=>setShowBilling(true)} onClose={()=>setShowAccount(false)} />}
          <button onClick={()=>setShowAccount(o=>!o)}
            style={{ display:'flex', alignItems:'center', gap:9, width:'100%', padding:'7px 8px', borderRadius:7, border:'none', cursor:'pointer', background:showAccount?'var(--bg-active)':'none', transition:'background .12s', textAlign:'left' }}
            onMouseOver={e=>{if(!showAccount)e.currentTarget.style.background='var(--bg-hover)';}} onMouseOut={e=>{if(!showAccount)e.currentTarget.style.background='none';}}>
            <div style={{ width:26, height:26, borderRadius:'50%', background:'var(--accent-dim)', border:'1px solid var(--accent)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:10, fontWeight:600, color:'var(--accent)', flexShrink:0 }}>
              {initials(user.name)}
            </div>
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{ fontSize:13, fontWeight:500, color:'var(--text)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{user.name}</div>
              <div style={{ fontSize:11, color:'var(--text3)' }}>{PLANS[currentPlan]?.label || currentPlan} plan</div>
            </div>
          </button>
        </div>
      </div>

      {/* ── Main area ── */}
      <div className="main-chat" style={{ flex:1, display:'flex', flexDirection:'column', minWidth:0, position:'relative' }}>
        {/* Mobile top bar */}
        <div className="mobile-topbar">
          <button onClick={()=>setMobileDrawerOpen(o=>!o)}
            style={{ color:'var(--text2)', background:'none', border:'none', cursor:'pointer', fontSize:20, padding:4, display:'flex', alignItems:'center' }}>☰</button>
          <span className="fraude-logo-text" style={{ color:'var(--text)', fontSize:16 }}>Fraude</span>
          <button onClick={()=>setShowAccount(o=>!o)}
            style={{ width:28, height:28, borderRadius:'50%', background:'var(--accent-dim)', border:'1px solid var(--accent)', color:'var(--accent)', fontSize:10, fontWeight:600, cursor:'pointer' }}>
            {initials(user.name)}
          </button>
        </div>
        {/* HighKu compacting overlay */}
        {compacting && (
          <div style={{ position:'absolute', inset:0, background:'var(--bg)', zIndex:10, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:16 }}>
            <span className="spin" style={{ width:28, height:28, borderRadius:'50%', border:'3px solid var(--border)', borderTopColor:'var(--accent)', display:'block' }}/>
            <div style={{ fontSize:14, color:'var(--text2)', fontFamily:'var(--font-ui)' }}>Compacting our conversation…</div>
            <div style={{ fontSize:12, color:'var(--text3)' }}>Loading HighKu locally</div>
          </div>
        )}
        {mainView==='projects' ? (
          <ProjectsPage projects={projects} conversations={conversations} activeConvId={activeConvId}
            onRefresh={()=>fetch('/api/projects').then(r=>r.json()).then(setProjects)}
            onOpenConv={(id)=>{ if(id){ setActiveConvId(id); } setMainView('chat'); }} />
        ) : mainView==='automations' ? (
          <AutomationsPage collapsed={sidebarCollapsed} onToggleSidebar={()=>setSidebarCollapsed(o=>!o)} />
        ) : mainView==='settings' ? (
          <SettingsPanel settings={settings} onSave={saveSettings} onClose={()=>setMainView('chat')} inline />
        ) : (
          <>
            {/* Messages */}
            <div style={{ flex:1, overflowY:'auto' }}>
              {messages.length===0 ? (
                <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', minHeight:'100%', padding:40 }}>
                  <FraudeLogo size={48} />
                  <h1 style={{ fontSize:22, fontWeight:600, color:'var(--text)', marginTop:16, marginBottom:7, textAlign:'center', fontFamily:'var(--font-serif)' }}>How can I help you today?</h1>
                  <p style={{ fontSize:13, color:'var(--text3)', marginBottom:28 }}>Fraude is ready. Results may vary.</p>
                  <div className="suggestion-chips">
                    {suggestionChips.map(item=>(
                      <div key={item.label} className="chip-category"
                        onClick={()=>{setInput(item.prompt);textareaRef.current?.focus();}}>
                        <span className="chip-icon">{item.icon}</span>
                        <span className="chip-label">{item.label}</span>
                      </div>
                    ))}
                    <div className="chip-category" onClick={()=>setShowQuiz(true)}>
                      <span className="chip-icon">🎭</span>
                      <span className="chip-label">Clone</span>
                    </div>
                  </div>
                </div>
              ) : (<>
                <div style={{ maxWidth:740, margin:'0 auto', padding:'24px 22px' }}>
                  {messages.map((msg,i) => (
                    <div key={i} className="anim-fadeup" style={{ marginBottom:22 }}>
                      {msg.role==='user' ? (
                        <div style={{ display:'flex', justifyContent:'flex-end' }}>
                          <div style={{ maxWidth:'72%', background:'var(--msg-user-bg)', border:'1px solid var(--border-sub)', borderRadius:'14px 3px 14px 14px', padding:'11px 15px', fontSize:14, color:'var(--text)', lineHeight:1.65, fontFamily:'var(--font-ui)' }}>
                            {msg.attachments?.length>0 && (
                              <div style={{ marginBottom:7, display:'flex', gap:6, flexWrap:'wrap' }}>
                                {msg.attachments.map((f,fi) => {
                                  const isImage = ['.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg'].includes((f.ext||'').toLowerCase());
                                  return isImage ? (
                                    <a key={fi} href={f.url} target="_blank" rel="noreferrer" style={{ display:'inline-block', border:'1px solid var(--border)', borderRadius:10, overflow:'hidden', width:120, height:90, background:'var(--bg3)' }}>
                                      <img src={f.url} alt={f.originalname} style={{ width:'100%', height:'100%', objectFit:'cover' }} />
                                    </a>
                                  ) : (
                                    <a key={fi} href={f.url} target="_blank" rel="noreferrer" style={{ fontSize:11, color:'var(--text2)', background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:4, padding:'5px 8px', fontFamily:'var(--font-mono)', textDecoration:'none' }}>
                                      📎 {f.originalname}
                                    </a>
                                  );
                                })}
                              </div>
                            )}
                            <span style={{ whiteSpace:'pre-wrap' }}>{msg.displayContent||msg.content}</span>
                          </div>
                        </div>
                      ) : (
                        <div style={{ display:'flex', gap:11, alignItems:'flex-start' }}>
                          <FraudeLogo size={20} />
                          <div style={{ flex:1, minWidth:0 }}>
                            <div style={{ fontSize:11, fontWeight:600, color:MODELS[msg.model]?.color||'var(--text3)', marginBottom:5, fontFamily:'var(--font-ui)', textTransform:'uppercase', letterSpacing:.5, display:'flex', alignItems:'center', gap:6 }}>
                            {MODELS[msg.model]?.label||'Fraude'}
                            {MODELS[msg.model]?.version && <span style={{fontSize:10,fontWeight:400,color:'var(--text3)',textTransform:'none',letterSpacing:0,background:'var(--bg3)',border:'1px solid var(--border)',borderRadius:4,padding:'0px 5px'}}>{MODELS[msg.model].version}</span>}
                          </div>
                            <MessageRenderer content={msg.content} convId={activeConvId} />
                            {msg.artifact && msg.artifact.type === 'code' && (
                              <button onClick={() => setArtifact(msg.artifact)}
                                style={{ marginTop:10, fontSize:12, color:'var(--accent)', background:'none', border:'1px solid var(--accent)', borderRadius:6, padding:'6px 10px', cursor:'pointer' }}>
                                View generated code
                              </button>
                            )}
                            {msg.artifact && msg.artifact.type === 'pdf' && (
                              <button onClick={() => setPdfPreview(msg.artifact)}
                                style={{ marginTop:10, fontSize:12, color:'var(--accent)', background:'none', border:'1px solid var(--accent)', borderRadius:6, padding:'6px 10px', cursor:'pointer' }}>
                                Preview generated PDF
                              </button>
                            )}
                            {!msg.error && <MsgActions onCopy={()=>navigator.clipboard.writeText(msg.content)} onRerun={()=>handleRerun(i)} />}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                  {loading && steps.length>0 && (
                    <div className="anim-fadeup" style={{ display:'flex', gap:11, marginBottom:22 }}>
                      <FraudeLogo size={20} />
                      <div>
                        <div style={{ fontSize:11, fontWeight:600, color:activeModelDef.color, marginBottom:7, fontFamily:'var(--font-ui)', textTransform:'uppercase', letterSpacing:.5 }}>{activeModelDef.label}</div>
                        <StepsDisplay steps={steps} />
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
                {pdfPreview && (
                  <div className="input-area" style={{ padding:'0 14px 16px', flexShrink:0 }}>
              {/* Rate limit toast — Claude style, above input */}
              {rateToast && (
                <div style={{
                  marginBottom:8, background:'var(--bg3)', border:'1px solid var(--border)',
                  borderRadius:'10px 10px 0 0', padding:'10px 16px',
                  display:'flex', justifyContent:'space-between', alignItems:'center',
                  fontSize:13, color:'var(--text2)',
                }}>
                  <span>{rateToast.title} — {rateToast.body}</span>
                  <button onClick={()=>setRateToast(null)} style={{ color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:15, padding:'0 2px' }}>✕</button>
                </div>
              )}
                    <div style={{ maxWidth:740, margin:'0 auto', border:'1px solid var(--border)', borderRadius:14, overflow:'hidden', background:'var(--bg2)' }}>
                      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', gap:10, padding:'12px 14px', background:'var(--bg3)' }}>
                        <div>
                          <div style={{ fontSize:13, fontWeight:600, color:'var(--text)' }}>{pdfPreview.pdfFilename || 'output.pdf'}</div>
                          <div style={{ fontSize:11, color:'var(--text3)' }}>PDF preview</div>
                        </div>
                        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                          <button onClick={() => window.open(pdfPreview.pdfUrl, '_blank')}
                            style={{ fontSize:12, color:'var(--accent)', background:'none', border:'1px solid var(--accent)', borderRadius:6, padding:'6px 12px', cursor:'pointer' }}>Open</button>
                          <button onClick={() => setPdfPreview(null)}
                            style={{ fontSize:12, color:'var(--text3)', background:'none', border:'1px solid var(--border)', borderRadius:6, padding:'6px 12px', cursor:'pointer' }}>Close</button>
                        </div>
                      </div>
                      <iframe src={pdfPreview.pdfUrl} title="PDF preview" style={{ width:'100%', height:420, border:'none', background:'#fff' }} />
                    </div>
                  </div>
                )}
              </>)}
            </div>

            {/* Input */}
            <div className="input-area" style={{ padding:'0 14px 16px', flexShrink:0 }}>
              {/* Rate limit toast — Claude style, above input */}
              {rateToast && (
                <div style={{
                  marginBottom:8, background:'var(--bg3)', border:'1px solid var(--border)',
                  borderRadius:'10px 10px 0 0', padding:'10px 16px',
                  display:'flex', justifyContent:'space-between', alignItems:'center',
                  fontSize:13, color:'var(--text2)',
                }}>
                  <span>{rateToast.title} — {rateToast.body}</span>
                  <button onClick={()=>setRateToast(null)} style={{ color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:15, padding:'0 2px' }}>✕</button>
                </div>
              )}
              <div style={{ maxWidth:740, margin:'0 auto' }}>
                {uploadedFiles.length>0 && (
                  <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:7 }}>
                    {uploadedFiles.map((f,i)=>(
                      <div key={i} style={{ display:'flex', alignItems:'center', gap:6, background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:9, padding:'6px 8px' }}>
                        {['.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg'].includes((f.ext||'').toLowerCase()) ? (
                          <img src={f.url} alt={f.originalname} style={{ width:48, height:40, objectFit:'cover', borderRadius:7, border:'1px solid var(--border-sub)' }} />
                        ) : (
                          <span style={{ fontSize:14 }}>📎</span>
                        )}
                        <div style={{ display:'flex', flexDirection:'column', minWidth:0 }}>
                          <span style={{ fontSize:11, color:'var(--text)', fontFamily:'var(--font-mono)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:170 }}>{f.originalname}</span>
                          <span style={{ fontSize:10, color:'var(--text3)' }}>{Math.round((f.size||0)/1024)} KB</span>
                        </div>
                        <button onClick={()=>setUploadedFiles(p=>p.filter((_,j)=>j!==i))} style={{ color:'var(--text3)', fontSize:11, padding:0 }}>✕</button>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ position:'relative' }}>
                  {slashQuery!==null && <SlashMenu query={slashQuery} skills={allSkills} onSelect={applySlashSkill} />}
                  <div style={{ background:'var(--input-bg)', border:'1px solid var(--border)', borderRadius:11, transition:'border-color .15s' }}
                    onFocusCapture={e=>e.currentTarget.style.borderColor='var(--accent)'}
                    onBlurCapture={e=>e.currentTarget.style.borderColor='var(--border)'}>
                    <textarea ref={textareaRef} value={input} onChange={handleInputChange} onPaste={handlePaste} onKeyDown={handleKeyDown}
                      placeholder={activeSkill?`Using ${activeSkill.name} — type your message...`:'Message Fraude... (/ for skills)'}
                      rows={3} disabled={loading}
                      style={{ width:'100%', background:'transparent', border:'none', outline:'none', padding:'12px 14px 7px', color:'var(--text)', fontSize:14, lineHeight:1.6, resize:'none', fontFamily:'var(--font-ui)' }} />
                    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'6px 10px' }}>
                      <div style={{ display:'flex', alignItems:'center', gap:3 }} ref={attachRef}>
                        <div style={{ position:'relative' }}>
                          <button onClick={()=>setShowAttachMenu(o=>!o)}
                            style={{ color:'var(--text3)', padding:'5px 6px', borderRadius:6, border:'none', background:'none', cursor:'pointer', display:'flex', alignItems:'center', transition:'all .12s' }}
                            onMouseOver={e=>{e.currentTarget.style.color='var(--text2)';e.currentTarget.style.background='var(--bg2)';}}
                            onMouseOut={e=>{e.currentTarget.style.color='var(--text3)';e.currentTarget.style.background='none';}}>
                            <Icon path={P.plus} size={16}/>
                          </button>
                          {showAttachMenu && (
                            <div className="anim-fadeup" style={{ position:'absolute', bottom:'100%', left:0, marginBottom:5, background:'var(--bg)', border:'1px solid var(--border)', borderRadius:8, minWidth:190, zIndex:60, boxShadow:'0 6px 20px rgba(0,0,0,.12)', padding:'4px' }}>
                              {[
                                { label:'Add files', icon:'📎', action:()=>{fileInputRef.current?.click();setShowAttachMenu(false);} },
                                { label:'Skills', icon:'⚡', action:()=>{setShowSkills(true);setShowAttachMenu(false);} },
                                { label:webSearch?'Web search: On':'Web search: Off', icon:'🌐', action:()=>{setWebSearch(w=>!w);setShowAttachMenu(false);}, active:webSearch },
                              ].map(item=>(
                                <button key={item.label} onClick={item.action}
                                  style={{ display:'flex', alignItems:'center', gap:8, width:'100%', padding:'8px 10px', borderRadius:5, border:'none', cursor:'pointer', background:'none', color:item.active?'var(--accent)':'var(--text)', fontSize:13, textAlign:'left' }}
                                  onMouseOver={e=>e.currentTarget.style.background='var(--bg-hover)'} onMouseOut={e=>e.currentTarget.style.background='none'}>
                                  {item.icon} {item.label}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                        {activeSkills.map(sk => (
                          <button key={sk.id} onClick={()=>setShowSkills(true)}
                            style={{ display:'flex', alignItems:'center', gap:4, fontSize:12, color:'var(--accent)', background:'var(--accent-dim)', border:'1px solid var(--accent)', borderRadius:6, padding:'3px 8px', cursor:'pointer' }}>
                            {sk.icon} {sk.name}
                            <span onClick={e=>{e.stopPropagation();toggleSkill(sk);}} style={{ color:'var(--accent)', marginLeft:1 }}>✕</span>
                          </button>
                        ))}
                        {webSearch && <span style={{ fontSize:11, color:'var(--accent)', background:'var(--accent-dim)', border:'1px solid var(--accent)', borderRadius:5, padding:'3px 7px' }}>🌐 Web</span>}
                      </div>
                      <div style={{ display:'flex', alignItems:'center', gap:7 }}>
                        <ModelSelector model={model} setModel={setModel} availableModels={availableModels} onOpenBilling={()=>setShowBilling(true)} />
                        <button onClick={handleSend} disabled={loading||!input.trim()}
                          style={{ width:31, height:31, borderRadius:7, display:'flex', alignItems:'center', justifyContent:'center',
                            background: loading||!input.trim() ? 'var(--bg3)' : 'var(--accent)',
                            border:'none', cursor: loading||!input.trim()?'not-allowed':'pointer',
                            color: loading||!input.trim()?'var(--text3)':'#fff', transition:'all .15s' }}>
                          {loading
                            ? <span className="spin" style={{ width:12, height:12, borderRadius:'50%', border:'2px solid var(--text3)', borderTopColor:'transparent', display:'block' }}/>
                            : <Icon path={P.send} size={13}/>}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                <p style={{ fontSize:11, color:'var(--text3)', textAlign:'center', marginTop:6 }}>
                  Fraude can make mistakes. Shift+Enter for new line · / for skills
                </p>
              </div>
            </div>
          </>
        )}
      </div>

      {artifact && <ArtifactPanel artifact={artifact} onClose={()=>setArtifact(null)} />}
      {showBilling  && <BillingModal  settings={settings} onSave={saveSettings} onClose={()=>setShowBilling(false)} />}
      {showSkills   && <SkillsPanel   activeSkills={activeSkills} onToggle={toggleSkill} onClear={()=>setChatSkills(p=>({...p,[activeConvId]:[]}))} onClose={()=>setShowSkills(false)} allSkills={allSkills} currentPlan={currentPlan} />}
      {showMemory   && <MemoryPanel   convId={activeConvId} onClose={()=>setShowMemory(false)} refreshTrigger={memRefresh} />}
      {showProjects && <ProjectsPanel projects={projects} conversations={conversations} activeConvId={activeConvId} onClose={()=>setShowProjects(false)} onRefresh={()=>fetch('/api/projects').then(r=>r.json()).then(setProjects)} />}
      {showQuiz && <QuizModal onSubmit={(instruction)=>{ setInput(instruction); setShowQuiz(false); const clone = allSkills.find(s=>s.id==='clone'); if(clone) toggleSkill(clone); textareaRef.current?.focus(); }} onClose={()=>setShowQuiz(false)} />}
      {showFraudeCode && <FraudeCode settings={settings} currentPlan={currentPlan} onClose={()=>setShowFraudeCode(false)} />}
      {/* Terminal permission modal */}
      {pendingCmd && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.4)', zIndex:250, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:11, width:'min(480px,90vw)', padding:24, boxShadow:'0 8px 30px rgba(0,0,0,.2)' }}>
            <div style={{ fontSize:16, fontWeight:600, color:'var(--text)', marginBottom:6 }}>Permission required</div>
            <p style={{ fontSize:13, color:'var(--text2)', marginBottom:16, lineHeight:1.5 }}>Fraude wants to run the following command on your system:</p>
            <pre style={{ background:'var(--code-bg)', border:'1px solid var(--code-border)', borderRadius:7, padding:'10px 13px', fontSize:13, color:'var(--text)', fontFamily:'var(--font-mono)', marginBottom:18, whiteSpace:'pre-wrap', wordBreak:'break-word' }}>{pendingCmd.command}</pre>
            <div style={{ display:'flex', gap:10 }}>
              <button onClick={async()=>{
                  setPendingCmd(null);
                  try {
                    const res = await fetch('/api/terminal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:pendingCmd.command})});
                    const data = await res.json();
                    setTerminalLog(l=>[...l,{cmd:pendingCmd.command,...data}]);
                    pendingCmd.resolve(data);
                  } catch(e) { pendingCmd.reject(e); }
                }}
                style={{ flex:1, background:'var(--accent)', color:'#fff', border:'none', borderRadius:7, padding:'10px', fontSize:13, fontWeight:500, cursor:'pointer' }}>
                Allow
              </button>
              <button onClick={()=>{ pendingCmd.reject(new Error('User denied')); setPendingCmd(null); }}
                style={{ background:'none', border:'1px solid var(--border)', color:'var(--text2)', borderRadius:7, padding:'10px 16px', fontSize:13, cursor:'pointer' }}>
                Deny
              </button>
            </div>
          </div>
        </div>
      )}
      {terminalLog.length>0 && !pendingCmd && (
        <div style={{ position:'fixed', bottom:16, right:16, background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:9, padding:'12px 14px', maxWidth:380, zIndex:200, boxShadow:'0 4px 20px rgba(0,0,0,.15)' }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
            <span style={{ fontSize:12, fontWeight:600, color:'var(--text)' }}>Terminal</span>
            <button onClick={()=>setTerminalLog([])} style={{ color:'var(--text3)', fontSize:13, cursor:'pointer' }}>✕</button>
          </div>
          {terminalLog.slice(-3).map((t,i)=>(
            <div key={i} style={{ marginBottom:6 }}>
              <div style={{ fontSize:11, color:'var(--text3)', fontFamily:'var(--font-mono)', marginBottom:2 }}>$ {t.cmd}</div>
              {t.output && <pre style={{ fontSize:11, color:'var(--text)', fontFamily:'var(--font-mono)', margin:0, whiteSpace:'pre-wrap' }}>{t.output.slice(0,200)}</pre>}
              {t.error  && <pre style={{ fontSize:11, color:'var(--danger)', fontFamily:'var(--font-mono)', margin:0, whiteSpace:'pre-wrap' }}>{t.error.slice(0,200)}</pre>}
            </div>
          ))}
        </div>
      )}

      {/* rateToast moved inline above input */}
      {updateInfo && (
        <div style={{ position:'fixed', top:10, right:10, background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, padding:'10px 14px', zIndex:250, display:'flex', gap:10, alignItems:'center', fontSize:13, boxShadow:'0 4px 16px rgba(0,0,0,.15)' }}>
          <span style={{ color:'var(--text2)' }}>Update available: {updateInfo.latestVersion}</span>
          <a href={updateInfo.releaseUrl} target="_blank" rel="noreferrer" style={{ background:'var(--accent)', color:'#fff', borderRadius:5, padding:'3px 10px', fontSize:12, textDecoration:'none', fontWeight:500 }}>View</a>
          <button onClick={()=>setUpdateInfo(null)} style={{ color:'var(--text3)', fontSize:14, cursor:'pointer', background:'none', border:'none' }}>✕</button>
        </div>
      )}
      {mobileDrawerOpen && (
        <>
          <div className="mobile-drawer-overlay" onClick={()=>setMobileDrawerOpen(false)} />
          <div className="mobile-drawer">
            <div style={{ padding:'16px 16px 10px', borderBottom:'1px solid var(--border-sub)', display:'flex', alignItems:'center', gap:10 }}>
              <span className="fraude-logo-text" style={{ color:'var(--text)', fontSize:17 }}>Fraude</span>
              <button onClick={()=>setMobileDrawerOpen(false)} style={{ marginLeft:'auto', color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:18 }}>✕</button>
            </div>
            <div style={{ padding:'8px 10px', borderBottom:'1px solid var(--border-sub)' }}>
              <button onClick={()=>{setActiveConvId(null);setMessages([]);setMainView('chat');setMobileDrawerOpen(false);}}
                style={{ display:'flex', alignItems:'center', gap:8, width:'100%', padding:'8px 10px', borderRadius:6, border:'none', background:'none', color:'var(--text2)', cursor:'pointer', fontSize:13, marginBottom:3 }}>+ New chat</button>
              {[
                ['⚡ Skills', ()=>{setShowSkills(true);setMobileDrawerOpen(false);}],
                ['📁 Projects', ()=>{setShowProjects(true);setMobileDrawerOpen(false);}],
                ['💻 Code', ()=>{setShowFraudeCode(true);setMobileDrawerOpen(false);}],
                ['⚙ Settings', ()=>{setMainView('settings');setMobileDrawerOpen(false);}],
              ].map(([label,action])=>(
                <button key={label} onClick={action} style={{ display:'block', width:'100%', padding:'8px 10px', borderRadius:6, border:'none', background:'none', color:'var(--text2)', cursor:'pointer', fontSize:13, textAlign:'left', marginBottom:2 }}>{label}</button>
              ))}
            </div>
            <div style={{ flex:1, overflowY:'auto', padding:'8px 10px' }}>
              <div style={{ fontSize:11, fontWeight:600, color:'var(--text3)', textTransform:'uppercase', letterSpacing:.8, padding:'4px 3px 6px' }}>Recents</div>
              {[...new Map(conversations.map(c=>[c.id,c])).values()].map(conv=>(
                <button key={conv.id} onClick={()=>{setActiveConvId(conv.id);setMainView('chat');setMobileDrawerOpen(false);}}
                  style={{ display:'block', width:'100%', padding:'7px 10px', borderRadius:6, border:'none', cursor:'pointer', textAlign:'left', background:conv.id===activeConvId?'var(--bg-active)':'none', color:conv.id===activeConvId?'var(--text)':'var(--text2)', fontSize:12, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', marginBottom:1 }}>
                  {conv.title}
                </button>
              ))}
            </div>
            <div style={{ padding:'10px 14px', borderTop:'1px solid var(--border-sub)' }}>
              <button onClick={()=>setShowAccount(o=>!o)}
                style={{ display:'flex', alignItems:'center', gap:9, width:'100%', padding:'8px 10px', borderRadius:7, border:'none', background:'none', cursor:'pointer' }}>
                <div style={{ width:28, height:28, borderRadius:'50%', background:'var(--accent-dim)', border:'1px solid var(--accent)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:11, fontWeight:600, color:'var(--accent)', flexShrink:0 }}>{initials(user.name)}</div>
                <div style={{ flex:1 }}>
                  <div style={{ fontSize:13, fontWeight:500, color:'var(--text)' }}>{user.name}</div>
                  <div style={{ fontSize:11, color:'var(--text3)' }}>{PLANS[currentPlan]?.label || currentPlan} plan</div>
                </div>
              </button>
            </div>
          </div>
        </>
      )}
      {showSearch   && <SearchModal   conversations={conversations} onSelect={id=>{setActiveConvId(id);setMainView('chat');}} onClose={()=>setShowSearch(false)} />}
      <input ref={fileInputRef} type="file" style={{ display:'none' }} onChange={e=>e.target.files[0]&&handleFileUpload(e.target.files[0])} />
    </div>
  );
}
