"""
Transaction schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.transaction import TransactionStatus


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    reservation_id: uuid.UUID | None = None
    seller_organization_id: uuid.UUID
    buyer_organization_id: uuid.UUID
    quantity: int
    unit_price: float
    total_amount: float
    platform_fee: float
    net_amount: float
    status: TransactionStatus
    reference_number: str
    dispatched_at: datetime | None = None
    received_at: datetime | None = None
    completed_at: datetime | None = None
    delivery_tracking_number: str | None = None
    seller_notes: str | None = None
    buyer_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class TransactionDetail(TransactionOut):
    product_name: str | None = None
    product_name_ar: str | None = None
    seller_org_name: str | None = None
    buyer_org_name: str | None = None
    batch_number: str | None = None


class DispatchRequest(BaseModel):
    delivery_tracking_number: str | None = None
    seller_notes: str | None = None


class ReceiptConfirmRequest(BaseModel):
    buyer_notes: str | None = None


class DisputeRequest(BaseModel):
    reason: str
