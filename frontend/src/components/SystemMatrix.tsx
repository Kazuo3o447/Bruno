"use client";

import React, { useState, useEffect } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Activity, Database, Cpu, Wifi, ShieldCheck } from "lucide-react";

interface HealthState {
  api: boolean;
  db: boolean;
  redis: boolean;
  ollama: boolean;
  bybit: boolean;
}

interface AgentStatus {
  id: string;
  name: string;
  status: string;
  last_heartbeat: string | null;
  healthy: boolean;
  age_seconds: number | null;
}

export default function SystemMatrix() {
  const [health, setHealth] = useState<HealthState>({
    api: false, db: false, redis: false, ollama: false, bybit: false
  });
  const [agents, setAgents] = useState<Record<string, AgentStatus>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("http://localhost:8001/api/v1/telemetry/live");
        if (res.ok) {
          const data = await res.json();
          
          // API & Core Health
          setHealth({
            api: true,
            db: data.agents ? Object.values(data.agents).length > 0 : true, // Placeholder logic if database field is missing in telemetry
            redis: true, // If we got data, redis is working
            ollama: true, // Placeholder
            bybit: data.live_trading_approved || false
          });

          // Agent Heartbeats
          setAgents(data.agents || {});
        }
      } catch (err) {
        console.error("Telemetry fetch failed:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const iv = setInterval(fetchData, 5000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Infrastructure Core */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
        <h3 className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-4 flex items-center gap-2">
          <Database className="w-3.5 h-3.5" /> Core Infrastructure
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <HealthNode label="Backend API" status={health.api ? 'ok' : 'error'} icon={<Activity className="w-3.5 h-3.5" />} />
          <HealthNode label="TimescaleDB" status={health.db ? 'ok' : 'error'} icon={<Database className="w-3.5 h-3.5" />} />
          <HealthNode label="Redis Cache" status={health.redis ? 'ok' : 'error'} icon={<Cpu className="w-3.5 h-3.5" />} />
          <HealthNode label="Ollama (Llama3)" status={health.ollama ? 'warn' : 'ok'} icon={<Cpu className="w-3.5 h-3.5" />} />
        </div>
      </div>

      {/* Agent Heartbeats */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
        <h3 className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-4 flex items-center gap-2">
          <Cpu className="w-3.5 h-3.5" /> Agent Heartbeats
        </h3>
        <div className="space-y-2 max-h-[140px] overflow-y-auto custom-scrollbar pr-1">
          {Object.entries(agents).map(([id, agent]) => (
             <div key={id} className="flex items-center justify-between py-1 border-b border-[#1a1a2e]/50 last:border-0">
                <div className="flex items-center gap-2">
                   <div className={`w-1.5 h-1.5 rounded-full ${agent.healthy ? 'bg-emerald-500' : 'bg-red-500'} ${agent.healthy ? 'animate-pulse' : ''}`} />
                   <span className="text-xs text-slate-300 font-medium capitalize">{id}</span>
                </div>
                <div className="flex items-center gap-3">
                   <span className="text-[10px] text-slate-500 font-mono">
                      {agent.age_seconds !== null ? `${agent.age_seconds}s ago` : 'never'}
                   </span>
                   <span className={`text-[10px] uppercase font-bold ${agent.status === 'running' ? 'text-emerald-500/80' : 'text-slate-600'}`}>
                      {agent.status}
                   </span>
                </div>
             </div>
          ))}
          {Object.keys(agents).length === 0 && !loading && (
             <p className="text-[10px] text-slate-600 italic">No heartbeats detected.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function HealthNode({ label, status, icon }: { label: string; status: 'ok' | 'warn' | 'error'; icon: any }) {
  const colors = {
    ok: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
    warn: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
    error: 'text-red-500 bg-red-500/10 border-red-500/20'
  };

  const StatusIcon = status === 'ok' ? CheckCircle2 : status === 'warn' ? AlertTriangle : XCircle;

  return (
    <div className={`flex items-center justify-between p-2 rounded-lg border ${colors[status]} transition-all`}>
      <div className="flex items-center gap-2 overflow-hidden">
        <span className="opacity-70">{icon}</span>
        <span className="text-[10px] font-bold truncate">{label}</span>
      </div>
      <StatusIcon className="w-3 h-3 shrink-0" />
    </div>
  );
}
