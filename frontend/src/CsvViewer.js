import React, { useState } from 'react';

// Columns hidden from the generic column list (rendered via custom logic or unused)
const HIDDEN_CLUSTER = new Set(['countryCode', 'rank_ci_low', 'rank_ci_high', 'n_years_data']);

const COLUMN_LABELS = {
  rank:                          'Rank',
  countryName:                   'Country',
  cluster:                       'Cluster',
  severity_case:                 'Inputs',
  people_in_need:                'People in Need',
  requirements_usd:              'Requirements (USD)',
  funding_usd:                   'Funding (USD)',
  coverage:                      'Coverage',
  neglect_index:                 'Neglect Index',
  need_rank:                     'Need Rank',
  coverage_rank:                 'Coverage Rank',
  ipc_severity_score:            'IPC Severity',
  uncertainty:                   'Uncertainty',
  priority_label:                'Priority',
  neglect_type:                  'Neglect Type',
  structural_neglect_score:      'Structural Score',
  consecutive_years_underfunded: 'Yrs Underfunded',
  coverage_trend:                'Funding Trend',
};

const COUNTRY_HEADERS = [
  'countryName', 'num_clusters', 'people_in_need',
  'neglect_index', 'ipc_severity_score', 'priority_label',
];
const COUNTRY_LABELS = {
  countryName:        'Country',
  num_clusters:       'Clusters',
  people_in_need:     'Total People in Need',
  neglect_index:      'Weighted Neglect',
  ipc_severity_score: 'Avg IPC Severity',
  priority_label:     'Highest Priority',
};

const NON_NUMERIC = new Set([
  'countryCode', 'countryName', 'cluster', 'priority_label', 'severity_case', 'neglect_type',
]);

const PRIORITY_COLORS = {
  critical: '#dc2626', high: '#d97706', medium: '#2563eb', low: '#6b7280',
};
const CASE_COLORS = { A: '#16a34a', B: '#2563eb', C: '#d97706', D: '#6b7280' };
const CASE_TIPS = {
  A: 'Need + IPC food severity + Conflict events',
  B: 'Need + IPC food severity (no conflict data)',
  C: 'Need + Conflict events (no IPC food data)',
  D: 'Need rank only — limited indicator coverage',
};

