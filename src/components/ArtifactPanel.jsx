export default function ArtifactPanel({ artifact, onClose }) {
  if (!artifact) return null;

  const isPdf = artifact.type === 'pdf' && artifact.pdfUrl;
  const isCode = !isPdf;

  const downloadCode = () => {
    const extMap = {python:'py',javascript:'js',js:'js',html:'html',css:'css',sql:'sql',bash:'sh',sh:'sh'};
    const ext = extMap[artifact.lang] || 'txt';
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([artifact.content], {type:'text/plain'}));
    a.download = artifact.filename || `output.${ext}`;
    a.click();
  };

  const downloadPdf = () => {
    const a = document.createElement('a');
    a.href = artifact.pdfUrl;
    a.download = artifact.pdfFilename || 'output.pdf';
    a.click();
  };

  return (
    <div className="anim-slideinr" style={{
      width: isPdf ? 520 : 420,
      background: 'var(--bg)',
      borderLeft: '1px solid var(--border-sub)',
      display: 'flex', flexDirection: 'column', flexShrink: 0, minHeight: 0,
    }}>
      {/* Header */}
      <div style={{ padding:'11px 14px', borderBottom:'1px solid var(--border-sub)', display:'flex', justifyContent:'space-between', alignItems:'center', background:'var(--bg2)', flexShrink:0 }}>
        <div style={{ minWidth:0, flex:1 }}>
          <div style={{ fontSize:13, fontWeight:500, color:'var(--text)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
            {isPdf ? (artifact.pdfFilename || 'output.pdf') : artifact.title}
          </div>
          <div style={{ fontSize:11, color:'var(--text3)', fontFamily:'var(--font-mono)', marginTop:1 }}>
            {isPdf ? 'PDF · saved to memory' : `${artifact.lang} · saved to memory`}
          </div>
        </div>
        <div style={{ display:'flex', gap:8, marginLeft:10, flexShrink:0, alignItems:'center' }}>
          {isPdf ? (
            <button onClick={downloadPdf}
              style={{ display:'flex', alignItems:'center', gap:5, fontSize:12, color:'#fff', background:'var(--accent)', border:'none', borderRadius:6, padding:'5px 12px', cursor:'pointer', fontWeight:500 }}>
              ↓ Download PDF
            </button>
          ) : (
            <button onClick={downloadCode}
              style={{ fontSize:12, color:'var(--accent)', background:'none', border:'1px solid var(--accent)', borderRadius:5, padding:'3px 9px', cursor:'pointer' }}>
              ↓ Download
            </button>
          )}
          <button onClick={onClose} style={{ color:'var(--text3)', fontSize:16, padding:'2px 4px', cursor:'pointer', background:'none', border:'none' }}>✕</button>
        </div>
      </div>

      {/* Body */}
      {isPdf ? (
        <iframe
          src={artifact.pdfUrl}
          style={{ flex:1, border:'none', background:'#fff' }}
          title="PDF Preview"
        />
      ) : (
        <pre style={{ flex:1, margin:0, padding:'14px', overflowY:'auto', fontSize:12, lineHeight:1.7, color:'var(--text)', fontFamily:'var(--font-mono)', whiteSpace:'pre-wrap', wordBreak:'break-word', background:'var(--code-bg)' }}>
          {artifact.content}
        </pre>
      )}

      {/* Footer */}
      {artifact.savedPath && (
        <div style={{ padding:'6px 13px', borderTop:'1px solid var(--border-sub)', fontSize:11, color:'var(--text3)', fontFamily:'var(--font-mono)', flexShrink:0 }}>
          📁 {artifact.savedPath}
        </div>
      )}
    </div>
  );
}
