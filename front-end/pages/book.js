import next from 'next';
import { useEffect, useState } from 'react';

export default function BookPage() {
  const [bookFullscreen, setBookFullscreen] = useState(false);
  const [appFullscreen, setAppFullscreen] = useState(false);
  const [currentPage, setCurrentPage] = useState(10);
  const [isTurning, setIsTurning] = useState(false);

  const bookmarks = [
    { y: '20%', label: 'Page 1', page: 10, opposite: 11 },
    { y: '40%', label: 'Page 2', page: 9, opposite: 12 },
    { y: '60%', label: 'Page 3', page: 8, opposite: 13 },
  ];

  useEffect(() => {
    const timeout = setTimeout(() => {
      setBookFullscreen(true);
      // wait for the book animation to finish before expanding the rest
      setTimeout(() => setAppFullscreen(true), 1000); // adjust timing
    }, 3500);

    return () => clearTimeout(timeout);
  }, []);

  const turnPage = (page, opposite) => {
    if (page === currentPage) return; // no need to turn to the same page
    if (isTurning) return; // prevent double clicks
    setIsTurning(true);

    const nextIndex = page;
    console.log('Next Page is :', nextIndex);
    if (nextIndex < currentPage){
      for (let i = currentPage; i > nextIndex; i--) {
        // Determine which page(s) to turn
        const turnPageEl = document.querySelector(`.page-${i}`);
        if (!turnPageEl) return;

        // Turn current page right to left
        const delay = (currentPage - i) * 300;
        setTimeout(() => {
          turnPageEl.classList.remove('back-turn', 'back-fade');
          turnPageEl.classList.add('turn', 'fade');
        }, delay);
      }
    }
    else {
      console.log('Backflipping to:', nextIndex);
      for (let i = currentPage+1; i <= nextIndex; i++) {
        // Determine which page(s) to turn
        const turnPageEl = document.querySelector(`.page-${i}`);
        if (!turnPageEl) return;
        // Turn current page left to right
        const delay = (i - currentPage) * 300;
        setTimeout(() => {
          turnPageEl.classList.remove('turn', 'fade');
          turnPageEl.classList.add('back-turn', 'back-fade');
        }, delay);
      }
    }

    for (let i = 11; i <= 13; i++) {
      const oppositePageEl = document.querySelector(`.page-${i}`);
      if (!oppositePageEl) return;

      if (i === opposite) {
        oppositePageEl.classList.remove('invisible');
        oppositePageEl.classList.add('visible');
        continue;
      }
      oppositePageEl.classList.remove('visible');
      oppositePageEl.classList.add('invisible');

    }

    // Wait for animation to complete
    setTimeout(() => {
      setCurrentPage(nextIndex);
      console.log('Current page is now:', currentPage);
      setIsTurning(false);
    }, 1000); // match your CSS animation duration
  };

  const handleBookmarkClick = (e, flip, opposite) => {
  const el = e.currentTarget;
  // Play click animation
  el.classList.add('clicked');
  setTimeout(() => el.classList.remove('clicked'), 400);
  // Trigger turnPage function
  turnPage(flip, opposite); // Testing turning to page 2
};

  return (
    <section
      className={`book-scene flex items-center justify-center h-screen transition-all duration-700 ${
        appFullscreen ? 'bg-gray-950' : 'bg-gray-900'
      }`}
    >
      <div className={`book transition-all duration-700 ${bookFullscreen ? 'fullscreen' : ''}`}>
        <span className="page turn page-1">:3</span>
        <span className="page turn page-2">:3:3:3</span>
        <span className="page turn page-3">:3:3:3:3
          :3:3:3:3:3:3:3
        </span>
        <span className="page turn page-4">:3:3:3:3:3:3:3
          :3:3:3:3:3:3:3
          :3:3:3:3:3:3:3
        </span>
        <span className="page turn page-5">:3</span>
        <span className="cover"></span>
        <span className="page page-6">Page 5</span>
        <span className="page page-7">Page 4</span>
        <span className="page page-8">Page 3
          {bookmarks
          .filter(b => b.page === 8)
          .map((b, i) => (
            <div
              key={i}
              onClick={(e) => handleBookmarkClick(e, b.page, b.opposite)}
              className={`bookmark-container bookmark ${
                bookFullscreen ? 'opacity-100' : 'opacity-0 pointer-events-none'
              }`}
              style={{
                top: b.y,
              }}
            >
              <svg viewBox="0 0 300 100" preserveAspectRatio="none">
                <polygon points="0,0 260,0 300,50 260,100 0,100" fill="#77425f" stroke="#5a2f49" strokeWidth="1" />
                <polygon points="5,5 255,5 296,50 254,95 5,95" fill="none" stroke="white" strokeWidth="2" strokeDasharray="8,6" />
                <text x="150" y="58" textAnchor="middle" fill="white" fontWeight="bold" fontFamily="sans-serif">
                  {b.label}
                </text>
              </svg>
            </div>
          ))}
        </span>
        <span className="page page-9">
          Page 2
          {bookmarks
          .filter(b => b.page === 9)
          .map((b, i) => (
            <div
              key={i}
              onClick={(e) => handleBookmarkClick(e, b.page, b.opposite)}
              className={`bookmark-container bookmark ${
                bookFullscreen ? 'opacity-100' : 'opacity-0 pointer-events-none'
              }`}
              style={{
                top: b.y,
              }}
            >
              <svg viewBox="0 0 300 100" preserveAspectRatio="none">
                <polygon points="0,0 260,0 300,50 260,100 0,100" fill="#77425f" stroke="#5a2f49" strokeWidth="1" />
                <polygon points="5,5 255,5 296,50 254,95 5,95" fill="none" stroke="white" strokeWidth="2" strokeDasharray="8,6" />
                <text x="150" y="58" textAnchor="middle" fill="white" fontWeight="bold" fontFamily="sans-serif">
                  {b.label}
                </text>
              </svg>
            </div>
          ))}
        </span>
        <span className="page page-10">
          <span className="page-text">
            Placeholder Text
          </span>
          {bookmarks
          .filter(b => b.page === 10)
          .map((b, i) => (
            <div
              key={i}
              onClick={(e) => handleBookmarkClick(e, b.page, b.opposite)}
              className={`bookmark-container bookmark ${
                bookFullscreen ? 'opacity-100' : 'opacity-0 pointer-events-none'
              }`}
              style={{
                top: b.y,
              }}
            >
              <svg viewBox="0 0 300 100" preserveAspectRatio="none">
                <polygon points="0,0 260,0 300,50 260,100 0,100" fill="#77425f" stroke="#5a2f49" strokeWidth="1" />
                <polygon points="5,5 255,5 296,50 254,95 5,95" fill="none" stroke="white" strokeWidth="2" strokeDasharray="8,6" />
                <text x="150" y="58" textAnchor="middle" fill="white" fontWeight="bold" fontFamily="sans-serif">
                  {b.label}
                </text>
              </svg>
            </div>
          ))}
        </span>
        <span className="page turn page-11">
          <span className="flipped-page-content">Placeholder Text</span>
        </span>
        <span className="page turn page-12 invisible">
          <span className="flipped-page-content">Pogg</span>
        </span>
        <span className="page turn page-13 invisible">
          <span className="flipped-page-content">Whoas</span>
        </span>
        
        <span className="cover turn">Hello</span>
      </div>
      
    </section>
  );
}
