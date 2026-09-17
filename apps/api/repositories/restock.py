"""Restock recommendation repository — org-scoped reads and the upsert key lookup."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.restock import RecommendationStatus, RestockKind, RestockRecommendation
from repositories.base import BaseRepository


class RestockRecommendationRepository(BaseRepository[RestockRecommendation]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RestockRecommendation, db)

    async def list_for_org(
        self,
        org_id: uuid.UUID,
        kind: RestockKind | None = None,
        status: RecommendationStatus | None = None,
        branch_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[RestockRecommendation], int]:
        clauses = [RestockRecommendation.organization_id == org_id]
        if kind:
            clauses.append(RestockRecommendation.kind == kind)
        if status:
            clauses.append(RestockRecommendation.status == status)
        if branch_id:
            clauses.append(RestockRecommendation.branch_id == branch_id)
        return await self.get_many(*clauses, offset=offset, limit=limit)

    async def list_all_for_org(self, org_id: uuid.UUID) -> Sequence[RestockRecommendation]:
        result = await self.db.execute(
            select(RestockRecommendation).where(
                RestockRecommendation.organization_id == org_id
            )
        )
        return result.scalars().all()

    async def get_for_org(
        self, rec_id: uuid.UUID, org_id: uuid.UUID
    ) -> RestockRecommendation | None:
        result = await self.db.execute(
            select(RestockRecommendation).where(
                RestockRecommendation.id == rec_id,
                RestockRecommendation.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_key(
        self, branch_id: uuid.UUID, product_id: uuid.UUID, kind: RestockKind
    ) -> RestockRecommendation | None:
        result = await self.db.execute(
            select(RestockRecommendation).where(
                RestockRecommendation.branch_id == branch_id,
                RestockRecommendation.product_id == product_id,
                RestockRecommendation.kind == kind,
            )
        )
        return result.scalar_one_or_none()

    async def counts_by_status(self, org_id: uuid.UUID) -> dict[str, int]:
        result = await self.db.execute(
            select(
                RestockRecommendation.kind,
                RestockRecommendation.status,
                func.count(),
            )
            .where(RestockRecommendation.organization_id == org_id)
            .group_by(RestockRecommendation.kind, RestockRecommendation.status)
        )
        counts: dict[str, int] = {}
        for kind, status, count in result.all():
            counts[f"{kind}.{status}"] = int(count)
        return counts

    async def last_computed_at(self, org_id: uuid.UUID):
        return await self.db.scalar(
            select(func.max(RestockRecommendation.computed_at)).where(
                RestockRecommendation.organization_id == org_id
            )
        )
