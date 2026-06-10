export const MODELS = {
  highku: {
    id: 'highku', label: 'HighKu', sublabel: 'Local Ollama', version: '0.5',
    color: '#a371f7', plan: 'free',
    thinkingMsg: 'Thinking very hard...',
    delay: [4000, 10000],
    errors: {
      connect:  { title: 'HighKu is unreachable', body: 'Ollama isn\'t running or isn\'t installed.', detail: 'Fraude tried to connect to http://localhost:11434 and got no response. Make sure Ollama is installed from ollama.com and running.', code: 'OFFLINE' },
      model:    { title: 'Model not found', body: 'That model isn\'t installed locally.', detail: 'Run: ollama pull llama3.2 in your terminal to download it.', code: 'BADMODEL' },
      generic:  { title: 'HighKu encountered an error', body: 'Something went wrong with the local model.', detail: null, code: 'ERR' },
    },
  },
  somenet: {
    id: 'somenet', label: 'Somenet', sublabel: 'Groq', version: '0.6',
    color: '#3fb950', plan: 'pro',
    thinkingMsg: 'Processing...',
    delay: [600, 1400],
    errors: {
      rateLimit: { title: 'Rate limit reached', body: 'Groq free tier rate limit hit. Try again in a moment.', detail: 'The Groq API returned HTTP 429. Free tier has per-minute request limits. Wait ~15 seconds and retry.', code: 'RATE', clearAfter: 15000 },
      quota:     { title: 'Daily quota reached', body: "Daily usage limit hit. Come back tomorrow.", detail: 'Groq free tier has a daily token quota. It has been fully consumed for today. Upgrade your Groq plan or wait until tomorrow.', code: 'QUOTA', clearAfter: 30000 },
      auth:      { title: 'Authentication failed', body: 'Invalid Groq API key.', detail: 'The API key in Settings was rejected by Groq. Double-check it at console.groq.com → API Keys.', code: 'AUTH' },
      generic:   { title: 'Somenet error', body: 'Groq returned an error.', detail: null, code: 'ERR' },
    },
  },
  oops: {
    id: 'oops', label: 'Oops 0.7', sublabel: 'Gemini', version: '0.7',
    color: '#4A9EFF', plan: 'max',
    thinkingMsg: 'Processing...',
    delay: [400, 900],
    errors: {
      rateLimit: { title: 'Rate limit reached', body: "Per-minute rate limit hit. Wait ~60 seconds.", detail: 'Gemini returned HTTP 429. The free tier has strict per-minute quotas. Wait 60 seconds before retrying.', code: 'RATE', clearAfter: 60000 },
      quota:     { title: 'Daily limit reached', body: "Daily Gemini quota exhausted.", detail: 'Your free Gemini API daily quota is fully used. It resets at midnight Pacific Time. Consider upgrading at aistudio.google.com.', code: 'QUOTA', clearAfter: 60000 },
      auth:      { title: 'Authentication failed', body: 'Invalid Gemini API key.', detail: 'The API key was rejected. Check it at aistudio.google.com → API Keys.', code: 'AUTH' },
      generic:   { title: 'Oops — something went wrong', body: 'Gemini returned an error.', detail: null, code: 'ERR' },
    },
  },
  aware: {
    id: 'aware', label: 'AWARE', sublabel: 'Group Node', version: '0.7',
    color: '#d29922', plan: 'max',
    thinkingMsg: 'Routing through AWARE node...',
    delay: [500, 1200],
    errors: {
      auth:    { title: 'AWARE not configured', body: 'Set your AWARE API key and base URL in Settings.', detail: 'AWARE uses an OpenAI-compatible API. You need the group shared API key and the node base URL (e.g. http://your-server:8000).', code: 'AUTH' },
      connect: { title: 'AWARE node unreachable', body: 'Cannot connect to the AWARE node.', detail: 'Check that the base URL in Settings is correct and the node is running.', code: 'OFFLINE' },
      generic: { title: 'AWARE error', body: 'The AWARE node returned an error.', detail: null, code: 'ERR' },
    },
  },
};

export const PLANS = {
  free: {
    id: 'free', label: 'Free', price: '$0', period: '/month',
    tagline: 'Get started with HighKu',
    features: ['HighKu (Local Ollama)', 'Conversation history', 'File uploads', 'Memory folder', 'Run Python scripts'],
    unlock: null, models: ['highku'], cta: 'Current plan',
  },
  pro: {
    id: 'pro', label: 'Pro', price: '$0', period: '/month',
    tagline: 'Unlock Somenet for faster responses',
    features: ['Everything in Free', 'Somenet 0.6 (Groq API)', 'FraudeCode (Pro)', 'Faster responses'],
    unlock: 'groqKey', unlockLabel: 'Groq API Key', unlockPlaceholder: 'gsk_...',
    unlockHint: 'Your Groq API key is your payment method.',
    unlockHintLink: { href: 'https://console.groq.com/keys', label: 'console.groq.com/keys' },
    unlockValidate: (k) => k.startsWith('gsk_'),
    models: ['highku', 'somenet'], cta: 'Upgrade to Pro', popular: false,
  },
  max: {
    id: 'max', label: 'Max', price: '$00', period: '/month',
    tagline: 'Full access to all models',
    features: ['Everything in Pro', 'Oops 0.7 (Gemini)', 'FraudeCode Multi-Agent', 'AWARE Group Node'],
    unlock: 'geminiKey', unlockLabel: 'Gemini API Key', unlockPlaceholder: 'AIza...',
    unlockHint: 'Your Gemini API key is your payment method.',
    unlockHintLink: { href: 'https://aistudio.google.com/api-keys', label: 'aistudio.google.com/api-keys' },
    unlockValidate: (k) => k.startsWith('AIza'),
    models: ['highku', 'somenet', 'oops', 'aware'], cta: 'Upgrade to Max', popular: true,
  },
};

