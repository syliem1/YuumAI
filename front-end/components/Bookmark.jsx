import React from "react";
import PropTypes from "prop-types";

const Bookmark = ({ label, targetPage, x, onClick, zIndex, color = "#C56BC5", stroke = "#F8D77B" }) => {
  const handleClick = (e) => {
    if (onClick) {
      onClick(e, targetPage); // send target page up
    }
  };

  return (
    <div
      className="bookmark-container bookmark"
      onClick={handleClick}
      style={{
        left: x,
        zIndex: zIndex || 10,
        position: "absolute",
        cursor: "pointer",
      }}
    >
      <svg viewBox="0 0 120 200" preserveAspectRatio="none">
        <defs>
          {/* Vertical gradient */}
          <linearGradient id="bookmarkGrad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="10%" stopColor={color} stopOpacity=".1"/>
            <stop offset="100%" stopColor={stroke} stopOpacity="1"/>
          </linearGradient>
        </defs>

        {/* Main body */}
        <polygon
          points="0,40 0,200 50,160 100,200 100,40"
          fill={color}
          stroke={stroke}
          strokeWidth="1"
        />
        {/* Inner dashed border */}
        <polygon
          points="2,42 2,198 50,160 100,200 100,42"
          fill="none"
          stroke="#9f814a"
          
          strokeWidth="4"
        />
        
        {/* Text label */}
        <text
          x="50"
          y="78"
          textAnchor="middle"
          fill="white"
          fontWeight="bold"
          fontFamily="sans-serif"
        >
          {label}
        </text>
      </svg>
    </div>
  );
};

Bookmark.propTypes = {
  label: PropTypes.string.isRequired,
  targetPage: PropTypes.number.isRequired,
  y: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onClick: PropTypes.func,
  color: PropTypes.string,
  stroke: PropTypes.string,
  zIndex: PropTypes.number,
};

export default Bookmark;
