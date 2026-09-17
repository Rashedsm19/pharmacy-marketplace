"""Restock intelligence: engine math, lifecycle, actions, and tenant boundaries.

Fixture organizations are built directly in the database (faster and more
precise than the registration flow). Demand history is recorded through the
real POST /inventory/movements endpoint and aged by rewriting created_at —
never by sleeping. Expected quantities are recomputed here from the design-doc
formulas with the same Decimal arithmetic the engine uses:

    daily_velocity = dispensed_total(window) / window_days        [window 90]
    target_stock   = (lead 7 + safety 7 + review 14) * velocity
    suggested_qty  = ceil(max(0, target - usable - incoming))
    expiry cap     = ceil(velocity * matched_listing_shelf_days)
    surplus        = ceil(max(0, available - velocity * days_to_expiry))
"""
from __future__ import annotations

import asyncio
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy import update as sql_update

from tests.conftest import auth, unique

FIXTURE_PASSWORD = "Fixture@12345"

GENEROUS = {
    "max_active_listings": None,
    "max_branches": None,
    "max_team_members": None,
    "max_listings_per_period": None,
    "advanced_reports": True,
    "restock_intelligence": True,
    "api_access": True,
}


# ── Fixture builders ────────────────────────────────────────────────────────


async def _make_org(client):
    """An approved organization with one owner account; returns (org_id, user_id, token)."""
    from auth.password import hash_password
    from database import AsyncSessionLocal
    from models.organization import (
        MembershipRole,
        OrganizationStatus,
        PharmacyOrganization,
        UserOrganizationMembership,
    )
    from models.user import User, UserRole

    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    email = f"{unique('restock-')}@fixture.sa"
    async with AsyncSessionLocal() as db:
        db.add(PharmacyOrganization(
            id=org_id,
            name=f"Restock Org {unique()}",
            name_ar="منشأة اختبار التوريد",
            commercial_registration_number=f"CR-{uuid.uuid4().hex[:10]}",
            license_number=f"LIC-{uuid.uuid4().hex[:8]}",
            is_licensed=True,
            status=OrganizationStatus.APPROVED,
            email=email,
            phone="+966500000000",
        ))
        db.add(User(
            id=user_id,
            email=email,
            phone=None,
            full_name="Restock Owner",
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
    return org_id, user_id, response.json()["access_token"]


async def _make_branch(org_id):
    from database import AsyncSessionLocal
    from models.branch import PharmacyBranch, StorageConditionStatus

    branch_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(PharmacyBranch(
            id=branch_id,
            organization_id=org_id,
            name=f"Restock Branch {unique()}",
            branch_code=unique("RB-"),
            is_active=True,
            storage_condition_status=StorageConditionStatus.COMPLIANT,
        ))
        await db.commit()
    return branch_id


async def _make_rule(org_id, *, min_days=1, discount_pct=20):
    from database import AsyncSessionLocal
    from models.inventory import NearExpiryRule

    async with AsyncSessionLocal() as db:
        db.add(NearExpiryRule(
            id=uuid.uuid4(),
            organization_id=org_id,
            min_days_for_listing=min_days,
            auto_listing_discount_pct=discount_pct,
        ))
        await db.commit()


async def _make_product(standard_price=50.0):
    from database import AsyncSessionLocal
    from models.product import Product, ProductCategory

    product_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        category = (await db.execute(select(ProductCategory).limit(1))).scalar_one()
        db.add(Product(
            id=product_id,
            category_id=category.id,
            name=f"Restock Product {unique()}",
            name_ar="منتج اختبار التوريد",
            sku=unique("RSKU-"),
            standard_price=standard_price,
            is_active=True,
        ))
        await db.commit()
    return product_id


async def _make_batch(
    org_id, branch_id, product_id, *, qty=100, expiry_days=200, is_opened=False
):
    from database import AsyncSessionLocal
    from models.inventory import BatchStatus, InventoryBatch

    batch_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(InventoryBatch(
            id=batch_id,
            organization_id=org_id,
            branch_id=branch_id,
            product_id=product_id,
            batch_number=unique("BTH-"),
            quantity=qty,
            quantity_available=qty,
            unit_cost=10,
            expiry_date=date.today() + timedelta(days=expiry_days),
            received_date=date.today(),
            status=BatchStatus.ACTIVE,
            storage_condition_status="compliant",
            is_opened=is_opened,
        ))
        await db.commit()
    return batch_id


async def _make_seller_listing(product_id, *, price, shelf_days=100, qa=500):
    """Another org's ACTIVE, eligible listing for the product; returns listing id."""
    from auth.password import hash_password
    from database import AsyncSessionLocal
    from models.branch import PharmacyBranch, StorageConditionStatus
    from models.inventory import BatchStatus, InventoryBatch
    from models.marketplace import ListingStatus, MarketplaceListing
    from models.organization import OrganizationStatus, PharmacyOrganization
    from models.user import User, UserRole

    listing_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        seller_org_id, branch_id, batch_id, user_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        db.add(PharmacyOrganization(
            id=seller_org_id,
            name=f"Seller Org {unique()}",
            name_ar="منشأة بائع",
            commercial_registration_number=f"CR-{uuid.uuid4().hex[:10]}",
            license_number=f"LIC-{uuid.uuid4().hex[:8]}",
            is_licensed=True,
            status=OrganizationStatus.APPROVED,
            email=f"{unique('seller-')}@fixture.sa",
            phone="+966500000000",
        ))
        db.add(PharmacyBranch(
            id=branch_id,
            organization_id=seller_org_id,
            name="Seller Branch",
            branch_code=unique("SB-"),
            is_active=True,
            storage_condition_status=StorageConditionStatus.COMPLIANT,
        ))
        db.add(User(
            id=user_id,
            email=f"{unique('selleruser-')}@fixture.sa",
            phone=None,
            full_name="Seller User",
            hashed_password=hash_password(FIXTURE_PASSWORD),
            role=UserRole.ORG_ADMIN,
            is_active=True,
        ))
        db.add(InventoryBatch(
            id=batch_id,
            organization_id=seller_org_id,
            branch_id=branch_id,
            product_id=product_id,
            batch_number=unique("BTH-"),
            quantity=qa,
            quantity_available=qa,
            unit_cost=10,
            expiry_date=date.today() + timedelta(days=shelf_days),
            status=BatchStatus.LISTED,
            storage_condition_status="compliant",
        ))
        db.add(MarketplaceListing(
            id=listing_id,
            seller_organization_id=seller_org_id,
            seller_branch_id=branch_id,
            batch_id=batch_id,
            created_by_id=user_id,
            title="Seller lot",
            title_ar="دفعة بائع",
            quantity_listed=qa,
            quantity_available=qa,
            asking_price=price,
            status=ListingStatus.ACTIVE,
            eligibility_passed=True,
        ))
        await db.commit()
    return listing_id


async def _dispense(client, token, batch_id, quantity, *, days_ago):
    """Record a dispensed movement through the API, then age it into the window."""
    from database import AsyncSessionLocal
    from models.inventory import InventoryMovement

    response = await client.post(
        "/inventory/movements",
        headers=auth(token),
        json={"batch_id": str(batch_id), "movement_type": "dispensed", "quantity": quantity},
    )
    assert response.status_code == 201, response.text
    movement_id = uuid.UUID(response.json()["id"])
    async with AsyncSessionLocal() as db:
        await db.execute(
            sql_update(InventoryMovement)
            .where(InventoryMovement.id == movement_id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=days_ago))
        )
        await db.commit()
    return movement_id


async def _refresh(client, token):
    response = await client.post("/restock/recommendations/refresh", headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()


async def _list(client, token, **params):
    response = await client.get(
        "/restock/recommendations", headers=auth(token), params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _single_rec(client, token, kind):
    body = await _list(client, token, kind=kind)
    assert body["total"] == 1, body
    return body["items"][0]


async def _rec_row(rec_id):
    from database import AsyncSessionLocal
    from models.restock import RestockRecommendation

    async with AsyncSessionLocal() as db:
        return (
            await db.execute(
                select(RestockRecommendation).where(RestockRecommendation.id == rec_id)
            )
        ).scalar_one()


async def _set_feature_subscription(org_id, *, restock_intelligence):
    from database import AsyncSessionLocal
    from models.subscription import (
        BillingCycle,
        OrganizationSubscription,
        SubscriptionPlan,
        SubscriptionStatus,
    )
    from services.subscription_service import plan_snapshot

    async with AsyncSessionLocal() as db:
        plan_id = uuid.uuid4()
        db.add(SubscriptionPlan(
            id=plan_id,
            code=unique("plan-"),
            version=1,
            name_ar="باقة اختبار",
            name_en="Test Plan",
            monthly_price=100,
            annual_price=1000,
            trial_days=0,
            limits={**GENEROUS, "restock_intelligence": restock_intelligence},
            is_active=True,
            is_public=False,
        ))
        await db.flush()
        plan = await db.get(SubscriptionPlan, plan_id)
        now = datetime.now(timezone.utc)
        db.add(OrganizationSubscription(
            id=uuid.uuid4(),
            organization_id=org_id,
            plan_id=plan_id,
            plan_snapshot=plan_snapshot(plan),
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=30),
        ))
        await db.commit()


# ── Evidence and replenishment math ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_zero_demand_is_insufficient_hold(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id)
    product_id = await _make_product()
    await _make_batch(org_id, branch_id, product_id, qty=100, expiry_days=200)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "replenishment")

    assert rec["action"] == "hold"
    assert rec["evidence_strength"] == "insufficient"
    assert rec["suggested_qty"] == 0
    assert rec["suggested_price"] is None
    assert float(rec["daily_velocity"]) == 0
    assert rec["days_of_cover"] is None
    assert rec["on_hand_qty"] == 100
    assert "صرف" in rec["reason_ar"], "the reason must name the missing dispensing history"
    assert "no dispensing history" in rec["reason_en"].lower()


@pytest.mark.asyncio
async def test_stale_demand_outside_window_is_insufficient(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=100, expiry_days=200)

    await _dispense(client, token, batch_id, 10, days_ago=100)
    await _dispense(client, token, batch_id, 10, days_ago=120)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "replenishment")
    assert rec["evidence_strength"] == "insufficient"
    assert rec["action"] == "hold"
    assert rec["suggested_qty"] == 0
    assert rec["on_hand_qty"] == 80


