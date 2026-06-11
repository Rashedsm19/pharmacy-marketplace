"""Inventory service — batch CRUD, FEFO, near-expiry."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.inventory import BatchStatus, InventoryBatch, InventoryMovement, MovementType
from repositories.inventory import InventoryBatchRepository, InventoryMovementRepository, NearExpiryRuleRepository
from repositories.branch import BranchRepository
from repositories.product import ProductRepository
from schemas.inventory import BatchCreate


class InventoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.batch_repo = InventoryBatchRepository(db)
        self.movement_repo = InventoryMovementRepository(db)
        self.rule_repo = NearExpiryRuleRepository(db)
        self.branch_repo = BranchRepository(db)
        self.product_repo = ProductRepository(db)

    async def create_batch(
        self, data: BatchCreate, org_id: uuid.UUID, created_by: uuid.UUID
    ) -> InventoryBatch:
        # Verify branch belongs to org
        branch = await self.branch_repo.get_by_org(data.branch_id, org_id)
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branch not found",
            )
        if not branch.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Branch is not active",
            )

        # Verify product exists and is active
        from sqlalchemy import select
        from models.product import Product
        result = await self.db.execute(
            select(Product).where(Product.id == data.product_id, Product.is_active.is_(True))
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found or inactive",
            )

        today = date.today()
        if data.expiry_date <= today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expiry date must be in the future",
            )

        batch = InventoryBatch(
            id=uuid.uuid4(),
            organization_id=org_id,
            branch_id=data.branch_id,
            product_id=data.product_id,
            batch_number=data.batch_number,
            quantity=data.quantity,
            quantity_available=data.quantity,
            unit_cost=data.unit_cost,
            expiry_date=data.expiry_date,
            manufacture_date=data.manufacture_date,
            received_date=data.received_date or today,
            supplier=data.supplier,
            purchase_order_number=data.purchase_order_number,
            is_opened=data.is_opened,
            is_patient_dispensed=data.is_patient_dispensed,
            storage_condition_status=data.storage_condition_status,
            storage_notes=data.storage_notes,
            requires_cold_chain=data.requires_cold_chain,
            notes=data.notes,
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        await self.db.flush()

        # Record movement
        movement = InventoryMovement(
            id=uuid.uuid4(),
            organization_id=org_id,
            batch_id=batch.id,
            movement_type=MovementType.RECEIVED,
            quantity_delta=data.quantity,
            quantity_before=0,
            quantity_after=data.quantity,
            performed_by_id=created_by,
            notes="Initial batch receipt",
        )
        self.db.add(movement)
        await self.db.flush()

        return batch

    def _compute_expiry_zone(self, days: int) -> str:
        if days > 180:
            return "green"
        elif days > 90:
            return "yellow"
        elif days > 30:
            return "orange"
        else:
            return "red"

    def enrich_batch(self, batch: InventoryBatch) -> dict:
        today = date.today()
        days = (batch.expiry_date - today).days
        return {
            "days_until_expiry": days,
            "expiry_zone": self._compute_expiry_zone(days),
        }
