"use client";
import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";

const API = "/api/v1";

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `vor ${s}s`;
  if (s < 3600) return `vor ${Math.floor(s / 60)}m ${s % 60}s`;
  return `vor ${Math.floor(s / 3600)}h`;
}

function AgentCard({ title, children, healthy, lastUpdate }: {
  title: string; children: React.ReactNode;
  healthy?: boolean; lastUpdate?: string | null;
}) {
  return (
    <div className="border border-zinc-800 rounded font-mono text-xs">
      <div className="px-3 py-2 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/50">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${
            healthy === true ? "bg-emerald-400 animate-pulse" :
            healthy === false ? "bg-red-400" : "bg-zinc-600"
          }`} />
          <span className="text-white font-bold uppercase tracking-wider text-xs">{title}</span>
        </div>
        {lastUpdate && (
          <span className="text-zinc-600">{timeAgo(lastUpdate)}</span>
        )}
      </div>
      <div className="px-3 py-3 space-y-2">{children}</div>
    </div>
  );
}

function KV({ label, value, color }: { label: string; value: string | number | null; color?: string }) {
  return (
    <span className="inline-flex gap-1 mr-4">
      <span className="text-zinc-500">{label}:</span>
      <span className={color ?? "text-zinc-200"}>{value ?? "—"}</span>
    </span>
  );
}

export default function AgentenPage() {
  const [grss, setGrss] = useState<any>(null);
  const [telemetry, setTelemetry] = useState<any>(null);
  const [cascade, setCascade] = useState<any>(null);
  const [decisions, setDecisions] = useState<any>(null);
  const [vetoHistory, setVetoHistory] = useState<any[]>([]);

  async function load() {
    const [tel, gr, cas, dec, veto] = await Promise.allSettled([
      fetch(`${API}/telemetry/live`).then(r => r.json()),
      fetch(`${API}/market/grss-full`).then(r => r.json()),
      fetch(`${API}/llm-cascade/status`).then(r => r.json()),
      fetch(`${API}/decisions/feed?limit=50`).then(r => r.json()),
      fetch(`${API}/decisions/veto-history`).then(r => r.json()),
    ]);
    if (tel.status === "fulfilled") setTelemetry(tel.value);
    if (gr.status === "fulfilled") setGrss(gr.value);
    if (cas.status === "fulfilled") setCascade(cas.value);
    if (dec.status === "fulfilled") setDecisions(dec.value);
    if (veto.status === "fulfilled") setVetoHistory(veto.value.events ?? []);
  }

  useEffect(() => {
    load();
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, []);

  const agents = telemetry?.agents ?? {};
  const market = telemetry?.market ?? {};
  const veto = telemetry?.veto_active;
  const vetoReason = telemetry?.veto_reason;

  const stats = decisions?.stats ?? {};
  const lastDecisions = decisions?.events ?? [];
  const lastCascadeRun = lastDecisions.find((e: any) => e.ofi_met);

  return (
    <div className="flex min-h-screen bg-[#0a0a0f] text-white">
      <Sidebar />
      <div className="flex-1 p-4 space-y-3">
        <h1 className="font-mono text-zinc-400 uppercase tracking-widest text-xs mb-4">
          Agenten-Zentrale — Röntgenblick
        </h1>

        <AgentCard
          title="Context Agent"
          healthy={agents.context?.healthy}
          lastUpdate={grss?.data_quality?.last_update}
        >
          <div className="flex flex-wrap gap-y-1">
            <KV label="NDX" value={grss?.macro?.ndx_status}
              color={grss?.macro?.ndx_status === "BULLISH" ? "text-emerald-400" : "text-red-400"} />
            <KV label="VIX" value={grss?.macro?.vix?.toFixed(1)}
              color={(grss?.macro?.vix ?? 20) > 25 ? "text-red-400" : "text-zinc-200"} />
            <KV label="10Y" value={grss?.macro?.yields_10y?.toFixed(2) + "%"} />
            <KV label="Funding" value={grss?.derivatives?.funding_rate !== null
              ? (grss.derivatives.funding_rate * 100).toFixed(4) + "%" : "—"} />
            <KV label="PCR" value={grss?.derivatives?.put_call_ratio?.toFixed(2)}
              color={(grss?.derivatives?.put_call_ratio ?? 1) < 0.5 ? "text-emerald-400" : "text-zinc-200"} />
            <KV label="DVOL" value={grss?.derivatives?.dvol?.toFixed(0)} />
            <KV label="OI-Delta" value={grss?.derivatives?.oi_delta_pct !== null
              ? (grss.derivatives.oi_delta_pct > 0 ? "+" : "") + grss.derivatives.oi_delta_pct.toFixed(1) + "%" : "—"} />
            <KV label="F&G" value={grss?.sentiment?.fear_greed} />
            <KV label="M2 YoY" value={grss?.macro?.m2_yoy_pct !== null
              ? (grss.macro.m2_yoy_pct > 0 ? "+" : "") + grss.macro.m2_yoy_pct?.toFixed(1) + "%" : "—"} />
            <KV label="USDT Δ7d" value={grss?.sentiment?.stablecoin_delta_bn !== null
              ? (grss.sentiment.stablecoin_delta_bn > 0 ? "+" : "") + grss.sentiment.stablecoin_delta_bn?.toFixed(1) + "B" : "—"} />
            <KV label="LLM Sent." value={grss?.sentiment?.llm_news_sentiment?.toFixed(2)}
              color={(grss?.sentiment?.llm_news_sentiment ?? 0) > 0.3 ? "text-emerald-400" :
                     (grss?.sentiment?.llm_news_sentiment ?? 0) < -0.3 ? "text-red-400" : "text-zinc-200"} />
            <KV label="News Silence" value={grss?.data_quality?.news_silence_seconds !== null
              ? grss.data_quality.news_silence_seconds + "s" : "—"}
              color={(grss?.data_quality?.news_silence_seconds ?? 0) > 1800 ? "text-red-400" : "text-zinc-200"} />
            <KV label="Sources" value={`${grss?.data_quality?.fresh_source_count ?? 0}/5`}
              color={(grss?.data_quality?.fresh_source_count ?? 0) >= 4 ? "text-emerald-400" : "text-amber-400"} />
          </div>
          <div className={`text-sm font-bold mt-1 ${
            (grss?.score ?? 0) >= 48 ? "text-emerald-400" :
            (grss?.score ?? 0) >= 35 ? "text-amber-400" : "text-red-400"
          }`}>
            → GRSS {grss?.score?.toFixed(1) ?? "—"} (EMA) | Raw {grss?.score_raw?.toFixed(1) ?? "—"}
            {grss?.velocity_30min !== null
              ? ` | Velocity ${grss.velocity_30min > 0 ? "▲" : "▼"} ${grss.velocity_30min?.toFixed(1)} letzte 30min` : ""}
          </div>
          {grss?.veto_active && (
            <div className="text-red-400">→ Veto aktiv: {grss.reason}</div>
          )}
          {grss?.data_quality?.funding_settlement_window && (
            <div className="text-amber-400">⚠ Funding-Settlement-Fenster aktiv</div>
          )}
        </AgentCard>

        <AgentCard
          title="Quant Agent"
          healthy={agents.quant?.healthy}
          lastUpdate={null}
        >
          <div className="flex flex-wrap gap-y-1">
            <KV label="OFI" value={market.ofi !== null ? (market.ofi > 0 ? "+" : "") + market.ofi?.toFixed(0) : "—"}
              color={Math.abs(market.ofi ?? 0) >= 500 ? "text-white font-bold" : "text-zinc-500"} />
            <KV label="Threshold" value="500" color="text-zinc-500" />
            <KV label="CVD" value={market.cvd !== null ? (market.cvd > 0 ? "+" : "") + market.cvd?.toFixed(0) : "—"}
              color={(market.cvd ?? 0) > 0 ? "text-emerald-400" : "text-red-400"} />
            <KV label="VAMP" value={market.vamp?.toLocaleString()} />
            <KV label="BTC" value={"$" + market.btc_price?.toLocaleString()} />
          </div>

          {market.ofi !== null && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-zinc-600 text-xs">OFI</span>
              <div className="flex-1 h-2 bg-zinc-800 rounded overflow-hidden">
                <div className="h-full rounded"
                  style={{
                    width: `${Math.min(100, Math.abs(market.ofi) / 10)}%`,
                    backgroundColor: market.ofi > 0 ? "#22c55e" : "#ef4444",
                    marginLeft: market.ofi < 0 ? "auto" : undefined,
                  }} />
              </div>
              <span className="text-zinc-600 text-xs">Threshold 500</span>
            </div>
          )}

          <div className="text-zinc-500 mt-1">
            {Math.abs(market.ofi ?? 0) < 500
              ? "→ OFI unter Threshold — kein LLM-Call, kein Trade"
              : "→ OFI über Threshold — LLM-Cascade wird getriggert"}
          </div>

          {stats && (
            <div className="flex gap-4 mt-1 text-xs">
              <span className="text-zinc-500">Letzte 50 Zyklen:</span>
              <span className="text-zinc-400">OFI zu niedrig: <span className="text-zinc-200">{stats.ofi_below_threshold}</span></span>
              <span className="text-zinc-400">Cascade HOLD: <span className="text-amber-400">{stats.cascade_hold}</span></span>
              <span className="text-zinc-400">Signals: <span className="text-emerald-400">{stats.signals_generated}</span></span>
            </div>
          )}
        </AgentCard>

        <AgentCard title="LLM Cascade" healthy={cascade?.ollama_available}>
          {cascade ? (
            <>
              <div className="flex flex-wrap gap-y-1">
                <KV label="Ollama" value={cascade.ollama_available ? "online" : "offline"}
                  color={cascade.ollama_available ? "text-emerald-400" : "text-red-400"} />
                <KV label="Modell 1" value={cascade.model_layer1 ?? "qwen2.5:14b"} />
                <KV label="Modell 2" value={cascade.model_layer2 ?? "deepseek-r1:14b"} />
              </div>

              {lastCascadeRun && (
                <div className="mt-2 space-y-1">
                  <div className="text-zinc-500">Letzter Cascade-Run: {timeAgo(lastCascadeRun.ts)}</div>
                  <div>
                    <span className="text-zinc-500">L1 (qwen2.5): </span>
                    <span className="text-zinc-200">regime={lastCascadeRun.regime ?? "—"}</span>
                    {lastCascadeRun.layer1_confidence !== null && (
                      <span className={lastCascadeRun.layer1_confidence >= 0.60
                        ? "text-emerald-400 ml-2" : "text-amber-400 ml-2"}>
                        conf {lastCascadeRun.layer1_confidence?.toFixed(2)}
                        {lastCascadeRun.layer1_confidence < 0.60 ? " (< 0.60 Gate)" : " ✓"}
                      </span>
                    )}
                  </div>
                  {lastCascadeRun.layer2_decision && (
                    <div>
                      <span className="text-zinc-500">L2 (deepseek-r1): </span>
                      <span className={lastCascadeRun.layer2_decision === "HOLD"
                        ? "text-amber-400" : "text-emerald-400"}>
                        {lastCascadeRun.layer2_decision}
                      </span>
                    </div>
                  )}
                  {lastCascadeRun.layer3_blocked !== null && (
                    <div>
                      <span className="text-zinc-500">L3 (Advocatus): </span>
                      <span className={lastCascadeRun.layer3_blocked ? "text-red-400" : "text-emerald-400"}>
                        {lastCascadeRun.layer3_blocked ? "BLOCKIERT" : "Kein Einwand"}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {cascade.recent_decisions && (
                <div className="mt-2">
                  <div className="text-zinc-500 mb-1">Cascade-Runs (nur wenn OFI erreicht):</div>
                  {(cascade.recent_decisions as any[]).slice(0, 5).map((d: any, i: number) => (
                    <div key={i} className="text-xs text-zinc-500">
                      {new Date(d.timestamp ?? d.ts).toLocaleTimeString("de-DE")} —{" "}
                      <span className={d.decision === "BUY" || d.decision === "SELL"
                        ? "text-emerald-400" : "text-amber-400"}>{d.decision ?? d.outcome}</span>
                      {d.regime ? ` regime=${d.regime}` : ""}
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <span className="text-zinc-600">Lade Cascade-Status...</span>
          )}
        </AgentCard>

        <AgentCard title="Risk Agent" healthy={agents.risk?.healthy}>
          <div className="flex flex-wrap gap-y-1">
            <KV label="Veto" value={veto ? "AKTIV" : "INAKTIV"}
              color={veto ? "text-red-400 font-bold" : "text-emerald-400"} />
            {vetoReason && <span className="text-zinc-400">{vetoReason}</span>}
          </div>

          {vetoHistory.length > 0 && (
            <div className="mt-2">
              <div className="text-zinc-500 mb-1">Veto-Zustandswechsel:</div>
              {vetoHistory.slice(0, 5).map((e, i) => (
                <div key={i} className="text-xs flex gap-3">
                  <span className="text-zinc-600">
                    {new Date(e.ts).toLocaleTimeString("de-DE")}
                  </span>
                  <span className={e.change === "VETO_ON" ? "text-red-400" : "text-emerald-400"}>
                    {e.change === "VETO_ON" ? "VETO AN" : "VETO AUS"}
                  </span>
                  <span className="text-zinc-500 truncate">{e.reason}</span>
                </div>
              ))}
            </div>
          )}
        </AgentCard>

        <AgentCard title="Execution Agent" healthy={agents.execution?.healthy}>
          <div className="flex flex-wrap gap-y-1">
            <KV label="DRY_RUN" value={telemetry?.dry_run ? "aktiv" : "DEAKTIVIERT"}
              color={telemetry?.dry_run ? "text-yellow-400" : "text-red-400 font-bold"} />
            <KV label="LIVE_APPROVED" value={telemetry?.live_trading_approved ? "JA" : "nein"}
              color={telemetry?.live_trading_approved ? "text-emerald-400" : "text-zinc-500"} />
          </div>
          <div className="text-zinc-500 mt-1">
            {telemetry?.dry_run
              ? "Kein echtes Kapital. Alle Trades sind simuliert."
              : "⚠ DRY_RUN ist deaktiviert — echte Orders möglich"}
          </div>
        </AgentCard>
      </div>
    </div>
  );
}
