"use client";

import { useState } from "react";
import {
  BookOpen,
  Cpu,
  Database,
  Brain,
  Shield,
  TrendingUp,
  Activity,
  ChevronRight,
  Layers,
  Zap,
  Lock,
  Globe,
  Server,
  GitBranch,
  Terminal
} from "lucide-react";

const SECTIONS = [
  {
    id: "control",
    title: "Transparenz & Kontrolle",
    icon: Shield,
    render: () => (
      <div className="space-y-6">
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-[0.28em] text-indigo-400 font-bold">Leitbild</p>
          <h2 className="text-3xl font-bold text-white">Bruno soll jederzeit erklärbar, prüfbar und kontrollierbar sein.</h2>
          <p className="text-slate-300 leading-relaxed max-w-3xl">
            Diese Seite ist kein Marketing-Text, sondern die Bedienungsanleitung der Plattform. Du siehst hier,
            <strong className="text-white"> welche Daten genutzt werden</strong>, <strong className="text-white">wie Entscheidungen entstehen</strong>,
            <strong className="text-white"> welche Schutzmechanismen greifen</strong> und <strong className="text-white">wo du das System anpassen kannst</strong>.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-2xl border border-[#1a1a2e] bg-[#080810]">
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500 mb-2">Beobachten</div>
            <div className="text-lg font-semibold text-white mb-2">Was ist gerade los?</div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Dashboard und Monitor zeigen API-Status, Agenten, offene Trades, Marktdaten und den aktuellen Zustand der Kaskade in Echtzeit.
            </p>
          </div>

          <div className="p-4 rounded-2xl border border-[#1a1a2e] bg-[#080810]">
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500 mb-2">Verstehen</div>
            <div className="text-lg font-semibold text-white mb-2">Warum hat Bruno so entschieden?</div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Trading und Reports erklären jede Kaskade: frische Daten, GRSS, Quant, Risk-Vetos, Positionsregeln und den finalen Signal- oder Hold-Zweig.
            </p>
          </div>

          <div className="p-4 rounded-2xl border border-[#1a1a2e] bg-[#080810]">
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500 mb-2">Kontrollieren</div>
            <div className="text-lg font-semibold text-white mb-2">Was kann ich beeinflussen?</div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Einstellungen enthalten Presets, Schwellen, Risikogrenzen, Deepseek-Test und Betriebsmodi – damit du die Plattform bewusst steuern kannst.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: "Agenten", value: "6", hint: "Spezialisierte Module" },
            { label: "Entscheidungsgates", value: "6", hint: "Jeder Schritt sichtbar" },
            { label: "Speicher", value: "DB + Redis", hint: "Kurzfristig + dauerhaft" },
            { label: "Mode", value: "Paper Only", hint: "Keine Live-Orders" },
          ].map((item) => (
            <div key={item.label} className="rounded-xl border border-[#1a1a2e] bg-[#0c0c18] p-4">
              <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">{item.label}</div>
              <div className="text-xl font-bold text-white mt-1">{item.value}</div>
              <div className="text-xs text-slate-500 mt-1">{item.hint}</div>
            </div>
          ))}
        </div>

        <div className="p-4 rounded-2xl border border-indigo-800 bg-indigo-950/15">
          <div className="text-xs uppercase tracking-[0.24em] text-indigo-400 mb-3">Transparenter Datenfluss</div>
          <pre className="text-xs text-slate-300 overflow-x-auto leading-6">{`Datenquellen → Context/GRSS → Technical/Quant → Risk Vetos → Portfolio Guard → Execution → Reports/Deepseek

Jede Stufe schreibt nachvollziehbare Zustände in Redis/DB und wird im UI sichtbar gemacht.`}</pre>
        </div>
      </div>
    )
  },
  {
    id: "overview",
    title: "Übersicht",
    icon: BookOpen,
    render: () => (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold text-white">Willkommen bei Bruno v2</h2>
        <p className="text-slate-300">Bruno ist ein <strong className="text-white">deterministischer, Multi-Agent Trading Bot</strong> für Bitcoin (BTC/USDT).</p>
        
        <h3 className="text-xl font-semibold text-indigo-400 mt-6">Kernprinzipien</h3>
        <ul className="list-disc list-inside text-slate-300 space-y-1">
          <li><strong className="text-white">Deterministisch</strong>: Keine Zufälligkeit, reproduzierbare Entscheidungen</li>
          <li><strong className="text-white">Multi-Agent</strong>: Spezialisierte Agenten für verschiedene Aufgaben</li>
          <li><strong className="text-white">Risiko-zuerst</strong>: Kapitalschutz hat Priorität über Gewinn</li>
          <li><strong className="text-white">Paper-Trading</strong>: Hard-locked auf Demo-Modus für Sicherheit</li>
        </ul>

        <h3 className="text-xl font-semibold text-indigo-400 mt-6">Architektur</h3>
        <pre className="bg-[#080810] p-4 rounded-lg text-xs text-slate-400 overflow-x-auto">
{`┌─────────────────────────────────────────┐
│           FRONTEND (Next.js)            │
│    Dashboard • Trading • Monitor        │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         BACKEND (FastAPI)               │
│  REST API • WebSockets • Redis • DB     │
└─────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌───────┐    ┌──────────┐    ┌──────────┐
│Agenten│    │  Redis   │    │PostgreSQL│
│       │    │  Cache   │    │   DB     │
└───────┘    └──────────┘    └──────────┘`}
        </pre>
      </div>
    )
  },
  {
    id: "agents",
    title: "Die Agenten",
    icon: Cpu,
    render: () => (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-white">Die 6 Agenten</h2>
        <p className="text-slate-300">Bruno besteht aus 6 spezialisierten Agenten, die in einer Pipeline zusammenarbeiten.</p>

        <div className="space-y-4">
          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">1. Ingestion Agent</h3>
            <p className="text-sm text-slate-400 mt-1">Daten von externen APIs sammeln</p>
            <ul className="list-disc list-inside text-xs text-slate-500 mt-2">
              <li>Binance (Preise, Liquidationen, OI)</li>
              <li>CoinMarketCap (News, Sentiment)</li>
              <li>yFinance (Makro-Daten, VIX)</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">2. Context Agent</h3>
            <p className="text-sm text-slate-400 mt-1">Global Risk Stress Score (GRSS) berechnen</p>
            <div className="grid grid-cols-2 gap-2 mt-2 text-xs text-slate-500">
              <div>VIX (Volatilität)</div>
              <div>NDX Trend</div>
              <div>10Y Yields</div>
              <div>Put/Call Ratio</div>
              <div>Funding Rate</div>
              <div>LLM News Sentiment</div>
            </div>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">3. Technical Analysis Agent</h3>
            <p className="text-sm text-slate-400 mt-1">Chart-Technische Analyse</p>
            <ul className="list-disc list-inside text-xs text-slate-500 mt-2">
              <li>Multi-Timeframe Analyse</li>
              <li>Support/Resistance Levels</li>
              <li>Pattern Erkennung</li>
              <li>MTF Filter (nur wenn HTF = LTF)</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">4. Quant Agent (QuantAgentV4)</h3>
            <p className="text-sm text-slate-400 mt-1">Order Flow & Mikrostruktur</p>
            <div className="grid grid-cols-2 gap-2 mt-2 text-xs text-slate-500">
              <div>OFI (Order Flow)</div>
              <div>CVD (Volume Delta)</div>
              <div>VAMP</div>
              <div>Liquidation Clusters</div>
              <div>OI Delta</div>
            </div>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">5. Risk Agent</h3>
            <p className="text-sm text-slate-400 mt-1">6 Hard Vetos überwachen</p>
            <ol className="list-decimal list-inside text-xs text-slate-500 mt-2 space-y-1">
              <li>Data Gap (fehlende Daten)</li>
              <li>Stale Context (alte GRSS)</li>
              <li>VIX &gt; 45 (extreme Volatilität)</li>
              <li>System Pause (manuell)</li>
              <li>Death Zone (GRSS &lt; 20)</li>
              <li>Daily Drawdown (3% Verlust oder 3x verlieren)</li>
            </ol>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">6. Execution Agent</h3>
            <p className="text-sm text-slate-400 mt-1">Order-Ausführung</p>
            <ul className="list-disc list-inside text-xs text-slate-500 mt-2">
              <li>Paper Trading (Bybit Demo)</li>
              <li>Breakeven Stop (SL → Entry bei +0.5%)</li>
              <li>ATR-basierte Position Sizing</li>
              <li>Drawdown Protection</li>
            </ul>
          </div>
        </div>
      </div>
    )
  },
  {
    id: "cascade",
    title: "Entscheidungs-Kaskade",
    icon: GitBranch,
    render: () => (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-white">Die 6-Gate Entscheidungs-Kaskade</h2>
        <p className="text-slate-300">Jeder Trade durchläuft 6 Gates. Ein einziges BLOCK stoppt den Trade.</p>

        <pre className="bg-[#080810] p-4 rounded-lg text-xs text-slate-400 overflow-x-auto">
{`Gate 1: Data Freshness
├── Alle Datenquellen online?
├── Letzte Updates < 60s?
└── BLOCK → Keine frischen Daten

Gate 2: GRSS Pre-Check
├── GRSS Score ≥ 20?
├── Kein "Death Zone"?
└── BLOCK → Extremstress (GRSS < 20)

Gate 3: Risk Veto
├── Kein aktives Veto?
├── VIX < 45?
├── Daily Drawdown nicht erreicht?
└── BLOCK → Risiko zu hoch

Gate 4: LLM Cascade (zeitbasiert)
├── Mindestzeit seit letztem Signal?
├── Composite Score ≥ Threshold?
└── BLOCK → Kein Signal oder zu früh

Gate 5: Position Guard
├── Keine offene Position?
└── BLOCK → Position aktiv

Gate 6: Portfolio Limits
├── Daily Limit nicht erreicht?
├── Consecutive Losses < 3?
└── BLOCK → Limits erreicht

[SIGNAL BUY/SELL]`}
        </pre>

        <h3 className="text-xl font-semibold text-indigo-400">Composite Scoring (v2)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="text-left p-2">Komponente</th>
                <th className="text-left p-2">Gewicht</th>
                <th className="text-left p-2">Beschreibung</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-t border-[#1a1a2e]">
                <td className="p-2">GRSS</td>
                <td className="p-2">40%</td>
                <td className="p-2">Global Risk Score</td>
              </tr>
              <tr className="border-t border-[#1a1a2e]">
                <td className="p-2">OFI</td>
                <td className="p-2">25%</td>
                <td className="p-2">Order Flow Imbalance</td>
              </tr>
              <tr className="border-t border-[#1a1a2e]">
                <td className="p-2">Technical</td>
                <td className="p-2">15%</td>
                <td className="p-2">MTF Alignment</td>
              </tr>
              <tr className="border-t border-[#1a1a2e]">
                <td className="p-2">Sentiment</td>
                <td className="p-2">10%</td>
                <td className="p-2">News Sentiment</td>
              </tr>
              <tr className="border-t border-[#1a1a2e]">
                <td className="p-2">Funding</td>
                <td className="p-2">10%</td>
                <td className="p-2">Funding Divergence</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="p-4 bg-indigo-950/20 border border-indigo-800 rounded-lg">
          <p className="text-sm text-indigo-400">Threshold: 65+ für Signal (konfigurierbar)</p>
        </div>
      </div>
    )
  },
  {
    id: "apis",
    title: "APIs & Datenquellen",
    icon: Globe,
    render: () => (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-white">APIs & Datenquellen</h2>

        <h3 className="text-xl font-semibold text-indigo-400">Primäre Datenquellen</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h4 className="font-medium text-white">Binance (REST + WebSocket)</h4>
            <ul className="list-disc list-inside text-xs text-slate-400 mt-2">
              <li>Market Data: Ticker, Orderbook, Trades</li>
              <li>Liquidation Data: Liquidation-Heatmap</li>
              <li>Open Interest: OI-Delta, Perp-Basis</li>
              <li>Funding Rate: 8h Funding</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h4 className="font-medium text-white">CoinMarketCap</h4>
            <ul className="list-disc list-inside text-xs text-slate-400 mt-2">
              <li>Bitcoin Bundle: BTC-spezifische Metriken</li>
              <li>Content/News: News-Feed für Sentiment</li>
              <li>Global Metrics: Marktübersicht</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h4 className="font-medium text-white">yFinance</h4>
            <ul className="list-disc list-inside text-xs text-slate-400 mt-2">
              <li>VIX: Volatilitäts-Index (^VIX)</li>
              <li>NDX: Nasdaq-100 Trend (^NDX)</li>
              <li>Yields: 10Y Treasury (^TNX)</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h4 className="font-medium text-white">Bybit (Demo/Testnet)</h4>
            <ul className="list-disc list-inside text-xs text-slate-400 mt-2">
              <li>Paper Trading: Demo API</li>
              <li>Order Execution: Limit/Market Orders</li>
              <li>Position Management: SL/TP</li>
            </ul>
          </div>
        </div>

        <h3 className="text-xl font-semibold text-indigo-400 mt-6">Redis Keys (Wichtige)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="text-left p-2">Key</th>
                <th className="text-left p-2">Beschreibung</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-t border-[#1a1a2e]"><td className="p-2 font-mono text-xs">bruno:context:grss</td><td className="p-2">Aktueller GRSS Score</td></tr>
              <tr className="border-t border-[#1a1a2e]"><td className="p-2 font-mono text-xs">bruno:quant:micro</td><td className="p-2">OFI, CVD, VAMP</td></tr>
              <tr className="border-t border-[#1a1a2e]"><td className="p-2 font-mono text-xs">bruno:veto:state</td><td className="p-2">Aktive Vetos</td></tr>
              <tr className="border-t border-[#1a1a2e]"><td className="p-2 font-mono text-xs">bruno:decisions:feed</td><td className="p-2">Letzte Entscheidungen</td></tr>
              <tr className="border-t border-[#1a1a2e]"><td className="p-2 font-mono text-xs">bruno:positions:BTCUSDT</td><td className="p-2">Offene Position</td></tr>
              <tr className="border-t border-[#1a1a2e]"><td className="p-2 font-mono text-xs">bruno:health:sources</td><td className="p-2">API-Health Status</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    )
  },
  {
    id: "features",
    title: "Key Features",
    icon: Zap,
    render: () => (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-white">Key Features</h2>

        <div className="space-y-4">
          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">1. Breakeven Stop</h3>
            <p className="text-sm text-slate-400 mt-2">Wenn Position im Profit &gt; 0.5%:</p>
            <pre className="mt-2 p-2 bg-black/30 rounded text-xs text-slate-500">Stop-Loss → Entry Price + 0.1%</pre>
            <p className="text-xs text-slate-500 mt-2">Schützt vor Rückschlägen bei Gewinnen.</p>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">2. Daily Drawdown Protection</h3>
            <p className="text-sm text-slate-400 mt-2">Trigger:</p>
            <ul className="list-disc list-inside text-xs text-slate-500 mt-1">
              <li>3% Verlust an einem Tag, ODER</li>
              <li>3 consecutive losses</li>
            </ul>
            <p className="text-sm text-slate-400 mt-3">Aktion:</p>
            <ul className="list-disc list-inside text-xs text-slate-500 mt-1">
              <li>24h Trading-Block</li>
              <li>Manueller Reset erforderlich</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">3. ATR Position Sizing</h3>
            <p className="text-sm text-slate-400 mt-2">Position-Größe basiert auf:</p>
            <pre className="mt-2 p-2 bg-black/30 rounded text-xs text-slate-500">Size = Risk Amount / (ATR × Multiplier)</pre>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">4. MTF Filter (Multi-Timeframe)</h3>
            <p className="text-sm text-slate-400 mt-2">Trade nur wenn:</p>
            <ul className="list-disc list-inside text-xs text-slate-500 mt-1">
              <li>HTF (1h) Trend = LTF (5m) Trend</li>
              <li>Vermeidet Gegen-Trend-Trades</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">5. Sweep Detection</h3>
            <p className="text-sm text-slate-400 mt-2">Erkennt Liquiditäts-Sweeps:</p>
            <ul className="list-disc list-inside text-xs text-slate-500 mt-1">
              <li>Stop-Loss Raids</li>
              <li>Breakout-Fakeouts</li>
              <li>Bonus-Punkte in Composite Score</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">6. Deepseek Integration</h3>
            <p className="text-sm text-slate-400 mt-2">Post-Trade Analysis:</p>
            <ul className="list-disc list-inside text-xs text-slate-500 mt-1">
              <li>Nach Trade-Close: Daten an Deepseek API</li>
              <li>LLM bewertet Trade (1-10)</li>
              <li>Analyse wird in DB gespeichert</li>
              <li>Sichtbar in Reports</li>
            </ul>
            <p className="text-xs text-indigo-400 mt-3">Keine Live-Entscheidungen – nur Lernen!</p>
          </div>
        </div>
      </div>
    )
  },
  {
    id: "safety",
    title: "Sicherheit",
    icon: Lock,
    render: () => (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-white">Sicherheits-Features</h2>

        <div className="p-4 bg-emerald-950/20 border border-emerald-800 rounded-lg">
          <h3 className="text-lg font-medium text-emerald-400">Paper Trading Only (Hard-Lock)</h3>
          <p className="text-sm text-slate-400 mt-2">Bruno ist hard-locked auf Paper Trading:</p>
          <pre className="mt-2 p-2 bg-black/30 rounded text-xs text-slate-500">PAPER_TRADING_ONLY = true</pre>
          <ul className="list-disc list-inside text-xs text-slate-500 mt-3">
            <li>Alle Orders gehen an Bybit Demo</li>
            <li>Keine echten Gelder riskiert</li>
            <li>Authentifizierung blockiert Live-Trading</li>
          </ul>
        </div>

        <h3 className="text-xl font-semibold text-indigo-400">6 Hard Vetos</h3>
        <p className="text-sm text-slate-400">Jedes Veto blockiert Trading sofort:</p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { name: "Data Gap", desc: "Fehlende oder veraltete Daten" },
            { name: "Stale Context", desc: "GRSS älter als 5 Minuten" },
            { name: "VIX Spike", desc: "VIX > 45 (extreme Angst)" },
            { name: "System Pause", desc: "Manueller Halt" },
            { name: "Death Zone", desc: "GRSS < 20 (Systemstress)" },
            { name: "Daily Drawdown", desc: "3% Verlust oder 3 Verlierer" },
          ].map((veto, i) => (
            <div key={veto.name} className="flex items-start gap-3 p-3 bg-[#080810] rounded-lg border border-[#1a1a2e]">
              <span className="w-6 h-6 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center text-xs font-bold">{i + 1}</span>
              <div>
                <div className="font-medium text-slate-300">{veto.name}</div>
                <div className="text-xs text-slate-500">{veto.desc}</div>
              </div>
            </div>
          ))}
        </div>

        <h3 className="text-xl font-semibold text-indigo-400 mt-6">Risk Limits</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 bg-[#080810] rounded-lg"><div className="text-xs text-slate-500">Max Leverage</div><div className="text-lg font-bold text-slate-300">1x</div></div>
          <div className="p-3 bg-[#080810] rounded-lg"><div className="text-xs text-slate-500">Max Position Size</div><div className="text-lg font-bold text-slate-300">100% Capital</div></div>
          <div className="p-3 bg-[#080810] rounded-lg"><div className="text-xs text-slate-500">Stop-Loss</div><div className="text-lg font-bold text-slate-300">1-3%</div></div>
          <div className="p-3 bg-[#080810] rounded-lg"><div className="text-xs text-slate-500">Take-Profit</div><div className="text-lg font-bold text-slate-300">2:1 / 3:1</div></div>
        </div>
      </div>
    )
  },
  {
    id: "techstack",
    title: "Tech Stack",
    icon: Server,
    render: () => (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-white">Technologie-Stack</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">Backend</h3>
            <ul className="list-disc list-inside text-sm text-slate-400 mt-2 space-y-1">
              <li><strong className="text-slate-300">FastAPI</strong> - Python Web Framework</li>
              <li><strong className="text-slate-300">SQLAlchemy</strong> - ORM für PostgreSQL</li>
              <li><strong className="text-slate-300">Redis</strong> - Cache & Pub/Sub</li>
              <li><strong className="text-slate-300">Celery</strong> - Task Queue (optional)</li>
              <li><strong className="text-slate-300">Alembic</strong> - DB Migrations</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">Frontend</h3>
            <ul className="list-disc list-inside text-sm text-slate-400 mt-2 space-y-1">
              <li><strong className="text-slate-300">Next.js 14</strong> - React Framework</li>
              <li><strong className="text-slate-300">TypeScript</strong> - Type Safety</li>
              <li><strong className="text-slate-300">Tailwind CSS</strong> - Styling</li>
              <li><strong className="text-slate-300">Recharts</strong> - Charts & Grafiken</li>
              <li><strong className="text-slate-300">Lucide</strong> - Icons</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">Datenbanken</h3>
            <ul className="list-disc list-inside text-sm text-slate-400 mt-2 space-y-1">
              <li><strong className="text-slate-300">PostgreSQL</strong> - Persistente Daten</li>
              <li><strong className="text-slate-300">Redis</strong> - Echtzeit-Daten</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">Externe APIs</h3>
            <ul className="list-disc list-inside text-sm text-slate-400 mt-2 space-y-1">
              <li><strong className="text-slate-300">Binance</strong> - Marktdaten</li>
              <li><strong className="text-slate-300">Bybit Demo</strong> - Paper Trading</li>
              <li><strong className="text-slate-300">CoinMarketCap</strong> - News</li>
              <li><strong className="text-slate-300">yFinance</strong> - Makro</li>
              <li><strong className="text-slate-300">Deepseek</strong> - LLM Analysis</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">Deployment</h3>
            <ul className="list-disc list-inside text-sm text-slate-400 mt-2 space-y-1">
              <li><strong className="text-slate-300">Docker</strong> - Containerisierung</li>
              <li><strong className="text-slate-300">Docker Compose</strong> - Multi-Container</li>
            </ul>
          </div>

          <div className="p-4 bg-[#080810] rounded-lg border border-[#1a1a2e]">
            <h3 className="text-lg font-medium text-indigo-400">Entwicklung</h3>
            <ul className="list-disc list-inside text-sm text-slate-400 mt-2 space-y-1">
              <li><strong className="text-slate-300">Git</strong> - Versionskontrolle</li>
              <li><strong className="text-slate-300">Windsurf/Cascade</strong> - AI-Assisted</li>
            </ul>
          </div>
        </div>
      </div>
    )
  }
];

