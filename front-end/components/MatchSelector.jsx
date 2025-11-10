import React from "react";

const MatchSelector = ({ matches = [], selectedMatchId, onMatchSelect }) => {
  // Format timestamp for display
  const formatMatchLabel = (match, index) => {
    return `Match ${index + 1}`;
  };

  if (!matches || matches.length === 0) {
    return (
      <div className="flex flex-col gap-2 p-4 bg-black bg-opacity-70 rounded-lg">
        <h3 className="text-lg font-semibold text-white mb-2">Select Match</h3>
        <p className="text-gray-400 text-center py-4">No matches available</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 p-4 bg-black bg-opacity-70 rounded-lg">
      <h3 className="text-lg font-semibold text-white mb-2">Select Match</h3>
      <div className="flex flex-col gap-2 max-h-96 overflow-y-auto">
        {matches.map((match, index) => {
          const isSelected = match.match_id === selectedMatchId;
          return (
            <button
              key={match.match_id}
              onClick={() => onMatchSelect(match.match_id)}
              className={`
                px-4 py-3 rounded text-left transition-all duration-200
                ${isSelected 
                  ? 'bg-blue-600 text-white shadow-lg' 
                  : 'bg-gray-800 text-white hover:bg-gray-700 active:bg-gray-600'
                }
                border ${isSelected ? 'border-blue-400' : 'border-gray-700'}
              `}
            >
              <div className="flex flex-col">
                <span className="font-medium">{formatMatchLabel(match, index)}</span>
                <span className="text-sm text-gray-300">
                  {match.total_events} events
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default MatchSelector;