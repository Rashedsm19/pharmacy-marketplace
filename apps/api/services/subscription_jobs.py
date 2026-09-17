"""
Subscription cycle job — one idempotent daily tick.

Every transition the calendar causes lives here: trials expiring and their
3-day reminder, cancellations taking effect at period end, scheduled
downgrades applying at the new period, renewal invoices and charges for due
subscriptions, and past-due subscriptions whose grace has lapsed. Each
organization is processed inside its own savepoint, so one bad row degrades
to a logged line rather than killing the tick for everyone.

`main.py` wires `process_subscription_cycle` into the scheduler; nothing here
runs on import.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from models.notification import NotificationType
from models.subscription import (
    OrganizationSubscription,
    SubscriptionEvent,
    SubscriptionStatus,
)
from services.subscription_service import TRIAL_REMINDER_DAYS, SubscriptionService

logger = logging.getLogger(__name__)


async def process_subscription_cycle() -> None:
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        subs = list(
            (
                await db.execute(
                    select(OrganizationSubscription).order_by(OrganizationSubscription.created_at)
                )
            )
            .scalars()
            .all()
        )
        outcomes: dict[str, int] = {}
        for sub in subs:
            try:
                async with db.begin_nested():
                    outcome = await _process_one(db, sub)
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                logger.error(
                    "Subscription cycle failed for org %s: %s",
                    sub.organization_id,
                    exc,
                    exc_info=True,
                )
                continue
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        logger.info(
            "Subscription cycle complete — %d subscription(s): %s",
            len(subs),
            outcomes or {"unchanged": 0},
        )


async def _process_one(db, sub: OrganizationSubscription) -> str:
    service = SubscriptionService(db)
    now = datetime.now(timezone.utc)

    # Locked for the whole decision so a webhook landing mid-tick cannot race it.
    sub = (
        await db.execute(
            select(OrganizationSubscription)
            .where(OrganizationSubscription.id == sub.id)
            .with_for_update()
        )
    ).scalar_one()
    status = SubscriptionStatus(sub.status)

    if status == SubscriptionStatus.TRIALING:
        if sub.trial_end is not None and sub.trial_end <= now:
            await service.expire_subscription(sub, reason="trial_ended")
            return "trial_expired"
        if (
            sub.trial_end is not None
            and sub.trial_end - now <= timedelta(days=TRIAL_REMINDER_DAYS)
            and not await _reminder_sent(db, sub)
        ):
            await service._record_event(sub.organization_id, sub.id, "trial_ending_reminder", None)
            await service._notify_org_admins(
                sub.organization_id,
                NotificationType.SUBSCRIPTION_TRIAL_ENDING,
                title="Trial ending soon",
                title_ar="الفترة التجريبية تقترب من نهايتها",
                body=f"Your trial ends on {sub.trial_end.date()}. Subscribe to keep your plan features.",
                body_ar=f"تنتهي فترتك التجريبية في {sub.trial_end.date()}. اشترك الآن للحفاظ على مزايا الباقة.",
                resource_id=sub.id,
            )
            return "trial_reminded"
        return "unchanged"

    if status == SubscriptionStatus.PAST_DUE:
        if sub.grace_until is not None and sub.grace_until <= now:
            await service.expire_subscription(sub, reason="grace_lapsed")
            return "grace_expired"
        return "unchanged"

    if status == SubscriptionStatus.ACTIVE:
        if sub.current_period_end is None:
            return "unchanged"  # complimentary — no period ever comes due
        if sub.current_period_end > now:
            return "unchanged"
        if sub.cancel_at_period_end:
            sub.status = SubscriptionStatus.CANCELLED
            sub.pending_plan_id = None
            await db.flush()
            await service._record_event(sub.organization_id, sub.id, "cancellation_effective", None)
            await service._notify_org_admins(
                sub.organization_id,
                NotificationType.SUBSCRIPTION_EXPIRED,
                title="Subscription ended",
                title_ar="انتهى الاشتراك",
                body="Your cancelled subscription reached its period end. Reactivate any time.",
                body_ar="بلغ اشتراكك الملغى نهاية الفترة. يمكنك إعادة التفعيل في أي وقت — بياناتك محفوظة.",
                resource_id=sub.id,
            )
            return "cancelled"
        if sub.pending_plan_id is not None:
            await _apply_pending_plan(db, service, sub)
        return await service.renew_due(sub)

    return "unchanged"


async def _reminder_sent(db, sub: OrganizationSubscription) -> bool:
    return (
        await db.execute(
            select(SubscriptionEvent.id).where(
                SubscriptionEvent.subscription_id == sub.id,
                SubscriptionEvent.event_type == "trial_ending_reminder",
            )
        )
    ).scalar_one_or_none() is not None


async def _apply_pending_plan(db, service: SubscriptionService, sub: OrganizationSubscription) -> None:
    from models.subscription import SubscriptionPlan
    from services.subscription_service import plan_snapshot

    plan = await db.get(SubscriptionPlan, sub.pending_plan_id)
    if plan is None:
        sub.pending_plan_id = None
        await db.flush()
        return
    before = str(sub.plan_id)
    sub.plan_id = plan.id
    sub.plan_snapshot = plan_snapshot(plan)
    sub.pending_plan_id = None
    await db.flush()
    await service._record_event(
        sub.organization_id,
        sub.id,
        "downgrade_applied",
        {"from_plan_id": before, "to_plan_code": plan.code},
    )
    await service._notify_org_admins(
        sub.organization_id,
        NotificationType.SYSTEM,
        title=f"Plan changed: {plan.name_en}",
        title_ar=f"تم تغيير الباقة: {plan.name_ar}",
        body=f"Your plan is now {plan.name_en}, as scheduled.",
        body_ar=f"أصبحت باقتك {plan.name_ar} كما كانت مجدولة.",
        resource_id=sub.id,
    )
