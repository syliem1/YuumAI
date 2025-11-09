import React, { useState } from "react";
import Link from "next/link";

export default function Home() {
  const [inputValue, setInputValue] = useState("");

  const handleChange = (event) => {
    setInputValue(event.target.value);
  };

  return (
    <section className="fixed left-0 top-0 m-0 flex h-full w-full items-center justify-center overflow-hidden p-0">
      {/* Top and bottom background layers */}
      <div className="background-top"></div>
      <div className="background-bot"></div>

      {/* Content */}
      <div className="z-10 rounded-lg bg-white/80 p-8 text-center shadow-lg">
        <h1 className="mb-4 text-4xl font-bold text-dark">Welcome!</h1>
        <div className="mt-2 flex items-center space-x-2">
          <input
            type="text"
            value={inputValue}
            onChange={handleChange}
            placeholder="Enter text here"
            className="flex-1 rounded-lg border p-2 text-dark"
          />
          <Link href="/FlipBook" className="text-background hover:underline">
            <button className="rounded-lg bg-[#8b6f4e] px-4 py-2 text-white transition hover:bg-[#73583f]">
              Search
            </button>
          </Link>
        </div>
        <p className="mt-2 text-dark">Current input: {inputValue}</p>
      </div>
    </section>
  );
}
