import React, { useState, useEffect, useRef } from "react";
import TraitPopup from "./TraitPopup";
import Image from "next/image";

const SummaryBack = ({ data }) => {
  const [activeTrait, setActiveTrait] = useState(null);
  const [activeRef, setActiveRef] = useState(null);

  // ✅ Create a ref array for all trait items
  const traitRefs = useRef([]);

  const descriptions = {
    "Late-Game": `Shines in the late stages of ${data.region} battle once resources are built.`,
    "Scaling": "Grows stronger over time with continuous development.",
    "Empire-Building": "Focuses on expansion and strategic dominance.",
  };

  const Regions = {
    //"Bilgewater" : `Citizens from Bilgewater have a high affinity for gold and are prone to make risky, daring plays on their lonesome. They value efficient gold generation per minute and are more willing to take tower dives if they think it can swing the tides in their favor. Based on your stats, you make an average of ${gpm} gold per minute. You’ve also gotten roughly ${avg_solo_kills} solo kills per game as well as an average of ${avg_kills_near_tower} kills near enemy tower. These impressive stats prove that you are a bonafide Bilgerat, ready to plunder the enemy team’s economy.`,
    //"Noxus" : `Noxians are known for their bloodlust and are eager to show off their strength to any unfortunate opponents that happen to stand in their way. Not only do they live for the thrill of battle, but they also take great pleasure in asserting their dominance as quickly and brutally as possible. According to your average damage per minute, ${dpm}, as well as your exemplary average early gold advantage, ${ega}, you are a perfect fit for the Noxian archetype.`,
    //"Bandle_City" : `Everyone in Bandle City knows that the scout’s code is one of the most important rulebooks to follow for any aspiring Bandle scout. Bandle scouts are known for their vigilance and their dedication to never be detected. The average Bandle scout never backs down from a fight and always comes prepared for anything. Scouts usually have a high vision score, high KDA and can always find a way to outplay when outnumbered. Your average KDA, ${avg_kda}, and vision score, ${vs}, are exceptionally high. Your average kills when outnumbered, ${avg_outnumbered_kills}, are exceptionally high which demonstrates that you are ready to become a Bandle scout.`,
    //"Demacia" : `Long ago, many Demacian soldiers believed that as long as they stood together, firm in their beliefs, they would never capitulate to the enemy. This same belief still holds true today, as the Demacian empire still stands tall, firm in their belief that what they do is right. Demacians are known for working together to destroy their enemies while making sure to keep their allies safe. Your average kill participation, ${kp}, and your teamfight damage, ${tfdmg}, are exceptionally high, but your average shielding on allies, ${soa}, proves that you know your teammates come first.`,
    //"Ionia" : `When Noxus invaded the first lands, everything changed for the people of Ionia. Families were split apart, temples were destroyed, and peace was nowhere to be found. The scars from Noxus linger on Ionia’s once peaceful lands, and now Ionians are ready for anything. To be an Ionian, you must be sharp and quick-witted if you want to stay alive. Ionians typically have exceptional cs and kill participation while also maintaining a high KDA. They are also known to be one with the land around them, meaning that they on average achieve a stellar vision score. Your KDA, {kda}, as well as your kill participation ${kp}, cs ${cs} and vision score ${vs}, prove that you are an honorary Ionian native.`,
    //"Ixtal" : `In the jungles of Ixtal, the hunt is what is considered to be the most sacred tradition held by the natives. The hunt brings in food, pays for shelter, and can save lives. Hunting the monsters in Ixtal can provide several benefits, such as honing your skills, immense amounts of meat, and special boons. A good jungler translates very easily into being an excellent hunter. Getting a high amount of dragon and herald kills per game means that you are a valuable asset to your team’s probability of success. Your high objective damage, ${objdmg}, paired with high dragon and herald kills, ${dkills}, ${hkills}, exhibits how hard of a jungle carry you can be.`,
    //"Piltover" : `Piltover prides itself on its constant need for innovation, always improving upon each iteration to produce wondrous results. There’s always a hidden cost that’s required to continue improving, which is why every up-and-coming inventor needs a sponsor or a wealthy background. In order to keep your place as an honorary Piltovian, your gold per minute must be high enough to satisfy the needs of your research and production costs. Since your cs per minute, ${cs}, and your cs consistency, ${cs_c}, are always exceptionally high, your gold per minute, ${gpm}, goes beyond the average Piltovian salary. The city of progress can make several technological advancements thanks to your immense wealth and consistent profits.`,
    //"Shadow_Isles" : `The Blessed Isles were once a place of refuge where people could go experience tranquility and safety while having the luxury of healing their wounds by taking a dip in the sacred waters. Everything changed, however, when a magical calamity befell the isles, turning them into the Shadow Isles. The isles that were once known for harboring life and prosperity now only hold death and despair for those who enter. However, not all has been lost, for there are those that reside in the Shadow Isles that want to restore them to their former glory. To be able to become a part of the few who can survive the Shadow Isles, an exceptional mastery of healing those around you accompanied by a will to stay alive is required. Your average lifespan per game, ${life}, outlasts even the safest of players, while your healing, ${heals}, is unmatched. You definitely have what it takes to return the Shadow Isles to their former glory.`,
    "Shurima": `To most, Shurima seems like a harsh desert wasteland with nothing of value left in it after its once great empire fell. For those who are patient and are willing to look beneath the sand, Shurima harbors an indescribable amount of wealth and power. This power to become ascended can only be tapped into by a certain few who prove themselves to be worthy after a substantial amount of time. Based on your high average cs per game, {cs}, and your exceptional gold generation per minute, {gpm}, your playstyle makes you the perfect candidate to become a Shuriman ascended.`,
    //"Targon" : `Anyone who scaled Mount Targon knows that the journey is treacherous and filled with adversity, but those who reach the top have the chance to be touched by celestial beings imbuing them with unimaginable power. To climb this mountain alone, however, is a death sentence; this climb encourages people to seek out unlikely allies to forge strong bonds that can soldier through the mountain's harsh conditions. Teamwork alone isn’t the only thing that’s needed; a summoner’s individual support skills like warding, healing, and shielding are necessary for the uncertain path ahead. Your average vision score per game, ${v_score}, demonstrates a perceptive and cautious player. Your average healing and shielding, ${heals}, ${shields}, on teammates is massive. This all but seals the deal that you are more than capable of making it to the top of Mount Targon.`,
    //"Freljord" : `The Freljord is a combination of harsh mountain ranges and cold, bitter wind that can rattle the bones of even the toughest of Runeterrans. Iceborn, the special few that are native to this land, have adapted to these tough conditions and have managed to thrive in this icy area. Iceborn have retained skills such as having insanely long crowd control chains while being an unscalable wall to anyone who dares challenge them. Your stats show that you apply an exceptionally long amount of crowd control, ${cc}, to your enemies. You also have an exceptional will to survive which is shown through how long you’ve survived, ${time_alive}, during each game. You are a true Iceborn.`,
    //"Void" : `The Void. A pit that houses a variety of unspeakable horrors from beyond Runeterra that are hungry to consume anything that lives. Almost nothing survives once they enter the Void, the only exception being the Voidborne. All of the Voidborne deal insane amounts of damage, obliterating anything weaker than them in their path, which allows them to survive the harsh conditions of the Void. A high average damage per minute accompanied with a high amount of solo kills and teamfight damage. Your high average damage per minute, ${dpm}, identifies you as a fearsome enemy that can tear through the enemy frontline. Your teamfight damage, ${tfd}, and your solo kills, ${sk}, per game prove that you are an unstoppable force alone and with your team.`,
    //"Zaun" : `The underbelly of Piltover, Zaun, is a place where dreams of progress go to die and a quiet desperation to survive replaces it. The streets of Zaun make it difficult to traverse if you aren’t already a resilient cutthroat. There’s plenty of opportunities to be kidnapped, mugged or straight up killed in cold blood. The good people of Zaun have adapted to this lifestyle, putting their life on the line in order to eliminate as many of their enemies as possible. Zaunites typically have a high number of deaths but manage to take down at least one or more enemy players with them. Your average deaths, ${death_con}, are quite high, however, you manage to take down around ${avg_outnumbered_kills} champions before you fall. The average amount of assassinations you perform on enemy champions are roughly ${avg_pick_kills} which means your map awareness is exemplary.`
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
        <p>{Regions[data.region]}</p>
      </div>

      {/* Profile traits with popups */}
      <div className="info-box">
        <h3>Profile</h3>
        <ul className="profile-list">
          {data.profile.map((trait, index) => {
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
