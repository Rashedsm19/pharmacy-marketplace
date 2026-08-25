"""Support console — organization lifecycle."""
from __future__ import annotations


import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, or_, select

from dependencies import DbSession, SuperAdmin
from models.inventory import InventoryBatch
from models.marketplace import (
    MarketplaceListing,
)
from models.organization import (
    OrganizationStatus,
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.transaction import Transaction
from schemas.support import (
    PurgeIn,
    PurgeOut,
    ReasonIn,
)
from services.audit_service import AuditService

from routers.support.helpers import _client

router = APIRouter()


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

