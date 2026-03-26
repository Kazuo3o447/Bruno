"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  DatabaseBackup,
  Download,
  Trash2,
  Loader2,
  CheckCircle,
  AlertCircle,
  Clock,
  HardDrive
} from "lucide-react";
import Sidebar from "@/components/Sidebar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Backup {
  filename: string;
  size_mb: number;
  created_at: string;
  created_formatted: string;
}

export default function BackupPage() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const fetchBackups = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/backups`);
      setBackups(response.data.backups);
    } catch (error) {
      setMessage({ type: "error", text: "Fehler beim Laden der Backups" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBackups();
    const interval = setInterval(fetchBackups, 30000); // Auto-refresh alle 30s
    return () => clearInterval(interval);
  }, []);

  const createBackup = async () => {
    setCreating(true);
    setMessage(null);
    try {
      const response = await axios.post(`${API_URL}/api/v1/backups/create`);
      setMessage({ type: "success", text: response.data.message });
      // Kurz warten, dann liste aktualisieren
      setTimeout(fetchBackups, 2000);
    } catch (error) {
      setMessage({ type: "error", text: "Fehler beim Starten des Backups" });
    } finally {
      setCreating(false);
    }
  };

  const deleteBackup = async (filename: string) => {
    try {
      await axios.delete(`${API_URL}/api/v1/backups/${filename}`);
      setMessage({ type: "success", text: `Backup ${filename} gelöscht` });
      setDeleteConfirm(null);
      fetchBackups();
    } catch (error) {
      setMessage({ type: "error", text: "Fehler beim Löschen" });
    }
  };

  const downloadBackup = (filename: string) => {
    window.open(`${API_URL}/api/v1/backups/download/${filename}`, "_blank");
  };

  const totalSize = backups.reduce((sum, b) => sum + b.size_mb, 0);

  return (
    <div className="flex min-h-screen bg-slate-950">
      <Sidebar />

      <main className="flex-1 p-8">
        <div className="max-w-6xl mx-auto">
          <header className="mb-8">
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <DatabaseBackup className="w-8 h-8 text-emerald-400" />
              Datensicherung / Backup
            </h1>
            <p className="text-slate-400 mt-2">
              Manuelle PostgreSQL-Backups mit maximaler Kompression (-Z 9)
            </p>
          </header>

          {/* Status Message */}
          {message && (
            <div
              className={`mb-6 p-4 rounded-lg flex items-center gap-3 ${
                message.type === "success"
                  ? "bg-emerald-900/30 border border-emerald-700 text-emerald-400"
                  : "bg-red-900/30 border border-red-700 text-red-400"
              }`}
            >
              {message.type === "success" ? (
                <CheckCircle className="w-5 h-5" />
              ) : (
                <AlertCircle className="w-5 h-5" />
              )}
              {message.text}
            </div>
          )}

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-slate-900 rounded-lg p-6 border border-slate-700">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-400 text-sm">Gesamt-Backups</p>
                  <p className="text-2xl font-bold text-white">{backups.length}</p>
                </div>
                <HardDrive className="w-8 h-8 text-blue-400" />
              </div>
            </div>
            <div className="bg-slate-900 rounded-lg p-6 border border-slate-700">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-400 text-sm">Speicherplatz</p>
                  <p className="text-2xl font-bold text-white">{totalSize.toFixed(2)} MB</p>
                </div>
                <DatabaseBackup className="w-8 h-8 text-purple-400" />
              </div>
            </div>
            <div className="bg-slate-900 rounded-lg p-6 border border-slate-700">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-400 text-sm">Letztes Backup</p>
                  <p className="text-lg font-bold text-white">
                    {backups.length > 0 ? backups[0].created_formatted.split(" ")[0] : "-"}
                  </p>
                </div>
                <Clock className="w-8 h-8 text-yellow-400" />
              </div>
            </div>
          </div>

          {/* Create Backup Button */}
          <div className="mb-8">
            <button
              onClick={createBackup}
              disabled={creating}
              className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-600 text-white font-semibold py-4 px-8 rounded-lg flex items-center gap-3 transition-colors"
            >
              {creating ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Backup wird erstellt...
                </>
              ) : (
                <>
                  <DatabaseBackup className="w-5 h-5" />
                  Neues Backup erstellen
                </>
              )}
            </button>
            <p className="text-slate-500 text-sm mt-2">
              Backups laufen asynchron im Hintergrund (kein Timeout). Format: pg_dump -Fc -Z 9
            </p>
          </div>

          {/* Backups Table */}
          <div className="bg-slate-900 rounded-lg border border-slate-700 overflow-hidden">
            <div className="p-6 border-b border-slate-700">
              <h2 className="text-xl font-semibold text-white">Verfügbare Backups</h2>
            </div>

            {loading ? (
              <div className="p-8 text-center text-slate-400">
                <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4" />
                Lade Backups...
              </div>
            ) : backups.length === 0 ? (
              <div className="p-8 text-center text-slate-400">
                <DatabaseBackup className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Noch keine Backups vorhanden</p>
                <p className="text-sm mt-2">Erstelle dein erstes Backup oben</p>
              </div>
            ) : (
              <table className="w-full">
                <thead className="bg-slate-800">
                  <tr>
                    <th className="text-left p-4 text-slate-300 font-medium">Dateiname</th>
                    <th className="text-left p-4 text-slate-300 font-medium">Größe</th>
                    <th className="text-left p-4 text-slate-300 font-medium">Erstellt</th>
                    <th className="text-right p-4 text-slate-300 font-medium">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {backups.map((backup) => (
                    <tr key={backup.filename} className="border-t border-slate-800 hover:bg-slate-800/50">
                      <td className="p-4 text-white font-mono text-sm">{backup.filename}</td>
                      <td className="p-4 text-slate-300">{backup.size_mb.toFixed(2)} MB</td>
                      <td className="p-4 text-slate-300">{backup.created_formatted}</td>
                      <td className="p-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => downloadBackup(backup.filename)}
                            className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                            title="Download"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(backup.filename)}
                            className="p-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                            title="Löschen"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Delete Confirmation Modal */}
          {deleteConfirm && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
              <div className="bg-slate-900 rounded-lg p-6 max-w-md w-full mx-4 border border-slate-700">
                <h3 className="text-xl font-bold text-white mb-4">Backup löschen?</h3>
                <p className="text-slate-400 mb-6">
                  Bist du sicher, dass du <strong className="text-white">{deleteConfirm}</strong> löschen möchtest?
                  Diese Aktion kann nicht rückgängig gemacht werden.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setDeleteConfirm(null)}
                    className="flex-1 py-2 px-4 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                  >
                    Abbrechen
                  </button>
                  <button
                    onClick={() => deleteBackup(deleteConfirm)}
                    className="flex-1 py-2 px-4 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                  >
                    Löschen
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
