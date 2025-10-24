import React, { useEffect, useRef, useState } from "react";
import FlipPage from "./FlipPage";
import { color } from "framer-motion";

const FlipBook = () => {
  const [pages, setPages] = useState([]);
  const [zIndices, setZIndices] = useState([]);
  const [flippedStates, setFlippedStates] = useState([]);
  const [currentPage, setCurrentPage] = useState(0);
  const [onFirstPage, setOnFirstPage] = useState(true);
  const [onLastPage, setOnLastPage] = useState(false);
  const [isTurning, setIsTurning] = useState(false);

  const pageRefs = useRef([]);

  useEffect(() => {
    const pageList = [
      { cover: "green-cover.jpg", frontCover: true },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: "test.txt",
        bookmark: { label: "Page 3", targetPage: 3, y: "10%", color: "#3b82f6" }
      },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: "test.txt",
        bookmark: { label: "Page 6", targetPage: 6, y: "32.5%", color: "#f63b89ff" }
      },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: "test.txt" },
      { front: "test.txt", back: "test.txt",
        bookmark: { label: "Page 9", targetPage: 9, y: "55%", color: "#2aa51fff" }
      },
      { front: "test.txt", back: "test.txt" },
      { cover: "green-cover.jpg" },
    ].map((page, index) => ({ ...page, id: index }));

    setPages(pageList);

    const total = pageList.length;
    setZIndices(Array.from({ length: total }, (_, i) => total - i + 1));
    setFlippedStates(Array(total).fill(false));

    // Initialize refs array
    pageRefs.current = Array(total)
      .fill()
      .map((_, i) => pageRefs.current[i] || React.createRef());
  }, []);

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
    if (isTurning) return; // prevent double clicks
    setIsTurning(true);

    // Forward flip
    if (targetPage > currentPage) {
      for (let i = currentPage; i < targetPage; i++) {
        await new Promise((resolve) => {
          setTimeout(() => {
            pageRefs.current[i]?.flip();
            resolve();
          }, 800);
        });
      }
    }
    // Backward flip
    else {
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

  // On load intro animation is played — book opens and flips 2 pages + Cover
  useEffect(() => {
  if (!pages.length) return;

  const waitForRefs = async () => {
    const total = pages.length;
    for (let i = 0; i < total; i++) {
      // wait up to a reasonable amount; this loop polls until the ref exists
      let tries = 0;
      while (!pageRefs.current[i] && tries < 40) { // ~2s max (40 * 50ms)
        await new Promise((r) => setTimeout(r, 50));
        tries++;
      }
    }

    // Give the browser a frame to paint so initial z / layout are stable
    await new Promise((r) => requestAnimationFrame(r));
    await new Promise((r) => setTimeout(r, 300)); // small buffer

    // Now run the intro flips
    await flipToPage(3);
  };

  waitForRefs();
}, [pages.length]);

  return (
    <div className="book-frame">
      <div className="page-wrapper slideUp-animation">

        {pages.map((page, i) => (
          <FlipPage
            key={i}
            ref={(el) => (pageRefs.current[i] = el)} // store ref
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
