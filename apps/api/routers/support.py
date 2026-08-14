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
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
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
    ImpersonateIn,
    ImpersonateOut,
    ImpersonationRow,
    AdminUserRow,
    CustomerDetail,
    CustomerList,
    CustomerRow,
    PurgeIn,
    PurgeOut,
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
        "message": "أعيد تفعيل المنشأة ويستطيع مستخدموها الدخول",
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
            title_ar="أزيل عرضك من السوق",
            body=f"Listing removed. Reason: {payload.reason}",
            body_ar=f"أزيل عرض «{listing.title_ar or listing.title}». السبب: {payload.reason}",
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
        "message": "أزيل العرض وأبلغ البائع بالسبب",
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
            detail="على التشغيلة عرض قائم في السوق — أزل العرض أولا",
        )

    if batch.quantity - batch.quantity_available > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"جزء من الكمية محجوز أو مباع "
                f"({batch.quantity - batch.quantity_available} وحدة) — لا يمكن الحذف"
            ),
        )
    if batch.status == BatchStatus.SOLD:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="التشغيلة مباعة — لا تحذف"
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
            detail="على التشغيلة حجز نشط من مشتر — لا يمكن الحذف",
        )

    sold_through = await db.scalar(
        select(Transaction.id)
        .join(MarketplaceListing, MarketplaceListing.id == Transaction.listing_id)
        .where(MarketplaceListing.batch_id == batch.id)
    )
    if sold_through is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="للتشغيلة صفقة مسجلة — سجل المبيعات لا يمس",
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
        message="حذفت التشغيلة وتحررت من سعة المخزون",
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
        message="أعيدت التشغيلة إلى مخزون العميل",
    )


# ── Acting for the customer ───────────────────────────────────────────────────

