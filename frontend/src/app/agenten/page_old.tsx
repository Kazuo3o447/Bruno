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
}

interface AgentInfo {
  id: string;
  name: string;
  description: string;
  purpose: string;
  logic: string;
  configuration: Record<string, any>;
  dependencies: string[];
}

interface AgentsResponse {
  agents: AgentStatus[];
  overall_status: string;
  last_check: string;
  total_agents: number;
  running_agents: number;
  error_agents: number;
}

export default function AgentenPage() {
  const [agentsData, setAgentsData] = useState<AgentsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentInfo | null>(null);
  const [infoModalOpen, setInfoModalOpen] = useState(false);

  const loadAgentsStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch("http://localhost:8001/api/v1/agents/status");
      const data = await response.json();
      setAgentsData(data);
    } catch (error) {
      console.error("Agenten Status laden fehlgeschlagen:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadAgentInfo = async (agentId: string) => {
    try {
      const response = await fetch(`http://localhost:8001/api/v1/agents/info/${agentId}`);
      const data = await response.json();
      setSelectedAgent(data);
      setInfoModalOpen(true);
    } catch (error) {
      console.error("Agenten Info laden fehlgeschlagen:", error);
    }
  };

  const restartAgent = async (agentId: string) => {
    try {
      const response = await fetch(`http://localhost:8001/api/v1/agents/restart/${agentId}`, {
        method: "POST"
      });
      const data = await response.json();
      if (data.status === "success") {
        await loadAgentsStatus(); // Status neu laden
      }
    } catch (error) {
      console.error("Agent neustarten fehlgeschlagen:", error);
    }
  };

  useEffect(() => {
    loadAgentsStatus();
    
    // Auto-Refresh alle 30 Sekunden
    const interval = setInterval(loadAgentsStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "text-green-400 bg-green-400/10";
      case "stopped":
        return "text-gray-400 bg-gray-400/10";
      case "error":
        return "text-red-400 bg-red-400/10";
      case "idle":
        return "text-yellow-400 bg-yellow-400/10";
      default:
        return "text-gray-400 bg-gray-400/10";
    }
  };

  const getOverallStatusColor = (status: string) => {
    switch (status) {
      case "success":
        return "bg-green-500";
      case "warning":
        return "bg-yellow-500";
      case "error":
        return "bg-red-500";
      default:
        return "bg-gray-500";
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

  return (
    <div className="flex min-h-screen bg-[#0f0f1e]">
      <Sidebar />
      
      <main className="flex-1 ml-64 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">Agenten</h1>
              <p className="text-gray-400">Überwachung und Steuerung der Trading-Agenten</p>
            </div>
            <button
              onClick={loadAgentsStatus}
              disabled={loading}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Lädt...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Refresh
                </>
              )}
            </button>
          </div>

          {/* Letzte Prüfung */}
          {agentsData && (
            <div className="bg-[#1a1a2e] rounded-xl p-4 border border-[#2d2d44] mb-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <span className="text-gray-400">Letzte Prüfung:</span>
                  <span className="text-white font-medium">{formatTime(agentsData.last_check)}</span>
                </div>
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                    <span className="text-gray-400">Laufend: {agentsData.running_agents}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                    <span className="text-gray-400">Fehler: {agentsData.error_agents}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-gray-500 rounded-full"></div>
                    <span className="text-gray-400">Gesamt: {agentsData.total_agents}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Overall Status */}
          {agentsData && (
            <div className={`rounded-xl p-6 border mb-6 ${getOverallStatusColor(agentsData.overall_status)} bg-opacity-10 border-opacity-30`}>
              <div className="flex items-center gap-4">
                <div className={`w-16 h-16 rounded-full ${getOverallStatusColor(agentsData.overall_status)} flex items-center justify-center`}>
                  {agentsData.overall_status === "success" ? (
                    <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : agentsData.overall_status === "warning" ? (
                    <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  ) : (
                    <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white">
                    {agentsData.overall_status === "success" && "Alle Agenten funktionieren"}
                    {agentsData.overall_status === "warning" && "Einige Agenten haben Warnungen"}
                    {agentsData.overall_status === "error" && "Kritische Agenten-Fehler"}
                    {agentsData.overall_status === "idle" && "Keine Agenten aktiv"}
                  </h3>
                  <p className="text-gray-400">
                    {agentsData.running_agents} von {agentsData.total_agents} Agenten laufen
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Agenten Liste */}
          {agentsData && (
            <div className="bg-[#1a1a2e] rounded-xl border border-[#2d2d44] overflow-hidden">
              <div className="p-6 border-b border-[#2d2d44]">
                <h3 className="text-lg font-semibold text-white">Agenten-Status</h3>
              </div>
              <div className="divide-y divide-[#2d2d44]">
                {agentsData.agents.map((agent, index) => (
                  <div key={index} className="p-6 hover:bg-[#252538] transition-colors">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-3">
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(agent.status)}`}>
                            {agent.status.toUpperCase()}
                          </span>
                          <h4 className="font-medium text-white text-lg">{agent.name}</h4>
                          <span className="text-sm text-gray-500">{agent.type}</span>
                        </div>
                        
                        <p className="text-gray-400 mb-3">{agent.description}</p>
                        
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
                          <div>
                            <p className="text-xs text-gray-500">Letzte Aktivität</p>
                            <p className="text-sm text-white">{formatTime(agent.last_activity)}</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">Tasks verarbeitet</p>
                            <p className="text-sm text-white">{agent.tasks_processed}</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">Fehler</p>
                            <p className="text-sm text-white">{agent.errors}</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">Uptime</p>
                            <p className="text-sm text-white">{formatUptime(agent.uptime_seconds)}</p>
                          </div>
                        </div>

                        {agent.last_error && (
                          <div className="bg-red-400/10 border border-red-400/20 rounded p-3 mb-3">
                      </div>
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Info Modal */}
          {infoModalOpen && selectedAgent && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-[#1a1a2e] rounded-xl border border-[#2d2d44] max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                <div className="p-6 border-b border-[#2d2d44] flex items-center justify-between">
                  <h3 className="text-xl font-semibold text-white">{selectedAgent.name}</h3>
                  <button
                    onClick={() => setInfoModalOpen(false)}
                    className="p-2 hover:bg-[#2d2d44] text-white rounded-lg transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                
                <div className="p-6 space-y-6">
                  <div>
                    <h4 className="text-lg font-medium text-white mb-2">Beschreibung</h4>
                    <p className="text-gray-400">{selectedAgent.description}</p>
                  </div>
                  
                  <div>
                    <h4 className="text-lg font-medium text-white mb-2">Zweck</h4>
                    <p className="text-gray-400">{selectedAgent.purpose}</p>
                  </div>
                  
                  <div>
                    <h4 className="text-lg font-medium text-white mb-2">Logik & Funktionsweise</h4>
                    <p className="text-gray-400 whitespace-pre-wrap">{selectedAgent.logic}</p>
                  </div>
                  
                  <div>
                    <h4 className="text-lg font-medium text-white mb-2">Konfiguration</h4>
                    <div className="bg-[#0f0f1e] rounded p-4">
                      <pre className="text-sm text-gray-300">
                        {JSON.stringify(selectedAgent.configuration, null, 2)}
                      </pre>
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-lg font-medium text-white mb-2">Abhängigkeiten</h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedAgent.dependencies.map((dep, index) => (
                        <span key={index} className="px-3 py-1 bg-blue-600/20 text-blue-400 rounded-lg text-sm">
                          {dep}
                        </span>
                      ))}
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
