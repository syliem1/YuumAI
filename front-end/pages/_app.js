import "@/styles/globals.css";
import "@/styles/SplitBackground.css";
import "@/styles/button.css";
import "@/styles/book.css";
import "@/styles/bookmark.css";
import "@/styles/classroom.css"

export default function App({ Component, pageProps }) {
  return (
    <>
      <main className="w-screen min-h-screen">
        <Component {...pageProps} />
      </main>
    </>
  );
}
