import React, { useRef, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";

const TraitPopup = ({ targetRef, children }) => {
  const [position, setPosition] = useState({ top: 0, left: 0 });

  // Compute popup position relative to viewport
  useLayoutEffect(() => {
    if (targetRef?.current) {
      const rect = targetRef.current.getBoundingClientRect();
      setPosition({
        top: rect.bottom + 8, // 8px gap below the element
        left: rect.left + rect.width / 2,
      });
    }
  }, [targetRef]);

  return createPortal(
    <div
      className="trait-popup"
      style={{
        position: "fixed",
        top: `${position.top}px`,
        left: `${position.left}px`,
        transform: "translateX(-50%)",
        zIndex: 9999,
      }}
    >
      {children}
    </div>,
    document.body
  );
};

export default TraitPopup;