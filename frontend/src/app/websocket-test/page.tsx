"use client";

import { useState, useEffect } from "react";

export default function WebSocketTest() {
  const [wsStatus, setWsStatus] = useState("disconnected");
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    console.log("Starting WebSocket test...");
    
    try {
      const ws = new WebSocket("ws://localhost:8001/ws/agents");
      
      ws.onopen = () => {
        console.log("WebSocket opened successfully");
        setWsStatus("connected");
        setMessages(prev => [...prev, "WebSocket connected"]);
      };
      
      ws.onmessage = (event) => {
        console.log("WebSocket message received:", event.data);
        setMessages(prev => [...prev, `Received: ${event.data}`]);
      };
      
      ws.onerror = (event) => {
        console.error("WebSocket error:", event);
        setError(`WebSocket error: ${event}`);
        setWsStatus("error");
      };
      
      ws.onclose = (event) => {
        console.log("WebSocket closed:", event.code, event.reason);
        setWsStatus(`closed (${event.code})`);
        setMessages(prev => [...prev, `WebSocket closed: ${event.code} - ${event.reason}`]);
      };
      
      return () => {
        ws.close();
      };
    } catch (err) {
      console.error("Failed to create WebSocket:", err);
      setError(`Failed to create WebSocket: ${err}`);
    }
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-2xl font-bold mb-4">WebSocket Connection Test</h1>
      
      <div className="mb-4">
        <span className="text-sm">Status: </span>
        <span className={`font-bold ${
          wsStatus === "connected" ? "text-green-400" : 
          wsStatus === "error" ? "text-red-400" : 
          "text-gray-400"
        }`}>{wsStatus}</span>
      </div>
      
      {error && (
        <div className="mb-4 p-3 bg-red-900/50 border border-red-500 rounded">
          <p className="text-red-400">Error: {error}</p>
        </div>
      )}
      
      <div className="mb-4">
        <h2 className="text-lg font-semibold mb-2">Console Messages:</h2>
        <div className="bg-gray-800 rounded p-4 max-h-96 overflow-y-auto">
          {messages.length === 0 ? (
            <p className="text-gray-500">No messages yet...</p>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className="text-sm mb-2 font-mono">
                {new Date().toLocaleTimeString()}: {msg}
              </div>
            ))
          )}
        </div>
      </div>
      
      <div className="text-sm text-gray-400">
        <p>Open browser console (F12) to see detailed WebSocket logs</p>
        <p>Check if backend is running on localhost:8001</p>
      </div>
    </div>
  );
}
