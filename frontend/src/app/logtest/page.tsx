"use client";

import { useState, useEffect } from "react";

export default function LogTest() {
  const [logs, setLogs] = useState<any[]>([]);
  const [wsStatus, setWsStatus] = useState<string>("disconnected");

  useEffect(() => {
    console.log("Starting log test...");
    
    const ws = new WebSocket("ws://localhost:8001/api/v1/logs/ws");
    
    ws.onopen = () => {
      console.log("WebSocket connected");
      setWsStatus("connected");
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("Received:", data);
        
        if (data.type === "history") {
          console.log("Setting history:", data.logs);
          setLogs(data.logs);
        } else if (data.type === "new_log") {
          console.log("Adding new log:", data.log);
          setLogs(prev => [data.log, ...prev]);
        }
      } catch (error) {
        console.error("Error parsing message:", error);
      }
    };
    
    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      setWsStatus("error");
    };
    
    ws.onclose = () => {
      console.log("WebSocket closed");
      setWsStatus("disconnected");
    };
    
    return () => {
      ws.close();
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-2xl font-bold mb-4">Log Test Page</h1>
      
      <div className="mb-4">
        <span className="text-sm">WebSocket Status: </span>
        <span className={`font-bold ${wsStatus === 'connected' ? 'text-green-400' : wsStatus === 'error' ? 'text-red-400' : 'text-gray-400'}`}>
          {wsStatus}
        </span>
      </div>
      
      <div className="mb-4">
        <h2 className="text-lg font-semibold mb-2">Logs ({logs.length})</h2>
        <div className="bg-gray-800 rounded-lg p-4 max-h-96 overflow-y-auto">
          {logs.length === 0 ? (
            <p className="text-gray-400">No logs received yet...</p>
          ) : (
            logs.map((log, index) => (
              <div key={index} className="mb-2 p-2 bg-gray-700 rounded text-sm">
                <span className="text-gray-400">{new Date(log.timestamp).toLocaleTimeString()}</span>
                <span className={`ml-2 font-bold ${
                  log.level === 'INFO' ? 'text-blue-400' : 
                  log.level === 'WARNING' ? 'text-yellow-400' : 
                  log.level === 'ERROR' ? 'text-red-400' : 'text-gray-400'
                }`}>{log.level}</span>
                <span className="ml-2 text-purple-400">[{log.category}]</span>
                <span className="ml-2 text-green-400">{log.source}:</span>
                <span className="ml-2">{log.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
