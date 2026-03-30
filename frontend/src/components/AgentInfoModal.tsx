import { useState } from "react";
import { 
  X, Database, Brain, Activity, ShieldCheck, Zap, ArrowRight, Layers, 
  Server, MessageSquare, Terminal, Settings2, Play, Square, RefreshCw,
  Cpu, AlertCircle, CheckCircle2, Info, Radio, Clock, Lock
} from "lucide-react";

interface AgentInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AgentInfoModal({ isOpen, onClose }: AgentInfoModalProps) {
  const [activeSection, setActiveSection] = useState<"overview" | "architecture" | "control" | "troubleshoot">("overview");
  
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[100] backdrop-blur-sm p-4">
      <div className="bg-[#0a0a14] rounded-3xl w-full max-w-5xl max-h-[90vh] overflow-hidden border border-[#1a1a2e] shadow-2xl relative">
        
        {/* Header */}
        <div className="sticky top-0 bg-[#0a0a14]/95 border-b border-[#1a1a2e] p-6 flex items-center justify-between z-10 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-indigo-500/20 text-indigo-400 rounded-2xl border border-indigo-500/30">
              <Layers className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white tracking-tight">System-Guide</h2>
              <p className="text-sm text-slate-500">Bruno Trading Bot — Agenten-Architektur & Steuerung</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-800/50 rounded-xl text-slate-400 hover:text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-[#1a1a2e] bg-[#070712]">
          <NavButton 
            active={activeSection === "overview"} 
            onClick={() => setActiveSection("overview")}
            icon={<Info className="w-4 h-4" />}
            label="Übersicht"
          />
          <NavButton 
            active={activeSection === "architecture"} 
            onClick={() => setActiveSection("architecture")}
            icon={<Server className="w-4 h-4" />}
            label="Architektur"
          />
          <NavButton 
            active={activeSection === "control"} 
            onClick={() => setActiveSection("control")}
            icon={<Settings2 className="w-4 h-4" />}
            label="Steuerung"
          />
          <NavButton 
            active={activeSection === "troubleshoot"} 
            onClick={() => setActiveSection("troubleshoot")}
            icon={<AlertCircle className="w-4 h-4" />}
            label="Fehlerbehebung"
          />
        </div>

        {/* Content */}
        <div className="p-8 overflow-y-auto max-h-[calc(90vh-140px)] custom-scrollbar">
          
          {activeSection === "overview" && <OverviewSection />}
          {activeSection === "architecture" && <ArchitectureSection />}
          {activeSection === "control" && <ControlSection />}
          {activeSection === "troubleshoot" && <TroubleshootSection />}

        </div>
      </div>
    </div>
  );
}

// ==================== SECTION COMPONENTS ====================

