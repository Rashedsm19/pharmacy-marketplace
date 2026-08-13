"""Operational guarantees: documents, commission, reservation sweep, eligibility."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from tests.conftest import auth

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.asyncio
async def test_document_upload_accepts_a_real_pdf(client, seller_token):
    response = await client.post(
        "/organizations/me/documents/cr",
        headers=auth(seller_token),
        files={"file": ("cr.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["cr_doc_url"], "the stored reference was not recorded"


@pytest.mark.asyncio
async def test_document_upload_rejects_a_disallowed_type(client, seller_token):
    response = await client.post(
        "/organizations/me/documents/cr",
        headers=auth(seller_token),
        files={"file": ("page.html", b"<html></html>", "text/html")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_document_upload_rejects_content_that_lies_about_its_type(client, seller_token):
    """Content-Type comes from the client, so the bytes are checked as well."""
    response = await client.post(
        "/organizations/me/documents/license",
        headers=auth(seller_token),
        files={"file": ("fake.pdf", b"GIF89a not a pdf", "application/pdf")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_document_upload_rejects_an_oversized_file(client, seller_token):
    from config import settings

    oversized = b"%PDF-" + b"x" * (settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 10)
    response = await client.post(
        "/organizations/me/documents/cr",
        headers=auth(seller_token),
        files={"file": ("big.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_documents_are_readable_by_owner_and_admin_only(
    client, seller_token, admin_token, buyer_token
):
    await client.post(
        "/organizations/me/documents/license",
        headers=auth(seller_token),
        files={"file": ("lic.png", PNG, "image/png")},
    )
    org = (await client.get("/organizations/me", headers=auth(seller_token))).json()
    url = f"/organizations/{org['id']}/documents/license"

    assert (await client.get(url, headers=auth(seller_token))).status_code == 200
    assert (await client.get(url, headers=auth(admin_token))).status_code == 200
    assert (await client.get(url, headers=auth(buyer_token))).status_code == 403
    assert (await client.get(url)).status_code == 401


@pytest.mark.asyncio
async def test_commission_follows_the_platform_setting(client, admin_token):
    """The admin owns the rate; it must not be hardcoded in the service."""
    from decimal import Decimal

    from database import AsyncSessionLocal
    from models.settings import PlatformSettings
    from services.transaction_service import TransactionService

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(PlatformSettings).where(
                    PlatformSettings.key == "marketplace.platform_fee_pct"
                )
            )
        ).scalar_one_or_none()
        assert row is not None, "the fee setting is missing from the seed"
        row.value = {"value": 3.5}
        await db.commit()

    async with AsyncSessionLocal() as db:
        assert await TransactionService(db)._platform_fee_pct() == Decimal("3.5")

    # A malformed value must fall back rather than block a sale.
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(PlatformSettings).where(
                    PlatformSettings.key == "marketplace.platform_fee_pct"
                )
            )
        ).scalar_one()
        row.value = {"value": True}
        await db.commit()

    async with AsyncSessionLocal() as db:
        assert await TransactionService(db)._platform_fee_pct() == Decimal("2")


@pytest.mark.asyncio
async def test_expired_reservations_release_the_listing(client, seller_token, buyer_token):
    """Regression: nothing swept these, so listings stayed reserved for ever."""
    from database import AsyncSessionLocal
    from models.marketplace import MarketplaceListing, Reservation
    from scheduler import expire_stale_reservations
    from tests.test_marketplace_cycle import _eligible_listing

    listing = await _eligible_listing(client, seller_token)
    offer = await client.post(
        "/offers",
        headers=auth(buyer_token),
        json={"listing_id": listing["id"], "offered_price": 30.0, "quantity": 3},
    )
    offer_id = offer.json()["id"]
    await client.post(f"/offers/{offer_id}/accept", headers=auth(seller_token))

    async with AsyncSessionLocal() as db:
        reservation = (
            await db.execute(select(Reservation).where(Reservation.offer_id == offer_id))
        ).scalar_one()
        reservation.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await db.commit()
        reservation_id = reservation.id

    await expire_stale_reservations()

    async with AsyncSessionLocal() as db:
        reservation = (
            await db.execute(select(Reservation).where(Reservation.id == reservation_id))
        ).scalar_one()
        assert reservation.status == "expired"

        refreshed = (
            await db.execute(
                select(MarketplaceListing).where(MarketplaceListing.id == listing["id"])
            )
        ).scalar_one()
        assert refreshed.status == "active", "the listing must return to the market"


@pytest.mark.asyncio
async def test_eligibility_reports_every_rule(client, seller_token):
    batches = (
        await client.get(
            "/inventory/batches", headers=auth(seller_token), params={"page_size": 1}
        )
    ).json()["items"]
    result = await client.get(
        "/listings/eligibility-check",
        headers=auth(seller_token),
        params={"batch_id": batches[0]["id"]},
    )
    assert result.status_code == 200
    body = result.json()
    assert "all_passed" in body
    assert len(body["rules"]) >= 10, "all ten marketplace rules must be reported"
    assert all("rule_name" in rule and "passed" in rule for rule in body["rules"])