@pytest.mark.asyncio
async def test_velocity_cover_and_suggested_qty_math(client):
    """Sparse history (40-day span): every figure checked against the formula."""
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=200, expiry_days=200)

    await _dispense(client, token, batch_id, 95, days_ago=60)
    await _dispense(client, token, batch_id, 95, days_ago=20)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "replenishment")

    velocity = (Decimal(190) / Decimal(90)).quantize(Decimal("0.001"))  # 2.111
    target = Decimal(7 + 7 + 14) * velocity                              # 59.108
    expected_qty = math.ceil(target - 10 - 0)                            # 50
    expected_cover = (Decimal(10) / velocity).quantize(Decimal("0.1"))   # 4.7

    assert rec["evidence_strength"] == "sparse", "40-day span is below half the window"
    assert float(rec["daily_velocity"]) == float(velocity)
    assert float(rec["days_of_cover"]) == float(expected_cover)
    assert rec["on_hand_qty"] == 10
    assert rec["incoming_qty"] == 0
    assert rec["action"] == "reorder_supplier", "no marketplace listing exists for this product"
    assert rec["matched_listing_id"] is None
    assert rec["suggested_qty"] == expected_qty
    assert rec["suggested_price"] is None, "no price is ever invented"
    assert "المورد" in rec["reason_ar"]


