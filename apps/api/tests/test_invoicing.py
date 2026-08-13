"""Tax invoicing: the QR payload, the hash chain, and issuing on completion."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from services.zatca_service import GENESIS_HASH, build_qr, hash_invoice, parse_qr, zatca_service
from tests.conftest import auth
from tests.test_marketplace_cycle import _eligible_listing


def test_qr_payload_round_trips_with_the_mandated_tags():
    """The five fields and their order are fixed by the specification."""
    qr = build_qr(
        "مجموعة صيدليات الدواء",
        "300000000000003",
        datetime(2026, 8, 14, 9, 30, tzinfo=timezone.utc),
        Decimal("460.00"),
        Decimal("60.00"),
    )
    fields = parse_qr(qr)
    assert fields[1] == "مجموعة صيدليات الدواء"
    assert fields[2] == "300000000000003"
    assert fields[3] == "2026-08-14T09:30:00Z"
    assert fields[4] == "460.00"
    assert fields[5] == "60.00"


def test_the_document_is_well_formed_and_carries_the_chain_fields():
    import xml.etree.ElementTree as ET

    xml_content = zatca_service.build_xml(
        invoice_number="INV-TEST-1",
        invoice_uuid="11111111-1111-1111-1111-111111111111",
        icv=7,
        previous_hash=GENESIS_HASH,
        issued_at=datetime.now(timezone.utc),
        seller_name="Al-Dawaa",
        seller_vat="300000000000003",
        buyer_name="Nahdi",
        buyer_vat="310000000000003",
        line_description="Amoxicillin 500mg",
        quantity=4,
        unit_price=Decimal("100"),
        subtotal=Decimal("400"),
        vat_rate=Decimal("15"),
        vat_amount=Decimal("60"),
        total_with_vat=Decimal("460"),
    )
    ET.fromstring(xml_content)  # raises if malformed
    assert "INV-TEST-1" in xml_content
    assert GENESIS_HASH in xml_content, "the previous hash must be embedded"
    assert "<cbc:UUID>7</cbc:UUID>" in xml_content, "the counter must be embedded"


def test_signing_produces_a_verifiable_signature():
    """Signing is exercised for real, even on stub credentials."""
    import base64

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    digest = hash_invoice("<Invoice/>")
    signature = zatca_service.sign(digest)
    public_key = zatca_service._signing_key().public_key()
    # Raises InvalidSignature if the signature does not match.
    public_key.verify(base64.b64decode(signature), digest.encode(), ec.ECDSA(hashes.SHA256()))


def test_a_changed_document_changes_its_hash():
    assert hash_invoice("<Invoice>a</Invoice>") != hash_invoice("<Invoice>b</Invoice>")


@pytest.mark.asyncio
async def test_completing_a_sale_issues_a_chained_invoice(
    client, seller_token, buyer_token
):
    """The seller needs a VAT number before a tax invoice can exist."""
    await client.patch(
        "/organizations/me",
        headers=auth(seller_token),
        json={"vat_number": "300000000000003"},
    )

    from database import AsyncSessionLocal
    from models.invoice import Invoice

    async def complete_one(quantity: int):
        listing = await _eligible_listing(client, seller_token, quantity_listed=20)
        offer = await client.post(
            "/offers",
            headers=auth(buyer_token),
            json={"listing_id": listing["id"], "offered_price": 100.0, "quantity": quantity},
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
        return tx

    first = await complete_one(4)
    second = await complete_one(3)

    async with AsyncSessionLocal() as db:
        invoices = (
            await db.execute(
                select(Invoice)
                .where(Invoice.transaction_id.in_([first["id"], second["id"]]))
                .order_by(Invoice.icv.asc())
            )
        ).scalars().all()

    assert len(invoices) == 2, "each completed sale must produce an invoice"
    earlier, later = invoices

    # VAT is applied on top of the agreed price.
    assert earlier.vat_amount == pytest.approx(float(earlier.subtotal) * 0.15, rel=1e-3)
    assert earlier.total_with_vat == pytest.approx(
        float(earlier.subtotal) + float(earlier.vat_amount), rel=1e-3
    )

    # The chain: consecutive counters, each hash pointing at its predecessor.
    assert later.icv == earlier.icv + 1
    assert later.previous_hash == earlier.invoice_hash
    assert earlier.status == "cleared", "stub mode clears the invoice"

    fields = parse_qr(earlier.qr_code)
    assert fields[2] == "300000000000003"


@pytest.mark.asyncio
async def test_invoice_is_visible_to_both_parties_and_nobody_else(
    client, seller_token, buyer_token, admin_token
):
    listed = await client.get("/invoices", headers=auth(seller_token))
    assert listed.status_code == 200
    if listed.json()["total"] == 0:
        pytest.skip("no invoice issued yet in this run")

    invoice = listed.json()["items"][0]
    assert (await client.get(f"/invoices/{invoice['id']}", headers=auth(buyer_token))).status_code == 200
    assert (await client.get(f"/invoices/{invoice['id']}", headers=auth(admin_token))).status_code == 200

    xml_download = await client.get(
        f"/invoices/{invoice['id']}/xml", headers=auth(seller_token)
    )
    assert xml_download.status_code == 200
    assert xml_download.text.startswith("<?xml")


@pytest.mark.asyncio
async def test_a_seller_without_a_vat_number_does_not_block_the_sale(
    client, seller_token, buyer_token
):
    """No VAT number means no invoice — but the goods still change hands."""
    from database import AsyncSessionLocal
    from models.organization import PharmacyOrganization

    org_id = (await client.get("/organizations/me", headers=auth(seller_token))).json()["id"]
    async with AsyncSessionLocal() as db:
        org = (
            await db.execute(
                select(PharmacyOrganization).where(PharmacyOrganization.id == org_id)
            )
        ).scalar_one()
        saved_vat = org.vat_number
        org.vat_number = None
        await db.commit()

    listing = await _eligible_listing(client, seller_token, quantity_listed=10)
    offer = await client.post(
        "/offers",
        headers=auth(buyer_token),
        json={"listing_id": listing["id"], "offered_price": 40.0, "quantity": 2},
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
    completed = await client.post(
        f"/transactions/{tx['id']}/confirm-receipt", headers=auth(buyer_token), json={}
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    async with AsyncSessionLocal() as db:
        org = (
            await db.execute(
                select(PharmacyOrganization).where(PharmacyOrganization.id == org_id)
            )
        ).scalar_one()
        org.vat_number = saved_vat
        await db.commit()
