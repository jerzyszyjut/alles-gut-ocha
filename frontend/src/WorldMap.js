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
              const hasData = availableCountries?.has(iso3);
              const isSelected = activeFilter === iso3;

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  // HOVER: Only updates local tooltip, doesn't touch the input box
                  onMouseEnter={() => {
                    setTooltipContent(geo.properties.name);
                  }}
                  onMouseLeave={() => {
                    setTooltipContent("");
                  }}
                  // CLICK: This is now the ONLY thing that updates the input box
                  onClick={() => {
                    // Toggle logic: if clicking the already selected country, clear it.
                    const newFilter = isSelected ? "" : iso3;
                    setHoveredCountry(newFilter);
                  }}
                  style={{
                    default: { 
                      // Colors: Selected (Blue) > Has Data (Gray) > No Data (Light Gray)
                      fill: isSelected ? "#3b82f6" : (hasData ? "#94a3b8" : "#D6D6DA"), 
                      outline: "none",
                      stroke: isSelected ? "#1e40af" : "#fff",
                      strokeWidth: isSelected ? 1.5 : 0.5,
                      transition: "fill 0.2s"
                    },
                    hover: { 
                      fill: "#60a5fa", // Lighter blue on hover
                      outline: "none", 
                      cursor: "pointer" 
                    },
                    pressed: { 
                      fill: "#2563eb", 
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