@router.post(
    "/organizations/{org_id}/imports",
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_for_customer(
    org_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
    reason: str = Query(min_length=5, max_length=500),
    file: UploadFile = File(...),
) -> dict:
    """Upload an inventory file into a customer's stock on their behalf.

    The processor takes the organization from the job row and does no
    authorization of its own, which means the only thing that has to be right is
    the id written here. Everything else — the worker, the matching, the error
    reporting — is the customer's own path, untouched.
    """
    from config import settings
    from models.import_job import ImportJob, ImportSource, ImportStatus
    from models.notification import NotificationType
    from services.import_service import count_org_items
    from services.notification_service import NotificationService
    from services.storage_service import storage_service

    organization = await db.get(PharmacyOrganization, org_id)
    if organization is None or organization.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="المنشأة غير موجودة"
        )

    # The processor needs somewhere to put the stock; refuse here rather than
    # queue a job that is guaranteed to fail.
    has_branch = await db.scalar(
        select(PharmacyBranch.id).where(
            PharmacyBranch.organization_id == org_id,
            PharmacyBranch.deleted_at.is_(None),
        )
    )
    if has_branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="لا يوجد فرع مسجل للمنشأة — أضف فرعا قبل الاستيراد",
        )

    used = await count_org_items(db, org_id)
    if used >= settings.MAX_INVENTORY_ITEMS_PER_ORG:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"بلغ مخزون المنشأة الحد الأقصى ({settings.MAX_INVENTORY_ITEMS_PER_ORG} صنف)",
        )

    stored_path, size = await storage_service.save_import_file(file, org_id)
    filename = (file.filename or "support-upload.xlsx")[:255]

    job = ImportJob(
        id=uuid.uuid4(),
        organization_id=org_id,
        created_by_id=current_user.id,
        filename=filename,
        stored_path=stored_path,
        source=ImportSource.CSV if filename.lower().endswith(".csv") else ImportSource.EXCEL,
        status=ImportStatus.QUEUED,
    )
    db.add(job)
    await db.flush()

    # The customer's stock is about to change. Telling them is not optional:
    # a re-upload overwrites quantities, and silently rewriting a pharmacy's
    # numbers is how a customer relationship ends.
    owners = (
        await db.execute(
            select(User)
            .join(
                UserOrganizationMembership,
                UserOrganizationMembership.user_id == User.id,
            )
            .where(
                UserOrganizationMembership.organization_id == org_id,
                UserOrganizationMembership.is_active.is_(True),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for owner in owners:
        try:
            await NotificationService(db).create(
                user_id=owner.id,
                organization_id=org_id,
                notification_type=NotificationType.SYSTEM,
                title="Support uploaded an inventory file to your account",
                title_ar="رفع فريق الدعم ملف مخزون إلى حسابكم",
                body=f"File: {filename}",
                body_ar=f"الملف: {filename}. السبب: {reason}",
                resource_type="import_job",
                resource_id=job.id,
            )
        except Exception:
            pass

    await AuditService(db).log(
        action="support.inventory.import",
        resource_type="import_job",
        resource_id=job.id,
        actor_id=current_user.id,
        organization_id=org_id,
        after_state={"filename": filename, "size_bytes": size},
        notes=reason,
        **_client(request),
    )
    await db.commit()
    return {
        "id": str(job.id),
        "organization_id": str(org_id),
        "organization_name": organization.name_ar or organization.name,
        "status": "queued",
        "message": "أدرج الملف في طابور المعالجة وأبلغ العميل",
    }


# ── Viewing as a customer ─────────────────────────────────────────────────────

@router.post("/users/{user_id}/impersonate", response_model=ImpersonateOut)
async def impersonate(
    user_id: uuid.UUID,
    payload: ImpersonateIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> ImpersonateOut:
    """Open a time-limited session inside a customer's account.

    "It doesn't work on my screen" is most of support, and answering it from
    outside the account is guesswork. The session is recorded, expires on its
    own, and can be ended on the spot — and no refresh token is issued, so it
    cannot quietly extend itself.
    """
    from config import settings
    from auth.jwt import create_access_token
    from models.impersonation import ImpersonationSession

    target = await _load_user(db, user_id)
    if target.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكن انتحال حساب مدير منصة",
        )
    if not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="الحساب معطل — فعله أولا إن أردت تصفحه",
        )

    organization, _ = await _org_of(db, target.id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="الحساب بلا منشأة — لا توجد شاشات لتصفحها",
        )

    now = datetime.now(timezone.utc)
    session = ImpersonationSession(
        id=uuid.uuid4(),
        admin_user_id=current_user.id,
        admin_email=current_user.email,
        target_user_id=target.id,
        target_email=target.email,
        organization_id=organization.id,
        organization_name=organization.name_ar or organization.name,
        reason=payload.reason,
        started_at=now,
        expires_at=now + timedelta(minutes=payload.minutes),
        **_client(request),
    )
    db.add(session)
    await db.flush()

    token = create_access_token(
        target.id,
        target.email,
        target.role,
        organization.id,
        impersonator_id=current_user.id,
        impersonator_email=current_user.email,
        session_id=session.id,
        expires_minutes=payload.minutes,
    )

    await AuditService(db).log(
        action="support.impersonation.start",
        resource_type="user",
        resource_id=target.id,
        actor_id=current_user.id,
        organization_id=organization.id,
        after_state={
            "session_id": str(session.id),
            "expires_at": session.expires_at.isoformat(),
            "minutes": payload.minutes,
        },
        notes=payload.reason,
        **_client(request),
    )
    assert settings  # configuration is loaded; keeps the import meaningful

    return ImpersonateOut(
        access_token=token,
        expires_at=session.expires_at,
        session_id=session.id,
        user_id=target.id,
        user_email=target.email,
        user_name=target.full_name,
        organization_id=organization.id,
        organization_name=session.organization_name or "",
        notice=(
            f"أنت الآن تتصفح حساب «{session.organization_name}» لمدة "
            f"{payload.minutes} دقيقة. كل إجراء يسجل باسمك."
        ),
    )


@router.post("/impersonation/{session_id}/end")
async def end_impersonation(
    session_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> dict:
    """Close a session immediately — the token stops working on its next use."""
    from models.impersonation import ImpersonationSession

    session = await db.get(ImpersonationSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="الجلسة غير موجودة"
        )
    if session.ended_at is not None:
        return {"id": str(session.id), "ended": True, "message": "الجلسة منتهية بالفعل"}

    session.ended_at = datetime.now(timezone.utc)
    session.ended_reason = "ended_by_admin"
    await db.flush()

    await AuditService(db).log(
        action="support.impersonation.end",
        resource_type="user",
        resource_id=session.target_user_id,
        actor_id=current_user.id,
        organization_id=session.organization_id,
        after_state={"session_id": str(session.id)},
        notes=f"إنهاء تصفح حساب {session.target_email}",
        **_client(request),
    )
    return {"id": str(session.id), "ended": True, "message": "أنهيت الجلسة"}


@router.get("/impersonation/sessions", response_model=list[ImpersonationRow])
async def list_impersonation_sessions(
    db: DbSession,
    current_user: SuperAdmin,
    active_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ImpersonationRow]:
    """Who has been inside which account, and who is inside one right now."""
    from models.impersonation import ImpersonationSession

    query = select(ImpersonationSession).order_by(
        ImpersonationSession.started_at.desc()
    )
    if active_only:
        query = query.where(
            ImpersonationSession.ended_at.is_(None),
            ImpersonationSession.expires_at > datetime.now(timezone.utc),
        )
    rows = (await db.execute(query.limit(limit))).scalars().all()
    return [ImpersonationRow.model_validate(row) for row in rows]


# ── The customer dashboard ────────────────────────────────────────────────────

def _zero() -> dict:
    return {}


async def _aggregate(db, org_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Every metric for a page of customers, in a fixed number of queries.

    Aggregating before paging would scan every batch on the platform on each
    request; grouping over one page's ids keeps the cost flat no matter how many
    pharmacies sign up.
    """
    from datetime import date

    from models.api_key import ApiKey
    from models.dispute import Dispute, DisputeStatus
    from models.import_job import ImportJob
    from models.transaction import Transaction as Txn

    if not org_ids:
        return {}
    today = date.today()
    out: dict[uuid.UUID, dict] = {oid: {} for oid in org_ids}

    def merge(rows, mapping):
        for row in rows:
            bucket = out.get(row[0])
            if bucket is None:
                continue
            for key, index in mapping.items():
                bucket[key] = row[index]

    merge(
        (
            await db.execute(
                select(
                    UserOrganizationMembership.organization_id,
                    func.count(func.distinct(User.id)),
                    func.count(func.distinct(User.id)).filter(User.is_active.is_(True)),
                    func.max(User.last_login_at),
                )
                .join(User, User.id == UserOrganizationMembership.user_id)
                .where(
                    UserOrganizationMembership.organization_id.in_(org_ids),
                    UserOrganizationMembership.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
                .group_by(UserOrganizationMembership.organization_id)
            )
        ).all(),
        {"users": 1, "active_users": 2, "last_login": 3},
    )

    merge(
        (
            await db.execute(
                select(PharmacyBranch.organization_id, func.count(PharmacyBranch.id))
                .where(
                    PharmacyBranch.organization_id.in_(org_ids),
                    PharmacyBranch.deleted_at.is_(None),
                )
                .group_by(PharmacyBranch.organization_id)
            )
        ).all(),
        {"branches": 1},
    )

    merge(
        (
            await db.execute(
                select(
                    InventoryBatch.organization_id,
                    func.count(InventoryBatch.id),
                    func.coalesce(func.sum(InventoryBatch.quantity_available), 0),
                    func.coalesce(
                        func.sum(
                            InventoryBatch.quantity_available * InventoryBatch.unit_cost
                        ),
                        0,
                    ),
                    func.count(InventoryBatch.id).filter(
                        InventoryBatch.expiry_date <= today
                    ),
                    func.count(InventoryBatch.id).filter(
                        InventoryBatch.expiry_date > today,
                        InventoryBatch.expiry_date <= today + timedelta(days=180),
                    ),
                )
                .where(
                    InventoryBatch.organization_id.in_(org_ids),
                    InventoryBatch.deleted_at.is_(None),
                )
                .group_by(InventoryBatch.organization_id)
            )
        ).all(),
        {"batches": 1, "units": 2, "stock_value": 3, "expired": 4, "near_expiry": 5},
    )

    merge(
        (
            await db.execute(
                select(
                    MarketplaceListing.seller_organization_id,
                    func.count(MarketplaceListing.id).filter(
                        MarketplaceListing.status == ListingStatus.ACTIVE
                    ),
                    func.max(MarketplaceListing.created_at),
                )
                .where(MarketplaceListing.seller_organization_id.in_(org_ids))
                .group_by(MarketplaceListing.seller_organization_id)
            )
        ).all(),
        {"active_listings": 1, "last_listing": 2},
    )

    merge(
        (
            await db.execute(
                select(
                    ImportJob.organization_id,
                    func.count(ImportJob.id),
                    func.max(ImportJob.created_at),
                )
                .where(ImportJob.organization_id.in_(org_ids))
                .group_by(ImportJob.organization_id)
            )
        ).all(),
        {"imports": 1, "last_import": 2},
    )

    merge(
        (
            await db.execute(
                select(
                    Txn.seller_organization_id,
                    func.count(Txn.id),
                    func.max(Txn.created_at),
                )
                .where(Txn.seller_organization_id.in_(org_ids))
                .group_by(Txn.seller_organization_id)
            )
        ).all(),
        {"sales": 1, "last_sale": 2},
    )

    merge(
        (
            await db.execute(
                select(Txn.buyer_organization_id, func.count(Txn.id))
                .where(Txn.buyer_organization_id.in_(org_ids))
                .group_by(Txn.buyer_organization_id)
            )
        ).all(),
        {"purchases": 1},
    )

    merge(
        (
            await db.execute(
                select(Dispute.raised_by_organization_id, func.count(Dispute.id))
                .where(
                    Dispute.raised_by_organization_id.in_(org_ids),
                    Dispute.status.in_(
                        [DisputeStatus.OPEN, DisputeStatus.SELLER_RESPONDED]
                    ),
                )
                .group_by(Dispute.raised_by_organization_id)
            )
        ).all(),
        {"open_disputes": 1},
    )

    merge(
        (
            await db.execute(
                select(ApiKey.organization_id, func.count(ApiKey.id))
                .where(
                    ApiKey.organization_id.in_(org_ids),
                    ApiKey.is_active.is_(True),
                )
                .group_by(ApiKey.organization_id)
            )
        ).all(),
        {"api_keys": 1},
    )
    return out


def _customer_row(organization, metrics: dict) -> CustomerRow:
    stamps = [
        metrics.get(key)
        for key in ("last_login", "last_import", "last_listing", "last_sale")
    ]
    stamps = [s for s in stamps if s is not None]
    return CustomerRow(
        id=organization.id,
        name=organization.name_ar or organization.name,
        status=str(getattr(organization.status, "value", organization.status)),
        city=organization.city,
        commercial_registration_number=organization.commercial_registration_number,
        is_licensed=bool(organization.is_licensed),
        created_at=organization.created_at,
        approved_at=organization.approved_at,
        users=int(metrics.get("users") or 0),
        active_users=int(metrics.get("active_users") or 0),
        branches=int(metrics.get("branches") or 0),
        batches=int(metrics.get("batches") or 0),
        units=int(metrics.get("units") or 0),
        stock_value=float(metrics.get("stock_value") or 0),
        near_expiry=int(metrics.get("near_expiry") or 0),
        expired=int(metrics.get("expired") or 0),
        active_listings=int(metrics.get("active_listings") or 0),
        imports=int(metrics.get("imports") or 0),
        sales=int(metrics.get("sales") or 0),
        purchases=int(metrics.get("purchases") or 0),
        open_disputes=int(metrics.get("open_disputes") or 0),
        api_keys=int(metrics.get("api_keys") or 0),
        last_activity_at=max(stamps) if stamps else None,
    )


@router.get("/customers", response_model=CustomerList)
async def list_customers(
    db: DbSession,
    current_user: SuperAdmin,
    search: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = Query(default=25, ge=1, le=100),
) -> CustomerList:
    """Every pharmacy on the platform, with the state of its account."""
    page = max(page, 1)
    conditions = [PharmacyOrganization.deleted_at.is_(None)]
    if status_filter:
        conditions.append(PharmacyOrganization.status == status_filter)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                PharmacyOrganization.name.ilike(pattern),
                PharmacyOrganization.name_ar.ilike(pattern),
                PharmacyOrganization.commercial_registration_number.ilike(pattern),
                PharmacyOrganization.email.ilike(pattern),
            )
        )

    total = int(
        await db.scalar(
            select(func.count(PharmacyOrganization.id)).where(*conditions)
        )
        or 0
    )
    organizations = (
        await db.execute(
            select(PharmacyOrganization)
            .where(*conditions)
            .order_by(PharmacyOrganization.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    metrics = await _aggregate(db, [o.id for o in organizations])
    return CustomerList(
        items=[_customer_row(o, metrics.get(o.id, {})) for o in organizations],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/customers/{org_id}", response_model=CustomerDetail)
async def get_customer(
    org_id: uuid.UUID, db: DbSession, current_user: SuperAdmin
) -> CustomerDetail:
    """Everything about one customer, on one screen."""
    from datetime import date

    from models.api_key import ApiKey
    from models.import_job import ImportJob

    organization = await db.get(PharmacyOrganization, org_id)
    if organization is None or organization.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="المنشأة غير موجودة"
        )

    metrics = (await _aggregate(db, [org_id])).get(org_id, {})
    today = date.today()

    users = (
        await db.execute(
            select(User, UserOrganizationMembership.role)
            .join(
                UserOrganizationMembership,
                UserOrganizationMembership.user_id == User.id,
            )
            .where(
                UserOrganizationMembership.organization_id == org_id,
                User.deleted_at.is_(None),
            )
            .order_by(User.created_at)
        )
    ).all()

    branches = (
        await db.execute(
            select(PharmacyBranch).where(
                PharmacyBranch.organization_id == org_id,
                PharmacyBranch.deleted_at.is_(None),
            )
        )
    ).scalars().all()

    zones = (
        await db.execute(
            select(
                func.count(InventoryBatch.id).filter(
                    InventoryBatch.expiry_date <= today
                ),
                func.count(InventoryBatch.id).filter(
                    InventoryBatch.expiry_date > today,
                    InventoryBatch.expiry_date < today + timedelta(days=30),
                ),
                func.count(InventoryBatch.id).filter(
                    InventoryBatch.expiry_date >= today + timedelta(days=30),
                    InventoryBatch.expiry_date < today + timedelta(days=90),
                ),
                func.count(InventoryBatch.id).filter(
                    InventoryBatch.expiry_date >= today + timedelta(days=90),
                    InventoryBatch.expiry_date <= today + timedelta(days=180),
                ),
                func.count(InventoryBatch.id).filter(
                    InventoryBatch.expiry_date > today + timedelta(days=180)
                ),
            ).where(
                InventoryBatch.organization_id == org_id,
                InventoryBatch.deleted_at.is_(None),
            )
        )
    ).one()

    imports = (
        await db.execute(
            select(ImportJob)
            .where(ImportJob.organization_id == org_id)
            .order_by(ImportJob.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    listing_counts = (
        await db.execute(
            select(MarketplaceListing.status, func.count(MarketplaceListing.id))
            .where(MarketplaceListing.seller_organization_id == org_id)
            .group_by(MarketplaceListing.status)
        )
    ).all()

    keys = (
        await db.execute(
            select(ApiKey)
            .where(ApiKey.organization_id == org_id)
            .order_by(ApiKey.created_at.desc())
        )
    ).scalars().all()

    return CustomerDetail(
        organization={
            "id": str(organization.id),
            "name": organization.name,
            "name_ar": organization.name_ar,
            "status": str(getattr(organization.status, "value", organization.status)),
            "commercial_registration_number": organization.commercial_registration_number,
            "license_number": organization.license_number,
            "is_licensed": organization.is_licensed,
            "vat_number": organization.vat_number,
            "email": organization.email,
            "phone": organization.phone,
            "city": organization.city,
            "region": organization.region,
            "address": organization.address,
            "created_at": organization.created_at.isoformat(),
            "approved_at": organization.approved_at.isoformat()
            if organization.approved_at
            else None,
            "suspension_reason": organization.suspension_reason,
            "rejection_reason": organization.rejection_reason,
        },
        summary=_customer_row(organization, metrics),
        users=[_row(u, organization, str(getattr(r, "value", r))) for u, r in users],
        branches=[
            {
                "id": str(b.id),
                "name": b.name_ar or b.name,
                "city": b.city,
                "is_active": b.is_active,
                "storage_condition_status": b.storage_condition_status,
                "cold_chain_available": b.cold_chain_available,
            }
            for b in branches
        ],
        inventory_by_zone={
            "expired": int(zones[0] or 0),
            "red": int(zones[1] or 0),
            "orange": int(zones[2] or 0),
            "yellow": int(zones[3] or 0),
            "green": int(zones[4] or 0),
        },
        recent_imports=[
            {
                "id": str(j.id),
                "filename": j.filename,
                "source": str(getattr(j.source, "value", j.source)),
                "status": str(getattr(j.status, "value", j.status)),
                "created_batches": j.created_batches,
                "failed_rows": j.failed_rows,
                "created_at": j.created_at.isoformat(),
            }
            for j in imports
        ],
        listings={
            str(getattr(s, "value", s)): int(c) for s, c in listing_counts
        },
        api_keys=[
            {
                "id": str(k.id),
                "name": k.name,
                "prefix": k.prefix,
                "scopes": list(k.scopes or []),
                "is_active": k.is_active,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "request_count": k.request_count,
            }
            for k in keys
        ],
    )


# ── Permanent deletion ────────────────────────────────────────────────────────

# Order matters: every foreign key in this schema is NO ACTION, so a child row
# left behind blocks its parent. Leaves first, the organization last.
_PURGE_ORDER: tuple[str, ...] = (
    "api_keys",
    "import_jobs",
    "notifications",
    "notification_preferences",
    "reservations",
    "listing_offers",
    "listing_views",
    "marketplace_listings",
    "inventory_movements",
    "inventory_batches",
    "near_expiry_rules",
    "products",
    "pharmacy_branches",
    "user_organization_memberships",
    "users",
    "pharmacy_organizations",
)


@router.delete("/organizations/{org_id}", response_model=PurgeOut)
async def purge_organization(
    org_id: uuid.UUID,
    payload: PurgeIn,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
) -> PurgeOut:
    """Erase a pharmacy and everything it owns. There is no undo.

    Two refusals are absolute. The pharmacy must be suspended first, so that
    deleting a live customer takes two deliberate steps rather than one. And it
    must have no financial history: a tax invoice carries a sequential counter
    and a hash chained to the one before it, and references both the seller and
    the buyer — so erasing this pharmacy's invoices would break the chain of a
    different pharmacy that has done nothing wrong, and destroy records both of
    them are required to keep. Suspend and anonymise such an account instead.
    """
    from sqlalchemy import delete as sql_delete, text, update as sql_update

    from models.audit import AuditLog
    from models.dispute import Dispute
    from models.impersonation import ImpersonationSession
    from models.invoice import Invoice

    from models.settings import PlatformSettings

    organization = await db.get(PharmacyOrganization, org_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="المنشأة غير موجودة"
        )

    if payload.confirm_name.strip() != (organization.name_ar or organization.name).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="اسم المنشأة المكتوب لا يطابق — الحذف النهائي يتطلب مطابقة الاسم",
        )

    if organization.status not in (
        OrganizationStatus.SUSPENDED,
        OrganizationStatus.REJECTED,
        OrganizationStatus.PENDING,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="أوقف المنشأة أولا — الحذف النهائي لا يطبق على منشأة عاملة",
        )

    invoices = int(
        await db.scalar(
            select(func.count(Invoice.id)).where(
                or_(
                    Invoice.seller_organization_id == org_id,
                    Invoice.buyer_organization_id == org_id,
                )
            )
        )
        or 0
    )
    deals = int(
        await db.scalar(
            select(func.count(Transaction.id)).where(
                or_(
                    Transaction.seller_organization_id == org_id,
                    Transaction.buyer_organization_id == org_id,
                )
            )
        )
        or 0
    )
    if invoices or deals:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"للمنشأة {deals} صفقة و{invoices} فاتورة ضريبية. حذفها يكسر سلسلة "
                "فواتير الطرف الآخر ويمحو سجلات ملزمة نظاما — أوقف المنشأة بدل حذفها."
            ),
        )

    # Users who belong to this pharmacy and to no other.
    user_ids = [
        row[0]
        for row in (
            await db.execute(
                select(UserOrganizationMembership.user_id).where(
                    UserOrganizationMembership.organization_id == org_id
                )
            )
        ).all()
    ]
    if user_ids:
        elsewhere = {
            row[0]
            for row in (
                await db.execute(
                    select(UserOrganizationMembership.user_id).where(
                        UserOrganizationMembership.user_id.in_(user_ids),
                        UserOrganizationMembership.organization_id != org_id,
                    )
                )
            ).all()
        }
        user_ids = [uid for uid in user_ids if uid not in elsewhere]

    listing_ids = [
        row[0]
        for row in (
            await db.execute(
                select(MarketplaceListing.id).where(
                    MarketplaceListing.seller_organization_id == org_id
                )
            )
        ).all()
    ]
    batch_ids = [
        row[0]
        for row in (
            await db.execute(
                select(InventoryBatch.id).where(
                    InventoryBatch.organization_id == org_id
                )
            )
        ).all()
    ]

    name = organization.name_ar or organization.name
    manifest = {
        "users": len(user_ids),
        "listings": len(listing_ids),
        "batches": len(batch_ids),
    }

    # The record of the deletion is written first, and deliberately carries no
    # organization_id — a row pointing at the pharmacy would block the very
    # delete it is describing. resource_id has no foreign key, so it survives as
    # the pointer.
    entry = await AuditService(db).log(
        action="support.organization.purge",
        resource_type="pharmacy_organization",
        resource_id=organization.id,
        actor_id=current_user.id,
        before_state={
            "name": organization.name,
            "name_ar": organization.name_ar,
            "commercial_registration_number": organization.commercial_registration_number,
            "license_number": organization.license_number,
            "status": str(getattr(organization.status, "value", organization.status)),
            "email": organization.email,
            "city": organization.city,
            "created_at": organization.created_at,
        },
        after_state=manifest,
        notes=payload.reason,
        **_client(request),
    )
    await db.flush()

    # Detach every inbound reference rather than deleting the history.
    await db.execute(
        sql_update(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .values(organization_id=None)
    )
    if user_ids:
        await db.execute(
            sql_update(AuditLog).where(AuditLog.actor_id.in_(user_ids)).values(actor_id=None)
        )
        await db.execute(
            sql_update(PlatformSettings)
            .where(PlatformSettings.updated_by_id.in_(user_ids))
            .values(updated_by_id=None)
        )
        await db.execute(
            sql_update(PharmacyOrganization)
            .where(PharmacyOrganization.approved_by_id.in_(user_ids))
            .values(approved_by_id=None)
        )
    await db.execute(
        sql_update(ImpersonationSession)
        .where(ImpersonationSession.organization_id == org_id)
        .values(organization_id=None, target_user_id=None)
    )

    deleted: dict[str, int] = {}

    async def wipe(table: str, where: str, params: dict) -> None:
        result = await db.execute(text(f"DELETE FROM {table} WHERE {where}"), params)
        if result.rowcount:
            deleted[table] = deleted.get(table, 0) + result.rowcount

    ids = {"org": org_id, "users": user_ids, "listings": listing_ids, "batches": batch_ids}

    await wipe("api_keys", "organization_id = :org", ids)
    await wipe("import_jobs", "organization_id = :org", ids)
    if user_ids:
        await wipe("notifications", "organization_id = :org OR user_id = ANY(:users)", ids)
        await wipe("notification_preferences", "user_id = ANY(:users)", ids)
    else:
        await wipe("notifications", "organization_id = :org", ids)
    await wipe("ratings", "rater_organization_id = :org OR rated_organization_id = :org", ids)
    await db.execute(
        sql_delete(Dispute).where(Dispute.raised_by_organization_id == org_id)
    )
    if listing_ids:
        await wipe(
            "reservations", "buyer_organization_id = :org OR listing_id = ANY(:listings)", ids
        )
        await wipe(
            "listing_offers", "buyer_organization_id = :org OR listing_id = ANY(:listings)", ids
        )
        await wipe("listing_views", "listing_id = ANY(:listings)", ids)
    else:
        await wipe("reservations", "buyer_organization_id = :org", ids)
        await wipe("listing_offers", "buyer_organization_id = :org", ids)
    await wipe("listing_views", "viewer_organization_id = :org", ids)
    await wipe("marketplace_listings", "seller_organization_id = :org", ids)
    if batch_ids:
        await wipe(
            "inventory_movements", "organization_id = :org OR batch_id = ANY(:batches)", ids
        )
    else:
        await wipe("inventory_movements", "organization_id = :org", ids)
    await wipe("inventory_batches", "organization_id = :org", ids)
    await wipe("near_expiry_rules", "organization_id = :org", ids)
    # Private drafts only; anything promoted has a NULL owner and stays.
    await wipe("products", "owner_organization_id = :org", ids)
    await wipe("pharmacy_branches", "organization_id = :org", ids)
    await wipe("user_organization_memberships", "organization_id = :org", ids)
    if user_ids:
        await wipe("users", "id = ANY(:users)", ids)
    await wipe("pharmacy_organizations", "id = :org", ids)

    return PurgeOut(
        organization_id=org_id,
        organization_name=name,
        deleted=deleted,
        audit_log_id=entry.id,
        message=f"حذفت «{name}» نهائيا وبقي أثر الحذف في سجل التدقيق",
    )
