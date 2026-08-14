"""
The platform support console.

One person is the entire support function for this platform, so these endpoints
exist to let them do for a customer what the customer cannot do for themselves:
look up an account, issue a reset link, disable someone who has left, remove a
listing that should not be public, and delete stock that got in by mistake.

Two rules run through all of it. Every action names a reason and lands in the
audit trail, because acting on someone else's data has to be answerable. And
every guard is a refusal with an explanation rather than a silent no-op — a
support tool that quietly does nothing is worse than one that says why it won't.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select

from dependencies import DbSession, SuperAdmin
from models.branch import PharmacyBranch
from models.inventory import BatchStatus, InventoryBatch
from models.marketplace import (
    ListingStatus,
    MarketplaceListing,
    Reservation,
    ReservationStatus,
)
from models.organization import (
    OrganizationStatus,
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.product import Product
from models.transaction import Transaction
from models.user import User, UserRole
from schemas.support import (
    AdminUserList,
    AdminUserRow,
    BatchDeleteOut,
    ListingRemoveIn,
    ReasonIn,
    ResetLinkOut,
    UserPatchIn,
)
from services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["Support console"])


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
            detail="حساب مدير المنصة لا يُدار من وحدة الدعم",
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
            "أُرسل الرابط إلى بريد العميل."
            if sent
            else "خدمة البريد غير مُفعّلة — انسخ الرابط وأرسله للعميل بنفسك."
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
            status_code=status.HTTP_409_CONFLICT, detail="الحساب معطّل بالفعل"
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
                    "هذا آخر حساب فعّال في المنشأة — حذفه يترك العميل بلا دخول. "
                    "أضف force=true إن كنت متأكداً."
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
        "message": f"حُذف الحساب وأُتيح البريد {before['email']} للتسجيل من جديد",
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
            detail=f"البريد {address} صار مستخدماً لحساب آخر — لا يمكن الاستعادة",
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


# ── Organization lifecycle ────────────────────────────────────────────────────

@router.post("/organizations/{org_id}/reactivate")
async def reactivate_organization(
    org_id: uuid.UUID,
    payload: ReasonIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> dict:
    """Lift a suspension. There was no way to undo one before this."""
    organization = await db.get(PharmacyOrganization, org_id)
    if organization is None or organization.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="المنشأة غير موجودة"
        )
    if organization.status == OrganizationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="المنشأة معتمدة بالفعل"
        )
    if organization.status == OrganizationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="المنشأة قيد المراجعة — استخدم الاعتماد لا إعادة التفعيل",
        )

    before = str(getattr(organization.status, "value", organization.status))
    organization.status = OrganizationStatus.APPROVED
    organization.suspension_reason = None
    organization.rejection_reason = None
    await db.flush()

    await AuditService(db).log(
        action="support.organization.reactivate",
        resource_type="pharmacy_organization",
        resource_id=organization.id,
        actor_id=current_user.id,
        organization_id=organization.id,
        before_state={"status": before},
        after_state={"status": "approved"},
        notes=payload.reason,
        **_client(request),
    )
    return {
        "id": str(organization.id),
        "status": "approved",
        "message": "أُعيد تفعيل المنشأة ويستطيع مستخدموها الدخول",
    }


# ── Marketplace moderation ────────────────────────────────────────────────────

@router.post("/moderation/{listing_id}/remove")
async def remove_listing(
    listing_id: uuid.UUID,
    payload: ListingRemoveIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> dict:
    """Take a listing off the market.

    The moderation screen has had this button since it was built; the endpoint
    behind it never existed, so pressing it returned 404. The seller is told
    why, because a listing vanishing without explanation is how a customer
    loses trust in a marketplace.
    """
    from models.notification import NotificationType
    from services.notification_service import NotificationService

    listing = (
        await db.execute(
            select(MarketplaceListing).where(
                MarketplaceListing.id == listing_id,
                MarketplaceListing.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="العرض غير موجود"
        )
    if listing.status not in (ListingStatus.ACTIVE, ListingStatus.DRAFT):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"لا يمكن إزالة عرض حالته {getattr(listing.status, 'value', listing.status)}",
        )

    before = str(getattr(listing.status, "value", listing.status))
    listing.status = ListingStatus.CANCELLED

    # Hand the stock back, or the seller's batch stays stuck as LISTED.
    batch = await db.get(InventoryBatch, listing.batch_id)
    if batch is not None and batch.status == BatchStatus.LISTED:
        batch.status = BatchStatus.ACTIVE
    await db.flush()

    try:
        await NotificationService(db).create(
            user_id=listing.created_by_id,
            organization_id=listing.seller_organization_id,
            notification_type=NotificationType.LISTING_CANCELLED,
            title="A listing was removed by the platform",
            title_ar="أُزيل عرضك من السوق",
            body=f"Listing removed. Reason: {payload.reason}",
            body_ar=f"أُزيل عرض «{listing.title_ar or listing.title}». السبب: {payload.reason}",
            resource_type="listing",
            resource_id=listing.id,
        )
    except Exception:  # notifying must not undo the moderation
        pass

    await AuditService(db).log(
        action="support.listing.remove",
        resource_type="marketplace_listing",
        resource_id=listing.id,
        actor_id=current_user.id,
        organization_id=listing.seller_organization_id,
        before_state={"status": before},
        after_state={"status": "cancelled"},
        notes=payload.reason,
        **_client(request),
    )
    return {
        "id": str(listing.id),
        "status": "cancelled",
        "message": "أُزيل العرض وأُبلغ البائع بالسبب",
    }


# ── Customer inventory ────────────────────────────────────────────────────────

@router.delete("/inventory/batches/{batch_id}", response_model=BatchDeleteOut)
async def delete_batch(
    batch_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
    reason: str = Query(min_length=5, max_length=500),
) -> BatchDeleteOut:
    """Remove a batch from a customer's stock.

    Soft, never hard: `inventory_movements` and `marketplace_listings` both hold
    a non-null foreign key to the batch, so a hard delete would mean destroying
    the stock ledger — the very record that explains how the quantity got there.
    A soft delete also frees import capacity, because every count already
    filters on `deleted_at`.
    """
    batch = (
        await db.execute(
            select(InventoryBatch).where(
                InventoryBatch.id == batch_id,
                InventoryBatch.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="التشغيلة غير موجودة"
        )

    # Refuse anything the customer or a counterparty is relying on.
    live_listing = await db.scalar(
        select(MarketplaceListing.id).where(
            MarketplaceListing.batch_id == batch.id,
            MarketplaceListing.status.in_(
                [ListingStatus.DRAFT, ListingStatus.ACTIVE, ListingStatus.RESERVED]
            ),
            MarketplaceListing.deleted_at.is_(None),
        )
    )
    if live_listing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="على التشغيلة عرض قائم في السوق — أزل العرض أولاً",
        )

    if batch.quantity - batch.quantity_available > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"جزء من الكمية محجوز أو مُباع "
                f"({batch.quantity - batch.quantity_available} وحدة) — لا يمكن الحذف"
            ),
        )
    if batch.status == BatchStatus.SOLD:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="التشغيلة مباعة — لا تُحذف"
        )

    active_reservation = await db.scalar(
        select(Reservation.id)
        .join(MarketplaceListing, MarketplaceListing.id == Reservation.listing_id)
        .where(
            MarketplaceListing.batch_id == batch.id,
            Reservation.status == ReservationStatus.ACTIVE,
        )
    )
    if active_reservation is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="على التشغيلة حجز نشط من مشترٍ — لا يمكن الحذف",
        )

    sold_through = await db.scalar(
        select(Transaction.id)
        .join(MarketplaceListing, MarketplaceListing.id == Transaction.listing_id)
        .where(MarketplaceListing.batch_id == batch.id)
    )
    if sold_through is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="للتشغيلة صفقة مسجّلة — سجل المبيعات لا يُمس",
        )

    organization = await db.get(PharmacyOrganization, batch.organization_id)
    product = await db.get(Product, batch.product_id)
    branch = await db.get(PharmacyBranch, batch.branch_id)

    batch.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    await AuditService(db).log(
        action="support.batch.delete",
        resource_type="inventory_batch",
        resource_id=batch.id,
        actor_id=current_user.id,
        organization_id=batch.organization_id,
        before_state={
            "batch_number": batch.batch_number,
            "quantity": batch.quantity,
            "expiry_date": batch.expiry_date,
            "product": (product.name_ar or product.name) if product else None,
            "branch": (branch.name_ar or branch.name) if branch else None,
        },
        after_state={"deleted": True},
        notes=reason,
        **_client(request),
    )

    return BatchDeleteOut(
        id=batch.id,
        batch_number=batch.batch_number,
        organization_name=(organization.name_ar or organization.name)
        if organization
        else "—",
        deleted=True,
        message="حُذفت التشغيلة وتحرّرت من سعة المخزون",
    )


@router.post("/inventory/batches/{batch_id}/restore", response_model=BatchDeleteOut)
async def restore_batch(
    batch_id: uuid.UUID,
    payload: ReasonIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> BatchDeleteOut:
    """Undo a deletion — the reason a support delete is soft in the first place."""
    from config import settings
    from services.import_service import count_org_items

    batch = await db.get(InventoryBatch, batch_id)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="التشغيلة غير موجودة"
        )
    if batch.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="التشغيلة غير محذوفة"
        )

    used = await count_org_items(db, batch.organization_id)
    if used >= settings.MAX_INVENTORY_ITEMS_PER_ORG:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="استعادتها تتجاوز الحد الأقصى لمخزون المنشأة",
        )

    batch.deleted_at = None
    await db.flush()

    organization = await db.get(PharmacyOrganization, batch.organization_id)
    await AuditService(db).log(
        action="support.batch.restore",
        resource_type="inventory_batch",
        resource_id=batch.id,
        actor_id=current_user.id,
        organization_id=batch.organization_id,
        after_state={"batch_number": batch.batch_number, "restored": True},
        notes=payload.reason,
        **_client(request),
    )
    return BatchDeleteOut(
        id=batch.id,
        batch_number=batch.batch_number,
        organization_name=(organization.name_ar or organization.name)
        if organization
        else "—",
        deleted=False,
        message="أُعيدت التشغيلة إلى مخزون العميل",
    )
