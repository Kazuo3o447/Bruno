"use client";

import { useState } from "react";

export function ExportButton() {
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  async function handleExport() {
    setLoading(true);
    try {
      const r = await fetch("/api/v1/export/snapshot");
      const data = await r.json();

      const text = [
        "# Bruno Trading Bot — Snapshot für Claude-Analyse",
        `# Generiert: ${new Date().toLocaleString("de-DE")}`,
        "",
        "Bitte analysiere diesen Snapshot:",
        "- Warum wurden in letzter Zeit keine Trades gesetzt?",
        "- Sind die Signale konsistent und plausibel?",
        "- Gibt es Datenlücken oder Anomalien?",
        "- Was würdest du als nächstes optimieren?",
        "",
        "```json",
        JSON.stringify(data, null, 2),
        "```"
      ].join("\n");

      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch (e) {
      console.error("Export error", e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={loading}
      className={`font-mono text-xs px-3 py-1 rounded border transition-all
        ${copied
          ? "border-emerald-600 text-emerald-400 bg-emerald-950/30"
          : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
        }`}
    >
      {loading ? "..." : copied ? "✓ Kopiert" : "📋 Export"}
    </button>
  );
}
