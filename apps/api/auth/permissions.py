"""
The permission catalogue.

A permission is a short key a role either carries or does not. The screens are
grouped by the page they sit on so an administrator building a role sees the
platform the way their staff do — "المخزون", "السوق", "المحفظة" — rather than a
flat list of verbs. The four historic membership roles map onto fixed sets here
so nobody loses access on the day this ships.
"""
from __future__ import annotations

from dataclasses import dataclass

from models.organization import MembershipRole


@dataclass(frozen=True)
class Permission:
    key: str
    label_ar: str
    label_en: str
    group_ar: str
    group_en: str


PERMISSIONS: tuple[Permission, ...] = (
    # Dashboard
    Permission("dashboard.view", "عرض لوحة العمليات", "View dashboard", "لوحة العمليات", "Dashboard"),
    # Inventory
    Permission("inventory.view", "عرض المخزون", "View inventory", "المخزون", "Inventory"),
    Permission("inventory.manage", "إدارة المخزون والدفعات", "Manage inventory", "المخزون", "Inventory"),
    Permission("inventory.import", "استيراد المخزون", "Import inventory", "المخزون", "Inventory"),
    Permission("products.manage", "إدارة كتالوج المنتجات", "Manage products", "المخزون", "Inventory"),
    Permission("restock.view", "عرض توصيات التوريد", "View restock advice", "المخزون", "Inventory"),
    # Marketplace
    Permission("marketplace.view", "تصفح سوق التبادل", "Browse marketplace", "سوق التبادل", "Marketplace"),
    Permission("marketplace.list", "نشر العروض وإلغاؤها", "Create and cancel listings", "سوق التبادل", "Marketplace"),
    Permission("marketplace.offer", "تقديم عروض شراء", "Submit offers", "سوق التبادل", "Marketplace"),
    Permission("marketplace.respond", "قبول ورفض عروض الشراء", "Accept and reject offers", "سوق التبادل", "Marketplace"),
    Permission("marketplace.reserve", "إدارة الحجوزات", "Manage reservations", "سوق التبادل", "Marketplace"),
    Permission("promotions.manage", "إدارة العروض الترويجية", "Manage promotions", "سوق التبادل", "Marketplace"),
    # Transactions
    Permission("transactions.view", "عرض الصفقات", "View transactions", "الصفقات", "Transactions"),
    Permission("transactions.dispatch", "شحن الصفقات", "Dispatch transactions", "الصفقات", "Transactions"),
    Permission("transactions.receive", "تأكيد الاستلام", "Confirm receipt", "الصفقات", "Transactions"),
    Permission("disputes.manage", "فتح النزاعات والرد عليها", "Manage disputes", "الصفقات", "Transactions"),
    Permission("insurance.manage", "التأمين على الشحنات", "Manage shipment insurance", "الصفقات", "Transactions"),
    # Money
    Permission("wallet.view", "عرض المحفظة", "View wallet", "المالية", "Finance"),
    Permission("wallet.topup", "شحن المحفظة", "Top up wallet", "المالية", "Finance"),
    Permission("wallet.withdraw", "طلب سحب الرصيد", "Request withdrawals", "المالية", "Finance"),
    Permission("loyalty.manage", "استبدال نقاط الولاء", "Redeem loyalty points", "المالية", "Finance"),
    Permission("subscription.manage", "إدارة الاشتراك", "Manage subscription", "المالية", "Finance"),
    # Point of sale
    Permission("pos.sell", "البيع من نقطة البيع", "Sell at POS", "نقطة البيع", "Point of sale"),
    Permission("pos.refund", "إرجاع مبيعات نقطة البيع", "Refund POS sales", "نقطة البيع", "Point of sale"),
    Permission("pos.shifts", "فتح الورديات وإغلاقها", "Open and close shifts", "نقطة البيع", "Point of sale"),
    Permission("pos.registers", "إدارة أجهزة نقطة البيع", "Manage registers", "نقطة البيع", "Point of sale"),
    # Reports
    Permission("reports.view", "عرض التقارير", "View reports", "التقارير", "Reports"),
    Permission("reports.export", "تصدير التقارير", "Export reports", "التقارير", "Reports"),
    # Organization
    Permission("org.view", "عرض ملف المنشأة", "View organization", "المنشأة", "Organization"),
    Permission("org.manage", "تعديل ملف المنشأة والفروع", "Manage organization and branches", "المنشأة", "Organization"),
    Permission("team.manage", "إدارة الفريق والأدوار", "Manage team and roles", "المنشأة", "Organization"),
    Permission("api_keys.manage", "إدارة مفاتيح الربط البرمجي", "Manage API keys", "المنشأة", "Organization"),
)

ALL_KEYS: frozenset[str] = frozenset(p.key for p in PERMISSIONS)

_VIEW_ONLY = frozenset(
    {
        "dashboard.view",
        "inventory.view",
        "restock.view",
        "marketplace.view",
        "transactions.view",
        "wallet.view",
        "reports.view",
        "org.view",
    }
)

_PHARMACIST = _VIEW_ONLY | frozenset(
    {
        "inventory.manage",
        "inventory.import",
        "marketplace.offer",
        "transactions.receive",
        "pos.sell",
        "pos.shifts",
    }
)

_ADMIN = ALL_KEYS - frozenset({"team.manage"})

# What each legacy membership role carries. Owners get everything; admins
# everything except hiring and firing; pharmacists the daily work; viewers a
# read-only window.
SYSTEM_ROLE_PERMISSIONS: dict[MembershipRole, frozenset[str]] = {
    MembershipRole.OWNER: ALL_KEYS,
    MembershipRole.ADMIN: _ADMIN,
    MembershipRole.PHARMACIST: _PHARMACIST,
    MembershipRole.VIEWER: _VIEW_ONLY,
}

SYSTEM_ROLE_NAMES: dict[MembershipRole, tuple[str, str]] = {
    MembershipRole.OWNER: ("المالك", "Owner"),
    MembershipRole.ADMIN: ("مدير المنشأة", "Administrator"),
    MembershipRole.PHARMACIST: ("صيدلي", "Pharmacist"),
    MembershipRole.VIEWER: ("مطلع", "Viewer"),
}


def is_known(key: str) -> bool:
    return key in ALL_KEYS
