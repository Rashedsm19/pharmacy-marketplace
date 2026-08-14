"""
Schemas for the external integration API.

These are the contract a customer's own system writes against, so the field
names are plain English and the shape is deliberately flat — a row of their
stock, not our internal model.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ExternalHealth(BaseModel):
    status: str = "ok"
    organization_id: uuid.UUID
    organization_name: str
    scopes: list[str]
    server_time: datetime


class InventoryItemIn(BaseModel):
    """One line of the customer's stock."""

    model_config = ConfigDict(extra="ignore")

    product_name: str = Field(min_length=1, max_length=255)
    batch_number: str = Field(min_length=1, max_length=100)
    expiry_date: date
    quantity: int = Field(ge=0)

    barcode: str | None = Field(default=None, max_length=100)
    sku: str | None = Field(default=None, max_length=100)
    unit_cost: float | None = Field(default=None, ge=0)
    branch_name: str | None = None
    supplier: str | None = None
    purchase_order_number: str | None = None
    requires_cold_chain: bool = False
    notes: str | None = None


class InventorySyncIn(BaseModel):
    items: list[InventoryItemIn] = Field(min_length=1, max_length=500)


class SyncItemError(BaseModel):
    index: int
    reason: str
    product_name: str | None = None
    batch_number: str | None = None


class InventorySyncOut(BaseModel):
    job_id: uuid.UUID
    received: int
    created_batches: int
    updated_batches: int
    created_products: int
    matched_products: int
    failed: int
    errors: list[SyncItemError] = []


class NearExpiryItem(BaseModel):
    batch_id: uuid.UUID
    product_name: str
    product_name_ar: str | None = None
    sku: str | None = None
    barcode: str | None = None
    batch_number: str
    branch_name: str | None = None
    expiry_date: date
    days_remaining: int
    quantity: int
    quantity_available: int
    unit_cost: float | None = None
    status: str
    # green | yellow | orange | red — the same bands the dashboard uses.
    zone: str


class NearExpiryOut(BaseModel):
    total: int
    within_days: int
    items: list[NearExpiryItem]


class ExternalListing(BaseModel):
    """One of the pharmacy's own listings, as its system would show it."""

    listing_id: uuid.UUID
    title: str
    product_name: str | None = None
    batch_number: str | None = None
    expiry_date: date | None = None
    quantity_listed: int
    quantity_available: int
    asking_price: float
    status: str
    view_count: int
    offer_count: int
    expires_at: datetime | None = None
    created_at: datetime


class ExternalListingsOut(BaseModel):
    total: int
    items: list[ExternalListing]
