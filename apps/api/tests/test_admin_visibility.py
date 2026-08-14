"""
The platform admin sees everything; a pharmacy sees only itself.

This is the pair of claims the whole ownership design rests on, so both halves
are asserted against the same data: one pharmacy imports stock, and the test
checks that the other pharmacy cannot reach it through any route while the admin
can see it through all of them.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import auth, unique
from tests.test_inventory_import import a_branch_name, build_sheet, upload


@pytest.mark.asyncio
async def test_the_admin_sees_stock_from_every_pharmacy(
    client, seller_token, buyer_token, admin_token
):
    seller_branch = await a_branch_name(client, seller_token)
    buyer_branch = await a_branch_name(client, buyer_token)
    seller_code = unique("ADMS")
    buyer_code = unique("ADMB")
    expiry = (date.today() + timedelta(days=100)).isoformat()

    for token, branch, code in (
        (seller_token, seller_branch, seller_code),
        (buyer_token, buyer_branch, buyer_code),
    ):
        job = await upload(
            client,
            token,
            build_sheet(
                [
                    {
                        "product_name": f"دواء {code}",
                        "sku": code,
                        "batch_number": code,
                        "expiry_date": expiry,
                        "quantity": 30,
                        "unit_cost": 10.0,
                    }
                ],
                branch,
            ),
        )
        assert job["created_batches"] == 1, job

    seen = await client.get(
        "/admin/inventory", headers=auth(admin_token), params={"page_size": 200}
    )
    assert seen.status_code == 200
    body = seen.json()

    numbers = {row["batch_number"] for row in body["items"]}
    assert seller_code in numbers, "the admin must see the seller's stock"
    assert buyer_code in numbers, "the admin must see the buyer's stock"

    # Every row names its owner, which is the point of the view.
    named = {
        row["batch_number"]: row["organization_name"]
        for row in body["items"]
        if row["batch_number"] in (seller_code, buyer_code)
    }
    assert all(named.values()), "each row must name the pharmacy holding it"
    assert named[seller_code] != named[buyer_code], "two pharmacies, two names"

    # And the totals span the platform rather than the page.
    assert body["totals"]["organizations"] >= 2
    assert body["totals"]["batches"] >= body["total"]


@pytest.mark.asyncio
async def test_a_pharmacy_cannot_reach_the_admin_views(client, seller_token):
    for path in ("/admin/inventory", "/admin/products/drafts", "/admin/imports"):
        response = await client.get(path, headers=auth(seller_token))
        assert response.status_code == 403, f"{path} was reachable by a pharmacy"


@pytest.mark.asyncio
async def test_the_admin_views_need_authentication(client):
    for path in ("/admin/inventory", "/admin/products/drafts", "/admin/imports"):
        response = await client.get(path)
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_the_zone_filter_narrows_by_expiry(client, seller_token, admin_token):
    branch = await a_branch_name(client, seller_token)
    code = unique("ZONE")
    await upload(
        client,
        seller_token,
        build_sheet(
            [
                {
                    "product_name": f"عاجل {code}",
                    "sku": f"{code}-R",
                    "batch_number": f"{code}-R",
                    "expiry_date": (date.today() + timedelta(days=12)).isoformat(),
                    "quantity": 5,
                },
                {
                    "product_name": f"بعيد {code}",
                    "sku": f"{code}-G",
                    "batch_number": f"{code}-G",
                    "expiry_date": (date.today() + timedelta(days=500)).isoformat(),
                    "quantity": 5,
                },
            ],
            branch,
        ),
    )

    red = await client.get(
        "/admin/inventory",
        headers=auth(admin_token),
        params={"zone": "red", "page_size": 200},
    )
    assert red.status_code == 200
    numbers = {row["batch_number"] for row in red.json()["items"]}
    assert f"{code}-R" in numbers
    assert f"{code}-G" not in numbers, "a 500 day batch is not in the red band"
    assert all(row["zone"] == "red" for row in red.json()["items"])

    # Searching finds it regardless of band.
    found = await client.get(
        "/admin/inventory",
        headers=auth(admin_token),
        params={"search": f"{code}-G", "page_size": 50},
    )
    assert f"{code}-G" in {row["batch_number"] for row in found.json()["items"]}


@pytest.mark.asyncio
async def test_a_draft_appears_in_the_queue_and_can_join_the_catalogue(
    client, seller_token, buyer_token, admin_token
):
    branch = await a_branch_name(client, seller_token)
    code = unique("DRAFT")

    job = await upload(
        client,
        seller_token,
        build_sheet(
            [
                {
                    "product_name": f"دواء غير معروف {code}",
                    "sku": code,
                    "batch_number": code,
                    "expiry_date": (date.today() + timedelta(days=200)).isoformat(),
                    "quantity": 15,
                }
            ],
            branch,
        ),
    )
    assert job["created_products"] == 1, "an unknown name must become a draft"

    queue = await client.get(
        "/admin/products/drafts", headers=auth(admin_token), params={"page_size": 200}
    )
    assert queue.status_code == 200
    entry = next(
        (row for row in queue.json()["items"] if row["sku"] == code), None
    )
    assert entry is not None, "the draft must appear in the admin queue"
    assert entry["organization_name"], "the queue must say whose draft it is"
    assert entry["batch_count"] >= 1, "and how much stock depends on it"
    assert entry["source"] == "import"

    # Before promotion the other pharmacy cannot see it.
    hidden = await client.get(
        "/products", headers=auth(buyer_token), params={"search": code}
    )
    assert code not in {item["sku"] for item in hidden.json()["items"]}

    promoted = await client.post(
        f"/admin/products/drafts/{entry['id']}/promote",
        headers=auth(admin_token),
        json={},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["is_draft"] is False
    assert promoted.json()["owner_organization_id"] is None

    # Now every pharmacy can use it.
    shared = await client.get(
        "/products", headers=auth(buyer_token), params={"search": code}
    )
    assert code in {item["sku"] for item in shared.json()["items"]}

    # And it has left the queue.
    again = await client.get(
        "/admin/products/drafts", headers=auth(admin_token), params={"page_size": 200}
    )
    assert code not in {row["sku"] for row in again.json()["items"]}

    # Promoting twice is a conflict, not a silent success.
    repeat = await client.post(
        f"/admin/products/drafts/{entry['id']}/promote",
        headers=auth(admin_token),
        json={},
    )
    assert repeat.status_code == 409


@pytest.mark.asyncio
async def test_promotion_keeps_the_pharmacys_stock_pointing_at_the_product(
    client, seller_token, admin_token
):
    """The batches must survive the move, or a pharmacy loses inventory."""
    from tests.test_inventory_import import find_batches

    branch = await a_branch_name(client, seller_token)
    code = unique("KEEP")
    await upload(
        client,
        seller_token,
        build_sheet(
            [
                {
                    "product_name": f"يبقى {code}",
                    "sku": code,
                    "batch_number": code,
                    "expiry_date": (date.today() + timedelta(days=210)).isoformat(),
                    "quantity": 42,
                }
            ],
            branch,
        ),
    )
    before = await find_batches(client, seller_token, code)
    assert len(before) == 1 and before[0]["quantity"] == 42

    queue = await client.get(
        "/admin/products/drafts", headers=auth(admin_token), params={"page_size": 200}
    )
    entry = next(row for row in queue.json()["items"] if row["sku"] == code)
    assert (
        await client.post(
            f"/admin/products/drafts/{entry['id']}/promote",
            headers=auth(admin_token),
            json={},
        )
    ).status_code == 200

    after = await find_batches(client, seller_token, code)
    assert len(after) == 1, "the batch must still exist"
    assert after[0]["quantity"] == 42
    assert after[0]["id"] == before[0]["id"], "and be the same batch"


@pytest.mark.asyncio
async def test_promotion_refuses_a_code_the_catalogue_already_uses(
    client, seller_token, admin_token
):
    from database import AsyncSessionLocal
    from models.product import Product
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(
                select(Product).where(Product.owner_organization_id.is_(None)).limit(1)
            )
        ).scalar_one()
        taken = existing.sku

    branch = await a_branch_name(client, seller_token)
    code = unique("CLASH")
    await upload(
        client,
        seller_token,
        build_sheet(
            [
                {
                    "product_name": f"تعارض {code}",
                    "sku": code,
                    "batch_number": code,
                    "expiry_date": (date.today() + timedelta(days=190)).isoformat(),
                    "quantity": 8,
                }
            ],
            branch,
        ),
    )

    queue = await client.get(
        "/admin/products/drafts", headers=auth(admin_token), params={"page_size": 200}
    )
    entry = next(row for row in queue.json()["items"] if row["sku"] == code)

    clash = await client.post(
        f"/admin/products/drafts/{entry['id']}/promote",
        headers=auth(admin_token),
        json={"sku": taken},
    )
    assert clash.status_code == 409
    assert taken in clash.json()["detail"]

    # The draft must be unharmed by the failed attempt.
    still = await client.get(
        "/admin/products/drafts", headers=auth(admin_token), params={"page_size": 200}
    )
    assert code in {row["sku"] for row in still.json()["items"]}


@pytest.mark.asyncio
async def test_the_admin_sees_every_import(client, seller_token, buyer_token, admin_token):
    branch = await a_branch_name(client, seller_token)
    code = unique("IMPADM")
    job = await upload(
        client,
        seller_token,
        build_sheet(
            [
                {
                    "product_name": f"سجل {code}",
                    "batch_number": code,
                    "expiry_date": (date.today() + timedelta(days=70)).isoformat(),
                    "quantity": 6,
                }
            ],
            branch,
        ),
    )

    seen = await client.get(
        "/admin/imports", headers=auth(admin_token), params={"page_size": 200}
    )
    assert seen.status_code == 200
    row = next((r for r in seen.json()["items"] if r["id"] == job["id"]), None)
    assert row is not None, "the admin must see the pharmacy's import"
    assert row["organization_name"], "and know whose it was"
    assert row["created_by_name"], "and who ran it"
    assert row["status"] in ("completed", "completed_with_errors")

    # The pharmacy that did not run it still cannot see it anywhere.
    theirs = await client.get(
        "/inventory/import", headers=auth(buyer_token), params={"page_size": 100}
    )
    assert job["id"] not in {item["id"] for item in theirs.json()["items"]}


@pytest.mark.asyncio
async def test_promoting_something_that_is_not_there(client, admin_token):
    response = await client.post(
        f"/admin/products/drafts/{uuid.uuid4()}/promote",
        headers=auth(admin_token),
        json={},
    )
    assert response.status_code == 404
