"""Audit log repository."""
from __future__ import annotations

import uuid
from typing import Sequence

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
        return await self.get_many(*clauses, offset=offset, limit=limit)
