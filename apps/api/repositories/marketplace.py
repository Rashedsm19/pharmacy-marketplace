"""Marketplace listing, offer, and reservation repositories."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import and_, func, null, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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

    @staticmethod
    def _haversine_km(lat: float, lng: float):
        """SQL expression: great-circle distance (km) from (lat, lng) to the branch."""
        from models.branch import PharmacyBranch

        earth_radius_km = 6371.0088
        lat1 = func.radians(lat)
        lng1 = func.radians(lng)
        lat2 = func.radians(PharmacyBranch.latitude)
        lng2 = func.radians(PharmacyBranch.longitude)
        a = (
            func.power(func.sin((lat2 - lat1) / 2), 2)
            + func.cos(lat1) * func.cos(lat2) * func.power(func.sin((lng2 - lng1) / 2), 2)
        )
        # asin(sqrt(a)) is numerically safer than atan2 for small distances; clamp
        # sqrt(a) at 1 so floating error never pushes asin out of its domain.
        return 2 * earth_radius_km * func.asin(func.least(1.0, func.sqrt(a)))

    async def search(
        self,
        search: str | None = None,
        status: ListingStatus | None = None,
        category_id: uuid.UUID | None = None,
        seller_org_id: uuid.UUID | None = None,
        exclude_org_id: uuid.UUID | None = None,
        near_lat: float | None = None,
        near_lng: float | None = None,
        radius_km: float | None = None,
        sort: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[tuple[MarketplaceListing, float | None]], int]:
        """Listing search returning (listing, distance_km) pairs.

        distance_km is None unless near_lat/near_lng are given, and None for
        listings whose branch has no coordinates. When radius_km is given,
        branches without coordinates are excluded.
        """
        from models.branch import PharmacyBranch
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

        has_point = near_lat is not None and near_lng is not None
        distance_expr = None
        if has_point:
            distance_expr = self._haversine_km(near_lat, near_lng).label("distance_km")
            q = select(MarketplaceListing, distance_expr).join(
                PharmacyBranch, MarketplaceListing.seller_branch_id == PharmacyBranch.id
            )
            if radius_km is not None:
                clauses.append(PharmacyBranch.latitude.is_not(None))
                clauses.append(PharmacyBranch.longitude.is_not(None))
                clauses.append(distance_expr <= radius_km)
        else:
            q = select(MarketplaceListing, null().label("distance_km"))

        q = q.where(and_(*clauses))

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

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        if sort == "distance" and has_point:
            order = (distance_expr.asc().nulls_last(), MarketplaceListing.created_at.desc())
        else:
            order = (MarketplaceListing.created_at.desc(),)

        result = await self.db.execute(q.order_by(*order).offset(offset).limit(limit))
        rows: list[tuple[MarketplaceListing, float | None]] = []
        for listing, distance in result.all():
            rows.append((listing, round(float(distance), 1) if distance is not None else None))
        return rows, total

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
        rows, total = await self.search(
            search=search,
            status=status,
            category_id=category_id,
            seller_org_id=seller_org_id,
            exclude_org_id=exclude_org_id,
            offset=offset,
            limit=limit,
        )
        return [listing for listing, _ in rows], total

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

    async def list_by_seller_org(
        self,
        seller_org_id: uuid.UUID,
        listing_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[ListingOffer], int]:
        """Offers received on listings owned by this organization."""
        clauses = [
            MarketplaceListing.seller_organization_id == seller_org_id,
            ListingOffer.deleted_at.is_(None),
        ]
        if listing_id:
            clauses.append(ListingOffer.listing_id == listing_id)

        count_stmt = (
            select(func.count())
            .select_from(ListingOffer)
            .join(MarketplaceListing, MarketplaceListing.id == ListingOffer.listing_id)
            .where(*clauses)
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            select(ListingOffer)
            .join(MarketplaceListing, MarketplaceListing.id == ListingOffer.listing_id)
            .where(*clauses)
            .options(
                selectinload(ListingOffer.listing).selectinload(MarketplaceListing.batch),
                selectinload(ListingOffer.buyer_organization),
            )
            .order_by(ListingOffer.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return rows, total

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

        count_stmt = select(func.count()).select_from(ListingOffer).where(*clauses)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            select(ListingOffer)
            .where(*clauses)
            .options(
                selectinload(ListingOffer.listing).selectinload(MarketplaceListing.batch),
                selectinload(ListingOffer.buyer_organization),
            )
            .order_by(ListingOffer.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return rows, total

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
