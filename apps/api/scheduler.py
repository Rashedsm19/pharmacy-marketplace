"""
APScheduler setup — near-expiry scan job runs every 6 hours.
"""
from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from datetime import date, datetime, timedelta, timezone

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

    # Both of these were wrong and each was severe on its own.
    #
    # `auto_listing_discount_pct` is Numeric, so it reads back as Decimal, and
    # `float * Decimal` raises TypeError. That exception propagated to the scan's
    # handler, which rolls the whole tick back — so a single auto-listable batch
    # silently killed near-expiry alerting for the entire platform, every six
    # hours, permanently.
    #
    # And the price was computed for the whole lot while every consumer reads it
    # per unit: `transaction_service` multiplies it by quantity again. A batch of
    # 120 at 12.50 would have billed 144,000 riyals instead of 1,200 — and that
    # figure goes onto a signed tax invoice.
    discount = Decimal(str(rule.auto_listing_discount_pct or 0)) / Decimal("100")
    unit_price = (Decimal(str(batch.unit_cost)) * (Decimal("1") - discount)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    asking_price = float(unit_price)

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
                    body_ar="انتهت مهلة الحجز قبل إنشاء المعاملة، وأعيد العرض إلى السوق.",
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
                        body_ar="لم يكمل المشتري الشراء، وأعيد عرضك إلى السوق.",
                        organization_id=listing.seller_organization_id,
                        resource_type="listing",
                        resource_id=listing.id,
                    )

            await db.commit()
            logger.info("Reservation sweep: expired %d reservation(s)", len(expired))
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.error("Reservation sweep failed: %s", exc)


async def retry_invoice_clearance() -> None:
    """Re-submit invoices the authority has not accepted yet.

    Clearance is deliberately non-blocking at sale time, so this is the path by
    which a transient outage eventually resolves itself.
    """
    from database import AsyncSessionLocal
    from services.invoice_service import InvoiceService

    async with AsyncSessionLocal() as db:
        try:
            svc = InvoiceService(db)
            pending = await svc.pending_retries()
            if not pending:
                return
            cleared = 0
            for invoice in pending:
                if await svc.attempt_clearance(invoice):
                    cleared += 1
            await db.commit()
            logger.info(
                "Invoice clearance retry: %d/%d cleared", cleared, len(pending)
            )
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.error("Invoice clearance retry failed: %s", exc)


async def process_import_jobs() -> None:
    """Pick up queued inventory imports and run them.

    Jobs are claimed with a row lock and SKIP LOCKED so that two instances — or
    two ticks that overlap because a big file is still running — never process
    the same file twice. One job per tick keeps a ten thousand row import from
    starving everything else on a small instance.
    """
    from sqlalchemy import select

    from sqlalchemy import update as sql_update

    from database import AsyncSessionLocal
    from models.import_job import ImportJob, ImportStatus
    from services.import_service import process_job

    async with AsyncSessionLocal() as db:
        try:
            # A job left PROCESSING by a redeploy would sit there for ever:
            # the claim query only looks at QUEUED and nothing ever revisits it.
            # Anything that has been "processing" far longer than any real file
            # takes is put back in the queue.
            stale_before = datetime.now(timezone.utc) - timedelta(minutes=30)
            requeued = await db.execute(
                sql_update(ImportJob)
                .where(
                    ImportJob.status == ImportStatus.PROCESSING,
                    ImportJob.started_at < stale_before,
                )
                .values(status=ImportStatus.QUEUED, started_at=None)
            )
            if requeued.rowcount:
                logger.warning("Requeued %d stalled import job(s)", requeued.rowcount)
                await db.commit()

            job = (
                await db.execute(
                    select(ImportJob)
                    .where(ImportJob.status == ImportStatus.QUEUED)
                    .order_by(ImportJob.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if job is None:
                return

            logger.info("Processing import job %s (%s)", job.id, job.filename)
            await process_job(db, job)
            logger.info(
                "Import job %s finished: %s (+%d batches, ~%d updated, %d failed)",
                job.id,
                job.status,
                job.created_batches,
                job.updated_batches,
                job.failed_rows,
            )
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.error("Import worker failed: %s", exc)


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
        retry_invoice_clearance,
        trigger=IntervalTrigger(minutes=settings.INVOICE_RETRY_INTERVAL_MINUTES),
        id="invoice_clearance_retry",
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
    scheduler.add_job(
        process_import_jobs,
        trigger=IntervalTrigger(seconds=settings.IMPORT_POLL_INTERVAL_SECONDS),
        id="import_worker",
        replace_existing=True,
        # A customer is watching a progress bar; a missed tick should run now,
        # and only one instance of the worker may run at a time.
        misfire_grace_time=60,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
