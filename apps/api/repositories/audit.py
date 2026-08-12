"""Audit log repository."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.audit import AuditLog
from repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(AuditLog, db)

    async def list_filtered(
        self,
        org_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[AuditLog], int]:
        clauses = []
        if org_id:
            clauses.append(AuditLog.organization_id == org_id)
        if actor_id:
            clauses.append(AuditLog.actor_id == actor_id)
        if action:
            clauses.append(AuditLog.action == action)
        if resource_type:
            clauses.append(AuditLog.resource_type == resource_type)
        if resource_id:
            clauses.append(AuditLog.resource_id == resource_id)

        count_stmt = select(func.count()).select_from(AuditLog).where(*clauses)
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Newest first, with id as a tiebreaker — an unordered audit trail also
        # makes pagination non-deterministic (rows repeating or being skipped).
        stmt = (
            select(AuditLog)
            .where(*clauses)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return rows, total
