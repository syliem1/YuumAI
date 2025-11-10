"use client";
import { createContext, useContext, useState } from "react";

const SearchContext = createContext();

export function SearchContextProvider({ children }) {
  const [searchResult, setSearchResult] = useState(null);
  return (
    <SearchContext.Provider value={{ searchResult, setSearchResult }}>
      {children}
    </SearchContext.Provider>
  );
}

export const useContextResults = () => useContext(SearchContext);
