"""Cold-chain evidence: a refrigerated batch may not ship unproven."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.conftest import auth
from tests.test_marketplace_cycle import _eligible_listing

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"


async def _pending_transaction(client, seller_token, buyer_token, cold: bool):
    """A transaction ready to dispatch, on a batch marked cold-chain or not."""
    listing = await _eligible_listing(client, seller_token, quantity_listed=10)

    from database import AsyncSessionLocal
    from models.inventory import InventoryBatch

    async with AsyncSessionLocal() as db:
        batch = (
            await db.execute(
                select(InventoryBatch).where(InventoryBatch.id == listing["batch_id"])
            )
        ).scalar_one()
        batch.requires_cold_chain = cold
        await db.commit()

    offer = await client.post(
        "/offers",
        headers=auth(buyer_token),
        json={"listing_id": listing["id"], "offered_price": 30.0, "quantity": 4},
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
    return tx


@pytest.mark.asyncio
async def test_cold_batch_cannot_be_dispatched_without_a_log(
    client, seller_token, buyer_token
):
    tx = await _pending_transaction(client, seller_token, buyer_token, cold=True)

    blocked = await client.post(
        f"/transactions/{tx['id']}/dispatch", headers=auth(seller_token), json={}
    )
    assert blocked.status_code == 400
    assert "سلسلة تبريد" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_an_ordinary_batch_still_dispatches_freely(client, seller_token, buyer_token):
    tx = await _pending_transaction(client, seller_token, buyer_token, cold=False)
    response = await client.post(
        f"/transactions/{tx['id']}/dispatch", headers=auth(seller_token), json={}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dispatched"


@pytest.mark.asyncio
async def test_readings_inside_range_clear_the_shipment(client, seller_token, buyer_token):
    tx = await _pending_transaction(client, seller_token, buyer_token, cold=True)

    attached = await client.post(
        f"/transactions/{tx['id']}/temperature-log",
        headers=auth(seller_token),
        files={"file": ("temps.pdf", PDF, "application/pdf")},
        data={"min_temp_c": "3.4", "max_temp_c": "7.1"},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["temperature_excursion"] is False

    dispatched = await client.post(
        f"/transactions/{tx['id']}/dispatch", headers=auth(seller_token), json={}
    )
    assert dispatched.status_code == 200


@pytest.mark.asyncio
async def test_an_excursion_is_recorded_and_visible_to_the_buyer(
    client, seller_token, buyer_token
):
    """Going out of range does not block the shipment — it discloses it, so the
    buyer can refuse at receipt."""
    tx = await _pending_transaction(client, seller_token, buyer_token, cold=True)

    attached = await client.post(
        f"/transactions/{tx['id']}/temperature-log",
        headers=auth(seller_token),
        files={"file": ("temps.pdf", PDF, "application/pdf")},
        data={"min_temp_c": "1.0", "max_temp_c": "11.5"},
    )
    assert attached.json()["temperature_excursion"] is True

    await client.post(f"/transactions/{tx['id']}/dispatch", headers=auth(seller_token), json={})

    seen_by_buyer = await client.get(f"/transactions/{tx['id']}", headers=auth(buyer_token))
    assert seen_by_buyer.json()["temperature_excursion"] is True


@pytest.mark.asyncio
async def test_only_the_seller_attaches_the_log(client, seller_token, buyer_token):
    tx = await _pending_transaction(client, seller_token, buyer_token, cold=True)
    response = await client.post(
        f"/transactions/{tx['id']}/temperature-log",
        headers=auth(buyer_token),
        files={"file": ("temps.pdf", PDF, "application/pdf")},
        data={"min_temp_c": "4", "max_temp_c": "6"},
    )
    assert response.status_code == 403
