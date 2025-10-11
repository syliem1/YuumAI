import { useState } from "react";

export default function ChatBox() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { sender: "user", text: input };
    setMessages([...messages, userMessage]);

    // Example: send to backend/chatbot API
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: input }),
    });

    const data = await response.json();
    const botMessage = { sender: "bot", text: data.reply };
    setMessages((prev) => [...prev, botMessage]);
    setInput("");
  };

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="border rounded-lg p-4 h-96 overflow-y-auto bg-white shadow">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`my-2 ${
              msg.sender === "user" ? "text-right text-blue-600" : "text-left text-gray-700"
            }`}
          >
            <span>{msg.text}</span>
          </div>
        ))}
      </div>

      <form onSubmit={sendMessage} className="mt-4 flex">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-grow border rounded-l-lg px-3 py-2 focus:outline-none"
          placeholder="Type your message..."
        />
        <button
          type="submit"
          className="bg-blue-600 text-white px-4 py-2 rounded-r-lg hover:bg-blue-700"
        >
          Send
        </button>
      </form>
    </div>
  );
}
