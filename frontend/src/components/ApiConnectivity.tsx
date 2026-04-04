"use client";

import React, { useState, useEffect } from "react";
import { 
  Wifi, WifiOff, Activity, Database, Globe, 
  TrendingUp, Newspaper, Server, Cpu, AlertCircle,
  CheckCircle2, XCircle, Clock, Zap
} from "lucide-react";

interface SourceHealth {
  status: string;
  latency_ms: number;
  last_update: string;
}

interface ApiConnectivityProps {
  sources?: Record<string, SourceHealth>;
  loading?: boolean;
}

export default function ApiConnectivity({ sources = {}, loading = false }: ApiConnectivityProps) {
  const [expanded, setExpanded] = useState(false);
  
  const sourceEntries = Object.entries(sources);
  const onlineCount = sourceEntries.filter(([_, data]) => 
    ["online", "ok", "healthy", "connected", "success", "running"].includes(data.status?.toLowerCase())
  ).length;
  const totalCount = sourceEntries.length;
  const offlineCount = totalCount - onlineCount;
  
  // Group sources by category
  const grouped = sourceEntries.reduce((acc, [name, data]) => {
    let category = "Other";
    if (name.includes("Binance") || name.includes("Bybit") || name.includes("Deribit")) {
      category = "Exchanges";
    } else if (name.includes("CryptoCompare") || name.includes("CoinMarketCap") || name.includes("yFinance")) {
      category = "Market Data";
    } else if (name.includes("TA") || name.includes("Liquidation")) {
      category = "Analytics";
    }
    
    if (!acc[category]) acc[category] = [];
    acc[category].push({ name, ...data });
    return acc;
  }, {} as Record<string, Array<{name: string} & SourceHealth>>);

  if (loading) {
    return (
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4 animate-pulse">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-3 h-3 bg-slate-700 rounded-full" />
          <div className="h-3 bg-slate-700 rounded w-32" />
        </div>
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-8 bg-slate-800/50 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (totalCount === 0) {
    return (
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
        <div className="flex items-center gap-2 text-slate-500">
          <WifiOff className="w-4 h-4" />
          <span className="text-xs font-medium">Keine API-Verbindungsdaten verfügbar</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl overflow-hidden">
      {/* Header */}
      <div 
        className="p-4 cursor-pointer hover:bg-[#111122] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-2.5 h-2.5 rounded-full ${offlineCount === 0 ? 'bg-emerald-500 animate-pulse' : offlineCount > 2 ? 'bg-red-500' : 'bg-amber-500'} shadow-[0_0_10px_currentColor]`} />
            <div>
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Globe className="w-3.5 h-3.5 text-indigo-400" />
                API Konnektivität
              </h3>
              <p className="text-[10px] text-slate-500 mt-0.5">
                {onlineCount}/{totalCount} Datenquellen aktiv
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Quick Stats */}
            <div className="flex gap-2 text-[10px]">
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {onlineCount} Online
              </span>
              {offlineCount > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
                  {offlineCount} Offline
                </span>
              )}
            </div>
            
            <span className="text-slate-600 text-xs">
              {expanded ? '▼' : '▶'}
            </span>
          </div>
        </div>
        
        {/* Progress Bar */}
        <div className="mt-3 h-1.5 w-full bg-[#1a1a2e] rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-500 ${
              offlineCount === 0 ? 'bg-emerald-500' : 
              offlineCount > 2 ? 'bg-red-500' : 'bg-amber-500'
            }`}
            style={{ width: `${(onlineCount / totalCount) * 100}%` }}
          />
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t border-[#1a1a2e]">
          {Object.entries(grouped).map(([category, items]) => (
            <div key={category} className="border-b border-[#1a1a2e]/50 last:border-0">
              <div className="px-4 py-2 bg-[#0a0a14]">
                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">
                  {category}
                </span>
              </div>
              <div className="p-2 space-y-1">
                {items.map((item) => {
                  const isOnline = ["online", "ok", "healthy", "connected", "success", "running"].includes(item.status?.toLowerCase());
                  const isWarning = ["degraded", "warning", "fallback", "partial"].includes(item.status?.toLowerCase());
                  
                  return (
                    <div 
                      key={item.name}
                      className={`flex items-center justify-between px-3 py-2 rounded-lg transition-all ${
                        isOnline ? 'bg-emerald-500/5 border border-emerald-500/10' : 
                        isWarning ? 'bg-amber-500/5 border border-amber-500/10' :
                        'bg-red-500/5 border border-red-500/10'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${
                          isOnline ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]' : 
                          isWarning ? 'bg-amber-500' : 'bg-red-500'
                        }`} />
                        <span className="text-xs text-slate-300 font-medium">{item.name}</span>
                      </div>
                      
                      <div className="flex items-center gap-3">
                        {isOnline && item.latency_ms > 0 && (
                          <span className={`text-[10px] font-mono ${
                            item.latency_ms < 200 ? 'text-emerald-400' : 
                            item.latency_ms < 1000 ? 'text-amber-400' : 'text-red-400'
                          }`}>
                            {Math.round(item.latency_ms)}ms
                          </span>
                        )}
                        <span className={`text-[9px] uppercase font-bold ${
                          isOnline ? 'text-emerald-400/80' : 
                          isWarning ? 'text-amber-400/80' : 'text-red-400/80'
                        }`}>
                          {item.status}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