function OverviewSection() {
  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 p-8 rounded-2xl border border-indigo-500/20">
        <h3 className="text-xl font-bold text-white mb-4">Die Bruno Agenten-Pipeline</h3>
        <p className="text-slate-400 leading-relaxed mb-6">
          Bruno ist kein monolithischer Bot, sondern ein <strong className="text-indigo-400">verteiltes System aus 6 hochspezialisierten KI-Agenten</strong>. 
          Jeder Agent besitzt eine exklusive Zuständigkeit und kommuniziert asynchron über den Redis Message-Broker. 
          Diese Architektur gewährleistet Fehlertoleranz, modulare Skalierbarkeit und latenzarme Datenverarbeitung.
        </p>
        <div className="grid grid-cols-4 gap-4 text-center">
          <StatBox number="6" label="Aktive Agenten" color="text-indigo-400" />
          <StatBox number="0ms" label="RAM-Veto Latenz" color="text-emerald-400" />
          <StatBox number="15s" label="Pulse-Intervall" color="text-blue-400" />
          <StatBox number="Live" label="Cascade-Tracking" color="text-purple-400" />
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-[#11111d] p-6 rounded-2xl border border-[#1a1a2e]">
          <div className="flex items-center gap-3 mb-4">
            <Radio className="w-5 h-5 text-emerald-400" />
            <h4 className="font-bold text-white">Echtzeit-Kommunikation</h4>
          </div>
          <ul className="space-y-2 text-sm text-slate-400">
            <li className="flex items-start gap-2">
              <span className="text-emerald-500">•</span>
              Redis Pub/Sub für Agenten-Kommandos (Start/Stop/Restart)
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-500">•</span>
              Heartbeats alle 5 Sekunden pro Agent
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-500">•</span>
              WebSocket-Streaming für Logs & Events
            </li>
          </ul>
        </div>

        <div className="bg-[#11111d] p-6 rounded-2xl border border-[#1a1a2e]">
          <div className="flex items-center gap-3 mb-4">
            <ShieldCheck className="w-5 h-5 text-yellow-400" />
            <h4 className="font-bold text-white">Sicherheits-Features</h4>
          </div>
          <ul className="space-y-2 text-sm text-slate-400">
            <li className="flex items-start gap-2">
              <span className="text-yellow-500">•</span>
              DRY_RUN-Modus: Keine echten Trades ohne explizite Freigabe
            </li>
            <li className="flex items-start gap-2">
              <span className="text-yellow-500">•</span>
              RAM-basiertes Veto-System (Zero-Latenz)
            </li>
            <li className="flex items-start gap-2">
              <span className="text-yellow-500">•</span>
              Shadow-Trading mit exakter Fee-Simulation (0.04%)
            </li>
          </ul>
        </div>
      </div>

      {/* Health Status Legend */}
      <div className="bg-[#11111d] p-6 rounded-2xl border border-[#1a1a2e]">
        <h4 className="font-bold text-white mb-4 flex items-center gap-2">
          <Activity className="w-5 h-5" />
          Agenten-Status erklärt
        </h4>
        <div className="grid grid-cols-2 gap-4">
          <StatusExplanation 
            badge={<span className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">running</span>}
            title="Agent Aktiv"
            desc="Der Agent bearbeitet gerade einen Task (z.B. 'Analyzing News' oder 'Running LLM Cascade')."
          />
          <StatusExplanation 
            badge={<span className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest bg-sky-500/10 border border-sky-500/20 text-sky-400">IDLE</span>}
            title="Wartemodus"
            desc="Der Agent ist gesund, wartet aber auf das nächste Intervall (Polling) oder neue Daten (Stream)."
          />
          <StatusExplanation 
            badge={<span className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest bg-amber-500/10 border border-amber-500/20 text-amber-500">DEGRADED</span>}
            title="Eingeschränkter Modus"
            desc="Der Agent läuft, aber mit Fallback-Mechanismen oder hoher Latenz."
          />
          <StatusExplanation 
            badge={<span className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest bg-red-500/10 border border-red-500/20 text-red-400">ERROR</span>}
            title="Fehlerzustand"
            desc="Kritischer Fehler. Der Agent pausiert kurzzeitig oder wird vom Orchestrator neu gestartet."
          />
        </div>
      </div>
    </div>
  );
}

function ArchitectureSection() {
  const agents = [
    {
      id: "ingestion",
      name: "Ingestion Agent",
      subtitle: "Daten-Sammler",
      icon: <Database className="w-6 h-6" />,
      color: "blue",
      interval: "WebSocket-Streaming",
      tech: "Binance Futures Multiplexing",
      desc: "Verbindet sich mit Binance Futures via persistenten WebSockets. Sammelt simultan: Orderbuch (L2), Kerzen (1m/5m), Funding Rates, Liquidationen. Speichert in TimescaleDB-Hypertables mit automatischer Partitionierung.",
      outputs: ["candles_1m", "orderbook_snapshots", "liquidations", "funding_rates"]
    },
    {
      id: "quant", 
      name: "Quant Agent",
      subtitle: "Mathematisches Auge",
      icon: <Activity className="w-6 h-6" />,
      color: "emerald",
      interval: "Alle 5 Sekunden",
      tech: "HFT Microstructure Analysis",
      desc: "Berechnet Order Flow Imbalance (OFI), CVD (Cumulative Volume Delta), und Liquidations-Cluster aus SQL. Nutzt Multi-Timeframe-Analysen (5m/1h) mit Indikatoren. Publiziert technische Signale an Redis.",
      outputs: ["ofi_signal", "cvd_trend", "liquidation_walls", "technical_score"]
    },
    {
      id: "context",
      name: "Context Agent",
      subtitle: "Markt-Kontext",
      icon: <Layers className="w-6 h-6" />,
      color: "cyan",
      interval: "Alle 60 Sekunden",
      tech: "Macro Data Aggregation",
      desc: "Sammelt makroökonomische Daten: Fear & Greed Index, DXY (US Dollar Index), 10Y Treasury, BTC ETF Flows, globale Liquiditätsindikatoren. Bereichert die Trading-Entscheidungen mit externem Kontext.",
      outputs: ["fear_greed", "dxy_trend", "etf_flows", "macro_score"]
    },
    {
      id: "sentiment",
      name: "Sentiment Agent",
      subtitle: "NLP-Analyse",
      icon: <Brain className="w-6 h-6" />,
      color: "purple",
      interval: "Alle 60 Sekunden",
      tech: "FinBERT + CryptoBERT + Zero-Shot",
      desc: "Nutzt lokal laufende Transformer-Modelle (ProsusAI/finbert, ElKulako/cryptobert) für Sentiment-Analyse von News-Headlines. Zero-Shot Classification filtert Rauschen (Opinion vs. Regulatory/Macro/Infrastructure).",
      outputs: ["sentiment_score", "news_classification", "bullish_bearish_ratio"]
    },
    {
      id: "risk",
      name: "Risk Agent",
      subtitle: "Konsens & Risiko",
      icon: <ShieldCheck className="w-6 h-6" />,
      color: "yellow",
      interval: "Event-getriggert",
      tech: "Multi-Faktor Konsens + Reasoning",
      desc: "Das Kontrollzentrum! Aggregiert Signale von Quant, Sentiment und Context. Befragt Ollama (deepseek-r1) für Reasoning. Prüft Konfluenz, Korrelationsrisiko, und Position-Limits. Gibt nur bei hoher Überzeugung Freigabe.",
      outputs: ["trade_decision", "position_size", "stop_loss_level", "risk_score"]
    },
    {
      id: "execution",
      name: "Execution Agent",
      subtitle: "Trade-Ausführung",
      icon: <Zap className="w-6 h-6" />,
      color: "red",
      interval: "On-Demand",
      tech: "Zero-Latency RAM-Veto",
      desc: "Führt genehmigte Trades aus. RAM-basierter Veto-Check (0ms) vor jeder Order. Shadow-Trading mit exakter 0.04% Fee-Simulation und Slippage-Tracking in BPS. Manipulationssichere Audit-Logs.",
      outputs: ["trade_executed", "shadow_pnl", "slippage_bps", "audit_trail"]
    }
  ];

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 p-6 rounded-2xl border border-indigo-500/20 mb-8">
        <p className="text-slate-400 leading-relaxed">
          Die Agenten-Pipeline folgt einer <strong className="text-indigo-400">strikten Datenfluss-Topologie</strong>: 
          Rohdaten → Analyse → Kontext → Sentiment → Risiko-Prüfung → Ausführung. 
          Jeder Agent ist ein unabhängiger Prozess innerhalb des Workers, supervised vom Orchestrator.
        </p>
      </div>

      {agents.map((agent, idx) => (
        <AgentArchitectureCard key={agent.id} agent={agent} index={idx + 1} />
      ))}

      {/* Data Flow Diagram */}
      <div className="bg-[#11111d] p-6 rounded-2xl border border-[#1a1a2e] mt-8">
        <h4 className="font-bold text-white mb-6">Datenfluss-Diagramm</h4>
        <div className="flex flex-col gap-4 text-xs">
          <FlowStep label="1. Ingestion" desc="sammelt Rohdaten von Binance → speichert in TimescaleDB" color="blue" />
          <FlowArrow />
          <FlowStep label="2. Quant + Context" desc="lesen DB → berechnen Indikatoren → publizieren an Redis" color="emerald/cyan" />
          <FlowArrow />
          <FlowStep label="3. Sentiment" desc="analysiert News parallel → publiziert Sentiment-Score" color="purple" />
          <FlowArrow />
          <FlowStep label="4. Risk Agent" desc="konsumiert alle Signale → Reasoning → Entscheidung (GO/NO-GO)" color="yellow" />
          <FlowArrow />
          <FlowStep label="5. Execution" desc="führt bei GO aus → RAM-Veto → Shadow-Trade-Logging" color="red" />
        </div>
      </div>
    </div>
  );
}

function ControlSection() {
  return (
    <div className="space-y-8">
      <div className="bg-gradient-to-r from-indigo-500/10 to-emerald-500/10 p-6 rounded-2xl border border-indigo-500/20">
        <h3 className="text-xl font-bold text-white mb-4">Agenten-Steuerung</h3>
        <p className="text-slate-400 leading-relaxed">
          Über die Agenten-Zentrale hast du <strong className="text-indigo-400">manuelle Kontrolle</strong> über jeden Agenten. 
          Diese Steuerbefehle werden via Redis Pub/Sub an den Worker gesendet und vom Orchestrator ausgeführt.
        </p>
      </div>

      {/* Control Options */}
      <div className="grid grid-cols-3 gap-6">
        <ControlCard 
          icon={<Play className="w-6 h-6 text-emerald-400" />}
          title="Online (Start)"
          desc="Startet einen gestoppten Agenten. Der Orchestrator führt setup() und run() aus."
          color="emerald"
        />
        <ControlCard 
          icon={<Square className="w-6 h-6 text-red-400" />}
          title="Offline (Stop)"
          desc="Signalisiert dem Agenten, sich sauber zu beenden. Laufende Tasks werden abgebrochen."
          color="red"
        />
        <ControlCard 
          icon={<RefreshCw className="w-6 h-6 text-indigo-400" />}
          title="System Reset"
          desc="Vollständiger Restart: teardown() → setup() → run(). Nützlich bei Fehlerzuständen."
          color="indigo"
        />
      </div>

      {/* Tabs Explanation */}
      <div className="bg-[#11111d] p-6 rounded-2xl border border-[#1a1a2e]">
        <h4 className="font-bold text-white mb-6">Interface-Tabs pro Agent</h4>
        <div className="space-y-4">
          <TabExplanation 
            icon={<MessageSquare className="w-5 h-5" />}
            title="Agent Chat"
            desc="Direkte Kommunikation mit dem Agenten via Ollama (qwen2.5:14b). Du kannst den Agenten nach seiner aktuellen Analyse, Meinung oder Entscheidungsgrundlagen fragen."
          />
          <TabExplanation 
            icon={<Settings2 className="w-5 h-5" />}
            title="Status & Control"
            desc="Zeigt Echtzeit-Metriken: Zustand (running/stopped), Operations-Zähler, Runtime, Error Score. Hier sind die Start/Stop/Reset Buttons."
          />
          <TabExplanation 
            icon={<Terminal className="w-5 h-5" />}
            title="System Logs"
            desc="Live-Streaming der Agenten-Logs via WebSocket. Zeigt DEBUG, INFO, WARNING, ERROR-Level. Filterbar nach Quelle."
          />
        </div>
      </div>

      {/* Orchestrator Behavior */}
      <div className="bg-[#11111d] p-6 rounded-2xl border border-[#1a1a2e]">
        <h4 className="font-bold text-white mb-4 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-indigo-400" />
          Orchestrator-Verhalten
        </h4>
        <ul className="space-y-3 text-sm text-slate-400">
          <li className="flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <span><strong>Supervised Execution:</strong> Jeder Agent läuft als überwachte asyncio.Task. Bei Crash wird automatisch neugestartet (max 5 Versuche).</span>
          </li>
          <li className="flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <span><strong>Startup Stages:</strong> Agenten starten in Phasen (Ingestion → Quant/Context → Risk → Execution) um Datenabhängigkeiten zu respektieren.</span>
          </li>
          <li className="flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <span><strong>Heartbeat Monitoring:</strong> Jeder Agent sendet alle 5s Vitalfunktionen an Redis. API liest diese für das Frontend.</span>
          </li>
          <li className="flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <span><strong>Graceful Degradation:</strong> Bei Teilausfällen (z.B. Ollama down) schalten Agenten in Degraded-Modus mit Fallback-Logik.</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

function TroubleshootSection() {
  return (
    <div className="space-y-8">
      <div className="bg-gradient-to-r from-red-500/10 to-orange-500/10 p-6 rounded-2xl border border-red-500/20">
        <h3 className="text-xl font-bold text-white mb-4">Fehlerdiagnose & Behebung</h3>
        <p className="text-slate-400 leading-relaxed">
          Häufige Probleme bei der Agenten-Steuerung und deren Lösungen. Bei kritischen Fehlern konsultiere die <strong className="text-red-400">System Logs</strong> im Agenten-Tab.
        </p>
      </div>

      {/* Common Issues */}
      <div className="space-y-4">
        <TroubleshootCard 
          symptom="Agent lässt sich nicht starten (bleibt 'stopped')"
          cause="Orchestrator hat den Agenten nicht registriert oder der Worker läuft nicht."
          solution="Prüfe Worker-Logs: docker logs bruno-worker. Starte Worker neu: docker restart bruno-worker."
        />
        <TroubleshootCard 
          symptom="'DEGRADED' Status im Frontend"
          cause="Ein Abhängigkeit ist nicht erreichbar (Ollama down, Binance API langsam)."
          solution="Prüfe Health-Status im Monitoring. Bei Sentiment: Prüfe ob Ollama läuft (ollama list)."
        />
        <TroubleshootCard 
          symptom="Keine Logs im 'System Logs' Tab"
          cause="WebSocket-Verbindung unterbrochen oder Log-Level zu restriktiv."
          solution="Prüfe Browser-Console. Aktualisiere die Seite. Prüfe ob Redis läuft: docker ps."
        />
        <TroubleshootCard 
          symptom="Agent stürzt immer wieder ab (Loop)"
          cause="Unbehandelter Exception in process() oder DB-Verbindung verloren."
          solution="Vollständiger Reset des Agenten. Prüfe Stacktrace in Worker-Logs."
        />
        <TroubleshootCard 
          symptom="Chat antwortet nicht / 503 Fehler"
          cause="Ollama ist nicht erreichbar oder Modell nicht geladen."
          solution="Stelle sicher dass Ollama auf Windows-Host läuft: http://localhost:11434. Lade Modell: ollama pull qwen2.5:14b."
        />
      </div>

      {/* Quick Commands */}
      <div className="bg-[#11111d] p-6 rounded-2xl border border-[#1a1a2e]">
        <h4 className="font-bold text-white mb-4 flex items-center gap-2">
          <Terminal className="w-5 h-5" />
          Nützliche Diagnose-Kommandos (PowerShell)
        </h4>
        <div className="space-y-2 font-mono text-xs">
          <CodeLine code="# Worker-Logs prüfen" />
          <CodeLine code="docker logs bruno-worker -f --tail 100" />
          <div className="h-2" />
          <CodeLine code="# Agenten-Status API abfragen" />
          <CodeLine code='Invoke-RestMethod -Uri "http://localhost:8000/api/v1/agents/status" | ConvertTo-Json' />
          <div className="h-2" />
          <CodeLine code="# Ollama Status prüfen" />
          <CodeLine code="Invoke-RestMethod -Uri 'http://localhost:11434/api/tags'" />
          <div className="h-2" />
          <CodeLine code="# Redis-Container Health" />
          <CodeLine code="docker exec bruno-redis redis-cli ping" />
        </div>
      </div>

      {/* Support */}
      <div className="bg-indigo-500/5 p-6 rounded-2xl border border-indigo-500/20">
        <div className="flex items-start gap-4">
          <Info className="w-6 h-6 text-indigo-400 shrink-0 mt-1" />
          <div>
            <h4 className="font-bold text-white mb-2">Wichtige Hinweise</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>• Ein gestoppter Ingestion Agent führt zu Datenlücken für alle nachgelagerten Agenten.</li>
              <li>• Der Risk Agent ohne Sentiment/Quant fällt auf konservative Heuristiken zurück.</li>
              <li>• DRY_RUN-Modus ist immer aktiv bis explizit in den Einstellungen deaktiviert.</li>
              <li>• Restart eines Agenten bewahrt seinen Zustand (außer bei fatalen Fehlern).</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== HELPER COMPONENTS ====================

function NavButton({ active, onClick, icon, label }: any) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-6 py-4 text-[11px] font-bold uppercase tracking-widest transition-all relative
        ${active ? "text-indigo-400 bg-indigo-500/10" : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/30"}
      `}
    >
      {icon}
      {label}
      {active && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500" />}
    </button>
  );
}

function StatBox({ number, label, color }: any) {
  return (
    <div className="bg-black/30 p-4 rounded-xl">
      <div className={`text-2xl font-bold font-mono ${color}`}>{number}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}

function StatusExplanation({ badge, title, desc }: any) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5">{badge}</div>
      <div>
        <div className="text-sm font-semibold text-white mb-1">{title}</div>
        <div className="text-xs text-slate-500">{desc}</div>
      </div>
    </div>
  );
}

function AgentArchitectureCard({ agent, index }: any) {
  const colors: any = {
    blue: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400" },
    emerald: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400" },
    cyan: { bg: "bg-cyan-500/10", border: "border-cyan-500/30", text: "text-cyan-400" },
    purple: { bg: "bg-purple-500/10", border: "border-purple-500/30", text: "text-purple-400" },
    yellow: { bg: "bg-yellow-500/10", border: "border-yellow-500/30", text: "text-yellow-400" },
    red: { bg: "bg-red-500/10", border: "border-red-500/30", text: "text-red-400" },
    "emerald/cyan": { bg: "bg-gradient-to-r from-emerald-500/10 to-cyan-500/10", border: "border-indigo-500/30", text: "text-indigo-400" }
  };
  const c = colors[agent.color] || colors.blue;

  return (
    <div className={`p-6 rounded-2xl border ${c.border} ${c.bg}`}>
      <div className="flex items-start gap-4">
        <div className={`p-3 bg-black/30 rounded-xl ${c.text}`}>
          {agent.icon}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-xs font-mono text-slate-500">#{index}</span>
            <h4 className={`font-bold text-lg ${c.text}`}>{agent.name}</h4>
            <span className="text-xs text-slate-500">— {agent.subtitle}</span>
          </div>
          
          <div className="grid grid-cols-2 gap-4 mb-4 text-xs">
            <div className="flex items-center gap-2">
              <Clock className="w-3 h-3 text-slate-500" />
              <span className="text-slate-400">{agent.interval}</span>
            </div>
            <div className="flex items-center gap-2">
              <Cpu className="w-3 h-3 text-slate-500" />
              <span className="text-slate-400">{agent.tech}</span>
            </div>
          </div>

          <p className="text-sm text-slate-400 leading-relaxed mb-4">
            {agent.desc}
          </p>

          <div className="flex flex-wrap gap-2">
            {agent.outputs.map((output: string) => (
              <span key={output} className="px-2 py-1 bg-black/30 rounded text-[10px] font-mono text-slate-500 border border-slate-800">
                {output}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function FlowStep({ label, desc, color }: any) {
  const colorClasses: any = {
    blue: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    emerald: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    cyan: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
    purple: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    yellow: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    red: "bg-red-500/20 text-red-400 border-red-500/30",
    "emerald/cyan": "bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 text-indigo-400 border-indigo-500/30"
  };
  
  return (
    <div className={`p-4 rounded-xl border ${colorClasses[color]} flex items-center gap-4`}>
      <span className="font-bold text-sm shrink-0">{label}</span>
      <span className="text-slate-400 text-xs">{desc}</span>
    </div>
  );
}

function FlowArrow() {
  return (
    <div className="flex justify-center">
      <ArrowRight className="w-5 h-5 text-slate-600 rotate-90" />
    </div>
  );
}

function ControlCard({ icon, title, desc, color }: any) {
  const bgColors: any = {
    emerald: "bg-emerald-500/5 border-emerald-500/20",
    red: "bg-red-500/5 border-red-500/20",
    indigo: "bg-indigo-500/5 border-indigo-500/20"
  };
  
  return (
    <div className={`p-6 rounded-2xl border ${bgColors[color]}`}>
      <div className="mb-4">{icon}</div>
      <h4 className="font-bold text-white mb-2">{title}</h4>
      <p className="text-xs text-slate-400 leading-relaxed">{desc}</p>
    </div>
  );
}

function TabExplanation({ icon, title, desc }: any) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-xl bg-black/20">
      <div className="p-2 bg-slate-800 rounded-lg text-slate-400">
        {icon}
      </div>
      <div>
        <h5 className="font-semibold text-white text-sm mb-1">{title}</h5>
        <p className="text-xs text-slate-500">{desc}</p>
      </div>
    </div>
  );
}

function TroubleshootCard({ symptom, cause, solution }: any) {
  return (
    <div className="bg-[#11111d] p-6 rounded-2xl border border-[#1a1a2e]">
      <div className="flex items-start gap-3 mb-3">
        <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
        <h4 className="font-semibold text-white">{symptom}</h4>
      </div>
      <div className="ml-8 space-y-2">
        <div className="text-sm">
          <span className="text-slate-500">Ursache: </span>
          <span className="text-slate-400">{cause}</span>
        </div>
        <div className="text-sm">
          <span className="text-emerald-500">Lösung: </span>
          <span className="text-slate-400">{solution}</span>
        </div>
      </div>
    </div>
  );
}

function CodeLine({ code }: any) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-slate-600 select-none">&gt;</span>
      <span className="text-emerald-400">{code}</span>
    </div>
  );
}

