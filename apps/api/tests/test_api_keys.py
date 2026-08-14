"""
API keys and the endpoints a customer's own system calls.

The security claims worth testing are: the plaintext key is never stored, a
revoked key stops working immediately, a scope the key lacks is refused, and the
key decides whose data comes back — a customer cannot reach another pharmacy's
stock through it.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import auth, unique


async def issue_key(client, token: str, scopes: list[str], name: str = "تكامل أودو"):
    response = await client.post(
        "/api-keys",
        headers=auth(token),
        json={"name": name, "scopes": scopes},
    )
    assert response.status_code == 201, response.text
    return response.json()


def key_header(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


@pytest.mark.asyncio
async def test_a_key_is_shown_once_and_never_stored(client, seller_token):
    created = await issue_key(client, seller_token, ["inventory:read"])

    plaintext = created["key"]
    assert plaintext.startswith("msk_live_")
    assert created["prefix"] == plaintext[: len(created["prefix"])]
    assert "لن يُعرض مرة أخرى" in created["warning"]

    # Listing keys must never hand the secret back.
    listed = await client.get("/api-keys", headers=auth(seller_token))
    assert listed.status_code == 200
    mine = [k for k in listed.json() if k["id"] == created["id"]]
    assert mine, "the key must appear in the list"
    assert "key" not in mine[0]

    # And the database holds a hash, not the key.
    from database import AsyncSessionLocal
    from models.api_key import ApiKey
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(ApiKey).where(ApiKey.id == uuid.UUID(created["id"])))
        ).scalar_one()
    assert plaintext not in row.key_hash
    assert row.key_hash.startswith("$argon2")


@pytest.mark.asyncio
async def test_the_key_authenticates_and_names_its_pharmacy(client, seller_token):
    created = await issue_key(client, seller_token, ["inventory:read"])
    seller_org = (
        await client.get("/organizations/me", headers=auth(seller_token))
    ).json()["id"]

    health = await client.get("/external/health", headers=key_header(created["key"]))
    assert health.status_code == 200
    assert health.json()["organization_id"] == seller_org
    assert health.json()["scopes"] == ["inventory:read"]


@pytest.mark.asyncio
async def test_no_key_and_a_wrong_key_are_both_refused(client):
    missing = await client.get("/external/health")
    assert missing.status_code == 401

    wrong = await client.get("/external/health", headers=key_header("msk_live_nonsense"))
    assert wrong.status_code == 401

    malformed = await client.get("/external/health", headers=key_header("not-a-key"))
    assert malformed.status_code == 401


@pytest.mark.asyncio
async def test_a_revoked_key_stops_working(client, seller_token):
    created = await issue_key(client, seller_token, ["inventory:read"])
    assert (
        await client.get("/external/health", headers=key_header(created["key"]))
    ).status_code == 200

    revoked = await client.delete(f"/api-keys/{created['id']}", headers=auth(seller_token))
    assert revoked.status_code == 200
    assert revoked.json()["is_active"] is False
    assert revoked.json()["revoked_at"] is not None

    after = await client.get("/external/health", headers=key_header(created["key"]))
    assert after.status_code == 401, "a revoked key must stop working at once"

    # Revoking twice is a conflict, not a silent success.
    again = await client.delete(f"/api-keys/{created['id']}", headers=auth(seller_token))
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_a_key_cannot_exceed_its_scopes(client, seller_token):
    read_only = await issue_key(client, seller_token, ["inventory:read"], "قراءة فقط")

    refused = await client.post(
        "/external/inventory/sync",
        headers=key_header(read_only["key"]),
        json={
            "items": [
                {
                    "product_name": "دواء",
                    "batch_number": "X-1",
                    "expiry_date": (date.today() + timedelta(days=90)).isoformat(),
                    "quantity": 1,
                }
            ]
        },
    )
    assert refused.status_code == 403
    assert "inventory:write" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_an_unknown_scope_is_rejected_at_creation(client, seller_token):
    response = await client.post(
        "/api-keys",
        headers=auth(seller_token),
        json={"name": "مفتاح", "scopes": ["everything:*"]},
    )
    assert response.status_code == 400
    assert "غير معروفة" in response.json()["detail"]


@pytest.mark.asyncio
async def test_stock_sent_through_the_api_lands_in_inventory(client, seller_token):
    from tests.test_inventory_import import a_branch_name, find_batches

    key = await issue_key(
        client, seller_token, ["inventory:read", "inventory:write"], "أودو"
    )
    branch = await a_branch_name(client, seller_token)
    code = unique("API")
    expiry = date.today() + timedelta(days=75)

    def payload(quantity: int) -> dict:
        return {
            "items": [
                {
                    "product_name": f"دواء عبر الواجهة {code}",
                    "sku": code,
                    "batch_number": code,
                    "expiry_date": expiry.isoformat(),
                    "quantity": quantity,
                    "unit_cost": 8.25,
                    "branch_name": branch,
                }
            ]
        }

    first = await client.post(
        "/external/inventory/sync", headers=key_header(key["key"]), json=payload(60)
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["received"] == 1
    assert body["created_batches"] == 1
    assert body["failed"] == 0

    rows = await find_batches(client, seller_token, code)
    assert len(rows) == 1
    assert rows[0]["quantity"] == 60

    # A scheduled sync sends the same item again; it must update, not duplicate.
    second = await client.post(
        "/external/inventory/sync", headers=key_header(key["key"]), json=payload(45)
    )
    assert second.status_code == 200
    assert second.json()["created_batches"] == 0
    assert second.json()["updated_batches"] == 1

    rows = await find_batches(client, seller_token, code)
    assert len(rows) == 1, "a repeated sync must not duplicate stock"
    assert rows[0]["quantity"] == 45


@pytest.mark.asyncio
async def test_a_bad_item_is_reported_by_index_without_losing_the_rest(
    client, seller_token
):
    from tests.test_inventory_import import a_branch_name

    key = await issue_key(client, seller_token, ["inventory:write"], "مزامنة")
    branch = await a_branch_name(client, seller_token)
    code = unique("PART")

    response = await client.post(
        "/external/inventory/sync",
        headers=key_header(key["key"]),
        json={
            "items": [
                {
                    "product_name": f"سليم {code}",
                    "batch_number": f"{code}-1",
                    "expiry_date": (date.today() + timedelta(days=120)).isoformat(),
                    "quantity": 5,
                    "branch_name": branch,
                },
                {
                    "product_name": f"فرع مجهول {code}",
                    "batch_number": f"{code}-2",
                    "expiry_date": (date.today() + timedelta(days=120)).isoformat(),
                    "quantity": 5,
                    "branch_name": "فرع غير موجود",
                },
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created_batches"] == 1
    assert body["failed"] == 1
    assert body["errors"][0]["index"] == 1, "the caller must know which item failed"
    assert "الفرع" in body["errors"][0]["reason"]


@pytest.mark.asyncio
async def test_near_expiry_returns_only_this_pharmacys_stock(
    client, seller_token, buyer_token
):
    from tests.test_inventory_import import a_branch_name

    seller_key = await issue_key(client, seller_token, ["inventory:read", "inventory:write"])
    buyer_key = await issue_key(client, buyer_token, ["inventory:read", "inventory:write"])

    branch = await a_branch_name(client, seller_token)
    code = unique("NE")
    await client.post(
        "/external/inventory/sync",
        headers=key_header(seller_key["key"]),
        json={
            "items": [
                {
                    "product_name": f"قريب الانتهاء {code}",
                    "sku": code,
                    "batch_number": code,
                    "expiry_date": (date.today() + timedelta(days=20)).isoformat(),
                    "quantity": 15,
                    "branch_name": branch,
                }
            ]
        },
    )

    mine = await client.get(
        "/external/inventory/near-expiry", headers=key_header(seller_key["key"])
    )
    assert mine.status_code == 200
    found = [i for i in mine.json()["items"] if i["batch_number"] == code]
    assert found, "the pharmacy must see its own near-expiry stock"
    assert found[0]["zone"] == "red", "twenty days out is the red band"
    assert 0 < found[0]["days_remaining"] <= 20

    # The other pharmacy's key must not reach it.
    theirs = await client.get(
        "/external/inventory/near-expiry",
        headers=key_header(buyer_key["key"]),
        params={"limit": 1000},
    )
    assert theirs.status_code == 200
    assert not [i for i in theirs.json()["items"] if i["batch_number"] == code], (
        "another pharmacy's stock leaked through the API"
    )


@pytest.mark.asyncio
async def test_a_key_belongs_to_one_pharmacy_only(client, seller_token, buyer_token):
    """A key issued by one pharmacy cannot be managed by another."""
    created = await issue_key(client, seller_token, ["inventory:read"])

    theirs = await client.get("/api-keys", headers=auth(buyer_token))
    assert created["id"] not in {k["id"] for k in theirs.json()}

    stolen = await client.delete(f"/api-keys/{created['id']}", headers=auth(buyer_token))
    assert stolen.status_code == 404, "the id must not confirm the key exists"


@pytest.mark.asyncio
async def test_using_a_key_records_when_it_was_last_used(client, seller_token):
    created = await issue_key(client, seller_token, ["inventory:read"])
    assert created["last_used_at"] is None
    assert created["request_count"] == 0

    await client.get("/external/health", headers=key_header(created["key"]))
    await client.get("/external/health", headers=key_header(created["key"]))

    listed = await client.get("/api-keys", headers=auth(seller_token))
    row = next(k for k in listed.json() if k["id"] == created["id"])
    assert row["last_used_at"] is not None
    assert row["request_count"] >= 2


@pytest.mark.asyncio
async def test_the_available_scopes_are_described_in_arabic(client, seller_token):
    response = await client.get("/api-keys/scopes", headers=auth(seller_token))
    assert response.status_code == 200
    values = {s["value"] for s in response.json()}
    assert values == {"inventory:read", "inventory:write", "listings:read"}
    assert all(s["label_ar"] and s["description_ar"] for s in response.json())


@pytest.mark.asyncio
async def test_listings_read_returns_only_this_pharmacys_listings(
    client, seller_token, buyer_token
):
    seller_key = await issue_key(client, seller_token, ["listings:read"])
    buyer_key = await issue_key(client, buyer_token, ["listings:read"])

    mine = await client.get("/external/listings", headers=key_header(seller_key["key"]))
    assert mine.status_code == 200

    seller_org = (
        await client.get("/organizations/me", headers=auth(seller_token))
    ).json()["id"]
    listed = await client.get(
        "/my/listings", headers=auth(seller_token), params={"page_size": 100}
    )
    if listed.status_code == 200 and listed.json().get("items"):
        expected = {item["id"] for item in listed.json()["items"]}
        assert {item["listing_id"] for item in mine.json()["items"]} <= expected

    theirs = await client.get("/external/listings", headers=key_header(buyer_key["key"]))
    assert theirs.status_code == 200
    assert not (
        {i["listing_id"] for i in mine.json()["items"]}
        & {i["listing_id"] for i in theirs.json()["items"]}
    ), "listings crossed between pharmacies"
    assert seller_org  # the seller org resolved


@pytest.mark.asyncio
async def test_a_key_without_listings_scope_cannot_read_them(client, seller_token):
    key = await issue_key(client, seller_token, ["inventory:read"], "بلا عروض")
    refused = await client.get("/external/listings", headers=key_header(key["key"]))
    assert refused.status_code == 403
