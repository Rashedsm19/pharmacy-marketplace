"""Offers router."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException, Request

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove
from repositories.marketplace import OfferRepository
from repositories.organization import MembershipRepository
from schemas.common import PaginatedResponse
from schemas.marketplace import OfferCreate, OfferOut
from services.offer_service import OfferService

router = APIRouter(prefix="/offers", tags=["Offers"])


async def _get_org_id(current_user, db) -> uuid.UUID:
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization")
    return org_id


@router.post("", response_model=OfferOut, status_code=201)
async def submit_offer(
    data: OfferCreate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _get_org_id(current_user, db)
    svc = OfferService(db)
    offer = await svc.submit_offer(
        data, org_id, current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return OfferOut.model_validate(offer)


def _to_offer_out(offer) -> OfferOut:
    """Serialize an offer with the listing/org labels the offer tables display."""
    out = OfferOut.model_validate(offer)
    listing = offer.listing
    if listing is not None:
        out.listing_title = listing.title_ar or listing.title
        product = listing.batch.product if listing.batch is not None else None
        if product is not None:
            out.listing_product_name = product.name
            out.listing_product_name_ar = product.name_ar
        if listing.seller_organization is not None:
            out.seller_org_name = (
                listing.seller_organization.name_ar or listing.seller_organization.name
            )
    if offer.buyer_organization is not None:
        out.buyer_org_name = offer.buyer_organization.name_ar or offer.buyer_organization.name
    return out


@router.get("", response_model=PaginatedResponse[OfferOut])
async def list_my_offers(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
):
    org_id = await _get_org_id(current_user, db)
    repo = OfferRepository(db)
    rows, total = await repo.list_by_buyer_org(
        org_id, offset=(page - 1) * page_size, limit=page_size
    )
    return PaginatedResponse(
        items=[_to_offer_out(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/incoming", response_model=PaginatedResponse[OfferOut])
async def list_incoming_offers(
    db: DbSession,
    current_user: CurrentUser,
    listing_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
):
    # scoped to listings this organization owns — never the whole platform
    org_id = await _get_org_id(current_user, db)
    repo = OfferRepository(db)
    rows, total = await repo.list_by_seller_org(
        org_id,
        listing_id=listing_id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse(
        items=[_to_offer_out(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/{offer_id}/accept", response_model=OfferOut)
async def accept_offer(
    offer_id: uuid.UUID,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _get_org_id(current_user, db)
    svc = OfferService(db)
    offer = await svc.accept_offer(
        offer_id, org_id, current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return OfferOut.model_validate(offer)


@router.post("/{offer_id}/reject", response_model=OfferOut)
async def reject_offer(
    offer_id: uuid.UUID,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
    seller_note: str | None = None,
):
    org_id = await _get_org_id(current_user, db)
    svc = OfferService(db)
    offer = await svc.reject_offer(
        offer_id, org_id, current_user.id,
        seller_note=seller_note,
        ip_address=request.client.host if request.client else None,
    )
    return OfferOut.model_validate(offer)


@router.post("/{offer_id}/cancel", response_model=OfferOut)
async def cancel_offer(
    offer_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    org_id = await _get_org_id(current_user, db)
    svc = OfferService(db)
    offer = await svc.cancel_offer(offer_id, org_id, current_user.id)
    return OfferOut.model_validate(offer)
