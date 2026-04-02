"use client";

import { useState, useEffect, useRef } from "react";
import Sidebar from "../components/Sidebar";
import { Play, Pause, Square, MessageSquare, Activity, AlertTriangle, CheckCircle, Clock, Send, Bot, Brain, Shield, TrendingUp } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL + "/api/v1" || "http://localhost:8000/api/v1";

// Agent-Typen
interface AgentStatus {
  id: string;
  name: string;
  status: "running" | "stopped" | "error" | "idle";
  last_heartbeat: string;
  healthy: boolean;
  age_seconds: number;
  description: string;
  icon: React.ReactNode;
  capabilities: string[];
  metrics?: Record<string, any>;
}

interface ChatMessage {
  id: string;
  agent_id: string;
  type: "user" | "agent";
  message: string;
  timestamp: string;
}

export default function AgentenPage() {
  // Agent Management
  const [agents, setAgents] = useState<Record<string, AgentStatus>>({});
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Detailed agent data (from original page)
  const [telemetry, setTelemetry] = useState<any>(null);
  const [grss, setGrss] = useState<any>(null);
  const [cascade, setCascade] = useState<any>(null);
  const [decisions, setDecisions] = useState<any>(null);
  const [vetoHistory, setVetoHistory] = useState<any[]>([]);

  // Chat functionality
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatAgent, setChatAgent] = useState<string>("sentiment");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // WebSocket connections
  const [wsConnected, setWsConnected] = useState(false);

  // Agent definitions
  const agentDefinitions = {
    sentiment: {
      id: "sentiment",
      name: "Sentiment Agent",
      description: "Analysiert Marktpsychologie und News-Sentiment",
      icon: <Brain className="w-5 h-5" />,
      capabilities: ["News-Analyse", "Sentiment-Scoring", "Social Media Monitoring"]
    },
    market: {
      id: "market",
      name: "Market Data Agent", 
      description: "Sammelt und verarbeitet Marktdaten in Echtzeit",
      icon: <TrendingUp className="w-5 h-5" />,
      capabilities: ["Price Feeds", "Technical Analysis", "Volume Analysis"]
    },
    quant: {
      id: "quant",
      name: "Quant Agent",
      description: "Führt quantitative Analysen und Berechnungen durch",
      icon: <Activity className="w-5 h-5" />,
      capabilities: ["OFI Analyse", "Quantitative Modelle", "Risk Metrics"]
    },
    risk: {
      id: "risk",
      name: "Risk Agent",
      description: "Überwacht und managed Handelsrisiken",
      icon: <Shield className="w-5 h-5" />,
      capabilities: ["Risk Assessment", "Position Monitoring", "Veto Power"]
    },
    execution: {
      id: "execution",
      name: "Execution Agent",
      description: "Führt Handelsorders aus und managed Positionen",
      icon: <Bot className="w-5 h-5" />,
      capabilities: ["Order Execution", "Position Management", "Trade Monitoring"]
    }
  };

  // Load agent status and detailed data
  const loadAgentStatus = async () => {
    try {
      const [statusResponse, telemetryResponse, grssResponse, cascadeResponse, decisionsResponse, vetoResponse] = await Promise.allSettled([
        fetch(`${API}/agents/status`),
        fetch(`${API}/telemetry/live`),
        fetch(`${API}/market/grss-full`),
        fetch(`${API}/llm-cascade/status`),
        fetch(`${API}/decisions/feed?limit=50`),
        fetch(`${API}/decisions/veto-history`)
      ]);

      if (statusResponse.status === "fulfilled") {
        const data = await statusResponse.value.json();
        setAgents(data.agents || {});
      }
      
      if (telemetryResponse.status === "fulfilled") {
        setTelemetry(await telemetryResponse.value.json());
      }
      
      if (grssResponse.status === "fulfilled") {
        setGrss(await grssResponse.value.json());
      }
      
      if (cascadeResponse.status === "fulfilled") {
        setCascade(await cascadeResponse.value.json());
      }
      
      if (decisionsResponse.status === "fulfilled") {
        setDecisions(await decisionsResponse.value.json());
      }
      
      if (vetoResponse.status === "fulfilled") {
        setVetoHistory((await vetoResponse.value.json()).events ?? []);
      }
    } catch (error) {
      console.error("Failed to load agent data:", error);
    } finally {
      setLoading(false);
    }
  };

  // Control individual agent
  const controlAgent = async (agentId: string, action: "start" | "stop" | "restart") => {
    try {
      const response = await fetch(`${API}/agents/${action}/${agentId}`, {
        method: "POST"
      });
      if (response.ok) {
        await loadAgentStatus();
      }
    } catch (error) {
      console.error(`Failed to ${action} agent ${agentId}:`, error);
    }
  };

  // Control all agents
  const controlAllAgents = async (action: "start" | "stop") => {
    try {
      const response = await fetch(`${API}/agents/${action}-all`, {
        method: "POST"
      });
      if (response.ok) {
        await loadAgentStatus();
      }
    } catch (error) {
      console.error(`Failed to ${action} all agents:`, error);
    }
  };

  // Send chat message
  const sendChatMessage = async () => {
    if (!chatInput.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      agent_id: chatAgent,
      type: "user",
      message: chatInput,
      timestamp: new Date().toISOString()
    };

    setChatMessages(prev => [...prev, userMessage]);
    setChatInput("");

    // Simulate agent response
    setTimeout(() => {
      const agentMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        agent_id: chatAgent,
        type: "agent",
        message: `Ich bin der ${agentDefinitions[chatAgent as keyof typeof agentDefinitions]?.name}. Deine Nachricht "${userMessage.message}" wurde erhalten. Ich arbeite gerade an einer Antwort...`,
        timestamp: new Date().toISOString()
      };
      setChatMessages(prev => [...prev, agentMessage]);
    }, 1000);
  };

  // WebSocket for real-time updates
  useEffect(() => {
    console.log("Attempting to connect to Agent WebSocket...");
    
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const wsUrl = `ws://${apiUrl.replace(/^https?:\/\//, "").replace(/^http:\/\//, "")}/ws/agents`;
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      setWsConnected(true);
      console.log("Agent WebSocket connected successfully");
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("WebSocket received:", data);
        if (data.type === "agents_status" && data.data?.agents) {
          console.log("Updating agents with:", data.data.agents);
          setAgents(data.data.agents);
        }
      } catch (error) {
        console.error("WebSocket message error:", error);
      }
    };
    
    ws.onerror = (error) => {
      console.error("Agent WebSocket error:", error);
      setWsConnected(false);
    };
    
    ws.onclose = (event) => {
      console.log("Agent WebSocket closed:", event.code, event.reason);
      setWsConnected(false);
    };
    
    return () => {
      console.log("Cleaning up WebSocket connection");
      ws.close();
    };
  }, []);

  // Initial load and periodic updates
  useEffect(() => {
    loadAgentStatus();
    const interval = setInterval(loadAgentStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case "running": return "text-green-400";
      case "stopped": return "text-gray-400";
      case "error": return "text-red-400";
      case "idle": return "text-yellow-400";
      default: return "text-gray-400";
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "running": return <CheckCircle className="w-4 h-4" />;
      case "stopped": return <Square className="w-4 h-4" />;
      case "error": return <AlertTriangle className="w-4 h-4" />;
      case "idle": return <Clock className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  // Get agent status from API data as fallback
  const getAgentStatus = (agentId: string) => {
    // First try WebSocket data
    if (agents[agentId]) {
      return agents[agentId];
    }
    
    // Fallback to API data
    const apiAgents = telemetry?.agents || {};
    if (apiAgents[agentId]) {
      return {
        id: agentId,
        name: agentDefinitions[agentId as keyof typeof agentDefinitions]?.name || agentId,
        status: apiAgents[agentId].healthy ? "running" : "stopped",
        last_heartbeat: new Date().toISOString(),
        healthy: apiAgents[agentId].healthy,
        age_seconds: 0
      };
    }
    
    // Default fallback
    return {
      id: agentId,
      name: agentDefinitions[agentId as keyof typeof agentDefinitions]?.name || agentId,
      status: "stopped",
      last_heartbeat: new Date().toISOString(),
      healthy: false,
      age_seconds: 0
    };
  };

  const formatTimeAgo = (timestamp: string) => {
    const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
  };

  return (
    <div className="flex min-h-screen bg-[#0a0a0f] text-white">
      <Sidebar />
      
      <div className="flex-1 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">Agent Control Center</h1>
            <p className="text-gray-400">Manage and monitor all Bruno trading agents</p>
          </div>
          
          <div className="flex items-center gap-4">
            {/* Global Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => controlAllAgents("start")}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg flex items-center gap-2 transition-colors"
              >
                <Play className="w-4 h-4" />
                Start All
              </button>
              <button
                onClick={() => controlAllAgents("stop")}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg flex items-center gap-2 transition-colors"
              >
                <Square className="w-4 h-4" />
                Stop All
              </button>
            </div>
            
            {/* Connection Status */}
            <div className="flex items-center gap-2 px-3 py-2 bg-gray-800 rounded-lg">
              <div className={`w-2 h-2 rounded-full ${wsConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
              <span className="text-sm">{wsConnected ? "Connected" : "Disconnected"}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Agent Cards */}
          <div className="lg:col-span-2 space-y-4">
            {Object.entries(agentDefinitions).map(([agentId, agentDef]) => {
              const agent = getAgentStatus(agentId);
              const isRunning = agent.status === "running";
              
              return (
                <div key={agentId} className="bg-gray-800 border border-gray-700 rounded-xl p-6">
                  {/* Agent Header */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${isRunning ? "bg-green-900/30" : "bg-gray-700"}`}>
                        {agentDef.icon}
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-white">{agentDef.name}</h3>
                        <p className="text-sm text-gray-400">{agentDef.description}</p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      {/* Status */}
                      <div className="flex items-center gap-2">
                        {getStatusIcon(agent.status)}
                        <span className={`text-sm font-medium ${getStatusColor(agent.status)}`}>
                          {agent.status}
                        </span>
                      </div>
                      
                      {/* Controls */}
                      <div className="flex items-center gap-1">
                        {isRunning ? (
                          <>
                            <button
                              onClick={() => controlAgent(agentId, "stop")}
                              className="p-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg transition-colors"
                              title="Pause"
                            >
                              <Pause className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => controlAgent(agentId, "restart")}
                              className="p-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                              title="Restart"
                            >
                              <Activity className="w-4 h-4" />
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => controlAgent(agentId, "start")}
                            className="p-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                            title="Start"
                          >
                            <Play className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => controlAgent(agentId, "stop")}
                          className="p-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
                          title="Stop"
                        >
                          <Square className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Agent Details */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Capabilities */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-400 mb-2">Capabilities</h4>
                      <div className="flex flex-wrap gap-2">
                        {agentDef.capabilities.map((cap, idx) => (
                          <span key={idx} className="px-2 py-1 bg-gray-700 rounded text-xs">
                            {cap}
                          </span>
                        ))}
                      </div>
                    </div>
                    
                    {/* Status Details */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-400 mb-2">Status Details</h4>
                      {agent ? (
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-500">Health:</span>
                            <span className={agent.healthy ? "text-green-400" : "text-red-400"}>
                              {agent.healthy ? "Healthy" : "Unhealthy"}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-500">Last Update:</span>
                            <span className="text-gray-300">{formatTimeAgo(agent.last_heartbeat)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-500">Age:</span>
                            <span className="text-gray-300">{agent.age_seconds}s</span>
                          </div>
                        </div>
                      ) : (
                        <div className="text-sm text-gray-500">No status data available</div>
                      )}
                    </div>
                  </div>

                  {/* Chat Button */}
                  <div className="mt-4 pt-4 border-t border-gray-700">
                    <button
                      onClick={() => {
                        setSelectedAgent(agentId);
                        setChatAgent(agentId);
                      }}
                      className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg flex items-center justify-center gap-2 transition-colors"
                    >
                      <MessageSquare className="w-4 h-4" />
                      Chat with {agentDef.name}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Chat Panel */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 flex flex-col h-[600px]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Agent Chat</h3>
              {selectedAgent && (
                <button
                  onClick={() => setSelectedAgent(null)}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  ×
                </button>
              )}
            </div>

            {selectedAgent ? (
              <>
                {/* Agent Selector */}
                <div className="mb-4">
                  <select
                    value={chatAgent}
                    onChange={(e) => setChatAgent(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:outline-none"
                  >
                    {Object.entries(agentDefinitions).map(([id, def]) => (
                      <option key={id} value={id}>{def.name}</option>
                    ))}
                  </select>
                </div>

                {/* Chat Messages */}
                <div className="flex-1 overflow-y-auto mb-4 space-y-3">
                  {chatMessages
                    .filter(msg => msg.agent_id === chatAgent)
                    .map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex ${msg.type === "user" ? "justify-end" : "justify-start"}`}
                      >
                        <div
                          className={`max-w-[80%] px-3 py-2 rounded-lg ${
                            msg.type === "user"
                              ? "bg-blue-600 text-white"
                              : "bg-gray-700 text-gray-200"
                          }`}
                        >
                          <p className="text-sm">{msg.message}</p>
                          <p className="text-xs opacity-70 mt-1">
                            {new Date(msg.timestamp).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  <div ref={chatEndRef} />
                </div>

                {/* Chat Input */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyPress={(e) => e.key === "Enter" && sendChatMessage()}
                    placeholder={`Message ${agentDefinitions[chatAgent as keyof typeof agentDefinitions]?.name}...`}
                    className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
                  />
                  <button
                    onClick={sendChatMessage}
                    disabled={!chatInput.trim()}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>Select an agent to start chatting</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Original Detailed Agent Information */}
        <div className="mt-8 space-y-4">
          <h2 className="text-xl font-bold text-white mb-4">Detailed Agent Analytics</h2>
          
          {/* Context Agent Details */}
          {grss && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Context Agent - Detailed Analysis</h3>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${getAgentStatus("sentiment").healthy ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
                  <span className="text-sm text-gray-400">
                    Last Update: {grss?.data_quality?.last_update ? new Date(grss.data_quality.last_update).toLocaleTimeString() : "Never"}
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-4">
                <div>
                  <span className="text-gray-500 text-xs">NDX</span>
                  <div className={`font-bold ${grss?.macro?.ndx_status === "BULLISH" ? "text-green-400" : "text-red-400"}`}>
                    {grss?.macro?.ndx_status || "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">VIX</span>
                  <div className={`font-bold ${(grss?.macro?.vix ?? 20) > 25 ? "text-red-400" : "text-zinc-200"}`}>
                    {grss?.macro?.vix?.toFixed(1) || "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">10Y Yield</span>
                  <div className="font-bold text-zinc-200">
                    {grss?.macro?.yields_10y?.toFixed(2) + "%" || "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">Funding</span>
                  <div className="font-bold text-zinc-200">
                    {grss?.derivatives?.funding_rate !== null
                      ? (grss.derivatives.funding_rate * 100).toFixed(4) + "%"
                      : "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">PCR</span>
                  <div className={`font-bold ${(grss?.derivatives?.put_call_ratio ?? 1) < 0.5 ? "text-green-400" : "text-zinc-200"}`}>
                    {grss?.derivatives?.put_call_ratio?.toFixed(2) || "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">DVOL</span>
                  <div className="font-bold text-zinc-200">
                    {grss?.derivatives?.dvol?.toFixed(0) || "—"}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <span className="text-gray-500 text-xs">OI-Delta</span>
                  <div className="font-bold text-zinc-200">
                    {grss?.derivatives?.oi_delta_pct !== null
                      ? (grss.derivatives.oi_delta_pct > 0 ? "+" : "") + grss.derivatives.oi_delta_pct.toFixed(1) + "%"
                      : "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">F&G Index</span>
                  <div className="font-bold text-zinc-200">
                    {grss?.sentiment?.fear_greed || "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">M2 YoY</span>
                  <div className="font-bold text-zinc-200">
                    {grss?.macro?.m2_yoy_pct !== null
                      ? (grss.macro.m2_yoy_pct > 0 ? "+" : "") + grss.macro.m2_yoy_pct?.toFixed(1) + "%"
                      : "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">USDT Δ7d</span>
                  <div className="font-bold text-zinc-200">
                    {grss?.sentiment?.stablecoin_delta_bn !== null
                      ? (grss.sentiment.stablecoin_delta_bn > 0 ? "+" : "") + grss.sentiment.stablecoin_delta_bn?.toFixed(1) + "B"
                      : "—"}
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-700 pt-4">
                <div className={`text-lg font-bold ${
                  (grss?.score ?? 0) >= 48 ? "text-green-400" :
                  (grss?.score ?? 0) >= 35 ? "text-yellow-400" : "text-red-400"
                }`}>
                  → GRSS {grss?.score?.toFixed(1) ?? "—"} (EMA) | Raw {grss?.score_raw?.toFixed(1) ?? "—"}
                  {grss?.velocity_30min !== null
                    ? ` | Velocity ${grss.velocity_30min > 0 ? "▲" : "▼"} ${grss.velocity_30min?.toFixed(1)} letzte 30min`
                    : ""}
                </div>
                {grss?.veto_active && (
                  <div className="text-red-400 mt-2">→ Veto aktiv: {grss.reason}</div>
                )}
                {grss?.data_quality?.funding_settlement_window && (
                  <div className="text-yellow-400 mt-2">⚠ Funding-Settlement-Fenster aktiv</div>
                )}
              </div>
            </div>
          )}

          {/* Quant Agent Details */}
          {telemetry?.market && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Quant Agent - Market Analysis</h3>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${getAgentStatus("quant").healthy ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
                  <span className="text-sm text-gray-400">Real-time Data</span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
                <div>
                  <span className="text-gray-500 text-xs">OFI</span>
                  <div className={`font-bold ${Math.abs(telemetry.market.ofi ?? 0) >= 500 ? "text-white" : "text-zinc-500"}`}>
                    {telemetry.market.ofi !== null ? (telemetry.market.ofi > 0 ? "+" : "") + telemetry.market.ofi?.toFixed(0) : "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">Threshold</span>
                  <div className="font-bold text-zinc-500">500</div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">CVD</span>
                  <div className={`font-bold ${(telemetry.market.cvd ?? 0) > 0 ? "text-green-400" : "text-red-400"}`}>
                    {telemetry.market.cvd !== null ? (telemetry.market.cvd > 0 ? "+" : "") + telemetry.market.cvd?.toFixed(0) : "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">VAMP</span>
                  <div className="font-bold text-zinc-200">
                    {telemetry.market.vamp?.toLocaleString() || "—"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">BTC Price</span>
                  <div className="font-bold text-zinc-200">
                    {"$" + telemetry.market.btc_price?.toLocaleString() || "—"}
                  </div>
                </div>
              </div>

              {telemetry.market.ofi !== null && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-gray-500 text-xs">OFI Progress</span>
                    <span className="text-xs text-gray-400">Threshold: 500</span>
                  </div>
                  <div className="w-full h-3 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.min(100, Math.abs(telemetry.market.ofi) / 10)}%`,
                        backgroundColor: telemetry.market.ofi > 0 ? "#22c55e" : "#ef4444",
                        marginLeft: telemetry.market.ofi < 0 ? "auto" : undefined,
                      }}
                    />
                  </div>
                </div>
              )}

              <div className="text-sm text-gray-400">
                {Math.abs(telemetry.market.ofi ?? 0) < 500
                  ? "→ OFI unter Threshold — kein LLM-Call, kein Trade"
                  : "→ OFI über Threshold — LLM-Cascade wird getriggert"}
              </div>

              {decisions?.stats && (
                <div className="mt-4 pt-4 border-t border-gray-700">
                  <div className="text-sm text-gray-500 mb-2">Letzte 50 Zyklen:</div>
                  <div className="grid grid-cols-3 gap-4 text-xs">
                    <div>
                      <span className="text-gray-500">OFI zu niedrig:</span>
                      <span className="text-zinc-200 ml-2">{decisions.stats.ofi_below_threshold}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Cascade HOLD:</span>
                      <span className="text-yellow-400 ml-2">{decisions.stats.cascade_hold}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Signals:</span>
                      <span className="text-green-400 ml-2">{decisions.stats.signals_generated}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* LLM Cascade Details */}
          {cascade && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">LLM Cascade - AI Decision Engine</h3>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${cascade.ollama_available ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
                  <span className="text-sm text-gray-400">
                    {cascade.ollama_available ? "Online" : "Offline"}
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <span className="text-gray-500 text-xs">Ollama Status</span>
                  <div className={`font-bold ${cascade.ollama_available ? "text-green-400" : "text-red-400"}`}>
                    {cascade.ollama_available ? "Online" : "Offline"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">Layer 1 Model</span>
                  <div className="font-bold text-zinc-200">
                    {cascade.model_layer1 || "qwen2.5:14b"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">Layer 2 Model</span>
                  <div className="font-bold text-zinc-200">
                    {cascade.model_layer2 || "deepseek-r1:14b"}
                  </div>
                </div>
              </div>

              {decisions?.events && (
                <div className="border-t border-gray-700 pt-4">
                  <div className="text-sm text-gray-500 mb-2">Cascade-Runs (nur wenn OFI erreicht):</div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {decisions.events.slice(0, 5).map((d: any, i: number) => (
                      <div key={i} className="text-xs text-gray-400 flex items-center gap-2">
                        <span>{new Date(d.timestamp ?? d.ts).toLocaleTimeString("de-DE")}</span>
                        <span className={d.decision === "BUY" || d.decision === "SELL"
                          ? "text-green-400 font-bold" : "text-yellow-400"}>
                          {d.decision ?? d.outcome}
                        </span>
                        {d.regime && <span className="text-gray-500">regime={d.regime}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Risk Agent Details */}
          {telemetry && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Risk Agent - Risk Management</h3>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${getAgentStatus("risk").healthy ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
                  <span className="text-sm text-gray-400">Monitoring Active</span>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <span className="text-gray-500 text-xs">Veto Status</span>
                  <div className={`font-bold ${telemetry?.veto_active ? "text-red-400" : "text-green-400"}`}>
                    {telemetry?.veto_active ? "AKTIV" : "INAKTIV"}
                  </div>
                  {telemetry?.veto_reason && (
                    <div className="text-sm text-gray-400 mt-1">{telemetry.veto_reason}</div>
                  )}
                </div>
                <div>
                  <span className="text-gray-500 text-xs">Risk Level</span>
                  <div className="font-bold text-yellow-400">MODERATE</div>
                </div>
              </div>

              {vetoHistory.length > 0 && (
                <div className="border-t border-gray-700 pt-4">
                  <div className="text-sm text-gray-500 mb-2">Veto-Zustandswechsel:</div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {vetoHistory.slice(0, 5).map((e, i) => (
                      <div key={i} className="text-xs flex gap-3 items-center">
                        <span className="text-gray-600">
                          {new Date(e.ts).toLocaleTimeString("de-DE")}
                        </span>
                        <span className={e.change === "VETO_ON" ? "text-red-400 font-bold" : "text-green-400"}>
                          {e.change === "VETO_ON" ? "VETO AN" : "VETO AUS"}
                        </span>
                        <span className="text-gray-500 truncate">{e.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Execution Agent Details */}
          {telemetry && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Execution Agent - Trade Execution</h3>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${getAgentStatus("execution").healthy ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
                  <span className="text-sm text-gray-400">
                    {telemetry?.dry_run ? "Simulation" : "Live"}
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-gray-500 text-xs">DRY_RUN Mode</span>
                  <div className={`font-bold ${telemetry?.dry_run ? "text-yellow-400" : "text-red-400"}`}>
                    {telemetry?.dry_run ? "AKTIV" : "DEAKTIVIERT"}
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 text-xs">Live Trading</span>
                  <div className={`font-bold ${telemetry?.live_trading_approved ? "text-green-400" : "text-zinc-500"}`}>
                    {telemetry?.live_trading_approved ? "APPROVED" : "NOT APPROVED"}
                  </div>
                </div>
              </div>

              <div className="mt-4 p-3 bg-gray-700 rounded-lg">
                <div className="text-sm">
                  {telemetry?.dry_run
                    ? "🔒 Kein echtes Kapital. Alle Trades sind simuliert."
                    : "⚠️ DRY_RUN ist deaktiviert — echte Orders möglich"}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
