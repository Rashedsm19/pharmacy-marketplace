"""Helpers shared by the support console routers.

The guard rules live here rather than in any one module because every support
action is subject to them: an action on another account has to name the actor,
name a reason, and refuse with an explanation rather than a silent no-op.
"""
from __future__ import annotations


import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from models.organization import (
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.user import User, UserRole
from schemas.support import (
    AdminUserRow,
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _client(request: Request) -> dict:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


async def _load_user(db, user_id: uuid.UUID, *, allow_deleted: bool = False) -> User:
    user = await db.get(User, user_id)
    if user is None or (user.deleted_at is not None and not allow_deleted):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="المستخدم غير موجود"
        )
    return user


def _guard(admin: User, target: User, action: str) -> None:
    """Refuse the actions that would lock support out or breach a peer account.

    A platform administrator is not a customer: their account is not support's
    to reset or disable. With one administrator today this is theoretical; the
    day there are two, "support" must not be the route to seizing a colleague's
    account. The legitimate paths remain self-service password reset and the
    out-of-band `seeds.create_superadmin` script.
    """
    if target.id == admin.id and action in {"deactivate", "delete"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكنك تعطيل حسابك أو حذفه",
        )
    if target.role == UserRole.SUPER_ADMIN and action in {
        "reset",
        "deactivate",
        "delete",
        "role",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب مدير المنصة لا يدار من وحدة الدعم",
        )


async def _org_of(db, user_id: uuid.UUID) -> tuple[PharmacyOrganization | None, str | None]:
    """The pharmacy a user belongs to, and their role in it."""
    row = (
        await db.execute(
            select(PharmacyOrganization, UserOrganizationMembership.role)
            .join(
                UserOrganizationMembership,
                UserOrganizationMembership.organization_id == PharmacyOrganization.id,
            )
            .where(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.is_active.is_(True),
            )
            # Deterministic: the console and the login token must never disagree
            # about which pharmacy a multi-org user belongs to.
            .order_by(UserOrganizationMembership.joined_at, UserOrganizationMembership.created_at)
            .limit(1)
        )
    ).first()
    if row is None:
        return None, None
    return row[0], str(getattr(row[1], "value", row[1]))


def _row(user: User, organization, membership_role) -> AdminUserRow:
    return AdminUserRow(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=str(getattr(user.role, "value", user.role)),
        is_active=user.is_active,
        is_deleted=user.deleted_at is not None,
        is_email_verified=user.is_email_verified,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        organization_id=organization.id if organization else None,
        organization_name=(organization.name_ar or organization.name)
        if organization
        else None,
        organization_status=str(getattr(organization.status, "value", organization.status))
        if organization
        else None,
        membership_role=membership_role,
    )

