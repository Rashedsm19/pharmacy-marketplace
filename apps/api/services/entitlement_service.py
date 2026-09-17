"""
Entitlement enforcement boundary.

Every feature gate and usage limit in the platform goes through this service so
a subscription change takes effect everywhere at once. Nothing is cached: each
check reads the organization_subscriptions row fresh, so an upgrade, a failed
renewal or a lapsed grace period applies on the very next request.

Public API (consumed by other domains — do not change the signatures):

    svc = EntitlementService(db)
    ent = await svc.get_entitlements(org_id)
    await svc.require_feature(org_id, "restock_intelligence")
    await svc.check_resource_limit(org_id, "max_active_listings", current)
    await svc.record_usage(org_id, "listings_created", idempotency_key=...)
    summary = await svc.usage_summary(org_id)

Add-ons stack on top of plan limits. The mapping is deliberately small and
declared here so a new booster is one line, not a code path:

    extra_listings  → max_active_listings  +10 per unit
    extra_branch    → max_branches         +1  per unit
    extra_member    → max_team_members     +1  per unit

An organization with no subscription row at all predates the feature: it gets
the permissive legacy defaults (every feature open, no caps) so a pre-migration
environment keeps working. The data migration / seed gives every real org a
complimentary `legacy` subscription, after which plan limits apply.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.marketplace import ListingStatus, MarketplaceListing
from models.branch import PharmacyBranch
from models.notification import NotificationType
from models.organization import (
    MembershipRole,
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.subscription import (
    AddonStatus,
    OrganizationAddon,
    OrganizationSubscription,
    SubscriptionStatus,
    UsageCounter,
    UsageLedger,
)

FEATURE_KEYS = ("advanced_reports", "restock_intelligence", "api_access")
LIMIT_KEYS = (
    "max_active_listings",
    "max_branches",
    "max_team_members",
    "max_listings_per_period",
)

FEATURE_LABELS_AR = {
    "advanced_reports": "التقارير المتقدمة",
    "restock_intelligence": "ذكاء إعادة التوريد",
    "api_access": "الربط البرمجي (API)",
}

LIMIT_LABELS_AR = {
    "max_active_listings": "العروض النشطة",
    "max_branches": "الفروع",
    "max_team_members": "أعضاء الفريق",
    "max_listings_per_period": "العروض الجديدة في الفترة الحالية",
}

ADDON_LIMIT_EFFECTS: dict[str, tuple[str, int]] = {
    "extra_listings": ("max_active_listings", 10),
    "extra_branch": ("max_branches", 1),
    "extra_member": ("max_team_members", 1),
}

METRIC_LIMITS: dict[str, str] = {
    "listings_created": "max_listings_per_period",
}

WARNING_RATIO = 0.8


@dataclass(frozen=True)
class Entitlements:
    organization_id: uuid.UUID
    features: dict[str, bool] = field(default_factory=dict)
    limits: dict[str, int | None] = field(default_factory=dict)
    status: str = "complimentary"
    plan_code: str | None = None
    entitled: bool = True


def _period_start_for(sub: OrganizationSubscription | None) -> date:
    """The billing period a usage increment belongs to.

    Counters are keyed by period start, so a new period begins at zero by
    construction — nothing needs resetting. Without a live period (legacy orgs)
    usage still meters, against the calendar month.
    """
    if sub is not None and sub.current_period_start is not None:
        return sub.current_period_start.date()
    today = datetime.now(timezone.utc).date()
    return today.replace(day=1)


class EntitlementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Resolution ────────────────────────────────────────────────────────

    async def _load_subscription(self, org_id: uuid.UUID) -> OrganizationSubscription | None:
        return (
            await self.db.execute(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org_id
                )
            )
        ).scalar_one_or_none()

    async def lock_subscription(self, org_id: uuid.UUID) -> OrganizationSubscription | None:
        """Row-lock the org's subscription for a check-then-create sequence.

        Two concurrent listing creations must not both read "under the cap" and
        both pass; the lock serialises them. An org without a row locks its
        organization row instead, so the guard holds there too.
        """
        sub = (
            await self.db.execute(
                select(OrganizationSubscription)
                .where(OrganizationSubscription.organization_id == org_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if sub is None:
            await self.db.execute(
                select(PharmacyOrganization.id)
                .where(PharmacyOrganization.id == org_id)
                .with_for_update()
            )
        return sub

    @staticmethod
    def _is_entitled(sub: OrganizationSubscription) -> bool:
        now = datetime.now(timezone.utc)
        status = SubscriptionStatus(sub.status)
        if status in (SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE):
            return True
        if status == SubscriptionStatus.PAST_DUE:
            return sub.grace_until is not None and sub.grace_until > now
        if status == SubscriptionStatus.CANCELLED:
            return sub.current_period_end is not None and sub.current_period_end > now
        return False

    async def get_entitlements(self, org_id: uuid.UUID) -> Entitlements:
        sub = await self._load_subscription(org_id)
        if sub is None:
            return Entitlements(
                organization_id=org_id,
                features={key: True for key in FEATURE_KEYS},
                limits={key: None for key in LIMIT_KEYS},
                status="legacy",
            )

        plan_code = None
        raw_limits: dict = {}
        snapshot = sub.plan_snapshot or {}
        if snapshot:
            plan_code = snapshot.get("code")
            raw_limits = dict(snapshot.get("limits") or {})
        if not raw_limits and sub.plan is not None:
            plan_code = plan_code or sub.plan.code
            raw_limits = dict(sub.plan.limits or {})

        if not self._is_entitled(sub):
            return Entitlements(
                organization_id=org_id,
                features={key: False for key in FEATURE_KEYS},
                limits={key: 0 for key in LIMIT_KEYS},
                status=str(SubscriptionStatus(sub.status).value),
                plan_code=plan_code,
                entitled=False,
            )

        features = {key: bool(raw_limits.get(key, False)) for key in FEATURE_KEYS}
        limits: dict[str, int | None] = {}
        for key in LIMIT_KEYS:
            value = raw_limits.get(key)
            limits[key] = None if value is None else int(value)

        now = datetime.now(timezone.utc)
        addons = (
            (
                await self.db.execute(
                    select(OrganizationAddon).where(
                        OrganizationAddon.organization_id == org_id,
                        OrganizationAddon.status == AddonStatus.ACTIVE,
                        OrganizationAddon.valid_from.is_not(None),
                        OrganizationAddon.valid_from <= now,
                    )
                )
            )
            .scalars()
            .all()
        )
        for addon in addons:
            if addon.valid_until is not None and addon.valid_until <= now:
                continue
            effect = ADDON_LIMIT_EFFECTS.get(str(addon.code))
            if effect is None:
                continue
            key, per_unit = effect
            if limits.get(key) is not None:
                limits[key] = limits[key] + per_unit * int(addon.quantity)

        return Entitlements(
            organization_id=org_id,
            features=features,
            limits=limits,
            status=str(SubscriptionStatus(sub.status).value),
            plan_code=plan_code,
            entitled=True,
        )

    # ── Gates ─────────────────────────────────────────────────────────────

    async def require_feature(self, org_id: uuid.UUID, feature: str) -> None:
        ent = await self.get_entitlements(org_id)
        if ent.features.get(feature, False):
            return None
        label = FEATURE_LABELS_AR.get(feature, feature)
        if not ent.entitled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="انتهت صلاحية اشتراك منشأتك — جدد الاشتراك لاستعادة الميزات",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"ميزة «{label}» غير مشمولة في باقتك الحالية — رقِّ اشتراكك لتفعيلها",
        )

    async def check_resource_limit(
        self, org_id: uuid.UUID, limit_key: str, current_count: int
    ) -> None:
        ent = await self.get_entitlements(org_id)
        if not ent.entitled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="انتهت صلاحية اشتراك منشأتك — جدد الاشتراك للمتابعة",
            )
        limit = ent.limits.get(limit_key)
        if limit is None or current_count < limit:
            return None
        label = LIMIT_LABELS_AR.get(limit_key, limit_key)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"بلغت الحد الأقصى لـ{label} في باقتك ({limit}) — "
                "رقِّ اشتراكك أو أضف وحدات إضافية للمتابعة"
            ),
        )

    # ── Usage metering ────────────────────────────────────────────────────

    async def current_usage(
        self,
        org_id: uuid.UUID,
        metric: str,
        sub: OrganizationSubscription | None = None,
    ) -> int:
        if sub is None:
            sub = await self._load_subscription(org_id)
        counter = await self._get_counter(org_id, _period_start_for(sub), metric)
        return counter.count if counter is not None else 0

    async def _get_counter(
        self, org_id: uuid.UUID, period_start: date, metric: str
    ) -> UsageCounter | None:
        return (
            await self.db.execute(
                select(UsageCounter)
                .where(
                    UsageCounter.organization_id == org_id,
                    UsageCounter.period_start == period_start,
                    UsageCounter.metric == metric,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def record_usage(
        self,
        org_id: uuid.UUID,
        metric: str,
        amount: int = 1,
        idempotency_key: str | None = None,
    ) -> None:
        if idempotency_key is not None:
            existing = (
                await self.db.execute(
                    select(UsageLedger.id).where(
                        UsageLedger.idempotency_key == idempotency_key
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return None
            try:
                async with self.db.begin_nested():
                    self.db.add(
                        UsageLedger(
                            id=uuid.uuid4(),
                            organization_id=org_id,
                            metric=metric,
                            amount=amount,
                            idempotency_key=idempotency_key,
                        )
                    )
                    await self.db.flush()
            except IntegrityError:
                # Lost the race against a concurrent retry of the same call.
                return None
        else:
            self.db.add(
                UsageLedger(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    metric=metric,
                    amount=amount,
                    idempotency_key=f"auto:{uuid.uuid4().hex}",
                )
            )
            await self.db.flush()

        sub = await self._load_subscription(org_id)
        period_start = _period_start_for(sub)
        counter = await self._get_counter(org_id, period_start, metric)
        if counter is None:
            try:
                async with self.db.begin_nested():
                    counter = UsageCounter(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        period_start=period_start,
                        metric=metric,
                        count=0,
                        warned_80=False,
                    )
                    self.db.add(counter)
                    await self.db.flush()
            except IntegrityError:
                counter = await self._get_counter(org_id, period_start, metric)
        counter.count += amount
        await self.db.flush()

        limit_key = METRIC_LIMITS.get(metric)
        if limit_key is None:
            return None
        ent = await self.get_entitlements(org_id)
        limit = ent.limits.get(limit_key)
        if (
            limit
            and not counter.warned_80
            and counter.count / limit >= WARNING_RATIO
        ):
            # The flag flips in this transaction, so a pair of racing requests
            # warns once, not twice — the second sees warned_80 already set.
            counter.warned_80 = True
            await self.db.flush()
            await self._notify_limit_warning(org_id, metric, counter.count, limit)
        return None

    async def _notify_limit_warning(
        self, org_id: uuid.UUID, metric: str, count: int, limit: int
    ) -> None:
        from services.notification_service import NotificationService

        label = LIMIT_LABELS_AR.get(METRIC_LIMITS.get(metric, metric), metric)
        notifier = NotificationService(self.db)
        members = (
            (
                await self.db.execute(
                    select(UserOrganizationMembership).where(
                        UserOrganizationMembership.organization_id == org_id,
                        UserOrganizationMembership.is_active.is_(True),
                        UserOrganizationMembership.role.in_(
                            [MembershipRole.OWNER, MembershipRole.ADMIN]
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        for member in members:
            await notifier.create(
                user_id=member.user_id,
                notification_type=NotificationType.USAGE_LIMIT_WARNING,
                title=f"Approaching plan limit: {metric}",
                title_ar=f"اقتراب من حد الباقة: {label}",
                body=f"You have used {count} of {limit} for {metric} this period.",
                body_ar=(
                    f"استهلكت {count} من {limit} المتاحة لـ{label} في الفترة الحالية. "
                    "فكر في ترقية الباقة قبل بلوغ الحد."
                ),
                organization_id=org_id,
                resource_type="usage_counter",
                metadata={"metric": metric, "count": count, "limit": limit},
            )

    # ── Summary for meters ────────────────────────────────────────────────

    async def usage_summary(self, org_id: uuid.UUID) -> dict:
        ent = await self.get_entitlements(org_id)
        sub = await self._load_subscription(org_id)
        period_start = _period_start_for(sub)

        active_listings = int(
            await self.db.scalar(
                select(func.count(MarketplaceListing.id)).where(
                    MarketplaceListing.seller_organization_id == org_id,
                    MarketplaceListing.status.in_(
                        [ListingStatus.DRAFT, ListingStatus.ACTIVE, ListingStatus.RESERVED]
                    ),
                    MarketplaceListing.deleted_at.is_(None),
                )
            )
            or 0
        )
        branches = int(
            await self.db.scalar(
                select(func.count(PharmacyBranch.id)).where(
                    PharmacyBranch.organization_id == org_id,
                    PharmacyBranch.is_active.is_(True),
                    PharmacyBranch.deleted_at.is_(None),
                )
            )
            or 0
        )
        members = int(
            await self.db.scalar(
                select(func.count(UserOrganizationMembership.id)).where(
                    UserOrganizationMembership.organization_id == org_id,
                    UserOrganizationMembership.is_active.is_(True),
                )
            )
            or 0
        )

        counters = (
            (
                await self.db.execute(
                    select(UsageCounter).where(
                        UsageCounter.organization_id == org_id,
                        UsageCounter.period_start == period_start,
                    )
                )
            )
            .scalars()
            .all()
        )
        usage = {c.metric: c.count for c in counters}

        resources = {
            "active_listings": active_listings,
            "branches": branches,
            "team_members": members,
        }
        resource_limits = {
            "active_listings": ent.limits.get("max_active_listings"),
            "branches": ent.limits.get("max_branches"),
            "team_members": ent.limits.get("max_team_members"),
        }
        warnings: list[dict] = []
        for key, current in resources.items():
            limit = resource_limits[key]
            if limit:
                ratio = current / limit
                if ratio >= WARNING_RATIO:
                    warnings.append(
                        {"resource": key, "current": current, "limit": limit, "ratio": round(ratio, 3)}
                    )
        for metric, count in usage.items():
            limit = ent.limits.get(METRIC_LIMITS.get(metric, ""))
            if limit:
                ratio = count / limit
                if ratio >= WARNING_RATIO:
                    warnings.append(
                        {"metric": metric, "count": count, "limit": limit, "ratio": round(ratio, 3)}
                    )

        return {
            "resources": resources,
            "usage": usage,
            "limits": ent.limits,
            "features": ent.features,
            "warnings": warnings,
            "status": ent.status,
            "plan_code": ent.plan_code,
            "period_start": period_start.isoformat(),
        }
