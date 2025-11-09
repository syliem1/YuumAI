import React, { useEffect, useRef, useState, useCallback } from "react";
import FlipPage from "./FlipPage";
import SummaryFront from "./SummaryFront";
import SummaryBack from "./SummaryBack";
import Social from "./Social";
import SearchAndCompare from "./SearchandCompare";
import { color } from "framer-motion";


const FlipBook = () => {
  const [pages, setPages] = useState([]);
  const [zIndices, setZIndices] = useState([]);
  const [flippedStates, setFlippedStates] = useState([]);
  const [currentPage, setCurrentPage] = useState(0);
  const [onFirstPage, setOnFirstPage] = useState(true);
  const [onLastPage, setOnLastPage] = useState(false);
  const [isTurning, setIsTurning] = useState(false);
  
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

  const handlePlayer2Found = (stats) => {
    setPlayer2Stats(stats);
  };
  
  const [searchQuery, setSearchQuery] = useState("");

  const pageRefs = useRef([]);

  // Mock function to search for player stats
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    // TODO: Replace this with actual API call to fetch player stats
    // For now, using mock data
    const mockPlayerData = {
      Games: "",
      WinRate: "",
      KDA: "",
      CPM: "",
      gold15: "",
      GPM: "",
      DPM: ""
    };
    
    setPlayer2Stats(mockPlayerData);
  };

  useEffect(() => {
    const pageList = [
      { cover: "book_cover.jpg", frontCover: true },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: <SummaryBack data={{ region: "Shurima", profile:["Late-Game", "Scaling", "Empire-Building"],
        statistics: { gamesPlayed: 120, winRate: "55%", averageKDA: "3.5", cspm: "7.8"}, 
        mostPlayed: [
          { name: "Azir", games: 23 },
          { name: "Sivir", games: 17 },
          { name: "Cassiopeia", games: 12 },],
      }}/> },
      { front: <SummaryFront data={{ roles: { top: 2, jg: 19, mid: 10, adc: 8, sup: 5 },
        strengths:["Azir", "Sivir", "Cassiopeia"], weaknesses:["Nasus", "Taliyah"] }}/>, back: "test.txt",
        bookmark: { label: "Summary", targetPage: 3, x: "12%", color: "#7B4643" }
      },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: <Social input1={player1Stats} input2={player2Stats} /> },
      // Search bar on the front (right page) with Social bookmark
      { front: <SearchAndCompare onPlayer2Found={handlePlayer2Found} player1Stats={player1Stats}/> , back: "text",
        bookmark: { label: "Social", targetPage: 6, x: "50%", color: "#354B89" }
      },
      // Player 2's perspective on the front (left page after bookmark)
      { front: "text", back: "test.txt" },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: "test.txt",
        bookmark: { label: "Matches", targetPage: 9, x: "75%", color: "#595440" }
      },
      { front: "test.txt", back: "test.txt" },
      { cover: "green-cover.jpg" },
    ].map((page, index) => ({ ...page, id: index }));

    setPages(pageList);

    const total = pageList.length;
    setZIndices(Array.from({ length: total }, (_, i) => total - i + 1));
    setFlippedStates(Array(total).fill(false));

    pageRefs.current = Array(total)
      .fill()
      .map((_, i) => pageRefs.current[i] || React.createRef());
  }, [player1Stats, player2Stats, searchQuery]); // Re-render when stats change

  const handleFlip = (pageIndex, isFlipped) => {
    const updatedFlipped = [...flippedStates];
    updatedFlipped[pageIndex] = isFlipped;
    setFlippedStates(updatedFlipped);

    const maxZ = Math.max(...zIndices);
    const newZ = [...zIndices];
    newZ[pageIndex] = maxZ + 1;
    setZIndices(newZ);

    const flippedCount = updatedFlipped.filter(Boolean).length;
    setCurrentPage(flippedCount);

    checkAllPagesFlipped(updatedFlipped);
  };

  const checkAllPagesFlipped = (flips) => {
    const firstFlipped = flips[0];
    const lastFlipped = flips[flips.length - 1];
    setOnFirstPage(!firstFlipped);
    setOnLastPage(!!lastFlipped);
  };

  const flipToPage = async (targetPage) => {
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
  };

  const handleBookmarkClick = (e, targetPage) => {
    e.stopPropagation();
    flipToPage(targetPage);
  };

  useEffect(() => {
    if (!pages.length) return;

    const waitForRefs = async () => {
      const total = pages.length;
      for (let i = 0; i < total; i++) {
        let tries = 0;
        while (!pageRefs.current[i] && tries < 40) {
          await new Promise((r) => setTimeout(r, 50));
          tries++;
        }
      }

      await new Promise((r) => requestAnimationFrame(r));
      await new Promise((r) => setTimeout(r, 300));

    };

    waitForRefs();
  }, [pages.length]);

  return (
    <div className="book-frame">
      <div className="page-wrapper slideUp-animation">
        {pages.map((page, i) => (
          <FlipPage
            key={i}
            ref={(el) => (pageRefs.current[i] = el)}
            Front={page.front}
            Back={page.back}
            Cover={page.cover}
            FrontCover={page.frontCover}
            onFlip={(flipped) => handleFlip(i, flipped)}
            flipped={flippedStates[i]}
            zIndex={zIndices[i]}
            bookmark={page.bookmark}
            onBookmarkClick={handleBookmarkClick}
            onFirstPage={onFirstPage}
            onLastPage={onLastPage}
          />
        ))}
      </div>
    </div>
  );
};

export default FlipBook;
