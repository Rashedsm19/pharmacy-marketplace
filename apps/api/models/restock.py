"""
Smart restock recommendations.

One row per (branch, product, kind): what the pharmacy should do with that
product right now — buy from the marketplace, list surplus before it expires,
reorder from the supplier, or hold. Rows are recomputed by the scheduler and on
demand; the unique key keeps the table small and lets a dismissal survive a
recompute.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.branch import PharmacyBranch
    from models.inventory import InventoryBatch
    from models.marketplace import MarketplaceListing
    from models.product import Product


class RestockKind(str, enum.Enum):
    REPLENISHMENT = "replenishment"
    LISTING = "listing"


class RecommendationStatus(str, enum.Enum):
    NEW = "new"
    VIEWED = "viewed"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    ACTED = "acted"
    SUPERSEDED = "superseded"


class EvidenceStrength(str, enum.Enum):
    SUFFICIENT = "sufficient"
    SPARSE = "sparse"
    INSUFFICIENT = "insufficient"


class RestockAction(str, enum.Enum):
    BUY_FROM_MARKETPLACE = "buy_from_marketplace"
    LIST_NOW = "list_now"
    HOLD = "hold"
    REORDER_SUPPLIER = "reorder_supplier"


class RestockRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "restock_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "product_id", "kind", name="uq_restock_branch_product_kind"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_branches.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    kind: Mapped[RestockKind] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[RecommendationStatus] = mapped_column(
        String(30), nullable=False, default=RecommendationStatus.NEW, index=True
    )
    action: Mapped[RestockAction] = mapped_column(String(50), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_batches.id"), nullable=True
    )
    evidence_strength: Mapped[EvidenceStrength] = mapped_column(
        String(20), nullable=False, default=EvidenceStrength.INSUFFICIENT
    )
    demand_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoming_qty: Mapped[int] = mapped_column(nullable=False, default=0)
    suggested_qty: Mapped[int] = mapped_column(nullable=False, default=0)
    suggested_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    days_of_cover: Mapped[Decimal | None] = mapped_column(Numeric(8, 1), nullable=True)
    daily_velocity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=0)
    on_hand_qty: Mapped[int] = mapped_column(nullable=False, default=0)
    nearest_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_zone: Mapped[str] = mapped_column(String(20), nullable=False, default="green")
    market_median_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    matched_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id"), nullable=True
    )
    inputs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason_ar: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reason_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    branch: Mapped["PharmacyBranch"] = relationship("PharmacyBranch", lazy="selectin")
    product: Mapped["Product"] = relationship("Product", lazy="selectin")
    batch: Mapped["InventoryBatch | None"] = relationship("InventoryBatch", lazy="selectin")
    matched_listing: Mapped["MarketplaceListing | None"] = relationship(
        "MarketplaceListing", lazy="selectin"
    )
