"""
Regulated evidence must outlive a deploy.

The instance disk is wiped on every deploy and there is no persistent volume, so
a pharmacy licence uploaded on Monday was gone on Tuesday while the record still
said it had been submitted — and the download answered "file not found" to the
admin reviewing that pharmacy for approval.
"""
from __future__ import annotations

import io
import shutil
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from tests.conftest import auth

PDF = b"%PDF-1.4\n% durable evidence\n"


@pytest.mark.asyncio
async def test_a_licence_survives_the_disk_being_wiped(client, seller_token, admin_token):
    uploaded = await client.post(
        "/organizations/me/documents/license",
        headers=auth(seller_token),
        files={"file": ("licence.pdf", PDF, "application/pdf")},
    )
    assert uploaded.status_code in (200, 201), uploaded.text

    org_id = (
        await client.get("/organizations/me", headers=auth(seller_token))
    ).json()["id"]

    # It reads back while the disk is intact.
    before = await client.get(
        f"/organizations/{org_id}/documents/license", headers=auth(admin_token)
    )
    assert before.status_code == 200
    assert before.content == PDF

    # Now do what a deploy does.
    from config import settings

    shutil.rmtree(Path(settings.STORAGE_LOCAL_PATH), ignore_errors=True)

    after = await client.get(
        f"/organizations/{org_id}/documents/license", headers=auth(admin_token)
    )
    assert after.status_code == 200, (
        "the licence vanished with the disk — this is the defect this test exists for"
    )
    assert after.content == PDF, "the bytes came back changed"


@pytest.mark.asyncio
async def test_the_durable_copy_is_recorded(client, seller_token):
    from database import AsyncSessionLocal
    from models.stored_file import StoredFile

    await client.post(
        "/organizations/me/documents/cr",
        headers=auth(seller_token),
        files={"file": ("cr.pdf", PDF, "application/pdf")},
    )
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(StoredFile))).scalars().all()

    assert rows, "nothing was persisted"
    assert any(r.content == PDF for r in rows)
    assert all(r.size_bytes == len(r.content) for r in rows)
    assert all(r.content_type for r in rows)


@pytest.mark.asyncio
async def test_a_missing_document_says_what_to_do(client, admin_token):
    """When a file predates this and is genuinely gone, say so usefully."""
    from database import AsyncSessionLocal
    from models.organization import PharmacyOrganization

    async with AsyncSessionLocal() as db:
        org = (await db.execute(select(PharmacyOrganization).limit(1))).scalar_one()
        org.cr_doc_url = f"{org.id}/cr-{uuid.uuid4().hex}.pdf"
        org_id = org.id
        await db.commit()

    response = await client.get(
        f"/organizations/{org_id}/documents/cr", headers=auth(admin_token)
    )
    assert response.status_code == 404
    assert "رفعه من جديد" in response.json()["detail"]
    assert io  # the import is used by the sibling tests