@pytest.mark.asyncio
async def test_sufficient_evidence_healthy_cover_holds_and_expired_stock_excluded(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=300, expiry_days=200)
    await _make_batch(org_id, branch_id, product_id, qty=500, expiry_days=-1)

    await _dispense(client, token, batch_id, 90, days_ago=80)
    await _dispense(client, token, batch_id, 90, days_ago=10)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "replenishment")

    assert rec["evidence_strength"] == "sufficient", "70-day span covers over half the window"
    assert float(rec["daily_velocity"]) == 2.0
    assert rec["on_hand_qty"] == 120, "the expired batch's 500 units are not usable stock"
    assert rec["action"] == "hold", "120 units beat the 56-unit target — cover is healthy"
    assert rec["suggested_qty"] == 0


@pytest.mark.asyncio
async def test_listed_and_incoming_quantities_reduce_what_is_needed(client):
    org_id, user_id, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=300, expiry_days=200)

    # 80 units of the batch are already committed to a live listing.
    from database import AsyncSessionLocal
    from models.marketplace import (
        ListingStatus,
        MarketplaceListing,
        Reservation,
        ReservationStatus,
    )
    from models.transaction import Transaction, TransactionStatus

    own_listing_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(MarketplaceListing(
            id=own_listing_id,
            seller_organization_id=org_id,
            seller_branch_id=branch_id,
            batch_id=batch_id,
            created_by_id=user_id,
            title="Own lot",
            quantity_listed=80,
            quantity_available=80,
            asking_price=15.0,
            status=ListingStatus.ACTIVE,
            eligibility_passed=True,
        ))
        await db.commit()

    # Incoming: an open reservation (5) plus an in-flight purchase (4).
    reserved_listing = await _make_seller_listing(product_id, price=30.0)
    inflight_listing = await _make_seller_listing(product_id, price=25.0)
    async with AsyncSessionLocal() as db:
        inflight_seller_org = (
            await db.execute(
                select(MarketplaceListing.seller_organization_id).where(
                    MarketplaceListing.id == inflight_listing
                )
            )
        ).scalar_one()
        db.add(Reservation(
            id=uuid.uuid4(),
            listing_id=reserved_listing,
            buyer_organization_id=org_id,
            reserved_by_id=user_id,
            quantity=5,
            agreed_price=30.0,
            status=ReservationStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        ))
        db.add(Transaction(
            id=uuid.uuid4(),
            listing_id=inflight_listing,
            seller_organization_id=inflight_seller_org,
            buyer_organization_id=org_id,
            quantity=4,
            unit_price=25.0,
            total_amount=100.0,
            platform_fee=2.0,
            net_amount=98.0,
            status=TransactionStatus.PENDING,
            reference_number=unique("TXN-"),
        ))
        await db.commit()

    await _dispense(client, token, batch_id, 90, days_ago=80)
    await _dispense(client, token, batch_id, 90, days_ago=10)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "replenishment")

    velocity = Decimal("2.000")
    target = Decimal(28) * velocity  # 56
    usable = 300 - 180 - 80          # 40 — listed units are not usable
    incoming = 9
    expected_qty = math.ceil(target - usable - incoming)  # 7

    assert rec["on_hand_qty"] == 40
    assert rec["incoming_qty"] == 9
    assert rec["suggested_qty"] == expected_qty
    assert rec["action"] == "buy_from_marketplace"
    assert rec["matched_listing_id"] == inflight_listing.__str__(), "cheapest eligible listing wins"


