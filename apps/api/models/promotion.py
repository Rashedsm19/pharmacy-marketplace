"""
Promotional offers: a seller's rule for lowering the price a buyer pays when
they buy at asking price, and the record of every time a rule was applied.

A promotion belongs to an organization and optionally to a single listing;
with no listing it covers every listing the organization has. The rule body
is JSON whose shape depends on `type` and is validated in schemas/promotion.py
before it ever reaches this table.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.marketplace import MarketplaceListing
    from models.organization import PharmacyOrganization


class PromotionType(str, enum.Enum):
    BOGO = "bogo"
    BUNDLE = "bundle"
    QUANTITY_TIER = "quantity_tier"
    THRESHOLD_DISCOUNT = "threshold_discount"
    EXPIRY_DYNAMIC = "expiry_dynamic"


class Promotion(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "promotions"
    __table_args__ = (
        Index("ix_promotions_org_active", "organization_id", "is_active"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[PromotionType] = mapped_column(String(30), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_redemptions: Mapped[int | None] = mapped_column(nullable=True)
    redemption_count: Mapped[int] = mapped_column(nullable=False, default=0)

    organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", lazy="selectin"
    )
    listing: Mapped["MarketplaceListing | None"] = relationship(
        "MarketplaceListing", lazy="selectin"
    )
    redemptions: Mapped[list["PromotionRedemption"]] = relationship(
        "PromotionRedemption", back_populates="promotion", lazy="noload"
    )


class PromotionRedemption(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "promotion_redemptions"
    __table_args__ = (
        Index("ix_promotion_redemptions_ref", "reference_type", "reference_id"),
    )

    promotion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("promotions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # reservation | pos_sale | quote — what the discount was granted on
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    promotion: Mapped["Promotion"] = relationship("Promotion", back_populates="redemptions")
