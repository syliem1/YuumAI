import React from "react";

const Social = ({ input1 = {}, input2 = {} }) => {
  const stats1 = input1;
  const stats2 = input2;
  
  const getStatColor = (stat1, stat2) => {
    const val1 = stat1;
    const val2 = stat2;
    
    if (!stat2 || stat2 === "") return "text-gray-300";
    if (isNaN(val1) || isNaN(val2)) return "text-gray-300";
    
    if (val1 > val2) return "text-green-400";
    if (val1 < val2) return "text-red-400";
    return "text-gray-300";
  };
  
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
  return (
    <div className="flex flex-col items-center justify-center p-8">
      <h2 className="section-title">Stat Comparison</h2>
      {/* Empty space to match search bar height */}
      <div className="w-full max-w-md mb-6"></div>
      
      {/* Stats Display */}
      <div className="bg-black bg-opacity-70 rounded-lg p-8 w-full max-w-md">
        <h3 className="text-xl font-semibold text-white mb-6 text-center">
          Player Name
        </h3>
        
        <div className="space-y-1">
          {stats.map(stat => (
            <div key={stat} className={`flex justify-between items-center px-3 py-2 bg-gray-800 border border-gray-700 rounded ${getStatColor(stats1[stat], stats2[stat])}`}>
              <label className="text-sm font-medium capitalize">
                {displayStats[stat]}
              </label>
              <div className="font-semibold">
                {stats1[stat].toFixed(2) || "0"}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Social;