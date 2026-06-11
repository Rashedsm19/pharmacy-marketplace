"""
Transaction model.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.marketplace import MarketplaceListing, Reservation
    from models.organization import PharmacyOrganization
    from models.user import User


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "transactions"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listings.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reservations.id"),
        nullable=True,
    )
    seller_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    buyer_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    platform_fee: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        String(50),
        nullable=False,
        default=TransactionStatus.PENDING,
        index=True,
    )
    reference_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatched_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    delivery_tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    seller_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    buyer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispute_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    listing: Mapped["MarketplaceListing"] = relationship(
        "MarketplaceListing", back_populates="transaction", lazy="selectin"
    )
    reservation: Mapped["Reservation | None"] = relationship(
        "Reservation", foreign_keys=[reservation_id], lazy="selectin"
    )
    seller_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization",
        foreign_keys=[seller_organization_id],
        lazy="selectin",
    )
    buyer_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization",
        foreign_keys=[buyer_organization_id],
        lazy="selectin",
    )
    dispatched_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[dispatched_by_id], lazy="selectin"
    )
    received_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[received_by_id], lazy="selectin"
    )
