"""
Schemas for the platform admin's cross-pharmacy views.

Each row names the pharmacy it belongs to, because that is the whole point of
these views: the org-scoped screens deliberately cannot show it.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class AdminBatchRow(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    branch_name: str | None = None
    product_name: str
    product_sku: str | None = None
    is_draft_product: bool = False
    product_source: str = "catalog"
    batch_number: str
    expiry_date: date
    days_remaining: int
    quantity: int
    quantity_available: int
    unit_cost: float | None = None
    status: str
    zone: str
    created_at: datetime


class AdminInventoryTotals(BaseModel):
    """The numbers the admin actually wants at a glance."""

    organizations: int
    batches: int
    units: int
    estimated_value: float
    near_expiry_batches: int
    expired_batches: int


class AdminInventoryOut(BaseModel):
    items: list[AdminBatchRow]
    total: int
    page: int
    page_size: int
    pages: int
    totals: AdminInventoryTotals


class AdminDraftProduct(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None = None
    organization_name: str | None = None
    name: str
    name_ar: str | None = None
    sku: str
    barcode: str | None = None
    category_name: str | None = None
    source: str
    batch_count: int
    created_at: datetime


class AdminDraftList(BaseModel):
    items: list[AdminDraftProduct]
    total: int
    page: int
    page_size: int
    pages: int


class PromoteDraftIn(BaseModel):
    """Optional corrections applied while joining the shared catalogue."""

    name: str | None = None
    name_ar: str | None = None
    sku: str | None = None
    barcode: str | None = None
    category_id: uuid.UUID | None = None


class AdminImportRow(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    created_by_name: str | None = None
    filename: str
    source: str
    status: str
    total_rows: int
    processed_rows: int
    created_batches: int
    updated_batches: int
    created_products: int
    failed_rows: int
    failure_reason: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AdminImportList(BaseModel):
    items: list[AdminImportRow]
    total: int
    page: int
    page_size: int
    pages: int
