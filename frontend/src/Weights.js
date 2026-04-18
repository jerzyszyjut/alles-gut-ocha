import React, { useState, useMemo } from 'react';

const Weights = ({ currentParams = {}, onWeightsChange }) => {
  // Use currentParams if passed from App.js, otherwise fallback to defaults from Python
  const [weights, setWeights] = useState({
    severity_weight: currentParams.severity_weight ?? 0.6,
    funding_gap_weight: currentParams.funding_gap_weight ?? 0.4,
    need_weight: currentParams.need_weight ?? 0.5,
    ipc_weight: currentParams.ipc_weight ?? 0.4,
    events_weight: currentParams.events_weight ?? 0.1,
  });

  // Handle local slider changes
  const handleChange = (e) => {
    const { name, value } = e.target;
    const newWeights = { ...weights, [name]: parseFloat(value) };
    setWeights(newWeights);
    
    // Optional: Trigger parent update to fetch new rankings from FastAPI
    if (onWeightsChange) {
      onWeightsChange(newWeights);
    }
  };

  // 1. Auto-normalize top-level weights
  const topTotal = weights.severity_weight + weights.funding_gap_weight || 1;
  const normSeverity = (weights.severity_weight / topTotal).toFixed(2);
  const normFunding = (weights.funding_gap_weight / topTotal).toFixed(2);

  // 2. Auto-normalize sub-weights (Assuming Case A: All data available for illustration)
  const subTotal = weights.need_weight + weights.ipc_weight + weights.events_weight || 1;
  const normNeed = (weights.need_weight / subTotal).toFixed(2);
  const normIpc = (weights.ipc_weight / subTotal).toFixed(2);
  const normEvents = (weights.events_weight / subTotal).toFixed(2);

  return (
    <div style={styles.container}>
      <h2 style={styles.header}>Scoring Methodology & Weights</h2>
      <p style={styles.description}>
        The <strong>Neglect Index (0-1)</strong> identifies crises that are simultaneously severe and underfunded. 
        Adjust the weights below to change how the algorithm prioritizes crises.
      </p>

      {/* TOP LEVEL WEIGHTS */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>1. Top-Level Balance</h3>
        <p style={styles.mathText}>
          <code>Neglect = ({normSeverity} × Severity) + ({normFunding} × Funding Gap)</code>
        </p>
        
        <WeightSlider 
          label="Severity Weight" 
          name="severity_weight" 
          value={weights.severity_weight} 
          onChange={handleChange} 
        />
        <WeightSlider 
          label="Funding Gap Weight" 
          name="funding_gap_weight" 
          value={weights.funding_gap_weight} 
          onChange={handleChange} 
        />
      </div>

      {/* SEVERITY SUB-WEIGHTS */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>2. Severity Composition</h3>
        <p style={styles.mathText}>
          When all data is available, the algorithm auto-normalizes the sub-weights: <br/>
          <code>Severity = ({normNeed} × Need Rank) + ({normIpc} × IPC) + ({normEvents} × Conflict)</code>
        </p>

        <WeightSlider 
          label="People In Need Weight" 
          name="need_weight" 
          value={weights.need_weight} 
          onChange={handleChange} 
        />
        <WeightSlider 
          label="Food Insecurity (IPC) Weight" 
          name="ipc_weight" 
          value={weights.ipc_weight} 
          onChange={handleChange} 
        />
        <WeightSlider 
          label="Conflict Events Weight" 
          name="events_weight" 
          value={weights.events_weight} 
          onChange={handleChange} 
        />
      </div>

      <div style={styles.infoBox}>
        <strong>Note on Missing Data:</strong> If a sector lacks IPC or Conflict data, the algorithm 
        automatically drops those variables and scales the remaining weights up to 100% to ensure fair comparison.
      </div>
    </div>
  );
};

// Reusable Slider Component
const WeightSlider = ({ label, name, value, onChange }) => (
  <div style={styles.sliderRow}>
    <div style={styles.sliderLabel}>
      <span>{label}</span>
      <strong>{value.toFixed(2)}</strong>
    </div>
    <input 
      type="range" 
      name={name}
      min="0" 
      max="1" 
      step="0.05" 
      value={value} 
      onChange={onChange}
      style={styles.slider}
    />
  </div>
);

const styles = {
  container: {
    padding: '20px',
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    border: '1px solid #e1e4e8',
    fontFamily: 'sans-serif',
    maxWidth: '600px'
  },
  header: {
    margin: '0 0 10px 0',
    fontSize: '20px',
    color: '#24292e'
  },
  description: {
    fontSize: '14px',
    color: '#586069',
    lineHeight: '1.5',
    marginBottom: '20px'
  },
  section: {
    backgroundColor: '#f6f8fa',
    padding: '15px',
    borderRadius: '6px',
    marginBottom: '15px'
  },
  sectionTitle: {
    margin: '0 0 10px 0',
    fontSize: '16px',
    color: '#24292e'
  },
  mathText: {
    fontSize: '13px',
    color: '#0366d6',
    backgroundColor: '#e1ecf8',
    padding: '8px',
    borderRadius: '4px',
    marginBottom: '15px'
  },
  sliderRow: {
    marginBottom: '15px'
  },
  sliderLabel: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '14px',
    marginBottom: '5px',
    color: '#444'
  },
  slider: {
    width: '100%',
    cursor: 'pointer'
  },
  infoBox: {
    fontSize: '13px',
    color: '#856404',
    backgroundColor: '#fff3cd',
    padding: '10px',
    borderRadius: '6px',
    border: '1px solid #ffeeba'
  }
};

export default Weights;