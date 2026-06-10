import { useState, useRef, useEffect, useCallback } from 'react';

// ─── Action catalogue ──────────────────────────────────────────────────────────
const CATALOGUE = [
  // Events
  { type:'evt_start',    label:'Start',          group:'Events',   icon:'▶', color:'#3fb950', desc:'Entry point of automation',    maxOut:1, maxIn:0 },
  { type:'evt_stop',     label:'Stop',           group:'Events',   icon:'⏹', color:'#e06c75', desc:'End automation here',          maxOut:0, maxIn:10 },
  { type:'evt_time',     label:'Schedule',       group:'Events',   icon:'🕐', color:'#4A9EFF', desc:'Run at time or interval',      maxOut:1, maxIn:0 },
  { type:'evt_hotkey',   label:'Hotkey',         group:'Events',   icon:'⌨', color:'#4A9EFF', desc:'Trigger on key combo',          maxOut:1, maxIn:0 },
  // Actions — Mouse
  { type:'act_move',     label:'Mouse Move',     group:'Mouse',    icon:'🖱', color:'#a371f7', desc:'Move cursor to position',      maxOut:1, maxIn:10 },
  { type:'act_click',    label:'Click',          group:'Mouse',    icon:'👆', color:'#a371f7', desc:'Click at position',            maxOut:1, maxIn:10 },
  { type:'act_scroll',   label:'Scroll',         group:'Mouse',    icon:'↕', color:'#a371f7', desc:'Scroll up or down',            maxOut:1, maxIn:10 },
  // Actions — Keyboard
  { type:'act_type',     label:'Type Text',      group:'Keyboard', icon:'📝', color:'#d29922', desc:'Type a string of text',       maxOut:1, maxIn:10 },
  { type:'act_keys',     label:'Press Keys',     group:'Keyboard', icon:'⌨', color:'#d29922', desc:'Press a key combo',            maxOut:1, maxIn:10 },
  // Actions — App
  { type:'act_open',     label:'Open App',       group:'App',      icon:'📂', color:'#56d364', desc:'Launch an application',       maxOut:1, maxIn:10 },
  { type:'act_close',    label:'Close App',      group:'App',      icon:'✕', color:'#56d364', desc:'Close a window',               maxOut:1, maxIn:10 },
  { type:'act_browser',  label:'Open URL',       group:'App',      icon:'🌐', color:'#56d364', desc:'Navigate browser to URL',     maxOut:1, maxIn:10 },
  // Logic
  { type:'logic_wait',   label:'Wait',           group:'Logic',    icon:'💤', color:'#B0AEA5', desc:'Pause for N seconds',         maxOut:1, maxIn:10 },
  { type:'logic_if',     label:'If Condition',   group:'Logic',    icon:'◇', color:'#C15F3C', desc:'Branch on condition',          maxOut:2, maxIn:10, isIf:true },
  { type:'logic_loop',   label:'Repeat',         group:'Logic',    icon:'🔁', color:'#C15F3C', desc:'Repeat N times',              maxOut:1, maxIn:10 },
  // AI
  { type:'ai_think',     label:'AI Think',       group:'AI',       icon:'🧠', color:'#e06c75', desc:'AI decides next action',      maxOut:1, maxIn:10 },
  { type:'ai_screen',    label:'Read Screen',    group:'AI',       icon:'👁', color:'#e06c75', desc:'Screenshot + AI analysis',    maxOut:1, maxIn:10 },
  { type:'ai_generate',  label:'AI Generate',    group:'AI',       icon:'✨', color:'#e06c75', desc:'Generate text with AI',       maxOut:1, maxIn:10 },
  { type:'ai_ask',       label:'Ask User',       group:'AI',       icon:'💬', color:'#e06c75', desc:'Pause and ask user',          maxOut:2, maxIn:10 },
  // System
  { type:'sys_copy',     label:'Clipboard',      group:'System',   icon:'📋', color:'#79c0ff', desc:'Copy text to clipboard',      maxOut:1, maxIn:10 },
  { type:'sys_notify',   label:'Notify',         group:'System',   icon:'🔔', color:'#79c0ff', desc:'Show notification',           maxOut:1, maxIn:10 },
  { type:'sys_file',     label:'File Op',        group:'System',   icon:'🗂', color:'#79c0ff', desc:'Read/write/copy files',       maxOut:1, maxIn:10 },
];

const GROUPS = ['Events','Mouse','Keyboard','App','Logic','AI','System'];
const getCat = (type) => CATALOGUE.find(c=>c.type===type) || { label:type, icon:'?', color:'#888', maxOut:1, maxIn:10 };

const GRID = 16;
const snap = v => Math.round(v/GRID)*GRID;

