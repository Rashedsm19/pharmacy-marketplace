"""Subscriptions: lifecycle, webhook billing, entitlements and enforcement.

Fixture organizations are built directly in the database (faster and more
precise than driving the registration flow); time travel is done by rewriting
rows, never by sleeping. Every webhook is exercised with the real HMAC check —
the secret is pinned on the settings object for the module.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from tests.conftest import auth, unique

WEBHOOK_SECRET = "test-webhook-secret"
FIXTURE_PASSWORD = "Fixture@12345"


@pytest.fixture(autouse=True)
def _webhook_secret():
    from config import settings

    previous = settings.PAYMENT_WEBHOOK_SECRET
    settings.PAYMENT_WEBHOOK_SECRET = WEBHOOK_SECRET
    yield
    settings.PAYMENT_WEBHOOK_SECRET = previous


# ── Fixture builders ────────────────────────────────────────────────────────


async def _make_org(client, *, org_status: str = "approved", licensed: bool = True):
    """An approved organization with one owner account; returns (org_id, token)."""
    from auth.password import hash_password
    from database import AsyncSessionLocal
    from models.organization import (
        MembershipRole,
        OrganizationStatus,
        PharmacyOrganization,
        UserOrganizationMembership,
    )
    from models.user import User, UserRole

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = f"{unique('owner-')}@fixture.sa"
    async with AsyncSessionLocal() as db:
        db.add(PharmacyOrganization(
            id=org_id,
            name=f"Fixture Org {unique()}",
            name_ar="منشأة اختبار",
            commercial_registration_number=f"CR-{uuid.uuid4().hex[:10]}",
            license_number=f"LIC-{uuid.uuid4().hex[:8]}",
            is_licensed=licensed,
            status=OrganizationStatus(org_status),
            email=email,
            phone="+966500000000",
        ))
        db.add(User(
            id=user_id,
            email=email,
            phone=None,
            full_name="Fixture Owner",
            hashed_password=hash_password(FIXTURE_PASSWORD),
            role=UserRole.ORG_ADMIN,
            is_active=True,
            is_email_verified=True,
            email_verified_at=datetime.now(timezone.utc),
        ))
        db.add(UserOrganizationMembership(
            id=uuid.uuid4(),
            user_id=user_id,
            organization_id=org_id,
            role=MembershipRole.OWNER,
            is_active=True,
            joined_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    response = await client.post(
        "/auth/login", json={"email": email, "password": FIXTURE_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return org_id, response.json()["access_token"]


async def _make_plan(limits: dict, *, monthly=100, annual=1000, trial_days=0, public=True):
    from database import AsyncSessionLocal
    from models.subscription import SubscriptionPlan

    plan_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(SubscriptionPlan(
            id=plan_id,
            code=unique("plan-"),
            version=1,
            name_ar="باقة اختبار",
            name_en="Test Plan",
            monthly_price=monthly,
            annual_price=annual,
            trial_days=trial_days,
            limits=limits,
            is_active=True,
            is_public=public,
        ))
        await db.commit()
    return plan_id


GENEROUS = {
    "max_active_listings": None,
    "max_branches": None,
    "max_team_members": None,
    "max_listings_per_period": None,
    "advanced_reports": True,
    "restock_intelligence": True,
    "api_access": True,
}


async def _set_subscription(
    org_id,
    plan_id,
    *,
    status="active",
    period_end=None,
    trial_end=None,
    grace=None,
    complimentary=False,
):
    from database import AsyncSessionLocal
    from models.subscription import (
        BillingCycle,
        OrganizationSubscription,
        SubscriptionPlan,
        SubscriptionStatus,
    )
    from services.subscription_service import plan_snapshot

    sub_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        plan = await db.get(SubscriptionPlan, plan_id)
        end = None if complimentary else (period_end or now + timedelta(days=30))
        db.add(OrganizationSubscription(
            id=sub_id,
            organization_id=org_id,
            plan_id=plan_id,
            plan_snapshot=plan_snapshot(plan),
            status=SubscriptionStatus(status),
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now - timedelta(days=1),
            current_period_end=end,
            trial_start=now - timedelta(days=1) if trial_end else None,
            trial_end=trial_end,
            grace_until=grace,
        ))
        await db.commit()
    return sub_id


async def _make_tradable(org_id, batches: int = 1):
    """A compliant branch, lenient expiry rule and N listable batches."""
    from database import AsyncSessionLocal
    from models.branch import PharmacyBranch, StorageConditionStatus
    from models.inventory import BatchStatus, InventoryBatch, NearExpiryRule
    from models.product import Product

    branch_id = uuid.uuid4()
    batch_ids: list[uuid.UUID] = []
    async with AsyncSessionLocal() as db:
        product = (
            await db.execute(
                select(Product)
                .where(
                    Product.is_active.is_(True),
                    Product.is_controlled.is_(False),
                    Product.is_restricted.is_(False),
                )
                .limit(1)
            )
        ).scalar_one()
        db.add(PharmacyBranch(
            id=branch_id,
            organization_id=org_id,
            name=f"Fixture Branch {unique()}",
            branch_code=unique("FB-"),
            is_active=True,
            storage_condition_status=StorageConditionStatus.COMPLIANT,
        ))
        db.add(NearExpiryRule(
            id=uuid.uuid4(), organization_id=org_id, min_days_for_listing=1
        ))
        for _ in range(batches):
            batch_id = uuid.uuid4()
            db.add(InventoryBatch(
                id=batch_id,
                organization_id=org_id,
                branch_id=branch_id,
                product_id=product.id,
                batch_number=unique("BTH-"),
                quantity=100,
                quantity_available=100,
                unit_cost=10,
                expiry_date=date.today() + timedelta(days=200),
                received_date=date.today(),
                status=BatchStatus.ACTIVE,
                storage_condition_status="compliant",
            ))
            batch_ids.append(batch_id)
        await db.commit()
    return branch_id, batch_ids


async def _create_listing(client, token, branch_id, batch_id):
    return await client.post(
        "/listings",
        headers=auth(token),
        json={
            "batch_id": str(batch_id),
            "seller_branch_id": str(branch_id),
            "title": "Subscription test lot",
            "title_ar": "دفعة اختبار اشتراك",
            "quantity_listed": 5,
            "asking_price": 40.0,
            "minimum_offer_price": 10.0,
            "allow_offers": True,
            "allow_partial_purchase": True,
            "min_purchase_quantity": 1,
        },
    )


def _signed_webhook(provider_ref: str, outcome: str = "paid", amount=None, event_id=None):
    from services.integrations.payment_service import sign_payload

    payload = {
        "event_id": event_id or f"evt_{uuid.uuid4().hex}",
        "provider_ref": provider_ref,
        "status": outcome,
        "amount": amount,
    }
    body = json.dumps(payload).encode()
    return body, {
        "x-payment-signature": sign_payload(body, WEBHOOK_SECRET),
        "content-type": "application/json",
    }


async def _plan_id_by_code(client, token, code: str) -> str:
    plans = (await client.get("/subscriptions/plans", headers=auth(token))).json()
    return next(p["id"] for p in plans if p["code"] == code)


async def _get_sub_row(org_id):
    from database import AsyncSessionLocal
    from models.subscription import OrganizationSubscription

    async with AsyncSessionLocal() as db:
        return (
            await db.execute(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org_id
                )
            )
        ).scalar_one()


# ── Plans ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plan_listing_is_public_and_ordered(client, seller_token):
    response = await client.get("/subscriptions/plans", headers=auth(seller_token))
    assert response.status_code == 200
    plans = response.json()
    codes = [p["code"] for p in plans]
    fixture_codes = [c for c in codes if c in ("starter", "growth", "scale")]
    assert fixture_codes == ["starter", "growth", "scale"]
    assert "legacy" not in codes, "the non-public migration plan must not be listed"
    starter = next(p for p in plans if p["code"] == "starter")
    assert starter["trial_days"] == 14
    assert "تجريبي" in starter["name_ar"], "dev fixtures stay clearly marked"


# ── Trial ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trial_start_and_once_per_org(client):
    org_id, token = await _make_org(client)
    starter = await _plan_id_by_code(client, token, "starter")

    created = await client.post(
        "/subscriptions/trial", headers=auth(token), json={"plan_id": starter}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "trialing"
    assert body["trial_end"] is not None

    again = await client.post(
        "/subscriptions/trial", headers=auth(token), json={"plan_id": starter}
    )
    assert again.status_code == 409

    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["entitlements"]["entitled"] is True
    assert current["entitlements"]["features"]["advanced_reports"] is False


@pytest.mark.asyncio
async def test_trial_cannot_be_reset_even_if_history_is_scrubbed(client):
    """The once-ever rule is anchored on the org row, not just the subscription."""
    org_id, token = await _make_org(client)
    starter = await _plan_id_by_code(client, token, "starter")
    await client.post("/subscriptions/trial", headers=auth(token), json={"plan_id": starter})

    from database import AsyncSessionLocal
    from models.subscription import OrganizationSubscription, SubscriptionEvent

    async with AsyncSessionLocal() as db:
        await db.execute(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == org_id
            )
        )
        # Wipe the event history and the subscription row itself, the way a
        # botched support cleanup would; the org row still says trial was used.
        await db.execute(
            SubscriptionEvent.__table__.delete().where(
                SubscriptionEvent.organization_id == org_id
            )
        )
        await db.execute(
            OrganizationSubscription.__table__.delete().where(
                OrganizationSubscription.organization_id == org_id
            )
        )
        await db.commit()

    retry = await client.post(
        "/subscriptions/trial", headers=auth(token), json={"plan_id": starter}
    )
    assert retry.status_code == 409


# ── Subscribe → checkout → webhook activation ───────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_activates_only_through_the_webhook(client):
    org_id, token = await _make_org(client)
    growth = await _plan_id_by_code(client, token, "growth")

    checkout = await client.post(
        "/subscriptions/subscribe",
        headers=auth(token),
        json={"plan_id": growth, "billing_cycle": "monthly"},
    )
    assert checkout.status_code == 201, checkout.text
    payload = checkout.json()
    assert payload["sandbox"] is True
    assert payload["redirect_url"]
    assert payload["total"] > payload["amount"], "VAT is added on top"

    # The redirect existing changes nothing by itself.
    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["subscription"]["status"] == "expired"
    assert current["entitlements"]["entitled"] is False

    settled = await client.post(
        "/subscriptions/dev/simulate-payment",
        headers=auth(token),
        json={"provider_ref": payload["provider_ref"], "status": "paid"},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["sandbox"] is True
    assert settled.json()["result"] == "activated"

    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["subscription"]["status"] == "active"
    assert current["entitlements"]["entitled"] is True


@pytest.mark.asyncio
async def test_webhook_rejects_a_bad_signature(client):
    body = json.dumps({"provider_ref": "stub_anything", "status": "paid"}).encode()
    response = await client.post(
        "/subscriptions/webhook",
        content=body,
        headers={"x-payment-signature": "0" * 64, "content-type": "application/json"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_webhook_delivery_is_a_noop(client):
    org_id, token = await _make_org(client)
    growth = await _plan_id_by_code(client, token, "growth")
    checkout = (
        await client.post(
            "/subscriptions/subscribe",
            headers=auth(token),
            json={"plan_id": growth, "billing_cycle": "monthly"},
        )
    ).json()

    body, headers = _signed_webhook(checkout["provider_ref"], amount=checkout["total"])
    first = await client.post("/subscriptions/webhook", content=body, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["result"] == "activated"

    second = await client.post("/subscriptions/webhook", content=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

    invoices = (
        await client.get("/subscriptions/invoices", headers=auth(token))
    ).json()
    assert [i["status"] for i in invoices] == ["paid"]


@pytest.mark.asyncio
async def test_unknown_and_out_of_order_events_are_stored_not_applied(client):
    org_id, token = await _make_org(client)
    growth = await _plan_id_by_code(client, token, "growth")
    checkout = (
        await client.post(
            "/subscriptions/subscribe",
            headers=auth(token),
            json={"plan_id": growth, "billing_cycle": "monthly"},
        )
    ).json()

    # An event for a checkout this platform never issued.
    body, headers = _signed_webhook("stub_nonexistent")
    response = await client.post("/subscriptions/webhook", content=body, headers=headers)
    assert response.json()["result"] == "no_matching_invoice"

    # Settle for real, then a late duplicate-state event with a fresh event id.
    body, headers = _signed_webhook(checkout["provider_ref"], amount=checkout["total"])
    assert (await client.post("/subscriptions/webhook", content=body, headers=headers)).json()[
        "result"
    ] == "activated"
    body, headers = _signed_webhook(checkout["provider_ref"], amount=checkout["total"])
    late = await client.post("/subscriptions/webhook", content=body, headers=headers)
    assert late.json()["result"] == "invoice_already_paid"

    from database import AsyncSessionLocal
    from models.subscription import PaymentEvent

    async with AsyncSessionLocal() as db:
        stored = (
            await db.execute(select(func.count()).select_from(PaymentEvent))
        ).scalar_one()
    assert stored >= 3

    sub = await _get_sub_row(org_id)
    assert str(sub.status) == "active"


# ── Plan changes ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upgrade_is_immediate_and_downgrade_waits_for_period_end(client):
    org_id, token = await _make_org(client)
    starter = await _plan_id_by_code(client, token, "starter")
    scale = await _plan_id_by_code(client, token, "scale")

    checkout = (
        await client.post(
            "/subscriptions/subscribe",
            headers=auth(token),
            json={"plan_id": starter, "billing_cycle": "monthly"},
        )
    ).json()
    await client.post(
        "/subscriptions/dev/simulate-payment",
        headers=auth(token),
        json={"provider_ref": checkout["provider_ref"]},
    )

    upgraded = await client.post(
        "/subscriptions/change-plan",
        headers=auth(token),
        json={"plan_id": scale},
    )
    assert upgraded.status_code == 200, upgraded.text
    body = upgraded.json()
    assert body["scheduled_downgrade"] is False
    assert body["checkout"] is not None, "an upgrade bills the prorated difference"
    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["plan"]["code"] == "scale"

    await client.post(
        "/subscriptions/dev/simulate-payment",
        headers=auth(token),
        json={"provider_ref": body["checkout"]["provider_ref"]},
    )

    downgraded = await client.post(
        "/subscriptions/change-plan",
        headers=auth(token),
        json={"plan_id": starter},
    )
    assert downgraded.status_code == 200
    body = downgraded.json()
    assert body["scheduled_downgrade"] is True
    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["plan"]["code"] == "scale", "the downgrade has not taken effect yet"
    assert current["subscription"]["pending_plan_id"] == starter

    # Roll time past the period end; the daily tick applies the downgrade and
    # renews on the new plan (the stub settles through the webhook path).
    from database import AsyncSessionLocal
    from models.subscription import OrganizationSubscription
    from services.subscription_jobs import process_subscription_cycle

    async with AsyncSessionLocal() as db:
        sub = (
            await db.execute(
                select(OrganizationSubscription)
                .where(OrganizationSubscription.organization_id == org_id)
                .with_for_update()
            )
        ).scalar_one()
        sub.current_period_end = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.commit()

    await process_subscription_cycle()

    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["plan"]["code"] == "starter"
    assert current["subscription"]["status"] == "active"
    assert current["subscription"]["pending_plan_id"] is None


@pytest.mark.asyncio
async def test_upgrade_from_complimentary_requires_payment_before_switch(client):
    """A legacy (no-period) subscription must not gain a paid plan for free."""
    org_id, token = await _make_org(client)
    legacy = await _make_plan({**GENEROUS})
    scale = await _plan_id_by_code(client, token, "scale")
    await _set_subscription(org_id, legacy, complimentary=True)

    upgraded = await client.post(
        "/subscriptions/change-plan",
        headers=auth(token),
        json={"plan_id": scale},
    )
    assert upgraded.status_code == 200, upgraded.text
    body = upgraded.json()
    assert body["checkout"] is not None, "the upgrade bills the full cycle"
    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["plan"]["code"] != "scale", "no entitlement before payment"
    assert current["subscription"]["pending_plan_id"] == scale

    # A failed payment clears the pending upgrade and leaves the org untouched.
    failed = await client.post(
        "/subscriptions/dev/simulate-payment",
        headers=auth(token),
        json={"provider_ref": body["checkout"]["provider_ref"], "status": "failed"},
    )
    assert failed.status_code == 200, failed.text
    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["plan"]["code"] != "scale"
    assert current["subscription"]["status"] == "active", "a failed upgrade is not past-due"
    assert current["subscription"]["pending_plan_id"] is None

    # Retrying and paying switches the plan and opens a real billing period.
    retry = await client.post(
        "/subscriptions/change-plan",
        headers=auth(token),
        json={"plan_id": scale},
    )
    assert retry.status_code == 200, retry.text
    paid = await client.post(
        "/subscriptions/dev/simulate-payment",
        headers=auth(token),
        json={"provider_ref": retry.json()["checkout"]["provider_ref"]},
    )
    assert paid.status_code == 200, paid.text
    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["plan"]["code"] == "scale"
    assert current["subscription"]["status"] == "active"
    assert current["subscription"]["current_period_end"] is not None


# ── Cancel / grace / expiry ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_keeps_access_until_period_end(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan(GENEROUS)
    await _set_subscription(org_id, plan)
    branch_id, batch_ids = await _make_tradable(org_id, batches=2)

    cancelled = await client.post("/subscriptions/cancel", headers=auth(token))
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancel_at_period_end"] is True

    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["entitlements"]["entitled"] is True, "access lasts to period end"
    created = await _create_listing(client, token, branch_id, batch_ids[0])
    assert created.status_code == 201, created.text

    from database import AsyncSessionLocal
    from models.subscription import OrganizationSubscription
    from services.subscription_jobs import process_subscription_cycle

    async with AsyncSessionLocal() as db:
        sub = (
            await db.execute(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org_id
                )
            )
        ).scalar_one()
        sub.current_period_end = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.commit()
    await process_subscription_cycle()

    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["subscription"]["status"] == "cancelled"
    assert current["entitlements"]["entitled"] is False
    blocked = await _create_listing(client, token, branch_id, batch_ids[1])
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_past_due_inside_grace_is_entitled_after_grace_is_not(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan(GENEROUS)
    now = datetime.now(timezone.utc)
    await _set_subscription(org_id, plan, status="past_due", grace=now + timedelta(days=2))
    branch_id, batch_ids = await _make_tradable(org_id, batches=2)

    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["entitlements"]["entitled"] is True
    assert (await _create_listing(client, token, branch_id, batch_ids[0])).status_code == 201

    from database import AsyncSessionLocal
    from models.subscription import OrganizationSubscription
    from services.subscription_jobs import process_subscription_cycle

    async with AsyncSessionLocal() as db:
        sub = (
            await db.execute(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org_id
                )
            )
        ).scalar_one()
        sub.grace_until = now - timedelta(hours=1)
        await db.commit()

    blocked = await _create_listing(client, token, branch_id, batch_ids[1])
    assert blocked.status_code == 403

    await process_subscription_cycle()
    sub = await _get_sub_row(org_id)
    assert str(sub.status) == "expired", "the tick expires past-due subscriptions past grace"


@pytest.mark.asyncio
async def test_expired_blocks_new_writes_but_existing_records_stay_readable(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan(GENEROUS)
    sub_id = await _set_subscription(org_id, plan)
    branch_id, batch_ids = await _make_tradable(org_id, batches=2)
    created = await _create_listing(client, token, branch_id, batch_ids[0])
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]

    from database import AsyncSessionLocal
    from models.subscription import OrganizationSubscription, SubscriptionStatus

    async with AsyncSessionLocal() as db:
        sub = await db.get(OrganizationSubscription, sub_id)
        sub.status = SubscriptionStatus.EXPIRED
        await db.commit()

    blocked = await _create_listing(client, token, branch_id, batch_ids[1])
    assert blocked.status_code == 403

    readable = await client.get(f"/listings/{listing_id}", headers=auth(token))
    assert readable.status_code == 200


@pytest.mark.asyncio
async def test_reactivation_goes_through_checkout(client):
    org_id, token = await _make_org(client)
    growth = await _plan_id_by_code(client, token, "growth")
    await _set_subscription(org_id, growth, status="expired")

    reactivated = await client.post(
        "/subscriptions/reactivate", headers=auth(token), json={}
    )
    assert reactivated.status_code == 200, reactivated.text
    checkout = reactivated.json()["checkout"]
    assert checkout is not None

    # Still expired until the webhook settles the new invoice.
    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["subscription"]["status"] == "expired"

    await client.post(
        "/subscriptions/dev/simulate-payment",
        headers=auth(token),
        json={"provider_ref": checkout["provider_ref"]},
    )
    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["subscription"]["status"] == "active"


@pytest.mark.asyncio
async def test_failed_payment_marks_past_due_with_grace(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan(GENEROUS)
    await _set_subscription(org_id, plan, status="trialing", trial_end=datetime.now(timezone.utc) + timedelta(days=5))

    checkout = (
        await client.post(
            "/subscriptions/subscribe",
            headers=auth(token),
            json={"plan_id": str(plan), "billing_cycle": "monthly"},
        )
    ).json()
    settled = await client.post(
        "/subscriptions/dev/simulate-payment",
        headers=auth(token),
        json={"provider_ref": checkout["provider_ref"], "status": "failed"},
    )
    assert settled.json()["result"] == "payment_failed"

    from database import AsyncSessionLocal
    from models.notification import Notification, NotificationType
    from models.subscription import SubscriptionInvoice

    async with AsyncSessionLocal() as db:
        invoice = (
            await db.execute(
                select(SubscriptionInvoice).where(
                    SubscriptionInvoice.provider_ref == checkout["provider_ref"]
                )
            )
        ).scalar_one()
        assert str(invoice.status) == "failed"
        notices = (
            await db.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.organization_id == org_id,
                    Notification.notification_type == NotificationType.SUBSCRIPTION_PAYMENT_FAILED,
                )
            )
        ).scalar_one()
    assert notices >= 1


# ── Limit enforcement ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_max_active_listings_cap(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan({**GENEROUS, "max_active_listings": 2})
    await _set_subscription(org_id, plan)
    branch_id, batch_ids = await _make_tradable(org_id, batches=3)

    assert (await _create_listing(client, token, branch_id, batch_ids[0])).status_code == 201
    assert (await _create_listing(client, token, branch_id, batch_ids[1])).status_code == 201
    blocked = await _create_listing(client, token, branch_id, batch_ids[2])
    assert blocked.status_code == 403
    assert "العروض النشطة" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_max_branches_cap(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan({**GENEROUS, "max_branches": 1})
    await _set_subscription(org_id, plan)
    await _make_tradable(org_id, batches=1)  # one active branch already

    blocked = await client.post(
        "/branches",
        headers=auth(token),
        json={"name": f"Overflow {unique()}", "branch_code": unique("OF-")},
    )
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_concurrent_listing_creation_at_cap_admits_exactly_one(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan({**GENEROUS, "max_active_listings": 1})
    await _set_subscription(org_id, plan)
    branch_id, batch_ids = await _make_tradable(org_id, batches=5)

    responses = await asyncio.gather(
        *[_create_listing(client, token, branch_id, bid) for bid in batch_ids]
    )
    outcomes = sorted(r.status_code for r in responses)
    assert outcomes == [201, 403, 403, 403, 403], outcomes


@pytest.mark.asyncio
async def test_record_usage_retry_does_not_double_count(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan(GENEROUS)
    await _set_subscription(org_id, plan)

    from database import AsyncSessionLocal
    from models.subscription import UsageCounter, UsageLedger
    from services.entitlement_service import EntitlementService

    async with AsyncSessionLocal() as db:
        svc = EntitlementService(db)
        key = f"retry:{uuid.uuid4().hex}"
        await svc.record_usage(org_id, "listings_created", idempotency_key=key)
        await svc.record_usage(org_id, "listings_created", idempotency_key=key)
        await svc.record_usage(org_id, "listings_created", idempotency_key=key)
        await db.commit()

        ledger_rows = (
            await db.execute(
                select(func.count()).select_from(UsageLedger).where(
                    UsageLedger.idempotency_key == key
                )
            )
        ).scalar_one()
        counter = (
            await db.execute(
                select(UsageCounter).where(
                    UsageCounter.organization_id == org_id,
                    UsageCounter.metric == "listings_created",
                )
            )
        ).scalar_one()
    assert ledger_rows == 1
    assert counter.count == 1


@pytest.mark.asyncio
async def test_usage_warning_fires_once_at_eighty_percent(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan({**GENEROUS, "max_listings_per_period": 5})
    await _set_subscription(org_id, plan)

    from database import AsyncSessionLocal
    from models.notification import Notification, NotificationType
    from services.entitlement_service import EntitlementService

    async def _warnings():
        async with AsyncSessionLocal() as db:
            return (
                await db.execute(
                    select(func.count()).select_from(Notification).where(
                        Notification.organization_id == org_id,
                        Notification.notification_type == NotificationType.USAGE_LIMIT_WARNING,
                    )
                )
            ).scalar_one()

    async with AsyncSessionLocal() as db:
        svc = EntitlementService(db)
        for _ in range(3):  # 3/5 = 60% — still quiet
            await svc.record_usage(
                org_id, "listings_created", idempotency_key=f"w:{uuid.uuid4().hex}"
            )
        await db.commit()
    assert await _warnings() == 0

    async with AsyncSessionLocal() as db:
        svc = EntitlementService(db)
        await svc.record_usage(
            org_id, "listings_created", idempotency_key=f"w:{uuid.uuid4().hex}"
        )
        await db.commit()
    assert await _warnings() == 1, "crossing 80% warns exactly once"

    async with AsyncSessionLocal() as db:
        svc = EntitlementService(db)
        await svc.record_usage(
            org_id, "listings_created", idempotency_key=f"w:{uuid.uuid4().hex}"
        )
        await db.commit()
    assert await _warnings() == 1, "and never again for this metric in this period"


# ── Compliance and isolation ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_suspended_org_stays_blocked_even_with_a_paid_plan(client):
    # Suspended accounts cannot sign in, so the suspension lands after login.
    org_id, token = await _make_org(client)
    plan = await _make_plan(GENEROUS)
    await _set_subscription(org_id, plan)
    branch_id, batch_ids = await _make_tradable(org_id)

    from database import AsyncSessionLocal
    from models.organization import OrganizationStatus, PharmacyOrganization

    async with AsyncSessionLocal() as db:
        org = await db.get(PharmacyOrganization, org_id)
        org.status = OrganizationStatus.SUSPENDED
        await db.commit()

    response = await _create_listing(client, token, branch_id, batch_ids[0])
    assert response.status_code == 422, "the eligibility gate wins over any subscription"


@pytest.mark.asyncio
async def test_cross_org_access_is_denied(client, seller_token):
    org_a, token_a = await _make_org(client)
    org_b, token_b = await _make_org(client)
    growth = await _plan_id_by_code(client, token_a, "growth")
    checkout = (
        await client.post(
            "/subscriptions/subscribe",
            headers=auth(token_a),
            json={"plan_id": growth, "billing_cycle": "monthly"},
        )
    ).json()

    invoices_b = (
        await client.get("/subscriptions/invoices", headers=auth(token_b))
    ).json()
    assert invoices_b == [], "org B sees none of org A's billing"

    current_b = (await client.get("/subscriptions/current", headers=auth(token_b))).json()
    assert current_b["subscription"] is None

    spoof = await client.post(
        "/subscriptions/dev/simulate-payment",
        headers=auth(token_b),
        json={"provider_ref": checkout["provider_ref"]},
    )
    assert spoof.status_code == 404, "a developer settles only their own org's checkouts"

    forbidden = await client.get("/subscriptions/admin/subscriptions", headers=auth(seller_token))
    assert forbidden.status_code == 403


# ── Trial expiry job ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trial_reminder_once_then_expiry(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan(GENEROUS, trial_days=14)
    now = datetime.now(timezone.utc)
    await _set_subscription(
        org_id, plan, status="trialing", trial_end=now + timedelta(days=2)
    )

    from database import AsyncSessionLocal
    from models.notification import Notification, NotificationType
    from models.subscription import OrganizationSubscription
    from services.subscription_jobs import process_subscription_cycle

    async def _reminders():
        async with AsyncSessionLocal() as db:
            return (
                await db.execute(
                    select(func.count()).select_from(Notification).where(
                        Notification.organization_id == org_id,
                        Notification.notification_type == NotificationType.SUBSCRIPTION_TRIAL_ENDING,
                    )
                )
            ).scalar_one()

    await process_subscription_cycle()
    assert await _reminders() == 1
    await process_subscription_cycle()
    assert await _reminders() == 1, "the 3-day reminder fires once, not on every tick"

    async with AsyncSessionLocal() as db:
        sub = (
            await db.execute(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org_id
                )
            )
        ).scalar_one()
        sub.trial_end = now - timedelta(hours=1)
        sub.current_period_end = sub.trial_end
        await db.commit()

    await process_subscription_cycle()
    sub = await _get_sub_row(org_id)
    assert str(sub.status) == "expired"


# ── Admin plan management ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_plan_crud_and_version_bump_on_referenced_plan(client, admin_token):
    created = await client.post(
        "/subscriptions/admin/plans",
        headers=auth(admin_token),
        json={
            "code": unique("adm-"),
            "name_ar": "باقة إدارية",
            "name_en": "Admin Plan",
            "monthly_price": 150,
            "annual_price": 1500,
            "trial_days": 0,
            "limits": GENEROUS,
        },
    )
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["version"] == 1

    # Unreferenced: edits happen in place.
    edited = await client.patch(
        f"/subscriptions/admin/plans/{plan['id']}",
        headers=auth(admin_token),
        json={"monthly_price": 175},
    )
    assert edited.status_code == 200
    assert edited.json()["id"] == plan["id"]
    assert edited.json()["version"] == 1
    assert float(edited.json()["monthly_price"]) == 175.0

    # Once an organization sits on the plan, editing forks a new version.
    org_id, _token = await _make_org(client)
    await _set_subscription(org_id, uuid.UUID(plan["id"]))
    bumped = await client.patch(
        f"/subscriptions/admin/plans/{plan['id']}",
        headers=auth(admin_token),
        json={"monthly_price": 199},
    )
    assert bumped.status_code == 200
    assert bumped.json()["version"] == 2
    assert bumped.json()["id"] != plan["id"]

    from database import AsyncSessionLocal
    from models.subscription import SubscriptionPlan

    async with AsyncSessionLocal() as db:
        original = await db.get(SubscriptionPlan, uuid.UUID(plan["id"]))
        assert float(original.monthly_price) == 175.0, "history is never rewritten"

    deactivated = await client.post(
        f"/subscriptions/admin/plans/{bumped.json()['id']}/deactivate",
        headers=auth(admin_token),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    same_code = await client.post(
        "/subscriptions/admin/plans",
        headers=auth(admin_token),
        json={
            "code": plan["code"],
            "name_ar": "باقة إدارية",
            "name_en": "Admin Plan",
            "monthly_price": 1,
            "annual_price": 1,
            "limits": {},
        },
    )
    assert same_code.status_code == 201
    assert same_code.json()["version"] == 3


# ── Usage summary ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_usage_summary_matches_live_counts(client):
    org_id, token = await _make_org(client)
    plan = await _make_plan({**GENEROUS, "max_active_listings": 10})
    await _set_subscription(org_id, plan)
    branch_id, batch_ids = await _make_tradable(org_id, batches=2)
    assert (await _create_listing(client, token, branch_id, batch_ids[0])).status_code == 201

    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    usage = current["usage"]
    assert usage["resources"]["active_listings"] == 1
    assert usage["resources"]["branches"] == 1
    assert usage["resources"]["team_members"] == 1
    assert usage["usage"]["listings_created"] == 1, "the listing hook meters itself"
    assert usage["limits"]["max_active_listings"] == 10


# ── Migration policy ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_migration_policy_covers_every_org(client):
    org_id, token = await _make_org(client)
    from database import AsyncSessionLocal
    from seeds.seed import ensure_legacy_subscriptions

    async with AsyncSessionLocal() as db:
        created = await ensure_legacy_subscriptions(db)
        await db.commit()
    assert created >= 1

    current = (await client.get("/subscriptions/current", headers=auth(token))).json()
    assert current["subscription"]["status"] == "active"
    assert current["subscription"]["current_period_end"] is None, "complimentary has no end"
    assert current["plan"]["code"] == "legacy"
    assert current["entitlements"]["entitled"] is True

    async with AsyncSessionLocal() as db:
        from models.organization import PharmacyOrganization
        from models.subscription import OrganizationSubscription

        total_orgs = (
            await db.execute(
                select(func.count()).select_from(PharmacyOrganization).where(
                    PharmacyOrganization.deleted_at.is_(None)
                )
            )
        ).scalar_one()
        total_subs = (
            await db.execute(select(func.count()).select_from(OrganizationSubscription))
        ).scalar_one()
    assert total_subs == total_orgs

    async with AsyncSessionLocal() as db:
        again = await ensure_legacy_subscriptions(db)
        await db.commit()
    assert again == 0, "the policy is idempotent"
