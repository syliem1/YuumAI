"use client";
import { createContext, useContext, useState } from "react";

const FriendContext = createContext();

export function FriendContextProvider({ children }) {
  const [friendResult, setFriendResult] = useState(null);
  return (
    <FriendContext.Provider value={{ friendResult, setFriendResult }}>
      {children}
    </FriendContext.Provider>
  );
}

export const useFriendContext = () => useContext(FriendContext);
