"use client";
import { motion } from "framer-motion";

const colors = [
  { name: "Primary", hex: "#78BCB0", class: "bg-primary" },
  { name: "Accent", hex: "#B99758", class: "bg-accent" },
  { name: "Background", hex: "#F4EAEA", class: "bg-background" },
  { name: "Dark", hex: "#56374E", class: "bg-dark" },
];

export default function ThemePreview() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background text-dark p-8">
      <motion.h1
        className="text-3xl font-bold mb-6"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        🎨 Theme Preview
      </motion.h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
        {colors.map((c, i) => (
          <motion.div
            key={c.name}
            className={`rounded-2xl shadow-lg p-4 flex flex-col items-center justify-center text-center ${c.class}`}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * i }}
          >
            <div className="w-20 h-20 rounded-xl border border-dark/10 mb-3" />
            <p className="font-semibold">{c.name}</p>
            <p className="text-sm opacity-80">{c.hex}</p>
          </motion.div>
        ))}
      </div>

      <p className="mt-10 text-accent italic">
        Your palette in action ✨
      </p>
    </div>
  );
}
