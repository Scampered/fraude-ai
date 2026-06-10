const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const multer = require('multer');
const { v4: uuidv4 } = require('uuid');
const { spawn, execSync } = require('child_process');
const { createServer } = require('http');
const { WebSocketServer } = require('ws');

const app = express();
const PORT = 3001;
const MEMORY_ROOT = path.join(__dirname, '..', 'fraude-memory');

app.use(cors());
app.use(express.json({ limit: '50mb' }));
if (!fs.existsSync(MEMORY_ROOT)) fs.mkdirSync(MEMORY_ROOT, { recursive: true });
app.use('/memory', express.static(MEMORY_ROOT));

// ─── Auto-start Ollama silently ───────────────────────────────────────────────
function tryStartOllama() {
  const http = require('http');
  const req = http.get('http://localhost:11434', () => {
    // already running, silent
  });
  req.on('error', () => {
    try {
      const isWin = process.platform === 'win32';
      const proc = spawn('ollama', ['serve'], {
        detached: true,
        stdio: ['ignore', 'ignore', 'ignore'],
        windowsHide: true,
      });
      proc.unref();
    } catch (_) { /* ollama not installed, that's fine */ }
  });
  req.setTimeout(1200);
}
tryStartOllama();

// ─── Conversation helpers ─────────────────────────────────────────────────────
function convDir(id) {
  const d = path.join(MEMORY_ROOT, id);
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  return d;
}
const convMetaPath = id => path.join(convDir(id), '_meta.json');
const convMsgPath  = id => path.join(convDir(id), '_messages.json');
const memPath      = id => path.join(convDir(id), '_memory.json');

// ─── Broadcast helper for sync ────────────────────────────────────────────────
const httpServer = createServer(app);
let wss;
try {
  wss = new WebSocketServer({ server: httpServer });
  wss.on('connection', ws => {
    ws.on('error', () => {});
  });
} catch(_) {}

function broadcast(type, data) {
  if (!wss) return;
  const msg = JSON.stringify({ type, ...data });
  wss.clients.forEach(c => { try { if (c.readyState === 1) c.send(msg); } catch(_){} });
}

// ─── Conversations ────────────────────────────────────────────────────────────
app.get('/api/conversations', (req, res) => {
  try {
    const dirs = fs.readdirSync(MEMORY_ROOT).filter(f => {
      const p = path.join(MEMORY_ROOT, f);
      try { return fs.statSync(p).isDirectory() && !f.startsWith('.'); } catch { return false; }
    });
    const convos = dirs.map(id => {
      try { return JSON.parse(fs.readFileSync(convMetaPath(id), 'utf8')); } catch { return null; }
    }).filter(Boolean).sort((a, b) => b.updatedAt - a.updatedAt);
    res.json(convos);
  } catch { res.json([]); }
});

app.post('/api/conversations', (req, res) => {
  const id = uuidv4();
  const meta = { id, title: req.body.title || 'New chat', createdAt: Date.now(), updatedAt: Date.now(), model: req.body.model || 'oops', messageCount: 0 };
  fs.writeFileSync(convMetaPath(id), JSON.stringify(meta, null, 2));
  fs.writeFileSync(convMsgPath(id), JSON.stringify([], null, 2));
  broadcast('conv_created', { conv: meta });
  res.json(meta);
});

app.get('/api/conversations/:id/messages', (req, res) => {
  try { res.json(JSON.parse(fs.readFileSync(convMsgPath(req.params.id), 'utf8'))); }
  catch { res.json([]); }
});

