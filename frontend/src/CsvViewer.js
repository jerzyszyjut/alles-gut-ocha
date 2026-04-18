import React from 'react';

/**
 * @param {Array} data - Array of objects (the filtered CSV data)
 * @param {number} totalCount - Total number of entries before filtering
 * @param {string} filter - Current search/filter string
 * @param {function} setFilter - Function to update the search string
 */
const CsvViewer = ({ data = [], totalCount = 0, filter, setFilter }) => {
  let headers;

  if (!data || data.length === 0) {
    headers = [];
  } else {
    headers = Object.keys(data[0]);
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
                <th key={h} style={styles.th}>{h.replace(/_/g, ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} style={i % 2 === 0 ? styles.trEven : styles.trOdd}>
                {headers.map((h) => {
                  const cellValue = row[h];
                  const displayValue = typeof cellValue === 'number' 
                    ? cellValue.toLocaleString(undefined, { maximumFractionDigits: 3 }) 
                    : cellValue;

                  return (
                    <td 
                      key={h} 
                      style={styles.td} 
                      title={String(cellValue)} // Native tooltip shows full text on hover
                    >
                      {displayValue}
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
    textTransform: 'capitalize',
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
  noData: {
    padding: '20px',
    textAlign: 'center',
    color: '#6a737d',
    fontSize: '14px'
  }
};

export default CsvViewer;