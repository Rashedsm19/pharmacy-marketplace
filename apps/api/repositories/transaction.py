"""Transaction repository."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.transaction import Transaction, TransactionStatus
from repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Transaction, db)

    async def get_by_ref(self, reference_number: str) -> Transaction | None:
        result = await self.db.execute(
            select(Transaction).where(Transaction.reference_number == reference_number)
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        as_seller: bool = True,
        as_buyer: bool = True,
        status: TransactionStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Transaction], int]:
        clauses = []
        if as_seller and as_buyer:
            clauses.append(
                or_(
                    Transaction.seller_organization_id == org_id,
                    Transaction.buyer_organization_id == org_id,
                )
            )
        elif as_seller:
            clauses.append(Transaction.seller_organization_id == org_id)
        elif as_buyer:
            clauses.append(Transaction.buyer_organization_id == org_id)
        if status:
            clauses.append(Transaction.status == status)
        return await self.get_many(*clauses, offset=offset, limit=limit)

    async def get_by_listing(self, listing_id: uuid.UUID) -> Transaction | None:
        result = await self.db.execute(
            select(Transaction).where(Transaction.listing_id == listing_id)
        )
        return result.scalar_one_or_none()
