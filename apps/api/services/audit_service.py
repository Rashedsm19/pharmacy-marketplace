"""Audit log service."""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from auth.context import actor_context

from models.audit import AuditLog


def json_safe(value: Any) -> Any:
    """Coerce a value into something JSONB can hold.

    Before/after states are built by handlers out of whatever the model exposes,
    so a date, UUID, Decimal or enum arrives sooner or later; asyncpg raises on
    those and the audit write takes the whole request down with it. Auditing must
    never be the reason an operation fails.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, enum.Enum):
        return json_safe(value.value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


def _with_actor(notes: str | None, context) -> str | None:
    """Stamp an impersonated action with the administrator really behind it."""
    if context is None or not context.is_impersonated:
        return notes
    stamp = f"[نفّذه الدعم: {context.impersonator_email} — جلسة {context.session_id}]"
    return f"{notes} {stamp}" if notes else stamp


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
        # If support is operating inside a customer's account, say so on the row
        # itself. The actor stays the customer — that is who the action was
        # performed as, and it is what every existing caller passes — but an
        # entry that does not reveal the platform was driving would make this
        # trail less trustworthy than it was before impersonation existed.
        context = actor_context.get()
        notes = _with_actor(notes, context)

        log = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=json_safe(before_state),
            after_state=json_safe(after_state),
            ip_address=ip_address,
            user_agent=user_agent,
            notes=notes,
        )
        self.db.add(log)
        await self.db.flush()
        return log
