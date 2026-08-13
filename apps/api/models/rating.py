"""
Counterparty ratings.

In a market between strangers, reputation is what makes the first trade
possible. A rating is only meaningful if it is earned, so one may be left only
after a transaction completes, once per party per transaction.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.organization import PharmacyOrganization
    from models.transaction import Transaction
    from models.user import User


class Rating(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ratings"

    # One rating per transaction per rating organization — enforced in the
    # database so a double submission cannot slip through a race.
    __table_args__ = (
        Index(
            "uq_ratings_transaction_rater",
            "transaction_id",
            "rater_organization_id",
            unique=True,
        ),
    )

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True
    )
    rater_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )
    rated_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )
    rated_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", foreign_keys=[transaction_id], lazy="selectin"
    )
    rater_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", foreign_keys=[rater_organization_id], lazy="selectin"
    )
    rated_organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", foreign_keys=[rated_organization_id], lazy="selectin"
    )
    rated_by: Mapped["User"] = relationship("User", foreign_keys=[rated_by_id], lazy="selectin")
