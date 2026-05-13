"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Package,
  ShoppingCart,
  FileBarChart,
  Building2,
  Settings,
  Shield,
  Bell,
  ChevronLeft,
  ChevronRight,
  Pill,
} from "lucide-react";

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
}

export default function Sidebar({ open, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const locale = useLocale();
  const t = useTranslations("nav");

  const navItems = [
    { href: `/${locale}/dashboard`, icon: LayoutDashboard, label: t("dashboard") },
    { href: `/${locale}/inventory/batches`, icon: Package, label: t("inventory") },
    { href: `/${locale}/marketplace`, icon: ShoppingCart, label: t("marketplace") },
    { href: `/${locale}/my/listings`, icon: Pill, label: t("myListings") },
    { href: `/${locale}/reports/near-expiry`, icon: FileBarChart, label: t("reports") },
    { href: `/${locale}/org/profile`, icon: Building2, label: t("organization") },
    { href: `/${locale}/notifications`, icon: Bell, label: t("notifications") },
  ];

  const adminItems = [
    { href: `/${locale}/admin/approvals`, icon: Shield, label: t("admin") },
  ];

  return (
    <aside
      className={cn(
        "flex flex-col bg-white border-l border-gray-200 transition-all duration-300 shadow-sm",
        open ? "w-64" : "w-16"
      )}
    >
      {/* Logo */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
        {open && (
          <div className="flex items-center gap-2">
            <Pill className="h-7 w-7 text-blue-600" />
            <span className="font-bold text-gray-900 text-sm leading-tight">
              سوق الصيدليات
            </span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
        >
          {open ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-2">
        {navItems.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              )}
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              {open && <span>{item.label}</span>}
            </Link>
          );
        })}

        <div className="pt-4 mt-4 border-t border-gray-200">
          {adminItems.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  active
                    ? "bg-purple-50 text-purple-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" />
                {open && <span>{item.label}</span>}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Settings at bottom */}
      <div className="border-t border-gray-200 p-2">
        <Link
          href={`/${locale}/org/profile`}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100"
        >
          <Settings className="h-5 w-5 flex-shrink-0" />
          {open && <span>{t("settings")}</span>}
        </Link>
      </div>
    </aside>
  );
}
