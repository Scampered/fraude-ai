import { BUILTIN_SKILLS } from '../constants.js';

export default function SkillsPanel({ activeSkills=[], onToggle, onClear, onClose, allSkills, currentPlan }) {
  const skills = allSkills || BUILTIN_SKILLS;
  const planOrder = { free:0, pro:1, main:2 };
  const userLevel = planOrder[currentPlan] || 0;

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.3)', zIndex:200, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
      <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:12, width:'min(460px,100%)', maxHeight:'85vh', overflowY:'auto' }}>
        <div style={{ padding:'18px 20px 14px', borderBottom:'1px solid var(--border-sub)', display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
          <div>
            <h2 style={{ fontSize:16, fontWeight:600, color:'var(--text)', marginBottom:3 }}>Skills</h2>
            <p style={{ fontSize:12, color:'var(--text2)' }}>Select one or more. Type /<em>skillname</em> in chat.</p>
          </div>
          <button onClick={onClose} style={{ color:'var(--text3)', fontSize:18, padding:4, cursor:'pointer', background:'none', border:'none' }}>✕</button>
        </div>
        <div style={{ padding:'10px 14px', display:'flex', flexDirection:'column', gap:2 }}>
          {skills.map(skill => {
            const isActive = activeSkills.some(s => s.id === skill.id);
            const locked = skill.proOnly && userLevel < 1;
            return (
              <button key={skill.id}
                onClick={() => !locked && onToggle(skill)}
                style={{
                  display:'flex', alignItems:'center', gap:12, padding:'10px 12px', borderRadius:8,
                  background: isActive ? 'var(--accent-dim)' : 'transparent',
                  border:`1px solid ${isActive ? 'var(--accent)' : 'transparent'}`,
                  cursor: locked ? 'not-allowed' : 'pointer', textAlign:'left', transition:'all .12s', width:'100%',
                  opacity: locked ? 0.5 : 1,
                }}
                onMouseOver={e=>{ if(!isActive && !locked) e.currentTarget.style.background='var(--bg2)'; }}
                onMouseOut={e=>{ if(!isActive) e.currentTarget.style.background=isActive?'var(--accent-dim)':'transparent'; }}>
                <span style={{ fontSize:16, width:24, textAlign:'center', flexShrink:0, color:'var(--text)' }}>{skill.icon}</span>
                <div style={{ flex:1 }}>
                  <div style={{ fontSize:13, fontWeight:500, color: isActive?'var(--accent)':'var(--text)', marginBottom:1, display:'flex', alignItems:'center', gap:6 }}>
                    {skill.name}
                    {skill.proOnly && <span style={{ fontSize:10, color:'var(--accent)', background:'var(--accent-dim)', border:'1px solid var(--accent)', borderRadius:3, padding:'1px 5px' }}>Pro</span>}
                    {locked && <span style={{ fontSize:10, color:'var(--text3)' }}>— upgrade to unlock</span>}
                  </div>
                  <div style={{ fontSize:11, color:'var(--text3)', fontFamily:'var(--font-mono)' }}>
                    /{skill.slash}{skill.imports?.length ? ' · '+skill.imports.join(', ') : ''}
                    {skill.custom && <span style={{ marginLeft:6, color:'var(--accent)', fontSize:10 }}>custom</span>}
                  </div>
                </div>
                {isActive && (
                  <span style={{ width:16, height:16, borderRadius:3, background:'var(--accent)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2 2 4-4" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {activeSkills.length > 0 && (
          <div style={{ padding:'0 14px 14px' }}>
            <button onClick={()=>{ onClear(); onClose(); }}
              style={{ width:'100%', background:'none', border:'1px solid var(--border)', color:'var(--text2)', borderRadius:7, padding:'8px', fontSize:12, cursor:'pointer' }}>
              Clear all skills ({activeSkills.length})
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
