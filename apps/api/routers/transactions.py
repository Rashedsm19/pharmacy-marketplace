"""Transactions router."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove
from repositories.organization import MembershipRepository
from repositories.transaction import TransactionRepository
from schemas.common import PaginatedResponse
from schemas.transaction import DispatchRequest, ReceiptConfirmRequest, TransactionDetail, TransactionOut
from services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions"])


async def _get_org_id(current_user, db) -> uuid.UUID:
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization")
    return org_id


@router.get("", response_model=PaginatedResponse[TransactionOut])
async def list_transactions(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
):
    org_id = await _get_org_id(current_user, db)
    repo = TransactionRepository(db)
    rows, total = await repo.list_by_org(
        org_id, offset=(page - 1) * page_size, limit=page_size
    )
    return PaginatedResponse(
        items=[TransactionOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/from-reservation/{reservation_id}", response_model=TransactionOut, status_code=201)
async def create_from_reservation(
    reservation_id: uuid.UUID,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _get_org_id(current_user, db)
    svc = TransactionService(db)
    tx = await svc.create_from_reservation(
        reservation_id, org_id, current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    return TransactionOut.model_validate(tx)


@router.get("/{tx_id}", response_model=TransactionDetail)
async def get_transaction(tx_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    org_id = await _get_org_id(current_user, db)
    repo = TransactionRepository(db)
    tx = await repo.get(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.seller_organization_id != org_id and tx.buyer_organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return TransactionDetail(
        **TransactionOut.model_validate(tx).model_dump(),
        product_name=tx.listing.batch.product.name if tx.listing and tx.listing.batch else None,
        product_name_ar=tx.listing.batch.product.name_ar if tx.listing and tx.listing.batch else None,
        seller_org_name=tx.seller_organization.name if tx.seller_organization else None,
        buyer_org_name=tx.buyer_organization.name if tx.buyer_organization else None,
        batch_number=tx.listing.batch.batch_number if tx.listing and tx.listing.batch else None,
    )


@router.post("/{tx_id}/dispatch", response_model=TransactionOut)
async def dispatch_transaction(
    tx_id: uuid.UUID,
    data: DispatchRequest,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _get_org_id(current_user, db)
    svc = TransactionService(db)
    tx = await svc.dispatch(
        tx_id, org_id, current_user.id,
        tracking_number=data.delivery_tracking_number,
        seller_notes=data.seller_notes,
        ip_address=request.client.host if request.client else None,
    )
    return TransactionOut.model_validate(tx)


@router.post("/{tx_id}/confirm-receipt", response_model=TransactionOut)
async def confirm_receipt(
    tx_id: uuid.UUID,
    data: ReceiptConfirmRequest,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _get_org_id(current_user, db)
    svc = TransactionService(db)
    tx = await svc.confirm_receipt(
        tx_id, org_id, current_user.id,
        buyer_notes=data.buyer_notes,
        ip_address=request.client.host if request.client else None,
    )
    return TransactionOut.model_validate(tx)
