"""Inventory router — batch CRUD, FEFO, near-expiry filter."""
from __future__ import annotations

import math
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Request, status

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove
from repositories.inventory import InventoryBatchRepository, InventoryMovementRepository, NearExpiryRuleRepository
from repositories.organization import MembershipRepository
from schemas.common import PaginatedResponse
from schemas.inventory import (
    BatchCreate,
    BatchDetail,
    BatchOut,
    BatchUpdate,
    MovementOut,
    NearExpiryRuleCreate,
    NearExpiryRuleOut,
)
from services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


async def _require_org(current_user, db) -> uuid.UUID:
    from models.user import UserRole
    if current_user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Use org_id param for super admin")
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization")
    return org_id


@router.get("/batches", response_model=PaginatedResponse[BatchDetail])
async def list_batches(
    db: DbSession,
    current_user: CurrentUser,
    branch_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    near_expiry_only: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    org_id = await _require_org(current_user, db)
    repo = InventoryBatchRepository(db)
    svc = InventoryService(db)

    from models.inventory import BatchStatus
    batch_status = None
    if status_filter:
        try:
            batch_status = BatchStatus(status_filter)
        except ValueError:
            pass

    expiry_before = None
    if near_expiry_only:
        expiry_before = date.today() + __import__("datetime").timedelta(days=180)

    rows, total = await repo.list_by_org(
        org_id,
        branch_id=branch_id,
        status=batch_status,
        expiry_before=expiry_before,
        offset=(page - 1) * page_size,
        limit=page_size,
    )

    items = []
    for b in rows:
        enriched = svc.enrich_batch(b)
        detail = BatchDetail(
            id=b.id,
            organization_id=b.organization_id,
            branch_id=b.branch_id,
            product_id=b.product_id,
            batch_number=b.batch_number,
            quantity=b.quantity,
            quantity_available=b.quantity_available,
            unit_cost=float(b.unit_cost) if b.unit_cost else None,
            expiry_date=b.expiry_date,
            manufacture_date=b.manufacture_date,
            received_date=b.received_date,
            supplier=b.supplier,
            purchase_order_number=b.purchase_order_number,
            is_opened=b.is_opened,
            is_patient_dispensed=b.is_patient_dispensed,
            storage_condition_status=b.storage_condition_status,
            storage_notes=b.storage_notes,
            requires_cold_chain=b.requires_cold_chain,
            notes=b.notes,
            status=b.status,
            created_at=b.created_at,
            updated_at=b.updated_at,
            **enriched,
            product_name=b.product.name if b.product else None,
            product_name_ar=b.product.name_ar if b.product else None,
            product_sku=b.product.sku if b.product else None,
            branch_name=b.branch.name if b.branch else None,
            category_name=b.product.category.name if b.product and b.product.category else None,
        )
        items.append(detail)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/batches", response_model=BatchOut, status_code=201)
async def create_batch(
    data: BatchCreate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    org_id = await _require_org(current_user, db)
    svc = InventoryService(db)
    batch = await svc.create_batch(data, org_id, current_user.id)
    enriched = svc.enrich_batch(batch)
    return BatchOut(
        id=batch.id,
        organization_id=batch.organization_id,
        branch_id=batch.branch_id,
        product_id=batch.product_id,
        batch_number=batch.batch_number,
        quantity=batch.quantity,
        quantity_available=batch.quantity_available,
        unit_cost=float(batch.unit_cost) if batch.unit_cost else None,
        expiry_date=batch.expiry_date,
        manufacture_date=batch.manufacture_date,
        received_date=batch.received_date,
        supplier=batch.supplier,
        purchase_order_number=batch.purchase_order_number,
        is_opened=batch.is_opened,
        is_patient_dispensed=batch.is_patient_dispensed,
        storage_condition_status=batch.storage_condition_status,
        storage_notes=batch.storage_notes,
        requires_cold_chain=batch.requires_cold_chain,
        notes=batch.notes,
        status=batch.status,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        **enriched,
    )


@router.get("/batches/{batch_id}", response_model=BatchDetail)
async def get_batch(batch_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    org_id = await _require_org(current_user, db)
    repo = InventoryBatchRepository(db)
    batch = await repo.get_by_org(batch_id, org_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    svc = InventoryService(db)
    enriched = svc.enrich_batch(batch)
    return BatchDetail(
        id=batch.id,
        organization_id=batch.organization_id,
        branch_id=batch.branch_id,
        product_id=batch.product_id,
        batch_number=batch.batch_number,
        quantity=batch.quantity,
        quantity_available=batch.quantity_available,
        unit_cost=float(batch.unit_cost) if batch.unit_cost else None,
        expiry_date=batch.expiry_date,
        manufacture_date=batch.manufacture_date,
        received_date=batch.received_date,
        supplier=batch.supplier,
        purchase_order_number=batch.purchase_order_number,
        is_opened=batch.is_opened,
        is_patient_dispensed=batch.is_patient_dispensed,
        storage_condition_status=batch.storage_condition_status,
        storage_notes=batch.storage_notes,
        requires_cold_chain=batch.requires_cold_chain,
        notes=batch.notes,
        status=batch.status,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        **enriched,
        product_name=batch.product.name if batch.product else None,
        product_name_ar=batch.product.name_ar if batch.product else None,
        product_sku=batch.product.sku if batch.product else None,
        branch_name=batch.branch.name if batch.branch else None,
        category_name=batch.product.category.name if batch.product and batch.product.category else None,
    )


@router.patch("/batches/{batch_id}", response_model=BatchOut)
async def update_batch(
    batch_id: uuid.UUID,
    data: BatchUpdate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    org_id = await _require_org(current_user, db)
    repo = InventoryBatchRepository(db)
    batch = await repo.get_by_org(batch_id, org_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(batch, k, v)
    await db.flush()
    svc = InventoryService(db)
    enriched = svc.enrich_batch(batch)
    return BatchOut(
        id=batch.id, organization_id=batch.organization_id, branch_id=batch.branch_id,
        product_id=batch.product_id, batch_number=batch.batch_number, quantity=batch.quantity,
        quantity_available=batch.quantity_available,
        unit_cost=float(batch.unit_cost) if batch.unit_cost else None,
        expiry_date=batch.expiry_date, manufacture_date=batch.manufacture_date,
        received_date=batch.received_date, supplier=batch.supplier,
        purchase_order_number=batch.purchase_order_number, is_opened=batch.is_opened,
        is_patient_dispensed=batch.is_patient_dispensed,
        storage_condition_status=batch.storage_condition_status,
        storage_notes=batch.storage_notes, requires_cold_chain=batch.requires_cold_chain,
        notes=batch.notes, status=batch.status, created_at=batch.created_at,
        updated_at=batch.updated_at, **enriched,
    )


@router.get("/batches/{batch_id}/fefo", response_model=list[BatchOut])
async def get_fefo_recommendation(
    batch_id: uuid.UUID, db: DbSession, current_user: CurrentUser
):
    org_id = await _require_org(current_user, db)
    repo = InventoryBatchRepository(db)
    batch = await repo.get_by_org(batch_id, org_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    fefo_batches = await repo.get_fefo_batches(org_id, batch.product_id, batch.branch_id)
    svc = InventoryService(db)
    results = []
    for b in fefo_batches:
        enriched = svc.enrich_batch(b)
        results.append(BatchOut(
            id=b.id, organization_id=b.organization_id, branch_id=b.branch_id,
            product_id=b.product_id, batch_number=b.batch_number, quantity=b.quantity,
            quantity_available=b.quantity_available,
            unit_cost=float(b.unit_cost) if b.unit_cost else None,
            expiry_date=b.expiry_date, manufacture_date=b.manufacture_date,
            received_date=b.received_date, supplier=b.supplier,
            purchase_order_number=b.purchase_order_number, is_opened=b.is_opened,
            is_patient_dispensed=b.is_patient_dispensed,
            storage_condition_status=b.storage_condition_status,
            storage_notes=b.storage_notes, requires_cold_chain=b.requires_cold_chain,
            notes=b.notes, status=b.status, created_at=b.created_at,
            updated_at=b.updated_at, **enriched,
        ))
    return results


@router.get("/near-expiry", response_model=list[BatchDetail])
async def list_near_expiry(
    db: DbSession,
    current_user: CurrentUser,
    days: int = 180,
):
    org_id = await _require_org(current_user, db)
    from datetime import timedelta
    threshold = date.today() + timedelta(days=days)
    repo = InventoryBatchRepository(db)
    batches = await repo.list_near_expiry(threshold, org_id)
    svc = InventoryService(db)
    results = []
    for b in batches:
        enriched = svc.enrich_batch(b)
        results.append(BatchDetail(
            id=b.id, organization_id=b.organization_id, branch_id=b.branch_id,
            product_id=b.product_id, batch_number=b.batch_number, quantity=b.quantity,
            quantity_available=b.quantity_available,
            unit_cost=float(b.unit_cost) if b.unit_cost else None,
            expiry_date=b.expiry_date, manufacture_date=b.manufacture_date,
            received_date=b.received_date, supplier=b.supplier,
            purchase_order_number=b.purchase_order_number, is_opened=b.is_opened,
            is_patient_dispensed=b.is_patient_dispensed,
            storage_condition_status=b.storage_condition_status,
            storage_notes=b.storage_notes, requires_cold_chain=b.requires_cold_chain,
            notes=b.notes, status=b.status, created_at=b.created_at,
            updated_at=b.updated_at, **enriched,
            product_name=b.product.name if b.product else None,
            product_name_ar=b.product.name_ar if b.product else None,
            product_sku=b.product.sku if b.product else None,
            branch_name=b.branch.name if b.branch else None,
            category_name=b.product.category.name if b.product and b.product.category else None,
        ))
    return results


@router.get("/rules", response_model=NearExpiryRuleOut)
async def get_near_expiry_rules(db: DbSession, current_user: CurrentUser):
    org_id = await _require_org(current_user, db)
    repo = NearExpiryRuleRepository(db)
    rule = await repo.get_by_org(org_id)
    if not rule:
        raise HTTPException(status_code=404, detail="No near-expiry rules configured")
    return NearExpiryRuleOut.model_validate(rule)


@router.put("/rules", response_model=NearExpiryRuleOut)
async def upsert_near_expiry_rules(
    data: NearExpiryRuleCreate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    org_id = await _require_org(current_user, db)
    repo = NearExpiryRuleRepository(db)
    rule = await repo.get_by_org(org_id)
    if rule:
        for k, v in data.model_dump().items():
            setattr(rule, k, v)
        await db.flush()
    else:
        from models.inventory import NearExpiryRule
        rule = NearExpiryRule(id=uuid.uuid4(), organization_id=org_id, **data.model_dump())
        db.add(rule)
        await db.flush()
    return NearExpiryRuleOut.model_validate(rule)


@router.get("/batches/{batch_id}/movements", response_model=PaginatedResponse[MovementOut])
async def list_batch_movements(
    batch_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
):
    org_id = await _require_org(current_user, db)
    repo = InventoryMovementRepository(db)
    rows, total = await repo.list_by_batch(batch_id, org_id, offset=(page - 1) * page_size, limit=page_size)
    return PaginatedResponse(
        items=[MovementOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )
