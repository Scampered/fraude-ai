export default function StepsDisplay({ steps }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
      {steps.map((s,i) => (
        <div key={i} style={{ display:'flex', alignItems:'center', gap:8, opacity: s.done ? 0.4 : 1, transition:'opacity .4s' }}>
          <span style={{ width:16, height:16, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
            {s.done
              ? <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5.5" stroke="var(--success)" strokeWidth="1"/><path d="M3.5 6l1.7 1.7L8.5 4" stroke="var(--success)" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>
              : s.active
                ? <span className="spin" style={{ width:12, height:12, borderRadius:'50%', border:'1.5px solid var(--accent)', borderTopColor:'transparent', display:'block' }} />
                : <span style={{ width:8, height:8, borderRadius:'50%', border:'1.5px solid var(--border)', display:'block', margin:'0 2px' }} />
            }
          </span>
          <span style={{ fontSize:13, color: s.done ? 'var(--text3)' : s.active ? 'var(--text2)' : 'var(--border)', fontFamily:'var(--font-ui)', transition:'color .3s' }}>
            {s.text}
          </span>
        </div>
      ))}
    </div>
  );
}