// ─── Config forms ──────────────────────────────────────────────────────────────
function ConfigForm({ type, cfg, onChange }) {
  const S = (k,v) => onChange({...cfg,[k]:v});
  const inp = (k,ph,t='text',extra={}) => (
    <div style={{marginBottom:8}}>
      <label style={{fontSize:10,color:'#888',display:'block',marginBottom:3,textTransform:'uppercase',letterSpacing:.5}}>{ph}</label>
      <input value={cfg[k]||''} onChange={e=>S(k,e.target.value)} type={t}
        style={{width:'100%',background:'#0d1117',border:'1px solid #30363d',borderRadius:5,padding:'5px 8px',color:'#e6edf3',fontSize:12,outline:'none'}} {...extra} />
    </div>
  );
  const sel = (k,ph,opts) => (
    <div style={{marginBottom:8}}>
      <label style={{fontSize:10,color:'#888',display:'block',marginBottom:3,textTransform:'uppercase',letterSpacing:.5}}>{ph}</label>
      <select value={cfg[k]||opts[0][0]} onChange={e=>S(k,e.target.value)}
        style={{width:'100%',background:'#0d1117',border:'1px solid #30363d',borderRadius:5,padding:'5px 8px',color:'#e6edf3',fontSize:12,outline:'none'}}>
        {opts.map(([v,l])=><option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
  const area = (k,ph) => (
    <div style={{marginBottom:8}}>
      <label style={{fontSize:10,color:'#888',display:'block',marginBottom:3,textTransform:'uppercase',letterSpacing:.5}}>{ph}</label>
      <textarea value={cfg[k]||''} onChange={e=>S(k,e.target.value)} rows={3}
        style={{width:'100%',background:'#0d1117',border:'1px solid #30363d',borderRadius:5,padding:'5px 8px',color:'#e6edf3',fontSize:12,outline:'none',resize:'none'}} />
    </div>
  );
  switch(type) {
    case 'evt_time':   return <>{sel('sched','Schedule',[['once','Once at time'],['daily','Daily'],['interval','Every N minutes']])} {inp('time','Time','time')} {(cfg.sched==='interval'||!cfg.sched)&&inp('interval','Interval (min)','number')}</>;
    case 'evt_hotkey': return <>{inp('keys','Key combo (e.g. ctrl+shift+f)')}</>;
    case 'act_move':   return <><div style={{display:'flex',gap:6}}>{inp('x','X','number')}{inp('y','Y','number')}</div></>;
    case 'act_click':  return <><div style={{display:'flex',gap:6}}>{inp('x','X','number')}{inp('y','Y','number')}</div>{sel('btn','Button',[['left','Left click'],['right','Right click'],['double','Double click'],['middle','Middle click']])}</>;
    case 'act_scroll': return <>{sel('dir','Direction',[['down','Scroll down'],['up','Scroll up']])} {inp('amount','Lines','number')}</>;
    case 'act_type':   return <>{area('text','Text to type')} {inp('delay','Delay per char (ms)','number')}</>;
    case 'act_keys':   return <>{inp('keys','Keys (e.g. ctrl+c, enter)')}</>;
    case 'act_open':   return <>{inp('path','Program path or name')} {inp('args','Arguments (optional)')}</>;
    case 'act_browser':return <>{inp('url','URL (https://...)')} {sel('br','Browser',[['default','Default browser'],['chrome','Chrome'],['edge','Edge'],['firefox','Firefox']])}</>;
    case 'logic_wait': return <>{inp('secs','Seconds to wait','number')}</>;
    case 'logic_if':   return <>{sel('cond','Condition',[['clipboard','Clipboard contains'],['window','Window title contains'],['file','File exists'],['ai','AI result contains'],['time','Time is after']])} {inp('value','Value to check')}</>;
    case 'logic_loop': return <>{inp('count','Repeat count','number')}</>;
    case 'ai_think':   return <>{area('prompt','Goal / instruction')} {sel('model','Model',[['gemini','Gemini (vision, screen)'],['groq','Groq (fast reasoning)'],['ollama','Ollama (local, private)']])}</>;
    case 'ai_screen':  return <>{inp('extract','What to extract from screen')} <div style={{fontSize:11,color:'#484f58'}}>Uses Gemini to take screenshot + analyse</div></>;
    case 'ai_generate':return <>{area('prompt','Generation prompt')} {sel('model','Model',[['gemini','Gemini'],['groq','Groq'],['ollama','Ollama']])} {inp('var','Store result in variable (optional)')}</>;
    case 'ai_ask':     return <>{inp('q','Question to ask user')} {sel('type','Answer type',[['yesno','Yes / No'],['text','Free text'],['confirm','Confirm only']])}</>;
    case 'sys_copy':   return <>{inp('text','Text to copy (or {variable})')}</>;
    case 'sys_notify': return <>{inp('title','Title')} {inp('body','Body')}</>;
    case 'sys_file':   return <>{sel('op','Operation',[['read','Read'],['write','Write'],['copy','Copy'],['delete','Delete'],['exists','Check exists']])} {inp('path','File path')} {(cfg.op==='write'||cfg.op==='copy')&&inp('dest','Destination')}</>;
    default: return <div style={{fontSize:11,color:'#484f58'}}>No configuration needed.</div>;
  }
}

// ─── Canvas node ───────────────────────────────────────────────────────────────
function Node({ node, selected, onSelect, onDragStart, onConnectStart, onConnectEnd, connecting }) {
  const cat = getCat(node.type);
  const isIf = cat.isIf;
  return (
    <div
      onMouseDown={e=>{ if(e.target.dataset.port) return; e.stopPropagation(); onDragStart(e, node.id); onSelect(node.id); }}
      onMouseUp={e=>{ if(connecting) onConnectEnd(node.id); }}
      style={{
        position:'absolute', left:node.x, top:node.y,
        width:140, background:'#161b22',
        border:`2px solid ${selected?cat.color:'#30363d'}`,
        borderTop:`3px solid ${cat.color}`,
        borderRadius:10, cursor:'grab', userSelect:'none',
        boxShadow: selected?`0 0 0 2px ${cat.color}44,0 4px 20px rgba(0,0,0,.4)`:'0 2px 8px rgba(0,0,0,.3)',
        transition:'box-shadow .15s,border-color .15s', zIndex: selected?10:5,
      }}>
      {/* Header */}
      <div style={{ padding:'8px 10px 6px', display:'flex', alignItems:'center', gap:7 }}>
        <span style={{ fontSize:14 }}>{cat.icon}</span>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:12, fontWeight:600, color:'#e6edf3', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
            {node.label || cat.label}
          </div>
          <div style={{ fontSize:10, color:'#484f58' }}>{cat.group}</div>
        </div>
      </div>

      {/* IN port - top centre */}
      {cat.maxIn > 0 && (
        <div data-port="in" data-node={node.id}
          onMouseUp={e=>{e.stopPropagation(); if(connecting) onConnectEnd(node.id);}}
          style={{ position:'absolute', top:-7, left:'50%', transform:'translateX(-50%)',
            width:13, height:13, borderRadius:'50%', background:'#21262d', border:`2px solid ${cat.color}`,
            cursor:'crosshair', zIndex:20 }} />
      )}

      {/* OUT port(s) - bottom */}
      {cat.maxOut > 0 && !isIf && (
        <div data-port="out" data-node={node.id} data-port-idx="0"
          onMouseDown={e=>{ e.stopPropagation(); onConnectStart(e, node.id, 0); }}
          style={{ position:'absolute', bottom:-7, left:'50%', transform:'translateX(-50%)',
            width:13, height:13, borderRadius:'50%', background:cat.color, border:'2px solid #161b22',
            cursor:'crosshair', zIndex:20 }} />
      )}
      {isIf && (
        <>
          <div style={{ display:'flex', justifyContent:'space-between', padding:'4px 10px 8px', fontSize:10, color:'#484f58' }}>
            <span>YES</span><span>NO</span>
          </div>
          {[0,1].map(i=>(
            <div key={i} data-port="out" data-node={node.id} data-port-idx={String(i)}
              onMouseDown={e=>{ e.stopPropagation(); onConnectStart(e, node.id, i); }}
              style={{ position:'absolute', bottom:-7, left: i===0?'25%':'75%', transform:'translateX(-50%)',
                width:13, height:13, borderRadius:'50%', background: i===0?'#3fb950':'#e06c75', border:'2px solid #161b22',
                cursor:'crosshair', zIndex:20 }} />
          ))}
        </>
      )}
    </div>
  );
}

// ─── SVG Arrow ─────────────────────────────────────────────────────────────────
function Arrow({ from, to, color='#30363d', id, onDelete, nodes }) {
  // from = {x,y}, to = {x,y} or null (dragging)
  if (!from || !to) return null;
  const dx = to.x - from.x, dy = to.y - from.y;
  const cx1 = from.x + Math.min(80, Math.abs(dx)*0.5);
  const cy1 = from.y;
  const cx2 = to.x - Math.min(80, Math.abs(dx)*0.5);
  const cy2 = to.y;
  const d = `M${from.x},${from.y} C${cx1},${cy1} ${cx2},${cy2} ${to.x},${to.y}`;
  const mx = (from.x+to.x)/2, my = (from.y+to.y)/2;
  return (
    <g>
      <path d={d} stroke={color} strokeWidth={1.5} fill="none" strokeDasharray="none" opacity={0.7} />
      <path d={`M${to.x-5},${to.y-4} L${to.x},${to.y} L${to.x-5},${to.y+4}`} stroke={color} strokeWidth={1.5} fill="none" />
      {id && onDelete && (
        <circle cx={mx} cy={my} r={7} fill="#21262d" stroke={color} strokeWidth={1} style={{ cursor:'pointer' }}
          onClick={()=>onDelete(id)} />
      )}
      {id && onDelete && (
        <text x={mx} y={my+4} textAnchor="middle" fontSize={10} fill="#e06c75" style={{ cursor:'pointer', pointerEvents:'none' }}>×</text>
      )}
    </g>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────
export default function AutomationsPage({ collapsed, onToggleSidebar }) {
  // State
  const [automations, setAutomations] = useState(()=>{ try{return JSON.parse(localStorage.getItem('fraude_automations_v2')||'[]')}catch{return []}});
  const [activeId, setActiveId] = useState(null);
  const [nodes, setNodes] = useState([]);     // {id,type,x,y,label,cfg}
  const [edges, setEdges] = useState([]);     // {id,from,fromIdx,to}
  const [selected, setSelected] = useState(null);
  const [connecting, setConnecting] = useState(null); // {fromId, fromIdx}
  const [dragNode, setDragNode] = useState(null);      // {id, offX, offY}
  const [dragModule, setDragModule] = useState(null);  // type being dragged from tray
  const [mousePos, setMousePos] = useState({x:0,y:0});
  const [showLog, setShowLog] = useState(false);
  const [runLog, setRunLog] = useState([]);
  const [running, setRunning] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiModel, setAiModel] = useState('groq');
  const [aiBuilding, setAiBuilding] = useState(false);
  const [drawerGroup, setDrawerGroup] = useState('Events');
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [showAutomList, setShowAutomList] = useState(true);

  const canvasRef = useRef(null);
  const active = automations.find(a=>a.id===activeId);

  // Persist
  const persist = (data) => { setAutomations(data); localStorage.setItem('fraude_automations_v2', JSON.stringify(data)); };
  const saveCanvas = useCallback((nds=nodes, eds=edges) => {
    persist(automations.map(a=>a.id===activeId ? {...a,nodes:nds,edges:eds,updatedAt:Date.now()} : a));
  }, [automations, activeId, nodes, edges]);

  // Load canvas when switching
  useEffect(()=>{
    if(!active) return;
    setNodes(active.nodes||[]);
    setEdges(active.edges||[]);
    setSelected(null);
  }, [activeId]);

  // Auto-save on change
  useEffect(()=>{
    if(activeId && (nodes.length||edges.length)) saveCanvas(nodes,edges);
  }, [nodes, edges]);

  // ── Canvas mouse ──────────────────────────────────────────────────────────────
  const canvasMouseMove = useCallback((e)=>{
    const rect = canvasRef.current?.getBoundingClientRect();
    if(!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setMousePos({x,y});
    if(dragNode) {
      setNodes(ns=>ns.map(n=>n.id===dragNode.id ? {...n, x:snap(x-dragNode.offX), y:snap(y-dragNode.offY)} : n));
    }
  },[dragNode]);

  const canvasMouseUp = useCallback((e)=>{
    if(dragModule && canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const x = snap(e.clientX - rect.left - 70);
      const y = snap(e.clientY - rect.top - 25);
      const id = `n_${Date.now()}`;
      setNodes(ns=>[...ns,{id,type:dragModule,x,y,label:'',cfg:{}}]);
    }
    setDragNode(null);
    setDragModule(null);
    if(!connecting) return;
    setConnecting(null);
  },[dragModule, connecting]);

  const canvasClick = (e) => {
    if(e.target===canvasRef.current || e.target.tagName==='svg' || e.target.tagName==='rect') {
      setSelected(null); setConnecting(null);
    }
  };

  // ── Connect ports ─────────────────────────────────────────────────────────────
  const connectStart = (e, fromId, fromIdx) => {
    e.stopPropagation();
    setConnecting({fromId, fromIdx});
  };

  const connectEnd = (toId) => {
    if(!connecting || connecting.fromId===toId) { setConnecting(null); return; }
    const id = `e_${Date.now()}`;
    const edge = {id, from:connecting.fromId, fromIdx:connecting.fromIdx, to:toId};
    setEdges(es=>[...es, edge]);
    setConnecting(null);
  };

  // ── Edge positions ────────────────────────────────────────────────────────────
  const getPortPos = (nodeId, isOut, portIdx=0) => {
    const n = nodes.find(x=>x.id===nodeId);
    if(!n) return null;
    const cat = getCat(n.type);
    if(isOut) {
      if(cat.isIf) return { x: n.x + 140*(portIdx===0?0.25:0.75), y: n.y + 58 };
      return { x: n.x+70, y: n.y + 58 };
    }
    return { x: n.x+70, y: n.y };
  };

  // ── Run ───────────────────────────────────────────────────────────────────────
  const runAutomation = async () => {
    if(!nodes.length) return;
    setRunLog([]); setRunning(true); setShowLog(true);
    const log = (msg,type='info') => setRunLog(p=>[...p,{msg,type,t:new Date().toLocaleTimeString('en',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}]);
    log(`▶ Starting: ${active?.name||'Automation'}`);
    // Find start node
    const start = nodes.find(n=>n.type==='evt_start')||nodes[0];
    if(!start) { log('No Start node found','error'); setRunning(false); return; }
    // Walk graph
    const visited = new Set();
    let current = start;
    while(current && !visited.has(current.id)) {
      visited.add(current.id);
      const cat = getCat(current.type);
      log(`→ ${cat.icon} ${current.label||cat.label}`, 'step');
      if(current.type==='evt_stop') { log('⏹ Stopped','info'); break; }
      try {
        const res = await fetch('/api/jarvis/action',{
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({type:current.type, config:current.cfg||{}}),
        });
        if(res.ok){ const d=await res.json(); log(`  ✓ ${d.result||'done'}`, 'ok'); }
        else { log(`  ⚠ JARVIS not connected — queued`, 'warn'); }
      } catch { log(`  ⚠ JARVIS not connected — queued`, 'warn'); }
      await new Promise(r=>setTimeout(r,350));
      // Follow first outgoing edge
      const outEdge = edges.find(e=>e.from===current.id);
      if(!outEdge) break;
      current = nodes.find(n=>n.id===outEdge.to);
    }
    log(`✓ Finished`, 'ok');
    setRunning(false);
  };

  // ── AI build ──────────────────────────────────────────────────────────────────
  const buildWithAI = async () => {
    if(!aiPrompt.trim()) return;
    setAiBuilding(true);
    try {
      const res = await fetch('/api/run', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ code:
          `import json\nprint(json.dumps({"nodes":[{"id":"n1","type":"evt_start","x":100,"y":100,"label":"Start","cfg":{}},{"id":"n2","type":"ai_think","x":100,"y":220,"label":"Think","cfg":{"prompt":"${aiPrompt.replace(/"/g,"'")}","model":"${aiModel}"}},{"id":"n3","type":"evt_stop","x":100,"y":340,"label":"Stop","cfg":{}}}],"edges":[{"id":"e1","from":"n1","fromIdx":0,"to":"n2"},{"id":"e2","from":"n2","fromIdx":0,"to":"n3"}]}))` })
      });
      const d = await res.json();
      const out = JSON.parse(d.output||'{}');
      if(out.nodes) { setNodes(out.nodes); setEdges(out.edges||[]); }
    } catch(e) {
      // fallback: just add an AI Think node
      const id = `n_${Date.now()}`;
      setNodes(ns=>[...ns, {id,type:'ai_think',x:200,y:200,label:aiPrompt.slice(0,20),cfg:{prompt:aiPrompt,model:aiModel}}]);
    }
    setAiBuilding(false);
    setAiPrompt('');
  };

  const selNode = nodes.find(n=>n.id===selected);

  // ── Dragging ghost ────────────────────────────────────────────────────────────
  useEffect(()=>{
    const up = (e)=>{ setDragModule(null); };
    window.addEventListener('mouseup', up);
    return ()=>window.removeEventListener('mouseup', up);
  },[]);

  // ── Create automation ─────────────────────────────────────────────────────────
  const createAuto = () => {
    if(!newName.trim()) return;
    const a = {id:Date.now(), name:newName.trim(), nodes:[], edges:[], enabled:true, createdAt:Date.now()};
    const next = [...automations, a];
    persist(next);
    setActiveId(a.id); setNodes([]); setEdges([]);
    setShowNewForm(false); setNewName('');
  };

  const exportJson = () => {
    if(!active) return;
    const b = new Blob([JSON.stringify({...active,nodes,edges},null,2)],{type:'application/json'});
    const a=document.createElement('a'); a.href=URL.createObjectURL(b);
    a.download=`${active.name.replace(/\s+/g,'-')}.json`; a.click();
  };

  const LOG_COLORS = { step:'#e6edf3', ok:'#3fb950', warn:'#d29922', error:'#f85149', info:'#484f58' };

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div style={{ display:'flex', height:'100%', overflow:'hidden', background:'#0d1117', fontFamily:"'Fira Code','Consolas',monospace", position:'relative' }}>

      {/* ── Automation list (left) ─────────────────────────────────────────── */}
      {showAutomList && (
        <div style={{ width:200, background:'#161b22', borderRight:'1px solid #21262d', display:'flex', flexDirection:'column', flexShrink:0, transition:'width .2s' }}>
          <div style={{ padding:'12px 12px 8px', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
            <span style={{ fontSize:13, fontWeight:600, color:'#e6edf3' }}>Automations</span>
            <button onClick={()=>setShowAutomList(false)} title="Collapse list"
              style={{ background:'none', border:'none', color:'#484f58', cursor:'pointer', fontSize:14, padding:2 }}>‹</button>
          </div>
          <input placeholder="Search…" style={{ margin:'0 10px 8px', background:'#0d1117', border:'1px solid #21262d', borderRadius:5, padding:'5px 8px', color:'#e6edf3', fontSize:12, outline:'none' }} />
          <div style={{ flex:1, overflowY:'auto', padding:'0 8px' }}>
            {showNewForm ? (
              <div style={{padding:'6px 4px'}}>
                <input value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Name…" autoFocus
                  onKeyDown={e=>e.key==='Enter'&&createAuto()}
                  style={{width:'100%',background:'#0d1117',border:'1px solid #C15F3C',borderRadius:5,padding:'6px 8px',color:'#e6edf3',fontSize:12,outline:'none',marginBottom:5}} />
                <div style={{display:'flex',gap:5}}>
                  <button onClick={createAuto} style={{flex:1,background:'#C15F3C',color:'#fff',border:'none',borderRadius:4,padding:'5px',fontSize:11,cursor:'pointer'}}>Create</button>
                  <button onClick={()=>{setShowNewForm(false);setNewName('');}} style={{background:'none',border:'1px solid #30363d',color:'#8b949e',borderRadius:4,padding:'5px 7px',fontSize:11,cursor:'pointer'}}>✕</button>
                </div>
              </div>
            ) : (
              <button onClick={()=>setShowNewForm(true)} style={{width:'100%',background:'none',border:'1px dashed #30363d',color:'#484f58',borderRadius:5,padding:'6px',fontSize:11,cursor:'pointer',marginBottom:5}}>
                + New automation
              </button>
            )}
            {automations.map(a=>(
              <div key={a.id} onClick={()=>setActiveId(a.id)}
                style={{ padding:'8px 8px', borderRadius:6, cursor:'pointer', marginBottom:2, background:a.id===activeId?'#21262d':'none', border:`1px solid ${a.id===activeId?'#30363d':'transparent'}`, display:'flex', alignItems:'center', gap:7 }}>
                <div style={{ width:7,height:7,borderRadius:'50%',background:a.enabled?'#3fb950':'#484f58',flexShrink:0 }} />
                <span style={{fontSize:12,color:a.id===activeId?'#e6edf3':'#8b949e',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',flex:1}}>{a.name}</span>
                <span style={{fontSize:10,color:'#484f58'}}>{(a.nodes||[]).length}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Canvas area ────────────────────────────────────────────────────── */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', minWidth:0, position:'relative' }}>

        {/* Toolbar */}
        <div style={{ height:46, background:'#161b22', borderBottom:'1px solid #21262d', display:'flex', alignItems:'center', padding:'0 14px', gap:10, flexShrink:0 }}>
          {(!showAutomList || collapsed) && (
            <button onClick={()=>{ if(collapsed) onToggleSidebar(); setShowAutomList(true); }} title="Show automations list"
              style={{background:'none',border:'1px solid #30363d',color:'#8b949e',borderRadius:5,padding:'4px 8px',fontSize:11,cursor:'pointer'}}>
              ⚡ {active?.name||'Select…'}
            </button>
          )}
          {showAutomList && collapsed && (
            <button onClick={()=>setShowAutomList(false)}
              style={{background:'none',border:'none',color:'#484f58',cursor:'pointer',fontSize:13}}>‹</button>
          )}
          <span style={{flex:1,fontSize:13,fontWeight:600,color:'#e6edf3'}}>{active?.name||'No automation selected'}</span>
          {active && <>
            <label style={{display:'flex',alignItems:'center',gap:5,fontSize:11,color:'#8b949e',cursor:'pointer'}}>
              <input type="checkbox" checked={active.enabled!==false} onChange={e=>persist(automations.map(a=>a.id===activeId?{...a,enabled:e.target.checked}:a))} />
              Enabled
            </label>
            <button onClick={exportJson} style={{background:'none',border:'1px solid #30363d',color:'#8b949e',borderRadius:5,padding:'4px 10px',fontSize:11,cursor:'pointer'}}>↓ Export</button>
            <button onClick={()=>{setShowLog(o=>!o); if(running||runLog.length===0) runAutomation();}}
              disabled={running}
              style={{ background:running?'#21262d':'#238636', color:running?'#484f58':'#fff', border:'none', borderRadius:6, padding:'6px 14px', fontSize:12, fontWeight:600, cursor:running?'not-allowed':'pointer', display:'flex', alignItems:'center', gap:5 }}>
              {running ? <><span style={{display:'inline-block',width:10,height:10,borderRadius:'50%',border:'2px solid #fff3',borderTopColor:'#fff',animation:'spin 1s linear infinite'}}/> Running…</> : '▶ Run'}
            </button>
          </>}
        </div>

        {/* Canvas + dotted bg */}
        <div style={{ flex:1, position:'relative', overflow:'hidden', cursor:dragModule?'grabbing':connecting?'crosshair':'default' }}
          ref={canvasRef}
          onMouseMove={canvasMouseMove}
          onMouseUp={canvasMouseUp}
          onClick={canvasClick}>
          {/* Dot grid background */}
          <svg style={{ position:'absolute', inset:0, width:'100%', height:'100%', pointerEvents:'none' }}>
            <defs>
              <pattern id="dots" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="1" fill="#30363d" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#dots)" />
          </svg>

          {active ? (
            <>
              {/* Edges SVG */}
              <svg style={{ position:'absolute', inset:0, width:'100%', height:'100%', pointerEvents:'none', zIndex:3 }}>
                {edges.map(e=>{
                  const from = getPortPos(e.from, true, e.fromIdx||0);
                  const to   = getPortPos(e.to, false);
                  const cat  = getCat(nodes.find(n=>n.id===e.from)?.type||'');
                  return <Arrow key={e.id} id={e.id} from={from} to={to} color={cat.color}
                    onDelete={id=>setEdges(es=>es.filter(x=>x.id!==id))} nodes={nodes} />;
                })}
                {/* Drag preview arrow */}
                {connecting && (()=>{
                  const from = getPortPos(connecting.fromId, true, connecting.fromIdx||0);
                  return from ? <Arrow from={from} to={mousePos} color='#4A9EFF' /> : null;
                })()}
              </svg>

              {/* Nodes */}
              {nodes.map(n=>(
                <Node key={n.id} node={n} selected={n.id===selected}
                  onSelect={setSelected}
                  onDragStart={(e,id)=>{
                    const rect = canvasRef.current.getBoundingClientRect();
                    setDragNode({id, offX:e.clientX-rect.left-n.x, offY:e.clientY-rect.top-n.y});
                  }}
                  onConnectStart={connectStart}
                  onConnectEnd={connectEnd}
                  connecting={connecting} />
              ))}

              {/* Empty state */}
              {nodes.length===0 && (
                <div style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', pointerEvents:'none', gap:8 }}>
                  <div style={{ fontSize:11, color:'#30363d', letterSpacing:2, textTransform:'uppercase' }}>Drag modules onto the canvas</div>
                  <div style={{ fontSize:10, color:'#21262d' }}>or describe your automation below ↓</div>
                </div>
              )}
            </>
          ) : (
            <div style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:10 }}>
              <div style={{ fontSize:28 }}>⚡</div>
              <div style={{ fontSize:13, color:'#8b949e' }}>Select or create an automation</div>
            </div>
          )}
        </div>

        {/* Bottom row: AI chat + module tray */}
        {active && (
          <div style={{ background:'#161b22', borderTop:'1px solid #21262d', flexShrink:0 }}>
            {/* Module tray */}
            <div style={{ padding:'8px 12px 6px', display:'flex', gap:6, overflowX:'auto', borderBottom:'1px solid #21262d', alignItems:'flex-start' }}>
              {/* Group tabs */}
              <div style={{ display:'flex', gap:4, alignItems:'center', flexShrink:0 }}>
                {GROUPS.map(g=>(
                  <button key={g} onClick={()=>setDrawerGroup(g)}
                    style={{ fontSize:10, padding:'3px 7px', borderRadius:4, border:'none', cursor:'pointer', background: drawerGroup===g?'#C15F3C':'#21262d', color: drawerGroup===g?'#fff':'#8b949e', whiteSpace:'nowrap', transition:'all .12s' }}>
                    {g}
                  </button>
                ))}
              </div>
              <div style={{ width:1, background:'#30363d', flexShrink:0, height:28, alignSelf:'center' }} />
              {/* Module blocks */}
              {CATALOGUE.filter(c=>c.group===drawerGroup).map(cat=>(
                <div key={cat.type}
                  draggable
                  onDragStart={()=>setDragModule(cat.type)}
                  onMouseDown={()=>setDragModule(cat.type)}
                  style={{
                    flexShrink:0, width:84, background:'#0d1117', border:`1px solid ${cat.color}44`,
                    borderTop:`2px solid ${cat.color}`, borderRadius:7, padding:'6px 8px',
                    cursor:'grab', userSelect:'none', textAlign:'center', transition:'border-color .12s',
                  }}
                  onMouseOver={e=>e.currentTarget.style.borderColor=cat.color}
                  onMouseOut={e=>e.currentTarget.style.borderColor=cat.color+'44'}>
                  <div style={{ fontSize:16, marginBottom:3 }}>{cat.icon}</div>
                  <div style={{ fontSize:10, fontWeight:600, color:'#e6edf3', lineHeight:1.2 }}>{cat.label}</div>
                  <div style={{ fontSize:9, color:'#484f58', lineHeight:1.3, marginTop:2 }}>{cat.desc}</div>
                </div>
              ))}
            </div>
            {/* AI chat bar */}
            <div style={{ padding:'8px 12px', display:'flex', gap:8, alignItems:'center' }}>
              <select value={aiModel} onChange={e=>setAiModel(e.target.value)}
                style={{ background:'#0d1117', border:'1px solid #30363d', borderRadius:5, padding:'6px 8px', color:'#8b949e', fontSize:11, outline:'none', flexShrink:0 }}>
                <option value="gemini">Gemini</option>
                <option value="groq">Groq</option>
                <option value="ollama">Ollama</option>
              </select>
              <input value={aiPrompt} onChange={e=>setAiPrompt(e.target.value)}
                placeholder="Describe what this automation should do…"
                onKeyDown={e=>e.key==='Enter'&&buildWithAI()}
                style={{ flex:1, background:'#0d1117', border:'1px solid #30363d', borderRadius:6, padding:'7px 10px', color:'#e6edf3', fontSize:12, outline:'none' }}
                onFocus={e=>e.target.style.borderColor='#C15F3C'} onBlur={e=>e.target.style.borderColor='#30363d'} />
              <button onClick={buildWithAI} disabled={aiBuilding||!aiPrompt.trim()}
                style={{ background: aiBuilding||!aiPrompt.trim()?'#21262d':'#C15F3C', color: aiBuilding||!aiPrompt.trim()?'#484f58':'#fff', border:'none', borderRadius:6, padding:'7px 14px', fontSize:12, fontWeight:600, cursor: aiPrompt.trim()&&!aiBuilding?'pointer':'not-allowed', flexShrink:0 }}>
                {aiBuilding?'Building…':'✨ Build'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Config panel / Run log (right) ─────────────────────────────────── */}
      {(selNode || showLog) && (
        <div style={{ width:280, background:'#161b22', borderLeft:'1px solid #21262d', display:'flex', flexDirection:'column', flexShrink:0 }}>
          {/* Tab row */}
          <div style={{ display:'flex', borderBottom:'1px solid #21262d', flexShrink:0 }}>
            {selNode && (
              <button onClick={()=>setShowLog(false)}
                style={{ flex:1, padding:'10px', fontSize:12, fontWeight:600, background:'none', border:'none', cursor:'pointer', color:!showLog?'#e6edf3':'#484f58', borderBottom:!showLog?'2px solid #C15F3C':'2px solid transparent' }}>
                Configure
              </button>
            )}
            <button onClick={()=>setShowLog(true)}
              style={{ flex:1, padding:'10px', fontSize:12, fontWeight:600, background:'none', border:'none', cursor:'pointer', color:showLog?'#e6edf3':'#484f58', borderBottom:showLog?'2px solid #3fb950':'2px solid transparent' }}>
              Run Log
            </button>
            <button onClick={()=>{ setShowLog(false); setSelected(null); }}
              style={{ background:'none', border:'none', color:'#484f58', cursor:'pointer', padding:'10px 12px', fontSize:14 }}>✕</button>
          </div>

          {/* Config */}
          {!showLog && selNode && (
            <div style={{ flex:1, overflowY:'auto', padding:'14px 14px' }}>
              <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:14 }}>
                <span style={{ fontSize:18 }}>{getCat(selNode.type).icon}</span>
                <div>
                  <div style={{ fontSize:13, fontWeight:600, color:'#e6edf3' }}>{getCat(selNode.type).label}</div>
                  <div style={{ fontSize:10, color:'#484f58' }}>{getCat(selNode.type).group}</div>
                </div>
              </div>
              <div style={{ marginBottom:10 }}>
                <label style={{ fontSize:10, color:'#484f58', display:'block', marginBottom:3, textTransform:'uppercase', letterSpacing:.5 }}>Label (optional)</label>
                <input value={selNode.label||''} onChange={e=>setNodes(ns=>ns.map(n=>n.id===selNode.id?{...n,label:e.target.value}:n))}
                  placeholder={getCat(selNode.type).label}
                  style={{ width:'100%', background:'#0d1117', border:'1px solid #30363d', borderRadius:5, padding:'5px 8px', color:'#e6edf3', fontSize:12, outline:'none' }} />
              </div>
              <ConfigForm type={selNode.type} cfg={selNode.cfg||{}}
                onChange={cfg=>setNodes(ns=>ns.map(n=>n.id===selNode.id?{...n,cfg}:n))} />
              <button onClick={()=>{ setNodes(ns=>ns.filter(n=>n.id!==selNode.id)); setEdges(es=>es.filter(e=>e.from!==selNode.id&&e.to!==selNode.id)); setSelected(null); }}
                style={{ marginTop:12, width:'100%', background:'none', border:'1px solid #f85149', color:'#f85149', borderRadius:6, padding:'6px', fontSize:12, cursor:'pointer' }}>
                Delete node
              </button>
            </div>
          )}

          {/* Run log */}
          {showLog && (
            <div style={{ flex:1, overflowY:'auto', padding:'8px 12px', display:'flex', flexDirection:'column', gap:1 }}>
              {runLog.length===0 && <div style={{ fontSize:12, color:'#484f58', textAlign:'center', paddingTop:20 }}>Click ▶ Run to start</div>}
              {runLog.map((l,i)=>(
                <div key={i} style={{ fontSize:11, fontFamily:"'Fira Code',monospace", color:LOG_COLORS[l.type]||'#e6edf3', padding:'2px 0', lineHeight:1.5 }}>
                  <span style={{ color:'#30363d', marginRight:8 }}>{l.t}</span>{l.msg}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Drag ghost */}
      {dragModule && (()=>{ const c=getCat(dragModule); return (
        <div style={{ position:'fixed', left:mousePos.x+10, top:mousePos.y+10, width:84, background:'#0d1117', border:`2px solid ${c.color}`, borderRadius:7, padding:'6px 8px', pointerEvents:'none', zIndex:9999, textAlign:'center', opacity:.9 }}>
          <div style={{ fontSize:16 }}>{c.icon}</div>
          <div style={{ fontSize:10, fontWeight:600, color:'#e6edf3' }}>{c.label}</div>
        </div>
      );})()}
    </div>
  );
}
