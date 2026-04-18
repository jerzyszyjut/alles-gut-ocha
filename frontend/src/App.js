import React, { useState } from 'react';
import Chat from './Chat';
import CsvViewer from './CsvViewer';
import { DUMMY_NEGLECT_DATA } from './dummy';
import WorldMap from "./WorldMap";

function App() {
  const [filterText, setFilterText] = useState("");

  return (
    <div style={styles.appContainer}>
      {/* LEFT SIDE: Map (Top) and CSV (Bottom) */}
      <div style={styles.mainContent}>
        <WorldMap setHoveredCountry={setFilterText} />

        {/* CSV Viewer at the bottom */}
        <div style={styles.csvSection}>
          <CsvViewer 
            data={DUMMY_NEGLECT_DATA}
            filter={filterText} 
            setFilter={setFilterText}
          />
        </div>
      </div>

      <div style={styles.sidebar}>
        <Chat />
      </div>
    </div>
  );
}

const styles = {
  appContainer: {
    display: 'flex',
    flexDirection: 'row',
    height: '100vh',    // Full viewport height
    width: '100vw',     // Full viewport width
    overflow: 'hidden', // Forces "No Scroll" <3
    backgroundColor: '#f0f2f5',
  },
  mainContent: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,            // Takes up all space not used by the sidebar
    height: '100%',
  },
  mapPlaceholder: {
    flex: 1,            // Map takes up all remaining top space
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#e5e7eb',
    margin: '10px',
    borderRadius: '12px',
    border: '2px dashed #9ca3af',
  },
  mapText: {
    textAlign: 'center',
    color: '#6b7280',
    fontSize: '1.2rem',
  },
  csvSection: {
    height: '40%',      // CSV takes up the bottom 40%
    padding: '0 10px 10px 10px',
  },
  sidebar: {
    width: '400px',
    height: '100vh',
    padding: '10px',
    display: 'flex',
  }
};

export default App;