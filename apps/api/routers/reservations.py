"""Reservations router."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove
from models.marketplace import ReservationStatus
from repositories.marketplace import ReservationRepository
from repositories.organization import MembershipRepository
from schemas.common import PaginatedResponse
from schemas.marketplace import ReservationOut

router = APIRouter(prefix="/reservations", tags=["Reservations"])


async def _get_org_id(current_user, db) -> uuid.UUID:
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization")
    return org_id


@router.get("", response_model=PaginatedResponse[ReservationOut])
async def list_reservations(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
):
    org_id = await _get_org_id(current_user, db)
    repo = ReservationRepository(db)
    rows, total = await repo.list_by_buyer_org(
        org_id, offset=(page - 1) * page_size, limit=page_size
    )
    return PaginatedResponse(
        items=[ReservationOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{reservation_id}", response_model=ReservationOut)
async def get_reservation(
    reservation_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    repo = ReservationRepository(db)
    reservation = await repo.get(reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    org_id = await _get_org_id(current_user, db)
    if reservation.buyer_organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return ReservationOut.model_validate(reservation)


@router.post("/{reservation_id}/cancel", response_model=ReservationOut)
async def cancel_reservation(
    reservation_id: uuid.UUID,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    org_id = await _get_org_id(current_user, db)
    repo = ReservationRepository(db)
    reservation = await repo.get(reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.buyer_organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if reservation.status != ReservationStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Reservation cannot be cancelled")

    reservation.status = ReservationStatus.CANCELLED

    # Restore listing to active
    from repositories.marketplace import ListingRepository
    from models.marketplace import ListingStatus
    listing_repo = ListingRepository(db)
    listing = await listing_repo.get(reservation.listing_id)
    if listing and listing.status == ListingStatus.RESERVED:
        listing.status = ListingStatus.ACTIVE
    await db.flush()
    return ReservationOut.model_validate(reservation)