@pytest.mark.asyncio
async def test_buyer_match_is_cheapest_eligible_and_expiry_capped(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=200, expiry_days=200)

    # A low shelf-life floor (5d) lets the expiry cap bind against a 10-day lot.
    from database import AsyncSessionLocal
    from models.settings import PlatformSettings

    setting_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(PlatformSettings(
            id=setting_id,
            key="restock.min_buy_shelf_life_days",
            value={"value": 5},
            category="restock",
        ))
        await db.commit()

    try:
        cheap_short = await _make_seller_listing(product_id, price=25.0, shelf_days=10)
        await _make_seller_listing(product_id, price=30.0, shelf_days=100)
        excluded = await _make_seller_listing(product_id, price=20.0, shelf_days=3)

        await _dispense(client, token, batch_id, 95, days_ago=60)
        await _dispense(client, token, batch_id, 95, days_ago=20)

        await _refresh(client, token)
        rec = await _single_rec(client, token, "replenishment")

        velocity = (Decimal(190) / Decimal(90)).quantize(Decimal("0.001"))  # 2.111
        raw_qty = math.ceil(Decimal(28) * velocity - 10)                    # 50
        expiry_cap = math.ceil(velocity * 10)                               # 22

        assert rec["action"] == "buy_from_marketplace"
        assert rec["matched_listing_id"] == str(cheap_short), (
            f"cheapest eligible listing wins, not the 3-day lot {excluded}"
        )
        assert rec["matched_listing_id"] != str(excluded)
        assert rec["suggested_qty"] == min(raw_qty, expiry_cap) == 22
        assert float(rec["suggested_price"]) == 25.0
        assert rec["inputs"]["expiry_cap_qty"] == expiry_cap
    finally:
        async with AsyncSessionLocal() as db:
            setting = await db.get(PlatformSettings, setting_id)
            if setting is not None:
                await db.delete(setting)
                await db.commit()


