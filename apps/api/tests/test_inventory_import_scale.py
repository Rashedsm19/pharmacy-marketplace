"""
The ten thousand row case — the reason this feature exists.

Marked slow because it writes a real file and a real ten thousand batches; run
it with `pytest -m slow`. It guards three promises: the import finishes, the
per-pharmacy ceiling holds, and reading the file does not load it all into
memory.
"""
from __future__ import annotations

import io
import tracemalloc
from datetime import date, timedelta

import pytest

from tests.conftest import auth, unique
from tests.test_inventory_import import a_branch_name, run_pending_imports

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def big_sheet(rows: int, branch: str, tag: str) -> bytes:
    """Written with openpyxl's write-only mode, as a real export would be."""
    from openpyxl import Workbook

    from services.excel_service import COLUMNS

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("البيانات")
    sheet.append([column.header_ar for column in COLUMNS])
    base = date.today() + timedelta(days=40)
    for index in range(rows):
        sheet.append(
            [
                f"دواء {tag}-{index}",
                None,
                f"{tag}-{index}",
                f"B{tag}{index}",
                (base + timedelta(days=index % 400)).isoformat(),
                (index % 50) + 1,
                round(1.5 + (index % 30), 2),
                branch,
                None,
                None,
                None,
                None,
            ]
        )
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_ten_thousand_rows_import_and_the_ceiling_holds(client, seller_token):
    from config import settings
    from services.import_service import count_org_items

    from database import AsyncSessionLocal

    branch = await a_branch_name(client, seller_token)
    tag = unique("K")

    async with AsyncSessionLocal() as db:
        seller_org = (
            await client.get("/organizations/me", headers=auth(seller_token))
        ).json()["id"]
        import uuid as _uuid

        before = await count_org_items(db, _uuid.UUID(seller_org))

    rows = settings.MAX_INVENTORY_ITEMS_PER_ORG - before
    assert rows > 100, "the pharmacy must have room for a meaningful run"

    # Ask for a hundred more than the ceiling allows: the file must import up to
    # the limit and report the rest rather than failing outright.
    content = big_sheet(rows + 100, branch, tag)

    response = await client.post(
        "/inventory/import",
        headers=auth(seller_token),
        files={"file": (f"{tag}.xlsx", content, XLSX)},
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    tracemalloc.start()
    await run_pending_imports()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    job = (
        await client.get(f"/inventory/import/{job_id}", headers=auth(seller_token))
    ).json()

    assert job["status"] in ("completed", "completed_with_errors"), job
    assert job["total_rows"] == rows + 100
    assert job["created_batches"] == rows, "everything up to the ceiling must land"
    assert job["failed_rows"] == 100, "the overflow must be reported, not silently dropped"
    assert "الحد الأقصى" in (job["failure_reason"] or "")

    async with AsyncSessionLocal() as db:
        import uuid as _uuid

        after = await count_org_items(db, _uuid.UUID(seller_org))
    assert after == settings.MAX_INVENTORY_ITEMS_PER_ORG

    # Streaming, not slurping: the whole run must stay far below the size a
    # fully materialised ten thousand row workbook would occupy.
    assert peak < 400 * 1024 * 1024, f"peak memory {peak / 1024 / 1024:.0f} MB"

    # And a further upload is refused up front, with an explanation.
    refused = await client.post(
        "/inventory/import",
        headers=auth(seller_token),
        files={"file": ("more.xlsx", big_sheet(1, branch, unique("X")), XLSX)},
    )
    assert refused.status_code == 409
    assert "الحد الأقصى" in refused.json()["detail"]
