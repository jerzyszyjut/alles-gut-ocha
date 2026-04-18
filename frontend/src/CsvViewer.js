import React from 'react';

const HIDDEN_COLUMNS = new Set(['countryCode']);

const COLUMN_LABELS = {
  countryName: 'Country',
  cluster: 'Cluster',
  people_in_need: 'People in Need',
  requirements_usd: 'Requirements (USD)',
  funding_usd: 'Funding (USD)',
  coverage: 'Coverage',
  neglect_index: 'Neglect Index',
  need_rank: 'Need Rank',
  coverage_rank: 'Coverage Rank',
  ipc_severity_score: 'IPC Severity Score',
  uncertainty: 'Uncertainty',
  priority_label: 'Priority',
};

const formatLabel = (key) =>
  COLUMN_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const NON_NUMERIC_COLUMNS = new Set(['countryCode', 'countryName', 'cluster', 'priority_label']);

const CsvViewer = ({ data = [], totalCount = 0, filter, setFilter }) => {
  let headers;

  if (!data || data.length === 0) {
    headers = [];
  } else {
    headers = Object.keys(data[0]).filter((h) => !HIDDEN_COLUMNS.has(h));
  }

  return (
    <div style={styles.container}>
      <div style={styles.toolbar}>
        <input
          type="text"
          placeholder="Focus on country, cluster, or score..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={styles.searchInput}
        />
        <span style={styles.stats}>
          Showing <strong>{data.length}</strong> of <strong>{totalCount}</strong> entries
        </span>
      </div>

      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h} style={styles.th}>{formatLabel(h)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} style={i % 2 === 0 ? styles.trEven : styles.trOdd}>
                {headers.map((h) => {
                  const cellValue = row[h];
                  const isEmpty = cellValue === null || cellValue === undefined || cellValue === '';

                  const displayValue = isEmpty
                    ? null
                    : typeof cellValue === 'number' && !NON_NUMERIC_COLUMNS.has(h)
                      ? cellValue.toLocaleString(undefined, { maximumFractionDigits: 3 })
                      : cellValue;

                  return (
                    <td
                      key={h}
                      style={isEmpty ? { ...styles.td, ...styles.tdEmpty } : styles.td}
                      title={isEmpty ? undefined : String(cellValue)}
                    >
                      {isEmpty ? <span style={styles.emptyCell}>—</span> : displayValue}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {data.length === 0 && (
          <div style={styles.noData}>No matching entries found.</div>
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    fontFamily: 'Inter, sans-serif',
    border: '1px solid #e1e4e8',
    borderRadius: '8px',
    backgroundColor: '#fff',
    overflow: 'hidden',
    height: '100%',
    display: 'flex',
    flexDirection: 'column'
  },
  toolbar: {
    padding: '12px 15px',
    backgroundColor: '#f6f8fa',
    borderBottom: '1px solid #e1e4e8',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexShrink: 0
  },
  searchInput: {
    padding: '8px 12px',
    borderRadius: '6px',
    border: '1px solid #d1d5da',
    width: '280px',
    fontSize: '14px',
    outline: 'none'
  },
  stats: {
    fontSize: '13px',
    color: '#586069'
  },
  tableWrapper: {
    overflowX: 'auto',
    overflowY: 'auto',
    flex: 1
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px',
    textAlign: 'left',
    tableLayout: 'fixed' // Helps enforce the cell width limits
  },
  th: {
    position: 'sticky',
    top: 0,
    backgroundColor: '#fff',
    padding: '12px',
    borderBottom: '2px solid #e1e4e8',
    color: '#24292e',
    zIndex: 1,
    whiteSpace: 'nowrap'
  },
  td: {
    padding: '10px 12px',
    borderBottom: '1px solid #eaecef',
    // Ellipsis Logic
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    maxWidth: '180px' // Adjust this value as needed
  },
  trEven: { backgroundColor: '#fff' },
  trOdd: { backgroundColor: '#fafbfc' },
  tdEmpty: { color: '#bbb' },
  emptyCell: { userSelect: 'none' },
  noData: {
    padding: '20px',
    textAlign: 'center',
    color: '#6a737d',
    fontSize: '14px'
  }
};

export default CsvViewer;