"""Support console — customer inventory."""
from __future__ import annotations


import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

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
    PharmacyOrganization,
)
from models.product import Product
from models.transaction import Transaction
from schemas.support import (
    BatchDeleteOut,
    ReasonIn,
)
from services.audit_service import AuditService

from routers.support.helpers import _client

router = APIRouter()


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

