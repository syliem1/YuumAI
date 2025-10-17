import { useEffect, useState } from 'react';

export default function BookPage() {
  const [bookFullscreen, setBookFullscreen] = useState(false);
  const [appFullscreen, setAppFullscreen] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [isTurning, setIsTurning] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setBookFullscreen(true);
      // wait for the book animation to finish before expanding the rest
      setTimeout(() => setAppFullscreen(true), 1000); // adjust timing
    }, 3500);

    return () => clearTimeout(timeout);
  }, []);

  const totalPages = 4;

  const turnPage = (direction) => {
    if (isTurning) return; // prevent double clicks
    setIsTurning(true);

    // play animation
    const book = document.querySelector('.book');
    book.classList.add('turning');

    setTimeout(() => {
      setCurrentPage((prev) => {
        const next =
          direction === 'next'
            ? Math.min(prev + 1, totalPages - 1)
            : Math.max(prev - 1, 0);
        return next;
      });
      book.classList.remove('turning');
      setIsTurning(false);
    }, 1000); // match animation time
  };

  return (
    <section
      className={`flex items-center justify-center h-screen transition-all duration-700 ${
        appFullscreen ? 'bg-gray-950' : 'bg-gray-900'
      }`}
    >
      <div className={`book transition-all duration-700 ${bookFullscreen ? 'fullscreen' : ''}`}>
        <span className="page turn"></span>
        <span className="page turn"></span>
        <span className="page turn"></span>
        <span className="page turn"></span>
        <span className="page turn"></span>
        <span className="page turn">
          <span className="flipped-page-content">Hey</span>
        </span>
        <span className="cover"></span>
        <span className="page">Page 5</span>
        <span className="page">Page 4</span>
        <span className="page">Page 3</span>
        <span className="page">Page 2</span>
        <span className="page">Chat</span>
        <span className="cover turn">Hello</span>
      </div>
      
        <div class="bookmark">
          <svg viewBox="0 0 300 100" preserveAspectRatio="none">
            <defs>
              <mask id="cutout">
               <polygon points="0,0 260,0 300,50 260,100 0,100" fill="white"/>
              <polygon points="10,10 255,10 290,50 255,90 10,90" fill="black"/>
              </mask>
            </defs>
            <polygon 
              points="0,0 260,0 300,50 260,100 0,100" 
              fill="#77425f" 
              stroke="#5a2f49" 
              stroke-width="1" />
            <polygon 
              points="5,5 255,5 296,50 254,95 5,95" 
              fill="none" 
              stroke="white" 
              stroke-width="2" 
              stroke-dasharray="8,6" />
            <text x="150" y="58" text-anchor="middle" fill="white" font-weight="bold" font-family="sans-serif">Bookmark</text>
          </svg>
        </div>

      {/* Other components that appear after fullscreen */}
      <div
        className={`absolute inset-0 flex items-center justify-center transition-opacity duration-700 ${
          appFullscreen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
      </div>
    </section>
  );
}
