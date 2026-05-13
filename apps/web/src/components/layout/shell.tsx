"use client";

import { useState, useEffect } from "react";
import Sidebar from "./sidebar";
import Navbar from "./navbar";

export default function Shell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Open sidebar by default on desktop, closed on mobile
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(min-width: 768px)");
    const apply = () => setSidebarOpen(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  const toggle = () => setSidebarOpen((v) => !v);
  const close = () => setSidebarOpen(false);

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden" dir="rtl">
      {/* Backdrop on mobile when drawer is open */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-30 md:hidden"
          onClick={close}
          aria-hidden
        />
      )}
      <Sidebar open={sidebarOpen} onToggle={toggle} onNavigate={close} />
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <Navbar onMenuToggle={toggle} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
