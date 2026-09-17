"""
Wallet, ledger, top-ups, withdrawals and platform revenue.

Every riyal a pharmacy holds on the platform lives in one wallet per
organization. Nothing changes a balance except a ledger entry: an escrow hold
moves money from `balance` to `held_balance`, a capture moves it from the
buyer's held funds to the seller, and the platform's commission is recorded
against `platform_revenue` at the same moment. The ledger is append-only and
each entry carries an idempotency key, so a retried request cannot move the
same money twice.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.organization import PharmacyOrganization
    from models.user import User


class WalletEntryType(str, enum.Enum):
    TOPUP = "topup"
    HOLD = "hold"
    RELEASE = "release"
    CAPTURE = "capture"
    FEE = "fee"
    REFUND = "refund"
    WITHDRAWAL = "withdrawal"
    LOYALTY_CREDIT = "loyalty_credit"
    SUBSCRIPTION_CHARGE = "subscription_charge"
    INSURANCE_PREMIUM = "insurance_premium"
    POS_SALE = "pos_sale"
    ADJUSTMENT = "adjustment"


class TopupStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class WithdrawalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class RevenueKind(str, enum.Enum):
    COMMISSION = "commission"
    SUBSCRIPTION = "subscription"
    INSURANCE_MARGIN = "insurance_margin"
    WITHDRAWAL_FEE = "withdrawal_fee"


class Wallet(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "wallets"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pharmacy_organizations.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    held_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", lazy="selectin"
    )
    entries: Mapped[list["WalletEntry"]] = relationship(
        "WalletEntry", back_populates="wallet", lazy="noload"
    )


class WalletEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "wallet_entries"

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False, index=True
    )
    entry_type: Mapped[WalletEntryType] = mapped_column(String(30), nullable=False, index=True)
    # Signed: negative leaves the available balance, positive enters it.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    held_after: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="entries")
    created_by: Mapped["User | None"] = relationship("User", lazy="selectin")


class WalletTopup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "wallet_topups"

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True, index=True
    )
    status: Mapped[TopupStatus] = mapped_column(
        String(20), nullable=False, default=TopupStatus.PENDING, index=True
    )
    redirect_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", lazy="selectin")


class WithdrawalRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "withdrawal_requests"

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    iban: Mapped[str] = mapped_column(String(34), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[WithdrawalStatus] = mapped_column(
        String(20), nullable=False, default=WithdrawalStatus.PENDING, index=True
    )
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    wallet: Mapped["Wallet"] = relationship("Wallet", lazy="selectin")
    reviewed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by_id], lazy="selectin"
    )


class PlatformRevenue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "platform_revenue"

    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=True, index=True
    )
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    kind: Mapped[RevenueKind] = mapped_column(String(30), nullable=False, index=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
