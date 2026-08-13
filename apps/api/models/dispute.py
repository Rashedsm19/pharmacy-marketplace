"""
Disputes raised against a completed or in-flight transaction.

The cycle used to end at "receipt confirmed" with no way to say the goods arrived
short, damaged, or suspect. This is that path: the buyer opens a case with
evidence, the seller answers, and a platform admin decides — with the stock and
the money moved to match the decision.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.organization import PharmacyOrganization
    from models.transaction import Transaction
    from models.user import User


class DisputeReason(str, enum.Enum):
    QUANTITY_SHORT = "quantity_short"
    DAMAGED = "damaged"
    WRONG_PRODUCT = "wrong_product"
    EXPIRY_MISMATCH = "expiry_mismatch"
    COLD_CHAIN_BREACH = "cold_chain_breach"
    SUSPECTED_COUNTERFEIT = "suspected_counterfeit"
    NOT_RECEIVED = "not_received"
    OTHER = "other"


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    SELLER_RESPONDED = "seller_responded"
    RESOLVED_REFUND = "resolved_refund"
    RESOLVED_REPLACEMENT = "resolved_replacement"
    RESOLVED_REJECTED = "resolved_rejected"
    WITHDRAWN = "withdrawn"


# A counterfeit claim is not an ordinary commercial disagreement: it suspends the
# seller immediately and is escalated, per the practice of comparable marketplaces.
CRITICAL_REASONS = frozenset({DisputeReason.SUSPECTED_COUNTERFEIT})


class Dispute(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "disputes"

    # One live case per transaction — closed ones may repeat if a second problem
    # surfaces later.
    __table_args__ = (
        Index(
            "uq_disputes_open_per_transaction",
            "transaction_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'seller_responded')"),
        ),
    )

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True
    )
    raised_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    raised_by_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )

    reason: Mapped[DisputeReason] = mapped_column(String(40), nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(
        String(30), nullable=False, default=DisputeStatus.OPEN, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # How many units the claim covers; a partial shortfall refunds only its share.
    disputed_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    seller_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refund_amount: Mapped[float | None] = mapped_column(nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="disputes", lazy="selectin"
    )
    raised_by: Mapped["User"] = relationship(
        "User", foreign_keys=[raised_by_id], lazy="selectin"
    )
    raised_by_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", foreign_keys=[raised_by_organization_id], lazy="selectin"
    )
    resolved_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[resolved_by_id], lazy="selectin"
    )
