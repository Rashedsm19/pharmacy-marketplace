"use client";

import { useState, useEffect } from "react";
import Sidebar from "./sidebar";
import Navbar from "./navbar";

export default function Shell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
    <div className="flex h-screen overflow-hidden bg-app-shell" dir="rtl">
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-[#1f2a24]/32 backdrop-blur-sm z-30 md:hidden animate-fade-in"
          onClick={close}
          aria-hidden
        />
      )}
      <Sidebar open={sidebarOpen} onToggle={toggle} onNavigate={close} />
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <Navbar onMenuToggle={toggle} />
        <main className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 sm:py-7">
          <div className="mx-auto max-w-[1400px] w-full">{children}</div>
        </main>
      </div>
    </div>
  );
}
