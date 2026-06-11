"""
Notification and notification preference models.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.user import User


class NotificationType(str, enum.Enum):
    NEAR_EXPIRY_180 = "near_expiry_180"
    NEAR_EXPIRY_90 = "near_expiry_90"
    NEAR_EXPIRY_30 = "near_expiry_30"
    LISTING_CREATED = "listing_created"
    LISTING_CANCELLED = "listing_cancelled"
    OFFER_RECEIVED = "offer_received"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_REJECTED = "offer_rejected"
    OFFER_CANCELLED = "offer_cancelled"
    RESERVATION_CREATED = "reservation_created"
    RESERVATION_EXPIRED = "reservation_expired"
    TRANSACTION_DISPATCHED = "transaction_dispatched"
    TRANSACTION_RECEIVED = "transaction_received"
    TRANSACTION_COMPLETED = "transaction_completed"
    ORG_APPROVED = "org_approved"
    ORG_REJECTED = "org_rejected"
    ORG_SUSPENDED = "org_suspended"
    SYSTEM = "system"


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=True,
        index=True,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_ar: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="notifications")


class NotificationPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        String(50),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        String(50),
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User", back_populates="notification_preferences"
    )
