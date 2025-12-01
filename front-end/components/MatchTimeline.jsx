import React, { useState } from "react";

const MatchTimeline = ({ match }) => {
  const [expandedEventId, setExpandedEventId] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(null);
  const [eventSummaries, setEventSummaries] = useState({});

  // Event type icons and colors
  const getEventStyle = (eventType) => {
    const styles = {
      OBJECTIVE: {
        icon: "👾",
        color: "bg-blue-600",
        borderColor: "border-blue-400",
        textColor: "text-blue-200",
      },
      STRUCTURE: {
        icon: "🏤",
        color: "bg-red-600",
        borderColor: "border-red-400",
        textColor: "text-red-200",
      },
      TEAMFIGHT: {
        icon: "⚔️",
        color: "bg-purple-600",
        borderColor: "border-purple-400",
        textColor: "text-purple-200",
      },
      KILL: {
        icon: "💀",
        color: "bg-orange-600",
        borderColor: "border-orange-400",
        textColor: "text-orange-200",
      },
    };
    return styles[eventType] || styles.OBJECTIVE;
  };

  // Format timestamp to minutes:seconds
  const formatTimestamp = (minutes) => {
    const min = Math.floor(minutes);
    const sec = Math.floor((minutes - min) * 60);
    return `${min}:${sec.toString().padStart(2, "0")}`;
  };

  // Get objective or structure type label
  const getEventLabel = (event) => {
    if (event.event_details.objective_type) {
      return event.event_details.objective_type.replace(/_/g, " ");
    }
    if (event.event_details.structure_type) {
      return event.event_details.structure_type.replace(/_/g, " ");
    }
    return event.event_type;
  };

  // Get team label
  const getTeamLabel = (team) => {
    return team === "PLAYER_TEAM" ? "Your Team" : "Enemy Team";
  };

  const toggleEvent = async (eventId, event) => {
    if (expandedEventId === eventId) {
      setExpandedEventId(null);
      return;
    }
    
    setExpandedEventId(eventId);
    
    // If we already have the summary cached or the event has it, don't fetch
    if (eventSummaries[eventId] || event.summary) {
      return;
    }
    
    // Fetch summary from API
    setLoadingSummary(eventId);
    try {
      const response = await fetch('https://v4ft9564pb.execute-api.us-west-2.amazonaws.com/timeline/events/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_id: eventId })
      });
      
      if (response.ok) {
        const data = await response.json();
        setEventSummaries(prev => ({
          ...prev,
          [eventId]: data.summary || 'No summary available for this event.'
        }));
      } else {
        setEventSummaries(prev => ({
          ...prev,
          [eventId]: 'Summary not yet generated.'
        }));
      }
    } catch (error) {
      console.error('Error fetching summary:', error);
      setEventSummaries(prev => ({
        ...prev,
        [eventId]: 'Failed to load summary.'
      }));
    } finally {
      setLoadingSummary(null);
    }
  };

  if (!match) {
    return (
      <div className="flex items-center justify-center h-full bg-black bg-opacity-70 rounded-lg p-6">
        <p className="text-gray-400">Select a match to view timeline</p>
      </div>
    );
  }

  // Remove duplicate events based on event_id
  const uniqueEvents = match.events.reduce((acc, event) => {
    if (!acc.find(e => e.event_id === event.event_id)) {
      acc.push(event);
    }
    return acc;
  }, []);

  return (
    <div className="bg-black bg-opacity-70 rounded-lg p-6 flex flex-col min-h-0">
      <h3 className="text-xl font-semibold text-white mb-4 flex-shrink-0">Match Timeline</h3>
      
      <div className="relative flex-1 min-h-0">
        {/* Vertical line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-green-700"></div>
        
        <div className="space-y-4 pb-4">
          {uniqueEvents.map((event, index) => {
            const style = getEventStyle(event.event_type);
            const isExpanded = expandedEventId === event.event_id;
            
            return (
              <div key={event.event_id} className="relative pl-14">
                {/* Timeline dot */}
                <div
                  className={`absolute left-3 top-2 w-6 h-6 rounded-full ${style.color} ${style.borderColor} border-2 flex items-center justify-center text-xs z-10`}
                >
                  {style.icon}
                </div>
                
                {/* Event card */}
                <div
                  className={`${style.color} bg-opacity-20 border ${style.borderColor} rounded-lg p-4 cursor-pointer hover:bg-opacity-30 transition-all`}
                  onClick={() => toggleEvent(event.event_id, event)}
                >
                  {/* Event header */}
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-semibold">
                          {formatTimestamp(event.timestamp_minutes)}
                        </span>
                        <span className={`text-sm ${style.textColor}`}>
                          {event.game_state.toUpperCase()}
                        </span>
                      </div>
                      <h4 className="text-white font-medium mt-1">
                        {getEventLabel(event)}
                      </h4>
                      {event.event_details.securing_team && (
                        <p className="text-sm text-gray-300">
                          {getTeamLabel(event.event_details.securing_team)}
                        </p>
                      )}
                      {event.event_details.destroying_team && (
                        <p className="text-sm text-gray-300">
                          {getTeamLabel(event.event_details.destroying_team)}
                        </p>
                      )}
                    </div>
                    
                    {/* Impact score badge */}
                    <div className="bg-black bg-opacity-50 px-3 py-1 rounded flex-shrink-0">
                      <span className="text-yellow-400 font-semibold text-sm">
                        {event.impact_score}
                      </span>
                    </div>
                  </div>
                  
                  {/* Expandable details */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-gray-600">
                      <div className="space-y-2 mb-3">
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-400">Gold Difference:</span>
                          <span className={`font-semibold ${
                            event.context?.gold_difference > 0 
                              ? 'text-green-400' 
                              : 'text-red-400'
                          }`}>
                            {event.context?.gold_difference > 0 ? '+' : ''}
                            {event.context?.gold_difference ?? 0}
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-400">Player Location:</span>
                          <span className="text-white">
                            {event.context?.player_location?.lane ?? 'Unknown'}
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-400">Distance:</span>
                          <span className="text-white">
                            {Math.round(event.context?.player_location?.distance_to_event ?? 0)} units
                          </span>
                        </div>
                      </div>
                      
                      <div className="bg-black bg-opacity-30 p-3 rounded text-sm text-gray-200">
                        {loadingSummary === event.event_id ? (
                          <div className="flex items-center justify-center py-2">
                            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                            <span>Loading AI summary...</span>
                          </div>
                        ) : (
                          eventSummaries[event.event_id] || event.summary || 'No summary available for this event.'
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Expand indicator */}
                  <div className="text-center mt-2">
                    <span className="text-xs text-gray-400">
                      {isExpanded ? '▲ Click to collapse' : '▼ Click for details'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default MatchTimeline;