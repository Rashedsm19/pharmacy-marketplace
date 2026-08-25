"""Support console — the customer dashboard."""
from __future__ import annotations


import math
import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from dependencies import DbSession, SuperAdmin
from models.branch import PharmacyBranch
from models.inventory import InventoryBatch
from models.marketplace import (
    ListingStatus,
    MarketplaceListing,
)
from models.organization import (
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.user import User
from schemas.support import (
    CustomerDetail,
    CustomerList,
    CustomerRow,
)

from routers.support.helpers import _row

router = APIRouter()


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


