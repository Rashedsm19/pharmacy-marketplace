"""
The integration API a customer's own system calls.

Authentication is an API key rather than a session, and every response is scoped
to the organization that key belongs to. There is no org_id parameter anywhere
in here on purpose: the key decides whose data this is, so a customer cannot
reach another pharmacy's stock even by asking for it.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from dependencies import ApiKeyContext, DbSession, require_scope
from models.api_key import ApiKeyScope
from models.branch import PharmacyBranch
from models.import_job import ImportJob, ImportSource, ImportStatus
from models.inventory import InventoryBatch
from models.product import Product
from schemas.external import (
    ExternalHealth,
    ExternalListing,
    ExternalListingsOut,
    InventorySyncIn,
    InventorySyncOut,
    NearExpiryItem,
    NearExpiryOut,
    SyncItemError,
)
from services import excel_service
from services.import_service import ImportProcessor

router = APIRouter(prefix="/external", tags=["External integration"])


@router.get("/health", response_model=ExternalHealth)
async def health(
    context: ApiKeyContext = Depends(require_scope(ApiKeyScope.INVENTORY_READ.value)),
) -> ExternalHealth:
    """Confirms the key works, and says who it belongs to.

    This is the first call the integration guide tells a customer to make.
    """
    return ExternalHealth(
        organization_id=context.organization_id,
        organization_name=context.key.organization.name_ar
        or context.key.organization.name,
        scopes=context.scopes,
        server_time=datetime.now(timezone.utc),
    )


@router.post("/inventory/sync", response_model=InventorySyncOut)
async def sync_inventory(
    payload: InventorySyncIn,
    db: DbSession,
    context: ApiKeyContext = Depends(require_scope(ApiKeyScope.INVENTORY_WRITE.value)),
) -> InventorySyncOut:
    """Send a batch of stock — the same matching and upsert as a spreadsheet.

    Sending the same batch again updates quantities rather than duplicating
    them, so this endpoint is safe to call on a schedule.
    """
    job = ImportJob(
        id=uuid.uuid4(),
        organization_id=context.organization_id,
        created_by_id=context.key.created_by_id,
        filename=f"api-sync-{len(payload.items)}-items",
        source=ImportSource.API,
        status=ImportStatus.PROCESSING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    rows = [
        excel_service.ParsedRow(
            # 1-based, so an error points at the item the caller sent.
            line_number=index + 1,
            values=item.model_dump(),
        )
        for index, item in enumerate(payload.items)
    ]

    processor = ImportProcessor(db, job)
    try:
        await processor.run_rows(rows)
    except ValueError as exc:
        job.status = ImportStatus.FAILED
        job.failure_reason = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    await db.commit()

    return InventorySyncOut(
        job_id=job.id,
        received=len(payload.items),
        created_batches=job.created_batches,
        updated_batches=job.updated_batches,
        created_products=job.created_products,
        matched_products=job.matched_products,
        failed=job.failed_rows,
        errors=[
            SyncItemError(
                index=error["line"] - 1,
                reason=error["reason"],
                product_name=error.get("product_name"),
                batch_number=error.get("batch_number"),
            )
            for error in (job.errors or [])
        ],
    )


@router.get("/inventory/near-expiry", response_model=NearExpiryOut)
async def near_expiry(
    db: DbSession,
    within_days: int = Query(default=180, ge=1, le=1095),
    limit: int = Query(default=200, ge=1, le=1000),
    context: ApiKeyContext = Depends(require_scope(ApiKeyScope.INVENTORY_READ.value)),
) -> NearExpiryOut:
    """What is approaching expiry — the answer the customer came for."""
    today = date.today()
    horizon = today.fromordinal(today.toordinal() + within_days)

    rows = (
        await db.execute(
            select(InventoryBatch, Product, PharmacyBranch)
            .join(Product, Product.id == InventoryBatch.product_id)
            .join(PharmacyBranch, PharmacyBranch.id == InventoryBatch.branch_id)
            .where(
                InventoryBatch.organization_id == context.organization_id,
                InventoryBatch.deleted_at.is_(None),
                InventoryBatch.expiry_date <= horizon,
                InventoryBatch.expiry_date > today,
                InventoryBatch.quantity_available > 0,
            )
            .order_by(InventoryBatch.expiry_date)
            .limit(limit)
        )
    ).all()

    items = []
    for batch, product, branch in rows:
        days = (batch.expiry_date - today).days
        items.append(
            NearExpiryItem(
                batch_id=batch.id,
                product_name=product.name,
                product_name_ar=product.name_ar,
                sku=product.sku,
                barcode=product.barcode,
                batch_number=batch.batch_number,
                branch_name=branch.name_ar or branch.name,
                expiry_date=batch.expiry_date,
                days_remaining=days,
                quantity=batch.quantity,
                quantity_available=batch.quantity_available,
                unit_cost=float(batch.unit_cost) if batch.unit_cost is not None else None,
                status=batch.status.value
                if hasattr(batch.status, "value")
                else str(batch.status),
                zone=_zone(days),
            )
        )

    return NearExpiryOut(total=len(items), within_days=within_days, items=items)


@router.get("/listings", response_model=ExternalListingsOut)
async def my_listings(
    db: DbSession,
    status_filter: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    context: ApiKeyContext = Depends(require_scope(ApiKeyScope.LISTINGS_READ.value)),
) -> ExternalListingsOut:
    """The pharmacy's own listings, so its system can show where stock went."""
    from sqlalchemy import func

    from models.marketplace import ListingOffer, MarketplaceListing

    offer_counts = (
        select(ListingOffer.listing_id, func.count(ListingOffer.id).label("offers"))
        .group_by(ListingOffer.listing_id)
        .subquery()
    )

    query = (
        select(MarketplaceListing, InventoryBatch, Product, offer_counts.c.offers)
        .join(InventoryBatch, InventoryBatch.id == MarketplaceListing.batch_id)
        .join(Product, Product.id == InventoryBatch.product_id)
        .outerjoin(offer_counts, offer_counts.c.listing_id == MarketplaceListing.id)
        .where(MarketplaceListing.seller_organization_id == context.organization_id)
        .order_by(MarketplaceListing.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        query = query.where(MarketplaceListing.status == status_filter)

    rows = (await db.execute(query)).all()
    items = [
        ExternalListing(
            listing_id=listing.id,
            title=listing.title_ar or listing.title,
            product_name=product.name_ar or product.name,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date,
            quantity_listed=listing.quantity_listed,
            quantity_available=listing.quantity_available,
            asking_price=float(listing.asking_price),
            status=listing.status.value
            if hasattr(listing.status, "value")
            else str(listing.status),
            view_count=listing.view_count,
            offer_count=int(offers or 0),
            expires_at=listing.expires_at,
            created_at=listing.created_at,
        )
        for listing, batch, product, offers in rows
    ]
    return ExternalListingsOut(total=len(items), items=items)


def _zone(days: int) -> str:
    """The colour bands used everywhere in the product."""
    if days < 30:
        return "red"
    if days < 90:
        return "orange"
    if days <= 180:
        return "yellow"
    return "green"
