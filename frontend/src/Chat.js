import React, { useState, useRef, useEffect } from 'react';

const Chat = () => {
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Hello! How can I help you today?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Reference to auto-scroll to the bottom of the chat
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
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // REPLACE THIS URL with your actual Python backend endpoint (e.g., FastAPI, Flask)
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: input }),
      });

      if (!response.ok) {
        throw new Error('Failed to fetch response from the server');
      }

      const data = await response.json();
      
      // Assuming your Python backend returns: { "reply": "The LLM's response..." }
      const aiMessage = { role: 'ai', content: data.reply };
      setMessages((prev) => [...prev, aiMessage]);

    } catch (error) {
      console.error("Error communicating with LLM:", error);
      setMessages((prev) => [
        ...prev, 
        { role: 'ai', content: "Sorry, I'm having trouble connecting to the server right now." }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container" style={styles.container}>
      <div className="chat-header" style={styles.header}>
        <h2>LLM Assistant</h2>
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
              {msg.content}
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
          placeholder="Type your message..."
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

// Basic inline styles to get you started quickly
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    maxWidth: '500px',
    margin: '0 auto',
    border: '1px solid #ccc',
    borderRadius: '8px',
    overflow: 'hidden',
    fontFamily: 'sans-serif'
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
    maxWidth: '75%',
    padding: '10px 15px',
    borderRadius: '18px',
    lineHeight: '1.4',
    wordWrap: 'break-word'
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
    fontSize: '16px'
  },
  button: {
    padding: '10px 20px',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    borderRadius: '20px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold'
  }
};

export default Chat;