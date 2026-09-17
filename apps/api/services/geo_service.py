"""Geo matching: marketplace search relative to one of the buyer's branches."""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.branch import PharmacyBranch
from repositories.branch import BranchRepository
from repositories.inventory import NearExpiryRuleRepository
from repositories.marketplace import ListingRepository
from schemas.marketplace import ListingOut

BRANCH_HAS_NO_COORDINATES = "الفرع المحدد لا يحتوي على إحداثيات. حدث موقع الفرع أولا."


class GeoSearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resolve_branch(
        self, branch_id: uuid.UUID, org_id: uuid.UUID | None
    ) -> PharmacyBranch:
        """The buyer's branch, which must belong to their org and carry coordinates."""
        repo = BranchRepository(self.db)
        branch = (
            await repo.get_by_org(branch_id, org_id) if org_id else await repo.get(branch_id)
        )
        if not branch or branch.deleted_at:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الفرع غير موجود")
        if branch.latitude is None or branch.longitude is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=BRANCH_HAS_NO_COORDINATES
            )
        return branch

    async def default_radius_km(self, org_id: uuid.UUID | None) -> float | None:
        if not org_id:
            return None
        rule = await NearExpiryRuleRepository(self.db).get_by_org(org_id)
        if rule and rule.max_delivery_radius_km is not None:
            return float(rule.max_delivery_radius_km)
        return None

    async def search(
        self,
        buyer_org_id: uuid.UUID | None,
        near_branch_id: uuid.UUID,
        radius_km: float | None = None,
        sort: str | None = "distance",
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ListingOut], int]:
        branch = await self.resolve_branch(near_branch_id, buyer_org_id)
        if radius_km is None:
            radius_km = await self.default_radius_km(buyer_org_id)

        rows, total = await ListingRepository(self.db).search(
            search=search,
            category_id=category_id,
            exclude_org_id=buyer_org_id,
            near_lat=branch.latitude,
            near_lng=branch.longitude,
            radius_km=radius_km,
            sort=sort,
            offset=offset,
            limit=limit,
        )
        items = []
        for listing, distance in rows:
            out = ListingOut.model_validate(listing)
            out.distance_km = distance
            items.append(out)
        return items, total
