import { useState } from 'react';

const COLORS = ['#4A9EFF','#C15F3C','#3fb950','#a371f7','#d29922','#e06c75','#56d364','#79c0ff'];
const EMOJIS = ['📁','🚀','⚡','🔬','💼','🎨','📊','🛠','🌍','🎯','💡','🔮'];

export default function ProjectsPage({ projects, conversations, activeConvId, onRefresh, onOpenConv }) {
  const [search, setSearch] = useState('');
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(COLORS[0]);
  const [newEmoji, setNewEmoji] = useState(EMOJIS[0]);
  const [newDesc, setNewDesc] = useState('');
  const [expanded, setExpanded] = useState(null);
  const [sortBy, setSortBy] = useState('activity');

  const createProject = async () => {
    if (!newName.trim()) return;
    await fetch('/api/projects', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name:newName.trim(), color:newColor, emoji:newEmoji, desc:newDesc.trim() }) });
    setCreating(false); setNewName(''); setNewDesc('');
    onRefresh();
  };

  const deleteProject = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this project?')) return;
    await fetch(`/api/projects/${id}`, { method:'DELETE' });
    onRefresh();
  };

  const addConv = async (projectId) => {
    if (!activeConvId) return;
    await fetch(`/api/projects/${projectId}/conversations`, { method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({ convId: activeConvId }) });
    onRefresh();
  };

  const removeConv = async (projectId, convId, e) => {
    e.stopPropagation();
    await fetch(`/api/projects/${projectId}/conversations`, { method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({ convId, remove:true }) });
    onRefresh();
  };

  const sorted = [...projects]
    .filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a,b) => sortBy==='name' ? a.name.localeCompare(b.name) : (b.updatedAt||0)-(a.updatedAt||0));

  return (
    <div style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden', background:'var(--bg)' }}>

      {/* Header */}
      <div style={{ padding:'24px 32px 16px', borderBottom:'1px solid var(--border-sub)', flexShrink:0 }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:16 }}>
          <h1 style={{ fontSize:26, fontWeight:700, color:'var(--text)', fontFamily:'Georgia,serif', margin:0 }}>Projects</h1>
          <div style={{ display:'flex', gap:10, alignItems:'center' }}>
            <span style={{ fontSize:13, color:'var(--text3)' }}>Sort by</span>
            <select value={sortBy} onChange={e=>setSortBy(e.target.value)}
              style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:7, padding:'5px 10px', color:'var(--text)', fontSize:13, outline:'none', cursor:'pointer' }}>
              <option value="activity">Activity</option>
              <option value="name">Name</option>
            </select>
            <button onClick={()=>setCreating(true)}
              style={{ background:'var(--text)', color:'var(--bg)', border:'none', borderRadius:8, padding:'8px 16px', fontSize:13, fontWeight:600, cursor:'pointer' }}>
              New project
            </button>
          </div>
        </div>
        <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search projects…"
          style={{ width:'100%', background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:10, padding:'10px 14px', color:'var(--text)', fontSize:14, outline:'none' }}
          onFocus={e=>e.target.style.borderColor='var(--accent)'} onBlur={e=>e.target.style.borderColor='var(--border)'} />
      </div>

      {/* New project form */}
      {creating && (
        <div style={{ padding:'16px 32px', borderBottom:'1px solid var(--border-sub)', background:'var(--bg2)', flexShrink:0 }}>
          <div style={{ maxWidth:520 }}>
            <div style={{ fontSize:14, fontWeight:600, color:'var(--text)', marginBottom:12 }}>New project</div>
            <input value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Project name" autoFocus
              onKeyDown={e=>e.key==='Enter'&&createProject()}
              style={{ width:'100%', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:7, padding:'9px 12px', color:'var(--text)', fontSize:13, outline:'none', marginBottom:10 }}
              onFocus={e=>e.target.style.borderColor='var(--accent)'} onBlur={e=>e.target.style.borderColor='var(--border)'} />
            <input value={newDesc} onChange={e=>setNewDesc(e.target.value)} placeholder="Description (optional)"
              style={{ width:'100%', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:7, padding:'9px 12px', color:'var(--text)', fontSize:13, outline:'none', marginBottom:12 }}
              onFocus={e=>e.target.style.borderColor='var(--accent)'} onBlur={e=>e.target.style.borderColor='var(--border)'} />
            <div style={{ display:'flex', gap:10, marginBottom:10, flexWrap:'wrap' }}>
              {EMOJIS.map(e=>(
                <button key={e} onClick={()=>setNewEmoji(e)}
                  style={{ fontSize:18, width:36, height:36, borderRadius:8, border:`2px solid ${newEmoji===e?'var(--accent)':'var(--border)'}`, background: newEmoji===e?'var(--accent-dim)':'none', cursor:'pointer' }}>
                  {e}
                </button>
              ))}
            </div>
            <div style={{ display:'flex', gap:7, marginBottom:14 }}>
              {COLORS.map(col=>(
                <button key={col} onClick={()=>setNewColor(col)}
                  style={{ width:24, height:24, borderRadius:'50%', background:col, border:`2.5px solid ${newColor===col?'var(--text)':'transparent'}`, cursor:'pointer', flexShrink:0 }} />
              ))}
            </div>
            <div style={{ display:'flex', gap:8 }}>
              <button onClick={createProject}
                style={{ flex:1, background:'var(--accent)', color:'#fff', border:'none', borderRadius:7, padding:'9px', fontSize:13, fontWeight:500, cursor:'pointer' }}>
                Create project
              </button>
              <button onClick={()=>{setCreating(false);setNewName('');setNewDesc('');}}
                style={{ background:'none', border:'1px solid var(--border)', color:'var(--text2)', borderRadius:7, padding:'9px 16px', fontSize:13, cursor:'pointer' }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Projects grid */}
      <div style={{ flex:1, overflowY:'auto', padding:'20px 32px' }}>
        {sorted.length === 0 ? (
          <div style={{ textAlign:'center', padding:'60px 20px', color:'var(--text3)' }}>
            <div style={{ fontSize:32, marginBottom:12 }}>📁</div>
            <div style={{ fontSize:15, color:'var(--text2)', marginBottom:6 }}>No projects yet</div>
            <div style={{ fontSize:13 }}>Create a project to organise your chats.</div>
          </div>
        ) : (
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))', gap:14 }}>
            {sorted.map(project => {
              const convs = (project.convIds||[]).map(cid => conversations.find(c=>c.id===cid)).filter(Boolean);
              const isExpanded = expanded === project.id;
              return (
                <div key={project.id} style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:12, overflow:'hidden', transition:'border-color .15s', cursor:'pointer' }}
                  onMouseOver={e=>e.currentTarget.style.borderColor=project.color}
                  onMouseOut={e=>e.currentTarget.style.borderColor='var(--border)'}
                  onClick={()=>setExpanded(isExpanded?null:project.id)}>
                  {/* Card header */}
                  <div style={{ borderTop:`3px solid ${project.color}`, padding:'16px 16px 10px' }}>
                    <div style={{ display:'flex', alignItems:'flex-start', gap:10 }}>
                      <span style={{ fontSize:20 }}>{project.emoji}</span>
                      <div style={{ flex:1 }}>
                        <div style={{ fontSize:14, fontWeight:600, color:'var(--text)', marginBottom:3 }}>{project.name}</div>
                        {project.desc && <div style={{ fontSize:12, color:'var(--text3)', lineHeight:1.5 }}>{project.desc}</div>}
                      </div>
                      <button onClick={e=>deleteProject(project.id,e)}
                        style={{ color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:14, padding:'2px 4px', opacity:.5 }}
                        onMouseOver={e=>{e.currentTarget.style.opacity='1';e.currentTarget.style.color='var(--danger)';}}
                        onMouseOut={e=>{e.currentTarget.style.opacity='.5';e.currentTarget.style.color='var(--text3)';}}>✕</button>
                    </div>
                    <div style={{ fontSize:11, color:'var(--text3)', marginTop:8 }}>
                      {convs.length} chat{convs.length!==1?'s':''} · Updated {project.updatedAt ? new Date(project.updatedAt).toLocaleDateString() : 'recently'}
                    </div>
                  </div>

                  {/* Chats list (expanded) */}
                  {isExpanded && (
                    <div style={{ borderTop:'1px solid var(--border-sub)', padding:'10px 14px 14px' }}>
                      {convs.length === 0 ? (
                        <div style={{ fontSize:12, color:'var(--text3)', marginBottom:8 }}>No chats yet.</div>
                      ) : convs.map(conv=>(
                        <div key={conv.id}
                          style={{ display:'flex', alignItems:'center', gap:8, padding:'5px 0', borderBottom:'1px solid var(--border-sub)' }}>
                          <span style={{ flex:1, fontSize:12, color:'var(--text2)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', cursor:'pointer' }}
                            onClick={e=>{e.stopPropagation(); onOpenConv(conv.id);}}>
                            {conv.title}
                          </span>
                          <button onClick={e=>removeConv(project.id,conv.id,e)}
                            style={{ color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:11, padding:'1px 4px' }}>✕</button>
                        </div>
                      ))}
                      <div style={{ display:'flex', gap:6, marginTop:10 }}>
                        <button onClick={e=>{e.stopPropagation();onOpenConv(null);}}
                          style={{ flex:1, background:'var(--accent)', color:'#fff', border:'none', borderRadius:6, padding:'7px', fontSize:12, cursor:'pointer', fontWeight:500 }}>
                          + New chat in project
                        </button>
                        {activeConvId && !(project.convIds||[]).includes(activeConvId) && (
                          <button onClick={e=>{e.stopPropagation();addConv(project.id);}}
                            style={{ background:'none', border:'1px solid var(--border)', color:'var(--text2)', borderRadius:6, padding:'7px 10px', fontSize:12, cursor:'pointer' }}>
                            Add current
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
