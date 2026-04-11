"use client";
import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";

const API = "/api/v1";

const PRESETS: Record<string, {
  label: string;
  description: string;
  icon: string;
  values: Record<string, number>;
}> = {
  standard: {
    label: "Ruben Standard",
    description: "Aktueller Markt (VIX ~31, ranging). Balance aus Aktivität und Sicherheit.",
    icon: "⚖️",
    values: {
      GRSS_Threshold: 40,    // Veto wenn GRSS < 40 — opportunistisch
      OFI_Threshold: 50,     // Full-Depth 20 Levels — ausgewogen
      Stop_Loss_Pct: 0.012,  // 1.2% — etwas weiter wegen VIX 31
      Max_Leverage: 1.0,     // Eiserne Regel
      Liq_Distance: 0.005,   // 0.5% Mindestabstand
    }
  },
  conservative: {
    label: "Ruben Konservativ",
    description: "Für unsichere Märkte. Weniger Trades, höhere Qualität.",
    icon: "🛡️",
    values: {
      GRSS_Threshold: 50,    // Nur handeln wenn Markt klar bullish
      OFI_Threshold: 80,     // Starkes Signal nötig
      Stop_Loss_Pct: 0.010,  // 1.0% — engerer Stop
      Max_Leverage: 1.0,
      Liq_Distance: 0.007,   // 0.7% — mehr Sicherheitsabstand
    }
  },
  aggressive: {
    label: "Ruben Aggressiv",
    description: "Für klare Bullmärkte oder Coiled-Spring-Setups. Mehr Trades.",
    icon: "⚡",
    values: {
      GRSS_Threshold: 35,    // Tiefer Threshold — mehr Opportunitäten
      OFI_Threshold: 30,     // Niedrigerer OFI-Trigger
      Stop_Loss_Pct: 0.015,  // 1.5% — weiter wegen erhöhter Vola
      Max_Leverage: 1.0,
      Liq_Distance: 0.004,   // 0.4%
    }
  },
};

const SCHEMA: Record<string, {
  label: string; min: number; max: number; step: number;
  unit: string; type: "int" | "float"; description: string;
  warning?: (v: number) => string | null;
}> = {
  GRSS_Threshold: {
    label: "GRSS Mindestschwelle", min: 30, max: 70, step: 1,
    unit: "Punkte", type: "int",
    description: "Unter diesem Wert: kein Trade. Aktuell empfohlen: 48.",
    warning: v => v < 40 ? "Warnung: Sehr niedrig — erhöhtes Risiko bei schlechten Marktbedingungen" : null
  },
  OFI_Threshold: {
    label: "OFI Schwellenwert (Full-Depth)", min: 10, max: 300, step: 5,
    unit: "", type: "int",
    description: "Full-Depth OFI über 20 Levels. Typische Werte: 20–150. Start: 50.",
    warning: v => v > 150 ? "Hoch — wenige Cascade-Trigger erwartet" :
              v < 20 ? "Sehr niedrig — häufige Trigger, viele HOLD-Outcomes" : null
  },
  Stop_Loss_Pct: {
    label: "Stop-Loss", min: 0.003, max: 0.03, step: 0.001,
    unit: "%", type: "float",
    description: "Prozentuale Distanz vom Entry-Preis zum Stop-Loss.",
    warning: v => v > 0.02 ? "Hoher Stop-Loss — größere Verluste pro Trade möglich" : null
  },
  Max_Leverage: {
    label: "Max. Leverage", min: 0.1, max: 1.0, step: 0.1,
    unit: "×", type: "float",
    description: "Eiserne Regel: niemals über 1.0. Kein Kredit.",
    warning: v => v > 1.0 ? "VERBOTEN laut Manifest" : null
  },
  Liq_Distance: {
    label: "Min. Liq-Wall Abstand", min: 0.002, max: 0.02, step: 0.001,
    unit: "%", type: "float",
    description: "Mindestabstand zu einer Liquidations-Wall. Unter diesem Wert: Veto.",
    warning: undefined
  },
};

type KillSwitchStatus = {
  killswitch_active: boolean;
  daily_limit_hit: boolean;
  consecutive_losses_global: number;
  effective_max_consecutive: number;
  reason: string | null;
};

