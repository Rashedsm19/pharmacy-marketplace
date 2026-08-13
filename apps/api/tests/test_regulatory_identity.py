"""VAT number, GLN and licence expiry on the organization."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.conftest import auth


@pytest.mark.asyncio
async def test_organisation_accepts_valid_regulatory_identity(client, seller_token):
    response = await client.patch(
        "/organizations/me",
        headers=auth(seller_token),
        json={
            "vat_number": "300000000000003",
            "gln": "6287000000009",
            "license_expires_at": "2027-03-31",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["vat_number"] == "300000000000003"
    assert body["gln"] == "6287000000009"
    assert body["license_expires_at"] == "2027-03-31"
    assert body["license_verification_status"] == "unverified"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"vat_number": "123456"},           # too short
        {"vat_number": "400000000000004"},  # must start and end with 3
        {"gln": "12345"},                   # wrong length
        {"gln": "6287000000001"},           # bad check digit
    ],
)
async def test_malformed_identifiers_are_rejected(client, seller_token, payload):
    response = await client.patch(
        "/organizations/me", headers=auth(seller_token), json=payload
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_identity_reaches_the_database(client, seller_token):
    await client.patch(
        "/organizations/me",
        headers=auth(seller_token),
        json={"vat_number": "310000000000003", "gln": "6287000000009"},
    )

    from database import AsyncSessionLocal
    from models.organization import PharmacyOrganization

    org_id = (await client.get("/organizations/me", headers=auth(seller_token))).json()["id"]
    async with AsyncSessionLocal() as db:
        org = (
            await db.execute(
                select(PharmacyOrganization).where(PharmacyOrganization.id == org_id)
            )
        ).scalar_one()
        assert org.vat_number == "310000000000003"
        assert org.gln == "6287000000009"


@pytest.mark.asyncio
async def test_audit_state_survives_non_json_values(client, seller_token, admin_token):
    """Regression: a date in before/after state made the audit write raise and
    took the whole request down with it."""
    response = await client.patch(
        "/organizations/me",
        headers=auth(seller_token),
        json={"license_expires_at": "2028-01-15"},
    )
    assert response.status_code == 200, response.text

    logs = await client.get(
        "/admin/audit-logs",
        headers=auth(admin_token),
        params={"action": "organization_updated", "page_size": 5},
    )
    entry = logs.json()["items"][0]
    assert entry["after_state"]["license_expires_at"] == "2028-01-15"
