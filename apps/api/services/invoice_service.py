"""
Issuing the tax invoice for a completed sale.

Two rules shape this. The invoice counter and hash chain are per seller and must
have no gaps, so they are read under a row lock. And clearance failing must never
undo the sale — the invoice is stored either way and retried by a scheduled job.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.invoice import Invoice, InvoiceStatus
from models.transaction import Transaction
from services.zatca_service import GENESIS_HASH, build_qr, hash_invoice, zatca_service

logger = logging.getLogger("api.invoices")


class InvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def issue_for_transaction(self, tx: Transaction) -> Invoice | None:
        """Create and attempt to clear the invoice for a completed transaction."""
        existing = (
            await self.db.execute(select(Invoice).where(Invoice.transaction_id == tx.id))
        ).scalar_one_or_none()
        if existing:
            return existing

        seller = tx.seller_organization
        buyer = tx.buyer_organization
        if seller is None or buyer is None:
            logger.error("Transaction %s has no parties to invoice", tx.id)
            return None

        # A seller with no VAT number cannot issue a tax invoice at all. That is
        # a data gap to surface, not a reason to fail the sale.
        if not seller.vat_number:
            logger.warning(
                "Seller %s has no VAT number — no invoice issued for %s", seller.id, tx.id
            )
            return None

        icv, previous_hash = await self._chain_position(seller.id)

        subtotal = Decimal(str(tx.total_amount))
        vat_rate = Decimal(str(settings.VAT_RATE_PCT))
        vat_amount = (subtotal * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        total_with_vat = subtotal + vat_amount

        issued_at = datetime.now(timezone.utc)
        invoice_uuid = str(uuid.uuid4())
        invoice_number = f"INV-{tx.reference_number}"

        product_name = "دواء"
        if tx.listing and tx.listing.batch and tx.listing.batch.product:
            product = tx.listing.batch.product
            product_name = product.name_ar or product.name

        xml_content = zatca_service.build_xml(
            invoice_number=invoice_number,
            invoice_uuid=invoice_uuid,
            icv=icv,
            previous_hash=previous_hash,
            issued_at=issued_at,
            seller_name=seller.name_ar or seller.name,
            seller_vat=seller.vat_number,
            buyer_name=buyer.name_ar or buyer.name,
            buyer_vat=buyer.vat_number,
            line_description=product_name,
            quantity=tx.quantity,
            unit_price=Decimal(str(tx.unit_price)),
            subtotal=subtotal,
            vat_rate=vat_rate,
            vat_amount=vat_amount,
            total_with_vat=total_with_vat,
        )
        invoice_hash = hash_invoice(xml_content)
        qr_code = build_qr(
            seller.name_ar or seller.name,
            seller.vat_number,
            issued_at,
            total_with_vat,
            vat_amount,
        )

        invoice = Invoice(
            id=uuid.uuid4(),
            transaction_id=tx.id,
            seller_organization_id=seller.id,
            buyer_organization_id=buyer.id,
            invoice_number=invoice_number,
            invoice_uuid=invoice_uuid,
            icv=icv,
            previous_hash=previous_hash,
            invoice_hash=invoice_hash,
            issued_at=issued_at,
            subtotal=float(subtotal),
            vat_rate=float(vat_rate),
            vat_amount=float(vat_amount),
            total_with_vat=float(total_with_vat),
            xml_content=xml_content,
            qr_code=qr_code,
            status=InvoiceStatus.PENDING_CLEARANCE,
        )
        self.db.add(invoice)
        await self.db.flush()

        await self.attempt_clearance(invoice)
        return invoice

    async def attempt_clearance(self, invoice: Invoice) -> bool:
        """Submit once. Called on issue and again by the retry job."""
        invoice.attempts += 1
        accepted, response = await zatca_service.clear(
            invoice.invoice_uuid, invoice.invoice_hash, invoice.xml_content
        )
        invoice.clearance_response = response
        if accepted:
            invoice.status = InvoiceStatus.CLEARED
            invoice.cleared_at = datetime.now(timezone.utc)
            invoice.last_error = None
        else:
            invoice.status = InvoiceStatus.FAILED
            invoice.last_error = response[:1000]
        await self.db.flush()
        return accepted

    async def _chain_position(self, seller_id: uuid.UUID) -> tuple[int, str]:
        """Next counter value and the hash it must chain onto.

        Locked for update: two concurrent sales by the same seller must not be
        handed the same counter, which would break the sequence irrecoverably.
        """
        last = (
            await self.db.execute(
                select(Invoice)
                .where(Invoice.seller_organization_id == seller_id)
                .order_by(Invoice.icv.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if last is None:
            return 1, GENESIS_HASH
        return last.icv + 1, last.invoice_hash

    async def pending_retries(self, limit: int = 50) -> list[Invoice]:
        result = await self.db.execute(
            select(Invoice)
            .where(Invoice.status.in_([InvoiceStatus.PENDING_CLEARANCE, InvoiceStatus.FAILED]))
            .order_by(Invoice.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_seller(self, seller_id: uuid.UUID) -> int:
        return (
            await self.db.execute(
                select(func.count())
                .select_from(Invoice)
                .where(Invoice.seller_organization_id == seller_id)
            )
        ).scalar_one()
