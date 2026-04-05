"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Settings,
  Save,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Database,
  Brain,
  Shield,
  TrendingUp,
  History,
  Play,
  Pause,
  ChevronDown,
  ChevronUp
} from "lucide-react";

// Types
interface Config {
  GRSS_Threshold: number;
  OFI_Threshold: number;
  Max_Leverage: number;
  Stop_Loss_Pct: number;
  Liq_Distance: number;
  COMPOSITE_SIGNAL_THRESHOLD?: number;
  COMPOSITE_W_TA?: number;
  COMPOSITE_W_LIQ?: number;
  COMPOSITE_W_FLOW?: number;
  COMPOSITE_W_MACRO?: number;
  TRADE_COOLDOWN_SECONDS?: number;
  DAILY_MAX_LOSS_PCT?: number;
  MAX_CONSECUTIVE_LOSSES?: number;
  BREAKEVEN_TRIGGER_PCT?: number;
  PAPER_TRADING_ONLY?: boolean;
  ENABLE_LLM_CASCADE_V4?: boolean;
  LEARNING_MODE_ENABLED?: boolean;
  // V2.2 Institutional Features
  ATR_TRAILING_MULTIPLIER?: number;
  TP1_SIZE_PCT?: number;
  TP2_SIZE_PCT?: number;
  ENABLE_ATR_TRAILING?: boolean;
  ENABLE_VOLUME_PROFILE?: boolean;
  ENABLE_DELTA_ABSORPTION?: boolean;
  [key: string]: any;
}

interface ConfigSchema {
  [key: string]: {
    min: number;
    max: number;
    type: string;
    label: string;
  };
}

interface ConfigHistory {
  timestamp: string;
  changed_by: string;
  file: string;
}

interface DeepseekStatus {
  status: string;
  response_time_ms?: number;
  message?: string;
}

const PRESETS = {
  konservativ: {
    name: "Konservativ",
    description: "Minimales Risiko, maximale Kontrolle",
    config: {
      GRSS_Threshold: 55,
      OFI_Threshold: 250,
      Max_Leverage: 1.0,
      Stop_Loss_Pct: 0.015,
      Liq_Distance: 0.008,
      COMPOSITE_SIGNAL_THRESHOLD: 75,
      COMPOSITE_W_TA: 0.18,
      COMPOSITE_W_LIQ: 0.12,
      COMPOSITE_W_FLOW: 0.25,
      COMPOSITE_W_MACRO: 0.45,
      DAILY_MAX_LOSS_PCT: 1.5,
      MAX_CONSECUTIVE_LOSSES: 2,
      BREAKEVEN_TRIGGER_PCT: 0.008,
      // V2.2 Features
      ATR_TRAILING_MULTIPLIER: 2.0,  // Konservativer Trailing
      TP1_SIZE_PCT: 0.6,            // Mehr bei TP1
      TP2_SIZE_PCT: 0.4,
      ENABLE_ATR_TRAILING: true,
      ENABLE_VOLUME_PROFILE: true,
      ENABLE_DELTA_ABSORPTION: true,
      PAPER_TRADING_ONLY: true,
      ENABLE_LLM_CASCADE_V4: false,
    }
  },
  balanced: {
    name: "Balanced",
    description: "Ausgewogenes Risiko/Ertrag",
    config: {
      GRSS_Threshold: 45,
      OFI_Threshold: 200,
      Max_Leverage: 1.0,
      Stop_Loss_Pct: 0.012,
      Liq_Distance: 0.006,
      COMPOSITE_SIGNAL_THRESHOLD: 65,
      COMPOSITE_W_TA: 0.22,
      COMPOSITE_W_LIQ: 0.18,
      COMPOSITE_W_FLOW: 0.25,
      COMPOSITE_W_MACRO: 0.35,
      DAILY_MAX_LOSS_PCT: 3.0,
      MAX_CONSECUTIVE_LOSSES: 3,
      BREAKEVEN_TRIGGER_PCT: 0.005,
      // V2.2 Features
      ATR_TRAILING_MULTIPLIER: 1.5,  // Standard
      TP1_SIZE_PCT: 0.5,            // 50/50 Split
      TP2_SIZE_PCT: 0.5,
      ENABLE_ATR_TRAILING: true,
      ENABLE_VOLUME_PROFILE: true,
      ENABLE_DELTA_ABSORPTION: true,
      PAPER_TRADING_ONLY: true,
      ENABLE_LLM_CASCADE_V4: false,
    }
  },
  aggressiv: {
    name: "Aggressiv",
    description: "Mehr Trades, engere Filter",
    config: {
      GRSS_Threshold: 35,
      OFI_Threshold: 150,
      Max_Leverage: 1.0,
      Stop_Loss_Pct: 0.01,
      Liq_Distance: 0.005,
      COMPOSITE_SIGNAL_THRESHOLD: 55,
      COMPOSITE_W_TA: 0.20,
      COMPOSITE_W_LIQ: 0.15,
      COMPOSITE_W_FLOW: 0.35,
      COMPOSITE_W_MACRO: 0.30,
      DAILY_MAX_LOSS_PCT: 5.0,
      MAX_CONSECUTIVE_LOSSES: 4,
      BREAKEVEN_TRIGGER_PCT: 0.003,
      // V2.2 Features
      ATR_TRAILING_MULTIPLIER: 1.0,  // Enger Trailing
      TP1_SIZE_PCT: 0.3,            // Weniger bei TP1
      TP2_SIZE_PCT: 0.7,
      ENABLE_ATR_TRAILING: true,
      ENABLE_VOLUME_PROFILE: true,
      ENABLE_DELTA_ABSORPTION: true,
      PAPER_TRADING_ONLY: true,
      ENABLE_LLM_CASCADE_V4: false,
    }
  },
  research: {
    name: "Research",
    description: "Mehr Beobachtung, mehr Lernen",
    config: {
      GRSS_Threshold: 40,
      OFI_Threshold: 180,
      Max_Leverage: 1.0,
      Stop_Loss_Pct: 0.014,
      Liq_Distance: 0.006,
      COMPOSITE_SIGNAL_THRESHOLD: 60,
      COMPOSITE_W_TA: 0.20,
      COMPOSITE_W_LIQ: 0.15,
      COMPOSITE_W_FLOW: 0.30,
      COMPOSITE_W_MACRO: 0.35,
      DAILY_MAX_LOSS_PCT: 3.0,
      MAX_CONSECUTIVE_LOSSES: 3,
      BREAKEVEN_TRIGGER_PCT: 0.005,
      // V2.2 Features
      ATR_TRAILING_MULTIPLIER: 1.5,  // Standard
      TP1_SIZE_PCT: 0.5,
      TP2_SIZE_PCT: 0.5,
      ENABLE_ATR_TRAILING: true,
      ENABLE_VOLUME_PROFILE: true,
      ENABLE_DELTA_ABSORPTION: true,
      PAPER_TRADING_ONLY: true,
      ENABLE_LLM_CASCADE_V4: true,
      LEARNING_MODE_ENABLED: true,
    }
  }
};

