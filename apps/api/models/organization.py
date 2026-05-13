"""
Pharmacy organization and membership models.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class MembershipRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    PHARMACIST = "pharmacist"
    VIEWER = "viewer"


class PharmacyOrganization(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pharmacy_organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commercial_registration_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    license_number: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    is_licensed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[OrganizationStatus] = mapped_column(
        String(50),
        nullable=False,
        default=OrganizationStatus.PENDING,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_doc_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cr_doc_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_auto_listing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    approved_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by_id],
        lazy="selectin",
    )
    branches: Mapped[list["PharmacyBranch"]] = relationship(
        "PharmacyBranch",
        back_populates="organization",
        lazy="selectin",
    )
    memberships: Mapped[list["UserOrganizationMembership"]] = relationship(
        "UserOrganizationMembership",
        back_populates="organization",
        lazy="selectin",
    )
    near_expiry_rules: Mapped[list["NearExpiryRule"]] = relationship(
        "NearExpiryRule",
        back_populates="organization",
        lazy="selectin",
    )
    listings: Mapped[list["MarketplaceListing"]] = relationship(
        "MarketplaceListing",
        back_populates="seller_organization",
        lazy="dynamic",
    )


class UserOrganizationMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_organization_memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[MembershipRole] = mapped_column(
        String(50),
        nullable=False,
        default=MembershipRole.PHARMACIST,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", back_populates="memberships"
    )
