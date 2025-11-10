import React, { useState } from "react";
import { useRouter } from "next/router";
import { useTimelineContext } from "@/context/TimelineContext";

export default function Home() {
  const [usernameValue, setUsernameValue] = useState("");
  const [taglineValue, setTaglineValue] = useState("");
  const [gameCountValue, setCountValue] = useState(10);

  const handleChange = (event) => {
    setInputValue(event.target.value);
  };
  const { setTimelineResult } = useTimelineContext();
  const router = useRouter();
  const handleSearch = async () => {
    router.push("/FlipBook");
    const endpoint = "https://v4ft9564pb.execute-api.us-west-2.amazonaws.com/player/process";

    const body = {
      game_name: "ShadowLeaf",
      tagline: "8005",
      num_games: 1
    };

    try {
      console.log("Fetching...");

      const res= await 
        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })

      if (!res.ok) {
        throw new Error(`API request failed: ${res.status}`);
      }

      const timelineData = await res.json();

      setTimelineResult(timelineData);

    } catch (err) {
      console.error("Error fetching API data:", err);
      setTimelineResult({ error: "Failed to load timeline." });
      router.push("/")
    }
  };

  return (
    <section className="fixed left-0 top-0 m-0 flex h-full w-full items-center justify-center overflow-hidden p-0">
      {/* Background */}
      <div className="background_full"></div>

      {/* Content */}
      <div className="detention_card">
        <input type="text" className="riotID_box" placeholder="Riot ID" onChange={setUsernameValue}/>
        <input type="text" className="tagline_box" placeholder="1234" onChange={setTaglineValue}/>
        <input type="number" className="num_games_analyzed_box" placeholder="10" onChange={setCountValue}/>
        <button
          style={{
            position: "absolute",
            bottom:"14%",
            right:"18%"}}
            className="magical-button"
            onClick={handleSearch}
        >
            <span className="button-text">Submit</span>
                <div className="particles">
                    <span className="particle"></span>
                    <span className="particle"></span>
                    <span className="particle"></span>
                    <span className="particle"></span>
                </div>
        </button>
      </div>
    </section>
  );
}
