"use client";
import { createContext, useContext, useState } from "react";

const PlayerContext = createContext();

export function PlayerContextProvider({ children }) {
  const [playerResult, setPlayerResult] = useState(null);
  return (
    <PlayerContext.Provider value={{ playerResult, setPlayerResult }}>
      {children}
    </PlayerContext.Provider>
  );
}

export const usePlayerContext = () => useContext(PlayerContext);
