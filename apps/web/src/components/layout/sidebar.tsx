"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import BrandLogo from "@/components/ui/brand-logo";
import { useAuthStore } from "@/lib/auth";
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
  AlertTriangle,
  Upload,
  KeyRound,
  Boxes,
  Contact,
  UsersRound,
  Handshake,
  CalendarClock,
  Receipt,
  Boxes as BoxesIcon,
  Tags,
  Gavel as GavelIcon,
  FileStack,
  ClipboardList,
  BadgeCheck,
  Gavel,
  ScrollText,
  X,
  Wallet,
  CreditCard,
  Percent,
  Award,
  ShieldCheck,
  Lightbulb,
  Store,
  UserCog,
  Landmark,
  PiggyBank,
  Layers,
} from "lucide-react";
import { hasPermission } from "@/lib/permissions";

interface NavItem {
  href: string;
  icon: typeof LayoutDashboard;
  label: string;
  permission?: string;
}

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
}

export default function Sidebar({ open, onToggle, onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const locale = useLocale();
  const t = useTranslations("nav");
  const user = useAuthStore((state) => state.user);
  // Showing a pharmacy eight links that all return 403 is worse than hiding them.
  const isPlatformAdmin = user?.role === "super_admin";

  // Each link names the permission that opens its screen. A member whose role
  // lacks it does not see the link; the server refuses the request either way.
  const allNavItems: NavItem[] = [
    { href: `/${locale}/dashboard`, icon: LayoutDashboard, label: t("dashboard"), permission: "dashboard.view" },
    { href: `/${locale}/inventory/batches`, icon: Package, label: t("inventory"), permission: "inventory.view" },
    { href: `/${locale}/inventory/import`, icon: Upload, label: t("importInventory"), permission: "inventory.import" },
    { href: `/${locale}/inventory/restock`, icon: Lightbulb, label: t("restock"), permission: "restock.view" },
    { href: `/${locale}/pos`, icon: Store, label: t("pos"), permission: "pos.sell" },
    { href: `/${locale}/marketplace`, icon: ShoppingCart, label: t("marketplace"), permission: "marketplace.view" },
    { href: `/${locale}/my/listings`, icon: Pill, label: t("myListings"), permission: "marketplace.view" },
    { href: `/${locale}/my/promotions`, icon: Percent, label: t("promotions"), permission: "promotions.manage" },
    { href: `/${locale}/my/offers`, icon: Handshake, label: t("myOffers"), permission: "marketplace.view" },
    { href: `/${locale}/my/reservations`, icon: CalendarClock, label: t("myReservations"), permission: "marketplace.view" },
    { href: `/${locale}/my/transactions`, icon: Receipt, label: t("myTransactions"), permission: "transactions.view" },
    { href: `/${locale}/my/insurance`, icon: ShieldCheck, label: t("insurance"), permission: "insurance.manage" },
    { href: `/${locale}/inventory/products`, icon: BoxesIcon, label: t("products"), permission: "inventory.view" },
    { href: `/${locale}/my/disputes`, icon: AlertTriangle, label: t("disputes"), permission: "transactions.view" },
    { href: `/${locale}/wallet`, icon: Wallet, label: t("wallet"), permission: "wallet.view" },
    { href: `/${locale}/loyalty`, icon: Award, label: t("loyalty"), permission: "wallet.view" },
    { href: `/${locale}/reports`, icon: FileBarChart, label: t("reports"), permission: "reports.view" },
    { href: `/${locale}/org/profile`, icon: Building2, label: t("organization"), permission: "org.view" },
    { href: `/${locale}/org/team`, icon: UserCog, label: t("team"), permission: "team.manage" },
    { href: `/${locale}/org/subscription`, icon: CreditCard, label: t("subscription"), permission: "subscription.manage" },
    { href: `/${locale}/org/api-keys`, icon: KeyRound, label: t("apiKeys"), permission: "api_keys.manage" },
    { href: `/${locale}/notifications`, icon: Bell, label: t("notifications") },
  ];
  const navItems = allNavItems.filter(
    (item) => !item.permission || hasPermission(user, item.permission)
  );

  // Every admin destination, not just approvals: the other screens existed but
  // nothing linked to them, so they were reachable only by typing the URL.
  const adminItems = [
    { href: `/${locale}/admin/customers`, icon: Contact, label: t("adminCustomers") },
    { href: `/${locale}/admin/users`, icon: UsersRound, label: t("adminUsers") },
    { href: `/${locale}/admin/approvals`, icon: Shield, label: t("admin") },
    { href: `/${locale}/admin/compliance`, icon: BadgeCheck, label: t("adminCompliance") },
    { href: `/${locale}/admin/inventory`, icon: Boxes, label: t("adminInventory") },
    { href: `/${locale}/admin/drafts`, icon: FileStack, label: t("adminDrafts") },
    { href: `/${locale}/admin/imports`, icon: ClipboardList, label: t("adminImports") },
    { href: `/${locale}/admin/moderation`, icon: Gavel, label: t("adminModeration") },
    { href: `/${locale}/admin/audit-logs`, icon: ScrollText, label: t("adminAudit") },
    { href: `/${locale}/admin/categories`, icon: Tags, label: t("adminCategories") },
    { href: `/${locale}/admin/disputes`, icon: GavelIcon, label: t("adminDisputes") },
    { href: `/${locale}/admin/withdrawals`, icon: Landmark, label: t("adminWithdrawals") },
    { href: `/${locale}/admin/revenue`, icon: PiggyBank, label: t("adminRevenue") },
    { href: `/${locale}/admin/plans`, icon: Layers, label: t("adminPlans") },
    { href: `/${locale}/admin/insurance`, icon: ShieldCheck, label: t("adminInsurance") },
    { href: `/${locale}/admin/settings`, icon: Settings, label: t("adminSettings") },
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

        {isPlatformAdmin && (
          <div className="pt-3 mt-3 border-t border-[#eadfcc]">
            {open && (
              <p className="px-3 pb-2 text-[10px] uppercase tracking-normal font-semibold text-[#9a8b77]">
                لوحة الإدارة
              </p>
            )}
            {adminItems.map((item) => renderNavItem(item, "gold"))}
          </div>
        )}
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
