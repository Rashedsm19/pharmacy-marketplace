"""Branch repository."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.branch import PharmacyBranch
from repositories.base import BaseRepository


class BranchRepository(BaseRepository[PharmacyBranch]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(PharmacyBranch, db)

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        active_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PharmacyBranch], int]:
        clauses = [
            PharmacyBranch.organization_id == org_id,
            PharmacyBranch.deleted_at.is_(None),
        ]
        if active_only:
            clauses.append(PharmacyBranch.is_active.is_(True))
        return await self.get_many(*clauses, offset=offset, limit=limit)

    async def get_by_org(
        self, branch_id: uuid.UUID, org_id: uuid.UUID
    ) -> PharmacyBranch | None:
        result = await self.db.execute(
            select(PharmacyBranch).where(
                PharmacyBranch.id == branch_id,
                PharmacyBranch.organization_id == org_id,
                PharmacyBranch.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()
