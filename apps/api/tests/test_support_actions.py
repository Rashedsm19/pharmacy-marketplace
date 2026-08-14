"""
Acting for a customer: importing on their behalf, entering their account, and
deleting a pharmacy for good.

These are the most powerful things in the product, so most of what is asserted
here is what they refuse to do.
"""
from __future__ import annotations

import io
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from tests.conftest import auth, unique
from tests.test_inventory_import import (
    a_branch_name,
    build_sheet,
    find_batches,
    run_pending_imports,
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _register(client, prefix: str) -> dict:
    suffix = unique(prefix)
    payload = {
        "full_name": "مالك المنشأة",
        "email": f"{suffix}@example.sa",
        "phone": f"+96650{uuid.uuid4().int % 10**7:07d}",
        "password": "Owner@12345",
        "org_name": f"Pharmacy {suffix}",
        "org_name_ar": f"صيدلية {suffix}",
        "commercial_registration_number": f"CR-{suffix}",
        "org_email": f"info-{suffix}@example.sa",
        "org_phone": f"+96611{uuid.uuid4().int % 10**7:07d}",
        "branch_name": "Main",
        "branch_name_ar": "الفرع الرئيسي",
    }
    created = await client.post("/auth/register", json=payload)
    assert created.status_code in (200, 201), created.text
    payload["suffix"] = suffix
    return payload


async def _find(client, admin_token, suffix: str) -> dict:
    found = await client.get(
        "/admin/users", headers=auth(admin_token), params={"search": suffix}
    )
    assert found.json()["items"], f"no account for {suffix}"
    return found.json()["items"][0]


# ── Importing on a customer's behalf ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_support_imports_into_the_right_pharmacy(
    client, admin_token, seller_token, buyer_token
):
    """The stock must land in the customer's account and nowhere else."""
    buyer_org = (
        await client.get("/organizations/me", headers=auth(buyer_token))
    ).json()["id"]
    branch = await a_branch_name(client, buyer_token)
    code = unique("BEHALF")

    sheet = build_sheet(
        [
            {
                "product_name": f"دواء رفعه الدعم {code}",
                "sku": code,
                "batch_number": code,
                "expiry_date": (date.today() + timedelta(days=140)).isoformat(),
                "quantity": 21,
            }
        ],
        branch,
    )

    queued = await client.post(
        f"/admin/organizations/{buyer_org}/imports",
        headers=auth(admin_token),
        params={"reason": "العميل أرسل الملف على الواتساب وطلب رفعه"},
        files={"file": (f"{code}.xlsx", sheet, XLSX)},
    )
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["id"]
    await run_pending_imports()

    landed = await find_batches(client, buyer_token, code)
    assert len(landed) == 1, "the stock must be in the customer's inventory"
    assert landed[0]["quantity"] == 21

    # And not in anyone else's.
    assert await find_batches(client, seller_token, code) == [], "it went to the wrong pharmacy"

    # /admin/imports attributes it to whoever really ran it.
    listed = await client.get(
        "/admin/imports", headers=auth(admin_token), params={"page_size": 50}
    )
    row = next(r for r in listed.json()["items"] if r["id"] == job_id)
    assert row["organization_id"] == buyer_org
    assert row["created_by_name"], "the support user must be named"


@pytest.mark.asyncio
async def test_the_customer_is_told_support_touched_their_stock(
    client, admin_token, buyer_token
):
    """Silently rewriting a pharmacy's quantities is not acceptable."""
    notifications = await client.get(
        "/notifications", headers=auth(buyer_token), params={"page_size": 20}
    )
    assert notifications.status_code == 200
    bodies = " ".join(
        (n.get("body_ar") or "") + (n.get("title_ar") or "")
        for n in notifications.json().get("items", [])
    )
    assert "الدعم" in bodies, "the customer was never told"


@pytest.mark.asyncio
async def test_importing_for_a_pharmacy_with_no_branch_is_refused(
    client, admin_token
):
    """Refuse up front rather than queue a job that is certain to fail."""
    from database import AsyncSessionLocal
    from models.branch import PharmacyBranch

    registered = await _register(client, "nobr")
    account = await _find(client, admin_token, registered["suffix"])
    org_id = account["organization_id"]

    async with AsyncSessionLocal() as db:
        branches = (
            await db.execute(
                select(PharmacyBranch).where(
                    PharmacyBranch.organization_id == uuid.UUID(org_id)
                )
            )
        ).scalars().all()
        for branch in branches:
            branch.deleted_at = date.today()
        await db.commit()

    refused = await client.post(
        f"/admin/organizations/{org_id}/imports",
        headers=auth(admin_token),
        params={"reason": "محاولة رفع بلا فرع"},
        files={"file": ("x.xlsx", build_sheet([], "أي فرع"), XLSX)},
    )
    assert refused.status_code == 409
    assert "فرع" in refused.json()["detail"]


