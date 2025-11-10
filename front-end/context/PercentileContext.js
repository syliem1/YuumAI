"use client";
import { createContext, useContext, useState } from "react";

const PercentileContext = createContext();

export function PercentileContextProvider({ children }) {
  const [percentileResult, setPercentileResult] = useState(null);
  return (
    <PercentileContext.Provider value={{ percentileResult, setPercentileResult }}>
      {children}
    </PercentileContext.Provider>
  );
}

export const usePercentileContext = () => useContext(PercentileContext);
