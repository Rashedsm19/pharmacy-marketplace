"""Offer service — submit, accept, reject, cancel."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.marketplace import ListingOffer, ListingStatus, OfferStatus, ReservationStatus, Reservation
from repositories.marketplace import ListingRepository, OfferRepository, ReservationRepository
from services.audit_service import AuditService
from schemas.marketplace import OfferCreate


class OfferService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.listing_repo = ListingRepository(db)
        self.offer_repo = OfferRepository(db)
        self.reservation_repo = ReservationRepository(db)
        self.audit = AuditService(db)

    async def submit_offer(
        self,
        data: OfferCreate,
        buyer_org_id: uuid.UUID,
        submitted_by: uuid.UUID,
        ip_address: str | None = None,
    ) -> ListingOffer:
        listing = await self.listing_repo.get(data.listing_id)
        if not listing or listing.deleted_at:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

        if listing.status != ListingStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Listing is not available for offers",
            )

        if listing.seller_organization_id == buyer_org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot submit an offer on your own listing",
            )

        if not listing.allow_offers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This listing does not accept offers",
            )

        if listing.minimum_offer_price and data.offered_price < listing.minimum_offer_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Offer price must be at least {listing.minimum_offer_price}",
            )

        if data.quantity > listing.quantity_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested quantity exceeds available",
            )

        # Check for existing pending offer
        existing = await self.offer_repo.get_by_buyer_and_listing(
            data.listing_id, buyer_org_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a pending offer on this listing",
            )

        offer = ListingOffer(
            id=uuid.uuid4(),
            listing_id=data.listing_id,
            buyer_organization_id=buyer_org_id,
            submitted_by_id=submitted_by,
            offered_price=data.offered_price,
            quantity=data.quantity,
            message=data.message,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        )
        self.db.add(offer)
        await self.db.flush()
        return offer

    async def accept_offer(
        self,
        offer_id: uuid.UUID,
        seller_org_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> ListingOffer:
        offer = await self.offer_repo.get(offer_id)
        if not offer or offer.deleted_at:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

        # Verify listing belongs to seller
        listing = await self.listing_repo.get_by_org(offer.listing_id, seller_org_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        if offer.status != OfferStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Offer is in '{offer.status}' state, cannot accept",
            )

        before = {"status": offer.status}
        offer.status = OfferStatus.ACCEPTED
        offer.responded_at = datetime.now(timezone.utc)

        # Reject all other pending offers on this listing
        from sqlalchemy import select, update
        await self.db.execute(
            update(ListingOffer).where(
                ListingOffer.listing_id == offer.listing_id,
                ListingOffer.id != offer_id,
                ListingOffer.status == OfferStatus.PENDING,
            ).values(status=OfferStatus.REJECTED, responded_at=datetime.now(timezone.utc)),
            execution_options={"synchronize_session": False},
        )

        # Create reservation
        reservation = Reservation(
            id=uuid.uuid4(),
            listing_id=offer.listing_id,
            offer_id=offer_id,
            buyer_organization_id=offer.buyer_organization_id,
            reserved_by_id=actor_id,
            quantity=offer.quantity,
            agreed_price=offer.offered_price,
            status=ReservationStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        self.db.add(reservation)

        # Update listing status
        listing.status = ListingStatus.RESERVED
        await self.db.flush()
        await self.db.refresh(offer)

        await self.audit.log(
            action="offer_accepted",
            resource_type="listing_offer",
            resource_id=offer_id,
            actor_id=actor_id,
            organization_id=seller_org_id,
            before_state=before,
            after_state={"status": "accepted"},
            ip_address=ip_address,
        )
        return offer

    async def reject_offer(
        self,
        offer_id: uuid.UUID,
        seller_org_id: uuid.UUID,
        actor_id: uuid.UUID,
        seller_note: str | None = None,
        ip_address: str | None = None,
    ) -> ListingOffer:
        offer = await self.offer_repo.get(offer_id)
        if not offer or offer.deleted_at:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

        listing = await self.listing_repo.get_by_org(offer.listing_id, seller_org_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        if offer.status != OfferStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Offer is in '{offer.status}' state, cannot reject",
            )

        offer.status = OfferStatus.REJECTED
        offer.seller_note = seller_note
        offer.responded_at = datetime.now(timezone.utc)
        await self.db.flush()

        await self.audit.log(
            action="offer_rejected",
            resource_type="listing_offer",
            resource_id=offer_id,
            actor_id=actor_id,
            organization_id=seller_org_id,
            after_state={"status": "rejected"},
            ip_address=ip_address,
        )
        return offer

    async def cancel_offer(
        self,
        offer_id: uuid.UUID,
        buyer_org_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> ListingOffer:
        offer = await self.offer_repo.get(offer_id)
        if not offer or offer.deleted_at:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

        if offer.buyer_organization_id != buyer_org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        if offer.status != OfferStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Offer is in '{offer.status}' state, cannot cancel",
            )

        offer.status = OfferStatus.CANCELLED
        offer.responded_at = datetime.now(timezone.utc)
        await self.db.flush()
        return offer
