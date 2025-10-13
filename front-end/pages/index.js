import React, { useState } from 'react';
import Link from "next/link";

export default function Home() {
  const [inputValue, setInputValue] = useState('');

  const handleChange = (event) => {
    setInputValue(event.target.value);
  };

  return (
    <section className="fixed top-0 left-0 w-full h-full flex items-center justify-center overflow-hidden m-0 p-0">
      {/* Top and bottom background layers */}
      <div className="background-top"></div>
      <div className="background-bot"></div>

      {/* Content */}
      <div className="z-10 bg-white/80 p-8 rounded-lg shadow-lg text-center">
        <h1 className="text-4xl text-dark font-bold mb-4">Welcome!</h1>
        <div className="mt-2 flex items-center space-x-2">
          <input
            type="text"
            value={inputValue}
            onChange={handleChange}
            placeholder="Enter text here"
            className="p-2 border rounded-lg text-dark flex-1"
          />
          <Link href="/book" className="text-background hover:underline">
            <button className="px-4 py-2 bg-[#8b6f4e] text-white rounded-lg hover:bg-[#73583f] transition">
              Search
            </button>
          </Link>
        </div>
        <p className="mt-2 text-dark">Current input: {inputValue}</p>
      </div>
    </section>
  );
}
