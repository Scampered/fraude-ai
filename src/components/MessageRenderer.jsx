import { useState } from 'react';

// Syntax highlight — strings first, then keywords, then numbers
function hl(code, lang) {
  // Escape HTML first
  let s = code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  
  if (['python'].includes(lang)) {
    // Comments
    s = s.replace(/(#[^\n]*)/g, '<C1>$1</C1>');
    // Strings (before keywords so "from" inside string isn't coloured)
    s = s.replace(/("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, '<S1>$1</S1>');
    // Keywords
    s = s.replace(/\b(def|class|import|from|return|if|else|elif|for|while|in|not|and|or|try|except|with|as|pass|break|continue|yield|lambda|True|False|None|raise|async|await)\b/g, '<K1>$1</K1>');
    // Numbers
    s = s.replace(/\b(\d+\.?\d*)\b/g, '<N1>$1</N1>');
  } else if (['javascript','js','typescript','ts','jsx','tsx'].includes(lang)) {
    s = s.replace(/(\/\/[^\n]*)/g, '<C1>$1</C1>');
    s = s.replace(/(`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, '<S1>$1</S1>');
    s = s.replace(/\b(const|let|var|function|return|if|else|for|while|class|import|export|default|from|new|async|await|try|catch|null|undefined|true|false|typeof|instanceof)\b/g, '<K1>$1</K1>');
    s = s.replace(/\b(\d+\.?\d*)\b/g, '<N1>$1</N1>');
  } else if (lang === 'sql') {
    s = s.replace(/\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|ON|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|DROP|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|AS|AND|OR|NOT|NULL|COUNT|SUM|AVG|MAX|MIN|DISTINCT)\b/gi, '<K1>$1</K1>');
  } else if (['bash','sh'].includes(lang)) {
    s = s.replace(/(#[^\n]*)/g, '<C1>$1</C1>');
    s = s.replace(/\b(echo|cd|ls|mkdir|rm|cp|mv|cat|grep|awk|sed|python|python3|pip|npm|node|git|chmod|sudo|apt|brew)\b/g, '<K1>$1</K1>');
    s = s.replace(/"([^"]*)"/g, '<S1>"$1"</S1>');
  }
  
  // Now replace placeholder tags with actual styled spans
  s = s
    .replace(/<C1>([\s\S]*?)<\/C1>/g, '<span style="color:var(--text3)">$1</span>')
    .replace(/<S1>([\s\S]*?)<\/S1>/g, '<span style="color:#2D7A47">$1</span>')
    .replace(/<K1>([\s\S]*?)<\/K1>/g, '<span style="color:#B25C2E;font-weight:500">$1</span>')
    .replace(/<N1>([\s\S]*?)<\/N1>/g, '<span style="color:#5C7DB5">$1</span>');
  
  return s;
}

function renderMd(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    // Bold and italic
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Headings (order matters: #### before ### before ## before #)
    .replace(/^#{4} (.*?)$/gm, '<h4 class="mh4">$1</h4>')
    .replace(/^#{3} (.*?)$/gm, '<h3 class="mh3">$1</h3>')
    .replace(/^#{2} (.*?)$/gm, '<h2 class="mh2">$1</h2>')
    .replace(/^# (.*?)$/gm,    '<h1 class="mh1">$1</h1>')
    // HR
    .replace(/^---+$/gm, '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">')
    // Bullets
    .replace(/^  - (.*?)$/gm,  '<div style="display:flex;gap:7px;margin:2px 0 2px 16px"><span style="color:var(--text3);font-size:9px;margin-top:6px">○</span><span>$1</span></div>')
    .replace(/^- (.*?)$/gm,    '<div style="display:flex;gap:8px;margin:3px 0"><span style="color:var(--accent);font-size:9px;margin-top:6px">●</span><span>$1</span></div>')
    // Ordered list
    .replace(/^(\d+)\. (.*?)$/gm, '<div style="display:flex;gap:8px;margin:3px 0"><span style="color:var(--text3);min-width:20px;font-family:var(--font-ui);font-size:13px;flex-shrink:0">$1.</span><span>$2</span></div>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code style="background:var(--code-bg);border:1px solid var(--code-border);padding:1px 5px;border-radius:4px;font-family:var(--font-mono);font-size:.87em;color:var(--text)">$1</code>');
}

function CodeBlock({ code, lang, convId }) {
  const [copied, setCopied] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [running, setRunning] = useState(false);

  const copy = () => {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(code).then(()=>{ setCopied(true); setTimeout(()=>setCopied(false),2000); });
    } else {
      // Fallback for non-https / older browsers
      const ta = document.createElement('textarea');
      ta.value = code; ta.style.position='fixed'; ta.style.opacity='0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); setCopied(true); setTimeout(()=>setCopied(false),2000); } catch {}
      document.body.removeChild(ta);
    }
  };

  const run = async () => {
    if (!['python','py'].includes(lang)) return;
    setRunning(true); setRunResult(null);
    try {
      const res = await fetch('/api/run', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ code, convId: convId || null }),
      });
      setRunResult(await res.json());
    } catch(e) { setRunResult({ error: e.message, exitCode:1 }); }
    setRunning(false);
  };

  const canRun = ['python','py'].includes(lang);

  return (
    <div style={{ background:'var(--code-bg)', border:'1px solid var(--code-border)', borderRadius:8, margin:'10px 0', overflow:'hidden', fontFamily:'var(--font-mono)' }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'5px 12px', background:'var(--bg3)', borderBottom:'1px solid var(--code-border)' }}>
        <span style={{ fontSize:11, color:'var(--text3)' }}>{lang||'code'}</span>
        <div style={{ display:'flex', gap:6 }}>
          {canRun && (
            <button onClick={run} disabled={running}
              style={{ fontSize:11, color:running?'var(--text3)':'var(--success)', background:'none', border:'1px solid currentColor', borderRadius:4, padding:'2px 8px', display:'flex', alignItems:'center', gap:4, cursor:running?'not-allowed':'pointer', opacity:running?.6:1 }}>
              {running ? <span className="spin" style={{width:9,height:9,borderRadius:'50%',border:'1.5px solid var(--text3)',borderTopColor:'transparent',display:'block'}}/> : '▶'}
              {running?'Running...':'Run'}
            </button>
          )}
          <button onClick={copy} style={{ fontSize:11, color:copied?'var(--success)':'var(--text3)', background:'none', border:'none', padding:'2px 6px', cursor:'pointer' }}>
            {copied?'✓ Copied':'Copy'}
          </button>
        </div>
      </div>
      <pre style={{ margin:0, padding:'13px 15px', overflowX:'auto', fontSize:12.5, lineHeight:1.65, whiteSpace:'pre-wrap', wordBreak:'break-word', color:'var(--text)' }}
        dangerouslySetInnerHTML={{ __html: hl(code, lang) }} />
      {runResult && (
        <div style={{ borderTop:'1px solid var(--code-border)', padding:'10px 13px', background:'var(--bg2)' }}>
          <div style={{ fontSize:11, color:runResult.exitCode===0?'var(--success)':'var(--danger)', marginBottom:4 }}>
            {runResult.exitCode===0 ? '✓ Exit 0' : `✗ Exit ${runResult.exitCode}`}
          </div>
          {runResult.output && <pre style={{ margin:0, fontSize:12, color:'var(--text)', whiteSpace:'pre-wrap' }}>{runResult.output}</pre>}
          {runResult.error  && <pre style={{ margin:0, fontSize:12, color:'var(--danger)', whiteSpace:'pre-wrap' }}>{runResult.error}</pre>}
        </div>
      )}
    </div>
  );
}

export default function MessageRenderer({ content, convId }) {
  const parts = [];
  const re = /```(\w*)\n?([\s\S]*?)```/g;
  let last=0, m;
  while ((m=re.exec(content))!==null) {
    if (m.index>last) parts.push({type:'text', text:content.slice(last,m.index)});
    parts.push({type:'code', lang:m[1]||'text', code:m[2].trim()});
    last=m.index+m[0].length;
  }
  if (last<content.length) parts.push({type:'text', text:content.slice(last)});

  return (
    <div className="msg-assistant-body">
      {parts.map((p,i) =>
        p.type==='code'
          ? <CodeBlock key={i} code={p.code} lang={p.lang} convId={convId} />
          : <span key={i} style={{whiteSpace:'pre-wrap'}} dangerouslySetInnerHTML={{__html:renderMd(p.text)}} />
      )}
    </div>
  );
}
