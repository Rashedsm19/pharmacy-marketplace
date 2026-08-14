"""
Inventory import job schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ImportRowError(BaseModel):
    line: int
    reason: str
    product_name: str | None = None
    batch_number: str | None = None


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    filename: str
    source: str
    status: str

    total_rows: int
    processed_rows: int
    created_batches: int
    updated_batches: int
    created_products: int
    matched_products: int
    failed_rows: int

    errors: list[ImportRowError] | None = None
    failure_reason: str | None = None
    has_error_file: bool = False

    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class ImportJobList(BaseModel):
    items: list[ImportJobOut]
    total: int
    page: int
    page_size: int


class ImportCapacity(BaseModel):
    """What the pharmacy may still add, shown before an upload starts."""

    used: int
    limit: int
    remaining: int
