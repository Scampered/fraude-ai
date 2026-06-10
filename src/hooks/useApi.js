import { classifyError } from '../constants.js';

export async function callModel(modelId, messages, settings) {
  if (modelId === 'highku') {
    let res;
    try {
      res = await fetch('/api/proxy/ollama', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, model: settings.ollamaModel, baseUrl: settings.ollamaUrl }),
      });
    } catch {
      const err = classifyError('highku', null, '');
      throw Object.assign(new Error(err.body), { fraude: err });
    }
    const data = await res.json();
    if (!res.ok) {
      const err = classifyError('highku', res.status, data.error || '');
      throw Object.assign(new Error(err.body), { fraude: err });
    }
    return data.content;
  }

  if (modelId === 'somenet') {
    if (!settings.groqKey) throw Object.assign(new Error('No key'), { fraude: { title: 'Pro plan required', body: 'Add your Groq API key in Billing to unlock Somenet.', detail: 'Go to Billing in the sidebar to activate the Pro plan.', code: 'AUTH' } });
    const res = await fetch('/api/proxy/groq', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, model: settings.groqModel || 'llama-3.3-70b-versatile', apiKey: settings.groqKey }),
    });
    const data = await res.json();
    if (!res.ok) {
      const err = classifyError('somenet', data._rawStatus || res.status, data.error?.message || JSON.stringify(data));
      throw Object.assign(new Error(err.body), { fraude: err });
    }
    return data.content;
  }

  if (modelId === 'oops') {
    if (!settings.geminiKey) throw Object.assign(new Error('No key'), { fraude: { title: 'Main plan required', body: 'Add your Gemini API key in Billing to unlock Oops 6.7.', detail: 'Go to Billing in the sidebar to activate the Main plan.', code: 'AUTH' } });
    const res = await fetch('/api/proxy/gemini', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, model: settings.geminiModel || 'gemini-3.1-flash-lite', apiKey: settings.geminiKey }),
    });
    const data = await res.json();
    if (!res.ok) {
      const err = classifyError('oops', data._rawStatus || res.status, data.error?.message || JSON.stringify(data));
      throw Object.assign(new Error(err.body), { fraude: err });
    }
    return data.content;
  }

  if (modelId === 'aware') {
    if (!settings.awareKey || !settings.awareUrl) throw Object.assign(new Error('Not configured'), { fraude: { title: 'AWARE not configured', body: 'Set your AWARE API key and base URL in Settings.', detail: 'AWARE requires a group node URL and shared API key. Configure these in Settings → AWARE.', code: 'AUTH' } });
    const res = await fetch('/api/proxy/aware', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, model: settings.awareModel, apiKey: settings.awareKey, baseUrl: settings.awareUrl }),
    });
    const data = await res.json();
    if (!res.ok) {
      const err = classifyError('aware', data._rawStatus || res.status, data.error || JSON.stringify(data));
      throw Object.assign(new Error(err.body), { fraude: err });
    }
    return data.content;
  }

  throw new Error('Unknown model');
}
