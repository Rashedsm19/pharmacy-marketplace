"""
A record of support entering a customer's account.

The session row is what makes "end impersonation" mean something. Without it,
leaving would be a gesture in the browser and the token would keep working until
it expired — a laptop left open would hold write access to a pharmacy's account.
With it, `ended_at` is a real kill switch, checked on every request.

The foreign keys are nullable and every name is also stored as text, so that
purging an organization later can detach the row instead of destroying the
evidence that support was inside that account.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ImpersonationSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "impersonation_sessions"
    __table_args__ = (
        # The worker question is "who is inside someone's account right now".
        Index("ix_impersonation_open", "ended_at"),
    )

    admin_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)

    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    target_email: Mapped[str] = mapped_column(String(255), nullable=False)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=True
    )
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
