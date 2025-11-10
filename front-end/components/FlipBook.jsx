import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import FlipPage from "./FlipPage";
import SummaryFront from "./SummaryFront";
import SummaryBack from "./SummaryBack";
import Social from "./Social";
import SearchAndCompare from "./SearchandCompare";
import MatchSelector from "./MatchSelector";
import MatchTimeline from "./MatchTimeline";
import { useTimelineContext } from "@/context/TimelineContext";


const FlipBook = () => {
  const [pages, setPages] = useState([]);
  const [zIndices, setZIndices] = useState([]);
  const [flippedStates, setFlippedStates] = useState([]);
  const [currentPage, setCurrentPage] = useState(0);
  const [onFirstPage, setOnFirstPage] = useState(true);
  const [onLastPage, setOnLastPage] = useState(false);
  const [isTurning, setIsTurning] = useState(false);
  const { timelineResult } = useTimelineContext();

  // Match Timeline state + Match Selector
  const [matches, setMatches] = useState([]);
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  
  // Player stats state
  const [player1Stats, setPlayer1Stats] = useState({
    Games: "150",
    WinRate: "60%",
    KDA: "100",
    CPM: "85",
    gold15: "70",
    GPM: "60",
    DPM: "90"
  });
  
  const [player2Stats, setPlayer2Stats] = useState({
    Games: "",
    WinRate: "",
    KDA: "",
    CPM: "",
    gold15: "",
    GPM: "",
    DPM: ""
  });

  const handlePlayer2Found = useCallback((stats) => {
    setPlayer2Stats(stats);
  }, []);
  
  const [searchQuery, setSearchQuery] = useState("");

  const pageRefs = useRef([]);
  const isInitialized = useRef(false);

  useEffect(() => {
    if (!timelineResult) return; 

    if (timelineResult.timeline_data) {
      setMatches(timelineResult.timeline_data);
      setSelectedMatchId(timelineResult.timeline_data[0]?.match_id || null);
    } else {
      console.warn("No timeline data found in search result:", timelineResult);
    }
  }, [timelineResult]);
  

  // Get the currently selected match - use useMemo to prevent unnecessary recalculations
  const selectedMatch = useMemo(() => 
    matches.find(m => m.match_id === selectedMatchId),
    [matches, selectedMatchId]
  );

  // Memoize the match selector callback to prevent recreating it
  const handleMatchSelect = useCallback((matchId) => {
    setSelectedMatchId(matchId);
  }, []);

  // Create page structure once and store it in a ref
  const pageStructure = useMemo(() => {

    return [
    { cover: "book_cover.jpg", frontCover: true, id: 0 },
    { front: "test.txt", back: "test.txt", id: 1 },
    { 
      front: "test.txt", 
      back: <SummaryBack data={{ 
        region: "Shurima", 
        profile:["Late-Game", "Scaling", "Empire-Building"],
        statistics: { gamesPlayed: 120, winRate: "55%", averageKDA: "3.5", cspm: "7.8"}, 
        mostPlayed: [
          { name: "Azir", games: 23 },
          { name: "Sivir", games: 17 },
          { name: "Cassiopeia", games: 12 },
        ],
      }}/>,
      id: 2
    },
    { 
      front: <SummaryFront data={{ 
        roles: { top: 2, jg: 19, mid: 10, adc: 8, sup: 5 },
        strengths:["Azir", "Sivir", "Cassiopeia"], 
        weaknesses:["Nasus", "Taliyah"] 
      }}/>, 
      back: "test.txt",
      bookmark: { label: "Summary", targetPage: 3, x: "12%", color: "#7B4643" },
      id: 3
    },
    { front: "test.txt", back: "test.txt", id: 4 },
    { 
      front: "test.txt", 
      back: "social", // Placeholder - will be replaced
      id: 5
    },
    { 
      front: "search", // Placeholder - will be replaced
      back: "text",
      bookmark: { label: "Social", targetPage: 6, x: "50%", color: "#354B89" },
      id: 6
    },
    { front: "text", back: "test.txt", id: 7 },
    { 
      front: "test.txt", 
      back: "matchSelector", // Placeholder - will be replaced
      id: 8
    },
    { 
      front: "matchTimeline", // Placeholder - will be replaced
      back: "test.txt",
      bookmark: { label: "Matches", targetPage: 9, x: "75%", color: "#595440" },
      id: 9
    },
    { front: "test.txt", back: "test.txt", id: 10 },
    { cover: "green-cover.jpg", id: 11 },
  ]}, []); // Empty dependency array - only create once

  // Initialize pages only once
  useEffect(() => {
    if (isInitialized.current) return;
    
    const total = pageStructure.length;
    setPages(pageStructure);
    setZIndices(Array.from({ length: total }, (_, i) => total - i + 1));
    setFlippedStates(Array(total).fill(false));

    pageRefs.current = Array(total)
      .fill()
      .map(() => React.createRef());
    
    isInitialized.current = true;
  }, [pageStructure]);

  const handleFlip = useCallback((pageIndex, isFlipped) => {
    setFlippedStates(prevFlipped => {
      const updatedFlipped = [...prevFlipped];
      updatedFlipped[pageIndex] = isFlipped;
      
      setZIndices(prevZ => {
        const maxZ = Math.max(...prevZ);
        const newZ = [...prevZ];
        newZ[pageIndex] = maxZ + 1;
        return newZ;
      });

      const flippedCount = updatedFlipped.filter(Boolean).length;
      setCurrentPage(flippedCount);

      const firstFlipped = updatedFlipped[0];
      const lastFlipped = updatedFlipped[updatedFlipped.length - 1];
      setOnFirstPage(!firstFlipped);
      setOnLastPage(!!lastFlipped);

      return updatedFlipped;
    });
  }, []);

  const flipToPage = useCallback(async (targetPage) => {
    if (targetPage === currentPage) return;
    if (isTurning) return;
    setIsTurning(true);

    if (targetPage > currentPage) {
      for (let i = currentPage; i < targetPage; i++) {
        await new Promise((resolve) => {
          setTimeout(() => {
            pageRefs.current[i]?.flip();
            resolve();
          }, 800);
        });
      }
    } else {
      for (let i = currentPage - 1; i >= targetPage; i--) {
        await new Promise((resolve) => {
          setTimeout(() => {
            pageRefs.current[i]?.flip();
            resolve();
          }, 800);
        });
      }
    }

    setTimeout(() => {
      setIsTurning(false);
    }, 1000);
  }, [currentPage, isTurning]);

  const handleBookmarkClick = useCallback((e, targetPage) => {
    e.stopPropagation();
    flipToPage(targetPage);
  }, [flipToPage]);

  // Replace placeholders with actual components that have dynamic data
  const getPageContent = useCallback((page) => {
    const newPage = { ...page };
    
    // Replace Social component
    if (page.back === "social") {
      newPage.back = <Social input1={player1Stats} input2={player2Stats} />;
    }
    
    // Replace SearchAndCompare component
    if (page.front === "search") {
      newPage.front = <SearchAndCompare onPlayer2Found={handlePlayer2Found} player1Stats={player1Stats}/>;
    }
    
    // Replace MatchSelector component
    if (page.back === "matchSelector") {
      newPage.back = <MatchSelector 
        matches={matches} 
        selectedMatchId={selectedMatchId}
        onMatchSelect={handleMatchSelect}
      />;
    }
    
    // Replace MatchTimeline component
    if (page.front === "matchTimeline") {
      newPage.front = <MatchTimeline match={selectedMatch} />;
    }
    
    return newPage;
  }, [player1Stats, player2Stats, matches, selectedMatchId, selectedMatch, handleMatchSelect, handlePlayer2Found]);

  if(!timelineResult){
    return (
      <div className="w-full text-center text-3xl">
        LOADING...
      </div>
    )
  }

  return (
    <div className="book-frame">
      <div className="page-wrapper slideUp-animation">
        {pages.map((page, i) => {
          const pageContent = getPageContent(page);
          return (
            <FlipPage
              key={page.id}
              ref={(el) => (pageRefs.current[i] = el)}
              Front={pageContent.front}
              Back={pageContent.back}
              Cover={pageContent.cover}
              FrontCover={pageContent.frontCover}
              onFlip={(flipped) => handleFlip(i, flipped)}
              flipped={flippedStates[i]}
              zIndex={zIndices[i]}
              bookmark={pageContent.bookmark}
              onBookmarkClick={handleBookmarkClick}
              onFirstPage={onFirstPage}
              onLastPage={onLastPage}
            />
          );
        })}
      </div>
    </div>
  );
};

export default FlipBook;