export default function JourneyPage() {
  const [activeSection, setActiveSection] = useState("control");

  const activeContent = SECTIONS.find(s => s.id === activeSection);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      <div className="flex h-screen">
        {/* Sidebar Navigation */}
        <div className="w-64 bg-[#08081a] border-r border-[#1a1a2e] p-4 overflow-y-auto">
          <div className="mb-6">
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Journey
            </h1>
            <p className="text-xs text-slate-500 mt-1">Bruno verstehen</p>
          </div>

          <nav className="space-y-1">
            {SECTIONS.map((section) => {
              const Icon = section.icon;
              const isActive = activeSection === section.id;

              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                    isActive
                      ? "bg-indigo-500/10 text-indigo-400 border-l-2 border-indigo-500"
                      : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-sm">{section.title}</span>
                </button>
              );
            })}
          </nav>

          {/* Quick Stats */}
          <div className="mt-8 p-3 bg-[#0c0c18] rounded-lg border border-[#1a1a2e]">
            <div className="text-xs text-slate-500 mb-2">System Info</div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Version</span>
                <span className="text-emerald-400">v2.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Agenten</span>
                <span className="text-indigo-400">6</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Gates</span>
                <span className="text-indigo-400">6</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Mode</span>
                <span className="text-amber-400">Paper</span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-8">
          {activeContent && (
            <div className="max-w-5xl space-y-6">
              <div className="rounded-3xl border border-[#1a1a2e] bg-gradient-to-br from-indigo-950/30 via-[#0c0c18] to-[#080810] p-6 lg:p-8 shadow-2xl shadow-black/20">
                <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
                  <div className="space-y-3 max-w-3xl">
                    <div className="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-slate-500 font-bold">
                      <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                      Journey · Bruno verstehen
                    </div>
                    <div className="flex items-center gap-3">
                      <activeContent.icon className="w-9 h-9 text-indigo-400" />
                      <h1 className="text-3xl lg:text-4xl font-bold">{activeContent.title}</h1>
                    </div>
                    <p className="text-slate-300 leading-relaxed max-w-3xl">
                      Dieser Bereich erklärt die Plattform so, dass du Entscheidungen, Risiken, Datenflüsse und Kontrollpunkte wirklich nachvollziehen kannst.
                      Fokus: maximale Transparenz, klare Kontrolle und eine saubere Trennung zwischen Live-Entscheidung und Lernen.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-3 min-w-[260px]">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Status</div>
                      <div className="mt-1 text-sm font-semibold text-white">Operative Dokumentation</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Modus</div>
                      <div className="mt-1 text-sm font-semibold text-amber-400">Paper Only</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Kern</div>
                      <div className="mt-1 text-sm font-semibold text-emerald-400">6 Agenten · 6 Gates</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Ziel</div>
                      <div className="mt-1 text-sm font-semibold text-indigo-400">Warum jede Entscheidung?</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-6 lg:p-7">
                {activeContent.render()}
              </div>

              {/* Navigation Footer */}
              <div className="flex justify-between mt-8 pt-6 border-t border-[#1a1a2e]">
                {(() => {
                  const currentIndex = SECTIONS.findIndex(s => s.id === activeSection);
                  const prev = SECTIONS[currentIndex - 1];
                  const next = SECTIONS[currentIndex + 1];

                  return (
                    <>
                      <div>
                        {prev && (
                          <button
                            onClick={() => setActiveSection(prev.id)}
                            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
                          >
                            <ChevronRight className="w-4 h-4 rotate-180" />
                            <span>{prev.title}</span>
                          </button>
                        )}
                      </div>
                      <div>
                        {next && (
                          <button
                            onClick={() => setActiveSection(next.id)}
                            className="flex items-center gap-2 text-indigo-400 hover:text-indigo-300 transition-colors"
                          >
                            <span>{next.title}</span>
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
