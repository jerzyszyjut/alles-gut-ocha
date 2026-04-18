import React from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip,
} from 'recharts';

const CASE_LABELS = {
  A: 'Need rank + IPC food severity + Conflict events',
  B: 'Need rank + IPC food severity (no conflict data)',
  C: 'Need rank + Conflict events (no IPC data)',
  D: 'Need rank only — limited indicator coverage',
};
const CASE_COLORS = { A: '#16a34a', B: '#2563eb', C: '#d97706', D: '#6b7280' };

const RadarModal = ({ row, onClose }) => {
  if (!row) return null;

  const radarData = [
    { metric: 'Need',         value: +(row.need_rank || 0).toFixed(3),               fullMark: 1 },
    { metric: 'Funding Gap',  value: +(1 - (row.coverage_rank || 0)).toFixed(3),     fullMark: 1 },
    { metric: 'IPC Severity', value: +(row.ipc_severity_score ?? 0).toFixed(3),      fullMark: 1 },
    { metric: 'Neglect',      value: +(row.neglect_index || 0).toFixed(3),            fullMark: 1 },
  ];

  const hasCI = row.rank_ci_low != null && row.rank_ci_high != null;
  const caseColor = CASE_COLORS[row.severity_case] || '#6b7280';
  const noIpc = row.ipc_severity_score == null;

  return (
    <div style={s.backdrop} onClick={onClose}>
      <div style={s.modal} onClick={e => e.stopPropagation()}>
        <button style={s.closeBtn} onClick={onClose}>✕</button>

        <div style={s.header}>
          <div style={s.title}>{row.countryName}</div>
          <div style={s.subtitle}>{row.cluster}</div>
        </div>

        <div style={s.statsRow}>
          <div style={s.stat}>
            <span style={s.statLabel}>Neglect Index</span>
            <span style={s.statValue}>{row.neglect_index?.toFixed(3)}</span>
          </div>
          <div style={s.stat}>
            <span style={s.statLabel}>Rank</span>
            <span style={s.statValue}>
              {row.rank != null ? `#${row.rank}` : '—'}
              {hasCI && (
                <span style={{ fontSize: 10, color: '#888', marginLeft: 4 }}>
                  [{row.rank_ci_low}–{row.rank_ci_high}]
                </span>
              )}
            </span>
          </div>
          <div style={s.stat}>
            <span style={s.statLabel}>Coverage</span>
            <span style={s.statValue}>{((row.coverage || 0) * 100).toFixed(1)}%</span>
          </div>
          <div style={s.stat}>
            <span style={s.statLabel}>Data Inputs</span>
            <span title={CASE_LABELS[row.severity_case]} style={{
              ...s.statValue,
              color: caseColor,
              background: caseColor + '18',
              padding: '2px 8px',
              borderRadius: 10,
              fontSize: 11,
              border: `1px solid ${caseColor}44`,
              cursor: 'help',
            }}>
              Case {row.severity_case || '?'}
            </span>
          </div>
        </div>

        {noIpc && (
          <div style={s.notice}>
            IPC Severity axis shows 0 — no food insecurity phase data available for this crisis.
          </div>
        )}

        <div style={{ height: 250 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid gridType="polygon" />
              <PolarAngleAxis
                dataKey="metric"
                tick={{ fontSize: 12, fill: '#444', fontFamily: 'Inter, sans-serif' }}
              />
              <PolarRadiusAxis
                angle={30} domain={[0, 1]}
                tick={{ fontSize: 9, fill: '#aaa' }} tickCount={3}
              />
              <Radar
                dataKey="value"
                stroke="#2563eb" fill="#2563eb" fillOpacity={0.25} strokeWidth={2}
              />
              <Tooltip formatter={(v) => v.toFixed(3)} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div style={s.caseNote}>
          <strong>Case {row.severity_case}:</strong> {CASE_LABELS[row.severity_case] || 'Unknown'}
        </div>
      </div>
    </div>
  );
};

const s = {
  backdrop: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.45)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    background: '#fff', borderRadius: 14,
    padding: '24px 28px', width: 480, maxWidth: '95vw',
    maxHeight: '90vh', overflowY: 'auto',
    boxShadow: '0 20px 60px rgba(0,0,0,0.22)',
    position: 'relative',
    display: 'flex', flexDirection: 'column', gap: 14,
    fontFamily: 'Inter, sans-serif',
  },
  closeBtn: {
    position: 'absolute', top: 12, right: 14,
    background: 'none', border: 'none',
    fontSize: 16, cursor: 'pointer', color: '#888', padding: 4,
  },
  header: { paddingRight: 28 },
  title: { fontSize: 17, fontWeight: 700, color: '#24292e' },
  subtitle: { fontSize: 13, color: '#586069', marginTop: 2 },
  statsRow: {
    display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 10, background: '#f6f8fa',
    borderRadius: 8, padding: '12px 14px',
  },
  stat: { display: 'flex', flexDirection: 'column', gap: 3 },
  statLabel: { fontSize: 9, color: '#888', textTransform: 'uppercase', letterSpacing: 0.5 },
  statValue: { fontSize: 14, fontWeight: 600, color: '#24292e' },
  notice: {
    fontSize: 11, color: '#92400e',
    background: '#fffbeb', padding: '6px 10px',
    borderRadius: 6, border: '1px solid #fde68a',
  },
  caseNote: {
    fontSize: 11, color: '#586069',
    background: '#f6f8fa', borderRadius: 6,
    padding: '8px 12px', borderTop: '1px solid #e1e4e8',
  },
};

export default RadarModal;
