"""Customer sign-up: registration persists every field, and the account can log in."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.conftest import auth, unique


def registration_payload(suffix: str) -> dict:
    return {
        "full_name": "عبدالله بن سالم القحطاني",
        "email": f"owner-{suffix}@sahapharma.sa",
        "phone": "+966501122334",
        "password": "Sahha@2026",
        "org_name": f"Sahha Pharmacies {suffix}",
        "org_name_ar": "شركة صحة للصيدليات",
        "commercial_registration_number": f"1010{suffix}",
        "license_number": f"PH-LIC-{suffix}",
        "org_email": f"info-{suffix}@sahapharma.sa",
        "org_phone": "+966114455667",
        "org_address": "طريق الملك فهد، برج المملكة",
        "org_city": "الرياض",
        "org_region": "منطقة الرياض",
        "branch_name": f"Sahha Olaya {suffix}",
        "branch_name_ar": "فرع صحة — العليا",
        "branch_address": "شارع العليا العام",
        "branch_city": "الرياض",
        "branch_phone": "+966114455668",
    }


@pytest.mark.asyncio
async def test_registration_persists_the_whole_profile(client):
    payload = registration_payload(unique())

    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text

    login = await client.post(
        "/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200, login.text
    token = login.json()
    assert token["role"] == "org_admin"
    assert token["org_id"], "membership was not created"

    from database import AsyncSessionLocal
    from models.branch import PharmacyBranch
    from models.organization import PharmacyOrganization, UserOrganizationMembership
    from models.user import User

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == payload["email"]))
        ).scalar_one()
        assert user.full_name == payload["full_name"]
        assert user.phone == payload["phone"]
        assert user.hashed_password.startswith("$argon2id"), "password stored unhashed"

        membership = (
            await db.execute(
                select(UserOrganizationMembership).where(
                    UserOrganizationMembership.user_id == user.id
                )
            )
        ).scalar_one()
        assert membership.role == "owner"

        org = (
            await db.execute(
                select(PharmacyOrganization).where(
                    PharmacyOrganization.id == membership.organization_id
                )
            )
        ).scalar_one()
        assert org.commercial_registration_number == payload["commercial_registration_number"]
        assert org.license_number == payload["license_number"]
        assert org.name_ar == payload["org_name_ar"]
        assert org.address == payload["org_address"]
        assert org.city == payload["org_city"]
        assert org.region == payload["org_region"]
        assert org.status == "pending", "a new organization must await review"
        assert org.is_licensed is False

        branch = (
            await db.execute(
                select(PharmacyBranch).where(
                    PharmacyBranch.organization_id == org.id
                )
            )
        ).scalar_one()
        assert branch.name_ar == payload["branch_name_ar"]
        assert branch.address == payload["branch_address"]
        assert branch.city == payload["branch_city"]


@pytest.mark.asyncio
async def test_blank_licence_does_not_collide_between_organisations(client):
    """Regression: "" was stored and hit the UNIQUE constraint on the second sign-up."""
    for _ in range(3):
        payload = registration_payload(unique())
        payload["license_number"] = ""
        payload["org_name_ar"] = ""
        payload["branch_phone"] = ""
        response = await client.post("/auth/register", json=payload)
        assert response.status_code == 201, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,message_fragment",
    [
        ("email", "البريد"),
        ("commercial_registration_number", "السجل التجاري"),
        ("license_number", "الترخيص"),
    ],
)
async def test_duplicates_answer_409_not_500(client, field, message_fragment):
    first = registration_payload(unique())
    assert (await client.post("/auth/register", json=first)).status_code == 201

    second = registration_payload(unique())
    second[field] = first[field]

    response = await client.post("/auth/register", json=second)
    assert response.status_code == 409, response.text
    assert message_fragment in response.json()["detail"]


@pytest.mark.asyncio
async def test_new_account_starts_with_notification_preferences(client):
    payload = registration_payload(unique())
    assert (await client.post("/auth/register", json=payload)).status_code == 201

    login = await client.post(
        "/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    token = login.json()["access_token"]

    prefs = await client.get("/notifications/preferences", headers=auth(token))
    assert prefs.status_code == 200
    assert len(prefs.json()) > 0, "preferences screen would be empty"


@pytest.mark.asyncio
async def test_forgot_password_issues_a_token(client):
    payload = registration_payload(unique())
    assert (await client.post("/auth/register", json=payload)).status_code == 201

    response = await client.post("/auth/forgot-password", json={"email": payload["email"]})
    assert response.status_code == 200

    from database import AsyncSessionLocal
    from models.user import User

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == payload["email"]))
        ).scalar_one()
        assert user.password_reset_token, "no reset token was issued"
        token = user.password_reset_token

    reset = await client.post(
        "/reset-password".replace("/reset-password", "/auth/reset-password"),
        json={"token": token, "new_password": "Changed@2026"},
    )
    assert reset.status_code == 200, reset.text

    relogin = await client.post(
        "/auth/login", json={"email": payload["email"], "password": "Changed@2026"}
    )
    assert relogin.status_code == 200, "the new password does not work"
