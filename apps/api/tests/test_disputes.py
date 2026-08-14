"""Returns and disputes: raising a case, answering it, and what a refund moves."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.conftest import auth
from tests.test_marketplace_cycle import _eligible_listing


async def _completed_transaction(client, seller_token, buyer_token, quantity: int = 6):
    """Drive a listing all the way to a completed sale and return the transaction."""
    listing = await _eligible_listing(client, seller_token, quantity_listed=20)
    offer = await client.post(
        "/offers",
        headers=auth(buyer_token),
        json={"listing_id": listing["id"], "offered_price": 25.0, "quantity": quantity},
    )
    offer_id = offer.json()["id"]
    await client.post(f"/offers/{offer_id}/accept", headers=auth(seller_token))
    reservations = await client.get(
        "/reservations", headers=auth(buyer_token), params={"page_size": 100}
    )
    reservation = next(r for r in reservations.json()["items"] if r["offer_id"] == offer_id)
    tx = (
        await client.post(
            f"/transactions/from-reservation/{reservation['id']}", headers=auth(buyer_token)
        )
    ).json()
    await client.post(f"/transactions/{tx['id']}/dispatch", headers=auth(seller_token), json={})
    await client.post(
        f"/transactions/{tx['id']}/confirm-receipt", headers=auth(buyer_token), json={}
    )
    return tx, listing


@pytest.mark.asyncio
async def test_buyer_opens_a_dispute_and_seller_answers(client, seller_token, buyer_token):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)

    opened = await client.post(
        "/disputes",
        headers=auth(buyer_token),
        json={
            "transaction_id": tx["id"],
            "reason": "quantity_short",
            "description": "وصلت الشحنة ناقصة وحدتين عن الكمية المتفق عليها",
            "disputed_quantity": 2,
        },
    )
    assert opened.status_code == 201, opened.text
    dispute = opened.json()
    assert dispute["status"] == "open"

    detail = await client.get(f"/transactions/{tx['id']}", headers=auth(buyer_token))
    assert detail.json()["status"] == "disputed"

    answered = await client.post(
        f"/disputes/{dispute['id']}/respond",
        headers=auth(seller_token),
        json={"response": "شحنت الكمية كاملة، وسنراجع مع شركة الشحن"},
    )
    assert answered.status_code == 200
    assert answered.json()["status"] == "seller_responded"


@pytest.mark.asyncio
async def test_the_side_that_raised_it_cannot_answer_itself(client, seller_token, buyer_token):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)
    dispute = (
        await client.post(
            "/disputes",
            headers=auth(buyer_token),
            json={
                "transaction_id": tx["id"],
                "reason": "damaged",
                "description": "العبوات وصلت متضررة من الأطراف",
            },
        )
    ).json()

    response = await client.post(
        f"/disputes/{dispute['id']}/respond",
        headers=auth(buyer_token),
        json={"response": "محاولة رد من نفس الطرف"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_only_one_open_case_per_transaction(client, seller_token, buyer_token):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)
    body = {
        "transaction_id": tx["id"],
        "reason": "other",
        "description": "أول بلاغ على هذه المعاملة",
    }
    assert (await client.post("/disputes", headers=auth(buyer_token), json=body)).status_code == 201
    second = await client.post("/disputes", headers=auth(buyer_token), json=body)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_refund_returns_the_disputed_units_to_the_seller(
    client, seller_token, buyer_token, admin_token
):
    tx, listing = await _completed_transaction(client, seller_token, buyer_token, quantity=6)
    batch_id = listing["batch_id"]

    from database import AsyncSessionLocal
    from models.inventory import InventoryBatch

    async with AsyncSessionLocal() as db:
        before = (
            await db.execute(select(InventoryBatch).where(InventoryBatch.id == batch_id))
        ).scalar_one().quantity_available

    dispute = (
        await client.post(
            "/disputes",
            headers=auth(buyer_token),
            json={
                "transaction_id": tx["id"],
                "reason": "quantity_short",
                "description": "نقص وحدتين في الشحنة الواصلة",
                "disputed_quantity": 2,
            },
        )
    ).json()

    resolved = await client.post(
        f"/disputes/{dispute['id']}/resolve",
        headers=auth(admin_token),
        json={"outcome": "resolved_refund", "notes": "قبل البلاغ بعد مراجعة الأدلة"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["refund_amount"] == pytest.approx(50.0)  # 2 units × 25.0

    async with AsyncSessionLocal() as db:
        batch = (
            await db.execute(select(InventoryBatch).where(InventoryBatch.id == batch_id))
        ).scalar_one()
        assert batch.quantity_available == before + 2, "refunded units were not returned"

        from models.inventory import InventoryMovement

        movement = (
            await db.execute(
                select(InventoryMovement)
                .where(InventoryMovement.reference_type == "dispute_refund")
                .order_by(InventoryMovement.created_at.desc())
            )
        ).scalars().first()
        assert movement is not None and movement.quantity_delta == 2


@pytest.mark.asyncio
async def test_a_rejected_case_leaves_the_sale_standing(
    client, seller_token, buyer_token, admin_token
):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)
    dispute = (
        await client.post(
            "/disputes",
            headers=auth(buyer_token),
            json={
                "transaction_id": tx["id"],
                "reason": "wrong_product",
                "description": "المنتج الواصل مختلف عما في العرض",
            },
        )
    ).json()

    await client.post(
        f"/disputes/{dispute['id']}/resolve",
        headers=auth(admin_token),
        json={"outcome": "resolved_rejected", "notes": "الأدلة لا تدعم البلاغ"},
    )
    detail = await client.get(f"/transactions/{tx['id']}", headers=auth(buyer_token))
    assert detail.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_a_counterfeit_report_suspends_the_seller(client, seller_token, buyer_token):
    """A counterfeit claim is escalated immediately rather than awaiting a decision."""
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)

    from database import AsyncSessionLocal
    from models.organization import PharmacyOrganization

    seller_org_id = tx["seller_organization_id"]
    async with AsyncSessionLocal() as db:
        org = (
            await db.execute(
                select(PharmacyOrganization).where(PharmacyOrganization.id == seller_org_id)
            )
        ).scalar_one()
        org.status = "approved"
        await db.commit()

    opened = await client.post(
        "/disputes",
        headers=auth(buyer_token),
        json={
            "transaction_id": tx["id"],
            "reason": "suspected_counterfeit",
            "description": "الطباعة على العبوة مختلفة والرقم التشغيلي غير مطابق",
        },
    )
    assert opened.status_code == 201, opened.text

    async with AsyncSessionLocal() as db:
        org = (
            await db.execute(
                select(PharmacyOrganization).where(PharmacyOrganization.id == seller_org_id)
            )
        ).scalar_one()
        assert org.status == "suspended", "a counterfeit report must suspend the seller"

    # Leave the fixture data usable for other tests.
    async with AsyncSessionLocal() as db:
        org = (
            await db.execute(
                select(PharmacyOrganization).where(PharmacyOrganization.id == seller_org_id)
            )
        ).scalar_one()
        org.status = "approved"
        org.suspension_reason = None
        await db.commit()


@pytest.mark.asyncio
async def test_only_platform_admins_resolve(client, seller_token, buyer_token):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)
    dispute = (
        await client.post(
            "/disputes",
            headers=auth(buyer_token),
            json={
                "transaction_id": tx["id"],
                "reason": "not_received",
                "description": "لم تصل الشحنة حتى الآن رغم مرور المدة",
            },
        )
    ).json()

    response = await client.post(
        f"/disputes/{dispute['id']}/resolve",
        headers=auth(seller_token),
        json={"outcome": "resolved_rejected", "notes": "محاولة حسم من طرف غير مخول"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_queue_lists_unresolved_cases(client, seller_token, buyer_token, admin_token):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)
    await client.post(
        "/disputes",
        headers=auth(buyer_token),
        json={
            "transaction_id": tx["id"],
            "reason": "expiry_mismatch",
            "description": "تاريخ الانتهاء على العبوة أقصر مما في العرض",
        },
    )
    queue = await client.get("/disputes/queue", headers=auth(admin_token))
    assert queue.status_code == 200
    assert queue.json()["total"] >= 1
