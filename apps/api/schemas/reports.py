"""
Report response schemas.
"""
from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class NearExpiryReportRow(BaseModel):
    batch_id: uuid.UUID
    product_name: str
    product_name_ar: str
    branch_name: str
    batch_number: str
    expiry_date: date
    days_until_expiry: int
    quantity: int
    expiry_zone: str
    estimated_value: float | None = None


class ExpiredLossReportRow(BaseModel):
    product_name: str
    product_name_ar: str
    branch_name: str
    batch_number: str
    expiry_date: date
    quantity_lost: int
    unit_cost: float | None = None
    total_loss: float | None = None


class RecoverableValueRow(BaseModel):
    expiry_zone: str
    batch_count: int
    total_quantity: int
    estimated_value: float
    potential_recovery_at_50_pct: float
    potential_recovery_at_30_pct: float


class TopProductRow(BaseModel):
    product_id: uuid.UUID
    product_name: str
    product_name_ar: str
    sku: str
    offer_count: int
    listing_count: int
    transaction_count: int
    total_value_traded: float


class BranchComparisonRow(BaseModel):
    branch_id: uuid.UUID
    branch_name: str
    total_batches: int
    near_expiry_batches: int
    expired_batches: int
    active_listings: int
    completed_transactions: int
    recovered_value: float
    loss_value: float
