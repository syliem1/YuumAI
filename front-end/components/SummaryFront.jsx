import React, { useState, useEffect, useRef } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import TraitPopup from "./TraitPopup";

const SummaryFront = ({ data }) => {
  const [activeTrait, setActiveTrait] = useState(null);
  const [activeRef, setActiveRef] = useState(null);

  // ✅ Create ref arrays outside the render loop
  const strengthRefs = useRef([]);
  const weaknessRefs = useRef([]);

  const roleData = Object.entries(data.roles || {}).map(([role, count]) => ({
    role: role.toUpperCase(),
    games: count,
  }));

  const roleColors = {
    TOP: "#f9c74f",
    JG: "#90be6d",
    MID: "#577590",
    ADC: "#f94144",
    SUP: "#f3722c",
  };

  useEffect(() => {
    const handleClickOutside = () => setActiveTrait(null);
    window.addEventListener("click", handleClickOutside);
    return () => window.removeEventListener("click", handleClickOutside);
  }, []);

  const handleTraitClick = (trait, ref, e) => {
    e.stopPropagation();
    if (activeTrait === trait) {
      setActiveTrait(null);
      setActiveRef(null);
    } else {
      setActiveTrait(trait);
      setActiveRef(ref);
    }
  };

  return (
    <div className="page-content summary-front">
      <h2 className="section-title">Gameplay Overview</h2>

      {/* Role Distribution Chart */}
      <div className="chart-container" style={{ width: "100%", height: 250 }}>
        <h3 className="header-text">Role Distribution</h3>
        <ResponsiveContainer>
          <BarChart
            data={roleData}
            margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="role" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="games" radius={[6, 6, 0, 0]}>
              {roleData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={roleColors[entry.role] || "#8884d8"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Strengths & Weaknesses Section */}
      <div className="info-box" style={{ marginTop: "1rem" }}>
        <h3>Strengths & Weaknesses</h3>

        <div className="trait-section">
          {/* Strengths */}
          <div className="trait-group">
            <h4 style={{ color: "#22c55e" }}>Strengths</h4>
            <ul className="trait-list">
              {data.strengths?.slice(0, 4).map((trait, index) => {
                // ✅ Initialize a unique ref for each item (once)
                if (!strengthRefs.current[index]) {
                  strengthRefs.current[index] = React.createRef();
                }

                const ref = strengthRefs.current[index];
                return (
                  <li
                    key={index}
                    ref={ref}
                    className="trait-item strength"
                    onClick={(e) => handleTraitClick(trait, ref, e)}
                    style={{ color: "#16a34a" }}
                  >
                    {trait}
                    {activeTrait === trait && activeRef === ref && (
                      <TraitPopup targetRef={ref}>
                        <p>
                          {data.details?.[trait] ||
                            "No specific data available."}
                        </p>
                      </TraitPopup>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Weaknesses */}
          <div className="trait-group">
            <h4 style={{ color: "#ef4444" }}>Weaknesses</h4>
            <ul className="trait-list">
              {data.weaknesses?.slice(0, 4).map((trait, index) => {
                // ✅ Initialize a unique ref for each weakness item
                if (!weaknessRefs.current[index]) {
                  weaknessRefs.current[index] = React.createRef();
                }

                const ref = weaknessRefs.current[index];
                return (
                  <li
                    key={index}
                    ref={ref}
                    className="trait-item weakness"
                    onClick={(e) => handleTraitClick(trait, ref, e)}
                    style={{ color: "#dc2626" }}
                  >
                    {trait}
                    {activeTrait === trait && activeRef === ref && (
                      <TraitPopup targetRef={ref}>
                        <p>
                          {data.details?.[trait] ||
                            "No specific data available."}
                        </p>
                      </TraitPopup>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SummaryFront;
