import { useState } from 'react';

const COLORS = ['#4A9EFF','#C15F3C','#3fb950','#a371f7','#d29922','#e06c75'];
const EMOJIS = ['📁','🚀','⚡','🔬','💼','🎨','📊','🛠️','🌍','🎯'];

export default function ProjectsPanel({ projects, conversations, activeConvId, onClose, onRefresh }) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(COLORS[0]);
  const [newEmoji, setNewEmoji] = useState(EMOJIS[0]);
  const [expanded, setExpanded] = useState(null);

  const createProject = async () => {
    if (!newName.trim()) return;
    await fetch('/api/projects', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name:newName.trim(), color:newColor, emoji:newEmoji }) });
    setCreating(false); setNewName(''); onRefresh();
  };

  const deleteProject = async (id) => {
    await fetch(`/api/projects/${id}`, { method:'DELETE' });
    onRefresh();
  };

  const addConvToProject = async (projectId, convId) => {
    await fetch(`/api/projects/${projectId}/conversations`, { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ convId }) });
    onRefresh();
  };

  const removeConvFromProject = async (projectId, convId) => {
    await fetch(`/api/projects/${projectId}/conversations`, { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ convId, remove:true }) });
    onRefresh();
  };

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.3)', zIndex:200, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
      <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:12, width:'min(500px,100%)', maxHeight:'85vh', overflowY:'auto' }}>
        <div style={{ padding:'18px 20px 14px', borderBottom:'1px solid var(--border-sub)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <h2 style={{ fontSize:16, fontWeight:600, color:'var(--text)' }}>Projects</h2>
          <div style={{ display:'flex', gap:8 }}>
            <button onClick={()=>setCreating(true)}
              style={{ fontSize:12, color:'var(--accent)', background:'var(--accent-dim)', border:'1px solid var(--accent)', borderRadius:6, padding:'4px 10px', cursor:'pointer' }}>
              + New project
            </button>
            <button onClick={onClose} style={{ color:'var(--text3)', fontSize:18, cursor:'pointer', background:'none', border:'none' }}>✕</button>
          </div>
        </div>

        {creating && (
          <div style={{ padding:'14px 18px', background:'var(--bg2)', borderBottom:'1px solid var(--border-sub)' }}>
            <div style={{ fontSize:13, fontWeight:500, color:'var(--text)', marginBottom:10 }}>New project</div>
            <input value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Project name"
              onKeyDown={e=>e.key==='Enter'&&createProject()}
              style={{ width:'100%', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6, padding:'7px 10px', color:'var(--text)', fontSize:13, outline:'none', marginBottom:10 }}
              onFocus={e=>e.target.style.borderColor='var(--accent)'} onBlur={e=>e.target.style.borderColor='var(--border)'} />
            <div style={{ display:'flex', gap:8, marginBottom:10 }}>
              {EMOJIS.map(e=>(
                <button key={e} onClick={()=>setNewEmoji(e)}
                  style={{ fontSize:16, width:32, height:32, borderRadius:6, border:`1px solid ${newEmoji===e?'var(--accent)':'var(--border)'}`, background:newEmoji===e?'var(--accent-dim)':'none', cursor:'pointer' }}>{e}</button>
              ))}
            </div>
            <div style={{ display:'flex', gap:6, marginBottom:10 }}>
              {COLORS.map(c=>(
                <button key={c} onClick={()=>setNewColor(c)}
                  style={{ width:22, height:22, borderRadius:'50%', background:c, border:`2px solid ${newColor===c?'var(--text)':'transparent'}`, cursor:'pointer' }} />
              ))}
            </div>
            <div style={{ display:'flex', gap:8 }}>
              <button onClick={createProject} style={{ flex:1, background:'var(--accent)', color:'#fff', border:'none', borderRadius:7, padding:'8px', fontSize:13, cursor:'pointer' }}>Create</button>
              <button onClick={()=>setCreating(false)} style={{ background:'none', border:'1px solid var(--border)', color:'var(--text2)', borderRadius:7, padding:'8px 14px', fontSize:13, cursor:'pointer' }}>Cancel</button>
            </div>
          </div>
        )}

        <div style={{ padding:'10px 14px' }}>
          {projects.length === 0 ? (
            <p style={{ fontSize:13, color:'var(--text3)', padding:'12px 0' }}>No projects yet. Create one to organise your chats.</p>
          ) : projects.map(project => (
            <div key={project.id} style={{ marginBottom:8 }}>
              <div className="project-item" style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 12px', background:'var(--bg2)', borderRadius:8, cursor:'pointer', borderLeft:`3px solid ${project.color}` }}
                onClick={()=>setExpanded(expanded===project.id?null:project.id)}>
                <span style={{ fontSize:16 }}>{project.emoji}</span>
                <div style={{ flex:1 }}>
                  <div style={{ fontSize:13, fontWeight:500, color:'var(--text)' }}>{project.name}</div>
                  <div style={{ fontSize:11, color:'var(--text3)' }}>{project.convIds?.length||0} chats</div>
                </div>
                <span style={{ fontSize:12, color:'var(--text3)' }}>{expanded===project.id?'▲':'▼'}</span>
                <button onClick={e=>{e.stopPropagation();deleteProject(project.id);}}
                  style={{ color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:12, padding:'2px 5px' }}>✕</button>
              </div>
              {expanded===project.id && (
                <div style={{ padding:'8px 12px', background:'var(--bg)', border:'1px solid var(--border-sub)', borderRadius:'0 0 8px 8px', marginTop:-4 }}>
                  {/* Chats in project */}
                  {(project.convIds||[]).map(cid => {
                    const conv = conversations.find(c=>c.id===cid);
                    return conv ? (
                      <div key={cid} style={{ display:'flex', alignItems:'center', gap:8, padding:'5px 0', borderBottom:'1px solid var(--border-sub)' }}>
                        <span style={{ flex:1, fontSize:12, color:'var(--text2)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{conv.title}</span>
                        <button onClick={()=>removeConvFromProject(project.id,cid)}
                          style={{ color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:11 }}>Remove</button>
                      </div>
                    ) : null;
                  })}
                  {/* Add current chat */}
                  {activeConvId && !(project.convIds||[]).includes(activeConvId) && (
                    <button onClick={()=>addConvToProject(project.id, activeConvId)}
                      style={{ width:'100%', background:'none', border:'1px dashed var(--border)', color:'var(--text3)', borderRadius:6, padding:'7px', fontSize:12, cursor:'pointer', marginTop:6 }}>
                      + Add current chat
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