export default function EinstellungenPage() {
  const [config, setConfig] = useState<Record<string, number>>({});
  const [pending, setPending] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // PROMPT 01: Kill-Switch State
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    fetch(`${API}/config`).then(r => r.json()).then(d => {
      setConfig(d.config ?? {});
      setPending(d.config ?? {});
    });
    
    // PROMPT 01: Fetch kill-switch status
    fetchKillSwitchStatus();
    
    // Refresh every 10 seconds
    const interval = setInterval(fetchKillSwitchStatus, 10000);
    return () => clearInterval(interval);
  }, []);
  
  const fetchKillSwitchStatus = async () => {
    try {
      const res = await fetch(`${API}/risk/killswitch_status`);
      if (res.ok) {
        const data = await res.json();
        setKillSwitch(data);
      }
    } catch (e) {
      console.error("Failed to fetch kill-switch status:", e);
    }
  };
  
  const resetKillSwitch = async (scope: "daily" | "consecutive" | "all") => {
    setResetting(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      const res = await fetch(`${API}/risk/reset_killswitch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: today, scope }),
      });
      
      if (res.ok) {
        await fetchKillSwitchStatus();
      } else {
        const err = await res.json();
        setError(err.detail || "Reset fehlgeschlagen");
      }
    } catch (e) {
      setError("Netzwerkfehler beim Reset");
    } finally {
      setResetting(false);
    }
  };

  const hasChanges = Object.keys(SCHEMA).some(k => pending[k] !== config[k]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload = { updates: Object.fromEntries(
        Object.keys(SCHEMA).map(k => [k, pending[k]])
      )};
      const r = await fetch(`${API}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok) {
        setError(Array.isArray(data.detail) ? data.detail.join(", ") : data.detail);
        return;
      }
      setConfig(data.config);
      setPending(data.config);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  }

  function reset() { setPending({ ...config }); }

  return (
    <div className="flex min-h-screen bg-[#0a0a0f] text-white">
      <Sidebar />
      <div className="flex-1 p-6 max-w-2xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="font-mono text-zinc-400 uppercase tracking-widest text-xs">
            Einstellungen — config.json
          </h1>
          <div className="flex gap-2">
            {hasChanges && (
              <button onClick={reset}
                className="font-mono text-xs px-3 py-1.5 border border-zinc-700 text-zinc-400 rounded hover:border-zinc-500">
                Zurücksetzen
              </button>
            )}
            <button onClick={save} disabled={!hasChanges || saving}
              className={`font-mono text-xs px-4 py-1.5 rounded border font-bold transition-all
                ${!hasChanges || saving
                  ? "border-zinc-800 text-zinc-600 cursor-not-allowed"
                  : saved
                    ? "border-emerald-600 text-emerald-400 bg-emerald-950/30"
                    : "border-blue-600 text-blue-400 hover:bg-blue-950/30"
                }`}>
              {saving ? "Speichert..." : saved ? "✓ Gespeichert" : "Speichern"}
            </button>
          </div>
        </div>

        {error && (
          <div className="border border-red-800 rounded px-3 py-2 text-red-400 font-mono text-xs mb-4">
            {error}
          </div>
        )}

        {/* PROMPT 01: Kill-Switch Banner */}
        {killSwitch?.killswitch_active && (
          <div className="border-2 border-red-600 rounded-lg p-4 mb-6 bg-red-950/30">
            <div className="flex items-start gap-3">
              <div className="text-2xl">🛑</div>
              <div className="flex-1">
                <div className="font-mono text-sm font-bold text-red-400 mb-1">
                  KILL-SWITCH AKTIV — TRADING BLOCKIERT
                </div>
                <div className="font-mono text-xs text-red-300/80 mb-3">
                  Grund: {killSwitch.reason}
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono mb-3">
                  <div className="text-zinc-400">
                    Daily Limit: <span className={killSwitch.daily_limit_hit ? "text-red-400" : "text-emerald-400"}>
                      {killSwitch.daily_limit_hit ? "HIT" : "OK"}
                    </span>
                  </div>
                  <div className="text-zinc-400">
                    Consecutive: <span className={killSwitch.consecutive_losses_global >= killSwitch.effective_max_consecutive ? "text-red-400" : "text-emerald-400"}>
                      {killSwitch.consecutive_losses_global}/{killSwitch.effective_max_consecutive}
                    </span>
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {killSwitch.daily_limit_hit && (
                    <button
                      onClick={() => resetKillSwitch("daily")}
                      disabled={resetting}
                      className="font-mono text-xs px-3 py-1.5 border border-red-600 text-red-400 rounded hover:bg-red-900/50 disabled:opacity-50"
                    >
                      {resetting ? "Reset..." : "Reset Daily Limit"}
                    </button>
                  )}
                  {killSwitch.consecutive_losses_global >= killSwitch.effective_max_consecutive && (
                    <button
                      onClick={() => resetKillSwitch("consecutive")}
                      disabled={resetting}
                      className="font-mono text-xs px-3 py-1.5 border border-red-600 text-red-400 rounded hover:bg-red-900/50 disabled:opacity-50"
                    >
                      {resetting ? "Reset..." : "Reset Consecutive"}
                    </button>
                  )}
                  <button
                    onClick={() => resetKillSwitch("all")}
                    disabled={resetting}
                    className="font-mono text-xs px-3 py-1.5 border border-red-600 text-red-400 rounded hover:bg-red-900/50 disabled:opacity-50"
                  >
                    {resetting ? "Reset..." : "Reset All"}
                  </button>
                </div>
                <div className="font-mono text-xs text-zinc-500 mt-2">
                  ⚠️ Reset nur für aktuellen Tag möglich. Manuelles Eingreifen erforderlich.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Preset-Selector */}
        <div className="mb-6">
          <div className="font-mono text-zinc-500 uppercase tracking-widest text-xs mb-3">
            Schnellauswahl — Preset laden
          </div>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(PRESETS).map(([key, preset]) => (
              <button
                key={key}
                onClick={() => {
                  setPending(prev => ({ ...prev, ...preset.values }));
                }}
                className={`
                  border rounded p-3 text-left font-mono text-xs transition-all
                  hover:border-zinc-500 border-zinc-800 bg-zinc-900/50
                  ${Object.entries(preset.values).every(([k, v]) => pending[k] === v)
                    ? 'border-blue-600 bg-blue-950/20'
                    : ''}
                `}
              >
                <div className="text-base mb-1">{preset.icon}</div>
                <div className="text-white text-sm font-bold">{preset.label}</div>
                <div className="text-zinc-500 mt-1 text-xs leading-relaxed">{preset.description}</div>
              </button>
            ))}
          </div>
          {/* Zeige aktive Werte des aktuell gewählten Presets */}
          {Object.entries(PRESETS).find(([, p]) =>
            Object.entries(p.values).every(([k, v]) => pending[k] === v)
          ) && (
            <div className="mt-3 border border-blue-900 rounded px-3 py-2 text-xs font-mono text-blue-400 bg-blue-950/10">
              ✓ Preset aktiv — klicke "Speichern" um anzuwenden
            </div>
          )}
        </div>

        <div className="space-y-6">
          {Object.entries(SCHEMA).map(([key, schema]) => {
            const current = pending[key] ?? config[key] ?? schema.min;
            const original = config[key];
            const changed = current !== original;
            const warn = schema.warning?.(current);
            const displayVal = schema.type === "float"
              ? (current * (schema.unit === "%" ? 100 : 1)).toFixed(
                  schema.unit === "%" ? 1 : 1
                ) + schema.unit
              : current + " " + schema.unit;

            return (
              <div key={key} className={`border rounded p-4 font-mono
                ${changed ? "border-blue-800" : "border-zinc-800"}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-white text-sm">{schema.label}</span>
                  <div className="flex items-center gap-3">
                    {changed && original !== undefined && (
                      <span className="text-zinc-500 text-xs line-through">
                        {schema.type === "float"
                          ? (original * (schema.unit === "%" ? 100 : 1)).toFixed(1) + schema.unit
                          : original + " " + schema.unit}
                      </span>
                    )}
                    <span className={`text-sm font-bold ${changed ? "text-blue-400" : "text-zinc-200"}`}>
                      {displayVal}
                    </span>
                  </div>
                </div>

                <input
                  type="range"
                  min={schema.min} max={schema.max} step={schema.step}
                  value={current}
                  onChange={e => setPending(p => ({
                    ...p,
                    [key]: schema.type === "int" ? parseInt(e.target.value) : parseFloat(e.target.value)
                  }))}
                  className="w-full accent-blue-500 mt-2"
                />

                <div className="flex justify-between text-zinc-600 text-xs mt-1">
                  <span>{schema.type === "float"
                    ? (schema.min * (schema.unit === "%" ? 100 : 1)).toFixed(1) : schema.min}{schema.unit}</span>
                  <span className="text-zinc-500 italic">{schema.description}</span>
                  <span>{schema.type === "float"
                    ? (schema.max * (schema.unit === "%" ? 100 : 1)).toFixed(1) : schema.max}{schema.unit}</span>
                </div>

                {warn && (
                  <div className="text-amber-400 text-xs mt-1">⚠ {warn}</div>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-4 border border-zinc-800 rounded px-3 py-2 font-mono text-xs">
          <div className="text-zinc-500 mb-2">Aktuelle Konfiguration erklärt:</div>
          <div className="space-y-1 text-zinc-400">
            <div>
              <span className="text-zinc-500">GRSS {pending.GRSS_Threshold}: </span>
              {(pending.GRSS_Threshold ?? 0) >= 50 ? "Konservativ — nur bei klarer Marktlage" :
               (pending.GRSS_Threshold ?? 0) >= 40 ? "Standard — opportunistisch aber selektiv" :
               "Aggressiv — auch bei schwierigen Bedingungen handeln"}
            </div>
            <div>
              <span className="text-zinc-500">OFI {pending.OFI_Threshold}: </span>
              {(pending.OFI_Threshold ?? 0) <= 30 ? "Niedrig — häufige Cascade-Trigger" :
               (pending.OFI_Threshold ?? 0) <= 80 ? "Ausgewogen — solider Orderflow nötig" :
               "Hoch — nur starke Signals triggern die Cascade"}
            </div>
            <div>
              <span className="text-zinc-500">Stop-Loss {((pending.Stop_Loss_Pct ?? 0) * 100).toFixed(1)}%: </span>
              Bei BTC $70k → ${Math.round(70000 * (pending.Stop_Loss_Pct ?? 0.01))} Abstand
            </div>
          </div>
        </div>

        <div className="mt-6 border border-zinc-800 rounded p-3 font-mono text-xs text-zinc-600">
          Änderungen werden in config.json geschrieben und in config_history/ versioniert.
          Agenten lesen config.json beim nächsten Zyklus. Kein Neustart nötig.
        </div>
      </div>
    </div>
  );
}