export const BUILTIN_SKILLS = [
  { id: 'code',  name: 'Code Generator', icon: '</>',  slash: 'code',  imports: [], prompt: 'You are a coding assistant. Generate clean, complete, working code with comments. Always specify the language in triple-backtick code blocks with the language name. Include usage examples.' },
  { id: 'excel', name: 'Excel Editor',   icon: '⊞',    slash: 'excel', imports: ['openpyxl','pandas'], prompt: 'You are an Excel/spreadsheet assistant. Generate complete, working Python code using openpyxl and pandas (pip install openpyxl pandas). Always include a runnable main() function with clear comments.' },
  { id: 'pdf',   name: 'PDF Maker',      icon: '⬡',    slash: 'pdf',   imports: ['fpdf2'], prompt: 'You are a PDF creation assistant. Generate complete, working Python code using fpdf2 (pip install fpdf2). Use: from fpdf import FPDF. Always include a runnable main() function.' },
  { id: 'essay', name: 'Essay Writer',   icon: '✍',    slash: 'essay', imports: [], prompt: 'You are an essay writing assistant. Write well-structured essays with a clear introduction, body paragraphs, and conclusion. Use markdown headings.' },
  { id: 'data',  name: 'Data Analyser',  icon: '∿',    slash: 'data',  imports: ['pandas','matplotlib','numpy'], prompt: 'You are a data analysis assistant. Generate complete, working Python code using pandas, matplotlib, numpy. Include data loading, analysis, and visualisation with a runnable main().' },
  { id: 'web',   name: 'Web Scraper',    icon: '⌗',    slash: 'web',   imports: ['requests','beautifulsoup4'], prompt: 'You are a web scraping assistant. Generate complete, working Python code using requests and BeautifulSoup4. Handle errors gracefully, include a runnable main().' },
  { id: 'sql',   name: 'SQL Helper',     icon: '⛁',    slash: 'sql',   imports: ['sqlite3'], prompt: 'You are a SQL assistant. Write correct SQL queries and Python code using sqlite3. Always explain what queries do and include working examples.' },
  { id: 'api',   name: 'API Builder',    icon: '⇌',    slash: 'api',   imports: ['flask'], prompt: 'You are an API development assistant. Generate complete, working Python Flask APIs (pip install flask). Include all routes, error handling, and example curl commands.' },
];

export const STEPS = {
  think:  ['Thinking...', 'Analysing your request...', 'Processing...'],
  read:   ['Reading uploaded files...', 'Parsing document content...'],
  memory: ['Checking memory...', 'Recalling previous context...'],
  plan:   ['Planning response...', 'Preparing output...'],
  code:   ['Generating code...', 'Writing implementation...'],
  write:  ['Writing response...', 'Generating output...'],
  file:   ['Saving to memory...', 'Creating file...'],
  search: ['Searching the web...', 'Fetching results...'],
};

export function randFrom(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
export function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

export function classifyError(modelId, status, body) {
  const m = MODELS[modelId];
  if (!m?.errors) return { title: 'Error', body: String(body), code: 'ERR' };
  if (modelId === 'highku') {
    if (!status || status === 503) return m.errors.connect;
    if (body?.includes('model') || body?.includes('not found')) return m.errors.model;
    return m.errors.generic;
  }
  if (status === 429) return m.errors.rateLimit || m.errors.generic;
  if (status === 402 || (body && body.toLowerCase?.().includes('quota'))) return m.errors.quota || m.errors.generic;
  if (status === 401 || status === 403) return m.errors.auth || m.errors.generic;
  return { ...m.errors.generic, detail: body };
}

export const FRAUDE_SELF_KNOWLEDGE = `You are Fraude, a locally-hosted AI assistant.

IDENTITY: You are Fraude — not Claude, ChatGPT or any commercial AI. You run at http://localhost:5173.

CAPABILITIES: Chat, Python code generation + auto-run, PDF creation (auto-executed, preview shown), Excel/spreadsheet files, web scraping, data analysis, SQL, Flask APIs, web search (search skill), personality cloning from .prf profiles or uploaded text, memory notes, file uploads, cross-chat context, FraudeCode (separate coding environment).

SKILLS: Type /skillname or they auto-activate. Multiple skills active at once. Skills inject specialised system prompts.

STYLE PROFILES: Users can import .prf files from ChatStyleTrainer. These contain a system prompt that makes you talk like a specific person.

LIMITS: Cannot browse web unless search skill active. PDF needs fpdf2/reportlab (auto-installed). HighKu (Ollama) is slower. Knowledge cutoff varies by model.

BEHAVIOUR: For vague/short messages, ask for clarification briefly. Don't generate code for "test" or similar.`;

export function detectAutoSkills(text, allSkills) {
  const t = text.toLowerCase();
  const find = id => allSkills?.find(s=>s.id===id);
  const active = [];
  if (/\bpdf\b|\breport\b/.test(t)) { const s=find('pdf'); if(s) active.push(s); }
  if (/excel|spreadsheet|\.xlsx/.test(t)) { const s=find('excel'); if(s) active.push(s); }
  if (/personality.*clone|clone.*personality|write like|sound like|chat style|mimic/i.test(t)) { const s=find('clone'); if(s) active.push(s); }
  if (/web scrape|scrape.*web/i.test(t)) { const s=find('web'); if(s) active.push(s); }
  if (/search.*web|look.*online|current.*event|latest.*news|recent/i.test(t)) { const s=find('search'); if(s) active.push(s); }
  return active;
}
