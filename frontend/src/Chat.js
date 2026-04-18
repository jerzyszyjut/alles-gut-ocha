import React, { useState, useRef, useEffect } from 'react';

const ANIM_CSS = `
@keyframes chatBounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-5px); opacity: 1; }
}
@keyframes chatFadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
`;

const parseInline = (str) => {
  const parts = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|__[^_]+__|_[^_]+_)/g;
  let last = 0, m;
  while ((m = re.exec(str)) !== null) {
    if (m.index > last) parts.push(str.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('`'))
      parts.push(<code key={m.index} style={s.inlineCode}>{tok.slice(1, -1)}</code>);
    else if (tok.startsWith('**') || tok.startsWith('__'))
      parts.push(<strong key={m.index}>{tok.slice(2, -2)}</strong>);
    else
      parts.push(<em key={m.index}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < str.length) parts.push(str.slice(last));
  return parts.length > 0 ? parts : str;
};

const renderMarkdown = (text) => {
  const lines = text.split('\n');
  const elements = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith('```')) {
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) { codeLines.push(lines[i]); i++; }
      elements.push(<pre key={i} style={s.codeBlock}><code>{codeLines.join('\n')}</code></pre>);
    } else if (/^#{1,6}\s/.test(line)) {
      const level = line.match(/^(#+)/)[1].length;
      const fs = ['17px', '15px', '14px', '13px', '13px', '13px'][level - 1];
      elements.push(
        <div key={i} style={{ fontWeight: 700, fontSize: fs, margin: '8px 0 3px', color: '#1e293b' }}>
          {parseInline(line.replace(/^#+\s/, ''))}
        </div>
      );
    } else if (/^[-*+]\s/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*+]\s/.test(lines[i])) {
        items.push(<li key={i}>{parseInline(lines[i].replace(/^[-*+]\s/, ''))}</li>);
        i++;
      }
      elements.push(<ul key={`ul-${i}`} style={s.list}>{items}</ul>);
      continue;
    } else if (/^\d+\.\s/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(<li key={i}>{parseInline(lines[i].replace(/^\d+\.\s/, ''))}</li>);
        i++;
      }
      elements.push(<ol key={`ol-${i}`} style={s.list}>{items}</ol>);
      continue;
    } else if (line.trim().startsWith('|')) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) { tableLines.push(lines[i].trim()); i++; }
      if (tableLines.length >= 2 && /^\|?\s*[-:]+[\-| :]*\s*\|?$/.test(tableLines[1])) {
        const parseRow = (r) => r.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
        const headers = parseRow(tableLines[0]);
        const rows = tableLines.slice(2).map(parseRow);
        elements.push(
          <div key={`tw-${i}`} style={s.tableWrap}>
            <table style={s.table}>
              <thead><tr>{headers.map((h, idx) => <th key={idx} style={s.th}>{parseInline(h)}</th>)}</tr></thead>
              <tbody>{rows.map((row, ri) => (
                <tr key={ri}>{row.map((cell, ci) => <td key={ci} style={s.td}>{parseInline(cell)}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        );
      } else {
        tableLines.forEach((l, ti) => elements.push(<p key={`fb-${i}-${ti}`} style={{ margin: '2px 0' }}>{parseInline(l)}</p>));
      }
      continue;
    } else if (line.trim() === '') {
      elements.push(<div key={i} style={{ height: '6px' }} />);
    } else {
      elements.push(<p key={i} style={{ margin: '3px 0', lineHeight: 1.55 }}>{parseInline(line)}</p>);
    }
    i++;
  }
  return elements;
};

const SUGGESTIONS = [
  'Which crisis is most underfunded?',
  'Compare Sudan and DRC',
  'Boost severity weight to 0.8',
];

const Chat = ({ currentParams, onUpdateState, messages, setMessages }) => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, isLoading]);

  const send = async (text) => {
    const content = (text || input).trim();
    if (!content) return;
    const userMsg = { role: 'user', content };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput('');
    setIsLoading(true);
    try {
      const payload = updated.filter(m => !m.isGreeting).map(m => ({ role: m.role, content: m.content }));
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: payload, current_params: currentParams || {} }),
      });
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      if (data.parameter_update || data.ranking_snapshot) {
        onUpdateState(data.parameter_update, data.ranking_snapshot);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: "Can't reach the backend — is FastAPI running?" }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e) => { e.preventDefault(); send(); };

  const showSuggestions = messages.length <= 1;

  return (
    <>
      <style>{ANIM_CSS}</style>
      <div style={s.container}>
        {/* Header */}
        <div style={s.header}>
          <div style={s.headerLeft}>
            <div style={s.avatar}>✦</div>
            <div>
              <div style={s.headerTitle}>AI Copilot</div>
              <div style={s.headerSub}>Powered by Claude · asks questions, adjusts weights</div>
            </div>
          </div>
          <div style={s.statusDot} title="Online" />
        </div>

        {/* Messages */}
        <div style={s.messages}>
          {messages.map((msg, i) => (
            <div key={i} style={{ ...s.row, justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', animation: 'chatFadeIn 0.2s ease' }}>
              {msg.role === 'assistant' && <div style={s.aiIcon}>✦</div>}
              <div style={msg.role === 'user' ? s.userBubble : s.aiBubble}>
                {msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content}
              </div>
            </div>
          ))}

          {isLoading && (
            <div style={{ ...s.row, justifyContent: 'flex-start' }}>
              <div style={s.aiIcon}>✦</div>
              <div style={s.thinkingBubble}>
                {[0, 1, 2].map(i => (
                  <span key={i} style={{ ...s.dot, animationDelay: `${i * 160}ms` }} />
                ))}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Suggestion chips */}
        {showSuggestions && (
          <div style={s.chips}>
            {SUGGESTIONS.map((t, i) => (
              <button key={i} style={s.chip} onClick={() => send(t)}>{t}</button>
            ))}
          </div>
        )}

        {/* Input */}
        <form onSubmit={handleSubmit} style={s.inputRow}>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask about a crisis or adjust weights…"
            style={s.input}
            disabled={isLoading}
          />
          <button type="submit" style={{ ...s.sendBtn, opacity: (!input.trim() || isLoading) ? 0.4 : 1 }} disabled={!input.trim() || isLoading}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </form>
      </div>
    </>
  );
};

const s = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
    fontFamily: 'Inter, sans-serif',
    backgroundColor: '#fff',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 14px',
    borderBottom: '1px solid #f0f2f5',
    flexShrink: 0,
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: '10px' },
  avatar: {
    width: 32, height: 32,
    borderRadius: '50%',
    background: 'linear-gradient(135deg, #1d4ed8, #7c3aed)',
    color: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '14px', flexShrink: 0,
  },
  headerTitle: { fontSize: '14px', fontWeight: 700, color: '#1e293b' },
  headerSub: { fontSize: '10px', color: '#94a3b8', marginTop: '1px' },
  statusDot: {
    width: 8, height: 8, borderRadius: '50%',
    background: '#22c55e',
    boxShadow: '0 0 0 2px #dcfce7',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '14px',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    scrollBehavior: 'smooth',
  },
  row: { display: 'flex', alignItems: 'flex-end', gap: '7px' },
  aiIcon: {
    width: 22, height: 22, borderRadius: '50%',
    background: 'linear-gradient(135deg, #1d4ed8, #7c3aed)',
    color: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '10px', flexShrink: 0, marginBottom: '2px',
  },
  userBubble: {
    maxWidth: '78%',
    padding: '9px 13px',
    borderRadius: '18px 18px 4px 18px',
    background: '#1d4ed8',
    color: '#fff',
    fontSize: '13px',
    lineHeight: 1.5,
    wordBreak: 'break-word',
  },
  aiBubble: {
    maxWidth: '82%',
    padding: '10px 13px',
    borderRadius: '4px 18px 18px 18px',
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    color: '#1e293b',
    fontSize: '13px',
    lineHeight: 1.55,
    wordBreak: 'break-word',
  },
  thinkingBubble: {
    padding: '12px 16px',
    borderRadius: '4px 18px 18px 18px',
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
  },
  dot: {
    display: 'inline-block',
    width: 7, height: 7,
    borderRadius: '50%',
    background: '#94a3b8',
    animation: 'chatBounce 1.2s ease-in-out infinite',
  },
  chips: {
    padding: '0 14px 10px',
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
    flexShrink: 0,
  },
  chip: {
    fontSize: '11px',
    padding: '5px 10px',
    borderRadius: '12px',
    border: '1px solid #e2e8f0',
    background: '#f8fafc',
    color: '#475569',
    cursor: 'pointer',
    fontFamily: 'Inter, sans-serif',
  },
  inputRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 12px',
    borderTop: '1px solid #f0f2f5',
    flexShrink: 0,
  },
  input: {
    flex: 1,
    padding: '9px 14px',
    borderRadius: '20px',
    border: '1.5px solid #e2e8f0',
    outline: 'none',
    fontSize: '13px',
    fontFamily: 'Inter, sans-serif',
    color: '#1e293b',
    background: '#f8fafc',
    transition: 'border-color 0.15s',
  },
  sendBtn: {
    width: 34, height: 34,
    borderRadius: '50%',
    background: '#1d4ed8',
    color: '#fff',
    border: 'none',
    cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
    transition: 'opacity 0.15s',
  },
  inlineCode: {
    background: '#f1f5f9',
    borderRadius: '3px',
    padding: '1px 5px',
    fontFamily: 'monospace',
    fontSize: '12px',
    color: '#0f172a',
  },
  codeBlock: {
    background: '#1e293b',
    color: '#e2e8f0',
    borderRadius: '8px',
    padding: '10px 12px',
    overflowX: 'auto',
    fontSize: '12px',
    fontFamily: 'monospace',
    margin: '6px 0',
    lineHeight: 1.6,
  },
  list: { margin: '4px 0', paddingLeft: '18px', lineHeight: 1.6 },
  tableWrap: { overflowX: 'auto', margin: '6px 0', borderRadius: '6px', border: '1px solid #e2e8f0' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '12px' },
  th: { padding: '6px 10px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', fontWeight: 600, textAlign: 'left', color: '#475569' },
  td: { padding: '5px 10px', borderBottom: '1px solid #f1f5f9', color: '#1e293b' },
};

export default Chat;
