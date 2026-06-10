import { useState } from 'react';

// Quiz modal - Claude-style multi-choice before sending
// Used for personality cloning and any other guided input

const PERSONALITY_QUIZ = {
  title: 'Personality Clone Setup',
  steps: [
    {
      id: 'who',
      question: 'Who would you like to clone?',
      type: 'choice',
      options: ['Myself', 'A friend / family member', 'A public figure', 'A fictional character', 'Other'],
    },
    {
      id: 'purpose',
      question: 'What should the cloned persona do?',
      type: 'choice',
      options: [
        'Write messages / replies in their style',
        'Write essays / long-form content in their style',
        'Answer questions as them',
        'Have a full conversation as them',
      ],
    },
    {
      id: 'data',
      question: 'How will you provide their writing style?',
      type: 'choice',
      options: [
        'I\'ll paste some sample messages below',
        'I\'ll upload a chat export file',
        'I\'ll describe their style manually',
        'I have a .prf profile file from ChatStyleTrainer',
      ],
    },
    {
      id: 'sample',
      question: 'Paste sample messages or describe the style:',
      type: 'textarea',
      placeholder: 'e.g. "hey!! omg that\'s so funny lol\nngl i think we should just go for it tbh\nanyway talk later x"',
    },
    {
      id: 'name',
      question: "What's the name of the person being cloned? (optional)",
      type: 'text',
      placeholder: 'e.g. Alex, Dad, or leave blank',
    },
  ],
};

export default function QuizModal({ onSubmit, onClose, type = 'personality' }) {
  const quiz = PERSONALITY_QUIZ;
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});

  const current = quiz.steps[step];
  const total = quiz.steps.length;
  const isLast = step === total - 1;

  const setAnswer = (val) => setAnswers(p => ({ ...p, [current.id]: val }));
  const answer = answers[current.id] || '';
  const canNext = answer && String(answer).trim().length > 0;

  const next = () => {
    if (isLast) {
      // Build the instruction string to prepend to the user's message
      const who = answers.who || 'a person';
      const name = answers.name ? answers.name : who;
      const purpose = answers.purpose || 'write in their style';
      const sample = answers.sample || '';
      const dataMethod = answers.data || '';
      const instruction = `[Personality Clone Request]
Clone target: ${name}
Purpose: ${purpose}
Style data method: ${dataMethod}
${sample ? `Sample messages / style description:\n${sample}` : ''}

Please respond and write entirely in ${name}'s style, matching their vocabulary, sentence length, punctuation habits, tone, and personality as shown above.`;
      onSubmit(instruction);
    } else {
      setStep(s => s + 1);
    }
  };

  const skip = () => {
    if (isLast) onClose();
    else setStep(s => s + 1);
  };

  return (
    <div className="quiz-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="quiz-card">
        {/* Header */}
        <div style={{ padding:'20px 22px 16px', borderBottom:'1px solid var(--border-sub)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <div>
            <div style={{ fontSize:15, fontWeight:600, color:'var(--text)', fontFamily:'var(--font-ui)' }}>{quiz.title}</div>
            <div style={{ fontSize:11, color:'var(--text3)', marginTop:2 }}>Step {step+1} of {total}</div>
          </div>
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            {/* Progress dots */}
            <div style={{ display:'flex', gap:4 }}>
              {quiz.steps.map((_,i) => (
                <div key={i} style={{ width:6, height:6, borderRadius:'50%', background: i<=step ? 'var(--accent)' : 'var(--border)' }} />
              ))}
            </div>
            <button onClick={onClose} style={{ color:'var(--text3)', background:'none', border:'none', cursor:'pointer', fontSize:18, padding:4 }}>✕</button>
          </div>
        </div>

        {/* Question */}
        <div style={{ padding:'20px 22px' }}>
          <div style={{ fontSize:16, fontWeight:500, color:'var(--text)', fontFamily:'var(--font-serif)', marginBottom:16, lineHeight:1.4 }}>
            {current.question}
          </div>

          {current.type === 'choice' && (
            <div>
              {current.options.map((opt, i) => (
                <div key={opt} className={`quiz-option${answer === opt ? ' selected' : ''}`} onClick={() => setAnswer(opt)}>
                  <div className="quiz-num">{i+1}</div>
                  <span style={{ fontSize:14, color:'var(--text)', fontFamily:'var(--font-ui)' }}>{opt}</span>
                </div>
              ))}
            </div>
          )}

          {current.type === 'textarea' && (
            <textarea value={answer} onChange={e => setAnswer(e.target.value)}
              placeholder={current.placeholder} rows={5}
              style={{ width:'100%', background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, padding:'10px 13px', color:'var(--text)', fontSize:13, fontFamily:'var(--font-ui)', outline:'none', resize:'none', lineHeight:1.6 }}
              onFocus={e=>e.target.style.borderColor='var(--accent)'} onBlur={e=>e.target.style.borderColor='var(--border)'} />
          )}

          {current.type === 'text' && (
            <input value={answer} onChange={e => setAnswer(e.target.value)}
              placeholder={current.placeholder}
              style={{ width:'100%', background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, padding:'10px 13px', color:'var(--text)', fontSize:13, fontFamily:'var(--font-ui)', outline:'none' }}
              onFocus={e=>e.target.style.borderColor='var(--accent)'} onBlur={e=>e.target.style.borderColor='var(--border)'}
              onKeyDown={e=>e.key==='Enter'&&canNext&&next()} />
          )}
        </div>

        {/* Footer */}
        <div style={{ padding:'0 22px 20px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <button onClick={skip}
            style={{ fontSize:13, color:'var(--text3)', background:'none', border:'none', cursor:'pointer', padding:'8px 4px' }}>
            {isLast ? 'Cancel' : 'Skip'}
          </button>
          <div style={{ display:'flex', gap:10 }}>
            {step > 0 && (
              <button onClick={()=>setStep(s=>s-1)}
                style={{ fontSize:13, color:'var(--text2)', background:'none', border:'1px solid var(--border)', borderRadius:7, padding:'8px 16px', cursor:'pointer' }}>
                ← Back
              </button>
            )}
            <button onClick={next} disabled={!canNext && current.type !== 'text'}
              style={{ fontSize:13, fontWeight:500, color:'#fff', background: canNext||current.type==='text' ? 'var(--accent)' : 'var(--bg3)', border:'none', borderRadius:7, padding:'8px 20px', cursor: canNext||current.type==='text' ? 'pointer' : 'not-allowed', transition:'background .15s' }}>
              {isLast ? 'Start cloning →' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
