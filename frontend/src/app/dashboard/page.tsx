"use client";

import { useState, useEffect } from "react";
import TradingChart from "../components/TradingChart";
import AgentStatusMonitor from "../components/AgentStatusMonitor";
import { useMarketData } from "../hooks/useWebSocket";

export default function Dashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");
  const [systemStatus, setSystemStatus] = useState({
    api: "online",
    database: "online",
    redis: "online",
    websocket: "online",
  });

  const { price, volume, isConnected } = useMarketData(selectedSymbol);

  // System-Status laden
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch("http://localhost:8000/health");
        const data = await response.json();
        setSystemStatus({
          api: data.status === "healthy" ? "online" : "offline",
          database: data.services?.redis === "ok" ? "online" : "offline",
          redis: data.services?.redis === "ok" ? "online" : "offline",
          websocket: isConnected ? "online" : "offline",
        });
      } catch (error) {
        console.error("Failed to fetch system status:", error);
        setSystemStatus({
          api: "offline",
          database: "unknown",
          redis: "unknown",
          websocket: isConnected ? "online" : "offline",
        });
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Alle 30 Sekunden
    return () => clearInterval(interval);
  }, [isConnected]);

  return (
    <div className="min-h-screen bg-[#0f0f1a] text-white p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-gray-400 text-sm">Bruno Trading Bot - Echtzeit-Übersicht</p>
        </div>
        <div className="flex items-center gap-4">
          {/* Symbol Selector */}
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-[#1a1a2e] border border-[#2d2d44] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="BTCUSDT">BTC/USDT</option>
            <option value="ETHUSDT">ETH/USDT</option>
            <option value="SOLUSDT">SOL/USDT</option>
            <option value="ADAUSDT">ADA/USDT</option>
          </select>

          {/* System Status */}
          <div className="flex items-center gap-2 bg-[#1a1a2e] rounded-lg px-3 py-2">
            <div
              className={`w-2 h-2 rounded-full ${
                systemStatus.api === "online" ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="text-sm">{systemStatus.api === "online" ? "Online" : "Offline"}</span>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Chart - Takes 8 columns */}
        <div className="col-span-12 lg:col-span-8">
          <TradingChart symbol={selectedSymbol} />
        </div>

        {/* Side Panel - Takes 4 columns */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          {/* Live Price Widget */}
          <div className="bg-[#1a1a2e] rounded-lg p-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <h3 className="text-sm font-medium text-gray-400">Aktueller Preis</h3>
                <p className="text-2xl font-bold text-white">
                  {price ? `$${price.toLocaleString()}` : "Loading..."}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-400">24h Vol</p>
                <p className="text-sm font-medium text-white">
                  {volume ? `${(volume / 1000000).toFixed(2)}M` : "-"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-green-400 text-sm">+2.34%</span>
              <span className="text-gray-500 text-xs">+1,542.30 USD</span>
            </div>
          </div>

          {/* System Metrics */}
          <div className="bg-[#1a1a2e] rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-4">System-Status</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">API Backend</span>
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      systemStatus.api === "online" ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                  <span className="text-sm">{systemStatus.api === "online" ? "Online" : "Offline"}</span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">Datenbank</span>
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      systemStatus.database === "online" ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                  <span className="text-sm">
                    {systemStatus.database === "online" ? "Online" : "Offline"}
                  </span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">Redis</span>
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      systemStatus.redis === "online" ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                  <span className="text-sm">{systemStatus.redis === "online" ? "Online" : "Offline"}</span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">WebSocket</span>
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      isConnected ? "bg-green-500 animate-pulse" : "bg-red-500"
                    }`}
                  />
                  <span className="text-sm">{isConnected ? "Verbunden" : "Getrennt"}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Agent Status Monitor */}
          <AgentStatusMonitor />
        </div>
      </div>

      {/* Bottom Section - Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
        <div className="bg-[#1a1a2e] rounded-lg p-4">
          <p className="text-sm text-gray-400">24h High</p>
          <p className="text-lg font-semibold">$67,432.50</p>
        </div>
        <div className="bg-[#1a1a2e] rounded-lg p-4">
          <p className="text-sm text-gray-400">24h Low</p>
          <p className="text-lg font-semibold">$64,123.80</p>
        </div>
        <div className="bg-[#1a1a2e] rounded-lg p-4">
          <p className="text-sm text-gray-400">Marktkapitalisierung</p>
          <p className="text-lg font-semibold">$1.31T</p>
        </div>
        <div className="bg-[#1a1a2e] rounded-lg p-4">
          <p className="text-sm text-gray-400">24h Volumen</p>
          <p className="text-lg font-semibold">$28.4B</p>
        </div>
      </div>
    </div>
  );
}
