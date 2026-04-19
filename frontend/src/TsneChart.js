import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

const KMEANS_COLORS = ['#2563eb', '#16a34a', '#d97706', '#7c3aed', '#0891b2', '#dc2626'];

const neglectColor = (score) => {
  const r = Math.round(22  + (220 - 22)  * score);
  const g = Math.round(163 + (38  - 163) * score);
  const b = Math.round(74  + (38  - 74)  * score);
  return `rgb(${r},${g},${b})`;
};

// KNN interpolation: estimate new t-SNE (x,y) from changed (neglect, coverage)
const estimatePosition = (allData, target, newNeglect, newCoverage, k = 6) => {
  const others = allData.filter(
    d => !(d.countryCode === target.countryCode && d.cluster === target.cluster)
  );
  const scored = others.map(d => ({
    ...d,
    dist: Math.sqrt(
      Math.pow((d.neglect_index - newNeglect) * 2, 2) +   // weight neglect 2×
      Math.pow(d.coverage - newCoverage, 2)
    ),
  })).sort((a, b) => a.dist - b.dist).slice(0, k);

  if (!scored.length) return { x: target.x, y: target.y };
  const eps = 1e-6;
  const totalW = scored.reduce((s, d) => s + 1 / (d.dist + eps), 0);
  return {
    x: scored.reduce((s, d) => s + d.x / (d.dist + eps), 0) / totalW,
    y: scored.reduce((s, d) => s + d.y / (d.dist + eps), 0) / totalW,
  };
};

// Normal dot
const Dot = ({ cx, cy, payload, fill }) => {
  if (payload?.is_outlier) {
    return (
      <g>
        <circle cx={cx} cy={cy} r={8} fill={fill} fillOpacity={0.3} stroke="#dc2626" strokeWidth={2} />
        <circle cx={cx} cy={cy} r={4} fill="#dc2626" />
      </g>
    );
  }
  return <circle cx={cx} cy={cy} r={4} fill={fill} fillOpacity={0.75} />;
};

// Selected dot (rendered in its own Scatter so position is controlled via data)
const SelectedDot = ({ cx, cy, payload, fill }) => {
  const hasCF = payload?.hasCF;
  const cfColor = hasCF ? neglectColor(payload.new_neglect_index) : fill;
  const delta = hasCF ? (payload.orig_neglect - payload.new_neglect_index) : 0;
  return (
    <g>
      {/* Ghost at original position */}
      {hasCF && (
        <>
          <circle cx={payload._origCx} cy={payload._origCy} r={5} fill={fill} fillOpacity={0.25} strokeDasharray="2 2" stroke={fill} strokeWidth={1} />
          <line x1={payload._origCx} y1={payload._origCy} x2={cx} y2={cy} stroke="#1d4ed8" strokeWidth={1} strokeDasharray="3 2" strokeOpacity={0.5} />
        </>
      )}
      {/* Glow */}
      <circle cx={cx} cy={cy} r={18} fill="#1d4ed8" fillOpacity={0.1} />
      {/* Ring */}
      <circle cx={cx} cy={cy} r={12} fill="none" stroke="#1d4ed8" strokeWidth={1.5} strokeDasharray="3 2" />
      {/* Dot coloured by new neglect */}
      <circle cx={cx} cy={cy} r={6} fill={cfColor} fillOpacity={0.95} />
      {/* Label */}
      <text x={cx} y={cy - 17} textAnchor="middle" fontSize={9} fontWeight={700} fill="#1d4ed8">
        {payload.countryName}
      </text>
      {hasCF && delta > 0.005 && (
        <text x={cx} y={cy + 22} textAnchor="middle" fontSize={9} fontWeight={700} fill="#16a34a">
          ▼ {delta.toFixed(3)}
        </text>
      )}
    </g>
  );
};