# ── Seller listing recommendations ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_seller_surplus_no_demand_and_median_price_evidence(client):
    org_id, user_id, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1, discount_pct=20)
    product_id = await _make_product(standard_price=50.0)
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=100, expiry_days=60)

    # Market evidence: two completed sales of the same product at 40 and 20.
    from database import AsyncSessionLocal
    from models.marketplace import MarketplaceListing
    from models.transaction import Transaction, TransactionStatus

    for price in (40.0, 20.0):
        listing_id = await _make_seller_listing(product_id, price=price)
        async with AsyncSessionLocal() as db:
            seller_org_id = (
                await db.execute(
                    select(MarketplaceListing.seller_organization_id).where(
                        MarketplaceListing.id == listing_id
                    )
                )
            ).scalar_one()
            db.add(Transaction(
                id=uuid.uuid4(),
                listing_id=listing_id,
                seller_organization_id=seller_org_id,
                buyer_organization_id=org_id,
                quantity=5,
                unit_price=price,
                total_amount=5 * price,
                platform_fee=1.0,
                net_amount=5 * price - 1.0,
                status=TransactionStatus.COMPLETED,
                reference_number=unique("TXN-"),
                completed_at=datetime.now(timezone.utc),
            ))
            await db.commit()

    await _refresh(client, token)
    rec = await _single_rec(client, token, "listing")

    assert rec["action"] == "list_now"
    assert rec["batch_id"] == str(batch_id)
    assert rec["evidence_strength"] == "insufficient"
    assert rec["suggested_qty"] == 100, "no demand data → the whole lot is surplus"
    assert rec["inputs"]["surplus_basis"] == "no_demand_data"
    assert rec["inputs"]["price_evidence"] == "market_median"
    assert float(rec["market_median_price"]) == 30.0, "median of [20, 40]"
    assert float(rec["suggested_price"]) == 24.0, "median less the 20% zone discount"

    # One notification for the owners on the first run, none on the next.
    from models.notification import Notification, NotificationType

    async def _notices():
        async with AsyncSessionLocal() as db:
            return (
                await db.execute(
                    select(func.count()).select_from(Notification).where(
                        Notification.organization_id == org_id,
                        Notification.notification_type == NotificationType.RESTOCK_RECOMMENDATION,
                    )
                )
            ).scalar_one()

    assert await _notices() == 1
    await _refresh(client, token)
    assert await _notices() == 1, "a recompute with nothing new must stay quiet"


@pytest.mark.asyncio
async def test_seller_price_falls_back_to_standard_price_then_none(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1, discount_pct=20)
    priced = await _make_product(standard_price=50.0)
    unpriced = await _make_product(standard_price=None)
    await _make_batch(org_id, branch_id, priced, qty=40, expiry_days=90)
    await _make_batch(org_id, branch_id, unpriced, qty=30, expiry_days=90)

    await _refresh(client, token)
    recs = (await _list(client, token, kind="listing"))["items"]
    by_product = {r["product_id"]: r for r in recs}

    fallback = by_product[str(priced)]
    assert float(fallback["suggested_price"]) == 40.0, "50.00 less the 20% discount"
    assert fallback["inputs"]["price_evidence"] == "standard_price"

    missing = by_product[str(unpriced)]
    assert missing["suggested_price"] is None, "no evidence → no invented price"
    assert missing["inputs"]["price_evidence"] == "none"
    assert "حدد سعر" in missing["reason_ar"]


