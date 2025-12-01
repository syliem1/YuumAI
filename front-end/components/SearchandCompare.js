import React, { useState } from "react";
import { useFriendContext } from "@/context/FriendContext";
import { useTimelineContext } from "@/context/TimelineContext";

const SearchAndCompare = ({ player1Stats, onPlayer2Found }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [username, setUsername] = useState("");
  const [tagline, setTagline] = useState("");
  const [fetchingPlayer2, setFetchingPlayer2] = useState(false);
  const [errorFetchingPlayer2, setErrorFetchingPlayer2] = useState(false);
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
  const { friendResult, setFriendResult } = useFriendContext();
  const { timelineResult } = useTimelineContext();
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
    if (!username.trim() || !tagline.trim() || !timelineResult) return;
    
    // TODO: Replace with actual API call
    const endpoint = "https://v4ft9564pb.execute-api.us-west-2.amazonaws.com/player/compare";

    const body = {
      game_name: username,
      tagline: tagline,
      num_games: timelineResult.matches_processed
    };

    try {
      setFetchingPlayer2(true);
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
      setFetchingPlayer2(false);
      setErrorFetchingPlayer2(false);
      setHasSearched(true);
    } catch (err) {
      console.error("Error fetching API data:", err);
      setFriendResult({ error: "Failed to load timeline." });
      setErrorFetchingPlayer2(true)
      setFetchingPlayer2(false);
    }
  };

  const getStatColor = (stat1, stat2) => {
    if (!hasSearched) return "text-gray-300"; // Gray if no search yet
    
    const val1 = stat1;
    const val2 = stat2;
    
    if (!stat2 || stat2 === "") return "text-gray-300";
    if (isNaN(val1) || isNaN(val2)) return "text-gray-300";
    
    if (val1 < val2) return "text-green-400";
    if (val1 > val2) return "text-red-400";
    return "text-gray-300";
  };

  return (
    <div className="flex flex-col items-center justify-center p-8">
      {/* Search Bar at Top - Centered */}
      <div className="w-full max-w-md mb-8">
        <div className="flex gap-2">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            className="flex-1 px-4 py-3 bg-gray-800 bg-opacity-70 border border-gray-700 rounded text-white focus:outline-none focus:border-gray-500"
            placeholder="Game name"
          />
          <input
            type="text"
            value={tagline}
            onChange={(e) => setTagline(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            className="w-24 px-4 py-3 bg-gray-800 bg-opacity-70 border border-gray-700 rounded text-white focus:outline-none focus:border-gray-500"
            placeholder="#tag"
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
      <div className="relative bg-black bg-opacity-70 rounded-lg p-8 w-full max-w-md">
        {fetchingPlayer2 && (<div className="absolute inset-0 bg-black bg-opacity-70 rounded-lg p-8 h-full w-full max-w-md">
          <div className="text-center">
            <div className="relative w-16 h-16 mx-auto mb-4">
              <div className="absolute inset-0 border-4 border-sky-200 border-t-sky-400 rounded-full animate-spin"></div>
            </div>
            <h2 className="text-xl font-semibold text-white">Loading...</h2>
            <p className="text-amber-100">Please wait...</p>
          </div>
        </div>)}
        {!fetchingPlayer2 && errorFetchingPlayer2 && (<div className="absolute inset-0 bg-black bg-opacity-70 rounded-lg p-8 h-full w-full max-w-md">
          <div className="text-center">
            <h2 className="text-xl font-semibold text-white">Error loading player, try again</h2>
          </div>
        </div>)}
        <h3 className="text-xl font-semibold text-white mb-6 text-center">
          {!friendResult && "Search for a player"}
          {friendResult && `${friendResult.player_id}`}
        </h3>
        <div className="space-y-1">
          {stats.map(stat => (
            <div key={stat} className={`flex justify-between items-center px-3 py-2 bg-gray-800 border border-gray-700 rounded ${getStatColor(player1Stats?.[stat], player2Stats?.[stat])}`}>
              <label className={"text-sm font-medium capitalize"}>
                {displayStats[stat]}
              </label>
              <div className="font-semibold">
                {hasSearched ? ((player2Stats?.[stat] ?? 0).toFixed(2)) : (player2Stats?.[stat] ?? "0")}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SearchAndCompare;