"""Ratings: earned by a completed trade, one per party, averaged per organization."""
from __future__ import annotations

import pytest

from tests.conftest import auth
from tests.test_disputes import _completed_transaction
from tests.test_marketplace_cycle import _eligible_listing


@pytest.mark.asyncio
async def test_both_sides_can_rate_a_completed_trade(client, seller_token, buyer_token):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)

    from_buyer = await client.post(
        "/ratings",
        headers=auth(buyer_token),
        json={"transaction_id": tx["id"], "score": 5, "comment": "وصلت الشحنة سليمة وفي وقتها"},
    )
    assert from_buyer.status_code == 201, from_buyer.text
    assert from_buyer.json()["rated_organization_id"] == tx["seller_organization_id"]

    from_seller = await client.post(
        "/ratings",
        headers=auth(seller_token),
        json={"transaction_id": tx["id"], "score": 4},
    )
    assert from_seller.status_code == 201
    assert from_seller.json()["rated_organization_id"] == tx["buyer_organization_id"]


@pytest.mark.asyncio
async def test_the_same_party_cannot_rate_twice(client, seller_token, buyer_token):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)
    body = {"transaction_id": tx["id"], "score": 5}

    assert (await client.post("/ratings", headers=auth(buyer_token), json=body)).status_code == 201
    second = await client.post("/ratings", headers=auth(buyer_token), json=body)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_rating_before_completion_is_refused(client, seller_token, buyer_token):
    """Nothing to judge until the goods have actually arrived."""
    listing = await _eligible_listing(client, seller_token, quantity_listed=10)
    offer = await client.post(
        "/offers",
        headers=auth(buyer_token),
        json={"listing_id": listing["id"], "offered_price": 30.0, "quantity": 3},
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

    response = await client.post(
        "/ratings", headers=auth(buyer_token), json={"transaction_id": tx["id"], "score": 5}
    )
    assert response.status_code == 400
    assert "قبل إتمام" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_stranger_to_the_trade_cannot_rate(client, seller_token, buyer_token, admin_token):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)
    response = await client.post(
        "/ratings", headers=auth(admin_token), json={"transaction_id": tx["id"], "score": 1}
    )
    # The platform admin belongs to no organization, so it is not a party.
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [0, 6, -1])
async def test_scores_outside_one_to_five_are_rejected(
    client, seller_token, buyer_token, score
):
    tx, _ = await _completed_transaction(client, seller_token, buyer_token)
    response = await client.post(
        "/ratings", headers=auth(buyer_token), json={"transaction_id": tx["id"], "score": score}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_average_reflects_what_was_left(client, seller_token, buyer_token):
    first, _ = await _completed_transaction(client, seller_token, buyer_token)
    second, _ = await _completed_transaction(client, seller_token, buyer_token)
    seller_org_id = first["seller_organization_id"]

    before = (
        await client.get(f"/ratings/organization/{seller_org_id}", headers=auth(buyer_token))
    ).json()

    await client.post(
        "/ratings", headers=auth(buyer_token), json={"transaction_id": first["id"], "score": 5}
    )
    await client.post(
        "/ratings", headers=auth(buyer_token), json={"transaction_id": second["id"], "score": 3}
    )

    after = (
        await client.get(f"/ratings/organization/{seller_org_id}", headers=auth(buyer_token))
    ).json()
    assert after["count"] == before["count"] + 2
    assert after["average"] is not None

    listed = await client.get(
        f"/ratings/organization/{seller_org_id}/list", headers=auth(buyer_token)
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 2
