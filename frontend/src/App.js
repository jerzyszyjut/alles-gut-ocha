import React, { useState, useMemo, useEffect } from 'react';
import Chat from './Chat';
import CsvViewer from './CsvViewer';
import WorldMap from "./WorldMap";

function App() {
  const [csvData, setCsvData] = useState([]);
  const [currentParams, setCurrentParams] = useState({});
  const [totalMatches, setTotalMatches] = useState(0);
  const [filterText, setFilterText] = useState("");

  // Fetch data from your FastAPI/Node backend
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const response = await fetch('http://localhost:8000/ranking');
        if (!response.ok) throw new Error("Failed to fetch");
        const data = await response.json();
        setCsvData(data.results || []);
        setTotalMatches(data.total_matches || 0);
      } catch (err) {
        console.error("Failed to fetch ranking data", err);
      }
    };
    fetchInitialData();
  }, []);

  const handleStateUpdateFromChat = (newParams, newSnapshot) => {
    if (newParams) setCurrentParams(newParams);
    if (newSnapshot && newSnapshot.length > 0) {
      setCsvData(newSnapshot);
      setFilterText(""); // Reset local search when AI updates data
    }
  };

  // 1. HIGHLIGHT LOGIC: Permanent list of ISOs that exist in your current data
  const allAvailableISOs = useMemo(() => {
    return new Set(csvData.map(row => row.countryCode)); 
  }, [csvData]);

  // 2. FILTER LOGIC: Sub-filtering for the CSV table based on Click/Search
  const filteredData = useMemo(() => {
    if (!filterText) return csvData;
    const lowerFilter = filterText.toLowerCase();
    return csvData.filter((row) =>
      Object.values(row).some((val) =>
        String(val).toLowerCase().includes(lowerFilter)
      )
    );
  }, [csvData, filterText]);

  return (
    <div style={styles.appContainer}>
      <div style={styles.mainContent}>
        
        {/* TOP: Map Section */}
        <div style={styles.mapSection}>
           <WorldMap
            setHoveredCountry={setFilterText}
            availableCountries={allAvailableISOs} 
            activeFilter={filterText}             
          />
        </div>

        {/* BOTTOM: CSV Section */}
        <div style={styles.csvSection}>
          <CsvViewer 
            data={filteredData}
            totalCount={totalMatches}
            filter={filterText} 
            setFilter={setFilterText}
          />
        </div>
      </div>

      {/* RIGHT: Chat Sidebar */}
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
  appContainer: { display: 'flex', flexDirection: 'row', height: '100vh', width: '100vw', overflow: 'hidden', backgroundColor: '#f0f2f5' },
  mainContent: { display: 'flex', flexDirection: 'column', flex: 1, height: '100%' },
  mapSection: { flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', margin: '10px', borderRadius: '12px', backgroundColor: '#fff', border: '1px solid #e1e4e8', overflow: 'hidden' },
  csvSection: { height: '40%', padding: '0 10px 10px 10px', overflow: 'hidden' },
  sidebar: { width: '400px', height: '100vh', padding: '10px', display: 'flex' }
};

export default App;