const ChartTooltip = ({ active, payload, selectedCrisis, counterfactualResult }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const isSelected =
    selectedCrisis &&
    d.countryCode === selectedCrisis.countryCode &&
    d.cluster === selectedCrisis.cluster;
  const cf = isSelected ? counterfactualResult : null;
  return (
    <div style={tooltipStyle}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{d.countryName}</div>
      <div style={{ color: '#586069', marginBottom: 6, fontSize: 12 }}>{d.cluster}</div>
      <div>Coverage: <strong>{(d.coverage * 100).toFixed(1)}%</strong>
        {cf && cf.new_coverage !== cf.current_coverage && (
          <span style={{ color: '#16a34a', marginLeft: 6 }}>→ {(cf.new_coverage * 100).toFixed(1)}%</span>
        )}
      </div>
      <div>Neglect Index: <strong>{d.neglect_index.toFixed(3)}</strong>
        {cf && (
          <span style={{ color: cf.new_neglect_index < cf.current_neglect_index ? '#16a34a' : '#64748b', marginLeft: 6 }}>
            → {cf.new_neglect_index.toFixed(3)}
          </span>
        )}
      </div>
      <div>People in Need: <strong>{d.people_in_need.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong></div>
      {d.neglect_type && (
        <div style={{ marginTop: 5 }}>
          <span style={{
            display: 'inline-block', padding: '1px 7px', borderRadius: 10,
            fontSize: 11, fontWeight: 600, textTransform: 'capitalize',
            background: { structural:'#7c3aed', worsening:'#dc2626', acute:'#d97706', improving:'#16a34a', adequate:'#6b7280' }[d.neglect_type] + '22',
            color: { structural:'#7c3aed', worsening:'#dc2626', acute:'#d97706', improving:'#16a34a', adequate:'#6b7280' }[d.neglect_type],
          }}>
            {d.neglect_type}
          </span>
          {d.consecutive_years_underfunded > 0 && (
            <span style={{ fontSize: 11, color: '#586069', marginLeft: 6 }}>
              {d.consecutive_years_underfunded}yr streak
            </span>
          )}
        </div>
      )}
      {cf && (
        <div style={{ color: '#1d4ed8', fontSize: 11, marginTop: 6, borderTop: '1px solid #e2e8f0', paddingTop: 5 }}>
          Counterfactual: rank #{cf.current_rank} → #{cf.new_rank} of {cf.total_in_cluster}
        </div>
      )}
      {d.is_outlier && (
        <div style={{ color: '#dc2626', fontWeight: 600, marginTop: 6 }}>
          ⚠ Outlier from support cluster
        </div>
      )}
    </div>
  );
};

const TsneChart = ({ currentParams, selectedCrisis, counterfactualResult }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTsne = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (currentParams?.last_years != null) params.set('last_years', currentParams.last_years);
      if (currentParams?.cluster?.length) currentParams.cluster.forEach(c => params.append('cluster', c));
      if (currentParams?.country?.length) currentParams.country.forEach(c => params.append('country', c));
      if (currentParams?.severity_weight != null) params.set('severity_weight', currentParams.severity_weight);
      if (currentParams?.funding_gap_weight != null) params.set('funding_gap_weight', currentParams.funding_gap_weight);
      if (currentParams?.need_weight != null) params.set('need_weight', currentParams.need_weight);
      if (currentParams?.ipc_weight != null) params.set('ipc_weight', currentParams.ipc_weight);
      if (currentParams?.events_weight != null) params.set('events_weight', currentParams.events_weight);

      const res = await fetch(`http://localhost:8000/tsne?${params}`);
      if (!res.ok) throw new Error('Failed to fetch t-SNE data');
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [currentParams]);

  useEffect(() => { fetchTsne(); }, [fetchTsne]);

  const kmeansGroups = useMemo(() => {
    const map = {};
    data.forEach(d => {
      // Exclude selected point — it gets its own Scatter so position can be controlled
      if (
        selectedCrisis &&
        d.countryCode === selectedCrisis.countryCode &&
        d.cluster === selectedCrisis.cluster
      ) return;
      const key = d.kmeans_cluster;
      if (!map[key]) map[key] = [];
      map[key].push(d);
    });
    return map;
  }, [data, selectedCrisis]);

  // Selected point with optionally estimated new position via KNN
  const selectedPointData = useMemo(() => {
    if (!selectedCrisis || !data.length) return null;
    const orig = data.find(
      d => d.countryCode === selectedCrisis.countryCode && d.cluster === selectedCrisis.cluster
    );
    if (!orig) return null;

    if (counterfactualResult) {
      const pos = estimatePosition(
        data, orig,
        counterfactualResult.new_neglect_index,
        counterfactualResult.new_coverage,
      );
      return [{
        ...orig,
        x: pos.x,
        y: pos.y,
        hasCF: true,
        orig_neglect: orig.neglect_index,
        new_neglect_index: counterfactualResult.new_neglect_index,
        // pixel coords of ghost are set dynamically via the chart scale — store data coords
        _origX: orig.x,
        _origY: orig.y,
      }];
    }
    return [{ ...orig, hasCF: false }];
  }, [data, selectedCrisis, counterfactualResult]);

  const clusterIds = useMemo(() => Object.keys(kmeansGroups).map(Number).sort((a, b) => a - b), [kmeansGroups]);

  const outlierCount = useMemo(() => data.filter(d => d.is_outlier).length, [data]);

  if (loading) {
    return (
      <div style={styles.center}>
        <div style={styles.spinner} />
        <span style={{ marginTop: 12, color: '#586069' }}>Computing t-SNE projection…</span>
      </div>
    );
  }
  if (error) return <div style={styles.center}>Error: {error}</div>;
  if (!data.length) return <div style={styles.center}>No data to project.</div>;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.title}>Crisis Landscape — t-SNE + KMeans Support Clusters</span>
        <span style={styles.subtitle}>
          {outlierCount} outlier{outlierCount !== 1 ? 's' : ''} &nbsp;·&nbsp; {data.length} crises &nbsp;·&nbsp; {clusterIds.length} support clusters
        </span>
      </div>

      <div style={styles.legendRow}>
        <span style={styles.legendItem}>
          <svg width={14} height={14}><circle cx={7} cy={7} r={4} fill="#888" fillOpacity={0.75} /></svg>
          Normal
        </span>
        <span style={styles.legendItem}>
          <svg width={14} height={14}>
            <circle cx={7} cy={7} r={7} fill="#dc2626" fillOpacity={0.3} stroke="#dc2626" strokeWidth={2} />
            <circle cx={7} cy={7} r={3} fill="#dc2626" />
          </svg>
          Outlier from cluster
        </span>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 5, right: 20, bottom: 20, left: 10 }}>
            <XAxis
              dataKey="x" type="number" name="t-SNE 1"
              tick={false} axisLine={false} tickLine={false}
              label={{ value: 't-SNE 1', position: 'insideBottom', offset: -4, fontSize: 11, fill: '#aaa' }}
            />
            <YAxis
              dataKey="y" type="number" name="t-SNE 2"
              tick={false} axisLine={false} tickLine={false}
              label={{ value: 't-SNE 2', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11, fill: '#aaa' }}
            />
            <ZAxis range={[55, 55]} />
            <Tooltip content={<ChartTooltip selectedCrisis={selectedCrisis} counterfactualResult={counterfactualResult} />} cursor={{ strokeDasharray: '3 3' }} />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 2 }}
              iconSize={8}
              layout="horizontal"
              verticalAlign="bottom"
            />
            {clusterIds.map(cid => (
              <Scatter
                key={cid}
                name={`Support cluster ${cid + 1}`}
                data={kmeansGroups[cid]}
                fill={KMEANS_COLORS[cid % KMEANS_COLORS.length]}
                shape={(props) => <Dot {...props} fill={KMEANS_COLORS[cid % KMEANS_COLORS.length]} />}
              />
            ))}
            {selectedPointData && (
              <Scatter
                key="selected"
                name={false}
                legendType="none"
                data={selectedPointData}
                fill={KMEANS_COLORS[(selectedPointData[0]?.kmeans_cluster ?? 0) % KMEANS_COLORS.length]}
                shape={(props) => {
                  const fill = KMEANS_COLORS[(props.payload?.kmeans_cluster ?? 0) % KMEANS_COLORS.length];
                  // Compute ghost pixel coords from the chart's xAxis/yAxis scales
                  const xScale = props.xAxis?.scale;
                  const yScale = props.yAxis?.scale;
                  const origCx = xScale ? xScale(props.payload._origX) : props.cx;
                  const origCy = yScale ? yScale(props.payload._origY) : props.cy;
                  return (
                    <SelectedDot
                      {...props}
                      fill={fill}
                      payload={{ ...props.payload, _origCx: origCx, _origCy: origCy }}
                    />
                  );
                }}
              />
            )}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

const styles = {
  container: {
    width: '100%',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    padding: '10px 14px 4px',
    boxSizing: 'border-box',
    fontFamily: 'Inter, sans-serif',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
    flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600, color: '#24292e' },
  subtitle: { fontSize: 12, color: '#586069' },
  legendRow: {
    display: 'flex',
    gap: 16,
    marginBottom: 4,
    flexShrink: 0,
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
    fontSize: 11,
    color: '#586069',
  },
  center: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    fontSize: 14,
    color: '#586069',
  },
  spinner: {
    width: 28,
    height: 28,
    border: '3px solid #e1e4e8',
    borderTop: '3px solid #2563eb',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
};

const tooltipStyle = {
  background: '#fff',
  border: '1px solid #e1e4e8',
  borderRadius: 8,
  padding: '10px 14px',
  fontSize: 13,
  boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
};

export default TsneChart;
