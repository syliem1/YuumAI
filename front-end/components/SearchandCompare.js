import React, { useState } from "react";

const SearchAndCompare = ({ player1Stats, onPlayer2Found }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [player2Stats, setPlayer2Stats] = useState({
    Games: "",
    WinRate: "",
    KDA: "",
    CPM: "",
    gold15: "",
    GPM: "",
    DPM: ""
  });
  const [hasSearched, setHasSearched] = useState(false); // Track if user has searched

  const stats = ["Games", "WinRate", "KDA", "CPM", "gold15", "GPM", "DPM"];

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    // TODO: Replace with actual API call
    const mockPlayerData = {
      Games: "95",
      WinRate: "55%",
      KDA: "80",
      CPM: "75",
      gold15: "65",
      GPM: "85",
      DPM: "70"
    };
    
    setPlayer2Stats(mockPlayerData);
    setHasSearched(true);
    onPlayer2Found(mockPlayerData); // Pass stats back to parent
  };

  const getStatColor = (stat1, stat2) => {
    if (!hasSearched) return "text-gray-300"; // Gray if no search yet
    
    const val1 = parseFloat(stat1);
    const val2 = parseFloat(stat2);
    
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
          Searched Player's Name
        </h3>
        
        <div className="space-y-1">
          {stats.map(stat => (
            <div key={stat} className={`flex justify-between items-center px-3 py-2 bg-gray-800 border border-gray-700 rounded ${getStatColor(player1Stats[stat], player2Stats[stat])}`}>
              <label className={"text-sm font-medium capitalize"}>
                {stat}
              </label>
              <div className="font-semibold">
                {hasSearched ? (player2Stats[stat] || "0") : (player2Stats[stat] || "0")}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SearchAndCompare;