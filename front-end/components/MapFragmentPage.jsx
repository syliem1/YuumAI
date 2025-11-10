import React from "react";

const MapFragmentPage = ({ 
  region = "Runeterra",
  variant = "default",
  showCompass = true,
  markerCount = 3,
  fragmentCount = 3,
  theme = "warm"
}) => {
  // Different color themes
  const themes = {
    warm: {
      primary: "rgba(139, 115, 85, 0.6)",
      secondary: "rgba(185, 151, 88, 0.5)",
      accent: "rgba(120, 188, 176, 0.4)",
      fill: "rgba(139, 115, 85, 0.15)",
    },
    cool: {
      primary: "rgba(83, 140, 176, 0.6)",
      secondary: "rgba(120, 188, 176, 0.5)",
      accent: "rgba(78, 188, 120, 0.4)",
      fill: "rgba(83, 140, 176, 0.15)",
    },
    dark: {
      primary: "rgba(86, 55, 78, 0.6)",
      secondary: "rgba(119, 66, 95, 0.5)",
      accent: "rgba(86, 55, 78, 0.4)",
      fill: "rgba(86, 55, 78, 0.15)",
    },
    mystical: {
      primary: "rgba(139, 92, 176, 0.6)",
      secondary: "rgba(185, 88, 151, 0.5)",
      accent: "rgba(197, 107, 197, 0.4)",
      fill: "rgba(139, 92, 176, 0.15)",
    },
  };

  const colors = themes[theme] || themes.warm;

  const markers = React.useMemo(() => {
    const markers = [];
    for (let i = 0; i < markerCount; i++) {
      markers.push({
        top: `${20 + Math.random() * 60}%`,
        left: `${20 + Math.random() * 60}%`,
      });
    }
    return markers;
  }, [markerCount]);

  // Different map patterns based on variant
  const mapPatterns = {
    default: [
      { path: "M 20 50 Q 40 30, 80 40 T 150 60 L 180 100 Q 160 120, 120 110 T 50 90 Z", type: "path" },
      { path: "M 30 80 L 60 50 L 100 60 L 130 40 L 160 70 L 140 120 L 90 110 L 50 130 Z", type: "region" },
      { cx: 100, cy: 100, rx: 60, ry: 40, type: "water" },
    ],
    mountains: [
      { path: "M 20 120 L 40 80 L 60 100 L 80 60 L 100 90 L 120 50 L 140 80 L 160 100 L 180 120", type: "path" },
      { path: "M 50 140 L 70 110 L 90 125 L 110 95 L 130 120 L 150 140", type: "path" },
      { path: "M 80 110 L 100 80 L 120 110", type: "region" },
    ],
    rivers: [
      { path: "M 30 20 Q 50 60, 70 100 T 110 160", type: "water" },
      { path: "M 150 30 Q 130 70, 110 110 T 70 170", type: "water" },
      { path: "M 90 80 Q 100 100, 110 120", type: "water" },
    ],
    forest: [
      { path: "M 40 60 L 50 40 L 60 60 Z", type: "region" },
      { path: "M 100 80 L 110 60 L 120 80 Z", type: "region" },
      { path: "M 140 100 L 150 80 L 160 100 Z", type: "region" },
      { path: "M 70 120 L 80 100 L 90 120 Z", type: "region" },
    ],
  };

  const patterns = mapPatterns[variant] || mapPatterns.default;

  return (
    <div className="relative w-full h-full overflow-hidden">
      <style jsx>{`
        .map-container {
          width: 100%;
          height: 100%;
          position: relative;
          background: linear-gradient(135deg, 
            rgba(139, 112, 78, 0.1) 0%, 
            rgba(185, 151, 88, 0.05) 100%);
        }

        .map-fragment {
          position: absolute;
          opacity: 0.6;
        }

        .map-fragment:nth-child(1) {
          top: 5%;
          left: 10%;
          width: 35%;
        }

        .map-fragment:nth-child(2) {
          top: 15%;
          right: 5%;
          width: 40%;
        }

        .map-fragment:nth-child(3) {
          bottom: 10%;
          left: 15%;
          width: 45%;
        }

        .map-svg {
          filter: sepia(60%) brightness(0.8) contrast(1.2);
          opacity: 0.7;
        }

        .location-marker {
          position: absolute;
          width: 12px;
          height: 12px;
          background: radial-gradient(circle, ${colors.secondary} 0%, transparent 70%);
          border: 2px solid ${colors.primary};
          border-radius: 50%;
          opacity: 0.8;
        }

        .torn-edge {
          position: absolute;
          width: 100%;
          height: 20px;
          background: repeating-linear-gradient(
            90deg,
            transparent,
            transparent 5px,
            rgba(139, 112, 78, 0.2) 5px,
            rgba(139, 112, 78, 0.2) 10px
          );
        }

        .torn-edge.top {
          top: 0;
          transform: rotate(180deg);
        }

        .torn-edge.bottom {
          bottom: 0;
        }

        .compass-rose {
          position: absolute;
          bottom: 15%;
          right: 10%;
          width: 80px;
          height: 80px;
          opacity: 0.4;
        }

        .map-legend {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          text-align: center;
          font-family: Georgia, serif;
          font-style: italic;
          color: rgba(86, 55, 78, 0.5);
          font-size: 1.2rem;
          letter-spacing: 3px;
          text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
        }

        .decorative-corner {
          position: absolute;
          width: 60px;
          height: 60px;
          border: 2px solid rgba(139, 115, 85, 0.3);
        }

        .corner-tl {
          top: 5%;
          left: 5%;
          border-right: none;
          border-bottom: none;
        }

        .corner-br {
          bottom: 5%;
          right: 5%;
          border-left: none;
          border-top: none;
        }
      `}</style>

      <div className="map-container">
        {/* Torn edges effect */}
        <div className="torn-edge top" />
        <div className="torn-edge bottom" />

        {/* Decorative corners */}
        <div className="decorative-corner corner-tl" />
        <div className="decorative-corner corner-br" />

        {/* Map fragments */}
        {Array.from({ length: Math.min(fragmentCount, 3) }).map((_, idx) => {
          const pattern = patterns[idx] || patterns[0];
          
          return (
            <div key={idx} className="map-fragment">
              <svg className="map-svg" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                {pattern.type === "water" && pattern.cx ? (
                  <ellipse 
                    cx={pattern.cx} 
                    cy={pattern.cy} 
                    rx={pattern.rx} 
                    ry={pattern.ry}
                    fill={colors.fill}
                    stroke={colors.accent}
                    strokeWidth="2"
                  />
                ) : pattern.type === "water" ? (
                  <path
                    d={pattern.path}
                    fill="none"
                    stroke={colors.accent}
                    strokeWidth="3"
                    strokeLinecap="round"
                  />
                ) : pattern.type === "region" ? (
                  <path
                    d={pattern.path}
                    fill={colors.fill}
                    stroke={colors.primary}
                    strokeWidth="1.5"
                  />
                ) : (
                  <path
                    d={pattern.path}
                    fill="none"
                    stroke={colors.primary}
                    strokeWidth="2"
                    strokeDasharray="5,5"
                  />
                )}
              </svg>
            </div>
          );
        })}

        {/* Location markers */}
        {markers.map((marker, idx) => (
          <div 
            key={idx}
            className="location-marker" 
            style={{ 
              top: marker.top, 
              left: marker.left,
            }} 
          />
        ))}

        {/* Compass rose */}
        {showCompass && (
          <svg className="compass-rose" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="45" fill="none" stroke={colors.primary} strokeWidth="1" />
            <circle cx="50" cy="50" r="35" fill="none" stroke={colors.primary} strokeWidth="1" opacity="0.6" />
            <polygon points="50,10 55,45 50,50 45,45" fill={colors.secondary} />
            <polygon points="50,90 55,55 50,50 45,55" fill={colors.primary} />
            <polygon points="10,50 45,55 50,50 45,45" fill={colors.primary} />
            <polygon points="90,50 55,55 50,50 55,45" fill={colors.primary} />
            <text x="50" y="20" textAnchor="middle" fill="rgba(86, 55, 78, 0.6)" fontSize="12" fontFamily="serif">N</text>
          </svg>
        )}

        {/* Central legend text */}
        <div className="map-legend">
          {region.toUpperCase()}
        </div>
      </div>
    </div>
  );
};

export default MapFragmentPage;