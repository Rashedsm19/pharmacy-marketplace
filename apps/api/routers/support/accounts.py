"""Support console — customer accounts."""
from __future__ import annotations


import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select

from dependencies import DbSession, SuperAdmin
from models.organization import (
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.user import User, UserRole
from schemas.support import (
    AdminUserList,
    AdminUserRow,
    ReasonIn,
    ResetLinkOut,
    UserPatchIn,
)
from services.audit_service import AuditService

from routers.support.helpers import _client, _guard, _load_user, _org_of, _row

router = APIRouter()


# ── Customer accounts ─────────────────────────────────────────────────────────

@router.get("/users", response_model=AdminUserList)
async def list_users(
    db: DbSession,
    current_user: SuperAdmin,
    search: str | None = None,
    role: str | None = None,
    organization_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = Query(default=25, ge=1, le=200),
) -> AdminUserList:
    """Every account on the platform, with the pharmacy it belongs to."""
    page = max(page, 1)

    # One membership per user, chosen the same way login chooses it.
    membership = (
        select(
            UserOrganizationMembership.user_id,
            UserOrganizationMembership.organization_id,
            UserOrganizationMembership.role.label("membership_role"),
            func.row_number()
            .over(
                partition_by=UserOrganizationMembership.user_id,
                order_by=(
                    UserOrganizationMembership.joined_at,
                    UserOrganizationMembership.created_at,
                ),
            )
            .label("rank"),
        )
        .where(UserOrganizationMembership.is_active.is_(True))
        .subquery()
    )
    primary = select(membership).where(membership.c.rank == 1).subquery()

    conditions = []
    if not include_deleted:
        conditions.append(User.deleted_at.is_(None))
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))
    if role:
        conditions.append(User.role == role)
    if organization_id:
        conditions.append(primary.c.organization_id == organization_id)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(User.email.ilike(pattern), User.full_name.ilike(pattern))
        )

    base = (
        select(User, PharmacyOrganization, primary.c.membership_role)
        .outerjoin(primary, primary.c.user_id == User.id)
        .outerjoin(
            PharmacyOrganization,
            PharmacyOrganization.id == primary.c.organization_id,
        )
        .where(*conditions)
    )

    total = int(
        await db.scalar(
            select(func.count())
            .select_from(User)
            .outerjoin(primary, primary.c.user_id == User.id)
            .where(*conditions)
        )
        or 0
    )
    rows = (
        await db.execute(
            base.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return AdminUserList(
        items=[_row(user, organization, role_) for user, organization, role_ in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/users/{user_id}", response_model=AdminUserRow)
async def get_user(
    user_id: uuid.UUID, db: DbSession, current_user: SuperAdmin
) -> AdminUserRow:
    user = await _load_user(db, user_id, allow_deleted=True)
    organization, membership_role = await _org_of(db, user.id)
    return _row(user, organization, membership_role)


@router.post("/users/{user_id}/reset-link", response_model=ResetLinkOut)
async def issue_reset_link(
    user_id: uuid.UUID,
    payload: ReasonIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> ResetLinkOut:
    """Issue a password-reset link for a customer and hand it to support.

    The link is emailed, and also returned once so support can pass it on by
    phone or WhatsApp — which matters because email delivery is not configured
    on this deployment, and a link nobody receives helps nobody.
    """
    from config import settings
    from services.auth_service import AuthService

    user = await _load_user(db, user_id)
    _guard(current_user, user, "reset")

    token, expires_at, sent = await AuthService(db).issue_password_reset(
        user, ttl_minutes=settings.ADMIN_RESET_LINK_TTL_MINUTES
    )
    reset_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/ar/reset-password?token={token}"
    )

    organization, _ = await _org_of(db, user.id)
    await AuditService(db).log(
        action="support.user.reset_link",
        resource_type="user",
        resource_id=user.id,
        actor_id=current_user.id,
        organization_id=organization.id if organization else None,
        # Never the token or the URL: the audit trail must not become a way to
        # take over the account it is recording.
        after_state={"expires_at": expires_at.isoformat(), "email_sent": sent},
        notes=payload.reason,
        **_client(request),
    )

    return ResetLinkOut(
        reset_url=reset_url,
        expires_at=expires_at,
        email_sent=sent,
        notice=(
            "أرسل الرابط إلى بريد العميل."
            if sent
            else "خدمة البريد غير مفعلة — انسخ الرابط وأرسله للعميل بنفسك."
        ),
    )


@router.patch("/users/{user_id}", response_model=AdminUserRow)
async def patch_user(
    user_id: uuid.UUID,
    payload: UserPatchIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> AdminUserRow:
    user = await _load_user(db, user_id)
    before = {
        "full_name": user.full_name,
        "phone": user.phone,
        "role": str(getattr(user.role, "value", user.role)),
    }

    if payload.role is not None and payload.role != before["role"]:
        _guard(current_user, user, "role")
        try:
            new_role = UserRole(payload.role)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"دور غير معروف: {payload.role}",
            ) from exc
        if new_role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ترقية حساب إلى مدير منصة لا تتم من وحدة الدعم",
            )
        user.role = new_role

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        user.phone = payload.phone

    await db.flush()
    organization, membership_role = await _org_of(db, user.id)
    await AuditService(db).log(
        action="support.user.update",
        resource_type="user",
        resource_id=user.id,
        actor_id=current_user.id,
        organization_id=organization.id if organization else None,
        before_state=before,
        after_state={
            "full_name": user.full_name,
            "phone": user.phone,
            "role": str(getattr(user.role, "value", user.role)),
        },
        notes=payload.reason,
        **_client(request),
    )
    return _row(user, organization, membership_role)


@router.post("/users/{user_id}/deactivate", response_model=AdminUserRow)
async def deactivate_user(
    user_id: uuid.UUID,
    payload: ReasonIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> AdminUserRow:
    """Disable an account. This takes effect on the customer's very next request."""
    user = await _load_user(db, user_id)
    _guard(current_user, user, "deactivate")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="الحساب معطل بالفعل"
        )

    user.is_active = False
    await db.flush()
    organization, membership_role = await _org_of(db, user.id)
    await AuditService(db).log(
        action="support.user.deactivate",
        resource_type="user",
        resource_id=user.id,
        actor_id=current_user.id,
        organization_id=organization.id if organization else None,
        before_state={"is_active": True},
        after_state={"is_active": False},
        notes=payload.reason,
        **_client(request),
    )
    return _row(user, organization, membership_role)


@router.post("/users/{user_id}/activate", response_model=AdminUserRow)
async def activate_user(
    user_id: uuid.UUID,
    payload: ReasonIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> AdminUserRow:
    user = await _load_user(db, user_id)
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="الحساب نشط بالفعل"
        )

    user.is_active = True
    await db.flush()
    organization, membership_role = await _org_of(db, user.id)
    await AuditService(db).log(
        action="support.user.activate",
        resource_type="user",
        resource_id=user.id,
        actor_id=current_user.id,
        organization_id=organization.id if organization else None,
        before_state={"is_active": False},
        after_state={"is_active": True},
        notes=payload.reason,
        **_client(request),
    )
    return _row(user, organization, membership_role)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
    reason: str = Query(min_length=5, max_length=500),
    force: bool = False,
) -> dict:
    """Soft-delete an account and release its email address.

    The email is released deliberately. `users.email` is UNIQUE and the
    constraint counts soft-deleted rows, so without this a departing pharmacist
    could never be re-registered on the same corporate address — a support
    ticket waiting to happen. The original is kept on the row so a restore can
    put it back.
    """
    user = await _load_user(db, user_id)
    _guard(current_user, user, "delete")

    organization, membership_role = await _org_of(db, user.id)

    # A pharmacy with no one able to sign in is a pharmacy that has to call
    # support to get back in. Refuse unless that is what was intended.
    if organization is not None and membership_role == "owner" and not force:
        remaining = int(
            await db.scalar(
                select(func.count(User.id))
                .join(
                    UserOrganizationMembership,
                    UserOrganizationMembership.user_id == User.id,
                )
                .where(
                    UserOrganizationMembership.organization_id == organization.id,
                    UserOrganizationMembership.is_active.is_(True),
                    User.id != user.id,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
            )
            or 0
        )
        if remaining == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "هذا آخر حساب فعال في المنشأة — حذفه يترك العميل بلا دخول. "
                    "أضف force=true إن كنت متأكدا."
                ),
            )

    before = {"email": user.email, "is_active": user.is_active}
    now = datetime.now(timezone.utc)

    user.former_email = user.email
    user.email = f"{uuid.uuid4().hex}+deleted@medsave.invalid"
    user.is_active = False
    user.deleted_at = now

    await db.execute(
        UserOrganizationMembership.__table__.update()
        .where(UserOrganizationMembership.user_id == user.id)
        .values(is_active=False)
    )
    await db.flush()

    await AuditService(db).log(
        action="support.user.delete",
        resource_type="user",
        resource_id=user.id,
        actor_id=current_user.id,
        organization_id=organization.id if organization else None,
        before_state=before,
        after_state={"deleted_at": now.isoformat(), "email_released": True},
        notes=reason,
        **_client(request),
    )
    return {
        "id": str(user.id),
        "deleted": True,
        "message": f"حذف الحساب وأتيح البريد {before['email']} للتسجيل من جديد",
    }


@router.post("/users/{user_id}/restore", response_model=AdminUserRow)
async def restore_user(
    user_id: uuid.UUID,
    payload: ReasonIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> AdminUserRow:
    """Undo a deletion, provided the address has not been taken meanwhile."""
    user = await _load_user(db, user_id, allow_deleted=True)
    if user.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="الحساب غير محذوف"
        )

    address = user.former_email or user.email
    taken = await db.scalar(
        select(User.id).where(User.email == address, User.id != user.id).limit(1)
    )
    if taken is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"البريد {address} صار مستخدما لحساب آخر — لا يمكن الاستعادة",
        )

    user.email = address
    user.former_email = None
    user.deleted_at = None
    user.is_active = True
    await db.execute(
        UserOrganizationMembership.__table__.update()
        .where(UserOrganizationMembership.user_id == user.id)
        .values(is_active=True)
    )
    await db.flush()

    organization, membership_role = await _org_of(db, user.id)
    await AuditService(db).log(
        action="support.user.restore",
        resource_type="user",
        resource_id=user.id,
        actor_id=current_user.id,
        organization_id=organization.id if organization else None,
        after_state={"email": user.email, "is_active": True},
        notes=payload.reason,
        **_client(request),
    )
    return _row(user, organization, membership_role)


