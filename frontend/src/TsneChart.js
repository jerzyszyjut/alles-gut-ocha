import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

const KMEANS_COLORS = ['#2563eb', '#16a34a', '#d97706', '#7c3aed', '#0891b2', '#dc2626'];

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

const ChartTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div style={tooltipStyle}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{d.countryName}</div>
      <div style={{ color: '#586069', marginBottom: 6, fontSize: 12 }}>{d.cluster}</div>
      <div>Coverage: <strong>{(d.coverage * 100).toFixed(1)}%</strong></div>
      <div>Neglect Index: <strong>{d.neglect_index.toFixed(3)}</strong></div>
      <div>People in Need: <strong>{d.people_in_need.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong></div>
      {d.is_outlier && (
        <div style={{ color: '#dc2626', fontWeight: 600, marginTop: 6 }}>
          ⚠ Outlier from support cluster
        </div>
      )}
    </div>
  );
};

const TsneChart = ({ currentParams }) => {
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
      const key = d.kmeans_cluster;
      if (!map[key]) map[key] = [];
      map[key].push(d);
    });
    return map;
  }, [data]);

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
            <Tooltip content={<ChartTooltip />} cursor={{ strokeDasharray: '3 3' }} />
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
