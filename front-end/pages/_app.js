import "@/styles/globals.css";
import "@/styles/SplitBackground.css";
import "@/styles/button.css";
import "@/styles/book.css";
import "@/styles/bookmark.css";
import "@/styles/classroom.css";
import "@/styles/FlipBook.css";
import "@/styles/FlipPage.css";
import "@/styles/Summary.css";
import { TimelineContextProvider } from "@/context/TimelineContext";
import { FriendContextProvider } from "@/context/FriendContext";
import "@/styles/detentionslip.css";
import "@/styles/index.css";

export default function App({ Component, pageProps }) {
  return (
    <>
      <main className="min-h-screen w-screen">
        <FriendContextProvider>
            <TimelineContextProvider>
              <Component {...pageProps} />
            </TimelineContextProvider>
        </FriendContextProvider>
        
      </main>
    </>
  );
}