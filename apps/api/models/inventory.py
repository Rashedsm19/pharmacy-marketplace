"""
Inventory batch, near-expiry rules, and inventory movement models.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class BatchStatus(str, enum.Enum):
    ACTIVE = "active"
    NEAR_EXPIRY = "near_expiry"
    EXPIRED = "expired"
    LISTED = "listed"
    SOLD = "sold"
    DISPOSED = "disposed"


class MovementType(str, enum.Enum):
    RECEIVED = "received"
    DISPENSED = "dispensed"
    TRANSFERRED = "transferred"
    LISTED = "listed"
    SOLD = "sold"
    DISPOSED = "disposed"
    ADJUSTED = "adjusted"


class InventoryBatch(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "inventory_batches"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_branches.id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id"),
        nullable=False,
        index=True,
    )
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=0)
    quantity_available: Mapped[int] = mapped_column(nullable=False, default=0)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purchase_order_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[BatchStatus] = mapped_column(
        String(50),
        nullable=False,
        default=BatchStatus.ACTIVE,
        index=True,
    )
    is_opened: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_patient_dispensed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage_condition_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="compliant"
    )
    storage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_cold_chain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Notification tracking
    notified_180: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notified_90: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notified_30: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Relationships ─────────────────────────────────────────────────────
    organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization",
        foreign_keys=[organization_id],
        lazy="selectin",
    )
    branch: Mapped["PharmacyBranch"] = relationship(
        "PharmacyBranch", back_populates="inventory_batches", lazy="selectin"
    )
    product: Mapped["Product"] = relationship(
        "Product", back_populates="inventory_batches", lazy="selectin"
    )
    listings: Mapped[list["MarketplaceListing"]] = relationship(
        "MarketplaceListing",
        back_populates="batch",
        lazy="dynamic",
    )
    movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        back_populates="batch",
        lazy="dynamic",
    )


class NearExpiryRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "near_expiry_rules"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    min_days_for_listing: Mapped[int] = mapped_column(nullable=False, default=30)
    yellow_threshold_days: Mapped[int] = mapped_column(nullable=False, default=180)
    orange_threshold_days: Mapped[int] = mapped_column(nullable=False, default=90)
    red_threshold_days: Mapped[int] = mapped_column(nullable=False, default=30)
    allow_auto_listing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_listing_discount_pct: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=20.0
    )
    notify_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Relationships ─────────────────────────────────────────────────────
    organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", back_populates="near_expiry_rules"
    )


class InventoryMovement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inventory_movements"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_batches.id"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[MovementType] = mapped_column(
        String(50), nullable=False
    )
    quantity_delta: Mapped[int] = mapped_column(nullable=False)
    quantity_before: Mapped[int] = mapped_column(nullable=False)
    quantity_after: Mapped[int] = mapped_column(nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    performed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    batch: Mapped["InventoryBatch"] = relationship(
        "InventoryBatch", back_populates="movements"
    )
    performed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[performed_by_id], lazy="selectin"
    )
