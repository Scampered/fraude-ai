import { useEffect, useState } from 'react';

export default function ErrorBanner({ error, onDismiss }) {
  const [visible, setVisible] = useState(false);
  const [showDetail, setShowDetail] = useState(false);

  useEffect(() => {
    if (!error) return;
    setVisible(true); setShowDetail(false);
    if (error.clearAfter) {
      const t = setTimeout(() => { setVisible(false); setTimeout(onDismiss, 300); }, error.clearAfter);
      return () => clearTimeout(t);
    }
  }, [error]);

  if (!error || !visible) return null;

  return (
    <div style={{ position:'fixed', top:14, left:'50%', transform:'translateX(-50%)', zIndex:300, animation:'bannerIn .25s ease',
      background:'var(--bg2)', border:'1px solid var(--accent)', borderRadius:8, padding:'10px 14px',
      maxWidth:400, width:'90vw', boxShadow:'0 4px 20px rgba(0,0,0,.12)',
      display:'flex', gap:10, alignItems:'flex-start' }}>
      <span style={{ fontSize:14, flexShrink:0, marginTop:1, color:'var(--accent)' }}>⚠</span>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:13, fontWeight:600, color:'var(--text)', marginBottom:2 }}>{error.title}</div>
        <div style={{ fontSize:12, color:'var(--text2)', lineHeight:1.5 }}>{error.body}</div>
        {error.detail && (
          <>
            <button onClick={() => setShowDetail(d => !d)}
              style={{ fontSize:11, color:'var(--text3)', background:'none', border:'none', padding:'3px 0', marginTop:3, cursor:'pointer', textDecoration:'underline' }}>
              {showDetail ? 'Hide details' : '? Why did this happen'}
            </button>
            {showDetail && (
              <div style={{ fontSize:11, color:'var(--text2)', background:'var(--code-bg)', border:'1px solid var(--code-border)', borderRadius:5, padding:'8px 10px', marginTop:5, lineHeight:1.6, fontFamily:'var(--font-mono)' }}>
                {error.detail}
              </div>
            )}
          </>
        )}
        {error.clearAfter && <div style={{ fontSize:10, color:'var(--text3)', marginTop:3 }}>Auto-dismisses in {Math.round(error.clearAfter/1000)}s</div>}
      </div>
      <button onClick={() => { setVisible(false); setTimeout(onDismiss, 300); }}
        style={{ color:'var(--text3)', fontSize:15, lineHeight:1, flexShrink:0, padding:2, cursor:'pointer' }}>✕</button>
    </div>
  );
}
