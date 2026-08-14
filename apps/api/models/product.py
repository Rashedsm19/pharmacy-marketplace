"""
Product category and product models.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.inventory import InventoryBatch


class ProductCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "product_categories"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_exchange_allowed_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    requires_cold_chain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_categories.id"),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    # ── Relationships ─────────────────────────────────────────────────────
    parent: Mapped["ProductCategory | None"] = relationship(
        "ProductCategory",
        remote_side="ProductCategory.id",
        lazy="selectin",
    )
    children: Mapped[list["ProductCategory"]] = relationship(
        "ProductCategory",
        back_populates="parent",
        lazy="selectin",
    )
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="category",
        lazy="dynamic",
    )


class ProductSource(str, enum.Enum):
    """Where the product record came from."""

    CATALOG = "catalog"   # curated by the platform
    IMPORT = "import"     # created while importing a customer's stock
    API = "api"           # created by an external system syncing in


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "products"

    # A pharmacy's own product codes are its own business: two pharmacies may
    # legitimately use the same SKU for different medicines. Uniqueness is
    # therefore per owner, with NULL owner meaning the shared catalogue.
    __table_args__ = (
        Index(
            "uq_products_owner_sku",
            "owner_organization_id",
            "sku",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    # NULL = shared catalogue, visible to everyone. Set = private to that
    # organization and invisible to the rest of the market.
    owner_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=True,
        index=True,
    )
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[ProductSource] = mapped_column(
        String(20), nullable=False, default=ProductSource.CATALOG
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_categories.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="unit")
    unit_ar: Mapped[str] = mapped_column(String(50), nullable=False, default="وحدة")
    standard_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_controlled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_prescription: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    category: Mapped["ProductCategory"] = relationship(
        "ProductCategory", back_populates="products", lazy="selectin"
    )
    inventory_batches: Mapped[list["InventoryBatch"]] = relationship(
        "InventoryBatch",
        back_populates="product",
        lazy="dynamic",
    )
