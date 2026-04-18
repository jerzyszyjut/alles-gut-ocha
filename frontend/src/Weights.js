import React, { useMemo } from 'react';

// --- HELPER: Fuzzy matching for key detection ---
const fuzzyKeyMatch = (text, target) => {
  const t = target.toLowerCase();
  const str = text.toLowerCase();
  // Check if target is inside text or vice-versa
  return str.includes(t) || t.includes(str) || (str.includes('food') && t === 'ipc_weight');
};

const Weights = ({ messages = [] }) => {
  
  // Logic: Scan messages from latest to oldest to find a weight table
  const detectedWeights = useMemo(() => {
    // Default fallback
    const weights = {
      severity_weight: 0.6,
      funding_gap_weight: 0.4,
      need_weight: 0.5,
      ipc_weight: 0.4,
      events_weight: 0.1,
    };

    // 1. Filter for assistant messages that contain tables (using the pipe symbol)
    const tableMessages = messages
      .filter(m => m.role === 'assistant' && m.content.includes('|'))
      .reverse(); // Start from newest

    if (tableMessages.length === 0) return { data: weights, source: 'System Default' };

    const latestContent = tableMessages[0].content;
    const lines = latestContent.split('\n');

    lines.forEach(line => {
      if (!line.includes('|')) return;
      const cells = line.split('|').map(c => c.trim().toLowerCase());
      
      // Look for a number in the row
      const value = parseFloat(cells.find(c => !isNaN(parseFloat(c)) && isFinite(c)));
      if (isNaN(value)) return;

      // Fuzzy map the row text to our keys
      if (cells.some(c => fuzzyKeyMatch(c, 'severity'))) weights.severity_weight = value;
      if (cells.some(c => fuzzyKeyMatch(c, 'funding'))) weights.funding_gap_weight = value;
      if (cells.some(c => fuzzyKeyMatch(c, 'need'))) weights.need_weight = value;
      if (cells.some(c => fuzzyKeyMatch(c, 'ipc') || fuzzyKeyMatch(c, 'food'))) weights.ipc_weight = value;
      if (cells.some(c => fuzzyKeyMatch(c, 'conflict') || fuzzyKeyMatch(c, 'event'))) weights.events_weight = value;
    });

    return { data: weights, source: 'Extracted from Chat' };
  }, [messages]);

  const { data, source } = detectedWeights;

  // Normalization logic for display
  const topTotal = data.severity_weight + data.funding_gap_weight || 1;
  const subTotal = data.need_weight + data.ipc_weight + data.events_weight || 1;

  return (
    <div style={styles.container}>
      <div style={styles.headerRow}>
        <h2 style={styles.header}>Active Methodology</h2>
        <span style={{
          ...styles.statusBadge, 
          backgroundColor: source === 'System Default' ? '#eee' : '#e1f5fe',
          color: source === 'System Default' ? '#666' : '#0288d1'
        }}>
          {source}
        </span>
      </div>

      <p style={styles.description}>
        The index is currently reading weights from the conversation history. 
        To change these, tell the AI: <em>"Update the severity weight to 0.8"</em>.
      </p>

      {/* READ-ONLY DISPLAY */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Macro Weights</div>
        <StatBar label="Severity" value={data.severity_weight} total={topTotal} color="#0366d6" />
        <StatBar label="Funding Gap" value={data.funding_gap_weight} total={topTotal} color="#f66a0a" />
      </div>

      <div style={styles.section}>
        <div style={styles.sectionTitle}>Severity Composition</div>
        <StatBar label="People In Need" value={data.need_weight} total={subTotal} color="#28a745" />
        <StatBar label="Food Security (IPC)" value={data.ipc_weight} total={subTotal} color="#6f42c1" />
        <StatBar label="Conflict Events" value={data.events_weight} total={subTotal} color="#d73a49" />
      </div>
    </div>
  );
};

// Purely visual component since user cannot edit
const StatBar = ({ label, value, total, color }) => {
  const percentage = ((value / total) * 100).toFixed(0);
  return (
    <div style={styles.statRow}>
      <div style={styles.statLabel}>
        <span>{label}</span>
        <strong>{percentage}%</strong>
      </div>
      <div style={styles.barBg}>
        <div style={{
          ...styles.barFill,
          width: `${percentage}%`,
          backgroundColor: color
        }} />
      </div>
      <div style={styles.rawVal}>Relative score: {value.toFixed(2)}</div>
    </div>
  );
};

const styles = {
  container: {
    padding: '20px',
    backgroundColor: '#fff',
    borderRadius: '12px',
    border: '1px solid #e1e4e8',
    fontFamily: 'sans-serif',
    maxWidth: '400px'
  },
  headerRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' },
  header: { margin: 0, fontSize: '18px', color: '#24292e' },
  statusBadge: { fontSize: '10px', padding: '3px 8px', borderRadius: '10px', fontWeight: 'bold', textTransform: 'uppercase' },
  description: { fontSize: '12px', color: '#586069', marginBottom: '20px', fontStyle: 'italic' },
  section: { marginBottom: '20px' },
  sectionTitle: { fontSize: '12px', fontWeight: 'bold', color: '#888', textTransform: 'uppercase', marginBottom: '10px', letterSpacing: '0.5px' },
  statRow: { marginBottom: '12px' },
  statLabel: { display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '4px' },
  barBg: { height: '6px', backgroundColor: '#f0f0f0', borderRadius: '3px', overflow: 'hidden' },
  barFill: { height: '100%', transition: 'width 0.5s ease-out' },
  rawVal: { fontSize: '10px', color: '#aaa', marginTop: '2px', textAlign: 'right' }
};

export default Weights;