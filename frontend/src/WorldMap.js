import React, { useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { Tooltip } from "react-tooltip";

const geoUrl = "https://raw.githubusercontent.com/subyfly/topojson/master/world-countries.json";

const WorldMap = ({ setHoveredCountry, availableCountries, activeFilter }) => {
  const [tooltipContent, setTooltipContent] = useState("");

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
      position: "relative"
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
              const iso3 = geo.id || geo.properties.ISO_A3;
              
              // 1. Identify states
              const isSelected = activeFilter === iso3;
              const hasData = availableCountries?.has(iso3);

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  onMouseEnter={() => setTooltipContent(geo.properties.name)}
                  onMouseLeave={() => setTooltipContent("")}
                  onClick={() => {
                    // Toggle: click same country again to clear selection
                    const newFilter = isSelected ? "" : iso3;
                    setHoveredCountry(newFilter);
                  }}
                  style={{
                    default: { 
                      // 2. Priority Fill Logic
                      fill: isSelected 
                        ? "#1d4ed8" // Deep blue for CLICKED
                        : hasData 
                          ? "#94a3b8" // Medium gray for AVAILABLE (remains visible)
                          : "#D6D6DA", // Light gray for NO DATA
                      outline: "none",
                      stroke: isSelected ? "#fff" : "#fff",
                      strokeWidth: isSelected ? 1.5 : 0.5,
                      transition: "all 200ms"
                    },
                    hover: { 
                      // 3. Hover Feedback
                      fill: isSelected ? "#1e40af" : (hasData ? "#60a5fa" : "#adb5bd"), 
                      outline: "none", 
                      cursor: "pointer" 
                    },
                    pressed: { 
                      fill: "#1e3a8a", 
                      outline: "none" 
                    },
                  }}
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>
      
      <Tooltip 
        anchorSelect=".rsm-geography" 
        content={tooltipContent}
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

export default WorldMap;