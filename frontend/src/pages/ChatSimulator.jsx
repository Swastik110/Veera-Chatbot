import React, { useState, useEffect, useRef } from 'react';
import apiClient from '../api/client';
import { Send, User, Bot } from 'lucide-react';

const ChatSimulator = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId] = useState(`conv_${Math.floor(Math.random() * 10000)}`);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = {
      role: 'customer',
      content: input,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await apiClient.post('/v1/reply', {
        conversation_id: conversationId,
        merchant_id: 'm123', // Demo ID
        customer_id: 'c123', // Demo ID
        from_role: 'customer',
        message: input,
        received_at: new Date().toISOString(),
        turn_number: messages.length + 1
      });

      const aiMessage = {
        role: 'assistant',
        content: response.data.body || JSON.stringify(response.data),
        timestamp: new Date().toISOString(),
        rationale: response.data.rationale
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'system', content: 'Error communicating with server.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <h1 className="text-2xl font-semibold text-gray-900 mb-4">Veera Chat Simulator</h1>
      
      <div className="flex-1 bg-[#e5ddd5] rounded-t-lg shadow-inner overflow-y-auto p-4 flex flex-col space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'customer' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] rounded-lg p-3 ${
              msg.role === 'customer' ? 'bg-[#dcf8c6]' : msg.role === 'system' ? 'bg-red-100' : 'bg-white'
            } shadow`}>
              <div className="text-sm">{msg.content}</div>
              <div className="text-[10px] text-gray-500 mt-1 text-right flex justify-end items-center space-x-1">
                <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>
              {msg.rationale && (
                <div className="mt-2 text-xs text-gray-400 border-t pt-1 border-gray-200">
                  Rationale: {msg.rationale}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white rounded-lg p-3 shadow text-gray-500 text-sm">
              Typing...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSend} className="bg-gray-100 p-4 rounded-b-lg flex items-center shadow">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message..."
          className="flex-1 bg-white rounded-full px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="ml-4 bg-green-500 text-white rounded-full p-2 hover:bg-green-600 focus:outline-none disabled:opacity-50"
        >
          <Send size={20} />
        </button>
      </form>
    </div>
  );
};

export default ChatSimulator;
