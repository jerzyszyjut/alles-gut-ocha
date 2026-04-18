import React, { useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { Tooltip } from "react-tooltip";

const geoUrl = "https://unpkg.com/world-atlas@2.0.2/countries-110m.json";

const MapChart = () => {
  const [content, setContent] = useState("");

  return (
    /* 1. Parent container controls the actual size */
    <div style={{ 
      width: "100%", 
      height: "400px", // Set your desired fixed height here
      overflow: "hidden", 
      display: "flex", 
      alignItems: "center", 
      justifyContent: "center",
      background: "#f0f2f5" 
    }}>
      <ComposableMap 
        // 2. Adjust these to crop the "view box"
        width={800} 
        height={400} 
        projectionConfig={{ 
          scale: 145,
          center: [0, 5] // 3. Moves the map slightly up to remove Antarctica whitespace
        }}
        style={{
          width: "100%",
          height: "100%", // 4. Forces it to fill the parent
        }}
      >
        <Geographies geography={geoUrl}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                onMouseEnter={() => setContent(geo.properties.name)}
                onMouseLeave={() => setContent("")}
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
        style={{ backgroundColor: "#1e293b", color: "#fff", borderRadius: "8px" }} 
      />
    </div>
  );
};

export default MapChart;