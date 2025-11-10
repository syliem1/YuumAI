"use client";
import { createContext, useContext, useState } from "react";

const TimelineContext = createContext();

export function TimelineContextProvider({ children }) {
  const [timelineResult, setTimelineResult] = useState(null);
  return (
    <TimelineContext.Provider value={{ timelineResult, setTimelineResult }}>
      {children}
    </TimelineContext.Provider>
  );
}

export const useTimelineContext = () => useContext(TimelineContext);
