"""Audit log service."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.audit import AuditLog


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        notes: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            user_agent=user_agent,
            notes=notes,
        )
        self.db.add(log)
        await self.db.flush()
        return log
