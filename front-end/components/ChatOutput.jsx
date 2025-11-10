import React, { useRef, useEffect } from "react";

const ChatOutput = ({ messages }) => {
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div className="flex flex-col h-full p-8">
      <h2 className="section-title">Book&apos;s Wisdom</h2>
      
      <div className="flex-1 bg-black bg-opacity-70 rounded-lg p-6 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto space-y-4 pr-2">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-400 text-center">
                No messages yet. Ask a question to get started.
              </p>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${
                    msg.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-4 ${
                      msg.sender === "user"
                        ? "bg-blue-600 bg-opacity-60 text-white"
                        : "bg-gray-800 bg-opacity-60 text-gray-100"
                    }`}
                  >
                    {msg.sender === "bot" && (
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-yellow-400 text-xl">🔮</span>
                        <span className="text-sm font-semibold text-yellow-400">
                          Book
                        </span>
                      </div>
                    )}
                    <p className="whitespace-pre-wrap break-words">{msg.text}</p>
                    <span className="text-xs text-gray-400 mt-2 block">
                      {msg.timestamp}
                    </span>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatOutput;