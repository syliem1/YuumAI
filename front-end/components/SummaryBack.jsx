import React, { useState, useEffect, useRef } from "react";
import TraitPopup from "./TraitPopup";
import Image from "next/image";
import { regions } from "@/data/regions";

const SummaryBack = ({ data }) => {
  const [activeTrait, setActiveTrait] = useState(null);
  const [activeRef, setActiveRef] = useState(null);

  // ✅ Create a ref array for all trait items
  const traitRefs = useRef([]);

  // Safely get region data with fallback
  const regionKey = data?.region?.toLowerCase() || 'shurima';
  const regionData = regions[regionKey] || regions['shurima'];
  
  // Create safe stats object with default values
  const safeStats = {
    avg_gpm: data?.playerStats?.avg_gpm ?? 0,
    avg_solo_kills: data?.playerStats?.avg_solo_kills ?? 0,
    avg_kills_near_tower: data?.playerStats?.avg_kills_near_tower ?? 0,
    avg_dpm: data?.playerStats?.avg_dpm ?? 0,
    avg_early_gold_adv: data?.playerStats?.avg_early_gold_adv ?? 0,
    avg_kda: data?.playerStats?.avg_kda ?? 0,
    avg_vision_score: data?.playerStats?.avg_vision_score ?? 0,
    avg_outnumbered_kills: data?.playerStats?.avg_outnumbered_kills ?? 0,
    avg_kill_participation: data?.playerStats?.avg_kill_participation ?? 0,
    avg_team_damage_pct: data?.playerStats?.avg_team_damage_pct ?? 0,
    avg_shields_on_teammates: data?.playerStats?.avg_shields_on_teammates ?? 0,
    avg_cs_per_min: data?.playerStats?.avg_cs_per_min ?? 0,
    avg_objective_damage: data?.playerStats?.avg_objective_damage ?? 0,
    avg_dragon_takedowns: data?.playerStats?.avg_dragon_takedowns ?? 0,
    avg_herald_takedowns: data?.playerStats?.avg_herald_takedowns ?? 0,
    cs_consistency: data?.playerStats?.cs_consistency ?? 0,
    avg_longest_alive: data?.playerStats?.avg_longest_alive ?? 0,
    avg_heals_on_teammates: data?.playerStats?.avg_heals_on_teammates ?? 0,
    avg_cc_time: data?.playerStats?.avg_cc_time ?? 0,
    death_consistency: data?.playerStats?.death_consistency ?? 0,
    avg_pick_kills: data?.playerStats?.avg_pick_kills ?? 0,
  };

  const descriptions = {
    "Late-Game": `Shines in the late stages of ${data.region} battle once resources are built.`,
    "Scaling": "Grows stronger over time with continuous development.",
    "Empire-Building": "Focuses on expansion and strategic dominance.",
    "Patient": "Ready to capitalize on enemy mistakes.",
    "Unpredictable": "No one knows this players next move will be, not even they know.",
    "Whimsical": "Tilt free and good mental.",
    "Mobile": "This summoner moves around the map quickly.",
    "Creative": "Utilizes unique methods to put themselves ahead.",
    "Relentless": "No one can hold this player back.",
    "Undying": "Death is a foreign concept to this summoner.",
    "Aggressive": "Takes control of the game by force.",
    "Altruistic": "Looks out for teammates in need of support.",
    "Opportunistic": "Constantly looking for plays to change the tide of the game.",
    "Risky" : "Willing to lose it all for a massive payout.",
    "Gold-Focused" : "Gold is the number one prospect in this player's agenda.",
    "Jungle-Focused": "Focuses on gettting a lead through massive jungle monsters.",
    "Elemental": "Grabs elemental buffs when needed.",
    "Objective-Control": "Sets up pressure to secure powerful objectives.",
    "Hidden": "Successful ganker",
    "Balanced": "Can attack ruthlessly with little to no holes in their defense.",
    "Harmonious": "In the flow state, they cannot be shaken.",
    "Skillful": "Takes fights to outplay the enemy.",
    "Adaptable": "Ready to overcome any situation, no matter how tough.",
    "Honorable": "Willing to fight fairly in order to prove a point.",
    "Protective": "Capable of protecting the less fortunate.",
    "Teamfight": "Coordinates with their team to setup favorable fights.",
    "Consistent": "Looks out for any possible positive outcomes that could bring about victory.",
    "Dominant": "Bullies the opposing laner into submission.",
    "Conquest": "Topples towers and inhibitors in order to crush enemy morale.",
    "Powerful": "Enemies crumble to the mere presence of this summoner.",
    "Efficient": "Makes the most out of every resource they have.",
    "Innovative": "When one idea fails, they have ten more waiting to be unleashed.",
    "Calculated": "Meticulous decision making goes into to each and every step of their plans.",
    "Wealthy": "Money is of no object.",
    "Draining": "Fuels their own life through the pain  of their enemies.",
    "Persistent": "Unyielding pressure that has no end.",
    "Sustain": "Has an infinite amount of self-healing making it impossible for them to die.",
    "Deaths-Dance": "Takes damage to recover that damage back.",
    "Supportive": "Live and die for your allies.",
    "Vision": "Able to see everywhere and anywhere across the map.",
    "Celestial": "Benevolent aura.",
    "Tanky": "You are an insurmountable wall that protects your team from enemy attacks.",
    "Survival": "Able to survive the harsh cold as well as brutal attacks.",
    "CC-Heavy": "Enemies find themselves unable to move in your presence.",
    "Enduring": "No matter how many blows you take, no matter how much you want to capitulate, you endure.",
    "Consuming": "Devours the enemy team's hope for victory.",
    "Chaotic": "Ready to take any fights, whenever and wherever on the map.",
    "Damage-Focused": "Eager to dish out tons of damage without a care in the world.",
    "Experimental": "Eager to try new builds to see what syngeries can be brought about.",
    "Damage-Over-Time": "Willing to push themselves to the limit to achieve their goals.",
    "High-Risk": "High risk? High reward."
    };

  

  useEffect(() => {
    const handleClickOutside = () => {
      setActiveTrait(null);
      setActiveRef(null);
    };
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

  return (
    <div className="page-content">
      <h2 className="section-title">{data?.username || 'Unknown Player'}</h2>

      {/* Region info */}
      <div className="info-box">
        <h3 className="region-title">
          Region: {data?.region || 'Unknown'}
          <Image
            src={`/images/regions/${(data?.region || 'shurima')
              .toLowerCase()
              .replace(/\s+/g, "_")}_crest_icon.png`}
            alt={`${data?.region || 'Unknown'} crest`}
            className="region-icon"
            width={32}
            height={32}
          />
        </h3>
        <p>{regionData?.description ? regionData.description(safeStats) : 'Loading region description...'}</p>
      </div>

      {/* Profile traits with popups */}
      <div className="info-box">
        <h3>Profile</h3>
        <ul className="profile-list">
          {(data?.profile || []).map((trait, index) => {
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
          <li>Win Rate: {data?.statistics?.winRate ?? '0.00'}</li>
          <li>Average KDA: {data?.statistics?.averageKDA ?? '0.00'}</li>
          <li>CS/M: {data?.statistics?.cspm ?? '0.00'}</li>
          <li>Gold/M: {data?.statistics?.goldpm ?? '0.00'}</li>
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
