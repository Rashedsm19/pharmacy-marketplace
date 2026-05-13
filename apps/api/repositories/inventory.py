"""Inventory batch and movement repositories."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.inventory import BatchStatus, InventoryBatch, InventoryMovement, NearExpiryRule
from repositories.base import BaseRepository


class InventoryBatchRepository(BaseRepository[InventoryBatch]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(InventoryBatch, db)

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        status: BatchStatus | None = None,
        search: str | None = None,
        expiry_before: date | None = None,
        expiry_after: date | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[InventoryBatch], int]:
        clauses = [
            InventoryBatch.organization_id == org_id,
            InventoryBatch.deleted_at.is_(None),
        ]
        if branch_id:
            clauses.append(InventoryBatch.branch_id == branch_id)
        if status:
            clauses.append(InventoryBatch.status == status)
        if expiry_before:
            clauses.append(InventoryBatch.expiry_date <= expiry_before)
        if expiry_after:
            clauses.append(InventoryBatch.expiry_date >= expiry_after)
        return await self.get_many(*clauses, offset=offset, limit=limit)

    async def list_near_expiry(
        self,
        threshold_date: date,
        org_id: uuid.UUID | None = None,
    ) -> Sequence[InventoryBatch]:
        clauses = [
            InventoryBatch.expiry_date <= threshold_date,
            InventoryBatch.expiry_date >= date.today(),
            InventoryBatch.status.in_([BatchStatus.ACTIVE, BatchStatus.NEAR_EXPIRY]),
            InventoryBatch.deleted_at.is_(None),
        ]
        if org_id:
            clauses.append(InventoryBatch.organization_id == org_id)
        result = await self.db.execute(
            select(InventoryBatch)
            .where(and_(*clauses))
            .order_by(InventoryBatch.expiry_date)
        )
        return result.scalars().all()

    async def list_all_active_for_scan(self) -> Sequence[InventoryBatch]:
        result = await self.db.execute(
            select(InventoryBatch).where(
                InventoryBatch.expiry_date >= date.today(),
                InventoryBatch.status.in_([BatchStatus.ACTIVE, BatchStatus.NEAR_EXPIRY]),
                InventoryBatch.deleted_at.is_(None),
            )
        )
        return result.scalars().all()

    async def get_by_org(
        self, batch_id: uuid.UUID, org_id: uuid.UUID
    ) -> InventoryBatch | None:
        result = await self.db.execute(
            select(InventoryBatch).where(
                InventoryBatch.id == batch_id,
                InventoryBatch.organization_id == org_id,
                InventoryBatch.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_fefo_batches(
        self,
        org_id: uuid.UUID,
        product_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
    ) -> Sequence[InventoryBatch]:
        """Return batches ordered by expiry date (FEFO — First Expired, First Out)."""
        clauses = [
            InventoryBatch.organization_id == org_id,
            InventoryBatch.product_id == product_id,
            InventoryBatch.quantity_available > 0,
            InventoryBatch.expiry_date >= date.today(),
            InventoryBatch.status == BatchStatus.ACTIVE,
            InventoryBatch.deleted_at.is_(None),
        ]
        if branch_id:
            clauses.append(InventoryBatch.branch_id == branch_id)
        result = await self.db.execute(
            select(InventoryBatch)
            .where(and_(*clauses))
            .order_by(InventoryBatch.expiry_date)
        )
        return result.scalars().all()


class NearExpiryRuleRepository(BaseRepository[NearExpiryRule]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(NearExpiryRule, db)

    async def get_by_org(self, org_id: uuid.UUID) -> NearExpiryRule | None:
        result = await self.db.execute(
            select(NearExpiryRule).where(NearExpiryRule.organization_id == org_id)
        )
        return result.scalar_one_or_none()


class InventoryMovementRepository(BaseRepository[InventoryMovement]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(InventoryMovement, db)

    async def list_by_batch(
        self,
        batch_id: uuid.UUID,
        org_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[InventoryMovement], int]:
        return await self.get_many(
            InventoryMovement.batch_id == batch_id,
            InventoryMovement.organization_id == org_id,
            offset=offset,
            limit=limit,
        )