@pytest.mark.asyncio
async def test_seller_surplus_formula_with_demand(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=190, expiry_days=60)

    await _dispense(client, token, batch_id, 45, days_ago=70)
    await _dispense(client, token, batch_id, 45, days_ago=10)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "listing")

    # velocity 1.0/day × 60 days to expiry consumes 60 of the 100 left.
    assert rec["evidence_strength"] == "sufficient"
    assert rec["suggested_qty"] == 40
    assert rec["inputs"]["surplus_basis"] == "velocity"


# ── Lifecycle ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dismiss_survives_refresh_until_signature_changes_or_cooldown_passes(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=100, expiry_days=200)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "replenishment")

    dismissed = await client.post(
        f"/restock/recommendations/{rec['id']}/dismiss", headers=auth(token)
    )
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["status"] == "dismissed"

    await _refresh(client, token)
    still = await _list(client, token, status="dismissed")
    assert still["total"] == 1, "a dismissal survives a recompute inside the cooldown"

    # Changed inputs (a dispensed unit shifts velocity and usable stock) revive it.
    await _dispense(client, token, batch_id, 10, days_ago=1)
    await _refresh(client, token)
    revived = await _list(client, token, status="new")
    assert revived["total"] == 1, "a changed input signature regenerates the recommendation"

    # Without any change, only the cooldown passing brings it back.
    await client.post(f"/restock/recommendations/{rec['id']}/dismiss", headers=auth(token))
    from database import AsyncSessionLocal
    from models.restock import RestockRecommendation

    async with AsyncSessionLocal() as db:
        await db.execute(
            sql_update(RestockRecommendation)
            .where(RestockRecommendation.id == uuid.UUID(rec["id"]))
            .values(dismissed_at=datetime.now(timezone.utc) - timedelta(days=8))
        )
        await db.commit()
    await _refresh(client, token)
    back = await _list(client, token, status="new")
    assert back["total"] == 1, "the 7-day dismiss cooldown expired"


@pytest.mark.asyncio
async def test_listing_rec_superseded_when_batch_listed_or_stock_hits_zero(client):
    org_id, user_id, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=50, expiry_days=100)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "listing")
    assert rec["status"] == "new"

    # Stock hits zero through the movements endpoint.
    drained = await client.post(
        "/inventory/movements",
        headers=auth(token),
        json={"batch_id": str(batch_id), "movement_type": "dispensed", "quantity": 50},
    )
    assert drained.status_code == 201, drained.text

    await _refresh(client, token)
    gone = await _list(client, token, status="superseded")
    assert gone["total"] == 1, "a batch with no stock left can no longer be listed"


@pytest.mark.asyncio
async def test_listing_rec_superseded_when_batch_already_listed(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=100, expiry_days=100)

    await _refresh(client, token)
    assert (await _list(client, token, kind="listing"))["total"] == 1

    listed = await client.post(
        "/listings",
        headers=auth(token),
        json={
            "batch_id": str(batch_id),
            "seller_branch_id": str(branch_id),
            "title": "Manual lot",
            "title_ar": "دفعة يدوية",
            "quantity_listed": 50,
            "asking_price": 10.0,
        },
    )
    assert listed.status_code == 201, listed.text

    await _refresh(client, token)
    superseded = await _list(client, token, status="superseded")
    assert superseded["total"] == 1, "a batch already on the market needs no recommendation"


