import React, { useState, useMemo, useEffect } from 'react';
import Chat from './Chat';
import CsvViewer from './CsvViewer';
import WorldMap from "./WorldMap";

function App() {
  // 1. App-level state for Backend Data and API Parameters
  const [csvData, setCsvData] = useState([]);
  const [currentParams, setCurrentParams] = useState({});
  const [totalMatches, setTotalMatches] = useState(0);

  const [filterText, setFilterText] = useState("");

  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const response = await fetch('http://localhost:8000/ranking?limit=25');
        if (!response.ok) throw new Error("Failed to fetch");
        const data = await response.json();
        setCsvData(data.results || []);
        setTotalMatches(data.total_matches || 0);
      } catch (err) {
        console.error("Failed to fetch initial ranking data", err);
      }
    };
    fetchInitialData();
  }, []);

  const handleStateUpdateFromChat = (newParams, newSnapshot) => {
    if (newParams) {
      setCurrentParams(newParams);
    }
    if (newSnapshot && newSnapshot.length > 0) {
      setCsvData(newSnapshot);
      setFilterText(""); // Clear local filter when AI changes the global view
    }
  };

  const filteredData = useMemo(() => {
    if (!filterText) return csvData;
    const lowerFilter = filterText.toLowerCase();
    return csvData.filter((row) =>
      Object.values(row).some((val) =>
        String(val).toLowerCase().includes(lowerFilter)
      )
    );
  }, [filterText, csvData]);

  const searchMatches = useMemo(() => {
    return new Set(filteredData.map(row => row.countryCode)); 
  }, [filteredData]);

  return (
    <div style={styles.appContainer}>
      
      {/* LEFT SIDE: Map (Top) and CSV (Bottom) */}
      <div style={styles.mainContent}>
        
        {/* World Map Component */}
        <div style={styles.mapSection}>
           <WorldMap
            setHoveredCountry={setFilterText}
            availableCountries={searchMatches}
          />
        </div>

        {/* CSV Viewer at the bottom */}
        <div style={styles.csvSection}>
          <CsvViewer 
            data={filteredData}
            totalCount={totalMatches}
            filter={filterText} 
            setFilter={setFilterText}
          />
        </div>
      </div>

      {/* RIGHT SIDE: Chat pinned to the right */}
      <div style={styles.sidebar}>
        <Chat 
          currentParams={currentParams} 
          onUpdateState={handleStateUpdateFromChat} 
        />
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
    overflow: 'hidden', // Forces "No Scroll" 
    backgroundColor: '#f0f2f5',
  },
  mainContent: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,            // Takes up all space not used by the sidebar
    height: '100%',
  },
  mapSection: {
    flex: 1,            // Map takes up all remaining top space
    display: 'flex',
    flexDirection: 'column',
    position: 'relative', // Ensures map renders correctly within bounds
    margin: '10px',
    borderRadius: '12px',
    backgroundColor: '#fff',
    border: '1px solid #e1e4e8',
    overflow: 'hidden',
  },
  csvSection: {
    height: '40%',      // CSV takes up the bottom 40%
    padding: '0 10px 10px 10px',
    overflow: 'hidden'
  },
  sidebar: {
    width: '400px',     // Fixed width for the chat
    height: '100vh',
    padding: '10px',
    display: 'flex',
  }
};

export default App;