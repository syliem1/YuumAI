import React from "react";
import FlipBook from "../components/FlipBook";

const BookPage = () => {
  return (
    <div style={{ height: "100vh", width: "100vw", backgroundImage: `url(/images/wood.jpg)`}}>
      <FlipBook />
    </div>
  );
};

export default BookPage;