import React, { useState, useMemo, useEffect } from "react";
import Chat from "./Chat";
import CsvViewer from "./CsvViewer";
import WorldMap from "./WorldMap";
import Weights from "./Weights";
import TsneChart from "./TsneChart";

function App() {
  const [csvData, setCsvData] = useState([]);
  const [currentParams, setCurrentParams] = useState({});
  const [totalMatches, setTotalMatches] = useState(0);
  const [filterText, setFilterText] = useState("");
  const [topView, setTopView] = useState("map");

  // Fetch data from your FastAPI/Node backend
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const response = await fetch("http://localhost:8000/ranking");
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
    return new Set(csvData.map((row) => row.countryCode));
  }, [csvData]);

  // 2. FILTER LOGIC: Sub-filtering for the CSV table based on Click/Search
  const filteredData = useMemo(() => {
    if (!filterText) return csvData;
    const lowerFilter = filterText.toLowerCase();
    return csvData.filter((row) =>
      Object.values(row).some((val) =>
        String(val).toLowerCase().includes(lowerFilter),
      ),
    );
  }, [csvData, filterText]);

  return (
    <div style={styles.appContainer}>
      <div style={styles.mainContent}>
        {/* TOP: Map / t-SNE toggle section */}
        <div style={styles.mapSection}>
          <div style={styles.viewToggle}>
            <button
              style={topView === "map" ? styles.toggleActive : styles.toggleBtn}
              onClick={() => setTopView("map")}
            >
              Map
            </button>
            <button
              style={
                topView === "tsne" ? styles.toggleActive : styles.toggleBtn
              }
              onClick={() => setTopView("tsne")}
            >
              t-SNE
            </button>
          </div>
          {topView === "map" ? (
            <WorldMap
              setHoveredCountry={setFilterText}
              availableCountries={allAvailableISOs}
              activeFilter={filterText}
            />
          ) : (
            <TsneChart currentParams={currentParams} />
          )}
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
        <Weights />
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
    display: "flex",
    flexDirection: "row",
    height: "100vh",
    width: "100vw",
    overflow: "hidden",
    backgroundColor: "#f0f2f5",
  },
  mainContent: {
    display: "flex",
    flexDirection: "column",
    flex: 1,
    height: "100%",
  },
  // --- UPDATED SIDEBAR & CHILDREN ---
  sidebar: {
    width: "400px",
    height: "100vh",
    padding: "10px",
    display: "flex", // Turn sidebar into flexbox
    flexDirection: "column", // Stack Weights and Chat vertically
    gap: "10px", // Adds space between the two components
    boxSizing: "border-box", // Ensures padding doesn't break the 100vh
  },
  weightsWrapper: {
    flexShrink: 0, // Prevents Weights from squishing
  },
  chatWrapper: {
    flex: 1, // Forces Chat to take up all remaining space
    display: "flex",
    flexDirection: "column",
    overflow: "hidden", // Important so the Chat's internal scroll works
  },
  mapSection: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    position: "relative",
    margin: "10px",
    borderRadius: "12px",
    backgroundColor: "#fff",
    border: "1px solid #e1e4e8",
    overflow: "hidden",
  },
  csvSection: {
    height: "40%",
    padding: "0 10px 10px 10px",
    overflow: "hidden",
  },
  sidebar: {
    width: "400px",
    height: "100vh",
    padding: "10px",
    display: "flex",
  },
  viewToggle: {
    position: "absolute",
    top: 10,
    right: 10,
    zIndex: 10,
    display: "flex",
    gap: 4,
    background: "#f6f8fa",
    borderRadius: 8,
    padding: 3,
    border: "1px solid #e1e4e8",
  },
  toggleBtn: {
    padding: "4px 14px",
    fontSize: 12,
    fontWeight: 500,
    border: "none",
    borderRadius: 6,
    background: "transparent",
    color: "#586069",
    cursor: "pointer",
  },
  toggleActive: {
    padding: "4px 14px",
    fontSize: 12,
    fontWeight: 600,
    border: "none",
    borderRadius: 6,
    background: "#fff",
    color: "#24292e",
    cursor: "pointer",
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
  },
};

export default App;