# ── Viewing as a customer ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_support_can_work_inside_a_customer_account(
    client, admin_token, buyer_token
):
    target = await _find(client, admin_token, "nahdi-demo")

    opened = await client.post(
        f"/admin/users/{target['id']}/impersonate",
        headers=auth(admin_token),
        json={"reason": "العميل يقول إن شاشة المخزون لا تفتح لديه", "minutes": 15},
    )
    assert opened.status_code == 200, opened.text
    session = opened.json()
    assert session["organization_name"]
    assert "تتصفّح حساب" in session["notice"]

    # The session behaves exactly like the customer's own.
    as_customer = session["access_token"]
    me = await client.get("/auth/me", headers=auth(as_customer))
    assert me.status_code == 200
    assert me.json()["email"] == target["email"]

    stock = await client.get("/inventory/batches", headers=auth(as_customer))
    assert stock.status_code == 200, "support must see what the customer sees"

    # Ending it kills the token on its next use.
    ended = await client.post(
        f"/admin/impersonation/{session['session_id']}/end", headers=auth(admin_token)
    )
    assert ended.status_code == 200
    dead = await client.get("/auth/me", headers=auth(as_customer))
    assert dead.status_code == 401, "an ended session must stop working"


@pytest.mark.asyncio
async def test_an_impersonated_action_names_the_administrator(client, admin_token):
    """The audit trail must not read as if the customer did it alone."""
    from database import AsyncSessionLocal
    from models.audit import AuditLog

    target = await _find(client, admin_token, "manager@aldawaa")
    opened = await client.post(
        f"/admin/users/{target['id']}/impersonate",
        headers=auth(admin_token),
        json={"reason": "تشخيص مشكلة في إنشاء العروض لدى العميل", "minutes": 10},
    )
    token = opened.json()["access_token"]

    # Any audited action taken inside the session.
    await client.patch(
        "/organizations/me",
        headers=auth(token),
        json={"notes": "تعديل أثناء جلسة دعم"},
    )

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.action == "organization_updated")
                .order_by(AuditLog.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    assert row is not None
    assert row.notes and "نفّذه الدعم" in row.notes, (
        "an impersonated action must record the administrator behind it"
    )

    await client.post(
        f"/admin/impersonation/{opened.json()['session_id']}/end",
        headers=auth(admin_token),
    )


@pytest.mark.asyncio
async def test_support_cannot_impersonate_a_platform_administrator(
    client, admin_token
):
    listed = await client.get(
        "/admin/users", headers=auth(admin_token), params={"role": "super_admin"}
    )
    peer = listed.json()["items"][0]
    refused = await client.post(
        f"/admin/users/{peer['id']}/impersonate",
        headers=auth(admin_token),
        json={"reason": "محاولة انتحال حساب مدير منصة آخر"},
    )
    assert refused.status_code == 403


@pytest.mark.asyncio
async def test_an_impersonated_session_cannot_mint_an_api_key(client, admin_token):
    """A key outlives the session, so it would turn a look into permanent access."""
    target = await _find(client, admin_token, "manager@aldawaa")
    opened = await client.post(
        f"/admin/users/{target['id']}/impersonate",
        headers=auth(admin_token),
        json={"reason": "التحقق من منع إنشاء المفاتيح أثناء التصفّح"},
    )
    token = opened.json()["access_token"]

    refused = await client.post(
        "/api-keys",
        headers=auth(token),
        json={"name": "مفتاح أثناء الانتحال", "scopes": ["inventory:read"]},
    )
    assert refused.status_code == 403
    assert "حساب عميل" in refused.json()["detail"]

    await client.post(
        f"/admin/impersonation/{opened.json()['session_id']}/end",
        headers=auth(admin_token),
    )


@pytest.mark.asyncio
async def test_sessions_are_listed_for_review(client, admin_token):
    sessions = await client.get(
        "/admin/impersonation/sessions", headers=auth(admin_token)
    )
    assert sessions.status_code == 200
    assert sessions.json(), "opened sessions must be reviewable"
    assert all(s["reason"] for s in sessions.json()), "each must carry its reason"


# ── The customer dashboard ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_dashboard_summarises_every_customer(client, admin_token):
    response = await client.get(
        "/admin/customers", headers=auth(admin_token), params={"page_size": 50}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2

    row = next(r for r in body["items"] if r["batches"] > 0)
    assert row["users"] >= 1
    assert row["branches"] >= 1
    assert row["name"] and row["status"]


@pytest.mark.asyncio
async def test_the_detail_page_holds_everything_about_one_customer(
    client, admin_token, seller_token
):
    org_id = (
        await client.get("/organizations/me", headers=auth(seller_token))
    ).json()["id"]

    detail = await client.get(f"/admin/customers/{org_id}", headers=auth(admin_token))
    assert detail.status_code == 200, detail.text
    body = detail.json()

    assert body["organization"]["commercial_registration_number"]
    assert body["users"], "its people"
    assert body["branches"], "its branches"
    assert set(body["inventory_by_zone"]) == {
        "expired", "red", "orange", "yellow", "green"
    }
    assert isinstance(body["recent_imports"], list)
    # Secrets never appear, even to the platform.
    assert all("key_hash" not in k for k in body["api_keys"])


@pytest.mark.asyncio
async def test_a_pharmacy_cannot_read_the_customer_dashboard(client, seller_token):
    for path in ("/admin/customers", "/admin/impersonation/sessions"):
        assert (
            await client.get(path, headers=auth(seller_token))
        ).status_code == 403, path


# ── Permanent deletion ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_pharmacy_that_has_traded_cannot_be_purged(client, admin_token):
    """Its invoices are chained to another pharmacy's records."""
    from database import AsyncSessionLocal
    from models.transaction import Transaction

    async with AsyncSessionLocal() as db:
        deal = (
            await db.execute(select(Transaction).limit(1))
        ).scalar_one_or_none()
    if deal is None:
        pytest.skip("no seeded transaction")

    org_id = str(deal.seller_organization_id)
    organization = (
        await client.get(f"/admin/customers/{org_id}", headers=auth(admin_token))
    ).json()["organization"]

    await client.post(
        f"/organizations/{org_id}/suspend",
        headers=auth(admin_token),
        json={"reason": "تحضير للاختبار"},
    )
    refused = await client.request(
        "DELETE",
        f"/admin/organizations/{org_id}",
        headers=auth(admin_token),
        json={
            "confirm_name": organization["name_ar"] or organization["name"],
            "reason": "محاولة حذف منشأة لها صفقات",
        },
    )
    assert refused.status_code == 409
    assert "صفقة" in refused.json()["detail"]

    await client.post(
        f"/admin/organizations/{org_id}/reactivate",
        headers=auth(admin_token),
        json={"reason": "إعادة بعد الاختبار"},
    )


@pytest.mark.asyncio
async def test_a_live_pharmacy_must_be_suspended_before_deletion(
    client, admin_token
):
    registered = await _register(client, "live")
    account = await _find(client, admin_token, registered["suffix"])
    org_id = account["organization_id"]
    await client.post(
        f"/organizations/{org_id}/approve",
        headers=auth(admin_token),
        json={"notes": "اعتماد"},
    )

    refused = await client.request(
        "DELETE",
        f"/admin/organizations/{org_id}",
        headers=auth(admin_token),
        json={
            "confirm_name": f"صيدلية {registered['suffix']}",
            "reason": "محاولة حذف منشأة عاملة",
        },
    )
    assert refused.status_code == 409
    assert "أوقف المنشأة أولاً" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_the_name_must_be_typed_exactly(client, admin_token):
    registered = await _register(client, "name")
    account = await _find(client, admin_token, registered["suffix"])
    org_id = account["organization_id"]

    refused = await client.request(
        "DELETE",
        f"/admin/organizations/{org_id}",
        headers=auth(admin_token),
        json={"confirm_name": "اسم خاطئ", "reason": "اسم غير مطابق"},
    )
    assert refused.status_code == 400
    assert "لا يطابق" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_a_pharmacy_with_no_history_is_deleted_and_leaves_a_trace(
    client, admin_token
):
    from database import AsyncSessionLocal
    from models.audit import AuditLog
    from models.organization import PharmacyOrganization

    registered = await _register(client, "purge")
    account = await _find(client, admin_token, registered["suffix"])
    org_id = account["organization_id"]
    name = f"صيدلية {registered['suffix']}"

    purged = await client.request(
        "DELETE",
        f"/admin/organizations/{org_id}",
        headers=auth(admin_token),
        json={"confirm_name": name, "reason": "تسجيل مكرر من نفس العميل"},
    )
    assert purged.status_code == 200, purged.text
    body = purged.json()
    assert body["deleted"].get("pharmacy_organizations") == 1
    assert body["deleted"].get("users") == 1

    async with AsyncSessionLocal() as db:
        gone = await db.get(PharmacyOrganization, uuid.UUID(org_id))
        assert gone is None, "the pharmacy must be gone"

        trace = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.id == uuid.UUID(body["audit_log_id"])
                )
            )
        ).scalar_one()
        assert trace.before_state["name_ar"] == name, "the record must survive"
        assert trace.notes

    # And the account is really gone.
    assert (
        await client.post(
            "/auth/login",
            json={"email": registered["email"], "password": registered["password"]},
        )
    ).status_code in (401, 403)


@pytest.mark.asyncio
async def test_a_pharmacy_cannot_delete_anything(client, seller_token):
    assert (
        await client.request(
            "DELETE",
            f"/admin/organizations/{uuid.uuid4()}",
            headers=auth(seller_token),
            json={"confirm_name": "x", "reason": "محاولة غير مصرّح بها"},
        )
    ).status_code == 403
    assert io  # imported for the sheet helpers above
