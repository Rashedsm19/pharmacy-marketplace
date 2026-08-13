"""
APScheduler setup — near-expiry scan job runs every 6 hours.
"""
from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings

logger = logging.getLogger(__name__)


async def scan_near_expiry_batches() -> None:
    """
    Scans all inventory batches for approaching expiry thresholds.
    Creates notifications for 180 / 90 / 30 day thresholds.
    Optionally triggers auto-listing if org allows it.
    """
    logger.info("Starting near-expiry scan...")
    from database import get_db_context
    from repositories.inventory import InventoryBatchRepository
    from services.notification_service import NotificationService

    async with get_db_context() as db:
        try:
            batch_repo = InventoryBatchRepository(db)
            batches = await batch_repo.list_all_active_for_scan()
            today = date.today()
            notification_svc = NotificationService(db)

            for batch in batches:
                days = (batch.expiry_date - today).days

                # Get org members to notify
                from sqlalchemy import select
                from models.organization import UserOrganizationMembership, MembershipRole
                result = await db.execute(
                    select(UserOrganizationMembership).where(
                        UserOrganizationMembership.organization_id == batch.organization_id,
                        UserOrganizationMembership.is_active.is_(True),
                        UserOrganizationMembership.role.in_(
                            [MembershipRole.OWNER, MembershipRole.ADMIN]
                        ),
                    )
                )
                members = result.scalars().all()

                product_name = batch.product.name if batch.product else "Unknown"

                # 30-day threshold
                if days <= 30 and not batch.notified_30:
                    for m in members:
                        await notification_svc.create_near_expiry_notification(
                            m.user_id, batch.organization_id, batch.id, product_name, days
                        )
                    batch.notified_30 = True
                    # Auto-listing check
                    if batch.organization.allow_auto_listing:
                        await _auto_list_batch(db, batch, days)

                # 90-day threshold
                elif days <= 90 and not batch.notified_90:
                    for m in members:
                        await notification_svc.create_near_expiry_notification(
                            m.user_id, batch.organization_id, batch.id, product_name, days
                        )
                    batch.notified_90 = True

                # 180-day threshold
                elif days <= 180 and not batch.notified_180:
                    for m in members:
                        await notification_svc.create_near_expiry_notification(
                            m.user_id, batch.organization_id, batch.id, product_name, days
                        )
                    batch.notified_180 = True

            await db.commit()
            logger.info("Near-expiry scan complete — processed %d batches", len(batches))
        except Exception as exc:
            logger.error("Near-expiry scan failed: %s", exc, exc_info=True)
            await db.rollback()


async def _auto_list_batch(db, batch, days: int) -> None:
    """Create a marketplace listing automatically if org allows it."""
    from repositories.inventory import NearExpiryRuleRepository
    from services.eligibility_service import EligibilityService
    from models.marketplace import MarketplaceListing, ListingStatus
    from models.inventory import BatchStatus
    import uuid

    rule_repo = NearExpiryRuleRepository(db)
    rule = await rule_repo.get_by_org(batch.organization_id)
    if not rule or not rule.allow_auto_listing:
        return

    eligibility_svc = EligibilityService(db)
    eligibility = await eligibility_svc.check_listing_eligibility(batch.id, batch.organization_id)
    if not eligibility.all_passed:
        return

    if not batch.unit_cost:
        return

    discount = rule.auto_listing_discount_pct / 100
    asking_price = float(batch.unit_cost) * (1 - discount) * batch.quantity_available

    product_name = batch.product.name if batch.product else "Product"
    listing = MarketplaceListing(
        id=uuid.uuid4(),
        seller_organization_id=batch.organization_id,
        seller_branch_id=batch.branch_id,
        batch_id=batch.id,
        created_by_id=None,  # system-created
        title=f"Auto-listed: {product_name} (expires in {days} days)",
        title_ar=f"إدراج تلقائي: {product_name} (ينتهي خلال {days} يوم)",
        quantity_listed=batch.quantity_available,
        quantity_available=batch.quantity_available,
        asking_price=asking_price,
        allow_offers=True,
        eligibility_passed=True,
        status=ListingStatus.ACTIVE,
    )
    db.add(listing)
    batch.status = BatchStatus.LISTED


async def expire_stale_reservations() -> None:
    """Release listings held by reservations nobody completed.

    A reservation is good for a week. Without this the listing stays RESERVED
    for ever and the seller can never sell that stock again.
    """
    from database import AsyncSessionLocal
    from models.marketplace import ListingStatus, ReservationStatus
    from models.notification import NotificationType
    from repositories.marketplace import ListingRepository, ReservationRepository
    from services.notification_service import NotificationService

    async with AsyncSessionLocal() as db:
        try:
            res_repo = ReservationRepository(db)
            listing_repo = ListingRepository(db)
            notifier = NotificationService(db)

            expired = await res_repo.list_expired_active()
            if not expired:
                logger.info("Reservation sweep: nothing expired")
                return

            for reservation in expired:
                reservation.status = ReservationStatus.EXPIRED

                listing = await listing_repo.get(reservation.listing_id)
                product = None
                if listing:
                    # Only hand it back to the market if it is still held; a listing
                    # already sold or cancelled must keep its final state.
                    if listing.status == ListingStatus.RESERVED:
                        listing.status = ListingStatus.ACTIVE
                    product = (
                        listing.batch.product.name_ar or listing.batch.product.name
                        if listing.batch and listing.batch.product
                        else None
                    )

                label = product or "العرض"
                await notifier.create(
                    user_id=reservation.reserved_by_id,
                    notification_type=NotificationType.RESERVATION_EXPIRED,
                    title=f"Reservation expired: {label}",
                    title_ar=f"انتهت مهلة الحجز: {label}",
                    body="The reservation expired before the transaction was created.",
                    body_ar="انتهت مهلة الحجز قبل إنشاء المعاملة، وأُعيد العرض إلى السوق.",
                    organization_id=reservation.buyer_organization_id,
                    resource_type="reservation",
                    resource_id=reservation.id,
                )
                if listing:
                    await notifier.create(
                        user_id=listing.created_by_id,
                        notification_type=NotificationType.RESERVATION_EXPIRED,
                        title=f"Reservation expired: {label}",
                        title_ar=f"انتهت مهلة الحجز: {label}",
                        body="The buyer did not complete the purchase; the listing is back on the market.",
                        body_ar="لم يُكمل المشتري الشراء، وأُعيد عرضك إلى السوق.",
                        organization_id=listing.seller_organization_id,
                        resource_type="listing",
                        resource_id=listing.id,
                    )

            await db.commit()
            logger.info("Reservation sweep: expired %d reservation(s)", len(expired))
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.error("Reservation sweep failed: %s", exc)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scan_near_expiry_batches,
        trigger=IntervalTrigger(hours=settings.NEAR_EXPIRY_SCAN_INTERVAL_HOURS),
        id="near_expiry_scan",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        expire_stale_reservations,
        trigger=IntervalTrigger(hours=settings.RESERVATION_SWEEP_INTERVAL_HOURS),
        id="reservation_sweep",
        replace_existing=True,
        misfire_grace_time=300,
    )
    return scheduler
