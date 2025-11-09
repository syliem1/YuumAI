import React from "react";
import PropTypes from "prop-types";

const BackBookmark = ({ label, targetPage, x, onClick, zIndex, color = "#77425f", stroke = "#5a2f49" }) => {
  const handleClick = (e) => {
    if (onClick) {
      onClick(e, targetPage); // send target page up
    }
  };

  return (
    <div
      className="bookmark-container back-bookmark"
      onClick={handleClick}
      style={{
        right: x,
        zIndex: zIndex || 10,
        position: "absolute",
        cursor: "pointer",
      }}
    >
      <svg viewBox="0 0 120 200" preserveAspectRatio="none">
        <defs>
          {/* Vertical gradient */}
          <linearGradient id="bookmarkGrad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="10%" stopColor={color}/>
            <stop offset="100%" stopColor={color} stopOpacity=".7"/>
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
          points="2,42 2,198 52,158 102,198 102,42"
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

BackBookmark.propTypes = {
  label: PropTypes.string.isRequired,
  targetPage: PropTypes.number.isRequired,
  y: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onClick: PropTypes.func,
  color: PropTypes.string,
  stroke: PropTypes.string,
  zIndex: PropTypes.number,
};

export default BackBookmark;