"""
API keys for a customer's own system.

The key is never stored. What is stored is an argon2 hash of it, exactly as with
a password, plus a short visible prefix so the customer can tell one key from
another in the list. Losing the plaintext is the point: a leaked database gives
an attacker nothing to authenticate with.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.organization import PharmacyOrganization
    from models.user import User


class ApiKeyScope(str, enum.Enum):
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"
    LISTINGS_READ = "listings:read"


class ApiKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "api_keys"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Shown in the UI so a key can be recognised: "msk_live_a1b2c3d4…".
    prefix: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Relationships ─────────────────────────────────────────────────────
    organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", foreign_keys=[organization_id], lazy="selectin"
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="selectin"
    )
