"""Invoices router — list, view, download the cleared document."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, select

from dependencies import CurrentUser, DbSession, SuperAdmin
from models.invoice import Invoice
from models.user import UserRole
from repositories.organization import MembershipRepository
from schemas.common import PaginatedResponse
from schemas.invoice import InvoiceOut

router = APIRouter(prefix="/invoices", tags=["Invoices"])


async def _org_id(current_user, db) -> uuid.UUID:
    org_id = await MembershipRepository(db).get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization")
    return org_id


def _to_out(invoice: Invoice) -> InvoiceOut:
    out = InvoiceOut.model_validate(invoice)
    if invoice.seller_organization is not None:
        out.seller_name = (
            invoice.seller_organization.name_ar or invoice.seller_organization.name
        )
    if invoice.buyer_organization is not None:
        out.buyer_name = invoice.buyer_organization.name_ar or invoice.buyer_organization.name
    if invoice.transaction is not None:
        out.transaction_reference = invoice.transaction.reference_number
    return out


async def _visible(db, invoice_id: uuid.UUID, current_user) -> Invoice:
    invoice = (
        await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الفاتورة غير موجودة")
    if current_user.role != UserRole.SUPER_ADMIN:
        org_id = await _org_id(current_user, db)
        if org_id not in (invoice.seller_organization_id, invoice.buyer_organization_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return invoice


@router.get("", response_model=PaginatedResponse[InvoiceOut])
async def list_invoices(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
):
    """Invoices this organization issued or received."""
    org_id = await _org_id(current_user, db)
    clause = select(Invoice).where(
        (Invoice.seller_organization_id == org_id)
        | (Invoice.buyer_organization_id == org_id)
    )
    total = (
        await db.execute(select(func.count()).select_from(clause.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            clause.order_by(Invoice.issued_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return PaginatedResponse(
        items=[_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(invoice_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    return _to_out(await _visible(db, invoice_id, current_user))


@router.get("/{invoice_id}/xml")
async def download_xml(invoice_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    """The signed UBL document itself — what the authority holds."""
    invoice = await _visible(db, invoice_id, current_user)
    return Response(
        content=invoice.xml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{invoice.invoice_number}.xml"'
        },
    )


@router.get("/admin/failed", response_model=PaginatedResponse[InvoiceOut])
async def failed_clearances(
    db: DbSession,
    current_user: SuperAdmin,
    page: int = 1,
    page_size: int = 50,
):
    """Invoices the authority has not accepted — the queue to chase."""
    from models.invoice import InvoiceStatus

    clause = select(Invoice).where(
        Invoice.status.in_([InvoiceStatus.FAILED, InvoiceStatus.PENDING_CLEARANCE])
    )
    total = (
        await db.execute(select(func.count()).select_from(clause.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            clause.order_by(Invoice.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return PaginatedResponse(
        items=[_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )
