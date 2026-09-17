"""
Subscriptions router — plans, org lifecycle, billing history, webhooks.

The webhook is the only unauthenticated endpoint here and the only path that
can move a subscription into `active`; it takes the raw body so the provider
signature is verified against exactly the bytes that arrived. Everything else
is scoped to the caller's organization through their membership, with the
super-admin console living under /admin/*.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from dependencies import (
    CurrentUser,
    DbSession,
    SuperAdmin,
    require_permission,
)
from models.subscription import BillingCycle
from models.user import User, UserRole
from repositories.organization import MembershipRepository
from schemas.subscription import (
    AddonOut,
    AddonPurchaseRequest,
    AdminSubscriptionRow,
    ChangePlanRequest,
    CheckoutResponse,
    CurrentSubscriptionResponse,
    InvoiceOut,
    PlanCreate,
    PlanOut,
    PlanUpdate,
    ReactivateRequest,
    SimulatePaymentRequest,
    SubscribeRequest,
    SubscriptionOut,
    TrialStartRequest,
)
from services.entitlement_service import EntitlementService
from services.subscription_service import SubscriptionService
from services.integrations.payment_service import stub_enabled

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

SubscriptionManager = Depends(require_permission("subscription.manage"))


def _checkout_payload(session) -> dict:
    return {
        "provider": session.provider,
        "provider_ref": session.provider_ref,
        "redirect_url": session.redirect_url,
        "sandbox": session.simulate_available,
    }


async def _require_org_id(current_user: User, db) -> uuid.UUID:
    if current_user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="الاشتراكات تدار من حساب المنشأة",
        )
    org_id = await MembershipRepository(db).get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا توجد منشأة مرتبطة بالحساب",
        )
    return org_id


def _checkout_response(subscription_id, invoice, session) -> CheckoutResponse:
    return CheckoutResponse(
        subscription_id=subscription_id,
        invoice_id=invoice.id,
        provider=session.provider,
        provider_ref=session.provider_ref,
        redirect_url=session.redirect_url,
        amount=invoice.amount,
        vat=invoice.vat,
        total=invoice.total,
        currency=invoice.currency,
        sandbox=session.simulate_available,
    )


# ── Plans ─────────────────────────────────────────────────────────────────


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(db: DbSession, current_user: CurrentUser):
    plans = await SubscriptionService(db).list_public_plans()
    return [PlanOut.model_validate(p) for p in plans]


# ── Current state ─────────────────────────────────────────────────────────


@router.get("/current", response_model=CurrentSubscriptionResponse)
async def current_subscription(db: DbSession, current_user: CurrentUser):
    org_id = await _require_org_id(current_user, db)
    service = SubscriptionService(db)
    sub = await service.get_subscription(org_id)
    entitlements = await EntitlementService(db).get_entitlements(org_id)
    usage = await EntitlementService(db).usage_summary(org_id)
    return CurrentSubscriptionResponse(
        subscription=SubscriptionOut.model_validate(sub) if sub else None,
        plan=PlanOut.model_validate(sub.plan) if sub and sub.plan else None,
        entitlements={
            "features": entitlements.features,
            "limits": entitlements.limits,
            "status": entitlements.status,
            "plan_code": entitlements.plan_code,
            "entitled": entitlements.entitled,
        },
        usage=usage,
        sandbox=stub_enabled(),
    )


# ── Lifecycle ─────────────────────────────────────────────────────────────


@router.post("/trial", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def start_trial(
    data: TrialStartRequest,
    request: Request,
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    org_id = await _require_org_id(current_user, db)
    sub = await SubscriptionService(db).start_trial(
        org_id,
        data.plan_id,
        current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return SubscriptionOut.model_validate(sub)


@router.post("/subscribe", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(
    data: SubscribeRequest,
    request: Request,
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    org_id = await _require_org_id(current_user, db)
    sub, invoice, session = await SubscriptionService(db).subscribe(
        org_id,
        data.plan_id,
        BillingCycle(data.billing_cycle),
        current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return _checkout_response(sub.id, invoice, session)


@router.post("/change-plan")
async def change_plan(
    data: ChangePlanRequest,
    request: Request,
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    org_id = await _require_org_id(current_user, db)
    sub, session = await SubscriptionService(db).change_plan(
        org_id,
        data.plan_id,
        BillingCycle(data.billing_cycle) if data.billing_cycle else None,
        current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return {
        "subscription": SubscriptionOut.model_validate(sub).model_dump(mode="json"),
        "scheduled_downgrade": sub.pending_plan_id is not None,
        "checkout": None if session is None else _checkout_payload(session),
        "sandbox": stub_enabled(),
    }


@router.post("/cancel", response_model=SubscriptionOut)
async def cancel(
    request: Request,
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    org_id = await _require_org_id(current_user, db)
    sub = await SubscriptionService(db).cancel(
        org_id,
        current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return SubscriptionOut.model_validate(sub)


@router.post("/reactivate")
async def reactivate(
    data: ReactivateRequest,
    request: Request,
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    org_id = await _require_org_id(current_user, db)
    sub, session = await SubscriptionService(db).reactivate(
        org_id,
        data.plan_id,
        BillingCycle(data.billing_cycle) if data.billing_cycle else None,
        current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return {
        "subscription": SubscriptionOut.model_validate(sub).model_dump(mode="json"),
        "checkout": None if session is None else _checkout_payload(session),
        "sandbox": stub_enabled(),
    }


# ── Billing history ───────────────────────────────────────────────────────


@router.get("/invoices", response_model=list[InvoiceOut])
async def list_invoices(
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    org_id = await _require_org_id(current_user, db)
    invoices = await SubscriptionService(db).list_invoices(org_id)
    return [InvoiceOut.model_validate(i) for i in invoices]


@router.get("/addons", response_model=list[AddonOut])
async def list_addons(
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    org_id = await _require_org_id(current_user, db)
    addons = await SubscriptionService(db).list_addons(org_id)
    return [AddonOut.model_validate(a) for a in addons]


@router.post("/addons", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def purchase_addon(
    data: AddonPurchaseRequest,
    request: Request,
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    org_id = await _require_org_id(current_user, db)
    addon, invoice, session = await SubscriptionService(db).purchase_addon(
        org_id,
        data.code,
        data.quantity,
        current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return _checkout_response(addon.id, invoice, session)


# ── Payment webhook (unauthenticated by design) ──────────────────────────


@router.post("/webhook")
async def payment_webhook(request: Request, db: DbSession):
    body = await request.body()
    return await SubscriptionService(db).process_webhook(request.headers, body)


# ── Development settlement (stub provider only) ───────────────────────────


@router.post("/dev/simulate-payment")
async def simulate_payment(
    data: SimulatePaymentRequest,
    db: DbSession,
    current_user: User = SubscriptionManager,
):
    if not stub_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="غير متاح خارج بيئة التطوير",
        )
    org_id = await _require_org_id(current_user, db)
    service = SubscriptionService(db)
    # A developer may only settle their own organization's checkouts.
    invoices = await service.list_invoices(org_id)
    if data.provider_ref not in {i.provider_ref for i in invoices}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="مرجع الدفع غير موجود",
        )
    return await service.simulate_payment(data.provider_ref, data.status)


# ── Admin console ─────────────────────────────────────────────────────────


@router.post("/admin/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def admin_create_plan(data: PlanCreate, db: DbSession, admin: SuperAdmin):
    plan = await SubscriptionService(db).create_plan(data, admin.id)
    return PlanOut.model_validate(plan)


@router.patch("/admin/plans/{plan_id}", response_model=PlanOut)
async def admin_update_plan(plan_id: uuid.UUID, data: PlanUpdate, db: DbSession, admin: SuperAdmin):
    plan = await SubscriptionService(db).update_plan(plan_id, data, admin.id)
    return PlanOut.model_validate(plan)


@router.post("/admin/plans/{plan_id}/deactivate", response_model=PlanOut)
async def admin_deactivate_plan(plan_id: uuid.UUID, db: DbSession, admin: SuperAdmin):
    plan = await SubscriptionService(db).deactivate_plan(plan_id, admin.id)
    return PlanOut.model_validate(plan)


@router.get("/admin/subscriptions", response_model=list[AdminSubscriptionRow])
async def admin_list_subscriptions(db: DbSession, admin: SuperAdmin):
    rows = await SubscriptionService(db).list_all_subscriptions()
    return [
        AdminSubscriptionRow(
            organization_id=org.id,
            organization_name=org.name_ar or org.name,
            organization_status=org.status,
            subscription=SubscriptionOut.model_validate(sub) if sub else None,
            plan=PlanOut.model_validate(sub.plan) if sub and sub.plan else None,
        )
        for org, sub in rows
    ]