app.post('/api/conversations/:id/messages', (req, res) => {
  const { id } = req.params;
  const { messages, title } = req.body;
  try {
    fs.writeFileSync(convMsgPath(id), JSON.stringify(messages, null, 2));
    const mp = convMetaPath(id);
    const meta = JSON.parse(fs.readFileSync(mp, 'utf8'));
    meta.updatedAt = Date.now();
    meta.messageCount = messages.length;
    if (title) meta.title = title;
    fs.writeFileSync(mp, JSON.stringify(meta, null, 2));
    broadcast('conv_updated', { conv: meta });
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.delete('/api/conversations/:id', (req, res) => {
  try {
    fs.rmSync(path.join(MEMORY_ROOT, req.params.id), { recursive: true, force: true });
    broadcast('conv_deleted', { id: req.params.id });
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// ─── Files ────────────────────────────────────────────────────────────────────
app.post('/api/conversations/:id/files', (req, res) => {
  const { filename, content } = req.body;
  const safe = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
  fs.writeFileSync(path.join(convDir(req.params.id), safe), content);
  res.json({ ok: true, path: `/memory/${req.params.id}/${safe}`, filename: safe });
});

app.get('/api/conversations/:id/files', (req, res) => {
  try {
    const dir = convDir(req.params.id);
    const files = fs.readdirSync(dir)
      .filter(f => !f.startsWith('_'))
      .map(f => {
        const stat = fs.statSync(path.join(dir, f));
        return { name: f, size: stat.size, createdAt: stat.birthtime, url: `/memory/${req.params.id}/${f}` };
      });
    res.json(files);
  } catch { res.json([]); }
});


// ─── Copy generated output.pdf into conversation memory ──────────────────────
app.post('/api/conversations/:id/pdf', (req, res) => {
  const { sourcePyFile } = req.body;
  const dir = convDir(req.params.id);
  // output.pdf should be in the conv dir (that's where python ran from)
  const pdfSrc = path.join(dir, 'output.pdf');
  if (!fs.existsSync(pdfSrc)) {
    // Also check OS temp dir
    const tmpPdf = path.join(require('os').tmpdir(), 'output.pdf');
    if (fs.existsSync(tmpPdf)) {
      const destName = `output_${Date.now()}.pdf`;
      const dest = path.join(dir, destName);
      fs.copyFileSync(tmpPdf, dest);
      return res.json({ ok: true, pdfUrl: `/memory/${req.params.id}/${destName}`, filename: destName });
    }
    return res.status(404).json({ error: 'output.pdf not found', searched: [pdfSrc] });
  }
  const destName = `output_${Date.now()}.pdf`;
  const dest = path.join(dir, destName);
  fs.copyFileSync(pdfSrc, dest);
  // Clean up the original so it doesn't clutter
  try { fs.unlinkSync(pdfSrc); } catch {}
  res.json({ ok: true, pdfUrl: `/memory/${req.params.id}/${destName}`, filename: destName });
});
// ─── Upload ───────────────────────────────────────────────────────────────────
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, convDir(req.params.id)),
  filename: (req, file, cb) => cb(null, file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_')),
});
const upload = multer({ storage, limits: { fileSize: 20 * 1024 * 1024 } });

app.post('/api/conversations/:id/upload', upload.single('file'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file' });
  let content = null;
  const textExts = ['.txt', '.py', '.js', '.jsx', '.ts', '.json', '.csv', '.md', '.html', '.css', '.sql'];
  const ext = path.extname(req.file.originalname).toLowerCase();
  if (textExts.includes(ext)) { try { content = fs.readFileSync(req.file.path, 'utf8'); } catch {} }
  res.json({ ok: true, filename: req.file.filename, originalname: req.file.originalname, size: req.file.size, url: `/memory/${req.params.id}/${req.file.filename}`, content, ext });
});

// ─── Memory notes ─────────────────────────────────────────────────────────────
app.get('/api/conversations/:id/memory', (req, res) => {
  try { res.json(JSON.parse(fs.readFileSync(memPath(req.params.id), 'utf8'))); } catch { res.json([]); }
});
app.post('/api/conversations/:id/memory', (req, res) => {
  fs.writeFileSync(memPath(req.params.id), JSON.stringify(req.body.memories, null, 2));
  res.json({ ok: true });
});

// ─── Custom skills CRUD ───────────────────────────────────────────────────────
const skillsPath = path.join(MEMORY_ROOT, '_custom_skills.json');
function loadSkills() { try { return JSON.parse(fs.readFileSync(skillsPath, 'utf8')); } catch { return []; } }
function saveSkills(skills) { fs.writeFileSync(skillsPath, JSON.stringify(skills, null, 2)); }

app.get('/api/skills', (req, res) => res.json(loadSkills()));
app.post('/api/skills', (req, res) => {
  const { id, name, icon, prompt, imports, slash } = req.body;
  const skills = loadSkills();
  const existing = skills.findIndex(s => s.id === id);
  const skill = { id: id || uuidv4().slice(0,8), name, icon: icon || '⚡', prompt, imports: imports || [], slash: slash || name.toLowerCase().replace(/\s+/g,''), custom: true };
  if (existing >= 0) skills[existing] = skill; else skills.push(skill);
  saveSkills(skills);
  res.json(skill);
});
app.delete('/api/skills/:id', (req, res) => {
  const skills = loadSkills().filter(s => s.id !== req.params.id);
  saveSkills(skills);
  res.json({ ok: true });
});

// ─── Run Python script (with auto-install on ModuleNotFoundError) ─────────────
function findPython() {
  // Try executables in order until one works
  const candidates = process.platform === 'win32'
    ? ['python', 'py', 'python3']
    : ['python3', 'python'];
  for (const cmd of candidates) {
    try {
      const { execSync } = require('child_process');
      execSync(`${cmd} --version`, { stdio: 'ignore', timeout: 3000 });
      return cmd;
    } catch {}
  }
  return 'python'; // last resort
}
const PY_CMD = findPython();

function runPyFile(tmpFile, dir, res, attempt) {
  const py = PY_CMD;
  let output = '', errOutput = '';
  let proc;
  try {
    proc = spawn(py, [tmpFile], { cwd: dir, windowsHide: true });
  } catch(spawnErr) {
    try { fs.unlinkSync(tmpFile); } catch {}
    return res.json({ output: '', error: `Could not start Python: ${spawnErr.message}`, exitCode: 1 });
  }
  proc.on('error', err => {
    clearTimeout(timeout);
    try { fs.unlinkSync(tmpFile); } catch {}
    res.json({ output: '', error: `Python not found: ${err.message}. Try: pip install python or check PATH.`, exitCode: 1 });
  });
  const timeout = setTimeout(() => { proc.kill(); output += '\n[Timed out after 30s]'; }, 30000);
  proc.stdout.on('data', d => { output += d.toString(); });
  proc.stderr.on('data', d => { errOutput += d.toString(); });
  proc.on('close', code => {
    clearTimeout(timeout);
    // Auto-install missing module on first attempt
    const missingMatch = errOutput.match(/No module named '([^']+)'/);
    if (missingMatch && attempt < 2) {
      const pkg = missingMatch[1].split('.')[0];
      const pipProc = spawn(PY_CMD, ['-m', 'pip', 'install', pkg, '--quiet'], { cwd: dir });
      let pipOut = '', pipErr = '';
      pipProc.stdout.on('data', d => { pipOut += d; });
      pipProc.stderr.on('data', d => { pipErr += d; });
      pipProc.on('close', pipCode => {
        if (pipCode === 0) {
          runPyFile(tmpFile, dir, res, attempt + 1);
        } else {
          try { fs.unlinkSync(tmpFile); } catch {}
          res.json({ output: '', error: `Auto-install of '${pkg}' failed:\n${pipErr}`, exitCode: 1, autoInstallFailed: pkg });
        }
      });
    } else {
      try { fs.unlinkSync(tmpFile); } catch {}
      res.json({ output: output.trim(), error: errOutput.trim(), exitCode: code });
    }
  });
}

app.post('/api/run', (req, res) => {
  const { code, convId } = req.body;
  if (!code) return res.status(400).json({ error: 'No code' });
  // Always use OS temp for the script file itself — never write to fraude root
  const tmpDir = require('os').tmpdir();
  const tmpFile = path.join(tmpDir, `_fraude_run_${Date.now()}.py`);
  // Use conv dir as cwd so relative file paths work (output.pdf etc)
  const cwd = convId ? convDir(convId) : tmpDir;
  fs.writeFileSync(tmpFile, code, 'utf8');
  runPyFile(tmpFile, cwd, res, 0);
});


// ─── Run arbitrary terminal command (user must confirm on client) ─────────────
app.post('/api/terminal', (req, res) => {
  const { command } = req.body;
  if (!command) return res.status(400).json({ error: 'No command' });
  const shell = process.platform === 'win32' ? 'cmd' : '/bin/sh';
  const args  = process.platform === 'win32' ? ['/c', command] : ['-c', command];
  let output = '', errOutput = '';
  const proc = spawn(shell, args, { cwd: require('os').homedir() });
  const timeout = setTimeout(() => { proc.kill(); output += '\n[Timed out after 60s]'; }, 60000);
  proc.stdout.on('data', d => { output += d.toString(); });
  proc.stderr.on('data', d => { errOutput += d.toString(); });
  proc.on('close', code => {
    clearTimeout(timeout);
    res.json({ output: output.trim(), error: errOutput.trim(), exitCode: code });
  });
});
// ─── Zip code files ───────────────────────────────────────────────────────────
app.get('/api/conversations/:id/zip', async (req, res) => {
  const dir = convDir(req.params.id);
  const files = fs.readdirSync(dir).filter(f => !f.startsWith('_'));
  if (files.length === 0) return res.status(404).json({ error: 'No files to zip' });

  const zipName = `fraude_files_${req.params.id.slice(0,8)}.zip`;
  const zipPath = path.join(require('os').tmpdir(), zipName);

  // Use python or system zip
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const script = `
import zipfile, os
dir = ${JSON.stringify(dir)}
out = ${JSON.stringify(zipPath)}
files = [f for f in os.listdir(dir) if not f.startswith('_')]
with zipfile.ZipFile(out, 'w') as z:
    for f in files:
        z.write(os.path.join(dir, f), f)
print('ok')
`.trim();

  const tmpPy = path.join(require('os').tmpdir(), '_zipper.py');
  fs.writeFileSync(tmpPy, script);

  const proc = spawn(py, [tmpPy]);
  let err = '';
  proc.stderr.on('data', d => err += d);
  proc.on('close', () => {
    try { fs.unlinkSync(tmpPy); } catch {}
    if (!fs.existsSync(zipPath)) return res.status(500).json({ error: err || 'Zip failed' });
    res.download(zipPath, zipName, () => { try { fs.unlinkSync(zipPath); } catch {} });
  });
});


// ─── DuckDuckGo web search ────────────────────────────────────────────────────
app.get('/api/search', async (req, res) => {
  const q = req.query.q;
  if (!q) return res.status(400).json({ error: 'No query' });
  try {
    // DuckDuckGo Instant Answer API (no key needed)
    const r = await fetch(`https://api.duckduckgo.com/?q=${encodeURIComponent(q)}&format=json&no_html=1&skip_disambig=1`);
    const d = await r.json();
    const results = [
      ...(d.RelatedTopics||[]).slice(0,6).map(t=>({ title: t.Text?.split(' - ')[0]||'', snippet: t.Text||'', url: t.FirstURL||'' })),
      d.AbstractText ? { title: d.Heading||q, snippet: d.AbstractText, url: d.AbstractURL||'' } : null,
    ].filter(Boolean).slice(0,5);
    res.json({ results, abstract: d.AbstractText||'', heading: d.Heading||'' });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// ─── Projects API ─────────────────────────────────────────────────────────────
const projectsPath = path.join(MEMORY_ROOT, '_projects.json');
function loadProjects() { try { return JSON.parse(fs.readFileSync(projectsPath,'utf8')); } catch { return []; } }
function saveProjects(p) { fs.writeFileSync(projectsPath, JSON.stringify(p,null,2)); }

app.get('/api/projects', (req, res) => res.json(loadProjects()));

app.post('/api/projects', (req, res) => {
  const { name, color, emoji } = req.body;
  const project = { id: require('crypto').randomUUID().slice(0,8), name, color: color||'#4A9EFF', emoji: emoji||'📁', createdAt: Date.now(), convIds: [] };
  const projects = [...loadProjects(), project];
  saveProjects(projects); broadcast('projects_updated', { projects });
  res.json(project);
});

app.patch('/api/projects/:id', (req, res) => {
  const projects = loadProjects().map(p => p.id===req.params.id ? {...p, ...req.body} : p);
  saveProjects(projects); broadcast('projects_updated', { projects });
  res.json({ ok: true });
});

app.delete('/api/projects/:id', (req, res) => {
  const projects = loadProjects().filter(p => p.id!==req.params.id);
  saveProjects(projects); broadcast('projects_updated', { projects });
  res.json({ ok: true });
});

// Add/remove conv from project
app.post('/api/projects/:id/conversations', (req, res) => {
  const { convId, remove } = req.body;
  const projects = loadProjects().map(p => {
    if (p.id!==req.params.id) return p;
    const convIds = remove ? p.convIds.filter(c=>c!==convId) : [...new Set([...p.convIds, convId])];
    return {...p, convIds};
  });
  saveProjects(projects); broadcast('projects_updated', { projects });
  res.json({ ok: true });
});

// ─── GitHub update check ──────────────────────────────────────────────────────
app.get('/api/update-check', async (req, res) => {
  try {
    const r = await fetch('https://api.github.com/repos/Scampered/fraude-ai/releases/latest', {
      headers: { 'User-Agent': 'fraude-local' }
    });
    if (!r.ok) return res.json({ hasUpdate: false });
    const d = await r.json();
    // Compare with local version from package.json
    const pkg = JSON.parse(fs.readFileSync(path.join(__dirname,'..','package.json'),'utf8'));
    const latest = d.tag_name?.replace('v','') || '0';
    const current = pkg.version || '3.0.0';
    res.json({ hasUpdate: latest > current, latestVersion: d.tag_name, currentVersion: current, releaseUrl: d.html_url, publishedAt: d.published_at });
  } catch(e) { res.json({ hasUpdate: false, error: e.message }); }
});


// ─── FraudeCode file storage ──────────────────────────────────────────────────
const CODE_DIR = path.join(MEMORY_ROOT, '..', 'fraude-code-memory');
if (!fs.existsSync(CODE_DIR)) fs.mkdirSync(CODE_DIR, { recursive: true });

app.get('/api/code/files', (req, res) => {
  try {
    const files = fs.readdirSync(CODE_DIR)
      .filter(f => !f.startsWith('_') && !f.startsWith('.'))
      .map(f => {
        const stat = fs.statSync(path.join(CODE_DIR, f));
        let content = null;
        try { content = fs.readFileSync(path.join(CODE_DIR, f), 'utf8'); } catch {}
        return { name: f, size: stat.size, content };
      });
    res.json({ files });
  } catch { res.json({ files: [] }); }
});

app.post('/api/code/files', (req, res) => {
  const { filename, content } = req.body;
  if (!filename || content === undefined) return res.status(400).json({ error: 'filename and content required' });
  const safe = filename.replace(/[^a-zA-Z0-9._\-\/]/g, '_').replace(/\.\./g, '_');
  const dest = path.join(CODE_DIR, safe);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, content);
  res.json({ ok: true, path: dest });
});

app.get('/api/code/files/:filename', (req, res) => {
  const fp = path.join(CODE_DIR, req.params.filename.replace(/\.\./g,'_'));
  if (!fs.existsSync(fp)) return res.status(404).json({ error: 'Not found' });
  res.download(fp);
});

// ─── Style profiles API ────────────────────────────────────────────────────────
const PROFILE_DIR = path.join(__dirname, '..', 'style_profiles');
if (!fs.existsSync(PROFILE_DIR)) fs.mkdirSync(PROFILE_DIR, { recursive: true });

app.get('/api/profiles', (req, res) => {
  try {
    const profiles = fs.readdirSync(PROFILE_DIR)
      .filter(f => f.endsWith('.json'))
      .map(f => {
        try {
          const p = JSON.parse(fs.readFileSync(path.join(PROFILE_DIR, f), 'utf8'));
          return { name: p.name, messageCount: p.message_count || 0, created: p.created };
        } catch { return null; }
      }).filter(Boolean);
    res.json({ profiles });
  } catch { res.json({ profiles: [] }); }
});

app.get('/api/profiles/:name/system-prompt', (req, res) => {
  const fp = path.join(PROFILE_DIR, `${req.params.name.replace(/[^a-zA-Z0-9_-]/g,'_')}.json`);
  if (!fs.existsSync(fp)) return res.status(404).json({ error: 'Profile not found' });
  try {
    const p = JSON.parse(fs.readFileSync(fp, 'utf8'));
    res.json({ systemPrompt: p.system_prompt || '', name: p.name });
  } catch(e) { res.status(500).json({ error: e.message }); }
});



// ─── Directory browser (for FraudeCode panel) ─────────────────────────────────
app.post('/api/browse-dir', async (req, res) => {
  // Server-side directory listing — returns selected path
  const start = req.body.start || require('os').homedir();
  // We can't open a real GUI from server, so return the fraude folder as suggestion
  const fraude_dir = path.join(__dirname, '..');
  res.json({ path: fraude_dir, suggestion: fraude_dir });
});

// ─── Download zip (serve as file download) ────────────────────────────────────
app.get('/api/download-zip', (req, res) => {
  const zipPath = req.query.path;
  if (!zipPath || !fs.existsSync(zipPath)) {
    return res.status(404).json({ error: 'File not found' });
  }
  res.download(zipPath);
});

// ─── Launch FraudeCode in a new terminal window ───────────────────────────────
app.post('/api/launch-terminal', (req, res) => {
  const { dir } = req.body;
  const workDir = dir || path.join(__dirname, '..');
  const scriptPath = path.join(workDir, 'fraudecode.py');

  let proc;
  try {
    if (process.platform === 'win32') {
      // Windows: open new cmd window
      proc = spawn('cmd', ['/c', 'start', 'cmd', '/k',
        `cd /d "${workDir}" && python fraudecode.py`
      ], { detached: true, stdio: 'ignore', shell: true });
    } else if (process.platform === 'darwin') {
      // macOS: open Terminal
      const script = `tell application "Terminal" to do script "cd '${workDir}' && python3 fraudecode.py"`;
      proc = spawn('osascript', ['-e', script], { detached: true, stdio: 'ignore' });
    } else {
      // Linux: try common terminals
      const terminals = ['gnome-terminal', 'xterm', 'konsole', 'xfce4-terminal'];
      for (const t of terminals) {
        try {
          proc = spawn(t, ['--', 'bash', '-c', `cd '${workDir}' && python3 fraudecode.py; read`],
            { detached: true, stdio: 'ignore' });
          break;
        } catch {}
      }
    }
    if (proc) proc.unref();
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ─── Proxy: Ollama ────────────────────────────────────────────────────────────
app.post('/api/proxy/ollama', async (req, res) => {
  const { messages, model, baseUrl } = req.body;
  try {
    const r = await fetch(`${baseUrl || 'http://localhost:11434'}/api/chat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: model || 'llama3.2', messages, stream: false }),
    });
    const d = await r.json();
    if (!r.ok) return res.status(500).json({ error: d.error || 'Ollama error', status: 500 });
    res.json({ content: d.message.content });
  } catch (e) {
    res.status(503).json({ error: `Cannot connect to Ollama: ${e.message}`, status: 503 });
  }
});

// ─── Proxy: Groq ──────────────────────────────────────────────────────────────
app.post('/api/proxy/groq', async (req, res) => {
  const { messages, model, apiKey } = req.body;
  try {
    const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
      body: JSON.stringify({ model: model || 'llama3-8b-8192', messages, max_tokens: 2048 }),
    });
    const d = await r.json();
    if (!r.ok) return res.status(r.status).json({ ...d, _rawStatus: r.status });
    res.json({ content: d.choices[0].message.content });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// ─── Proxy: Gemini ────────────────────────────────────────────────────────────
app.post('/api/proxy/gemini', async (req, res) => {
  const { messages, model, apiKey } = req.body;
  const contents = messages.filter(m => m.role !== 'system').map(m => ({
    role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }],
  }));
  const sys = messages.find(m => m.role === 'system');
  const body = { contents };
  if (sys) body.system_instruction = { parts: [{ text: sys.content }] };
  try {
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model || 'gemini-1.5-flash'}:generateContent?key=${apiKey}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const d = await r.json();
    if (!r.ok) return res.status(r.status).json({ ...d, _rawStatus: r.status });
    res.json({ content: d.candidates[0].content.parts[0].text });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// ─── Proxy: AWARE (OpenAI-compatible group node) ──────────────────────────────
app.post('/api/proxy/aware', async (req, res) => {
  const { messages, model, apiKey, baseUrl } = req.body;
  if (!apiKey || !baseUrl) return res.status(401).json({ error: 'AWARE not configured — set API key and base URL in Settings.' });
  const url = baseUrl.replace(/\/$/, '') + (baseUrl.includes('/v1') ? '' : '/v1') + '/chat/completions';
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
      body: JSON.stringify({ model: model || 'AWARE-I', messages, max_tokens: 2048 }),
    });
    const d = await r.json();
    if (!r.ok) return res.status(r.status).json({ ...d, _rawStatus: r.status });
    res.json({ content: d.choices[0].message.content });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// ─── Settings sync endpoint ───────────────────────────────────────────────────
const settingsPath = path.join(MEMORY_ROOT, '_settings.json');
app.get('/api/settings', (req, res) => {
  try { res.json(JSON.parse(fs.readFileSync(settingsPath, 'utf8'))); } catch { res.json({}); }
});
app.post('/api/settings', (req, res) => {
  fs.writeFileSync(settingsPath, JSON.stringify(req.body, null, 2));
  res.json({ ok: true });
});

httpServer.listen(PORT, () => {
  console.log(`\n🔵 Fraude  →  http://localhost:5173`);
  console.log(`📁 Memory  →  ${MEMORY_ROOT}\n`);
});
