import React, { useState, useEffect, useRef } from "react";
import TraitPopup from "./TraitPopup";
import Image from "next/image";

const SummaryBack = ({ data }) => {
  const [activeTrait, setActiveTrait] = useState(null);
  const [activeRef, setActiveRef] = useState(null);

  // ✅ Create a ref array for all trait items
  const traitRefs = useRef([]);

  const descriptions = {
    "Late-Game": "Shines in the late stages of battle once resources are built.",
    "Scaling": "Grows stronger over time with continuous development.",
    "Empire-Building": "Focuses on expansion and strategic dominance.",
  };

  useEffect(() => {
    const handleClickOutside = () => {
      setActiveTrait(null);
      setActiveRef(null);
    };
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
    <div className="page-content">
      <h2 className="section-title">Username</h2>

      {/* Region info */}
      <div className="info-box">
        <h3 className="region-title">
          Region: {data.region}
          <Image
            src={`/images/regions/${data.region
              .toLowerCase()
              .replace(/\s+/g, "_")}_crest_icon.png`}
            alt={`${data.region} crest`}
            className="region-icon"
            width={32}
            height={32}
          />
        </h3>
        <p>Shurima is a region known for its incredible power built over dynasties.</p>
      </div>

      {/* Profile traits with popups */}
      <div className="info-box">
        <h3>Profile</h3>
        <ul className="profile-list">
          {data.profile.map((trait, index) => {
            // ✅ assign a ref for each trait
            if (!traitRefs.current[index]) {
              traitRefs.current[index] = React.createRef();
            }

            const ref = traitRefs.current[index];
            return (
              <li
                key={index}
                ref={ref}
                className="trait-item"
                onClick={(e) => handleTraitClick(trait, ref, e)}
              >
                {trait}
                {activeTrait === trait && activeRef === ref && (
                  <TraitPopup targetRef={ref}>
                    <p>{descriptions[trait] || "No description available."}</p>
                  </TraitPopup>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      {/* Key Statistics + Most Played Champions */}
      <div className="info-box">
        <h3>Key Statistics</h3>
        <ul className="statistics-list">
          <li>Games Played: {data.statistics.gamesPlayed}</li>
          <li>Win Rate: {data.statistics.winRate}</li>
          <li>Average KDA: {data.statistics.averageKDA}</li>
          <li>CS/M: {data.statistics.cspm}</li>
        </ul>

        {/* Most Played Champions */}
        {data.mostPlayed && data.mostPlayed.length > 0 && (
          <div className="most-played-section">
            <h4 style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>
              Most Played Champions
            </h4>
            <div className="champion-row">
              {data.mostPlayed.slice(0, 3).map((champ, index) => (
                <div key={index} className="champion-item">
                  <Image
                    src={`/images/champions/${champ.name
                      .toLowerCase()
                      .replace(/\s+/g, "_")}.avif`}
                    alt={champ.name}
                    className="champion-icon"
                    width={64}
                    height={64}
                  />
                  <p className="champion-name">{champ.name}</p>
                  <p className="champion-games">{champ.games} games</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SummaryBack;
