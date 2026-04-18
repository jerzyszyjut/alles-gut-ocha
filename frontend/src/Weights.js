import React, { useMemo } from 'react';
import Chat from './Chat';


const WEIGHT_KEYS = ['severity_weight', 'funding_gap_weight', 'need_weight', 'ipc_weight', 'events_weight'];

const Weights = ({ messages = [], setMessages, currentParams, onUpdateState }) => {

  const detectedWeights = useMemo(() => {
    const defaults = {
      severity_weight: 0.6,
      funding_gap_weight: 0.4,
      need_weight: 0.5,
      ipc_weight: 0.4,
      events_weight: 0.1,
    };

    // Prefer currentParams if the AI has updated any weight key
    if (currentParams && WEIGHT_KEYS.some(k => k in currentParams)) {
      return {
        data: { ...defaults, ...Object.fromEntries(WEIGHT_KEYS.map(k => [k, currentParams[k] ?? defaults[k]])) },
        source: 'Updated by AI',
      };
    }

    return { data: defaults, source: 'System Default' };
  }, [currentParams]);

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
          backgroundColor: source === 'System Default' ? '#eee' : '#e6ffed',
          color: source === 'System Default' ? '#666' : '#22863a'
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

      <div style={styles.chatSection}>
        <Chat
          messages={messages}
          setMessages={setMessages}
          currentParams={currentParams}
          onUpdateState={onUpdateState}
        />
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
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    boxSizing: 'border-box',
    overflow: 'hidden',
  },
  chatSection: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    borderTop: '1px solid #e1e4e8',
    marginTop: '8px',
    paddingTop: '8px',
    overflow: 'hidden',
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