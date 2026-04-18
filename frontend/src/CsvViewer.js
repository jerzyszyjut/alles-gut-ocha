import React, { useState, useMemo } from 'react';

/**
 * @param {Array} data - Array of objects (the CSV data)
 * @param {string} initialFocus - Optional initial search term
 */
const CsvViewer = ({ data = [], initialFocus = '' }) => {
  const [filter, setFilter] = useState(initialFocus);

  const filteredData = useMemo(() => {
    if (!filter) return data;
    const lowerFilter = filter.toLowerCase();
    return data.filter((row) =>
      Object.values(row).some((val) =>
        String(val).toLowerCase().includes(lowerFilter)
      )
    );
  }, [data, filter]);

  if (!data || data.length === 0) return <p>No data available to view.</p>;

  // Extract headers from the first object
  const headers = Object.keys(data[0]);

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
          Showing {filteredData.length} of {data.length} entries
        </span>
      </div>

      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h} style={styles.th}>{h.replace(/_/g, ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredData.map((row, i) => (
              <tr key={i} style={i % 2 === 0 ? styles.trEven : styles.trOdd}>
                {headers.map((h) => (
                  <td key={h} style={styles.td}>
                    {/* Formatting numbers for readability */}
                    {typeof row[h] === 'number' 
                      ? row[h].toLocaleString(undefined, { maximumFractionDigits: 3 }) 
                      : row[h]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
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
    margin: '20px 0'
  },
  toolbar: {
    padding: '15px',
    backgroundColor: '#f6f8fa',
    borderBottom: '1px solid #e1e4e8',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  searchInput: {
    padding: '8px 12px',
    borderRadius: '6px',
    border: '1px solid #d1d5da',
    width: '300px',
    fontSize: '14px'
  },
  stats: {
    fontSize: '13px',
    color: '#586069'
  },
  tableWrapper: {
    overflowX: 'auto',
    maxHeight: '500px'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px',
    textAlign: 'left'
  },
  th: {
    position: 'sticky',
    top: 0,
    backgroundColor: '#fff',
    padding: '12px',
    borderBottom: '2px solid #e1e4e8',
    color: '#24292e',
    textTransform: 'capitalize',
    zIndex: 1
  },
  td: {
    padding: '10px 12px',
    borderBottom: '1px solid #eaecef',
    whiteSpace: 'nowrap'
  },
  trEven: { backgroundColor: '#fff' },
  trOdd: { backgroundColor: '#fafbfc' }
};

export default CsvViewer;