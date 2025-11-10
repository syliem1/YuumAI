import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import FlipPage from "./FlipPage";
import SummaryFront from "./SummaryFront";
import SummaryBack from "./SummaryBack";
import Social from "./Social";
import SearchAndCompare from "./SearchandCompare";
import MatchSelector from "./MatchSelector";
import MatchTimeline from "./MatchTimeline";
import { useTimelineContext } from "@/context/TimelineContext";
import ChatInput from "./ChatInput";
import ChatOutput from "./ChatOutput.jsx";
import AncientRunicPage from "./AncientRunicPage.jsx";
import MapFragmentPage from "./MapFragmentPage";


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
    "avg_kda": 0,
    "avg_cs_per_min": 0,
    "avg_kill_participation": 0,
    "avg_dpm": 0,
    "avg_gpm": 0,
    "avg_solo_kills": 0,
    "avg_vision_score": 0,
    "avg_cc_time": 0});
  
  const [player2Stats, setPlayer2Stats] = useState({
    "avg_kda": 0,
    "avg_cs_per_min": 0,
    "avg_kill_participation": 0,
    "avg_dpm": 0,
    "avg_gpm": 0,
    "avg_solo_kills": 0,
    "avg_vision_score": 0,
    "avg_cc_time": 0});

  // Chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [isLoadingChat, setIsLoadingChat] = useState(false);

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
    setPlayer1Stats(timelineResult.stats)
  }, [timelineResult]);
  

  // Get the currently selected match
  const selectedMatch = useMemo(() => 
    matches.find(m => m.match_id === selectedMatchId),
    [matches, selectedMatchId]
  );

  // Memoize the match selector callback
  const handleMatchSelect = useCallback((matchId) => {
    setSelectedMatchId(matchId);
  }, []);

  // Handle sending chat messages
  const handleSendMessage = useCallback(async (userMessage) => {
    const timestamp = new Date().toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });

    // Add user message
    const newUserMessage = { 
      sender: "user", 
      text: userMessage, 
      timestamp 
    };
    setChatMessages(prev => [...prev, newUserMessage]);
    setIsLoadingChat(true);

    try {
      // TODO: Replace with actual API call to your backend
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      const data = await response.json();
      
      // Add bot response
      const botMessage = { 
        sender: "bot", 
        text: data.reply || "I received your question. Let me analyze that for you...",
        timestamp: new Date().toLocaleTimeString([], { 
          hour: '2-digit', 
          minute: '2-digit' 
        })
      };
      setChatMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("Chat error:", error);
      // Add error message
      const errorMessage = {
        sender: "bot",
        text: "I apologize, but I'm having trouble connecting right now. Please try again later.",
        timestamp: new Date().toLocaleTimeString([], { 
          hour: '2-digit', 
          minute: '2-digit' 
        })
      };
      setChatMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoadingChat(false);
    }
  }, []);

  // Create page structure once and store it in a ref
  const pageStructure = useMemo(() => 

     [
    { cover: "book_cover.jpg", frontCover: true, id: 0 },
    { front: <AncientRunicPage 
        variant="power"           // "default", "power", "mystical", "elements"
        centerText="ᛗᚨᚷᛁᚲ"       // Custom text at bottom (or null to hide)
        runeColor="#8b7355"       // Color of the runes
        runeCount={12}            // Number of runes (default 9)
      />, back: <MapFragmentPage 
        region="Shurima"          // Text displayed in center
        variant="mountains"       // "default", "mountains", "rivers", "forest"
        showCompass={true}        // Show/hide compass rose
        markerCount={5}           // Number of location markers (default 3)
        fragmentCount={3}         // Number of map fragments (1-3)
        theme="mystical"          // "warm", "cool", "dark", "mystical"
      />, id: 1 },
    { 
      front: <AncientRunicPage 
        variant="mystical"           // "default", "power", "mystical", "elements"
        centerText="ᛗᚨᚷᛁᚲ"       // Custom text at bottom (or null to hide)
        runeColor="#558b7dff"       // Color of the runes
        runeCount={10}            // Number of runes (default 9)
      />, 
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
      back: <MapFragmentPage 
        region="Ionia"          // Text displayed in center
        variant="forest"       // "default", "mountains", "rivers", "forest"
        showCompass={true}        // Show/hide compass rose
        markerCount={8}           // Number of location markers (default 3)
        fragmentCount={3}         // Number of map fragments (1-3)
        theme="mystical"          // "warm", "cool", "dark", "mystical"
      />,
      bookmark: { label: "Summary", targetPage: 3, x: "12%", color: "#7B4643" },
      id: 3
    },
    { front: <AncientRunicPage 
        variant="elements"           // "default", "power", "mystical", "elements"
        centerText="ᛗᚨᚷᛁᚲ"       // Custom text at bottom (or null to hide)
        runeColor="#8b5582ff"       // Color of the runes
        runeCount={7}            // Number of runes (default 9)
      />, back: <MapFragmentPage 
        region="Zaun"          // Text displayed in center
        variant="default"       // "default", "mountains", "rivers", "forest"
        showCompass={true}        // Show/hide compass rose
        markerCount={4}           // Number of location markers (default 3)
        fragmentCount={8}         // Number of map fragments (1-3)
        theme="dark"          // "warm", "cool", "dark", "mystical"
      />, id: 4 },
    { 
      front: <AncientRunicPage 
        variant="default"           // "default", "power", "mystical", "elements"
        centerText="ᛗᚨᚷᛁᚲ"       // Custom text at bottom (or null to hide)
        runeColor="#377b45ff"       // Color of the runes
        runeCount={16}            // Number of runes (default 9)
      />, 
      back: "social",
      id: 5
    },
    { 
      front: "search",
      back: <MapFragmentPage 
        region="Shadow Isles"          // Text displayed in center
        variant="rivers"       // "default", "mountains", "rivers", "forest"
        showCompass={true}        // Show/hide compass rose
        markerCount={7}           // Number of location markers (default 3)
        fragmentCount={6}         // Number of map fragments (1-3)
        theme="dark"          // "warm", "cool", "dark", "mystical"
      />,
      bookmark: { label: "Social", targetPage: 6, x: "40%", color: "#354B89" },
      id: 6
    },
    { front: <AncientRunicPage 
        variant="power"           // "default", "power", "mystical", "elements"
        centerText="ᛗᚨᚷᛁᚲ"       // Custom text at bottom (or null to hide)
        runeColor="#91b047ff"       // Color of the runes
        runeCount={12}            // Number of runes (default 9)
      />, back: <MapFragmentPage 
        region="Demacia"          // Text displayed in center
        variant="mountains"       // "default", "mountains", "rivers", "forest"
        showCompass={true}        // Show/hide compass rose
        markerCount={6}           // Number of location markers (default 3)
        fragmentCount={9}         // Number of map fragments (1-3)
        theme="warm"          // "warm", "cool", "dark", "mystical"
      />, id: 7 },
    { 
      front: <AncientRunicPage 
        variant="mystical"           // "default", "power", "mystical", "elements"
        centerText="ᛗᚨᚷᛁᚲ"       // Custom text at bottom (or null to hide)
        glowColor="rgba(59, 185, 162, 0.8)"  // Glow effect color
        runeCount={15}            // Number of runes (default 9)
      />, 
      back: "matchSelector",
      id: 8
    },
    { 
      front: "matchTimeline",
      back: <MapFragmentPage 
        region="Freljord"          // Text displayed in center
        variant="mountains"       // "default", "mountains", "rivers", "forest"
        showCompass={true}        // Show/hide compass rose
        markerCount={8}           // Number of location markers (default 3)
        fragmentCount={8}         // Number of map fragments (1-3)
        theme="cool"          // "warm", "cool", "dark", "mystical"
      />,
      bookmark: { label: "Matches", targetPage: 9, x: "65%", color: "#595440" },
      id: 9
    },
    { front: <AncientRunicPage 
        variant="elements"           // "default", "power", "mystical", "elements"
        centerText="ᛗᚨᚷᛁᚲ"       // Custom text at bottom (or null to hide)
        glowColor="rgba(96, 78, 171, 0.8)"  // Glow effect color
        runeCount={12}            // Number of runes (default 9)
      />, back: "chatInput", id: 10 },
    { 
      front: "chatOutput", 
      back: <MapFragmentPage 
        region="Shurima"          // Text displayed in center
        variant="mountains"       // "default", "mountains", "rivers", "forest"
        showCompass={true}        // Show/hide compass rose
        markerCount={5}           // Number of location markers (default 3)
        fragmentCount={3}         // Number of map fragments (1-3)
        theme="mystical"          // "warm", "cool", "dark", "mystical"
      />,
      bookmark: { label: "Questions", targetPage: 11, x: "78%", color: "#4A5568" },
      id: 11 
    },
    { cover: "green-cover.jpg", id: 12 },
  ], []);

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

    // Replace ChatInput component
    if (page.back === "chatInput") {
      newPage.back = <ChatInput 
        onSendMessage={handleSendMessage} 
        isLoading={isLoadingChat}
      />;
    }

    // Replace ChatOutput component
    if (page.front === "chatOutput") {
      newPage.front = <ChatOutput messages={chatMessages} />;
    }
    
    return newPage;
  }, [player1Stats, player2Stats, matches, selectedMatchId, selectedMatch, handleMatchSelect, handlePlayer2Found, chatMessages, isLoadingChat, handleSendMessage]);

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