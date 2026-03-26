"use client";

import { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";

interface AgentStatus {
  id: string;
  name: string;
  type: string;
  status: "running" | "stopped" | "error" | "idle";
  last_activity: string;
  uptime_seconds?: number;
  cpu_usage?: number;
  memory_usage?: number;
  tasks_processed: number;
  errors: number;
  last_error?: string;
  description: string;
  purpose: string;
  logic: string;
  configuration?: Record<string, any>;
  dependencies?: string[];
}

interface AgentsResponse {
  agents: AgentStatus[];
  overall_status: "success" | "warning" | "error" | "idle";
  last_check: string;
  total_agents: number;
  running_agents: number;
  error_agents: number;
}

export default function AgentenPage() {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastCheck, setLastCheck] = useState<string>("");
  const [selectedAgent, setSelectedAgent] = useState<AgentStatus | null>(null);
  const [infoModalOpen, setInfoModalOpen] = useState(false);

  const fetchAgents = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/agents/status");
      if (!response.ok) throw new Error("Fehler beim Laden der Agenten-Daten");
      
      const data: AgentsResponse = await response.json();
      setAgents(data.agents);
      setLastCheck(data.last_check);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
    const interval = setInterval(fetchAgents, 30000); // Alle 30 Sekunden aktualisieren
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "bg-green-400/20 text-green-400 border-green-400/30";
      case "stopped":
        return "bg-gray-400/20 text-gray-400 border-gray-400/30";
      case "error":
        return "bg-red-400/20 text-red-400 border-red-400/30";
      case "idle":
        return "bg-yellow-400/20 text-yellow-400 border-yellow-400/30";
      default:
        return "bg-gray-400/20 text-gray-400 border-gray-400/30";
    }
  };

  const getOverallStatusColor = (status: string) => {
    switch (status) {
      case "success":
        return "bg-green-400/20 text-green-400 border-green-400/30";
      case "warning":
        return "bg-yellow-400/20 text-yellow-400 border-yellow-400/30";
      case "error":
        return "bg-red-400/20 text-red-400 border-red-400/30";
      case "idle":
        return "bg-blue-400/20 text-blue-400 border-blue-400/30";
      default:
        return "bg-gray-400/20 text-gray-400 border-gray-400/30";
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit", 
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  };

  const getAgentTypeIcon = (type: string) => {
    switch (type) {
      case "data":
        return "📡";
      case "analysis":
        return "📊";
      case "risk":
        return "⚖️";
      case "execution":
        return "💰";
      default:
        return "🤖";
    }
  };

  const getAgentTypeColor = (type: string) => {
    switch (type) {
      case "data":
        return "text-blue-400 bg-blue-400/10";
      case "analysis":
        return "text-green-400 bg-green-400/10";
      case "risk":
        return "text-yellow-400 bg-yellow-400/10";
      case "execution":
        return "text-purple-400 bg-purple-400/10";
      default:
        return "text-gray-400 bg-gray-400/10";
    }
  };

  const formatUptime = (seconds?: number) => {
    if (!seconds) return "N/A";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  return (
    <div className="flex min-h-screen bg-[#0f0f1e]">
      <Sidebar />
      
      <main className="flex-1 ml-64 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">Agenten</h1>
              <p className="text-gray-400">Überwachung der Trading-Agenten</p>
            </div>
            <button
              onClick={fetchAgents}
              className="flex items-center gap-2 px-4 py-2 bg-[#2d2d44] hover:bg-[#3d3d54] text-white rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Aktualisieren
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400"></div>
            </div>
          ) : error ? (
            <div className="bg-red-400/20 border border-red-400/30 rounded-xl p-6">
              <h3 className="text-red-400 font-semibold mb-2">Fehler</h3>
              <p className="text-white">{error}</p>
            </div>
          ) : (
            <>
              {/* Overall Status */}
              <div className={`rounded-xl p-6 border mb-8 ${getOverallStatusColor(agents.length > 0 ? (agents.filter(a => a.status === "running").length === agents.length ? "success" : agents.filter(a => a.status === "error").length > 0 ? "error" : "warning") : "idle")}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                    <div>
                      <h2 className="text-xl font-semibold text-white">System Status</h2>
                      <p className="text-gray-300">
                        {agents.filter(a => a.status === "running").length} von {agents.length} Agenten aktiv
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-400">Letzte Prüfung</p>
                    <p className="text-white">{formatTime(lastCheck)}</p>
                  </div>
                </div>
              </div>

              {/* Agent Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {agents.map((agent, index) => (
                  <div key={agent.id} className="bg-[#1a1a2e] rounded-xl p-6 border border-[#2d2d44] hover:border-[#3d3d54] transition-all">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className={`text-2xl p-2 rounded-lg ${getAgentTypeColor(agent.type)}`}>
                          {getAgentTypeIcon(agent.type)}
                        </div>
                        <div>
                          <h3 className="text-white font-semibold">{agent.name}</h3>
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(agent.status)}`}>
                              {agent.status}
                            </span>
                            <span className="text-gray-400 text-xs">{agent.type}</span>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setSelectedAgent(agent);
                          setInfoModalOpen(true);
                        }}
                        className="p-2 bg-[#2d2d44] hover:bg-[#3d3d54] text-white rounded-lg transition-colors"
                        title="Agent-Info"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </button>
                    </div>

                    <p className="text-gray-400 text-sm mb-4">{agent.description}</p>

                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <p className="text-xs text-gray-500">Tasks</p>
                        <p className="text-sm text-white">{agent.tasks_processed}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Fehler</p>
                        <p className="text-sm text-white">{agent.errors}</p>
                      </div>
                    </div>

                    <div className="text-xs text-gray-500">
                      <p>Letzte Aktivität: {formatTime(agent.last_activity)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Info Modal */}
          {infoModalOpen && selectedAgent && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
              <div className="bg-[#1a1a2e] rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className={`text-2xl p-2 rounded-lg ${getAgentTypeColor(selectedAgent.type)}`}>
                      {getAgentTypeIcon(selectedAgent.type)}
                    </div>
                    <div>
                      <h2 className="text-xl font-semibold text-white">{selectedAgent.name}</h2>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(selectedAgent.status)}`}>
                        {selectedAgent.status}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => setInfoModalOpen(false)}
                    className="p-2 bg-[#2d2d44] hover:bg-[#3d3d54] text-white rounded-lg transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-2">Beschreibung</h3>
                    <p className="text-gray-300">{selectedAgent.description}</p>
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-white mb-2">Zweck</h3>
                    <p className="text-gray-300">{selectedAgent.purpose}</p>
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold text-white mb-2">Logik</h3>
                    <p className="text-gray-300">{selectedAgent.logic}</p>
                  </div>

                  {selectedAgent.dependencies && selectedAgent.dependencies.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-2">Abhängigkeiten</h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedAgent.dependencies.map((dep, index) => (
                          <span key={index} className="px-3 py-1 bg-[#2d2d44] text-gray-300 rounded-full text-sm">
                            {dep}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-gray-500">Tasks verarbeitet</p>
                      <p className="text-lg text-white">{selectedAgent.tasks_processed}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Fehler</p>
                      <p className="text-lg text-white">{selectedAgent.errors}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Letzte Aktivität</p>
                      <p className="text-sm text-white">{formatTime(selectedAgent.last_activity)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Uptime</p>
                      <p className="text-sm text-white">{formatUptime(selectedAgent.uptime_seconds)}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
