import React from "react";
import PropTypes from "prop-types";

const BackBookmark = ({ label, targetPage, y, onClick, zIndex, color = "#77425f", stroke = "#5a2f49" }) => {
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
        top: y,
        zIndex: zIndex || 10,
        position: "absolute",
        right: "auto",
      }}
    >
      <svg viewBox="0 0 300 100" preserveAspectRatio="none">
        <polygon
          points="300,0 40,0 0,50 40,100 300,100"
          fill={color}
          stroke={stroke}
          strokeWidth="1"
        />
        <polygon
          points="295,5 45,5 4,50 46,95 295,95"
          fill="none"
          stroke= "white"
          strokeWidth="2"
          strokeDasharray="8,6"
        />
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
