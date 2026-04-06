"use client";

import { useState, useEffect } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Brain,
  Cpu,
  Database,
  Globe,
  Layers,
  Lock,
  Newspaper,
  Radio,
  Server,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
  ChevronRight,
  ChevronDown,
  GitBranch,
  Terminal,
  Wifi,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Wallet,
  LineChart,
  Scale,
  Radar,
  Microscope,
} from "lucide-react";

// Types for system state
interface SystemState {
  stage1_ingestion: boolean;
  stage2_analysis: boolean;
  stage3_quant: boolean;
  stage4_risk: boolean;
  stage5_execution: boolean;
  bybit_connected: boolean;
  news_active: boolean;
  grss_available: boolean;
  last_update: string;
}

// Section types
interface Section {
  id: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  shortDesc: string;
}

const SECTIONS: Section[] = [
  { id: "overview", title: "System-Übersicht", icon: Radar, shortDesc: "Bruno v8.0 Architektur" },
  { id: "pipeline", title: "Agent-Pipeline", icon: GitBranch, shortDesc: "5-Stufen-Kaskade" },
  { id: "bybit", title: "Bybit V5 Core", icon: Database, shortDesc: "Single Source of Truth" },
  { id: "news", title: "News-System", icon: Newspaper, shortDesc: "Privacy-First Ingestion" },
  { id: "scoring", title: "Composite Scoring", icon: Scale, shortDesc: "Deterministische Logik" },
  { id: "modules", title: "Module", icon: Layers, shortDesc: "Alle Komponenten" },
  { id: "decisions", title: "Entscheidungs-Kaskade", icon: Target, shortDesc: "Von Daten zu Trade" },
  { id: "safety", title: "Sicherheit", icon: Shield, shortDesc: "6 Hard Vetos" },
];

// Component: Live Status Indicator
function LiveIndicator({ active, label }: { active: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`h-2 w-2 rounded-full ${active ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`} />
      <span className={`text-xs ${active ? "text-emerald-400" : "text-slate-500"}`}>{label}</span>
    </div>
  );
}

// Component: Compact Metric Card
function MetricCard({ 
  label, 
  value, 
  subtext, 
  trend 
}: { 
  label: string; 
  value: string; 
  subtext?: string; 
  trend?: "up" | "down" | "neutral";
}) {
  const trendColor = trend === "up" ? "text-emerald-400" : trend === "down" ? "text-rose-400" : "text-slate-400";
  return (
    <div className="rounded-xl border border-[#1a1a2e] bg-[#080810] p-3">
      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className={`text-lg font-bold ${trendColor} mt-1`}>{value}</div>
      {subtext && <div className="text-[10px] text-slate-600 mt-1">{subtext}</div>}
    </div>
  );
}

// Component: Pipeline Stage
function PipelineStage({
  stage,
  title,
  agents,
  outputs,
  active,
  delay,
}: {
  stage: number;
  title: string;
  agents: string[];
  outputs: string[];
  active: boolean;
  delay: string;
}) {
  return (
    <div className={`relative rounded-xl border p-4 transition-all duration-300 ${
      active 
        ? "border-indigo-500/50 bg-indigo-950/10" 
        : "border-[#1a1a2e] bg-[#080810]"
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
            active ? "bg-indigo-500 text-white" : "bg-[#1a1a2e] text-slate-500"
          }`}>
            {stage}
          </span>
          <span className="text-sm font-medium text-slate-200">{title}</span>
        </div>
        <span className="text-[10px] text-slate-500">{delay}</span>
      </div>
      
      <div className="space-y-2">
        <div className="flex flex-wrap gap-1">
          {agents.map((agent) => (
            <span key={agent} className="text-[10px] px-2 py-0.5 rounded bg-[#0c0c18] text-slate-400 border border-[#1a1a2e]">
              {agent}
            </span>
          ))}
        </div>
        
        <div className="pt-2 border-t border-[#1a1a2e]/50">
          <div className="text-[10px] text-slate-500 mb-1">Redis Output:</div>
          <div className="flex flex-wrap gap-1">
            {outputs.map((output) => (
              <code key={output} className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/30 text-emerald-400/70 font-mono">
                {output}
              </code>
            ))}
          </div>
        </div>
      </div>
      
      {stage < 5 && (
        <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 text-slate-600">
          <ArrowRight className="w-4 h-4 rotate-90" />
        </div>
      )}
    </div>
  );
}

// Component: Expandable Detail Section
function DetailSection({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-[#1a1a2e] rounded-xl overflow-hidden bg-[#080810]">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-[#0c0c18] transition-colors"
      >
        <span className="text-sm font-medium text-slate-300">{title}</span>
        <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="p-4 pt-0 border-t border-[#1a1a2e]">{children}</div>}
    </div>
  );
}

