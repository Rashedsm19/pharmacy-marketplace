"""
Subscription lifecycle service.

State moves in exactly three ways: an org admin asks for something (trial,
subscribe, change, cancel, reactivate — these only ever create a pending
invoice and a checkout), a verified payment webhook settles that invoice, or
the daily cycle job rolls periods forward. A browser redirect never activates
anything: the only path to `active` is a signature-verified webhook, and in
development the stub settles through that same webhook handler via the
clearly-labelled simulate endpoint.

Money is Decimal throughout (`services/money.py`); VAT follows the platform
`VAT_RATE_PCT`. Proration follows the `billing.proration_policy` setting —
`immediate_prorated` charges or credits the remaining fraction of the current
period on upgrade.
"""
from __future__ import annotations

import calendar
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.notification import NotificationType
from models.organization import (
    MembershipRole,
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.subscription import (
    AddonStatus,
    BillingCycle,
    OrganizationAddon,
    OrganizationSubscription,
    PaymentEvent,
    SubscriptionEvent,
    SubscriptionInvoice,
    SubscriptionInvoiceStatus,
    SubscriptionPlan,
    SubscriptionStatus,
)
from services.audit_service import AuditService
from services.money import pct_of, to_money
from services.notification_service import NotificationService
from services.settings_reader import get_int
from services.integrations.payment_service import (
    CheckoutSession,
    get_payment_provider,
    sign_payload,
    stub_enabled,
)

logger = logging.getLogger(__name__)

GRACE_PERIOD_KEY = "billing.grace_period_days"
GRACE_PERIOD_DEFAULT_DAYS = 3
PRORATION_POLICY_KEY = "billing.proration_policy"
PRORATION_POLICY_DEFAULT = "immediate_prorated"

TRIAL_REMINDER_DAYS = 3
ADDON_VALIDITY_DAYS = 30

# Paid limit boosters. Prices are development fixtures pending commercial
# approval, exactly like the seeded plans.
ADDON_CATALOG: dict[str, tuple[str, Decimal]] = {
    "extra_listings": ("عروض نشطة إضافية (+10)", Decimal("49.00")),
    "extra_branch": ("فرع إضافي", Decimal("99.00")),
    "extra_member": ("عضو فريق إضافي", Decimal("19.00")),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_cycle(start: datetime, cycle: BillingCycle) -> datetime:
    """One billing period after `start`, month-length aware (Jan 31 → Feb 28)."""
    months = 12 if BillingCycle(cycle) == BillingCycle.ANNUAL else 1
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def plan_price(plan: SubscriptionPlan | dict, cycle: BillingCycle) -> Decimal:
    if isinstance(plan, dict):
        raw = plan.get("annual_price" if BillingCycle(cycle) == BillingCycle.ANNUAL else "monthly_price")
    else:
        raw = plan.annual_price if BillingCycle(cycle) == BillingCycle.ANNUAL else plan.monthly_price
    return to_money(raw)


def plan_snapshot(plan: SubscriptionPlan) -> dict:
    return {
        "plan_id": str(plan.id),
        "code": plan.code,
        "version": plan.version,
        "name_ar": plan.name_ar,
        "name_en": plan.name_en,
        "monthly_price": str(to_money(plan.monthly_price)),
        "annual_price": str(to_money(plan.annual_price)),
        "currency": plan.currency,
        "trial_days": plan.trial_days,
        "limits": plan.limits or {},
    }


class SubscriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    # ── Lookups ───────────────────────────────────────────────────────────

    async def get_subscription(self, org_id: uuid.UUID) -> OrganizationSubscription | None:
        return (
            await self.db.execute(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org_id
                )
            )
        ).scalar_one_or_none()

    async def _locked_subscription(self, org_id: uuid.UUID) -> OrganizationSubscription | None:
        return (
            await self.db.execute(
                select(OrganizationSubscription)
                .where(OrganizationSubscription.organization_id == org_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def _plan_or_404(self, plan_id: uuid.UUID) -> SubscriptionPlan:
        plan = await self.db.get(SubscriptionPlan, plan_id)
        if plan is None or not plan.is_active or not plan.is_public:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="الباقة غير موجودة أو غير متاحة"
            )
        return plan

    async def list_public_plans(self) -> list[SubscriptionPlan]:
        return list(
            (
                await self.db.execute(
                    select(SubscriptionPlan)
                    .where(
                        SubscriptionPlan.is_active.is_(True),
                        SubscriptionPlan.is_public.is_(True),
                    )
                    .order_by(SubscriptionPlan.sort_order, SubscriptionPlan.code)
                )
            )
            .scalars()
            .all()
        )

    async def list_invoices(self, org_id: uuid.UUID) -> list[SubscriptionInvoice]:
        return list(
            (
                await self.db.execute(
                    select(SubscriptionInvoice)
                    .where(SubscriptionInvoice.organization_id == org_id)
                    .order_by(SubscriptionInvoice.created_at.desc())
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )

    async def list_addons(self, org_id: uuid.UUID) -> list[OrganizationAddon]:
        return list(
            (
                await self.db.execute(
                    select(OrganizationAddon)
                    .where(OrganizationAddon.organization_id == org_id)
                    .order_by(OrganizationAddon.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def _subscription_or_404(self, org_id: uuid.UUID) -> OrganizationSubscription:
        sub = await self._locked_subscription(org_id)
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="لا يوجد اشتراك لهذه المنشأة",
            )
        return sub

    # ── Shared plumbing ───────────────────────────────────────────────────

    async def _record_event(
        self,
        org_id: uuid.UUID,
        subscription_id: uuid.UUID | None,
        event_type: str,
        payload: dict | None = None,
    ) -> None:
        self.db.add(
            SubscriptionEvent(
                id=uuid.uuid4(),
                organization_id=org_id,
                subscription_id=subscription_id,
                event_type=event_type,
                payload=payload,
            )
        )
        await self.db.flush()

    async def _notify_org_admins(
        self,
        org_id: uuid.UUID,
        notification_type: NotificationType,
        title: str,
        title_ar: str,
        body: str,
        body_ar: str,
        resource_id: uuid.UUID | None = None,
    ) -> None:
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
            await self.notifications.create(
                user_id=member.user_id,
                notification_type=notification_type,
                title=title,
                title_ar=title_ar,
                body=body,
                body_ar=body_ar,
                organization_id=org_id,
                resource_type="organization_subscription",
                resource_id=resource_id,
            )

    def _new_invoice(
        self,
        sub: OrganizationSubscription,
        period_start: datetime,
        period_end: datetime,
        amount: Decimal,
        purpose_key: str,
        currency: str = "SAR",
    ) -> SubscriptionInvoice:
        amount = to_money(amount)
        vat = pct_of(amount, settings.VAT_RATE_PCT)
        invoice = SubscriptionInvoice(
            id=uuid.uuid4(),
            organization_id=sub.organization_id,
            subscription_id=sub.id,
            period_start=period_start,
            period_end=period_end,
            amount=amount,
            vat=vat,
            total=amount + vat,
            currency=currency,
            status=SubscriptionInvoiceStatus.PENDING,
            idempotency_key=purpose_key,
        )
        self.db.add(invoice)
        return invoice

    async def _void_pending_invoices(self, sub: OrganizationSubscription, prefixes: tuple[str, ...]) -> None:
        pending = (
            (
                await self.db.execute(
                    select(SubscriptionInvoice).where(
                        SubscriptionInvoice.subscription_id == sub.id,
                        SubscriptionInvoice.status == SubscriptionInvoiceStatus.PENDING,
                    )
                )
            )
            .scalars()
            .all()
        )
        for invoice in pending:
            if invoice.idempotency_key.startswith(prefixes):
                invoice.status = SubscriptionInvoiceStatus.VOID
        await self.db.flush()

    async def _checkout(self, invoice: SubscriptionInvoice, org_id: uuid.UUID) -> CheckoutSession:
        provider = get_payment_provider()
        session = await provider.create_checkout(invoice.total, org_id, invoice.id)
        invoice.provider = provider.name
        invoice.provider_ref = session.provider_ref
        await self.db.flush()
        return session

    # ── Trial ─────────────────────────────────────────────────────────────

    async def start_trial(
        self,
        org_id: uuid.UUID,
        plan_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> OrganizationSubscription:
        org = await self.db.get(PharmacyOrganization, org_id)
        if org is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المنشأة غير موجودة")

        sub = await self._locked_subscription(org_id)
        if sub is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="لدى المنشأة اشتراك مسجل بالفعل",
            )
        # A trial is once per organization, ever — checked both on the org row
        # and on the event history, so a deleted or rebuilt row cannot reset it.
        trialled = org.trial_used_at is not None or (
            await self.db.execute(
                select(func.count(SubscriptionEvent.id)).where(
                    SubscriptionEvent.organization_id == org_id,
                    SubscriptionEvent.event_type == "trial_started",
                )
            )
        ).scalar_one() > 0
        if trialled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="استُخدمت الفترة التجريبية لهذه المنشأة من قبل",
            )

        plan = await self._plan_or_404(plan_id)
        if plan.trial_days <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="هذه الباقة لا تتضمن فترة تجريبية",
            )

        now = utcnow()
        trial_end = now + timedelta(days=plan.trial_days)
        sub = OrganizationSubscription(
            id=uuid.uuid4(),
            organization_id=org_id,
            plan_id=plan.id,
            plan_snapshot=plan_snapshot(plan),
            status=SubscriptionStatus.TRIALING,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=trial_end,
            trial_start=now,
            trial_end=trial_end,
        )
        self.db.add(sub)
        org.trial_used_at = now
        await self.db.flush()

        await self._record_event(
            org_id,
            sub.id,
            "trial_started",
            {"plan_code": plan.code, "trial_end": trial_end.isoformat()},
        )
        await self.audit.log(
            action="subscription.trial_start",
            resource_type="organization_subscription",
            resource_id=sub.id,
            actor_id=actor_id,
            organization_id=org_id,
            after_state={"plan_code": plan.code, "trial_end": trial_end},
            ip_address=ip_address,
        )
        await self._notify_org_admins(
            org_id,
            NotificationType.SYSTEM,
            title=f"Trial started: {plan.name_en}",
            title_ar=f"بدأت الفترة التجريبية: {plan.name_ar}",
            body=f"Your trial of {plan.name_en} runs until {trial_end.date()}.",
            body_ar=f"تجربتك لباقة {plan.name_ar} مستمرة حتى {trial_end.date()}. بعدها يلزم اشتراك مدفوع للمتابعة.",
            resource_id=sub.id,
        )
        return sub

    # ── Subscribe / checkout ──────────────────────────────────────────────

    async def subscribe(
        self,
        org_id: uuid.UUID,
        plan_id: uuid.UUID,
        billing_cycle: BillingCycle,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> tuple[OrganizationSubscription, SubscriptionInvoice, CheckoutSession]:
        plan = await self._plan_or_404(plan_id)
        sub = await self._locked_subscription(org_id)
        now = utcnow()

        if sub is not None:
            current = SubscriptionStatus(sub.status)
            live = current in (
                SubscriptionStatus.TRIALING,
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.PAST_DUE,
            ) or (
                current == SubscriptionStatus.CANCELLED
                and sub.current_period_end is not None
                and sub.current_period_end > now
            )
            if current == SubscriptionStatus.ACTIVE or current == SubscriptionStatus.PAST_DUE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="لديك اشتراك فعّال — استخدم تغيير الباقة بدلا من اشتراك جديد",
                )
            if current == SubscriptionStatus.CANCELLED and live:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="اشتراكك ما زال ساريا حتى نهاية الفترة — استخدم إعادة التفعيل",
                )

        if sub is None:
            sub = OrganizationSubscription(
                id=uuid.uuid4(),
                organization_id=org_id,
                plan_id=plan.id,
                plan_snapshot=plan_snapshot(plan),
                # Nothing is entitled until the webhook settles the invoice.
                status=SubscriptionStatus.EXPIRED,
                billing_cycle=billing_cycle,
            )
            self.db.add(sub)
            await self.db.flush()

        sub.plan_id = plan.id
        sub.plan_snapshot = plan_snapshot(plan)
        sub.billing_cycle = billing_cycle
        sub.pending_plan_id = None
        sub.cancel_at_period_end = False
        sub.grace_until = None
        await self._void_pending_invoices(sub, ("sub:", "upg:"))

        period_end = add_cycle(now, billing_cycle)
        invoice = self._new_invoice(
            sub,
            now,
            period_end,
            plan_price(plan, billing_cycle),
            purpose_key=f"sub:{sub.id}:{now.isoformat()}",
            currency=plan.currency,
        )
        await self.db.flush()
        session = await self._checkout(invoice, org_id)

        await self._record_event(
            org_id,
            sub.id,
            "checkout_created",
            {
                "plan_code": plan.code,
                "billing_cycle": str(BillingCycle(billing_cycle).value),
                "invoice_id": str(invoice.id),
                "total": str(invoice.total),
            },
        )
        await self.audit.log(
            action="subscription.checkout",
            resource_type="organization_subscription",
            resource_id=sub.id,
            actor_id=actor_id,
            organization_id=org_id,
            after_state={"plan_code": plan.code, "invoice_id": invoice.id, "total": invoice.total},
            ip_address=ip_address,
        )
        return sub, invoice, session

    # ── Plan changes ──────────────────────────────────────────────────────

    async def change_plan(
        self,
        org_id: uuid.UUID,
        plan_id: uuid.UUID,
        billing_cycle: BillingCycle | None,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> tuple[OrganizationSubscription, CheckoutSession | None]:
        sub = await self._subscription_or_404(org_id)
        current = SubscriptionStatus(sub.status)
        if current not in (SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="تغيير الباقة متاح فقط لاشتراك فعّال أو تجريبي",
            )

        plan = await self._plan_or_404(plan_id)
        new_cycle = billing_cycle or BillingCycle(sub.billing_cycle)
        if plan.id == sub.plan_id and new_cycle == BillingCycle(sub.billing_cycle):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="أنت مشترك في هذه الباقة بهذه الدورة بالفعل",
            )

        old_price = plan_price(sub.plan_snapshot or {}, BillingCycle(sub.billing_cycle))
        new_price = plan_price(plan, new_cycle)
        is_upgrade = new_price > old_price
        now = utcnow()

        if not is_upgrade:
            # Downgrades take effect at the next period start; the current
            # period was already paid for at the current level.
            sub.pending_plan_id = plan.id
            sub.billing_cycle = new_cycle
            await self.db.flush()
            await self._record_event(
                org_id,
                sub.id,
                "downgrade_scheduled",
                {"pending_plan_code": plan.code, "effective_at": (sub.current_period_end or now).isoformat()},
            )
            await self.audit.log(
                action="subscription.plan_change",
                resource_type="organization_subscription",
                resource_id=sub.id,
                actor_id=actor_id,
                organization_id=org_id,
                after_state={"direction": "downgrade", "pending_plan_code": plan.code},
                ip_address=ip_address,
            )
            await self._notify_org_admins(
                org_id,
                NotificationType.SYSTEM,
                title=f"Plan change scheduled: {plan.name_en}",
                title_ar=f"تمت جدولة تغيير الباقة: {plan.name_ar}",
                body=f"Your plan changes to {plan.name_en} at the end of the current period.",
                body_ar=f"ستنتقل منشأتك إلى باقة {plan.name_ar} عند نهاية الفترة الحالية.",
                resource_id=sub.id,
            )
            return sub, None

        checkout: CheckoutSession | None = None
        before = {"plan_id": str(sub.plan_id), "billing_cycle": str(BillingCycle(sub.billing_cycle).value)}

        if sub.current_period_end is None or sub.current_period_end <= now:
            # Complimentary (legacy) or lapsed subscription: there is no paid
            # period to prorate against, so the upgrade is a full purchase —
            # the plan only switches when the invoice is settled (webhook).
            await self._void_pending_invoices(sub, ("sub:", "upg:"))
            period_end = add_cycle(now, new_cycle)
            invoice = self._new_invoice(
                sub,
                now,
                period_end,
                new_price,
                purpose_key=f"upg:{sub.id}:{now.isoformat()}",
                currency=plan.currency,
            )
            await self.db.flush()
            checkout = await self._checkout(invoice, org_id)
            sub.pending_plan_id = plan.id
            sub.billing_cycle = new_cycle
            await self.db.flush()
            await self._record_event(
                org_id,
                sub.id,
                "upgrade_pending_payment",
                {"plan_code": plan.code, "invoice_id": str(invoice.id), "total": str(invoice.total)},
            )
            await self.audit.log(
                action="subscription.plan_change",
                resource_type="organization_subscription",
                resource_id=sub.id,
                actor_id=actor_id,
                organization_id=org_id,
                before_state=before,
                after_state={"direction": "upgrade_pending_payment", "plan_code": plan.code},
                ip_address=ip_address,
            )
            return sub, checkout

        policy = str(await _get_proration_policy(self.db))
        if (
            policy == PRORATION_POLICY_DEFAULT
            and current == SubscriptionStatus.ACTIVE
            and sub.current_period_start is not None
            and sub.current_period_end is not None
            and sub.current_period_end > now
        ):
            total_seconds = (sub.current_period_end - sub.current_period_start).total_seconds()
            remaining_seconds = (sub.current_period_end - now).total_seconds()
            fraction = Decimal(str(max(remaining_seconds, 0) / total_seconds)) if total_seconds > 0 else Decimal("0")
            difference = to_money((new_price - old_price) * fraction)
            if difference > 0:
                await self._void_pending_invoices(sub, ("sub:", "upg:"))
                invoice = self._new_invoice(
                    sub,
                    now,
                    sub.current_period_end,
                    difference,
                    purpose_key=f"upg:{sub.id}:{now.isoformat()}",
                    currency=plan.currency,
                )
                await self.db.flush()
                checkout = await self._checkout(invoice, org_id)
            elif difference < 0:
                sub.proration_credit = to_money(sub.proration_credit) + (-difference)

        sub.plan_id = plan.id
        sub.plan_snapshot = plan_snapshot(plan)
        sub.billing_cycle = new_cycle
        sub.pending_plan_id = None
        await self.db.flush()

        await self._record_event(
            org_id,
            sub.id,
            "plan_upgraded",
            {
                "from": before,
                "to": {"plan_code": plan.code, "billing_cycle": str(new_cycle.value)},
                "proration_invoice": checkout.provider_ref if checkout else None,
            },
        )
        await self.audit.log(
            action="subscription.plan_change",
            resource_type="organization_subscription",
            resource_id=sub.id,
            actor_id=actor_id,
            organization_id=org_id,
            before_state=before,
            after_state={"direction": "upgrade", "plan_code": plan.code, "billing_cycle": str(new_cycle.value)},
            ip_address=ip_address,
        )
        await self._notify_org_admins(
            org_id,
            NotificationType.SYSTEM,
            title=f"Plan upgraded: {plan.name_en}",
            title_ar=f"تمت ترقية الباقة: {plan.name_ar}",
            body=f"Your plan is now {plan.name_en}, effective immediately.",
            body_ar=f"أصبحت باقتك {plan.name_ar} سارية فورا.",
            resource_id=sub.id,
        )
        return sub, checkout

    # ── Cancel / reactivate ───────────────────────────────────────────────

    async def cancel(
        self,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> OrganizationSubscription:
        sub = await self._subscription_or_404(org_id)
        current = SubscriptionStatus(sub.status)
        if current not in (
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="لا يمكن إلغاء اشتراك بهذه الحالة",
            )
        if sub.cancel_at_period_end:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="الاشتراك مجدول للإلغاء بالفعل",
            )

        now = utcnow()
        sub.cancel_at_period_end = True
        sub.cancelled_at = now
        complimentary = sub.current_period_end is None
        if complimentary:
            sub.status = SubscriptionStatus.CANCELLED
        await self.db.flush()

        await self._record_event(
            org_id,
            sub.id,
            "cancelled",
            {"effective_at": (sub.current_period_end or now).isoformat(), "immediate": complimentary},
        )
        await self.audit.log(
            action="subscription.cancel",
            resource_type="organization_subscription",
            resource_id=sub.id,
            actor_id=actor_id,
            organization_id=org_id,
            after_state={"cancel_at_period_end": True, "current_period_end": sub.current_period_end},
            ip_address=ip_address,
        )
        if complimentary:
            body_ar = "تم إلغاء الاشتراك المجاني فورا."
            body = "The complimentary subscription was cancelled immediately."
        else:
            body_ar = f"سيبقى اشتراكك فعالا حتى {sub.current_period_end.date()} ثم يتوقف التجديد."
            body = f"Your subscription stays active until {sub.current_period_end.date()} and will not renew."
        await self._notify_org_admins(
            org_id,
            NotificationType.SYSTEM,
            title="Subscription cancelled",
            title_ar="تم إلغاء الاشتراك",
            body=body,
            body_ar=body_ar,
            resource_id=sub.id,
        )
        return sub

    async def reactivate(
        self,
        org_id: uuid.UUID,
        plan_id: uuid.UUID | None,
        billing_cycle: BillingCycle | None,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> tuple[OrganizationSubscription, CheckoutSession | None]:
        sub = await self._subscription_or_404(org_id)
        current = SubscriptionStatus(sub.status)
        now = utcnow()

        if current in (SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE) and not sub.cancel_at_period_end:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="الاشتراك فعّال بالفعل",
            )

        if current == SubscriptionStatus.CANCELLED and (
            sub.current_period_end is None or sub.current_period_end <= now
        ):
            current = SubscriptionStatus.EXPIRED

        if current == SubscriptionStatus.EXPIRED:
            chosen_plan = await self._plan_or_404(plan_id) if plan_id else None
            if chosen_plan is None:
                plan = await self.db.get(SubscriptionPlan, sub.plan_id)
                if plan is None or not plan.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="الباقة السابقة لم تعد متاحة — اختر باقة جديدة",
                    )
                chosen_plan = plan
            cycle = billing_cycle or BillingCycle(sub.billing_cycle)
            _sub, invoice, session = await self.subscribe(
                org_id, chosen_plan.id, cycle, actor_id, ip_address
            )
            return _sub, session

        # Still inside a paid (or trial) period with a pending cancellation:
        # undo the cancellation, and optionally switch plan immediately.
        sub.cancel_at_period_end = False
        sub.cancelled_at = None
        if current == SubscriptionStatus.CANCELLED:
            still_trialing = (
                sub.trial_end is not None
                and sub.trial_end > now
                and sub.last_payment_at is None
            )
            sub.status = (
                SubscriptionStatus.TRIALING if still_trialing else SubscriptionStatus.ACTIVE
            )
        if plan_id is not None and plan_id != sub.plan_id:
            plan = await self._plan_or_404(plan_id)
            sub.plan_id = plan.id
            sub.plan_snapshot = plan_snapshot(plan)
            sub.pending_plan_id = None
        if billing_cycle is not None:
            sub.billing_cycle = billing_cycle
        await self.db.flush()

        await self._record_event(org_id, sub.id, "reactivated", None)
        await self.audit.log(
            action="subscription.reactivate",
            resource_type="organization_subscription",
            resource_id=sub.id,
            actor_id=actor_id,
            organization_id=org_id,
            after_state={"status": str(SubscriptionStatus(sub.status).value)},
            ip_address=ip_address,
        )
        await self._notify_org_admins(
            org_id,
            NotificationType.SUBSCRIPTION_RENEWED,
            title="Subscription reactivated",
            title_ar="تمت إعادة تفعيل الاشتراك",
            body="Your subscription is active again and will renew normally.",
            body_ar="اشتراكك فعّال من جديد وسيتجدد بشكل طبيعي.",
            resource_id=sub.id,
        )
        return sub, None

    # ── Past due / expiry ─────────────────────────────────────────────────

    async def mark_past_due(
        self, sub: OrganizationSubscription, invoice: SubscriptionInvoice | None = None
    ) -> None:
        grace_days = await get_int(self.db, GRACE_PERIOD_KEY, GRACE_PERIOD_DEFAULT_DAYS)
        now = utcnow()
        sub.status = SubscriptionStatus.PAST_DUE
        sub.grace_until = now + timedelta(days=max(grace_days, 0))
        await self.db.flush()
        await self._record_event(
            sub.organization_id,
            sub.id,
            "payment_failed",
            {"invoice_id": str(invoice.id) if invoice else None, "grace_until": sub.grace_until.isoformat()},
        )
        await self.audit.log(
            action="subscription.past_due",
            resource_type="organization_subscription",
            resource_id=sub.id,
            organization_id=sub.organization_id,
            after_state={"grace_until": sub.grace_until},
        )
        await self._notify_org_admins(
            sub.organization_id,
            NotificationType.SUBSCRIPTION_PAYMENT_FAILED,
            title="Subscription payment failed",
            title_ar="فشل دفع الاشتراك",
            body=(
                f"We could not collect your subscription payment. Your access continues "
                f"until {sub.grace_until.date()} while we retry."
            ),
            body_ar=(
                f"تعذر تحصيل دفعة اشتراكك. سيستمر وصولك حتى {sub.grace_until.date()} "
                "بانتظار سداد الدفعة."
            ),
            resource_id=sub.id,
        )

    async def expire_subscription(self, sub: OrganizationSubscription, reason: str) -> None:
        sub.status = SubscriptionStatus.EXPIRED
        sub.grace_until = None
        await self.db.flush()
        await self._record_event(sub.organization_id, sub.id, "subscription_expired", {"reason": reason})
        await self.audit.log(
            action="subscription.expired",
            resource_type="organization_subscription",
            resource_id=sub.id,
            organization_id=sub.organization_id,
            after_state={"reason": reason},
        )
        await self._notify_org_admins(
            sub.organization_id,
            NotificationType.SUBSCRIPTION_EXPIRED,
            title="Subscription expired",
            title_ar="انتهى الاشتراك",
            body="Your subscription has expired. Reactivate it to regain plan features.",
            body_ar="انتهت صلاحية اشتراك منشأتك. أعد التفعيل لاستعادة مزايا الباقة — بياناتك محفوظة كما هي.",
            resource_id=sub.id,
        )

    # ── Webhook processing ────────────────────────────────────────────────

    async def process_webhook(self, headers, body: bytes) -> dict:
        """Verify, store, then apply — in that order, every time.

        Storage comes first so a duplicate delivery is answered from the inbox
        rather than re-applied, and an event that does not match current state
        is kept with a note instead of being dropped or corrupting anything.
        """
        provider = get_payment_provider()
        event = provider.verify_webhook(headers, body)
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            payload = {}
        event_id = str(payload.get("event_id") or f"{event.provider_ref}:{event.status}")

        stored = PaymentEvent(
            id=uuid.uuid4(),
            provider=provider.name,
            event_id=event_id,
            event_type=f"payment.{event.status}",
            payload=payload,
        )
        try:
            async with self.db.begin_nested():
                self.db.add(stored)
                await self.db.flush()
        except IntegrityError:
            return {"received": True, "duplicate": True}

        result = await self._apply_webhook(provider.name, event, payload)
        stored.processed_at = utcnow()
        stored.result = result
        await self.db.flush()
        return {"received": True, "duplicate": False, "result": result}

    async def _apply_webhook(self, provider_name: str, event, payload: dict) -> str:
        invoice = (
            await self.db.execute(
                select(SubscriptionInvoice).where(
                    SubscriptionInvoice.provider_ref == event.provider_ref
                )
            )
        ).scalar_one_or_none()
        if invoice is None:
            return "no_matching_invoice"
        if invoice.status == SubscriptionInvoiceStatus.PAID:
            return "invoice_already_paid"
        if invoice.status == SubscriptionInvoiceStatus.VOID:
            return "invoice_void"

        sub = (
            await self.db.execute(
                select(OrganizationSubscription)
                .where(OrganizationSubscription.id == invoice.subscription_id)
                .with_for_update()
            )
        ).scalar_one()

        if event.status != "paid":
            invoice.status = SubscriptionInvoiceStatus.FAILED
            await self.db.flush()
            is_upgrade_invoice = invoice.idempotency_key.startswith("upg:")
            if is_upgrade_invoice and sub.pending_plan_id is not None:
                # A pending upgrade whose payment failed leaves the organization
                # exactly where it was — no plan switch, no entitlement change.
                sub.pending_plan_id = None
                await self.db.flush()
            if SubscriptionStatus(sub.status) == SubscriptionStatus.ACTIVE and not is_upgrade_invoice:
                await self.mark_past_due(sub, invoice)
                return "past_due"
            await self._record_event(
                sub.organization_id, sub.id, "payment_failed", {"invoice_id": str(invoice.id)}
            )
            await self._notify_org_admins(
                sub.organization_id,
                NotificationType.SUBSCRIPTION_PAYMENT_FAILED,
                title="Subscription payment failed",
                title_ar="فشل دفع الاشتراك",
                body="A subscription payment was declined.",
                body_ar="تم رفض دفعة اشتراك. أكمل الدفع من صفحة الاشتراك لتفعيل باقتك.",
                resource_id=sub.id,
            )
            return "payment_failed"

        if event.amount is not None and to_money(event.amount) != to_money(invoice.total):
            return "amount_mismatch"

        now = utcnow()
        invoice.status = SubscriptionInvoiceStatus.PAID
        invoice.paid_at = now
        await self.db.flush()

        if invoice.idempotency_key.startswith("addon:"):
            return await self._settle_addon_invoice(invoice, sub)

        previous = SubscriptionStatus(sub.status)
        sub.status = SubscriptionStatus.ACTIVE
        sub.current_period_start = invoice.period_start
        sub.current_period_end = invoice.period_end
        sub.grace_until = None
        sub.last_payment_at = now
        sub.cancel_at_period_end = False
        sub.cancelled_at = None

        applied_pending_upgrade = False
        if invoice.idempotency_key.startswith("upg:") and sub.pending_plan_id is not None:
            # The upgrade was gated on this payment — switch the plan now.
            from models.subscription import SubscriptionPlan

            pending_plan = await self.db.get(SubscriptionPlan, sub.pending_plan_id)
            if pending_plan is not None:
                sub.plan_id = pending_plan.id
                sub.plan_snapshot = plan_snapshot(pending_plan)
                applied_pending_upgrade = True
            sub.pending_plan_id = None
        await self.db.flush()

        activated = previous in (
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.CANCELLED,
        )
        await self._record_event(
            sub.organization_id,
            sub.id,
            "subscription_activated" if activated else "subscription_renewed",
            {"invoice_id": str(invoice.id), "previous_status": str(previous.value)},
        )
        await self.audit.log(
            action="subscription.activated" if activated else "subscription.renewed",
            resource_type="organization_subscription",
            resource_id=sub.id,
            organization_id=sub.organization_id,
            after_state={
                "status": "active",
                "period_start": invoice.period_start,
                "period_end": invoice.period_end,
                "invoice_id": invoice.id,
            },
        )
        await self._notify_org_admins(
            sub.organization_id,
            NotificationType.SUBSCRIPTION_RENEWED,
            title="Subscription active" if activated else "Subscription renewed",
            title_ar="تم تفعيل اشتراكك" if activated else "تم تجديد اشتراكك",
            body=f"Paid {invoice.total} {invoice.currency}; period runs until {invoice.period_end.date()}.",
            body_ar=f"تم سداد {invoice.total} {invoice.currency}؛ تمتد الفترة حتى {invoice.period_end.date()}.",
            resource_id=sub.id,
        )
        return "activated" if activated else "renewed"

    async def _settle_addon_invoice(
        self, invoice: SubscriptionInvoice, sub: OrganizationSubscription
    ) -> str:
        addon_id = invoice.idempotency_key.split(":", 1)[1]
        addon = (
            await self.db.execute(
                select(OrganizationAddon).where(
                    OrganizationAddon.id == uuid.UUID(addon_id),
                    OrganizationAddon.organization_id == sub.organization_id,
                )
            )
        ).scalar_one_or_none()
        if addon is None:
            return "addon_missing"
        now = utcnow()
        addon.valid_from = now
        addon.valid_until = now + timedelta(days=ADDON_VALIDITY_DAYS)
        addon.status = AddonStatus.ACTIVE
        await self.db.flush()
        await self._record_event(
            sub.organization_id,
            sub.id,
            "addon_activated",
            {"addon_id": addon_id, "code": addon.code, "quantity": addon.quantity},
        )
        await self._notify_org_admins(
            sub.organization_id,
            NotificationType.SYSTEM,
            title=f"Add-on active: {addon.code}",
            title_ar=f"تم تفعيل الإضافة: {addon.code}",
            body=f"{addon.quantity} × {addon.code} is now part of your plan limits.",
            body_ar=f"أصبحت {addon.quantity} × {addon.code} ضمن حدود باقتك حتى {addon.valid_until.date()}.",
            resource_id=sub.id,
        )
        return "addon_activated"

    # ── Dev-only settlement ───────────────────────────────────────────────

    async def simulate_payment(self, provider_ref: str, outcome: str = "paid") -> dict:
        """Settle a checkout the way the stub gateway would: by delivering a
        properly signed webhook through the one and only webhook code path."""
        invoice = (
            await self.db.execute(
                select(SubscriptionInvoice).where(
                    SubscriptionInvoice.provider_ref == provider_ref
                )
            )
        ).scalar_one_or_none()
        payload = {
            "event_id": f"evt_{uuid.uuid4().hex}",
            "provider_ref": provider_ref,
            "status": outcome,
            "amount": str(invoice.total) if invoice is not None else None,
        }
        body = json.dumps(payload).encode()
        signature = sign_payload(body, settings.PAYMENT_WEBHOOK_SECRET)
        result = await self.process_webhook({"x-payment-signature": signature}, body)
        return {"sandbox": True, **result}

    # ── Renewals (driven by the daily cycle job) ──────────────────────────

    async def renew_due(self, sub: OrganizationSubscription) -> str:
        """Invoice and charge the next period of an active subscription.

        Idempotent per (subscription, period start): a tick that already ran
        finds the invoice and stops. The stub provider settles through the
        signed-webhook path; a real provider without off-session charging
        answers 501, which becomes past-due-with-grace rather than a crash.
        """
        period_start = sub.current_period_end
        if period_start is None:
            return "complimentary_skipped"
        period_end = add_cycle(period_start, BillingCycle(sub.billing_cycle))

        existing = (
            await self.db.execute(
                select(SubscriptionInvoice).where(
                    SubscriptionInvoice.subscription_id == sub.id,
                    SubscriptionInvoice.period_start == period_start,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return "invoice_exists"

        snapshot = sub.plan_snapshot or {}
        amount = plan_price(snapshot, BillingCycle(sub.billing_cycle))
        credit = to_money(sub.proration_credit)
        if credit > 0:
            consumed = min(credit, amount)
            amount = amount - consumed
            sub.proration_credit = credit - consumed
        currency = str(snapshot.get("currency") or "SAR")

        invoice = self._new_invoice(
            sub,
            period_start,
            period_end,
            amount,
            purpose_key=f"renew:{sub.id}:{period_start.isoformat()}",
            currency=currency,
        )
        try:
            await self.db.flush()
        except IntegrityError:
            # Lost a race against another tick for the same period.
            await self.db.rollback()
            return "invoice_exists"

        await self._record_event(
            sub.organization_id,
            sub.id,
            "renewal_invoice_created",
            {"invoice_id": str(invoice.id), "total": str(invoice.total)},
        )

        if stub_enabled():
            provider = get_payment_provider()
            session = await provider.create_checkout(invoice.total, sub.organization_id, invoice.id)
            invoice.provider = provider.name
            invoice.provider_ref = session.provider_ref
            await self.db.flush()
            result = await self.simulate_payment(session.provider_ref, "paid")
            return str(result.get("result", "settled"))

        try:
            await self._checkout(invoice, sub.organization_id)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_501_NOT_IMPLEMENTED:
                raise
            logger.warning(
                "Provider %s cannot charge off-session; marking %s past due",
                getattr(get_payment_provider(), "name", "?"),
                sub.organization_id,
            )
            await self.mark_past_due(sub, invoice)
            return "past_due_provider_unavailable"
        return "checkout_created"

    # ── Add-ons ───────────────────────────────────────────────────────────

    async def purchase_addon(
        self,
        org_id: uuid.UUID,
        code: str,
        quantity: int,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> tuple[OrganizationAddon, SubscriptionInvoice, CheckoutSession]:
        entry = ADDON_CATALOG.get(code)
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="الإضافة المطلوبة غير موجودة",
            )
        sub = await self._subscription_or_404(org_id)
        if SubscriptionStatus(sub.status) not in (
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.ACTIVE,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="الإضافات تتطلب اشتراكا فعالا",
            )

        label_ar, unit_price = entry
        # valid_from stays null until the webhook settles the invoice; the
        # entitlement resolver only counts addons inside their window.
        addon = OrganizationAddon(
            id=uuid.uuid4(),
            organization_id=org_id,
            code=code,
            quantity=quantity,
            price=to_money(unit_price * quantity),
            status=AddonStatus.ACTIVE,
        )
        self.db.add(addon)
        await self.db.flush()

        now = utcnow()
        invoice = self._new_invoice(
            sub,
            now,
            now + timedelta(days=ADDON_VALIDITY_DAYS),
            addon.price,
            purpose_key=f"addon:{addon.id}",
        )
        await self.db.flush()
        session = await self._checkout(invoice, org_id)

        await self._record_event(
            org_id,
            sub.id,
            "addon_purchased",
            {"addon_id": str(addon.id), "code": code, "quantity": quantity},
        )
        await self.audit.log(
            action="subscription_addon.purchase",
            resource_type="organization_addon",
            resource_id=addon.id,
            actor_id=actor_id,
            organization_id=org_id,
            after_state={"code": code, "quantity": quantity, "total": invoice.total},
            ip_address=ip_address,
        )
        return addon, invoice, session

    # ── Admin ─────────────────────────────────────────────────────────────

    async def create_plan(self, data, actor_id: uuid.UUID) -> SubscriptionPlan:
        existing_max = (
            await self.db.execute(
                select(func.max(SubscriptionPlan.version)).where(
                    SubscriptionPlan.code == data.code
                )
            )
        ).scalar_one()
        plan = SubscriptionPlan(
            id=uuid.uuid4(),
            code=data.code,
            version=(existing_max or 0) + 1,
            name_ar=data.name_ar,
            name_en=data.name_en,
            description_ar=data.description_ar,
            description_en=data.description_en,
            monthly_price=to_money(data.monthly_price),
            annual_price=to_money(data.annual_price),
            currency=data.currency,
            trial_days=data.trial_days,
            limits=data.limits or {},
            is_active=data.is_active,
            is_public=data.is_public,
            sort_order=data.sort_order,
        )
        self.db.add(plan)
        await self.db.flush()
        await self.audit.log(
            action="subscription_plan.create",
            resource_type="subscription_plan",
            resource_id=plan.id,
            actor_id=actor_id,
            after_state={"code": plan.code, "version": plan.version},
        )
        return plan

    async def _plan_is_referenced(self, plan: SubscriptionPlan) -> bool:
        referenced = (
            await self.db.execute(
                select(func.count(OrganizationSubscription.id)).where(
                    (OrganizationSubscription.plan_id == plan.id)
                    | (OrganizationSubscription.pending_plan_id == plan.id)
                )
            )
        ).scalar_one()
        return referenced > 0

    async def update_plan(self, plan_id: uuid.UUID, data, actor_id: uuid.UUID) -> SubscriptionPlan:
        plan = await self.db.get(SubscriptionPlan, plan_id)
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الباقة غير موجودة")
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return plan

        if await self._plan_is_referenced(plan):
            # Organizations bought this exact row; editing it would rewrite
            # their history. The edit becomes the next version instead.
            from schemas.subscription import PlanCreate

            merged = PlanCreate(
                code=plan.code,
                name_ar=plan.name_ar,
                name_en=plan.name_en,
                description_ar=plan.description_ar,
                description_en=plan.description_en,
                monthly_price=to_money(plan.monthly_price),
                annual_price=to_money(plan.annual_price),
                currency=plan.currency,
                trial_days=plan.trial_days,
                limits=plan.limits or {},
                is_active=plan.is_active,
                is_public=plan.is_public,
                sort_order=plan.sort_order,
            )
            for key, value in changes.items():
                setattr(merged, key, value)
            new_version = await self.create_plan(merged, actor_id)
            await self.audit.log(
                action="subscription_plan.update",
                resource_type="subscription_plan",
                resource_id=plan.id,
                actor_id=actor_id,
                after_state={"version_bumped_to": new_version.version, "changes": changes},
            )
            return new_version

        before = {key: getattr(plan, key) for key in changes}
        for key, value in changes.items():
            if key in ("monthly_price", "annual_price") and value is not None:
                value = to_money(value)
            setattr(plan, key, value)
        await self.db.flush()
        await self.audit.log(
            action="subscription_plan.update",
            resource_type="subscription_plan",
            resource_id=plan.id,
            actor_id=actor_id,
            before_state=before,
            after_state=changes,
        )
        return plan

    async def deactivate_plan(self, plan_id: uuid.UUID, actor_id: uuid.UUID) -> SubscriptionPlan:
        plan = await self.db.get(SubscriptionPlan, plan_id)
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الباقة غير موجودة")
        plan.is_active = False
        await self.db.flush()
        await self.audit.log(
            action="subscription_plan.deactivate",
            resource_type="subscription_plan",
            resource_id=plan.id,
            actor_id=actor_id,
            after_state={"code": plan.code, "version": plan.version},
        )
        return plan

    async def list_all_subscriptions(self) -> list[tuple[PharmacyOrganization, OrganizationSubscription | None]]:
        rows = (
            await self.db.execute(
                select(PharmacyOrganization, OrganizationSubscription)
                .outerjoin(
                    OrganizationSubscription,
                    OrganizationSubscription.organization_id == PharmacyOrganization.id,
                )
                .where(PharmacyOrganization.deleted_at.is_(None))
                .order_by(PharmacyOrganization.created_at)
            )
        ).all()
        return list(rows)


async def _get_proration_policy(db: AsyncSession) -> str:
    from services.settings_reader import get_setting

    raw = await get_setting(db, PRORATION_POLICY_KEY, PRORATION_POLICY_DEFAULT)
    return str(raw) if raw else PRORATION_POLICY_DEFAULT
