import React, { useState, useRef, useEffect } from 'react';

const Chat = ({ currentParams, onUpdateState }) => {
  const [messages, setMessages] = useState([
    // ADDED isGreeting flag so we know not to send this to the backend
    { role: 'assistant', content: 'Hello! I am your humanitarian crisis analyst. I can explain the neglect index, adjust weights, or filter the data. How can I help?', isGreeting: true }
  ]);
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
    height: '100%', 
    width: '100%',
    border: '1px solid #ccc',
    borderRadius: '8px',
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
    whiteSpace: 'pre-wrap'
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