// Component: Data Flow Visualization
function DataFlowViz() {
  return (
    <div className="rounded-xl border border-[#1a1a2e] bg-[#080810] p-4">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-slate-500">Live Datenfluss</span>
        <LiveIndicator active={true} label="Echtzeit" />
      </div>
      
      <div className="space-y-3">
        {/* Bybit WebSocket */}
        <div className="flex items-center gap-3 p-2 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
          <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
            <Zap className="w-4 h-4 text-orange-400" />
          </div>
          <div className="flex-1">
            <div className="text-xs font-medium text-slate-300">Bybit V5 WebSocket</div>
            <div className="text-[10px] text-slate-500">kline.1 · publicTrade · orderbook.50</div>
          </div>
          <div className="text-[10px] text-emerald-400">● Live</div>
        </div>
        
        {/* RSS News */}
        <div className="flex items-center gap-3 p-2 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Newspaper className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex-1">
            <div className="text-xs font-medium text-slate-300">RSS News Feeds</div>
            <div className="text-[10px] text-slate-500">CoinDesk · Cointelegraph · Decrypt</div>
          </div>
          <div className="text-[10px] text-emerald-400">● 49 Items</div>
        </div>
        
        {/* Processing */}
        <div className="flex items-center gap-3 p-2 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center">
            <Brain className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="flex-1">
            <div className="text-xs font-medium text-slate-300">Composite Scoring</div>
            <div className="text-[10px] text-slate-500">TA × 0.4 + Liq × 0.25 + Flow × 0.2 + Macro × 0.15</div>
          </div>
          <div className="text-[10px] text-slate-500">60s Zyklus</div>
        </div>
      </div>
    </div>
  );
}

