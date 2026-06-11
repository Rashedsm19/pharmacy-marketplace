"""
Marketplace listing, offer, and reservation models.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.branch import PharmacyBranch
    from models.inventory import InventoryBatch
    from models.organization import PharmacyOrganization
    from models.transaction import Transaction
    from models.user import User


class ListingStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RESERVED = "reserved"
    SOLD = "sold"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OfferStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ReservationStatus(str, enum.Enum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MarketplaceListing(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "marketplace_listings"

    seller_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    seller_branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_branches.id"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_batches.id"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_ar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity_listed: Mapped[int] = mapped_column(nullable=False)
    quantity_available: Mapped[int] = mapped_column(nullable=False)
    asking_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    minimum_offer_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[ListingStatus] = mapped_column(
        String(50),
        nullable=False,
        default=ListingStatus.ACTIVE,
        index=True,
    )
    allow_offers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_partial_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_purchase_quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    eligibility_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    eligibility_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    view_count: Mapped[int] = mapped_column(nullable=False, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Relationships ─────────────────────────────────────────────────────
    seller_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", back_populates="listings", lazy="selectin"
    )
    seller_branch: Mapped["PharmacyBranch"] = relationship(
        "PharmacyBranch", back_populates="listings", lazy="selectin"
    )
    batch: Mapped["InventoryBatch"] = relationship(
        "InventoryBatch", back_populates="listings", lazy="selectin"
    )
    created_by: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="selectin"
    )
    offers: Mapped[list["ListingOffer"]] = relationship(
        "ListingOffer",
        back_populates="listing",
        lazy="dynamic",
    )
    views: Mapped[list["ListingView"]] = relationship(
        "ListingView",
        back_populates="listing",
        lazy="dynamic",
    )
    reservation: Mapped["Reservation | None"] = relationship(
        "Reservation",
        back_populates="listing",
        uselist=False,
        lazy="selectin",
    )
    transaction: Mapped["Transaction | None"] = relationship(
        "Transaction",
        back_populates="listing",
        uselist=False,
        lazy="selectin",
    )


class ListingView(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "listing_views"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listings.id"),
        nullable=False,
        index=True,
    )
    viewer_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=True,
    )
    viewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    listing: Mapped["MarketplaceListing"] = relationship(
        "MarketplaceListing", back_populates="views"
    )


class ListingOffer(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "listing_offers"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listings.id"),
        nullable=False,
        index=True,
    )
    buyer_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    submitted_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    offered_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[OfferStatus] = mapped_column(
        String(50),
        nullable=False,
        default=OfferStatus.PENDING,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────
    listing: Mapped["MarketplaceListing"] = relationship(
        "MarketplaceListing", back_populates="offers"
    )
    buyer_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization",
        foreign_keys=[buyer_organization_id],
        lazy="selectin",
    )
    submitted_by: Mapped["User"] = relationship(
        "User", foreign_keys=[submitted_by_id], lazy="selectin"
    )


class Reservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reservations"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listings.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listing_offers.id"),
        nullable=True,
    )
    buyer_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    reserved_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    agreed_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        String(50),
        nullable=False,
        default=ReservationStatus.ACTIVE,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    listing: Mapped["MarketplaceListing"] = relationship(
        "MarketplaceListing", back_populates="reservation"
    )
    offer: Mapped["ListingOffer | None"] = relationship(
        "ListingOffer", foreign_keys=[offer_id], lazy="selectin"
    )
    buyer_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization",
        foreign_keys=[buyer_organization_id],
        lazy="selectin",
    )
    reserved_by: Mapped["User"] = relationship(
        "User", foreign_keys=[reserved_by_id], lazy="selectin"
    )
