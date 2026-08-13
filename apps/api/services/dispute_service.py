"""
Dispute handling.

Opening a case moves the transaction to DISPUTED so it stops looking settled.
Resolving it is where the real work happens: a refund returns the disputed units
to the seller's batch, records the movement, and — because a transfer that is
reversed is itself a reportable event — leaves a trail the regulator can follow.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.dispute import CRITICAL_REASONS, Dispute, DisputeReason, DisputeStatus
from models.inventory import InventoryMovement, MovementType
from models.notification import NotificationType
from models.organization import OrganizationStatus, PharmacyOrganization
from models.transaction import Transaction, TransactionStatus
from repositories.marketplace import ListingRepository
from repositories.transaction import TransactionRepository
from services.audit_service import AuditService
from services.notification_service import NotificationService

logger = logging.getLogger("api.disputes")

# A case can only be opened while the outcome is still meaningful.
DISPUTABLE_STATUSES = {
    TransactionStatus.DISPATCHED,
    TransactionStatus.IN_TRANSIT,
    TransactionStatus.DELIVERED,
    TransactionStatus.COMPLETED,
}
OPEN_STATUSES = {DisputeStatus.OPEN, DisputeStatus.SELLER_RESPONDED}


class DisputeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.tx_repo = TransactionRepository(db)
        self.listing_repo = ListingRepository(db)
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    async def _transaction_for(self, transaction_id: uuid.UUID) -> Transaction:
        tx = await self.tx_repo.get(transaction_id)
        if not tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المعاملة غير موجودة")
        return tx

    async def open_dispute(
        self,
        transaction_id: uuid.UUID,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: DisputeReason,
        description: str,
        disputed_quantity: int | None = None,
        evidence_url: str | None = None,
        ip_address: str | None = None,
    ) -> Dispute:
        tx = await self._transaction_for(transaction_id)

        # Either side may raise a case, but only the two sides of this trade.
        if org_id not in (tx.buyer_organization_id, tx.seller_organization_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مخوَّل")

        # Checked before the status guard: opening a case is what moves the
        # transaction to DISPUTED, so "a case is already open" is the accurate
        # answer to a second attempt, not "the status is wrong".
        existing = (
            await self.db.execute(
                select(Dispute).where(
                    Dispute.transaction_id == transaction_id,
                    Dispute.status.in_(OPEN_STATUSES),
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="يوجد نزاع مفتوح على هذه المعاملة",
            )

        if tx.status not in DISPUTABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"لا يمكن فتح نزاع على معاملة في حالة «{tx.status}»",
            )

        if disputed_quantity is not None and not (0 < disputed_quantity <= tx.quantity):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"الكمية محل النزاع يجب أن تكون بين ١ و{tx.quantity}",
            )

        dispute = Dispute(
            id=uuid.uuid4(),
            transaction_id=transaction_id,
            raised_by_id=actor_id,
            raised_by_organization_id=org_id,
            reason=reason,
            description=description,
            disputed_quantity=disputed_quantity,
            evidence_url=evidence_url,
            status=DisputeStatus.OPEN,
        )
        self.db.add(dispute)

        before_status = tx.status
        tx.status = TransactionStatus.DISPUTED
        tx.dispute_reason = f"{reason.value}: {description[:200]}"

        # A counterfeit claim suspends the seller straight away rather than
        # waiting for a decision — the risk of it spreading outweighs the delay.
        if reason in CRITICAL_REASONS:
            counterparty_id = (
                tx.seller_organization_id
                if org_id == tx.buyer_organization_id
                else tx.buyer_organization_id
            )
            org = (
                await self.db.execute(
                    select(PharmacyOrganization).where(PharmacyOrganization.id == counterparty_id)
                )
            ).scalar_one_or_none()
            if org and org.status == OrganizationStatus.APPROVED:
                org.status = OrganizationStatus.SUSPENDED
                org.suspension_reason = "بلاغ اشتباه بمنتج مزيّف — قيد التحقيق"
                logger.warning("Suspended org %s after counterfeit report", counterparty_id)

        await self.db.flush()
        await self._notify_counterparty(
            tx,
            org_id,
            NotificationType.SYSTEM,
            "Dispute opened",
            "فُتح نزاع على معاملة",
            "A dispute was opened on one of your transactions.",
            f"فُتح نزاع على المعاملة {tx.reference_number}. راجعه وقدّم ردّك.",
            dispute.id,
        )
        await self.audit.log(
            action="dispute_opened",
            resource_type="dispute",
            resource_id=dispute.id,
            actor_id=actor_id,
            organization_id=org_id,
            before_state={"transaction_status": before_status},
            after_state={"reason": reason, "quantity": disputed_quantity},
            ip_address=ip_address,
        )
        return dispute

    async def respond(
        self,
        dispute_id: uuid.UUID,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        response: str,
        ip_address: str | None = None,
    ) -> Dispute:
        dispute = await self._get(dispute_id)
        tx = await self._transaction_for(dispute.transaction_id)

        # The response belongs to the side that did not raise the case.
        if org_id == dispute.raised_by_organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="الرد على النزاع من حق الطرف الآخر",
            )
        if org_id not in (tx.buyer_organization_id, tx.seller_organization_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مخوَّل")
        if dispute.status not in OPEN_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="النزاع مغلق"
            )

        dispute.seller_response = response
        dispute.seller_responded_at = datetime.now(timezone.utc)
        dispute.status = DisputeStatus.SELLER_RESPONDED
        await self.db.flush()

        await self.audit.log(
            action="dispute_responded",
            resource_type="dispute",
            resource_id=dispute.id,
            actor_id=actor_id,
            organization_id=org_id,
            ip_address=ip_address,
        )
        return dispute

    async def resolve(
        self,
        dispute_id: uuid.UUID,
        actor_id: uuid.UUID,
        outcome: DisputeStatus,
        notes: str,
        ip_address: str | None = None,
    ) -> Dispute:
        """Platform decision. A refund returns stock and reverses the sale."""
        if outcome not in {
            DisputeStatus.RESOLVED_REFUND,
            DisputeStatus.RESOLVED_REPLACEMENT,
            DisputeStatus.RESOLVED_REJECTED,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="قرار غير معروف"
            )

        dispute = await self._get(dispute_id)
        if dispute.status not in OPEN_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="النزاع محسوم مسبقاً"
            )

        tx = await self._transaction_for(dispute.transaction_id)
        quantity = dispute.disputed_quantity or tx.quantity

        if outcome == DisputeStatus.RESOLVED_REFUND:
            await self._return_stock(tx, quantity, actor_id)
            unit_price = Decimal(str(tx.unit_price))
            dispute.refund_amount = float(
                (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))
            )
            tx.status = (
                TransactionStatus.REFUNDED
                if quantity == tx.quantity
                else TransactionStatus.COMPLETED
            )
        else:
            # Rejected or replaced: the sale stands as completed.
            tx.status = TransactionStatus.COMPLETED

        dispute.status = outcome
        dispute.resolution_notes = notes
        dispute.resolved_by_id = actor_id
        dispute.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()

        for org_id in (tx.buyer_organization_id, tx.seller_organization_id):
            await self._notify_org(
                org_id,
                "Dispute resolved",
                "حُسم النزاع",
                f"The dispute on {tx.reference_number} was resolved.",
                f"صدر قرار في النزاع على المعاملة {tx.reference_number}.",
                dispute.id,
            )

        await self.audit.log(
            action="dispute_resolved",
            resource_type="dispute",
            resource_id=dispute.id,
            actor_id=actor_id,
            after_state={
                "outcome": outcome,
                "refund_amount": dispute.refund_amount,
                "returned_quantity": quantity if outcome == DisputeStatus.RESOLVED_REFUND else 0,
            },
            ip_address=ip_address,
        )
        return dispute

    async def _return_stock(
        self, tx: Transaction, quantity: int, actor_id: uuid.UUID
    ) -> None:
        """Put the refunded units back on the seller's batch, with a movement."""
        listing = await self.listing_repo.get(tx.listing_id)
        if not listing or not listing.batch:
            logger.warning("Refund for tx %s has no batch to restore", tx.id)
            return

        batch = listing.batch
        before = batch.quantity_available
        batch.quantity_available = before + quantity

        from models.inventory import BatchStatus

        # Stock is back, so a batch previously marked sold is available again.
        if batch.status == BatchStatus.SOLD and batch.quantity_available > 0:
            batch.status = BatchStatus.ACTIVE

        self.db.add(
            InventoryMovement(
                id=uuid.uuid4(),
                organization_id=tx.seller_organization_id,
                batch_id=batch.id,
                movement_type=MovementType.ADJUSTED,
                quantity_delta=quantity,
                quantity_before=before,
                quantity_after=batch.quantity_available,
                reference_type="dispute_refund",
                reference_id=tx.id,
                performed_by_id=actor_id,
                notes="إرجاع كمية إثر حسم نزاع",
            )
        )

    async def _get(self, dispute_id: uuid.UUID) -> Dispute:
        dispute = (
            await self.db.execute(select(Dispute).where(Dispute.id == dispute_id))
        ).scalar_one_or_none()
        if not dispute:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="النزاع غير موجود")
        return dispute

    async def _notify_counterparty(
        self, tx: Transaction, raiser_org_id: uuid.UUID, ntype, title, title_ar, body, body_ar, ref
    ) -> None:
        other = (
            tx.seller_organization_id
            if raiser_org_id == tx.buyer_organization_id
            else tx.buyer_organization_id
        )
        await self._notify_org(other, title, title_ar, body, body_ar, ref)

    async def _notify_org(self, org_id, title, title_ar, body, body_ar, ref) -> None:
        from models.organization import UserOrganizationMembership

        members = (
            await self.db.execute(
                select(UserOrganizationMembership).where(
                    UserOrganizationMembership.organization_id == org_id,
                    UserOrganizationMembership.is_active.is_(True),
                )
            )
        ).scalars().all()
        for member in members:
            await self.notifier.create(
                user_id=member.user_id,
                notification_type=NotificationType.SYSTEM,
                title=title,
                title_ar=title_ar,
                body=body,
                body_ar=body_ar,
                organization_id=org_id,
                resource_type="dispute",
                resource_id=ref,
            )
