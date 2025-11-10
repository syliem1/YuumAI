import React, { useState } from "react";

const ChatInput = ({ onSendMessage, isLoading }) => {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    
    onSendMessage(input);
    setInput("");
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-8">
      <h2 className="section-title">Ask the Book</h2>
      
      <div className="bg-black bg-opacity-70 rounded-lg p-8 w-full max-w-2xl">
        <div className="mb-4">
          <p className="text-gray-300 text-sm mb-4">
            Ask questions about your gameplay, get strategic advice, or learn more about your matches.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
              className="w-full px-4 py-3 bg-gray-800 bg-opacity-70 border border-gray-700 rounded text-white focus:outline-none focus:border-gray-500 resize-none"
              placeholder="What would you like to know about your gameplay?"
              rows={6}
            />
          </div>

          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">
              {input.length > 0 && `${input.length} characters`}
            </span>
            
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="magical-button disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="button-text">
                {isLoading ? "Sending..." : "Enter"}
              </span>
              <div className="particles">
                <span className="particle"></span>
                <span className="particle"></span>
                <span className="particle"></span>
                <span className="particle"></span>
              </div>
            </button>
          </div>
        </form>

        {isLoading && (
          <div className="mt-4 flex items-center justify-center text-gray-400">
            <div className="animate-pulse">The Book is thinking...</div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatInput;