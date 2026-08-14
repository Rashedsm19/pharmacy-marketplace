"""
The platform support console.

Support acts on other people's accounts, so these tests are mostly about what it
must refuse: locking itself out, touching a peer administrator, deleting stock a
buyer is relying on, and leaving an action without a trace.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from tests.conftest import auth, unique


async def a_customer_user(client, admin_token, email_contains: str = "aldawaa"):
    listed = await client.get(
        "/admin/users", headers=auth(admin_token), params={"page_size": 200}
    )
    assert listed.status_code == 200
    match = next(
        (u for u in listed.json()["items"] if email_contains in u["email"]), None
    )
    assert match is not None, f"no seeded user matching {email_contains}"
    return match


# ── Reading accounts ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_support_sees_every_account_with_its_pharmacy(client, admin_token):
    response = await client.get(
        "/admin/users", headers=auth(admin_token), params={"page_size": 200}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 4

    seller = next(u for u in body["items"] if u["email"] == "manager@aldawaa.sa")
    assert seller["organization_name"], "each account must name its pharmacy"
    assert seller["membership_role"], "and the person's role in it"
    assert seller["role"] == "org_admin"

    # The platform's own account has no pharmacy, and says so rather than lying.
    admin = next(
        u for u in body["items"] if u["email"] == "admin@pharmacy-marketplace.sa"
    )
    assert admin["organization_id"] is None


@pytest.mark.asyncio
async def test_support_can_search_and_filter(client, admin_token):
    found = await client.get(
        "/admin/users", headers=auth(admin_token), params={"search": "aldawaa"}
    )
    assert found.status_code == 200
    assert found.json()["total"] >= 1
    assert all("aldawaa" in u["email"] for u in found.json()["items"])

    by_role = await client.get(
        "/admin/users", headers=auth(admin_token), params={"role": "pharmacist"}
    )
    assert all(u["role"] == "pharmacist" for u in by_role.json()["items"])


@pytest.mark.asyncio
async def test_a_pharmacy_cannot_reach_the_support_console(client, seller_token):
    for path in ("/admin/users", f"/admin/users/{uuid.uuid4()}"):
        response = await client.get(path, headers=auth(seller_token))
        assert response.status_code == 403, path


# ── Password reset ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_support_issued_link_actually_resets_the_password(
    client, admin_token, buyer_token
):
    """The whole point: the customer must be able to get back in with it."""
    from tests.conftest import SEEDED

    email, original = SEEDED["buyer"]
    target = await a_customer_user(client, admin_token, "nahdi-demo")

    issued = await client.post(
        f"/admin/users/{target['id']}/reset-link",
        headers=auth(admin_token),
        json={"reason": "العميل فقد كلمة المرور واتصل بالدعم"},
    )
    assert issued.status_code == 200, issued.text
    body = issued.json()
    assert "/ar/reset-password?token=" in body["reset_url"]
    # Email is not configured on this deployment; the response says so plainly
    # instead of pretending the customer received something.
    assert body["email_sent"] is False
    assert "انسخ الرابط" in body["notice"]

    token = body["reset_url"].split("token=")[1]
    new_password = "Reset@98765"
    used = await client.post(
        "/auth/reset-password", json={"token": token, "new_password": new_password}
    )
    assert used.status_code in (200, 204), used.text

    signed_in = await client.post(
        "/auth/login", json={"email": email, "password": new_password}
    )
    assert signed_in.status_code == 200, "the customer must be able to sign in"

    # Put the seeded password back so the rest of the suite is unaffected.
    again = await client.post(
        f"/admin/users/{target['id']}/reset-link",
        headers=auth(admin_token),
        json={"reason": "إعادة كلمة المرور الأصلية بعد الاختبار"},
    )
    restore_token = again.json()["reset_url"].split("token=")[1]
    await client.post(
        "/auth/reset-password",
        json={"token": restore_token, "new_password": original},
    )


@pytest.mark.asyncio
async def test_the_reset_token_is_not_stored_in_readable_form(client, admin_token):
    """A stored token is a stored password. Only its digest may be kept."""
    from database import AsyncSessionLocal
    from models.user import User

    target = await a_customer_user(client, admin_token, "pharmacist@aldawaa")
    issued = await client.post(
        f"/admin/users/{target['id']}/reset-link",
        headers=auth(admin_token),
        json={"reason": "اختبار تخزين الرمز"},
    )
    token = issued.json()["reset_url"].split("token=")[1]

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(User).where(User.id == uuid.UUID(target["id"])))
        ).scalar_one()

    assert row.password_reset_token != token, "the raw token must not be stored"
    assert len(row.password_reset_token) == 64, "a sha-256 digest is expected"


@pytest.mark.asyncio
async def test_the_reset_link_never_reaches_the_audit_trail(client, admin_token):
    """The audit trail must not become a way into the account it records."""
    from database import AsyncSessionLocal
    from models.audit import AuditLog

    target = await a_customer_user(client, admin_token, "pharmacist@aldawaa")
    issued = await client.post(
        f"/admin/users/{target['id']}/reset-link",
        headers=auth(admin_token),
        json={"reason": "اختبار سجل التدقيق"},
    )
    token = issued.json()["reset_url"].split("token=")[1]

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.action == "support.user.reset_link")
                .order_by(AuditLog.created_at.desc())
                .limit(5)
            )
        ).scalars().all()

    assert rows, "issuing a link must be audited"
    blob = " ".join(str(r.after_state) + str(r.notes) for r in rows)
    assert token not in blob, "the token leaked into the audit trail"
    assert rows[0].notes, "and the reason must be recorded"


@pytest.mark.asyncio
async def test_support_cannot_reset_another_platform_administrator(
    client, admin_token
):
    listed = await client.get(
        "/admin/users", headers=auth(admin_token), params={"role": "super_admin"}
    )
    peer = next(
        (u for u in listed.json()["items"] if u["email"] != "admin@pharmacy-marketplace.sa"),
        listed.json()["items"][0],
    )
    refused = await client.post(
        f"/admin/users/{peer['id']}/reset-link",
        headers=auth(admin_token),
        json={"reason": "محاولة الوصول لحساب مدير آخر"},
    )
    assert refused.status_code == 403
    assert "مدير المنصة" in refused.json()["detail"]


# ── Enabling and disabling ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deactivating_locks_the_customer_out_immediately(client, admin_token):
    from tests.conftest import SEEDED

    email, password = SEEDED["pharmacist"]
    target = await a_customer_user(client, admin_token, "pharmacist@aldawaa")

    assert (
        await client.post("/auth/login", json={"email": email, "password": password})
    ).status_code == 200

    off = await client.post(
        f"/admin/users/{target['id']}/deactivate",
        headers=auth(admin_token),
        json={"reason": "الموظف غادر الصيدلية"},
    )
    assert off.status_code == 200
    assert off.json()["is_active"] is False

    blocked = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert blocked.status_code == 403, "a disabled account must not sign in"

    on = await client.post(
        f"/admin/users/{target['id']}/activate",
        headers=auth(admin_token),
        json={"reason": "عاد الموظف للعمل"},
    )
    assert on.status_code == 200
    assert (
        await client.post("/auth/login", json={"email": email, "password": password})
    ).status_code == 200


@pytest.mark.asyncio
async def test_support_cannot_disable_or_delete_itself(client, admin_token):
    me = (await client.get("/auth/me", headers=auth(admin_token))).json()

    off = await client.post(
        f"/admin/users/{me['id']}/deactivate",
        headers=auth(admin_token),
        json={"reason": "محاولة تعطيل الذات"},
    )
    assert off.status_code == 403
    assert "حسابك" in off.json()["detail"]

    gone = await client.delete(
        f"/admin/users/{me['id']}",
        headers=auth(admin_token),
        params={"reason": "محاولة حذف الذات"},
    )
    assert gone.status_code == 403


@pytest.mark.asyncio
async def test_deleting_an_account_frees_its_email_for_reuse(client, admin_token):
    """A pharmacist who leaves and returns must be registrable again."""
    from tests.conftest import SEEDED

    admin_email, admin_password = SEEDED["admin"]
    suffix = unique("dep")
    email = f"{suffix}@example.sa"

    created = await client.post(
        "/auth/register",
        json={
            "full_name": "موظف مغادر",
            "email": email,
            "phone": f"+96650{uuid.uuid4().int % 10**7:07d}",
            "password": "Leaver@12345",
            "org_name": f"Leaver Pharmacy {suffix}",
            "org_name_ar": f"صيدلية المغادر {suffix}",
            "commercial_registration_number": f"CR-{suffix}",
            "org_email": f"info-{suffix}@example.sa",
            "org_phone": f"+96611{uuid.uuid4().int % 10**7:07d}",
            "branch_name": "Main",
            "branch_name_ar": "الرئيسي",
        },
    )
    assert created.status_code in (200, 201), created.text

    found = await client.get(
        "/admin/users", headers=auth(admin_token), params={"search": suffix}
    )
    target = found.json()["items"][0]

    deleted = await client.delete(
        f"/admin/users/{target['id']}",
        headers=auth(admin_token),
        params={"reason": "الموظف غادر نهائياً", "force": True},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    # The address is free again — this is what the release is for.
    again = await client.post(
        "/auth/register",
        json={
            "full_name": "موظف عائد",
            "email": email,
            "phone": f"+96650{uuid.uuid4().int % 10**7:07d}",
            "password": "Returner@12345",
            "org_name": f"Returner Pharmacy {suffix}",
            "org_name_ar": f"صيدلية العائد {suffix}",
            "commercial_registration_number": f"CR2-{suffix}",
            "org_email": f"info2-{suffix}@example.sa",
            "org_phone": f"+96611{uuid.uuid4().int % 10**7:07d}",
            "branch_name": "Main",
            "branch_name_ar": "الرئيسي",
        },
    )
    assert again.status_code in (200, 201), (
        f"the released address must be registrable again: {again.text}"
    )
    assert admin_email and admin_password  # the fixture stays untouched


@pytest.mark.asyncio
async def test_deleting_the_last_active_account_needs_intent(client, admin_token):
    suffix = unique("solo")
    await client.post(
        "/auth/register",
        json={
            "full_name": "المالك الوحيد",
            "email": f"{suffix}@example.sa",
            "phone": f"+96650{uuid.uuid4().int % 10**7:07d}",
            "password": "Solo@12345",
            "org_name": f"Solo Pharmacy {suffix}",
            "org_name_ar": f"صيدلية الوحيد {suffix}",
            "commercial_registration_number": f"CR-{suffix}",
            "org_email": f"info-{suffix}@example.sa",
            "org_phone": f"+96611{uuid.uuid4().int % 10**7:07d}",
            "branch_name": "Main",
            "branch_name_ar": "الرئيسي",
        },
    )
    found = await client.get(
        "/admin/users", headers=auth(admin_token), params={"search": suffix}
    )
    target = found.json()["items"][0]

    refused = await client.delete(
        f"/admin/users/{target['id']}",
        headers=auth(admin_token),
        params={"reason": "حذف آخر حساب"},
    )
    assert refused.status_code == 409
    assert "آخر حساب" in refused.json()["detail"]


# ── Organization lifecycle ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_suspended_pharmacy_cannot_sign_in_and_can_be_brought_back(
    client, admin_token
):
    """Regression: suspension used to let staff sign in, browse and bid.

    Uses a pharmacy of its own — suspending a seeded one would strand every
    test that follows if this one failed halfway.
    """
    suffix = unique("susp")
    email = f"{suffix}@example.sa"
    password = "Susp@12345"
    await client.post(
        "/auth/register",
        json={
            "full_name": "مالك المنشأة",
            "email": email,
            "phone": f"+96650{uuid.uuid4().int % 10**7:07d}",
            "password": password,
            "org_name": f"Suspend Pharmacy {suffix}",
            "org_name_ar": f"صيدلية التعليق {suffix}",
            "commercial_registration_number": f"CR-{suffix}",
            "org_email": f"info-{suffix}@example.sa",
            "org_phone": f"+96611{uuid.uuid4().int % 10**7:07d}",
            "branch_name": "Main",
            "branch_name_ar": "الرئيسي",
        },
    )
    found = await client.get(
        "/admin/users", headers=auth(admin_token), params={"search": suffix}
    )
    org_id = found.json()["items"][0]["organization_id"]

    await client.post(
        f"/organizations/{org_id}/approve",
        headers=auth(admin_token),
        json={"notes": "اعتماد للاختبار"},
    )
    assert (
        await client.post("/auth/login", json={"email": email, "password": password})
    ).status_code == 200

    suspended = await client.post(
        f"/organizations/{org_id}/suspend",
        headers=auth(admin_token),
        json={"reason": "مخالفة شروط الاستخدام"},
    )
    assert suspended.status_code == 200

    blocked = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert blocked.status_code == 403, "a suspended pharmacy must not sign in"
    assert "موقوف" in blocked.json()["detail"]

    back = await client.post(
        f"/admin/organizations/{org_id}/reactivate",
        headers=auth(admin_token),
        json={"reason": "عولجت المخالفة"},
    )
    assert back.status_code == 200
    assert back.json()["status"] == "approved"

    assert (
        await client.post("/auth/login", json={"email": email, "password": password})
    ).status_code == 200, "reactivation must restore access"


# ── Marketplace moderation ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_removing_a_listing_works_and_returns_the_stock(client, admin_token):
    """Regression: this endpoint did not exist, so the button returned 404."""
    from database import AsyncSessionLocal
    from models.inventory import BatchStatus, InventoryBatch
    from models.marketplace import ListingStatus, MarketplaceListing

    queue = await client.get(
        "/admin/moderation", headers=auth(admin_token), params={"page_size": 20}
    )
    assert queue.status_code == 200
    listings = queue.json()["items"]
    if not listings:
        pytest.skip("no active listing seeded to moderate")

    listing_id = listings[0]["id"]
    removed = await client.post(
        f"/admin/moderation/{listing_id}/remove",
        headers=auth(admin_token),
        json={"reason": "معلومات مضلّلة في العرض"},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "cancelled"

    async with AsyncSessionLocal() as db:
        listing = (
            await db.execute(
                select(MarketplaceListing).where(
                    MarketplaceListing.id == uuid.UUID(listing_id)
                )
            )
        ).scalar_one()
        assert listing.status == ListingStatus.CANCELLED
        batch = (
            await db.execute(
                select(InventoryBatch).where(InventoryBatch.id == listing.batch_id)
            )
        ).scalar_one()
        assert batch.status != BatchStatus.LISTED, "the stock must be handed back"

    # Removing it twice is a conflict, not a silent success.
    again = await client.post(
        f"/admin/moderation/{listing_id}/remove",
        headers=auth(admin_token),
        json={"reason": "محاولة ثانية"},
    )
    assert again.status_code == 409


# ── Customer inventory ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_support_can_delete_a_batch_and_restore_it(
    client, admin_token, seller_token
):
    from tests.test_inventory_import import (
        a_branch_name,
        build_sheet,
        find_batches,
        upload,
    )

    branch = await a_branch_name(client, seller_token)
    code = unique("DEL")
    await upload(
        client,
        seller_token,
        build_sheet(
            [
                {
                    "product_name": f"دواء للحذف {code}",
                    "sku": code,
                    "batch_number": code,
                    "expiry_date": (date.today() + timedelta(days=120)).isoformat(),
                    "quantity": 12,
                }
            ],
            branch,
        ),
    )
    rows = await find_batches(client, seller_token, code)
    assert len(rows) == 1
    batch_id = rows[0]["id"]

    deleted = await client.delete(
        f"/admin/inventory/batches/{batch_id}",
        headers=auth(admin_token),
        params={"reason": "دخلت بالخطأ في ملف العميل"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    assert await find_batches(client, seller_token, code) == [], "still visible"

    restored = await client.post(
        f"/admin/inventory/batches/{batch_id}/restore",
        headers=auth(admin_token),
        json={"reason": "تبيّن أنها صحيحة"},
    )
    assert restored.status_code == 200
    assert len(await find_batches(client, seller_token, code)) == 1


@pytest.mark.asyncio
async def test_a_batch_under_a_live_listing_is_not_deletable(client, admin_token):
    """Stock a buyer can see must not vanish from under them."""
    from database import AsyncSessionLocal
    from models.marketplace import ListingStatus, MarketplaceListing

    async with AsyncSessionLocal() as db:
        listing = (
            await db.execute(
                select(MarketplaceListing)
                .where(
                    MarketplaceListing.status == ListingStatus.ACTIVE,
                    MarketplaceListing.deleted_at.is_(None),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
    if listing is None:
        pytest.skip("no active listing seeded")

    refused = await client.delete(
        f"/admin/inventory/batches/{listing.batch_id}",
        headers=auth(admin_token),
        params={"reason": "محاولة حذف تشغيلة معروضة"},
    )
    assert refused.status_code == 409
    assert "عرض قائم" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_every_support_action_leaves_a_reason_in_the_audit_trail(
    client, admin_token
):
    from database import AsyncSessionLocal
    from models.audit import AuditLog

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.action.like("support.%"))
                .order_by(AuditLog.created_at.desc())
                .limit(30)
            )
        ).scalars().all()

    assert rows, "support actions must be audited"
    assert all(r.notes for r in rows), "every support action must carry its reason"
    assert all(r.actor_id is not None for r in rows), "and name who did it"
