"""Transaction service — dispatch, receipt, completion."""
from __future__ import annotations

import uuid
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.inventory import BatchStatus, InventoryMovement, MovementType
from models.marketplace import ListingStatus, ReservationStatus
from models.transaction import Transaction, TransactionStatus
from repositories.marketplace import ListingRepository, ReservationRepository
from repositories.transaction import TransactionRepository
from services.audit_service import AuditService


class TransactionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.tx_repo = TransactionRepository(db)
        self.listing_repo = ListingRepository(db)
        self.reservation_repo = ReservationRepository(db)
        self.audit = AuditService(db)

    def _generate_ref(self) -> str:
        return f"TXN-{secrets.token_hex(6).upper()}"

    async def create_from_reservation(
        self,
        reservation_id: uuid.UUID,
        buyer_org_id: uuid.UUID,
        actor_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> Transaction:
        reservation = await self.reservation_repo.get(reservation_id)
        if not reservation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
        if reservation.buyer_organization_id != buyer_org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        if reservation.status != ReservationStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reservation is not active",
            )

        listing = await self.listing_repo.get(reservation.listing_id)
        total = reservation.quantity * reservation.agreed_price
        platform_fee = round(total * 0.02, 2)  # 2% platform fee

        tx = Transaction(
            id=uuid.uuid4(),
            listing_id=reservation.listing_id,
            reservation_id=reservation_id,
            seller_organization_id=listing.seller_organization_id,
            buyer_organization_id=buyer_org_id,
            quantity=reservation.quantity,
            unit_price=reservation.agreed_price,
            total_amount=total,
            platform_fee=platform_fee,
            net_amount=total - platform_fee,
            reference_number=self._generate_ref(),
        )
        self.db.add(tx)

        reservation.status = ReservationStatus.CONFIRMED
        reservation.confirmed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return tx

    async def dispatch(
        self,
        tx_id: uuid.UUID,
        seller_org_id: uuid.UUID,
        actor_id: uuid.UUID,
        tracking_number: str | None = None,
        seller_notes: str | None = None,
        ip_address: str | None = None,
    ) -> Transaction:
        tx = await self.tx_repo.get(tx_id)
        if not tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        if tx.seller_organization_id != seller_org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        if tx.status != TransactionStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction is in '{tx.status}' state",
            )

        tx.status = TransactionStatus.DISPATCHED
        tx.dispatched_at = datetime.now(timezone.utc)
        tx.dispatched_by_id = actor_id
        tx.delivery_tracking_number = tracking_number
        tx.seller_notes = seller_notes
        await self.db.flush()

        await self.audit.log(
            action="transaction_dispatched",
            resource_type="transaction",
            resource_id=tx_id,
            actor_id=actor_id,
            organization_id=seller_org_id,
            ip_address=ip_address,
        )
        return tx

    async def confirm_receipt(
        self,
        tx_id: uuid.UUID,
        buyer_org_id: uuid.UUID,
        actor_id: uuid.UUID,
        buyer_notes: str | None = None,
        ip_address: str | None = None,
    ) -> Transaction:
        tx = await self.tx_repo.get(tx_id)
        if not tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        if tx.buyer_organization_id != buyer_org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        if tx.status not in (TransactionStatus.DISPATCHED, TransactionStatus.IN_TRANSIT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction has not been dispatched yet",
            )

        tx.status = TransactionStatus.COMPLETED
        tx.received_at = datetime.now(timezone.utc)
        tx.received_by_id = actor_id
        tx.completed_at = datetime.now(timezone.utc)
        tx.buyer_notes = buyer_notes

        # Mark listing as sold
        listing = await self.listing_repo.get(tx.listing_id)
        if listing:
            listing.status = ListingStatus.SOLD

        # Update batch status
        from repositories.inventory import InventoryBatchRepository
        batch_repo = InventoryBatchRepository(self.db)
        batch = await batch_repo.get(listing.batch_id) if listing else None
        if batch:
            batch.status = BatchStatus.SOLD
            # Record movement
            movement = InventoryMovement(
                id=uuid.uuid4(),
                organization_id=tx.seller_organization_id,
                batch_id=batch.id,
                movement_type=MovementType.SOLD,
                quantity_delta=-tx.quantity,
                quantity_before=batch.quantity_available,
                quantity_after=max(0, batch.quantity_available - tx.quantity),
                reference_type="transaction",
                reference_id=tx.id,
                performed_by_id=actor_id,
            )
            batch.quantity_available = max(0, batch.quantity_available - tx.quantity)
            self.db.add(movement)

        await self.db.flush()

        await self.audit.log(
            action="transaction_completed",
            resource_type="transaction",
            resource_id=tx_id,
            actor_id=actor_id,
            organization_id=buyer_org_id,
            ip_address=ip_address,
        )
        return tx
