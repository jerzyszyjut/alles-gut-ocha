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

// Ultra-compact StatBar (removed raw value text)
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
    </div>
  );
};

const styles = {
  container: {
    padding: '12px', // Reduced from 20px
    backgroundColor: '#fff',
    borderRadius: '12px',
    border: '1px solid #e1e4e8',
    fontFamily: 'sans-serif',
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
    boxSizing: 'border-box',
    overflow: 'hidden',
  },
  chatSection: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    borderTop: '1px solid #e1e4e8',
    marginTop: '4px', // Reduced
    paddingTop: '8px',
    overflow: 'hidden',
  },
  headerRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }, // Reduced
  header: { margin: 0, fontSize: '14px', color: '#24292e' }, // Reduced from 18px
  statusBadge: { fontSize: '9px', padding: '2px 6px', borderRadius: '8px', fontWeight: 'bold', textTransform: 'uppercase' },
  section: { marginBottom: '8px' }, // Reduced from 20px
  sectionTitle: { fontSize: '10px', fontWeight: 'bold', color: '#888', textTransform: 'uppercase', marginBottom: '4px', letterSpacing: '0.5px' },
  statRow: { marginBottom: '6px' }, // Reduced from 12px
  statLabel: { display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '2px' }, // Reduced font and margin
  barBg: { height: '4px', backgroundColor: '#f0f0f0', borderRadius: '2px', overflow: 'hidden' }, // Thinner bars
  barFill: { height: '100%', transition: 'width 0.5s ease-out' }
};

export default Weights;