const formatLabel = (key, isCountry) => {
  const labels = isCountry ? COUNTRY_LABELS : COLUMN_LABELS;
  return labels[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

const NEGLECT_TYPE_OPTIONS = [
  { value: null,         label: 'All',        color: '#586069' },
  { value: 'structural', label: 'Structural',  color: '#7c3aed' },
  { value: 'worsening',  label: 'Worsening',   color: '#dc2626' },
  { value: 'acute',      label: 'Acute',       color: '#d97706' },
  { value: 'improving',  label: 'Improving',   color: '#16a34a' },
];

const CsvViewer = ({
  data = [],
  countryData = [],
  totalCount = 0,
  filter,
  setFilter,
  viewMode = 'cluster',
  setViewMode,
  selectedCrisis,
  onSelectCrisis,
}) => {
  const [neglectTypeFilter, setNeglectTypeFilter] = useState(null);
  const isCountry = viewMode === 'country';
  const rows = isCountry ? countryData : data;

  const headers = isCountry
    ? COUNTRY_HEADERS
    : (rows.length > 0
        ? Object.keys(rows[0]).filter(h => !HIDDEN_CLUSTER.has(h))
        : []);

  const filtered = rows.filter(row => {
    if (filter && !Object.values(row).some(v => String(v).toLowerCase().includes(filter.toLowerCase()))) {
      return false;
    }
    if (!isCountry && neglectTypeFilter && row.neglect_type !== neglectTypeFilter) {
      return false;
    }
    return true;
  });

  const isSelected = (row) =>
    selectedCrisis &&
    selectedCrisis.countryCode === row.countryCode &&
    selectedCrisis.cluster === row.cluster;

  const handleRowClick = (row) => {
    if (onSelectCrisis) onSelectCrisis(isSelected(row) ? null : row);
  };

  const renderCell = (h, row) => {
    const v = row[h];
    const isEmpty = v === null || v === undefined || v === '';

    if (isEmpty) {
      return <td key={h} style={styles.td}><span style={styles.empty}>—</span></td>;
    }

    // Rank: show "#N [CI low–high]" with CI width color-coded
    if (h === 'rank') {
      const lo = row.rank_ci_low;
      const hi = row.rank_ci_high;
      const span = lo != null && hi != null ? hi - lo : null;
      const ciColor = span == null ? '#999' : span <= 3 ? '#16a34a' : span <= 8 ? '#d97706' : '#dc2626';
      return (
        <td key={h} style={styles.td} title={span != null ? `Bootstrap rank CI [${lo}–${hi}] at 90% confidence (width ${span})` : undefined}>
          <span style={{ fontWeight: 600 }}>#{v}</span>
          {lo != null && hi != null && (
            <span style={{ color: ciColor, fontSize: 10, marginLeft: 4 }}>
              [{lo}–{hi}]
            </span>
          )}
        </td>
      );
    }

    // Neglect index: mini bar with ±uncertainty overlay
    if (h === 'neglect_index') {
      const u = row.uncertainty;
      const W = 72;
      const barW = Math.round(v * W);
      const uLo = u != null ? Math.round(Math.max(0, v - u) * W) : null;
      const uHi = u != null ? Math.round(Math.min(1, v + u) * W) : null;
      return (
        <td key={h} style={styles.td} title={u != null ? `${v.toFixed(4)} ± ${u.toFixed(4)} (1σ bootstrap)` : v.toFixed(4)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ fontWeight: 600, fontSize: 12, minWidth: 32 }}>{v.toFixed(3)}</span>
            <div style={{ position: 'relative', height: 5, width: W, background: '#e5e7eb', borderRadius: 3, flexShrink: 0 }}>
              {uLo != null && (
                <div style={{
                  position: 'absolute', left: uLo, width: uHi - uLo,
                  top: 0, height: '100%', background: '#fca5a5', borderRadius: 2,
                }} />
              )}
              <div style={{
                position: 'absolute', left: 0, width: barW,
                top: 0, height: '100%', background: '#2563eb', borderRadius: 3,
              }} />
            </div>
          </div>
        </td>
      );
    }

    // Uncertainty: colored badge (low/medium/high)
    if (h === 'uncertainty') {
      const level = v < 0.03 ? 'low' : v < 0.07 ? 'medium' : 'high';
      const UCOL = { low: '#16a34a', medium: '#d97706', high: '#dc2626' };
      const c = UCOL[level];
      return (
        <td key={h} style={styles.td} title={`Bootstrap σ = ${v.toFixed(4)} — std dev of neglect index across 50 resamples`}>
          <span style={{
            display: 'inline-block', padding: '1px 7px', borderRadius: 10,
            fontSize: 11, fontWeight: 600,
            background: c + '18', color: c, border: `1px solid ${c}44`,
          }}>
            {level} {v.toFixed(3)}
          </span>
        </td>
      );
    }

    // Severity case: colored badge with tooltip
    if (h === 'severity_case') {
      const color = CASE_COLORS[v] || '#6b7280';
      return (
        <td key={h} style={styles.td} title={CASE_TIPS[v] || v}>
          <span style={{
            display: 'inline-block',
            padding: '1px 7px', borderRadius: 10,
            fontSize: 11, fontWeight: 600,
            background: color + '20', color,
            border: `1px solid ${color}55`,
            cursor: 'help',
          }}>
            {v}
          </span>
        </td>
      );
    }

    // Priority label: colored badge
    if (h === 'priority_label') {
      const color = PRIORITY_COLORS[v] || '#6b7280';
      return (
        <td key={h} style={styles.td}>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px', borderRadius: 10,
            fontSize: 11, fontWeight: 600,
            background: color + '18', color,
            border: `1px solid ${color}44`,
            textTransform: 'capitalize',
          }}>
            {v}
          </span>
        </td>
      );
    }

    // Neglect type: colored badge
    if (h === 'neglect_type') {
      const NEGLECT_COLORS = {
        structural: '#7c3aed', worsening: '#dc2626',
        acute: '#d97706', improving: '#16a34a', adequate: '#6b7280',
      };
      const NEGLECT_TIPS = {
        structural: '≥3 consecutive underfunded years — systemic failure',
        worsening:  'Coverage declining rapidly — on the structural path',
        acute:      'Currently underfunded but not yet chronic',
        improving:  'Coverage recovering — positive trend',
        adequate:   'Adequately funded',
      };
      const color = NEGLECT_COLORS[v] || '#6b7280';
      return (
        <td key={h} style={styles.td} title={NEGLECT_TIPS[v] || v}>
          <span style={{
            display: 'inline-block', padding: '1px 7px', borderRadius: 10,
            fontSize: 11, fontWeight: 600,
            background: color + '18', color,
            border: `1px solid ${color}44`,
            textTransform: 'capitalize', cursor: 'help',
          }}>
            {v}
          </span>
        </td>
      );
    }

    // Coverage trend: show arrow + value
    if (h === 'coverage_trend') {
      const arrow = v > 0.005 ? '▲' : v < -0.005 ? '▼' : '→';
      const color = v > 0.005 ? '#16a34a' : v < -0.005 ? '#dc2626' : '#6b7280';
      return (
        <td key={h} style={styles.td} title={`${v > 0 ? '+' : ''}${v.toFixed(3)} coverage per year`}>
          <span style={{ color, fontWeight: 600 }}>
            {arrow} {Math.abs(v).toFixed(3)}
          </span>
        </td>
      );
    }

    const display = typeof v === 'number' && !NON_NUMERIC.has(h)
      ? v.toLocaleString(undefined, { maximumFractionDigits: 3 })
      : v;

    return (
      <td key={h} style={styles.td} title={String(v)}>
        {display}
      </td>
    );
  };

  return (
    <div style={styles.container}>
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          <input
            type="text"
            placeholder="Filter by country, cluster, or score..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            style={styles.searchInput}
          />
          {!isCountry && (
            <div style={styles.neglectTypeBar} title="Filter by structural neglect classification">
              {NEGLECT_TYPE_OPTIONS.map(opt => {
                const active = neglectTypeFilter === opt.value;
                return (
                  <button
                    key={opt.value ?? 'all'}
                    onClick={() => setNeglectTypeFilter(active ? null : opt.value)}
                    style={{
                      ...styles.neglectBtn,
                      background: active ? opt.color + '22' : 'transparent',
                      color: active ? opt.color : '#586069',
                      border: `1px solid ${active ? opt.color : '#d1d5da'}`,
                      fontWeight: active ? 700 : 500,
                    }}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          )}
          {setViewMode && (
            <div style={styles.toggleGroup}>
              <button
                style={viewMode === 'cluster' ? styles.toggleActive : styles.toggleBtn}
                onClick={() => setViewMode('cluster')}
              >
                By Cluster
              </button>
              <button
                style={viewMode === 'country' ? styles.toggleActive : styles.toggleBtn}
                onClick={() => setViewMode('country')}
              >
                By Country
              </button>
            </div>
          )}
        </div>
        <span style={styles.stats}>
          {!isCountry && onSelectCrisis && <span style={styles.hint}>Click a row to explore counterfactual funding · </span>}
          {isCountry
            ? <><strong>{filtered.length}</strong> countries</>
            : <>Showing <strong>{filtered.length}</strong> of <strong>{totalCount}</strong> crises</>
          }
        </span>
      </div>

      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              {headers.map(h => (
                <th key={h} style={styles.th}>{formatLabel(h, isCountry)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => {
              const selected = isSelected(row);
              const baseStyle = i % 2 === 0 ? styles.trEven : styles.trOdd;
              const rowStyle = selected
                ? { ...baseStyle, ...styles.trSelected }
                : onSelectCrisis
                ? { ...baseStyle, cursor: 'pointer' }
                : baseStyle;
              return (
                <tr key={i} style={rowStyle} onClick={() => handleRowClick(row)}>
                  {headers.map(h => renderCell(h, row))}
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div style={styles.noData}>No matching entries found.</div>
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    fontFamily: 'Inter, sans-serif',
    border: '1px solid #e1e4e8', borderRadius: 8,
    backgroundColor: '#fff', overflow: 'hidden',
    height: '100%', display: 'flex', flexDirection: 'column',
  },
  toolbar: {
    padding: '10px 15px',
    backgroundColor: '#f6f8fa',
    borderBottom: '1px solid #e1e4e8',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    flexShrink: 0, gap: 10,
  },
  toolbarLeft: { display: 'flex', alignItems: 'center', gap: 10 },
  searchInput: {
    padding: '6px 12px', borderRadius: 6,
    border: '1px solid #d1d5da', width: 240,
    fontSize: 13, outline: 'none',
  },
  toggleGroup: {
    display: 'flex', background: '#e8eaed',
    borderRadius: 6, padding: 2, gap: 2,
  },
  toggleBtn: {
    padding: '3px 12px', fontSize: 12, fontWeight: 500,
    border: 'none', borderRadius: 4,
    background: 'transparent', color: '#586069', cursor: 'pointer',
  },
  toggleActive: {
    padding: '3px 12px', fontSize: 12, fontWeight: 600,
    border: 'none', borderRadius: 4,
    background: '#fff', color: '#24292e', cursor: 'pointer',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
  },
  stats: { fontSize: 12, color: '#586069', whiteSpace: 'nowrap' },
  neglectTypeBar: { display: 'flex', gap: 4, alignItems: 'center' },
  neglectBtn: {
    padding: '2px 9px', fontSize: 11, borderRadius: 12,
    cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.15s',
  },
  tableWrapper: { overflowX: 'auto', overflowY: 'auto', flex: 1 },
  table: {
    width: '100%', borderCollapse: 'collapse',
    fontSize: 13, textAlign: 'left', tableLayout: 'fixed',
  },
  th: {
    position: 'sticky', top: 0,
    backgroundColor: '#fff', padding: '10px 12px',
    borderBottom: '2px solid #e1e4e8', color: '#24292e',
    zIndex: 1, whiteSpace: 'nowrap',
  },
  td: {
    padding: '9px 12px', borderBottom: '1px solid #eaecef',
    whiteSpace: 'nowrap', overflow: 'hidden',
    textOverflow: 'ellipsis', maxWidth: 180,
  },
  trEven: { backgroundColor: '#fff' },
  trOdd: { backgroundColor: '#fafbfc' },
  trSelected: { backgroundColor: '#eff6ff', outline: '1.5px solid #1d4ed8', outlineOffset: '-1px' },
  empty: { color: '#ccc', userSelect: 'none' },
  hint: { color: '#94a3b8', fontSize: '12px' },
  noData: { padding: 20, textAlign: 'center', color: '#6a737d', fontSize: 14 },
};

export default CsvViewer;
