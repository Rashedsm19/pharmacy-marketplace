"""
Scheduler job — periodic recompute of restock recommendations.

Runs after the near-expiry scan: every approved organization gets a full
recompute in one shared session; a failing org is logged and skipped rather
than taking down the tick for everyone else.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from database import AsyncSessionLocal
from models.organization import OrganizationStatus, PharmacyOrganization
from services.restock_service import RestockService

logger = logging.getLogger(__name__)


async def recompute_restock_recommendations() -> None:
    """Recompute restock recommendations for every approved organization."""
    logger.info("Starting restock recommendation recompute...")
    async with AsyncSessionLocal() as db:
        orgs = (
            await db.execute(
                select(PharmacyOrganization.id).where(
                    PharmacyOrganization.status == OrganizationStatus.APPROVED,
                    PharmacyOrganization.deleted_at.is_(None),
                )
            )
        ).scalars().all()

    totals = {"orgs": 0, "failed": 0, "created": 0, "updated": 0, "superseded": 0}
    for org_id in orgs:
        async with AsyncSessionLocal() as db:
            try:
                summary = await RestockService(db).compute_for_org(org_id)
                await db.commit()
                totals["orgs"] += 1
                totals["created"] += summary["created"]
                totals["updated"] += summary["updated"]
                totals["superseded"] += summary["superseded"]
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                totals["failed"] += 1
                logger.error("Restock recompute failed for org %s: %s", org_id, exc, exc_info=True)

    logger.info(
        "Restock recompute complete — %d orgs (%d failed): +%d created, %d updated, %d superseded",
        totals["orgs"], totals["failed"], totals["created"], totals["updated"],
        totals["superseded"],
    )
