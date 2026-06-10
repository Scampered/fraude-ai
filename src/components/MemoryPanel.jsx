import { useEffect, useState } from 'react';

export default function MemoryPanel({ convId, onClose, refreshTrigger }) {
  const [files, setFiles] = useState([]);
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!convId) return;
    setLoading(true);
    Promise.all([
      fetch(`/api/conversations/${convId}/files`).then(r=>r.json()),
      fetch(`/api/conversations/${convId}/memory`).then(r=>r.json()),
    ]).then(([f,m]) => { setFiles(f); setMemories(m); setLoading(false); }).catch(() => setLoading(false));
  }, [convId, refreshTrigger]);

  const fmt = b => b < 1024 ? `${b}B` : `${(b/1024).toFixed(1)}KB`;

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.3)', zIndex:200, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
      <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:12, width:'min(460px,100%)', maxHeight:'80vh', display:'flex', flexDirection:'column' }}>
        <div style={{ padding:'18px 22px 14px', borderBottom:'1px solid var(--border-sub)', display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
          <div>
            <h2 style={{ fontSize:16, fontWeight:600, color:'var(--text)', marginBottom:3 }}>Memory</h2>
            <p style={{ fontSize:11, color:'var(--text3)', fontFamily:'var(--font-mono)' }}>fraude-memory/{convId?.slice(0,8)}…</p>
          </div>
          <button onClick={onClose} style={{ color:'var(--text3)', fontSize:18, padding:4, cursor:'pointer' }}>✕</button>
        </div>
        <div style={{ flex:1, overflowY:'auto', padding:'14px 22px' }}>
          {loading ? <p style={{ fontSize:13, color:'var(--text3)' }}>Loading...</p> : <>
            {memories.length > 0 && (
              <div style={{ marginBottom:18 }}>
                <div style={{ fontSize:11, fontWeight:600, color:'var(--text3)', textTransform:'uppercase', letterSpacing:.8, marginBottom:8 }}>Notes</div>
                {memories.map((m,i) => <div key={i} style={{ background:'var(--bg2)', border:'1px solid var(--border-sub)', borderRadius:6, padding:'9px 12px', marginBottom:6, fontSize:13, color:'var(--text2)', lineHeight:1.5 }}>{m}</div>)}
              </div>
            )}
            <div style={{ fontSize:11, fontWeight:600, color:'var(--text3)', textTransform:'uppercase', letterSpacing:.8, marginBottom:8 }}>Files ({files.length})</div>
            {files.length === 0 ? <p style={{ fontSize:13, color:'var(--text3)' }}>No files yet.</p>
              : files.map((f,i) => (
                <div key={i} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'9px 12px', background:'var(--bg2)', border:'1px solid var(--border-sub)', borderRadius:6, marginBottom:6 }}>
                  <div style={{ minWidth:0 }}>
                    <div style={{ fontSize:13, color:'var(--text)', fontFamily:'var(--font-mono)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{f.name}</div>
                    <div style={{ fontSize:11, color:'var(--text3)', marginTop:1 }}>{fmt(f.size)}</div>
                  </div>
                  <a href={f.url} download={f.name} style={{ fontSize:12, color:'var(--accent)', border:'1px solid var(--accent)', borderRadius:5, padding:'3px 9px', marginLeft:12, flexShrink:0 }}>↓</a>
                </div>
              ))
            }
          </>}
        </div>
      </div>
    </div>
  );
}
