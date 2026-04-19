import React, { useState, useMemo, useEffect } from "react";
import CsvViewer from "./CsvViewer";
import WorldMap from "./WorldMap";
import Weights from "./Weights";
import TsneChart from "./TsneChart";
import CounterfactualSlider from "./CounterfactualSlider";


function App() {
  const [csvData, setCsvData] = useState([]);
  const [currentParams, setCurrentParams] = useState({});
  const [totalMatches, setTotalMatches] = useState(0);
  const [filterText, setFilterText] = useState("");
  const [topView, setTopView] = useState("map");
  const [viewMode, setViewMode] = useState("cluster");
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am your humanitarian crisis analyst. I can explain the neglect index, adjust weights, or filter the data. How can I help?', isGreeting: true }
  ]);
  const [selectedCrisis, setSelectedCrisis] = useState(null);
  const [counterfactualResult, setCounterfactualResult] = useState(null);

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
      setFilterText("");
    }
  };

  const allAvailableISOs = useMemo(() => new Set(csvData.map(r => r.countryCode)), [csvData]);

  // Country-level rollup: aggregate cluster rows per country, weighted by PIN
  const countryData = useMemo(() => {
    if (!csvData.length) return [];
    const byCountry = {};
    csvData.forEach(row => {
      if (!byCountry[row.countryCode]) {
        byCountry[row.countryCode] = {
          countryCode: row.countryCode,
          countryName: row.countryName,
          num_clusters: 0,
          _pin: 0,
          _neglect_w: 0,
          _ipc_w: 0,
          _ipc_pin: 0,
          priority_label: 'low',
        };
      }
      const c = byCountry[row.countryCode];
      const pin = row.people_in_need || 0;
      c.num_clusters += 1;
      if (row.country_total_pin && !c._country_total_pin) {
        c._country_total_pin = row.country_total_pin;
      }
      c._pin += pin;
      c._neglect_w += (row.neglect_index || 0) * pin;
      if (row.ipc_severity_score != null) {
        c._ipc_w += row.ipc_severity_score * pin;
        c._ipc_pin += pin;
      }
      const order = ['critical', 'high', 'medium', 'low'];
      if (order.indexOf(row.priority_label) < order.indexOf(c.priority_label)) {
        c.priority_label = row.priority_label;
      }
    });

    return Object.values(byCountry).map(c => ({
      countryCode: c.countryCode,
      countryName: c.countryName,
      num_clusters: c.num_clusters,
      people_in_need: c._country_total_pin || c._pin,
      neglect_index: c._pin > 0 ? +(c._neglect_w / c._pin).toFixed(4) : 0,
      ipc_severity_score: c._ipc_pin > 0 ? +(c._ipc_w / c._ipc_pin).toFixed(3) : null,
      priority_label: c.priority_label,
    })).sort((a, b) => b.neglect_index - a.neglect_index);
  }, [csvData]);

  const filteredData = useMemo(() => {
    if (!filterText) return csvData;
    const lower = filterText.toLowerCase();
    return csvData.filter(row =>
      Object.values(row).some(val => String(val).toLowerCase().includes(lower))
    );
  }, [csvData, filterText]);

  return (
    <div style={styles.appContainer}>
      <div style={styles.mainContent}>
        <div style={styles.mapSection}>
          <div style={styles.viewToggle}>
            <button
              style={topView === "map" ? styles.toggleActive : styles.toggleBtn}
              onClick={() => setTopView("map")}
            >
              Map
            </button>
            <button
              style={topView === "tsne" ? styles.toggleActive : styles.toggleBtn}
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
            <TsneChart
                currentParams={currentParams}
                selectedCrisis={selectedCrisis}
                counterfactualResult={counterfactualResult}
                rankingData={csvData}
              />
          )}
        </div>

        <div style={styles.csvSection}>
          <CsvViewer
            data={filteredData}
            countryData={countryData}
            totalCount={totalMatches}
            filter={filterText}
            setFilter={setFilterText}
            selectedCrisis={selectedCrisis}
            onSelectCrisis={setSelectedCrisis}
            viewMode={viewMode}
            setViewMode={setViewMode}
          />
        </div>
      </div>

      <div style={styles.sidebar}>
        {selectedCrisis && (
          <CounterfactualSlider
            crisis={selectedCrisis}
            currentParams={currentParams}
            onClose={() => { setSelectedCrisis(null); setCounterfactualResult(null); }}
            onResult={setCounterfactualResult}
          />
        )}
        <Weights
          messages={messages}
          setMessages={setMessages}
          currentParams={currentParams}
          onUpdateState={handleStateUpdateFromChat}
        />
      </div>

    </div>
  );
}

const styles = {
  appContainer: {
    display: "flex", flexDirection: "row",
    height: "100vh", width: "100vw",
    overflow: "hidden", backgroundColor: "#f0f2f5",
  },
  mainContent: {
    display: "flex", flexDirection: "column",
    flex: 1, height: "100%",
  },
  mapSection: {
    flex: 1, display: "flex", flexDirection: "column",
    position: "relative", margin: "10px",
    borderRadius: 12, backgroundColor: "#fff",
    border: "1px solid #e1e4e8", overflow: "hidden",
  },
  csvSection: {
    height: "40%", padding: "0 10px 10px 10px", overflow: "hidden",
  },
  sidebar: {
    width: 400, height: "100vh", padding: 10,
    display: "flex", flexDirection: "column", boxSizing: "border-box",
  },
  viewToggle: {
    position: "absolute", top: 10, right: 10, zIndex: 10,
    display: "flex", gap: 4, background: "#f6f8fa",
    borderRadius: 8, padding: 3, border: "1px solid #e1e4e8",
  },
  toggleBtn: {
    padding: "4px 14px", fontSize: 12, fontWeight: 500,
    border: "none", borderRadius: 6,
    background: "transparent", color: "#586069", cursor: "pointer",
  },
  toggleActive: {
    padding: "4px 14px", fontSize: 12, fontWeight: 600,
    border: "none", borderRadius: 6,
    background: "#fff", color: "#24292e", cursor: "pointer",
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
  },
};

export default App;
