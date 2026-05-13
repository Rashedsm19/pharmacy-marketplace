"""
Inventory batch, near-expiry rules, and movement schemas.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from models.inventory import BatchStatus, MovementType


class BatchBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    branch_id: uuid.UUID
    product_id: uuid.UUID
    batch_number: str
    quantity: int = Field(ge=1)
    unit_cost: float | None = None
    expiry_date: date
    manufacture_date: date | None = None
    received_date: date | None = None
    supplier: str | None = None
    purchase_order_number: str | None = None
    is_opened: bool = False
    is_patient_dispensed: bool = False
    storage_condition_status: str = "compliant"
    storage_notes: str | None = None
    requires_cold_chain: bool = False
    notes: str | None = None


class BatchCreate(BatchBase):
    pass


class BatchUpdate(BaseModel):
    quantity: int | None = Field(None, ge=0)
    unit_cost: float | None = None
    supplier: str | None = None
    purchase_order_number: str | None = None
    is_opened: bool | None = None
    is_patient_dispensed: bool | None = None
    storage_condition_status: str | None = None
    storage_notes: str | None = None
    notes: str | None = None
    status: BatchStatus | None = None


class BatchOut(BatchBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    quantity_available: int
    status: BatchStatus
    days_until_expiry: int | None = None
    expiry_zone: str | None = None  # green / yellow / orange / red
    created_at: datetime
    updated_at: datetime


class BatchDetail(BatchOut):
    product_name: str | None = None
    product_name_ar: str | None = None
    product_sku: str | None = None
    branch_name: str | None = None
    category_name: str | None = None


class NearExpiryRuleBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    min_days_for_listing: int = Field(ge=1, default=30)
    yellow_threshold_days: int = Field(ge=1, default=180)
    orange_threshold_days: int = Field(ge=1, default=90)
    red_threshold_days: int = Field(ge=1, default=30)
    allow_auto_listing: bool = False
    auto_listing_discount_pct: float = Field(ge=0, le=100, default=20.0)
    notify_owner: bool = True
    notify_admin: bool = False


class NearExpiryRuleCreate(NearExpiryRuleBase):
    pass


class NearExpiryRuleUpdate(BaseModel):
    min_days_for_listing: int | None = Field(None, ge=1)
    yellow_threshold_days: int | None = Field(None, ge=1)
    orange_threshold_days: int | None = Field(None, ge=1)
    red_threshold_days: int | None = Field(None, ge=1)
    allow_auto_listing: bool | None = None
    auto_listing_discount_pct: float | None = Field(None, ge=0, le=100)
    notify_owner: bool | None = None
    notify_admin: bool | None = None


class NearExpiryRuleOut(NearExpiryRuleBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    movement_type: MovementType
    quantity_delta: int
    quantity_before: int
    quantity_after: int
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    notes: str | None = None
    created_at: datetime
