"use client";

import { useState } from "react";

interface KillSwitchProps {
  compact?: boolean;
}

export function KillSwitch({ compact = false }: KillSwitchProps) {
  const [confirmStep, setConfirmStep] = useState(0);
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (confirmStep === 0) {
      setConfirmStep(1);
      // Reset nach 3 Sekunden falls nicht bestätigt
      setTimeout(() => setConfirmStep(0), 3000);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/v1/agents/kill", { method: "POST" });
      if (res.ok) {
        window.location.reload();
      }
    } catch (e) {
      console.error("Kill failed", e);
    } finally {
      setLoading(false);
      setConfirmStep(0);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className={`font-mono font-bold border transition-all duration-150 rounded
        ${compact ? "text-xs px-2 py-1" : "px-4 py-2 text-sm"}
        ${confirmStep === 1
          ? "bg-red-600 border-red-400 text-white animate-pulse"
          : "bg-zinc-900 border-red-800 text-red-500 hover:border-red-500"
        }`}
    >
      {loading ? "..." : confirmStep === 1 ? "⚠ BESTÄTIGEN" : "⚡ STOP"}
    </button>
  );
}
