"""Listing service — create, update, cancel with eligibility check."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.inventory import BatchStatus
from models.marketplace import ListingStatus, MarketplaceListing
from repositories.inventory import InventoryBatchRepository
from repositories.marketplace import ListingRepository
from schemas.marketplace import ListingCreate, ListingUpdate
from services.audit_service import AuditService
from services.eligibility_service import EligibilityService
from services.notification_service import NotificationService
from models.notification import NotificationType


class ListingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.listing_repo = ListingRepository(db)
        self.batch_repo = InventoryBatchRepository(db)
        self.eligibility = EligibilityService(db)
        self.audit = AuditService(db)

    async def create_listing(
        self,
        data: ListingCreate,
        org_id: uuid.UUID,
        created_by: uuid.UUID,
        ip_address: str | None = None,
    ) -> MarketplaceListing:
        # Run eligibility check
        eligibility = await self.eligibility.check_listing_eligibility(data.batch_id, org_id)
        if not eligibility.all_passed:
            reasons = [r.reason for r in eligibility.rules if not r.passed and r.reason]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Listing eligibility check failed", "reasons": reasons},
            )

        # Validate quantity
        batch = await self.batch_repo.get_by_org(data.batch_id, org_id)
        if data.quantity_listed > batch.quantity_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested quantity {data.quantity_listed} exceeds available {batch.quantity_available}",
            )

        listing = MarketplaceListing(
            id=uuid.uuid4(),
            seller_organization_id=org_id,
            seller_branch_id=data.seller_branch_id,
            batch_id=data.batch_id,
            created_by_id=created_by,
            title=data.title,
            title_ar=data.title_ar,
            description=data.description,
            quantity_listed=data.quantity_listed,
            quantity_available=data.quantity_listed,
            asking_price=data.asking_price,
            minimum_offer_price=data.minimum_offer_price,
            allow_offers=data.allow_offers,
            allow_partial_purchase=data.allow_partial_purchase,
            min_purchase_quantity=data.min_purchase_quantity,
            expires_at=data.expires_at,
            eligibility_passed=True,
            eligibility_result=json.dumps([r.model_dump() for r in eligibility.rules]),
        )
        self.db.add(listing)

        # Update batch status to LISTED
        batch.status = BatchStatus.LISTED
        await self.db.flush()

        await self.audit.log(
            action="listing_created",
            resource_type="marketplace_listing",
            resource_id=listing.id,
            actor_id=created_by,
            organization_id=org_id,
            after_state={"listing_id": str(listing.id), "batch_id": str(data.batch_id)},
            ip_address=ip_address,
        )

        return listing

    async def cancel_listing(
        self,
        listing_id: uuid.UUID,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> MarketplaceListing:
        listing = await self.listing_repo.get_by_org(listing_id, org_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

        if listing.status not in (ListingStatus.ACTIVE, ListingStatus.DRAFT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel a listing in '{listing.status}' state",
            )

        before_state = {"status": listing.status}
        listing.status = ListingStatus.CANCELLED

        # Restore batch status
        batch = await self.batch_repo.get_by_org(listing.batch_id, org_id)
        if batch and batch.status == BatchStatus.LISTED:
            batch.status = BatchStatus.ACTIVE

        await self.db.flush()

        await self.audit.log(
            action="listing_cancelled",
            resource_type="marketplace_listing",
            resource_id=listing.id,
            actor_id=actor_id,
            organization_id=org_id,
            before_state=before_state,
            after_state={"status": "cancelled"},
            ip_address=ip_address,
        )
        return listing
