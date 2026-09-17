"""
Roles a pharmacy defines for its own staff, and the invitations that bring
staff in.

A role is a named bundle of permission keys owned by one organization. The four
system roles are created for every organization the first time it is looked at,
so a membership that predates this table keeps working through its legacy
`role` column until it is pointed at a row here.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.organization import PharmacyOrganization
    from models.user import User


class InviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OrgRole(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "org_roles"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_org_roles_org_key"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The system roles mirror the legacy membership roles and cannot be deleted.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permissions: Mapped[list[str]] = mapped_column(
        ARRAY(String(60)), nullable=False, default=list
    )

    organization: Mapped["PharmacyOrganization"] = relationship("PharmacyOrganization")


class TeamInvite(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "team_invites"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_roles.id"), nullable=False
    )
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Only the hash is stored; the token itself goes out in the email once.
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[InviteStatus] = mapped_column(
        String(20), nullable=False, default=InviteStatus.PENDING
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["PharmacyOrganization"] = relationship("PharmacyOrganization")
    role: Mapped["OrgRole"] = relationship("OrgRole", lazy="selectin")
    invited_by: Mapped["User"] = relationship("User", foreign_keys=[invited_by_id], lazy="selectin")
