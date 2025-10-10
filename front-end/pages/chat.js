import ChatBox from "@/components/ChatBox";

export default function ChatPage() {
  return (
    <section className="flex flex-col items-center justify-center h-[80vh]">
      <h1 className="text-3xl font-semibold mb-6 text-blue-600">
        Chat with Our Bot 🤖
      </h1>
      <ChatBox />
    </section>
  );
}
