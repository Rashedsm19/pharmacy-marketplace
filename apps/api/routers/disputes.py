"""Disputes router — raise, evidence, respond, resolve."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove, SuperAdmin
from models.dispute import Dispute, DisputeStatus
from models.transaction import Transaction
from models.user import UserRole
from repositories.organization import MembershipRepository
from schemas.common import PaginatedResponse
from schemas.dispute import DisputeCreate, DisputeOut, DisputeResolve, DisputeRespond
from services.dispute_service import DisputeService

router = APIRouter(prefix="/disputes", tags=["Disputes"])


async def _org_id(current_user, db) -> uuid.UUID:
    org_id = await MembershipRepository(db).get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization")
    return org_id


async def _reload(db, dispute_id: uuid.UUID) -> Dispute:
    """Re-select so the selectin chains (transaction → listing → batch → product)
    are populated. A freshly added instance has them unloaded, and touching one
    during serialization would attempt IO outside the async context."""
    dispute = (
        await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    ).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="النزاع غير موجود")
    return dispute


def _to_out(dispute: Dispute) -> DisputeOut:
    out = DisputeOut.model_validate(dispute)
    tx = dispute.transaction
    if tx is not None:
        out.transaction_reference = tx.reference_number
        listing = tx.listing
        if listing is not None and listing.batch is not None and listing.batch.product is not None:
            product = listing.batch.product
            out.product_name_ar = product.name_ar or product.name
    org = dispute.raised_by_organization
    if org is not None:
        out.raised_by_org_name = org.name_ar or org.name
    return out


@router.post("", response_model=DisputeOut, status_code=201)
async def open_dispute(
    data: DisputeCreate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _org_id(current_user, db)
    dispute = await DisputeService(db).open_dispute(
        transaction_id=data.transaction_id,
        org_id=org_id,
        actor_id=current_user.id,
        reason=data.reason,
        description=data.description,
        disputed_quantity=data.disputed_quantity,
        ip_address=request.client.host if request.client else None,
    )
    return _to_out(await _reload(db, dispute.id))


@router.get("", response_model=PaginatedResponse[DisputeOut])
async def list_my_disputes(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
):
    """Cases on transactions this organization is a party to — either side."""
    org_id = await _org_id(current_user, db)
    clause = (
        select(Dispute)
        .join(Transaction, Transaction.id == Dispute.transaction_id)
        .where(
            (Transaction.buyer_organization_id == org_id)
            | (Transaction.seller_organization_id == org_id)
        )
    )
    rows = (
        await db.execute(
            clause.order_by(Dispute.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    total = len((await db.execute(clause)).scalars().all())
    return PaginatedResponse(
        items=[_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/queue", response_model=PaginatedResponse[DisputeOut])
async def admin_queue(
    db: DbSession,
    current_user: SuperAdmin,
    page: int = 1,
    page_size: int = 20,
):
    """Unresolved cases awaiting a platform decision."""
    clause = select(Dispute).where(
        Dispute.status.in_([DisputeStatus.OPEN, DisputeStatus.SELLER_RESPONDED])
    )
    rows = (
        await db.execute(
            clause.order_by(Dispute.created_at.asc())  # oldest first: it has waited longest
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    total = len((await db.execute(clause)).scalars().all())
    return PaginatedResponse(
        items=[_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{dispute_id}", response_model=DisputeOut)
async def get_dispute(dispute_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    dispute = (
        await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    ).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="النزاع غير موجود")

    if current_user.role != UserRole.SUPER_ADMIN:
        org_id = await _org_id(current_user, db)
        tx = dispute.transaction
        if org_id not in (tx.buyer_organization_id, tx.seller_organization_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _to_out(dispute)


@router.post("/{dispute_id}/evidence", response_model=DisputeOut)
async def upload_evidence(
    dispute_id: uuid.UUID,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    file: UploadFile = File(...),
):
    """A photo or document supporting the claim — same validation as licences."""
    from services.storage_service import storage_service

    org_id = await _org_id(current_user, db)
    dispute = (
        await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    ).scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="النزاع غير موجود")

    tx = dispute.transaction
    if org_id not in (tx.buyer_organization_id, tx.seller_organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    dispute.evidence_url = await storage_service.save_document(file, org_id, "dispute")
    await db.flush()
    return _to_out(await _reload(db, dispute.id))


@router.post("/{dispute_id}/respond", response_model=DisputeOut)
async def respond(
    dispute_id: uuid.UUID,
    data: DisputeRespond,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _org_id(current_user, db)
    dispute = await DisputeService(db).respond(
        dispute_id=dispute_id,
        org_id=org_id,
        actor_id=current_user.id,
        response=data.response,
        ip_address=request.client.host if request.client else None,
    )
    return _to_out(await _reload(db, dispute.id))


@router.post("/{dispute_id}/resolve", response_model=DisputeOut)
async def resolve(
    dispute_id: uuid.UUID,
    data: DisputeResolve,
    db: DbSession,
    current_user: SuperAdmin,
    request: Request,
):
    dispute = await DisputeService(db).resolve(
        dispute_id=dispute_id,
        actor_id=current_user.id,
        outcome=data.outcome,
        notes=data.notes,
        ip_address=request.client.host if request.client else None,
    )
    return _to_out(await _reload(db, dispute.id))
