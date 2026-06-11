"""Reports router — all 10 report endpoints."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from dependencies import CurrentUser, DbSession
from repositories.organization import MembershipRepository
from schemas.reports import (
    BranchComparisonRow,
    ExpiredLossReportRow,
    NearExpiryReportRow,
    RecoverableValueRow,
    TopProductRow,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


async def _get_org_id(current_user, db) -> uuid.UUID:
    from models.user import UserRole
    if current_user.role == UserRole.SUPER_ADMIN:
        return None
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization")
    return org_id


@router.get("/near-expiry", response_model=list[NearExpiryReportRow])
async def report_near_expiry(
    db: DbSession,
    current_user: CurrentUser,
    days: int = 180,
    branch_id: uuid.UUID | None = None,
):
    from sqlalchemy import select
    from models.inventory import InventoryBatch, BatchStatus
    from models.product import Product
    from models.branch import PharmacyBranch

    org_id = await _get_org_id(current_user, db)
    threshold = date.today() + timedelta(days=days)
    today = date.today()

    q = (
        select(InventoryBatch, Product, PharmacyBranch)
        .join(Product, InventoryBatch.product_id == Product.id)
        .join(PharmacyBranch, InventoryBatch.branch_id == PharmacyBranch.id)
        .where(
            InventoryBatch.expiry_date <= threshold,
            InventoryBatch.expiry_date >= today,
            InventoryBatch.status.in_([BatchStatus.ACTIVE, BatchStatus.NEAR_EXPIRY]),
            InventoryBatch.deleted_at.is_(None),
        )
        .order_by(InventoryBatch.expiry_date)
    )
    if org_id:
        q = q.where(InventoryBatch.organization_id == org_id)
    if branch_id:
        q = q.where(InventoryBatch.branch_id == branch_id)

    result = await db.execute(q)
    rows = []
    for batch, product, branch in result:
        days_left = (batch.expiry_date - today).days
        zone = "green" if days_left > 180 else "yellow" if days_left > 90 else "orange" if days_left > 30 else "red"
        estimated = float(batch.unit_cost or 0) * batch.quantity_available
        rows.append(NearExpiryReportRow(
            batch_id=batch.id,
            product_name=product.name,
            product_name_ar=product.name_ar,
            branch_name=branch.name,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date,
            days_until_expiry=days_left,
            quantity=batch.quantity_available,
            expiry_zone=zone,
            estimated_value=estimated if estimated > 0 else None,
        ))
    return rows


@router.get("/expired-loss", response_model=list[ExpiredLossReportRow])
async def report_expired_loss(
    db: DbSession,
    current_user: CurrentUser,
    start_date: date | None = None,
    end_date: date | None = None,
):
    from sqlalchemy import select
    from models.inventory import InventoryBatch
    from models.product import Product
    from models.branch import PharmacyBranch

    org_id = await _get_org_id(current_user, db)
    today = date.today()
    end = end_date or today
    start = start_date or (today - timedelta(days=365))

    q = (
        select(InventoryBatch, Product, PharmacyBranch)
        .join(Product, InventoryBatch.product_id == Product.id)
        .join(PharmacyBranch, InventoryBatch.branch_id == PharmacyBranch.id)
        .where(
            InventoryBatch.expiry_date < today,
            InventoryBatch.expiry_date >= start,
            InventoryBatch.expiry_date <= end,
            InventoryBatch.deleted_at.is_(None),
        )
    )
    if org_id:
        q = q.where(InventoryBatch.organization_id == org_id)

    result = await db.execute(q)
    rows = []
    for batch, product, branch in result:
        unit_cost = float(batch.unit_cost) if batch.unit_cost else None
        total_loss = unit_cost * batch.quantity_available if unit_cost else None
        rows.append(ExpiredLossReportRow(
            product_name=product.name,
            product_name_ar=product.name_ar,
            branch_name=branch.name,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date,
            quantity_lost=batch.quantity_available,
            unit_cost=unit_cost,
            total_loss=total_loss,
        ))
    return rows


@router.get("/recoverable-value", response_model=list[RecoverableValueRow])
async def report_recoverable_value(db: DbSession, current_user: CurrentUser):
    from sqlalchemy import select
    from models.inventory import InventoryBatch, BatchStatus

    org_id = await _get_org_id(current_user, db)
    today = date.today()

    q = select(InventoryBatch).where(
        InventoryBatch.expiry_date >= today,
        InventoryBatch.status.in_([BatchStatus.ACTIVE, BatchStatus.NEAR_EXPIRY]),
        InventoryBatch.deleted_at.is_(None),
    )
    if org_id:
        q = q.where(InventoryBatch.organization_id == org_id)

    result = await db.execute(q)
    batches = result.scalars().all()

    zones = {"green": [], "yellow": [], "orange": [], "red": []}
    for b in batches:
        days = (b.expiry_date - today).days
        z = "green" if days > 180 else "yellow" if days > 90 else "orange" if days > 30 else "red"
        zones[z].append(b)

    rows = []
    for zone, zone_batches in zones.items():
        count = len(zone_batches)
        total_qty = sum(b.quantity_available for b in zone_batches)
        total_val = sum(float(b.unit_cost or 0) * b.quantity_available for b in zone_batches)
        rows.append(RecoverableValueRow(
            expiry_zone=zone,
            batch_count=count,
            total_quantity=total_qty,
            estimated_value=total_val,
            potential_recovery_at_50_pct=total_val * 0.5,
            potential_recovery_at_30_pct=total_val * 0.3,
        ))
    return rows


@router.get("/top-products", response_model=list[TopProductRow])
async def report_top_products(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 10,
):
    from sqlalchemy import func, select
    from models.marketplace import MarketplaceListing
    from models.inventory import InventoryBatch
    from models.product import Product

    await _get_org_id(current_user, db)

    q = (
        select(
            Product.id,
            Product.name,
            Product.name_ar,
            Product.sku,
            func.count(MarketplaceListing.id).label("listing_count"),
        )
        .join(InventoryBatch, Product.id == InventoryBatch.product_id)
        .join(MarketplaceListing, InventoryBatch.id == MarketplaceListing.batch_id)
        .group_by(Product.id)
        .order_by(func.count(MarketplaceListing.id).desc())
        .limit(limit)
    )

    result = await db.execute(q)
    rows = []
    for row in result:
        rows.append(TopProductRow(
            product_id=row.id,
            product_name=row.name,
            product_name_ar=row.name_ar,
            sku=row.sku,
            offer_count=0,
            listing_count=row.listing_count,
            transaction_count=0,
            total_value_traded=0,
        ))
    return rows


@router.get("/branch-comparison", response_model=list[BranchComparisonRow])
async def report_branch_comparison(db: DbSession, current_user: CurrentUser):
    from sqlalchemy import func, select
    from models.branch import PharmacyBranch
    from models.inventory import InventoryBatch
    from models.marketplace import MarketplaceListing, ListingStatus
    from models.transaction import Transaction, TransactionStatus

    org_id = await _get_org_id(current_user, db)
    if not org_id:
        return []

    q = select(PharmacyBranch).where(
        PharmacyBranch.organization_id == org_id,
        PharmacyBranch.deleted_at.is_(None),
    )
    result = await db.execute(q)
    branches = result.scalars().all()

    today = date.today()
    rows = []
    for branch in branches:
        # Count batches
        batches_q = await db.execute(
            select(func.count(InventoryBatch.id)).where(
                InventoryBatch.branch_id == branch.id,
                InventoryBatch.deleted_at.is_(None),
            )
        )
        total_batches = batches_q.scalar_one()

        near_expiry_q = await db.execute(
            select(func.count(InventoryBatch.id)).where(
                InventoryBatch.branch_id == branch.id,
                InventoryBatch.expiry_date >= today,
                InventoryBatch.expiry_date <= today + timedelta(days=180),
                InventoryBatch.deleted_at.is_(None),
            )
        )
        near_expiry = near_expiry_q.scalar_one()

        expired_q = await db.execute(
            select(func.count(InventoryBatch.id)).where(
                InventoryBatch.branch_id == branch.id,
                InventoryBatch.expiry_date < today,
                InventoryBatch.deleted_at.is_(None),
            )
        )
        expired = expired_q.scalar_one()

        listings_q = await db.execute(
            select(func.count(MarketplaceListing.id)).where(
                MarketplaceListing.seller_branch_id == branch.id,
                MarketplaceListing.status == ListingStatus.ACTIVE,
                MarketplaceListing.deleted_at.is_(None),
            )
        )
        active_listings = listings_q.scalar_one()

        tx_q = await db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.listing_id.in_(
                    select(MarketplaceListing.id).where(
                        MarketplaceListing.seller_branch_id == branch.id
                    )
                ),
                Transaction.status == TransactionStatus.COMPLETED,
            )
        )
        completed_tx = tx_q.scalar_one()

        rows.append(BranchComparisonRow(
            branch_id=branch.id,
            branch_name=branch.name,
            total_batches=total_batches,
            near_expiry_batches=near_expiry,
            expired_batches=expired,
            active_listings=active_listings,
            completed_transactions=completed_tx,
            recovered_value=0,
            loss_value=0,
        ))
    return rows
