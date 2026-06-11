"use client";

import { Bell, Menu, LogOut, User } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { notificationsApi } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";

interface NavbarProps {
  onMenuToggle: () => void;
}

function getInitials(name?: string) {
  if (!name) return "؟";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 1);
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export default function Navbar({ onMenuToggle }: NavbarProps) {
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations("nav");
  const { user, logout } = useAuthStore();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const { data: countData } = useQuery({
    queryKey: ["notifications-count"],
    queryFn: () => notificationsApi.unreadCount().then((r) => r.data),
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!userMenuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [userMenuOpen]);

  const handleLogout = () => {
    logout();
    router.push(`/${locale}/login`);
  };

  const initials = getInitials(user?.full_name);
  const unreadCount = countData?.count ?? 0;

  return (
    <header className="h-16 bg-[#fffdf9]/88 backdrop-blur supports-[backdrop-filter]:bg-[#fffdf9]/76 border-b border-[#e2d4bf] flex items-center justify-between px-3 sm:px-6 sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="p-2 rounded-full hover:bg-[#f4eadf] text-[#5f665f] md:hidden"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      <div className="flex items-center gap-1.5 sm:gap-2">
        {/* Language toggle */}
        <Link
          href={locale === "ar" ? "/en/dashboard" : "/ar/dashboard"}
          className="hidden sm:inline-flex h-9 items-center px-3 text-xs font-medium text-[#5f665f] hover:text-[#1f2a24] rounded-full hover:bg-[#f4eadf] transition-colors"
        >
          {locale === "ar" ? "EN" : "عربي"}
        </Link>

        {/* Notifications */}
        <Link
          href={`/${locale}/notifications`}
          className="relative h-9 w-9 inline-flex items-center justify-center rounded-full hover:bg-[#f4eadf] text-[#5f665f] transition-colors"
          aria-label="Notifications"
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-gold-500 text-[#1f2a24] text-[10px] font-semibold rounded-full flex items-center justify-center ring-2 ring-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Link>

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setUserMenuOpen((v) => !v)}
            className="flex items-center gap-2 h-9 px-1.5 sm:pl-3 rounded-full hover:bg-[#f4eadf] transition-colors"
            aria-haspopup="menu"
            aria-expanded={userMenuOpen}
          >
            <div className="h-7 w-7 bg-[#1f2a24] rounded-full flex items-center justify-center text-[#fbf7f0] text-xs font-semibold shadow-sm">
              {initials}
            </div>
            {user && (
              <span className="hidden sm:inline text-sm font-medium text-[#4d554e] max-w-[140px] truncate">
                {user.full_name}
              </span>
            )}
          </button>

          {userMenuOpen && (
            <div className="absolute left-0 mt-2 w-56 max-w-[calc(100vw-1rem)] bg-[#fffdf9] rounded-2xl shadow-lift ring-1 ring-[#e2d4bf] py-1.5 z-50 animate-fade-in">
              {user && (
                <div className="px-3 py-2 border-b border-[#eadfcc]">
                  <p className="text-sm font-medium text-[#1f2a24] truncate">
                    {user.full_name}
                  </p>
                  <p className="text-xs text-[#6d746d] truncate">{user.email}</p>
                  {user.role && (
                    <span className="inline-flex items-center gap-1 mt-1.5 px-2 py-0.5 rounded-full bg-[#f4eadf] text-[#1f2a24] ring-1 ring-inset ring-[#e2d4bf] text-[10px] font-semibold">
                      {user.role === "super_admin"
                        ? "مدير المنصة"
                        : user.role === "org_admin"
                        ? "مدير منظمة"
                        : user.role === "pharmacist"
                        ? "صيدلي"
                        : user.role}
                    </span>
                  )}
                </div>
              )}
              <Link
                href={`/${locale}/org/profile`}
                onClick={() => setUserMenuOpen(false)}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#4d554e] hover:bg-[#fbf7f0]"
              >
                <User className="h-4 w-4 text-[#9a8b77]" />
                <span>{t("profile") ?? "الملف الشخصي"}</span>
              </Link>
              <button
                onClick={handleLogout}
                className={cn(
                  "flex items-center gap-2 w-full px-3 py-2 text-sm text-rose-600 hover:bg-rose-50 transition-colors"
                )}
              >
                <LogOut className="h-4 w-4" />
                <span>{t("logout")}</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