// Main Content Components
function OverviewSection() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="System" value="v8.0" subtext="Privacy-First News & Bybit Core" />
        <MetricCard label="Pipeline" value="5 Stages" subtext="Deterministisch · 60s Zyklus" trend="neutral" />
        <MetricCard label="Modus" value="Paper Only" subtext="Hard-Locked · Kein Live-Riskio" trend="neutral" />
        <MetricCard label="Datenquellen" value="Bybit + RSS" subtext="Bybit V5 WS · RSS/Reddit News" trend="up" />
      </div>

      <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-950/10">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <span className="text-sm font-medium text-indigo-400">Was ist neu in v8.0?</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-slate-300"><strong>Bybit V5 WebSocket</strong> als Single Source of Truth</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-slate-300"><strong>Privacy-First News</strong> via RSS (keine API-Keys nötig)</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-slate-300"><strong>Deterministisches Scoring</strong> - Kein LLM im Live-Pfad</span>
            </div>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-slate-300"><strong>Deepseek API</strong> nur für Post-Trade Analyse</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-slate-300"><strong>Zero-Tolerance</strong> für Heuristiken</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-slate-300"><strong>Mathematische Reinheit</strong> in allen Berechnungen</span>
            </div>
          </div>
        </div>
      </div>

      <DataFlowViz />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <h3 className="text-sm font-medium text-slate-300 mb-3">Architektur-Prinzipien</h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-start gap-2">
              <Target className="w-4 h-4 text-indigo-400 mt-0.5" />
              <div>
                <span className="text-slate-200 font-medium">Deterministisch</span>
                <p className="text-xs text-slate-500">Gleiche Inputs = Gleiche Outputs. Keine Zufälligkeit, reproduzierbare Entscheidungen.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Shield className="w-4 h-4 text-indigo-400 mt-0.5" />
              <div>
                <span className="text-slate-200 font-medium">Risiko-zuerst</span>
                <p className="text-xs text-slate-500">6 Hard Vetos schützen das Kapital vor jeder Trade-Entscheidung.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Radio className="w-4 h-4 text-indigo-400 mt-0.5" />
              <div>
                <span className="text-slate-200 font-medium">Transparenz</span>
                <p className="text-xs text-slate-500">Jeder Schritt sichtbar: Von Rohdaten bis zum Entscheidungs-Log.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <h3 className="text-sm font-medium text-slate-300 mb-3">Technologie-Stack</h3>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 rounded bg-[#0c0c18]">
              <span className="text-indigo-400 font-medium">Backend</span>
              <p className="text-slate-500">FastAPI · SQLAlchemy · Redis</p>
            </div>
            <div className="p-2 rounded bg-[#0c0c18]">
              <span className="text-indigo-400 font-medium">Frontend</span>
              <p className="text-slate-500">Next.js 14 · TypeScript · Tailwind</p>
            </div>
            <div className="p-2 rounded bg-[#0c0c18]">
              <span className="text-indigo-400 font-medium">Datenbanken</span>
              <p className="text-slate-500">PostgreSQL · TimescaleDB · Redis</p>
            </div>
            <div className="p-2 rounded bg-[#0c0c18]">
              <span className="text-indigo-400 font-medium">Extern</span>
              <p className="text-slate-500">Bybit V5 · RSS · Deepseek API</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PipelineSection() {
  const [systemState] = useState<SystemState>({
    stage1_ingestion: true,
    stage2_analysis: true,
    stage3_quant: true,
    stage4_risk: true,
    stage5_execution: true,
    bybit_connected: true,
    news_active: true,
    grss_available: true,
    last_update: new Date().toISOString(),
  });

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
        <p className="text-sm text-slate-300">
          Bruno v8.0 arbeitet mit einer <strong className="text-white">5-stufigen Pipeline</strong>. 
          Jede Stufe verarbeitet Daten und speichert Ergebnisse in Redis für maximale Transparenz. 
          Die Pipeline läuft alle 60 Sekunden oder bei Liquidations-Events (Sweeps).
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <PipelineStage
          stage={1}
          title="Ingestion"
          agents={["Bybit V5 WS", "NewsIngestionService"]}
          outputs={["market:ticker", "market:cvd", "bruno:news:rss", "market:orderbook"]}
          active={systemState.stage1_ingestion}
          delay="Echtzeit"
        />
        <PipelineStage
          stage={2}
          title="Analyse & Kontext"
          agents={["TechnicalAnalysisAgent", "ContextAgent", "Sentiment"]}
          outputs={["bruno:ta:snapshot", "bruno:context:grss", "bruno:sentiment:aggregate"]}
          active={systemState.stage2_analysis}
          delay="60s"
        />
        <PipelineStage
          stage={3}
          title="Quant"
          agents={["QuantAgentV4", "LiquidityEngine", "CompositeScorer"]}
          outputs={["bruno:quant:micro", "bruno:decisions:feed", "bruno:pubsub:signals"]}
          active={systemState.stage3_quant}
          delay="60s"
        />
        <PipelineStage
          stage={4}
          title="Risk"
          agents={["RiskAgent"]}
          outputs={["bruno:veto:state", "bruno:risk:daily_block"]}
          active={systemState.stage4_risk}
          delay="0ms (RAM)"
        />
        <PipelineStage
          stage={5}
          title="Execution"
          agents={["ExecutionAgentV4", "PositionTracker"]}
          outputs={["bruno:portfolio:state", "bruno:positions:BTCUSDT"]}
          active={systemState.stage5_execution}
          delay="<100ms"
        />
      </div>

      <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
        <h3 className="text-sm font-medium text-slate-300 mb-4">Redis Key Übersicht</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 text-xs font-mono">
          <div className="p-2 rounded bg-[#0c0c18] border border-[#1a1a2e]">
            <span className="text-emerald-400">market:cvd:cumulative</span>
            <p className="text-slate-500 mt-1">Bybit CVD (Taker-basiert)</p>
          </div>
          <div className="p-2 rounded bg-[#0c0c18] border border-[#1a1a2e]">
            <span className="text-emerald-400">bruno:context:grss</span>
            <p className="text-slate-500 mt-1">Global Risk Score v3</p>
          </div>
          <div className="p-2 rounded bg-[#0c0c18] border border-[#1a1a2e]">
            <span className="text-emerald-400">bruno:decisions:feed</span>
            <p className="text-slate-500 mt-1">12h History (144 Einträge)</p>
          </div>
          <div className="p-2 rounded bg-[#0c0c18] border border-[#1a1a2e]">
            <span className="text-emerald-400">bruno:veto:state</span>
            <p className="text-slate-500 mt-1">Risk Veto Status</p>
          </div>
          <div className="p-2 rounded bg-[#0c0c18] border border-[#1a1a2e]">
            <span className="text-emerald-400">bruno:portfolio:state</span>
            <p className="text-slate-500 mt-1">Paper Trading Kapital</p>
          </div>
          <div className="p-2 rounded bg-[#0c0c18] border border-[#1a1a2e]">
            <span className="text-emerald-400">bruno:news:rss:items</span>
            <p className="text-slate-500 mt-1">Deduplizierte News (SHA256)</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function BybitSection() {
  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-orange-500/30 bg-orange-950/10">
        <div className="flex items-center gap-2 mb-2">
          <Zap className="w-5 h-5 text-orange-400" />
          <span className="text-lg font-bold text-orange-400">Single Source of Truth</span>
        </div>
        <p className="text-sm text-slate-300">
          Bybit V5 WebSocket ist die <strong className="text-white">exklusive Datenquelle</strong> für alle Marktdaten. 
          Keine Binance REST Calls mehr - mathematische Reinheit durch dedizierte WebSocket-Streams.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-orange-400" />
            <span className="text-sm font-medium text-slate-300">kline.1.BTCUSDT</span>
          </div>
          <p className="text-xs text-slate-500">1-Minuten-Kerzen für Technical Analysis. OHLCV + Volumen in Echtzeit.</p>
        </div>
        <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="w-4 h-4 text-orange-400" />
            <span className="text-sm font-medium text-slate-300">publicTrade.BTCUSDT</span>
          </div>
          <p className="text-xs text-slate-500">Trades für CVD-Berechnung. Taker-Mathematik mit execId-Deduplizierung.</p>
        </div>
        <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="flex items-center gap-2 mb-3">
            <Database className="w-4 h-4 text-orange-400" />
            <span className="text-sm font-medium text-slate-300">orderbook.50.BTCUSDT</span>
          </div>
          <p className="text-xs text-slate-500">50-Level Orderbook für OFI (Order Flow Imbalance) Berechnung.</p>
        </div>
      </div>

      <DetailSection title="Institutionelle CVD-Mathematik" defaultOpen>
        <div className="space-y-3 text-sm">
          <p className="text-slate-300">
            CVD (Cumulative Volume Delta) wird direkt aus Bybit <code className="text-orange-400">publicTrade</code> Streams berechnet:
          </p>
          <pre className="bg-[#0c0c18] p-3 rounded-lg text-xs text-slate-400 overflow-x-auto">
{`# Bybit side-Field (institutionell korrekt)
if side == "Buy":
    # Taker Buy: Aggressives Kaufvolumen
    cvd_cumulative += volume
elif side == "Sell":
    # Taker Sell: Aggressives Verkaufsvolumen  
    cvd_cumulative -= volume

# Deduplizierung mit execId (maxlen=10000)
if exec_id not in last_exec_ids:
    last_exec_ids.append(exec_id)`}
          </pre>
          <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-950/20 border border-emerald-800/50">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5" />
            <p className="text-xs text-slate-400">
              <strong className="text-emerald-400">Keine close &gt; open Heuristik.</strong> 
              Traditionelle CVD-Berechnungen verwenden oft die Heuristik "close &gt; open = Buy Pressure", 
              was technisch falsch ist. Bybit liefert das echte Taker-Side Field.
            </p>
          </div>
        </div>
      </DetailSection>

      <DetailSection title="VWAP & VPOC mit täglichen Resets">
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
              <span className="text-indigo-400 font-medium">VWAP Reset</span>
              <p className="text-xs text-slate-500 mt-1">Exakt um 00:00:00 UTC. Kumulatives Volumen und typischer Preis werden zurückgesetzt.</p>
            </div>
            <div className="p-3 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
              <span className="text-indigo-400 font-medium">VPOC (Volume Point of Control)</span>
              <p className="text-xs text-slate-500 mt-1">10-Dollar-Bucket-Rounding. Täglicher Reset mit institutioneller Präzision.</p>
            </div>
          </div>
        </div>
      </DetailSection>
    </div>
  );
}

function NewsSection() {
  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-950/10">
        <div className="flex items-center gap-2 mb-2">
          <Newspaper className="w-5 h-5 text-blue-400" />
          <span className="text-lg font-bold text-blue-400">Privacy-First News</span>
        </div>
        <p className="text-sm text-slate-300">
          Bruno v8.0 verwendet <strong className="text-white">RSS-Feeds als primäre Quelle</strong> - 
          keine API-Keys nötig, keine Tracking-Header, maximale Privatsphäre. 
          SHA256-Deduplizierung verhindert Double-Counting.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-emerald-400">Tier 1: RSS Feeds</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">Primär</span>
          </div>
          <ul className="space-y-1 text-xs text-slate-400">
            <li>• CoinDesk</li>
            <li>• Cointelegraph</li>
            <li>• Decrypt</li>
          </ul>
          <div className="mt-3 pt-2 border-t border-[#1a1a2e]">
            <span className="text-[10px] text-slate-500">30s Intervall · BTC-Filter aktiv</span>
          </div>
        </div>

        <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-amber-400">Tier 2: Reddit</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">Sekundär</span>
          </div>
          <ul className="space-y-1 text-xs text-slate-400">
            <li>• r/Bitcoin Hot Posts</li>
            <li>• JSON API (kein Auth)</li>
            <li>• Community Sentiment</li>
          </ul>
          <div className="mt-3 pt-2 border-t border-[#1a1a2e]">
            <span className="text-[10px] text-slate-500">60s Intervall · JSON Endpoint</span>
          </div>
        </div>

        <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-400">Tier 3: APIs</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-slate-700 text-slate-400">Fallback</span>
          </div>
          <ul className="space-y-1 text-xs text-slate-400">
            <li>• CryptoPanic API</li>
            <li>• Free-Crypto-News</li>
            <li>• (Zero-Trust Defensive)</li>
          </ul>
          <div className="mt-3 pt-2 border-t border-[#1a1a2e]">
            <span className="text-[10px] text-slate-500">120s Intervall · Fallback-Modus</span>
          </div>
        </div>
      </div>

      <DetailSection title="SHA256 Deduplizierung" defaultOpen>
        <div className="space-y-3 text-sm">
          <p className="text-slate-300">
            Jeder News-Artikel wird anhand von SHA256-Hash dedupliziert. 
            Rolling deque mit maxlen=3000 verhindert Memory-Bloat:
          </p>
          <pre className="bg-[#0c0c18] p-3 rounded-lg text-xs text-slate-400 overflow-x-auto">
{`# SHA256 Deduplizierung
article_hash = hashlib.sha256(
    (title + source + str(timestamp)).encode()
).hexdigest()

if article_hash not in seen_hashes:  # deque maxlen=3000
    seen_hashes.append(article_hash)
    process_article()`}
          </pre>
          <p className="text-xs text-slate-500">
            BTC-Filter: Nur Artikel mit "BTC" oder "Bitcoin" (case-insensitive) werden verarbeitet.
          </p>
        </div>
      </DetailSection>

      <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Sentiment-Analyse Pipeline</h3>
        <div className="flex items-center gap-2 text-xs">
          <div className="flex-1 p-2 rounded bg-[#0c0c18] text-center">
            <span className="text-slate-500">Rohtext</span>
          </div>
          <ArrowRight className="w-3 h-3 text-slate-600" />
          <div className="flex-1 p-2 rounded bg-[#0c0c18] text-center">
            <span className="text-blue-400">FinBERT</span>
          </div>
          <ArrowRight className="w-3 h-3 text-slate-600" />
          <div className="flex-1 p-2 rounded bg-[#0c0c18] text-center">
            <span className="text-blue-400">CryptoBERT</span>
          </div>
          <ArrowRight className="w-3 h-3 text-slate-600" />
          <div className="flex-1 p-2 rounded bg-emerald-950/30 text-center">
            <span className="text-emerald-400">Score (-1 bis +1)</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ScoringSection() {
  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-950/10">
        <div className="flex items-center gap-2 mb-2">
          <Scale className="w-5 h-5 text-indigo-400" />
          <span className="text-lg font-bold text-indigo-400">Deterministisches Scoring</span>
        </div>
        <p className="text-sm text-slate-300">
          Bruno v8.0 verwendet <strong className="text-white">kein LLM im Live-Trading-Pfad</strong>. 
          Die Entscheidung ist 100% deterministisch: Composite Score = (TA × w_TA) + (Liq × w_Liq) + (Flow × w_Flow) + (Macro × w_Macro).
          Deepseek API wird nur für Post-Trade-Analysen verwendet.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="text-[10px] text-slate-500 mb-1">TA Score</div>
          <div className="text-xl font-bold text-indigo-400">-25 bis +25</div>
          <div className="text-[10px] text-slate-600 mt-1">MTF Alignment · Pattern</div>
        </div>
        <div className="p-3 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="text-[10px] text-slate-500 mb-1">Liq Score</div>
          <div className="text-xl font-bold text-purple-400">-25 bis +25</div>
          <div className="text-[10px] text-slate-600 mt-1">Sweep Detection · Walls</div>
        </div>
        <div className="p-3 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="text-[10px] text-slate-500 mb-1">Flow Score</div>
          <div className="text-xl font-bold text-amber-400">-25 bis +25</div>
          <div className="text-[10px] text-slate-600 mt-1">CVD · OFI · OI Delta</div>
        </div>
        <div className="p-3 rounded-xl border border-[#1a1a2e] bg-[#080810]">
          <div className="text-[10px] text-slate-500 mb-1">Macro Score</div>
          <div className="text-xl font-bold text-emerald-400">0 bis 100</div>
          <div className="text-[10px] text-slate-600 mt-1">GRSS v3</div>
        </div>
      </div>

      <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
        <h3 className="text-sm font-medium text-slate-300 mb-4">Regime-Adaptive Gewichtung</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-[#1a1a2e]">
                <th className="text-left p-2">Regime</th>
                <th className="text-center p-2">TA</th>
                <th className="text-center p-2">Liq</th>
                <th className="text-center p-2">Flow</th>
                <th className="text-center p-2">Macro</th>
                <th className="text-left p-2">Threshold</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-b border-[#1a1a2e]/50">
                <td className="p-2 font-medium text-emerald-400">trending_bull</td>
                <td className="p-2 text-center">50%</td>
                <td className="p-2 text-center">15%</td>
                <td className="p-2 text-center">20%</td>
                <td className="p-2 text-center">15%</td>
                <td className="p-2 text-emerald-400">45</td>
              </tr>
              <tr className="border-b border-[#1a1a2e]/50">
                <td className="p-2 font-medium text-amber-400">ranging</td>
                <td className="p-2 text-center">40%</td>
                <td className="p-2 text-center">25%</td>
                <td className="p-2 text-center">20%</td>
                <td className="p-2 text-center">15%</td>
                <td className="p-2 text-amber-400">55</td>
              </tr>
              <tr className="border-b border-[#1a1a2e]/50">
                <td className="p-2 font-medium text-rose-400">bear</td>
                <td className="p-2 text-center">50%</td>
                <td className="p-2 text-center">15%</td>
                <td className="p-2 text-center">20%</td>
                <td className="p-2 text-center">15%</td>
                <td className="p-2 text-rose-400">50</td>
              </tr>
              <tr>
                <td className="p-2 font-medium text-purple-400">high_vola</td>
                <td className="p-2 text-center">40%</td>
                <td className="p-2 text-center">20%</td>
                <td className="p-2 text-center">20%</td>
                <td className="p-2 text-center">20%</td>
                <td className="p-2 text-purple-400">60</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <DetailSection title="GRSS v3 (Global Risk Sentiment Score)" defaultOpen>
        <div className="space-y-3 text-sm">
          <p className="text-slate-300">GRSS v3 verwendet 4 gewichtete Sub-Scores statt 25 additiver Terme:</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
              <span className="text-indigo-400 font-medium">1. Derivatives (40%)</span>
              <ul className="text-xs text-slate-500 mt-1 space-y-0.5">
                <li>• Funding Rate (Binance)</li>
                <li>• OI-Delta + Preis-Richtung</li>
                <li>• Put/Call Ratio (Deribit)</li>
                <li>• Max Pain (15% Gewichtung)</li>
              </ul>
            </div>
            <div className="p-3 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
              <span className="text-indigo-400 font-medium">2. Institutional (20%)</span>
              <ul className="text-xs text-slate-500 mt-1 space-y-0.5">
                <li>• ETF Flows (Farside)</li>
                <li>• OI-Trend 7d</li>
                <li>• Stablecoin Delta</li>
              </ul>
            </div>
            <div className="p-3 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
              <span className="text-indigo-400 font-medium">3. Sentiment (20%)</span>
              <ul className="text-xs text-slate-500 mt-1 space-y-0.5">
                <li>• Fear & Greed Index</li>
                <li>• LLM News Sentiment</li>
                <li>• Social Metrics</li>
              </ul>
            </div>
            <div className="p-3 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
              <span className="text-indigo-400 font-medium">4. Macro (20%)</span>
              <ul className="text-xs text-slate-500 mt-1 space-y-0.5">
                <li>• VIX (CBOE CSV)</li>
                <li>• NDX Trend (Yahoo)</li>
                <li>• 10Y Yields (FRED)</li>
                <li>• M2 Money Supply</li>
              </ul>
            </div>
          </div>
        </div>
      </DetailSection>

      <DetailSection title="Adaptive Thresholds">
        <div className="space-y-3 text-sm">
          <p className="text-slate-300">Thresholds passen sich automatisch an Marktbedingungen an:</p>
          <div className="space-y-2">
            <div className="flex items-center justify-between p-2 rounded bg-[#0c0c18]">
              <span className="text-slate-400">Basis-Threshold (Regime)</span>
              <span className="text-indigo-400 font-mono">45-60</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-[#0c0c18]">
              <span className="text-slate-400">ATR Multiplier</span>
              <span className="text-indigo-400 font-mono">× 0.8 - 1.2</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-[#0c0c18]">
              <span className="text-slate-400">Sweep-Bonus</span>
              <span className="text-emerald-400 font-mono">-15 Punkte</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-[#0c0c18]">
              <span className="text-slate-400">Event Guard (FOMC/CPI/NFP)</span>
              <span className="text-amber-400 font-mono">× 1.3 - 1.5</span>
            </div>
          </div>
        </div>
      </DetailSection>
    </div>
  );
}

function ModulesSection() {
  const modules = [
    {
      name: "IngestionAgent",
      icon: Database,
      color: "orange",
      desc: "Bybit V5 WebSocket + News Ingestion",
      details: [
        "kline.1.BTCUSDT Stream",
        "publicTrade.BTCUSDT (CVD)",
        "orderbook.50.BTCUSDT (OFI)",
        "RSS News (Tier 1-3)",
        "SHA256 Deduplizierung",
      ],
    },
    {
      name: "TechnicalAnalysisAgent",
      icon: LineChart,
      color: "indigo",
      desc: "MTF Analyse + Pattern Erkennung",
      details: [
        "Multi-Timeframe (1m, 5m, 1h)",
        "Support/Resistance Levels",
        "VWAP / VPOC (daily reset)",
        "MTF Filter (aligned/unaligned)",
        "Trend Strength Berechnung",
      ],
    },
    {
      name: "ContextAgent",
      icon: Globe,
      color: "emerald",
      desc: "GRSS v3 + Makro-Kontext",
      details: [
        "4 Sub-Scores (Derivatives, Inst., Sentiment, Macro)",
        "Max Pain Integration (15%)",
        "VIX, NDX, 10Y Yields, M2",
        "Funding Divergenz Bybit/OKX",
        "Regime Detection (2-Bestätigungen)",
      ],
    },
    {
      name: "QuantAgentV4",
      icon: Cpu,
      color: "purple",
      desc: "Composite Scoring + Microstruktur",
      details: [
        "Order Flow Imbalance (OFI)",
        "CVD (Taker-basiert)",
        "VAMP (Volume-Weighted Price)",
        "Liquidity Engine (Walls, Sweeps)",
        "CompositeScorer (deterministisch)",
      ],
    },
    {
      name: "RiskAgent",
      icon: Shield,
      color: "rose",
      desc: "6 Hard Vetos + Daily Limits",
      details: [
        "Data Gap Veto",
        "Stale Context Veto",
        "VIX > 45 Veto",
        "Daily Drawdown (3% / 3 losses)",
        "Death Zone (GRSS < 20)",
        "0ms RAM-Check",
      ],
    },
    {
      name: "ExecutionAgentV4",
      icon: Zap,
      color: "amber",
      desc: "Paper Trading + Slippage Protection",
      details: [
        "Bybit Demo API",
        "Slippage Protection (0.1% max)",
        "Limit/Market Order Routing",
        "Breakeven Stop (SL → Entry + 0.1%)",
        "Deepseek Post-Trade Analysis",
      ],
    },
  ];

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
        <p className="text-sm text-slate-300">
          Bruno besteht aus <strong className="text-white">6 spezialisierten Agenten</strong>, 
          die in einer deterministischen Pipeline zusammenarbeiten. 
          Jeder Agent hat eine klare Verantwortung und schreibt seine Ergebnisse in Redis.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {modules.map((mod) => {
          const Icon = mod.icon;
          const colorMap: Record<string, string> = {
            orange: "text-orange-400 bg-orange-500/10 border-orange-500/30",
            indigo: "text-indigo-400 bg-indigo-500/10 border-indigo-500/30",
            emerald: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
            purple: "text-purple-400 bg-purple-500/10 border-purple-500/30",
            rose: "text-rose-400 bg-rose-500/10 border-rose-500/30",
            amber: "text-amber-400 bg-amber-500/10 border-amber-500/30",
          };
          return (
            <div key={mod.name} className={`rounded-xl border p-4 ${colorMap[mod.color]}`}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className="w-5 h-5" />
                <span className="font-medium">{mod.name}</span>
              </div>
              <p className="text-xs opacity-80 mb-3">{mod.desc}</p>
              <ul className="space-y-1 text-[10px] opacity-70">
                {mod.details.map((d, i) => (
                  <li key={i}>• {d}</li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
        <h3 className="text-sm font-medium text-slate-300 mb-4">Agent Interaktions-Diagramm</h3>
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
          <span className="px-3 py-1.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/30">Ingestion</span>
          <ArrowRight className="w-3 h-3 text-slate-600" />
          <div className="flex gap-1">
            <span className="px-2 py-1.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">TA</span>
            <span className="px-2 py-1.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">Context</span>
          </div>
          <ArrowRight className="w-3 h-3 text-slate-600" />
          <span className="px-3 py-1.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30">Quant</span>
          <ArrowRight className="w-3 h-3 text-slate-600" />
          <span className="px-3 py-1.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">Risk</span>
          <ArrowRight className="w-3 h-3 text-slate-600" />
          <span className="px-3 py-1.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">Execution</span>
        </div>
      </div>
    </div>
  );
}

function DecisionsSection() {
  const gates = [
    { name: "Data Freshness", check: "Alle Quellen online?", block: "Keine frischen Daten", active: true },
    { name: "GRSS Pre-Check", check: "GRSS ≥ 20?", block: "Extremstress", active: true },
    { name: "Risk Veto", check: "Kein aktives Veto?", block: "Risiko zu hoch", active: true },
    { name: "Composite Gate", check: "Score ≥ Threshold?", block: "Score zu niedrig", active: true },
    { name: "Position Guard", check: "Keine offene Position?", block: "Slot belegt", active: true },
    { name: "Portfolio Limits", check: "Daily Limits OK?", block: "Limits erreicht", active: true },
  ];

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
        <p className="text-sm text-slate-300">
          Jeder Trade durchläuft <strong className="text-white">6 Gates</strong>. 
          Ein einziges BLOCK stoppt den Trade sofort. 
          Alle Gates sind in der Entscheidungs-Kaskade sichtbar und werden im Decision Feed geloggt.
        </p>
      </div>

      <div className="space-y-3">
        {gates.map((gate, idx) => (
          <div key={gate.name} className="flex items-center gap-4 p-3 rounded-xl border border-[#1a1a2e] bg-[#080810]">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
              gate.active ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-800 text-slate-500"
            }`}>
              {idx + 1}
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium text-slate-300">{gate.name}</div>
              <div className="text-xs text-slate-500">{gate.check}</div>
            </div>
            <div className="text-xs px-2 py-1 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
              BLOCK: {gate.block}
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-950/10">
        <h3 className="text-sm font-medium text-indigo-400 mb-3">Beispiel: Ein LONG Signal entsteht</h3>
        <div className="space-y-2 text-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span className="text-slate-400">TA Score: +12.5 (Support bounce + confluence)</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span className="text-slate-400">Liq Score: +8.2 (Sweep detected at 82,400)</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span className="text-slate-400">Flow Score: +5.3 (CVD positive, OFI 0.62)</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span className="text-slate-400">Macro Score: 57.8 (bearish but not blocking)</span>
          </div>
          <div className="pt-2 border-t border-[#1a1a2e]">
            <span className="text-indigo-400 font-medium">Composite: 26.9</span>
            <span className="text-slate-500"> &gt; Threshold: 26.2 ✓</span>
          </div>
          <div className="flex items-center gap-2">
            <ArrowRight className="w-3 h-3 text-emerald-400" />
            <span className="text-emerald-400 font-medium">SIGNAL_LONG → Execution</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function SafetySection() {
  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/10">
        <div className="flex items-center gap-2 mb-2">
          <Lock className="w-5 h-5 text-emerald-400" />
          <span className="text-lg font-bold text-emerald-400">Paper Trading Only</span>
        </div>
        <p className="text-sm text-slate-300">
          Bruno ist <strong className="text-white">hard-locked auf Paper Trading</strong>. 
          Alle Orders gehen an Bybit Demo. Keine echten Gelder werden riskiert. 
          Live-Trading erfordert explizite Freigabe und Hardware-Level-Validierung.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {[
          { name: "Data Gap", desc: "Fehlende oder veraltete Daten", color: "rose" },
          { name: "Stale Context", desc: "GRSS älter als 5 Min", color: "rose" },
          { name: "VIX Spike", desc: "VIX > 45", color: "rose" },
          { name: "System Pause", desc: "Manueller Halt", color: "amber" },
          { name: "Death Zone", desc: "GRSS < 20", color: "rose" },
          { name: "Daily Drawdown", desc: "3% oder 3 Verlierer", color: "rose" },
        ].map((veto) => (
          <div key={veto.name} className="p-3 rounded-xl border border-[#1a1a2e] bg-[#080810]">
            <div className={`text-sm font-medium ${
              veto.color === "rose" ? "text-rose-400" : "text-amber-400"
            }`}>{veto.name}</div>
            <div className="text-[10px] text-slate-500 mt-1">{veto.desc}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Max Leverage" value="1.0x" subtext="Kein Margin" />
        <MetricCard label="Max Position" value="100%" subtext="Vom simulierten Kapital" />
        <MetricCard label="SL Range" value="1-3%" subtext="ATR-basiert" />
        <MetricCard label="TP Ratio" value="2:1" subtext="Mindestens" />
      </div>

      <DetailSection title="Breakeven Stop Mechanismus" defaultOpen>
        <div className="space-y-3 text-sm">
          <p className="text-slate-300">
            Wenn eine Position im Profit &gt; 0.5% ist, wird der Stop-Loss automatisch auf Entry + 0.1% verschoben:
          </p>
          <pre className="bg-[#0c0c18] p-3 rounded-lg text-xs text-slate-400">
{`if unrealized_pnl_pct > 0.5%:
    new_sl = entry_price * 1.001  # +0.1%
    update_stop_loss(new_sl)`}
          </pre>
          <p className="text-xs text-slate-500">
            Dies schützt vor Rückschlägen bei Gewinnen und sichert zumindest Break-Even.
          </p>
        </div>
      </DetailSection>

      <DetailSection title="Daily Drawdown Protection">
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
              <span className="text-rose-400 font-medium">Trigger</span>
              <ul className="text-xs text-slate-500 mt-1 space-y-0.5">
                <li>• 3% Verlust an einem Tag, ODER</li>
                <li>• 3 aufeinanderfolgende Verluste</li>
              </ul>
            </div>
            <div className="p-3 rounded-lg bg-[#0c0c18] border border-[#1a1a2e]">
              <span className="text-amber-400 font-medium">Aktion</span>
              <ul className="text-xs text-slate-500 mt-1 space-y-0.5">
                <li>• 24h Trading-Block</li>
                <li>• Manueller Reset erforderlich</li>
                <li>• Logging in bruno:risk:daily_block</li>
              </ul>
            </div>
          </div>
        </div>
      </DetailSection>
    </div>
  );
}

// Main Page Component
export default function JourneyPage() {
  const [activeSection, setActiveSection] = useState("overview");
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const renderContent = () => {
    switch (activeSection) {
      case "overview": return <OverviewSection />;
      case "pipeline": return <PipelineSection />;
      case "bybit": return <BybitSection />;
      case "news": return <NewsSection />;
      case "scoring": return <ScoringSection />;
      case "modules": return <ModulesSection />;
      case "decisions": return <DecisionsSection />;
      case "safety": return <SafetySection />;
      default: return <OverviewSection />;
    }
  };

  const activeContent = SECTIONS.find((s) => s.id === activeSection);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <div className="w-72 bg-[#080810] border-r border-[#1a1a2e] flex flex-col">
          {/* Header */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="flex items-center gap-2 mb-1">
              <Microscope className="w-5 h-5 text-indigo-400" />
              <h1 className="text-lg font-bold text-white">Journey</h1>
            </div>
            <p className="text-xs text-slate-500">Bruno v8.0 Architektur</p>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-2 space-y-1">
            {SECTIONS.map((section) => {
              const Icon = section.icon;
              const isActive = activeSection === section.id;
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${
                    isActive
                      ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/30"
                      : "text-slate-400 hover:bg-[#0c0c18] hover:text-slate-200"
                  }`}
                >
                  <Icon className="w-4 h-4 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{section.title}</div>
                    <div className="text-[10px] opacity-60">{section.shortDesc}</div>
                  </div>
                </button>
              );
            })}
          </nav>

          {/* System Status */}
          <div className="p-3 border-t border-[#1a1a2e]">
            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2">System Status</div>
            <div className="space-y-1.5">
              <LiveIndicator active={true} label="Bybit V5 Connected" />
              <LiveIndicator active={true} label="RSS News Active" />
              <LiveIndicator active={true} label="Pipeline Running" />
            </div>
            <div className="mt-3 pt-2 border-t border-[#1a1a2e] text-[10px] text-slate-600 font-mono">
              {currentTime.toLocaleTimeString()} UTC
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Header Area */}
          <div className="sticky top-0 z-10 bg-[#0a0a0f]/95 backdrop-blur border-b border-[#1a1a2e] p-6">
            <div className="max-w-6xl">
              <div className="flex items-center gap-2 mb-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  {activeContent?.shortDesc}
                </span>
              </div>
              <div className="flex items-center gap-3">
                {activeContent && <activeContent.icon className="w-8 h-8 text-indigo-400" />}
                <h1 className="text-3xl font-bold text-white">{activeContent?.title}</h1>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="p-6">
            <div className="max-w-6xl">
              {renderContent()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
