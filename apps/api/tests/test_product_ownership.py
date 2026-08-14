"""Private products belong to one pharmacy and stay invisible to the rest."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from tests.conftest import auth


async def _make_private_product(org_id, sku: str, name: str = "دواء خاص"):
    """Insert a product owned by one organization, as an import would."""
    from database import AsyncSessionLocal
    from models.product import Product, ProductCategory, ProductSource

    async with AsyncSessionLocal() as db:
        category = (await db.execute(select(ProductCategory).limit(1))).scalar_one()
        product = Product(
            id=uuid.uuid4(),
            owner_organization_id=org_id,
            is_draft=True,
            source=ProductSource.IMPORT,
            category_id=category.id,
            name=name,
            name_ar=name,
            sku=sku,
        )
        db.add(product)
        await db.commit()
        return product.id


@pytest.mark.asyncio
async def test_the_shared_catalogue_is_still_visible_to_everyone(client, seller_token):
    """Owning products must not have hidden the catalogue every pharmacy shares."""
    from database import AsyncSessionLocal
    from models.product import Product

    async with AsyncSessionLocal() as db:
        catalogue = (
            await db.execute(
                select(Product).where(
                    Product.owner_organization_id.is_(None),
                    Product.deleted_at.is_(None),
                )
            )
        ).scalars().all()
    assert catalogue, "the seeded catalogue must exist"

    visible: set[str] = set()
    page = 1
    while True:
        listed = await client.get(
            "/products",
            headers=auth(seller_token),
            params={"page": page, "page_size": 100},
        )
        assert listed.status_code == 200
        body = listed.json()
        visible |= {item["id"] for item in body["items"]}
        if page * 100 >= body["total"]:
            break
        page += 1

    missing = {str(p.id) for p in catalogue} - visible
    assert not missing, f"{len(missing)} catalogue products are not visible"


@pytest.mark.asyncio
async def test_a_private_product_is_hidden_from_other_pharmacies(
    client, seller_token, buyer_token
):
    seller_org = (await client.get("/organizations/me", headers=auth(seller_token))).json()["id"]
    sku = f"PRIV-{uuid.uuid4().hex[:8]}"
    product_id = await _make_private_product(seller_org, sku, "أموكسيسيلين خاص")

    mine = await client.get("/products", headers=auth(seller_token), params={"search": sku})
    assert sku in {item["sku"] for item in mine.json()["items"]}, "the owner must see it"

    theirs = await client.get("/products", headers=auth(buyer_token), params={"search": sku})
    assert sku not in {item["sku"] for item in theirs.json()["items"]}, "it leaked"

    # Nor by fetching the id directly.
    direct = await client.get(f"/products/{product_id}", headers=auth(buyer_token))
    assert direct.status_code == 404


@pytest.mark.asyncio
async def test_the_platform_admin_sees_private_products(client, seller_token, admin_token):
    seller_org = (await client.get("/organizations/me", headers=auth(seller_token))).json()["id"]
    sku = f"PRIV-{uuid.uuid4().hex[:8]}"
    product_id = await _make_private_product(seller_org, sku)

    seen = await client.get(f"/products/{product_id}", headers=auth(admin_token))
    assert seen.status_code == 200
    assert seen.json()["is_draft"] is True
    assert seen.json()["source"] == "import"


@pytest.mark.asyncio
async def test_two_pharmacies_may_use_the_same_internal_code(
    client, seller_token, buyer_token
):
    """Regression: sku was globally unique, so the second pharmacy could not import."""
    seller_org = (await client.get("/organizations/me", headers=auth(seller_token))).json()["id"]
    buyer_org = (await client.get("/organizations/me", headers=auth(buyer_token))).json()["id"]

    shared_code = f"SAME-{uuid.uuid4().hex[:6]}"
    first = await _make_private_product(seller_org, shared_code, "دواء أ")
    second = await _make_private_product(buyer_org, shared_code, "دواء ب")
    assert first != second

    from database import AsyncSessionLocal
    from models.product import Product

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(select(Product).where(Product.sku == shared_code))
        ).scalars().all()
    assert len(rows) == 2, "both pharmacies must be able to hold the same code"


@pytest.mark.asyncio
async def test_the_shared_catalogue_still_rejects_duplicate_codes(client, admin_token):
    """NULLS NOT DISTINCT keeps the catalogue itself free of duplicates."""
    from database import AsyncSessionLocal
    from models.product import Product, ProductCategory

    async with AsyncSessionLocal() as db:
        category = (await db.execute(select(ProductCategory).limit(1))).scalar_one()
        sku = f"CAT-{uuid.uuid4().hex[:6]}"
        db.add(
            Product(
                id=uuid.uuid4(), category_id=category.id, name="A", name_ar="أ", sku=sku
            )
        )
        await db.commit()

    duplicate = await client.post(
        "/products",
        headers=auth(admin_token),
        json={
            "sku": sku,
            "name": "B",
            "name_ar": "ب",
            "category_id": str(category.id),
            "unit": "box",
        },
    )
    assert duplicate.status_code == 409