@pytest.mark.asyncio
async def test_concurrent_refresh_creates_no_duplicates(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1)
    product_id = await _make_product()
    await _make_batch(org_id, branch_id, product_id, qty=100, expiry_days=100)

    first, second = await asyncio.gather(
        client.post("/restock/recommendations/refresh", headers=auth(token)),
        client.post("/restock/recommendations/refresh", headers=auth(token)),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    summary = (
        await client.get("/restock/recommendations/summary", headers=auth(token))
    ).json()
    assert summary["total"] == 2, "one replenishment + one listing row, unique key holds"

    await _refresh(client, token)
    again = (
        await client.get("/restock/recommendations/summary", headers=auth(token))
    ).json()
    assert again["total"] == 2, "refresh is idempotent"


# ── Actions ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_act_open_listing_marks_acted_and_survives_recompute(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=200, expiry_days=200)
    matched = await _make_seller_listing(product_id, price=25.0, shelf_days=100)

    await _dispense(client, token, batch_id, 95, days_ago=60)
    await _dispense(client, token, batch_id, 95, days_ago=20)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "replenishment")
    assert rec["matched_listing_id"] == str(matched)

    acted = await client.post(
        f"/restock/recommendations/{rec['id']}/act",
        headers=auth(token),
        json={"action": "open_listing"},
    )
    assert acted.status_code == 200, acted.text
    assert acted.json()["listing_id"] == str(matched)
    assert acted.json()["recommendation"]["status"] == "acted"

    again = await client.post(
        f"/restock/recommendations/{rec['id']}/act",
        headers=auth(token),
        json={"action": "open_listing"},
    )
    assert again.status_code == 409, "acting twice is refused"

    dismissed = await client.post(
        f"/restock/recommendations/{rec['id']}/dismiss", headers=auth(token)
    )
    assert dismissed.status_code == 409

    await _refresh(client, token)
    row = await _rec_row(uuid.UUID(rec["id"]))
    assert str(row.status) == "acted", "acted rows are never overwritten by a recompute"


@pytest.mark.asyncio
async def test_act_create_listing_creates_a_real_listing(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1, discount_pct=20)
    product_id = await _make_product(standard_price=50.0)
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=100, expiry_days=100)

    await _refresh(client, token)
    rec = await _single_rec(client, token, "listing")
    assert float(rec["suggested_price"]) == 40.0

    acted = await client.post(
        f"/restock/recommendations/{rec['id']}/act",
        headers=auth(token),
        json={"action": "create_listing", "asking_price": 33.5, "quantity": 40},
    )
    assert acted.status_code == 200, acted.text
    listing_id = acted.json()["listing_id"]
    assert listing_id is not None
    assert acted.json()["recommendation"]["status"] == "acted"
    assert acted.json()["recommendation"]["inputs"]["created_listing_id"] == listing_id

    from database import AsyncSessionLocal
    from models.marketplace import ListingStatus, MarketplaceListing

    async with AsyncSessionLocal() as db:
        listing = await db.get(MarketplaceListing, uuid.UUID(listing_id))
    assert listing is not None
    assert listing.batch_id == batch_id
    assert listing.quantity_listed == 40
    assert float(listing.asking_price) == 33.5
    assert str(listing.status) == ListingStatus.ACTIVE.value
    assert listing.eligibility_passed is True


@pytest.mark.asyncio
async def test_act_create_listing_revalidates_eligibility(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1)
    product_id = await _make_product()
    await _make_batch(
        org_id, branch_id, product_id, qty=100, expiry_days=100, is_opened=True
    )

    await _refresh(client, token)
    rec = await _single_rec(client, token, "listing")

    refused = await client.post(
        f"/restock/recommendations/{rec['id']}/act",
        headers=auth(token),
        json={"action": "create_listing"},
    )
    assert refused.status_code == 422, "an opened batch fails eligibility at submit time"

    row = await _rec_row(uuid.UUID(rec["id"]))
    assert str(row.status) != "acted", "a refused act leaves the recommendation actionable"


# ── Read paths, boundaries and the entitlement gate ─────────────────────────


