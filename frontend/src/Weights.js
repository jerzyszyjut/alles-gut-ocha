import React, { useState, useMemo } from 'react';
import Chat from './Chat';

const WEIGHT_KEYS = ['severity_weight', 'funding_gap_weight', 'need_weight', 'ipc_weight', 'events_weight'];

const Weights = ({ messages = [], setMessages, currentParams, onUpdateState }) => {
  const [expanded, setExpanded] = useState(false);

  const detectedWeights = useMemo(() => {
    const defaults = {
      severity_weight: 0.6,
      funding_gap_weight: 0.4,
      need_weight: 0.5,
      ipc_weight: 0.4,
      events_weight: 0.1,
    };
    if (currentParams && WEIGHT_KEYS.some(k => k in currentParams)) {
      return {
        data: { ...defaults, ...Object.fromEntries(WEIGHT_KEYS.map(k => [k, currentParams[k] ?? defaults[k]])) },
        source: 'AI',
      };
    }
    return { data: defaults, source: 'default' };
  }, [currentParams]);

  const { data, source } = detectedWeights;
  const topTotal = data.severity_weight + data.funding_gap_weight || 1;
  const subTotal  = data.need_weight + data.ipc_weight + data.events_weight || 1;

  return (
    <div style={s.container}>
      {/* Collapsible methodology strip */}
      <button style={s.toggleRow} onClick={() => setExpanded(v => !v)}>
        <span style={s.toggleLabel}>
          Active Methodology
          <span style={{ ...s.badge, background: source === 'AI' ? '#dcfce7' : '#f1f5f9', color: source === 'AI' ? '#15803d' : '#64748b' }}>
            {source}
          </span>
        </span>
        <span style={s.chevron}>{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div style={s.weightsBody}>
          <div style={s.sectionTitle}>Macro Weights</div>
          <StatBar label="Severity"    value={data.severity_weight}    total={topTotal} color="#1d4ed8" />
          <StatBar label="Funding Gap" value={data.funding_gap_weight} total={topTotal} color="#f66a0a" />

          <div style={{ ...s.sectionTitle, marginTop: '10px' }}>Severity Composition</div>
          <StatBar label="People in Need"    value={data.need_weight}   total={subTotal} color="#16a34a" />
          <StatBar label="Food Security (IPC)" value={data.ipc_weight}  total={subTotal} color="#7c3aed" />
          <StatBar label="Conflict Events"  value={data.events_weight}  total={subTotal} color="#dc2626" />
        </div>
      )}

      {/* Chat fills the rest */}
      <div style={s.chatSection}>
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

const StatBar = ({ label, value, total, color }) => {
  const pct = ((value / total) * 100).toFixed(0);
  return (
    <div style={sb.row}>
      <span style={sb.label}>{label}</span>
      <div style={sb.track}>
        <div style={{ ...sb.fill, width: `${pct}%`, background: color }} />
      </div>
      <span style={sb.pct}>{pct}%</span>
    </div>
  );
};

const s = {
  container: {
    backgroundColor: '#fff',
    borderRadius: '12px',
    border: '1px solid #e1e4e8',
    fontFamily: 'Inter, sans-serif',
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
    boxSizing: 'border-box',
    overflow: 'hidden',
  },
  toggleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 14px',
    border: 'none',
    borderBottom: '1px solid #f0f2f5',
    background: '#fafbfc',
    cursor: 'pointer',
    width: '100%',
    flexShrink: 0,
    borderRadius: '12px 12px 0 0',
  },
  toggleLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '11px',
    fontWeight: 700,
    color: '#475569',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  badge: {
    fontSize: '9px',
    fontWeight: 700,
    padding: '2px 6px',
    borderRadius: '8px',
    textTransform: 'uppercase',
  },
  chevron: { fontSize: '9px', color: '#94a3b8' },
  weightsBody: {
    padding: '10px 14px 12px',
    borderBottom: '1px solid #f0f2f5',
    flexShrink: 0,
  },
  sectionTitle: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '6px',
  },
  chatSection: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
    overflow: 'hidden',
  },
};

const sb = {
  row: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' },
  label: { fontSize: '11px', color: '#475569', width: '110px', flexShrink: 0 },
  track: { flex: 1, height: '5px', background: '#f1f5f9', borderRadius: '3px', overflow: 'hidden' },
  fill: { height: '100%', borderRadius: '3px', transition: 'width 0.4s ease' },
  pct: { fontSize: '11px', fontWeight: 600, color: '#64748b', width: '28px', textAlign: 'right', flexShrink: 0 },
};

export default Weights;
