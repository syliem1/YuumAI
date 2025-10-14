"use client";

import { motion } from "framer-motion";

const colors = [
  { name: "Primary", hex: "#78BCB0" },
  { name: "Accent", hex: "#B99758" },
  { name: "Background", hex: "#F4EAEA" },
  { name: "Dark", hex: "#56374E" },
];

export default function ThemePreview() {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-8"
      style={{ backgroundColor: "#F4EAEA", color: "#56374E" }}
    >
      <h1 className="text-3xl font-bold mb-8">Theme Preview</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
        {colors.map((c, i) => (
          <motion.div
            key={i}
            className="flex flex-col items-center justify-center p-6 rounded-2xl shadow-lg cursor-pointer transition-transform"
            style={{ backgroundColor: c.hex }}
            whileHover={{
              scale: 1.15,
              rotate: 2,
              transition: { duration: 0.3, ease: "easeInOut" },
            }}
          >
            <div
              className="w-20 h-20 rounded-xl border border-black/20 mb-3"
              style={{ backgroundColor: c.hex }}
            />
            <p className="font-semibold text-white drop-shadow">{c.name}</p>
            <p className="text-sm opacity-80 text-white drop-shadow">{c.hex}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
