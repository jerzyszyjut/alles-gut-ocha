import React, { useState, useRef, useEffect } from 'react';

const renderMarkdown = (text) => {
  const lines = text.split('\n');
  const elements = [];
  let i = 0;

  const parseInline = (str) => {
    const parts = [];
    // Basic inline matching for code, bold, italic
    const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|__[^_]+__|_[^_]+_)/g;
    let last = 0, m;
    while ((m = re.exec(str)) !== null) {
      if (m.index > last) parts.push(str.slice(last, m.index));
      const tok = m[0];
      if (tok.startsWith('`')) parts.push(<code key={m.index} style={styles.inlineCode}>{tok.slice(1,-1)}</code>);
      else if (tok.startsWith('**') || tok.startsWith('__')) parts.push(<strong key={m.index}>{tok.slice(2,-2)}</strong>);
      else parts.push(<em key={m.index}>{tok.slice(1,-1)}</em>);
      last = m.index + tok.length;
    }
    if (last < str.length) parts.push(str.slice(last));
    return parts.length > 0 ? parts : str; // Return string if no matches to avoid empty arrays
  };

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith('```')) {
      // Code Blocks
      const lang = line.slice(3).trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) { codeLines.push(lines[i]); i++; }
      elements.push(<pre key={i} style={styles.codeBlock}><code>{codeLines.join('\n')}</code></pre>);
    } else if (/^#{1,6}\s/.test(line)) {
      // Headings
      const level = line.match(/^(#+)/)[1].length;
      const content = line.replace(/^#+\s/, '');
      const Tag = `h${Math.min(level, 6)}`;
      const fs = ['20px','18px','16px','15px','14px','14px'][level-1];
      elements.push(<Tag key={i} style={{margin:'6px 0 2px',fontSize:fs}}>{parseInline(content)}</Tag>);
    } else if (/^[-*+]\s/.test(line)) {
      // Bullet Lists
      const items = [];
      while (i < lines.length && /^[-*+]\s/.test(lines[i])) {
        items.push(<li key={i}>{parseInline(lines[i].replace(/^[-*+]\s/,''))}</li>);
        i++;
      }
      elements.push(<ul key={`ul-${i}`} style={{margin:'4px 0',paddingLeft:'18px'}}>{items}</ul>);
      continue;
    } else if (/^\d+\.\s/.test(line)) {
      // Numbered Lists
      const items = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(<li key={i}>{parseInline(lines[i].replace(/^\d+\.\s/,''))}</li>);
        i++;
      }
      elements.push(<ol key={`ol-${i}`} style={{margin:'4px 0',paddingLeft:'18px'}}>{items}</ol>);
      continue;
    } else if (line.trim().startsWith('|')) {
      // TABLES
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        tableLines.push(lines[i].trim());
        i++;
      }
      
      // Basic validation: needs at least 2 lines (header + separator like |---|---|)
      if (tableLines.length >= 2 && /^\|?\s*[-:]+[\-| :]*\s*\|?$/.test(tableLines[1])) {
        const parseRow = (rowStr) => {
          // Remove leading and trailing pipes before splitting
          let cleaned = rowStr.replace(/^\|/, '').replace(/\|$/, '');
          return cleaned.split('|').map(cell => cell.trim());
        };

        const headers = parseRow(tableLines[0]);
        const rows = tableLines.slice(2).map(parseRow);

        elements.push(
          <div key={`table-wrapper-${i}`} style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  {headers.map((h, idx) => <th key={`th-${idx}`} style={styles.th}>{parseInline(h)}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rIdx) => (
                  <tr key={`tr-${rIdx}`}>
                    {row.map((cell, cIdx) => <td key={`td-${cIdx}`} style={styles.td}>{parseInline(cell)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      } else {
        // Fallback if it looks like a pipe but isn't a valid markdown table
        tableLines.forEach((tLine, tIdx) => {
          elements.push(<p key={`fallback-${i}-${tIdx}`} style={{margin:'2px 0'}}>{parseInline(tLine)}</p>);
        });
      }
      continue;
    } else if (line.trim() === '') {
      // Blank lines
      elements.push(<br key={i} />);
    } else {
      // Standard Paragraphs
      elements.push(<p key={i} style={{margin:'4px 0'}}>{parseInline(line)}</p>);
    }
    i++;
  }
  return elements;
};

const Chat = ({ currentParams, onUpdateState, messages, setMessages }) => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    const updatedMessages = [...messages, userMessage];
    
    setMessages(updatedMessages);
    setInput('');
    setIsLoading(true);

    try {
      // THE FIX: Strip out the initial greeting before sending to FastAPI!
      const payloadMessages = updatedMessages
        .filter(msg => !msg.isGreeting)
        .map(msg => ({ role: msg.role, content: msg.content }));

      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          messages: payloadMessages, // Send the cleaned array
          current_params: currentParams || {} 
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch response: ${response.status}`);
      }

      const data = await response.json();
      
      const aiMessage = { role: 'assistant', content: data.reply };
      setMessages((prev) => [...prev, aiMessage]);

      if (data.parameter_update || data.ranking_snapshot) {
        onUpdateState(data.parameter_update, data.ranking_snapshot);
      }

    } catch (error) {
      console.error("Error communicating with LLM:", error);
      setMessages((prev) => [
        ...prev, 
        { role: 'assistant', content: "Sorry, I'm having trouble connecting to the backend server. Make sure FastAPI is running and CORS is configured." }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container" style={styles.container}>
      <div className="chat-header" style={styles.header}>
        <h2 style={{ margin: 0, fontSize: '18px', color: '#333' }}>AI Copilot</h2>
      </div>

      <div className="chat-messages" style={styles.messagesContainer}>
        {messages.map((msg, index) => (
          <div 
            key={index} 
            style={{
              ...styles.messageWrapper,
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
            }}
          >
            <div style={{
              ...styles.bubble,
              backgroundColor: msg.role === 'user' ? '#007bff' : '#f1f1f1',
              color: msg.role === 'user' ? '#fff' : '#333'
            }}>
              {msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div style={{ ...styles.messageWrapper, justifyContent: 'flex-start' }}>
            <div style={{ ...styles.bubble, backgroundColor: '#f1f1f1', color: '#666' }}>
              <em>Thinking...</em>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSend} style={styles.inputArea}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a crisis or adjust weights..."
          style={styles.input}
          disabled={isLoading}
        />
        <button type="submit" style={styles.button} disabled={isLoading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
};

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    height: '100%',
    overflow: 'hidden',
    fontFamily: 'sans-serif',
    backgroundColor: '#fff'
  },
  header: {
    backgroundColor: '#f8f9fa',
    padding: '15px',
    borderBottom: '1px solid #eee',
    textAlign: 'center',
    margin: 0
  },
  messagesContainer: {
    flex: 1,
    padding: '20px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    backgroundColor: '#fff'
  },
  messageWrapper: {
    display: 'flex',
    width: '100%'
  },
  bubble: {
    maxWidth: '85%',
    padding: '10px 15px',
    borderRadius: '18px',
    lineHeight: '1.4',
    wordWrap: 'break-word',
    fontSize: '14px',
    whiteSpace: 'normal'
  },
  inputArea: {
    display: 'flex',
    padding: '15px',
    backgroundColor: '#f8f9fa',
    borderTop: '1px solid #eee'
  },
  input: {
    flex: 1,
    padding: '10px 15px',
    borderRadius: '20px',
    border: '1px solid #ccc',
    outline: 'none',
    marginRight: '10px',
    fontSize: '14px'
  },
  inlineCode: {
    backgroundColor: '#e8e8e8',
    borderRadius: '3px',
    padding: '1px 4px',
    fontFamily: 'monospace',
    fontSize: '13px'
  },
  codeBlock: {
    backgroundColor: '#2d2d2d',
    color: '#f8f8f2',
    borderRadius: '6px',
    padding: '10px 12px',
    overflowX: 'auto',
    fontSize: '13px',
    fontFamily: 'monospace',
    margin: '6px 0'
  },
  button: {
    padding: '10px 20px',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    borderRadius: '20px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 'bold'
  }
};

export default Chat;