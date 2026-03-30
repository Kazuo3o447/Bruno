"use client";
import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";

const API = "/api/v1";

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
    label: "OFI Schwellenwert", min: 200, max: 1000, step: 50,
    unit: "", type: "int",
    description: "Order Flow Imbalance muss diesen Absolutwert überschreiten um Cascade zu starten.",
    warning: v => v > 800 ? "Sehr hoch — wenige Trades werden getriggert" : null
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

export default function EinstellungenPage() {
  const [config, setConfig] = useState<Record<string, number>>({});
  const [pending, setPending] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/config`).then(r => r.json()).then(d => {
      setConfig(d.config ?? {});
      setPending(d.config ?? {});
    });
  }, []);

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

        <div className="mt-6 border border-zinc-800 rounded p-3 font-mono text-xs text-zinc-600">
          Änderungen werden in config.json geschrieben und in config_history/ versioniert.
          Agenten lesen config.json beim nächsten Zyklus. Kein Neustart nötig.
        </div>
      </div>
    </div>
  );
}
