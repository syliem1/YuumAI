import "@/styles/globals.css";
import "@/styles/SplitBackground.css";
import "@/styles/button.css";
import "@/styles/book.css";
import "@/styles/bookmark.css";
import "@/styles/classroom.css";
import "@/styles/FlipBook.css";
import "@/styles/FlipPage.css";
import "@/styles/Summary.css";
import { SearchContextProvider } from "@/context/SearchContext";

export default function App({ Component, pageProps }) {
  return (
    <>
      <main className="min-h-screen w-screen">
        <SearchContextProvider>
          <Component {...pageProps} />
        </SearchContextProvider>
      </main>
    </>
  );
}
