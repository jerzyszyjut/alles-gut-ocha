import React, { useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { Tooltip } from "react-tooltip";

//const geoUrl = "https://unpkg.com/world-atlas@2.0.2/countries-110m.json";
const geoUrl = "https://raw.githubusercontent.com/subyfly/topojson/master/world-countries.json";

const MapChart = ({ setHoveredCountry }) => {
  const [content, setContent] = useState("");

  return (
    <div style={{ 
      flex: 1,           // Changed from fixed height to flex: 1 to fill App.js container
      width: "100%", 
      overflow: "hidden", 
      display: "flex", 
      alignItems: "center", 
      justifyContent: "center",
      background: "#f0f2f5",
      borderRadius: "12px", // Matches your App.js theme
    }}>
      <ComposableMap 
        width={800} 
        height={400} 
        projectionConfig={{ 
          scale: 145,
          center: [0, 5] 
        }}
        style={{
          width: "100%",
          height: "100%", 
        }}
      >
        <Geographies geography={geoUrl}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                onMouseEnter={() => {
                  // geo.id is usually the 3-letter code in many datasets
                  // If your dataset has it inside properties, use geo.properties.ISO_A3
                  const iso3 = geo.id || geo.properties.ISO_A3 || geo.properties.iso_a3;
                  
                  setContent(geo.properties.name); // Keeps tooltip as "Afghanistan"
                  setHoveredCountry(iso3);        // Sends "AFG" to the CSV filter
                }}
                onMouseLeave={() => {
                  setContent("");                   // Hides Tooltip
                  setHoveredCountry("");            // Clears Input (Optional)
                }}
                style={{
                  default: { fill: "#D6D6DA", outline: "none" },
                  hover: { fill: "#3b82f6", outline: "none", cursor: "pointer" },
                  pressed: { fill: "#2563eb", outline: "none" },
                }}
              />
            ))
          }
        </Geographies>
      </ComposableMap>
      
      <Tooltip 
        anchorSelect=".rsm-geography" 
        content={content}
        style={{ 
          backgroundColor: "#1e293b", 
          color: "#fff", 
          borderRadius: "8px",
          zIndex: 100 // Ensure it floats above other components
        }} 
      />
    </div>
  );
};

export default MapChart;