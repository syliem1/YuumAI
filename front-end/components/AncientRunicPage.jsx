import React from "react";

const AncientRunicPage = ({ 
  variant = "default", 
  centerText = "ᛋᚢᛗᛗᛟᚾᛖᚱ'ᛋ ᛏᛟᛗᛖ",
  runeColor = "#8b7355",
  runeCount = 9
}) => {
  // Different rune sets for variety
  const runeSymbols = {
    default: ["ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚲ", "ᚷ", "ᚹ", "ᚺ", "ᚾ", "ᛁ", "ᛃ"],
    power: ["ᛉ", "ᛊ", "ᛏ", "ᛒ", "ᛖ", "ᛗ", "ᛚ", "ᛜ", "ᛞ", "ᛟ"],
    mystical: ["◉", "◈", "◊", "✦", "✧", "✺", "✹", "❂", "✶", "✷"],
    elements: ["🜁", "🜂", "🜃", "🜄", "☿", "♀", "♂", "♃", "♄", "⚡"],
  };

  const runes = React.useMemo(() => {
    const runes = [];
    const usedRunes = (runeSymbols[variant] || runeSymbols.default).slice(0, runeCount);
    
    for (let i = 0; i < usedRunes.length; i++) {
      runes.push({
        symbol: usedRunes[i],
        x: `${15 + (Math.random() * 70)}%`,
        y: `${15 + (Math.random() * 70)}%`,
        rotation: Math.random() * 360,
        opacity: 0.3 + Math.random() * 0.4,
      });
    }
    return runes;
    }, [variant, runeCount]);

  // Different circle patterns based on variant
  const circlePatterns = {
    default: { circles: 3 },
    power: { circles: 5 },
    mystical: { circles: 4 },
    elements: { circles: 2 },
  };

  const pattern = circlePatterns[variant] || circlePatterns.default;

  return (
    <div className="relative w-full h-full overflow-hidden">
      <style jsx>{`
        .rune-symbol {
          position: absolute;
          font-size: 3rem;
          color: ${runeColor};
          font-family: serif;
          user-select: none;
          pointer-events: none;
          text-shadow: 0 0 10px rgba(139, 115, 85, 0.3);
        }

        .center-circle {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          border: 3px solid rgba(139, 115, 85, 0.3);
          border-radius: 50%;
        }

        .ancient-text {
          position: absolute;
          bottom: 10%;
          left: 50%;
          transform: translateX(-50%);
          text-align: center;
          font-family: Georgia, serif;
          font-style: italic;
          color: rgba(86, 55, 78, 0.6);
          font-size: 0.9rem;
          letter-spacing: 2px;
        }
      `}</style>

      {/* Central decorative circles */}
      {Array.from({ length: pattern.circles }).map((_, i) => (
        <div
          key={i}
          className="center-circle"
          style={{
            width: `${200 - i * 40}px`,
            height: `${200 - i * 40}px`,
            opacity: 0.5 - i * 0.1,
          }}
        />
      ))}

      {/* Static runes */}
      {runes.map((rune, index) => (
        <div
          key={index}
          className="rune-symbol"
          style={{
            left: rune.x,
            top: rune.y,
            transform: `rotate(${rune.rotation}deg)`,
            opacity: rune.opacity,
          }}
        >
          {rune.symbol}
        </div>
      ))}

      {/* Ancient text at bottom */}
      {centerText && (
        <div className="ancient-text">
          {centerText}
        </div>
      )}
    </div>
  );
};

export default AncientRunicPage;