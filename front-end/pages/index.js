import React, { useState } from "react";
import { useRouter } from "next/router";
import { useTimelineContext } from "@/context/TimelineContext";
import { usePercentileContext } from "@/context/PercentileContext";

export default function Home() {
  const [usernameValue, setUsernameValue] = useState("");
  const [taglineValue, setTaglineValue] = useState("");
  const [gameCountValue, setCountValue] = useState(10);

  const handleUsernameChange = (event) => {
    setUsernameValue(event.target.value);
  };
  const handleTaglineChange = (event) => {
    setTaglineValue(event.target.value);
  };
  const handleCountChange = (event) => {
    setCountValue(event.target.value);
  };
  const { setTimelineResult } = useTimelineContext();
  const { setPercentileResult } = usePercentileContext();
  const router = useRouter();
  const handleSearch = async () => {
    router.push("/loading");
    const endpoint = "https://v4ft9564pb.execute-api.us-west-2.amazonaws.com/player/process";

    const body = {
      game_name: usernameValue,
      tagline: taglineValue,
      num_games: gameCountValue
    };

    try {
      console.log("Fetching...");

      // First, trigger the player processing
      const timelineRes = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!timelineRes.ok) {
        throw new Error(`API request failed: ${timelineRes.status}`);
      }

      const timelineData = await timelineRes.json();
      setTimelineResult(timelineData);

      // Poll for percentiles until data is ready (with timeout)
      let percentileData = null;
      const maxAttempts = 30; // 30 attempts * 2 seconds = 60 seconds max
      let attempt = 0;

      while (attempt < maxAttempts) {
        const percentileRes = await fetch(`https://v4ft9564pb.execute-api.us-west-2.amazonaws.com/player/percentiles?game_name=${usernameValue}&tagline=${taglineValue}`);
        
        if (percentileRes.ok) {
          percentileData = await percentileRes.json();
          
          // Check if data is ready (has actual percentile data)
          if (percentileData.status === 'COMPLETED' || 
              (percentileData.percentiles && Object.keys(percentileData.percentiles).length > 0)) {
            break;
          }
        }

        // Wait 2 seconds before next attempt
        await new Promise(resolve => setTimeout(resolve, 2000));
        attempt++;
      }

      // Set percentile result (even if still processing, we'll handle it in FlipBook)
      console.log('Setting percentileResult:', percentileData);
      console.log('Setting timelineResult:', timelineData);
      setPercentileResult(percentileData || { status: 'PROCESSING', percentiles: {}, ranked_stats: { top_5: [], bottom_5: [] } });
      router.push("/FlipBook")

    } catch (err) {
      console.error("Error fetching API data:", err);
      setTimelineResult({ error: "Failed to load timeline." });
      setPercentileResult({ error: "Failed to load percentiles." });
      router.push("/invalid")
    }
  };

  return (
    <section className="fixed left-0 top-0 m-0 flex h-full w-full items-center justify-center overflow-hidden p-0">
      {/* Background */}
      <div className="background_full"></div>

      {/* Content */}
      <div className="detention_card">
        <input type="text" className="riotID_box" placeholder="Riot ID" value={usernameValue} onChange={handleUsernameChange}/>
        <input type="text" className="tagline_box" placeholder="1234" value={taglineValue} onChange={handleTaglineChange}/>
        <input type="number" className="num_games_analyzed_box" placeholder="10" value={gameCountValue} onChange={handleCountChange}/>
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
