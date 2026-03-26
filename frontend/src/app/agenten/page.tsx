"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import AgentInfoModal from "../../components/AgentInfoModal";
import { 
  MessageSquare, 
  Terminal, 
  Settings2, 
  Play, 
  Square, 
  RefreshCw, 
  Send, 
  Info, 
  ShieldAlert, 
  Cpu, 
  Activity,
  Zap,
  History,
  CheckCircle2,
  AlertCircle
} from "lucide-react";

interface AgentStatus {
  id: string;
  name: string;
  type: string;
  status: "running" | "stopped" | "error" | "dead" | "unknown";
  last_activity: string;
  uptime_seconds?: number;
  processed_count: number;
  error_count: number;
  last_error?: string;
  description: string;
  health: "healthy" | "degraded" | "error";
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
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [infoModalOpen, setInfoModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "logs" | "control">("chat");

  const fetchAgents = useCallback(async (isInitial = false) => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/agents/status");
      if (!response.ok) throw new Error("Fehler beim Laden der Agenten-Daten");
      
      const data: AgentsResponse = await response.json();
      setAgents(data.agents);
      setLastCheck(data.last_check);
      setError(null);
      
      // Nur beim ERSTEN Laden oder wenn die Selection ungültig wird, den ersten wählen
      if (isInitial && data.agents.length > 0) {
        setSelectedAgentId(prev => prev ?? data.agents[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler");
      console.error(err);
    } finally {
      if (isInitial) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents(true);
    const interval = setInterval(() => fetchAgents(false), 5000);
    return () => clearInterval(interval);
  }, [fetchAgents]);

  const selectedAgent = agents.find(a => a.id === selectedAgentId);

  const handleAgentControl = async (action: "start" | "stop" | "restart", id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/agents/${action}/${id}`, { method: 'POST' });
      if (!res.ok) throw new Error(`Konnte Agent nicht ${action}`);
      fetchAgents(false);
    } catch (e) {
      alert(e);
    }
  };

  return (
    <>
    <div className="w-full p-4 lg:p-8 overflow-hidden h-[calc(100vh-2rem)] flex flex-col">
        {/* Modern Glass Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 shrink-0 mb-8 bg-[#0a0a14]/40 p-6 rounded-2xl border border-[#1a1a2e] backdrop-blur-sm">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="p-2 bg-indigo-500/10 rounded-lg">
                <Cpu className="text-indigo-400 w-6 h-6" />
              </div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Agenten-Zentrale</h1>
            </div>
            <p className="text-slate-500 text-sm">Oversight & Steuerung der aktiven KI-Pipeline</p>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Letzter Check</p>
              <p className="text-xs text-indigo-400 font-mono">{lastCheck ? new Date(lastCheck).toLocaleTimeString() : '--:--:--'}</p>
            </div>
            <button
              onClick={() => setInfoModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 rounded-xl transition-all border border-indigo-500/20 text-xs font-bold uppercase tracking-wider h-max"
            >
              <Info className="w-4 h-4" />
              System-Guide
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-4">
             <div className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
             <p className="text-slate-500 text-sm font-medium animate-pulse">Initialisiere Neural Network...</p>
          </div>
        ) : error && agents.length === 0 ? (
          <div className="bg-red-500/5 border border-red-500/20 text-red-400 p-6 rounded-2xl flex items-center gap-4">
            <ShieldAlert className="w-8 h-8 opacity-50" />
            <div>
              <p className="font-bold">Verbindungsfehler</p>
              <p className="text-sm opacity-80">{error}</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-1 gap-8 overflow-hidden">
            {/* Left: Premium Master List */}
            <div className="w-[380px] shrink-0 flex flex-col gap-4 overflow-y-auto pr-2 custom-scrollbar pb-6">
              {agents.map((agent) => {
                const isSelected = agent.id === selectedAgentId;
                const isRunning = agent.status === 'running';
                
                return (
                  <div 
                    key={agent.id}
                    onClick={() => setSelectedAgentId(agent.id)}
                    className={`group relative cursor-pointer p-5 rounded-2xl border transition-all duration-300 ${
                      isSelected 
                        ? "bg-indigo-500/5 border-indigo-500/40 shadow-[0_0_20px_rgba(99,102,241,0.1)]" 
                        : "bg-[#0a0a14] border-[#1a1a2e] hover:border-indigo-500/20 hover:bg-indigo-500/[0.02]"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                       <div className="flex flex-col">
                         <h3 className={`font-bold transition-colors ${isSelected ? 'text-white' : 'text-slate-300 group-hover:text-white'}`}>
                           {agent.name}
                         </h3>
                         <span className="text-[10px] font-mono text-slate-500 uppercase">{agent.type}</span>
                       </div>
                        <div className="flex gap-2">
                           {agent.health === "degraded" && (
                             <div className="px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest bg-yellow-500/10 border border-yellow-500/20 text-yellow-500">
                               DEGRADED
                             </div>
                           )}
                           <div className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest border ${
                             isRunning ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
                           }`}>
                             {agent.status}
                           </div>
                        </div>
                    </div>
                    
                    <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed mb-4 group-hover:text-slate-400 transition-colors">
                      {agent.description}
                    </p>

                    <div className="flex items-center gap-4 text-[10px] font-bold text-slate-600">
                      <div className="flex items-center gap-1.5">
                        <Activity className="w-3 h-3" />
                        {agent.processed_count} <span className="text-slate-700">Ops</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <History className="w-3 h-3" />
                        {formatUptime(agent.uptime_seconds)}
                      </div>
                    </div>

                    {isSelected && (
                      <div className="absolute right-4 bottom-4">
                        <Zap className="w-4 h-4 text-indigo-500 animate-pulse" />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Right: Premium Detail View */}
            {selectedAgent ? (
              <div className="flex-1 bg-[#0a0a14] border border-[#1a1a2e] rounded-3xl flex flex-col overflow-hidden shadow-2xl relative">
                {/* Header Background Glow */}
                <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-indigo-500/[0.03] to-transparent pointer-events-none" />

                {/* Tabs Bar */}
                <div className="flex items-center bg-[#070712] border-b border-[#1a1a2e] z-10 px-4">
                  <TabButton active={activeTab === 'chat'} onClick={() => setActiveTab('chat')} icon={<MessageSquare />} label="Agent Chat" />
                  <TabButton active={activeTab === 'control'} onClick={() => setActiveTab('control')} icon={<Settings2 />} label="Status & Control" />
                  <TabButton active={activeTab === 'logs'} onClick={() => setActiveTab('logs')} icon={<Terminal />} label="System Logs" />
                </div>

                {/* Tab Content */}
                <div className="flex-1 overflow-hidden relative z-0">
                   {activeTab === 'chat' && <AgentChat agent={selectedAgent} />}
                   {activeTab === 'logs' && <AgentLogs agent={selectedAgent} />}
                   {activeTab === 'control' && <AgentControl agent={selectedAgent} handleControl={handleAgentControl} />}
                   
                   {/* Health Banner for Degraded State */}
                   {selectedAgent.health === "degraded" && (
                     <div className="absolute bottom-6 left-6 right-6 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-2xl flex items-center gap-3 animate-pulse z-20">
                       <AlertCircle className="text-yellow-500 w-5 h-5 shrink-0" />
                       <p className="text-xs text-yellow-500 font-medium">
                         Dieser Agent läuft im **eingeschränkten Modus** (Degraded). 
                         {selectedAgent.id === 'sentiment' && " LLM nicht erreichbar -> Keyword-Fallback aktiv."}
                         {selectedAgent.id === 'risk' && " Reasoning-Modell fehlt -> Heuristiken aktiv."}
                       </p>
                     </div>
                   )}
                </div>

              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center opacity-20 border-2 border-dashed border-[#1a1a2e] rounded-3xl">
                <Cpu className="w-16 h-16 mb-4" />
                <p className="text-lg font-bold tracking-widest uppercase">Wähle einen Agenten</p>
              </div>
            )}
          </div>
        )}
      </div>

      <AgentInfoModal isOpen={infoModalOpen} onClose={() => setInfoModalOpen(false)} />

      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #1a1a2e; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #312e81; }
      `}</style>
    </>
  );
}

// ---------------- Helper Components ----------------

function TabButton({ active, onClick, icon, label }: any) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2.5 px-6 py-4 text-[11px] font-bold uppercase tracking-widest transition-all relative
        ${active ? "text-indigo-400" : "text-slate-500 hover:text-slate-300"}
      `}
    >
      <span className="[&>svg]:w-4 [&>svg]:h-4">{icon}</span>
      {label}
      {active && <div className="absolute bottom-[-1px] left-0 right-0 h-[2px] bg-indigo-500 shadow-[0_0_10px_#6366f1]" />}
    </button>
  );
}

// --- Premium Agent Chat ---
function AgentChat({ agent }: { agent: AgentStatus }) {
  const [messages, setMessages] = useState<{role: string, content: string}[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Selection stability fix: only reset if it's a completely different agent
    setMessages([
      { role: "agent", content: `System-Check abgeschlossen. Ich bin **${agent.name}**. Mein aktueller Fokus: ${agent.description}. Wie kann ich dich heute unterstützen?` }
    ]);
  }, [agent.id]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    
    const userMsg = input.trim();
    setInput("");
    setMessages((prev: any) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    const fullPrompt = `System: Du bist der ${agent.name} eines Krypto Trading-Bots. Dein Aufgabenbereich ist: ${agent.description}. Bleibe strikt in deiner Rolle. Halte Antworten präzise und professionell.\n\nUser: ${userMsg}`;

    try {
      const res = await fetch("http://localhost:8000/api/v1/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "qwen2.5:14b",
          prompt: fullPrompt,
          stream: false
        })
      });
      
      if (!res.ok) {
        // Parse the actual backend error
        let errorMsg = `HTTP ${res.status}`;
        try {
          const errData = await res.json();
          errorMsg = errData.detail || errorMsg;
        } catch {}
        
        if (res.status === 503) {
          throw new Error(`⚠️ Ollama nicht erreichbar: ${errorMsg}\n\nBitte prüfe:\n• Läuft Ollama auf deinem PC? (ollama serve)\n• Ist das Modell qwen2.5:14b geladen? (ollama list)\n• Firewall blockiert Port 11434?`);
        } else if (res.status === 504) {
          throw new Error("⏱️ Zeitüberschreitung: Das Modell braucht zu lange. Versuche es erneut oder wechsle zu einem kleineren Modell.");
        } else {
          throw new Error(`❌ Backend-Fehler: ${errorMsg}`);
        }
      }
      
      const data = await res.json();
      setMessages((prev: any) => [...prev, { role: "agent", content: data.response }]);
    } catch (e: any) {
      const errorContent = e.message?.includes("fetch") || e.message?.includes("Failed")
        ? "❌ Backend nicht erreichbar. Läuft der API-Container? (docker ps)"
        : e.message || "❌ Unbekannter Fehler beim LLM-Aufruf.";
      setMessages((prev: any) => [...prev, { role: "agent", content: errorContent }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#050510]/50">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-8 space-y-6 custom-scrollbar">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] relative ${m.role === 'user' ? 'text-right' : 'text-left'}`}>
              <div className={`inline-block px-5 py-3 rounded-2xl text-[13px] leading-relaxed transition-all ${
                m.role === 'user' 
                  ? 'bg-indigo-600 text-white rounded-tr-none shadow-[0_5px_15px_rgba(79,70,229,0.2)]' 
                  : 'bg-[#11111d] border border-[#1a1a2e] text-slate-200 rounded-tl-none'
              }`}>
                <div className="whitespace-pre-wrap">{m.content}</div>
              </div>
              <div className="text-[10px] font-bold text-slate-600 mt-1 uppercase tracking-tighter opacity-50">
                {m.role === 'user' ? 'Administrator' : agent.name}
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#11111d] border border-[#1a1a2e] rounded-2xl p-4 flex gap-1.5 items-center">
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce"></div>
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.2s]"></div>
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.4s]"></div>
            </div>
          </div>
        )}
      </div>
      <div className="p-6 border-t border-[#1a1a2e] bg-[#070712]">
        <div className="relative group">
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
            placeholder={`Neuraler Link zu ${agent.name} wird aufgebaut...`}
            className="w-full bg-[#050510] border border-[#1a1a2e] text-white rounded-xl py-4 pl-5 pr-14 focus:outline-none focus:border-indigo-500/50 transition-all placeholder:text-slate-700 text-sm shadow-inner"
          />
          <button 
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg disabled:opacity-30 transition-all shadow-lg"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// --- Premium Agent Status & Control ---
function AgentControl({ agent, handleControl }: { agent: AgentStatus, handleControl: any }) {
  const isRunning = agent.status === 'running';

  return (
    <div className="h-full overflow-y-auto p-10 custom-scrollbar relative">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-10">
        
        {/* Core Metrics Grid */}
        <div className="space-y-8">
           <div className="flex items-center gap-3 mb-2">
             <Activity className="w-5 h-5 text-indigo-400" />
             <h3 className="text-lg font-bold text-white tracking-tight">Status & Biometrie</h3>
           </div>
           
           <div className="grid grid-cols-2 gap-4">
              <MetricBox label="Zustand" value={agent.status} color={isRunning ? 'text-emerald-400' : 'text-slate-500'} />
              <MetricBox label="Operations" value={agent.processed_count.toString()} />
              <MetricBox label="Runtime" value={formatUptime(agent.uptime_seconds)} />
              <MetricBox label="Error Score" value={agent.error_count.toString()} color={agent.error_count > 0 ? 'text-red-400' : 'text-emerald-400'} />
           </div>

           <div className="bg-[#11111d] rounded-2xl p-6 border border-[#1a1a2e]">
             <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-4">Neural Descriptor</h4>
             <p className="text-sm text-slate-400 leading-relaxed italic">
               "{agent.description}"
             </p>
           </div>
        </div>

        {/* Action Center */}
        <div className="space-y-8">
           <div className="flex items-center gap-3 mb-2">
             <Settings2 className="w-5 h-5 text-indigo-400" />
             <h3 className="text-lg font-bold text-white tracking-tight">Override Center</h3>
           </div>

           <div className="bg-[#11111d] rounded-2xl p-6 border border-[#1a1a2e] space-y-6">
              <div className="flex gap-4">
                <button 
                   onClick={() => handleControl("start", agent.id)}
                   disabled={isRunning}
                   className="flex-1 flex items-center justify-center gap-2 py-4 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-xl transition-all font-bold text-[11px] uppercase tracking-widest disabled:opacity-20"
                >
                  <Play className="w-4 h-4" /> Online
                </button>
                <button 
                   onClick={() => handleControl("stop", agent.id)}
                   disabled={!isRunning}
                   className="flex-1 flex items-center justify-center gap-2 py-4 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 rounded-xl transition-all font-bold text-[11px] uppercase tracking-widest disabled:opacity-20"
                >
                  <Square className="w-4 h-4" /> Offline
                </button>
              </div>
              <button 
                 onClick={() => handleControl("restart", agent.id)}
                 className="w-full flex items-center justify-center gap-2 py-4 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/20 rounded-xl transition-all font-bold text-[11px] uppercase tracking-widest"
              >
                <RefreshCw className="w-4 h-4" /> System Reset
              </button>
           </div>

           {agent.last_error && (
             <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-6">
                <div className="flex items-center gap-2 text-red-400 mb-3">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-[11px] font-bold uppercase tracking-widest">Kritischer Error Log</span>
                </div>
                <div className="font-mono text-[11px] text-red-400/80 bg-black/40 p-4 rounded-xl border border-red-500/10 break-all leading-relaxed">
                  {agent.last_error}
                </div>
             </div>
           )}
        </div>

      </div>
    </div>
  );
}

