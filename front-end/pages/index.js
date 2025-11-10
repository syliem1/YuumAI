import React, { useState } from "react";
import { useRouter } from "next/router";
import { useTimelineContext } from "@/context/TimelineContext";
import { usePlayerContext } from "@/context/PlayerContext";

export default function Home() {
  const [inputValue, setInputValue] = useState("");

  const handleChange = (event) => {
    setInputValue(event.target.value);
  };
  const { setTimelineResult } = useTimelineContext();
  const { setPlayerResult } = usePlayerContext();
  const router = useRouter();
  const handleSearch = async () => {
    router.push("/FlipBook");

    const timelineEndpoint = "https://v4ft9564pb.execute-api.us-west-2.amazonaws.com/player/process";
    const profileEndpoint = "https://n891ddrkmg.execute-api.us-west-2.amazonaws.com/classify-player";

    const timelinebody = {
      game_name: "ShadowLeaf",
      tagline: "8005",
      num_games: 1
    };

    const profilebody = {
      username: "ShadowLeaf",
      tag: "8005",
      match_count: 10
    }

    try {
      console.log("Fetching data from both APIs...");

      const [timelineRes, profileRes] = await Promise.all([
        fetch(timelineEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(timelinebody),
        }),
        fetch(profileEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(profilebody),
        })
      ]);

      if (!timelineRes.ok || !profileRes.ok) {
        throw new Error(`API request failed: ${timelineRes.status} / ${profileRes.status}`);
      }

      const [timelineData, profileData] = await Promise.all([
        timelineRes.json(),
        profileRes.json(),
      ]);

      setTimelineResult(timelineData);
      setPlayerResult(profileData);

    } catch (err) {
      console.error("Error fetching API data:", err);
      setTimelineResult({ error: "Failed to load timeline." });
      setPlayerResult({ error: "Failed to load profile." });
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
