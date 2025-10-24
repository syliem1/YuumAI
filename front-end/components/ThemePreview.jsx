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
      className="flex min-h-screen flex-col items-center justify-center p-8"
      style={{ backgroundColor: "#F4EAEA", color: "#56374E" }}
    >
      <h1 className="mb-8 text-3xl font-bold">Theme Preview</h1>

      <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        {colors.map((c, i) => (
          <motion.div
            key={i}
            className="flex cursor-pointer flex-col items-center justify-center rounded-2xl p-6 shadow-lg transition-transform"
            style={{ backgroundColor: c.hex }}
            whileHover={{
              scale: 1.15,
              rotate: 2,
              transition: { duration: 0.3, ease: "easeInOut" },
            }}
          >
            <div
              className="mb-3 h-20 w-20 rounded-xl border border-black/20"
              style={{ backgroundColor: c.hex }}
            />
            <p className="font-semibold text-white drop-shadow">{c.name}</p>
            <p className="text-sm text-white opacity-80 drop-shadow">{c.hex}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
