"""The trading cycle end to end, plus the tenant boundaries that protect it."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.conftest import auth


async def _eligible_listing(client, seller_token, **overrides):
    """Publish a listing from the first batch that passes all ten rules."""
    branches = (await client.get("/branches", headers=auth(seller_token))).json()["items"]
    batches = (
        await client.get(
            "/inventory/near-expiry", headers=auth(seller_token), params={"days": 180}
        )
    ).json()

    for batch in batches:
        result = await client.get(
            "/listings/eligibility-check",
            headers=auth(seller_token),
            params={"batch_id": batch["id"]},
        )
        if not result.json()["all_passed"]:
            continue
        payload = {
            "batch_id": batch["id"],
            "seller_branch_id": batch.get("branch_id") or branches[0]["id"],
            "title": "Cycle test lot",
            "title_ar": "دفعة اختبار",
            "quantity_listed": 10,
            "asking_price": 45.0,
            "minimum_offer_price": 10.0,
            "allow_offers": True,
            "allow_partial_purchase": True,
            "min_purchase_quantity": 1,
        }
        payload.update(overrides)
        created = await client.post("/listings", headers=auth(seller_token), json=payload)
        if created.status_code == 201:
            return created.json()
    pytest.skip("no eligible batch available in the seeded data")


@pytest.mark.asyncio
async def test_full_trading_cycle(client, seller_token, buyer_token):
    listing = await _eligible_listing(client, seller_token)
    listing_id = listing["id"]

    market = await client.get("/listings", headers=auth(buyer_token), params={"page_size": 50})
    assert listing_id in {item["id"] for item in market.json()["items"]}

    offer = await client.post(
        "/offers",
        headers=auth(buyer_token),
        json={"listing_id": listing_id, "offered_price": 38.0, "quantity": 5},
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]

    incoming = await client.get("/offers/incoming", headers=auth(seller_token))
    assert offer_id in {item["id"] for item in incoming.json()["items"]}

    accepted = await client.post(f"/offers/{offer_id}/accept", headers=auth(seller_token))
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    reservations = await client.get(
        "/reservations", headers=auth(buyer_token), params={"page_size": 100}
    )
    reservation = next(
        r for r in reservations.json()["items"] if r["offer_id"] == offer_id
    )
    assert reservation["status"] == "active"

    tx = await client.post(
        f"/transactions/from-reservation/{reservation['id']}", headers=auth(buyer_token)
    )
    assert tx.status_code == 201, tx.text
    tx_id = tx.json()["id"]

    dispatched = await client.post(
        f"/transactions/{tx_id}/dispatch",
        headers=auth(seller_token),
        json={"delivery_tracking_number": "SMSA-TEST-1", "seller_notes": "شحنت"},
    )
    assert dispatched.json()["status"] == "dispatched"

    completed = await client.post(
        f"/transactions/{tx_id}/confirm-receipt",
        headers=auth(buyer_token),
        json={"buyer_notes": "استلمت"},
    )
    assert completed.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_partial_sale_keeps_the_rest_of_the_stock_visible(client, seller_token, buyer_token):
    """Regression: the batch used to be marked sold outright, hiding what remained."""
    listing = await _eligible_listing(client, seller_token, quantity_listed=20)
    listing_id, batch_id = listing["id"], listing["batch_id"]

    from database import AsyncSessionLocal
    from models.inventory import InventoryBatch

    async with AsyncSessionLocal() as db:
        before = (
            await db.execute(select(InventoryBatch).where(InventoryBatch.id == batch_id))
        ).scalar_one().quantity_available

    offer = await client.post(
        "/offers",
        headers=auth(buyer_token),
        json={"listing_id": listing_id, "offered_price": 25.0, "quantity": 6},
    )
    offer_id = offer.json()["id"]
    await client.post(f"/offers/{offer_id}/accept", headers=auth(seller_token))
    reservations = await client.get(
        "/reservations", headers=auth(buyer_token), params={"page_size": 100}
    )
    reservation = next(r for r in reservations.json()["items"] if r["offer_id"] == offer_id)
    tx = await client.post(
        f"/transactions/from-reservation/{reservation['id']}", headers=auth(buyer_token)
    )
    tx_id = tx.json()["id"]
    await client.post(f"/transactions/{tx_id}/dispatch", headers=auth(seller_token), json={})
    await client.post(f"/transactions/{tx_id}/confirm-receipt", headers=auth(buyer_token), json={})

    after = await client.get(f"/listings/{listing_id}", headers=auth(seller_token))
    assert after.json()["quantity_available"] == 14
    assert after.json()["status"] == "active", "a partly sold lot must stay on the market"

    async with AsyncSessionLocal() as db:
        batch = (
            await db.execute(select(InventoryBatch).where(InventoryBatch.id == batch_id))
        ).scalar_one()
        assert batch.quantity_available == before - 6
        assert batch.status != "sold", "stock remains, so the batch is not sold"


@pytest.mark.asyncio
async def test_incoming_offers_are_scoped_to_the_organisation(client, buyer_token):
    """Regression: this endpoint used to return every offer on the platform."""
    response = await client.get("/offers/incoming", headers=auth(buyer_token))
    assert response.status_code == 200
    # The buyer organization owns no listings, so it must see no incoming offers.
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_no_split_listing_rejects_a_partial_offer(client, seller_token, buyer_token):
    listing = await _eligible_listing(
        client,
        seller_token,
        quantity_listed=20,
        allow_partial_purchase=False,
        min_purchase_quantity=5,
    )
    response = await client.post(
        "/offers",
        headers=auth(buyer_token),
        json={"listing_id": listing["id"], "offered_price": 20.0, "quantity": 6},
    )
    assert response.status_code == 400
    assert "التجزئة" in response.json()["detail"]


@pytest.mark.asyncio
async def test_role_and_auth_boundaries(client, seller_token):
    assert (await client.get("/listings")).status_code == 401
    assert (await client.get("/admin/approvals", headers=auth(seller_token))).status_code == 403
    assert (await client.get("/admin/audit-logs", headers=auth(seller_token))).status_code == 403


@pytest.mark.asyncio
async def test_lists_are_ordered_newest_first(client, admin_token):
    """Regression: pagination had no ORDER BY, so rows repeated or vanished."""
    response = await client.get(
        "/admin/audit-logs", headers=auth(admin_token), params={"page_size": 10}
    )
    stamps = [item["created_at"] for item in response.json()["items"]]
    assert stamps == sorted(stamps, reverse=True)
