"use client";

import { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";

interface TestResult {
  name: string;
  category: string;
  status: "success" | "error" | "warning";
  response_time_ms: number;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
}

interface SystemTestData {
  overall_status: string;
  total_tests: number;
  passed: number;
  failed: number;
  tests: TestResult[];
  execution_time_ms: number;
  timestamp: string;
}

interface FlowRun {
  id: string;
  name: string;
  status: "success" | "error" | "running";
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  details?: Record<string, any>;
}

interface FlowStats {
  total: number;
  success: number;
  error: number;
  running: number;
  success_rate: number;
}

interface SchedulerStatus {
  status: string;
  enabled: boolean;
  interval_minutes: number;
  last_run?: string;
  next_run?: string;
  run_count: number;
  is_running: boolean;
  is_paused: boolean;
}

export default function EinstellungenPage() {
  const [activeTab, setActiveTab] = useState<"systemtest" | "flows">("systemtest");
  const [testData, setTestData] = useState<SystemTestData | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [flows, setFlows] = useState<FlowRun[]>([]);
  const [flowStats, setFlowStats] = useState<FlowStats | null>(null);
  const [flowsLoading, setFlowsLoading] = useState(false);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [schedulerLoading, setSchedulerLoading] = useState(false);

  const runSystemTest = async () => {
    setTestLoading(true);
    try {
      const response = await fetch("http://localhost:8000/api/v1/systemtest/run");
      const data = await response.json();
      setTestData(data);
    } catch (error) {
      console.error("Systemtest fehlgeschlagen:", error);
    } finally {
      setTestLoading(false);
    }
  };

  const loadFlows = async () => {
    setFlowsLoading(true);
    try {
      const [flowsRes, statsRes] = await Promise.all([
        fetch("http://localhost:8000/api/v1/systemtest/flows"),
        fetch("http://localhost:8000/api/v1/systemtest/flows/stats"),
      ]);
      const flowsData = await flowsRes.json();
      const statsData = await statsRes.json();
      setFlows(flowsData.flows || []);
      setFlowStats(statsData);
    } catch (error) {
      console.error("Flows laden fehlgeschlagen:", error);
    } finally {
      setFlowsLoading(false);
    }
  };

  const loadSchedulerStatus = async () => {
    setSchedulerLoading(true);
    try {
      const response = await fetch("http://localhost:8000/api/v1/systemtest/scheduler/status");
      const data = await response.json();
      setSchedulerStatus(data);
    } catch (error) {
      console.error("Scheduler Status laden fehlgeschlagen:", error);
    } finally {
      setSchedulerLoading(false);
    }
  };

  const startScheduler = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/systemtest/scheduler/start", {
        method: "POST"
      });
      const data = await response.json();
      if (data.status === "success") {
        await loadSchedulerStatus();
      }
    } catch (error) {
      console.error("Scheduler starten fehlgeschlagen:", error);
    }
  };

  const stopScheduler = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/systemtest/scheduler/stop", {
        method: "POST"
      });
      const data = await response.json();
      if (data.status === "success") {
        await loadSchedulerStatus();
      }
    } catch (error) {
      console.error("Scheduler stoppen fehlgeschlagen:", error);
    }
  };

  const pauseScheduler = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/systemtest/scheduler/pause", {
        method: "POST"
      });
      const data = await response.json();
      if (data.status === "success") {
        await loadSchedulerStatus();
      }
    } catch (error) {
      console.error("Scheduler pausieren fehlgeschlagen:", error);
    }
  };

  useEffect(() => {
    if (activeTab === "flows") {
      loadFlows();
    }
    if (activeTab === "systemtest") {
      loadSchedulerStatus();
    }
  }, [activeTab]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "success":
        return "text-green-400 bg-green-400/10";
      case "error":
        return "text-red-400 bg-red-400/10";
      case "warning":
        return "text-yellow-400 bg-yellow-400/10";
      default:
        return "text-gray-400 bg-gray-400/10";
    }
  };

  const getOverallStatusColor = (status: string) => {
    switch (status) {
      case "success":
        return "bg-green-500";
      case "warning":
        return "bg-yellow-500";
      case "error":
        return "bg-red-500";
      default:
        return "bg-gray-500";
    }
  };

  return (
    <div className="flex min-h-screen bg-[#0f0f1e]">
      <Sidebar />
      
      <main className="flex-1 ml-64 p-8">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-3xl font-bold text-white mb-2">Einstellungen</h1>
          <p className="text-gray-400 mb-8">Systemkonfiguration und Überwachung</p>

          {/* Tabs */}
          <div className="flex gap-4 mb-6">
            <button
              onClick={() => setActiveTab("systemtest")}
              className={`px-6 py-3 rounded-lg font-medium transition-all ${
                activeTab === "systemtest"
                  ? "bg-blue-600 text-white"
                  : "bg-[#1a1a2e] text-gray-400 hover:bg-[#2d2d44]"
              }`}
            >
              Systemtest
            </button>
            <button
              onClick={() => setActiveTab("flows")}
              className={`px-6 py-3 rounded-lg font-medium transition-all ${
                activeTab === "flows"
                  ? "bg-blue-600 text-white"
                  : "bg-[#1a1a2e] text-gray-400 hover:bg-[#2d2d44]"
              }`}
            >
              Flows
            </button>
          </div>

          {/* Systemtest Tab */}
          {activeTab === "systemtest" && (
            <div className="space-y-6">
              {/* Letzte Test-Zeit */}
              {testData && (
                <div className="bg-[#1a1a2e] rounded-xl p-4 border border-[#2d2d44]">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <span className="text-gray-400">Letzter Test:</span>
                      <span className="text-white font-medium">
                        {new Date(testData.timestamp).toLocaleString("de-DE", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit"
                        })}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400">Dauer:</span>
                      <span className="text-white font-medium">{testData.execution_time_ms.toFixed(0)}ms</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Test Start Button */}
              <div className="bg-[#1a1a2e] rounded-xl p-6 border border-[#2d2d44]">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-white mb-2">Systemtest</h2>
                    <p className="text-gray-400">
                      Testet alle APIs, Datenbanken und externen Services
                    </p>
                  </div>
                  <button
                    onClick={runSystemTest}
                    disabled={testLoading}
                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                  >
                    {testLoading ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Teste...
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Test starten
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => {
                      // Letzte Testergebnisse neu laden
                      fetch("http://localhost:8000/api/v1/systemtest/last")
                        .then(res => res.json())
                        .then(data => setTestData(data))
                        .catch(console.error);
                    }}
                    className="p-3 bg-[#2d2d44] hover:bg-[#3d3d54] text-white rounded-lg transition-colors"
                    title="Ergebnisse aktualisieren"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Test Results */}
              {testData && (
                <>
                  {/* Overall Status */}
                  <div className={`rounded-xl p-6 border ${getOverallStatusColor(testData.overall_status)} bg-opacity-10 border-opacity-30`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`w-16 h-16 rounded-full ${getOverallStatusColor(testData.overall_status)} flex items-center justify-center`}>
                          {testData.overall_status === "success" ? (
                            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          ) : testData.overall_status === "warning" ? (
                            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                          ) : (
                            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          )}
                        </div>
                        <div>
                          <h3 className="text-xl font-semibold text-white">
                            {testData.overall_status === "success" && "Alle Systeme funktionieren"}
                            {testData.overall_status === "warning" && "Systeme mit Warnungen"}
                            {testData.overall_status === "error" && "Systemfehler erkannt"}
                          </h3>
                          <p className="text-gray-400">
                            {testData.passed} von {testData.total_tests} Tests erfolgreich
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-400">Ausführungszeit</p>
                        <p className="text-lg font-semibold text-white">{testData.execution_time_ms.toFixed(0)}ms</p>
                      </div>
                    </div>
                  </div>

                  {/* Individual Tests */}
                  <div className="bg-[#1a1a2e] rounded-xl border border-[#2d2d44] overflow-hidden">
                    <div className="p-6 border-b border-[#2d2d44]">
                      <h3 className="text-lg font-semibold text-white">Testergebnisse</h3>
                    </div>
                    <div className="divide-y divide-[#2d2d44]">
                      {testData.tests.map((test, index) => (
                        <div key={index} className="p-6 hover:bg-[#252538] transition-colors">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-3 mb-2">
                                <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(test.status)}`}>
                                  {test.status.toUpperCase()}
                                </span>
                                <h4 className="font-medium text-white">{test.name}</h4>
                                <span className="text-sm text-gray-500">{test.category}</span>
                              </div>
                              <p className="text-gray-400 mb-2">{test.message}</p>
                              {test.details && Object.keys(test.details).length > 0 && (
                                <div className="text-sm text-gray-500 bg-[#0f0f1e] rounded p-2 mt-2">
                                  <pre className="whitespace-pre-wrap">
                                    {JSON.stringify(test.details, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                            <div className="text-right ml-4">
                              <p className="text-sm text-gray-500">{test.response_time_ms.toFixed(0)}ms</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Flows Tab */}
          {activeTab === "flows" && (
            <div className="space-y-6">
              {/* Flow Stats */}
              {flowStats && (
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-[#1a1a2e] rounded-xl p-6 border border-[#2d2d44]">
                    <p className="text-gray-400 text-sm mb-1">Gesamt</p>
                    <p className="text-3xl font-bold text-white">{flowStats.total}</p>
                  </div>
                  <div className="bg-[#1a1a2e] rounded-xl p-6 border border-[#2d2d44]">
                    <p className="text-gray-400 text-sm mb-1">Erfolgreich</p>
                    <p className="text-3xl font-bold text-green-400">{flowStats.success}</p>
                  </div>
                  <div className="bg-[#1a1a2e] rounded-xl p-6 border border-[#2d2d44]">
                    <p className="text-gray-400 text-sm mb-1">Fehler</p>
                    <p className="text-3xl font-bold text-red-400">{flowStats.error}</p>
                  </div>
                  <div className="bg-[#1a1a2e] rounded-xl p-6 border border-[#2d2d44]">
                    <p className="text-gray-400 text-sm mb-1">Erfolgsrate</p>
                    <p className="text-3xl font-bold text-blue-400">{flowStats.success_rate.toFixed(1)}%</p>
                  </div>
                </div>
              )}

              {/* Flow List */}
              <div className="bg-[#1a1a2e] rounded-xl border border-[#2d2d44] overflow-hidden">
                <div className="p-6 border-b border-[#2d2d44] flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-white">Flow-Runs</h3>
                  <button
                    onClick={loadFlows}
                    disabled={flowsLoading}
                    className="px-4 py-2 bg-[#2d2d44] hover:bg-[#3d3d54] disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
                  >
                    {flowsLoading ? "Lädt..." : "Aktualisieren"}
                  </button>
                </div>
                <div className="divide-y divide-[#2d2d44]">
                  {flows.length === 0 ? (
                    <div className="p-8 text-center text-gray-400">
                      <svg className="w-12 h-12 mx-auto mb-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                      <p>Noch keine Flows ausgeführt</p>
                      <p className="text-sm mt-2">n8n Flows werden hier angezeigt, sobald sie laufen</p>
                    </div>
                  ) : (
                    flows.map((flow, index) => (
                      <div key={index} className="p-6 hover:bg-[#252538] transition-colors">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(flow.status)}`}>
                              {flow.status.toUpperCase()}
                            </span>
                            <div>
                              <h4 className="font-medium text-white">{flow.name}</h4>
                              <p className="text-sm text-gray-500">ID: {flow.id}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-sm text-gray-400">
                              {new Date(flow.start_time).toLocaleString("de-DE")}
                            </p>
                            {flow.duration_ms && (
                              <p className="text-sm text-gray-500">{flow.duration_ms.toFixed(0)}ms</p>
                            )}
                          </div>
                        </div>
                        {flow.details && Object.keys(flow.details).length > 0 && (
                          <div className="mt-3 text-sm text-gray-500 bg-[#0f0f1e] rounded p-2">
                            <pre className="whitespace-pre-wrap">
                              {JSON.stringify(flow.details, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
