import { useState } from 'react';
import { PLANS, MODELS } from '../constants.js';

const Check = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2.5 7l3 3L11.5 4" stroke="var(--success)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

export default function BillingModal({ settings, onSave, onClose }) {
  const [upgrading, setUpgrading] = useState(null);
  const [keyInput, setKeyInput] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const currentPlan = settings.geminiKey ? 'main' : settings.groqKey ? 'pro' : 'free';

  const planOrder = ['free', 'pro', 'max'];
  // Normalise legacy 'main' plan to 'max'
  const normPlan = currentPlan === 'main' ? 'max' : (currentPlan || 'free');

  const handleUpgrade = (planId) => {
    setUpgrading(planId);
    setKeyInput('');
    setError('');
    setSuccess('');
  };

  const handleSubmit = () => {
    const plan = PLANS[upgrading];
    if (!keyInput.trim()) { setError('This field is required.'); return; }
    if (plan.unlockValidate && !plan.unlockValidate(keyInput.trim())) {
      setError(`Invalid key format. Expected: ${plan.unlockPlaceholder}`);
      return;
    }
    const next = { ...settings };
    if (upgrading === 'pro') next.groqKey = keyInput.trim();
    if (upgrading === 'main') { next.geminiKey = keyInput.trim(); if (!next.groqKey) next.groqKey = ''; }
    onSave(next);
    setSuccess(`${plan.label} plan activated.`);
    setTimeout(() => setUpgrading(null), 1400);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.35)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 12, width: 'min(680px,100%)', maxHeight: '90vh', overflowY: 'auto' }}>
        {/* Header */}
        <div style={{ padding: '24px 28px 20px', borderBottom: '1px solid var(--bg-active)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>Plans & Billing</h2>
            <p style={{ fontSize: 13, color: 'var(--text2)' }}>
              Current plan: <span style={{ color: 'var(--accent)', fontWeight: 500 }}>{PLANS[normPlan]?.label || normPlan}</span>
            </p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text2)', fontSize: 18, padding: 4, borderRadius: 6, lineHeight: 1, cursor: 'pointer' }}>✕</button>
        </div>

        {/* Plans grid */}
        <div style={{ padding: '24px 28px', display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>
          {planOrder.map(planId => {
            const plan = PLANS[planId];
            const isCurrent = normPlan === planId;
            const isPast = planOrder.indexOf(planId) < planOrder.indexOf(normPlan);
            const canUpgrade = !isCurrent && !isPast && plan.unlock;

            return (
              <div key={planId} style={{
                background: plan.popular ? 'var(--bg2)' : 'var(--bg)',
                border: `1px solid ${isCurrent ? 'var(--accent)' : plan.popular ? 'var(--border)' : 'var(--bg-active)'}`,
                borderRadius: 10, padding: '20px 18px', position: 'relative', display: 'flex', flexDirection: 'column',
              }}>
                {plan.popular && !isCurrent && (
                  <div style={{ position: 'absolute', top: -10, left: '50%', transform: 'translateX(-50%)', background: 'var(--accent)', color: 'var(--bg)', fontSize: 10, fontWeight: 600, padding: '2px 10px', borderRadius: 20, whiteSpace: 'nowrap', letterSpacing: 0.5 }}>
                    MOST POPULAR
                  </div>
                )}
                {isCurrent && (
                  <div style={{ position: 'absolute', top: -10, left: '50%', transform: 'translateX(-50%)', background: 'var(--accent)22', border: '1px solid var(--accent)', color: 'var(--accent)', fontSize: 10, fontWeight: 600, padding: '2px 10px', borderRadius: 20, whiteSpace: 'nowrap' }}>
                    CURRENT PLAN
                  </div>
                )}

                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>{plan.label}</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 4 }}>
                  <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--text)' }}>{plan.price}</span>
                  <span style={{ fontSize: 12, color: 'var(--text2)' }}>{plan.period}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 16, lineHeight: 1.4 }}>{plan.tagline}</div>

                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 7, marginBottom: 18 }}>
                  {plan.features.map((f, i) => (
                    <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12, color: isPast || isCurrent ? 'var(--text2)' : 'var(--text2)' }}>
                      <span style={{ flexShrink: 0, marginTop: 1 }}><Check /></span>
                      {f}
                    </div>
                  ))}
                </div>

                <button
                  onClick={() => canUpgrade && handleUpgrade(planId)}
                  disabled={isCurrent || isPast}
                  style={{
                    width: '100%', padding: '9px', borderRadius: 7, fontSize: 13, fontWeight: 500,
                    cursor: canUpgrade ? 'pointer' : 'default',
                    background: isCurrent ? 'var(--accent)22' : isPast ? 'transparent' : canUpgrade ? 'var(--accent)' : 'var(--accent)',
                    color: isCurrent ? 'var(--accent)' : isPast ? 'var(--text3)' : '#fff',
                    border: `1px solid ${isCurrent ? 'var(--accent)44' : isPast ? 'var(--bg-active)' : 'var(--accent)'}`,
                    transition: 'opacity .2s',
                    opacity: isPast ? 0.4 : 1,
                  }}>
                  {isCurrent ? 'Current plan' : isPast ? 'Included' : plan.cta}
                </button>
              </div>
            );
          })}
        </div>

        {/* FAQ line */}
        <div style={{ padding: '0 28px 24px' }}>
          <p style={{ fontSize: 11, color: 'var(--text3)', lineHeight: 1.6 }}>
            * API keys are stored locally in your browser and are never sent to our servers. Fraude charges $0 for all plans. Always has. Always will. Probably.
          </p>
        </div>
      </div>

      {/* Payment sheet */}
      {upgrading && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(1,4,9,.7)', zIndex: 210, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, width: 'min(400px,100%)', padding: 28 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>
              Upgrade to {PLANS[upgrading].label}
            </h3>
            <p style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 20, lineHeight: 1.5 }}>
              Enter your {PLANS[upgrading].unlockLabel} to activate this plan.{' '}
              <span style={{ color: 'var(--text3)' }}>{PLANS[upgrading].unlockHint}</span>
            </p>

            <label style={{ display: 'block', fontSize: 12, color: 'var(--text2)', fontWeight: 500, marginBottom: 6 }}>
              {PLANS[upgrading].unlockLabel}
            </label>
            <input
              type="password" value={keyInput}
              onChange={e => { setKeyInput(e.target.value); setError(''); }}
              placeholder={PLANS[upgrading].unlockPlaceholder}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              style={{
                width: '100%', background: 'var(--bg)', border: `1px solid ${error ? 'var(--danger)' : 'var(--border)'}`,
                borderRadius: 7, padding: '9px 12px', color: 'var(--text)', fontSize: 13, fontFamily: 'monospace',
                outline: 'none', marginBottom: error ? 6 : 16,
              }} />
            {error && <p style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 14 }}>{error}</p>}
            {success && <p style={{ fontSize: 12, color: 'var(--success)', marginBottom: 14 }}>{success}</p>}

            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={handleSubmit} style={{
                flex: 1, background: 'var(--accent)', color: '#fff', border: 'none',
                borderRadius: 7, padding: '10px', fontSize: 13, fontWeight: 500, cursor: 'pointer',
              }}>
                Activate plan
              </button>
              <button onClick={() => setUpgrading(null)} style={{
                background: 'none', border: '1px solid var(--border)', color: 'var(--text2)',
                borderRadius: 7, padding: '10px 14px', fontSize: 13, cursor: 'pointer',
              }}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
