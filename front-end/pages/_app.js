import "@/styles/globals.css";
import "@/styles/SplitBackground.css";
import "@/styles/button.css";
import "@/styles/book.css";

export default function App({ Component, pageProps }) {
  return (
    <>
      <main className="p-8">
        <Component {...pageProps} />
      </main>
    </>
  );
}
