"""Support console — marketplace moderation."""
from __future__ import annotations


import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from dependencies import DbSession, SuperAdmin
from models.inventory import BatchStatus, InventoryBatch
from models.marketplace import (
    ListingStatus,
    MarketplaceListing,
)
from schemas.support import (
    ListingRemoveIn,
)
from services.audit_service import AuditService

from routers.support.helpers import _client

router = APIRouter()


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

