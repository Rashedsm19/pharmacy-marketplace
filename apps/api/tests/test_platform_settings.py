"""Platform settings are legible before they are edited."""
from __future__ import annotations

import pytest

from tests.conftest import auth


@pytest.mark.asyncio
async def test_settings_come_back_described_in_both_languages(client, admin_token):
    """Regression: the screen showed "[object Object]" and English-only labels."""
    response = await client.get("/admin/settings", headers=auth(admin_token))
    assert response.status_code == 200
    rows = response.json()
    assert rows, "the platform must have settings"

    for row in rows:
        assert row["label_ar"] and row["label_en"], row["key"]
        assert row["description_ar"], row["key"]
        assert row["group_ar"] and row["group_en"], row["key"]
        assert row["value_type"] in ("number", "percent", "boolean", "text")
        # The value must be renderable, not a nested object.
        assert not isinstance(row["value"], dict), f'{row["key"]} is still wrapped'

    fee = next(r for r in rows if r["key"] == "marketplace.platform_fee_pct")
    assert fee["value_type"] == "percent"
    assert fee["unit_ar"] == "٪"
    assert fee["label_ar"] == "عمولة المنصة"
    assert isinstance(fee["value"], (int, float))


@pytest.mark.asyncio
async def test_a_number_saves_as_a_number(client, admin_token):
    saved = await client.put(
        "/admin/settings/marketplace.min_listing_days",
        headers=auth(admin_token),
        json={"value": "45"},
    )
    assert saved.status_code == 200
    assert saved.json()["value"] == 45, "a form submits text; storage must not"

    rows = (await client.get("/admin/settings", headers=auth(admin_token))).json()
    row = next(r for r in rows if r["key"] == "marketplace.min_listing_days")
    assert row["value"] == 45
    assert not isinstance(row["value"], str)


@pytest.mark.asyncio
async def test_a_boolean_saves_as_a_boolean(client, admin_token):
    saved = await client.put(
        "/admin/settings/notifications.email_enabled",
        headers=auth(admin_token),
        json={"value": "true"},
    )
    assert saved.status_code == 200
    assert saved.json()["value"] is True


@pytest.mark.asyncio
async def test_a_value_outside_its_range_is_refused_with_the_reason(client, admin_token):
    refused = await client.put(
        "/admin/settings/marketplace.platform_fee_pct",
        headers=auth(admin_token),
        json={"value": 150},
    )
    assert refused.status_code == 400
    assert "أعلى قيمة" in refused.json()["detail"]

    not_a_number = await client.put(
        "/admin/settings/marketplace.min_listing_days",
        headers=auth(admin_token),
        json={"value": "كثير"},
    )
    assert not_a_number.status_code == 400
    assert "رقم" in not_a_number.json()["detail"]


@pytest.mark.asyncio
async def test_a_pharmacy_cannot_read_or_change_platform_settings(client, seller_token):
    assert (
        await client.get("/admin/settings", headers=auth(seller_token))
    ).status_code == 403
    assert (
        await client.put(
            "/admin/settings/marketplace.platform_fee_pct",
            headers=auth(seller_token),
            json={"value": 0},
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_a_value_stored_with_the_wrong_type_still_displays(client, admin_token):
    """Regression: a percentage stored as a boolean rendered as "True ٪".

    Values written before the types were enforced can disagree with the setting
    they belong to; the screen must still show something an administrator can
    read and correct.
    """
    from database import AsyncSessionLocal
    from models.settings import PlatformSettings
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(PlatformSettings).where(
                    PlatformSettings.key == "marketplace.platform_fee_pct"
                )
            )
        ).scalar_one()
        row.value = {"value": True}          # exactly the broken shape found
        await db.commit()

    rows = (await client.get("/admin/settings", headers=auth(admin_token))).json()
    fee = next(r for r in rows if r["key"] == "marketplace.platform_fee_pct")
    assert not isinstance(fee["value"], bool), "a percentage must not read as a boolean"
    assert isinstance(fee["value"], (int, float))

    # And it can be corrected from the screen.
    fixed = await client.put(
        "/admin/settings/marketplace.platform_fee_pct",
        headers=auth(admin_token),
        json={"value": "2.5"},
    )
    assert fixed.status_code == 200
    assert fixed.json()["value"] == 2.5
