"""
Branch schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.branch import StorageConditionStatus


class BranchBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    name_ar: str | None = None
    branch_code: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    phone: str | None = None
    manager_name: str | None = None
    cold_chain_available: bool = False
    narcotics_license: bool = False


class BranchCreate(BranchBase):
    organization_id: uuid.UUID | None = None  # injected from token if omitted


class BranchUpdate(BaseModel):
    name: str | None = None
    name_ar: str | None = None
    branch_code: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    phone: str | None = None
    manager_name: str | None = None
    is_active: bool | None = None
    cold_chain_available: bool | None = None
    narcotics_license: bool | None = None
    storage_condition_status: StorageConditionStatus | None = None
    storage_notes: str | None = None


class BranchOut(BranchBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    storage_condition_status: StorageConditionStatus
    storage_notes: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime
    updated_at: datetime