export default function SettingsPage() {
  const [config, setConfig] = useState<Config | null>(null);
  const [schema, setSchema] = useState<ConfigSchema | null>(null);
  const [history, setHistory] = useState<ConfigHistory[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [deepseekStatus, setDeepseekStatus] = useState<DeepseekStatus | null>(null);
  const [testingDeepseek, setTestingDeepseek] = useState(false);
  const [expandedSection, setExpandedSection] = useState<string | null>("trading");

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/config");
      if (res.ok) {
        const data = await res.json();
        setConfig(data.config);
        setSchema(data.schema);
      }

      const historyRes = await fetch("/api/v1/config/history");
      if (historyRes.ok) {
        const data = await historyRes.json();
        setHistory(data.history || []);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const saveConfig = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const res = await fetch("/api/v1/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates: config }),
      });

      if (res.ok) {
        setSuccess("Konfiguration gespeichert");
        fetchConfig();
        setTimeout(() => setSuccess(""), 3000);
      } else {
        const err = await res.json();
        setError(err.detail || "Fehler beim Speichern");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const testDeepseek = async () => {
    setTestingDeepseek(true);
    try {
      const res = await fetch("/api/v1/deepseek/test", { method: "POST" });
      const data = await res.json();
      setDeepseekStatus(data);
    } catch (e) {
      setDeepseekStatus({ status: "error", message: "Verbindung fehlgeschlagen" });
    } finally {
      setTestingDeepseek(false);
    }
  };

  const applyPreset = (presetKey: string) => {
    const preset = PRESETS[presetKey as keyof typeof PRESETS];
    if (preset && config) {
      setConfig({ ...config, ...preset.config });
    }
  };

  const updateConfigValue = (key: string, value: number) => {
    setConfig(prev => prev ? { ...prev, [key]: value } : null);
  };

  const updateConfigBoolean = (key: string, value: boolean) => {
    setConfig(prev => prev ? { ...prev, [key]: value } : null);
  };

  const Section = ({ id, title, icon: Icon, children }: { id: string; title: string; icon: any; children: React.ReactNode }) => (
    <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl overflow-hidden mb-4">
      <button
        onClick={() => setExpandedSection(expandedSection === id ? null : id)}
        className="w-full flex items-center justify-between p-4 hover:bg-[#0f0f18] transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon className="w-5 h-5 text-indigo-400" />
          <span className="font-medium">{title}</span>
        </div>
        {expandedSection === id ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
      </button>
      {expandedSection === id && (
        <div className="p-4 pt-0 border-t border-[#1a1a2e]">
          {children}
        </div>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] text-white p-6 flex items-center justify-center">
        <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Einstellungen</h1>
            <p className="text-sm text-slate-500">Konfiguration & Steuerung</p>
          </div>
          <div className="flex items-center gap-3">
            {success && (
              <span className="flex items-center gap-2 text-emerald-400 text-sm">
                <CheckCircle className="w-4 h-4" />
                {success}
              </span>
            )}
            <button
              onClick={fetchConfig}
              className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              Aktualisieren
            </button>
            <button
              onClick={saveConfig}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {saving ? "Speichern..." : "Speichern"}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-950/30 border border-red-800 rounded-xl flex items-center gap-2 text-red-400">
          <AlertTriangle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Presets */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {Object.entries(PRESETS).map(([key, preset]) => (
          <button
            key={key}
            onClick={() => applyPreset(key)}
            className="p-4 bg-[#0c0c18] border border-[#1a1a2e] hover:border-indigo-800 rounded-xl text-left transition-colors"
          >
            <div className="font-medium text-indigo-400">{preset.name}</div>
            <div className="text-xs text-slate-500 mt-1">{preset.description}</div>
          </button>
        ))}
      </div>

      {/* Config Sections */}
      <div className="max-w-3xl">
        <Section id="trading" title="Trading Parameter" icon={TrendingUp}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {schema && config && [
              { key: "GRSS_Threshold", label: "GRSS Mindestschwelle", unit: "" },
              { key: "OFI_Threshold", label: "OFI Schwellenwert", unit: "" },
              { key: "COMPOSITE_SIGNAL_THRESHOLD", label: "Composite Signal Threshold", unit: "" },
              { key: "COMPOSITE_W_TA", label: "Composite Gewicht TA", unit: "" },
              { key: "COMPOSITE_W_LIQ", label: "Composite Gewicht Liquidity", unit: "" },
              { key: "COMPOSITE_W_FLOW", label: "Composite Gewicht Flow", unit: "" },
              { key: "COMPOSITE_W_MACRO", label: "Composite Gewicht Macro", unit: "" },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="text-xs text-slate-500 block mb-1">{label}</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={config[key] || 0}
                    onChange={(e) => updateConfigValue(key, parseFloat(e.target.value))}
                    min={schema[key]?.min}
                    max={schema[key]?.max}
                    step={schema[key]?.type === "float" ? 0.001 : 1}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                  />
                  <span className="text-xs text-slate-500 w-20">
                    [{schema[key]?.min}-{schema[key]?.max}]
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section id="operations" title="Betrieb & Kontrolle" icon={Shield}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {config && [
              { key: "PAPER_TRADING_ONLY", label: "Paper Trading Only", desc: "Hard-Lock auf Demo-Modus" },
              { key: "ENABLE_LLM_CASCADE_V4", label: "LLM Cascade V4", desc: "Zeitbasierte Kaskade aktivieren" },
              { key: "LEARNING_MODE_ENABLED", label: "Learning Mode", desc: "Runs für spätere Auswertung markieren" },
            ].map(({ key, label, desc }) => (
              <label key={key} className="flex items-center justify-between gap-4 p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
                <div>
                  <div className="text-sm font-medium text-slate-200">{label}</div>
                  <div className="text-xs text-slate-500 mt-1">{desc}</div>
                </div>
                <input
                  type="checkbox"
                  checked={Boolean(config[key])}
                  onChange={(e) => updateConfigBoolean(key, e.target.checked)}
                  className="h-5 w-5 rounded border-slate-700 bg-slate-900 text-indigo-500"
                />
              </label>
            ))}
          </div>
        </Section>

        <Section id="risk" title="Risiko Management" icon={Shield}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {schema && config && [
              { key: "Max_Leverage", label: "Max. Leverage", unit: "x" },
              { key: "Stop_Loss_Pct", label: "Stop-Loss %", unit: "%" },
              { key: "Liq_Distance", label: "Min. Liq-Wall Abstand", unit: "" },
              { key: "DAILY_MAX_LOSS_PCT", label: "Tägliches Max Loss", unit: "%" },
              { key: "MAX_CONSECUTIVE_LOSSES", label: "Max. Consecutive Losses", unit: "" },
              { key: "BREAKEVEN_TRIGGER_PCT", label: "Breakeven Trigger", unit: "%" },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="text-xs text-slate-500 block mb-1">{label}</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={config[key] || 0}
                    onChange={(e) => updateConfigValue(key, parseFloat(e.target.value))}
                    min={schema[key]?.min}
                    max={schema[key]?.max}
                    step={schema[key]?.type === "float" ? 0.001 : 1}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                  />
                  <span className="text-xs text-slate-500 w-20">
                    [{schema[key]?.min}-{schema[key]?.max}]
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section id="exit" title="Exit Management" icon={TrendingUp}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {schema && config && [
              { key: "ATR_TRAILING_MULTIPLIER", label: "ATR Trailing Multiplier", unit: "x" },
              { key: "TP1_SIZE_PCT", label: "TP1 Size", unit: "" },
              { key: "TP2_SIZE_PCT", label: "TP2 Size", unit: "" },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="text-xs text-slate-500 block mb-1">{label}</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={config[key] || 0}
                    onChange={(e) => updateConfigValue(key, parseFloat(e.target.value))}
                    min={schema[key]?.min}
                    max={schema[key]?.max}
                    step={schema[key]?.type === "float" ? 0.001 : 1}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                  />
                  <span className="text-xs text-slate-500 w-20">
                    [{schema[key]?.min}-{schema[key]?.max}]
                  </span>
                </div>
              </div>
            ))}

            {config && [
              { key: "ENABLE_ATR_TRAILING", label: "ATR Trailing aktiv", desc: "Trailing Stop nach TP1 scharf schalten" },
              { key: "ENABLE_VOLUME_PROFILE", label: "Volume Profile aktiv", desc: "VPOC in TA Snapshot berücksichtigen" },
              { key: "ENABLE_DELTA_ABSORPTION", label: "Delta Absorption aktiv", desc: "Absorptionssignale im TA aktivieren" },
            ].map(({ key, label, desc }) => (
              <label key={key} className="flex items-center justify-between gap-4 p-4 rounded-xl border border-[#1a1a2e] bg-[#080810]">
                <div>
                  <div className="text-sm font-medium text-slate-200">{label}</div>
                  <div className="text-xs text-slate-500 mt-1">{desc}</div>
                </div>
                <input
                  type="checkbox"
                  checked={Boolean(config[key])}
                  onChange={(e) => updateConfigBoolean(key, e.target.checked)}
                  className="h-5 w-5 rounded border-slate-700 bg-slate-900 text-indigo-500"
                />
              </label>
            ))}
          </div>
        </Section>

        <Section id="system" title="System Parameter" icon={Database}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {schema && config && [
              { key: "TRADE_COOLDOWN_SECONDS", label: "Trade Cooldown", unit: "s" },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="text-xs text-slate-500 block mb-1">{label}</label>
                <input
                  type="number"
                  value={config[key] || 0}
                  onChange={(e) => updateConfigValue(key, parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
            ))}
          </div>
        </Section>

        <Section id="deepseek" title="Deepseek API" icon={Brain}>
          <div className="space-y-4">
            <p className="text-sm text-slate-400">
              Deepseek API wird für Post-Trade Analysen und Lern-Logs verwendet. Der Verbindungstest prüft die Erreichbarkeit.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-400">
              <div className="rounded-xl border border-[#1a1a2e] bg-[#080810] p-3">• Analyse nach Trade-Close</div>
              <div className="rounded-xl border border-[#1a1a2e] bg-[#080810] p-3">• Runs nur 24h, Trades dauerhaft</div>
              <div className="rounded-xl border border-[#1a1a2e] bg-[#080810] p-3">• Manuell testbar per Button</div>
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={testDeepseek}
                disabled={testingDeepseek}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm disabled:opacity-50"
              >
                {testingDeepseek ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
                {testingDeepseek ? "Teste..." : "Verbindung testen"}
              </button>

              {deepseekStatus && (
                <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                  deepseekStatus.status === "ok" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                }`}>
                  {deepseekStatus.status === "ok" ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                  {deepseekStatus.status === "ok" ? (
                    <span>Verbunden ({deepseekStatus.response_time_ms?.toFixed(0)}ms)</span>
                  ) : (
                    <span>{deepseekStatus.message || "Fehler"}</span>
                  )}
                </div>
              )}
            </div>
          </div>
        </Section>

        {/* Config History */}
        <div className="mt-8">
          <h3 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
            <History className="w-4 h-4" />
            Letzte Änderungen
          </h3>
          <div className="space-y-2">
            {history.map((item, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-[#0c0c18] border border-[#1a1a2e] rounded-lg text-sm">
                <div className="flex items-center gap-3">
                  <span className="text-slate-500">{new Date(item.timestamp).toLocaleString("de-DE")}</span>
                  <span className="text-slate-400">von {item.changed_by}</span>
                </div>
                <span className="text-xs text-slate-500 font-mono">{item.file}</span>
              </div>
            ))}

            {history.length === 0 && (
              <p className="text-slate-500 text-sm">Keine Konfigurationshistorie verfügbar</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
