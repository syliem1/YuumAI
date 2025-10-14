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
