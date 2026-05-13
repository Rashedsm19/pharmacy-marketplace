"use client";

import { Bell, Menu, LogOut, User } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { notificationsApi } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useState } from "react";
import Link from "next/link";

interface NavbarProps {
  onMenuToggle: () => void;
}

export default function Navbar({ onMenuToggle }: NavbarProps) {
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations("nav");
  const { user, logout } = useAuthStore();
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const { data: countData } = useQuery({
    queryKey: ["notifications-count"],
    queryFn: () => notificationsApi.unreadCount().then((r) => r.data),
    refetchInterval: 30000,
  });

  const handleLogout = () => {
    logout();
    router.push(`/${locale}/login`);
  };

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 sm:px-6 shadow-sm">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuToggle}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 md:hidden"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      <div className="flex items-center gap-3">
        {/* Language toggle */}
        <Link
          href={locale === "ar" ? "/en/dashboard" : "/ar/dashboard"}
          className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-100"
        >
          {locale === "ar" ? "EN" : "عربي"}
        </Link>

        {/* Notifications */}
        <Link
          href={`/${locale}/notifications`}
          className="relative p-2 rounded-lg hover:bg-gray-100 text-gray-500"
        >
          <Bell className="h-5 w-5" />
          {countData?.count > 0 && (
            <span className="absolute top-1 right-1 h-4 w-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
              {countData.count > 9 ? "9+" : countData.count}
            </span>
          )}
        </Link>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100"
          >
            <div className="h-8 w-8 bg-blue-600 rounded-full flex items-center justify-center">
              <User className="h-4 w-4 text-white" />
            </div>
            {user && (
              <span className="hidden sm:inline text-sm font-medium text-gray-700">{user.full_name}</span>
            )}
          </button>

          {userMenuOpen && (
            <div className="absolute left-0 mt-1 w-48 max-w-[calc(100vw-1rem)] bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50"
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
