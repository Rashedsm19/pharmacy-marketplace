"""
Tax invoices.

Every sale between two organizations is a B2B supply, and in Saudi Arabia the
tax invoice must be cleared by ZATCA before it is handed to the buyer. This
table is the record of that: the generated document, its place in the hash
chain, and what the authority answered.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.organization import PharmacyOrganization
    from models.transaction import Transaction


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    # Waiting for the authority; the sale is complete either way.
    PENDING_CLEARANCE = "pending_clearance"
    CLEARED = "cleared"
    REJECTED = "rejected"
    FAILED = "failed"


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "invoices"

    # The counter is unique per seller — a duplicate would break the chain in a
    # way that cannot be corrected after the fact.
    __table_args__ = (
        Index("uq_invoices_seller_icv", "seller_organization_id", "icv", unique=True),
    )

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, unique=True, index=True
    )
    seller_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )
    buyer_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )

    invoice_number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    invoice_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    # Invoice Counter Value: strictly sequential per seller, never reused.
    icv: Mapped[int] = mapped_column(Integer, nullable=False)
    # Previous Invoice Hash — what makes the sequence tamper-evident.
    previous_hash: Mapped[str] = mapped_column(Text, nullable=False)
    invoice_hash: Mapped[str] = mapped_column(Text, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    vat_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    vat_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    total_with_vat: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    xml_content: Mapped[str] = mapped_column(Text, nullable=False)
    qr_code: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[InvoiceStatus] = mapped_column(
        String(30), nullable=False, default=InvoiceStatus.DRAFT, index=True
    )
    clearance_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", foreign_keys=[transaction_id], lazy="selectin"
    )
    seller_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", foreign_keys=[seller_organization_id], lazy="selectin"
    )
    buyer_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", foreign_keys=[buyer_organization_id], lazy="selectin"
    )
