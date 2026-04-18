import React, { useState, useEffect, useCallback } from 'react';

const fmt = (n) => {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const CounterfactualSlider = ({ crisis, currentParams, onClose }) => {
  const [additional, setAdditional] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const gap = Math.max((crisis.requirements_usd || 2e9) - (crisis.funding_usd || 0), 0);
  const sliderMax = Math.max(gap * 1.5, 1e9);

  const fetchResult = useCallback(async (amount) => {
    setLoading(true);
    try {
      const p = new URLSearchParams({
        country_code: crisis.countryCode,
        cluster: crisis.cluster,
        additional_funding: amount,
        severity_weight: currentParams?.severity_weight ?? 0.6,
        funding_gap_weight: currentParams?.funding_gap_weight ?? 0.4,
        need_weight: currentParams?.need_weight ?? 0.5,
        ipc_weight: currentParams?.ipc_weight ?? 0.4,
        events_weight: currentParams?.events_weight ?? 0.1,
      });
      const res = await fetch(`http://localhost:8000/counterfactual?${p}`);
      if (res.ok) setResult(await res.json());
    } catch (_) {
      // ignore network errors during drag
    } finally {
      setLoading(false);
    }
  }, [crisis.countryCode, crisis.cluster, currentParams]);

  useEffect(() => { fetchResult(0); }, [fetchResult]);

  useEffect(() => {
    const t = setTimeout(() => fetchResult(additional), 180);
    return () => clearTimeout(t);
  }, [additional, fetchResult]);

  const neglectDiff = result ? result.current_neglect_index - result.new_neglect_index : 0;
  const rankDiff = result ? result.current_rank - result.new_rank : 0;
  const covDiff = result ? result.new_coverage - result.current_coverage : 0;

  return (
    <div style={s.card}>
      <div style={s.header}>
        <div>
          <div style={s.title}>Counterfactual Funding</div>
          <div style={s.subtitle}>{crisis.countryName} · {crisis.cluster}</div>
        </div>
        <button style={s.close} onClick={onClose} title="Close">✕</button>
      </div>

      <div style={s.question}>
        If donors added <strong style={s.highlight}>{fmt(additional)}</strong> to this crisis, where would it rank?
      </div>

      <div style={s.sliderWrap}>
        <input
          type="range"
          min={0}
          max={sliderMax}
          step={Math.ceil(sliderMax / 200)}
          value={additional}
          onChange={e => setAdditional(Number(e.target.value))}
          style={s.slider}
        />
        <div style={s.sliderLabels}>
          <span>+$0</span>
          <span style={s.sliderValue}>{fmt(additional)} added</span>
          <span>{fmt(sliderMax)}</span>
        </div>
      </div>

      {result && (
        <div style={s.metrics}>
          <MetricRow
            label="Neglect Index"
            before={result.current_neglect_index.toFixed(3)}
            after={result.new_neglect_index.toFixed(3)}
            delta={neglectDiff > 0.001 ? `▼ ${neglectDiff.toFixed(3)}` : null}
            improved={neglectDiff > 0.001}
          />
          <MetricRow
            label="Cluster Rank"
            before={`#${result.current_rank} of ${result.total_in_cluster}`}
            after={`#${result.new_rank} of ${result.total_in_cluster}`}
            delta={rankDiff > 0 ? `▼ ${rankDiff} place${rankDiff > 1 ? 's' : ''}` : null}
            improved={rankDiff > 0}
            hint="1 = most neglected"
          />
          <div style={s.covRow}>
            <span style={s.metricLabel}>Coverage</span>
            <div style={s.barTrack}>
              <div style={{ ...s.barSeg, width: `${(result.current_coverage * 100).toFixed(1)}%`, background: '#94a3b8' }} />
              <div style={{ ...s.barSeg, width: `${Math.max(covDiff * 100, 0).toFixed(1)}%`, background: '#16a34a', transition: 'width 0.25s' }} />
            </div>
            <span style={s.covLabel}>
              {(result.current_coverage * 100).toFixed(0)}%
              <span style={s.arrow}> → </span>
              <strong style={{ color: covDiff > 0.005 ? '#16a34a' : '#64748b' }}>
                {(result.new_coverage * 100).toFixed(0)}%
              </strong>
            </span>
          </div>
        </div>
      )}

      {loading && <div style={s.loader} />}
    </div>
  );
};

const MetricRow = ({ label, before, after, delta, improved, hint }) => (
  <div style={mr.row}>
    <span style={mr.label}>
      {label}
      {hint && <span style={mr.hint}> ({hint})</span>}
    </span>
    <div style={mr.values}>
      <span style={mr.before}>{before}</span>
      <span style={mr.arrow}> → </span>
      <span style={{ ...mr.after, color: improved ? '#16a34a' : '#64748b' }}>{after}</span>
      {delta && <span style={{ ...mr.delta, color: improved ? '#16a34a' : '#94a3b8' }}>{delta}</span>}
    </div>
  </div>
);

const s = {
  card: {
    backgroundColor: '#fff',
    border: '1px solid #e1e4e8',
    borderRadius: '12px',
    padding: '14px 16px',
    fontFamily: 'Inter, sans-serif',
    marginBottom: '10px',
    flexShrink: 0,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '8px',
  },
  title: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#586069',
    textTransform: 'uppercase',
    letterSpacing: '0.6px',
  },
  subtitle: { fontSize: '13px', fontWeight: 600, color: '#24292e', marginTop: '2px' },
  close: {
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    color: '#aaa',
    fontSize: '13px',
    padding: '0 2px',
    lineHeight: 1,
  },
  question: {
    fontSize: '12px',
    color: '#586069',
    marginBottom: '10px',
    lineHeight: 1.5,
  },
  highlight: { color: '#1d4ed8' },
  sliderWrap: { marginBottom: '12px' },
  slider: { width: '100%', accentColor: '#1d4ed8', cursor: 'pointer' },
  sliderLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '10px',
    color: '#aaa',
    marginTop: '2px',
  },
  sliderValue: { fontWeight: 700, color: '#1d4ed8', fontSize: '11px' },
  metrics: { display: 'flex', flexDirection: 'column', gap: '8px' },
  covRow: { display: 'flex', alignItems: 'center', gap: '8px' },
  metricLabel: { fontSize: '11px', color: '#888', width: '90px', flexShrink: 0 },
  barTrack: {
    flex: 1,
    height: '6px',
    background: '#f0f2f5',
    borderRadius: '3px',
    overflow: 'hidden',
    display: 'flex',
  },
  barSeg: { height: '100%' },
  covLabel: { fontSize: '12px', color: '#586069', whiteSpace: 'nowrap' },
  arrow: { color: '#ccc' },
  loader: {
    height: '2px',
    background: 'linear-gradient(90deg,#1d4ed8 0%,#7c3aed 100%)',
    borderRadius: '1px',
    marginTop: '10px',
    opacity: 0.7,
  },
};

const mr = {
  row: { display: 'flex', alignItems: 'baseline', gap: '6px', flexWrap: 'wrap' },
  label: { fontSize: '11px', color: '#888', width: '90px', flexShrink: 0 },
  hint: { fontSize: '10px', color: '#bbb' },
  values: { display: 'flex', alignItems: 'baseline', gap: '3px', flexWrap: 'wrap' },
  before: { fontSize: '12px', color: '#94a3b8' },
  arrow: { fontSize: '11px', color: '#ddd' },
  after: { fontSize: '13px', fontWeight: 600 },
  delta: { fontSize: '11px', marginLeft: '3px' },
};

export default CounterfactualSlider;