@pytest.mark.asyncio
async def test_view_marks_viewed_and_summary_and_filters(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    await _make_rule(org_id, min_days=1)
    product_id = await _make_product()
    await _make_batch(org_id, branch_id, product_id, qty=100, expiry_days=100)

    await _refresh(client, token)
    summary = (
        await client.get("/restock/recommendations/summary", headers=auth(token))
    ).json()
    assert summary["total"] == 2
    assert summary["counts"]["listing.new"] == 1
    assert summary["counts"]["replenishment.new"] == 1
    assert summary["last_computed_at"] is not None

    rec = await _single_rec(client, token, "listing")
    viewed = await client.get(
        f"/restock/recommendations/{rec['id']}", headers=auth(token))
    assert viewed.status_code == 200, viewed.text
    assert viewed.json()["status"] == "viewed"

    assert (await _list(client, token, status="viewed"))["total"] == 1
    assert (await _list(client, token, kind="replenishment"))["total"] == 1
    assert (await _list(client, token, branch_id=uuid.uuid4()))["total"] == 0


@pytest.mark.asyncio
async def test_cross_org_access_is_denied(client):
    org_a, _, token_a = await _make_org(client)
    branch_a = await _make_branch(org_a)
    await _make_rule(org_a, min_days=1)
    product_id = await _make_product()
    await _make_batch(org_a, branch_a, product_id, qty=100, expiry_days=100)
    await _refresh(client, token_a)
    rec = await _single_rec(client, token_a, "listing")

    org_b, _, token_b = await _make_org(client)

    seen = await _list(client, token_b)
    assert seen["total"] == 0, "org B sees none of org A's recommendations"

    detail = await client.get(
        f"/restock/recommendations/{rec['id']}", headers=auth(token_b))
    assert detail.status_code == 404

    dismissed = await client.post(
        f"/restock/recommendations/{rec['id']}/dismiss", headers=auth(token_b))
    assert dismissed.status_code == 404

    acted = await client.post(
        f"/restock/recommendations/{rec['id']}/act",
        headers=auth(token_b),
        json={"action": "create_listing", "asking_price": 10.0},
    )
    assert acted.status_code == 404


@pytest.mark.asyncio
async def test_entitlement_gate_blocks_without_restock_feature(client):
    org_id, _, token = await _make_org(client)

    allowed = await client.get("/restock/recommendations", headers=auth(token))
    assert allowed.status_code == 200, "a legacy org without a subscription row is entitled"

    await _set_feature_subscription(org_id, restock_intelligence=False)

    blocked = await client.get("/restock/recommendations", headers=auth(token))
    assert blocked.status_code == 403
    assert "باقتك" in blocked.json()["detail"]

    refresh = await client.post("/restock/recommendations/refresh", headers=auth(token))
    assert refresh.status_code == 403


# ── Movements endpoint ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispensing_more_than_available_is_rejected(client):
    org_id, _, token = await _make_org(client)
    branch_id = await _make_branch(org_id)
    product_id = await _make_product()
    batch_id = await _make_batch(org_id, branch_id, product_id, qty=10, expiry_days=200)

    too_much = await client.post(
        "/inventory/movements",
        headers=auth(token),
        json={"batch_id": str(batch_id), "movement_type": "dispensed", "quantity": 11},
    )
    assert too_much.status_code == 400
    assert "المتاح" in too_much.json()["detail"]

    ok = await client.post(
        "/inventory/movements",
        headers=auth(token),
        json={
            "batch_id": str(batch_id),
            "movement_type": "dispensed",
            "quantity": 4,
            "note": "صرف للمرضى",
        },
    )
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["movement_type"] == "dispensed"
    assert body["quantity_delta"] == -4
    assert body["quantity_before"] == 10
    assert body["quantity_after"] == 6

    adjusted = await client.post(
        "/inventory/movements",
        headers=auth(token),
        json={"batch_id": str(batch_id), "movement_type": "adjusted", "quantity": 6},
    )
    assert adjusted.status_code == 201
    assert adjusted.json()["quantity_after"] == 0

    empty = await client.post(
        "/inventory/movements",
        headers=auth(token),
        json={"batch_id": str(batch_id), "movement_type": "dispensed", "quantity": 1},
    )
    assert empty.status_code == 400


@pytest.mark.asyncio
async def test_movement_on_another_orgs_batch_is_not_found(client):
    org_a, _, token_a = await _make_org(client)
    branch_a = await _make_branch(org_a)
    product_id = await _make_product()
    batch_id = await _make_batch(org_a, branch_a, product_id, qty=10, expiry_days=200)

    _, _, token_b = await _make_org(client)
    response = await client.post(
        "/inventory/movements",
        headers=auth(token_b),
        json={"batch_id": str(batch_id), "movement_type": "dispensed", "quantity": 1},
    )
    assert response.status_code == 404
