import React, { useEffect, useState, useImperativeHandle, forwardRef } from "react";
import Bookmark from "./Bookmark";
import BackBookmark from "./BackBookmark.jsx";

const FlipPage = forwardRef(
  (
    {
      Front,
      Back,
      Cover,
      FrontCover = false,
      onFlip,
      flipped = false,
      zIndex,
      onFirstPage,
      onLastPage,
      bookmark,
      onBookmarkClick,
    },
    ref
  ) => {
    const [isFlipped, setIsFlipped] = useState(false);
    const [flipSounds, setFlipSounds] = useState([]);

    useEffect(() => {
      setIsFlipped(flipped);
    }, [flipped]);

    useEffect(() => {
      const sounds = [];
      for (let i = 1; i <= 12; i++) {
        sounds.push(`/audio/flip-(${i}).wav`);
      }
      setFlipSounds(sounds);
    }, []);

    const pageFlip = () => {
      const newFlipState = !isFlipped;
      setIsFlipped(newFlipState);
      onFlip(newFlipState);

      if (!Cover) {
        const random = Math.floor(Math.random() * flipSounds.length);
        const flipSound = new Audio(flipSounds[random]);
        flipSound.play().catch((e) => console.error("Audio play failed", e));
      } else {
        let sound;
        if (FrontCover) {
          sound = newFlipState
            ? new Audio("/audio/cover-open.wav")
            : new Audio("/audio/cover-close.wav");
        } else {
          sound = newFlipState
            ? new Audio("/audio/cover-close.wav")
            : new Audio("/audio/cover-open.wav");
        }
        sound.play().catch((e) => console.error("Audio play failed", e));
      }
    };

    useImperativeHandle(ref, () => ({
      flip: pageFlip,
    }));

    const coverStyle = Cover
      ? { backgroundImage: `url(/images/${Cover})` }
      : undefined;

    return (
      <div
        className={`flip-page
          ${isFlipped ? "flipped" : ""}
          ${Cover ? "cover-page" : ""}
          ${FrontCover ? "front" : ""}
          ${onFirstPage ? "first-page" : ""}
          ${onLastPage ? "last-page" : ""}
        `}
        style={{ zIndex }}
      >
        {Cover ? (
          <>
            <div className="back-page" style={coverStyle}></div>
            <div className="front-page" style={coverStyle}></div>
          </>
        ) : (
          <>
            <div className="back-page">
              <div className="paper">
                <p>{Back || "Back content"}</p>
                {bookmark && (
                  <BackBookmark
                    label={bookmark.label}
                    targetPage={bookmark.targetPage}
                    y={bookmark.y}
                    onClick={onBookmarkClick}
                    zIndex={zIndex - 100}
                    color={bookmark.color}
                    stroke={bookmark.stroke}
                  />
                )}
              </div>
            </div>
            <div className="front-page">
              <div className="paper">
                <p>{Front || "Front content"}</p>
                {bookmark && (
                  <Bookmark
                    label={bookmark.label}
                    targetPage={bookmark.targetPage}
                    y={bookmark.y}
                    onClick={onBookmarkClick}
                    zIndex={zIndex + 1}
                    color={bookmark.color}
                    stroke={bookmark.stroke}
                  />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    );
  }
);

export default FlipPage;
