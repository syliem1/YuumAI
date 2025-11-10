"use client";
import { createContext, useContext, useState } from "react";

const RealTimelineContext = createContext();

export function RealTimelineContextProvider({ children }) {
  const [realTimelineResult, setRealTimelineResult] = useState(null);
  return (
    <RealTimelineContext.Provider value={{ realTimelineResult, setRealTimelineResult }}>
      {children}
    </RealTimelineContext.Provider>
  );
}

export const useRealTimelineContext = () => useContext(RealTimelineContext);