function MetricBox({ label, value, color = 'text-white' }: { label: string, value: string, color?: string }) {
  return (
    <div className="bg-[#11111d] p-4 rounded-2xl border border-[#1a1a2e]">
      <p className="text-[9px] text-slate-500 font-bold uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono uppercase tracking-tight ${color}`}>{value}</p>
    </div>
  );
}

// --- Basic Agent Logs ---
function AgentLogs({ agent }: { agent: AgentStatus }) {
  const [logs, setLogs] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const connectWs = () => {
      const ws = new WebSocket("ws://localhost:8000/api/v1/logs/ws");
      wsRef.current = ws;
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "new_log" && (data.log.source === `agent.${agent.id}` || data.log.name?.includes(agent.id))) {
            setLogs(prev => [data.log, ...prev].slice(0, 100));
          } else if (data.type === "history" || data.type === "filtered") {
            const filtered = data.logs.filter((l:any) => l.source === `agent.${agent.id}` || l.name?.includes(agent.id));
            setLogs(filtered.slice(0, 100));
          }
        } catch (e) {}
      };
      ws.onclose = () => setTimeout(connectWs, 3000);
    };

    connectWs();
    return () => wsRef.current?.close();
  }, [agent.id]);

  return (
    <div className="h-full bg-black/80 font-mono text-[11px] overflow-y-auto p-6 custom-scrollbar">
      {logs.length === 0 ? (
        <div className="text-slate-700 italic h-full flex items-center justify-center uppercase tracking-widest">
           Warte auf Datenstrom...
        </div>
      ) : (
        <div className="space-y-1.5">
          {logs.map((L, i) => {
            let color = "text-slate-500";
            if (L.level === "ERROR" || L.level === "CRITICAL") color = "text-red-500";
            if (L.level === "WARNING") color = "text-amber-500";
            if (L.level === "INFO") color = "text-indigo-400";
            return (
              <div key={i} className={`flex gap-3 items-start ${color}`}>
                <span className="opacity-30 shrink-0">[{new Date(L.timestamp).toLocaleTimeString()}]</span>
                <span className="font-bold shrink-0 w-16">[{L.level}]</span>
                <span className="text-slate-300">{L.message}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function formatUptime(seconds?: number) {
  if (seconds === undefined || seconds === 0) return "0S";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}H ${m}M`;
  return `${m}M ${seconds % 60}S`;
}
