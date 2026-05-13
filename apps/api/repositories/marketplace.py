"""Marketplace listing, offer, and reservation repositories."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.marketplace import (
    ListingOffer,
    ListingStatus,
    MarketplaceListing,
    OfferStatus,
    Reservation,
    ReservationStatus,
)
from repositories.base import BaseRepository


class ListingRepository(BaseRepository[MarketplaceListing]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(MarketplaceListing, db)

    async def list_active(
        self,
        search: str | None = None,
        status: ListingStatus | None = None,
        category_id: uuid.UUID | None = None,
        seller_org_id: uuid.UUID | None = None,
        exclude_org_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[MarketplaceListing], int]:
        from models.inventory import InventoryBatch
        from models.product import Product

        clauses = [MarketplaceListing.deleted_at.is_(None)]
        if status:
            clauses.append(MarketplaceListing.status == status)
        else:
            clauses.append(MarketplaceListing.status == ListingStatus.ACTIVE)
        if seller_org_id:
            clauses.append(MarketplaceListing.seller_organization_id == seller_org_id)
        if exclude_org_id:
            clauses.append(MarketplaceListing.seller_organization_id != exclude_org_id)

        q = select(MarketplaceListing).where(and_(*clauses))

        if category_id or search:
            q = q.join(InventoryBatch, MarketplaceListing.batch_id == InventoryBatch.id)
            if category_id:
                q = q.join(Product, InventoryBatch.product_id == Product.id).where(
                    Product.category_id == category_id
                )
            if search:
                q = q.where(
                    or_(
                        MarketplaceListing.title.ilike(f"%{search}%"),
                        MarketplaceListing.title_ar.ilike(f"%{search}%"),
                    )
                )

        from sqlalchemy import func
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()
        rows = (
            await self.db.execute(
                q.order_by(MarketplaceListing.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return rows, total

    async def get_by_org(
        self, listing_id: uuid.UUID, org_id: uuid.UUID
    ) -> MarketplaceListing | None:
        result = await self.db.execute(
            select(MarketplaceListing).where(
                MarketplaceListing.id == listing_id,
                MarketplaceListing.seller_organization_id == org_id,
                MarketplaceListing.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


class OfferRepository(BaseRepository[ListingOffer]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ListingOffer, db)

    async def list_by_listing(
        self,
        listing_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[ListingOffer], int]:
        return await self.get_many(
            ListingOffer.listing_id == listing_id,
            ListingOffer.deleted_at.is_(None),
            offset=offset,
            limit=limit,
        )

    async def list_by_buyer_org(
        self,
        buyer_org_id: uuid.UUID,
        status: OfferStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[ListingOffer], int]:
        clauses = [
            ListingOffer.buyer_organization_id == buyer_org_id,
            ListingOffer.deleted_at.is_(None),
        ]
        if status:
            clauses.append(ListingOffer.status == status)
        return await self.get_many(*clauses, offset=offset, limit=limit)

    async def get_by_buyer_and_listing(
        self,
        listing_id: uuid.UUID,
        buyer_org_id: uuid.UUID,
    ) -> ListingOffer | None:
        result = await self.db.execute(
            select(ListingOffer).where(
                ListingOffer.listing_id == listing_id,
                ListingOffer.buyer_organization_id == buyer_org_id,
                ListingOffer.status == OfferStatus.PENDING,
                ListingOffer.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_org_and_id(
        self, offer_id: uuid.UUID, org_id: uuid.UUID
    ) -> ListingOffer | None:
        result = await self.db.execute(
            select(ListingOffer).where(
                ListingOffer.id == offer_id,
                or_(
                    ListingOffer.buyer_organization_id == org_id,
                ),
                ListingOffer.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


class ReservationRepository(BaseRepository[Reservation]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Reservation, db)

    async def get_by_listing(self, listing_id: uuid.UUID) -> Reservation | None:
        result = await self.db.execute(
            select(Reservation).where(Reservation.listing_id == listing_id)
        )
        return result.scalar_one_or_none()

    async def list_by_buyer_org(
        self,
        buyer_org_id: uuid.UUID,
        status: ReservationStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Reservation], int]:
        clauses = [Reservation.buyer_organization_id == buyer_org_id]
        if status:
            clauses.append(Reservation.status == status)
        return await self.get_many(*clauses, offset=offset, limit=limit)

    async def list_expired_active(self) -> Sequence[Reservation]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Reservation).where(
                Reservation.status == ReservationStatus.ACTIVE,
                Reservation.expires_at < now,
            )
        )
        return result.scalars().all()
