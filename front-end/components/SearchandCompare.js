import React, { useState } from "react";
import { useFriendContext } from "@/context/FriendContext";

const SearchAndCompare = ({ player1Stats, onPlayer2Found }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [player2Stats, setPlayer2Stats] = useState({
    "avg_kda": 0,
    "avg_cs_per_min": 0,
    "avg_kill_participation": 0,
    "avg_dpm": 0,
    "avg_gpm": 0,
    "avg_solo_kills": 0,
    "avg_vision_score": 0,
    "avg_cc_time": 0});
  const [hasSearched, setHasSearched] = useState(false); // Track if user has searched
  const { setFriendResult } = useFriendContext();
  const stats = ["avg_kda", "avg_cs_per_min", "avg_kill_participation", "avg_dpm", "avg_gpm", "avg_solo_kills", "avg_vision_score", "avg_cc_time"];
  const displayStats = {
    "avg_kda": "KDA",
    "avg_cs_per_min": "CS per min",
    "avg_kill_participation": "kill participation",
    "avg_dpm": "damage per minute",
    "avg_gpm": "gold per minute",
    "avg_solo_kills": "solo kills",
    "avg_vision_score": "vision score",
    "avg_cc_time": "crowd control time"
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    // TODO: Replace with actual API call
    const endpoint = "https://v4ft9564pb.execute-api.us-west-2.amazonaws.com/player/process";

    const body = {
      game_name: "ShadowLeaf",
      tagline: "8005",
      num_games: 1
    };

    try {
      console.log("Fetching...");

      const res= await 
        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })

      if (!res.ok) {
        throw new Error(`API request failed: ${res.status}`);
      }

      const timelineData = await res.json();
      setFriendResult(timelineData)
      setPlayer2Stats(timelineData.stats);
      onPlayer2Found(timelineData.stats);
      setHasSearched(true);
    } catch (err) {
      console.error("Error fetching API data:", err);
      setFriendResult({ error: "Failed to load timeline." });
    }
  };

  const getStatColor = (stat1, stat2) => {
    if (!hasSearched) return "text-gray-300"; // Gray if no search yet
    
    const val1 = stat1;
    const val2 = stat2;
    
    if (!stat2 || stat2 === "") return "text-gray-300";
    if (isNaN(val1) || isNaN(val2)) return "text-gray-300";
    
    if (val1 > val2) return "text-green-400";
    if (val1 < val2) return "text-red-400";
    return "text-gray-300";
  };

  return (
    <div className="flex flex-col items-center justify-center p-8">
      {/* Search Bar at Top - Centered */}
      <div className="w-full max-w-md mb-8">
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1 px-4 py-3 bg-gray-800 bg-opacity-70 border border-gray-700 rounded text-white focus:outline-none focus:border-gray-500"
            placeholder="Find opponent..."
          />
          <button
            onClick={handleSearch}
            className="magical-button"
        >
            <span className="button-text">Search</span>
                <div className="particles">
                    <span className="particle"></span>
                    <span className="particle"></span>
                    <span className="particle"></span>
                    <span className="particle"></span>
                </div>
          </button>
        </div>
        {hasSearched && player2Stats.Games && (
          <p className="text-green-400 text-center text-sm mt-2">
            Player found: {searchQuery}
          </p>
        )}
      </div>

      {/* Stats Display - Identical to Social */}
      <div className="bg-black bg-opacity-70 rounded-lg p-8 w-full max-w-md">
        <h3 className="text-xl font-semibold text-white mb-6 text-center">
          Searched Player&apos;s Name
        </h3>
        
        <div className="space-y-1">
          {stats.map(stat => (
            <div key={stat} className={`flex justify-between items-center px-3 py-2 bg-gray-800 border border-gray-700 rounded ${getStatColor(player1Stats[stat], player2Stats[stat])}`}>
              <label className={"text-sm font-medium capitalize"}>
                {displayStats[stat]}
              </label>
              <div className="font-semibold">
                {hasSearched ? (player2Stats[stat].toFixed(2) || "0") : (player2Stats[stat] || "0")}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SearchAndCompare;