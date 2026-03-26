"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  DatabaseBackup,
  Activity,
  Settings,
  TrendingUp,
  BrainCircuit,
  Terminal
} from "lucide-react";

const menuItems = [
  { href: "/",            label: "Dashboard",     icon: LayoutDashboard, description: "Markt-Übersicht" },
  { href: "/dashboard",   label: "Trading",       icon: TrendingUp,      description: "Charts & Trades" },
  { href: "/agenten",     label: "Agenten",       icon: BrainCircuit,    description: "KI-Pipeline" },
  { href: "/logs",        label: "Logs",          icon: Terminal,        description: "System-Terminal" },
  { href: "/backup",      label: "Backups",       icon: DatabaseBackup,  description: "Datensicherung" },
  { href: "/einstellungen", label: "Settings",    icon: Settings,        description: "Konfiguration" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex md:fixed w-64 bg-[#08081a] border-r border-[#1a1a2e] min-h-screen flex-col z-50">
      {/* Logo */}
      <div className="px-6 py-7 border-b border-[#1a1a2e]">
        <h1 className="text-2xl font-extrabold tracking-tight">
          <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
            Bruno
          </span>
        </h1>
        <p className="text-[10px] text-slate-600 font-bold uppercase tracking-[0.2em] mt-0.5">
          Trading Intelligence
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4">
        <ul className="space-y-1">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group relative ${
                    isActive
                      ? "bg-indigo-500/10 text-white"
                      : "text-slate-500 hover:bg-white/[0.02] hover:text-slate-300"
                  }`}
                >
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 bg-indigo-500 rounded-r-full shadow-[0_0_12px_rgba(99,102,241,0.6)]" />
                  )}
                  <Icon className={`w-[18px] h-[18px] transition-all ${
                    isActive ? "text-indigo-400" : "text-slate-600 group-hover:text-slate-400"
                  }`} />
                  <div className="flex flex-col">
                    <span className={`text-[13px] font-semibold leading-tight ${isActive ? 'text-white' : ''}`}>
                      {item.label}
                    </span>
                    <span className="text-[10px] text-slate-600 leading-tight hidden group-hover:block">
                      {item.description}
                    </span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Engine Status Footer */}
      <div className="p-3 border-t border-[#1a1a2e]">
        <div className="bg-[#0c0c18] rounded-xl p-4 border border-[#1a1a2e]">
          <p className="text-[9px] text-slate-600 font-bold uppercase tracking-[0.15em] mb-2">
            Engine Status
          </p>
          <div className="flex items-center gap-2.5">
            <div className="relative flex items-center justify-center">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
              <span className="absolute flex h-2 w-2 animate-ping rounded-full bg-emerald-400 opacity-40" />
            </div>
            <span className="text-xs font-semibold text-emerald-400">System Online</span>
          </div>
          <div className="flex items-center gap-2.5 mt-1.5">
            <span className="flex h-2 w-2 rounded-full bg-indigo-500" />
            <span className="text-[10px] text-slate-500">Paper Trading Mode</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
