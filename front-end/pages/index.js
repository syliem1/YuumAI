import React, { useState } from "react";
import Link from "next/link";

export default function Home() {
  const [inputValue, setInputValue] = useState("");

  const handleChange = (event) => {
    setInputValue(event.target.value);
  };

  return (
    <section className="fixed left-0 top-0 m-0 flex h-full w-full items-center justify-center overflow-hidden p-0">
      {/* Background */}
      <div className="background_full"></div>

      {/* Content */}
      <div className="detention_card">
        <div className="riotID_box">
          Hello
        </div>
          {/* <Link href="/FlipBook" className="text-background hover:underline">
            <button className="rounded-lg bg-[#8b6f4e] px-4 py-2 text-white transition hover:bg-[#73583f]">
              Search
            </button>
          </Link> */}
      </div>
    </section>
  );
}
