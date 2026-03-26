import { useState } from "react";
import { X, Database, Brain, Activity, ShieldCheck, Zap, ArrowRight, Layers } from "lucide-react";

interface AgentInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AgentInfoModal({ isOpen, onClose }: AgentInfoModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[100] backdrop-blur-sm p-4">
      <div className="bg-[#1a1a2e] rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto border border-slate-700 shadow-2xl relative">
        
        {/* Header */}
        <div className="sticky top-0 bg-[#1a1a2e] border-b border-slate-700 p-6 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-500/20 text-blue-400 rounded-xl">
              <Layers className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">Agent Pipeline Architektur</h2>
              <p className="text-sm text-slate-400">Wie der Bruno Trading Bot denkt und handelt</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-8">
          
          {/* Intro */}
          <div className="bg-slate-800/50 p-6 rounded-xl border border-slate-700">
            <p className="text-slate-300 leading-relaxed">
              Bruno ist nicht ein einzelner Bot, sondern ein System aus <strong>5 hochspezialisierten KI-Agenten</strong>. Jeder Agent hat eine spezifische Verantwortung und darf nicht in die Aufgaben der anderen eingreifen. Die Agenten kommunizieren asynchron über den Redis Message-Broker.
            </p>
          </div>

          {/* Pipeline Visualization */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2 text-center items-center py-4 text-xs font-semibold text-slate-400">
            <div>1. Daten sammeln</div>
            <div>2. Analyse</div>
            <div>3. Sentiment</div>
            <div>4. Konsens & Risiko</div>
            <div>5. Ausführung</div>
          </div>

          <div className="flex flex-col md:flex-row items-center gap-4 justify-between w-full relative">
            {/* Connections */}
            <div className="hidden md:block absolute top-1/2 left-0 right-0 h-1 bg-gradient-to-r from-blue-500/30 via-purple-500/30 to-green-500/30 -translate-y-1/2 z-0" />

            <PipelineStep 
              icon={<Database />}
              color="text-blue-400"
              bg="bg-blue-400/20"
              border="border-blue-500/50"
              title="Ingestion"
            />
            <ArrowRight className="hidden md:block w-6 h-6 text-slate-600 z-10" />
            
            <PipelineStep 
              icon={<Activity />}
              color="text-emerald-400"
              bg="bg-emerald-400/20"
              border="border-emerald-500/50"
              title="Quant"
            />
            
            <ArrowRight className="hidden md:block w-6 h-6 text-slate-600 z-10" />
            <PipelineStep 
              icon={<Brain />}
              color="text-purple-400"
              bg="bg-purple-400/20"
              border="border-purple-500/50"
              title="Sentiment"
            />

            <ArrowRight className="hidden md:block w-6 h-6 text-slate-600 z-10" />
            <PipelineStep 
              icon={<ShieldCheck />}
              color="text-yellow-400"
              bg="bg-yellow-400/20"
              border="border-yellow-500/50"
              title="Risk"
            />

            <ArrowRight className="hidden md:block w-6 h-6 text-slate-600 z-10" />
            <PipelineStep 
              icon={<Zap />}
              color="text-red-400"
              bg="bg-red-400/20"
              border="border-red-500/50"
              title="Execution"
            />
          </div>

          {/* Details */}
          <div className="space-y-6">
            <AgentDetailCard 
              name="1. Ingestion Agent (Daten-Silo)"
              desc="Verbindet sich mit Binance Futures (Multiplexing). Liest gleichzeitig Kerzen, das Orderbuch, Funding Rates und Milliarden-Liquidationen. Speichert alles extrem schnell in skalierbaren TimescaleDB Hypertables."
              icon={<Database className="w-6 h-6 text-blue-400" />}
            />
            <AgentDetailCard 
              name="2. Quant Agent (Das mathematische Auge)"
              desc="Fragt kontinuierlich die Timescale-DB ab. Nutzt Multi-Timeframe-Analysen (5min & 1h) mit Indikatoren wie RSI, MACD und ATR. Betrachtet auch das Orderbuch (Kauf-/Verkaufs-Überhang), um mathematische Trading-Signale zu erzeugen."
              icon={<Activity className="w-6 h-6 text-emerald-400" />}
            />
            <AgentDetailCard 
              name="3. Sentiment Agent (Das Ohr am Markt)"
              desc="Überwacht Krypto-News und soziale Medien (z.B. CryptoPanic). Nutzt das lokale qwen2.5 LLM, um Headlines zu bewerten und ein Sentiment-Signal (-1 bis +1) zu generieren, frei von Panik oder Gier."
              icon={<Brain className="w-6 h-6 text-purple-400" />}
            />
            <AgentDetailCard 
              name="4. Risk Agent (Das vernünftige Gehirn)"
              desc="Das absolute Kontroll-Zentrum! Zieht Quant-Signale, Sentiment-Signale und den 'Rich Market Context' (Fear&Greed, Liquidations) zusammen. Befragt das deepseek-r1 Reasoning Model. Setzt strenge Limits durch: Stop-Loss, Max Drawdown und Positionsgrößenberechnung. Gibt einen Trade nur frei, wenn eine hohe Konfluenz an Signalen herrscht."
              icon={<ShieldCheck className="w-6 h-6 text-yellow-400" />}
            />
            <AgentDetailCard 
              name="5. Execution Agent (Der Ausführer)"
              desc="Hört nur auf den Risk-Agenten. Sobald ein Trade genehmigt ('Approved') wurde, loggt er diesen manipulationssicher in der Datenbank und wickelt die Paper-Trades (bzw. später Echtgeldbestellungen) rigoros nach Vorgabe ab."
              icon={<Zap className="w-6 h-6 text-red-400" />}
            />
          </div>

        </div>
      </div>
    </div>
  );
}

function PipelineStep({ icon, title, color, bg, border }: any) {
  return (
    <div className={`flex flex-col items-center justify-center p-4 rounded-full border-2 ${border} ${bg} ${color} z-10 w-24 h-24 shadow-lg`}>
      <div className="mb-1">{icon}</div>
      <span className="text-xs font-bold">{title}</span>
    </div>
  );
}

function AgentDetailCard({ name, desc, icon }: any) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 hover:bg-slate-800/80 transition-colors">
      <div className="p-3 bg-slate-900 rounded-lg shrink-0">
        {icon}
      </div>
      <div>
        <h4 className="text-lg font-semibold text-white mb-2">{name}</h4>
        <p className="text-slate-400 text-sm leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}
