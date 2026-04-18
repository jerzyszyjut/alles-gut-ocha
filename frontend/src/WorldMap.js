import React, { useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { Tooltip } from "react-tooltip";

const geoUrl = "https://raw.githubusercontent.com/subyfly/topojson/master/world-countries.json";

const MapChart = ({ setHoveredCountry, availableCountries }) => {
  const [content, setContent] = useState("");

  return (
    <div style={{ 
      flex: 1,
      width: "100%", 
      overflow: "hidden", 
      display: "flex", 
      alignItems: "center", 
      justifyContent: "center",
      background: "#f0f2f5",
      borderRadius: "12px",
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
            geographies.map((geo) => {
              // 1. Logic must happen inside curly braces
              const iso3 = geo.id || geo.properties.ISO_A3 || geo.properties.iso_a3;
              const hasData = availableCountries?.has(iso3);

              // 2. You must explicitly 'return' the JSX
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  onMouseEnter={() => {
                    setContent(geo.properties.name);
                    setHoveredCountry(iso3);
                  }}
                  onMouseLeave={() => {
                    setContent("");
                    setHoveredCountry("");
                  }}
                  style={{
                    default: { 
                      // 3. Apply the highlight color based on hasData
                      fill: hasData ? "#94a3b8" : "#D6D6DA", 
                      outline: "none",
                      stroke: "#fff",
                      strokeWidth: 0.5
                    },
                    hover: { 
                      fill: "#3b82f6", 
                      outline: "none", 
                      cursor: hasData ? "pointer" : "default" 
                    },
                    pressed: { fill: "#2563eb", outline: "none" },
                  }}
                />
              );
            })
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
          zIndex: 100 
        }} 
      />
    </div>
  );
};

export default MapChart;