import React, { useState } from "react";
import { useRouter } from "next/router";
import { useContextResults } from "@/context/SearchContext";
import Link from "next/link";

export default function Home() {
  const [inputValue, setInputValue] = useState("");

  const handleChange = (event) => {
    setInputValue(event.target.value);
  };
  const { setSearchResult } = useContextResults();
  const router = useRouter();
  const handleSearch = async () => {
    router.push("/FlipBook");

    try {
      const endpoint = "https://v4ft9564pb.execute-api.us-west-2.amazonaws.com/player/process";
      const body = {
        "game_name": "ShadowLeaf",
        "tagline": "8005",
        "num_games": 1
      };
      console.log("fetching...")
      const res = await fetch(endpoint, {
        method: "POST",
        body,
      });

      if (!res.ok) {
        throw new Error(`AWS API request failed: ${res.status} ${res.statusText}`);
      }

      const data = await res.json();
      setSearchResult(data);
    } catch (err) {
      console.error("Error fetching search results:", err);
      setSearchResult({ error: "Failed to load search results." });
    }
  };

  return (
    <section className="fixed left-0 top-0 m-0 flex h-full w-full items-center justify-center overflow-hidden p-0">
      {/* Top and bottom background layers */}
      <div className="background-top"></div>
      <div className="background-bot"></div>

      {/* Content */}
      <div className="z-10 rounded-lg bg-white/80 p-8 text-center shadow-lg">
        <h1 className="mb-4 text-4xl font-bold text-dark">Welcome!</h1>
        <div className="mt-2 flex items-center space-x-2">
          <input
            type="text"
            value={inputValue}
            onChange={handleChange}
            placeholder="Enter text here"
            className="flex-1 rounded-lg border p-2 text-dark"
          />
            <button className="rounded-lg bg-[#8b6f4e] px-4 py-2 hover:underline text-white transition hover:bg-[#73583f]" onClick={handleSearch}>
              Search
            </button>
        </div>
        <p className="mt-2 text-dark">Current input: {inputValue}</p>
      </div>
    </section>
  );
}
