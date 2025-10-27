import React from "react";
import PropTypes from "prop-types";

const Bookmark = ({ label, targetPage, y, onClick, zIndex, color = "#77425f", stroke = "#5a2f49" }) => {
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
        top: y,
        zIndex: zIndex || 10,
        position: "absolute",
        cursor: "pointer",
      }}
    >
      <svg viewBox="0 0 300 100" preserveAspectRatio="none">
        {/* Main body */}
        <polygon
          points="0,0 260,0 300,50 260,100 0,100"
          fill={color}
          stroke={stroke}
          strokeWidth="1"
        />
        {/* Inner dashed border */}
        <polygon
          points="5,5 255,5 296,50 254,95 5,95"
          fill="none"
          stroke="white"
          strokeWidth="2"
          strokeDasharray="8,6"
        />
        {/* Text label */}
        <text
          x="150"
          y="58"
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
