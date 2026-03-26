"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import LogViewer from "./LogViewer";

interface SidebarItem {
  name: string;
  href: string;
  icon: string;
}

const sidebarItems: SidebarItem[] = [
  { name: "Dashboard", href: "/dashboard", icon: "" },
  { name: "Backup", href: "/backup", icon: "" },
  { name: "Agenten", href: "/agenten", icon: "" },
  { name: "Einstellungen", href: "/einstellungen", icon: "" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [isLogViewerOpen, setIsLogViewerOpen] = useState(false);

  return (
    <>
      <aside className="w-64 bg-[#1a1a2e] h-screen fixed left-0 top-0 border-r border-[#2d2d44]">
        <div className="p-4 border-b border-[#2d2d44]">
          <h1 className="text-xl font-bold text-white">Bruno</h1>
          <p className="text-xs text-gray-400">Trading Bot Dashboard</p>
        </div>

        <nav className="p-4 space-y-2">
          {sidebarItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:bg-[#2d2d44] hover:text-white"
                }`}
              >
                <span className="text-sm font-medium">{item.name}</span>
              </Link>
            );
          })}
          {/* Log Viewer Button */}
          <button
            onClick={() => setIsLogViewerOpen(true)}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-gray-400 hover:bg-[#2d2d44] hover:text-white"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-sm font-medium">Log</span>
          </button>
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-[#2d2d44]">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span>System Online</span>
          </div>
        </div>
      </aside>

      {/* Log Viewer Modal */}
      <LogViewer 
        isOpen={isLogViewerOpen} 
        onClose={() => setIsLogViewerOpen(false)} 
      />
    </>
  );
}
