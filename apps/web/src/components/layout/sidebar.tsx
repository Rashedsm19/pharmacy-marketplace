"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import BrandLogo from "@/components/brand-logo";
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
  X,
} from "lucide-react";

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
}

export default function Sidebar({ open, onToggle, onNavigate }: SidebarProps) {
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

  const handleNavClick = () => {
    if (typeof window !== "undefined" && window.innerWidth < 768) onNavigate?.();
  };

  const renderNavItem = (
    item: { href: string; icon: typeof LayoutDashboard; label: string },
    accent: "brand" | "gold"
  ) => {
    const active = pathname.startsWith(item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={handleNavClick}
        className={cn(
          "group relative flex items-center gap-3 px-3 py-2.5 rounded-full text-sm font-medium transition-all duration-150",
          active
            ? accent === "brand"
              ? "bg-[#f4eadf] text-[#1f2a24]"
              : "bg-[#f7efe3] text-[#7b5411]"
            : "text-[#5f665f] hover:bg-[#fbf7f0] hover:text-[#1f2a24]"
        )}
      >
        {active && (
          <span
            className={cn(
              "absolute inset-y-2 right-0 w-1 rounded-full",
              accent === "brand" ? "bg-brand-600" : "bg-gold-500"
            )}
            aria-hidden
          />
        )}
        <item.icon
          className={cn(
            "h-5 w-5 flex-shrink-0",
            active && (accent === "brand" ? "text-brand-700" : "text-gold-700")
          )}
        />
        {open && <span className="truncate">{item.label}</span>}
      </Link>
    );
  };

  return (
    <aside
      className={cn(
        "flex flex-col bg-[#fffdf9]/95 border-l border-[#e2d4bf] shadow-soft backdrop-blur",
        "fixed inset-y-0 right-0 z-40 transition-transform duration-300 md:static md:translate-x-0 md:transition-all",
        open ? "translate-x-0 w-72" : "translate-x-full md:translate-x-0",
        "md:w-64",
        !open && "md:w-[72px]"
      )}
    >
      {/* Logo */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-[#eadfcc]">
        {open && (
          <BrandLogo size="sm" />
        )}
        {!open && (
          <BrandLogo compact size="sm" className="hidden md:flex mx-auto" />
        )}
        <button
          onClick={onToggle}
          className="p-1.5 rounded-full hover:bg-[#f4eadf] text-[#6d746d] transition-colors"
          aria-label="Toggle sidebar"
        >
          <X className="h-4 w-4 md:hidden" />
          <span className="hidden md:inline">
            {open ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </span>
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-2.5">
        {navItems.map((item) => renderNavItem(item, "brand"))}

        <div className="pt-3 mt-3 border-t border-[#eadfcc]">
          {open && (
            <p className="px-3 pb-2 text-[10px] uppercase tracking-normal font-semibold text-[#9a8b77]">
              لوحة الإدارة
            </p>
          )}
          {adminItems.map((item) => renderNavItem(item, "gold"))}
        </div>
      </nav>

      {/* Settings at bottom */}
      <div className="border-t border-[#eadfcc] p-2.5">
        <Link
          href={`/${locale}/org/profile`}
          onClick={handleNavClick}
          className="flex items-center gap-3 px-3 py-2.5 rounded-full text-sm font-medium text-[#5f665f] hover:bg-[#fbf7f0] hover:text-[#1f2a24] transition-colors"
        >
          <Settings className="h-5 w-5 flex-shrink-0" />
          {open && <span>{t("settings")}</span>}
        </Link>
      </div>
    </aside>
  );
}
