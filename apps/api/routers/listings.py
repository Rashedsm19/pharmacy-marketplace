"""Listings router."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove
from repositories.marketplace import ListingRepository
from repositories.organization import MembershipRepository
from schemas.common import PaginatedResponse
from schemas.marketplace import (
    EligibilityResult,
    ListingCreate,
    ListingDetail,
    ListingOut,
    ListingUpdate,
)
from services.eligibility_service import EligibilityService
from services.listing_service import ListingService

router = APIRouter(prefix="/listings", tags=["Listings"])


async def _get_org_id(current_user, db) -> uuid.UUID:
    from models.user import UserRole
    if current_user.role == UserRole.SUPER_ADMIN:
        return None
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization")
    return org_id


@router.get("", response_model=PaginatedResponse[ListingOut])
async def list_listings(
    db: DbSession,
    current_user: CurrentUser,
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    my_listings: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    repo = ListingRepository(db)
    org_id = await _get_org_id(current_user, db)

    seller_org = org_id if my_listings else None
    exclude_org = None if my_listings else org_id  # hide own listings from marketplace

    rows, total = await repo.list_active(
        search=search,
        category_id=category_id,
        seller_org_id=seller_org,
        exclude_org_id=exclude_org,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse(
        items=[ListingOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=ListingOut, status_code=201)
async def create_listing(
    data: ListingCreate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _get_org_id(current_user, db)
    svc = ListingService(db)
    listing = await svc.create_listing(
        data, org_id, current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return ListingOut.model_validate(listing)


@router.get("/{listing_id}/eligibility", response_model=EligibilityResult)
async def check_eligibility(
    listing_id: uuid.UUID,
    batch_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    org_id = await _get_org_id(current_user, db)
    svc = EligibilityService(db)
    return await svc.check_listing_eligibility(batch_id, org_id)


@router.get("/{listing_id}", response_model=ListingDetail)
async def get_listing(
    listing_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    request: Request,
):
    repo = ListingRepository(db)
    listing = await repo.get(listing_id)
    if not listing or listing.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    # Track view
    from models.marketplace import ListingView
    org_id = await _get_org_id(current_user, db)
    view = ListingView(
        id=uuid.uuid4(),
        listing_id=listing_id,
        viewer_organization_id=org_id,
        viewer_user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(view)
    listing.view_count += 1

    from datetime import date
    days = (listing.batch.expiry_date - date.today()).days
    zone = "green" if days > 180 else "yellow" if days > 90 else "orange" if days > 30 else "red"

    return ListingDetail(
        **ListingOut.model_validate(listing).model_dump(),
        product_name=listing.batch.product.name if listing.batch else None,
        product_name_ar=listing.batch.product.name_ar if listing.batch else None,
        product_sku=listing.batch.product.sku if listing.batch else None,
        batch_number=listing.batch.batch_number if listing.batch else None,
        expiry_date=str(listing.batch.expiry_date) if listing.batch else None,
        days_until_expiry=days,
        expiry_zone=zone,
        seller_org_name=listing.seller_organization.name if listing.seller_organization else None,
        seller_branch_name=listing.seller_branch.name if listing.seller_branch else None,
    )


@router.patch("/{listing_id}", response_model=ListingOut)
async def update_listing(
    listing_id: uuid.UUID,
    data: ListingUpdate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    org_id = await _get_org_id(current_user, db)
    repo = ListingRepository(db)
    listing = await repo.get_by_org(listing_id, org_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(listing, k, v)
    await db.flush()
    return ListingOut.model_validate(listing)


@router.delete("/{listing_id}", status_code=204)
async def cancel_listing(
    listing_id: uuid.UUID,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _get_org_id(current_user, db)
    svc = ListingService(db)
    await svc.cancel_listing(
        listing_id, org_id, current_user.id,
        ip_address=request.client.host if request.client else None,
    )
