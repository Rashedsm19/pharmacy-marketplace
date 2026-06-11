"""
Pharmacy branch model.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.inventory import InventoryBatch
    from models.marketplace import MarketplaceListing
    from models.organization import PharmacyOrganization


class StorageConditionStatus(str, enum.Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"
    UNKNOWN = "unknown"


class PharmacyBranch(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pharmacy_branches"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branch_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_condition_status: Mapped[StorageConditionStatus] = mapped_column(
        String(50),
        nullable=False,
        default=StorageConditionStatus.UNKNOWN,
    )
    storage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cold_chain_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    narcotics_license: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Relationships ─────────────────────────────────────────────────────
    organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", back_populates="branches"
    )
    inventory_batches: Mapped[list["InventoryBatch"]] = relationship(
        "InventoryBatch",
        back_populates="branch",
        lazy="dynamic",
    )
    listings: Mapped[list["MarketplaceListing"]] = relationship(
        "MarketplaceListing",
        back_populates="seller_branch",
        lazy="dynamic",
    )
