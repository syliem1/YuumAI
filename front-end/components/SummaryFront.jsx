import React, { useState, useEffect, useRef } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from "recharts";
import TraitPopup from "./TraitPopup";

const SummaryFront = ({ data }) => {
  const [activeTrait, setActiveTrait] = useState(null);
  const [activeRef, setActiveRef] = useState(null);

  const strengthRefs = useRef([]);
  const weaknessRefs = useRef([]);
  const overallPercentile = data.overall.percentile; 
  const percentileLabel = data.overall.interpretation;

  const pieData = [
    { name: "Percentile", value: overallPercentile },
    { name: "Remaining", value: 100 - overallPercentile },
  ];

  const pieColors = ["#8b6f4e", "#e5e5e5"];


  useEffect(() => {
    const handleClickOutside = () => setActiveTrait(null);
    window.addEventListener("mousedown", handleClickOutside);
    return () => window.removeEventListener("mousedown", handleClickOutside);
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

  const statDisplayNames = {
    "avg_dpm": "Damage per minute",
    "avg_gpm": "Gold per minute",
    "avg_kill_participation": "Kill participation",
    "avg_kda": "KDA",
    "avg_vision_score": "Vision Score",
    "avg_cs_per_min": "CS per minute",
    "avg_team_damage_pct": "Team Damage Participation",
    "avg_outnumbered_kills": "Outnumbered Kills",
    "avg_solo_kills": "Solo Kills",
    "avg_kills_near_tower": "Kills near tower",
    "avg_shields_on_teammates": "Shielding Teammates",
    "avg_objective_damage": "Objective Damage",
    "avg_dragon_takedowns": "Dragon Takedowns",
    "avg_herald_takedowns": "Rift Herald Takedowns",
    "avg_early_gold_adv": "Early Gold Advantage",
    "avg_heals_on_teammates": "Healing Teammates",
    "avg_longest_alive": "Time Alive",
    "avg_cc_time": "Crowd Control Time",
    "avg_time_dead": "Time Dead",
    "avg_pick_kills": "Pick Kills",
    "avg_deaths": "Deaths",
    "death_consistency": "Death rate",
    "cs_consistency": "CS rate",
    "win_rate": "Win Rate"
  }

  return (
    <div className="page-content summary-front">
      <h2 className="section-title">Gameplay Overview</h2>
      {/* 🌟 Overall Percentile Section */}
      <div className="info-box" style={{ marginBottom: "1.5rem", height: 270}}>
        <h3>Overall Performance Percentile</h3>
        <div className="flex flex-col items-center justify-center">
          <div style={{ width: "200px", height: "200px" }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={pieData}
                  innerRadius={70}
                  outerRadius={90}
                  dataKey="value"
                  startAngle={90}
                  endAngle={-270}
                  stroke="none"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={pieColors[index]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="text-center mt-[-120px]">
            <h2 className="text-4xl font-bold text-[#8b6f4e]">
              {overallPercentile}%
            </h2>
            <p className="text-lg text-gray-700">{percentileLabel}</p>
          </div>
        </div>
      </div>

      {/* Strengths & Weaknesses Section */}
      <div className="info-box" style={{ marginTop: "1rem" }}>
        <h3>Strengths & Weaknesses</h3>

        <div className="trait-section">
          {/* Strengths */}
          <div className="trait-group">
            <h4 style={{ color: "#22c55e" }}>Strengths</h4>
            <ul className="trait-list">
              {data.strengths?.slice(0, 5).map((trait, index) => {
                // ✅ Initialize a unique ref for each item (once)
                if (!strengthRefs.current[index]) {
                  strengthRefs.current[index] = React.createRef();
                }

                const ref = strengthRefs.current[index];
                return (
                  <li
                    key={index}
                    ref={ref}
                    className="trait-item strength my-1"
                    onClick={(e) => handleTraitClick(trait, ref, e)}
                    style={{ color: "#16a34a" }}
                  >
                    {statDisplayNames[trait.stat]}
                    {activeTrait === trait && activeRef === ref && (
                      <TraitPopup targetRef={ref}>
                        <p>
                          {`Percentile: ${trait.percentile}` ||
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
              {data.weaknesses?.slice(0, 5).map((trait, index) => {
                // ✅ Initialize a unique ref for each weakness item
                if (!weaknessRefs.current[index]) {
                  weaknessRefs.current[index] = React.createRef();
                }

                const ref = weaknessRefs.current[index];
                return (
                  <li
                    key={index}
                    ref={ref}
                    className="trait-item weakness my-1"
                    onClick={(e) => handleTraitClick(trait, ref, e)}
                    style={{ color: "#dc2626" }}
                  >
                    {statDisplayNames[trait.stat]}
                    {activeTrait === trait && activeRef === ref && (
                      <TraitPopup targetRef={ref}>
                        <p>
                          {`Percentile: ${trait.percentile}` ||
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
